# Simulated budget and lifecycle orchestration

This increment joins durable budget admission to the existing Pod lifecycle state
machine. It is an executable simulation, not a permission path to rent a GPU.
`SimulationCoordinator` accepts only an instance whose exact type is the built-in
`FakeGpuProvider`. Passing `RunpodProvider` or another provider fails before any
provider call. All approvals are stored with `mode: simulation`. There is no HTTP
approval route, UI spending switch, live provider dispatch, invoice integration or
cloud resource allocation in this increment.

The host must supply an authenticated owner identity to these trusted Python APIs.
Owner/project access is resolved from the existing project database. The simulated
approval records used by tests are not John's authorization for any real charge.

## Authoritative approval and accounting model

`BudgetLedger(control)` persists three tables alongside the project and lifecycle
state: `budget_approvals`, `budget_reservations` and `budget_events`. Money is integer
USD cents. Approval terms are immutable and contain exactly:

- `currency: USD` and positive `approved_cents`.
- `max_runtime_seconds`, between 1 and 86400.
- A timezone-aware `valid_until`.
- The exact fictional launch `profile` object.

A new explicit approval supersedes earlier approvals for future admissions and
new dispatches. It does not modify old terms, refund recorded charges or reset the
project's cumulative spend. Raising a cap requires a new explicit approval record.
Revoking the latest approval does not reactivate an older approval.

The cap applies to cumulative project accounting across approval versions. Each
reservation retains its original estimate. Before final settlement, its outstanding
reserved amount is `max(0, estimate - recorded charges)`. Total commitments are
recorded spend plus these residual reservations. New admissions must fit the
remaining approval. Actual charges are always recorded, including amounts over a
cap and late charges after a previous final bill. Overcommitment blocks new
admissions and new queued-to-provisioning dispatch transitions.

For example, in a fictional 100-cent project, an 80-cent reservation leaves 20
available. A 20-cent interim charge changes the split to 20 spent plus 60 reserved,
so availability stays 20. Confirmed deletion does not change that split. An explicit
final cumulative bill of 60 records the remaining 40 and releases the residual
reservation, leaving 40 available. A later 50-cent charge raises cumulative spend
to 110, records the 10-cent overrun and blocks more admission under that cap.

These numbers are accounting controls, not price forecasts or a guaranteed dollar
hard stop. The reservation may underestimate actual usage. Provider billing can
arrive after shutdown; a dispatch authorized before a later charge can already be
in flight. Runtime deadlines and cleanup requests cannot guarantee a provider-side
maximum bill. No such guarantee is claimed here.

## APIs and transaction boundaries

```python
coordinator = SimulationCoordinator(studio, FakeGpuProvider())
approval = coordinator.budget.approve(owner, project_id, terms, "approval-key")
reply = coordinator.submit(owner, project_id, {
    "approval_id": approval["id"],
    "shot_ids": [saved_shot_id],
    "expected_revision": workspace_revision,
    "reservation_cents": estimate_cents,
    "runtime_seconds": requested_runtime,
    "idempotency_key": "queue-key",
})
batch_id = reply["batch"]["id"]
coordinator.provision(owner, project_id, batch_id)
```

`submit` freezes persisted shot revisions and the stored approval profile. The
reservation and the `pod_batches` row are inserted in one SQLite `BEGIN IMMEDIATE`
transaction. A failed insertion rolls back both. A process cannot leave a
dispatchable queue row with no reservation. Runtime starts at admission; queueing
time consumes the runtime envelope. Requested runtime must fit both the approved
maximum and expiry. The deadline is not extended on restart.

`Lifecycle.provision` now accepts an optional `authorize` callback. The coordinator
always supplies one, and it runs inside the queued-to-provisioning transaction.
It verifies current approval identity, simulated mode, revocation/expiry, deadline,
unsettled reservation and project commitments before authorizing a new create.
A cap already exhausted by recorded spend also blocks new dispatch, even when a
reservation has no residual amount left.
The default keeps existing lifecycle callers compatible. This callback is not a
production authorization adapter and must not be used to bypass the coordinator.

