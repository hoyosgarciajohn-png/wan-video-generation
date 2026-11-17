"""Durable Studio creator state and authoritative execution-state boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from services.controller.service import ControlService, stamp
from services.controller.studio import StudioWorkspace, StudioConflict
from workers.gpu.common import utcnow
from workers.gpu.worker import run_once

ROOT = Path(__file__).resolve().parents[1]


class StudioServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = ControlService(self.root / 'state.sqlite', self.root / 'assets')
        self.studio = StudioWorkspace(self.control)
        self.owner = 'owner-a'
        self.fixture = json.loads((ROOT / 'fixtures/project.json').read_text())

    def create(self):
        return self.studio.create(self.owner, 'My project', 'music_video', self.studio.get(self.owner)['revision'])

    def add_shot(self, state):
        project = state['projects'][0]
        shot = deepcopy(self.fixture['shots'][0])
        shot.update(project_id=project['bundle']['project']['id'], scene_id=project['scenes'][0]['id'])
        project['bundle']['shots'].append(shot)
        return self.studio.save(self.owner, state, state['revision'])

    def test_empty_workspace_create_restart_and_owner_boundaries(self):
        self.assertEqual(self.studio.get(self.owner), dict(version=1, revision=0, projects=[]))
        state = self.create()
        restarted = StudioWorkspace(ControlService(self.root / 'state.sqlite', self.root / 'assets'))
        self.assertEqual(restarted.get(self.owner), state)
        self.assertEqual(restarted.get('owner-b')['projects'], [])
        project_id = state['projects'][0]['bundle']['project']['id']
        with self.assertRaises(KeyError):
            restarted.get_project('owner-b', project_id)
        with self.assertRaises(PermissionError):
            restarted.get('')
        self.assertEqual(state['projects'][0]['bundle']['assets'], [])
        self.assertEqual(state['projects'][0]['bundle']['takes'], [])
        self.assertEqual(state['projects'][0]['bundle']['project']['runtime_limit_ms'], 360000)

    def test_creator_fields_history_and_canonical_project_shared(self):
        state = self.add_shot(self.create())
        p = state['projects'][0]
        p['script'] = 'An original short script.'
        p['scenes'][0]['title'] = 'Act one'
        p['bundle']['project']['title'] = 'Renamed'
        p['bundle']['shots'][0].update(revision=2, prompt='A different blue room')
        state = self.studio.save(self.owner, state, state['revision'])
        p = state['projects'][0]
        self.assertEqual(p['shotHistory'][0]['revision'], 1)
        bundle = self.control.bundle(self.owner, p['bundle']['project']['id'])
        self.assertEqual(bundle['shots'][0]['revision'], 2)
        self.assertEqual(bundle['project']['title'], 'Renamed')
        self.assertEqual(StudioWorkspace(self.control).get(self.owner), state)

    def test_edit_does_not_expand_existing_limit_or_accept_client_override(self):
        state = self.create()
        project_id = state['projects'][0]['bundle']['project']['id']
        with self.control.transaction() as db:
            bundle = self.control._load(db, self.owner, project_id)
            bundle['project']['runtime_limit_ms'] = 300000
            self.control._save(db, bundle)
        state = self.studio.get(self.owner)
        state['projects'][0]['bundle']['project'].update(title='Renamed legacy project', runtime_limit_ms=360000)
        saved = self.studio.save(self.owner, state, state['revision'])
        self.assertEqual(saved['projects'][0]['bundle']['project']['runtime_limit_ms'], 300000)
        self.assertEqual(saved['projects'][0]['bundle']['project']['title'], 'Renamed legacy project')

    def test_optimistic_concurrency_and_whole_save_rollback(self):
        state = self.create()
        first, second = deepcopy(state), deepcopy(state)
        first['projects'][0]['script'] = 'first'
        second['projects'][0]['script'] = 'second'
        def save(value):
            try:
                return self.studio.save(self.owner, value, state['revision'])
            except StudioConflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, (first, second)))
        self.assertEqual(sum(result is not None for result in results), 1)
        with self.assertRaises(StudioConflict):
            self.studio.create(self.owner, 'late', 'cartoon', state['revision'])
        saved = self.studio.get(self.owner)
        invalid = deepcopy(saved)
        invalid['projects'][0]['script'] = 'must roll back'
        invalid['projects'][0]['selectedTakes'] = {'unknown-shot': 'forged-take'}
        with self.assertRaises(ValueError):
            self.studio.save(self.owner, invalid, saved['revision'])
        self.assertEqual(self.studio.get(self.owner), saved)

    def test_forged_execution_and_media_are_ignored(self):
        state = self.create()
        p = state['projects'][0]
        for key in ('assets','batches','attempts','takes','reviews','timelines','exports'):
            p['bundle'][key] = [{'id': 'forged'}]
        p['media'] = {'forged': 'data:video/mp4;base64,AAAA'}
        p['shotHistory'] = [{'id': 'forged'}]
        saved = self.studio.save(self.owner, state, state['revision'])['projects'][0]
        for key in ('assets','batches','attempts','takes','reviews','timelines','exports'):
            self.assertEqual(saved['bundle'][key], [])
        self.assertEqual(saved['media'], {})
        self.assertEqual(saved['shotHistory'], [])

    def test_server_progress_survives_stale_workspace_and_selection_validates(self):
        state = self.add_shot(self.create())
        p = state['projects'][0]
        project_id = p['bundle']['project']['id']
        request = deepcopy(self.fixture['batches'][0])
        request.update(project_id=project_id, deadline_at=stamp(utcnow() + timedelta(minutes=10)))
        shot = p['bundle']['shots'][0]
        request['shot_snapshots'] = [dict(shot_id=shot['id'], **{k: v for k, v in shot.items()
                                    if k not in ('id','project_id','scene_id')})]
        batch = self.control.admit(self.owner, project_id, request)
        client = self.control.worker_client(self.owner, project_id, batch['id'], 'worker')
        result = run_once(client.claim(), client, self.control.asset_root)
        self.control.review(self.owner, project_id, result['take']['id'], 'approved')
        p['script'] = 'Stale workspace can still save creator edits.'
        p['selectedTakes'] = {shot['id']: result['take']['id']}
        saved = self.studio.save(self.owner, state, state['revision'])
        current = saved['projects'][0]
        self.assertEqual(current['bundle']['batches'][0]['state'], 'succeeded')
        self.assertEqual(len(current['bundle']['takes']), 1)
        self.assertEqual(current['selectedTakes'], p['selectedTakes'])
        self.assertTrue(current['media'][result['asset']['id']].startswith('/v1/studio/projects/'))
        self.control.review(self.owner, project_id, result['take']['id'], 'rejected')
        self.assertEqual(self.studio.get(self.owner)['projects'][0]['selectedTakes'], {})
        with self.assertRaises(ValueError):
            self.studio.save(self.owner, saved, saved['revision'])

    def test_malformed_envelopes_and_boolean_revisions_are_rejected(self):
        state = self.create()
        malformed_projects = [None, [], {}, {'bundle': None}, {'bundle': []},
                              {'bundle': {'project': []}}, {'bundle': {'project': {'id': []}}}]
        for project in malformed_projects:
            with self.subTest(project=project):
                malformed = dict(state, projects=[project])
                with self.assertRaises(ValueError):
                    self.studio.save(self.owner, malformed, state['revision'])
        for field in ('version', 'revision'):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.studio.save(self.owner, dict(state, **{field: True}), state['revision'])
        with self.assertRaises(StudioConflict):
            self.studio.save(self.owner, state, True)
        with self.assertRaises(ValueError):
            self.studio.create(self.owner, 'x' * 501, 'music_video', state['revision'])
        self.assertEqual(self.studio.get(self.owner), state)

    def test_editing_shot_preserves_frozen_admitted_snapshot(self):
        state = self.add_shot(self.create())
        p = state['projects'][0]
        project_id = p['bundle']['project']['id']
        request = deepcopy(self.fixture['batches'][0])
        request.update(project_id=project_id, deadline_at=stamp(utcnow() + timedelta(minutes=10)))
        shot = p['bundle']['shots'][0]
        request['shot_snapshots'] = [dict(shot_id=shot['id'], **{k: v for k, v in shot.items()
                                    if k not in ('id','project_id','scene_id')})]
        admitted = self.control.admit(self.owner, project_id, request)
        shot.update(revision=2, prompt='New revision after admission')
        saved = self.studio.save(self.owner, state, state['revision'])['projects'][0]
        self.assertEqual(saved['bundle']['batches'][0]['shot_snapshots'], admitted['shot_snapshots'])
        self.assertEqual(saved['bundle']['shots'][0]['revision'], 2)
        self.assertEqual(saved['shotHistory'][0]['revision'], 1)
        from scripts.validate_contract import validate_bundle
        validate_bundle(saved['bundle'])

    def test_invalid_revisions_scene_links_and_cross_project_selection(self):
        state = self.add_shot(self.create())
        changed = deepcopy(state)
        changed['projects'][0]['bundle']['shots'][0]['prompt'] = 'Unversioned edit'
        with self.assertRaises(StudioConflict):
            self.studio.save(self.owner, changed, state['revision'])
        changed = deepcopy(state)
        changed['projects'][0]['scenes'] = [{'id': 'unrelated', 'title': 'Other'}]
        with self.assertRaises(ValueError):
            self.studio.save(self.owner, changed, state['revision'])
        changed = deepcopy(state)
        changed['projects'][0]['bundle']['project']['owner_id'] = 'owner-b'
        with self.assertRaises(ValueError):
            self.studio.save(self.owner, changed, state['revision'])
        self.assertEqual(self.studio.get(self.owner), state)


if __name__ == '__main__':
    unittest.main()
