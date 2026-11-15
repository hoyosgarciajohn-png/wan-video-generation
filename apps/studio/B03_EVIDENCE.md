# B03 implementation evidence

November 15, 2026. Issue #4. Branch `work/b03-studio`. Baseline `c9c364ab3f68cfca24489715ab0cd8419d0d4f60`. Contract 0.1.0. The pull request identifies the delivered commit.

The fixture implementation is ready for code review. Browser verification is blocked in this executor and keeps B03 acceptance open.

## Delivered behavior

- React and TypeScript Studio with project creation and editing for music video, short film and cartoon.
- Scene names, shot grouping and within-scene ordering, revisioned shot editing, reusable image references, soundtrack import and a script editor.
- Frozen batch snapshots, repeat-submission handling, progress, simulated failures, cancellation and renewed approval of unfinished work.
- Take playback controls and explicit approval/replacement. Previous takes, review records and timeline revisions are retained.
- Versioned browser persistence, JSON Schema validation on reload, stale-write errors and storage-failure feedback. Safe error presentation for ownership, validation, revision and dependency errors.
- Generated contract types, local fonts, responsive CSS, native labels and controls, status/error announcements and a skip link.

## Checks executed

| Command | Result |
|---|---|
| `.venv/bin/python scripts/validate_contract.py --media-root fixtures` | PASS, original fixture checksums and ffprobe metadata verified |
| `.venv/bin/python -m unittest discover -s tests -v` | PASS, 14 foundation tests |
| `npm run test` in apps/studio | PASS, 8 Studio regressions, including generated bundles through the unchanged Python validator |
| `npm run test:ui` in apps/studio | PASS, 5 DOM tests covering creator flow, three project types, scene editing, project isolation, persistence, conflict and quota messages, and structural accessibility |
| `npm run build` in apps/studio | PASS, TypeScript and Vite production build |
| `npm run format:check` in apps/studio | PASS, all matched files formatted |
| `npx playwright install chromium` | BLOCKED, browser download returned an unusable archive |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:browser` | BLOCKED before test actions, Chromium socket creation returned Operation not permitted |

Elevated execution for the local browser test was also rejected by the environment's approval policy. The browser tests remain in the repository for an executor with Chromium support. Their four reported failures occurred during browser launch. No browser scenario reached its first application action.

The DOM accessibility run used WCAG 2 A/AA and WCAG 2.1 AA rule tags with color contrast disabled because jsdom has no rendering engine. It found zero applicable violations in Storyboard, References, Render batches and Take review. It establishes structural checks only. Actual contrast, responsive layout, native focus/keyboard behavior, image/audio import decoding and media playback remain unverified here.

## Integration and acceptance gaps

Issue #17 records proposed persistence/API decisions for B02, B03, B04 and B05. Scene titles/order, script text, reference display names, historical shot copies and the selected take map remain local to Studio. The shared contract remains 0.1.0.

Hosted authentication, upload transport, server authorization, queue polling and real generated footage belong to integration and later batches. The fixture output is always the supplied two-second blue clip even when the planned shot target is longer. Browser-local checks do not establish server authorization or transactional multi-user concurrency. Owner creative and live-user acceptance remain pending.

## Cost and resources

GPU spend incurred is $0. Paid resources created are zero. The implementation creates no Runpod resources. Browser tests manage their local Vite server and stop it on exit. Production deployment remains pending.

## Next recipient

Command Center and B05 QA receive the PR, this evidence, `npm run test:browser`, and issue #17. Run the browser suite and inspect desktop, narrow and enlarged layouts in a permitted executor, then resolve any failures before closing B03. B02 and B04 receive the contract bundles and local metadata semantics described in README.md for their integration decisions.

## Command Center integration review — November 15, 2026

Reviewed B03 PR #18 source at `f07ee6adcadbb3dd635cc1cc5d891845b8c492b2`
in the combined integration workspace, contract 0.1.0. Shared API routes and
metadata remain subject to issue #17; no guessed backend transport was added.

Fixed stale browser saves after another tab deletes the stored workspace, and
recognized `localStorage.clear()` events as conflicts. Malformed persisted data
now raises the recoverable revision-conflict error on save. Storage read failures
use the same storage-unavailable error as write failures. Failed writes no longer
advance the caller's workspace revision. Regression tests cover each boundary.

Fresh verification:

| Command | Result |
|---|---|
| `npm ci` | PASS |
| `npm run build` | PASS |
| `WAN_PYTHON=python npm test` | PASS, 10 model tests |
| `npm run test:ui` | PASS, 6 DOM tests |
| `npm run format:check` | PASS after EOF normalization |
| `npm run test:browser` | BLOCKED before app actions: bundled Chromium executable absent |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:browser` | BLOCKED before app actions: installed Chromium aborts at `process_singleton_posix.cc:297`, `socket() failed: Operation not permitted (1)` |

The local Vite server started for both browser attempts and was stopped by
Playwright afterward. All four browser scenarios failed at browser launch.
No elevated execution was requested in this review. Real browser playback,
import decoding, keyboard focus, contrast and responsive layout remain pending.
DOM checks retain their documented limitations. Source formatting also removes
surplus EOF blank lines from the materialized snapshot.

Recommendation: suitable for continued fixture integration with these fixes;
B03 acceptance and B05 browser end-to-end completion remain open. No cloud
resources, GPU cost, production deployment or external mutations were incurred.


## Durable workspace adapter — November 15, 2026

