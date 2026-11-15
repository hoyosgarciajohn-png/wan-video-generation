# Shared contract 0.1.0

`contracts/bundle.schema.json` defines the wire records through reusable `$defs`. `fixtures/project.json` is a complete fictional project bundle. `scripts/validate_contract.py` checks record relationships in addition to JSON Schema types. B01–B04 consume these definitions and coordinate changes through the Command Center.

## Record semantics

All durations and offsets use integer milliseconds. Frame rates use integer numerator/denominator pairs. USD budget values use integer cents. Identifiers are opaque strings. A batch freezes shot snapshots, prompts, reference asset IDs, seed/settings and model revision at admission. Later edits to a shot create a new revision and future batch. Creative regeneration creates a new attempt and take.

Takes describe immutable render outputs and reference assets by ID. Asset records carry byte size, checksum and storage object key. Review records carry the creative approval decision independently. Timeline items select approved takes with explicit trim intervals. Exports capture a timeline ID and revision. Timelines include created_at, and their approvals are evaluated at that revision time. Historical revisions must remain readable.

The fixture bundle is a point-in-time development interchange. Runtime services must enforce identity and transitions transactionally. Passing the bundle validator establishes static consistency. It supplies no authentication, concurrency control or provider verification.

## Backend interface to implement in B02

Base prefix `/v1`. Every project route requires authenticated project access derived from server identity. Use the schema record shape for corresponding response objects. List responses use `{items, next_cursor}`. Errors use `{code, message, request_id}` without credentials or private provider diagnostics.

| Method and route | Input | Result and semantics |
|---|---|---|
| POST /projects | title, kind | Project with server-generated ID, owner and runtime cap. |
| GET /projects/{project_id} | — | Project for an authorized member. |
| POST /projects/{project_id}/assets | staged upload metadata | Server-owned asset record after checksum and size verification. B02 defines the upload transport. |
| POST /projects/{project_id}/shots | scene_id, prompt, reference_asset_ids, target_duration_ms, settings | Shot revision 1. |
| PATCH /projects/{project_id}/shots/{shot_id} | expected_revision and editable fields | Incremented revision, or 409 if stale. |
| POST /projects/{project_id}/batches | shot IDs/revisions, model profile ID/revision, execution mode, deadline, budget approval reference; Idempotency-Key header | 202 with frozen batch, or existing batch for the same key and canonical input. 409 for a reused key with different input. |
| GET /projects/{project_id}/batches/{batch_id} | — | Render state, attempts and cleanup state. |
| POST /projects/{project_id}/batches/{batch_id}/cancel | — | 202 with cancellation intent and cleanup state. Repeated requests are idempotent. |
| GET /projects/{project_id}/takes | shot_id, cursor | Available takes. |
| POST /projects/{project_id}/reviews | take_id, decision | Server-stamped review record. |
| POST /projects/{project_id}/timelines | optional timeline_id/expected_revision, items, audio | New immutable timeline revision. Server verifies trim bounds and duration. |
| POST /projects/{project_id}/exports | timeline_id, timeline_revision, profile; Idempotency-Key header | 202 export record. Repeated matching input returns the same export. |
| GET /projects/{project_id}/exports/{export_id} | — | Export record and scoped download access when complete. |

Budget values and owner IDs in client records are never sufficient authorization. Resolve stored approval and ownership on the server. Return 401 for missing identity, 404 for absent or inaccessible project records, 409 for revision/idempotency conflicts, 422 for invalid input, and 503 for temporarily unavailable dependencies.

## Worker interface to implement in B01 and B02

Use an authenticated private worker endpoint scoped to its assigned batch. `POST /v1/worker/claim` returns an attempt plus its frozen shot and input asset access, or 204 when no work is ready. Claiming is atomic and allocates a fresh attempt ID and lease. `POST /v1/worker/attempts/{attempt_id}/heartbeat` supplies lease ID and progress and returns server lease expiry. B02 owns worker credential issuance and deadline checks.

`POST /v1/worker/attempts/{attempt_id}/complete` supplies lease ID and output asset manifest. Verify active lease, project, object existence, checksum and media metadata before committing one take. Identical completion replay returns the existing take. Conflicting replay returns 409. `POST /v1/worker/attempts/{attempt_id}/fail` supplies lease ID and a safe failure code. Retries follow controller policy and get a new attempt ID. Old workers cannot complete after a fenced lease. B01 implements the client, B02 implements these handlers.

## State and cost contract

Batch rendering progresses queued → provisioning → rendering → succeeded, failed or canceled. Cleanup progresses pending → confirmed, or failed with retry eligibility. A provider timeout never proves deletion. Worker attempt state is claimed, running, succeeded, failed or canceled. Export is queued, rendering, succeeded, failed or canceled. Transition rules and crash recovery are B02/B04 implementation work.

Reserve estimated remaining cost before launch and before a retry. Move settled amounts from reserved to spent atomically. Actual settled charges remain recordable even if billing lag exceeds the approved ceiling. Halt additional launches and surface any overrun. Fixture mode has zero approved/reserved/spent cents and no provider network requests. Model profile `fixture-v1` is explicitly fictional. Real Wan settings, checkpoint pins, supported frame counts and duration rounding belong to B01's supported profile.

## Compatibility

The earlier starter ZIP used a compact draft with singular record keys. Keep it as archived planning evidence. Use the versioned bundle for new work. This is a new repository, with no production data to migrate. An additive or breaking change must increment contract version and provide an updated fixture and consumer handoff.
