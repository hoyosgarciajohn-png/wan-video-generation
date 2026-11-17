"""Contract regressions that could desynchronize the parallel workstreams."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from jsonschema import ValidationError

from scripts.validate_contract import ROOT, validate_bundle


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads((ROOT / "fixtures" / "project.json").read_text())

    def test_complete_fixture_and_media(self):
        validate_bundle(self.bundle, ROOT / "fixtures")

    def test_six_minute_three_second_policy_preserves_smaller_project_limits(self):
        bundle = self.bundle
        bundle["project"]["runtime_limit_ms"] = 363000
        validate_bundle(bundle)
        bundle["project"]["runtime_limit_ms"] = 363001
        with self.assertRaisesRegex(ValueError, "supported runtime cap"):
            validate_bundle(bundle)
        bundle["project"]["runtime_limit_ms"] = 300000
        timeline = bundle["timelines"][0]
        item = timeline["items"][0]
        timeline["items"] = [deepcopy(item) for _ in range(170)] + [dict(item, source_out_ms=126)]
        timeline["duration_ms"] = 340126
        bundle["exports"] = []
        with self.assertRaisesRegex(ValueError, "exceeds project runtime limit"):
            validate_bundle(bundle)
        bundle["project"]["runtime_limit_ms"] = 363000
        validate_bundle(bundle)

    def test_cross_project_and_owner_references_are_rejected(self):
        for record, key in (("takes", "project_id"), ("assets", "owner_id")):
            with self.subTest(record=record, key=key):
                bundle = deepcopy(self.bundle)
                bundle[record][0][key] = "another-owner-or-project"
                with self.assertRaises(ValueError):
                    validate_bundle(bundle)

    def test_budget_types_and_cost_envelope(self):
        for value in (True, "5", 0.5, -1):
            with self.subTest(value=value):
                bundle = deepcopy(self.bundle)
                bundle["batches"][0]["budget"]["approved_cents"] = value
                with self.assertRaises(ValidationError):
                    validate_bundle(bundle)
        self.bundle["batches"][0]["execution_mode"] = "runpod"
        with self.assertRaisesRegex(ValueError, "positive approved cap"):
            validate_bundle(self.bundle)
        self.bundle["batches"][0]["budget"].update(approved_cents=100, spent_cents=70, reserved_cents=40)
        with self.assertRaisesRegex(ValueError, "exceed approval"):
            validate_bundle(self.bundle)
        self.bundle["batches"][0]["budget"].update(approved_cents=100, spent_cents=110, reserved_cents=0)
        validate_bundle(self.bundle)

    def test_frozen_revision_and_attempt_configuration(self):
        self.bundle["attempts"][0]["settings"]["seed"] = 43
        with self.assertRaisesRegex(ValueError, "settings mismatch"):
            validate_bundle(self.bundle)
        self.bundle["attempts"][0]["settings"]["seed"] = 42
        self.bundle["shots"][0]["revision"] = 2
        self.bundle["shots"][0]["prompt"] = "A revised prompt for a future render"
        validate_bundle(self.bundle)

    def test_take_link_and_lease(self):
        self.bundle["takes"][0]["attempt_id"] = "missing-attempt"
        with self.assertRaisesRegex(ValueError, "Unknown attempt"):
            validate_bundle(self.bundle)
        self.bundle["takes"][0]["attempt_id"] = "attempt-1"
        self.bundle["takes"][0]["committed_at"] = "2026-11-15T14:03:00Z"
        with self.assertRaisesRegex(ValueError, "outside its lease"):
            validate_bundle(self.bundle)

    def test_timeline_approval_trim_duration_and_project_limit(self):
        cases = (
            ("approval", lambda bundle: bundle["reviews"].clear()),
            ("trim", lambda bundle: bundle["timelines"][0]["items"][0].update(source_out_ms=2001)),
            ("duration", lambda bundle: bundle["timelines"][0].update(duration_ms=1999)),
            ("limit", lambda bundle: bundle["project"].update(runtime_limit_ms=1000)),
            ("cap", lambda bundle: bundle["project"].update(runtime_limit_ms=1800000)),
            ("audio", lambda bundle: bundle["timelines"][0]["audio"][0].update(timeline_start_ms=1)),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                bundle = deepcopy(self.bundle)
                mutate(bundle)
                with self.assertRaises(ValueError):
                    validate_bundle(bundle)

    def test_export_tracks_timeline_revision_and_output(self):
        self.bundle["exports"][0]["timeline_revision"] = 2
        with self.assertRaisesRegex(ValueError, "Unknown export timeline revision"):
            validate_bundle(self.bundle)
        self.bundle["exports"][0]["timeline_revision"] = 1
        self.bundle["exports"][0]["state"] = "succeeded"
        with self.assertRaisesRegex(ValueError, "requires an output asset"):
            validate_bundle(self.bundle)

    def test_historical_timeline_revision_and_approval_are_preserved(self):
        revised = deepcopy(self.bundle["timelines"][0])
        revised["revision"] = 2
        revised["created_at"] = "2026-11-15T14:00:07Z"
        self.bundle["timelines"].append(revised)
        self.bundle["reviews"].append({
            **self.bundle["reviews"][0], "id": "review-2", "decision": "rejected",
            "decided_at": "2026-11-15T14:00:08Z",
        })
        validate_bundle(self.bundle)
        revised["created_at"] = "2026-11-15T14:00:09Z"
        with self.assertRaisesRegex(ValueError, "requires approval"):
            validate_bundle(self.bundle)

    def test_render_success_can_have_unconfirmed_cleanup(self):
        self.bundle["batches"][0]["cleanup_state"] = "failed"
        validate_bundle(self.bundle)

    def test_corrupt_media_and_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "fixtures" / "media", root / "media")
            clip = root / "media" / "clip.mp4"
            data = bytearray(clip.read_bytes())
            data[-1] ^= 1
            clip.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                validate_bundle(self.bundle, root)
        self.bundle["assets"][0]["object_key"] = "../outside.mp4"
        with self.assertRaisesRegex(ValueError, "relative object key"):
            validate_bundle(self.bundle)


if __name__ == "__main__":
    unittest.main()
