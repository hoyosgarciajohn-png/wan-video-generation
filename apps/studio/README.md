# WAN Studio fixture implementation

B03 provides the React and TypeScript creator workspace for issue #4. Contract version is 0.1.0. The shared JSON schema generates the local TypeScript wire types.

## Run locally

Use Node 22.12 or newer and the repository's Python environment. From the repository root, install the foundation requirements as described in AGENTS.md, then run the following commands.

```sh
cd apps/studio
npm ci
npm run dev
```

Open the local URL printed by Vite. The default interface connects to the durable server on `/v1/studio`, proxied by Vite to `http://127.0.0.1:8787`. Start the controller HTTP service separately using its documented command and provision an owner token on that server. Enter the token in the connection form; it is exchanged for a same-origin HttpOnly session cookie and is never saved in localStorage. Create your first server project, edit scenes/shots or the creative brief, and click **Save to server**. Unsaved edits remain in tab memory. A conflict requires explicit reload; saving never silently replaces a newer server revision. Multiple unsaved edits to one shot become one new revision when saved. Reloading or signing out intentionally discards unsaved edits. If the session expires during a save, the interface retains an in-memory recovery draft and offers a JSON download, including after signing in again. Closing or refreshing the tab triggers the browser’s unsaved-change protection while edits or a recovery draft remain.

Connected mode now submits server fixture batches, cancels them and approves/rejects takes using authenticated commands. Save all changes first. Server fixture rendering produces silent synthetic 320×180, 24 fps clips of 1–5 seconds, with one step and no reference images; it does not run Wan or rent GPUs. Active batches poll every 1.5 seconds only while the workspace is clean. Poll responses cannot overwrite edits, and refreshes preserve the current project and tab. If a command fails ambiguously, use **Retry pending command**: the exact original payload and idempotency key are retained. Connected References uploads PNG/JPEG/WebP images up to 1 MiB and WAV/MP3 audio up to 128 MiB to protected server storage using resumable 1 MiB binary chunks. The client hashes each chunk separately and verifies server receipts; it never reads the whole soundtrack into one buffer or base64 string. Save pending edits first. The server validates bytes, media type and duration. Images can be prepared for future Wan work; the synthetic renderer still refuses image-conditioned shots. In **Timeline and export**, choose one soundtrack (or none), assemble the current selected approved take for every saved shot, then export a specific immutable timeline revision. Audio starts at zero, trims to the video length, and leaves silence if shorter. Manual trim controls and multiple audio tracks are not exposed yet. Queued exports are polled automatically, and completed MP4 files download through an authenticated same-origin asset URL. Pending upload/timeline/export requests retain their identity for safe retry. For large uploads, Retry keeps the same File, session ID and key, checks the stored prefix and continues missing chunks—even after signing in again if the session expired. Resume works while this tab remains open; refreshing or closing loses the browser File reference and requires selecting the file again. Server upload sessions expire after 24 hours. Server and fictional workspaces are separate; connected mode never loads fictional browser data.

For the existing fictional rehearsal, open `/?mode=fixture`. It starts with the supplied fictional blue studio project. Metadata and small reference files persist in this browser under `wan-studio.fixture.0.1.0`. A saved-state revision conflict requires reloading the newer saved state. Browser storage is intended for the local fixture rehearsal. B02 owns authenticated durable storage and transactional multi-user edits.

The interface supports music videos up to 300,000 ms and short films and cartoons up to 1,800,000 ms. Create scenes, edit prompts and shot duration, attach recurring images, reorder shots within a scene, approve a batch and advance the fixture simulation. Every fixture take plays the same supplied two-second 320×180, 24 fps blue clip. Target shot durations are planning inputs. Actual Wan profiles and supported output lengths come from B01.

Batch approval captures shot revisions, prompts, references, settings and fixture profile. Later shot changes append to local revision history. Render failures preserve prior completed takes. Preparing unfinished shots opens a new approval using their latest revisions. Acceptance selects a take explicitly and leaves earlier takes and timeline revisions readable. Timeline assembly is B04's responsibility.

## References and storage

In explicit fictional rehearsal mode, reference imports accept PNG, JPEG and WebP images up to 1 MiB and supported audio up to 4 MiB. Actual browser decoding, audio duration and SHA-256 are checked before saving the asset record. Storage quota failures retain the last saved workspace and display an error. Imported bytes use data URLs during the rehearsal. Script text, scene names, asset display names, previous shot revisions and the selected take map are Studio-local metadata. Download contract bundle exports only the contract 0.1.0 records, with media referenced by object key.

Integration decisions for hosted metadata, uploads and selected takes are tracked in issue #17. The fixture adapter runs locally with a fictional owner. Server ownership enforcement and real transport are part of B02/B05.

## Checks

```sh
npm run build
npm run test
npm run test:ui
npm run format:check
npm run types
npx playwright install chromium
npm run test:browser
```

`npm run test` invokes the existing Python contract validator for generated fixture records. It defaults to `../../.venv/bin/python`. Set `WAN_PYTHON` to another Python executable with the root requirements installed if needed.

The browser suite covers actual file import, playback, native dialog keyboard behavior, accessibility and narrow viewports. `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` optionally selects an installed Chromium executable. The DOM suite uses jsdom and excludes color contrast because it has no layout engine. Its dialog shim checks visibility only. Native focus, Escape, video playback and visual layout require the browser suite.

See B03_EVIDENCE.md for commands and results from this implementation run.

