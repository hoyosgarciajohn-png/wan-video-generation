"""Connected fixture commands, durable scheduler and owner boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import threading
import unittest

from services.controller.commands import RenderCommands
from services.controller.runner import FixtureRunner
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace, StudioConflict
from workers.gpu.common import utcnow

ROOT = Path(__file__).resolve().parents[1]


class RenderCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = ControlService(self.root / 'state.sqlite', self.root / 'assets')
        self.studio = StudioWorkspace(self.control)
        self.commands = RenderCommands(self.studio)
        self.owner = 'owner-a'
        state = self.studio.create(self.owner, 'Fixture project', 'music_video', 0)
        project = state['projects'][0]
        self.project = project['bundle']['project']['id']
        shot = deepcopy(json.loads((ROOT / 'fixtures/project.json').read_text())['shots'][0])
        shot.update(project_id=self.project, scene_id=project['scenes'][0]['id'])
        project['bundle']['shots'].append(shot)
        self.state = self.studio.save(self.owner, state, state['revision'])
        self.request = dict(shot_ids=[shot['id']], expected_revision=self.state['revision'], idempotency_key='submit-1')

    def submit(self):
        return self.commands.submit(self.owner, self.project, self.request)

    def test_real_render_then_atomic_review_and_selection(self):
        admitted = self.submit()
        self.assertEqual(admitted['batch']['execution_mode'], 'fixture')
        self.assertEqual(admitted['batch']['budget']['approved_cents'], 0)
        self.assertTrue(FixtureRunner(self.control).tick())
        current = self.studio.get(self.owner)
        take = current['projects'][0]['bundle']['takes'][0]
        payload = dict(decision='approved', expected_revision=current['revision'], idempotency_key='approve-1')
        reply = self.commands.review(self.owner, self.project, take['id'], payload)
        self.assertEqual(reply['workspace']['revision'], current['revision'] + 1)
        self.assertEqual(reply['workspace']['projects'][0]['selectedTakes'], {take['shot_id']: take['id']})
        replay = self.commands.review(self.owner, self.project, take['id'], payload)
        self.assertEqual(reply['review'], replay['review'])
        self.assertEqual(reply['workspace']['revision'], replay['workspace']['revision'])
        with self.assertRaises(StudioConflict):
            self.commands.review(self.owner, self.project, take['id'], dict(payload, decision='rejected'))
        rejected = self.commands.review(self.owner, self.project, take['id'],
                      dict(decision='rejected', expected_revision=reply['workspace']['revision'], idempotency_key='reject-1'))
        self.assertEqual(rejected['workspace']['projects'][0]['selectedTakes'], {})
        self.assertFalse(FixtureRunner(self.control).tick())

    def test_admission_idempotency_after_restart_and_creator_edit(self):
        admitted = self.submit()
        state = self.studio.get(self.owner)
        shot = state['projects'][0]['bundle']['shots'][0]
        shot.update(revision=2, prompt='New prompt')
        self.studio.save(self.owner, state, state['revision'])
        restarted = RenderCommands(StudioWorkspace(ControlService(self.root / 'state.sqlite', self.root / 'assets')))
        replay = restarted.submit(self.owner, self.project, self.request)
        self.assertEqual(replay['batch'], admitted['batch'])
        self.assertEqual(replay['batch']['shot_snapshots'][0]['revision'], 1)
        with self.assertRaises(StudioConflict):
            restarted.submit(self.owner, self.project, dict(self.request, expected_revision=replay['workspace']['revision']))
        with self.assertRaises(StudioConflict):
            restarted.submit(self.owner, self.project, dict(self.request, idempotency_key='new-but-stale'))

    def test_concurrent_duplicate_admission_and_cross_owner(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.submit(), range(4)))
        self.assertEqual(len({r['batch']['id'] for r in results}), 1)
        with self.assertRaises(KeyError):
            self.commands.submit('other-owner', self.project, self.request)
        with self.assertRaises(KeyError):
            self.commands.cancel('other-owner', self.project, results[0]['batch']['id'])
        with self.assertRaises(KeyError):
            self.commands.review('other-owner', self.project, 'take',
                                 dict(decision='approved', expected_revision=0, idempotency_key='other'))
        with self.assertRaises(ValueError):
            self.commands.submit(self.owner, self.project, dict(self.request, execution_mode='runpod'))

    def test_cancel_during_render_fences_completion_and_runner_restart(self):
        admitted = self.submit()
        def cancel_then_complete(claim, client, output_root):
            self.commands.cancel(self.owner, self.project, admitted['batch']['id'])
            with self.assertRaises(ValueError):
                client.heartbeat(claim['attempt'], 0.5)
        self.assertTrue(FixtureRunner(self.control, renderer=cancel_then_complete).tick())
        self.assertFalse(FixtureRunner(self.control).tick())
        bundle = self.control.bundle(self.owner, self.project)
        self.assertEqual(bundle['batches'][0]['state'], 'canceled')
        self.assertEqual(bundle['takes'], [])
        self.assertEqual(self.commands.cancel(self.owner, self.project, admitted['batch']['id'])['batch']['state'], 'canceled')

    def test_restart_abandoned_claim_retry_bound_and_deadline(self):
        admitted = self.submit()
        client = self.control.worker_client(self.owner, self.project, admitted['batch']['id'], 'abandoned-worker')
        first = client.claim()
        future = utcnow() + timedelta(seconds=31)
        restarted = ControlService(self.root / 'state.sqlite', self.root / 'assets', clock=lambda: future)
        def fail(claim, client, output_root):
            self.assertNotEqual(claim['attempt']['id'], first['attempt']['id'])
            raise RuntimeError('private diagnostic not exposed')
        runner = FixtureRunner(restarted, renderer=fail)
        self.assertTrue(runner.tick())
        self.assertEqual(runner.last_error, 'fixture_render_failed')
        self.assertFalse(runner.tick())
        self.assertEqual(restarted.bundle(self.owner, self.project)['batches'][0]['state'], 'failed')
        second = self.commands.submit(self.owner, self.project, dict(self.request, idempotency_key='deadline'))
        future += timedelta(minutes=11)
        self.assertFalse(runner.tick())
        batch = next(b for b in restarted.bundle(self.owner, self.project)['batches'] if b['id'] == second['batch']['id'])
        self.assertEqual(batch['state'], 'failed')

    def test_runner_lock_and_continuous_loop(self):
        self.submit()
        entered, release = threading.Event(), threading.Event()
        def hold(claim, client, output_root):
            entered.set()
            self.assertTrue(release.wait(5))
            client.fail(claim['attempt'], 'worker_failed')
        runner = FixtureRunner(self.control, renderer=hold)
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(runner.tick)
            self.assertTrue(entered.wait(5))
            self.assertFalse(FixtureRunner(self.control).tick())
            release.set()
            self.assertTrue(first.result(5))
        stop = threading.Event()
        def finish(claim, client, output_root):
            client.fail(claim['attempt'], 'worker_failed')
            stop.set()
        FixtureRunner(self.control, renderer=finish).serve(stop, poll_interval=.01)
        self.assertTrue(stop.is_set())


if __name__ == '__main__':
    unittest.main()
