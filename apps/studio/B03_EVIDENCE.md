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

