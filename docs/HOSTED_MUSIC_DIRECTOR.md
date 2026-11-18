# Hosted Music Video Director

November 18, 2026 · Interface and adapter foundation · related issue #4

John approved building the interface first: upload a song, original character
photos, video description and a selectable hosted video model. This changes the
old self-host-only architecture. No new GPU rental, generation charge or live
provider request was made in this implementation.

## Implemented

- Existing React Studio adds `/#director`; the classic workspace stays at `/`.
- Existing session authentication, project ownership and resumable media uploads.
- Create/select projects; save and reopen separately revisioned creative briefs.
- Song selection and start/end in seconds (stored as integer milliseconds).
- Original character references, primary face, cap/outfit/identity direction.
- Description, location, lighting, environment, dancer behavior, group-vocal cues.
- Explicit model/provider, endpoint documentation, output format, supported clip
  durations, audio-input capability and indicative cost. No hidden fallback.
- Editable 12-shot one-minute pacing template with distinct camera/action cards;
  editable cut points and singing flags. It is a template, **not** lyric/beat AI
  analysis. Longer songs require deliberate new action direction before rendering.
- Audio-timed direction cards and server checks for missing inputs, unsupported
  lengths, singing/model incompatibility, timing gaps and budget estimates.
- Four server-side fal adapters: build exact payload, submit, read queue status,
  retrieve result JSON. POST transport errors propagate without automatic retries.
- HTTPS provider response URLs restricted to queue.fal.run; redirects rejected.
- Credentials are never returned to the browser. Configuration and verification
  have separate states; the catalog always reports unverified in this release.
- Director briefs included in verified backup/restore; cross-project media
  references and stale save revisions rejected server-side.

## Hosted models in this release

| Model / exact endpoint | Intended use | Uploaded song |
|---|---|---|
| LTX 2.5 Audio Fast — `lightricks/ltx-2.5/audio-to-video/fast` | Audio-driven performance candidate | Required trimmed audio, optional first-frame reference (required by this app) |
| Wan 3.0 Reference — `alibaba/wan-3.0/reference-to-video` | Character plus audio reference generation | Reference audio; exact lyric lip-sync unverified |
| Kling 4 Image — `kling/v4/image-to-video` | Concert camera coverage and directed action | No song input in this endpoint; singing shots flagged incompatible |
| Seedance 2.5 Reference — `bytedance/seedance-2.5/reference-to-video` | Multimodal reference performance | Reference audio; exact lyric lip-sync unverified |

Provider: fal, using server `FAL_KEY`. No Runway substitution. The interface does
not guarantee identity, choreography, lip-sync or sub-ten-minute completion.
LongCat is not mislabeled as connected: the desired hosted Avatar variant still
needs an exact endpoint/version and input-schema verification.

Sources checked November 18:
- https://fal.ai/models/lightricks/ltx-2.5/audio-to-video/fast/api
- https://fal.ai/models/alibaba/wan-3.0/reference-to-video/api
- https://fal.ai/models/kling/v4/image-to-video/api
- https://fal.ai/models/bytedance/seedance-2.5/reference-to-video/api
- https://fal.ai/docs/documentation/model-apis/inference/queue

The integration limits Wan audio-reference clips to 15 seconds and Seedance to
30; full upstream capabilities may exceed this app's scope. LTX uses the supplied
audio's duration and does not take a fabricated duration/resolution field. The
integration must trim audio before submission. Kling image dimensions determine
composition; the adapter does not fabricate an unsupported aspect-ratio field.

## API contract addition (canonical bundle remains 0.1.0)

Consumers: Studio Director UI, controller, backup/restore, future hosted worker.
All routes use existing session, same-origin mutation checks and owner scope.

- GET `/v1/studio/director/models`: catalog and credential-presence boolean.
- GET `/v1/studio/projects/{id}/director`: `{revision, brief}`.
- PUT same path: `{expected_revision, brief}`; stale revision is HTTP 409.
- POST `/v1/studio/projects/{id}/director/review` with `{}`: timing/capability
  issues, video-only estimate and exact endpoint. No spending authorization.
