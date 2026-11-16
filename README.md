# Wan Video Generation

A private foundation for self-hosted Wan production using temporary Runpod GPU Pods. Target projects are music videos up to 5 minutes and short films and cartoons up to 30 minutes.

The local integration checkpoint includes the storyboard fixture UI, durable fixture controller, Wan worker source, CPU exporter and QA checks. See [integration evidence and remaining gates](docs/B05_INTEGRATION_CHECKPOINT.md). The [connected Studio checkpoint](docs/STUDIO_API_V1.md) adds local authenticated project persistence and protected media reads. [Connected fixture render commands](docs/RENDER_COMMANDS_V1.md) now submit, cancel and review actual synthetic worker outputs. [Protected uploads and timeline/export controls](docs/MEDIA_COMMANDS_V1.md) complete the local synthetic workflow through MP4 download. Durable chunk uploads support WAV/MP3 tracks up to 128 MiB; see [upload protocol](docs/UPLOADS_V1.md). [Checked local recovery](docs/BACKUP_RESTORE.md) and [staging preparation](docs/DEPLOYMENT_READINESS.md) are available. [Budget/lifecycle rehearsals](docs/BUDGET_ORCHESTRATION.md) use only the built-in fake provider; they cannot dispatch Runpod. [Scoped remote worker transfer](docs/WORKER_TRANSPORT.md) now supports separate controller/worker storage roots for fixture batches, with expiring credentials and replay-safe completion. The CPU controller is hosted with HTTPS and durable disk. Owner browser sign-in and the synthetic hosted workflow with independent recovery are verified. The first bounded live trial is recorded separately from synthetic acceptance.

The [first real Wan run checklist](deployment/FIRST_WAN_RUN.md) records the concrete host, image, model and budget requirements. Trusted live execution is implemented; default execution remains disarmed pending verified deployment and owner authority. Supplying a GPU alone does not enable live execution.

The [Runpod deployment worksheet](deployment/RUNPOD_DEPLOYMENT.md) covers the v2 provider adapter, durable storage, independent cleanup and remaining activation prerequisites. Trusted live execution is connected. A private operator installs authority only for the approved single trial; the public Studio cannot provision paid GPUs.

[Signed admission source](docs/LIVE_ADMISSION.md) now verifies installed owner authority and atomically saves queued jobs with separate reservations. The default staging host remains unconfigured; the dedicated production host now receives scoped worker execution for the approved trial. [Trusted execution and signed billing](docs/LIVE_EXECUTION.md) now connect the guarded callable path; the dedicated host has private authority scoped to one approved attempt, with independent deadline cleanup.

## Start

Read [the master handoff](docs/WAN_00_Master_Handoff.md), [architecture](docs/ARCHITECTURE.md), [shared contract](docs/CONTRACT.md), and [workstream assignments](docs/WORKSTREAMS.md).

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/validate_contract.py --media-root fixtures
python -m unittest discover -s tests -v
```

Install FFmpeg, including ffprobe, through your operating system package manager. Fixture media is synthetic and intentionally tiny. Run validation from the repository root. Python dependencies are confined to development checks at this stage.

The 0.1.0 schema and complete fictional project live under `contracts/` and `fixtures/`. The previous starter ZIP is an archived draft. Use this repository as the current source for implementations.

The [build/hosting review and first-render proposal](deployment/FIRST_RENDER_PROPOSAL.md) records the verified cloud builds, remaining host evidence, Runpod connection and owner-approved $5 / 30-minute / one-attempt envelope. Hosting, HTTPS, owner access and synthetic hosted recovery are verified. The private one-attempt operator is installed; public paid dispatch remains disabled.

[Manual cloud container builds](deployment/BUILD_VERIFICATION.md) now use GitHub
Actions within the account's included allowance. Windows Docker Desktop is not
required. Image verification is separate from registry publication, hosted
controller acceptance and the approved first GPU trial.

The [hosting and cleanup package](deployment/hosting/README.md) adds a loopback
Waitress backend behind Caddy TLS, persistent controller service, separate cleanup
process and an optional second-host deadline guard. The primary services are installed and healthy; a separate deadline guard is bound to the admitted trial.
Owner browser access and synthetic workload/recovery are verified; actual GPU evidence is tracked separately. The manual private GHCR
publication workflow records visibility and digest evidence separately from the
still-unverified Runpod download.

[Installed controller evidence](deployment/evidence/2026-11-16-controller-hosting/README.md)
records the initial hosted release and resource/cost. Later [access and recovery evidence](deployment/evidence/2026-11-16-access-recovery/README.md) supersedes its original sign-in and recovery gaps. See the [first live trial](deployment/evidence/2026-11-16-first-live-trial/README.md) for GPU execution, cleanup, costs and remaining gates.

## Current continuation status

The 1280x704/24fps exporter and hosted one-minute synthetic rehearsal passed.
No real Wan clip has been saved: the original trial failed without a retained
cause, the diagnostic failed with GPU out of memory, and the repaired-worker
attempt never produced an observed allocation. Its original create response was
lost; both monitoring workflows finished and cleanup remains unresolved.

[PR #76](https://github.com/hoyosgarciajohn-png/wan-video-generation/pull/76)
adds durable redacted create diagnostics, explicit-rejection handling, signed
multiple-data-center placement and an isolated next validation scope. The changes
pass 172 root and 41 deployment fictional checks. They are not deployed over the
unresolved request. See [reconciliation evidence](deployment/evidence/2026-11-16-launch-reconciliation/README.md)
and the [master handoff](docs/WAN_00_Master_Handoff.md).

John authorized continuing one second → five seconds → one minute within unchanged
limits, after reconciling the prior request. No new GPU attempt or larger budget
was used. Public Studio dispatch remains synthetic. The repaired worker image is
[verified offline](deployment/evidence/2026-11-16-memory-repair-build/README.md),
with actual memory fit and successful output still pending.
