"""Canonical job/accounting atomicity; media here is deliberately synthetic."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from services.controller.real_jobs import RealJobBridge
from services.controller.service import ControlService, stamp
from services.controller.studio import StudioWorkspace
from services.controller.worker_transport import WorkerTransport, WorkerAccessError
from src.wan_platform.fake_provider import FakeGpuProvider
from workers.gpu.common import LOCK, digest, probe, utcnow, validate_claim

ROOT = Path(__file__).resolve().parents[1]


class RealJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = ControlService(self.root / 'state.sqlite', self.root / 'assets')
        self.studio = StudioWorkspace(self.control)
        self.owner = 'fictional-owner'
        state = self.studio.create(self.owner, 'Explicit synthetic test', 'music_video', 0)
        p = state['projects'][0]
        self.project = p['bundle']['project']['id']
        shot = deepcopy(json.loads((ROOT / 'fixtures/project.json').read_text())['shots'][0])
        shot.update(project_id=self.project, scene_id=p['scenes'][0]['id'], target_duration_ms=1000)
        shot['settings'].update(width=1280, height=704, steps=50)
        p['bundle']['shots'].append(shot)
        self.state = self.studio.save(self.owner, state, state['revision'])
        self.provider = FakeGpuProvider()
        self.bridge = RealJobBridge.for_testing(self.studio, self.provider)
        self.profile = dict(model_profile=deepcopy(LOCK['profile']), image_ref='registry.example/wan@sha256:' + 'a' * 64,
                            gpu_type='fictional', gpu_count=1, region='fictional', worker_endpoint='https://worker.example', storage_id='fictional')
        self.terms = dict(currency='USD', approved_cents=100, max_runtime_seconds=120,
                          valid_until=stamp(utcnow() + timedelta(minutes=10)), profile=self.profile)
        approval = self.bridge.budget.approve(self.owner, self.project, self.terms, 'approve')
        self.request = dict(approval_id=approval['id'], shot_ids=[shot['id']], expected_revision=self.state['revision'],
                            reservation_cents=60, runtime_seconds=90, idempotency_key='job')

    def submit(self, **changes):
        return self.bridge.submit(self.owner, self.project, dict(self.request, **changes))

    def test_default_disarmed_bridge_does_not_break_backup(self):
        from services.controller.backup import create_backup, restore_backup
        other = ControlService(self.root / 'disarmed.sqlite', self.root / 'disarmed-assets')
        studio = StudioWorkspace(other)
        studio.create('fictional-other', 'No live resources', 'music_video', 0)
        RealJobBridge(studio)
        create_backup(other.db_path, other.asset_root, self.root / 'disarmed-backup')
        restored = restore_backup(self.root / 'disarmed-backup', self.root / 'disarmed-restored')
        self.assertTrue(Path(restored['database']).is_file())

    def test_concurrent_idempotency_creates_one_canonical_lifecycle_reservation(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            replies = list(pool.map(lambda _: self.submit(), range(3)))
        self.assertEqual(len({r['batch']['id'] for r in replies}), 1)
        with self.control.transaction() as db:
            for table in ('budget_reservations','pod_batches','real_job_links'):
                self.assertEqual(db.execute('SELECT count(*) FROM ' + table).fetchone()[0], 1)
        self.assertEqual(len(self.control.bundle(self.owner, self.project)['batches']), 1)
        self.assertEqual(replies[0]['batch']['execution_mode'], 'runpod')
        self.assertEqual(replies[0]['provenance'], 'synthetic_test_only')
        with self.assertRaises(ValueError):
            self.submit(idempotency_key='would-overspend')

    def test_invalid_profile_rolls_back_all_admission_records(self):
        invalid = deepcopy(self.terms)
        invalid['profile']['model_profile']['revision'] = 'unreviewed'
        approval = self.bridge.budget.approve(self.owner, self.project, invalid, 'wrong-model')
        with self.assertRaises(ValueError):
            self.submit(approval_id=approval['id'])
        with self.control.transaction() as db:
            for table in ('budget_reservations','pod_batches','real_job_links'):
                self.assertEqual(db.execute('SELECT count(*) FROM ' + table).fetchone()[0], 0)
        self.assertEqual(self.control.bundle(self.owner, self.project)['batches'], [])

    def test_unknown_create_restart_and_default_transport_stays_closed(self):
        batch = self.submit()['batch']['id']
        self.provider.timeout_after_create = True
        first = self.bridge.provision(self.owner, self.project, batch)
        self.assertEqual(first['batch']['state'], 'provisioning')
        restarted = RealJobBridge.for_testing(self.studio, self.provider)
        second = restarted.provision(self.owner, self.project, batch)
        self.assertEqual(second['batch']['state'], 'rendering')
        self.assertEqual(len(self.provider.find(batch, batch)), 1)
        with self.assertRaises(WorkerAccessError):
            WorkerTransport(self.control).issue(self.owner, self.project, batch, 'worker')
        with self.assertRaises(ValueError):
            self.control.worker_client(self.owner, self.project, batch, 'worker')
        transport = WorkerTransport(self.control, real_jobs=restarted)
        credential = transport.issue(self.owner, self.project, batch, 'worker')
        claim = transport.call('Bearer ' + credential['token'], 'claim', {})
        validate_claim(claim)
        with self.assertRaises(WorkerAccessError):
            WorkerTransport(self.control).principal('Bearer ' + credential['token'])

    def test_verified_completion_and_lifecycle_terminal_transition_are_atomic(self):
        batch = self.submit()['batch']['id']
        self.bridge.provision(self.owner, self.project, batch)
        transport = WorkerTransport(self.control, real_jobs=self.bridge)
        token = transport.issue(self.owner, self.project, batch, 'worker')
        auth = 'Bearer ' + token['token']
        claim = transport.call(auth, 'claim', {})
        attempt = claim['attempt']
        output = self.root / 'synthetic.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i','color=c=blue:s=1280x704:r=24',
                        '-frames:v','25','-an','-c:v','libx264','-threads','1','-pix_fmt','yuv420p',str(output)], check=True)
        media = probe(output, attempt['settings'], 25)
        checksum = digest(output)
        with output.open('rb') as stream:
            uploaded = transport.upload(auth, attempt['id'], attempt['lease_id'], checksum, output.stat().st_size, stream)
        manifest = dict(asset=dict(id='output-' + attempt['id'], project_id=self.project, owner_id=self.owner, kind='video',
                                  object_key=uploaded['object_key'], mime_type='video/mp4', bytes=uploaded['bytes'],
                                  sha256=checksum, duration_ms=media['duration_ms']), media=media)
        payload = dict(lease_id=attempt['lease_id'], output_asset_manifest=manifest)
        with self.control.transaction() as db:
            db.execute("CREATE TRIGGER terminal_fault BEFORE UPDATE OF state ON pod_batches WHEN NEW.state='succeeded' BEGIN SELECT RAISE(ABORT,'injected transaction fault'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            transport.call(auth, f"attempts/{attempt['id']}/complete", payload)
        self.assertEqual(self.control.bundle(self.owner, self.project)['takes'], [])
        self.assertEqual(self.bridge.status(self.owner, self.project, batch)['lifecycle']['state'], 'rendering')
        with self.control.transaction() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM completions').fetchone()[0], 0)
            db.execute('DROP TRIGGER terminal_fault')
        take = transport.call(auth, f"attempts/{attempt['id']}/complete", payload)
        self.assertEqual(take['attempt_id'], attempt['id'])
        self.assertEqual(self.bridge.status(self.owner, self.project, batch)['lifecycle']['state'], 'succeeded')
        self.provider.fail_next_delete = True
        self.assertEqual(self.bridge.watchdog(), [batch])
        self.assertEqual(self.bridge.status(self.owner, self.project, batch)['budget']['reserved_cents'], 60)
        self.assertEqual(self.bridge.watchdog(), [])
        self.assertEqual(self.bridge.status(self.owner, self.project, batch)['batch']['cleanup_state'], 'confirmed')
        self.assertEqual(self.bridge.status(self.owner, self.project, batch)['budget']['unsettled_count'], 1)


if __name__ == '__main__':
    unittest.main()
