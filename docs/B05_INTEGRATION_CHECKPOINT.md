# B05 local integration checkpoint — 2026-11-15

Status: local fixture integration PASS; full hosted B05 remains OPEN. Contract 0.1.0.

## Integrated inputs

| PR | Exact reviewed head | Component |
|---|---|---|
| 13 | 5c2442b291c21c87c23288b0439622e6e5ac6783 | SQLite Pod lifecycle and Runpod REST adapter |
| 14 | d031826df3239873305db6035ca8f4f8689b87b1 | CPU timeline/audio export |
| 15 | 946ebb45656fdedfbb3e7b72fdcdd558dd6f36f8 | QA preparation matrix and evidence runner |
| 16 | c47dbe0ebb1e270eaa514dfc0a151bc3a4046ddf | Pinned Wan worker and fixture mode |
| 18 | f07ee6adcadbb3dd635cc1cc5d891845b8c492b2 | React storyboard fixture workspace |

This checkpoint combines those source snapshots and review fixes. It does not certify draft components for production or close their remaining acceptance gates. Original PR evidence remains historical evidence for its stated revision.

## Delivered behavior

ControlService persists fixture projects, frozen batch admission, scoped worker claims, leases, bounded retries, verified completion and take records in SQLite. Trusted host identities are checked against project ownership. Actual worker run_once renders synthetic footage, commits it through that service, and replays completion after controller restart without rerendering. Approved takes become an immutable timeline revision, CPU export mixes synthetic audio, and the completed export survives another restart. No network authentication is claimed by this in-process adapter.

Review fixes prevent export retry from trusting corrupted cached video and prevent Studio saves from overwriting removed or malformed browser storage. Failed storage writes preserve the previous local revision. Regression checks cover both defects.

## Checks actually run

- Python root discovery: 44 passed (foundation, QA preparation, provider/lifecycle, six new service tests, combined render/review/export test).
- GPU worker suite: 17 passed, synthetic CPU mode.
- Media suite: 4 passed; full decode of low-resolution 5-minute music and 30-minute film/cartoon exports, audio alignment, replacement, retry and corruption recovery.
- Contract/schema and fixture-media validation: PASS.
- Studio: production build PASS; 10 model tests and 6 DOM tests PASS; formatting PASS.
- Fresh browser attempt: BLOCKED before application interaction; installed Chromium aborts on socket creation with EPERM. Four browser tests did not execute their app steps. DOM results do not substitute for browser acceptance.

Commands: `python -m unittest discover -s tests -v`, `python -m unittest workers.gpu.tests.test_worker -q`, `python -m unittest workers.media.test_export -v`, `python scripts/validate_contract.py --media-root fixtures`. Studio commands and browser details are recorded in apps/studio/B03_EVIDENCE.md.

## Remaining implementation, in order

1. Resolve issue #17 with a versioned Studio persistence contract: scene/script metadata, selected takes, revision control and upload/preview operations. Connect Studio to authenticated backend transport; local browser state is still its current store.
2. Add hosted persistence/storage and durable export admission, cancellation and publication. The local service uses a shared filesystem and SQLite; it is not a deployed multi-host database or signed-download service.
3. Connect render queue to the separately tested Pod lifecycle; implement approved budget reservation/settlement and independent scheduled cleanup. Paid dispatch is disabled in ControlService. Direct lifecycle adapter availability is not proof of hosted shutdown automation.
4. Build and smoke-test the pinned GPU container in a compatible build environment. Benchmark cold/warm behavior; the current process loads Wan per attempt, so resident-model batching is still an optimization candidate.
5. Run hosted fictional creator journey and isolation/download tests, then B06 real GPU benchmark with John’s explicit project dollar ceiling and runtime envelope.

B04 CPU component is accepted with the cache fix; QA preparation is accepted. B01/B02/B03 remain partial and full B05 stays open. Human creative review remains for the live owner session. No production deployment occurred. GPU spend: $0. GPU resources created by this work: zero. Existing account-wide resources were not inspected.
