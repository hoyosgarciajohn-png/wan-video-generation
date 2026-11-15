"""Simulated budget authority, atomic admission and independent settlement."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.controller.orchestration import SimulationCoordinator
from services.controller.runpod import RunpodProvider
from services.controller.service import ControlService, stamp
from services.controller.studio import StudioWorkspace, StudioConflict
from src.wan_platform.fake_provider import FakeGpuProvider
from workers.gpu.common import FIXTURE_PROFILE, utcnow

ROOT = Path(__file__).resolve().parents[1]


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = ControlService(self.root / 'state.sqlite', self.root / 'assets')
        self.studio = StudioWorkspace(self.control)
        self.owner = 'owner-a'
        state = self.studio.create(self.owner, 'Simulation', 'music_video', 0)
        p = state['projects'][0]
        self.project = p['bundle']['project']['id']
        shot = deepcopy(json.loads((ROOT / 'fixtures/project.json').read_text())['shots'][0])
        shot.update(project_id=self.project, scene_id=p['scenes'][0]['id'])
        p['bundle']['shots'].append(shot)
        self.state = self.studio.save(self.owner, state, state['revision'])
        self.provider = FakeGpuProvider()
        self.coordinator = SimulationCoordinator(self.studio, self.provider)
        self.terms = dict(currency='USD', approved_cents=100, max_runtime_seconds=60,
                          valid_until=stamp(utcnow() + timedelta(minutes=10)), profile=deepcopy(FIXTURE_PROFILE))
        self.approval = self.coordinator.budget.approve(self.owner, self.project, self.terms, 'approval')
        self.request = dict(approval_id=self.approval['id'], shot_ids=[shot['id']], expected_revision=self.state['revision'],
                            reservation_cents=80, runtime_seconds=30, idempotency_key='batch-1')

    def submit(self, **changes):
        return self.coordinator.submit(self.owner, self.project, dict(self.request, **changes))

    def test_atomic_reservation_admission_and_concurrent_budget_limit(self):
        with self.control.transaction() as db:
            db.execute("CREATE TRIGGER reject_queue BEFORE INSERT ON pod_batches BEGIN SELECT RAISE(ABORT,'simulated crash'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.submit()
        with self.control.transaction() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM budget_reservations').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM pod_batches').fetchone()[0], 0)
            db.execute('DROP TRIGGER reject_queue')
        def race(index):
            try:
                return self.submit(idempotency_key=f'race-{index}')
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(race, range(2)))
        self.assertEqual(sum(r is not None for r in replies), 1)
        self.assertEqual(self.coordinator.budget.status(self.owner, self.project)['reserved_cents'], 80)

    def test_immutable_approval_replay_scope_and_simulation_gate(self):
        replay = self.coordinator.budget.approve(self.owner, self.project, self.terms, 'approval')
        self.assertEqual(replay, self.approval)
        with self.assertRaises(StudioConflict):
            self.coordinator.budget.approve(self.owner, self.project, dict(self.terms, approved_cents=200), 'approval')
        with self.assertRaises(KeyError):
            self.coordinator.budget.status('other-owner', self.project)
        transport_calls = []
        real = RunpodProvider('fictional-unused-token', transport=lambda *args, **kwargs: transport_calls.append(args))
        with self.assertRaises(ValueError):
            SimulationCoordinator(self.studio, real)
        self.assertEqual(transport_calls, [])
        with self.assertRaises(ValueError):
            self.submit(runtime_seconds=61)
        with self.assertRaises(ValueError):
            self.submit(reservation_cents=True)

    def test_cleanup_does_not_settle_and_late_charge_preserved(self):
        admitted = self.submit()
        batch = admitted['batch']['id']
        self.coordinator.provision(self.owner, self.project, batch)
        self.coordinator.finish(self.owner, self.project, batch, 'succeeded')
        with self.assertRaises(ValueError):
            self.coordinator.budget.settle(self.owner, self.project, batch, 60, 'final-bill', 'settle')
        self.assertEqual(self.coordinator.watchdog(), [])
        self.assertEqual(self.coordinator.status(self.owner, self.project, batch)['budget']['reserved_cents'], 80)
        settled = self.coordinator.budget.settle(self.owner, self.project, batch, 60, 'final-bill', 'settle')
        self.assertEqual(settled['budget']['reserved_cents'], 0)
        self.assertEqual(settled['budget']['spent_cents'], 60)
        late = self.coordinator.budget.record_charge(self.owner, self.project, batch, 50, 'late-bill', 'late')
        self.assertEqual(late['budget']['spent_cents'], 110)
        self.assertEqual(late['budget']['overrun_cents'], 10)
        with self.assertRaises(ValueError):
            self.submit(idempotency_key='blocked', reservation_cents=1)
        self.assertEqual(self.coordinator.budget.record_charge(self.owner, self.project, batch, 50, 'late-bill', 'late')['event_id'], late['event_id'])
        self.assertEqual(self.coordinator.budget.settle(self.owner, self.project, batch, 60, 'final-bill', 'settle')['event_id'], settled['event_id'])

    def test_newly_observed_overrun_blocks_queued_dispatch_atomically(self):
        first = self.submit(reservation_cents=40)['batch']['id']
        second = self.submit(reservation_cents=40, idempotency_key='batch-2')['batch']['id']
        self.coordinator.provision(self.owner, self.project, first)
        self.coordinator.budget.record_charge(self.owner, self.project, first, 90, 'interim', 'charge')
        with self.assertRaises(ValueError):
            self.coordinator.provision(self.owner, self.project, second)
        self.assertEqual(self.provider.find(second, second), [])
        self.assertEqual(self.coordinator.status(self.owner, self.project, second)['batch']['state'], 'queued')
        self.coordinator.cancel(self.owner, self.project, second)
        self.coordinator.budget.settle(self.owner, self.project, second, 0, 'never-dispatched', 'settle-second')
        self.assertEqual(self.coordinator.budget.status(self.owner, self.project)['spent_cents'], 90)

    def test_unknown_create_restart_retains_reservation_and_no_blind_retry(self):
        batch = self.submit()['batch']['id']
        calls = []
        def unknown(*args):
            calls.append(args)
            raise TimeoutError('No observable allocation yet')
        self.provider.create = unknown
        self.coordinator.provision(self.owner, self.project, batch)
        restarted = SimulationCoordinator(self.studio, self.provider)
        restarted.provision(self.owner, self.project, batch)
        self.assertEqual(len(calls), 1)
        restarted.budget.revoke(self.owner, self.project, self.approval['id'])
        restarted.cancel(self.owner, self.project, batch)
        self.assertEqual(restarted.watchdog(), [batch])
        self.assertEqual(restarted.status(self.owner, self.project, batch)['budget']['reserved_cents'], 80)
        with self.assertRaises(ValueError):
            restarted.budget.settle(self.owner, self.project, batch, 0, 'unconfirmed', 'settle')

    def test_exhausted_cap_blocks_dispatch_even_without_residual_reservation(self):
        batch = self.submit()['batch']['id']
        status = self.coordinator.budget.record_charge(self.owner, self.project, batch, 100, 'observed-charge', 'charge')['budget']
        self.assertEqual(status['reserved_cents'], 0)
        self.assertFalse(status['overcommitted'])
        with self.assertRaises(ValueError):
            self.coordinator.provision(self.owner, self.project, batch)
        self.assertEqual(self.provider.find(batch, batch), [])

    def test_revocation_blocks_new_dispatch_but_deadline_cleanup_remains_independent(self):
        batch = self.submit()['batch']['id']
        self.coordinator.budget.revoke(self.owner, self.project, self.approval['id'])
        with self.assertRaises(ValueError):
            self.coordinator.provision(self.owner, self.project, batch)
        self.assertEqual(self.provider.find(batch, batch), [])
        future = utcnow() + timedelta(seconds=31)
        self.control.clock = lambda: future
        self.assertEqual(self.coordinator.watchdog(), [])
        status = self.coordinator.status(self.owner, self.project, batch)
        self.assertEqual((status['batch']['state'], status['batch']['cleanup']), ('failed', 'confirmed'))
        self.assertEqual(status['budget']['reserved_cents'], 80)
        result = self.coordinator.budget.settle(self.owner, self.project, batch, 0, 'never-dispatched-deadline', 'settle')
        self.assertEqual(result['budget']['unsettled_count'], 0)

    def test_charge_replay_race_and_explicit_cap_increase_carries_history(self):
        batch = self.submit()['batch']['id']
        self.coordinator.cancel(self.owner, self.project, batch)
        self.coordinator.budget.settle(self.owner, self.project, batch, 0, 'no-launch', 'settle')
        def charge(_):
            return self.coordinator.budget.record_charge(self.owner, self.project, batch, 110, 'late-charge', 'event')
        with ThreadPoolExecutor(max_workers=4) as pool:
            events = list(pool.map(charge, range(4)))
        self.assertEqual(len({e['event_id'] for e in events}), 1)
        new_approval = self.coordinator.budget.approve(self.owner, self.project, dict(self.terms, approved_cents=200), 'raised')
        budget = self.coordinator.budget.status(self.owner, self.project)
        self.assertEqual((budget['spent_cents'], budget['available_cents']), (110, 90))
        self.submit(approval_id=new_approval['id'], idempotency_key='new-budget')
        with self.assertRaises(KeyError):
            self.coordinator.budget.record_charge('other-owner', self.project, batch, 1, 'cross-owner', 'cross-owner')


if __name__ == '__main__':
    unittest.main()
