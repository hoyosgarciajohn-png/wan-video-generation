# First Wan render: host review and proposed limits

November 15, 2026. **PROPOSED — owner spending approval is unset; launch remains blocked.**
Reviewed source: main `21a5bcab35db6ef047f9190c4185b38415f8882f` (PR #31), tree
`0af62a393cfa8eb2ea5b3461ac952099de2c7994`. Contract 0.1.0.
This document is a decision worksheet, not a grant or launch configuration.

## What was actually verified

| Area | Observation | Result |
|---|---|---|
| Available build workspace | Linux x86_64; 56.4 GiB free; Docker, Podman, buildctl and buildkitd absent; no standard Docker/containerd socket; AF_UNIX bind denied with errno 1 | Cannot execute the prepared image builds here |
| GPU in this workspace | No NVIDIA device, nvidia-smi or nvcc | No CUDA validation or inference possible here |
| Owner's computer or other server | No compatible daemon or host access verified | Remains unverified; the workspace result says nothing about the owner's PC |
| Runpod account | Connected browser reached the Runpod sign-in page | Account, balance, GPU availability and existing resources could not be inspected |
| Image and registry | No actual CPU/GPU image IDs or published tested digest | Build and publication gates remain unverified |
| Controller and cleanup hosting | Source exists; no verified HTTPS endpoint, durable storage or independently running watchdog | Hosting is not ready for dispatch |
| Billing | Delegated signed-receipt ingestion exists | Automatic Runpod bill retrieval remains pending |

No resource, image build, model download, API key, registry push or paid service was
created by this review. Cost incurred by this review: $0. No resources were created;
the account's pre-existing resources are unknown because sign-in is required.

## Recommended first trial

| Control | Proposed value, awaiting John |
|---|---|
| Overall incremental trial allowance | **USD $5 total**, not recurring and not an account top-up |
| Pod spending sublimit | $4 within the $5 total; reserve the full $4 for the single job |
| Non-Pod storage allowance | $1 within the $5 total; separately tracked because the current Pod ledger does not enforce shared-volume costs |
| Runtime | **1,800 seconds / 30 minutes from admission**, including queue, startup, checkpoint verification, generation and upload; never reset after restart |
| Work | One fictional text-to-video shot, target 5 seconds, Wan2.2 TI2V-5B, 1280×704, 24 fps, 50 steps, seed 42; worker-compatible frame count |
| Compute | One RTX 4090, one GPU; live GPU quote ceiling $1/hour; no automatic substitution |
| Attempts | One worker attempt and one Pod-create attempt; no automatic rerender or replacement Pod |
| Shutdown | Request termination after verified completion, failure/cancel or deadline; confirm absence with the independent monitor |
| Storage | Provisional 100 GB model cache plus 10 GB journal/cache, standard network storage; size and placement verified before purchase |
| Retention | Trial-only volumes up to 24 hours from creation, with verified output/journal preservation before removal; shared volumes are not deleted |
| Other purchases | No paid build host, hosting subscription, registry upgrade, auto-refill or paid generation API in this proposal |

The GPU preference preserves the existing benchmark baseline. Official Wan
documentation supports TI2V-5B on 24 GB with CPU/model offload, but the pinned image
and selected host have not demonstrated it. System RAM, disk, driver and actual
availability must be checked. A lower hourly price on another GPU does not prove a
lower cost per usable clip. Alternative hardware gets a separate reviewed profile.

Runpod's public price page, updated November 12, lists RTX 4090 at $0.89/hour.
Thirty minutes would be $0.445 of GPU time. Standard network storage below 1 TB is
$0.07/GB/month: 110 GB is $7.70/month, roughly $0.26/day using a 30-day planning
month. Container disk is additional at $0.10/GB/month. These are public planning
rates, not an authenticated quote or a prediction of render time. Confirm billing
granularity, taxes, disk size and the complete live quote before allocating.

The $5 proposal is an authorization ceiling, not a provider-guaranteed hard stop.
Delayed cleanup or billing can exceed an estimate. The present implementation
blocks new admission/launch against recorded Pod liabilities; it does not enforce
shared-storage spending or automatically cancel an active job on a late overrun.
For this supervised trial, keep the separate $1 storage allowance unavailable to
the Pod grant, prohibit new work, and reconcile both accounts of cost manually.
Do not sign an owner grant until the overall allowance is explicitly approved and
all installation gates pass. Approval does not by itself verify hosting or release.

## Build and hosting route

1. Verify an existing, approved Linux amd64 build machine with a local Unix-socket
   Docker/runc daemon. Use `BUILD_VERIFICATION.md` from the reviewed checkout.
   Record available RAM/disk and image/build-cache requirements before the large
   download. A Windows host is only a candidate through a verified Linux environment;
   no Docker installation or daemon on John's computer has been observed.
2. Execute CPU and GPU build/import/fixture verification and retain manifests,
   immutable image IDs and logs. Publish the tested image to an approved registry;
   verify its remote digest and worker pull access. No paid build service is selected.
3. Choose an existing approved persistent host for the controller. Install the
   reviewed source checkout, optional live services and private secrets; verify
   HTTPS, authentication, durable database/media, quotas and restore. The current
   loopback development server and staging Compose are not production hosting.
4. Deploy the cleanup scheduler outside the GPU, targeting a 15-second poll interval,
   with restart supervision, durable identity and an operator alert. Exercise the
   chosen host's recovery with fictional resources before permitting a real launch.
   A polling target is not a guaranteed termination time. If no suitable existing
   host is available, price a specific alternative separately; do not silently add
   a hosting subscription to this trial.
5. After Runpod sign-in, inspect account/resource inventory read-only and obtain
   actual placement/storage/compute quotes. Stage and checksum the locked 34.2 GB
   model files before paid GPU time where practical, with any staging cost included
   or separately approved. Verify private mounts and worker outbound HTTPS.
6. Bind approved limits, `max_attempts=1`, source/image/model/configuration and host
   acceptance to installed authority. Admit just before dispatch. Run one shot only
   after all required evidence passes, with the independent monitor already active.
7. Save output and evidence, confirm Pod absence, reconcile Pod and retained-storage
   costs, and close temporary storage within its retention window. Keep unresolved
   liability open. A failed render does not authorize another attempt.

## Pending automated billing work

Implement a read-only collector for `GET /v2/billing/pods`, mapped to persisted Pod
identity. Use aligned time windows, retain the original evidence, deduplicate
overlapping snapshots, use decimal cumulative amounts and ingest only new deltas.
Handle delayed charges, mismatched resources, rate limits and decreasing totals
without inflating available budget. The API exposes time buckets, not a documented
final-invoice closure signal; an empty or unchanged response must not settle a job.
Shared-volume charges need separate accounting. Until this work is deployed and
verified, a trusted operator must reconcile provider evidence and sign receipts.
No actual bill was retrieved in this review.

## Next recipient and owner decisions

Command Center coordinates B01 build evidence, B02 deployment/cleanup and B05 host
acceptance before B06. Existing 158 controller and 36 worker test results remain
source evidence; no behavior changed and those suites were not rerun for this
documentation review. Proposal JSON status/arithmetic, unchanged image-gate records,
documentation-only diff and whitespace checks passed. No CI workflow was present
or triggered. Actual image/CUDA/host acceptance remains pending.

John: approve or revise **$5 total / 30 minutes / one attempt**, sign in to Runpod,
and identify an existing Docker-capable build machine if one is available. These
are independent inputs. Sign-in alone does not authorize spending; budget approval
does not authorize a new subscription or remove the release/hosting gates.

Sources checked November 15, 2026:

- https://www.runpod.io/pricing
- https://github.com/Wan-Video/Wan2.2#run-text-image-to-video-generation
- https://docs.runpod.io/api-reference-v2/billing/get-pod-billing-history
