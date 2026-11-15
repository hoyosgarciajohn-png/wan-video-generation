"""Synthetic checks of the trusted local service transport, without network/GPU."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from services.controller.service import ControlService, stamp
from workers.gpu.common import utcnow
from workers.gpu.worker import run_once

ROOT = Path(__file__).resolve().parents[1]


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'service.sqlite'
        self.assets = self.root / 'assets'
        shutil.copytree(ROOT / 'fixtures/media', self.assets / 'media')
        self.fixture = json.loads((ROOT / 'fixtures/project.json').read_text())
        self.owner = self.fixture['project']['owner_id']
        self.project = self.fixture['project']['id']
        self.service = ControlService(self.db, self.assets)
        self.service.seed(self.owner, self.fixture)
        self.request = deepcopy(self.fixture['batches'][0])
        self.request['deadline_at'] = stamp(utcnow() + timedelta(minutes=10))
        self.batch = self.service.admit(self.owner, self.project, self.request)
        self.client = self.client_for(self.service)

    def client_for(self, service, worker='worker-a'):
        return service.worker_client(self.owner, self.project, self.batch['id'], worker)

    def test_real_worker_completion_restart_and_replay(self):
        claim = self.client.claim()
        result = run_once(claim, self.client, self.assets)
        restarted = ControlService(self.db, self.assets)
        manifest = {k: result[k] for k in ('asset','media')}
        self.assertEqual(self.client_for(restarted).complete(claim['attempt'], manifest), result['take'])
        bundle = restarted.bundle(self.owner, self.project)
        self.assertEqual(len(bundle['takes']), 1)
        self.assertEqual(bundle['batches'][0]['state'], 'succeeded')
        self.assertIsNone(self.client_for(restarted).claim())
        manifest['asset']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.client_for(restarted).complete(claim['attempt'], manifest)

    def test_idempotency_restart_and_cross_owner(self):
        restarted = ControlService(self.db, self.assets)
        self.assertEqual(restarted.admit(self.owner, self.project, self.request), self.batch)
        modified = deepcopy(self.request)
        modified['shot_snapshots'][0]['prompt'] = 'other'
        with self.assertRaises(ValueError):
            restarted.admit(self.owner, self.project, modified)
        with self.assertRaises(KeyError):
            restarted.bundle('other-owner', self.project)
        with self.assertRaises(KeyError):
            restarted.worker_client('other-owner', self.project, self.batch['id'], 'worker')
        with self.assertRaises(KeyError):
            restarted.cancel('other-owner', self.project, self.batch['id'])

    def test_concurrent_claims_allocate_one_attempt(self):
        clients = [self.client_for(ControlService(self.db, self.assets), f'worker-{i}') for i in range(6)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            claims = list(pool.map(lambda c: c.claim(), clients))
        self.assertEqual(sum(c is not None for c in claims), 1)

    def test_expired_lease_fenced_after_restart_and_bounded_retries(self):
        now = utcnow()
        service = ControlService(self.db, self.assets, clock=lambda: now)
        old = self.client_for(service)
        first = old.claim()
        now += timedelta(seconds=31)
        restarted = ControlService(self.db, self.assets, clock=lambda: now)
        new = self.client_for(restarted, 'worker-b')
        second = new.claim()
        self.assertNotEqual(first['attempt']['id'], second['attempt']['id'])
        with self.assertRaises(ValueError):
            self.client_for(restarted).heartbeat(first['attempt'], .5)
        with self.assertRaises(PermissionError):
            new.heartbeat(first['attempt'], .5)
        new.fail(second['attempt'], 'render_failed')
        self.assertIsNone(new.claim())
        self.assertEqual(restarted.bundle(self.owner, self.project)['batches'][0]['state'], 'failed')

    def test_unuploaded_output_cannot_commit_and_cancel_fences(self):
        claim = self.client.claim()
        a = deepcopy(self.fixture['assets'][0])
        a.update(id='output-' + claim['attempt']['id'],
                 object_key=f"projects/{self.project}/attempts/{claim['attempt']['id']}/output.mp4")
        manifest = dict(asset=a, media={k: self.fixture['takes'][0][k] for k in ('duration_ms','width','height','frame_rate')})
        with self.assertRaises(ValueError):
            self.client.complete(claim['attempt'], manifest)
        self.assertEqual(self.service.bundle(self.owner, self.project)['takes'], [])
        self.service.cancel(self.owner, self.project, self.batch['id'])
        with self.assertRaises(ValueError):
            self.client.complete(claim['attempt'], manifest)

    def test_paid_mode_disabled_and_foreign_snapshot_rejected(self):
        paid = deepcopy(self.request)
        paid.update(idempotency_key='paid', execution_mode='runpod')
        with self.assertRaises(ValueError):
            self.service.admit(self.owner, self.project, paid)
        invalid = deepcopy(self.request)
        invalid['idempotency_key'] = 'invalid'
        invalid['shot_snapshots'][0]['prompt'] = 'unpersisted edit'
        with self.assertRaises(ValueError):
            self.service.admit(self.owner, self.project, invalid)


if __name__ == '__main__':
    unittest.main()
