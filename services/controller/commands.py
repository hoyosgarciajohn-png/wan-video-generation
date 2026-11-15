"""Atomic creator commands for local fixture generation and take review.

HTTP identity is supplied by the authenticated host. Command receipts retain the
original request identity independently of later creator revisions or worker state.
No request field can select a paid execution mode, provider, budget or model.
"""
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

from services.controller.service import canonical, stamp
from services.controller.studio import StudioConflict, require
from workers.gpu.common import FIXTURE_PROFILE, validate_claim


class RenderCommands:
    def __init__(self, studio):
        self.studio, self.control = studio, studio.control
        with self.control.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS command_receipts (
                project TEXT NOT NULL, operation TEXT NOT NULL, idem TEXT NOT NULL,
                request TEXT NOT NULL, record_id TEXT NOT NULL,
                PRIMARY KEY(project, operation, idem))''')

    @staticmethod
    def _request(payload, fields):
        require(isinstance(payload, dict) and set(payload) == set(fields), 'Invalid command fields')
        key = payload.get('idempotency_key')
        require(isinstance(key, str) and 0 < len(key.strip()) <= 200, 'Idempotency key required')
        require(type(payload.get('expected_revision')) is int and payload['expected_revision'] >= 0,
                'Expected revision must be a nonnegative integer')

    @staticmethod
    def _receipt(db, project, operation, payload):
        row = db.execute('SELECT request,record_id FROM command_receipts WHERE project=? AND operation=? AND idem=?',
                         (project, operation, payload['idempotency_key'])).fetchone()
        if row and row[0] != canonical(payload):
            raise StudioConflict('Idempotency key already used for different input')
        return row[1] if row else None

    @staticmethod
    def _remember(db, project, operation, payload, record_id):
        db.execute('INSERT INTO command_receipts VALUES (?,?,?,?,?)',
                   (project, operation, payload['idempotency_key'], canonical(payload), record_id))

    def submit(self, owner, project_id, payload):
        self.studio._owner(owner)
        self._request(payload, ('shot_ids','expected_revision','idempotency_key'))
        shot_ids = payload['shot_ids']
        require(isinstance(shot_ids, list) and 0 < len(shot_ids) <= 1000 and
                all(isinstance(s, str) and s for s in shot_ids) and len(set(shot_ids)) == len(shot_ids),
                'Select distinct saved shots')
        with self.control.transaction() as db:
            bundle = self.control._load(db, owner, project_id)
            prior = self._receipt(db, project_id, 'submit', payload)
            if prior:
                batch = self.control._batch(bundle, prior)
                return dict(batch=deepcopy(batch), workspace=self.studio._get(db, owner))
            self.studio._check_revision(db, owner, payload['expected_revision'])
            shots = {s['id']: s for s in bundle['shots']}
            if any(s not in shots for s in shot_ids):
                raise KeyError('Shot unavailable')
            snapshots = [dict(shot_id=s, **{k: deepcopy(v) for k, v in shots[s].items()
                         if k not in ('id','project_id','scene_id')}) for s in shot_ids]
            now = self.control.clock()
            batch = dict(id=uuid4().hex, project_id=project_id, idempotency_key=payload['idempotency_key'],
                         execution_mode='fixture', model_profile=deepcopy(FIXTURE_PROFILE), shot_snapshots=snapshots,
                         budget=dict(currency='USD', approved_cents=0, reserved_cents=0, spent_cents=0),
                         approved_at=stamp(now), deadline_at=stamp(now + timedelta(minutes=10)),
                         state='rendering', cleanup_state='confirmed', provider_resource_id=None)
            for snapshot in snapshots:
                attempt = self.control._attempt(batch, snapshot, 'admission-check', now)
                validate_claim(self.control._envelope(bundle, batch, attempt, snapshot))
            bundle['batches'].append(batch)
            self.control._save(db, bundle)
            self._remember(db, project_id, 'submit', payload, batch['id'])
            return dict(batch=deepcopy(batch), workspace=self.studio._get(db, owner))

    def cancel(self, owner, project_id, batch_id):
        self.studio._owner(owner)
        with self.control.transaction() as db:
            bundle = self.control._load(db, owner, project_id)
            batch = next((b for b in bundle['batches'] if b['id'] == batch_id), None)
            if batch is None:
                raise KeyError('Batch unavailable')
            require(batch['execution_mode'] == 'fixture', 'Only fixture batches supported')
            if batch['state'] in ('queued','provisioning','rendering'):
                batch.update(state='canceled', cleanup_state='confirmed')
            self.control._reconcile(bundle, batch, self.control.clock())
            self.control._save(db, bundle)
            return dict(batch=deepcopy(batch), workspace=self.studio._get(db, owner))

    def review(self, owner, project_id, take_id, payload):
        self.studio._owner(owner)
        self._request(payload, ('decision','expected_revision','idempotency_key'))
        require(payload['decision'] in ('approved','rejected'), 'Invalid review decision')
        receipt_request = dict(payload, take_id=take_id)
        with self.control.transaction() as db:
            bundle = self.control._load(db, owner, project_id)
            prior = self._receipt(db, project_id, 'review', receipt_request)
            if prior:
                review = next(r for r in bundle['reviews'] if r['id'] == prior)
                return dict(review=deepcopy(review), workspace=self.studio._get(db, owner))
            self.studio._check_revision(db, owner, payload['expected_revision'])
            take = next((t for t in bundle['takes'] if t['id'] == take_id), None)
            if take is None:
                raise KeyError('Take unavailable')
            project = self.studio._project(db, bundle)
            review = dict(id=uuid4().hex, project_id=project_id, take_id=take_id, decision=payload['decision'],
                          decided_by=owner, decided_at=stamp(self.control.clock()))
            bundle['reviews'].append(review)
            selections = project['selectedTakes']
            if payload['decision'] == 'approved':
                selections[take['shot_id']] = take_id
            elif selections.get(take['shot_id']) == take_id:
                selections.pop(take['shot_id'])
            metadata = {k: project[k] for k in ('scenes','shotHistory','selectedTakes','assetNames','script')}
            self.control._save(db, bundle)
            db.execute('UPDATE studio_projects SET metadata=? WHERE project=?', (canonical(metadata), project_id))
            self.studio._advance(db, owner)
            self._remember(db, project_id, 'review', receipt_request, review['id'])
            return dict(review=deepcopy(review), workspace=self.studio._get(db, owner))
