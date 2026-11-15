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

## Remaining implementation at this historical checkpoint

1. Resolve issue #17 with a versioned Studio persistence contract: scene/script metadata, selected takes, revision control and upload/preview operations. Connect Studio to authenticated backend transport; local browser state is still its current store.
2. Add hosted persistence/storage and durable export admission, cancellation and publication. The local service uses a shared filesystem and SQLite; it is not a deployed multi-host database or signed-download service.
3. Connect render queue to the separately tested Pod lifecycle; implement approved budget reservation/settlement and independent scheduled cleanup. Paid dispatch is disabled in ControlService. Direct lifecycle adapter availability is not proof of hosted shutdown automation.
4. Build and smoke-test the pinned GPU container in a compatible build environment. Benchmark cold/warm behavior; the current process loads Wan per attempt, so resident-model batching is still an optimization candidate.
5. Run hosted fictional creator journey and isolation/download tests, then B06 real GPU benchmark with John’s explicit project dollar ceiling and runtime envelope.

B04 CPU component is accepted with the cache fix; QA preparation is accepted. B01/B02/B03 remain partial and full B05 stays open. Human creative review remains for the live owner session. No production deployment occurred. GPU spend: $0. GPU resources created by this work: zero. Existing account-wide resources were not inspected.

## Subsequent local integration

The connected Studio, fixture render and media command increments supersede the
local transport gaps above. See STUDIO_API_V1.md, RENDER_COMMANDS_V1.md and
MEDIA_COMMANDS_V1.md. The larger-upload increment adds restartable local upload
sessions with 1 MiB chunks and WAV/MP3 support up to 128 MiB (UPLOADS_V1.md).

Next work is hosted storage/identity readiness, quotas and restore evidence,
provider lifecycle/budget integration, and a buildable pinned Wan runtime.
Docker, Podman and buildctl are absent in the current environment; no container
build is claimed. Native browser acceptance and full hosted B05 remain open.
No deployment or GPU spend occurred.

## Recovery and staging source readiness

Local backup/restore now verifies SQLite snapshots and immutable committed media,
fences interrupted render attempts, aborts incomplete uploads, and preserves
queued exports for recovery. An independent rehearsal restores actual synthetic
takes and completed output, resumes a pending worker/export, and fully decodes
recovered MP4 files. The 93-test Python root suite passes, including corruption,
traversal, overwrite refusal and source-snapshot consistency checks.

The staging package serves built Studio and authenticated API on one loopback
origin, keeps secrets/state outside the build context, and supplies health and
shutdown handling. Eight staging tests pass, including recovered-project HTTP access and shutdown.
Source packaging is checked; no container build or deployment
has occurred because Docker/Podman/buildctl are unavailable. See BACKUP_RESTORE.md
and DEPLOYMENT_READINESS.md. Full hosted B05 and native browser acceptance remain
open, and no provider requests or GPU spending occurred.

## Simulated budget/lifecycle follow-up

The 103-test Python root suite passes with the simulation-only budget coordinator.
Reservations and queue admission are atomic; queued dispatch rechecks current
approval and observed liability, unknown creation remains reserved, and confirmed
resource deletion does not settle billing. Late charges and overruns survive
restart and backup/restore; unresolved liabilities prevent backup. Only the
built-in fake provider is permitted. This does not enable real Runpod dispatch.

Sixteen combined staging/build-verifier tests and artifact source checks pass.
Manual image verification prepares distinct UNVERIFIED gates and executes nothing
by default. No CI, container builds, CUDA inference or deployment were activated.
Host build/smoke, explicit real spend/runtime approval, securely provisioned provider
credentials, and the remote worker/storage bridge remain required before B06.

## Separate-process fixture worker checkpoint

The authenticated worker bridge now streams scoped inputs and MP4 artifacts between
separate controller and worker filesystem roots. Trusted operators issue credentials
bound to one owner/project/batch/worker with expiry and revocation; no public Studio
credential-issuance route exists. The transport accepts only zero-cost fixture batches.
Lost claim/upload/completion responses can be reconciled with durable worker journals
and immutable receipts while the same credential remains valid. Backup snapshots
revoke worker credentials without changing the live source.

Independent actual TCP tests run a staging controller subprocess and a worker CLI
subprocess, verify separately stored checksummed media, fully decode the result and
prove replay creates one take. Scope, lease, corruption, expiry and restored-token
checks pass. Review also fixed expiry during media probing: authorization is checked
inside the database transaction and again before commit, so no expired completion
can publish a take. MP4 probing forces the MOV demuxer with file/pipe protocols.

