# Resumable local media uploads

This extends the authenticated same-origin Studio development API. It stores
sessions and chunk receipts in SQLite and staged bytes on the persistent asset
filesystem. It does not provision cloud storage or incur provider charges.

## Protocol

All routes have prefix `/v1/studio/projects/{project_id}/uploads`. Session cookies,
exact configured Origin and `X-WAN-Request: studio` are required as for other Studio
writes. JSON methods use `Content-Type: application/json`; chunk PUT uses
`Content-Type: application/octet-stream` and a raw binary body.

| Method/path | Input | Result |
|---|---|---|
| POST prefix | `{name,mime_type,bytes,expected_revision,idempotency_key}` | `{upload}` |
| GET prefix `/{id}` | — | `{upload}` with persisted progress and chunk hashes |
| PUT prefix `/{id}/chunks/{index}` | Raw bytes, maximum 1 MiB | `{upload}` |
| POST prefix `/{id}/finish` | `{chunk_sha256:[ordered lowercase SHA-256 strings]}` | `{asset,workspace}` |
| DELETE prefix `/{id}` | `{}` | `{upload}` marked aborted; staged bytes removed |

An upload response contains `id`, `project_id`, `state`, `bytes`, `received_bytes`,
`chunk_size` (1048576), `next_chunk_index`, ordered `chunk_sha256`, `expires_at`, and
nullable `asset_id`. States are `uploading`, `completed`, `aborted` and `expired`.
The initial creator revision must match. Finish merges the verified asset and its
display name into the current workspace, increments the revision once, and preserves
creator edits made since the session began.

Audio permits WAV or MP3, up to 128 MiB decoded file bytes. Images permit PNG, JPEG
or WebP, up to 1 MiB. Chunks are fixed at 1 MiB except the exact remaining final
chunk. Upload in order starting with index zero; the maximum is 128 chunks. The
transport bounds raw requests to 1 MiB. No whole-file base64 request is needed.
The older small JSON upload endpoint remains available for compatibility.

A browser can read and hash one `File.slice()` at a time with WebCrypto. On resume,
GET the session, compute each local prefix chunk's hash, compare it to persisted
`chunk_sha256`, and skip only verified matches. Then send missing chunks and finish
with the complete ordered manifest. Changing the selected file must not silently
reuse an existing prefix. File bytes and hashing work stay bounded to one chunk;
the manifest is at most 128 short hashes. The UI retains its File and session in
its open tab. Reloading or closing the tab loses the client File and session ID;
the current UI starts a new upload after reselection rather than resuming the old
session. The abandoned server session expires through the cleanup policy below.

## Integrity and retry behavior

A chunk is flushed and atomically linked into place before its SQLite receipt
commits. Repeating identical bytes at an existing index succeeds; different bytes
or an out-of-order index returns 409. A process exit after filesystem publication
but before the receipt commit is recoverable by retrying the same chunk. Declared
file size and exact final chunk size are immutable.

Finish checks all receipts and the client manifest, rehashes staged chunks while
streaming them into one file, and computes the full SHA-256 recorded on the asset.
It validates MIME signatures, forces an allowed FFmpeg demuxer, restricts protocols
to `file,pipe`, probes codec and dimensions/duration, and fully decodes within a
bounded timeout before publishing the original bytes. Images are limited to
4096 pixels per dimension. Audio is limited to two channels, 96 kHz and the current
project runtime cap. Source media is not transcoded. Invalid media never becomes
an asset. The uploaded original can be retrieved only through the scoped asset API.

The final object key and asset ID are derived from the session ID. A crash before
or after the asset transaction cannot create a second asset on retry. Successful
finish replay requires the identical manifest and returns the original asset plus
the current workspace. Begin replay requires identical admission fields, including
its original expected revision, and returns the original session even if the
workspace has since changed. Changed key input or manifest is 409; malformed data
is 422; inaccessible project/session is 404; oversized HTTP bodies are 413.

## Lifecycle and bounds

Sessions expire 24 hours after creation. Expired sessions return state `expired`
on GET and 410 on write/finish. A new session needs a new idempotency key. At most
four active uploads per owner are admitted; further admissions return 429. Abort
is idempotent and never deletes a committed asset. Completed uploads cannot be
aborted. A per-session OS file lock serializes chunk/finish/cleanup work across
processes on the same host.

Cleanup runs on service startup and upload requests. It expires old sessions,
removes terminal staging directories, and removes published-but-uncommitted links
for aborted or expired sessions. Durable receipt metadata and tiny lock files are
retained for replay; this increment does not implement metadata retention limits.
When the local service is stopped, scheduled cleanup does not run; the next startup
reconciles leftovers. Staging can temporarily hold both chunks and a combined file.
The deployment remains a single-host local filesystem/SQLite design, not a remote
object-storage multipart protocol.

Verification: `python -m unittest discover -s tests -p 'test_uploads.py' -v` covers
resume/replay, interrupted writes, corruption, expiry, abort, post-commit cleanup,
creator edits, scope, exact sizes, and session caps. TCP and browser-client tests
exercise the corresponding HTTP transport separately.

## Combined acceptance evidence

Python root discovery: 85 tests PASS (29.750 seconds), including six upload unit
checks and two real loopback TCP scenarios. The TCP scenario uploads a 5.04 MiB
55-second WAV, restarts the HTTP/API process state mid-upload, retries chunks,
checks integrity conflicts and commits one byte-identical protected asset.

The actual TypeScript client smoke passes with a >4 MiB WAV and a deliberately
lost response after a chunk commits. Retrying the same command verifies and skips
the persisted prefix, then completes synthetic rendering, review, soundtrack
assembly, queued export, authenticated download and full FFmpeg decode. Command:
`cd apps/studio && node --import tsx ../../scripts/check_studio_client.mjs`.

Studio: 16 model/client and 17 DOM tests; build/TypeScript and formatting PASS.
Contract/media validation and whitespace checks PASS. Native browser acceptance,
hosted storage, production release and actual Wan execution remain unverified.
No cloud requests, GPU allocations or spending occurred in these checks.
