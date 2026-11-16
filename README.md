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
No real Wan clip has been saved yet. PR #76's launch diagnostics and multiple-data-center
request are merged, and PR #77 records the support inquiry already sent.

John subsequently authorized one isolated one-second test without waiting for the
old request to be reconciled. The exception retains that exact request's $4 billing
reservation and cleanup monitoring, checks its expired worker access, and adds it
to the new independent cleanup guard. All other unresolved historical work blocks
admission. Hardware, $5 additional total and 1800-second limits stay unchanged.
See [the current handoff](docs/WAN_00_Master_Handoff.md) for deployment and results.

The latest isolated one-second allocation was rejected by Runpod with HTTP 400
at 18:52:45 UTC on November 16: no instance matched the requested specifications.
No Pod, GPU render or take resulted. The repaired diagnostics retained the reason
and request ID, and cleanup is confirmed for this request. PR #80 is installed
as d30fa01. The one-create scope is consumed, its billing reservation is retained,
and the older ambiguous request remains unresolved. Hourly capacity checks are
read-only. Five-second generation awaits successful one-second output. See
[the allocation result](deployment/evidence/2026-11-16-isolated-validation/allocation-result.json).

John approved an L40S fallback and bounded retries after explicit capacity
rejections. The new isolated scope allows RTX 4090 or L40S at <=$1.10/hour, keeps
the $5 / 1800-second / one-render envelope, and permits at most three allocation
requests. [Fallback evidence](deployment/evidence/2026-11-16-fallback-validation/README.md)
records checks and live status. Earlier consumed scopes remain immutable.

PR #82 is installed as bef93c9. The approved L40S launch 43949478736 exhausted
its three capacity-only requests: all returned explicit HTTP 400 no-capacity
rejections. No Pod, render or take resulted; cleanup is confirmed and the billing
reservation remains retained. The fallback scope is consumed. See the linked
fallback evidence for request IDs and next-step constraints.
