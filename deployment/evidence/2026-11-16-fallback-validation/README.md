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
- No new paid request has been submitted at this source checkpoint.
