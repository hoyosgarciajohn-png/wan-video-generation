# Canonical real-profile job bridge — synthetic test authority only

The data path is now connected: one admission transaction creates a canonical
`runpod`-mode batch, its frozen Wan model/shot profile, a budget reservation, a Pod
lifecycle row and a durable authority link. Scoped workers can claim its attempts,
upload media and complete a take through that link. Verified final completion
marks the existing lifecycle terminal in the same transaction, making it eligible
for independent cleanup. Accounting and cleanup remain distinct.

Its only enabled factory is named `RealJobBridge.for_testing(studio, FakeGpuProvider())`.
It accepts the exact built-in fake-provider type. The normal constructor is disarmed
and there is **no live factory**. Simulated approvals and `mode: test` links never
constitute permission for real GPU spending. No test performed Wan inference.

## Trusted configuration and admission

```python
bridge = RealJobBridge(studio)  # disarmed: submit/provision/worker authority refused

# Explicit synthetic integration rehearsal only:
bridge = RealJobBridge.for_testing(studio, FakeGpuProvider())
```

The trusted server/test creates an immutable BudgetLedger approval whose `profile`
contains exactly:

- `model_profile`: the complete current `workers/gpu/model.lock.json` profile.
- `image_ref`: an immutable registry image digest.
- `gpu_type`, `gpu_count: 1`, `region` and `storage_id`.
- `worker_endpoint`: an HTTPS origin without credentials, query or fragment.

The rehearsal checks these values and binds their content plus the complete model
lock to a configuration hash. Its test image/provider/host values are explicitly
fictional: the hash does not certify a built image or a real deployment. The
existing simulated approval mode is preserved in the ledger and never upgraded.
An eventual live activation mechanism must independently authenticate real owner
approval, build evidence, host/storage configuration and provider authority.

`submit(owner, project, request)` accepts the same six queue fields as the
simulation coordinator: `approval_id`, `shot_ids`, `expected_revision`,
`reservation_cents`, `runtime_seconds` and `idempotency_key`. It validates the
persisted shots against the exact real worker contract: pinned profile, 24 fps,
1280×704 or 704×1280, 50 steps, at most five seconds and at most one validated image
reference. It does not accept a caller-provided model substitution or a test/live
boolean. The public `ControlService.admit` and Studio render-command paths retain
their fixture-only behavior.

The canonical batch, reservation, lifecycle row and `real_job_links` record commit
in one SQLite transaction. An invalid profile or failed insertion rolls back all
four. Idempotency replay returns the same batch and preserves the original frozen
shot revisions even after creator edits. Each link records `mode: test`, approval
identity and configuration hash; status additionally returns
`provenance: synthetic_test_only` so the synthetic provenance is explicit.

## Worker and lifecycle linkage

The trusted host can install the bridge explicitly:

```python
transport = WorkerTransport(control, real_jobs=bridge)
# Or StudioAPI(..., real_jobs=bridge) in a trusted test server.
```

Default worker transport still rejects non-fixture batches. The optional argument
must be the exact bridge type bound to the same ControlService instance. Its
authorization checks persisted scope, simulated approval, test provenance,
configuration hash, pinned profile and agreement between canonical and lifecycle
state. Unknown/unlinked batches are denied. Direct trusted ControlService worker
clients for `runpod` batches must supply both server authorization and lifecycle
synchronization callbacks; omission cannot silently bypass the bridge.

`provision` reuses the existing `SimulationCoordinator`/`Lifecycle` dispatch gate,
including atomic cap/revocation checks and uncertain-create reconciliation. It then
reconciles the canonical batch with the observed lifecycle. A crash between those
steps leaves a durable lifecycle record; `status`, `provision` replay or `watchdog`
can reconcile it. It does not blindly create another Pod.

The worker request/claim and artifact transport shapes are unchanged. During
completion, ControlService verifies the actual uploaded bytes, codec, dimensions,
frame count, duration and active lease. Its server-only synchronization callback
sets the lifecycle outcome before the same transaction commits. A fault in that
lifecycle write rolls back the new asset, take and completion receipt. An identical
completion can be retried safely. The configured model profile describes the
requested job contract; media validation alone does not prove a particular model
produced the pixels. Test results remain labeled synthetic by the authority link.

`watchdog()` reuses the existing independent lifecycle cleanup engine, then updates
canonical state, provider ID, cleanup status and budget values. Successful rendering
does not imply confirmed deletion, and confirmed deletion does not imply a final
bill. The host must run this watchdog independently of workers; no new hosted
supervisor or deployment is provisioned by this module.

`cancel` updates lifecycle intent and reconciles canonical state, fencing worker
mutation even across the reconciliation gap. Runtime deadlines remain bounded by
the immutable approval. Revoking/expiring an approval blocks new admissions and
new dispatches; it does not automatically cancel an already provisioned reserved
job. Explicit cancel or its deadline performs that operation, preserving the
existing accounting policy.

## Billing and recovery

`record_charge` and `settle` retain the existing ledger APIs and append-only receipt
rules. Their bridge wrappers reconcile canonical batch budget values afterward.
The ledger remains authoritative during any brief reconciliation gap. Cleanup
failures and unknown allocation retain unsettled reservation liability. A final
settlement still requires confirmed cleanup and explicit cumulative billing
evidence; late charges remain recorded and may block future admission/dispatch.

The fake provider inventory is process-local; controller-restart tests preserve
that inventory object. This demonstrates durable controller reconciliation, not a
real provider control plane. Restoring settled synthetic history preserves its
`mode: test` linkage and pinned profile. Backup refuses unresolved lifecycle or
monetary obligations, validates the authority/configuration/canonical snapshot
relationships and revokes worker credentials in its recovery copy. Merely creating
a disarmed bridge with no linked jobs does not prevent an otherwise valid backup.
No restored test link can activate a live provider.

## Evidence and the remaining boundary

```sh
python -m unittest discover -s tests -p 'test_real_jobs.py' -v
python -m unittest discover -s tests -p 'test_real_jobs_integration.py' -v
```

The targeted and independent tests generate an explicit synthetic H.264 clip at
1280×704 and 24 fps, with 25 frames for a 1000 ms requested shot under Wan's 4n+1
frame rule. They send it through the actual scoped artifact/completion path, then
verify a canonical take, lifecycle terminal transition, failed/retried deletion,
confirmed cleanup, retained liability, final settlement and recovered history.
They also exercise concurrent admission, transaction rollback, default disarming,
unchanged public fixture guards, revoked-admission semantics and uncertain create
reconciliation. No Wan weights, CUDA inference, provider API or paid resource is
used by these tests.

The previously missing canonical queue→attempt→verified take→cleanup/accounting
connection is implemented and rehearsed. Still missing for an actual first run:
authenticated live owner approval with a specific dollar/runtime envelope, verified
built image and host/storage evidence, a distinct reviewed live authority/provider
factory, real usage/final-invoice ingestion, and a supervised owner-approved GPU
benchmark with observed deletion. John has not supplied the real spending terms.
Neither the preflight attestation files nor the simulated budget records fill that
absence. Live provider dispatch stays disarmed until those separate steps exist.
