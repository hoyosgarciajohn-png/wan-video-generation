# Scoped fixture worker and artifact bridge

A worker can now run in a separate process and filesystem from the controller.
It claims a fixture attempt, renders locally, streams its output to a fixed
controller-owned location, and requests completion. The controller verifies the
uploaded bytes and media before committing a take. This is a local/loopback
rehearsal of that transport. It does not allocate a GPU, enable Runpod admission,
issue real budget approval or deploy a public worker service.

## Credential boundary

`WorkerTransport(control).issue(owner, project, batch, worker_id, ttl_seconds=300)`
is a trusted Python/CLI operation. It validates project ownership and permits only
canonical fixture batches with zero budgets. It returns a generated high-entropy
bearer token once. SQLite stores only the token's SHA-256, the owner/project/batch/
worker scope, expiry, revocation flag and creation time. The token cannot choose a
different scope through a request body. A worker ID should identify one active
worker process for its assignment.

The token lifetime is at most one hour. It may extend past the batch deadline to
allow replay of an already committed completion receipt. It never extends a job's
runtime or attempt lease. Every request requires a currently valid credential.
Revoked and expired credentials return 401, including completion replay. Issuing a
replacement token is another trusted operation and retains its specified scope.
There is no public worker login, credential-minting route or owner-session shortcut.

Trusted operators can provision a token into a new private file:

```sh
python -m services.controller.worker_transport \
  --database /path/to/studio.sqlite --assets /path/to/studio-assets \
  issue --owner OWNER_ID --project PROJECT_ID --batch BATCH_ID \
  --worker fixture-worker-1 --ttl-seconds 300 \
  --token-file /private/path/new-worker-token
```

The CLI creates the file exclusively with mode 0600, never overwrites an existing
file, and prints only the credential ID and expiry. Supply the file's value as
`WAN_WORKER_TOKEN` through the worker's private environment; do not put it in a URL,
project record or browser storage. Revocation uses the returned credential ID:

```sh
python -m services.controller.worker_transport \
  --database /path/to/studio.sqlite --assets /path/to/studio-assets \
  revoke --owner OWNER_ID --project PROJECT_ID --credential CREDENTIAL_ID
```

Worker tokens and Studio login tokens are independent. Worker endpoints do not use
Studio cookies and reject browser Origin headers. The existing allowed-Host checks
remain in force. The worker client requires an exact HTTPS origin; only an explicit
`--allow-local-http` flag permits HTTP on `localhost` or `127.0.0.1` for development.
Redirects are not followed.

## Wire contract

All routes use `Authorization: Bearer <worker token>`. JSON requests use
`Content-Type: application/json`.

| Method and route | Request | Result |
|---|---|---|
| POST `/v1/worker/claim` | `{}` | Existing/fresh claim envelope, or 204 when no work is ready. |
| POST `/v1/worker/attempts/{id}/heartbeat` | `{lease_id,progress}` | Current renewed lease expiry. |
| PUT `/v1/worker/attempts/{id}/artifact` | Raw MP4 plus upload headers below | `{bytes,sha256,object_key}` upload receipt. |
| POST `/v1/worker/attempts/{id}/complete` | `{lease_id,output_asset_manifest}` | The one committed take, including identical replay. |
| POST `/v1/worker/attempts/{id}/fail` | `{lease_id,code}` | 204; safe codes are `render_failed` or `worker_failed`. |
| GET `/v1/worker/attempts/{id}/inputs/{asset_id}` | `X-WAN-Lease-ID` header | Checked bytes only for that attempt's frozen input reference list. |

Claim envelopes retain contract 0.1.0: `project`, `batch`, `attempt`,
`shot_snapshot`, `input_assets` and `contract_version`. Repeated claims by the same
worker return its existing active attempt within one transaction; a lost response
does not allocate a second attempt. Another worker does not receive that active
attempt. An expired lease is fenced and a retry gets a fresh attempt and lease.

