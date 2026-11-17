"""Static cross-component fixtures and real decoding of synthetic media.

Runtime authorization, state transitions and controller recovery require B01–B04.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from integration.fixtures import project_bundle, replacement_bundle, stage_media
from scripts.validate_contract import COLLECTIONS, validate_bundle


class IntegrationPreparationTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("socket.socket.connect", side_effect=AssertionError("Unexpected network call"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.first = project_bundle("alpha")
        self.second = project_bundle("beta")

    def test_two_project_fixtures_validate_with_scoped_media(self):
        with tempfile.TemporaryDirectory() as directory:
            for bundle in (self.first, self.second):
                stage_media(bundle, directory)
                validate_bundle(json.loads(json.dumps(bundle)), Path(directory))
            self.assertNotEqual(self.first["project"]["owner_id"], self.second["project"]["owner_id"])
            for collection in COLLECTIONS:
                first_ids = {record["id"] for record in self.first[collection]}
                self.assertTrue(first_ids.isdisjoint(record["id"] for record in self.second[collection]))
            first_keys = {asset["object_key"] for asset in self.first["assets"]}
            self.assertTrue(first_keys.isdisjoint(asset["object_key"] for asset in self.second["assets"]))

    def test_foreign_references_are_rejected_across_component_boundaries(self):
        cases = (
            ("attempts", "batch_id", "batches", "Unknown batch"),
            ("takes", "attempt_id", "attempts", "Unknown attempt"),
            ("takes", "asset_id", "assets", "Unknown take asset"),
            ("reviews", "take_id", "takes", "Unknown reviewed take"),
            ("exports", "timeline_id", "timelines", "Unknown export timeline revision"),
        )
        for collection, field, foreign_collection, error in cases:
            with self.subTest(boundary=f"{collection}.{field}"):
                bundle = deepcopy(self.first)
                bundle[collection][0][field] = self.second[foreign_collection][0]["id"]
                with self.assertRaisesRegex(ValueError, error):
                    validate_bundle(bundle)

    def test_foreign_assets_cannot_be_grafted_by_rewriting_project_id(self):
        foreign = deepcopy(self.second["assets"][0])
        foreign["project_id"] = self.first["project"]["id"]
        self.first["assets"].append(foreign)
        with self.assertRaisesRegex(ValueError, "Asset owner mismatch"):
            validate_bundle(self.first)

    def test_replacement_preserves_old_take_and_export_revision(self):
        bundle = replacement_bundle("alpha")
        with tempfile.TemporaryDirectory() as directory:
            stage_media(bundle, directory)
            validate_bundle(bundle, Path(directory))
        self.assertEqual(bundle["takes"][0], self.first["takes"][0])
        self.assertEqual(bundle["timelines"][0], self.first["timelines"][0])
        self.assertEqual(bundle["exports"][0], self.first["exports"][0])
        self.assertNotEqual(bundle["timelines"][0]["items"], bundle["timelines"][1]["items"])
        bundle["reviews"][1]["decision"] = "rejected"
        with self.assertRaisesRegex(ValueError, "requires approval"):
            validate_bundle(bundle)
        # Removing the new revision leaves the captured old export valid.
        bundle["timelines"].pop()
        validate_bundle(bundle)

    def test_failed_attempt_retry_cannot_receive_a_committed_take(self):
        bundle = replacement_bundle("alpha")
        failed = deepcopy(bundle["attempts"][0])
        failed.update(id="alpha-failed-attempt", state="failed", failure_reason="worker_lost")
        bundle["attempts"].insert(0, failed)
        validate_bundle(bundle)
        bundle["takes"][1]["attempt_id"] = failed["id"]
        with self.assertRaisesRegex(ValueError, "requires successful attempt"):
            validate_bundle(bundle)

    def test_retry_with_expired_lease_cannot_commit(self):
        bundle = replacement_bundle("alpha")
        bundle["attempts"][1]["lease_expires_at"] = "2026-11-15T14:00:08Z"
        with self.assertRaisesRegex(ValueError, "outside its lease"):
            validate_bundle(bundle)

    def test_missing_and_partial_uploads_fail_media_verification(self):
        for fault in ("missing", "truncated"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                stage_media(self.first, directory)
                clip = Path(directory) / self.first["assets"][0]["object_key"]
                if fault == "missing":
                    clip.unlink()
                    with self.assertRaises(FileNotFoundError):
                        validate_bundle(self.first, Path(directory))
                else:
                    clip.write_bytes(clip.read_bytes()[:100])
                    with self.assertRaisesRegex(ValueError, "Asset size mismatch"):
                        validate_bundle(self.first, Path(directory))

    def test_symlink_cannot_escape_media_root(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            stage_media(self.first, directory)
            clip = Path(directory) / self.first["assets"][0]["object_key"]
            external = Path(outside) / "clip.mp4"
            clip.replace(external)
            clip.symlink_to(external)
            with self.assertRaisesRegex(ValueError, "escapes the media root"):
                validate_bundle(self.first, Path(directory))

    def test_music_film_and_cartoon_timeline_boundaries(self):
        for kind, cap in (("music_video", 360000), ("short_film", 1800000), ("cartoon", 1800000)):
            with self.subTest(kind=kind):
                bundle = deepcopy(self.first)
                bundle["project"].update(kind=kind, runtime_limit_ms=cap)
                timeline = bundle["timelines"][0]
                item = timeline["items"][0]
                timeline["items"] = [deepcopy(item) for _ in range(cap // 2000)]
                timeline["duration_ms"] = cap
                validate_bundle(bundle)
                timeline["items"].append({**item, "source_out_ms": 1})
                timeline["duration_ms"] += 1
                with self.assertRaisesRegex(ValueError, "exceeds project runtime limit"):
                    validate_bundle(bundle)

    def test_synthetic_sources_decode_completely_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            stage_media(self.first, directory)
            for asset in self.first["assets"]:
                source = Path(directory) / asset["object_key"]
                result = subprocess.run(
                    ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(source),
                     "-map", "0", "-f", "null", "-"],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), asset["sha256"])


if __name__ == "__main__":
    unittest.main()

