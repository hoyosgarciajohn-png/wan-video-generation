import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from deployment.build_verify import allowed_source, daemon_environment, digest, execute, local_daemon, prepare, verify_context, verify_fixture


class BuildVerificationTests(unittest.TestCase):
    def test_context_excludes_generated_private_and_model_bytes(self):
        for target in ['cpu', 'gpu']:
            for path in ['.env', 'workers/gpu/.env.secret', 'workers/gpu/weights/model.pth',
                         'workers/gpu/model.safetensors', 'apps/studio/node_modules/a.js',
                         'apps/studio/dist/index.html', 'private/tokens.json', 'studio.sqlite']:
                self.assertFalse(allowed_source(path, target), (path, target))
            self.assertTrue(allowed_source('workers/gpu/model.lock.json', target))
        self.assertFalse(allowed_source('apps/studio/src/App.tsx', 'gpu'))
        self.assertTrue(allowed_source('scripts/validate_contract.py', 'cpu'))
        self.assertTrue(allowed_source('src/wan_platform/fake_provider.py', 'cpu'))
        self.assertFalse(allowed_source('src/wan_platform/fake_provider.py', 'gpu'))

    def test_plan_never_calls_docker_and_reports_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            original_run = subprocess.run
            def git_only(command, *args, **kwargs):
                self.assertEqual(command[0], 'git')
                return original_run(command, *args, **kwargs)
            with patch('deployment.build_verify.shutil.which', return_value=None), patch('deployment.build_verify.subprocess.run', side_effect=git_only):
                output, manifest = prepare('cpu', Path(directory) / 'evidence')
            self.assertEqual(manifest['mode'], 'PLAN_ONLY')
            self.assertTrue(all(value == 'UNVERIFIED' for value in manifest['gates'].values()))
            self.assertIsNone(manifest['image_id'])
            self.assertEqual(manifest['executed_commands'], [])
            for item in manifest['planned_commands']:
                self.assertNotIn('--gpus', item['argv'])
                if item['argv'][1] == 'run':
                    self.assertIn('runc', item['argv'])
                    self.assertIn('NVIDIA_VISIBLE_DEVICES=void', item['argv'])
            self.assertTrue((output / 'context/scripts/validate_contract.py').is_file())
            self.assertFalse((output / 'context/apps/studio/node_modules').exists())
            self.assertEqual(json.loads((output / 'manifest.json').read_text()), manifest)
            with self.assertRaises(ValueError):
                prepare('cpu', output)

    def test_remote_daemons_and_emulation_are_refused(self):
        for endpoint in ['ssh://builder', 'tcp://127.0.0.1:2375', 'tcp://remote:2376', 'npipe://engine']:
            with self.assertRaises(ValueError):
                local_daemon({'DOCKER_HOST': endpoint}, run=lambda *_args, **_kwargs: self.fail('remote probe forbidden'))
        def arm(command, **_):
            return '"unix:///run/docker.sock"' if command[1] == 'context' else 'linux/arm64'
        with self.assertRaises(ValueError):
            local_daemon({}, run=arm)
        def amd(command, **_):
            return '"unix:///run/docker.sock"' if command[1] == 'context' else 'linux/amd64'
        self.assertEqual(local_daemon({}, run=amd), 'unix:///run/docker.sock')

    def test_remote_context_cannot_override_a_local_host_environment(self):
        with self.assertRaises(ValueError):
            local_daemon({'DOCKER_HOST': 'unix:///run/docker.sock', 'DOCKER_CONTEXT': 'remote'},
                         run=lambda command, **kwargs: '"ssh://remote"')
        environment = daemon_environment('unix:///run/docker.sock', {'DOCKER_CONTEXT': 'remote', 'DOCKER_TLS_VERIFY': '1'})
        self.assertNotIn('DOCKER_CONTEXT', environment)
        self.assertNotIn('DOCKER_TLS_VERIFY', environment)
        self.assertEqual(environment['DOCKER_HOST'], 'unix:///run/docker.sock')

    def test_unavailable_docker_cannot_pass_build_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = {'source_dirty': False, 'docker_executable': None, 'gates': {'image_build': 'UNVERIFIED'}}
            with patch('deployment.build_verify.subprocess.check_output', return_value=b''), patch('deployment.build_verify.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError, 'Docker unavailable'):
                    execute(Path(directory), manifest)
                run.assert_not_called()
            self.assertEqual(manifest['gates']['image_build'], 'UNVERIFIED')

    def test_mutated_prepared_context_is_refused_before_daemon_access(self):
        with tempfile.TemporaryDirectory() as directory:
            output, manifest = prepare('cpu', Path(directory) / 'evidence')
            manifest['source_dirty'] = False
            manifest['docker_executable'] = 'docker'
            (output / 'context/scripts/validate_contract.py').write_text('changed')
            with patch('deployment.build_verify.subprocess.check_output', return_value=b''), patch('deployment.build_verify.local_daemon') as daemon:
                with self.assertRaisesRegex(ValueError, 'source bytes changed'):
                    execute(output, manifest)
                daemon.assert_not_called()
            self.assertEqual(manifest['gates']['image_build'], 'UNVERIFIED')

    def test_mock_execution_pins_smokes_to_build_image_id(self):
        with tempfile.TemporaryDirectory() as directory:
            output, manifest = prepare('cpu', Path(directory) / 'evidence')
            manifest['source_dirty'] = False
            manifest['docker_executable'] = 'docker'
            image_id = 'sha256:' + 'a' * 64
            def fake_run(argv, **kwargs):
                if argv[1] == 'build':
                    Path(argv[argv.index('--iidfile') + 1]).write_text(image_id)
                elif argv[1] == 'image':
                    self.assertEqual(argv[-1], image_id)
                    kwargs['stdout'].write(json.dumps([{'Id': image_id, 'Architecture': 'amd64', 'Os': 'linux', 'RepoDigests': []}]))
                else:
                    self.assertIn(image_id, argv)
                    self.assertNotIn(manifest['image_tag'], argv)
                    self.assertEqual(kwargs['env']['DOCKER_HOST'], 'unix:///run/docker.sock')
                    if 'workers.gpu.cli' in argv:
                        fixture = output / 'fixture'
                        asset = fixture / 'clip.mp4'
                        asset.write_bytes(b'fictional mock output')
                        (fixture / 'result.json').write_text(json.dumps({'contract_version': '0.1.0',
                            'asset': {'id': 'a', 'object_key': asset.name, 'bytes': asset.stat().st_size, 'sha256': digest(asset)},
                            'take': {'asset_id': 'a'}, 'media': {'duration_ms': 2000}, 'metrics': {'mode': 'fixture', 'cost_cents': 0}}))
                return subprocess.CompletedProcess(argv, 0)
            with patch('deployment.build_verify.subprocess.check_output', return_value=b''), patch('deployment.build_verify.local_daemon', return_value='unix:///run/docker.sock'), patch('deployment.build_verify.subprocess.run', side_effect=fake_run):
                result = execute(output, manifest)
            self.assertEqual(result['image_id'], image_id)
            self.assertEqual(result['gates']['fixture_smoke'], 'PASS')
            self.assertEqual(result['gates']['cuda_inference'], 'UNVERIFIED')
            self.assertEqual(result['gates']['hosted_deployment'], 'UNVERIFIED')

    def test_fixture_result_requires_matching_output_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            fixture = output / 'fixture'
            fixture.mkdir()
            clip = fixture / 'fictional.mp4'
            clip.write_bytes(b'fictional-test-bytes')
            result = {'contract_version': '0.1.0', 'asset': {'id': 'a', 'object_key': clip.name,
                      'bytes': clip.stat().st_size, 'sha256': digest(clip)}, 'take': {'asset_id': 'a'},
                      'media': {'duration_ms': 2000}, 'metrics': {'mode': 'fixture', 'cost_cents': 0}}
            (fixture / 'result.json').write_text(json.dumps(result))
            self.assertEqual(verify_fixture(output)['asset_sha256'], digest(clip))
            clip.write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                verify_fixture(output)


if __name__ == '__main__':
    unittest.main()