Validation: 111 Python root tests, 24 worker tests and 16 staging/build-verifier
tests pass; contract and artifact/runtime-source checks pass. See
docs/WORKER_TRANSPORT.md and workers/gpu/README.md. These are local synthetic
checks, not CUDA inference or live Runpod evidence. Container image builds, hosted
B05/native-browser acceptance and creative Wan acceptance remain unverified.

Next: build/smoke the pinned images on a compatible Docker host, obtain the explicit
project GPU ceiling/runtime envelope and securely provision Runpod credentials,
then connect the verified transport to real Wan execution and approved lifecycle
dispatch. The remote fixture bridge is implemented; production TLS, storage quotas,
orphan retention and hosting remain open. No cloud deployment, GPU allocation or
spending occurred.

## First real-run readiness checkpoint

A fresh host audit found no container daemon/tools, NVIDIA device/runtime or
installed Wan/PyTorch stack. Standard daemon sockets are absent and a local Unix
socket bind is denied. No compatible compute-host connection was available.
Static inspection found no evidenced Docker pin/import defect to change; image
build and CUDA gates remain UNVERIFIED. See deployment/FIRST_WAN_RUN.md.

The next owner decisions are concrete: identify an existing approved Linux amd64
Docker build host (or choose a host provisioned separately), specify the first
project's dollar ceiling, maximum elapsed runtime and retry allowance, and choose
the HTTPS controller/persistent storage location. Runpod credentials must then be
provided through protected secret handling, never pasted into the handoff.

Those inputs do not finish the software. WorkerTransport still admits only
zero-cost fixture batches and the coordinator still accepts only the fake provider.
Real Wan admission must connect server-side budget reservation, model/image policy,
scoped credentials, provider reconciliation and independent cleanup. Supplying a
GPU URL or deleting the fixture guard is not an acceptable substitute.

Further local fixture code cannot demonstrate actual Wan image compatibility,
creative quality, VRAM demand or billed cost. The next meaningful acceptance step
requires the host/owner prerequisites, remaining real-admission implementation and
an observed capped one-shot benchmark. No GPU, cloud deployment or spending was
started during this readiness review. Full hosted B05 and B06 remain open.

The offline preflight now binds non-secret run intent to current source/model
hashes and checks supplied build logs, image identity and fixture bytes for local
consistency. Missing or fabricated PASS-only evidence remains invalid. Owner
attestation files are consistency inputs, not authenticated spending authority.
Saved reports are write-once and detect changed bytes or source; neither their
hashes nor the report can authorize execution. Both readiness and execution flags
remain false, including when every supplied input is internally consistent.

Validation for this checkpoint: 121 Python root tests pass, including ten new
preflight/review cases; eight build-verifier tests and the shared contract pass.
The checked-in docs/REAL_RUN_PREFLIGHT.json was generated with empty owner inputs
and verifies against current source. All nine gates remain missing or blocked.
See docs/REAL_RUN_PREFLIGHT.md for evidence limits and exact plan fields.

## Disarmed canonical Wan-profile bridge checkpoint

The queue-to-worker connection now has executable source: one transaction freezes
the pinned model/shot profile, reserves fictional budget and links a canonical
runpod-shaped batch to lifecycle state and durable test authority. Scoped verified
completion commits its take and lifecycle terminal outcome together; independent
cleanup and final billing remain separate. Restart and checked restore preserve
settled history, while restored worker credentials remain revoked.

The normal RealJobBridge constructor is disarmed. Its only enabled factory is
for_testing with the exact built-in fake provider. Default public admission and
worker transport remain fixture-only. Neither a preflight report, caller boolean
nor simulated approval grants live authority. A trusted test server must explicitly
install the bridge, and durable links identify every rehearsal as synthetic.

Independent tests generated and fully decoded a real H.264 file with 25 frames at
1280x704/24fps under the pinned profile's requested contract. Verified completion,
replay, cleanup, fictional settlement, restart and recovered history pass. These
pixels came from FFmpeg, not Wan. Deadline/cancellation fences pass; revocation
blocks future admission/dispatch but does not implicitly cancel an already
provisioned reservation. The existing documented cancellation policy is preserved.

The worker now decodes and validates image references before expensive model
startup. CPU-mocked adapter tests check invocation/profile arguments; they do not
import real Wan, load weights or execute CUDA. See docs/REAL_JOB_BRIDGE.md and
workers/gpu/README.md for exact boundaries.

