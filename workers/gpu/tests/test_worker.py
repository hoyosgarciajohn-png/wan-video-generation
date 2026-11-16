import copy
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from workers.gpu.cli import FixtureClient, fixture_claim
from workers.gpu.common import LOCK, frame_count, scoped, utcnow, validate_claim
from workers.gpu.worker import LeaseLost, run_once
from workers.gpu.weights import verify
from workers.gpu.client import WorkerClient, WorkerAPIError


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.claim = fixture_claim()
        self.client = FixtureClient(self.claim, self.root)

    def run_job(self, **kwargs):
        return run_once(self.claim, self.client, self.root, **kwargs)

    def test_fixture_output_and_replay(self):
        first = self.run_job()
        with patch('workers.gpu.worker.render', side_effect=AssertionError('re-render')):
            second = self.run_job()
        self.assertEqual(first, second)
        self.assertEqual(first['take']['duration_ms'], 2000)
        self.assertEqual(first['metrics']['cost_cents'], 0)
        self.assertEqual(len(list(self.root.rglob('*.mp4'))), 1)

    def test_replay_after_ambiguous_completion_survives_restart(self):
        original = self.client.complete
        def lost_reply(attempt, manifest):
            original(attempt, manifest)
            raise WorkerAPIError(503)
        with patch.object(self.client, 'complete', side_effect=lost_reply):
            with self.assertRaises(WorkerAPIError):
                self.run_job()
        self.assertEqual(self.client.failures, [])
        self.client = FixtureClient(self.claim, self.root)
        with patch('workers.gpu.worker.render', side_effect=AssertionError('re-render')):
            self.assertEqual(self.run_job()['take']['attempt_id'], 'attempt-1')

    def test_concurrent_replay_creates_one_output(self):
        results, errors = [], []
        def run():
            try:
                results.append(self.run_job())
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])

    def test_corrupt_durable_output_blocks_completion(self):
        result = self.run_job()
        (self.root / result['asset']['object_key']).write_bytes(b'corruption')
        with patch.object(self.client, 'complete', side_effect=AssertionError('complete')):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                self.run_job()

    def test_conflicting_retry_is_rejected(self):
        self.run_job()
        snapshot = self.claim['shot_snapshot']
        snapshot['prompt'] = 'Different creative request'
        with self.assertRaisesRegex(ValueError, 'replay conflict'):
            self.run_job()

    def test_expired_lease_prevents_render(self):
        self.claim['attempt']['lease_expires_at'] = (utcnow() - timedelta(seconds=1)).isoformat()
        with patch('workers.gpu.worker.render', side_effect=AssertionError('render')):
            with self.assertRaises(LeaseLost):
                self.run_job()

    def test_expired_batch_prevents_render(self):
        self.claim['batch']['deadline_at'] = (utcnow() - timedelta(seconds=1)).isoformat()
        with self.assertRaises(ValueError):
            self.run_job()

    def test_heartbeat_loss_terminates_child_and_prevents_completion(self):
        calls = 0
        def heartbeat(attempt, progress):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise WorkerAPIError(409)
            return {'lease_expires_at': (utcnow()+timedelta(seconds=30)).isoformat()}
        from workers.gpu.worker import execute
        def slow_render(claim, destination, lease, input_root, weights):
            execute(['python', '-c', 'import time; time.sleep(30)'], lease)
        with patch.object(self.client, 'heartbeat', side_effect=heartbeat), \
             patch('workers.gpu.worker.render', side_effect=slow_render), \
             patch.object(self.client, 'complete', side_effect=AssertionError('complete')):
            with self.assertRaises(LeaseLost):
                self.run_job(interval=0.05)
        self.assertFalse(list(self.root.rglob('output.mp4')))

    def test_render_failure_reports_safe_code(self):
        with patch('workers.gpu.worker.render', side_effect=RuntimeError('private diagnostic')):
            with self.assertRaises(RuntimeError):
                self.run_job()
        self.assertEqual(self.client.failures, ['render_failed'])

    def test_failed_attempt_cannot_render_again_after_container_restart(self):
        with patch('workers.gpu.worker.render', side_effect=RuntimeError('private diagnostic')):
            with self.assertRaises(RuntimeError): self.run_job()
        with patch('workers.gpu.worker.render', side_effect=AssertionError('Second render forbidden')):
            with self.assertRaisesRegex(ValueError, 'already failed'): self.run_job()
        self.assertEqual(self.client.failures, ['render_failed'])

    def test_child_failure_classification_never_returns_private_log_text(self):
        from workers.gpu.worker import process_failure
        import io
        self.assertEqual(process_failure(io.BytesIO(b'WAN_STAGE:generation\nCUDA out of memory\nprivate prompt')), 'gpu_out_of_memory')
        self.assertEqual(process_failure(io.BytesIO(b'WAN_STAGE:video_encode\nprivate diagnostic')), 'video_encode_failed')

    def test_invalid_claims_rejected(self):
        mutations = [
            lambda c: c.update(contract_version='9.0.0'),
            lambda c: c['attempt'].update(project_id='other'),
            lambda c: c['attempt'].update(batch_id='other'),
            lambda c: c['attempt'].update(shot_revision=2),
            lambda c: c['batch']['budget'].update(spent_cents=1),
            lambda c: c['attempt'].update(state='succeeded'),
            lambda c: c['shot_snapshot']['settings'].update(width=321),
            lambda c: c['shot_snapshot'].update(target_duration_ms=5001),
            lambda c: c['attempt']['model_profile'].update(revision='other'),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                claim = copy.deepcopy(self.claim)
                mutation(claim)
                with self.assertRaises(Exception):
                    validate_claim(claim)

    def test_wan_profile_rounding_and_limits(self):
        c = self.claim
        c['batch']['execution_mode'] = 'runpod'
        c['batch']['budget']['approved_cents'] = 100
        c['attempt']['model_profile'] = c['batch']['model_profile'] = LOCK['profile']
        settings = dict(width=1280,height=704,frame_rate={'numerator':24,'denominator':1},seed=42,steps=50)
        c['attempt']['settings'] = c['shot_snapshot']['settings'] = settings
        validate_claim(c)
        self.assertEqual(frame_count(c['shot_snapshot'], 'runpod'), 49)
        c['shot_snapshot']['target_duration_ms'] = 5000
        self.assertEqual(frame_count(c['shot_snapshot'], 'runpod'), 121)

    def test_paths_and_symlinks_rejected(self):
        for key in ('../escape', '/absolute', 'x\\y'):
            with self.assertRaises(ValueError):
                scoped(self.root, key)
        (self.root/'link').symlink_to('/tmp')
        with self.assertRaises(ValueError):
            scoped(self.root, 'link/escape')

    def test_emitted_records_fit_complete_shared_bundle(self):
        from scripts.validate_contract import validate_bundle
        from workers.gpu.common import ROOT
        result = self.run_job()
        bundle = json.loads((ROOT/'fixtures/project.json').read_text())
        bundle['assets'] = [result['asset']]
        bundle['takes'] = [result['take']]
        bundle['batches'] = [copy.deepcopy(self.claim['batch'])]
        bundle['batches'][0]['state'] = 'succeeded'
        bundle['attempts'] = [copy.deepcopy(self.claim['attempt'])]
        bundle['attempts'][0].update(state='succeeded', completed_at=result['take']['committed_at'])
        for key in ('reviews', 'timelines', 'exports'):
            bundle[key] = []
        validate_bundle(bundle, self.root)

    def test_input_ownership_and_scope(self):
        c = self.claim
        c['batch']['execution_mode'] = 'runpod'
        c['batch']['budget']['approved_cents'] = 100
        c['attempt']['model_profile'] = c['batch']['model_profile'] = LOCK['profile']
        c['attempt']['settings'] = c['shot_snapshot']['settings'] = dict(
            width=1280, height=704, frame_rate={'numerator':24,'denominator':1}, seed=42, steps=50)
        c['shot_snapshot']['reference_asset_ids'] = ['image-1']
        asset = dict(id='image-1', project_id='fictional-project', owner_id='fictional-owner',
                     kind='image', object_key='projects/fictional-project/image.png',
                     mime_type='image/png', bytes=100, sha256='a'*64, duration_ms=None)
        c['input_assets'] = [asset]
        validate_claim(c)
        for key, value in [('owner_id','other'), ('project_id','other'),
                           ('object_key','projects/other/image.png')]:
            changed = copy.deepcopy(c)
            changed['input_assets'][0][key] = value
            with self.assertRaises(ValueError):
                validate_claim(changed)

    def test_weights_require_every_pinned_file(self):
        with self.assertRaises(FileNotFoundError):
            verify(self.root)

    def test_fixture_cli_is_credential_free(self):
        output = self.root/'result.json'
        subprocess.run(['python', '-m', 'workers.gpu.cli', 'fixture', '--output-root', str(self.root),
                        '--result', str(output)], check=True, capture_output=True)
        self.assertEqual(json.loads(output.read_text())['contract_version'], '0.1.0')

    def test_http_client_paths_and_auth_policy(self):
        for url in ('http://host', 'https://user:pass@host', 'https://host?token=x'):
            with self.assertRaises(ValueError):
                WorkerClient(url, 'token')
        client = WorkerClient('https://worker.example', 'fictional-token')
        with patch.object(client, 'post', return_value=None) as post:
            self.assertIsNone(client.claim())
            post.assert_called_once_with('claim', {})
        with patch.object(client, 'post', return_value={}) as post:
            client.heartbeat(self.claim['attempt'], 0.5)
            post.assert_called_once_with('attempts/attempt-1/heartbeat', {'lease_id':'lease-1','progress':0.5})


if __name__ == '__main__':
    unittest.main()

