# Connected fixture rendering and take review

This B05 increment connects the authenticated Studio to the actual synthetic worker.
It is local development evidence; it does not execute Wan inference or rent a GPU.
Bundle 0.1.0 and workspace 1 remain unchanged. Read STUDIO_API_V1.md for session,
Origin/Host checks, owner identity, persistence and protected media access.

## Commands

| POST route | JSON request | Response |
|---|---|---|
| /v1/studio/projects/{project}/batches | shot_ids, expected_revision, idempotency_key | batch, workspace |
| /v1/studio/projects/{project}/batches/{batch}/cancel | {} | batch, workspace |
| /v1/studio/projects/{project}/takes/{take}/review | decision, expected_revision, idempotency_key | review, workspace |

Render/review request fields are exact: no client execution mode, model, cost or
owner fields are accepted. All routes use the existing session and CSRF protections.
Unknown/foreign projects, batches and takes return 404; stale revisions or reused
keys with different payload return 409; unsupported input returns 422.

Admission freezes the selected persisted shot revisions in one SQLite transaction.
It selects fixture-v1, a zero-dollar budget, confirmed no-provider cleanup and a
server-controlled ten-minute deadline. Supported shots are 1–5000 ms, 320×180, 24 fps,
one step and no reference assets. The worker creates silent blue test footage
matching the requested duration. The result is plainly labeled synthetic in Studio.

The same project-scoped idempotency key and exact original payload return the same
batch/review identity after process restart or later creator edits. Changed payloads
conflict. The response contains a fresh authoritative workspace, not an old snapshot.
Submit/cancel do not advance the creator revision; review does. Approving a take
atomically records its review and selects it for that shot. Rejecting a selected take
clears that selection. It never silently replaces an existing historical timeline.

Cancellation is idempotent. It fences active attempts and prevents their completion
from publishing a take. A completion that already committed can win the race;
canceling that completed batch returns its existing succeeded state. Outputs from
canceled work can remain unreferenced on disk; storage retention/garbage collection
is an explicit later operational task, not claimed by this batch.

## Background execution and recovery

The local HTTP CLI now starts FixtureRunner automatically. It scans durable fixture
batches, reconciles deadlines/leases, claims work and invokes workers.gpu.worker.run_once.
The worker writes durable bytes; ControlService verifies them before committing takes.
A nonblocking POSIX file lock permits one renderer per database across processes.
The runner drains one attempt at a time, rechecking the database between jobs.

Abandoned claims become eligible only after their lease expires; retry count is
bounded by the existing controller policy (default two attempts). A restarted runner
finds queued eligible work without a browser session. Rendering success is distinct
from scheduler availability. A graceful stop finishes the current attempt; abrupt
termination relies on lease recovery. This is a Linux/POSIX local process, not a hosted
scheduler, Runpod lifecycle service or container-build verification.

## Studio behavior

Save creator edits before submitting or reviewing. The UI submits commands over HTTP,
shows server batches, polls active work when the workspace is clean and preserves the
current project/tab. Poll responses cannot overwrite edits begun after a request.
Pending commands retain their original identity and payload for an explicit retry
following an ambiguous network/server error. The UI does not run the fixture advance
simulator in connected mode. Imports and final exports remain disabled until their
transports are implemented. The isolated ?mode=fixture rehearsal remains separate.

## Evidence and boundaries

- Python root discovery: 70 tests PASS, including 6 command/runner tests and 3 real TCP
  command tests. These exercise actual rendering, approval/rejection, frozen inputs,
  duplicate requests, concurrent admission, cancellation fences, retries/deadlines,
  runner exclusion, restart, tenant isolation and protected download checksums.
- Actual TypeScript StudioClient → local Python HTTP → background renderer → media
  download → review/replay → cancellation → logout: PASS using
  `cd apps/studio && node --import tsx ../../scripts/check_studio_client.mjs`.
- Studio: 13 model/client tests, 13 DOM tests, build and formatting PASS, recorded in
  apps/studio/B03_EVIDENCE.md. Browser acceptance remains unverified under the known
  Chromium socket restriction; TCP/DOM tests do not establish browser layout/playback.
- Unchanged GPU-worker/long-export evidence from prior checkpoints is retained.

No cloud resources were provisioned and GPU spend is $0. Next B05 work: protected
reference/audio uploads and timeline assembly/export commands, followed by hosted
storage/identity and queue-to-Pod budget/lifecycle integration. Real Wan rendering
requires the still-pending container build and owner-approved B06 budget/runtime cap.