- No `/render` route is exposed. Existing fixture jobs remain separate.

The `director_briefs` table is additive. Deploy backend before clients; never roll
back to an old backup validator that does not recognize this table. Existing
saved film bundles and source audio remain unchanged.

## Remaining before live generation

1. Configure server-owned fal credentials and verify access without exposing keys.
2. Retain exact approved scene images, identity review and song-aligned shot cues;
   add the image-generation provider separately. Current Preview is text/audio.
3. Add a durable hosted-job admission/outbox with immutable prompt/reference/model
   snapshots, atomic budget reservations and per-request idempotency. Do not invoke
   `submit()` directly from a browser request without this layer. Unknown POST
   outcomes must be reconciled and cannot be blindly re-submitted.
4. Trim and validate original audio for every shot; transfer scoped images/audio
   through supported provider storage or data URIs. Do not send private Studio
   URLs to fal: they require the user's session cookie.
5. Persist queue receipts; poll, reconcile terminal failures, import and verify
   generated MP4s into project storage before reporting a downloadable result.
6. Assemble reviewed shots with original song; compare measured cost, latency,
   identity, lip-sync, action and continuity. No fake preview/download buttons.

The Render and Compare views disclose these pending stages. This is not a
completed music-video rendering service. Current uploader limits: 1 MB per image,
128 MB per audio file. Seedance pricing is quote-required; other amounts are
indicative video-only rates, not billing caps or reservations.

## Validation

Build, TypeScript, existing UI/service tests and new fictional integration tests
are recorded in the PR. Browser QA used an isolated fictional database, with no
personal media or API keys: selected a project, built twelve shots, saved, checked
missing inputs, reloaded, reopened and confirmed the saved twelve-shot brief.
Screenshot: [implemented interface](evidence/director-2026-11-18/interface.jpg).
Owner creative acceptance, mobile browser acceptance, live provider validation
and production deployment remain pending. The repository requires John's approval
for this specific production release; no production change has been made.

## Live deployment — November 18, 2026

John approved deploying this specific interface release. PR #109 was merged at
`d8957527559ba1fe25c92cbed6598cf4b4b35047`. Deployment workflow
[44336172131](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/44336172131)
succeeded. The public Director is https://wan-64-225-114-46.sslip.io/#director.

The release is an explicitly recorded overlay on installed Git baseline
`9277e14a7d21a4f8bb142c50943fd3f8a1bfce4b`, not a claim that the server's Git HEAD
matches the new release. `/opt/wan/current/director-installed-release.json`
records the approved source and all deployed file hashes. The installer checked
exact predecessor hashes for both changed backend files before writing, saved a
private database checkpoint and previous files, and preserved all 12 historical
project records unchanged. Controller, cleanup and proxy services passed checks.

External HTTPS health returned ready=true, paid_dispatch=false. The public page
loads the verified Director bundle and all four catalog entries; unauthenticated
catalog access correctly returns 401. The live browser shows the new Director
sign-in screen. Existing owner access token is still required; restart invalidated
in-memory sessions. No credential was rotated. Saving/restore passed fictional
automated checks; authenticated owner acceptance on the live page remains pending.
No GPU or paid generation was started. Model credentials, live validation and
paid-generation/assembly integration remain the next work, as described above.

Do not rerun this one-time installer: its existing stage guard prevents blindly
reapplying the release. Future releases must recognize this overlay and the
additive Director database table, including during rollback and backup handling.

## Email/password follow-up

Owner approved replacing confusing access-token entry with email/password and recovery. The implementation is on `work/studio-email-login`; see `docs/STUDIO_EMAIL_LOGIN.md`. Live installation awaits a mail relay and private verified-email-to-existing-owner mapping. Read-only probe run 44343693588 confirmed no controller mail configuration. Existing live projects remain untouched. Do not tell John the new login is live until the guarded auth overlay and actual email delivery have passed.
