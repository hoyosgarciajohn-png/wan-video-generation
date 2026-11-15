# Wan Video Generation · Master handoff
Version 1.6 | November 15, 2026 | Owner: John Hoyos

## Approved direction
Build a shot-based platform for music videos up to 5 minutes and short films and animated cartoons up to 30 minutes. Self-host open-weight Wan. Rent GPU infrastructure by the batch and avoid per-generation model fees. Baseline: Wan2.2 TI2V-5B, RTX 4090 24 GB, pinned Docker image, temporary Runpod Pod. Keep project state and outputs outside the GPU. Confirm teardown after every batch. Larger Wan checkpoints, custom Runpod Flex, and other GPU rental providers are benchmark alternatives. Repository is https://github.com/hoyosgarciajohn-png/wan-video-generation. Project-specific budget ceiling, hosted storage vendor, and release dates are pending. B00 is complete. PR #11 merged with 14 passing local tests and verified synthetic media. GPU benchmarking is scheduled for B06.

## Ownership and source of truth
The Command Center coordinates dependencies, reconciles evidence, and keeps the batch register. John owns spending, scope changes, and production approval. GitHub is the source of truth for code, contracts, issues, PRs, and release evidence. Each chat owns its assigned issues and branch. Chat context does not synchronize automatically. Start each chat with the same handoff and confirmed repository link. Use the companion WAN_01_Workstreams_and_Chat_Prompts.md.

## Batch register
B00 is complete. B01–B04 source snapshots and review fixes are combined in the B05 local fixture checkpoint. B04 CPU export and QA preparation pass; B01/B02/B03 remain partial. Full hosted B05 is open. Exact completion evidence and branch assignments are in docs/B00_EVIDENCE.md and docs/WORKSTREAMS.md.

| Batch | Lead | Depends on | Evidence needed to close |
|---|---|---|---|
| B00 COMPLETE — Repository and shared contract | Command Center | — | Confirm private repo and access, review AGENTS.md, publish architecture, schemas, fixture and test commands, assign branches and owners. |
| B01 Wan worker | GPU | B00 | Versioned Docker build, pinned checkpoint and runtime, fixture input/output smoke test and reproducible benchmark command. |
| B02 Queue and Pod lifecycle | Backend | B00 | Fake provider demonstrates launch, reconcile, cancel, retry, deadline, cleanup and confirmed deletion. |
| B03 Project and storyboard UI | Studio | B00 | Fixture workflow for projects, scenes, shots, reference assets, take review and approvals. |
| B04 Timeline, audio and export | Media | B00 | Synthetic clips and original-track fixture produce a playable export with verified duration and sync. |
| B05 Integrated rehearsal | Command Center and QA | B01–B04 | Staging build runs project → queue → simulated render → review → export. Fault cases and project isolation verified. |
| B06 Runpod benchmark | GPU and QA | B05 and owner-approved spend cap | One on-demand RTX 4090 renders cold and warm samples, partial failure recovery is exercised, uploaded outputs survive deletion, billing and resource closure recorded. |
| B07 Music-video pilot | Studio and Media | B06 | End-to-end export up to 5 minutes with song preserved and selective shot replacement verified. John evaluates creative quality in the live owner session. |
| B08 Short film and cartoon pilot | Studio, Media and GPU | B07 | Verify 30-minute timelines using fixtures and validate representative generated sequences for recurring characters, dialogue, and cartoon action. Record separately whether a complete 30-minute generated project was rendered and reviewed. |
| B09 Release and operations | Command Center and QA | B08 | Verify deployed revision, owner authorization, rollback, storage recovery, billing monitoring, and shutdown alerts. Record any live-user acceptance still pending. |

## Workflow between batches
Publish a versioned contract and common fixture in B00. B01–B04 then proceed in parallel. Each lead opens a PR and sends the handoff below. The Command Center resolves conflicts, records actual test results, integrates the agreed revision in B05, and dispatches the next eligible batch. For a failed check, reopen the owning batch and rerun affected checks. A proposed contract change requires a linked issue naming affected consumers and a migration or compatibility plan.

**Handoff template**  
Batch and status (Ready / In progress / Pass / Fail / Blocked)  
Issue, PR, commit, contract version, staging link if available  
Delivered behavior and changed interfaces  
Commands actually run and results, with evidence links  
Known gaps, cost incurred, and resources still active  
Next eligible batch, recipient, and exact input they need

