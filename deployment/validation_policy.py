"""Owner-authorized exception for one known, expired, unresolved request.

This does not settle billing, declare deletion, authorize a retry, or relax the
normal backup/restore rules. The new validation retains its own signed grant.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time

from workers.gpu.common import timestamp

OLD_BATCH = '249c50635ec84ac38cef0eb66232efed'
OLD_PROJECT = 'project-10088bb273fb41d78399957f2dc8cd83'
OLD_SCOPE = json.dumps(['john-hoyos', OLD_PROJECT], separators=(',', ':'))


def known_unknown(db, now=None):
    now = time.time() if now is None else now
    row = db.execute('SELECT project,state,cleanup,pod_id,deadline FROM pod_batches WHERE id=?', (OLD_BATCH,)).fetchone()
    assert row is not None and tuple(row[:4]) == (OLD_PROJECT, 'failed', 'failed', None)
    assert row[4] == timestamp('2026-11-16T15:33:20Z').timestamp() < now
    row = db.execute('SELECT owner,project,dispatch_state FROM live_job_links WHERE batch=?', (OLD_BATCH,)).fetchone()
    assert row is not None and tuple(row) == ('john-hoyos', OLD_PROJECT, 'attempted')
    row = db.execute('SELECT reserved_cents,state FROM live_reservations WHERE batch=?', (OLD_BATCH,)).fetchone()
    assert row is not None and tuple(row) == (400, 'reserved')
    credentials = db.execute('SELECT expires,revoked FROM worker_credentials WHERE batch=?', (OLD_BATCH,)).fetchall()
    assert credentials and all(revoked or timestamp(expires).timestamp() <= now for expires, revoked in credentials)


def quiescent(db, *, allow_unknown=False):
    rows = db.execute("SELECT id FROM pod_batches WHERE cleanup!='confirmed' OR state NOT IN ('succeeded','failed','canceled')").fetchall()
    if rows:
        assert allow_unknown and [row[0] for row in rows] == [OLD_BATCH]
        known_unknown(db)
    assert db.execute('SELECT count(*) FROM live_job_links l LEFT JOIN pod_batches p ON p.id=l.batch WHERE p.id IS NULL').fetchone()[0] == 0
    return bool(rows)


def monitor_ready(db, status, *, allow_unknown=False, now=None):
    now = time.time() if now is None else now
    assert 0 <= now - status['checked_at'] < 45 and not status.get('error')
    if status.get('ready') is not True:
        assert allow_unknown and status.get('unresolved') == [OLD_BATCH] and status.get('due_batches') == 1
        known_unknown(db, now)


def verify_absent(token, *, transport):
    from deployment.cleanup_monitor import CleanupOnlyProvider
    provider = CleanupOnlyProvider(token, scope=OLD_SCOPE, transport=transport)
    assert provider.find(OLD_BATCH, OLD_BATCH) == [], 'Old allocation appeared; let cleanup reconcile it first'


def checkpoint(database, assets, output):
    """Private forensic rollback copy, deliberately not a restorable bundle."""
    output = Path(output)
    output.mkdir(mode=0o700)
    with sqlite3.connect(database) as source, sqlite3.connect(output / 'studio.sqlite') as target:
        quiescent(source, allow_unknown=True)
        source.backup(target)
        assert target.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        quiescent(target, allow_unknown=True)
    shutil.copytree(assets, output / 'assets')
    checksums = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in output.rglob('*') if path.is_file()}
    (output / 'CHECKPOINT.json').write_text(json.dumps({
        'kind': 'maintenance-forensic-checkpoint', 'automatic_restore_allowed': False,
        'unresolved_request': OLD_BATCH, 'billing_reservation_retained': True,
        'sha256': checksums, 'created_at': time.time()}, indent=2) + '\n')


if __name__ == '__main__':
    import sys
    checkpoint('/var/lib/wan/studio.sqlite', '/var/lib/wan/assets', sys.argv[1])
