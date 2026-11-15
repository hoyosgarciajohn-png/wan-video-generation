"""Validate the shared bundle and cross-record invariants with fictional media."""

import argparse
from datetime import datetime
from fractions import Fraction
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "contracts" / "bundle.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
COLLECTIONS = ("assets", "shots", "batches", "attempts", "takes", "reviews", "timelines", "exports")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def linked(records, record_id, label):
    require(record_id in records, f"Unknown {label}: {record_id}")
    return records[record_id]


def validate_bundle(bundle, media_root=None):
    """Check static contract consistency. Runtime authorization belongs to B02."""
    VALIDATOR.validate(bundle)
    project = bundle["project"]
    runtime_cap = 300000 if project["kind"] == "music_video" else 1800000
    require(project["runtime_limit_ms"] <= runtime_cap, "Project exceeds the supported runtime cap")
    indexes = {}
    for collection in COLLECTIONS:
        records = bundle[collection]
        indexes[collection] = {
            (record["id"], record["revision"]) if collection == "timelines" else record["id"]: record
            for record in records
        }
        require(len(indexes[collection]) == len(records), f"Duplicate IDs in {collection}")
        for record in records:
            require(record["project_id"] == project["id"], f"Cross-project record in {collection}")

    media_probes = {}
    for asset in bundle["assets"]:
        require(asset["owner_id"] == project["owner_id"], "Asset owner mismatch")
        path = PurePosixPath(asset["object_key"])
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in str(path),
                "Asset key must be a relative object key without traversal")
        if asset["kind"] in ("audio", "video"):
            require(asset["duration_ms"] is not None, "Timed media requires a duration")
        if media_root is not None:
            root = Path(media_root).resolve()
            source = (root / asset["object_key"]).resolve()
            require(source.is_relative_to(root), "Asset path escapes the media root")
            content = source.read_bytes()
            require(len(content) == asset["bytes"], "Asset size mismatch")
            require(hashlib.sha256(content).hexdigest() == asset["sha256"], "Asset checksum mismatch")
            probe = json.loads(subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(source)],
                text=True,
            ))
            media_probes[asset["id"]] = probe
            if asset["duration_ms"] is not None:
                duration_ms = float(probe["format"]["duration"]) * 1000
                require(abs(duration_ms - asset["duration_ms"]) <= 50, "Media duration mismatch")

    for shot in bundle["shots"]:
        for asset_id in shot["reference_asset_ids"]:
            asset = linked(indexes["assets"], asset_id, "reference asset")
            require(asset["kind"] == "image", "Shot reference must be an image")

    snapshot_indexes = {}
    for batch in bundle["batches"]:
        budget = batch["budget"]
        # Actual bills can exceed a cap after delayed provider accounting.
        # Preserve those bills while preventing additional reservations.
        require(budget["reserved_cents"] <= max(0, budget["approved_cents"] - budget["spent_cents"]),
                "Budget commitments exceed approval")
        if batch["execution_mode"] == "fixture":
            require(all(budget[key] == 0 for key in ("approved_cents", "reserved_cents", "spent_cents")),
                    "Fixture budget must be zero")
        else:
            require(budget["approved_cents"] > 0, "Runpod requires a positive approved cap")
        require(timestamp(batch["deadline_at"]) > timestamp(batch["approved_at"]), "Invalid batch deadline")
        snapshots = batch["shot_snapshots"]
        snapshot_indexes[batch["id"]] = {item["shot_id"]: item for item in snapshots}
        require(len(snapshot_indexes[batch["id"]]) == len(snapshots), "Duplicate shot in batch")
        for snapshot in snapshots:
            shot = linked(indexes["shots"], snapshot["shot_id"], "shot")
            require(snapshot["revision"] <= shot["revision"], "Snapshot references a future shot revision")
            for asset_id in snapshot["reference_asset_ids"]:
                asset = linked(indexes["assets"], asset_id, "snapshot reference")
                require(asset["kind"] == "image", "Snapshot reference must be an image")
            if snapshot["revision"] == shot["revision"]:
                for key in ("prompt", "reference_asset_ids", "target_duration_ms", "settings"):
                    require(snapshot[key] == shot[key], f"Snapshot differs from shot revision in {key}")

    for attempt in bundle["attempts"]:
        batch = linked(indexes["batches"], attempt["batch_id"], "batch")
        snapshot = linked(snapshot_indexes[batch["id"]], attempt["shot_id"], "batch shot")
        require(attempt["shot_revision"] == snapshot["revision"], "Attempt shot revision mismatch")
        require(attempt["settings"] == snapshot["settings"], "Attempt settings mismatch")
        require(attempt["model_profile"] == batch["model_profile"], "Attempt model profile mismatch")
        start = timestamp(attempt["started_at"])
        lease_end = timestamp(attempt["lease_expires_at"])
        require(timestamp(batch["approved_at"]) <= start < timestamp(batch["deadline_at"]),
                "Attempt started outside its batch window")
        require(lease_end > start, "Attempt lease is invalid")
        if attempt["completed_at"] is not None:
            require(start <= timestamp(attempt["completed_at"]), "Attempt completed before starting")
        if attempt["state"] == "succeeded":
            require(attempt["completed_at"] is not None and attempt["failure_reason"] is None,
                    "Successful attempt needs a completion time and empty failure reason")
            require(timestamp(attempt["completed_at"]) <= lease_end, "Attempt completed outside its lease")

    attempt_takes = set()
    for take in bundle["takes"]:
        attempt = linked(indexes["attempts"], take["attempt_id"], "attempt")
        require(take["attempt_id"] not in attempt_takes, "Multiple committed takes for one attempt")
        attempt_takes.add(take["attempt_id"])
        require(attempt["state"] == "succeeded", "Committed take requires successful attempt")
        require(take["shot_id"] == attempt["shot_id"], "Take shot mismatch")
        require(timestamp(attempt["completed_at"]) <= timestamp(take["committed_at"]) <=
                timestamp(attempt["lease_expires_at"]), "Take committed outside its lease")
        asset = linked(indexes["assets"], take["asset_id"], "take asset")
        require(asset["kind"] == "video" and asset["duration_ms"] == take["duration_ms"],
                "Take video metadata mismatch")
        for key in ("width", "height", "frame_rate"):
            require(take[key] == attempt["settings"][key], f"Take {key} differs from attempt")
        if media_root is not None:
            streams = media_probes[asset["id"]]["streams"]
            video = next((stream for stream in streams if stream["codec_type"] == "video"), None)
            require(video is not None, "Take has no video stream")
            require((video["width"], video["height"]) == (take["width"], take["height"]),
                    "Media dimensions mismatch")
            expected_rate = Fraction(take["frame_rate"]["numerator"], take["frame_rate"]["denominator"])
            require(Fraction(video["avg_frame_rate"]) == expected_rate, "Media frame rate mismatch")

    reviews = sorted(bundle["reviews"], key=lambda review: timestamp(review["decided_at"]))
    for review in reviews:
        take = linked(indexes["takes"], review["take_id"], "reviewed take")
        require(timestamp(review["decided_at"]) >= timestamp(take["committed_at"]), "Review predates take")

    for timeline in bundle["timelines"]:
        approved_takes = set()
        for review in reviews:
            if timestamp(review["decided_at"]) <= timestamp(timeline["created_at"]):
                if review["decision"] == "approved":
                    approved_takes.add(review["take_id"])
                else:
                    approved_takes.discard(review["take_id"])
        duration = 0
        for item in timeline["items"]:
            take = linked(indexes["takes"], item["take_id"], "timeline take")
            require(take["id"] in approved_takes, "Timeline take requires approval")
            require(item["source_in_ms"] < item["source_out_ms"] <= take["duration_ms"], "Invalid take trim")
            duration += item["source_out_ms"] - item["source_in_ms"]
        require(duration == timeline["duration_ms"], "Timeline duration mismatch")
        require(duration <= project["runtime_limit_ms"], "Timeline exceeds project runtime limit")
        for item in timeline["audio"]:
            asset = linked(indexes["assets"], item["asset_id"], "timeline audio")
            require(asset["kind"] == "audio", "Audio item requires an audio asset")
            require(item["source_in_ms"] < item["source_out_ms"] <= asset["duration_ms"], "Invalid audio trim")
            require(item["timeline_start_ms"] + item["source_out_ms"] - item["source_in_ms"] <= duration,
                    "Audio exceeds timeline")

    for export in bundle["exports"]:
        timeline = linked(indexes["timelines"], (export["timeline_id"], export["timeline_revision"]),
                          "export timeline revision")
        if export["output_asset_id"] is not None:
            asset = linked(indexes["assets"], export["output_asset_id"], "export output")
            require(asset["kind"] == "video" and asset["duration_ms"] == timeline["duration_ms"],
                    "Export output metadata mismatch")
        if export["state"] == "succeeded":
            require(export["output_asset_id"] is not None, "Successful export requires an output asset")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, nargs="?", default=ROOT / "fixtures" / "project.json")
    parser.add_argument("--media-root", type=Path, help="Also verify local asset sizes and SHA-256 hashes")
    args = parser.parse_args()
    validate_bundle(json.loads(args.bundle.read_text()), args.media_root)
    print("PASS: shared contract and record invariants")


if __name__ == "__main__":
    main()