## Next action
Prepare hosted storage/deployment and Runpod lifecycle/budget integration, including larger durable audio uploads and a buildable pinned Wan runtime. The local authenticated synthetic workflow now covers upload → render → review → timeline → export → protected MP4 download; see docs/MEDIA_COMMANDS_V1.md. Full hosted B05 and native browser acceptance remain open. No deployment or GPU spend has occurred. B06 GPU rental still requires a project dollar ceiling and runtime envelope.

## References
- AI Project Development Master Guide v1.0, supplied project guide.
- [Official Wan2.2 inference and checkpoints](https://github.com/Wan-Video/Wan2.2)
- [Runpod Pod operations](https://docs.runpod.io/api-reference/pods/POST/pods)

## Repository coordination

Canonical implementation and fixture records are in https://github.com/hoyosgarciajohn-png/wan-video-generation. Read docs/CONTRACT.md, contracts/ and fixtures/ at the B00 baseline. The earlier WAN_B00_Starter.zip remains an archived draft. The complete issue and branch mapping is in docs/WORKSTREAMS.md.

## B00 closure

[PR #11](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/11) merged. Baseline commit `c9c364ab3f68cfca24489715ab0cd8419d0d4f60`. Five workstream branches exist from that exact commit. [All batch issues](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues) cover B00–B09. Authentication/deployment vendors and Runpod budget are pending. React/TypeScript studio, Python services, PostgreSQL metadata and S3-compatible storage interfaces are implementation defaults selected during B00 and can be revised before infrastructure provisioning.

## Command Center integration review

Local actual-worker → durable completion → review → timeline/audio export → restart recovery passes with fictional media. Root tests: 44; worker: 17; media: 4; Studio model/DOM: 16, with build passing. Export cache corruption and browser-storage conflict defects fixed. Browser acceptance is blocked by Chromium socket restrictions; container build, real GPU and hosted authentication remain unverified. No production deployment, GPU allocation or spending occurred. Detailed source revisions, acceptance boundaries and next steps are in docs/B05_INTEGRATION_CHECKPOINT.md in the repository.

## Connected Studio checkpoint

Studio now defaults to a server connection with operator-provisioned token login, HttpOnly session, owner-scoped project creation and revision-checked storyboard/script saves. It preserves server render history, protects media downloads and retains a recoverable in-memory draft after authentication expiry. The actual TypeScript client passes a real local Python HTTP roundtrip. Checks: 61 Python, 12 Studio model/client and 10 DOM tests; build/format PASS. This is local development, not a live hosted release. Full B05 remains open, no paid GPU or production deployment. See docs/STUDIO_API_V1.md for precise contract, evidence and next tasks.

Previous publication: [integration PR #19](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/19) merged at `ab02e6ccc780e193a1bde6bdb75b8f126b2b52f1`. PRs #13–#16 and #18 were superseded by that checkpoint; their outstanding batch gates remain open. Continue from current main rather than the original B00 workstream branches.

## Connected render checkpoint

Studio commands now submit saved frozen shots to the durable background fixture runner, poll completed takes, cancel active work and approve/reject takes through authenticated server operations. Exact request retries cannot create duplicate batches/reviews; selection updates atomically with approval. 70 Python tests and the actual TypeScript-client/server/render/download/review scenario pass. Studio: 13 model/client and 13 DOM tests, build and formatting PASS; evidence is in apps/studio/B03_EVIDENCE.md. These are synthetic CPU outputs, not Wan/GPU results. Full hosted B05 remains open. No GPU spend or deployment.

Previous publication: [connected Studio PR #20](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/20) merged at `1d148371c7ca202e71089723ef33334dbc092363`.

## Connected media checkpoint

Protected PNG/JPEG/WebP and WAV/MP3 upload, immutable soundtrack timeline assembly, durable background CPU export and authenticated MP4 download are connected. The actual TypeScript client completed the entire local workflow; the downloaded file contains video/audio and fully decodes. Development upload caps are 1 MiB images and 4 MiB audio; larger original tracks require the next storage increment. 77 Python, 14 Studio model/client and 16 DOM tests pass, plus build/formatting. Tests and limitations are documented in docs/MEDIA_COMMANDS_V1.md and apps/studio/B03_EVIDENCE.md. Synthetic CPU footage only; no actual Wan generation, GPU cost or public deployment.

Previous publication: [render controls PR #21](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/21) merged at `a458c0ed4711c1bd144515ac60cdd6815eace62a`.