The coordinator reuses `Lifecycle` for create, find/reconciliation, cancellation,
terminal state, deadline and deletion verification. If create times out, its
provisioning state is durable and retries search for that allocation; they do not
blindly create another Pod. Reconciliation remains permitted even after approval
revocation or an overrun, because it does not authorize a new create. Independent
watchdog calls continue until cleanup is confirmed. A canceled/expired queued job
can prove that it was never dispatched. Unknown dispatched creation cannot be
considered cleaned up merely because one inventory response is empty.

```python
coordinator.cancel(owner, project_id, batch_id)
unresolved_batch_ids = coordinator.watchdog()
coordinator.budget.record_charge(
    owner, project_id, batch_id, incremental_cents, "fictional-bill-ref", "charge-key"
)
coordinator.budget.settle(
    owner, project_id, batch_id, final_cumulative_cents, "fictional-final-bill", "settlement-key"
)
```

`finish(owner, project, batch, outcome)` is a trusted simulation hook for terminal
render outcome; it does not prove a real render or create a take. `watchdog()` is a
trusted system operation, intended to run independently of rendering. It refuses
unmanaged lifecycle rows in its simulation database.

Settlement requires a terminal batch, confirmed cleanup (or confirmed no dispatch),
and an explicit cumulative bill reference. Deletion alone never releases residual
liability. Settlement cannot reduce already-recorded charges. Additional charges
after settlement use `record_charge`; an earlier settlement receipt remains
unchanged. Monetary events are append-only through these APIs. Refunds or negative
corrections are not implemented.

Approval, admission and billing receipts use scoped idempotency keys. Identical
replay returns the original identity even after creator edits or later billing;
changed input with the same key conflicts. New receipt keys are new accounting
events, so a future invoice adapter must derive stable keys from authoritative
provider events. It must not invent a new key each time the same invoice is polled.

`status(owner, project)` returns the active approval, cumulative spend, residual
reservations, unsettled count, available cents, actual overrun, overcommitment and
admission-blocked flags. Coordinator responses also contain the current durable
lifecycle row and parsed frozen snapshot. Ledger data is separate from the public
fixture bundle: fixture generation continues to have zero cost, and simulated
reservations do not masquerade as real generated takes.

## Recovery, backup and remaining production work

Controller restart uses the same SQLite rows. The fake provider's inventory is
process-local; tests retain its instance when modeling a controller restart. A
fresh empty fake inventory does not establish the absence of a previously unknown
allocation. It leaves cleanup and liability unresolved, as intended.

Backup includes settled simulation history, validates its ownership and cumulative
settlement arithmetic, and preserves late-charge overruns on restore. It refuses
any unsettled reservation, including a resource already deleted but still unbilled.
Existing backup checks also reject unconfirmed provider cleanup. Recovery does not
convert unsettled liability into available approval.

Before a real Runpod benchmark can use any of this architecture, separate work must
provide all of the following:

1. John's explicit project-specific real spending ceiling and runtime envelope,
   captured by an authenticated operator approval workflow. Simulation approvals
   must never be migrated into live spending authority.
2. An audited live dispatch adapter and launch profile, with pinned runtime/model,
   launch-time configuration validation, authoritative resource identity, supported
   termination behavior and independent watchdog operation.
3. A trustworthy estimate/reservation policy, provider usage and final-invoice
   ingestion, stable billing-event keys, delayed-charge reconciliation and explicit
   handling of ambiguous allocation outcomes. No accounting record may disappear
   merely because a worker or Pod shuts down.
4. A bridge from lifecycle queue snapshots to canonical worker attempts and leases,
   worker credential issuance, authoritative completion verification, private object
   upload/download access and durable media outside the temporary GPU.
5. Failure rehearsal for real transport and storage, an isolated limited benchmark,
   observed output integrity and confirmed resource deletion. This requires the
   approved spending terms before any real resource is rented.

## Checks

```sh
python -m unittest discover -s tests -p 'test_budget.py' -v
python -m unittest discover -s tests -p 'test_budget_integration.py' -v
python -m unittest discover -s tests -p 'test_b02_lifecycle.py' -v
```

Tests use fictional profiles, bills and provider inventory. They exercise atomic
reservation rollback, concurrent admission and charge replay, frozen terms,
cross-owner boundaries, real-provider rejection, late overruns, queued launch
blocking, revocation, independent deadline cleanup, unknown create recovery,
confirmed deletion without settlement, retained charges and restored accounting.
No provider endpoint is contacted and no actual charges are incurred.
