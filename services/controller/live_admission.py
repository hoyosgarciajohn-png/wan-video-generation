"""Authenticated, source-bound live admission records. Dispatch remains disabled.

Installed signing keys delegate approval authority; no key or signature is issued
here. These records cannot be consumed by the simulated budget/worker bridge.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
import re
from uuid import uuid4

from services.controller.budget import cents
from services.controller.live_billing import initialize as initialize_billing, totals as billing_totals
from services.controller.lifecycle import Lifecycle
from services.controller.real_jobs import RealJobBridge
from services.controller.runpod import validate_launch_profile
from services.controller.service import canonical, stamp
from services.controller.studio import require, StudioConflict
from workers.gpu.common import LOCK, timestamp, validate_claim

APPROVAL_DOMAIN = 'wan-live-owner-approval-v1'
HOST_DOMAIN = 'wan-live-host-acceptance-v1'
GRANT_FIELDS = {'id','owner','project','currency','approved_cents','max_runtime_seconds',
                'valid_until','profile','launch_profile','source_sha256'}


def _sources():
    # Admission requires the reviewed source checkout; ordinary backup imports do not.
    from services.controller.preflight import _sources as source_inventory
    return source_inventory()


def _build(directory, image_ref):
    from services.controller.preflight import _build as verify_build
    return verify_build(directory, image_ref)


def configuration_hash(profile, launch_profile):
    RealJobBridge.configuration_hash(profile)
    launch = validate_launch_profile(launch_profile)
    return hashlib.sha256(canonical(dict(profile=profile, launch_profile=launch, model_lock=LOCK)).encode()).hexdigest()


class AuthorityError(PermissionError):
    pass


def _verify(envelope, keys, domain, owner):
    if not isinstance(envelope, dict) or set(envelope) != {'key_id','payload','signature'}:
        raise AuthorityError('Signed authority required')
    key_id = envelope['key_id']
    installed = keys.get(key_id) if isinstance(key_id, str) else None
    if installed is None or installed[0] != owner:
        raise AuthorityError('Approval key is not installed for this owner')
    payload, signature = envelope['payload'], envelope['signature']
    if not isinstance(payload, dict) or not isinstance(signature, str) or re.fullmatch(r'[a-f0-9]{64}', signature) is None:
        raise AuthorityError('Invalid signed authority')
    message = (domain + '\n' + canonical(payload)).encode()
    expected = hmac.new(installed[1], message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AuthorityError('Invalid signed authority')
    return deepcopy(payload)


def _keys(values):
    require(isinstance(values, dict), 'Installed key mapping required')
    result = {}
    for key_id, binding in values.items():
        require(isinstance(key_id, str) and 0 < len(key_id) <= 100 and
                isinstance(binding, tuple) and len(binding) == 2 and
                isinstance(binding[0], str) and bool(binding[0]) and
                isinstance(binding[1], bytes) and len(binding[1]) >= 32, 'Invalid installed authority key')
        result[key_id] = binding
    return result


class _DisarmedProvider:
    def __getattr__(self, name):
        raise AuthorityError('Live provider dispatch is disabled')


class LiveAdmission:
    def __init__(self, studio, *, approval_keys=None, host_keys=None, build_evidence=None):
        self.studio, self.control = studio, studio.control
        self._approval_keys = _keys(approval_keys or {})
        self._host_keys = _keys(host_keys or {})
        self._build_evidence = build_evidence
        self._lifecycle = Lifecycle(self.control.db_path, _DisarmedProvider())
        with self.control.transaction() as db:
            initialize_billing(db)
            db.execute('''CREATE TABLE IF NOT EXISTS live_approvals (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
                envelope TEXT NOT NULL, created TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)''')
            db.execute('''CREATE TABLE IF NOT EXISTS live_reservations (
                batch TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
                approval TEXT NOT NULL, idem TEXT NOT NULL, request TEXT NOT NULL,
                reserved_cents INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'reserved',
                created TEXT NOT NULL, UNIQUE(owner,project,idem))''')
            db.execute('''CREATE TABLE IF NOT EXISTS live_job_links (
                batch TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
                approval TEXT NOT NULL, config_hash TEXT NOT NULL,
                dispatch_state TEXT NOT NULL DEFAULT 'disabled')''')

    @staticmethod
    def _identifier(value):
        require(isinstance(value, str) and 0 < len(value.strip()) <= 200, 'Identifier required')

    def _grant(self, owner, project, envelope, *, current=True):
        grant = _verify(envelope, self._approval_keys, APPROVAL_DOMAIN, owner)
        require(set(grant) == GRANT_FIELDS, 'Exact approval fields required')
        if grant['owner'] != owner or grant['project'] != project:
            raise AuthorityError('Approval owner or project mismatch')
        require(isinstance(grant['id'], str) and re.fullmatch(r'[A-Za-z0-9_-]{1,200}', grant['id']), 'Route-compatible approval ID required')
        require(grant['currency'] == 'USD', 'Only USD approval supported')
        cents(grant['approved_cents'], positive=True)
        require(type(grant['max_runtime_seconds']) is int and 1 <= grant['max_runtime_seconds'] <= 3600,
                'Benchmark runtime must be 1 to 3600 seconds')
        expiry = timestamp(grant['valid_until'])
        profile = grant['profile']
        RealJobBridge.configuration_hash(profile)
        launch = validate_launch_profile(grant['launch_profile'])
        require(launch['image'] == profile['image_ref'] and launch['gpu'] == {'id': profile['gpu_type'], 'count': 1} and
                launch['dataCenterIds'] == [profile['region']], 'Launch and worker configuration mismatch')
        # Approval artifacts are durable audit material: credentials are never signed or stored here.
        require(launch['env'] == {}, 'Approval launch profile must contain no runtime credentials')
        if current:
            require(expiry > self.control.clock(), 'Approval expired')
            require(grant['source_sha256'] == _sources(), 'Approved source inventory changed')
        return grant, configuration_hash(profile, launch)

    def _approval(self, db, owner, project, approval_id, *, current=True):
        row = db.execute('SELECT envelope,revoked FROM live_approvals WHERE id=? AND owner=? AND project=?',
                         (approval_id, owner, project)).fetchone()
        if row is None:
            raise KeyError('Live approval unavailable')
        require(not row[1], 'Live approval revoked')
        return self._grant(owner, project, json.loads(row[0]), current=current)

    def approve(self, owner, project, envelope):
        """owner MUST come from the authenticated host session, never request JSON."""
        with self.control.transaction() as db:
            self.control._load(db, owner, project)
            grant, config_hash = self._grant(owner, project, envelope)
            prior = db.execute('SELECT envelope,revoked FROM live_approvals WHERE id=?', (grant['id'],)).fetchone()
            if prior:
                if prior[0] != canonical(envelope):
                    raise StudioConflict('Approval ID reused with different signed terms')
                require(not prior[1], 'Live approval revoked')
            else:
                db.execute('INSERT INTO live_approvals (id,owner,project,envelope,created) VALUES (?,?,?,?,?)',
                           (grant['id'], owner, project, canonical(envelope), stamp(self.control.clock())))
            return dict(id=grant['id'], approved_cents=grant['approved_cents'], max_runtime_seconds=grant['max_runtime_seconds'],
                        valid_until=grant['valid_until'], config_hash=config_hash, dispatch_enabled=False)

    def revoke(self, owner, project, approval_id):
        with self.control.transaction() as db:
            self.control._load(db, owner, project)
            row = db.execute('SELECT id FROM live_approvals WHERE id=? AND owner=? AND project=?',
                             (approval_id, owner, project)).fetchone()
            if row is None:
                raise KeyError('Live approval unavailable')
            db.execute('UPDATE live_approvals SET revoked=1 WHERE id=?', (approval_id,))
        return dict(id=approval_id, revoked=True, dispatch_enabled=False)

    def submit(self, owner, project, request):
        require(isinstance(request, dict) and set(request) == {'approval_id','shot_ids','expected_revision',
                'reservation_cents','runtime_seconds','idempotency_key'}, 'Exact live admission fields required')
        for key in ('approval_id', 'idempotency_key'):
            self._identifier(request[key])
        cents(request['reservation_cents'], positive=True)
        require(type(request['runtime_seconds']) is int and 1 <= request['runtime_seconds'] <= 3600 and
                type(request['expected_revision']) is int and request['expected_revision'] >= 0, 'Invalid runtime or revision')
        ids = request['shot_ids']
        require(isinstance(ids, list) and len(ids) == 1 and isinstance(ids[0], str), 'First live admission is one saved shot only')
        with self.control.transaction() as db:
            bundle = self.control._load(db, owner, project)
            prior = db.execute('SELECT batch,request FROM live_reservations WHERE owner=? AND project=? AND idem=?',
                               (owner, project, request['idempotency_key'])).fetchone()
            if prior:
                if prior[1] != canonical(request):
                    raise StudioConflict('Admission idempotency conflict')
                batch_id = prior[0]
            else:
                self.studio._check_revision(db, owner, request['expected_revision'])
                if any(b['idempotency_key'] == request['idempotency_key'] for b in bundle['batches']):
                    raise StudioConflict('Canonical idempotency key already used')
                grant, config_hash = self._approval(db, owner, project, request['approval_id'])
                # Each latest installed grant is a total project cap, never additive.
                latest = db.execute('SELECT id FROM live_approvals WHERE owner=? AND project=? ORDER BY rowid DESC LIMIT 1',
                                    (owner, project)).fetchone()[0]
                require(latest == grant['id'], 'Approval is not current')
                balance = billing_totals(db, owner, project)
                require(balance['spent_cents'] + balance['reserved_cents'] + request['reservation_cents'] <= grant['approved_cents'], 'Insufficient live budget')
                now = self.control.clock()
                deadline = math.floor(now.timestamp()) + request['runtime_seconds']
                require(request['runtime_seconds'] <= grant['max_runtime_seconds'] and deadline <= timestamp(grant['valid_until']).timestamp(),
                        'Runtime exceeds signed approval')
                shots = {s['id']: s for s in bundle['shots']}
                if ids[0] not in shots:
                    raise KeyError('Shot unavailable')
                shot = shots[ids[0]]
                snapshot = dict(shot_id=shot['id'], **{k: deepcopy(v) for k, v in shot.items() if k not in ('id','project_id','scene_id')})
                batch_id = uuid4().hex
                batch = dict(id=batch_id, project_id=project, idempotency_key=request['idempotency_key'], execution_mode='runpod',
                             model_profile=deepcopy(LOCK['profile']), shot_snapshots=[snapshot],
                             budget=dict(currency='USD', approved_cents=grant['approved_cents'], reserved_cents=request['reservation_cents'], spent_cents=0),
                             approved_at=stamp(now), deadline_at=stamp(datetime.fromtimestamp(deadline, timezone.utc)),
                             state='queued', cleanup_state='pending', provider_resource_id=None)
                probe = dict(batch, state='rendering')
                attempt = self.control._attempt(probe, snapshot, 'live-admission-check', now)
                validate_claim(self.control._envelope(bundle, probe, attempt, snapshot))
                bundle['batches'].append(batch)
                self.control._save(db, bundle)
                db.execute('INSERT INTO live_reservations (batch,owner,project,approval,idem,request,reserved_cents,created) VALUES (?,?,?,?,?,?,?,?)',
                           (batch_id, owner, project, grant['id'], request['idempotency_key'], canonical(request), request['reservation_cents'], stamp(now)))
                frozen = dict(mode='live_pending', config_hash=config_hash, canonical_batch=deepcopy(batch))
                db.execute('INSERT INTO pod_batches (id,project,idem,snapshot,deadline) VALUES (?,?,?,?,?)',
                           (batch_id, project, request['idempotency_key'], canonical(frozen), deadline))
                db.execute('INSERT INTO live_job_links (batch,owner,project,approval,config_hash) VALUES (?,?,?,?,?)',
                           (batch_id, owner, project, grant['id'], config_hash))
            return self._status(db, owner, project, batch_id)

    def _status(self, db, owner, project, batch_id):
        bundle = self.control._load(db, owner, project)
        row = db.execute('SELECT state,reserved_cents,approval FROM live_reservations WHERE batch=? AND owner=? AND project=?',
                         (batch_id, owner, project)).fetchone()
        if row is None:
            raise KeyError('Live job unavailable')
        return dict(batch=deepcopy(self.control._batch(bundle, batch_id)), reservation_state=row[0],
                    reservation_cents=row[1], approval_id=row[2], dispatch_enabled=False,
                    blocking_gate='live_worker_dispatch_not_installed')

    def status(self, owner, project, batch_id):
        with self.control.transaction() as db:
            return self._status(db, owner, project, batch_id)

    def cancel(self, owner, project, batch_id):
        with self.control.transaction() as db:
            self._status(db, owner, project, batch_id)
            row = db.execute('SELECT state,cleanup,pod_id FROM pod_batches WHERE id=? AND project=?', (batch_id, project)).fetchone()
            link = db.execute('SELECT dispatch_state FROM live_job_links WHERE batch=?', (batch_id,)).fetchone()
            require(row is not None and row[2] is None and link is not None and link[0] == 'disabled' and
                    row[0] in ('queued','canceled'), 'Cannot release a dispatched or uncertain live obligation')
            bundle = self.control._load(db, owner, project)
            batch = self.control._batch(bundle, batch_id)
            batch.update(state='canceled', cleanup_state='confirmed')
            batch['budget']['reserved_cents'] = 0
            self.control._save(db, bundle)
            db.execute("UPDATE pod_batches SET state='canceled',cleanup='confirmed' WHERE id=?", (batch_id,))
            db.execute("UPDATE live_reservations SET state='released' WHERE batch=?", (batch_id,))
            return self._status(db, owner, project, batch_id)

    def verify_execution_evidence(self, db, owner, project, approval_id, host_envelope):
        """Verify prerequisites; intentionally cannot return a spending-capable provider."""
        self.control._load(db, owner, project)
        grant, config_hash = self._approval(db, owner, project, approval_id)
        require(self._build_evidence is not None, 'Verified build evidence is not installed')
        evidence = _build(self._build_evidence, grant['profile']['image_ref'])
        host = _verify(host_envelope, self._host_keys, HOST_DOMAIN, owner)
        require(set(host) == {'owner','project','config_hash','source_sha256','build_manifest_sha256','valid_until','worker_endpoint','storage_id'},
                'Exact host acceptance evidence required')
        require(host['owner'] == owner and host['project'] == project and host['config_hash'] == config_hash and
                host['source_sha256'] == grant['source_sha256'] and
                host['build_manifest_sha256'] == evidence['manifest_sha256'] and
                host['worker_endpoint'] == grant['profile']['worker_endpoint'] and host['storage_id'] == grant['profile']['storage_id'] and
                timestamp(host['valid_until']) > self.control.clock(), 'Host acceptance does not match approved execution')
        return grant, host

    def prepare_provider(self, owner, project, approval_id, host_envelope):
        """Legacy planning API never installs a transport; use trusted LiveExecution."""
        with self.control.transaction() as db:
            self.verify_execution_evidence(db, owner, project, approval_id, host_envelope)
        raise AuthorityError('Live worker dispatch is not installed; no provider transport can be returned')