Artifact PUT requires `Content-Type: video/mp4`, exact `Content-Length`,
`X-WAN-Lease-ID` and `X-WAN-SHA256` (lowercase SHA-256). The controller streams at
most 64 KiB per read into a private temporary file, with a 32 MiB total limit. It
checks credential and assignment before reading, verifies the streamed length,
checksum and MP4 signature, and checks credential/lease again before publication.
Only `projects/{project}/attempts/{attempt}/output.mp4` can be published; callers
cannot supply a filesystem key. The file is flushed and atomically linked. An
identical retry returns its receipt; different bytes cannot overwrite it.
Temporary files are removed on handled failure. A process crash can leave temporary
staging files. A cancellation or expiry racing after immutable publication can also
leave an unreferenced output object; completion cannot commit it, and backup copies
only referenced assets. A general orphan-file retention collector is not part of
this batch.

Completion independently verifies the persisted output's project/owner, exact
attempt path, byte size, checksum, H.264 codec, silent stream count, dimensions,
frame rate, frame count and duration. Output probing forces MOV/MP4 demuxing and
restricts protocols to `file,pipe`; an uploaded playlist cannot trigger arbitrary
format/network probing. The lease is checked again after media inspection.
Credential scope/expiry is also checked inside the database transaction and again
before commit. If it expires during inspection, asset/take/completion-receipt
changes roll back. Revocation serializes with these mutations through SQLite.

An identical completion replay returns the previously committed take even if its
attempt lease has since expired, provided the worker credential is still valid.
Changed manifests conflict. The worker records an upload receipt in its local
completion journal before completion so an ambiguous completion response can be
retried without trying to upload again to an already terminal attempt.

Reference download verifies ownership, frozen-reference membership, live lease and
stored size/checksum, and returns `X-WAN-SHA256`. The actual fixture profile rejects
reference inputs at admission, so real image conditioning and a successful remote
conditioning workflow are **not** claimed by this fixture rehearsal. No general
asset listing, arbitrary object-key download or output GET endpoint is exposed to
a worker credential.

## Process and filesystem separation

With `WAN_WORKER_API_URL` and `WAN_WORKER_TOKEN` supplied privately, run:

```sh
python -m workers.gpu.cli worker \
  --output-root /separate/worker-local \
  --result /separate/worker-local/result.json \
  --allow-local-http
```

Use the loopback flag only for the local rehearsal. The worker root must be separate
from the controller asset root; uploading replaces the earlier shared-mount
assumption. Local input/output checksums, claim/completion journals and a worker
lock survive restart. Journals bind to an origin/credential fingerprint and do not
contain the plaintext token. Changing origin or credential while a claim journal
is pending requires an explicit operator recovery decision; the client refuses to
silently reuse a differently bound journal.

A dedicated remote-worker rehearsal starts the controller without its competing
in-process `FixtureRunner`. The independent integration test does this using the
existing server factory. The normal Studio staging launcher still starts local
fixture workers; this batch does not add a UI for assigning batches to remote
machines or a hosted scheduler.

Backup snapshots revoke every stored worker credential hash without revoking the
source installation. Restored controllers therefore require new trusted worker
credentials. Hashes and scope metadata may remain for audit, but no restored hash
is active and plaintext token files are outside the backup inventory. Active
attempts retain the backup workflow's fencing rules.

## Evidence and remaining work

```sh
python -m unittest discover -s tests -p 'test_worker_transport.py' -v
python -m unittest discover -s tests -p 'test_remote_bridge.py' -v
python -m unittest discover -s workers/gpu/tests -v
```

Synthetic tests cover separate controller/worker processes and roots, a real CPU
fixture render, checksum-verified transfer, controller completion and full video
decode, token revocation/expiry, expiry during server media verification, scope
isolation, concurrent claim replay, lease replacement, malformed artifacts,
completion conflicts and backup revocation. The server reuses the same completion
transaction and worker lease logic used by the local fixture path.

Still pending: live worker provisioning, a production TLS/authentication host,
real GPU lease/queue bridging, remote object storage, model weights and image
conditioning transfer, durable orphan retention, authoritative invoice ingestion
and an owner-approved capped real benchmark. The simulated budget coordinator and
the remote fixture transport remain separately gated; neither grants permission
to spend on infrastructure.
