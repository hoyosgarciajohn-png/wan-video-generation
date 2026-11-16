# Launch rejection handling and reconciliation — November 16, 2026

Issue #7; PR #76. Contract 0.1.0 remains unchanged. The existing operational
release is 42b3e993dc8ac3540d1ae450d287c1a90b555338. New source is prepared,
not deployed over unresolved cleanup.

## Implemented

- Retain bounded, redacted provider detail/title, validation messages, HTTP status
  and x-request-id in the private lifecycle database and operator output. Never
  retain raw bodies, arbitrary headers, validation input or request credentials.
- Documented explicit POST rejections (400, 401, 402, 403, 404, 409, 413, 422, 429)
  fail immediately with no allocation; transport errors, 408, 5xx, malformed
  success and unexpected responses remain ambiguous. No POST retry is automatic.
- Atomic rejection state plus diagnostic survive restart. Existing unknown rows
  gain a null diagnostic, remain unresolved and retain all billing reservations.
- Freeze up to eight distinct currently eligible data centers inside one signed
  launch configuration. Rechecks may use another available member of that same
  list but cannot expand it. Primary region is the first entry; actual location
  remains provider-reported. Existing one-location signatures remain valid.
- A new isolated `validation` scope is prepared for the approved one-second stage:
  $5 total, $4 Pod reservation, $1 storage allowance, 1800 seconds, one create and
  one render, same repaired image/GPU/RAM/CUDA/disk and no added volume. It requires
  all three historical requests to be closed first. No grant has been installed.

The independent guard remains conservative: it cannot infer rejection solely
from empty inventory, and a never-observed allocation still reports unresolved
unless a separate definitive provider response reconciles it. This behavior is
not changed or bypassed by these fixes.

## Exact current blocker

Batch 249c50635ec84ac38cef0eb66232efed has no retained original provider response
or Pod identity. Launch 43892451814 and guard 43892343231 both finished with failure;
there were zero worker attempts and zero takes. Its $4 reservation remains open.
Connected inventory/audit are empty, billing has no trial-window records, and the
console shows a $9.35 balance plus Pods read/write on the enabled wan-cleanup key.
Those are current observations, not proof of the original response or final costs.
The exact request needs provider confirmation before cleanup can be marked closed.

A support request is drafted in support-request.md and has not been sent. No API
key, permission, account balance, Pod, grant, budget reservation or deployed source
was changed during this continuation. No new GPU spending was initiated.

## Verification

See checks.json for completed fictional checks. Root suite covers lifecycle,
tenancy, backup/restore, approvals and export. Targeted deployment checks cover
single-create isolation, stale quotes, fixed region lists and guard behavior.
The historical real-run and hosted synthetic export evidence is preserved.

## Next action

Obtain Runpod's definitive response for the exact request. Reconcile the existing
record with that evidence; retain historical billing liabilities. Deploy the
reviewed source, verify the host, then prepare/admit/guard/launch the isolated
one-second validation. Advance to five seconds and then one minute only after
successful output retention and measured feasibility within unchanged limits.
