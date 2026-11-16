# Protected uploads and timeline/export controls

Local B05 checkpoint, November 15, 2026. Bundle 0.1.0 and workspace 1 are unchanged.
This completes the locally connected synthetic creator path through a downloaded
MP4 with soundtrack. Hosted B05, browser acceptance and real Wan inference remain open.

## Authenticated commands

All POST routes inherit the existing same-origin session, owner and CSRF checks.
Responses contain the affected record (`asset`, `timeline`, or `export`) and the fresh
workspace. Client identity, object paths, duration, checksums and output assets are
never trusted. Exact retries retain the original identity; changed payloads with the
same project/operation/idempotency key return 409.

| Route under /v1/studio/projects/{project} | Exact JSON request |
|---|---|
| /assets | name, mime_type, data_base64, expected_revision, idempotency_key |
| /timelines | expected_revision, idempotency_key, audio_asset_id (string or null) |
| /exports | timeline_id, timeline_revision, idempotency_key |

Upload and timeline assembly advance the creator revision. Export admission captures
an existing immutable timeline revision and does not change creator metadata.

## Uploads

Initial connected limits are PNG/JPEG/WebP up to 1 MiB and WAV/MP3 up to 4 MiB decoded.
WAV supports the listed PCM codecs in media_commands.py; audio is limited to two
channels, 96 kHz and the project runtime cap. Images may not exceed 4096 pixels per
axis. These are development limits, not a complete large-song upload solution;
chunked/object-store uploads and larger original WAV tracks remain next work.

The upload endpoint alone accepts a 6 MiB JSON body to accommodate base64; other
routes retain their 2 MiB limit. The server checks decoded size, signatures, forced
media format/codec and complete decoding. FFprobe/FFmpeg receive explicit format and
file/pipe protocol restrictions and 15/20-second timeouts. Playlist/remote-format
payloads are not accepted. Untrusted names become display text, never filesystem paths.

Original source bytes are retained unchanged under a server-generated project key.
Publication uses a durable immutable file followed by the transactional asset record,
display name, creator revision and receipt. Receipts store checksums/size rather than
a duplicate base64 source. Abrupt process death between file publication and database
commit can leave unreferenced files; retention/garbage collection remains operational
work. Reference images can be saved now, but the synthetic renderer still refuses
image-conditioned shots; that belongs to the real Wan path.

## Assembly and export

Assembly takes every saved shot in current storyboard order, using its selected
server-approved take and trimming from zero to the shot target duration. Every shot
must have a selected take long enough for the trim. Each assembly adds a new immutable
timeline revision; replay returns its original revision even after later assemblies.
An optional uploaded soundtrack starts at zero and is trimmed to the lesser of its
length and timeline duration. The CPU exporter fills the remaining timeline with
silence where required. Multi-track editing, arbitrary trim/offset UI and transitions
are not part of this increment.

Export admission records a frozen bundle snapshot and queued job transactionally.
The CLI starts ExportRunner alongside FixtureRunner. A per-database POSIX lock allows
one export renderer at a time. Queued/rendering jobs resume after process interruption,
and the existing verified cache can be reused. Later take reviews, shot edits or
new timeline revisions cannot alter the snapshot already queued.

Output is currently MP4/H.264, 320×180 at 24 fps, with AAC when the timeline contains
a soundtrack. The runner verifies media, publishes immutable output and commits its
asset together with the succeeded export state. Protected same-owner download routes
support byte ranges. Explicit processing errors persist as failed; the user can
submit a new export for the retained timeline. Export cancellation is not implemented.
The original audio asset remains unchanged; AAC in the MP4 is an encoded copy.

## Studio behavior

Connected References imports call the server and display only returned assets. Clean
saved state is required; asynchronous file reads cannot overwrite edits started while
reading. Upload requests retain their exact body for an ambiguous retry.

The Timeline and export tab selects an uploaded soundtrack, assembles approved takes,
queues a chosen timeline revision, polls active exports and offers Download MP4 only
after server completion. Polling preserves the view and pauses while editing. The
isolated browser fixture rehearsal stays separate from actual server execution.

## Evidence

- Python root suite: 77 tests PASS. New tests include
  accepted PNG/JPEG/WebP/WAV bytes, media limits, malicious/mismatched formats,
  cross-owner access, receipts, timeline history, restart and immutable export snapshots.
- Two media TCP scenarios include actual synthetic generation, review, audio upload,
  timeline revisions, a fresh export runner, protected download and full FFmpeg decode.
- Actual TypeScript StudioClient → HTTP → audio upload → synthetic render → take review
  → soundtrack timeline → export queue → MP4 download/FFprobe/full decode: PASS via
  `cd apps/studio && node --import tsx ../../scripts/check_studio_client.mjs`.
- Studio: 14 model/client tests, 16 DOM tests, build and formatting PASS, recorded
  in apps/studio/B03_EVIDENCE.md. Browser
  layout/native upload/playback remain unverified under the prior Chromium restriction.
- Previously accepted long-duration CPU export evidence is retained; this connected
  smoke uses a two-second fixture and does not claim a full generated 30-minute movie.

No cloud resources, GPU spend or production deployment. Next: deployment/storage
readiness, larger durable media uploads, hosted lifecycle/budget wiring and a buildable
pinned Wan runtime. Paid B06 benchmarking still requires an explicit dollar ceiling
and runtime envelope. Full B05 remains open until its hosted/browser gates are met.

## November 16 HD export update

New exports now capture 1280x704 at 24fps. Existing exports retain their original
profile and output verification follows that immutable profile. FFmpeg uses one
codec/filter thread for the small controller. Studio shows per-export dimensions.
Synthetic source enlargement proves assembly mechanics only. See
PROGRESSIVE_VALIDATION.md for separate local/hosted and real-GPU acceptance.
