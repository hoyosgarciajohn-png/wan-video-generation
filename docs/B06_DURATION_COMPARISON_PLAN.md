# B06: controlled five-second and fifteen-second comparison

Prepared November 16, 2026 for John Hoyos. Owner requested two tests and an
improved comparison plan. This document defines the tests; it does not claim that
either has run. John approved the new $5 / 45-minute envelope with "yes I approve".

## Objective

Generate two independent, continuous clips of the same fictional scene. Change
duration while holding the model, checkpoint, GPU, prompt, seed, resolution,
frame rate, sampler and quality settings fixed. Compare visual continuity,
generation time, memory use and attributed cost. A single pair is an exploratory
comparison; it does not establish statistically reliable performance.

The successful one-second H100 run remains preserved. It took about 18m34s from
allocation through confirmed cleanup, including cold startup, with 50 sampling
steps reported in about 25 seconds. Its exact peak-memory metrics and final bill
remain unavailable. These observations justify sharing startup, but do not prove
the memory fit or runtime of a fifteen-second clip.

## Two test cases

| Setting | Test A | Test B |
| --- | --- | --- |
| Comparison duration | 5.000 seconds | 15.000 seconds |
| Purpose | Baseline quality and resource use | Longer-shot consistency and resource growth |
| Independently generated frames | 121 | 361 |
| Original take duration at 24 fps | About 5.042 seconds | About 15.042 seconds |
| Comparison copy | First 120 frames | First 360 frames |
| Current worker duration support | Supported ceiling | Requires an experimental extension |

Use Wan2.2 TI2V-5B, the same pinned model/code revisions for both tests, one
H100 80GB HBM3, 1280x704, 24 fps, seed 42, 50 sampling steps, UniPC, shift 5,
guidance 5 and the repaired sequential-offload/BF16-VAE memory policy. No audio
or reference image. Keep each original take intact; trimming one final frame
creates the exact-duration comparison copy without changing playback speed.

Shared prompt:

> One small blue sailboat with a single white sail moves slowly from left to right across a calm lake at sunrise. A fixed wide camera keeps the entire boat visible. Keep the boat's shape, sail, colors, shoreline and mountains consistent. Gentle continuous ripples, natural light, one uninterrupted shot, no cuts, no text.

The same seed controls one setting but does not make the two clips pixel-matched:
changing the temporal tensor size can change the generated sequence. Compare the
common first five seconds and then examine the long clip's final ten seconds.
The fifteen-second test must be a fresh continuous generation, not three short
clips, a loop, slow motion or an extension made by copying the five-second take.

## Approved execution and cost envelope

- One fresh comparison scope and one allocated H100 Pod for both ordered renders.
- Additional total ceiling: **$5 for the pair**, split into $4 Pod reservation and
  $1 storage allowance. Do not reuse any consumed trial's approval or reservation.
- Hourly ceiling: **$4.50**. Connected H100 catalog quote at planning was $4.39/hour;
  availability was LOW. Refresh price and stock before admission and each request.
- Fixed runtime: **45 minutes from admission**, shared by both tests. At the hourly
  ceiling, 45 minutes is $3.375 of compute; adding the $1 storage allowance gives
  $4.375 before billing variation. These are planning bounds, not a quoted invoice.
- At most three capacity-only allocation requests under one immutable H100/location
  profile, fixed name/deadline and reservation. Retry only the exact explicit
  no-capacity rejection; never retry an uncertain outcome or create a second Pod.
- At most two render attempts: one per duration, no automatic regeneration.
- Secure Cloud, CUDA >=12.8, host RAM >=64GB, 80GB ephemeral disk, no persistent
  volume and no new paid service. Preserve all historical liabilities and the
  exact old unknown repair-request exception and cleanup monitoring.

The previous $5 authority covered the completed one-second trial. John separately
approved this pair and its longer runtime. The limits are
enforced by admission, deadlines and cleanup; they are not a provider account cap.

## Implementation and execution sequence

1. Add durable benchmark telemetry. Save timings, peak allocated/reserved VRAM,
   hardware, image/model identity and output checksums on the controller, and
   require acknowledgement before completing a take or deleting the Pod. Preserve
   backward compatibility; coordinate any necessary shared-contract changes.
