# Runpod v2 adapter preparation

This is executable provider transport code tested with fictional HTTP responses. No Runpod request, GPU allocation, image pull, or paid resource was used. `RealJobBridge` remains disarmed except for its exact built-in fake-provider test factory. There is no production admission path, API switch, or client-supplied authorization flag.

## Interface and authority

`RunpodProvider(token, launch_profile=None, scope=None, transport=None, expected_names=None)` preserves the lifecycle `create/find/get/delete` interface. Without explicit scope and transport, every request fails closed. `https_transport()` constructs a standard TLS-verifying urllib opener with redirects disabled, but does not contact Runpod. Supplying it is future trusted host wiring, not proof of authorization. Never expose this constructor to client input.

The scope must be a stable server-resolved owner/project/deployment identifier. A SHA-256 name binds scope, batch ID and request key. This identity is a collision-resistant reconciliation marker, not a secret or authorization credential. Account access remains controlled by Runpod credentials. A shared account administrator can alter names; this implementation conservatively refuses mismatches.

Create/find learn exact Pod ID/name bindings. For recovery after restart when a saved Pod is absent from inventory, trusted host code must provide `expected_names(pod_id)`: resolve only durable lifecycle records in this same owner/project scope and derive the expected name with `_name(batch_id, request_key)`. Never accept this mapping from a worker or HTTP body. Without it, unbound IDs remain unresolved; the adapter never deletes an arbitrary supplied ID.

## Supported profile

`validate_launch_profile(profile)` returns a defensive copy and performs offline structural validation. Required fields:

- `image`: immutable `repository@sha256:<64 lowercase hex>` identity.
- `gpu`: explicit `id` and integer `count: 1`.
- `cloud: SECURE`, `disk`: 1–1000 GB, `dataCenterIds`: exactly one ID.
- `ports: []`: worker connections are outbound.
- `env`: string mapping; account-level `RUNPOD_API_KEY` is rejected.
- `mounts`: `{}`, or `persistent: {size,path}`, or `network: [{volumeId,path}]`.

Optional `cmd`/`entrypoint` argument arrays and `registry` credential ID are accepted. Queueing, mutable template inheritance, global mounts, multi-GPU allocation, inbound ports, and fallback placement are intentionally unsupported. Network mounts allow up to four distinct volumes with distinct nonoverlapping absolute paths. Validation does not establish volume ownership, region compatibility, capacity, price, or model contents. A pre-staged reusable model cache requires separately verified network-volume placement; Pod-local persistent storage is not the durable output store. Worker output upload must finish before Pod termination.

## Failure and cleanup contract

The adapter sends one POST per `create` call with no automatic retry, fallback GPU, or provider-side queue. Existing durable lifecycle code transitions to provisioning before calling create and subsequently reconciles via find. Lost responses and errors therefore remain uncertain, including malformed create replies.

Find reads every v2 inventory page before publishing bindings/results. Invalid metadata, repeated cursors/IDs, more than 100 pages, missing fields, oversized responses, HTTP failures and rate limiting raise `ConnectionError`; none mean an empty inventory. This bounded strategy can leave very large accounts unresolved, requiring operator investigation. Pagination is not a provider snapshot guarantee: independent watchdog passes remain necessary.

Get verifies both expected name and requested ID and returns only sanitized identity. Delete first verifies the binding with GET. DELETE 204 acknowledges a request; it does not settle billing or establish absence. The existing lifecycle watchdog requires later GET 404 and a complete empty matching inventory before marking cleanup confirmed. A readable TERMINATED tombstone is conservatively still present; no status string is treated as proof of absence. If Runpod retains tombstones, cleanup remains unresolved until operationally verified handling is implemented.

Responses are limited to 8 MiB per page and 15-second request timeout. Errors exclude provider bodies, tokens, environment values and raw exception diagnostics. No retries or blocking backoff occur inside the adapter. Settlement remains a separate explicit ledger operation after resource cleanup; storage charges are outside Pod deletion.

## Official evidence checked November 15, 2026

- [Migration guide](https://docs.runpod.io/api-reference-v2/migrate-from-v1): v1 retirement date November 15, 2026; base URL `https://api.runpod.io/v2`; nested requests and cursor pagination replace v1 shapes. The old adapter endpoint has been removed.
- [Create Pod](https://docs.runpod.io/api-reference-v2/pods/create-a-pod): POST `/v2/pods`, 201 response, explicit container/GPU fields and mutually exclusive storage combinations. We deliberately do not copy the guide's transient POST retry example because our lifecycle requires ambiguous-create reconciliation.
- [List Pods](https://docs.runpod.io/api-reference-v2/pods/list-pods): `pods` array plus required `pagination.hasNextPage` and `nextCursor`; subsequent requests pass `cursor`.
- [Terminate Pod](https://docs.runpod.io/api-reference-v2/pods/terminate-a-pod): DELETE `/v2/pods/{id}`, 204 with no body. Account/team API keys retain their assigned permissions.
- [Official Python SDK](https://github.com/runpod/runpod-python/blob/main/runpod/api/ctl_commands.py): confirms `mounts.network:[{volumeId,path}]` and persistent mount shape.

These sources establish request formats, not a live integration result. Next gates remain trusted owner spend/runtime approval, hosted HTTPS identity/storage, verified pinned image/GPU acceptance, scoped worker credential provisioning, durable provider binding recovery, and a reviewed production admission implementation. Run the fictional adapter and lifecycle checks with `python -m unittest discover -s tests -p 'test_b02_runpod.py' -v` and `python -m unittest discover -s tests -p 'test_runpod_integration.py' -v`.
