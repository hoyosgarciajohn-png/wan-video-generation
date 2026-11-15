# B05 preparation evidence

Recorded November 15, 2026. Issue [#6](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/6). Branch `work/b05-qa`. Contract `0.1.0`.

Preparation status is **PASS**. Full B05 integrated rehearsal is **BLOCKED** pending B01–B04 integration and staging. Live-owner creative acceptance is pending.

## Revision and execution provenance

B00 baseline is `c9c364ab3f68cfca24489715ab0cd8419d0d4f60`. The tested implementation is published as commit `570a0aa335ae604250e9628974c36f77e5b46a40`.

Checks ran on the working tree derived from B00 before publication. The [machine-readable report](evidence/preparation.json) retains the actual baseline HEAD and dirty state observed at execution. Every recorded Python source hash was subsequently compared with its blob in `570a0aa335ae604250e9628974c36f77e5b46a40` and matched. Schema and synthetic media retain the verified B00 blobs. README.md and MATRIX.md were added after that run. This evidence file and report are published in a following documentation commit.

The private repository was read and published through the connected GitHub API because local Git HTTPS authentication was unavailable. All 20 baseline blobs, the complete tree and original commit object were verified against GitHub SHA values before work began. The published implementation tree matched the locally staged tree. The assigned branch was updated with an expected-head check.

Latest inspected main was `bdcc8e0a4beb8f534f63acda3d05c0a5ca61f467`. Its changes since B00 were four handoff/evidence documents. B01–B04 remained open prerequisites at this checkpoint.

## Commands actually executed

Working directory was the repository root except virtual-environment creation and installation, which were invoked from its parent with the repository path.

| Command | Result |
|---|---|
| `python3 -m venv wan-video-generation/.venv` | PASS |
| `wan-video-generation/.venv/bin/python -m pip install -r wan-video-generation/requirements-dev.txt` | PASS, jsonschema 4.26.0 installed |
| `.venv/bin/python tests/integration/run_checks.py --output /tmp/wan-b05-preflight.json` | PASS, report archived as `evidence/preparation.json` with publication verification appended |
| `.venv/bin/python scripts/validate_contract.py --media-root fixtures` via runner | PASS, canonical contract relationships, hashes and ffprobe media metadata |
| `.venv/bin/python -m unittest discover -s tests -v` via runner | PASS, 28 tests, zero failures/errors/skips. Fourteen existing B00 tests plus fourteen new QA tests |
| `ffmpeg -version` and `ffprobe -version` via runner | PASS, 7.1.5-0+deb13u1 |
| `git diff --check` via runner | PASS |
| `.venv/bin/python -m compileall -q tests/integration` | PASS |
| `git diff --cached --check` after staging all preparation files | PASS |

Python was 3.12.14. Complete per-test output, tool versions and exit codes are in the JSON report. FFmpeg fully decoded the two-second source clip and audio during the tests. The 5- and 30-minute checks validated timeline records and caps. Export generation, long-output playback and A/V sync measurements remain R01/R13 in the matrix.

## Delivered behavior and interfaces

Two independent fictional projects and a selective-replacement bundle are reusable across workstreams. Tests exercise record boundaries, partial uploads, filesystem escape, expired static leases, historical takes/timelines and runtime caps against the existing validator. The evidence runner preserves command errors, missing executables, timeouts, empty discovery and skipped-test outcomes. The acceptance matrix specifies fifteen application-level rehearsal scenarios plus B06–B09 evidence requirements. Shared contract version remains `0.1.0`.

## Cost, resources and next recipient

This preparation incurred **$0** in GPU or paid infrastructure charges. It created **zero GPU resources** and left **zero GPU resources active from this work**. Fixtures used local temporary files and the existing process-local fake provider. Provider API requests during the fictional checks were zero.

Command Center is the next recipient. Review this preparation PR, integrate the B01–B04 PRs, and provide the exact staging build identity and component entry points listed in README.md. QA then executes R01–R15, records observed results and revises B05 status. Issue #6 remains open for that integrated rehearsal. Real GPU benchmark, provider billing, deployed recovery and live-owner acceptance retain their scheduled batch dependencies.

