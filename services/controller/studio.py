"""Owner-scoped Studio metadata backed by canonical ControlService projects.

The trusted HTTP host supplies owner identity. Workspace version 1 is a UI envelope
around bundle contract 0.1.0, not a replacement for it. Submitted execution records,
assets, media URLs and shot history are never authoritative and are ignored on save.
"""
from copy import deepcopy
import json
from uuid import uuid4
from urllib.parse import quote

from scripts.validate_contract import COLLECTIONS, RUNTIME_CAPS, validate_bundle
from services.controller.service import canonical
from workers.gpu.common import record

CAPS = RUNTIME_CAPS


class StudioConflict(ValueError):
    """Map to HTTP 409; invalid creator input remains HTTP 422."""


def require(value, message):
    if not value:
        raise ValueError(message)


class StudioWorkspace:
    def __init__(self, control_service):
        self.control = control_service
        with self.control.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS studio_owners (owner TEXT PRIMARY KEY, revision INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS studio_projects (project TEXT PRIMARY KEY, metadata TEXT NOT NULL)')

    @staticmethod
    def _owner(owner):
        if not isinstance(owner, str) or not owner.strip():
            raise PermissionError('Authenticated owner required')

    @staticmethod
    def _revision(db, owner):
        row = db.execute('SELECT revision FROM studio_owners WHERE owner=?', (owner,)).fetchone()
        return row[0] if row else 0

    def _check_revision(self, db, owner, expected):
        if type(expected) is not int or expected != self._revision(db, owner):
            raise StudioConflict('Workspace revision conflict')

    @staticmethod
    def _advance(db, owner):
        db.execute('INSERT INTO studio_owners VALUES (?,1) ON CONFLICT(owner) DO UPDATE SET revision=revision+1', (owner,))

    @staticmethod
    def _default_metadata(bundle):
        scene_ids = list(dict.fromkeys(s['scene_id'] for s in bundle['shots'])) or ['scene-' + uuid4().hex]
        return dict(scenes=[dict(id=s, title='Opening scene' if i == 0 else f'Scene {i + 1}')
                            for i, s in enumerate(scene_ids)],
                    shotHistory=[], selectedTakes={}, assetNames={}, script='')

    def _project(self, db, bundle):
        project_id = bundle['project']['id']
        row = db.execute('SELECT metadata FROM studio_projects WHERE project=?', (project_id,)).fetchone()
        if row:
            metadata = json.loads(row[0])
        else:
            metadata = self._default_metadata(bundle)
            db.execute('INSERT INTO studio_projects VALUES (?,?)', (project_id, canonical(metadata)))
        # Revoked approvals must not continue to appear selected after server updates.
        decisions = {r['take_id']: r['decision'] for r in sorted(bundle['reviews'], key=lambda r: r['decided_at'])}
        prior_selections = metadata['selectedTakes']
        metadata['selectedTakes'] = {shot: take for shot, take in prior_selections.items()
                                     if decisions.get(take) == 'approved'}
        if metadata['selectedTakes'] != prior_selections:
            db.execute('UPDATE studio_projects SET metadata=? WHERE project=?', (canonical(metadata), project_id))
        media = {a['id']: f"/v1/studio/projects/{quote(project_id, safe='')}/assets/{quote(a['id'], safe='')}/content"
                 for a in bundle['assets']}
        return dict(bundle=bundle, media=media, **metadata)

    def _get(self, db, owner):
        bundles = [json.loads(row[0]) for row in db.execute('SELECT bundle FROM projects WHERE owner=? ORDER BY id', (owner,))]
        return dict(version=1, revision=self._revision(db, owner), projects=[self._project(db, b) for b in bundles])

    def get(self, owner):
        self._owner(owner)
        with self.control.transaction() as db:
            return self._get(db, owner)

    def list_projects(self, owner):
        return [p['bundle']['project'] for p in self.get(owner)['projects']]

    def get_project(self, owner, project_id):
        self._owner(owner)
        with self.control.transaction() as db:
            return self._project(db, self.control._load(db, owner, project_id))

    def create(self, owner, title, kind, expected_revision):
        self._owner(owner)
        require(isinstance(title, str) and 0 < len(title.strip()) <= 500, 'Project title must contain 1 to 500 characters')
        require(isinstance(kind, str) and kind in CAPS, 'Unknown project kind')
        bundle = dict(contract_version='0.1.0', project=dict(id='project-' + uuid4().hex, owner_id=owner,
                      title=title.strip(), kind=kind, runtime_limit_ms=CAPS[kind]), **{c: [] for c in COLLECTIONS})
        validate_bundle(bundle)
        with self.control.transaction() as db:
            self._check_revision(db, owner, expected_revision)
            db.execute('INSERT INTO projects VALUES (?,?,?)', (bundle['project']['id'], owner, canonical(bundle)))
            self._advance(db, owner)
            return self._get(db, owner)

    def save(self, owner, workspace, expected_revision):
        self._owner(owner)
        require(isinstance(workspace, dict) and type(workspace.get('version')) is int and workspace['version'] == 1 and
                type(workspace.get('revision')) is int and isinstance(workspace.get('projects'), list) and
                len(workspace['projects']) <= 1000, 'Unsupported workspace envelope')
        for project in workspace['projects']:
            require(isinstance(project, dict) and isinstance(project.get('bundle'), dict) and
                    isinstance(project['bundle'].get('project'), dict) and
                    isinstance(project['bundle']['project'].get('id'), str), 'Invalid project envelope')
        with self.control.transaction() as db:
            self._check_revision(db, owner, expected_revision)
            if workspace.get('revision') != expected_revision:
                raise StudioConflict('Workspace envelope revision conflict')
            current = self._get(db, owner)
            previous = {p['bundle']['project']['id']: p for p in current['projects']}
            submitted_ids = [p['bundle']['project']['id'] for p in workspace['projects']]
            require(len(submitted_ids) == len(set(submitted_ids)) and set(submitted_ids) == set(previous),
                    'Use project creation; project deletion is not supported')
            for incoming in workspace['projects']:
                project_id = incoming['bundle']['project']['id']
                saved = self._merge(previous[project_id], incoming)
                self.control._save(db, saved['bundle'])
                metadata = {k: saved[k] for k in ('scenes','shotHistory','selectedTakes','assetNames','script')}
                db.execute('UPDATE studio_projects SET metadata=? WHERE project=?', (canonical(metadata), project_id))
            self._advance(db, owner)
            return self._get(db, owner)

    def _merge(self, current, incoming):
        saved = deepcopy(current)
        bundle = saved['bundle']
        # Owner, runtime cap and every execution collection come from persisted state.
        project = incoming['bundle']['project']
        require(project.get('owner_id') == bundle['project']['owner_id'], 'Project owner is immutable')
        title, kind = project.get('title'), project.get('kind')
        require(isinstance(title, str) and 0 < len(title.strip()) <= 500, 'Project title must contain 1 to 500 characters')
        require(isinstance(kind, str) and kind in CAPS, 'Unknown project kind')
        runtime_limit = (bundle['project']['runtime_limit_ms']
                         if kind == bundle['project']['kind'] else CAPS[kind])
        bundle['project'].update(title=title.strip(), kind=kind, runtime_limit_ms=runtime_limit)
        scenes = incoming.get('scenes')
        require(isinstance(scenes, list) and 0 < len(scenes) <= 1000, 'At least one scene required')
        scene_ids = set()
        for scene in scenes:
            require(isinstance(scene, dict) and set(scene) == {'id','title'} and
                    isinstance(scene['id'], str) and 0 < len(scene['id']) <= 200 and
                    isinstance(scene['title'], str) and 0 < len(scene['title'].strip()) <= 500,
                    'Invalid scene')
            require(scene['id'] not in scene_ids, 'Duplicate scene')
            scene_ids.add(scene['id'])
        saved['scenes'] = deepcopy(scenes)
        script = incoming.get('script')
        require(isinstance(script, str) and len(script) <= 1_000_000, 'Invalid script')
        saved['script'] = script
        old_shots = {s['id']: s for s in bundle['shots']}
        shots = incoming['bundle'].get('shots')
        require(isinstance(shots, list) and len(shots) <= 10000, 'Invalid shot list')
        seen = set()
        for shot in shots:
            record('shot', shot)
            require(shot['project_id'] == bundle['project']['id'] and shot['scene_id'] in scene_ids,
                    'Shot project or scene unavailable')
            require(shot['id'] not in seen, 'Duplicate shot')
            seen.add(shot['id'])
            prior = old_shots.get(shot['id'])
            if prior:
                if prior == shot:
                    continue
                if shot['revision'] != prior['revision'] + 1:
                    raise StudioConflict('Shot revision conflict')
                saved['shotHistory'].append(deepcopy(prior))
            elif shot['revision'] != 1:
                raise StudioConflict('New shot must start at revision one')
        require(set(old_shots).issubset(seen), 'Shot deletion is not supported')
        require(sum(s['target_duration_ms'] for s in shots) <= bundle['project']['runtime_limit_ms'],
                'Planned shots exceed project duration')
        bundle['shots'] = deepcopy(shots)
        asset_names = incoming.get('assetNames')
        asset_ids = {a['id'] for a in bundle['assets']}
        require(isinstance(asset_names, dict) and all(k in asset_ids and isinstance(v, str) and
                0 < len(v.strip()) <= 500 for k, v in asset_names.items()), 'Invalid asset display names')
        saved['assetNames'] = deepcopy(asset_names)
        selections = incoming.get('selectedTakes')
        require(isinstance(selections, dict), 'Invalid take selection')
        takes = {t['id']: t for t in bundle['takes']}
        decisions = {r['take_id']: r['decision'] for r in sorted(bundle['reviews'], key=lambda r: r['decided_at'])}
        for shot_id, take_id in selections.items():
            require(isinstance(take_id, str) and shot_id in seen and take_id in takes and
                    takes[take_id]['shot_id'] == shot_id and decisions.get(take_id) == 'approved',
                    'Selection requires an approved take from this shot')
        saved['selectedTakes'] = deepcopy(selections)
        validate_bundle(bundle)
        return saved