2. Add explicitly scoped fifteen-second support. The current worker rejects
   durations above 5000 ms. Preserve that default for historical and ordinary
   scopes; enable the new experiment only through reviewed, bound authority.
3. Add a bounded two-attempt operator. Download and verify weights once, then run
   the five-second attempt. Save its valid video and metrics off-Pod. Inspect
   actual memory use and remaining time before allowing the fifteen-second claim.
   Stop with an honest partial result if the longer attempt is unsuitable.
4. Verify with fictional data: ordering and gating, separate output identities,
   telemetry durability/replay, duration rounding, expiry/cancellation, no duplicate
   Pod or render, and cleanup after either failure. Build the exact reviewed image
   and verify the installed release before new admission.
5. Execute the approved pair with persistent cleanup and an independent guard
   covering the original shared deadline. An error never authorizes another paid
   attempt. Keep the completed five-second take if the longer test fails.
6. Confirm Pod deletion, then retrieve and decode the retained outputs. Produce
   comparison copies and a results table. Import actual billing when available;
   keep unsettled reservations until reconciliation is complete.

The upstream pinned implementation accepts a frame count of the form 4n+1 and
defaults to 121 frames. The 361-frame case fits that arithmetic; this is **not**
evidence of its quality, memory fit or successful runtime. Longer clips may cost
more than three times as much to render. Do not extrapolate a guaranteed result
from the one-second sampling measurement.

## Comparison and deliverables

Report shared setup/download time separately from each attempt's model-load,
generation, decode/encode, upload and verification times. Report peak allocated
and reserved VRAM for each attempt. The provider invoice belongs to the entire
Pod; per-clip costs are attributed estimates and must be labeled accordingly.
Do not assign all cold-start overhead to Test A when comparing efficiency.

Technical checks: expected frame count, exact comparison duration, 1280x704,
24 fps, readable/decodeable MP4, nonempty output, checksum match, two distinct
asset identities, retained telemetry and accessibility after Pod deletion.

Owner visual review happens in the live session. Review boat/sail consistency,
smooth natural movement, flicker, background stability and prompt adherence,
including deterioration near the end of the fifteen-second clip. Automated
technical checks do not establish creative acceptance.

Deliver two original takes, the 5s and 15s MP4 comparison copies if successful,
a labeled side-by-side comparison of their first five seconds, the full long
clip, and a timing/memory/cost/quality table. Mark failed, skipped or unavailable
measurements explicitly. No result is prefilled as PASS.

## Sources and current preparation state

- Scope: [B06 issue #7](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/7).
- Baseline main: a746d01714886edf6ae0c900ef9f2e283a82048a; installed runtime:
  84fe9d2d9e2aad680c825069dd5dc5a84f5314f5.
- One-second evidence: deployment/evidence/2026-11-16-multi-gpu-allocation/result.json.
- Exact upstream [frame-count implementation](https://github.com/Wan-Video/Wan2.2/blob/e5058c08fada388b04bb3d1a4734bddbd2fdeac5/wan/textimage2video.py).
- Machine-readable terms: deployment/duration-comparison-proposal.json.

The owner-approved implementation adds a private protocol named
`wan-duration-comparison-v1`, shared by B01 worker and B02 controller, with B05
fictional lifecycle/transport checks. Canonical bundle records remain at 0.1.0.
The signed grant and host configuration hash bind the ordered shots and experiment.
Ordinary scopes retain the five-second ceiling. `POST /v1/worker/attempts/{id}/telemetry`
accepts strict bounded metrics and returns their hash before completion; replay
must match. Controller backup retains and checks these records. No telemetry is
accepted for other scopes. The fifteen-second claim additionally requires the
first take, its measurements, remaining-time allowance and projected memory headroom.
The projection uses 9x measured generation time and 3x variable reserved VRAM plus
10% device headroom. These are cautious feasibility estimates, not guarantees.

Implementation and fictional verification are in progress. No new Pod is admitted
until the reviewed image is published, installed and bound into a fresh scope.
