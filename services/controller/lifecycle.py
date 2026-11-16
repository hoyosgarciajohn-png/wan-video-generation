"""Durable fixture-mode Pod lifecycle for contract 0.1.0."""
import json
import sqlite3
from contextlib import contextmanager
from typing import Protocol
from uuid import uuid4

from src.wan_platform.fake_provider import Pod
from services.controller.runpod import ProviderCreateError, ProviderCreateRejected


class Provider(Protocol):
    def create(self, batch_id: str, request_key: str) -> Pod: ...
    def find(self, batch_id: str, request_key: str) -> list[Pod]: ...
    def get(self, pod_id: str) -> object | None: ...
    def delete(self, pod_id: str) -> None: ...


class Lifecycle:
    def __init__(self, path, provider: Provider):
        self.path = path
        self.provider = provider
        with self.transaction() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS pod_batches (
                    id TEXT PRIMARY KEY, project TEXT NOT NULL, idem TEXT NOT NULL,
                    snapshot TEXT NOT NULL, deadline INTEGER NOT NULL,
                    state TEXT NOT NULL DEFAULT 'queued',
                    cleanup TEXT NOT NULL DEFAULT 'pending',
                    pod_id TEXT,
                    UNIQUE(project, idem)
                )
            """)
            if 'create_diagnostic' not in {row[1] for row in db.execute('PRAGMA table_info(pod_batches)')}:
                db.execute('ALTER TABLE pod_batches ADD COLUMN create_diagnostic TEXT')

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        finally:
            db.close()

    def admit(self, project, key, snapshot, deadline, now):
        """The caller supplies a project resolved by its authorization layer."""
        canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                               allow_nan=False)
        with self.transaction() as db:
            row = db.execute(
                "SELECT * FROM pod_batches WHERE project=? AND idem=?",
                (project, key),
            ).fetchone()
            if row:
                if (row["snapshot"], row["deadline"]) != (canonical, deadline):
                    raise ValueError("Idempotency key already used for different input")
                return row["id"]
            if deadline <= now:
                raise ValueError("Deadline must be in the future")
            batch = uuid4().hex
            db.execute("""
                INSERT INTO pod_batches (id, project, idem, snapshot, deadline)
                VALUES (?, ?, ?, ?, ?)
            """, (batch, project, key, canonical, deadline))
            return batch

    def status(self, project, batch):
        with self.transaction() as db:
            row = db.execute(
                "SELECT * FROM pod_batches WHERE id=? AND project=?",
                (batch, project),
            ).fetchone()
            if row is None:
                raise KeyError(batch)
            return dict(row)

    def cancel(self, project, batch):
        self.status(project, batch)
        self.finish(batch, "canceled")

    def finish(self, batch, outcome):
        if outcome not in ("canceled", "failed", "succeeded"):
            raise ValueError("Invalid terminal outcome")
        with self.transaction() as db:
            db.execute("""
                UPDATE pod_batches
                SET state=?, cleanup=CASE WHEN state='queued'
                                          THEN 'confirmed' ELSE cleanup END
                WHERE id=? AND (state IN ('provisioning', 'rendering')
                                OR (state='queued' AND ? != 'succeeded'))
            """, (outcome, batch, outcome))

    def provision(self, project, batch, now, authorize=None):
        row = self.status(project, batch)
        if row["deadline"] <= now:
            self.finish(batch, "failed")
            return
        with self.transaction() as db:
            current = db.execute("SELECT state FROM pod_batches WHERE id=?", (batch,)).fetchone()
            if authorize is not None and current["state"] == "queued":
                # Admission/budget policy shares the durable dispatch transition.
                # Reconciliation of an already-uncertain create must stay available.
                authorize(db)
            dispatch = db.execute("""
                UPDATE pod_batches SET state='provisioning'
                WHERE id=? AND state='queued'
            """, (batch,)).rowcount
        if not dispatch and row["state"] != "provisioning":
            return
        try:
            if dispatch:
                pod = self.provider.create(batch, batch)
            else:
                pods = self.provider.find(batch, batch)
                if len(pods) > 1:
                    self.finish(batch, "failed")
                    return
                if not pods:
                    return
                pod = pods[0]
        except ProviderCreateError as error:
            # Only this dispatch's definitive response can establish rejection.
            # Opt-in retries must prove every preceding request was rejected.
            # A GET error or an old missing diagnostic cannot close an allocation.
            if dispatch:
                with self.transaction() as db:
                    db.execute('UPDATE pod_batches SET create_diagnostic=? WHERE id=?',
                               (json.dumps(error.diagnostic, sort_keys=True), batch))
                    if isinstance(error, ProviderCreateRejected):
                        db.execute("""UPDATE pod_batches SET
                            state=CASE WHEN state='provisioning' THEN 'failed' ELSE state END,
                            cleanup='confirmed' WHERE id=? AND pod_id IS NULL""", (batch,))
            return
        except (TimeoutError, ConnectionError):
            return
        with self.transaction() as db:
            db.execute("""
                UPDATE pod_batches SET pod_id=?,
                    state=CASE WHEN state='provisioning' THEN 'rendering' ELSE state END
                WHERE id=?
            """, (pod.id, batch))

    def watchdog(self, now, *, batch_ids=None):
        """Run independently of provisioning and repeat until cleanup is confirmed."""
        with self.transaction() as db:
            rows = db.execute("""
                SELECT * FROM pod_batches WHERE cleanup != 'confirmed'
                  AND (deadline <= ? OR state IN ('failed', 'canceled', 'succeeded'))
            """, (now,)).fetchall()
        unresolved = []
        for row in rows:
            batch = row["id"]
            if batch_ids is not None and batch not in batch_ids:
                continue
            self.finish(batch, "failed")
            with self.transaction() as db:
                current = db.execute(
                    "SELECT * FROM pod_batches WHERE id=?", (batch,)
                ).fetchone()
            if current["cleanup"] == "confirmed":
                continue
            try:
                pods = {pod.id for pod in self.provider.find(batch, batch)}
                if current["pod_id"]:
                    pods.add(current["pod_id"])
                if not pods:
                    # A dispatched create may allocate after this inventory read.
                    raise ConnectionError("Launch outcome is still unknown")
                # Record an observed allocation before deletion so the watchdog
                # can establish absence after a restart between delete and commit.
                with self.transaction() as db:
                    db.execute(
                        "UPDATE pod_batches SET pod_id=COALESCE(pod_id, ?) WHERE id=?",
                        (min(pods), batch),
                    )
                for pod_id in pods:
                    if self.provider.get(pod_id) is not None:
                        self.provider.delete(pod_id)
                    if self.provider.get(pod_id) is not None:
                        raise ConnectionError("Pod remains in inventory")
                if self.provider.find(batch, batch):
                    raise ConnectionError("Batch still has Pods")
                cleanup = "confirmed"
            except (TimeoutError, ConnectionError):
                cleanup = "failed"
                unresolved.append(batch)
            with self.transaction() as db:
                db.execute("""
                    UPDATE pod_batches SET cleanup=?
                    WHERE id=? AND cleanup != 'confirmed'
                """, (cleanup, batch))
        return unresolved

