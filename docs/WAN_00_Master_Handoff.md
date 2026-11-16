# Wan Video Generation · Master handoff
Version 1.34 | November 16, 2026 | Owner: John Hoyos

## Approved direction
Build a shot-based platform for music videos up to 5 minutes and short films and animated cartoons up to 30 minutes. Self-host open-weight Wan. Rent GPU infrastructure by the batch and avoid per-generation model fees. Baseline: Wan2.2 TI2V-5B, RTX 4090 24 GB, pinned Docker image, temporary Runpod Pod. Keep project state and outputs outside the GPU. Confirm teardown after every batch. Larger Wan checkpoints, custom Runpod Flex, and other GPU rental providers are benchmark alternatives. Repository is https://github.com/hoyosgarciajohn-png/wan-video-generation. The first-trial $5 / 30-minute / one-attempt envelope was consumed; its render failed and cleanup was confirmed. Hosting is installed; release dates remain pending. B00 is complete. PR #11 merged with 14 passing local tests and verified synthetic media. GPU benchmarking is scheduled for B06.

## Current Command Center checkpoint
The controller is live at https://wan-64-225-114-46.sslip.io. Owner sign-in after the
latest restart is verified. Saved synthetic and real-trial history remain available.
Installed source: `8e07ba3e8dfb9a250424bb4c8607cd1cac36cfe6` (PR #68), upgrade run
43811745342. Controller, independent persistent cleanup and Caddy remain enabled.
Public Studio paid dispatch is disabled; its buttons still create synthetic fixtures.
Private operator reception supports explicitly scoped live workers.

One DigitalOcean controller remains active: wan-controller-01, Droplet 619703894,
SFO2, 64.225.114.46, Ubuntu 24.04.5 LTS amd64, 1 vCPU / 2 GiB / 50 GiB. Approved
recurring cost is $14.40/month before tax ($12 host plus $2.40 weekly backups).
Weekly backups are enabled for Wednesday 04:00–08:00 UTC. The first completed
snapshot, recurring offsite application backup and accrued hosting bill remain
unverified. No additional host, persistent volume, paid add-on or domain was bought.

Hosted synthetic acceptance and recovery remain valid: authenticated project/upload,
fixture render, review, timeline/export, checksum/full decode, restart persistence,
cleanup while the web service was stopped, same-host restore and independent runner
restore 43800008304. These do not establish successful Wan output or human acceptance.

**Both approved GPU attempts are now consumed. No third render is authorized.**
The original five-second batch `7c811e6ab21a4392b0e3a80e331fc57a` failed without a take;
its exact cause remains unknown. Pod `xhd7cd3nqsrcca` was automatically deleted at its
04:28:34 UTC deadline; independent absence was confirmed at 04:28:37.627 UTC. Its
latest imported provider observation was $0.1475849028211087, conservatively booked
as 15 cents, with 385 cents still reserved. This is not final settlement.

John approved a separate additional one-second diagnostic: one create and one render,
$5 total ($4 Pod reservation plus $1 storage allowance), 1,800 seconds from admission.
Project `project-894af8d869d6448290d34a762a736781`; batch
`def5478dc85949139ca1c0ae404f9d1f`; sole Pod `hzprkb5xllm8p0`. Admission was
05:42:07 UTC on November 16, with fixed deadline 06:12:07 UTC. The isolated grant,
operator directory and signing keys preserved the first trial and its liabilities.

The new Pod was SECURE RTX 4090 in EU-RO-1 at $0.89/hour, with 80 GB ephemeral disk,
24,564 MiB GPU memory and approximately 83 GB host RAM. It pulled the private image
`sha256:f724b9f32ac4ac780702072fd32e9d08254524ca81afd6aadeb87169904f993b`
at 05:49:09 UTC. All pinned model files passed checksums at 05:51:38.396 UTC. The
worker claimed one actual Wan shot: 1280x704, 24 fps, 25 frames, 50 steps, seed 42.
CPU preparation took roughly ten minutes before GPU sampling. At 06:02:40.994 UTC,
39/50 sampling steps were captured with 14,860 MiB GPU use and 100% utilization.

**Diagnostic result: GPU out of memory; zero video takes.** The container reported
`gpu_out_of_memory` at 06:03:10.958 UTC, and the controller recorded failure at
06:03:11.408 UTC. Automatic cleanup was confirmed at 06:03:19.988 UTC, about nine
seconds after failure and nearly nine minutes before the deadline. Runpod inventory
was empty and exact-Pod GET returned 404. No manual DELETE or extra create/render
was used. Launch 43812096376 succeeded as an orchestration/cleanup job, not a render.
The exact failing allocation and whether all sampling steps finished were not captured.

Billing observation import 43814346326 completed at 06:04:59 UTC: zero provider records,
`RETRIEVED_NOT_FINAL`, with the full $4 diagnostic reservation retained. This is
reporting lag, not free usage. Estimated GPU-only allocation was about $0.29 plus
disk; the final bill remains pending. Automatic application-side bill retrieval is
still unimplemented. Independent guard 43811980342 completed successfully. It retained
the earlier allocation identity and confirmed absence repeatedly from 06:12:17.762
through 06:17:00.647 UTC, completing the original deadline plus five-minute watch.
This corroborates the primary cleanup that removed the Pod at 06:03:20 UTC.

A memory-repair candidate is prepared in draft PR #69:
https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/69
Head `1722e8cd9929a2b5c5784408dbf5644aa1264bbc`. It initializes DiT on CPU, encodes
text on GPU with sequential offload, uses BF16 VAE parameters/autocast, and preserves
fixed text/decode failure phases without private diagnostic text. Ten targeted
fictional CPU checks passed. The pinned upstream source supports the proposed
execution order. High decoder memory is a hypothesis, not the proved failing stage.
This candidate is NOT built, published, installed or GPU-validated. Output quality,
actual memory fit and CUDA compatibility remain pending. Do not reuse the old image's
source-bound attestation for changed worker code.

Evidence is under `deployment/evidence/2026-11-16-diagnostic-trial/`. Human creative
acceptance, a successful real Wan clip, five-second acceptance, warm-batch benchmarks
and B06 closure remain pending. No model-use/API fee was introduced.

Historical entries below are chronological; this checkpoint supersedes them.

## Ownership and source of truth
The Command Center coordinates dependencies, reconciles evidence, and keeps the batch register. John owns spending, scope changes, and production approval. GitHub is the source of truth for code, contracts, issues, PRs, and release evidence. Each chat owns its assigned issues and branch. Chat context does not synchronize automatically. Start each chat with the same handoff and confirmed repository link. Use the companion WAN_01_Workstreams_and_Chat_Prompts.md.

## Batch register
B00 is complete. B01–B04 source snapshots and review fixes are combined in the B05 local fixture checkpoint. B04 CPU export and QA preparation pass; B01/B02/B03 remain partial. The B05 hosted synthetic workflow, restart and independent recovery are verified; human creative acceptance is pending. B06 remains open after two failed live attempts; the diagnostic confirmed GPU OOM. Exact completion evidence and branch assignments are in docs/B00_EVIDENCE.md and docs/WORKSTREAMS.md.

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
Continue free review and build preparation for draft PR #69. Build a new immutable
private worker image and verify its source/runtime evidence before proposing another
paid trial. Do not deploy the candidate or claim the OOM is fixed based on CPU mocks.

Any subsequent GPU validation requires a fresh, concrete owner-approved scope and
new isolated job/grant. Both existing attempts are consumed; preserve their terminal
states, fixed deadlines and unsettled billing. A proposed one-second validation may
use the same $5 / 1,800-second / one-attempt limits, but no such third attempt is
approved. Do not reset or rerun either historical prepare/admit/launch flow.

Other pending operations: final provider bill reconciliation, automatic billing
collection, the first completed weekly backup, recurring offsite application backup
and restore of the new post-trial snapshot. Existing synthetic recovery evidence
remains valid. General paid Studio rendering and creative acceptance are not complete.

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

## Larger soundtrack upload checkpoint

Connected Studio now uploads WAV/MP3 originals up to 128 MiB using 1 MiB chunks,
with owner-scoped durable sessions, verified chunk manifests, progress and safe
same-tab retry after network loss or reauthentication. Server sessions survive
process restart; closing/reloading the browser loses the in-memory File/session,
and the current UI starts a new upload after reselection. Images remain capped
at 1 MiB. Completed/aborted/expired staging is reconciled after crashes.

Validation: 85 Python tests PASS; 16 Studio model/client and 17 DOM tests PASS;
build, formatting, contract/media validation and whitespace PASS. The actual
TypeScript client uploaded a 5.04 MiB, 55-second synthetic WAV, recovered from a
lost committed-chunk response, and completed render/review/timeline/export with
a protected fully decoded MP4. These are synthetic CPU results, not Wan output.
See docs/UPLOADS_V1.md and apps/studio/B03_EVIDENCE.md.

Next: hosted storage/identity readiness, durable storage quotas and backup/restore,
Pod lifecycle and budget integration, and a buildable pinned Wan runtime. Docker,
Podman and buildctl are absent here; no container build was performed. Full hosted
B05, native browser and creative acceptance remain open. No deployment or GPU spend.

Previous publication: [media controls PR #22](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/22) merged at `57e7cb9e226565cc5b67bbb1be2661544615fff5`.

## Recovery and staging preparation checkpoint

A checked local backup now captures a consistent SQLite snapshot and every
referenced immutable media object, with manifest checksums and completion markers.
Restore refuses nonempty destinations, traversal and linked files. Recovery
preserves accepted takes, reviews, timeline revisions and completed exports;
incomplete uploads abort, interrupted attempts are fenced, and queued exports
resume from frozen inputs. The source installation is unchanged.

The 93-test Python root suite passes, including an independent recovery of an
actual synthetic project, resumed worker/export processing, full MP4 decoding,
corruption/path checks and refusal to overwrite an existing restore. Deployment
source adds a loopback-only staging host, external secret/state preparation, health
checks and shutdown handling. Runtime packaging now includes the shared validator;
restored database paths can be selected explicitly rather than opening empty state.
Eight staging tests also pass, including recovered-project HTTP access and SIGTERM.
Static artifact/runtime source imports, Compose YAML parsing and six target wheel
hashes are verified; this does not establish a container build.
See docs/BACKUP_RESTORE.md and docs/DEPLOYMENT_READINESS.md.

Next: build and smoke-test the CPU staging image on a compatible Docker host,
complete native browser acceptance, decide hosted identity/storage and implement
storage quotas/offsite retention, then finish lifecycle/budget wiring and the
pinned Wan runtime. Container images have not been built here; Docker/Podman/
buildctl are absent. Full hosted B05 and real Wan/GPU generation remain unverified.
No deployment, provider requests or GPU spending occurred.

Previous publication: [larger soundtrack uploads PR #23](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/23) merged at `cbd300fe74fc8a2f47e8b1c69cfe1273414e2467`.

## Simulated budget/lifecycle and build-verification checkpoint

The coordinator now atomically reserves fictional approved cents with a frozen
lifecycle job. It rechecks approval and budget at dispatch, retains unknown-create
liability, and keeps cleanup separate from final billing. Actual-shaped late charges
and overruns remain recorded without resetting history under a new approval.
Backup preserves settled simulation history and refuses every unsettled liability,
including deleted-but-unbilled resources. Only the built-in fake provider is accepted;
no HTTP spending route or real Runpod dispatch is enabled.

The Python root suite passes 103 tests, including concurrent reservation/replay,
queued dispatch blocking after overrun, restart/unknown creation, deletion before
settlement, late corrections and restored ledger history. All amounts in these
tests are fictional, and fixture generation still records zero real cost.
See docs/BUDGET_ORCHESTRATION.md. Sixteen combined staging/build-verifier tests
also pass; artifact/runtime-source import checks include the simulation coordinator.

Manual build-verification tooling prepares a source/hash inventory and separate
image-build, import, fixture, weight and GPU gates. Plan-only mode executes no
builds. Runtime checks bind to the captured image ID and reject changed prepared
source; see deployment/BUILD_VERIFICATION.md. No CI is triggered; image builds, CUDA inference and hosted deployment
remain explicitly UNVERIFIED. A compatible local Docker host is still required.

Next real gates: host image build/smoke, John's project-specific GPU ceiling and
runtime envelope, securely provisioned Runpod credentials, and an authenticated
remote worker/storage bridge. Native browser/hosted B05 and real Wan creative
acceptance remain open. No live provider allocation, GPU spending or deployment.

Previous publication: [backup/staging PR #24](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/24) merged at `61be611f0df205436dcbad77fe629ebf7d84b9b4`.

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

Previous publication: [budget/build gates PR #25](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/25) merged at `a3ceceeb1e7e38329fdbaf58ea6e601f4a1105ae`.

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

Previous publication: [remote bridge PR #26](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/26) merged at `8ee3150938d7b569b48b354b5f109f827b7b0052`.

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

Previous publication: [real-run preflight PR #27](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/27) merged at `df0be05f79e730b585c4695ed32a2ebbfe005f33`.

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

Previous publication: [canonical job bridge PR #28](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/28) merged at `9c6f6d5e7164139126adeb1dd5d8925b398522ee`.

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

Previous publication: [Runpod v2 preparation PR #29](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/29) merged at `851b594ecba321d810153b0bde7a2d542ea202ef`.

## Guarded execution and signed billing checkpoint

Trusted LiveExecution source now connects signed admission to Runpod v2 creation,
scoped remote work, verified take completion, cleanup and a separate live billing
ledger. Dispatch rechecks installed owner/source/build/host/configuration evidence,
current project liabilities and bounded bootstrap credentials inside the durable
queued-to-provisioning transition. The default host has no transport, account key
or actual authority installed. No real owner grant or spending terms were created.

A worker starting during POST waits on authenticated empty claims until durable
resource reconciliation. The bounded startup wait does not extend the deadline.
Unknown creation reconciles without another POST or token rotation. Cleanup uses
frozen identity and remains available after owner-key revocation, expiry or current
model/source changes. Worker tokens and active leases still fence work.

Signed billing receipts bind exact owner/project/batch/resource and record either
incremental charges or final cumulative settlement. Cleanup alone cannot settle.
Late charges survive settlement and block further admission/launch if they exhaust
the cap; newer grants do not reset historical spending. This is delegated receipt
enforcement, not automatic Runpod invoice retrieval or a provider hard stop. It
does not automatically cancel an active job upon a newly observed overrun.

Independent tests generated actual synthetic 25-frame 1280x704 H.264 output, verified
its scoped upload/take/replay, retried failed cleanup, settled fictional charges,
recorded a late overrun and restored fully decoded media with revoked authority.
Tests used fictional signatures, mocked build evidence and mocked HTTP; none
establish actual Wan/GPU compatibility.

See docs/LIVE_EXECUTION.md and deployment/LIVE_BILLING_OPERATIONS.md. Actual owner
cap/runtime, operator trust, build/registry/GPU proof, HTTPS/storage, deployed
independent watchdog and provider billing reconciliation remain operational gates.
No cloud calls, live resources, deployment, keys for John or spending occurred.

Validation: 158 Python root tests passed in 37.387 seconds on the corrected source; 36 worker tests passed. Shared contract and expanded isolated runtime-source imports passed. The final source-bound preflight remains PLAN_ONLY with all nine gates missing or blocked.

Previous publication: [authenticated admission PR #30](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/30) merged at `6238c8c1e0076f87bf55f82ccaa4349055361235`.

## Build/hosting review and first-render proposal

PR #31 merged at `21a5bcab35db6ef047f9190c4185b38415f8882f`; its tested tree is `0af62a393cfa8eb2ea5b3461ac952099de2c7994`. This follow-up is documentation only. The available Linux workspace has no container engine, NVIDIA device or daemon socket and rejects Unix socket binding. No compatible build host or hosted controller/watchdog has been verified. Runpod is waiting for the owner to sign in; account balance, capacity and pre-existing resources are unknown.

See deployment/FIRST_RENDER_PROPOSAL.md and deployment/first-render-proposal.json for the concrete, unapproved $5/30-minute / one-attempt envelope, current public price assumptions, storage retention, ordered host acceptance and billing follow-up. Approval fields remain null. Shared storage is not covered by the existing Pod ledger; $1 is held separately from the proposed $4 Pod grant. No recurring hosting, paid build service, account top-up or automatic retry is included.

The independent watchdog is callable source, not a running service. A local deadline is not a provider hard spending stop. Automatic bill retrieval and final-charge reconciliation remain pending; no bill was retrieved. All image/CUDA/host gates remain unverified. Prior 158 controller and 36 worker fictional checks are preserved without rerunning unchanged behavior. No GPU, build, key provisioning or paid resource was started. Next inputs: John’s specific numeric approval, Runpod sign-in and selection of a compatible existing build host; Command Center then coordinates actual image and hosted acceptance before the supervised first render.

Published: [build/hosting review PR #32](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/32), merged main `9ab0069fa39d09facd4c4bef20a3ab6c650acd88`; documentation tree `8c589663bfd8be065af746f27995abf9e91b01fd`. [First-render proposal](https://github.com/hoyosgarciajohn-png/wan-video-generation/blob/main/deployment/FIRST_RENDER_PROPOSAL.md). Numeric approval remains pending.

## Runpod connection verification — November 15, 2026

John completed the official ChatGPT Runpod connection. Authenticated list-pods (including cluster members), list-endpoints, list-network-volumes and list-global-volumes all succeeded and returned empty inventories with no further pages. Account credit/balance and write permissions were not tested. The earlier sign-in blocker is resolved for the connected tools; the browser's separate sign-in state was not checked.

The aggregate billing query for 2026-11-15 00:00 UTC through 2026-11-16 00:00 UTC returned no records and totalAmount 0. This is an in-progress time-bucket response, not proof of a finalized bill or funded balance. Billing read access is verified. Automated collection, deduplication and signed-receipt ingestion inside the Wan controller remain unimplemented. No real billing receipt was synthesized or settled.

The guide's local Codex plugin setup could not write its read-only configuration directory; the working ChatGPT connector supplies the account tools without that local installation. No extra API key, new resource, paid service, deployment, model download or render was created. Existing code/test evidence and pending host/image/release gates are unchanged. Source baseline remains PR #32 at `9ab0069fa39d09facd4c4bef20a3ab6c650acd88`, contract 0.1.0. Next owner inputs remain the proposed numeric cap/runtime approval and a compatible build-host choice; connecting the account does not approve spending.

## First-trial spending approval — November 15, 2026

John replied “Yes you are approved” directly to the proposal for $5 total / 30 minutes / one attempt. This authorizes the first five-second Wan trial within the recorded terms: $4 Pod reservation, $1 separately tracked storage allowance, one GPU, one worker attempt, no automatic rerender, and trial-storage retention up to 24 hours. No recurring service, extra builder purchase or account top-up is included. Do not ask for these same spending/runtime limits again.

The Runpod GPU catalog returned `availability: NONE` for one RTX 4090 in Secure Cloud, Pod product, minimum CUDA 12.8. Its listed Secure rate was $0.89/hour. This is current availability evidence, not a reservation or render benchmark. Host/image/registry/controller/watchdog evidence remains absent. The approved decision record keeps execution disabled and verified infrastructure references null; no fabricated owner signature, host attestation or build proof was installed.

Runpod's managed GitHub builder and experimental Weld route were reviewed as alternatives. Neither established a compatible, free, connected build host for the current Pod worker. See the updated first-render document for their constraints and sources. Command Center next needs a concrete build/hosting route before B01/B05 acceptance and B06 dispatch. Automated application billing remains open despite verified connector read access. No billable resource or actual render was started. Validation is limited to approval-record consistency, unchanged runtime source and documentation checks; previously passed fictional tests were not rerun.

## Cloud build setup — November 15, 2026

John approved keeping builds in the cloud. The manual-only GitHub Actions
workflow selects one CPU/GPU target on Ubuntu 24.04, pins action revisions,
uses read-only checkout credentials, limits jobs to 35 minutes and the build
to 30 minutes, validates Docker/RAM/disk, and retains bounded evidence for one
day. It cannot create Runpod resources or publish/deploy images. GPU capacity
preparation removes only listed unused SDKs from the disposable hosted VM.

Account billing observation: $4.91 included compute remaining, $0 billable
Actions usage, 0 / 0.5 GB Actions storage, existing $0 Actions paid budget with
usage blocking. No account limits or plan were changed. Four targeted fictional
checks and workflow syntax/restriction checks passed. Actual build evidence
remains pending until a manual run completes; see deployment/BUILD_VERIFICATION.md.
The approved Runpod trial remains unused and no new numeric approval is needed.

Cloud CPU verification succeeded in run 43772264998 on reviewed source
`18bbdfdcbe266d11db48b6f21cfa9441775cf5c3`: actual image build/identity, static
HTTP/auth check and worker fixture all passed. Downloaded evidence hashes and
full H.264 decoding passed (320x180, 48 frames, two seconds). Evidence is retained
in deployment/evidence/2026-11-15-cpu; the image was not published.

The first GPU host check (run 43772384860) stopped before Docker build because
34.69 GiB free remained after unused SDK cleanup, below the 40 GiB minimum.
The bounded cleanup list now also includes unused Java and CodeQL SDKs; the
minimum is preserved. GPU image and inference gates remain unverified pending
the corrected run. PR #34 added the workflow; PR #35 corrected GitHub runner
context validation before the first build. No Runpod resources were used.

The third GPU run (43773064856) passed host capacity, then exposed an eager CUDA
initialization in Wan's T5 module during import on a CPU builder. Build/smoke
checks now import actual Torch/FlashAttention and compile Wan source syntax;
`wan_cuda_import` remains explicitly unverified until the GPU trial. No CUDA
mock or upstream patch is used. Two targeted syntax checks and seven preflight
checks pass. The source-bound offline plan is refreshed but remains disarmed.
Actual successful GPU image evidence still awaits the corrected build.

## Cloud build batch complete

CPU run 43773935725 and Wan worker image run 43774509988 succeeded. The final
source contexts, helper/verifier, command logs, immutable image identities and
fixture output checksums were reviewed after downloading the actual artifacts.
Both synthetic clips fully decoded as H.264, 320x180, 24 fps, 48 frames/two seconds.
Final evidence lives in deployment/evidence/2026-11-15-cpu-final and gpu-final.

The GPU image loads Torch 2.8.0+cu128/FlashAttention and compiles 28 Wan source
files without executing Wan. Wan's GPU-only import remains explicitly unverified;
no CUDA mock or upstream patch was introduced. No model weights were downloaded.
The offline plan's current source binding is verified and still disarmed.
Validation: four cloud guards, two source-syntax checks and seven affected
preflight checks passed; actual cloud builds add separate evidence. Prior broad
controller/worker suites were not repeated without relevant behavior changes.

The final build used a temporary PR-opened workflow because the browser connection
timed out. PR #40 is closed without merging; main remains manual-only, one build
at a time, 35-minute job ceiling and one-day bounded artifacts. PRs #34–39 contain
the cloud setup and observed fixes. No billing limit or subscription was changed.
The existing $0 paid Actions budget and included allowance were checked before
dispatch; no final post-run invoice is claimed. No Runpod resource was created.

The images existed on disposable runners and were not published. Next recipient:
Command Center for private registry publication and authenticated pull evidence,
then HTTPS controller/durable storage, independent watchdog and actual installed
authority. The owner-approved $5 / 1,800-second / one-attempt trial remains unused.
Automated application Runpod bill collection remains pending. Contract 0.1.0.

Published: [cloud build evidence PR #41](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/41), merged main `e6b9770808071d94fb8080d9167addb172088f5c`; exact reviewed tree `37cea1218fffeb3ae36e3b08fc704a60b3f43b97`. Both image/offline gates are supported by actual cloud artifacts. Registry publication and hosted/GPU acceptance remain open.


## Private publication and hosting preparation — November 16 UTC

Publication implementation [PR #42](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/42)
merged at `e9f37eddf3297695af7f4f2ed5544c17f0885039`. The actual successful
[cloud run 43777990153](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43777990153)
used that source and completed in 12 minutes 28 seconds. Private image:

`ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:c1b181cf4fb83f6451c721dc1035d55966a3757bf6567636bcbeff77f740fbe2`

The registry config equals tested image ID
`sha256:a613ab8cf437275833720e431538d87df9164e31bdf7509733cd6f1fcce9f5d0`.
Visibility is private; anonymous requests are denied; authenticated manifest/config
access passed. This does not prove a fresh layer pull or Runpod access. Compressed
layers total 5,220,107,260 bytes; model weights are not included. No production
credential was included in the build or published image.

Artifact 14187433438 was downloaded and reviewed; ZIP SHA-256:
`e5f2bf648e324dc384521b51f9514f168afe81db91515a70bb72b0d3993a1bb3`.
All 32 source files, four command logs, helper hashes, image identity and fixture
checksum matched. The synthetic H.264 fixture fully decoded. Original logs and
pre-push image inspection remain unchanged. Separate publication evidence binds
the registry digest to the built image; the offline verifier accepts relocated
evidence while preserving original command-path relationships. Tampered manifest,
source binding, image identity and public visibility are rejected. This consistency
check is not a substitute for registry/GPU acceptance. Original evidence is
retained in deployment/evidence/2026-11-15-private-publication.

Hosting and cleanup [PR #43](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/43)
merged at `d0bc84cf2eebe9a15c87643b203d7ed132b188d4`. It includes:

- A Waitress 3.0.2 controller behind Caddy TLS, persistent SQLite/assets, secure
  sessions, bounded uploads, owner/path checks and explicit restored-state binding.
- Independent systemd controller and cleanup processes. The cleanup transport can
  only inspect/delete; it cannot create compute. It reconciles exact durable job
  bindings on completion, failure, cancellation and deadline, including ambiguous
  creation and uncertain deletion. Same-host separation does not survive host loss.
- A manual GitHub Actions deadline guard on a separate host. It requires an
  explicitly installed Runpod secret and exact owner/project/batch/deadline, a
  verified READY record before provisioning, and repeated deletion reconciliation
  for five minutes after the original deadline. It cannot create compute, extend
  the runtime allowance or retry rendering. This workflow is not running.
- Deployment instructions, service/env/Caddy examples and a non-launchable draft
  Runpod template pinned to the published digest. The web entry point does not
  install paid dispatch; real operator trust/admission must be installed separately.

Validation performed for this batch: 36 distinct fictional checks passed (two
publication, four cloud guards, seven hosting/cleanup, two deadline guard, eight
preflight, thirteen existing live admission/execution checks). The locked hosting
dependencies installed with hash checking; a real local Waitress process served
the fictional health request with paid dispatch disabled and shut down cleanly.
The second-host guard imports with the Python standard library alone. Actual
cloud publication and downloaded-artifact review are separate observed evidence.
Unchanged broad suites were not repeated. No deployed TLS/storage/cleanup or GPU
inference success is claimed. The source-bound plan remains PLAN_ONLY/disarmed.

Account observations: no Pods, no templates, no container-registry credential,
$0 balance and $0/hour displayed current spending. Auto-pay is disabled; no payment
method is saved. The console rejected a $5 top-up and states a $10 minimum. A $10
amount was prepared but never submitted. The account's existing $80/hour spending
rate was not changed and is not a $5 trial cap. No WAN Vercel project was found.
No suitable Linux host has been established; no host, subscription, volume, GPU
or top-up was purchased. Runpod download should be verified as part of the one
approved deployment attempt, not by consuming an additional unapproved trial.

The browser is left at Runpod registry credentials and billing for owner-only
credential/payment actions. Never paste tokens into chat or commit them. A
low-cost Linux hosting candidate and its limitations are recorded in
deployment/hosting/README.md; it is not an available accepted quote or approval.
Application billing ingestion, external alert delivery, installed runtime trust,
actual host/restore acceptance, registry pull and GPU inference remain open.
The $5 allocation remains $4 Pod plus $1 separately tracked storage, maximum
1,800 seconds from admission, one Pod-create/worker attempt and one five-second
shot, with temporary storage retention no longer than 24 hours. Reservations and
cleanup checks cannot guarantee a provider-side dollar hard stop during outages
or delayed billing. Contract remains 0.1.0. Next recipient: Command Center.

Published evidence: [PR #44](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/44), merged main `0bc52ba44e084767cbbfd373f7ca9c9e2625c56d`; exact reviewed tree `c954754e098d9043f5366e7cd580ea363ffb5d4a`. Private image publication is verified; actual Runpod pull, hosting and installed cleanup remain open.


## Account setup continuation — November 16 UTC

John instructed the Command Center to proceed with the remaining setup after
being shown the $10 minimum funding amount. One $10 Runpod credit payment was
submitted through the existing selected checkout method and returned a card-declined
message. The balance remained $0 and no successful top-up is claimed. The agent
stopped after that single funding attempt; no alternate card was selected or
retried. The checkout is left open for John. This is separate from the unused
one-attempt GPU trial; no Pod or inference attempt was made. Auto-pay remains off.
Do not repeat the funding attempt without John's choice of a working payment method.

GitHub classic token creation is blocked by Confirm access. The Verify via email
step sent the owner an authentication code; John must complete it on GitHub.
Never paste the code or new credentials in chat. The Runpod registry form is
named wan-ghcr-pull, with username/password not populated and Save not submitted.
The proposed GitHub token remains read:packages only; no token was generated.

The Runpod API-key form is prepared as wan-cleanup with only REST Pods Read and
Write selected. Create was NOT submitted; no credential was generated or saved.
Runpod's Pod Write permission is broader than delete-only and can also authorize
Pod creation. The cleanup software restricts itself to GET/DELETE, but that does
not reduce the credential's provider permissions. Final credential creation and
secure installation need the owner's action/confirmation; do not reuse or expose
the existing connected-app key. GraphQL, Serverless, Secrets, Authentication,
Billing and unrelated scopes were not enabled on this prepared cleanup form.

Hosting research: the official Hetzner cost-optimized page still lists CX23 as
unavailable. OVHcloud's US configurator lists VPS-1 unavailable, and the VPS-2
configuration showed no available location in the North America and Europe tabs.
No host was ordered. Its default 12-month commitment was changed to No commitment
for investigation only. The incomplete zero-dollar cart was not treated as a quote.
DigitalOcean's public Basic Regular rate for 2 vCPU/4 GiB/80 GiB is $24/month before
optional backup and taxes; it is an unapproved higher-cost fallback, not a selected
host or verified capacity. Do not silently substitute it for the cheaper plan.

References checked November 16 UTC:
- https://www.hetzner.com/cloud/cost-optimized/
- https://us.ovhcloud.com/vps/configurator/?planCode=vps-2027-model1
- https://www.digitalocean.com/pricing/droplets

Immediate handoff: John completes GitHub email verification and chooses a working
payment method in the Runpod $10 checkout. Continue the scoped private-registry
credential, trusted cleanup secret and concrete hosting selection afterward.
The existing private image and 36-test evidence are unchanged; no code was changed
and no tests were repeated. Hosting, actual Runpod image download and installed
automatic shutdown remain unverified. No new recurring service was purchased.


## Runpod funding confirmed — November 15, 2026 (America/New_York)

John stated he confirmed the prior decline with Bank of America and explicitly
authorized a retry of the $10 Runpod payment. The same previously selected
checkout payment method was selected and Pay was submitted exactly once for the
retry. The observed post-payment Runpod billing page showed:

- Account balance: $10.00.
- Current spend rate: $0.000/hour.
- Auto-Pay: Disabled.

Funding is therefore complete. The prior decline and credential/hosting records
above remain historical. Do not make another top-up unless separately requested.
The existing checkout also resulted in the payment method being listed in the
Runpod account; no separate Add payment method action or Auto-Pay change was made.
No payment screenshot or card details are retained in project documents.

The $10 is prepaid service credit, not observed GPU consumption. The trial remains
$5 maximum total, 1,800 seconds from admission and one attempt; it has not started.
No GPU, volume or recurring hosting resource was created. GitHub email verification,
private pull credentials, hosting and installed shutdown remain pending. The
billing result is left open, and the credential/verification tabs remain available.


## GitHub verification complete; credentials prepared — November 15, 2026

John reported Done, and the browser showed the new classic-token form rather
than the previous Confirm access screen. GitHub verification is observed complete.
The form has note wan-runpod-image-pull, 30-day expiration (December 15, 2026),
and exactly one selected scope: read:packages. Generate token was not clicked.
Runpod's registry credential form has name wan-ghcr-pull and the GitHub username;
its password remains empty and Save was not clicked.

The wan-cleanup Runpod API-key form remains prepared with only REST Pods Read and
Write selected. No key has been created. Those provider permissions include Pod
creation and deletion across the account; the cleanup program limits itself to
its exact WAN resource bindings and GET/DELETE but does not narrow the key itself.
The WAN repository's Actions secret entry is prepared for RUNPOD_CLEANUP_TOKEN;
its secret value remains empty and Add secret was not submitted. The requested
owner confirmation covers creating both credentials and directly saving the GHCR
token to Runpod registry credentials and the Runpod key to this private repository's
encrypted Actions secrets. Tokens must never appear in chat, logs or source files.

Funding remains complete and the GPU trial unused. No further payment, provider
resource, hosting service, live credential or rendering job was created. Hosting
and actual Runpod download/installed shutdown remain open. No code or tests changed.

## Approved credentials saved and private template created — November 15, 2026

John explicitly approved creation and secure storage of both credentials. The
GitHub classic token wan-runpod-image-pull has read:packages only and 30-day
expiration (December 15, 2026). It was transferred directly to Runpod registry
wan-ghcr-pull, ID cmwik8xrr008eoog7l16ldqug, for hoyosgarciajohn-png. The Runpod
key wan-cleanup has only REST Pods Read and Write, with GraphQL/Serverless and
all other REST sections disabled. It was transferred directly into this private
repository's encrypted RUNPOD_CLEANUP_TOKEN Actions secret. Both destination
listings were verified. Values are absent from chat, source, evidence and documents.

Private template lehfc5qf3s was created and read back through Runpod. It uses the
published sha256:c1b181cf4fb83f6451c721dc1035d55966a3757bf6567636bcbeff77f740fbe2
image, registry ID above, 80 GB ephemeral disk, CUDA 12.8, no ports, no SSH or
Jupyter, empty environment and no mounts. This configuration incurs no GPU or
storage allocation. Controller/bootstrap and model mounts remain required.

The new manual check-cleanup-credential workflow makes exactly one authenticated
GET using the saved secret. It cannot create/delete resources and logs only a
sanitized result. Two fictional tests pass: GET-only request/data redaction and
failure-message redaction. Live workflow execution is pending at this checkpoint.
Read authentication does not prove deletion permission or installed shutdown.
No GPU attempt, recurring host or additional payment was made. Contract remains
0.1.0. The next recipient is Command Center for hosted deployment prerequisites.

## Cleanup credential read access verified — November 15, 2026

[PR #47](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/47)
merged at 365b3f2a6b6ab05f2b1240cc8175b6c9f20aa318. The manual
[credential check](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43784863537)
succeeded (job 133030124483, 11-second total workflow). Its exact logged result is
AUTHENTICATED_POD_READ_PASS: one GET, zero resources created/deleted,
deletion_permission_verified=false and shutdown_verified=false. The encrypted
GitHub Actions secret therefore works against Runpod REST v2. It is not proof of
an operating deadline guard, primary cleanup service or provider-side dollar cap.
A separate connected full inventory, including cluster Pods, returned zero Pods
with pagination exhausted. The $5 / 1,800-second / one-attempt trial remains unused.

The first UI dispatch click produced no run; after confirming no run and inspecting
the ready form, keyboard submission produced the single observed run #1. No rerun
or GPU request occurred. Original sanitized job log and result metadata are saved
in deployment/evidence/2026-11-15-cleanup-credential. Two fictional checks passed;
no unaffected build/test suite was repeated. Contract 0.1.0 remains unchanged.

Remaining gates: approved and available controller hosting/HTTPS, installed runtime
authority and primary plus independent cleanup, model/storage bootstrap, actual
private image download and CUDA/Wan inference, and authoritative billing retrieval.
Runpod funding ($10 credit) and credential setup are complete. No additional payment,
GPU/storage allocation, recurring host or paid builder was purchased in this step.

## Controller installation prepared; hosting decision pending — November 15, 2026

**Historical proposal; superseded by the free-only hosting decision below.**

User requested controller hosting and automatic shutdown installation. Remote main
baseline c4b6251076797ab7d38f452721b1f8b496b82199 was verified. No compatible
connected host exists in the known setup. DigitalOcean/Hetzner plugin discovery
returned no matching management integration. DigitalOcean's console was opened
and is at sign-in; its existing servers, account state and actual regional stock
remain unknown. That page is retained for the owner to sign in.

The recommended concrete configuration is documented in
[HOSTING_DECISION.md](https://github.com/hoyosgarciajohn-png/wan-video-generation/blob/main/deployment/hosting/HOSTING_DECISION.md):
one Ubuntu 24.04 amd64 DigitalOcean Basic Regular bundled 2 vCPU / 4 GiB / 80 GiB
server ($24/month) plus weekly backups ($4.80/month), four weekly copies, subtotal
$28.80 before tax. Request approval for a **$32/month ceiling including tax**.
No hosting approval is inferred from the earlier $5 GPU trial or credential approval.
Check existing suitable resources first after login; confirm exact price/capacity
before purchase. No domain, upgrade, extra volume or other paid add-on is included.

Hetzner CX23 remains publicly marked unavailable; CPX22's current European USD
rate is $22.99 before extras. Connected Runpod CPU3c is available at two vCPUs x
$0.03/hour, $43.20 per 720 hours before storage; not chosen for continuous hosting.
Sources and limits are retained in the decision document.

Implementation: guarded fresh-host service installer validates exact commit,
architecture, dependencies and protected secret files; refuses existing state or
settings; installs separate controller/cleanup/HTTPS services. The dedicated Caddy
unit avoids overwriting another site's proxy configuration. The new disarmed
initializer creates cleanup/admission/execution tables without authority keys or
provider transport. This fixes the fresh-install failure where cleanup tables
were absent. No live create route is enabled. Installer source and new runtime
files are included in source-bound preflight; PLAN_ONLY remains non-executable.

Validation actually run: 2 fictional initialization checks (repeat initialization,
retained data, empty cleanup without network, and restored-path refusal), 8 affected
preflight checks, bash syntax check, source-bound plan verification and whitespace
check. All pass. Installer/systemd/TLS were not executed on a real server; no
shutdown operation or Runpod private image download is claimed. Existing build,
credential and publication checks were retained without repetition. Contract 0.1.0.

Next recipient: Command Center after owner hosting decision and DigitalOcean
sign-in. Confirm region/price and hostname, provision/reuse the approved host,
securely install credentials and the prepared release, verify TLS/persistence/
recovery/monitor operation, then install live authority and use the one-attempt
GPU trial. The approved $5 / 1,800-second / one-attempt trial remains unused.
No additional payment, recurring host, GPU or storage resource was created.

## Paid controller proposal withdrawn; free route selected — November 15, 2026

**Historical direction; superseded by the lower-cost DigitalOcean approval below.**

John explicitly rejected DigitalOcean and requested a free alternative. Additional
recurring controller budget is now $0. The previous $32/month approval request is
withdrawn. No paid replacement VPS or paid account upgrade is authorized. The
DigitalOcean login tab was closed. No subscription or server was purchased.

Reviewed official Oracle, Render, Cloudflare, Microsoft WSL and GitHub documentation.
Oracle Always Free is a persistent-server candidate; the Windows PC is a fallback.
John then asked what our other projects already use. Connected inventories confirm
Vercel and ChatGPT Sites host existing websites, with Supabase databases for several
projects. Existing-service reuse is now the first option to assess before creating
another hosting account; it requires backend adaptation and quota/cost verification.
The decision document records exact current allowances, limitations and steps.
Cloudflare would need a material backend redesign; Render Free does not preserve
this implementation's SQLite and media filesystem. GitHub Actions remains the
bounded independent cleanup guard, subject to remaining included usage.

The current installer rejects ARM, so Oracle is not deployment-ready. Account
eligibility/capacity, ARM dependencies and actual host behavior must be verified.
Do not weaken source-bound admission or claim hardware acceptance from research.
The existing Runpod GPU image remains amd64. No signup, account upgrade, runtime
change, credential creation, GPU or volume allocation occurred in this step.

Source baseline: PR #49 / main 3ac7309a103b9b5bcf0c237aa24d8d6975242355.
Contract 0.1.0 unchanged. Documentation consistency and whitespace checked;
previous automated/runtime evidence retained without repeating unaffected tests.
Actual shutdown, Runpod image pull and authoritative bill retrieval remain open.
The approved $5 / 1,800-second / one-attempt GPU trial remains unused.
Next recipient: Command Center to compare reuse of existing hosting with the free
server alternatives, verify the chosen route, and complete existing launch gates.
No existing project data or deployment was changed during the inventory review.

## Lower-cost DigitalOcean approved; account sign-in pending — November 15, 2026

John selected the proposed $12/month Basic Regular bundled server plus weekly
backups at 20%: $14.40/month before expected tax, one host, 1 vCPU, 2 GiB RAM,
50 GiB SSD. He intends to consider an upgrade if more capacity is needed. This
is initial-host authorization, not unlimited future capacity spending. The prior
free-only rule and larger $24 server proposal are superseded for this purchase.

Current tool discovery found no DigitalOcean management integration. Connected
Chrome reached the DigitalOcean login form with blank fields. The page is marked
for owner sign-in. No account inventory, billing state, region capacity, checkout
or host creation was verified. No server, paid subscription, credential, volume,
GPU or model download was created. No other project was changed.

Prepared a non-executable exact configuration in
 deployment/hosting/digitalocean-controller-proposal.json and revised installation
instructions: off-host Studio build, one-at-a-time exports, actual memory/disk and
cleanup acceptance before GPU use, no automatic upgrades. The current fixture
export profile is 320x180; production-quality long-form exports are not established
by choosing this host. Source behavior and contract 0.1.0 are unchanged.

Baseline remote main c5e6a5687802c9f137cf19ad34a819b36aaef498 / PR #50.
Validation: JSON amounts/scope/status and handoff consistency, plus whitespace.
Existing runtime tests were retained without repetition. The $5 / 1,800-second /
one-attempt trial remains unused. No DigitalOcean charge was initiated here.
Next recipient: owner for sign-in, then Command Center for actual host provisioning,
installation and acceptance. No repeat numeric hosting approval is required.


## DigitalOcean account verified; dedicated access prepared — November 15, 2026

John confirmed sign-in. The current account is My Team; first-project has no
resources and the global Droplet inventory is empty. An existing primary payment
method is present. No billing change or payment attempt was made. The exact
approved checkout is configured: one wan-controller-01, Ubuntu 24.04 LTS x64,
SFO2, Basic Regular s-1vcpu-2gb, 1 vCPU, 2 GiB RAM, 50 GiB SSD, $12/month plus
weekly percentage backups $2.40/month. Tax is not itemized. NYC3 did not offer
Basic Regular, so the form retains SFO2 rather than a higher-priced substitute.
No extra volume or managed database is selected. Free monitoring is selected.

The existing SUMAN staging key is unrelated and remains unselected. A dedicated
ed25519 key named wan-controller-deploy was generated locally, with private-file
mode 0600. Its public fingerprint is
SHA256:GGPDVk0v1xgocnC0P1OCvmSM/h9VggrKxAUDIbF1iKA. The public-key registration
dialog is filled but unsubmitted. Confirmation is needed at this action because
it grants administrator access. The concrete request covers registering the
public key for this WAN host and keeping its private part as encrypted
WAN_HOST_SSH_KEY in the private WAN GitHub repository for installation/maintenance.
The private key has not been printed, committed, uploaded or registered externally.
The form is retained for continuation after that access confirmation.

The hosting purchase itself is already authorized; do not ask again for its
$14.40/month pre-tax price. No server has been created, so installation, hostname,
HTTPS, persistent restore, live authority, image pull, shutdown and billing
collection remain pending. The separate $5 / 1,800-second / one-attempt GPU trial
remains unused. No new paid resource or Runpod job was started in this step.

Issue: #7 (B06), with the one-shot owner envelope superseding its original six-shot
proposal. Baseline main: 5dae41d3d7e7811aa761f42f7c30a332406cf9a7 / PR #51.
Contract 0.1.0 is unchanged. This update changes documentation/configuration only.
Validation: JSON scope/price/access state and matching handoff copies, plus
git diff --check. Existing fictional runtime test evidence is retained without
repetition. Next recipient: John for dedicated access confirmation, then Command
Center for the approved host purchase, installation and deployment acceptance.


## DigitalOcean controller installed and verified — November 15 local / November 16 UTC, 2026

John approved the concrete key registration and encrypted GitHub storage with
“yes”. Created only the approved SFO2 server and enabled weekly percentage backups.
Source/access preparation merged in PR #53; root-owned archive extraction and a
narrow partial-install recovery merged in PR #54; strict-CSP Studio schema
precompilation and guarded source upgrade merged in PR #55. Deployed commit:
42dbdc127b299b7e11e674630bef8683473f5a7a. Contract remains 0.1.0.

Cloud run outcomes are retained, including failures: inspect 43793819679 passed;
install 43793913368 stopped on source ownership before private application state;
resume 43794353466 installed all services but its immediate TLS probe failed during
certificate issuance; upgrade 43794933132 installed the CSP fix and preserved
private state but its immediate local health probe preceded socket readiness.
Read-only verification 43795476474 then passed on the installed revision, including
valid external TLS. A bounded read-only health retry now addresses the observed
startup race in the verification source; it is not a repeated render or install.

An application-consistent pre-upgrade backup was created on the same host, and
the old source is retained. This is not off-host recovery acceptance. Database
integrity passed with zero live-job bindings. Cleanup status was ready with zero
due batches and no unresolved entries; authenticated Runpod GET passed, zero
creates/deletes. Actual shutdown and independent guard activation remain open.

Fictional validation performed in this turn: 20 targeted hosting/initialization/
preflight checks; extraction ownership regression; 17 Studio model/API/CSP checks;
17 UI checks; production build; one affected source-inventory test after adding
upgrade-host; formatting, shell syntax and whitespace. Retained previous evidence
without full-suite repetition. Hosted CPU baseline is not a production load test.

Browser evidence: initial blank UI due to runtime AJV compilation was corrected;
the sign-in screen now renders. Its session request remains rejected, and a direct
browser session navigation returned 403. Separate direct same-origin/cross-site
HTTP checks returned expected 401/403. Owner token exists only in protected host
configuration; delivery and successful owner login are pending. Security checks
were not relaxed. No real media or creative acceptance was claimed.

Active cost/resource: one DigitalOcean CPU host at $14.40/month before expected
tax, with backups enabled and first scheduled backup pending. No additional
Runpod charge was incurred; the existing $5/1,800-second / one-attempt trial is unused.
Exact accrued DigitalOcean billing has not been retrieved. Next: owner access,
fictional hosted workload/recovery, live execution setup, then the approved trial.

## November 16, 2026 — owner access, recovery and first actual GPU trial

PRs #57–63 resolved owner browser sign-in, added hosted/independent recovery evidence,
installed the private trial operator and worker receiver, and preserved narrow cleanup
credentials by accepting fresh catalog/billing reads from the existing connected account.
Installed release remains 387555fd40a57f1fcda2d0abff1fff20d93e4075. Contract 0.1.0 unchanged.

The native browser fetch receiver bug was fixed without weakening security controls.
Owner access succeeded and the synthetic project with succeeded MP4 export was visible.
Hosted acceptance/restart/same-host recovery passed; its copy step failed separately.
Copy-only recovery then passed on an independent runner 43800008304, with exact media
hash/full decoding, history and owner isolation. Earlier copy-only failures (missing
FFmpeg, transient checkout) were retained rather than represented as successful tests.

Trial 43801863653 created exactly one RTX 4090 Pod at $0.89/hour. Private image pull,
all 13 pinned model-file checksums and scoped worker claim passed. The real shot failed
before committing output. Automatic deadline cleanup completed; no Pod or persistent
volume remains. The render and creative/output-retention acceptance gates remain open.
No retry was launched, and the $5 / 1800-second / one-attempt envelope was not expanded.

Post-trial code addresses delayed failure cleanup, restart replay, safe diagnostics,
and stale guard readiness. The original child error was not retained, so no root-cause
fix or second live acceptance is claimed. Deployment and rebuilt image publication are
pending browser reconnection; the installed image/source remain the measured versions.
Authoritative billing/final settlement and automatic application-side collection remain
pending. Weekly provider backups are enabled but the first scheduled snapshot is pending.

Final guard outcomes:43801724802 observed the allocated Pod and confirmed its absence
at04:28:37.627UTC, then through the post-deadline watch. Earlier guard43801296860
missed the already-removed allocation and exited with NO_ALLOCATION_OBSERVED. This
known evidence limitation is addressed in the prepared source; no GPU remains.
Post-trial validation passed29worker/execution/integration tests,8hosting tests plus
the safe-code cleanup regression,3guard tests and1freshness regression, syntax/compile
and whitespace checks. Billing at04:33UTC still had no records; final charge is pending.

Prepared corrections and full evidence: PR #64, https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/64, head d29cfdd869f347195ce4c68151b88ac936a324fd. This source is not yet installed on the controller or rebuilt into the private worker.

PR #64 merged as 0f94a1754d03818c04f4376c905a735fd45fa033. Installed production source remains 387555fd40a57f1fcda2d0abff1fff20d93e4075; no post-trial deployment or new GPU image build has run. Reconnect the existing browser to resume the authorized deployment/build preparation. A new paid render remains outside the consumed one-attempt authority.

## November 16 continuation — deployment resumed (00:09–00:18 Eastern)

PR #65 fixed a backup compatibility failure exposed by the live trial; PR #66 fixed
a host-verification assumption that the database had no live history. The corrected
controller is installed at 4555997 and final verification 43809179887 passed.
The new private worker was published and independently reviewed from build 43808492420;
see `deployment/evidence/2026-11-16-private-rebuild/` and
`deployment/evidence/2026-11-16-resumed-deployment/`. Existing encrypted owner access
was restored after restart. No extra GPU trial was launched. The first-trial billing
observation was imported as provisional 15 cents, with 385 cents still reserved.
The next paid diagnostic is documented but disabled pending fresh specific approval.

## Additional diagnostic approval — November 16, 2026

John approved the concrete one-second diagnostic: an additional $5 total, 1,800 seconds from admission, one Pod-create/render attempt. PR #68 installed isolated trial/grant/guard routing at 8e07ba3e8dfb9a250424bb4c8607cd1cac36cfe6. Deployment 43811745342 passed. The prior failed trial and its provisional billing remain preserved. The new trial is being prepared; this entry does not claim a render result.

## Additional diagnostic outcome — November 16, 2026 (01:03 Eastern)

The separately approved diagnostic is consumed. It failed with gpu_out_of_memory at
06:03:11 UTC, no take. Automatic cleanup was confirmed at 06:03:20 UTC; connected
Runpod inventory and exact-Pod 404 independently confirmed absence. The full $4
reservation remains because the connected billing observation is not final. The
private image pull, pinned weight checks, scoped claim, failure-code transport and
early automatic deletion are verified. No successful real video exists yet. Draft
PR #69 prepares a lower-memory execution candidate and stronger phase diagnostics;
its ten CPU-only checks pass, but it is unbuilt and undeployed. No third GPU attempt
is authorized.

Independent guard closure: run 43811980342 completed successfully after repeated
ABSENCE_CONFIRMED observations through 06:17:00.647 UTC. No GPU remains and the
late-allocation observation window is complete.
