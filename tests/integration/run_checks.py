"""Run B00/B05 preparation checks and write revision-bound QA evidence.

Usage from the repository root
    python tests/integration/run_checks.py --output /tmp/wan-b05-evidence.json
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def run_check(command, *, is_test_suite=False):
    """Preserve command failures, missing executables, timeouts and skipped tests."""
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"command": command, "started_at": started, "status": "FAIL",
                "returncode": None, "error": str(error)}
    record = {"command": command, "started_at": started,
              "status": "PASS" if result.returncode == 0 else "FAIL",
              "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    if is_test_suite:
        output = result.stdout + result.stderr
        count = re.search(r"Ran (\d+) tests?\b", output)
        record["tests_run"] = int(count.group(1)) if count else 0
        if result.returncode == 0 and (not record["tests_run"] or "skipped=" in output):
            record.update(status="BLOCKED", reason="Empty discovery or skipped checks require review")
    return record


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = {
        "issue": "https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/6",
        "scope": "B05 preparation using fictional data",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "working_tree_changes_before_run": git("status", "--porcelain"),
        "contract_version": json.loads((ROOT / "fixtures/project.json").read_text())["contract_version"],
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "jsonschema": importlib.metadata.version("jsonschema")},
        "commands": [],
        "b05_integration_status": "BLOCKED",
        "remaining_evidence": [
            "Merged B01–B04 and exact deployed staging revision",
            "Authenticated creator journey through simulated render, review, timeline and playable export",
            "Runtime project isolation, concurrency, crash recovery, stale leases and cleanup watchdog",
            "B06 approved spend/runtime envelope, GPU benchmark and provider billing/deletion evidence",
            "Live-owner creative acceptance and B07–B09 release/recovery evidence",
        ],
        "resources_for_this_run": {"gpu_resources_created": 0, "gpu_resources_active": 0,
                                   "provider_requests": 0, "incurred_cents": 0, "currency": "USD"},
    }
    report["source_hashes"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(ROOT.rglob("*.py"))
        if ".venv" not in path.parts and ".git" not in path.parts
    }
    for command, is_test_suite in (
        ([sys.executable, "scripts/validate_contract.py", "--media-root", "fixtures"], False),
        ([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], True),
        (["ffmpeg", "-version"], False),
        (["ffprobe", "-version"], False),
        (["git", "diff", "--check"], False),
    ):
        report["commands"].append(run_check(command, is_test_suite=is_test_suite))
    statuses = {record["status"] for record in report["commands"]}
    report["preparation_status"] = "PASS"
    if "BLOCKED" in statuses:
        report["preparation_status"] = "BLOCKED"
    if "FAIL" in statuses:
        report["preparation_status"] = "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Preparation {report['preparation_status']}. Full B05 BLOCKED. Evidence {args.output}")
    return 0 if report["preparation_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

