# Approved L40S fallback and bounded capacity retries

Owner approved the concrete proposal on November 16: RTX 4090/L40S, <=$1.10/hour,
$5 total, 1800 seconds from admission, one one-second render. Implementation
selects a GPU before admission and permits at most three same-profile POSTs only
after exact definitive capacity rejection, with 15-second backoff. Every start
and redacted result is retained durably. No POST resumes after process restart.

All prior trial state and liabilities remain; only the existing exact expired
unknown request exception applies. Source baseline 590a365; installed baseline
d30fa01. Code checks and live deployment/result will be recorded below.

## Verification

- Final root suite: 182 tests passed in 36.612 seconds.
- Deployment/guard/hosting suite: 48 tests passed in 2.015 seconds.
- Shared contract validation, shell syntax and whitespace checks passed.
- The first broad run exposed a misplaced backup audit validation block; fixed
  before deployment. Targeted backup/retry verification: 14 passed in 1.682s.
- No new paid request had been submitted at the implementation checkpoint.

## Deployment and admission

PR #82 merged as bef93c9e27ae6382695701e2e640852c78d79ab0 and is installed.
Upgrade 43946771144 / job 133578443705 passed at 20:09:48 UTC. All three
services are enabled/active and HTTPS checks pass; four historical trials and
all reservations remain. Preparation 43946945751 / job 133579026280 passed.
Admission 43947092891 / job 133579527960 at 20:11:12 UTC created batch
4e87af47cce0477b8750b2e4681b722d, project project-ebb553f81bbb476fa94edae11feb48c1,
L40S in EUR-IS-2 at $1.09/hour. Fixed deadline 20:41:11 UTC (3:41:11 p.m. Eastern).

## Live result — all three allocation requests rejected

Independent guard 43947253491 / job 133580091315 delivered READY at 20:12:05 UTC
and continued refreshing readiness. It also watches the older exact unknown
repair request. Catalog capacity disappeared before launch and later returned at
20:24:25 UTC in the admitted Iceland location. Launch 43949478736 / job
133587835939 verified the running guard and submitted the bounded sequence.

| Response time (UTC) | Request ID | Result |
| --- | --- | --- |
| 20:24:48 | req_26597215-3198-4b99-afd9-dbaea03cdce4 | HTTP 400 explicit no-capacity rejection |
| 20:25:03 | req_4a707063-db24-4961-8c1e-773663f310d2 | HTTP 400 explicit no-capacity rejection |
| 20:25:19 | req_96f87c71-32d7-4f43-8632-2c76e970d6a1 | HTTP 400 explicit no-capacity rejection |

Final controller status: `failed`, cleanup `confirmed`, no Pod ID, zero worker
attempts, zero takes, three allocation requests, reservation `reserved`.
The code stopped at its approved limit. No fourth request or grant reset occurred.
The launch workflow passed because rejection handling completed; GPU validation
did not pass. Full redacted provider explanations and the fresh launch quote are
in [allocation-result.json](allocation-result.json) and
[launch-redacted.log](launch-redacted.log).

Complete Pod inventory was empty after the sequence. Audit records since 20:09
UTC and the 20:00–21:00 UTC Pod billing bucket were empty at the recorded check.
No new GPU runtime occurred. This is not final billing settlement; retain the
$4 reservation and all previous liabilities. The older unknown request remains
unresolved. The independent guard was still running when this evidence was saved,
and keeps its original deadline plus five-minute late-allocation window.

The admitted data-center list contained only EUR-IS-2. Transient L40S quotes also
appeared in Missouri, North Carolina and Texas during monitoring, but could not
change registered authority. See [capacity-observations.json](capacity-observations.json)
for the retained sample (not a complete history). Gather several suitable locations
before the next admission and shorten the preparation-to-launch gap. The capacity
watch remains read-only. Five seconds still requires a successful measured
one-second result; one minute of real footage remains pending.
