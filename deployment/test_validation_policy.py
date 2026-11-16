"""Fictional state and provider records; no network or cloud credentials."""
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from deployment import validation_policy as policy
from deployment.cleanup_monitor import CleanupOnlyProvider
from deployment.deadline_guard import watch_previous
from tests.test_live_execution import HTTP


def fixture(db):
    db.executescript('''
        CREATE TABLE pod_batches(id TEXT, project TEXT, state TEXT, cleanup TEXT, pod_id TEXT, deadline INTEGER);
        CREATE TABLE live_job_links(batch TEXT, owner TEXT, project TEXT, dispatch_state TEXT);
        CREATE TABLE live_reservations(batch TEXT, reserved_cents INTEGER, state TEXT);
        CREATE TABLE worker_credentials(batch TEXT, expires TEXT, revoked INTEGER);
    ''')
    db.execute("INSERT INTO pod_batches VALUES (?,?,'failed','failed',NULL,?)",
               (policy.OLD_BATCH, policy.OLD_PROJECT, policy.timestamp('2026-11-16T15:33:20Z').timestamp()))
    db.execute("INSERT INTO live_job_links VALUES (?,'john-hoyos',?,'attempted')", (policy.OLD_BATCH, policy.OLD_PROJECT))
    db.execute("INSERT INTO live_reservations VALUES (?,400,'reserved')", (policy.OLD_BATCH,))
    db.execute("INSERT INTO worker_credentials VALUES (?,'2026-11-16T15:38:20Z',0)", (policy.OLD_BATCH,))
    db.commit()


class ValidationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        fixture(self.db)

    def test_only_explicit_allowance_accepts_the_exact_retained_unknown(self):
        before = list(self.db.iterdump())
        with self.assertRaises(AssertionError): policy.quiescent(self.db)
        self.assertTrue(policy.quiescent(self.db, allow_unknown=True))
        self.assertEqual(before, list(self.db.iterdump()))
        self.db.execute("INSERT INTO pod_batches VALUES ('another','fictional','failed','failed',NULL,1)")
        with self.assertRaises(AssertionError): policy.quiescent(self.db, allow_unknown=True)

    def test_changed_liability_resource_or_live_credential_blocks_exception(self):
        for sql in ["UPDATE live_reservations SET reserved_cents=0", "UPDATE live_reservations SET state='settled'",
                    "UPDATE pod_batches SET pod_id='fictional-pod'", "UPDATE pod_batches SET state='provisioning'",
                    "UPDATE worker_credentials SET expires='2099-01-01T00:00:00Z'",
                    "UPDATE live_job_links SET project='other'", "UPDATE pod_batches SET deadline=1"]:
            with self.subTest(sql=sql):
                self.db.execute('SAVEPOINT mutation')
                self.db.execute(sql)
                with self.assertRaises(AssertionError): policy.known_unknown(self.db)
                self.db.execute('ROLLBACK TO mutation')
                self.db.execute('RELEASE mutation')

    def test_monitor_must_be_fresh_and_only_report_the_old_request(self):
        now = time.time()
        status = dict(checked_at=now,ready=False,unresolved=[policy.OLD_BATCH],due_batches=1)
        policy.monitor_ready(self.db,status,allow_unknown=True,now=now)
        for change in [dict(checked_at=now-45),dict(checked_at=now+1),dict(error='cleanup_check_failed'),
                       dict(unresolved=['other']),dict(due_batches=2)]:
            with self.assertRaises(AssertionError): policy.monitor_ready(self.db,dict(status,**change),allow_unknown=True,now=now)

    def test_previous_guard_deletes_late_old_pod_without_touching_new_test(self):
        http = HTTP()
        provider = CleanupOnlyProvider('fictional',scope=policy.OLD_SCOPE,transport=http)
        self.assertEqual(watch_previous(provider,set()),'NO_ALLOCATION_OBSERVED')
        http.pods['old']={'id':'old','name':provider._name(policy.OLD_BATCH,policy.OLD_BATCH)}
        http.pods['new']={'id':'new','name':'fictional-new-trial'}
        with self.assertRaises(AssertionError): policy.verify_absent('fictional',transport=http)
        observed=set()
        self.assertEqual(watch_previous(provider,observed),'ABSENCE_CONFIRMED')
        self.assertEqual(set(http.pods),{'new'})
        self.assertEqual(http.posts,0)
        policy.verify_absent('fictional',transport=http)

    def test_checkpoint_preserves_unresolved_liability_and_is_not_restore_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); database=root/'source.sqlite'; assets=root/'assets'; assets.mkdir()
            (assets/'fictional.txt').write_text('fictional media')
            with sqlite3.connect(database) as db: fixture(db)
            output=root/'checkpoint'
            policy.checkpoint(database,assets,output)
            with sqlite3.connect(output/'studio.sqlite') as db: policy.known_unknown(db)
            manifest=json.loads((output/'CHECKPOINT.json').read_text())
            self.assertFalse(manifest['automatic_restore_allowed'])
            self.assertFalse((output/'manifest.json').exists())
            self.assertEqual((output/'assets/fictional.txt').read_text(),'fictional media')
