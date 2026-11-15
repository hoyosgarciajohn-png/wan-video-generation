# Local fixture integration

`ControlService` in `service.py` persists project interchange bundles, admission
idempotency records, and completion receipts in SQLite. It is a trusted Python
application API, **not an HTTP server or authentication system**. An authenticated
host must resolve owner identity and issue a worker capability for one assignment;
never expose `owner_id` or capability construction as caller-controlled HTTP fields.
SQLite transactions serialize claims and commit output assets and takes together.

```python
from services.controller.service import ControlService
from workers.gpu.worker import run_once

service = ControlService("control.sqlite", "durable-assets")
service.seed(owner_id, input_bundle)  # new project, verified assets and shots only
batch = service.admit(owner_id, project_id, fixture_batch_record)
client = service.worker_client(owner_id, project_id, batch["id"], "fixture-worker")
claim = client.claim()
if claim:
    result = run_once(claim, client, "durable-assets")
bundle = service.bundle(owner_id, project_id)
```

The full schema batch input freezes exact persisted shot revisions. ID, approval
time, execution state and cleanup state are service-owned. Matching original
admission input returns the existing batch even after restart; conflicting input
with the same project/idempotency key is rejected. Fixture mode is immediately
renderable and has no provider resources, so cleanup is confirmed with zero cost.

The callable transport matches `workers.gpu.client.WorkerClient`:
`claim()`, `heartbeat(attempt, progress)`, `complete(attempt, manifest)`,
`fail(attempt, "render_failed"|"worker_failed")`. Claim envelopes contain
`contract_version`, `project`, `batch`, `attempt`, `shot_snapshot`, `input_assets`.
Leases last 30 seconds by default (bounded by batch deadline), heartbeat extends
only an active assignment, and retries get fresh attempt and lease IDs, up to two
attempts per shot by default. Claim operations reconcile expired leases and batch
deadlines. A caller polling only `bundle()` gets persisted status, not a live clock
reconciliation; a hosted scheduler is not implemented. Cancel fences active work.

The worker writes to a shared persistent filesystem, atomically publishing
`projects/{project_id}/attempts/{attempt_id}/output.mp4` before completion. The
controller independently checks namespace, owner, size, SHA-256, stream count,
codec, dimensions, frame count, frame rate and duration before committing a take.
It rechecks expiry after inspection. Identical completion replay returns the saved
take after restart; changed manifests are rejected. The host must enforce mount
permissions: trusted workers can write their assignment's output; untrusted clients
must not have arbitrary filesystem write access. This is a shared-mount fixture
transport, not remote upload URLs or immutable object-store verification.

`review()` server-stamps a review. `save_timeline()` creates the next immutable
revision and checks approval and trim relationships. `save_export()` accepts only
a completed local export with verified uploaded bytes and its output asset; it is
not an asynchronous export queue. `seed()` is a fixture bootstrap operation and
strips all supplied execution/history records. Legacy fixture input object keys
are accepted within the asset root; production upload namespacing is not provided.

## Deliberate release boundaries

Runpod admission is rejected. `Lifecycle` and the Runpod provider adapter remain
separate components: provider allocation/cleanup is not connected to this fixture
service. There is no hosted authentication, HTTP route adapter, remote object
storage, managed database, budget approval/reservation/settlement ledger, billing
reconciliation, or live Studio API transport. Do not enable paid mode by removing
the admission guard. Paid integration must first resolve authoritative approvals,
atomic reservations and retained unsettled liability after shutdown, independent
cleanup, and explicit project-specific spending/runtime approval.

Synthetic validation: `python -m unittest discover -s tests -p 'test_b02_service.py' -v`.
The suite includes the actual fixture renderer, durable restart and completion
replay, simultaneous claims, retry exhaustion, stale-worker fencing, ownership,
missing upload rejection and disabled paid admission. No cloud calls or paid GPU
execution are used. Human creative acceptance and production readiness remain pending.
