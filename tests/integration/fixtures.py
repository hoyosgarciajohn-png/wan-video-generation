"""Reusable contract fixtures for B05, derived from the canonical B00 bundle."""

from copy import deepcopy
import json
from pathlib import Path
import shutil

from scripts.validate_contract import COLLECTIONS, ROOT


def project_bundle(namespace):
    """Return a fresh fictional project with distinct IDs and scoped asset paths."""
    source = json.loads((ROOT / "fixtures/project.json").read_text())
    identifiers = {source["project"]["id"], source["project"]["owner_id"]}
    for collection in COLLECTIONS:
        identifiers.update(record["id"] for record in source[collection])
    identifiers.update(("scene-1", "fictional-worker", "lease-1", "fixture-batch-1", "fake-pod-1"))
    mapping = {value: f"{namespace}-{value}" for value in identifiers}

    def remap(value):
        if isinstance(value, dict):
            return {key: remap(item) for key, item in value.items()}
        if isinstance(value, list):
            return [remap(item) for item in value]
        if isinstance(value, str):
            return mapping.get(value, value)
        return value

    bundle = remap(source)
    bundle["project"]["title"] = f"Fictional {namespace} studio"
    for asset in bundle["assets"]:
        asset["object_key"] = f"projects/{bundle['project']['id']}/{asset['object_key']}"
    return bundle


def stage_media(bundle, destination):
    """Copy the two B00 synthetic assets into this fixture's project namespace."""
    for asset in bundle["assets"]:
        target = Path(destination) / asset["object_key"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "fixtures/media" / target.name, target)


def replacement_bundle(namespace):
    """Add a second take and timeline revision while retaining the first export."""
    bundle = project_bundle(namespace)
    attempt = deepcopy(bundle["attempts"][0])
    attempt.update(id=f"{namespace}-attempt-2", lease_id=f"{namespace}-lease-2",
                   started_at="2026-11-15T14:00:07Z", completed_at="2026-11-15T14:00:09Z")
    take = deepcopy(bundle["takes"][0])
    take.update(id=f"{namespace}-take-2", attempt_id=attempt["id"],
                committed_at="2026-11-15T14:00:10Z")
    # The fictional attempts reuse the same synthetic bytes as distinct objects.
    asset = deepcopy(bundle["assets"][0])
    asset.update(id=f"{namespace}-asset-video-2",
                 object_key=f"projects/{bundle['project']['id']}/replacement/clip.mp4")
    take["asset_id"] = asset["id"]
    review = deepcopy(bundle["reviews"][0])
    review.update(id=f"{namespace}-review-2", take_id=take["id"],
                  decided_at="2026-11-15T14:00:11Z")
    timeline = deepcopy(bundle["timelines"][0])
    timeline.update(revision=2, created_at="2026-11-15T14:00:12Z")
    timeline["items"][0]["take_id"] = take["id"]
    for collection, record in (("attempts", attempt), ("takes", take), ("assets", asset),
                               ("reviews", review), ("timelines", timeline)):
        bundle[collection].append(record)
    return bundle
