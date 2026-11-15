"""CPU-only acceptance using synthetic footage and soundtrack."""

import copy
import subprocess
import tempfile
import unittest
from array import array
from pathlib import Path

from workers.media.export import digest, export_bundle, probe


class ExportTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.rate = {"numerator": 4, "denominator": 1}
        self.assets = [
            self.media("blue", "video", "color=c=blue:s=64x48:r=4:d=300"),
            self.media("red", "video", "color=c=red:s=64x48:r=4:d=300"),
            self.media("tone", "audio", "sine=frequency=440:duration=2"),
        ]

    def media(self, name, kind, filter_value):
        suffix = "mp4" if kind == "video" else "wav"
        path = self.root / f"{name}.{suffix}"
        subprocess.run([
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i", filter_value, str(path),
        ], check=True)
        return dict(
            id=name, project_id="fiction", owner_id="owner", kind=kind,
            object_key=path.name, bytes=path.stat().st_size, sha256=digest(path),
            duration_ms=300000 if kind == "video" else 2000,
        )

    def bundle(self, kind, seconds):
        cap = 300 if kind == "music_video" else 1800
        items = []
        for start in range(0, seconds, 299):
            items.append(dict(
                take_id="blue", source_in_ms=1000,
                source_out_ms=1000 + min(seconds - start, 299) * 1000,
            ))
        timestamp = "2026-11-15T00:00:00Z"
        return dict(
            project=dict(id="fiction", owner_id="owner", kind=kind, runtime_limit_ms=cap * 1000),
            assets=self.assets,
            takes=[
                dict(id=name, project_id="fiction", asset_id=name, duration_ms=300000,
                     width=64, height=48, frame_rate=self.rate)
                for name in ("blue", "red")
            ],
            reviews=[
                dict(project_id="fiction", take_id=name, decision="approved", decided_at=timestamp)
                for name in ("blue", "red")
            ],
            timelines=[dict(
                id="timeline", project_id="fiction", revision=1, duration_ms=seconds * 1000,
                created_at=timestamp, items=items,
                audio=[dict(asset_id="tone", source_in_ms=250, source_out_ms=1250,
                            timeline_start_ms=seconds * 1000 - 2000)],
            )],
            exports=[dict(
                id=kind, project_id="fiction", timeline_id="timeline", timeline_revision=1,
                profile=dict(width=64, height=48, frame_rate=self.rate,
                             container="mp4", video_codec="h264", audio_codec="aac"),
            )],
        )

    def run_job(self, bundle, progress=None):
        return export_bundle(
            bundle, bundle["exports"][0]["id"], "fiction", self.root, self.root / "jobs", progress,
        )

    def test_runtime_caps_playback_and_soundtrack_sync(self):
        original = self.assets[-1]["sha256"]
        for kind, seconds in (("music_video", 300), ("short_film", 1800), ("cartoon", 1800)):
            with self.subTest(kind=kind):
                output = self.run_job(self.bundle(kind, seconds))
                video = probe(output, "v:0")
                self.assertEqual(float(video["duration"]), seconds)
                self.assertEqual(video["avg_frame_rate"], "4/1")
                subprocess.run([
                    "ffmpeg", "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-",
                ], check=True)
                samples = array("h", subprocess.check_output([
                    "ffmpeg", "-v", "error", "-ss", str(seconds - 2.5), "-i", str(output),
                    "-t", "2", "-map", "0:a:0", "-ar", "8000", "-ac", "1", "-f", "s16le", "-",
                ]))
                self.assertLess(max(map(abs, samples[:3700])), 40)
                self.assertGreater(max(map(abs, samples[4300:11700])), 1000)
                self.assertLess(max(map(abs, samples[12400:])), 40)
                with self.assertRaisesRegex(ValueError, "cap exceeded"):
                    self.run_job(self.bundle(kind, seconds + 1))
        self.assertEqual(digest(self.root / "tone.wav"), original)

    def test_replacement_retry_and_snapshot_isolation(self):
        bundle = self.bundle("music_video", 4)
        first = bundle["timelines"][0]
        first["items"] *= 2
        first["items"] = [dict(item, source_out_ms=3000) for item in first["items"]]
        original = self.run_job(bundle)
        revision = copy.deepcopy(first)
        revision["revision"] = 2
        revision["items"][1]["take_id"] = "red"
        bundle["timelines"].append(revision)
        bundle["exports"][0].update(id="replacement", timeline_revision=2)

        def interrupt(state, count, total):
            if state == "rendering" and count == 1:
                raise RuntimeError("Fictional interruption")

        with self.assertRaisesRegex(RuntimeError, "interruption"):
            self.run_job(bundle, interrupt)
        segment, = (
            path for path in (self.root / "jobs").glob("*/shot-000000.mp4")
            if path.parent != original.parent
        )
        mtime = segment.stat().st_mtime_ns
        replacement = self.run_job(bundle)
        self.assertEqual(segment.stat().st_mtime_ns, mtime)

        def pixel(path, timestamp):
            return subprocess.check_output([
                "ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", str(path),
                "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-",
            ])[:3]

        self.assertEqual(pixel(original, 1), pixel(replacement, 1))
        self.assertNotEqual(pixel(original, 3), pixel(replacement, 3))
        revision["items"][1]["take_id"] = "blue"
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            self.run_job(bundle)

    def test_rejects_foreign_take_and_wrong_frame_rate(self):
        bundle = self.bundle("music_video", 4)
        bundle["takes"][0]["project_id"] = "foreign"
        with self.assertRaisesRegex(ValueError, "another project"):
            self.run_job(bundle)
        bundle["takes"][0].update(
            project_id="fiction", frame_rate={"numerator": 5, "denominator": 1},
        )
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.run_job(bundle)
