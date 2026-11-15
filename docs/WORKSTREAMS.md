# Workstream assignments

The Command Center integrates the common baseline and owns `contracts/`, `docs/`, root setup and release records. Each workstream opens its own PR. Resolve shared contract changes with the affected leads before merging.

| Chat | Branch | Owned paths | Batch |
|---|---|---|---|
| GPU Worker and Model Benchmarks | work/b01-gpu | workers/gpu/ and its tests | B01 |
| Backend, Queue and Runpod Lifecycle | work/b02-backend | services/api/, services/controller/, provider adapters and their tests | B02 |
| Studio and Storyboard | work/b03-studio | apps/studio/ and its tests | B03 |
| Timeline, Audio and Export | work/b04-media | workers/media/ and its tests | B04 |
| QA, Integration and Release Evidence | work/b05-qa | tests/integration/, QA evidence | Preparation for B05 |

Branches start from the merged B00 foundation. First read your GitHub issue and the root AGENTS.md. Contracts and fixtures are the shared development input. The current fake provider intentionally allows duplicate allocation on blind retry, so the B02 controller must reconcile ambiguous creates.

All prior owner authorizations carry forward. Preparation and fictional development can proceed. The Runpod benchmark dollar ceiling and maximum runtime are still to be specified. Human-input checks happen in the owner's live session.

Each handoff includes issue/PR links, commit, contract version, actual checks, remaining issues, costs and active resources. A workstream is ready when its issue has the inputs needed to begin. Record in progress only after the chat or engineer actually starts. Chat dispatch is through these shared records and user messages.

## Issue register

- [B00 Foundation](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/1)
- [B01 GPU](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/2)
- [B02 Backend](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/3)
- [B03 Studio](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/4)
- [B04 Media](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/5)
- [B05 QA and integration](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/6)
- [B06 Benchmark](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/7)
- [B07 Music video](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/8)
- [B08 Film and cartoon](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/9)
- [B09 Release](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/10)
