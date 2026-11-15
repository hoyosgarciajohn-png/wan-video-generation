"""Authenticated local TCP batch/render/review rehearsal with fictional media."""
from http.client import HTTPConnection
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest

from services.controller.http_api import StudioAPI, make_server
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace


class RenderHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        repository = Path(__file__).resolve().parents[1]
        shutil.copytree(repository / 'fixtures/media', self.root / 'assets/media')
        fixture = json.loads((repository / 'fixtures/project.json').read_text())
        self.owner = fixture['project']['owner_id']
        self.project = fixture['project']['id']
        self.control = ControlService(self.root / 'db.sqlite', self.root / 'assets')
        self.control.seed(self.owner, fixture)
        self.studio = StudioWorkspace(self.control)
        self.api = StudioAPI(self.studio, {'a' * 40: self.owner, 'b' * 40: 'other-owner'})
        self.server = make_server(self.api, ('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.cookie = self.login('a' * 40)
        self.foreign_cookie = self.login('b' * 40)
        self.batch_path = f'/v1/studio/projects/{self.project}/batches'
        self.payload = {'shot_ids': ['shot-1'], 'expected_revision': 0, 'idempotency_key': 'http-fixture-1'}

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path, payload=None, cookie=None):
        headers = {'Origin': self.api.origin, 'X-WAN-Request': 'studio', 'Content-Type': 'application/json'}
        if cookie:
            headers['Cookie'] = cookie
        connection = HTTPConnection(*self.server.server_address, timeout=10)
        try:
            connection.request(method, path, body=json.dumps(payload or {}).encode(), headers=headers)
            response = connection.getresponse()
            raw = response.read()
            data = json.loads(raw) if response.getheader('Content-Type') == 'application/json' else raw
            return response.status, data, dict(response.getheaders())
        finally:
            connection.close()

    def login(self, token):
        status, _, headers = self.request('POST', '/v1/studio/session', {'token': token})
        self.assertEqual(status, 200)
        return headers['Set-Cookie'].split(';')[0]

    def workspace(self):
        status, data, _ = self.request('GET', '/v1/studio/workspaces/default', cookie=self.cookie)
        self.assertEqual(status, 200)
        return data['workspace']

    def admit(self):
        status, data, _ = self.request('POST', self.batch_path, self.payload, self.cookie)
        self.assertIn(status, (200, 202), data)
        return data

    def test_admission_idempotency_frozen_shot_and_owner_boundary(self):
        self.assertEqual(self.request('POST', self.batch_path, self.payload)[0], 401)
        self.assertEqual(self.request('POST', self.batch_path, self.payload, self.foreign_cookie)[0], 404)
        first = self.admit()
        replay = self.admit()
        self.assertEqual(first['batch']['id'], replay['batch']['id'])
        self.assertEqual(first['batch']['budget'], {'approved_cents': 0, 'reserved_cents': 0,
                                                  'spent_cents': 0, 'currency': 'USD'})
        self.assertEqual(first['batch']['execution_mode'], 'fixture')
        self.assertEqual(len(self.workspace()['projects'][0]['bundle']['batches']), 1)
        changed = dict(self.payload, shot_ids=['other-shot'])
        self.assertEqual(self.request('POST', self.batch_path, changed, self.cookie)[0], 409)
        paid = dict(self.payload, execution_mode='runpod')
        self.assertEqual(self.request('POST', self.batch_path, paid, self.cookie)[0], 422)
        workspace = self.workspace()
        shot = workspace['projects'][0]['bundle']['shots'][0]
        shot['prompt'] = 'A changed prompt after admission'
        shot['revision'] += 1
        status, _, _ = self.request('PUT', '/v1/studio/workspaces/default',
                                   {'workspace': workspace, 'expected_revision': workspace['revision']}, self.cookie)
        self.assertEqual(status, 200)
        persisted = self.workspace()['projects'][0]['bundle']
        self.assertNotEqual(persisted['shots'][0]['prompt'], persisted['batches'][0]['shot_snapshots'][0]['prompt'])
        self.assertEqual(self.admit()['batch']['id'], first['batch']['id'])
        stale = dict(self.payload, idempotency_key='new-stale-submission')
        self.assertEqual(self.request('POST', self.batch_path, stale, self.cookie)[0], 409)

    def test_cancel_is_scoped_idempotent_and_prevents_claim(self):
        batch = self.admit()['batch']
        path = f"{self.batch_path}/{batch['id']}/cancel"
        self.assertEqual(self.request('POST', path, {}, self.foreign_cookie)[0], 404)
        status, data, _ = self.request('POST', path, {}, self.cookie)
        self.assertIn(status, (200, 202), data)
        self.assertEqual(data['batch']['state'], 'canceled')
        again = self.request('POST', path, {}, self.cookie)
        self.assertIn(again[0], (200, 202))
        self.assertEqual(again[1]['batch']['state'], 'canceled')
        client = self.control.worker_client(self.owner, self.project, batch['id'], 'fixture-test-worker')
        self.assertIsNone(client.claim())
        self.assertEqual(self.workspace()['projects'][0]['bundle']['takes'], [])

    def test_background_worker_completion_review_and_authorized_playback(self):
        from services.controller.runner import FixtureRunner
        batch = self.admit()['batch']
        runner = FixtureRunner(self.control)
        stop = threading.Event()
        errors = []
        def work():
            try:
                runner.serve(stop, poll_interval=0.02)
            except Exception as error:
                errors.append(error)
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        def finish():
            stop.set()
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive(), 'Fixture runner did not shut down')
        self.addCleanup(finish)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            workspace = self.workspace()
            bundle = workspace['projects'][0]['bundle']
            if bundle['takes'] or errors:
                break
            stop.wait(0.05)
        self.assertFalse(errors, errors)
        self.assertEqual(len(bundle['takes']), 1, bundle['attempts'])
        self.assertEqual(bundle['batches'][0]['state'], 'succeeded')
        self.assertEqual(bundle['batches'][0]['cleanup_state'], 'confirmed')
        take = bundle['takes'][0]
        review_path = f"/v1/studio/projects/{self.project}/takes/{take['id']}/review"
        payload = {'decision': 'approved', 'expected_revision': workspace['revision'],
                   'idempotency_key': 'http-review-1'}
        self.assertEqual(self.request('POST', review_path, payload, self.foreign_cookie)[0], 404)
        status, approved, _ = self.request('POST', review_path, payload, self.cookie)
        self.assertIn(status, (200, 201), approved)
        self.assertEqual(approved['review']['decision'], 'approved')
        self.assertEqual(approved['review']['decided_by'], self.owner)
        self.assertEqual(approved['workspace']['revision'], workspace['revision'] + 1)
        status, replay, _ = self.request('POST', review_path, payload, self.cookie)
        self.assertIn(status, (200, 201), replay)
        self.assertEqual(replay['review']['id'], approved['review']['id'])
        self.assertEqual(len(replay['workspace']['projects'][0]['bundle']['reviews']), 1)
        conflict = dict(payload, decision='rejected')
        self.assertEqual(self.request('POST', review_path, conflict, self.cookie)[0], 409)
        stale = dict(payload, idempotency_key='http-review-stale')
        self.assertEqual(self.request('POST', review_path, stale, self.cookie)[0], 409)
        asset_path = f"/v1/studio/projects/{self.project}/assets/{take['asset_id']}/content"
        status, media, _ = self.request('GET', asset_path, cookie=self.cookie)
        self.assertEqual(status, 200)
        asset = next(a for a in bundle['assets'] if a['id'] == take['asset_id'])
        import hashlib
        self.assertEqual(hashlib.sha256(media).hexdigest(), asset['sha256'])
        self.assertEqual(self.request('GET', asset_path, cookie=self.foreign_cookie)[0], 404)
        self.assertEqual(self.admit()['batch']['id'], batch['id'])
        self.assertEqual(len(self.workspace()['projects'][0]['bundle']['takes']), 1)


if __name__ == '__main__':
    unittest.main()