Connected mode is now the default. `?mode=fixture` explicitly selects the original
browser-local rehearsal. The same-origin client implements the agreed issue #17
session and default-workspace endpoints, cookie credentials, `X-WAN-Request:
studio` mutation header, and revision-bearing saves. The connection form clears
its token input immediately after submission and retains no token or server
workspace in browser storage. Empty server workspaces support first-project
creation. Editing is staged in tab memory with explicit Save to server; revision
conflicts lock edits until reload. Shot revisions advance once per server save,
even after several local edits. Server execution, imports and take approvals are
read-only/disabled in this increment; fixture simulation is never presented as
server execution.

Validation: production build and TypeScript pass; 12 model/client tests pass;
10 DOM tests pass (including session-expiry draft recovery, connected login, empty workspace creation, owner
identity, explicit save, conflict/reload and no localStorage writes); formatting
passes. Fetch tests use a controlled HTTP-response implementation and DOM tests
use jsdom. These do not establish real-browser or live-HTTP end-to-end acceptance.
The previously observed Chromium execution restriction still limits browser
acceptance. No GPU resources or paid services are used.

Session expiry preserves unsaved edits as a separate in-memory downloadable JSON draft, retained across reauthentication. The editor is hidden without an authenticated owner. A beforeunload handler protects unsaved edits and retained recovery drafts; regression coverage verifies downloaded draft contents after reauthentication.

## Connected render and review commands — November 15, 2026

Added authenticated submit/cancel/review commands using the agreed project routes.
These run server CPU fixture jobs, not local progress simulation or Wan inference.
The interface explicitly describes the synthetic 1–5 second output constraint,
zero GPU rental and unsupported references. Render/cancel/review actions require a
clean saved workspace. A failed ambiguous command keeps its full original payload
and idempotency key for an explicit retry. Polling refreshes active server jobs
without remounting the editor or changing the current project/tab; it pauses for
unsaved form input, applied edits, commands and conflicts. In-flight responses are
ignored after edits begin. Backend take decisions and selected-take state replace
local simulated approvals. Reference uploads and export commands remain pending.

Checks: 13 model/client tests and 13 DOM tests pass. Added command payload/status
coverage, exact ambiguous retry coverage, real timed polling tab preservation,
in-flight polling-versus-edit regression, cancellation and take reject/reapprove
through controlled server responses. Production build/TypeScript and formatting
pass. Tests remain DOM emulation and mocked HTTP responses; the Command Center's
separate actual client/server smoke evidence covers the real transport. Native
browser and owner creative acceptance remain open. No paid resources created.

## Protected upload, timeline and export controls — November 15, 2026

Connected References now sends file bytes to the protected asset endpoint; it
never manufactures local fixture asset metadata. Images accept PNG/JPEG/WebP up
to 1 MiB and audio accepts WAV/MP3 up to 4 MiB (`audio/x-wav` normalizes to
`audio/wav`). Server response metadata is authoritative. A delayed file read
cannot submit through stale clean-state callbacks after editing begins. Synthetic
rendering still rejects image references; uploads prepare them for later Wan work.

Added Timeline and export: select one soundtrack or none, assemble all current
selected approved takes in saved order, queue export of a specific immutable
timeline revision, observe export state and download the authenticated MP4.
The soundtrack selector does not mark creator metadata dirty. Assembly/export
require a clean workspace. Audio starts at zero, trims to the timeline, and pads
with silence if shorter; manual trims/multi-track audio remain future work.
Active exports participate in clean-only polling. Upload, assembly and export
commands retain the exact original payload/key on ambiguous errors; pending
commands also activate beforeunload protection.

Validation: 14 model/client tests and 16 DOM tests, production build/TypeScript
and formatting pass. New coverage checks command transport bodies, protected
upload without browser-local metadata, unsupported audio rejection, delayed-read
versus edit race, soundtrack selection/assembly, asynchronous export polling and
authenticated download link attributes. DOM transport tests use controlled
responses and do not establish native file-dialog/media decoding or browser
acceptance. Command Center owns separate actual HTTP and exporter verification.
No paid resources or external mutations were performed by this workstream.

## Larger resumable uploads — November 15, 2026

Connected References now accepts WAV/MP3 soundtracks up to 128 MiB (images remain
1 MiB). It passes the File directly to a resumable client command and immediately
locks creator edits. Begin returns an upload identity, GET returns verified chunk
receipts, PUT sends raw binary slices of at most 1 MiB, and finish sends the client
SHA-256 chunk manifest. WebCrypto hashes only individual slices. No full-file
arrayBuffer or base64 string is created, and no new dependency was introduced.
The original File, session ID and idempotency key survive ambiguous network errors
and session-expiry reauthentication in the same open tab. Server-committed chunks
are verified and skipped on retry; completed finish replay returns the existing
asset. Changed prefixes fail closed, expired uploads show a restart message, and
pending transfers activate beforeunload protection. Refresh/close resume is not
implemented: reselecting after losing tab memory starts a new session. Server
sessions expire after 24 hours.

Checks: 16 model/client tests and 17 DOM tests pass; production build/TypeScript,
formatting and diff checks pass. The new client regression transfers a 5 MiB-plus
fixture, forbids whole-file reads, loses responses after a committed chunk and
finish, and confirms one begin and no duplicated chunks. Additional cases verify
prefix mismatch, expiry, oversize rejection before requests, immediate editor
lock, File identity preservation and reauthentication resume. DOM HTTP responses
are controlled; separate Command Center/QA TCP tests establish actual service
integration. Browser/native media acceptance remains pending. No paid resources
or external mutations were performed by this workstream.
