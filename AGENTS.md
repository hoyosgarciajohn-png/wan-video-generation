# WAN project instructions

Read README.md, docs/WAN_00_Master_Handoff.md, docs/CONTRACT.md and your assigned issue. Verify the repository, branch and baseline commit before editing. Source ownership is listed in docs/WORKSTREAMS.md.

The product self-hosts Wan on rented GPU infrastructure. Paid generation APIs are outside the approved architecture. Prepare production adapters using fictional fixtures. GPU spending requires a project-specific dollar ceiling and runtime envelope. John approved the first trial on November 15, 2026: $5 total, 1,800 seconds from admission, one five-second shot and one attempt. The approved envelope in deployment/first-render-proposal.json allocates $4 to the Pod and $1 to separately tracked storage. Do not request the same numeric approval again. This does not verify infrastructure or install runtime authority. Keep secrets in environment or service secret storage, and keep model weights and user media outside Git.

Use isolated branches and reviewable pull requests. Coordinate shared contract changes through an issue naming affected consumers. Preserve existing accepted takes and timeline revisions. Namespace every asset and job by project and check ownership at server entry points. Persist job state outside the GPU. Reconcile ambiguous provider creation before retrying and track cleanup independently from rendering.

John subsequently approved starting with one DigitalOcean Basic Regular bundled Linux amd64 server: 1 vCPU, 2 GiB RAM, 50 GiB SSD, $12/month plus weekly percentage-based backups at $2.40/month, total $14.40/month before expected tax. This specific approval supersedes the earlier free-only controller restriction; the former $24 server / $32 ceiling remains withdrawn. Inspect the account and actual checkout first; no duplicate server, larger plan, extra volume, domain purchase or paid add-on is included. Capacity upgrades are possible later but have no approved price yet. Do not request the same initial hosting approval again. Follow deployment/hosting/HOSTING_DECISION.md. The separate $5 / 1,800-second / one-attempt Runpod trial is unchanged.

Automated checks use fictional data. Human-input and creative acceptance take place in the owner's live session and remain explicitly pending until observed. Preserve existing evidence and rerun affected checks when behavior changes. Production deployment requires John’s approval for the specific release.

## Local checks

Python 3.11+ and FFmpeg/ffprobe are required for B00. Install `requirements-dev.txt` in a virtual environment. From the repository root run `python scripts/validate_contract.py --media-root fixtures` and `python -m unittest discover -s tests -v`. Tests must run without cloud credentials. Add targeted regression coverage for lifecycle, tenancy and export changes.

Report the issue, PR, commit, contract version, checks actually run, costs incurred, active resources, remaining gaps and next recipient. Shared chats obtain state from GitHub and the handoff documents. A posted assignment does not establish that another chat has started.

John approved a separate additional diagnostic on November 16, 2026: one one-second shot, one Pod-create/render attempt, $5 additional total and 1,800 seconds from admission. Preserve the consumed first trial and its billing reservation. Use deployment/diagnostic-trial-proposal.json and the isolated diagnostic trial scope; do not request the same approval again. This authorizes its necessary preparation, deployment and bounded execution, not another retry.

That diagnostic is now consumed: batch def5478dc85949139ca1c0ae404f9d1f, Pod hzprkb5xllm8p0, one failed attempt with gpu_out_of_memory, no take, automatic cleanup confirmed. Both historical attempts and unsettled bills must remain preserved. At that checkpoint no third Pod create/render was authorized. PR #69 is merged and its repaired worker image was built and published privately by run 43864992211; see deployment/evidence/2026-11-16-memory-repair-build/. Build/runtime/fixture and registry checks pass, but the new digest is not Runpod-pull or GPU-validated. The controller remains at 8e07ba3; do not treat publication as host deployment or permission for a new paid trial. Use a new isolated owner-approved scope and matching reviewed host source for any later paid validation.

John subsequently instructed starting progressive validation: repaired one second,
five seconds, HD export, then one minute. The new `repair` scope retains the
previously proposed additional $5 / 1800-second / one-attempt envelope, without
resetting either consumed scope. This scope authorizes only one new one-second
validation; later paid stages need measured budgets and separate scoped authority.
The exporter and isolated fictional one-minute rehearsal are authorized implementation.

Progressive operational release 42b3e993 is installed; the hosted one-minute
synthetic rehearsal passed in run 43890910756. Repair batch
249c50635ec84ac38cef0eb66232efed consumed its sole POST at 15:04:38 UTC.
Launch 43892451814 and guard 43892343231 finished with failure, with no Pod ever
observed. Preserve its reservation and unresolved cleanup. Empty inventory and
missing billing are not definitive rejection; the original response was lost.

