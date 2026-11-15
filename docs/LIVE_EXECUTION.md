# Trusted live execution and delegated billing

The source now connects signed admission, Runpod v2 lifecycle, scoped remote workers and a separate live ledger. There is a callable execution path when trusted host code installs all required authority and transport. No such installation, real grant, account request, GPU run or spending occurred during this batch. Local tests inject fictional HTTP responses, signatures and build-verifier results; synthetic media is not Wan inference evidence.

## Installation and launch boundary

`LiveExecution(admission, runpod_token=None, transport=None, billing_keys={})` accepts an exact trusted `LiveAdmission`. With no account token or explicit transport, provisioning fails before any request. Production host wiring would supply `https_transport()` only after a separately reviewed deployment. Neither Studio HTTP requests nor worker requests can install this service, keys or transport. There is no public launch or billing-ingestion route.

`provision(owner, project, batch, host_envelope, worker_token=...)` loads the stored signed configuration and uses the existing lifecycle compare-and-set. In the same transaction as queued → provisioning it:

- Re-verifies current installed owner signature, source inventory, cap/runtime and latest project grant.
- Verifies installed build evidence and separately signed host acceptance against exact image, source, configuration, endpoint and storage.
- Checks cumulative project spend plus unsettled residual reservations, including older grants and late charges.
- Verifies the queued job's scoped worker credential and expiry cover the original deadline.
- Stores only the credential ID and signed host envelope, and marks dispatch attempted before sending POST.

Failure rolls back the marker and binding. A crash after this transaction is uncertain even if POST never reached Runpod; reconciliation never blindly creates again. Once provisioning, subsequent calls only find the original scoped allocation. They need no fresh token, host signature or owner grant. Exactly one GPU-create attempt is made per admitted job. Worker attempt retries use the original Pod/deadline/reservation; they do not authorize replacement Pods.

## Worker bootstrap

Trusted host code constructs `WorkerTransport(control, real_jobs=execution)` and issues a scoped expiring token while the job is queued. The signature/source checks apply to that queued authority. Claims return no work until durable resource reconciliation and canonical rendering state agree. A worker that starts inside the create-response window can safely poll authenticated empty claims.

The signed launch profile must use exactly:

```json
{"cmd":["worker","--output-root","/worker","--weights","/models","--result","/worker/result.json","--claim-wait-seconds","60"]}
```

The image's default entrypoint is `python -m workers.gpu.cli`; an explicit entrypoint must match. Runtime must exceed 60 seconds. The bounded startup wait is part of the original runtime, not an extension. It retries only successful empty claims, never authentication or network failures. This launches one worker operation, not a resident multi-job service.

Only the transient POST environment receives `WAN_WORKER_API_URL` and `WAN_WORKER_TOKEN`. Plaintext tokens are absent from approval, lifecycle and execution-binding records. Existing worker credentials persist hashes only. A lost POST response does not mint or inject another token: the running Pod already received its original environment, or the unknown outcome requires reconciliation. If a host loses the plaintext token before its first POST, it must explicitly replace bootstrap credentials while still undispatched; there is no automatic secret recovery path.

After dispatch, owner grant revocation/expiry prevents new launches but does not erase a reserved running job or disable cleanup. Token expiry/revocation and attempt leases still fence worker operations. Verified completion uses existing artifact byte/media verification and atomically records the take and lifecycle terminal state. Old completion receipts remain idempotent under valid scoped credential authority.

## Independent cleanup and cancellation

`watchdog()` iterates only linked live batches and uses the frozen persisted identity. It does not require a current source inventory, fresh owner approval, host envelope or current model-lock acceptance to find/delete an already-dispatched resource. Durable Pod ID → expected-name mapping comes from scoped lifecycle/link rows. Provider GET and complete paginated inventory must establish absence; deletion acknowledgment alone is insufficient.

The watchdog must be run independently by future host scheduling; constructing the service does not start a background process. `cancel()` closes rendering authority and retains the liability until cleanup and signed final settlement. Existing authenticated Studio cancel/status routes use this executor when installed. Never-dispatched cancellation uses admission's release policy. No public route provisions a Pod.

## Signed billing receipts

`ingest_bill(owner, project, envelope)` is trusted host ingestion only. Keys are installed separately as `key_id: (owner, secret_bytes)` and cannot reuse an owner-approval secret. The signature domain is `wan-live-billing-receipt-v1` followed by a newline and canonical payload JSON, HMAC-SHA256 lowercase hex. Receipts contain exactly:

| Field | Meaning |
|---|---|
| `id` | Durable globally unique receipt ID |
| `owner`, `project`, `batch` | Exact persisted reservation scope |
| `provider_resource_id` | Exact observed lifecycle Pod ID, or null for an undispatched zero-bill closure |
| `currency` | USD |
| `kind` | `charge` or `settlement` |
| `amount_cents` | Incremental charge, or final cumulative batch total for settlement |
| `bill_reference` | External reconciler's supporting reference |
| `valid_until` | Future ingestion expiry |

The signer delegates billing reconciliation authority. A valid signature is not direct Runpod invoice verification. See the operator billing document for provider time-bucket limitations. There is no automatic billing fetch or final-invoice detector.

Charge events require an observed resource and a reserved/settled reservation. Released never-dispatched rows cannot receive charges. Explicit settlement requires a terminal batch and confirmed cleanup, cannot reduce previously recorded charges, and releases the remaining estimate. The stored settlement amount is its delta above prior recorded spend. Late charges append after settlement and can exceed the approved cap; those actual charges are retained and block further admission/launch. A changed receipt with a reused ID conflicts; identical replay adds nothing. New grants are total project caps, not additive allowances.

`live_billing_events` stores signed receipts and amounts; `live_execution_bindings` stores credential IDs and signed host acceptance. No signing keys or account token enter backups. Restore revokes grant/worker authority and requires safe terminal settled resource history; unresolved obligations remain non-restorable under the backup policy.

## Remaining operational gates

Source implementation is not deployment. John approved the first-trial $5 total / 30-minute / one-attempt envelope on November 15, 2026; see deployment/first-render-proposal.json. The decision is recorded, but a signed runtime grant is not installed. Installed trust roots, authenticated hosted identity/storage, executed build/GPU acceptance, network-model cache verification, scheduler installation, billing reconciliation and release approval remain pending. Budget estimates are not provider-enforced hard spending stops. Provider outage or cleanup failure retains uncertainty and liability.

Focused tests: `python -m unittest discover -s tests -p 'test_live_execution*.py' -v`. The tests use fictional API transport and delegated signatures. Worker media checks, including actual FFmpeg output where exercised, remain synthetic acceptance evidence.
