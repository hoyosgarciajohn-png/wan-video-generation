# Wan Video Generation · Parallel implementation chats
Version 1.2 | November 15, 2026

Keep this conversation as **WAN Command Center**. Open four implementation chats in the same project for B01–B04 and a fifth QA chat for independent acceptance work. Give each chat the master handoff, confirmed repository link below, and the prompt below. QA can draft its fixtures and matrix from day one. The Command Center owns integration and dispatch.

## Shared opening instructions
Read WAN_00_Master_Handoff.md, the project guide and repository AGENTS.md. Verify repository and baseline commit. Work on an assigned branch and issue. Use the versioned shared contract and fictional test data. Surface interface changes before adopting them. Record evidence using the master handoff template. Paid rendering requires the approved project cap. Production deployment requires owner approval.

## 1 · WAN GPU Worker and Model Benchmarks
> Own B01 and the GPU portion of B06. Package official Wan2.2 TI2V-5B for an RTX 4090 using a pinned Docker environment. Implement the agreed render input/output contract, save per-take metadata, and emit worker heartbeats. Provide a fixture mode and reproducible commands. For B06 compare cold startup, cached startup if feasible, and warm per-shot latency. Report GPU minutes, failure rate, cost per approved second, and peak VRAM. Preserve portability for optional Flex or alternate rentals.

## 2 · WAN Backend, Queue and Runpod Lifecycle
> Own B02. Build persistent batch and shot state, provider abstraction, hard deadlines, launch reconciliation, cancellation, and verified cleanup. Use a fake provider in automated tests. Demonstrate behavior for duplicate requests, ambiguous Pod creation, worker interruption, and failed deletion. Keep secrets server-side. Publish API and state transition changes through the shared contract.

## 3 · WAN Studio and Storyboard
> Own B03 and the creator workflow in B07–B08. Build project setup for music video, film and cartoon, storyboard, recurring reference assets, shot editor, batch approval, and take review. Begin with fixtures. Preserve accepted takes when a shot is regenerated and show render progress and errors. Keep user-facing acceptance separate from fictional automated checks.

## 4 · WAN Timeline, Audio and Export
> Own B04 and export in B07–B08. Define timeline ordering, trims, shot replacement and soundtrack alignment. Preserve the uploaded song. Generate playable video exports through a CPU pipeline. Verify duration, audio sync, resumable failures, and the 5- and 30-minute limits using synthetic media.

## 5 · WAN QA, Integration and Release Evidence
> Prepare the test matrix during B00. Verify B05 and collect evidence for B06–B09. Cover project isolation, repeated submission, controller restart, incomplete uploads, lost workers, teardown confirmation, billing reconciliation, and export playback. Record exact versions and PASS, FAIL or BLOCKED. Do not represent owner creative acceptance or paid GPU results as complete without evidence.

## Repository coordination

Canonical implementation and fixture records are in https://github.com/hoyosgarciajohn-png/wan-video-generation. Read docs/CONTRACT.md, contracts/ and fixtures/ at the B00 baseline. The earlier WAN_B00_Starter.zip remains an archived draft. The complete issue and branch mapping is in docs/WORKSTREAMS.md.

## Start now

Repository https://github.com/hoyosgarciajohn-png/wan-video-generation

Baseline `c9c364ab3f68cfca24489715ab0cd8419d0d4f60` from merged PR #11. B00 is complete.

| Workstream | Issue | Branch |
|---|---|---|
| GPU | [#2](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/2) | `work/b01-gpu` |
| Backend | [#3](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/3) | `work/b02-backend` |
| Studio | [#4](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/4) | `work/b03-studio` |
| Media | [#5](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/5) | `work/b04-media` |
| QA preparation | [#6](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/6) | `work/b05-qa` |

Paste into each existing workstream chat

> Start your assigned issue from the repository and baseline above. Read AGENTS.md and docs/WORKSTREAMS.md, use your assigned branch, implement the issue with fictional automated checks, and return a PR plus evidence to the Command Center. B00 is complete. QA starts with preparation while B01–B04 proceed.
