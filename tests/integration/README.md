# B05 QA preparation

Issue [#6](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/6) assigns this work to `work/b05-qa` from B00 commit `c9c364ab3f68cfca24489715ab0cd8419d0d4f60`. Shared contract version is `0.1.0`. The root AGENTS.md, handoff, architecture and workstream assignments govern this directory.

This package prepares reusable fixtures and automated evidence for B05. Full B05 execution needs B01–B04 merged and a deployed staging revision. The [acceptance matrix](MATRIX.md) specifies the remaining runtime checks and the evidence required from their owners. The [recorded results](EVIDENCE.md) identify the tested source revision and commands.

## Run the fictional checks

From the repository root with the development virtual environment activated and FFmpeg installed, run the following command.

```sh
python tests/integration/run_checks.py --output /tmp/wan-b05-evidence.json
```

The runner invokes the root contract validator, the complete root unittest discovery, FFmpeg/ffprobe version checks and `git diff --check`. Its JSON includes commands, exit codes, full output, test count, commit, dirty state, Python source hashes, contract version, tool versions, remaining integration evidence and the cost/resource record for this local run. Failures produce a nonzero exit status. Empty discovery or skipped checks produce BLOCKED and a nonzero exit status. The preparation result and full B05 status have distinct fields. A successful preparation command leaves full B05 BLOCKED.

The standard commands continue to discover every added test through `tests/integration/__init__.py`.

```sh
python scripts/validate_contract.py --media-root fixtures
python -m unittest discover -s tests -v
```

## Fixture reuse

`fixtures.py` derives fresh bundles from `fixtures/project.json` each time. `project_bundle("alpha")` and `project_bundle("beta")` use different fictional owners, record IDs and asset paths. `stage_media(bundle, temporary_directory)` copies the existing two-second synthetic clip and audio into those paths. `replacement_bundle("alpha")` adds another attempt, take, review and timeline revision while retaining the original export's revision. Both takes use identical synthetic video bytes in separate objects. Visual replacement quality requires the creator pilot.

Consumers can import these helpers with `PYTHONPATH=tests` from the repository root. Pass only local fixture data to these test helpers. Their timestamps are deliberately fixed to November 15, 2026. Runtime consumers should inject a clock around that interval when exercising deadlines. Runtime creation should use the normal API and map returned IDs into the scenario. These bundles describe expected record relationships.

The checks reject foreign record links, partial media, escaped paths and expired static leases. They verify historical revisions, duration boundaries and complete decoding of the synthetic sources. Server authorization, transactional retries, controller restart and actual export playback require the normal application entry points specified in the matrix.

## Next handoff

Command Center reviews this preparation PR and integrates it with B01–B04. Backend supplies the API/auth fixture setup, durable controller/queue, injected clock and failure hooks. GPU supplies the fixture worker command and authenticated claim/complete client. Studio supplies the creator flow and staging build identity. Media supplies export invocation, output profile and duration/sync measurements. QA then binds the matrix to those existing entry points and records the exact deployed revision. Reuse completed checks when their code and inputs remain applicable.

B06 needs the owner-approved dollar cap and runtime envelope. Owner creative acceptance remains pending in John's live session. Production authorization and recovery evidence belong to B09.
