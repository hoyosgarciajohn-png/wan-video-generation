import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from workers.gpu.cli import FixtureClient, fixture_claim, remote_run
from workers.gpu.client import NoRedirect, WorkerAPIError, WorkerClient
from workers.gpu.common import digest, scoped


class Response(io.BytesIO):
    status = 200


class RemoteFixture(FixtureClient):
    binding = 'fictional-origin-and-token-fingerprint'

    def claim(self):
        return self.claim_data

    def upload(self, attempt, manifest, local):
        asset = manifest['asset']
        destination = scoped(self.root, asset['object_key'])
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if digest(destination) != asset['sha256']:
                raise WorkerAPIError(409)
        else:
            shutil.copyfile(local, destination)
        return {key: asset[key] for key in ('bytes', 'sha256', 'object_key')}


class RemoteWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / 'worker-only'
        self.remote = self.root / 'controller-only'
        self.claim = fixture_claim()
        self.client = RemoteFixture(self.claim, self.remote)
        self.result = self.root / 'result.json'

    def test_upload_ambiguity_replays_existing_local_output(self):
        original = self.client.upload
        def lost_reply(*args):
            original(*args)
            raise WorkerAPIError(503)
        with patch.object(self.client, 'upload', side_effect=lost_reply):
            with self.assertRaises(WorkerAPIError):
                remote_run(self.client, self.local, self.result)
        self.assertEqual(self.client.failures, [])
        self.assertTrue((self.local / 'worker-claim.json').is_file())
        with patch.object(self.client, 'claim', side_effect=AssertionError('must use durable claim')), patch('workers.gpu.worker.render', side_effect=AssertionError('must not rerender')):
            remote_run(self.client, self.local, self.result)
        result = json.loads(self.result.read_text())
        self.assertEqual(digest(self.remote / result['asset']['object_key']), result['asset']['sha256'])
        self.assertEqual(digest(self.local / result['asset']['object_key']), result['asset']['sha256'])
        self.assertFalse((self.local / 'worker-claim.json').exists())

    def test_completion_ambiguity_skips_already_confirmed_upload(self):
        original = self.client.complete
        def lost_reply(*args):
            original(*args)
            raise WorkerAPIError(503)
        with patch.object(self.client, 'complete', side_effect=lost_reply):
            with self.assertRaises(WorkerAPIError):
                remote_run(self.client, self.local, self.result)
        self.assertEqual(self.client.failures, [])
        journal = next(self.local.rglob('completion.json'))
        self.assertEqual(json.loads(journal.read_text())['uploaded']['sha256'], digest(next(self.local.rglob('output.mp4'))))
        with patch.object(self.client, 'upload', side_effect=AssertionError('terminal lease must not be reuploaded')), patch.object(self.client, 'claim', side_effect=AssertionError('must use durable claim')), patch('workers.gpu.worker.render', side_effect=AssertionError('must not rerender')):
            remote_run(self.client, self.local, self.result)
        self.assertEqual(json.loads(self.result.read_text())['take']['attempt_id'], 'attempt-1')

    def test_claim_journal_refuses_other_origin_or_credentials(self):
        with patch.object(self.client, 'upload', side_effect=WorkerAPIError(503)):
            with self.assertRaises(WorkerAPIError):
                remote_run(self.client, self.local, self.result)
        self.client.binding = 'other-credential-binding'
        with self.assertRaisesRegex(ValueError, 'credential/origin mismatch'):
            remote_run(self.client, self.local, self.result)

    def test_http_policy_and_bounded_safe_json(self):
        for url in ['http://example.com', 'http://127.0.0.1.evil', 'http://0.0.0.0', 'https://host/path']:
            with self.assertRaises(ValueError):
                WorkerClient(url, 'private-token', allow_local_http=True)
        with self.assertRaises(ValueError):
            WorkerClient('http://127.0.0.1', 'private-token')
        client = WorkerClient('http://127.0.0.1:8787', 'private-token', allow_local_http=True)
        self.assertNotIn('private-token', client.binding)
        for body in [b'private-provider-detail-not-json', b' ' * 2_000_001]:
            with patch.object(client.opener, 'open', return_value=Response(body)):
                with self.assertRaises(WorkerAPIError) as error:
                    client.claim()
                self.assertEqual(error.exception.status, 502)
                self.assertNotIn('private', str(error.exception))
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'http://other'))

    def test_artifact_put_streams_and_checks_receipt(self):
        client = WorkerClient('https://worker.example', 'fictional-token')
        local = self.root / 'clip.mp4'
        local.write_bytes(b'fictional-video-bytes')
        asset = {'bytes': local.stat().st_size, 'sha256': digest(local), 'object_key': 'projects/p/attempts/a/output.mp4'}
        def opener(request, **_):
            self.assertEqual(request.get_method(), 'PUT')
            self.assertEqual(request.get_header('Content-length'), str(asset['bytes']))
            self.assertEqual(request.get_header('X-wan-lease-id'), 'lease-1')
            self.assertEqual(request.get_header('Authorization'), 'Bearer fictional-token')
            self.assertTrue(hasattr(request.data, 'read'))
            self.assertEqual(request.data.read(65536), local.read_bytes())
            return Response(json.dumps(asset).encode())
        with patch.object(client.opener, 'open', side_effect=opener):
            self.assertEqual(client.upload(self.claim['attempt'], {'asset': asset}, local), asset)
        with patch.object(client.opener, 'open', return_value=Response(b'{}')):
            with self.assertRaises(WorkerAPIError):
                client.upload(self.claim['attempt'], {'asset': asset}, local)

    def test_reference_download_verifies_before_publishing(self):
        client = WorkerClient('https://worker.example', 'fictional-token')
        data = b'fictional-reference'
        asset = {'id': 'image-1', 'object_key': 'projects/fictional-project/reference.png', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        claim = {**self.claim, 'input_assets': [asset]}
        inputs = self.root / 'inputs'
        with patch.object(client.opener, 'open', return_value=Response(b'corrupt')):
            with self.assertRaises(ValueError):
                client.download_inputs(claim, inputs)
        self.assertFalse((inputs / asset['object_key']).exists())
        with patch.object(client.opener, 'open', return_value=Response(data)) as opener:
            client.download_inputs(claim, inputs)
            self.assertIn('/attempts/attempt-1/inputs/image-1', opener.call_args.args[0].full_url)
        with patch.object(client.opener, 'open', side_effect=AssertionError('valid cache must be reused')):
            client.download_inputs(claim, inputs)
        self.assertEqual((inputs / asset['object_key']).read_bytes(), data)

    def test_cli_error_redacts_environment_token(self):
        secret = 'fictional-private-token-never-print'
        result = subprocess.run([sys.executable, '-m', 'workers.gpu.cli', 'worker', '--output-root', str(self.local), '--result', str(self.result)],
                                env={**os.environ, 'WAN_WORKER_API_URL': 'http://untrusted.invalid', 'WAN_WORKER_TOKEN': secret}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
