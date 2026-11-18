# Complete-song LongCat preparation

Issue #8; source baseline `311ce5930e54413f4b990fdbbe307cc9c845de65`.

John selected LongCat after reviewing its three-shot singing benchmark and
approved the complete approximately 6:03 recording on November 17, 2026. This
supersedes the earlier preference for a 5:59 edit. The planned video has 110 shots
across 11 locations: 65 singer, 30 sport/adventure and 15 crowd/location shots.
John is the singer and an athlete; keep his face and age consistent and use a
cap, hat or appropriate helmet in every shot. Eighteen approved concept panels
establish the look. Personal images, song files and model weights remain outside
Git. Still-image approval does not validate demanding sports motion.

## Source prepared here

- Shared runtime policy 1.2.0 allows new music projects up to 363000 ms. Existing
  smaller project limits remain binding; no saved records or deployed hosts change.
- The new private batch protocol validates contiguous timeline frames, audio
  offsets, trims, hashes, headwear requirement, seeds and 4.72-second conditioning.
- A CPU-testable serial queue initializes one adapter, verifies each result and
  waits for a matching durable receipt before advancing. Published takes are
  skipped on resume. An ambiguous publish checks the authenticated saved receipt;
  interrupted rendering requires explicit recovery rather than a blind rerender.
- The pinned upstream adapter initializes LongCat once, changes prompt/image/audio
  and seed for each case, and broadcasts rank-zero queue decisions to both ranks.
  Native 864×448 output, 93 frames at 25 fps, and full decode are checked before
  publication. The authenticated controller stream transport saves each immutable
  take outside the GPU and returns a hash-bound receipt before the next shot.
- Signed private admission binds the reviewed source, runtime image digest,
  manifest, original deadline, independently accepted guard and retained budget.
  It has no public admission endpoint and cannot sign authority or rent a GPU.
  Durable inference-start records prevent a lost GPU journal from silently
  repeating a shot. Revocation retains the original compute reservation.
- The guard's exact rental name is derived from the scope ID and bound by the
  host attestation. A separate signed provider-absence record revokes the worker
  token after cleanup. Backups require that record and retain the input images,
  audio, saved takes, receipts and budget reservations. Restoring cannot revive
  an old credential or erase the prior spend envelope.
- The production bootstrap downloads hash-bound inputs and pinned weights, then
  starts one two-rank resident model. A process-group timeout stops the child and
  both ranks; a separate exact-name provider guard handles rental termination.
- The scene preparation CLI copies original images and existing 4.72-second WAVs
  into a validated, frozen input package. It never changes the soundtrack or
  invents execution authority. Image aspect ratios must select the measured
  native 864×448 upstream bucket.
- A private review assembly command reads all immutable controller receipts,
  verifies each saved take, applies frame-exact trims and joins the native clips
  with the complete stereo master. It writes a review MP4 and integrity report,
  never inventing Studio approvals or declaring creative acceptance.
- The default production negative prompt allows the requested close-ups and
  crowds, unlike the upstream exclusions. This is unmeasured creative behavior.
- A time gate retains recovery time. Fixed execution scope, deadline and manifest
  identity cannot be changed on resume. The candidate ceiling is 80 minutes,
  two H100s and $11.71 compute, plus separately budgeted disk/recovery. These
  constants are limits, not an installed grant or a completion guarantee.

## Remaining live work

Review the 18 clean individual frames and musical cut alignment; publish the
import-tested production image; deploy this exact controller release; install a
separately scoped independent cleanup guard and verify the exact remaining
financial envelope. The old benchmark image
is not a full-batch production image. Do not extend or replay its consumed grant.
Use initial difficult shots to measure motion quality and update remaining-time
estimates. Preserve accepted outputs and retry affected work only within scope.

The public Studio/controller LongCat dispatch remains disabled. No real GPU
work, paid generation, allocation, runtime deployment or owner creative acceptance
of a full film is asserted by the fictional checks.

## Operator preparation

`python -m deployment.longcat_prepare --plan PLAN.json --scenes SCENES.json
--audio-zip AUDIO.zip --output INPUTS --project-id PROJECT --batch-id BATCH`
creates a new input directory only. `python -m deployment.longcat_operator
preflight --inputs INPUTS` validates hashes, geometry, timing and audio without
an allocation. Admission is a separate private operation requiring independently
installed keys and exact owner/host signed envelopes. Never commit those keys,
envelopes, worker credentials or personal media. The grant's source digest is
computed from the exact deployed files; do not substitute the benchmark digest.

After all takes are durable, `python -m deployment.longcat_operator
assemble-review --inputs INPUTS --database STATE --assets ASSETS --owner OWNER
--scope-id SCOPE --master MASTER.wav --master-sha256 SHA256 --review-output REVIEW.mp4`
builds one private review video. It works from the retained controller records
after GPU teardown and does not need a still-valid GPU credential. An incomplete
scope is refused; do not substitute stills or duplicate clips for missing takes.

After observed provider teardown, `record-cleanup` consumes a signed host absence
attestation using the `wan-longcat-cleanup-host-v1` domain. It records the exact
scope/grant/guard/name and confirmation time, revokes the worker credential, and
retains its money reservation. It does not perform deletion or reconcile billing
by itself. Normal controller backup/restore then preserves all LongCat media.

The complete project budget remains capped at $20 with prior posted and retained
liabilities included. The known $8.156768710002916 in earlier posted use is not a
fresh account-balance check. The 80-minute ceiling is a candidate maximum, not
another four-hour allowance. Provider cleanup must be observed independently;
process exit alone does not prove billing stopped.

## Validation

Run the shared contract validator, root tests, media export tests, Studio model
tests and `python -m unittest workers.gpu.tests.test_longcat_batch -v`. The new
fictional queue checks cover 110 jobs with one model initialization, unchanged
published takes, ambiguous-publication recovery, failed-render refusal, foreign
receipts, deadline gates, input/scope mutations and rank-loop input/seed changes.
The existing media test uses a synthetic 362.88-second soundtrack to check full
duration through actual CPU encoding. None of these checks proves GPU throughput,
identity, lip sync, crowd choreography, sports motion or fleet scaling.
