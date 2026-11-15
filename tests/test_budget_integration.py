"""Independent fictional budget/lifecycle liability and recovery checks."""
from datetime import timedelta
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from services.controller.service import ControlService, stamp
from services.controller.studio import StudioWorkspace
from services.controller.backup import create_backup, restore_backup
from src.wan_platform.fake_provider import FakeGpuProvider
from workers.gpu.common import FIXTURE_PROFILE, utcnow


class BudgetIntegrationTests(unittest.TestCase):
    def setUp(self):
        from services.controller.orchestration import SimulationCoordinator
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        repo = Path(__file__).resolve().parents[1]
        fixture = json.loads((repo / 'fixtures/project.json').read_text())
        self.owner, self.project = fixture['project']['owner_id'], fixture['project']['id']
        self.db, self.assets = self.root / 'state.sqlite', self.root / 'assets'
        shutil.copytree(repo / 'fixtures/media', self.assets / 'media')
        self.now = utcnow()
        self.control = ControlService(self.db, self.assets, clock=lambda: self.now)
        self.control.seed(self.owner, fixture)
        self.studio = StudioWorkspace(self.control)
        self.provider = FakeGpuProvider()
        self.coordinator = SimulationCoordinator(self.studio, self.provider)
        self.terms = {'currency': 'USD', 'approved_cents': 100, 'max_runtime_seconds': 120,
                      'valid_until': stamp(self.now + timedelta(hours=1)), 'profile': FIXTURE_PROFILE}
        self.approval = self.coordinator.budget.approve(self.owner, self.project, self.terms, 'approval-1')

    def request(self, key='batch-1', reservation=80):
        return {'approval_id': self.approval['id'], 'shot_ids': ['shot-1'], 'expected_revision': 0,
                'reservation_cents': reservation, 'runtime_seconds': 60, 'idempotency_key': key}

    def test_unknown_creation_cleanup_settlement_overrun_and_backup(self):
        from services.controller.orchestration import SimulationCoordinator
        submitted = self.coordinator.submit(self.owner, self.project, self.request())
        batch_id = submitted['batch']['id']
        self.provider.timeout_after_create = True
        self.coordinator.provision(self.owner, self.project, batch_id)
        self.assertEqual(len(self.provider._pods), 1)
        restarted = SimulationCoordinator(StudioWorkspace(ControlService(self.db, self.assets,
                                           clock=lambda: self.now)), self.provider)
        with patch.object(self.provider, 'find', side_effect=ConnectionError('Unknown inventory')):
            restarted.provision(self.owner, self.project, batch_id)
            restarted.cancel(self.owner, self.project, batch_id)
            restarted.watchdog()
        self.assertEqual(len(self.provider._pods), 1)
        with self.assertRaises(ValueError):
            restarted.submit(self.owner, self.project, self.request('over-reservation', 30))
        with self.assertRaises(ValueError):
            create_backup(self.db, self.assets, self.root / 'unknown-liability')
        restarted.watchdog()
        self.assertEqual(len(self.provider._pods), 0)
        self.assertEqual(restarted.budget.status(self.owner, self.project)['reserved_cents'], 80)
        self.assertEqual(restarted.budget.status(self.owner, self.project)['unsettled_count'], 1)
        # Confirmed deletion is not permission to release unsettled liability.
        with self.assertRaises(ValueError):
            restarted.submit(self.owner, self.project, self.request('deleted-unbilled', 30))
        with self.assertRaises(ValueError):
            create_backup(self.db, self.assets, self.root / 'deleted-unbilled')
        restarted.budget.settle(self.owner, self.project, batch_id, 60, 'fictional-final-bill', 'settle-1')
        baseline = restarted.budget.status(self.owner, self.project)
        restarted.budget.settle(self.owner, self.project, batch_id, 60, 'fictional-final-bill', 'settle-1')
        self.assertEqual(restarted.budget.status(self.owner, self.project), baseline)
        with self.assertRaises((ValueError, KeyError, PermissionError)):
            restarted.budget.record_charge('other-owner', self.project, batch_id, 50, 'late', 'late-1')
        restarted.budget.record_charge(self.owner, self.project, batch_id, 50, 'late-correction', 'late-1')
        overrun = restarted.budget.status(self.owner, self.project)
        self.assertEqual((overrun['spent_cents'], overrun['reserved_cents'], overrun['overrun_cents']), (110, 0, 10))
        restarted.budget.record_charge(self.owner, self.project, batch_id, 50, 'late-correction', 'late-1')
        self.assertEqual(restarted.budget.status(self.owner, self.project), overrun)
        with self.assertRaises(ValueError):
            restarted.submit(self.owner, self.project, self.request('after-overrun', 1))
        # A new approval must not erase cumulative project billing.
        renewed = restarted.budget.approve(self.owner, self.project, self.terms, 'approval-2')
        with self.assertRaises(ValueError):
            restarted.submit(self.owner, self.project, dict(self.request('renewed-overrun', 1), approval_id=renewed['id']))
        create_backup(self.db, self.assets, self.root / 'settled-backup')
        paths = restore_backup(self.root / 'settled-backup', self.root / 'restored')
        restored = SimulationCoordinator(StudioWorkspace(ControlService(paths['database'], paths['assets'],
                                         clock=lambda: self.now)), FakeGpuProvider())
        self.assertEqual(restored.budget.status(self.owner, self.project), restarted.budget.status(self.owner, self.project))
        with self.assertRaises(ValueError):
            restored.submit(self.owner, self.project, dict(self.request('restore-overrun', 1), approval_id=renewed['id']))

    def test_backup_refuses_inconsistent_settlement_history(self):
        batch = self.coordinator.submit(self.owner, self.project, self.request())['batch']['id']
        self.coordinator.cancel(self.owner, self.project, batch)
        self.coordinator.budget.settle(self.owner, self.project, batch, 0, 'never-dispatched', 'settled-zero')
        create_backup(self.db, self.assets, self.root / 'valid-zero-settlement')
        # Simulate corruption of a ledger row despite a syntactically valid DB.
        with self.control.transaction() as db:
            db.execute('UPDATE budget_events SET amount_cents=1 WHERE batch=?', (batch,))
        with self.assertRaisesRegex(ValueError, 'settlement'):
            create_backup(self.db, self.assets, self.root / 'corrupt-ledger')


if __name__ == '__main__':
    unittest.main()
