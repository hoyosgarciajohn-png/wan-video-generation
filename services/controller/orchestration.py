"""Simulation-only reservation + durable queue/lifecycle coordination.

No real provider is accepted, no HTTP route exposes this coordinator, and no
fixture worker is connected to these paid-shape rehearsals. Existing Lifecycle
owns create reconciliation, deadline, cancellation and independent cleanup.
"""
from copy import deepcopy
import json
import math
from uuid import uuid4

from services.controller.budget import BudgetLedger, cents
from services.controller.lifecycle import Lifecycle
from services.controller.service import canonical
from services.controller.studio import StudioConflict, require
from src.wan_platform.fake_provider import FakeGpuProvider
from workers.gpu.common import timestamp


class SimulationCoordinator:
    def __init__(self, studio, provider=None):
        if provider is None:
            provider = FakeGpuProvider()
        require(type(provider) is FakeGpuProvider, 'Only the built-in fictional provider is allowed; real dispatch is disabled')
        self.studio, self.control = studio, studio.control
        self.budget = BudgetLedger(self.control)
        self.lifecycle = Lifecycle(self.control.db_path, provider)

    def submit(self, owner, project, request):
        require(isinstance(request, dict) and set(request) == {'approval_id','shot_ids','expected_revision',
                'reservation_cents','runtime_seconds','idempotency_key'}, 'Exact queue command required')
        require(isinstance(request['approval_id'], str), 'Approval ID required')
        require(isinstance(request['shot_ids'], list) and request['shot_ids'] and len(request['shot_ids']) <= 1000 and
                all(isinstance(s, str) for s in request['shot_ids']) and len(set(request['shot_ids'])) == len(request['shot_ids']),
                'Select distinct saved shots')
        require(type(request['expected_revision']) is int and request['expected_revision'] >= 0, 'Saved workspace revision required')
        require(type(request['runtime_seconds']) is int and 0 < request['runtime_seconds'] <= 86400, 'Invalid runtime')
        cents(request['reservation_cents'], positive=True)
        self.budget._key(request['idempotency_key'])
        with self.lifecycle.transaction() as db:
            bundle = self.control._load(db, owner, project)
            prior = db.execute('SELECT batch,request FROM budget_reservations WHERE owner=? AND project=? AND idem=?',
                               (owner, project, request['idempotency_key'])).fetchone()
            if prior:
                if prior['request'] != canonical(request):
                    raise StudioConflict('Queue idempotency conflict')
                batch_id = prior['batch']
            else:
                self.studio._check_revision(db, owner, request['expected_revision'])
                if db.execute('SELECT id FROM pod_batches WHERE project=? AND idem=?', (project, request['idempotency_key'])).fetchone():
                    raise StudioConflict('Lifecycle idempotency key is already in use')
                shots = {s['id']: s for s in bundle['shots']}
                if any(s not in shots for s in request['shot_ids']):
                    raise KeyError('Shot unavailable')
                batch_id = uuid4().hex
                approval = self.budget._reserve(db, owner, project, batch_id, request)
                snapshot = dict(mode='simulation', project_id=project, approval_id=approval['id'],
                                profile=deepcopy(approval['terms']['profile']),
                                shot_snapshots=[dict(shot_id=s, **{k: deepcopy(v) for k, v in shots[s].items()
                                    if k not in ('id','project_id','scene_id')}) for s in request['shot_ids']])
                # Insertion shares the reservation transaction; Lifecycle supplies all
                # subsequent transitions. No crash can leave a dispatchable unreserved row.
                deadline = math.floor(self.control.clock().timestamp()) + request['runtime_seconds']
                db.execute('INSERT INTO pod_batches (id,project,idem,snapshot,deadline) VALUES (?,?,?,?,?)',
                           (batch_id, project, request['idempotency_key'], canonical(snapshot), deadline))
        return self.status(owner, project, batch_id)

    def _authorize(self, owner, project, batch):
        with self.control.transaction() as db:
            self.control._load(db, owner, project)
            return self.budget._reservation(db, owner, project, batch)

    def status(self, owner, project, batch):
        self._authorize(owner, project, batch)
        row = self.lifecycle.status(project, batch)
        row['snapshot'] = json.loads(row['snapshot'])
        return dict(batch=row, budget=self.budget.status(owner, project))

    def _authorize_dispatch(self, db, owner, project, batch):
        reservation = self.budget._reservation(db, owner, project, batch)
        budget = self.budget._status(db, owner, project)
        approval = budget['approval']
        require(approval is not None and approval['id'] == reservation['approval_id'] and
                approval['mode'] == 'simulation' and not approval['revoked'] and
                timestamp(approval['terms']['valid_until']) > self.control.clock(),
                'Dispatch approval is no longer current')
        require(not budget['overcommitted'] and budget['spent_cents'] < budget['approved_cents'],
                'Observed liability exhausts or exceeds approval; additional dispatch is blocked')
        require(reservation['state'] == 'reserved', 'Dispatch requires an unsettled reservation')
        deadline = db.execute('SELECT deadline FROM pod_batches WHERE id=?', (batch,)).fetchone()[0]
        require(deadline > self.control.clock().timestamp(), 'Dispatch deadline reached')

    def provision(self, owner, project, batch):
        self._authorize(owner, project, batch)
        self.lifecycle.provision(project, batch, self.control.clock().timestamp(),
                                 authorize=lambda db: self._authorize_dispatch(db, owner, project, batch))
        return self.status(owner, project, batch)

    def cancel(self, owner, project, batch):
        self._authorize(owner, project, batch)
        self.lifecycle.cancel(project, batch)
        return self.status(owner, project, batch)

    def finish(self, owner, project, batch, outcome):
        self._authorize(owner, project, batch)
        self.lifecycle.finish(batch, outcome)
        return self.status(owner, project, batch)

    def watchdog(self):
        """Trusted system entry point; run independently of the render worker."""
        with self.control.transaction() as db:
            require(not db.execute('SELECT id FROM pod_batches WHERE id NOT IN (SELECT batch FROM budget_reservations)').fetchone(),
                    'This simulation database contains unmanaged lifecycle rows')
        return self.lifecycle.watchdog(self.control.clock().timestamp())
