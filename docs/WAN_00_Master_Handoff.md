# Wan Video Generation · Master handoff
Version 1.1 | November 15, 2026 | Owner: John Hoyos

## Approved direction
Build a shot-based platform for music videos up to 5 minutes and short films and animated cartoons up to 30 minutes. Self-host open-weight Wan. Rent GPU infrastructure by the batch and avoid per-generation model fees. Baseline: Wan2.2 TI2V-5B, RTX 4090 24 GB, pinned Docker image, temporary Runpod Pod. Keep project state and outputs outside the GPU. Confirm teardown after every batch. Larger Wan checkpoints, custom Runpod Flex, and other GPU rental providers are benchmark alternatives. Repository is https://github.com/hoyosgarciajohn-png/wan-video-generation. Project-specific budget ceiling, hosted storage vendor, and release dates are pending. B00 foundation implementation is underway. GPU benchmarking is scheduled for B06.

## Ownership and source of truth
The Command Center coordinates dependencies, reconciles evidence, and keeps the batch register. John owns spending, scope changes, and production approval. GitHub is the source of truth for code, contracts, issues, PRs, and release evidence. Each chat owns its assigned issues and branch. Chat context does not synchronize automatically. Start each chat with the same handoff and confirmed repository link. Use the companion WAN_01_Workstreams_and_Chat_Prompts.md.

## Batch register
B00 foundation is being published through the repository issue and PR. B01–B04 are next in parallel, with QA preparation. Exact completion evidence and branch assignments are in docs/B00_EVIDENCE.md and docs/WORKSTREAMS.md.

| Batch | Lead | Depends on | Evidence needed to close |
|---|---|---|---|
| B00 Repository and shared contract | Command Center | — | Confirm private repo and access, review AGENTS.md, publish architecture, schemas, fixture and test commands, assign branches and owners. |
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

## First action
Publish the prepared contract 0.1.0, project fixture, media and fake provider at the shared repository baseline. Then start B01–B04 and QA preparation on their assigned branches. The approved plan covers implementation preparation. B06 still needs a project-specific dollar ceiling and runtime envelope before renting the GPU.

## References
- AI Project Development Master Guide v1.0, supplied project guide.
- [Official Wan2.2 inference and checkpoints](https://github.com/Wan-Video/Wan2.2)
- [Runpod Pod operations](https://docs.runpod.io/api-reference/pods/POST/pods)

## Repository coordination

Canonical implementation and fixture records are in https://github.com/hoyosgarciajohn-png/wan-video-generation. Read docs/CONTRACT.md, contracts/ and fixtures/ at the B00 baseline. The earlier WAN_B00_Starter.zip remains an archived draft. The complete issue and branch mapping is in docs/WORKSTREAMS.md.
