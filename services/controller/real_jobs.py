"""Canonical real-profile job wiring, executable only as an explicit test rehearsal.

There is deliberately no live-provider factory. Simulation approvals and test links
cannot authorize real spending. Public fixture admission/transport remain unchanged.
"""
from copy import deepcopy
import hashlib
import json
import math
import re
from urllib.parse import urlsplit
from uuid import uuid4

from services.controller.budget import BudgetLedger, cents
from services.controller.orchestration import SimulationCoordinator
from services.controller.service import canonical, stamp
from services.controller.studio import StudioConflict, require
from src.wan_platform.fake_provider import FakeGpuProvider
from workers.gpu.common import LOCK, validate_claim


class RealJobBridge:
    def __init__(self, studio):
        self.studio, self.control = studio, studio.control
        self.budget = BudgetLedger(self.control)
        self._simulation = None
        with self.control.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS real_job_links (
                batch TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
                approval TEXT NOT NULL, mode TEXT NOT NULL,
                config_hash TEXT NOT NULL, created TEXT NOT NULL)''')

    @classmethod
    def for_testing(cls, studio, provider):
        require(type(provider) is FakeGpuProvider, 'Test rehearsal requires the exact fictional provider')
        bridge = cls(studio)
        bridge._simulation = SimulationCoordinator(studio, provider)
        return bridge

    def _enabled(self):
        require(self._simulation is not None, 'Real execution is disarmed; no authenticated live activation exists')

    @staticmethod
    def configuration_hash(profile):
        require(isinstance(profile, dict) and set(profile) == {'model_profile','image_ref','gpu_type','gpu_count','region','worker_endpoint','storage_id'},
                'Exact approved run configuration required')
        require(profile['model_profile'] == LOCK['profile'], 'Configuration must use the exact pinned Wan profile')
        require(isinstance(profile['image_ref'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/:-]*@sha256:[a-f0-9]{64}', profile['image_ref']),
                'Immutable image reference required')
        require(type(profile['gpu_count']) is int and profile['gpu_count'] == 1, 'One GPU is supported')
        for key in ('gpu_type','region','storage_id'):
            require(isinstance(profile[key], str) and 0 < len(profile[key]) <= 200, 'Run configuration field missing')
        endpoint = urlsplit(profile['worker_endpoint'])
        require(endpoint.scheme == 'https' and endpoint.hostname and not endpoint.username and not endpoint.password and
                endpoint.path in ('','/') and not endpoint.query and not endpoint.fragment, 'Private worker endpoint must be an HTTPS origin')
        return hashlib.sha256(canonical(dict(profile=profile, model_lock=LOCK)).encode()).hexdigest()

    def _link(self, db, owner, project, batch_id):
        self.control._load(db, owner, project)
        row = db.execute('SELECT approval,mode,config_hash FROM real_job_links WHERE batch=? AND owner=? AND project=?',
                         (batch_id, owner, project)).fetchone()
        if row is None:
            raise KeyError('Linked job unavailable')
        require(row[1] == 'test', 'Live job authority is not implemented')
        approval = self.budget._approval(db, owner, project, row[0])
        require(approval['mode'] == 'simulation' and self.configuration_hash(approval['terms']['profile']) == row[2],
                'Stored job configuration or approval mode changed')
        reservation = self.budget._reservation(db, owner, project, batch_id)
        require(reservation['approval_id'] == row[0], 'Reservation approval mismatch')
        return approval, reservation

    def submit(self, owner, project, request):
        self._enabled()
        require(isinstance(request, dict) and set(request) == {'approval_id','shot_ids','expected_revision','reservation_cents','runtime_seconds','idempotency_key'},
                'Exact admission fields required')
        require(isinstance(request['approval_id'], str) and type(request['expected_revision']) is int and request['expected_revision'] >= 0,
                'Approval and saved workspace revision required')
        require(isinstance(request['shot_ids'], list) and 0 < len(request['shot_ids']) <= 1000 and
                all(isinstance(s, str) for s in request['shot_ids']) and len(set(request['shot_ids'])) == len(request['shot_ids']), 'Select distinct saved shots')
        require(type(request['runtime_seconds']) is int and 1 <= request['runtime_seconds'] <= 3600, 'Invalid benchmark runtime')
        cents(request['reservation_cents'], positive=True)
        self.budget._key(request['idempotency_key'])
        with self._simulation.lifecycle.transaction() as db:
            bundle = self.control._load(db, owner, project)
            prior = db.execute('SELECT batch,request FROM budget_reservations WHERE owner=? AND project=? AND idem=?',
                               (owner, project, request['idempotency_key'])).fetchone()
            if prior:
                if prior['request'] != canonical(request):
                    raise StudioConflict('Admission idempotency conflict')
                batch_id = prior['batch']
                self._link(db, owner, project, batch_id)
            else:
                self.studio._check_revision(db, owner, request['expected_revision'])
                if any(b['idempotency_key'] == request['idempotency_key'] for b in bundle['batches']):
                    raise StudioConflict('Canonical idempotency key already used')
                shots = {s['id']: s for s in bundle['shots']}
                if any(s not in shots for s in request['shot_ids']):
                    raise KeyError('Shot unavailable')
                batch_id = uuid4().hex
                approval = self.budget._reserve(db, owner, project, batch_id, request)
                config_hash = self.configuration_hash(approval['terms']['profile'])
                now = self.control.clock()
                deadline = math.floor(now.timestamp()) + request['runtime_seconds']
                from datetime import datetime, timezone
                snapshots = [dict(shot_id=s, **{k: deepcopy(v) for k, v in shots[s].items()
                              if k not in ('id','project_id','scene_id')}) for s in request['shot_ids']]
                batch = dict(id=batch_id, project_id=project, idempotency_key=request['idempotency_key'],
                             execution_mode='runpod', model_profile=deepcopy(LOCK['profile']), shot_snapshots=snapshots,
                             budget=dict(currency='USD', approved_cents=approval['terms']['approved_cents'],
                                         reserved_cents=request['reservation_cents'], spent_cents=0),
                             approved_at=stamp(now), deadline_at=stamp(datetime.fromtimestamp(deadline, timezone.utc)),
                             state='queued', cleanup_state='pending', provider_resource_id=None)
                for shot in snapshots:
                    probe_batch = dict(batch, state='rendering')
                    attempt = self.control._attempt(probe_batch, shot, 'test-admission-check', now)
                    validate_claim(self.control._envelope(bundle, probe_batch, attempt, shot))
                bundle['batches'].append(batch)
                self.control._save(db, bundle)
                frozen = dict(mode='test', config_hash=config_hash, canonical_batch=deepcopy(batch))
                db.execute('INSERT INTO pod_batches (id,project,idem,snapshot,deadline) VALUES (?,?,?,?,?)',
                           (batch_id, project, request['idempotency_key'], canonical(frozen), deadline))
                db.execute('INSERT INTO real_job_links VALUES (?,?,?,?,?,?,?)',
                           (batch_id, owner, project, approval['id'], 'test', config_hash, stamp(now)))
        return self.status(owner, project, batch_id)

    def _refresh(self, db, owner, project, batch_id):
        approval, reservation = self._link(db, owner, project, batch_id)
        row = db.execute('SELECT state,cleanup,pod_id FROM pod_batches WHERE id=? AND project=?', (batch_id, project)).fetchone()
        require(row is not None, 'Lifecycle binding unavailable')
        bundle = self.control._load(db, owner, project)
        batch = self.control._batch(bundle, batch_id)
        total = db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM budget_events WHERE batch=?', (batch_id,)).fetchone()[0]
        batch.update(state=row[0], cleanup_state=row[1], provider_resource_id=row[2])
        batch['budget'].update(spent_cents=total, reserved_cents=(max(0, reservation['reserved_cents'] - total)
                               if reservation['state'] == 'reserved' else 0))
        self.control._reconcile(bundle, batch, self.control.clock())
        # If canonical deadline reconciliation closed a rendering job, persist that
        # transition here so worker authority never sees contradictory states.
        if batch['state'] != row[0]:
            db.execute("UPDATE pod_batches SET state=?,cleanup=CASE WHEN state='queued' THEN 'confirmed' ELSE cleanup END WHERE id=?",
                       (batch['state'], batch_id))
            if row[0] == 'queued':
                batch['cleanup_state'] = 'confirmed'
        self.control._save(db, bundle)
        return bundle, batch

    def status(self, owner, project, batch_id):
        with self.control.transaction() as db:
            bundle, batch = self._refresh(db, owner, project, batch_id)
            row = db.execute('SELECT state,cleanup,pod_id FROM pod_batches WHERE id=?', (batch_id,)).fetchone()
            return dict(batch=deepcopy(batch), budget=self.budget._status(db, owner, project),
                        lifecycle=dict(state=row[0], cleanup=row[1], pod_id=row[2]), provenance='synthetic_test_only')

    def provision(self, owner, project, batch_id):
        self._enabled()
        with self.control.transaction() as db:
            self._link(db, owner, project, batch_id)
        self._simulation.provision(owner, project, batch_id)
        return self.status(owner, project, batch_id)

    def cancel(self, owner, project, batch_id):
        self._enabled()
        with self.control.transaction() as db:
            self._link(db, owner, project, batch_id)
        self._simulation.cancel(owner, project, batch_id)
        return self.status(owner, project, batch_id)

    def watchdog(self):
        self._enabled()
        unresolved = self._simulation.watchdog()
        with self.control.transaction() as db:
            rows = db.execute('SELECT owner,project,batch FROM real_job_links').fetchall()
            for owner, project, batch in rows:
                self._refresh(db, owner, project, batch)
        return unresolved

    def record_charge(self, owner, project, batch_id, amount_cents, bill_reference, idempotency_key):
        self._enabled()
        with self.control.transaction() as db:
            self._link(db, owner, project, batch_id)
        result = self.budget.record_charge(owner, project, batch_id, amount_cents, bill_reference, idempotency_key)
        return dict(**result, job=self.status(owner, project, batch_id))

    def settle(self, owner, project, batch_id, total_cents, bill_reference, idempotency_key):
        self._enabled()
        with self.control.transaction() as db:
            self._link(db, owner, project, batch_id)
        result = self.budget.settle(owner, project, batch_id, total_cents, bill_reference, idempotency_key)
        return dict(**result, job=self.status(owner, project, batch_id))

    def authorize_scope(self, db, owner, project, batch_id):
        """Trusted transport hook; no request can install or arm this authority."""
        self._enabled()
        self._link(db, owner, project, batch_id)
        bundle = self.control._load(db, owner, project)
        batch = self.control._batch(bundle, batch_id)
        row = db.execute('SELECT state FROM pod_batches WHERE id=? AND project=?', (batch_id, project)).fetchone()
        require(batch['execution_mode'] == 'runpod' and batch['model_profile'] == LOCK['profile'] and
                row is not None and row[0] == batch['state'], 'Job/lifecycle authority is not reconciled')

    def synchronize(self, db, bundle, batch):
        """Within the completion/claim transaction, link canonical terminal outcomes."""
        if batch['execution_mode'] != 'runpod':
            return
        self._enabled()
        owner, project = bundle['project']['owner_id'], bundle['project']['id']
        self._link(db, owner, project, batch['id'])
        if batch['state'] in ('succeeded','failed','canceled'):
            db.execute("""UPDATE pod_batches SET state=?,
                       cleanup=CASE WHEN state='queued' THEN 'confirmed' ELSE cleanup END
                       WHERE id=? AND state IN ('queued','provisioning','rendering')""", (batch['state'], batch['id']))
