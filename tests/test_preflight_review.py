"""Independent checks that offline evidence cannot grant execution authority."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.controller import preflight


class PreflightReviewTests(unittest.TestCase):
    def test_missing_inputs_remain_actionable_and_non_executable(self):
        plan = preflight.evaluate_plan({})
        self.assertIsNone(plan['intent'])
        self.assertFalse(plan['execution_authorized'])
        self.assertFalse(plan['ready_for_live_run'])
        gates = {g['id']:g for g in plan['gates']}
        self.assertEqual(gates['intent_constraints']['status'], 'MISSING_OR_INVALID')
        for name in ('live_admission_not_implemented','real_worker_bridge_not_implemented',
                     'host_storage_acceptance_unverified','specific_execution_authorization_missing'):
            self.assertEqual(gates[name]['status'], 'BLOCKED')
            self.assertTrue(gates[name]['action'])

    def test_write_once_tamper_current_source_and_forged_authority(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'plan.json'
            plan = preflight.evaluate_plan({})
            preflight.write_plan(plan, path)
            self.assertEqual(preflight.verify_plan(path), plan)
            with self.assertRaises(FileExistsError):
                preflight.write_plan(plan, path)
            altered = dict(plan, ready_for_live_run=True)
            path.write_text(json.dumps(altered))
            with self.assertRaises(ValueError):
                preflight.verify_plan(path)
            altered['plan_sha256'] = preflight._hash({k:v for k,v in altered.items() if k != 'plan_sha256'})
            path.write_text(json.dumps(altered))
            with self.assertRaises(ValueError):
                preflight.verify_plan(path)
            path.write_text(json.dumps(plan))
            with patch.object(preflight, '_sources', return_value={'changed.py':'0'*64}):
                with self.assertRaises(ValueError):
                    preflight.verify_plan(path)

    def test_pass_text_does_not_establish_build_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path / 'manifest.json').write_text(json.dumps({
                'schema_version':1,'target':'gpu','mode':'LOCAL_EXECUTION','source_dirty':False,
                'gates':{key:'PASS' for key in ('image_build','image_identity','runtime_smoke','fixture_smoke')}}))
            with self.assertRaises(ValueError):
                preflight._build(path, 'registry.example/fictional@sha256:' + '0'*64)
