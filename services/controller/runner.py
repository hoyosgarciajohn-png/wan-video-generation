"""Recoverable single-job local fixture runner; never allocates cloud resources.

Run continuously using serve(stop_event), or call tick() for one scheduler pass.
An OS file lock prevents multiple runner processes from rendering simultaneously
against the same database. Persisted claims survive restarts; abandoned claims
become retryable only after lease expiry. SQLite remains the execution authority.
"""
import fcntl
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from workers.gpu.worker import run_once


class FixtureRunner:
    def __init__(self, control, *, renderer=run_once):
        self.control, self.renderer = control, renderer
        self.worker_id = 'fixture-runner-' + uuid4().hex
        self.lock_path = Path(str(Path(control.db_path).resolve()) + '.runner.lock')
        self.last_error = None

    def _candidates(self):
        candidates = []
        with self.control.transaction() as db:
            for row in db.execute('SELECT owner,bundle FROM projects ORDER BY id').fetchall():
                owner, bundle = row[0], json.loads(row[1])
                changed = False
                for batch in bundle['batches']:
                    if batch['execution_mode'] != 'fixture':
                        continue
                    before = json.dumps([batch, bundle['attempts']], sort_keys=True)
                    self.control._reconcile(bundle, batch, self.control.clock())
                    changed |= before != json.dumps([batch, bundle['attempts']], sort_keys=True)
                    if batch['state'] == 'rendering':
                        candidates.append((owner, bundle['project']['id'], batch['id']))
                if changed:
                    self.control._save(db, bundle)
        return candidates

    def tick(self):
        """Return True when one attempt was executed (success or failure)."""
        with self.lock_path.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            for owner, project, batch in self._candidates():
                client = self.control.worker_client(owner, project, batch, self.worker_id)
                claim = client.claim()
                if claim is None:
                    continue
                try:
                    self.renderer(claim, client, self.control.asset_root)
                    self.last_error = None
                except Exception:
                    # Error strings can contain prompts or filesystem diagnostics.
                    self.last_error = 'fixture_render_failed'
                    try:
                        client.fail(claim['attempt'], 'worker_failed')
                    except (ValueError, PermissionError):
                        pass  # Lease already fenced, canceled or completed.
                return True
        return False

    def serve(self, stop_event, *, poll_interval=1):
        """Drain durable work; stop gracefully after the current attempt."""
        if not isinstance(poll_interval, (int, float)) or not 0 < poll_interval <= 60:
            raise ValueError('Poll interval must be between zero and sixty seconds')
        while not stop_event.is_set():
            try:
                worked = self.tick()
            except (OSError, sqlite3.Error):
                self.last_error = 'fixture_scheduler_unavailable'
                worked = False
            if not worked:
                stop_event.wait(poll_interval)
