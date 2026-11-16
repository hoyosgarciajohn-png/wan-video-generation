# Wan Video Generation · Master handoff
Version 1.21 | November 16, 2026 UTC (November 15 owner local) | Owner: John Hoyos

## Approved direction
Build a shot-based platform for music videos up to 5 minutes and short films and animated cartoons up to 30 minutes. Self-host open-weight Wan. Rent GPU infrastructure by the batch and avoid per-generation model fees. Baseline: Wan2.2 TI2V-5B, RTX 4090 24 GB, pinned Docker image, temporary Runpod Pod. Keep project state and outputs outside the GPU. Confirm teardown after every batch. Larger Wan checkpoints, custom Runpod Flex, and other GPU rental providers are benchmark alternatives. Repository is https://github.com/hoyosgarciajohn-png/wan-video-generation. The first-trial $5 / 30-minute / one-attempt envelope is approved; hosted storage and release dates remain pending. B00 is complete. PR #11 merged with 14 passing local tests and verified synthetic media. GPU benchmarking is scheduled for B06.

## Current Command Center checkpoint
The Wan worker image is now published privately in GHCR. Actual publication run
43777990153 succeeded; authenticated registry manifest/config verification binds
the private digest to the tested image, and anonymous access is denied. Original
build/publication evidence is retained in deployment/evidence/2026-11-15-private-publication.
Actual Runpod download remains unverified. No Docker Desktop is required.

Controller hosting, persistent state and two automatic-cleanup layers are
implemented and tested with fictional data, but are not installed on a host.
The Runpod account displays $0, no payment method and no registry credential.
The console requires a minimum $10 credit top-up; none was submitted. No suitable
existing controller host or recurring hosting budget is established. The approved
$5 / 1,800-second / one-attempt trial remains unused. Historical entries below
are chronological; this checkpoint supersedes earlier publication status.

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
Command Center: finish the account/host inputs, deploy and verify the reviewed
controller and both cleanup layers, then verify the exact private image on Runpod
within the already-approved trial. John approved $5 total, 30 minutes from
admission, one five-second clip and one attempt on November 15, 2026. Do not
request the same numeric approval again. A $10 credit top-up and any new recurring
hosting expense are separate from that consumption envelope and have not occurred.

Required inputs: scoped GHCR pull credential saved directly in Runpod; an
application/cleanup Runpod credential in trusted service secret storage; funded
Runpod credit; an available Linux amd64 controller host and owned HTTPS hostname.
Install real live authority, persistent storage/restore evidence and primary plus
second-host cleanup before GPU creation. Recheck compatible RTX 4090 capacity and
price only when those prerequisites are ready. The published image has no model
weights. Wan CUDA import, model checksum verification and inference remain open.
Automated authoritative application billing collection remains pending. A draft
Runpod template is saved but no template or paid resource was created.

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

See deployment/FIRST_RENDER_PROPOSAL.md and deployment/first-render-proposal.json for the concrete, unapproved $5/30-minute/one-attempt envelope, current public price assumptions, storage retention, ordered host acceptance and billing follow-up. Approval fields remain null. Shared storage is not covered by the existing Pod ledger; $1 is held separately from the proposed $4 Pod grant. No recurring hosting, paid build service, account top-up or automatic retry is included.

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