Remaining for live execution: authenticated owner approval with a specific dollar
ceiling/runtime envelope, a separately reviewed live provider/configuration factory,
actual built-image/host/storage evidence, authoritative billing and observed cleanup,
and a supervised capped GPU benchmark. John has not supplied real spending terms.
No cloud resources, deployment, CI, model download or GPU spending occurred.

Validation: 130 Python root tests and 29 worker tests pass; contract and static/runtime-source artifact checks pass. The empty-input preflight was regenerated against the final source and remains non-executable with all nine gates missing or blocked.

## Runpod v2 adapter and deployment preparation checkpoint

The provider adapter now uses Runpod v2 request/response shapes, explicit scoped
resource identity and complete paginated inventory. It requires an explicitly
supplied transport; constructing it does not enable network access. Launch-profile
validation requires an immutable image reference and constrained GPU/storage/port
configuration. This validates request shape, not actual availability or permission.

Independent mocked-HTTP lifecycle tests preserve liability after ambiguous creation
and transient inventory/deletion failures. Reconciliation never repeats the POST.
Cleanup requires checked resource absence and a complete inventory; after restart,
a persisted resource ID also requires trusted expected-name binding. Wrong or
unbound identities cannot be deleted. No provider response bodies or environment
values are returned to lifecycle callers.

See deployment/RUNPOD_DEPLOYMENT.md and its configuration worksheet. Owner budget,
runtime, host, image and storage fields remain empty. The worksheet cannot authorize
a launch. The provider adapter is not automatically connected to production
dispatch: authenticated live admission/approval and a reviewed provider factory
remain outstanding, along with actual image builds, host/TLS/storage acceptance
and the capped real Wan benchmark. Independent cleanup must operate outside the
GPU; worker exit does not prove termination and retained volumes may keep billing.

No real provider call, cloud resource, CI run, deployment, model download or GPU
spending occurred. Previous worker evidence remains 29 passing tests; worker source
was unchanged in this batch. Full hosted B05 and actual Wan compatibility remain
unverified.

Validation: 140 Python root tests pass, including ten focused adapter tests and three independent mocked-HTTP lifecycle tests. Shared contract and static/runtime-source artifact checks pass. The regenerated preflight verifies current source and remains PLAN_ONLY with execution disabled.

## Signed admission source checkpoint — execution disabled

An optional trusted LiveAdmission service now combines the authenticated Studio
session owner with a domain-separated HMAC grant under a server-installed key
bound to that owner. It verifies exact project/configuration/source, cap, runtime
and expiry; caller JSON cannot choose the identity or trust key. Grant envelopes
are immutable, revocation is sticky, and simulation records remain separate.
No key, actual approval or spending limit was created for John. HMAC proves the
installed key holder's delegated authority, not John's personal review.

Admission atomically saves canonical queued job, frozen shot, live reservation,
lifecycle row and authority link. Outstanding reservations across grants count
against the project cap. Only provably never-dispatched jobs can cancel/release.
The provider preparation gate checks separately signed host acceptance and build
evidence, then still refuses to return a provider because live worker dispatch
is not installed. There is no enable flag or public signing endpoint.

Independent local TCP tests prove session/grant ownership, tamper rejection and
replay/cancellation. Backup preserves only safe released history, rejects dispatch
evidence and revokes copied approvals. The old signed grant cannot reactivate
restored authority; source authority remains unchanged. Signing keys remain outside
database and backup. Simulation cleanup is scoped to its own reservations so
pending live admission cannot obstruct it.

The standard CPU staging package does not install this optional admission service
or contain the reviewed Git/source checkout it needs. Isolated source imports
now include backup and live admission; they pass without claiming an image build.
See docs/LIVE_ADMISSION.md and deployment/LIVE_APPROVAL_OPERATIONS.md.

Next remains real operator trust provisioning and owner cap/runtime, verified
image/build-host/HTTPS/storage evidence, live worker/provider launch authority,
independent cleanup and actual usage/final-bill settlement. Queued admission alone
cannot run Wan or spend. No real provider calls, deployment, keys for John, GPU
activity or spending occurred. Full hosted B05 and actual Wan acceptance stay open.

Validation: 151 Python root tests pass, including eight focused admission cases and three independent TCP/recovery cases. Shared contract and expanded static/runtime-source artifact checks pass. The regenerated preflight verifies final source hashes and keeps all nine gates missing or blocked. Prior worker evidence is unchanged-source; no CUDA or provider execution was performed.
