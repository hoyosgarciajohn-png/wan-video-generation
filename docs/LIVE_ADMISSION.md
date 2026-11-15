# Authenticated live admission, dispatch disabled

This batch implements real approval verification and durable queued job admission in source. It does not launch a Pod, enable a Wan worker, or supply actual owner approval. Fictional signatures in automated tests are not authority for John's project. No account key, owner signing key, hosted acceptance, or spending allocation has been installed.

## Trust boundary

`LiveAdmission(studio, approval_keys={}, host_keys={}, build_evidence=None)` is an optional trusted host component. A key mapping has `key_id: (owner_id, secret_bytes)` entries; keys contain at least 32 bytes and are provisioned outside the database and backups. No key-generation, signing, or client-key installation endpoint exists. A signature establishes the installed key holder's delegated authority for that owner, not proof that John personally signed it. Host administrators who can install keys or change code control this trust boundary. See [operator responsibilities](../deployment/LIVE_APPROVAL_OPERATIONS.md).

`StudioAPI(..., live_admission=service)` accepts only an exact `LiveAdmission` instance sharing its controller. With no service installed, live routes return 404. The existing provisioned login token establishes an HttpOnly session; same-origin mutation checks remain required. The HTTP adapter derives the owner from that session. A submitted owner value cannot replace it. Foreign projects are unavailable; wrong-key, wrong-owner and invalid-signature requests are rejected without exposing key material.

## Signed owner envelope

Envelope keys are exactly `key_id`, `payload`, `signature`. The signature is lowercase hex HMAC-SHA256 over UTF-8 bytes of `wan-live-owner-approval-v1`, a newline, then `services.controller.service.canonical(payload)`. This canonical JSON uses sorted keys, compact separators and rejects nonfinite numbers. Verification uses constant-time comparison. Server-installed key identity must match the session owner.

Payload keys are exactly:

| Field | Constraint |
|---|---|
| `id` | Stable grant ID, 1–200 letters/digits/underscore/hyphen |
| `owner`, `project` | Exact authenticated owner and accessible project |
| `currency`, `approved_cents` | USD and positive integer cents, never boolean |
| `max_runtime_seconds` | Integer 1–3600 |
| `valid_until` | Future timestamp |
| `profile` | Exact pinned Wan worker configuration accepted by `RealJobBridge.configuration_hash` |
| `launch_profile` | Strict v2 profile accepted by `validate_launch_profile`, matching image/GPU/region; empty `env` |
| `source_sha256` | Exact current `preflight._sources()` inventory, including model lock and admission/authentication source |

Approval artifacts contain no runtime worker or account credentials. A future trusted dispatch path must inject short-lived worker credentials after approval verification. The configuration hash includes the complete validated launch profile, worker profile and model lock, so disk, mounts and commands are bound as well as image and GPU.

The immutable signed envelope is stored in `live_approvals`. Reusing an ID with changed content conflicts. Revocation is sticky: replay cannot clear it. Restore revokes approvals in the restored copy; reinstalling original keys does not reactivate revoked grants. New authority requires a new grant ID.

## HTTP and callable contract

All routes below begin `/v1/studio/projects/{project_id}/live`. Mutations require the existing Studio session, origin and `X-WAN-Request: studio` checks. No signing, provider factory, launch or live-worker route is exposed.

| Route | Request | Result |
|---|---|---|
| POST `/approvals` | Signed envelope | Grant ID, cap/runtime/expiry, configuration hash, `dispatch_enabled:false` |
| POST `/approvals/{id}/revoke` | `{}` | Sticky revocation |
| POST `/batches` | `approval_id`, one `shot_ids` entry, `expected_revision`, `reservation_cents`, `runtime_seconds`, `idempotency_key` | Canonical queued batch and reservation state |
| GET `/batches/{id}` | — | Scoped persisted status |
| POST `/batches/{id}/cancel` | `{}` | Canceled/confirmed and reservation released only if never dispatched |

Callable methods use `(owner, project, ...)`, where owner must come from the host authentication layer. They are not standalone authentication endpoints. Admission freezes the saved shot, validates the worker claim against the pinned model profile, and inserts canonical bundle, live reservation, lifecycle row and live link in one SQLite transaction. Any validation or persistence failure rolls back everything. Idempotency retries return the original job across restarts, including canceled history; changed requests conflict.

New admission re-verifies installed signature, expiry and current source. The latest installed grant defines a total project cap, not an additional allowance. Outstanding live reservations across all grants count against it. Simulation approvals/reservations cannot be promoted or consumed. Runtime must fit the signed cap and expiry. This is an estimate ledger for never-dispatched jobs, **not an implemented live billing ledger or provider-enforced dollar stop**.

Cancellation releases only a lifecycle row that is queued/canceled, has no Pod ID and has disabled dispatch provenance. Uncertain or dispatched rows cannot release liability. Revocation prevents new admission without erasing existing reservations; explicit cancellation releases never-dispatched jobs. No automatic deadline scheduler for pending live admissions is installed; their reservations remain until cancellation. Fixture workers skip runpod jobs. The simulation cleanup watchdog scopes itself to simulation reservations, so a pending live job does not stop existing simulation cleanup.

Admission currently requires a reviewed source checkout with Git and the build-verifier modules available. The standard staging container does not contain that checkout and does not install this optional service. Ordinary controller and backup imports remain usable without those build tools. Containerized authority provisioning requires a separate reviewed packaging change.

## Evidence gate and remaining work

`prepare_provider(owner, project, approval_id, host_envelope)` cannot return a provider. It verifies current owner authority, installed build evidence using the existing source/image/log/fixture consistency verifier, and separately installed host authority. The host domain is `wan-live-host-acceptance-v1`; payload fields are exactly owner, project, configuration hash, current source inventory, build manifest hash, expiry, HTTPS worker endpoint and durable storage identity. These bind the delegated host acceptance to the approved deployment; a caller-supplied PASS boolean or preflight report has no authority.

Even when these checks succeed, it raises `AuthorityError` because live worker dispatch is not installed. There is no HTTP transport assignment, factory enable flag or fallback fake-to-live conversion. Build-log consistency alone is not actual GPU or registry acceptance. Before enabling live execution, a future reviewed batch must implement production worker callbacks, explicit launch/reconciliation authority, independent cleanup, live billing/settlement retention, authenticated host acceptance procedures and resource closure. Actual owner cap/runtime, image/GPU and hosted evidence remain absent.

## Validation

`python -m unittest discover -s tests -p 'test_live_admission*.py' -v` uses fictional keys and synthetic projects. It checks authenticated session ownership, malformed/tampered grants, source changes, expiry, race-safe admission, rollback, replay, cross-grant caps, sticky revocation, cancellation, backup recovery and permanently disabled dispatch. A mocked host/build gate test establishes only that verified inputs still cannot activate a provider; it is not GPU evidence.
