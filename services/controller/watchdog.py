"""Run one independent cleanup pass against the controller database."""
import argparse
import json
import os
import time
from pathlib import Path

from services.controller.lifecycle import Lifecycle
from services.controller.runpod import RunpodProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("an existing controller database is required")
    token = os.environ.get("RUNPOD_API_KEY")
    if not token:
        parser.error("RUNPOD_API_KEY is required")
    unresolved = Lifecycle(args.database, RunpodProvider(token)).watchdog(int(time.time()))
    print(json.dumps({"unresolved_batches": unresolved}))
    return int(bool(unresolved))


if __name__ == "__main__":
    raise SystemExit(main())
