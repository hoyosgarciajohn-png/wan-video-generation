"""Private fixture-worker transport and trusted scoped credential provisioning."""
import argparse
from datetime import timedelta
import hashlib
import os
from pathlib import Path
import re
import secrets
import tempfile
from uuid import uuid4

from services.controller.service import ControlService, stamp
from services.controller.studio import require
from workers.gpu.common import digest, scoped, sync_dir, timestamp

MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
IDENTIFIER = r'[A-Za-z0-9][A-Za-z0-9._-]*'


class WorkerAccessError(ValueError):
    def __init__(self, status):
        self.status = status
        super().__init__('Worker request unavailable')


class WorkerTransport:
    def __init__(self, control, *, real_jobs=None):
        if real_jobs is not None:
            from services.controller.real_jobs import RealJobBridge
            require(type(real_jobs) is RealJobBridge and real_jobs.control is control, 'Invalid server job authority')
        self.real_jobs = real_jobs
        self.control = control
        with control.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS worker_credentials (
                id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
                owner TEXT NOT NULL, project TEXT NOT NULL, batch TEXT NOT NULL,
                worker TEXT NOT NULL, expires TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL)''')

    def _allowed_batch(self, db, owner, project, batch):
        if batch['execution_mode'] == 'fixture':
            if any(batch['budget'][k] for k in ('approved_cents','reserved_cents','spent_cents')):
                raise WorkerAccessError(403)
            return
        if self.real_jobs is None:
            raise WorkerAccessError(403)
        try:
            self.real_jobs.authorize_scope(db, owner, project, batch['id'])
        except (KeyError, ValueError):
            raise WorkerAccessError(403) from None

    def issue(self, owner, project, batch_id, worker_id, *, ttl_seconds=300):
        """Trusted host/CLI only; return plaintext once and persist only its SHA256."""
        require(isinstance(worker_id, str) and len(worker_id) <= 200 and re.fullmatch(IDENTIFIER, worker_id), 'Invalid worker ID')
        require(type(ttl_seconds) is int and 0 < ttl_seconds <= 3600, 'Worker credential TTL must be 1 to 3600 seconds')
        with self.control.transaction() as db:
            bundle = self.control._load(db, owner, project)
            batch = self.control._batch(bundle, batch_id)
            self._allowed_batch(db, owner, project, batch)
            now = self.control.clock()
            expiry = now + timedelta(seconds=ttl_seconds)
            # Tokens may outlive a render deadline briefly to reconcile a completion
            # receipt, but never extend an attempt lease or permit fresh late claims.
            token, credential_id = secrets.token_urlsafe(32), uuid4().hex
            db.execute('INSERT INTO worker_credentials (id,token_hash,owner,project,batch,worker,expires,created) VALUES (?,?,?,?,?,?,?,?)',
                       (credential_id, hashlib.sha256(token.encode()).hexdigest(), owner, project, batch_id,
                        worker_id, stamp(expiry), stamp(now)))
            return dict(id=credential_id, token=token, project_id=project, batch_id=batch_id,
                        worker_id=worker_id, expires_at=stamp(expiry))

    def revoke(self, owner, project, credential_id):
        with self.control.transaction() as db:
            self.control._load(db, owner, project)
            changed = db.execute('UPDATE worker_credentials SET revoked=1 WHERE id=? AND owner=? AND project=?',
                                 (credential_id, owner, project)).rowcount
            if not changed:
                raise KeyError('Credential unavailable')

    def principal(self, authorization):
        if not isinstance(authorization, str) or not re.fullmatch(r'Bearer [A-Za-z0-9_-]{32,256}', authorization):
            raise WorkerAccessError(401)
        token_hash = hashlib.sha256(authorization[7:].encode()).hexdigest()
        with self.control.transaction() as db:
            row = db.execute('SELECT owner,project,batch,worker,expires,revoked FROM worker_credentials WHERE token_hash=?', (token_hash,)).fetchone()
            if row is None or row[5] or timestamp(row[4]) <= self.control.clock():
                raise WorkerAccessError(401)
            principal = dict(zip(('owner','project','batch','worker','expires','revoked'), row))
            try:
                bundle = self.control._load(db, principal['owner'], principal['project'])
                self._allowed_batch(db, principal['owner'], principal['project'], self.control._batch(bundle, principal['batch']))
            except (KeyError, StopIteration):
                raise WorkerAccessError(401) from None
            return principal

    def _attempt(self, authorization, attempt_id, lease_id, *, active=True):
        principal = self.principal(authorization)
        with self.control.transaction() as db:
            bundle = self.control._load(db, principal['owner'], principal['project'])
            batch = self.control._batch(bundle, principal['batch'])
            attempt = next((a for a in bundle['attempts'] if a['id'] == attempt_id and
                            a['batch_id'] == batch['id'] and a['worker_id'] == principal['worker']), None)
            if attempt is None or not isinstance(lease_id, str) or attempt['lease_id'] != lease_id:
                raise WorkerAccessError(404)
            if active and (batch['state'] != 'rendering' or attempt['state'] not in ('claimed','running') or
                           self.control.clock() >= min(timestamp(attempt['lease_expires_at']), timestamp(batch['deadline_at']))):
                raise WorkerAccessError(409)
            return principal, bundle, batch, attempt

    def _credential_fence(self, db, authorization, principal):
        token_hash = hashlib.sha256(authorization[7:].encode()).hexdigest()
        row = db.execute('SELECT owner,project,batch,worker,expires,revoked FROM worker_credentials WHERE token_hash=?',
                         (token_hash,)).fetchone()
        if (row is None or row[5] or timestamp(row[4]) <= self.control.clock() or
                tuple(row[:4]) != tuple(principal[k] for k in ('owner','project','batch','worker'))):
            raise WorkerAccessError(401)
        bundle = self.control._load(db, principal['owner'], principal['project'])
        self._allowed_batch(db, principal['owner'], principal['project'], self.control._batch(bundle, principal['batch']))

    def call(self, authorization, route, payload):
        require(isinstance(payload, dict), 'JSON object required')
        principal = self.principal(authorization)
        client = self.control.worker_client(principal['owner'], principal['project'], principal['batch'], principal['worker'],
                     authorize=lambda db: self._credential_fence(db, authorization, principal),
                     synchronize=self.real_jobs.synchronize if self.real_jobs is not None else None)
        if route == 'claim':
            require(not payload, 'Claim body must be empty')
            return client.claim()
        match = re.fullmatch(rf'attempts/({IDENTIFIER})/(heartbeat|complete|fail)', route)
        if not match:
            raise WorkerAccessError(404)
        attempt_id, action = match.groups()
        field = {'heartbeat':'progress','complete':'output_asset_manifest','fail':'code'}[action]
        require(set(payload) == {'lease_id',field} and isinstance(payload['lease_id'], str), 'Invalid worker message')
        if action == 'heartbeat':
            require(type(payload[field]) in (float,int) and 0 <= payload[field] <= 1, 'Invalid progress')
        elif action == 'fail':
            require(payload[field] in ('render_failed','worker_failed'), 'Unknown failure code')
        else:
            require(isinstance(payload[field], dict) and set(payload[field]) == {'asset','media'}, 'Invalid output manifest')
        self._attempt(authorization, attempt_id, payload['lease_id'], active=action != 'complete')
        attempt = dict(id=attempt_id, lease_id=payload['lease_id'])
        try:
            return getattr(client, action)(attempt, payload[field])
        except WorkerAccessError:
            raise
        except PermissionError:
            raise WorkerAccessError(404) from None
        except ValueError:
            raise WorkerAccessError(409) from None

    def upload(self, authorization, attempt_id, lease_id, checksum, length, stream):
        require(type(length) is int and 0 < length <= MAX_ARTIFACT_BYTES, 'Artifact exceeds byte limit')
        require(isinstance(checksum, str) and re.fullmatch(r'[a-f0-9]{64}', checksum), 'Artifact SHA256 required')
        principal, _, _, _ = self._attempt(authorization, attempt_id, lease_id)
        stage_root = self.control.asset_root / '.worker-staging'
        stage_root.mkdir(mode=0o700, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=stage_root, delete=False) as stage:
            temporary = Path(stage.name)
            try:
                hasher, remaining = hashlib.sha256(), length
                while remaining:
                    chunk = stream.read(min(65536, remaining))
                    if not chunk or len(chunk) > min(65536, remaining):
                        raise WorkerAccessError(422)
                    remaining -= len(chunk)
                    hasher.update(chunk)
                    stage.write(chunk)
                stage.flush()
                os.fsync(stage.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            require(hasher.hexdigest() == checksum, 'Artifact checksum mismatch')
            with temporary.open('rb') as source:
                signature = source.read(12)
            require(len(signature) == 12 and signature[4:8] == b'ftyp', 'Only MP4 artifacts are accepted')
            # Upload duration may exceed the original lease or credential window.
            self._attempt(authorization, attempt_id, lease_id)
            key = f"projects/{principal['project']}/attempts/{attempt_id}/output.mp4"
            destination = scoped(self.control.asset_root, key)
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if destination.stat().st_size != length or digest(destination) != checksum:
                    raise WorkerAccessError(409) from None
            sync_dir(destination.parent)
            # Complete will independently recheck owner, active lease, bytes and media.
            self._attempt(authorization, attempt_id, lease_id)
            return dict(bytes=length, sha256=checksum, object_key=key)
        finally:
            temporary.unlink(missing_ok=True)

    def download(self, authorization, attempt_id, lease_id, asset_id):
        principal, bundle, batch, attempt = self._attempt(authorization, attempt_id, lease_id)
        snapshot = next(s for s in batch['shot_snapshots'] if s['shot_id'] == attempt['shot_id'])
        asset = next((a for a in bundle['assets'] if a['id'] == asset_id and a['id'] in snapshot['reference_asset_ids'] and
                      a['owner_id'] == principal['owner'] and a['project_id'] == principal['project']), None)
        if asset is None:
            raise WorkerAccessError(404)
        path = scoped(self.control.asset_root, asset['object_key'])
        if not path.is_file() or path.stat().st_size != asset['bytes'] or digest(path) != asset['sha256']:
            raise WorkerAccessError(503)
        self._attempt(authorization, attempt_id, lease_id)
        return path, asset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--assets', required=True, type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    issue = commands.add_parser('issue')
    for name in ('owner','project','batch','worker'):
        issue.add_argument('--' + name, required=True)
    issue.add_argument('--ttl-seconds', type=int, default=300)
    issue.add_argument('--token-file', type=Path, required=True)
    revoke = commands.add_parser('revoke')
    for name in ('owner','project','credential'):
        revoke.add_argument('--' + name, required=True)
    args = parser.parse_args()
    transport = WorkerTransport(ControlService(args.database, args.assets))
    if args.command == 'revoke':
        transport.revoke(args.owner, args.project, args.credential)
        print('Worker credential revoked.')
        return
    # Refuse to replace a credential file, and never print its plaintext token.
    fd = os.open(args.token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        value = transport.issue(args.owner, args.project, args.batch, args.worker, ttl_seconds=args.ttl_seconds)
        with os.fdopen(fd, 'w') as output:
            output.write(value['token'] + '\n')
            output.flush()
            os.fsync(output.fileno())
        sync_dir(args.token_file.parent)
        print(f"Worker credential {value['id']} issued; expires {value['expires_at']}.")
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        args.token_file.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    main()