John now explicitly approved finishing PR #76, reconciling that request before
another submission, allowing multiple eligible data centers under unchanged
hardware/spending limits, and resuming one second, five seconds, then one minute.
The fresh validation scope is prepared at $5 total / 1800 seconds / one create /
one render, but cannot be admitted until all three historical requests are closed.
Do not ask for the same approval again. Deployment is authorized after the existing
cleanup gate passes; do not bypass that gate or rewrite a consumed grant. Subsequent
stages must use measured costs and separate scopes inside the retained limits.
A provider-support reconciliation inquiry is drafted but has not been sent.

John subsequently instructed: "we do not need to wait. we can make a new test in
the mean time". This supersedes the waiting prerequisite above for one isolated
validation, including its necessary deployment, under the unchanged additional
$5 / 1800 seconds / one create / one render envelope. Preserve the old repair
request's failed/unresolved state, expired worker credential and $4 reservation.
Only that exact historical request may be excepted; all other outstanding work
blocks admission. Keep persistent cleanup alive, check provider absence, and bind
the independent new guard to both the new deadline and immediate old-request
cleanup. A maintenance forensic checkpoint is not an approved restore bundle.
The support inquiry was sent to help@runpod.io; see PR #77 delivery evidence.

John next instructed running the one-second GPU test when matching capacity is
available, followed by five seconds. Preparation for the isolated validation now
exists but was not admitted. Refreshing only an unregistered preparation to
include fresh eligible locations is authorized; preserve its previous signed
preparation as evidence and never mutate registered/admitted grants. Verify the
one-second result, measured runtime and cost before the separate five-second stage.

