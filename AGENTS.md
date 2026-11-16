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
