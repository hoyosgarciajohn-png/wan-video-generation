"""Durable, trusted in-process fixture service; no HTTP or paid dispatch.

Identity arguments must come from a trusted host, never directly from request JSON.
WorkerClient is a capability bound by that host to one project, batch and worker.
All state changes serialize through SQLite BEGIN IMMEDIATE, including lease fencing.
The asset root must be a persistent, controller-readable shared mount.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from scripts.validate_contract import COLLECTIONS, validate_bundle
from workers.gpu.common import (digest, frame_count, probe, record, scoped,
                                timestamp, utcnow, validate_claim)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def stamp(value):
    return value.isoformat().replace('+00:00', 'Z')


class ControlService:
    def __init__(self, db_path, asset_root, *, clock=utcnow, lease_seconds=30, max_attempts=2):
        if lease_seconds < 15 or max_attempts < 1:
            raise ValueError('Invalid retry or lease policy')
        self.db_path, self.asset_root = str(db_path), Path(asset_root)
        self.clock, self.lease_seconds, self.max_attempts = clock, lease_seconds, max_attempts
        self.asset_root.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, owner TEXT NOT NULL, bundle TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS admissions (project TEXT, idem TEXT, request TEXT NOT NULL, batch TEXT NOT NULL, PRIMARY KEY(project,idem))')
            db.execute('CREATE TABLE IF NOT EXISTS completions (attempt TEXT PRIMARY KEY, manifest TEXT NOT NULL, take TEXT NOT NULL)')

    @contextmanager
    def transaction(self):
        with sqlite3.connect(self.db_path, timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            yield db

    def _load(self, db, owner, project):
        if not owner:
            raise PermissionError('Authenticated owner required')
        row = db.execute('SELECT bundle FROM projects WHERE id=? AND owner=?', (project, owner)).fetchone()
        if not row:
            raise KeyError('Project unavailable')
        return json.loads(row[0])

    def _save(self, db, bundle):
        validate_bundle(bundle)
        db.execute('UPDATE projects SET bundle=? WHERE id=?', (canonical(bundle), bundle['project']['id']))

    def seed(self, owner_id, bundle):
        """Import a new project and its input assets/shots, never execution history."""
        value = deepcopy(bundle)
        if not owner_id or value['project']['owner_id'] != owner_id:
            raise PermissionError('Project owner mismatch')
        for collection in COLLECTIONS:
            if collection not in ('shots', 'assets'):
                value[collection] = []
        validate_bundle(value)
        for asset in value['assets']:
            path = scoped(self.asset_root, asset['object_key'])
            if not path.is_file() or path.stat().st_size != asset['bytes'] or digest(path) != asset['sha256']:
                raise ValueError('Unverified input asset')
        with self.transaction() as db:
            db.execute('INSERT INTO projects VALUES (?,?,?)', (value['project']['id'], owner_id, canonical(value)))
        return value['project']

    def bundle(self, owner_id, project_id):
        with self.transaction() as db:
            return self._load(db, owner_id, project_id)

    def admit(self, owner_id, project_id, batch_record):
        """Accept exact stored shot revisions. Paid mode is deliberately unavailable."""
        request = deepcopy(batch_record)
        record('batch', request)
        if request['project_id'] != project_id:
            raise ValueError('Project mismatch')
        if request['execution_mode'] != 'fixture':
            raise ValueError('Paid dispatch disabled: approved budget ledger and provider settlement not integrated')
        if any(request['budget'][k] for k in ('approved_cents','reserved_cents','spent_cents')):
            raise ValueError('Fixture cost must be zero')
        with self.transaction() as db:
            bundle = self._load(db, owner_id, project_id)
            prior = db.execute('SELECT request,batch FROM admissions WHERE project=? AND idem=?',
                               (project_id, request['idempotency_key'])).fetchone()
            if prior:
                if prior[0] != canonical(request):
                    raise ValueError('Idempotency conflict')
                return deepcopy(self._batch(bundle, prior[1]))
            now = self.clock()
            if timestamp(request['deadline_at']) <= now:
                raise ValueError('Deadline must be in the future')
            shots = {s['id']: s for s in bundle['shots']}
            for snapshot in request['shot_snapshots']:
                shot = shots.get(snapshot['shot_id'])
                expected = {k: v for k, v in (shot or {}).items() if k not in ('id','project_id','scene_id')}
                expected['shot_id'] = snapshot['shot_id']
                if snapshot != expected:
                    raise ValueError('Shot snapshot differs from stored revision')
            batch = deepcopy(request)
            batch.update(id=uuid4().hex, approved_at=stamp(now), state='rendering',
                         cleanup_state='confirmed', provider_resource_id=None)
            bundle['batches'].append(batch)
            # Validate the worker profile before admitting any unusable work.
            for snapshot in batch['shot_snapshots']:
                attempt = self._attempt(batch, snapshot, 'validation', now)
                validate_claim(self._envelope(bundle, batch, attempt, snapshot))
            self._save(db, bundle)
            db.execute('INSERT INTO admissions VALUES (?,?,?,?)',
                       (project_id, request['idempotency_key'], canonical(request), batch['id']))
            return deepcopy(batch)

    @staticmethod
    def _batch(bundle, batch_id):
        return next(b for b in bundle['batches'] if b['id'] == batch_id)

    def worker_client(self, owner_id, project_id, batch_id, worker_id, *, authorize=None, synchronize=None):
        """Trusted host issues this capability only after authenticating its worker."""
        if not worker_id:
            raise PermissionError('Worker identity required')
        with self.transaction() as db:
            batch = self._batch(self._load(db, owner_id, project_id), batch_id)
            if batch['execution_mode'] == 'runpod' and (authorize is None or synchronize is None):
                raise ValueError('Real-profile workers require an installed server authority bridge')
        return WorkerClient(self, owner_id, project_id, batch_id, worker_id, authorize=authorize, synchronize=synchronize)

    def _attempt(self, batch, snapshot, worker, now):
        return dict(id=uuid4().hex, project_id=batch['project_id'], batch_id=batch['id'],
                    shot_id=snapshot['shot_id'], shot_revision=snapshot['revision'], worker_id=worker,
                    lease_id=uuid4().hex, lease_expires_at=stamp(min(now + timedelta(seconds=self.lease_seconds),
                                                               timestamp(batch['deadline_at']))),
                    started_at=stamp(now), completed_at=None, settings=deepcopy(snapshot['settings']),
                    model_profile=deepcopy(batch['model_profile']), state='claimed', failure_reason=None)

    @staticmethod
    def _envelope(bundle, batch, attempt, snapshot):
        return deepcopy(dict(contract_version='0.1.0', project=bundle['project'], batch=batch,
                             attempt=attempt, shot_snapshot=snapshot,
                             input_assets=[a for a in bundle['assets'] if a['id'] in snapshot['reference_asset_ids']]))

    def _reconcile(self, bundle, batch, now):
        for attempt in bundle['attempts']:
            if attempt['batch_id'] != batch['id'] or attempt['state'] not in ('claimed','running'):
                continue
            reason = ('batch_closed' if batch['state'] != 'rendering' else
                      'deadline_exceeded' if now >= timestamp(batch['deadline_at']) else
                      'lease_expired' if now >= timestamp(attempt['lease_expires_at']) else None)
            if reason:
                attempt.update(state='failed', completed_at=stamp(now), failure_reason=reason)
        if batch['state'] == 'rendering' and now >= timestamp(batch['deadline_at']):
            batch['state'] = 'failed'

    def _worker(self, client, action, supplied=None, payload=None):
        with self.transaction() as db:
            client.authorize(db)
            bundle = self._load(db, client.owner, client.project)
            batch = self._batch(bundle, client.batch)
            now = self.clock()
            self._reconcile(bundle, batch, now)
            if action == 'claim':
                answer = None
                if batch['state'] == 'rendering':
                    # Reconcile a lost claim response for this exact worker identity.
                    # A lease already fenced by _reconcile is never returned here.
                    existing = next((a for a in bundle['attempts'] if a['batch_id'] == batch['id'] and
                                     a['worker_id'] == client.worker and a['state'] in ('claimed','running')), None)
                    if existing:
                        snapshot = next(s for s in batch['shot_snapshots'] if s['shot_id'] == existing['shot_id'])
                        self._save(db, bundle)
                        if client.synchronize is not None:
                            client.synchronize(db, bundle, batch)
                        client.authorize(db)
                        return self._envelope(bundle, batch, existing, snapshot)
                    for snapshot in batch['shot_snapshots']:
                        attempts = [a for a in bundle['attempts'] if a['batch_id'] == batch['id'] and a['shot_id'] == snapshot['shot_id']]
                        if any(a['state'] in ('claimed','running','succeeded') for a in attempts):
                            continue
                        if len(attempts) >= self.max_attempts:
                            batch['state'] = 'failed'
                            break
                        attempt = self._attempt(batch, snapshot, client.worker, now)
                        bundle['attempts'].append(attempt)
                        answer = self._envelope(bundle, batch, attempt, snapshot)
                        break
                self._save(db, bundle)
                if client.synchronize is not None:
                    client.synchronize(db, bundle, batch)
                client.authorize(db)
                return answer
            attempt = next((a for a in bundle['attempts'] if a['id'] == supplied['id'] and
                            a['batch_id'] == client.batch and a['worker_id'] == client.worker), None)
            if not attempt or supplied.get('lease_id') != attempt['lease_id']:
                raise PermissionError('Worker assignment unavailable')
            if action == 'complete':
                prior = db.execute('SELECT manifest,take FROM completions WHERE attempt=?', (attempt['id'],)).fetchone()
                if prior:
                    if canonical(payload) != prior[0]:
                        raise ValueError('Completion replay conflict')
                    return json.loads(prior[1])
            if batch['state'] != 'rendering' or attempt['state'] not in ('claimed','running'):
                # The fence is also recomputed from persisted expiry after a restart.
                raise ValueError('Lease fenced or batch closed')
            if action == 'heartbeat':
                if not isinstance(payload, (int,float)) or not 0 <= payload <= 1:
                    raise ValueError('Invalid progress')
                attempt.update(state='running', lease_expires_at=stamp(min(now + timedelta(seconds=self.lease_seconds),
                                                                         timestamp(batch['deadline_at']))))
                result = {'lease_expires_at': attempt['lease_expires_at']}
            elif action == 'fail':
                if payload not in ('render_failed','worker_failed'):
                    raise ValueError('Unknown failure code')
                attempt.update(state='failed', completed_at=stamp(now), failure_reason=payload)
                result = None
            elif action == 'complete':
                result = self._complete(db, bundle, batch, attempt, payload, now)
            else:
                raise ValueError('Unknown worker action')
            self._save(db, bundle)
            if client.synchronize is not None:
                client.synchronize(db, bundle, batch)
            client.authorize(db)
            return result

    def _complete(self, db, bundle, batch, attempt, manifest, now):
        asset, media = manifest['asset'], manifest['media']
        record('asset', asset)
        expected_key = f"projects/{batch['project_id']}/attempts/{attempt['id']}/output.mp4"
        if (asset['project_id'] != batch['project_id'] or asset['owner_id'] != bundle['project']['owner_id'] or
                asset['object_key'] != expected_key or asset['kind'] != 'video' or asset['mime_type'] != 'video/mp4' or
                asset['duration_ms'] != media['duration_ms'] or any(a['id'] == asset['id'] for a in bundle['assets'])):
            raise ValueError('Invalid output asset ownership or identity')
        path = scoped(self.asset_root, expected_key)
        if not path.is_file() or path.stat().st_size != asset['bytes'] or digest(path) != asset['sha256']:
            raise ValueError('Output not durably uploaded or checksum mismatch')
        snapshot = next(s for s in batch['shot_snapshots'] if s['shot_id'] == attempt['shot_id'])
        if probe(path, attempt['settings'], frame_count(snapshot, batch['execution_mode'])) != media:
            raise ValueError('Output metadata mismatch')
        # Media inspection may outlive the lease; recheck using the clock after I/O.
        now = self.clock()
        if now >= min(timestamp(attempt['lease_expires_at']), timestamp(batch['deadline_at'])):
            raise ValueError('Lease expired during verification')
        take = dict(id=uuid4().hex, project_id=batch['project_id'], attempt_id=attempt['id'],
                    shot_id=attempt['shot_id'], asset_id=asset['id'], committed_at=stamp(now), **media)
        record('take', take)
        bundle['assets'].append(deepcopy(asset))
        bundle['takes'].append(take)
        attempt.update(state='succeeded', completed_at=stamp(now))
        if all(any(a['batch_id'] == batch['id'] and a['shot_id'] == s['shot_id'] and a['state'] == 'succeeded'
                   for a in bundle['attempts']) for s in batch['shot_snapshots']):
            batch['state'] = 'succeeded'
        db.execute('INSERT INTO completions VALUES (?,?,?)', (attempt['id'], canonical(manifest), canonical(take)))
        return deepcopy(take)

    def cancel(self, owner_id, project_id, batch_id):
        with self.transaction() as db:
            bundle = self._load(db, owner_id, project_id)
            batch = self._batch(bundle, batch_id)
            if batch['state'] == 'rendering':
                batch['state'] = 'canceled'
            self._reconcile(bundle, batch, self.clock())
            self._save(db, bundle)
            return deepcopy(batch)

    def review(self, owner_id, project_id, take_id, decision):
        with self.transaction() as db:
            bundle = self._load(db, owner_id, project_id)
            value = dict(id=uuid4().hex, project_id=project_id, take_id=take_id, decision=decision,
                         decided_by=owner_id, decided_at=stamp(self.clock()))
            bundle['reviews'].append(value)
            self._save(db, bundle)
            return value

    def save_timeline(self, owner_id, project_id, timeline):
        with self.transaction() as db:
            bundle = self._load(db, owner_id, project_id)
            previous = [t for t in bundle['timelines'] if t['id'] == timeline['id']]
            if timeline['revision'] != max((t['revision'] for t in previous), default=0) + 1:
                raise ValueError('Timeline revision conflict')
            value = dict(deepcopy(timeline), created_at=stamp(self.clock()))
            bundle['timelines'].append(value)
            self._save(db, bundle)
            return value

    def save_export(self, owner_id, project_id, export, output_asset=None):
        """Persist a completed local exporter result after validating durable bytes."""
        if export["state"] != "succeeded" or output_asset is None or export["output_asset_id"] != output_asset["id"]:
            raise ValueError("Only a completed export with its uploaded asset can be persisted")
        with self.transaction() as db:
            bundle = self._load(db, owner_id, project_id)
            if output_asset:
                path = scoped(self.asset_root, output_asset['object_key'])
                if path.stat().st_size != output_asset['bytes'] or digest(path) != output_asset['sha256']:
                    raise ValueError('Unverified export upload')
                bundle['assets'].append(deepcopy(output_asset))
            bundle['exports'].append(deepcopy(export))
            self._save(db, bundle)
            return deepcopy(export)


class WorkerClient:
    """Same callable transport surface as workers.gpu.client.WorkerClient."""
    def __init__(self, service, owner, project, batch, worker, *, authorize=None, synchronize=None):
        self.synchronize = synchronize
        self.authorize = authorize or (lambda db: None)
        self.service, self.owner, self.project, self.batch, self.worker = service, owner, project, batch, worker

    def claim(self):
        return self.service._worker(self, 'claim')

    def heartbeat(self, attempt, progress):
        return self.service._worker(self, 'heartbeat', attempt, progress)

    def complete(self, attempt, manifest):
        return self.service._worker(self, 'complete', attempt, manifest)

    def fail(self, attempt, code):
        return self.service._worker(self, 'fail', attempt, code)
