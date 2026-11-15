"""Offline preflight is source-bound evidence review, never spending authority."""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment import build_verify
from services.controller import preflight
from workers.gpu.common import utcnow


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = utcnow()
        self.intent = dict(project_id='fictional-project', owner_id='fictional-owner', batch_id='fictional-batch',
            worker_id='fictional-worker', provider='runpod', region='owner-selected-region', gpu_type='owner-selected-gpu',
            gpu_count=1, image_ref='registry.example/wan@sha256:' + 'a' * 64,
            worker_endpoint='https://worker.example', runtime_seconds=300, reservation_cents=100,
            worker_ttl_seconds=600, storage=dict(kind='controller_bridge', namespace='projects/fictional-project',
              durable_artifact_id='owner-selected-storage', retention_days=7),
            pod=dict(disk_gib=100, model_mount='/models', output_mount='/worker', public_ports=[], privileged=False))

    def evaluate(self, intent=None, **kwargs):
        return preflight.evaluate_plan(self.intent if intent is None else intent, now=self.now, **kwargs)

    @staticmethod
    def gate(plan, name):
        return next(g for g in plan['gates'] if g['id'] == name)['status']

    def attestation(self, plan, **changes):
        value = dict(schema_version=1, owner_id=self.intent['owner_id'], project_id=self.intent['project_id'],
                     intent_sha256=plan['intent_sha256'], currency='USD', approved_cents=100,
                     max_runtime_seconds=300, issued_at=(self.now - timedelta(minutes=1)).isoformat(),
                     expires_at=(self.now + timedelta(minutes=10)).isoformat(), reference='private-owner-reference')
        value.update(changes)
        path = self.root / 'approval.json'
        path.write_text(json.dumps(value))
        return path

    def test_empty_report_lists_actual_missing_implementation(self):
        plan = self.evaluate({})
        self.assertFalse(plan['execution_authorized'])
        self.assertFalse(plan['ready_for_live_run'])
        self.assertEqual(self.gate(plan, 'intent_constraints'), 'MISSING_OR_INVALID')
        self.assertEqual(self.gate(plan, 'live_admission_not_implemented'), 'BLOCKED')
        self.assertEqual(self.gate(plan, 'real_worker_bridge_not_implemented'), 'BLOCKED')
        self.assertGreater(plan['locked_weight_bytes'], 0)
        self.assertEqual(plan['model_profile']['id'], 'wan22-ti2v-5b')

    def test_exact_intent_and_source_bound_immutable_artifact(self):
        plan = self.evaluate()
        self.assertEqual(self.gate(plan, 'intent_constraints'), 'CONSISTENT')
        path = self.root / 'plan.json'
        preflight.write_plan(plan, path)
        self.assertEqual(preflight.verify_plan(path), plan)
        with self.assertRaises(FileExistsError):
            preflight.write_plan(plan, path)
        modified_sources = dict(plan['source_sha256'])
        modified_sources['workers/gpu/model.lock.json'] = '0' * 64
        with patch.object(preflight, '_sources', return_value=modified_sources):
            with self.assertRaises(ValueError):
                preflight.verify_plan(path)
        value = json.loads(path.read_text())
        value['intent']['runtime_seconds'] = 500
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            preflight.verify_plan(path)

    def test_expired_mismatched_and_consistent_attestations_never_authorize(self):
        base = self.evaluate()
        valid = self.attestation(base)
        plan = self.evaluate(approval=valid)
        self.assertEqual(self.gate(plan, 'owner_attestation'), 'CONSISTENT')
        self.assertFalse(plan['execution_authorized'])
        self.assertNotIn('private-owner-reference', json.dumps(plan))
        for changes in ({'expires_at':self.now.isoformat()}, {'owner_id':'other-owner'},
                        {'intent_sha256':'0' * 64}, {'approved_cents':99}, {'max_runtime_seconds':299}):
            with self.subTest(changes=changes):
                self.assertEqual(self.gate(self.evaluate(approval=self.attestation(base, **changes)), 'owner_attestation'),
                                 'MISSING_OR_INVALID')
        changed = dict(self.intent, runtime_seconds=301)
        self.assertNotEqual(self.evaluate(changed)['intent_sha256'], base['intent_sha256'])

    def test_secret_fields_and_credential_urls_are_not_echoed(self):
        secret = 'fictional-sensitive-token-do-not-echo'
        for intent in (dict(self.intent, api_key=secret), dict(self.intent, worker_endpoint=f'https://user:{secret}@worker.example')):
            plan = self.evaluate(intent)
            self.assertEqual(self.gate(plan, 'intent_constraints'), 'MISSING_OR_INVALID')
            self.assertNotIn(secret, json.dumps(plan))
            self.assertIsNone(plan['intent'])
        intent = deepcopy(self.intent)
        intent['pod']['env'] = {'WAN_WORKER_TOKEN':secret}
        self.assertNotIn(secret, json.dumps(self.evaluate(intent)))

    def test_consistent_synthetic_build_evidence_and_modified_log(self):
        # This constructs synthetic evidence, not an assertion that Docker ran.
        from workers.gpu.cli import fixture_claim, FixtureClient
        from workers.gpu.worker import run_once
        from workers.gpu.common import atomic_json, digest
        directory, manifest = build_verify.prepare('gpu', self.root / 'complete-evidence')
        image_id = 'sha256:' + 'b' * 64
        manifest.update(mode='LOCAL_EXECUTION', source_dirty=False, image_id=image_id,
                        built_image_id=image_id, repo_digests=[self.intent['image_ref']])
        (directory / 'built-image-id.txt').write_text(image_id)
        model = json.loads((preflight.ROOT / 'workers/gpu/model.lock.json').read_text())
        claim = fixture_claim()
        result = run_once(claim, FixtureClient(claim, directory / 'fixture'), directory / 'fixture')
        atomic_json(directory / 'fixture/result.json', result)
        manifest['fixture_evidence'] = build_verify.verify_fixture(directory)
        values = dict(image_identity=[dict(Id=image_id, Architecture='amd64', Os='linux', RepoDigests=[self.intent['image_ref']])],
                      runtime_smoke=dict(runtime_import='PASS', source_revision=model['profile']['code_revision']))
        for item in manifest['planned_commands']:
            gate = item['gate']
            log = directory / (gate + '.log')
            log.write_text(json.dumps(values.get(gate, {'synthetic_test_record': True})))
            argv = item['argv'] if gate == 'image_build' else [image_id if a == manifest['image_tag'] else a for a in item['argv']]
            manifest['executed_commands'].append(dict(gate=gate, argv=argv, exit_code=0, log=log.name, log_sha256=digest(log)))
            manifest['gates'][gate] = 'PASS'
        build_verify.write_manifest(directory, manifest)
        plan = self.evaluate(build_evidence=directory)
        self.assertEqual(self.gate(plan, 'built_image_evidence'), 'CONSISTENT')
        self.assertFalse(plan['ready_for_live_run'])
        self.assertIn('local_evidence_consistency_only', plan['evidence']['image']['assurance'])
        (directory / 'runtime_smoke.log').write_text('modified')
        self.assertEqual(self.gate(self.evaluate(build_evidence=directory), 'built_image_evidence'), 'MISSING_OR_INVALID')

    def test_malformed_evidence_shapes_are_actionable_failures(self):
        directory = self.root / 'bad-evidence'
        directory.mkdir()
        for value in (None, [], {'gates': []}):
            with self.subTest(value=value):
                (directory / 'manifest.json').write_text(json.dumps(value))
                self.assertEqual(self.gate(self.evaluate(build_evidence=directory), 'built_image_evidence'), 'MISSING_OR_INVALID')
        path = self.root / 'bad-plan.json'
        path.write_text('[]')
        with self.assertRaises(ValueError):
            preflight.verify_plan(path)

    def test_pass_strings_without_executed_evidence_do_not_satisfy_image_gate(self):
        directory, manifest = build_verify.prepare('gpu', self.root / 'evidence')
        manifest.update(mode='LOCAL_EXECUTION', source_dirty=False, image_id='sha256:' + 'b' * 64,
                        built_image_id='sha256:' + 'b' * 64)
        manifest['gates'] = {key:'PASS' for key in manifest['gates']}
        (directory / 'built-image-id.txt').write_text(manifest['image_id'])
        build_verify.write_manifest(directory, manifest)
        plan = self.evaluate(build_evidence=directory)
        self.assertEqual(self.gate(plan, 'built_image_evidence'), 'MISSING_OR_INVALID')
        self.assertNotIn('image', plan['evidence'])
        model = directory / 'context/workers/gpu/model.lock.json'
        model.write_text(model.read_text() + ' ')
        self.assertEqual(self.gate(self.evaluate(build_evidence=directory), 'built_image_evidence'), 'MISSING_OR_INVALID')


if __name__ == '__main__':
    unittest.main()
