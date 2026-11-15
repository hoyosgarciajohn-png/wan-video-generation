"""Actual controller and fixture worker processes with separate filesystem roots."""
from datetime import timedelta
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from services.controller.service import ControlService, stamp
from workers.gpu.common import digest, utcnow

ROOT = Path(__file__).resolve().parents[1]


class RemoteBridgeTests(unittest.TestCase):
    def setUp(self):
        from services.controller.worker_transport import WorkerTransport
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'controller/state.sqlite'
        self.assets = self.root / 'controller/assets'
        shutil.copytree(ROOT / 'fixtures/media', self.assets / 'media')
        fixture = json.loads((ROOT / 'fixtures/project.json').read_text())
        self.owner, self.project = fixture['project']['owner_id'], fixture['project']['id']
        self.control = ControlService(self.db, self.assets)
        self.control.seed(self.owner, fixture)
        batch = fixture['batches'][0]
        batch['deadline_at'] = stamp(utcnow() + timedelta(minutes=5))
        self.batch = self.control.admit(self.owner, self.project, batch)
        self.transport = WorkerTransport(self.control)
        self.credential = self.transport.issue(self.owner, self.project, self.batch['id'], 'remote-worker', ttl_seconds=120)
        self.worker_root = self.root / 'separate-worker'
        self.worker_root.mkdir()
        static = self.root / 'controller/static'
        static.mkdir()
        (static / 'index.html').write_text('<title>Fictional controller</title>')
        script = '''
import os
from services.controller.service import ControlService
from deployment.local_stage import create_server
c=ControlService(os.environ['TEST_DATABASE'],os.environ['TEST_ASSETS'])
s=create_server(c, {'synthetic-admin-token-at-least-32-characters':'fictional-owner'},
                os.environ['TEST_STATIC'],'http://127.0.0.1:8080',('127.0.0.1',0))
print(s.server_port,flush=True)
s.serve_forever()
'''
        self.server = subprocess.Popen([sys.executable, '-c', script], cwd=ROOT,
            env={**os.environ, 'TEST_DATABASE': str(self.db), 'TEST_ASSETS': str(self.assets), 'TEST_STATIC': str(static)},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop_server)
        import selectors
        selector = selectors.DefaultSelector()
        selector.register(self.server.stdout, selectors.EVENT_READ)
        try:
            self.assertTrue(selector.select(timeout=10), 'Controller startup timed out')
            line = self.server.stdout.readline().strip()
            self.assertTrue(line.isdigit(), 'Controller did not publish a port')
            self.port = int(line)
        finally:
            selector.close()

    def stop_server(self):
        if self.server.poll() is None:
            self.server.terminate()
        try:
            self.server.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            self.server.kill()
            self.server.communicate(timeout=5)

    def request(self, method, route, payload=None, token=None, raw=None, headers=None):
        supplied = {'Authorization': 'Bearer ' + (token or self.credential['token']),
                    'Content-Type': 'application/json' if raw is None else 'video/mp4'}
        supplied.update(headers or {})
        connection = HTTPConnection('127.0.0.1', self.port, timeout=15)
        try:
            connection.request(method, '/v1/worker/' + route,
                               body=json.dumps(payload or {}).encode() if raw is None else raw, headers=supplied)
            response = connection.getresponse()
            content = response.read()
            return response.status, json.loads(content) if content else None
        finally:
            connection.close()

    def run_worker(self):
        result = self.worker_root / 'result.json'
        completed = subprocess.run([sys.executable, '-m', 'workers.gpu.cli', 'worker',
            '--allow-local-http', '--output-root', str(self.worker_root / 'outputs'),
            '--input-root', str(self.worker_root / 'inputs'), '--result', str(result)], cwd=ROOT,
            env={**os.environ, 'WAN_WORKER_API_URL': f'http://127.0.0.1:{self.port}',
                 'WAN_WORKER_TOKEN': self.credential['token']}, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn(self.credential['token'], completed.stdout + completed.stderr)
        return json.loads(result.read_text())

    def test_separate_process_render_upload_completion_and_replay(self):
        result = self.run_worker()
        bundle = self.control.bundle(self.owner, self.project)
        self.assertEqual(len(bundle['takes']), 1)
        self.assertEqual(bundle['batches'][0]['state'], 'succeeded')
        asset = result['asset']
        controller_output = self.assets / asset['object_key']
        worker_output = self.worker_root / 'outputs' / asset['object_key']
        self.assertNotEqual(controller_output, worker_output)
        self.assertTrue(controller_output.is_file())
        self.assertTrue(worker_output.is_file())
        self.assertNotEqual(controller_output.stat().st_ino, worker_output.stat().st_ino)
        self.assertEqual(digest(controller_output), digest(worker_output))
        attempt = bundle['attempts'][0]
        manifest = {key: result[key] for key in ('asset', 'media')}
        status, replay = self.request('POST', f"attempts/{attempt['id']}/complete",
                                     {'lease_id': attempt['lease_id'], 'output_asset_manifest': manifest})
        self.assertEqual(status, 200, replay)
        self.assertEqual(replay['id'], result['take']['id'])
        self.run_worker()
        self.assertEqual(len(self.control.bundle(self.owner, self.project)['takes']), 1)
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(controller_output),
                        '-map', '0', '-f', 'null', '-'], check=True, timeout=20)
        self.transport.revoke(self.owner, self.project, self.credential['id'])
        self.assertEqual(self.request('POST', 'claim')[0], 401)

    def test_wrong_worker_attempt_and_bad_output_cannot_commit(self):
        status, claim = self.request('POST', 'claim')
        self.assertEqual(status, 200, claim)
        attempt = claim['attempt']
        other = self.transport.issue(self.owner, self.project, self.batch['id'], 'different-worker', ttl_seconds=120)
        route = f"attempts/{attempt['id']}/heartbeat"
        body = {'lease_id': attempt['lease_id'], 'progress': 0.5}
        self.assertIn(self.request('POST', route, body, token=other['token'])[0], (403, 404))
        self.assertIn(self.request('POST', 'attempts/missing/heartbeat', body)[0], (403, 404))
        self.assertEqual(self.request('POST', route, body, token='forged-token')[0], 401)
        status, _ = self.request('PUT', f"attempts/{attempt['id']}/artifact", raw=b'not video',
             headers={'X-WAN-Lease-ID': attempt['lease_id'], 'X-WAN-SHA256': '0' * 64})
        self.assertEqual(status, 422)
        self.assertEqual(self.control.bundle(self.owner, self.project)['takes'], [])
        fixture = json.loads((ROOT / 'fixtures/project.json').read_text())
        asset = dict(fixture['assets'][0], id='remote-output',
                     object_key=f"projects/{self.project}/attempts/{attempt['id']}/output.mp4")
        data = (ROOT / 'fixtures/media/clip.mp4').read_bytes()
        status, _ = self.request('PUT', f"attempts/{attempt['id']}/artifact", raw=data,
             headers={'X-WAN-Lease-ID': attempt['lease_id'], 'X-WAN-SHA256': asset['sha256']})
        self.assertEqual(status, 200)
        media = {key: fixture['takes'][0][key] for key in ('duration_ms', 'width', 'height', 'frame_rate')}
        asset['sha256'] = '0' * 64
        status, _ = self.request('POST', f"attempts/{attempt['id']}/complete",
             {'lease_id': attempt['lease_id'], 'output_asset_manifest': {'asset': asset, 'media': media}})
        self.assertIn(status, (409, 422))
        self.assertEqual(self.control.bundle(self.owner, self.project)['takes'], [])
        self.assertIn(self.request('GET', f"attempts/{attempt['id']}/inputs/asset-audio",
                                  headers={'X-WAN-Lease-ID': attempt['lease_id']})[0], (403, 404))
        # Expire the lease through persisted test state; the controller process
        # must reread authority rather than trusting the client's claim.
        with self.control.transaction() as db:
            bundle = self.control._load(db, self.owner, self.project)
            bundle['attempts'][0]['lease_expires_at'] = stamp(utcnow() - timedelta(seconds=1))
            db.execute('UPDATE projects SET bundle=? WHERE id=?', (json.dumps(bundle), self.project))
        self.assertIn(self.request('POST', route, body)[0], (403, 409))

    def test_expired_credentials_and_restore_revocation(self):
        from services.controller.backup import create_backup, restore_backup
        from services.controller.worker_transport import WorkerTransport, WorkerAccessError
        short = self.transport.issue(self.owner, self.project, self.batch['id'], 'short-lived', ttl_seconds=1)
        time.sleep(1.05)
        self.assertEqual(self.request('POST', 'claim', token=short['token'])[0], 401)
        create_backup(self.db, self.assets, self.root / 'backup')
        paths = restore_backup(self.root / 'backup', self.root / 'restored')
        restored = WorkerTransport(ControlService(paths['database'], paths['assets']))
        with self.assertRaises(WorkerAccessError) as denied:
            restored.principal('Bearer ' + self.credential['token'])
        self.assertEqual(denied.exception.status, 401)
        self.assertEqual(self.transport.principal('Bearer ' + self.credential['token'])['worker'], 'remote-worker')


if __name__ == '__main__':
    unittest.main()
