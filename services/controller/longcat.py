"""Private signed LongCat admission and durable, credential-scoped media recovery.

No HTTP admission, provider allocation, authority signing or reservation release.
The operator must supply independently installed owner/host signatures. A new
scope cannot reset the retained budget or conceal an interrupted inference.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import tempfile

from services.controller.live_admission import _keys, _verify
from services.controller.service import canonical
from services.controller.worker_transport import WorkerAccessError, MAX_ARTIFACT_BYTES
from workers.gpu.common import digest, require, scoped, sync_dir
from workers.gpu.longcat_batch import fingerprint, validate_execution, validate_manifest, validate_reference_images, verify_output

OWNER_DOMAIN = 'wan-longcat-owner-v1'
HOST_DOMAIN = 'wan-longcat-host-v1'
CLEANUP_DOMAIN = 'wan-longcat-cleanup-host-v1'
IDENTIFIER = r'[A-Za-z0-9_-]{1,80}'


def pod_name(scope_id):
    return 'wan-longcat-song-'+hashlib.sha256(scope_id.encode()).hexdigest()[:16]


def source_digest():
    root = Path(__file__).resolve().parents[2]
    names = ['services/controller/longcat.py', 'services/controller/http_api.py',
             'deployment/hosted_app.py', 'workers/gpu/longcat_batch.py',
             'workers/gpu/longcat_client.py', 'workers/gpu/longcat_resident.py',
             'workers/gpu/longcat_bootstrap.py', 'workers/gpu/longcat.Dockerfile',
             'benchmarks/longcat/model_manifest.json', 'contracts/runtime-policy.json',
             'services/controller/backup.py', 'deployment/longcat_guard.py',
             'workers/media/longcat_assemble.py']
    return fingerprint({name: digest(root/name) for name in names})


class LongCatTransport:
    def __init__(self, control, *, verify=verify_output):
        self.control, self.verify = control, verify
        with control.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS longcat_budgets (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, terms TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS longcat_scopes (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
                batch TEXT NOT NULL UNIQUE, budget TEXT NOT NULL, reserved INTEGER NOT NULL,
                grant TEXT NOT NULL, host TEXT NOT NULL, manifest TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE, revoked INTEGER NOT NULL DEFAULT 0)''')
            db.execute('''CREATE TABLE IF NOT EXISTS longcat_shots (
                scope TEXT NOT NULL, shot TEXT NOT NULL, state TEXT NOT NULL,
                receipt TEXT, PRIMARY KEY(scope,shot))''')
            db.execute('''CREATE TABLE IF NOT EXISTS longcat_cleanup (
                scope TEXT PRIMARY KEY, envelope TEXT NOT NULL)''')

    def now(self):
        return self.control.clock().timestamp()

    def root(self, project, batch):
        return scoped(self.control.asset_root, f'longcat/{project}/{batch}')

    def admit(self, owner, manifest, inputs, owner_envelope, host_envelope, *, approval_keys, host_keys):
        """Trusted host only. Plaintext credential is returned once, never stored."""
        grant = _verify(owner_envelope, _keys(approval_keys), OWNER_DOMAIN, owner)
        host = _verify(host_envelope, _keys(host_keys), HOST_DOMAIN, owner)
        require(set(grant) == {'owner', 'project', 'execution', 'image_ref', 'source_sha256',
                              'budget_id', 'budget_total_cents', 'prior_committed_cents',
                              'storage_reserve_cents'}, 'Exact signed grant required')
        require(grant['owner'] == owner and grant['project'] == manifest['project_id'], 'Owner/project mismatch')
        validate_manifest(manifest, inputs)
        validate_reference_images(manifest, inputs)
        execution = validate_execution(grant['execution'], self.now())
        require(execution['manifest_sha256'] == fingerprint(manifest), 'Manifest grant mismatch')
        require(re.fullmatch(IDENTIFIER, execution['scope_id']) and
                re.fullmatch(IDENTIFIER, grant['budget_id']), 'Invalid scope/budget identity')
        require(grant['source_sha256'] == source_digest(), 'Reviewed source changed')
        require(isinstance(grant['image_ref'], str) and re.fullmatch(
            r'ghcr\.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:[a-f0-9]{64}', grant['image_ref']),
            'Pinned private runtime image required')
        expected_host = dict(owner=owner, project=grant['project'], grant_sha256=fingerprint(grant),
                             source_sha256=grant['source_sha256'], image_ref=grant['image_ref'],
                             guard_run_id=execution['guard_run_id'], deadline=execution['deadline'],
                             pod_name=pod_name(execution['scope_id']),
                             image_import_verified=True, guard_ready=True, storage_verified=True)
        require(host == expected_host, 'Signed image/storage/guard acceptance required')
        for key in ('budget_total_cents', 'prior_committed_cents', 'storage_reserve_cents'):
            require(type(grant[key]) is int and grant[key] >= 0, 'Integer budget cents required')
        require(0 < grant['budget_total_cents'] <= 2000 and grant['storage_reserve_cents'] > 0,
                'Project budget exceeds ceiling or lacks reserve')
        terms = {k: grant[k] for k in ('budget_total_cents', 'prior_committed_cents', 'storage_reserve_cents')}
        with self.control.transaction() as db:
            bundle = self.control._load(db, owner, grant['project'])
            require(manifest['duration_frames']*40 <= bundle['project']['runtime_limit_ms'], 'Project duration cap exceeded')
            require(db.execute('SELECT 1 FROM longcat_scopes WHERE id=? OR batch=?',
                               (execution['scope_id'], manifest['batch_id'])).fetchone() is None,
                    'Scope/batch already consumed; never renew its deadline')
            prior = db.execute('SELECT owner,terms FROM longcat_budgets WHERE id=?', (grant['budget_id'],)).fetchone()
            if prior:
                require(prior == (owner, canonical(terms)), 'Retained budget cannot be reset')
            else:
                # A second ledger for the same owner's project would reset spent/reserved usage.
                require(db.execute('SELECT 1 FROM longcat_scopes WHERE owner=? AND project=?',
                                   (owner, grant['project'])).fetchone() is None, 'Project already has a budget ledger')
                db.execute('INSERT INTO longcat_budgets VALUES (?,?,?)', (grant['budget_id'], owner, canonical(terms)))
            reserved = db.execute('SELECT COALESCE(SUM(reserved),0) FROM longcat_scopes WHERE budget=?',
                                  (grant['budget_id'],)).fetchone()[0]
            require(reserved + execution['compute_cap_cents'] + grant['prior_committed_cents'] +
                    grant['storage_reserve_cents'] <= grant['budget_total_cents'], 'Insufficient retained budget')
            destination = self.root(grant['project'], manifest['batch_id'])/'inputs'
            require(not destination.exists(), 'Input destination already exists; reconcile before admission')
            destination.mkdir(parents=True)
            try:
                assets = {s[k]['path']: s[k] for s in manifest['shots'] for k in ('image','audio')}
                for name, asset in assets.items():
                    target = scoped(destination, name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with scoped(inputs, name).open('rb') as source, target.open('xb') as out:
                        shutil.copyfileobj(source, out, 65536); out.flush(); os.fsync(out.fileno())
                    require(digest(target) == asset['sha256'], 'Input changed while staging')
                    sync_dir(target.parent)
                validate_manifest(manifest, destination)
                token = secrets.token_urlsafe(32)
                db.execute('INSERT INTO longcat_scopes (id,owner,project,batch,budget,reserved,grant,host,manifest,token_hash) VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (execution['scope_id'], owner, grant['project'], manifest['batch_id'], grant['budget_id'],
                            execution['compute_cap_cents'], canonical(owner_envelope), canonical(host_envelope),
                            canonical(manifest), hashlib.sha256(token.encode()).hexdigest()))
            except BaseException:
                shutil.rmtree(destination)
                raise
        return dict(token=token, scope_id=execution['scope_id'], deadline=execution['deadline'],
                    binding=fingerprint(manifest), image_ref=grant['image_ref'],pod_name=pod_name(execution['scope_id']))

    def _principal(self, db, authorization, *, recovery=False):
        if not isinstance(authorization, str) or not re.fullmatch(r'Bearer [A-Za-z0-9_-]{32,256}', authorization):
            raise WorkerAccessError(401)
        row = db.execute('SELECT id,owner,project,batch,grant,manifest,revoked FROM longcat_scopes WHERE token_hash=?',
                         (hashlib.sha256(authorization[7:].encode()).hexdigest(),)).fetchone()
        if not row or row[6]: raise WorkerAccessError(401)
        grant = json.loads(row[4])['payload']; execution = grant['execution']
        if self.now() >= execution['deadline'] + (180 if recovery else -35): raise WorkerAccessError(401)
        self.control._load(db, row[1], row[2])
        return dict(scope=row[0], owner=row[1], project=row[2], batch=row[3], execution=execution,
                    manifest=json.loads(row[5]))

    @staticmethod
    def _shot(principal, shot_id):
        shot = next((s for s in principal['manifest']['shots'] if s['id'] == shot_id), None)
        if shot is None: raise WorkerAccessError(404)
        return shot

    def configuration(self, authorization):
        with self.control.transaction() as db:
            p = self._principal(db, authorization)
            return dict(manifest=p['manifest'], execution=p['execution'])

    def input_file(self, authorization, shot_id, kind):
        with self.control.transaction() as db:
            p = self._principal(db, authorization)
            if kind not in ('image','audio'): raise WorkerAccessError(404)
            asset = self._shot(p, shot_id)[kind]
            path = scoped(self.root(p['project'], p['batch'])/'inputs', asset['path'])
            require(path.is_file() and digest(path) == asset['sha256'], 'Stored input changed')
            return path, dict(sha256=asset['sha256'], bytes=path.stat().st_size)

    def start(self, authorization, shot_id):
        with self.control.transaction() as db:
            p = self._principal(db, authorization); self._shot(p, shot_id)
            require(self.now() + 150 < p['execution']['deadline'], 'Recovery time exhausted')
            existing = db.execute('SELECT state FROM longcat_shots WHERE scope=? AND shot=?', (p['scope'], shot_id)).fetchone()
            if existing: raise WorkerAccessError(409)
            for shot in p['manifest']['shots']:
                if shot['id'] == shot_id: break
                previous = db.execute('SELECT state FROM longcat_shots WHERE scope=? AND shot=?', (p['scope'], shot['id'])).fetchone()
                require(previous == ('published',), 'Previous shot lacks durable recovery')
            db.execute('INSERT INTO longcat_shots VALUES (?,?,?,NULL)', (p['scope'], shot_id, 'rendering'))
            return dict(shot_id=shot_id, binding=fingerprint(p['manifest']), state='rendering')

    def _receipt(self, db, p, shot_id):
        self._shot(p, shot_id)
        row = db.execute('SELECT receipt FROM longcat_shots WHERE scope=? AND shot=?', (p['scope'], shot_id)).fetchone()
        if not row or row[0] is None: return None
        receipt = json.loads(row[0]); path = scoped(self.control.asset_root, receipt['object_key'])
        require(path.is_file() and path.stat().st_size == receipt['bytes'] and digest(path) == receipt['sha256'],
                'Durable output missing or changed')
        return receipt

    def receipt(self, authorization, shot_id):
        with self.control.transaction() as db:
            p = self._principal(db, authorization, recovery=True)
            return self._receipt(db, p, shot_id)

    def upload(self, authorization, shot_id, checksum, length, stream):
        require(type(length) is int and 0 < length <= MAX_ARTIFACT_BYTES and
                isinstance(checksum, str) and re.fullmatch(r'[a-f0-9]{64}', checksum), 'Invalid output size/hash')
        with self.control.transaction() as db:
            p = self._principal(db, authorization); self._shot(p, shot_id)
            prior = self._receipt(db, p, shot_id)
            if prior:
                require((prior['sha256'], prior['bytes']) == (checksum, length), 'Conflicting immutable output')
                return prior
            require(db.execute('SELECT state FROM longcat_shots WHERE scope=? AND shot=?',
                               (p['scope'],shot_id)).fetchone() == ('rendering',), 'Shot was not admitted to inference')
        staging = self.root(p['project'], p['batch'])/'staging'; staging.mkdir(exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=staging, suffix='.mp4', delete=False) as out:
                temp = Path(out.name); remaining = length
                while remaining:
                    block = stream.read(min(65536, remaining))
                    require(block and len(block) <= remaining, 'Incomplete artifact stream')
                    out.write(block); remaining -= len(block)
                out.flush(); os.fsync(out.fileno())
            require(digest(temp) == checksum, 'Artifact hash mismatch')
            metadata = self.verify(temp)
            require(metadata['sha256'] == checksum and metadata['bytes'] == length, 'Artifact verification mismatch')
            with self.control.transaction() as db:
                current = self._principal(db, authorization)
                require(current['scope'] == p['scope'], 'Credential scope changed')
                prior = self._receipt(db, p, shot_id)
                if prior:
                    require((prior['sha256'],prior['bytes']) == (checksum,length), 'Conflicting immutable output')
                    return prior
                key = f"longcat/{p['project']}/{p['batch']}/takes/{shot_id}-{checksum}.mp4"
                target = scoped(self.control.asset_root,key); target.parent.mkdir(exist_ok=True)
                if target.exists(): require(digest(target) == checksum, 'Recovery object changed')
                else: os.replace(temp,target); sync_dir(target.parent)
                receipt = dict(binding=fingerprint(p['manifest']), shot_id=shot_id, sha256=checksum,
                               bytes=length, object_key=key, scope_id=p['scope'])
                db.execute('UPDATE longcat_shots SET state=?,receipt=? WHERE scope=? AND shot=?',
                           ('published',canonical(receipt),p['scope'],shot_id))
                return receipt
        finally:
            if temp is not None: temp.unlink(missing_ok=True)

    def revoke(self, owner, scope_id):
        with self.control.transaction() as db:
            require(db.execute('UPDATE longcat_scopes SET revoked=1 WHERE id=? AND owner=?',
                               (scope_id,owner)).rowcount == 1, 'Scope unavailable')
        # Reservations remain retained until explicit billing reconciliation.

    def confirm_cleanup(self,owner,scope_id,envelope,*,host_keys):
        """Trusted host attests provider absence; retains budget and fences token."""
        payload=_verify(envelope,_keys(host_keys),CLEANUP_DOMAIN,owner)
        with self.control.transaction() as db:
            row=db.execute('SELECT grant FROM longcat_scopes WHERE id=? AND owner=?',(scope_id,owner)).fetchone()
            require(row is not None,'Scope unavailable')
            grant=json.loads(row[0])['payload'];execution=grant['execution']
            expected=dict(owner=owner,scope_id=scope_id,grant_sha256=fingerprint(grant),
                guard_run_id=execution['guard_run_id'],pod_name=pod_name(scope_id),absence_confirmed=True,
                confirmed_at=payload.get('confirmed_at'))
            require(payload==expected and type(payload['confirmed_at']) is int and
                    execution['admitted_at']<=payload['confirmed_at']<=self.now(),'Invalid cleanup attestation')
            previous=db.execute('SELECT envelope FROM longcat_cleanup WHERE scope=?',(scope_id,)).fetchone()
            require(previous is None or previous[0]==canonical(envelope),'Cleanup attestation changed')
            db.execute('INSERT OR IGNORE INTO longcat_cleanup VALUES (?,?)',(scope_id,canonical(envelope)))
            db.execute('UPDATE longcat_scopes SET revoked=1 WHERE id=?',(scope_id,))
        return dict(status='CLEANUP_RECORDED_RESERVATION_RETAINED',scope_id=scope_id)
