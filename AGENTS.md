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
