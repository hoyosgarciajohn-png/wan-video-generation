# Studio API version 1 — local connected checkpoint

Status: implemented and tested locally. Bundle contract remains 0.1.0. The separate
workspace envelope has `version: 1`, an integer creator revision and `projects`.
See contracts/studio-workspace.schema.json and fixtures/studio-workspace.json.
This records the creator-persistence checkpoint of issue #17; it does not close the
upload/timeline operations portion.

## Identity and transport

Run the API on loopback, with Vite proxying `/v1/studio` to port 8787. A trusted
operator provisions a high-entropy access token per owner using the
`WAN_STUDIO_TOKENS` environment variable (JSON object mapping token to owner ID).
Tokens must contain at least 32 characters; generate with `secrets.token_urlsafe(32)`.
Never commit tokens or put them in Vite variables, source code, URLs or browser storage.
The default browser entry point is the connected workspace. `?mode=fixture` is an
explicit isolated fictional rehearsal with its separate browser-local store.

POST session exchanges the token for an HttpOnly, SameSite=Strict session cookie.
The cookie is Secure for HTTPS configured origins; loopback HTTP is supported for
local development. Cookie lifetime is 30 minutes; the in-memory server session also
expires after 30 minutes inactivity or 12 hours absolute. Restarting the API requires
signing in again but preserves projects. This is operator-provisioned local access,
not public registration, password recovery, or a managed production identity service.

All mutations require `Content-Type: application/json`, `X-WAN-Request: studio`,
and an exact matching browser Origin. Set `WAN_STUDIO_ORIGIN` to the actual frontend
origin; default is `http://127.0.0.1:5173`. Host allowlisting blocks unrelated hosts.
No CORS permissions are granted. Requests are capped at 2 MiB. Responses are no-store.

## Routes

| Method and route | Request | Response |
|---|---|---|
| POST /v1/studio/session | `{token}` | `{owner_id}` and session cookie |
| GET /v1/studio/session | Cookie | `{owner_id}` |
| DELETE /v1/studio/session | Cookie | Revoked cookie |
| GET /v1/studio/workspaces | Cookie | `{workspaces:[{id:"default",title,revision}]}` |
| GET /v1/studio/workspaces/default | Cookie | `{id:"default",workspace}` |
| POST /v1/studio/workspaces | `{title,kind,expected_revision}` | New project in returned workspace; 201 |
| PUT /v1/studio/workspaces/default | `{expected_revision,workspace}` | Updated authoritative workspace |
| GET /v1/studio/projects/{project}/assets/{asset}/content | Cookie; optional Range | Owner-scoped bytes; 200/206 |

The owner is derived exclusively from the session. There is no request owner selector.
Each owner has one workspace containing their projects. Empty workspaces are valid.
Invalid input returns 422; stale revisions return 409; anonymous requests return 401;
unavailable asset paths return 404; CSRF/Host violations return 403; oversized bodies
return 413; throttled login returns 429. Responses never include secret or database
exception text. Media reads enforce canonical asset ownership, confined filesystem
paths and a safe media MIME allowlist, with single byte ranges supported.

## Save semantics

Workspace PUT atomically saves creator fields across the existing project set:
project title/format, ordered scenes, ordered current shots, source script, asset
display names and selected approved take per shot. Server-derived runtime caps and
owner identity remain authoritative. Shot changes increment the prior revision by
one; the server archives the previous shot. Reordering does not create a revision.
Multiple unsaved edits in the UI become one persisted shot revision when saved.
New projects use POST; project/shot deletion is not provided in this increment.

Submitted execution records, assets, preview URLs and shot-history copies are ignored.
They cannot overwrite canonical ControlService state. A GET/PUT response refreshes
those server-owned records, so a worker completing a render while the browser edits
cannot lose its result. Selected takes must be approved server-side and belong to
the selected shot. Historical timelines and frozen batch snapshots are preserved.

The UI clearly distinguishes unsaved edits from successful server saves. It locks
saving after a 409 until reload, and retains unsaved work in an in-memory recovery
draft if authentication expires. That draft can be downloaded; it is not autosaved
or persisted across closing the tab. A dirty/recovery draft triggers the browser
leave-page warning. Connected mode disables the browser fixture simulator and unsupported uploads.
Render/review commands now use the server; see RENDER_COMMANDS_V1.md. It never labels
browser-simulated work as a server-rendered result.

## Run and verify

From repository root, with operator-provided environment variables:

```sh
python -m services.controller.http_api --database /path/to/studio.sqlite --assets /path/to/assets
```

In another terminal:

```sh
cd apps/studio
npm ci
npm run dev -- --port 5173 --strictPort
```

Then open http://127.0.0.1:5173. This is a local development address, not a hosted URL.
The stdlib threaded HTTP adapter and SQLite/shared mount are development components;
do not expose them publicly as a production service.

Validation for this checkpoint:

- 61 Python tests PASS, including 8 real loopback TCP security/persistence/media tests,
  8 Studio repository tests and the versioned workspace fixture check.
- Studio: 12 model/client tests and 10 DOM tests PASS; build and formatting PASS.
- `cd apps/studio && node --import tsx ../../scripts/check_studio_client.mjs`: PASS.
  This runs the actual TypeScript StudioClient against the actual Python HTTP server,
  checking login/create/edit/save/conflict/load/logout. It does not emulate browser
  cookie policy, layout or media playback; TCP and DOM checks are distinct evidence.
- Earlier GPU-worker and long-media checks remain recorded in the prior checkpoint;
  those unchanged components were not repeatedly tested in this increment.

Browser acceptance remains unverified under the previously observed Chromium socket
restriction. Hosted deployment, production identity, remote storage, reference
uploads, timeline/export commands, queue-to-Pod lifecycle and paid budget settlement
remain open. Next: add uploads and timeline/export over this authenticated boundary. GPU
spending remains disabled; no external resources or charges were created.

## Subsequent render-command increment

Render submission, cancellation, take review and clean-workspace polling are now
connected. The HTTP CLI starts the actual synthetic background worker. See
[RENDER_COMMANDS_V1.md](RENDER_COMMANDS_V1.md) for current routes, review selection,
retry/recovery behavior and evidence. Earlier disabled-command descriptions above
record the prior checkpoint. Uploads and timeline/export transport remain pending.
