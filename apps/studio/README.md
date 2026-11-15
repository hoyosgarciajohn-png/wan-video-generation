# WAN Studio fixture implementation

B03 provides the React and TypeScript creator workspace for issue #4. Contract version is 0.1.0. The shared JSON schema generates the local TypeScript wire types.

## Run locally

Use Node 22.12 or newer and the repository's Python environment. From the repository root, install the foundation requirements as described in AGENTS.md, then run the following commands.

```sh
cd apps/studio
npm ci
npm run dev
```

Open the local URL printed by Vite. The app starts with the supplied fictional blue studio project. Metadata and small reference files persist in this browser under `wan-studio.fixture.0.1.0`. A saved-state revision conflict requires reloading the newer saved state. Browser storage is intended for the local fixture rehearsal. B02 owns authenticated durable storage and transactional multi-user edits.

The interface supports music videos up to 300,000 ms and short films and cartoons up to 1,800,000 ms. Create scenes, edit prompts and shot duration, attach recurring images, reorder shots within a scene, approve a batch and advance the fixture simulation. Every fixture take plays the same supplied two-second 320×180, 24 fps blue clip. Target shot durations are planning inputs. Actual Wan profiles and supported output lengths come from B01.

Batch approval captures shot revisions, prompts, references, settings and fixture profile. Later shot changes append to local revision history. Render failures preserve prior completed takes. Preparing unfinished shots opens a new approval using their latest revisions. Acceptance selects a take explicitly and leaves earlier takes and timeline revisions readable. Timeline assembly is B04's responsibility.

## References and storage

Reference imports accept PNG, JPEG and WebP images up to 1 MiB and supported audio up to 4 MiB. Actual browser decoding, audio duration and SHA-256 are checked before saving the asset record. Storage quota failures retain the last saved workspace and display an error. Imported bytes use data URLs during the rehearsal. Script text, scene names, asset display names, previous shot revisions and the selected take map are Studio-local metadata. Download contract bundle exports only the contract 0.1.0 records, with media referenced by object key.

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