The isolated validation is now consumed: project
project-bad45576e6c840cfbf3f4c633c8e3f87, batch bee9e55b1d4a4f458771ad4ac69c3318.
Its sole POST at 18:52:45 UTC was explicitly rejected (HTTP 400, no matching
capacity), request req_c5b30a44-e3c4-4dd2-becf-5ad5c57063c9. No Pod, worker
attempt or take; state failed and cleanup confirmed. Preserve its $4 reservation
and all older liabilities. Installed source is d30fa01 (PR #80). Launch workflow
43933406724 success means rejection was handled, not that video generation passed.
Never rerun this launch or reset its grant. Hourly matching-capacity automation is
read-only; a future paid attempt requires fresh isolated bounded authority.
Five seconds remains pending successful one-second output and measured feasibility.

John approved the concrete fallback/retry proposal: RTX 4090 or L40S, <=$1.10/hour,
unchanged $5 total / 1800 seconds, one render and at most three allocation requests
with 15-second backoff only after the exact explicit HTTP 400 no-capacity response.
Use the new fallback scope; preserve all four consumed scopes, billing reservations
and the exact old unknown exception. Its signed policy and durable attempt log
prevent resets, duplicate allocations and retry after any uncertain response.
Deployment and one-second execution are authorized. Success on L40S does not prove
the repaired worker's 24GB RTX 4090 memory fit. Later five seconds uses measurements.

The fallback scope is now consumed: batch 4e87af47cce0477b8750b2e4681b722d,
project project-ebb553f81bbb476fa94edae11feb48c1. Installed runtime is bef93c9
(PR #82). Launch 43949478736 submitted three requests at 20:24:48–20:25:19 UTC;
all were explicit HTTP 400 no-capacity rejections. Final state failed, cleanup
confirmed, no Pod, zero worker attempts/takes, reservation retained. Do not replay
the launch, reset the grant or submit a fourth request. The original deadline and
independent guard remain unchanged. All older liabilities and the exact unknown
repair request remain preserved. One-second GPU validation is still unproved.

John approved the reviewed multi-GPU allocation proposal: $4.50/hour maximum,
$5 total ($4 Pod reservation / $1 storage), 1800 seconds from admission, one
one-second render and at most three create requests. Implement, deploy and execute
one fresh `allocation` scope. Eligible GPUs are the reviewed RTX 4090, L40S,
A100 SXM 80GB, H100 NVL and H100 SXM 80GB. Bind the GPU/location candidate list
into signed approval and host evidence before admission. Only explicit capacity
rejection permits another untried candidate. Preserve all five consumed scopes,
the exact historical unknown exception, reservations and independent cleanup.
This supersedes the $1.10 hourly ceiling only for the new scope, never old grants.

The allocation scope is now consumed successfully: project
project-13ccbd8f41ad4f4c94566f6e9e3aa2ca, batch 0a30c22ff1a8493bbe2714ad36cd0321.
PR #84 is installed as 84fe9d2d9e2aad680c825069dd5dc5a84f5314f5. Launch
43977423400 allocated H100 80GB HBM3 Pod ymhk7srf23nend in CA-MTL-1 at $4.39/hour
on its first POST. At 23:32:28 UTC November 16 the controller recorded succeeded,
cleanup confirmed, one take and one worker attempt; complete Pod inventory was
empty. Preserve the successful take and consumed grant. Do not replay this launch.
The final bill is pending; $1.36 is only an elapsed-time compute estimate.
Exact peak VRAM/load/generation metrics were not retained before teardown.
Guard 43976858968 stays active through the original deadline plus five minutes
(23:44:46 UTC), including the exact old unresolved repair request. Preserve all
older reservations and persistent cleanup. A later five-second test must use a
new scoped authority, actual measurements and durable performance telemetry.

John approved PR #86's concrete duration comparison with "yes I approve": one
new H100 scope, $5 additional total ($4 Pod / $1 storage), <=$4.50/hour, 2700
seconds from admission, up to three capacity-only creates and one allocated Pod.
Run 5 seconds then a fresh continuous 15 seconds, one attempt each, identical
settings. Implementation, image publication, deployment and execution are
authorized. Preserve all six consumed scopes and the exact old unknown exception.
Save first video and durable telemetry before the second claim; gate remaining
time and memory. No automatic regeneration or additional rental.

The comparison scope is now consumed: project
project-0ebe9e6ddab243cf8e91924211593c27, batch 1226612319814a0d85c2d0d62a9c4357.
Installed release af3b013 (PR #87), launch 44026660382, H100 Pod 5kolyuk9n1ete3.
One five-second attempt succeeded and its video/telemetry were saved; the 15s
claim was refused for insufficient remaining time (1084.399s available versus
1812.398s required). Memory projection passed. Batch state failed/incomplete;
sole attempt succeeded. Cleanup confirmed and provider inventory empty. Export
44029555013 recovered the original and exact five-second copy after deletion.
Estimated compute $1.7036, current billing pending, reservation retained.
Never replay/reset this grant or extend its 06:29:51 UTC November 17 deadline.
Independent guard 44026572576 continues through 06:34:51 UTC; preserve the old
unknown exception and all seven consumed scopes. No additional rental or render
is authorized. Owner creative acceptance and continuous 15s remain pending.
Read deployment/evidence/2026-11-17-duration-comparison/ for measured results.

John subsequently directed completing the whole 5:40.126 music video as the real
capability test, learning from failures, fixing problems and retrying until done.
This authorizes preparation and corrective retries for the new B07 production;
a short sample alone does not meet the goal. Preserve successful takes and retry
affected work. See docs/B07_FULL_SONG_PRODUCTION.md and issue #8. No new numeric
production budget or rental runtime envelope was supplied. Prepare the full
workflow, but obtain that missing financial scope before paid admission. Never
reset/replay any of the seven consumed grants. The older one-attempt rules remain
historical facts for those scopes; they do not negate the new retry direction.

John then set the B07 production ceiling to $20 total and approved four hours
of GPU usage, with continuous queued rendering and corrective retries. These
numeric approvals are now present; do not request them again. Use a fresh
production scope, one GPU at a time, up to $18 GPU at <=$4.50/hour and $2 storage/
cleanup reserve, with at most four cumulative GPU hours including startup and
retries. Two hours remains the optimization target. Never reset the limits on
retry. See docs/B07_BUDGET_AND_QUEUE_PLAN.md. This authorizes the bounded work;
it does not establish audio-driven worker, resident queue or release readiness.

B07's first production batch `7e89330141794b85827d48341def92fe` failed before
inference on conditioning-audio transfer; zero takes, two failed attempts.
Pod `22hk9nt6u1t76z` is deleted and complete inventory is empty. Preserve this
batch and pending bill. The owner-authorized corrective retry uses the isolated
`singing-recovery` input ownership repair, a conservative pending-liability hold,
remaining project GPU budget and the original 1794919601 absolute deadline.
Never replay the first grant or renew four hours/$20 on retry. CPU verification
must prove service-account readability before another GPU starts. See the B07
budget plan for evidence and the precise recovery constraints.
