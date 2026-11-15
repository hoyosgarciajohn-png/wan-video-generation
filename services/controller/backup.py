"""Checksummed local SQLite/media backups and restore into an empty destination.

Current application assets are immutable and published before their DB commit.
SQLite backup pins a read transaction; referenced assets can then be copied while
new work proceeds. External mutation or deletion causes verification failure.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
from urllib.parse import quote

from scripts.validate_contract import validate_bundle
from services.controller.service import canonical
from workers.gpu.common import digest, sync_dir, timestamp

TABLES = {'projects','admissions','completions','studio_owners','studio_projects',
          'command_receipts','upload_sessions','upload_chunks','export_jobs','pod_batches',
          'budget_approvals','budget_reservations','budget_events','worker_credentials','real_job_links'}
DB_NAME = 'database.sqlite'


def require(value, message):
    if not value:
        raise ValueError(message)


def _plain_path(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        require(not part.is_symlink(), 'Symlinks are not accepted')
    return path.resolve()


def _file(path, *, hardlinks=False):
    path = _plain_path(path)
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and (hardlinks or info.st_nlink == 1), 'Expected a regular unlinked backup file')
    return path


def _key(key):
    require(isinstance(key, str) and key and '\\' not in key and '\x00' not in key,
            'Invalid relative path')
    value = PurePosixPath(key)
    require(not value.is_absolute() and '..' not in value.parts and str(value) == key and key != '.',
            'Unsafe relative path')
    return key


def _destination(path):
    path = _plain_path(path)
    if path.exists():
        require(path.is_dir() and not any(path.iterdir()), 'Destination must be empty; existing data is never overwritten')
    else:
        require(path.parent.is_dir(), 'Destination parent must already exist')
        path.mkdir(mode=0o700)
        sync_dir(path.parent)
    return path


@contextmanager
def _connect(path, readonly=False):
    path = _plain_path(path)
    connection = sqlite3.connect(f"file:{quote(str(path), safe='/')}?mode={'ro' if readonly else 'rw'}", uri=True)
    connection.execute('PRAGMA trusted_schema=OFF')
    connection.enable_load_extension(False)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _tables(db):
    objects = db.execute("SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    require(all(kind in ('table','index') and (kind == 'index' or name in TABLES) for kind, name in objects),
            'Unsupported database objects; backup only the application database')
    names = {name for kind, name in objects if kind == 'table'}
    require('projects' in names, 'Missing project database')
    return names


def _inspect_budget(db, names, projects):
    """Preserve settled simulation history; never restore uncertain liabilities."""
    ledger_tables = {'budget_approvals', 'budget_reservations', 'budget_events'}
    if not names & ledger_tables:
        return
    require(ledger_tables <= names, 'Incomplete budget ledger schema')

    def owner_matches(owner, project):
        return project in projects and projects[project]['project']['owner_id'] == owner

    def money(amount, positive=False):
        return type(amount) is int and (1 if positive else 0) <= amount <= 2**53 - 1

    approvals = {}
    for identity, owner, project, raw, revoked, mode in db.execute(
            'SELECT id,owner,project,terms,revoked,mode FROM budget_approvals'):
        terms = json.loads(raw)
        require(owner_matches(owner, project) and mode == 'simulation' and revoked in (0, 1),
                'Invalid budget approval ownership or mode')
        require(isinstance(terms, dict) and terms.get('currency') == 'USD' and
                money(terms.get('approved_cents'), True) and
                type(terms.get('max_runtime_seconds')) is int and 0 < terms['max_runtime_seconds'] <= 86400 and
                isinstance(terms.get('profile'), dict) and bool(terms['profile']), 'Invalid budget approval terms')
        timestamp(terms['valid_until'])
        approvals[identity] = (owner, project)
    reservations = {}
    for batch, owner, project, approval, reserved, state, raw in db.execute(
            'SELECT batch,owner,project,approval,reserved_cents,state,request FROM budget_reservations'):
        require(owner_matches(owner, project) and approvals.get(approval) == (owner, project) and money(reserved, True),
                'Invalid reservation ownership or approval')
        require(state == 'settled', 'Outstanding budget liability must be explicitly settled before backup')
        require('pod_batches' in names, 'Budget lifecycle unavailable')
        pod = db.execute('SELECT project,state,cleanup FROM pod_batches WHERE id=?', (batch,)).fetchone()
        require(pod and pod[0] == project and pod[1] in ('succeeded','failed','canceled') and pod[2] == 'confirmed',
                'Settled budget lifecycle is not closed')
        request = json.loads(raw)
        require(request.get('approval_id') == approval and request.get('reservation_cents') == reserved,
                'Reservation receipt mismatch')
        reservations[batch] = (owner, project)
    totals, settlements = {}, set()
    for owner, project, batch, raw, kind, delta in db.execute(
            'SELECT owner,project,batch,request,kind,amount_cents FROM budget_events ORDER BY rowid'):
        request = json.loads(raw)
        require(reservations.get(batch) == (owner, project) and kind in ('charge','settlement') and money(delta),
                'Invalid billing event ownership or amount')
        require(request.get('batch_id') == batch and request.get('kind') == kind and
                money(request.get('amount_cents')) and isinstance(request.get('bill_reference'), str) and
                bool(request['bill_reference'].strip()), 'Billing event receipt mismatch')
        previous = totals.get(batch, 0)
        if kind == 'settlement':
            require(batch not in settlements and request['amount_cents'] >= previous and
                    delta == request['amount_cents'] - previous, 'Invalid cumulative settlement')
            settlements.add(batch)
        else:
            require(delta == request['amount_cents'], 'Incremental charge mismatch')
        totals[batch] = previous + delta
    require(settlements == set(reservations), 'Settled reservation lacks final billing evidence')


def _inspect_real_jobs(db, names, projects):
    if 'real_job_links' not in names:
        return set()
    from services.controller.real_jobs import RealJobBridge
    from workers.gpu.common import LOCK
    rows = db.execute('SELECT batch,owner,project,approval,mode,config_hash FROM real_job_links').fetchall()
    if not rows:
        return set()
    require({'budget_approvals','budget_reservations','budget_events','pod_batches'} <= names,
            'Linked job accounting or lifecycle unavailable')
    linked = set()
    for batch_id, owner, project, approval_id, mode, config_hash in rows:
        require(project in projects and projects[project]['project']['owner_id'] == owner and mode == 'test',
                'Live/unknown linked authority is not restorable')
        batch = next((b for b in projects[project]['batches'] if b['id'] == batch_id), None)
        require(batch and batch['execution_mode'] == 'runpod' and batch['model_profile'] == LOCK['profile'],
                'Linked canonical model profile mismatch')
        approval = db.execute('SELECT owner,project,mode,terms FROM budget_approvals WHERE id=?', (approval_id,)).fetchone()
        require(approval and tuple(approval[:3]) == (owner, project, 'simulation'), 'Linked approval ownership mismatch')
        terms = json.loads(approval[3])
        require(RealJobBridge.configuration_hash(terms['profile']) == config_hash and
                batch['budget']['approved_cents'] == terms['approved_cents'], 'Linked approval configuration changed')
        reservation = db.execute('SELECT owner,project,approval,state FROM budget_reservations WHERE batch=?', (batch_id,)).fetchone()
        require(reservation and tuple(reservation[:3]) == (owner, project, approval_id) and reservation[3] == 'settled',
                'Linked job retains unsettled monetary liability')
        spent = db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM budget_events WHERE batch=?', (batch_id,)).fetchone()[0]
        require(batch['budget']['spent_cents'] == spent and batch['budget']['reserved_cents'] == 0,
                'Canonical budget is not reconciled with settled accounting')
        pod = db.execute('SELECT project,state,cleanup,pod_id,snapshot FROM pod_batches WHERE id=?', (batch_id,)).fetchone()
        require(pod and tuple(pod[:4]) == (project, batch['state'], batch['cleanup_state'], batch['provider_resource_id']),
                'Canonical lifecycle state is not reconciled')
        frozen = json.loads(pod[4])
        require(frozen.get('mode') == 'test' and frozen.get('config_hash') == config_hash and
                all(frozen['canonical_batch'][key] == batch[key] for key in
                    ('id','project_id','idempotency_key','execution_mode','model_profile','shot_snapshots','approved_at','deadline_at')),
                'Immutable linked snapshot mismatch')
        linked.add(batch_id)
    return linked


def _inspect(db):
    require(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'Database integrity check failed')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(), 'Database foreign key check failed')
    names = _tables(db)
    assets = {}
    projects = {}

    def collect(bundle):
        validate_bundle(bundle)
        for batch in bundle['batches']:
            require(batch['execution_mode'] == 'fixture' or (batch['state'] in ('succeeded','failed','canceled') and
                    batch['cleanup_state'] == 'confirmed'), 'Outstanding or uncertain paid resources cannot be restored safely')
        for asset in bundle['assets']:
            key = _key(asset['object_key'])
            prior = assets.get(key)
            require(prior is None or (prior['bytes'], prior['sha256']) == (asset['bytes'],asset['sha256']),
                    'Conflicting immutable asset references')
            assets[key] = asset

    for project_id, owner, raw in db.execute('SELECT id,owner,bundle FROM projects'):
        bundle = json.loads(raw)
        require(bundle['project']['id'] == project_id and bundle['project']['owner_id'] == owner, 'Project row identity mismatch')
        collect(bundle)
        projects[project_id] = bundle
    if 'pod_batches' in names:
        require(db.execute("SELECT count(*) FROM pod_batches WHERE cleanup!='confirmed'").fetchone()[0] == 0,
                'Provider cleanup must be confirmed before backup')
    if 'export_jobs' in names:
        for job_id, project_id, owner, raw, state in db.execute('SELECT id,project,owner,snapshot,state FROM export_jobs'):
            require(project_id in projects and projects[project_id]['project']['owner_id'] == owner, 'Export job owner mismatch')
            frozen = json.loads(raw)
            require(frozen['project']['id'] == project_id and frozen['project']['owner_id'] == owner, 'Export snapshot identity mismatch')
            collect(frozen)  # Include snapshot-only assets, independent of canonical refs.
            source = next((j for j in frozen['exports'] if j['id'] == job_id), None)
            current = next((j for j in projects[project_id]['exports'] if j['id'] == job_id), None)
            require(source is not None and current is not None and state == current['state'] and
                    all(source[k] == current[k] for k in ('id','project_id','timeline_id','timeline_revision','profile')),
                    'Export job state or frozen identity mismatch')
    if 'studio_projects' in names:
        for project_id, raw in db.execute('SELECT project,metadata FROM studio_projects'):
            require(project_id in projects, 'Studio project unavailable')
            value = json.loads(raw)
            require(isinstance(value.get('script'), str) and isinstance(value.get('scenes'), list) and
                    isinstance(value.get('shotHistory'), list) and isinstance(value.get('assetNames'), dict) and
                    isinstance(value.get('selectedTakes'), dict), 'Invalid Studio metadata')
    if 'upload_sessions' in names:
        for owner, project_id, state, asset_id in db.execute('SELECT owner,project,state,asset FROM upload_sessions'):
            require(project_id in projects and projects[project_id]['project']['owner_id'] == owner and
                    state in ('uploading','completed','expired','aborted'), 'Invalid upload session')
            if state == 'completed':
                require(any(a['id'] == asset_id for a in projects[project_id]['assets']), 'Completed upload asset unavailable')
    linked_test_jobs = _inspect_real_jobs(db, names, projects)
    if 'worker_credentials' in names:
        for token_hash, owner, project_id, batch_id, worker, expires, revoked in db.execute(
                'SELECT token_hash,owner,project,batch,worker,expires,revoked FROM worker_credentials'):
            require(project_id in projects and projects[project_id]['project']['owner_id'] == owner,
                    'Worker credential owner mismatch')
            batch = next((b for b in projects[project_id]['batches'] if b['id'] == batch_id), None)
            require(batch and ((batch['execution_mode'] == 'fixture' and
                    all(batch['budget'][key] == 0 for key in ('approved_cents','reserved_cents','spent_cents'))) or
                    batch_id in linked_test_jobs), 'Worker credential batch has no valid fixture/test binding')
            require(isinstance(token_hash, str) and len(token_hash) == 64 and
                    all(c in '0123456789abcdef' for c in token_hash) and
                    isinstance(worker, str) and bool(worker) and revoked in (0, 1),
                    'Invalid worker credential')
            timestamp(expires)
    _inspect_budget(db, names, projects)
    return assets


def _normalize(db, now):
    counts = dict(uploads_aborted=0, attempts_fenced=0, worker_credentials_revoked=0)
    names = _tables(db)
    if 'upload_sessions' in names:
        counts['uploads_aborted'] = db.execute("UPDATE upload_sessions SET state='aborted' WHERE state='uploading'").rowcount
    if 'worker_credentials' in names:
        counts['worker_credentials_revoked'] = db.execute('UPDATE worker_credentials SET revoked=1 WHERE revoked=0').rowcount
    for project_id, raw in db.execute('SELECT id,bundle FROM projects').fetchall():
        bundle = json.loads(raw)
        changed = False
        for attempt in bundle['attempts']:
            if attempt['state'] in ('claimed','running'):
                completed = max(timestamp(now), timestamp(attempt['started_at'])).isoformat().replace('+00:00', 'Z')
                attempt.update(state='failed', failure_reason='backup_interrupted', completed_at=completed)
                counts['attempts_fenced'] += 1
                changed = True
        if changed:
            validate_bundle(bundle)
            db.execute('UPDATE projects SET bundle=? WHERE id=?', (canonical(bundle), project_id))
    return counts


def _copy(source, destination, size, checksum, *, hardlinks=False):
    source = _file(source, hardlinks=hardlinks)
    require(type(size) is int and size >= 0 and source.stat().st_size == size, 'Backup file size mismatch')
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    hasher = hashlib.sha256()
    written = 0
    with source.open('rb') as incoming, destination.open('xb') as output:
        while chunk := incoming.read(65536):
            written += len(chunk)
            require(written <= size, 'Source file changed while copying')
            hasher.update(chunk)
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    require(written == size and hasher.hexdigest() == checksum, 'Backup checksum mismatch')
    sync_dir(destination.parent)


def _write(path, data):
    with path.open('xb') as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    sync_dir(path.parent)


def _sync_directories(directory):
    directories = [Path(parent) for parent, _, _ in os.walk(directory)]
    for path in reversed(directories):
        sync_dir(path)


def _finish_marker(directory, manifest_bytes):
    _sync_directories(directory)
    temporary = directory / 'COMPLETE.tmp'
    _write(temporary, (hashlib.sha256(manifest_bytes).hexdigest() + '\n').encode())
    os.replace(temporary, directory / 'COMPLETE')
    sync_dir(directory)


def create_backup(database, asset_root, destination):
    """Copy a consistent DB snapshot and its immutable committed media refs.

    Only the backup copy is normalized: active uploads abort, active attempts are
    fenced. Queued/rendering export jobs retain their captured inputs for restart.
    """
    database = _file(database, hardlinks=True)
    asset_root = _plain_path(asset_root)
    require(asset_root.is_dir(), 'Asset root unavailable')
    destination_path = _plain_path(destination)
    require(not destination_path.is_relative_to(asset_root) and not database.is_relative_to(destination_path),
            'Backup destination must be separate from active data')
    output = _destination(destination_path)
    snapshot = output / DB_NAME
    with _connect(database, readonly=True) as source:
        # Pin the snapshot before backup; writers may continue publishing new media.
        source.execute('BEGIN')
        source.execute('SELECT count(*) FROM sqlite_master').fetchone()
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target, pages=256)
        finally:
            target.close()
        source.rollback()
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    with _connect(snapshot) as db:
        db.execute('PRAGMA journal_mode=DELETE')
        _inspect(db)  # Reject uncertain provider obligations before normalization.
        recovery = _normalize(db, now)
        db.commit()
        assets = _inspect(db)
        db.execute('VACUUM')  # Do not retain discarded/free page contents.
    with snapshot.open('rb') as handle:
        os.fsync(handle.fileno())
    files = [dict(path=DB_NAME, bytes=snapshot.stat().st_size, sha256=digest(snapshot))]
    (output / 'assets').mkdir(mode=0o700)
    for key, asset in sorted(assets.items()):
        relative = 'assets/' + key
        _copy(asset_root / key, output / relative, asset['bytes'], asset['sha256'], hardlinks=True)
        files.append(dict(path=relative, bytes=asset['bytes'], sha256=asset['sha256']))
    manifest = dict(version=1, contract_version='0.1.0', created_at=now,
                    recovery=recovery, files=files)
    encoded = (canonical(manifest) + '\n').encode()
    _write(output / 'manifest.json', encoded)
    _finish_marker(output, encoded)
    return manifest


def _verify_backup(directory):
    directory = _plain_path(directory)
    require(directory.is_dir(), 'Backup directory unavailable')
    manifest_path = _file(directory / 'manifest.json')
    require(manifest_path.stat().st_size <= 32 * 1024 * 1024, 'Manifest exceeds bounds')
    raw = manifest_path.read_bytes()
    marker = _file(directory / 'COMPLETE')
    require(marker.stat().st_size == 65 and marker.read_bytes() == (hashlib.sha256(raw).hexdigest() + '\n').encode(),
            'Backup is incomplete or manifest checksum changed')
    manifest = json.loads(raw)
    require(isinstance(manifest, dict) and set(manifest) == {'version','contract_version','created_at','recovery','files'} and
            type(manifest['version']) is int and manifest['version'] == 1 and manifest['contract_version'] == '0.1.0',
            'Unsupported backup manifest')
    require(isinstance(manifest['created_at'], str) and timestamp(manifest['created_at']).tzinfo is not None,
            'Invalid backup timestamp')
    recovery = manifest['recovery']
    require(isinstance(recovery, dict) and set(recovery) in (
                {'uploads_aborted','attempts_fenced'},
                {'uploads_aborted','attempts_fenced','worker_credentials_revoked'}) and
            all(type(v) is int and v >= 0 for v in recovery.values()), 'Invalid recovery summary')
    require(isinstance(manifest['files'], list) and 0 < len(manifest['files']) <= 100000, 'Invalid file inventory')
    entries = {}
    for entry in manifest['files']:
        require(isinstance(entry, dict) and set(entry) == {'path','bytes','sha256'}, 'Invalid file entry')
        key = _key(entry['path'])
        require(key == DB_NAME or key.startswith('assets/'), 'Unexpected backup path')
        require(key not in entries and type(entry['bytes']) is int and entry['bytes'] >= 0 and
                isinstance(entry['sha256'], str) and len(entry['sha256']) == 64 and
                all(c in '0123456789abcdef' for c in entry['sha256']), 'Invalid file metadata')
        file = _file(directory / key)
        require(file.stat().st_size == entry['bytes'] and digest(file) == entry['sha256'], 'Backup file checksum mismatch')
        entries[key] = entry
    require(DB_NAME in entries, 'Database missing from backup')
    actual = set()
    for parent, dirs, names in os.walk(directory, followlinks=False):
        for name in dirs + names:
            require(not (Path(parent) / name).is_symlink(), 'Backup contains symlink')
        actual.update(str((Path(parent) / name).relative_to(directory)) for name in names)
    require(actual == set(entries) | {'manifest.json','COMPLETE'}, 'Unlisted backup files')
    with _connect(directory / DB_NAME, readonly=True) as db:
        assets = _inspect(db)
        if 'worker_credentials' in _tables(db):
            require(db.execute('SELECT count(*) FROM worker_credentials WHERE revoked!=1').fetchone()[0] == 0,
                    'Backup worker credentials must be revoked before restore')
    require(set(entries) == {DB_NAME} | {'assets/' + key for key in assets}, 'Manifest does not match database references')
    for key, asset in assets.items():
        entry = entries['assets/' + key]
        require((entry['bytes'],entry['sha256']) == (asset['bytes'],asset['sha256']), 'Asset record checksum mismatch')
    return manifest


def restore_backup(backup_dir, destination):
    """Validate then restore into a NEW/empty directory; never overwrite live data."""
    source = _plain_path(backup_dir)
    target_path = _plain_path(destination)
    require(not target_path.is_relative_to(source) and not source.is_relative_to(target_path), 'Restore destination overlaps backup')
    manifest = _verify_backup(source)
    target = _destination(target_path)
    (target / 'assets').mkdir(mode=0o700)
    for entry in manifest['files']:
        _copy(source / entry['path'], target / entry['path'], entry['bytes'], entry['sha256'])
    with _connect(target / DB_NAME, readonly=True) as db:
        _inspect(db)
    recovery = dict(database=str(target / DB_NAME), assets=str(target / 'assets'),
                    restored_at=datetime.now(timezone.utc).isoformat(), recovery=manifest['recovery'])
    _sync_directories(target)
    _write(target / 'RESTORED.tmp', (canonical(recovery) + '\n').encode())
    os.replace(target / 'RESTORED.tmp', target / 'RESTORED.json')
    sync_dir(target)
    return recovery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create')
    create.add_argument('--database', required=True, type=Path)
    create.add_argument('--assets', required=True, type=Path)
    create.add_argument('--output', required=True, type=Path)
    restore = commands.add_parser('restore')
    restore.add_argument('--backup', required=True, type=Path)
    restore.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'create':
        result = create_backup(args.database, args.assets, args.output)
        print(json.dumps({'complete': True, 'files': len(result['files']), 'recovery': result['recovery']}))
    else:
        print(json.dumps(restore_backup(args.backup, args.output)))


if __name__ == '__main__':
    main()
