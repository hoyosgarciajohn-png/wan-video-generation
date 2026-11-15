"""Fictional installed keys/signatures; no real approval or provider request."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import hmac
from unittest.mock import patch
import unittest

from services.controller.live_admission import LiveAdmission, APPROVAL_DOMAIN, AuthorityError
from services.controller.preflight import _sources
from services.controller.service import canonical
from tests import test_real_jobs


class LiveAdmissionTests(unittest.TestCase):
    def setUp(self):
        test_real_jobs.RealJobTests.setUp(self)
        self.secret = b'fictional-test-approval-key-only-123456'
        self.live = LiveAdmission(self.studio, approval_keys={'fictional': (self.owner, self.secret)})
        self.payload = dict(id='fictional-grant', owner=self.owner, project=self.project,
                            currency='USD', approved_cents=100, max_runtime_seconds=120,
                            valid_until=self.terms['valid_until'], profile=self.profile,
                            source_sha256=_sources(), launch_profile={
                                'image': self.profile['image_ref'], 'gpu': {'id': 'fictional', 'count': 1},
                                'cloud': 'SECURE', 'disk': 50, 'dataCenterIds': ['fictional'],
                                'mounts': {}, 'ports': [], 'env': {}})
        self.request['approval_id'] = self.payload['id']

    def signed(self, payload=None, domain=APPROVAL_DOMAIN):
        payload = deepcopy(self.payload if payload is None else payload)
        signature = hmac.new(self.secret, (domain + '\n' + canonical(payload)).encode(), hashlib.sha256).hexdigest()
        return dict(key_id='fictional', payload=payload, signature=signature)

    def test_concurrent_atomic_admission_restart_and_cancel_replay(self):
        envelope = self.signed()
        self.live.approve(self.owner, self.project, envelope)
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs = list(pool.map(lambda _: self.live.submit(self.owner, self.project, self.request), range(3)))
        batch = jobs[0]['batch']['id']
        self.assertEqual({j['batch']['id'] for j in jobs}, {batch})
        other = LiveAdmission(self.studio, approval_keys={'fictional': (self.owner, self.secret)})
        self.assertEqual(other.submit(self.owner, self.project, self.request)['batch']['id'], batch)
        with self.control.transaction() as db:
            for table in ('live_reservations', 'live_job_links'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 1)
            self.assertIsNone(db.execute('SELECT batch FROM budget_reservations WHERE batch=?', (batch,)).fetchone())
        reply = other.cancel(self.owner, self.project, batch)
        self.assertEqual(reply['reservation_state'], 'released')
        self.assertEqual(reply['batch']['cleanup_state'], 'confirmed')
        self.assertEqual(other.cancel(self.owner, self.project, batch), reply)
        self.assertEqual(other.submit(self.owner, self.project, self.request), reply)

    def test_signature_owner_domain_expiry_source_and_boolean_rejected(self):
        for payload, domain in ((dict(self.payload, owner='foreign'), APPROVAL_DOMAIN),
                                (self.payload, 'wrong-domain'),
                                (dict(self.payload, valid_until='2020-01-01T00:00:00Z'), APPROVAL_DOMAIN),
                                (dict(self.payload, source_sha256={}), APPROVAL_DOMAIN),
                                (dict(self.payload, approved_cents=True), APPROVAL_DOMAIN)):
            with self.assertRaises((AuthorityError, ValueError)):
                self.live.approve(self.owner, self.project, self.signed(payload, domain))
        unsigned = self.signed()
        unsigned['payload']['approved_cents'] += 1
        with self.assertRaises(AuthorityError):
            self.live.approve(self.owner, self.project, unsigned)
        with self.control.transaction() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM live_approvals').fetchone()[0], 0)

    def test_new_grant_does_not_reset_project_cap_and_revocation_is_sticky(self):
        self.live.approve(self.owner, self.project, self.signed())
        first = self.live.submit(self.owner, self.project, self.request)
        self.payload['id'] = 'second-grant'
        envelope = self.signed()
        self.live.approve(self.owner, self.project, envelope)
        request = dict(self.request, approval_id='second-grant', idempotency_key='second')
        with self.assertRaises(ValueError):
            self.live.submit(self.owner, self.project, request)
        self.live.cancel(self.owner, self.project, first['batch']['id'])
        self.assertEqual(self.live.submit(self.owner, self.project, request)['reservation_state'], 'reserved')
        self.live.revoke(self.owner, self.project, 'second-grant')
        with self.assertRaises(ValueError):
            self.live.approve(self.owner, self.project, envelope)

    def test_transaction_rollback_invalid_claim_and_source_changed(self):
        self.live.approve(self.owner, self.project, self.signed())
        with patch('services.controller.live_admission.validate_claim', side_effect=ValueError('fictional invalid claim')):
            with self.assertRaises(ValueError):
                self.live.submit(self.owner, self.project, self.request)
        with self.control.transaction() as db:
            for table in ('live_reservations','live_job_links','pod_batches'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)
        with patch('services.controller.live_admission._sources', return_value={'modified': 'source'}):
            with self.assertRaises(ValueError):
                self.live.submit(self.owner, self.project, self.request)

    def test_no_dispatch_or_simulated_approval_promotion(self):
        with self.assertRaises(KeyError):
            self.live.submit(self.owner, self.project, self.request)
        self.live.approve(self.owner, self.project, self.signed())
        with self.assertRaises(ValueError):
            self.live.prepare_provider(self.owner, self.project, self.payload['id'], {})
        job = self.live.submit(self.owner, self.project, self.request)
        self.assertFalse(job['dispatch_enabled'])
        with self.assertRaises((ValueError, KeyError)):
            self.bridge.provision(self.owner, self.project, job['batch']['id'])
        with self.assertRaises((ValueError, PermissionError)):
            self.control.worker_client(self.owner, self.project, job['batch']['id'], 'worker').claim()
        self.assertEqual(self.provider._pods, {})

    def test_simulated_watchdog_does_not_touch_pending_live_job(self):
        self.live.approve(self.owner, self.project, self.signed())
        live_job = self.live.submit(self.owner, self.project, self.request)
        simulation = dict(self.request, approval_id=self.bridge.budget.status(self.owner, self.project)['approval']['id'], idempotency_key='simulation')
        simulated = self.bridge.submit(self.owner, self.project, simulation)
        self.bridge.provision(self.owner, self.project, simulated['batch']['id'])
        self.bridge.cancel(self.owner, self.project, simulated['batch']['id'])
        self.assertEqual(self.bridge.watchdog(), [])
        self.assertEqual(self.bridge.status(self.owner, self.project, simulated['batch']['id'])['batch']['cleanup_state'], 'confirmed')
        self.assertEqual(self.live.status(self.owner, self.project, live_job['batch']['id'])['batch']['state'], 'queued')

    def test_even_consistent_installed_host_evidence_cannot_enable_dispatch(self):
        from services.controller.live_admission import HOST_DOMAIN, configuration_hash
        self.live.approve(self.owner, self.project, self.signed())
        self.live._host_keys = {'fictional': (self.owner, self.secret)}
        self.live._build_evidence = 'fictional-local-evidence'
        host = dict(owner=self.owner, project=self.project,
                    config_hash=configuration_hash(self.payload['profile'], self.payload['launch_profile']),
                    source_sha256=self.payload['source_sha256'], build_manifest_sha256='a' * 64,
                    valid_until=self.payload['valid_until'], worker_endpoint=self.profile['worker_endpoint'],
                    storage_id=self.profile['storage_id'])
        with patch('services.controller.live_admission._build', return_value={'manifest_sha256': 'a' * 64}):
            with self.assertRaisesRegex(AuthorityError, 'not installed'):
                self.live.prepare_provider(self.owner, self.project, self.payload['id'], self.signed(host, HOST_DOMAIN))
        altered = deepcopy(self.payload['launch_profile'])
        altered['disk'] += 1
        self.assertNotEqual(configuration_hash(self.profile, altered), host['config_hash'])

    def test_final_link_insert_failure_rolls_back_bundle_reservation_and_lifecycle(self):
        import sqlite3
        self.live.approve(self.owner, self.project, self.signed())
        with self.control.transaction() as db:
            db.execute("CREATE TRIGGER fictional_failure BEFORE INSERT ON live_job_links BEGIN SELECT RAISE(ABORT, 'fictional final insert failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.live.submit(self.owner, self.project, self.request)
        with self.control.transaction() as db:
            for table in ('live_reservations','live_job_links','pod_batches'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)
            self.assertEqual(self.control._load(db, self.owner, self.project)['batches'], [])
