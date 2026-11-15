"""Owner-scoped, restartable local uploads with bounded raw chunks.

A client hashes each chunk independently and supplies the ordered manifest on
finish. The server verifies every staged byte then streams the whole-object SHA256.
No request, browser allocation or server read needs to contain the full upload.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from uuid import uuid4

from services.controller.media_commands import TYPES, inspect_upload
from services.controller.service import canonical, stamp
from services.controller.studio import StudioConflict, require
from workers.gpu.common import digest, scoped, sync_dir, timestamp

CHUNK_SIZE = 1024 * 1024
AUDIO_LIMIT = 128 * CHUNK_SIZE
IMAGE_LIMIT = CHUNK_SIZE


class UploadExpired(ValueError):
    status = 410


class UploadCapacity(ValueError):
    status = 429


class ResumableUploads:
    def __init__(self, studio):
        self.studio, self.control = studio, studio.control
        self.root = self.control.asset_root / '.uploads'
        self.locks = self.root / 'locks'
        self.locks.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.control.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS upload_sessions (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, project TEXT NOT NULL,
                idem TEXT NOT NULL, request TEXT NOT NULL, state TEXT NOT NULL,
                expires TEXT NOT NULL, asset TEXT, manifest TEXT,
                UNIQUE(owner,project,idem))''')
            db.execute('''CREATE TABLE IF NOT EXISTS upload_chunks (
                session TEXT NOT NULL, idx INTEGER NOT NULL, size INTEGER NOT NULL,
                sha TEXT NOT NULL, PRIMARY KEY(session,idx))''')
        self.cleanup_expired()

    @contextmanager
    def _lock(self, upload_id, *, blocking=True):
        # Identifiers are checked before opening a path, including internal cleanup.
        require(isinstance(upload_id, str) and re.fullmatch(r'[a-f0-9]{32}', upload_id), 'Invalid upload ID')
        with (self.locks / upload_id).open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            yield

    def _session(self, db, owner, project, upload_id):
        self.control._load(db, owner, project)
        row = db.execute('SELECT id,owner,project,request,state,expires,asset,manifest FROM upload_sessions WHERE id=? AND owner=? AND project=?',
                         (upload_id, owner, project)).fetchone()
        if row is None:
            raise KeyError('Upload unavailable')
        return dict(zip(('id','owner','project','request','state','expires','asset','manifest'), row))

    @staticmethod
    def _chunks(db, upload_id):
        return db.execute('SELECT idx,size,sha FROM upload_chunks WHERE session=? ORDER BY idx', (upload_id,)).fetchall()

    def _response(self, db, session):
        chunks = self._chunks(db, session['id'])
        request = json.loads(session['request'])
        return dict(upload=dict(id=session['id'], project_id=session['project'], state=session['state'],
                    bytes=request['bytes'], received_bytes=sum(c[1] for c in chunks), chunk_size=CHUNK_SIZE,
                    next_chunk_index=len(chunks), chunk_sha256=[c[2] for c in chunks],
                    expires_at=session['expires'], asset_id=session['asset']))

    def _live(self, session):
        if session['state'] == 'expired' or (session['state'] == 'uploading' and
                timestamp(session['expires']) <= self.control.clock()):
            raise UploadExpired('Upload expired')
        if session['state'] != 'uploading':
            raise StudioConflict('Upload is no longer writable')

    def _discard(self, session):
        shutil.rmtree(self.root / session['id'], ignore_errors=True)
        if session['state'] in ('expired', 'aborted') and session['asset'] is None:
            # A crash can leave a published link before the asset transaction commits.
            request = json.loads(session['request'])
            key = f"projects/{session['project']}/uploads/asset-{session['id']}{TYPES[request['mime_type']][3]}"
            scoped(self.control.asset_root, key).unlink(missing_ok=True)

    def cleanup_expired(self):
        now = self.control.clock()
        with self.control.transaction() as db:
            rows = db.execute("SELECT id,owner,project FROM upload_sessions WHERE state!='uploading' OR expires<=?", (stamp(now),)).fetchall()
        for upload_id, owner, project in rows:
            try:
                with self._lock(upload_id, blocking=False):
                    with self.control.transaction() as db:
                        db.execute("UPDATE upload_sessions SET state='expired' WHERE id=? AND state='uploading' AND expires<=?",
                                   (upload_id, stamp(now)))
                        session = self._session(db, owner, project, upload_id)
                    if session['state'] != 'uploading':
                        self._discard(session)
            except BlockingIOError:
                continue

    def begin(self, owner, project, payload):
        self.studio._owner(owner)
        require(isinstance(payload, dict) and set(payload) == {'name','mime_type','bytes','expected_revision','idempotency_key'},
                'Invalid upload request')
        require(isinstance(payload['name'], str) and 0 < len(payload['name'].strip()) <= 500, 'Invalid asset name')
        mime = payload['mime_type']
        require(isinstance(mime, str) and mime in TYPES, 'Unsupported upload MIME type')
        limit = IMAGE_LIMIT if TYPES[mime][0] == 'image' else AUDIO_LIMIT
        require(type(payload['bytes']) is int and 0 < payload['bytes'] <= limit, 'Upload exceeds size limit')
        require(type(payload['expected_revision']) is int and payload['expected_revision'] >= 0, 'Invalid workspace revision')
        require(isinstance(payload['idempotency_key'], str) and 0 < len(payload['idempotency_key'].strip()) <= 200,
                'Idempotency key required')
        self.cleanup_expired()
        with self.control.transaction() as db:
            self.control._load(db, owner, project)
            prior = db.execute('SELECT id,request FROM upload_sessions WHERE owner=? AND project=? AND idem=?',
                               (owner, project, payload['idempotency_key'])).fetchone()
            if prior:
                if prior[1] != canonical(payload):
                    raise StudioConflict('Upload idempotency conflict')
                return self._response(db, self._session(db, owner, project, prior[0]))
            self.studio._check_revision(db, owner, payload['expected_revision'])
            count = db.execute("SELECT count(*) FROM upload_sessions WHERE owner=? AND state='uploading'", (owner,)).fetchone()[0]
            if count >= 4:
                raise UploadCapacity('At most four active uploads per owner')
            upload_id = uuid4().hex
            expiry = stamp(self.control.clock() + timedelta(hours=24))
            db.execute('INSERT INTO upload_sessions VALUES (?,?,?,?,?,?,?,NULL,NULL)',
                       (upload_id, owner, project, payload['idempotency_key'], canonical(payload), 'uploading', expiry))
            return self._response(db, self._session(db, owner, project, upload_id))

    def get(self, owner, project, upload_id):
        self.studio._owner(owner)
        self.cleanup_expired()
        with self.control.transaction() as db:
            return self._response(db, self._session(db, owner, project, upload_id))

    def chunk(self, owner, project, upload_id, index, data):
        self.studio._owner(owner)
        require(type(index) is int and 0 <= index < 128 and isinstance(data, bytes) and 0 < len(data) <= CHUNK_SIZE,
                'Invalid upload chunk')
        self.cleanup_expired()
        with self.control.transaction() as db:
            self._session(db, owner, project, upload_id)  # authorize before filesystem use
        with self._lock(upload_id):
            with self.control.transaction() as db:
                session = self._session(db, owner, project, upload_id)
                self._live(session)
                request = json.loads(session['request'])
                expected = min(CHUNK_SIZE, request['bytes'] - index * CHUNK_SIZE)
                require(expected > 0 and len(data) == expected, 'Chunk does not match declared size')
                chunks = self._chunks(db, upload_id)
                checksum = hashlib.sha256(data).hexdigest()
                if index < len(chunks):
                    if (len(data), checksum) != (chunks[index][1], chunks[index][2]):
                        raise StudioConflict('Uploaded chunk content conflict')
                    return self._response(db, session)
                if index != len(chunks):
                    raise StudioConflict('Upload chunks in order')
                directory = self.root / upload_id
                directory.mkdir(mode=0o700, exist_ok=True)
                destination = directory / f'{index:03d}.chunk'
                if destination.exists():
                    # A process may have stopped after publishing bytes but before DB commit.
                    if destination.stat().st_size != len(data) or digest(destination) != checksum:
                        raise StudioConflict('Interrupted chunk content conflict')
                else:
                    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stage:
                        temp = Path(stage.name)
                        stage.write(data)
                        stage.flush()
                        os.fsync(stage.fileno())
                    try:
                        os.link(temp, destination)
                        sync_dir(directory)
                    finally:
                        temp.unlink(missing_ok=True)
                db.execute('INSERT INTO upload_chunks VALUES (?,?,?,?)', (upload_id, index, len(data), checksum))
                return self._response(db, session)

    def finish(self, owner, project, upload_id, payload):
        self.studio._owner(owner)
        require(isinstance(payload, dict) and set(payload) == {'chunk_sha256'}, 'Chunk manifest required')
        hashes = payload['chunk_sha256']
        require(isinstance(hashes, list) and 0 < len(hashes) <= 128 and
                all(isinstance(s, str) and re.fullmatch(r'[a-f0-9]{64}', s) for s in hashes), 'Invalid chunk manifest')
        self.cleanup_expired()
        with self.control.transaction() as db:
            self._session(db, owner, project, upload_id)
        with self._lock(upload_id):
            with self.control.transaction() as db:
                session = self._session(db, owner, project, upload_id)
                if session['state'] == 'completed':
                    if session['manifest'] != canonical(hashes):
                        raise StudioConflict('Completed upload manifest conflict')
                    bundle = self.control._load(db, owner, project)
                    asset = next(a for a in bundle['assets'] if a['id'] == session['asset'])
                    return dict(asset=deepcopy(asset), workspace=self.studio._get(db, owner))
                self._live(session)
                request = json.loads(session['request'])
                chunks = self._chunks(db, upload_id)
                count = math.ceil(request['bytes'] / CHUNK_SIZE)
                require(len(chunks) == len(hashes) == count and sum(c[1] for c in chunks) == request['bytes'], 'Upload is incomplete')
                if [c[2] for c in chunks] != hashes:
                    raise StudioConflict('Client chunk manifest mismatch')
                bundle = self.control._load(db, owner, project)
            directory = self.root / upload_id
            combined = directory / 'verified-input'
            whole_hash = hashlib.sha256()
            with combined.open('wb') as output:
                for index, size, checksum in chunks:
                    chunk_hash = hashlib.sha256()
                    read = 0
                    with (directory / f'{index:03d}.chunk').open('rb') as source:
                        while block := source.read(65536):
                            read += len(block)
                            chunk_hash.update(block)
                            whole_hash.update(block)
                            output.write(block)
                    require(read == size and chunk_hash.hexdigest() == checksum, 'Staged chunk checksum mismatch')
                output.flush()
                os.fsync(output.fileno())
            with combined.open('rb') as source:
                signature = source.read(16)
            kind, duration = inspect_upload(combined, signature, request['mime_type'], bundle['project']['runtime_limit_ms'])
            asset_id = 'asset-' + upload_id
            key = f"projects/{project}/uploads/{asset_id}{TYPES[request['mime_type']][3]}"
            destination = scoped(self.control.asset_root, key)
            checksum = whole_hash.hexdigest()
            asset = dict(id=asset_id, project_id=project, owner_id=owner, kind=kind, object_key=key,
                         mime_type=request['mime_type'], bytes=request['bytes'], sha256=checksum, duration_ms=duration)
            with self.control.transaction() as db:
                session = self._session(db, owner, project, upload_id)
                self._live(session)
                bundle = self.control._load(db, owner, project)
                require(duration is None or duration <= bundle['project']['runtime_limit_ms'], 'Audio exceeds current project duration')
                metadata = self.studio._project(db, bundle)
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                try:
                    os.link(combined, destination)
                except FileExistsError:
                    require(destination.stat().st_size == request['bytes'] and digest(destination) == checksum,
                            'Immutable upload output conflict')
                sync_dir(destination.parent)
                bundle['assets'].append(asset)
                metadata['assetNames'][asset_id] = request['name'].strip()
                values = {k: metadata[k] for k in ('scenes','shotHistory','selectedTakes','assetNames','script')}
                self.control._save(db, bundle)
                db.execute('UPDATE studio_projects SET metadata=? WHERE project=?', (canonical(values), project))
                db.execute("UPDATE upload_sessions SET state='completed',asset=?,manifest=? WHERE id=?", (asset_id, canonical(hashes), upload_id))
                self.studio._advance(db, owner)
                response = dict(asset=deepcopy(asset), workspace=self.studio._get(db, owner))
            shutil.rmtree(directory, ignore_errors=True)
            return response

    def abort(self, owner, project, upload_id):
        self.studio._owner(owner)
        with self.control.transaction() as db:
            self._session(db, owner, project, upload_id)
        with self._lock(upload_id):
            with self.control.transaction() as db:
                session = self._session(db, owner, project, upload_id)
                if session['state'] == 'completed':
                    raise StudioConflict('Completed assets cannot be aborted')
                db.execute("UPDATE upload_sessions SET state='aborted' WHERE id=?", (upload_id,))
                session['state'] = 'aborted'
                response = self._response(db, session)
            self._discard(session)
            return response
