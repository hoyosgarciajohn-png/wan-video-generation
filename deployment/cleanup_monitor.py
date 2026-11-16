"""Independent cleanup process: reads durable bindings and can only GET/DELETE.

Runs separately from the web process and GPU. Same-host installation survives
web restarts but is not protection against loss of that host or its database.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time

from services.controller.lifecycle import Lifecycle
from services.controller.runpod import RunpodProvider, https_transport


class CleanupOnlyProvider(RunpodProvider):
    def create(self, *_):
        raise PermissionError('Cleanup monitor cannot create resources')

    def _request(self, method, path, data=None):
        if method not in ('GET', 'DELETE') or data is not None:
            raise PermissionError('Cleanup transport only permits GET and DELETE')
        return super()._request(method, path, data)


def sweep(database, token, *, transport, now=None):
    database = Path(database).resolve(strict=True)
    now = time.time() if now is None else now
    # Missing live tables are a setup error, not successful monitoring.
    with sqlite3.connect(database) as db:
        rows = db.execute('''SELECT l.owner,l.project,l.batch,p.pod_id FROM live_job_links l
            JOIN pod_batches p ON p.id=l.batch AND p.project=l.project
            WHERE l.dispatch_state='attempted' AND p.cleanup!='confirmed'
            AND (p.deadline<=? OR p.state IN ('succeeded','failed','canceled'))''', (now,)).fetchall()
    unresolved = []
    for owner, project, batch, pod_id in rows:
        scope = json.dumps([owner, project], sort_keys=True, separators=(',', ':'))
        provider = CleanupOnlyProvider(token, scope=scope, transport=transport)
        expected_name = provider._name(batch, batch)
        provider._expected_names = lambda identity, saved=pod_id, name=expected_name: name if identity == saved else None
        unresolved.extend(Lifecycle(database, provider).watchdog(now, batch_ids={batch}))
    return {'checked_at': now, 'due_batches': len(rows), 'unresolved': unresolved,
            'ready': not unresolved, 'scope': 'cleanup-only; no billing settlement'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    state = Path(os.environ['WAN_STATE'])
    restored_database = os.environ.get('WAN_STUDIO_DATABASE')
    if (state / 'RESTORED.json').exists() and not restored_database:
        raise ValueError('Cleanup must use the explicit restored controller database')
    database = Path(restored_database) if restored_database else state / 'studio.sqlite'
    token = Path(os.environ['WAN_RUNPOD_TOKEN_FILE']).read_text().strip()
    status_file = Path(os.environ['WAN_MONITOR_STATUS'])
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    transport = https_transport()
    while not stop.is_set():
        try:
            result = sweep(database, token, transport=transport)
        except Exception:
            # Never emit provider credentials, environment or raw diagnostics.
            result = {'checked_at': time.time(), 'ready': False, 'error': 'cleanup_check_failed'}
        temporary = status_file.with_suffix('.tmp')
        temporary.write_text(json.dumps(result) + '\n')
        temporary.replace(status_file)
        print(json.dumps(result), flush=True)
        if args.once:
            raise SystemExit(0 if result['ready'] else 1)
        stop.wait(15)


if __name__ == '__main__':
    main()
