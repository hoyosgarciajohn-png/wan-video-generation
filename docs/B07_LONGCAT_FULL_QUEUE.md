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
  skipped on resume. An ambiguous publish retries publication of the same bytes;
  interrupted rendering requires explicit recovery rather than a blind rerender.
- The pinned upstream adapter initializes LongCat once, changes prompt/image/audio
  and seed for each case, and broadcasts rank-zero queue decisions to both ranks.
  Output shape/frame count and full decode are checked before publication. Its
  pending receipt files must be supplied by an authenticated collector outside
  the GPU; that transport is not yet connected in this PR.
- The default production negative prompt allows the requested close-ups and
  crowds, unlike the upstream exclusions. This is unmeasured creative behavior.
- A time gate retains recovery time. Fixed execution scope, deadline and manifest
  identity cannot be changed on resume. The candidate ceiling is 80 minutes,
  two H100s and $11.71 compute, plus separately budgeted disk/recovery. These
  constants are limits, not an installed grant or a completion guarantee.

## Remaining live work

Prepare clean individual source frames from approved concepts; finish musical
cut review; connect controller admission and authenticated durable collection;
build/import-test the new image; install a separately scoped independent cleanup
guard and verify the exact remaining financial envelope. The old benchmark image
is not a full-batch production image. Do not extend or replay its consumed grant.
Use initial difficult shots to measure motion quality and update remaining-time
estimates. Preserve accepted outputs and retry affected work only within scope.

The public Studio/controller LongCat dispatch remains disabled. No real GPU
work, paid generation, allocation, runtime deployment or owner creative acceptance
of a full film is asserted by the fictional checks.

## Validation

Run the shared contract validator, root tests, media export tests, Studio model
tests and `python -m unittest workers.gpu.tests.test_longcat_batch -v`. The new
fictional queue checks cover 110 jobs with one model initialization, unchanged
published takes, ambiguous-publication recovery, failed-render refusal, foreign
receipts, deadline gates, input/scope mutations and rank-loop input/seed changes.
The existing media test uses a synthetic 362.88-second soundtrack to check full
duration through actual CPU encoding. None of these checks proves GPU throughput,
identity, lip sync, crowd choreography, sports motion or fleet scaling.
