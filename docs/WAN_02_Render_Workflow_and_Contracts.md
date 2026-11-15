# Wan Video Generation · Render workflow and contracts
Version 1.1 | Contract 0.1.0 baseline

## Creator workflow
Create project → import song or script → create scenes and shots → attach reusable references → approve a render batch → review takes → replace selected shots as needed → assemble timeline → mix audio → export MP4. The timeline persists while the GPU is off. Accepted take references are immutable unless an editor explicitly replaces them.

## Shared contract
| Record | Required fields |
|---|---|
| Project / shot | Project and owner IDs, project type and runtime limit, scene and shot IDs, target duration, prompt and reference asset IDs. |
| Render batch | Project ID, batch ID, approved budget envelope and deadline, model profile version, ordered shot IDs, idempotency key and state. |
| Render attempt | Shot and attempt IDs, seed, resolved settings and checkpoint revision, worker and provider references, timestamps, failure reason. |
| Completed take | Attempt ID, durable object key, size and checksum, video duration/resolution/frame rate, preview reference. |
| Timeline / export | Timeline revision, ordered take IDs with trims, audio asset and offsets, export profile, state and completed asset. |

## GPU lifecycle
1. Validate ownership and limits, persist approved batch and reserve its budget. Allow one GPU per batch at first and cap concurrent Pods at the project or account level.
2. Create a Pod through the controller using a unique batch identifier. If creation times out, reconcile the provider inventory before retrying.
3. Load one model and process ready shots. Upload each output and verify its object and checksum before marking the take complete. Return uncompleted work to the queue on interruption, subject to retry and cost limits.
4. Track batch status and cleanup independently. A user can cancel queued work, with the controller draining or ending the current attempt within its deadline. Keep successfully committed takes.
5. Terminate the temporary Pod and verify deletion with the provider. An independent watchdog retries cleanup and alerts on unresolved resources. Reconcile billed compute, storage and transfers against the batch. Keep status visible until cleanup is confirmed.

## Benchmark and decision record
Use the same six shots across runs: a beat-driven music shot, two continuity shots with the same character, a dialogue close-up, a cartoon action shot and a two-character cartoon shot. Pin seeds and settings where supported. Capture cold startup, model loading, warm render time, upload and teardown time, failure causes and approved footage. Compare with a cache only after accounting for persistent storage cost. Compare self-hosted Flex or another rental only if the workload warrants it. No paid render or infrastructure change occurred during planning.

## Repository coordination

Canonical implementation and fixture records are in https://github.com/hoyosgarciajohn-png/wan-video-generation. Read docs/CONTRACT.md, contracts/ and fixtures/ at the B00 baseline. The earlier WAN_B00_Starter.zip remains an archived draft. The complete issue and branch mapping is in docs/WORKSTREAMS.md.
