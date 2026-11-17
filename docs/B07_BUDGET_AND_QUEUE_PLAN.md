# B07 — $20 production budget and one continuous queue

Version 1.0 · November 17, 2026 · Owner: John Hoyos

## Latest owner authorization

John set a **$20 additional total ceiling** for the complete 5:40.126 music video
and corrective retries, then approved **four hours** to allow enough execution
time. Two hours remains an optimization target, not the approved hard runtime
limit. Do not request these approvals again. This replaces the unaccepted $100
recommendation and the earlier statement that B07 had no numeric funding scope.

| Control | Production envelope |
|---|---|
| Additional total ceiling | $20, including this production's paid startup, generation, retries and storage |
| GPU allocation | Up to $18; one H100 SXM 80 GB at a time, rate no higher than $4.50/hour |
| Storage and cleanup reserve | $2; do not consume this reserve on extra renders |
| Cumulative GPU runtime | At most four hours across all production attempts; never four hours per retry |
| Optimization target | Finish in approximately two hours if measured throughput permits |
| Rendering mode | Sequential ready-shot queue; retain model weights and initialized model across compatible shots |
| Boundary behavior | Stop new claims before remaining time or money is insufficient for the shot and cleanup; preserve progress |

The live catalog and official pricing page checked November 17 show H100 SXM at
$4.39/hour on Secure Cloud: four hours is $17.56 compute, leaving $2.44 of the
$20 envelope. That is an arithmetic estimate, not an invoice or an advance
guarantee of completing the video. Quote again at admission. Existing separately
approved recurring CPU hosting and historical bills are outside this additional
production allowance; they must not be charged to a reset historical grant.

## What loading once changes

The current worker invokes a fresh inference process per render, verifies the
weights again, then constructs the model again. Keeping the Pod alive alone
does not eliminate that work. Prepare a long-lived inference worker that:

1. Downloads and verifies the selected pinned weights once at startup.
2. Initializes the selected audio-driven model once and retains it across shots.
3. Accepts each next immutable shot specification, exact audio interval and
   reference image without reconstructing unchanged model components.
4. Clears per-shot tensors, preserves lease/deadline cancellation and fences
   stale attempts, and records per-shot time/VRAM/quality results.
5. Saves validated output outside the Pod before marking a take complete.

Normal sequential operation should need one model download and one initialization.
A process or hardware failure may require recovery/reload; its cost and time
still consume the same $20/four-hour allowance. Never promise one load even
through a crash. Weight verification can be cached only with immutable verified
files; user inputs and output hashes remain checked for every shot.

## Measured feasibility, not an assumption

The retained TI2V-5B benchmark measured 55.329 seconds loading the model,
177.813 seconds generating five seconds of video, and 11.948 seconds decoding
and encoding. The render/verification path took 273.060 seconds and upload
0.903 seconds. The cold startup before first claim was 1112.553 seconds, including
a failed file transfer. These are ordinary-video measurements, not S2V results.

The full recording is approximately 68 five-second equivalents. Removing
repeated initialization alone saves about an hour. Generation alone projects to
3 hours 22 minutes; generation plus decode/encode to about 3 hours 35 minutes,
before startup, other overhead, extra coverage or retries. Thus four hours is a
useful controlled envelope but still tight. Two hours requires materially faster
inference as well as the continuous queue. Do not claim the singing model has
this speed merely because the older model did.

Allowing approximately 20 minutes for shared startup and shutdown leaves about
220 minutes. Covering 340 seconds then requires approximately **194 seconds per
five seconds of accepted footage**, including the applicable per-shot overhead.
Retries and unused handles make the required rate faster. With a two-hour target
and the same overhead, the rate would need to be about 88 seconds per five
seconds. Measure *usable* timeline coverage, not just generated frames.

## Production design to reduce waste

- Complete lyrics, beat alignment, prompts, city references, audio windows and
  camera specifications before renting. Build the compatible worker image first.
  Model download/loading still count as billable startup inside the four hours.
- Start with roughly 60–70 source clips, adjusted to musical phrases and exact
  duration. Create fast editorial cuts from useful contiguous footage. Multiple
  crops are reframing, not proof of new physical angles. Do not recycle a singing
  clip over different words or substitute repeated filler for missing coverage.
- Select one audio-capable model for the production where feasible. Build angle,
  landmark and audience variety through shot inputs; avoid repeated model swaps.
- Optimize memory placement, attention and encoding using supported settings.
  Any reduced native resolution or faster sampling profile is a quality tradeoff
  that must be assessed openly. Preserve the requested identity, singing and ten
  concert settings; an upscale is not native detail.
- Prepare alternative prompts and corrections in advance. Retain successful
  takes, classify failures, change the relevant cause and retry only rejected
  coverage. The first useful performance shots belong in the full-video project.
- Save each take promptly. Run suitable CPU bookkeeping while the GPU continues,
  without allowing unsafe completion before durable bytes exist. Final assembly
  should not keep the expensive GPU idle.

## Admission and continuation

Budget and retry permission are granted. Launch readiness is **not yet proved**:
the audio-driven adapter, resident-model queue and full production accounting
still require implementation and checks. PR #89 prepares six-minute support and
is not yet deployed. Do not install a historical one-attempt operator as a
shortcut to a new production scope.

Prepare one fresh signed production scope, one durable attempt/cost ledger and
an independent watchdog tied to the fixed deadline. Reconcile ambiguous provider
creation before another request. Retain all seven consumed grants, reservations
and the exact old unresolved-request handling. Revisions never reset spent time,
spent money, pending liabilities or accepted outputs.

Use the first planned shots to measure actual singing quality and usable seconds
per minute. Update the forecast for all missing coverage after each shot. If the
current configuration cannot fit the remainder, diagnose and optimize within the
same allowance; do not keep an idle GPU running while preparing code changes.
Stop paid work at the limits, retain the partial result and report the specific
unfinished requirements. A budget stop is not completion and does not revoke
the overall full-video goal. There is no further routine permission question for
retries that fit the already approved envelope.

## Evidence and current status

This planning update starts no GPU and incurs no new generation charge. No
application behavior is changed; previous passing duration/export checks are
retained without rerunning them. Runtime policy is 1.1.0; canonical bundle 0.1.0.
Live singing quality, full production throughput, recovery and final owner
creative acceptance remain pending.

Sources: retained five-second measurements in
`deployment/evidence/2026-11-17-duration-comparison/`, current worker source, and
[Runpod pricing](https://www.runpod.io/pricing). Related: issue #8 and PR #89.

## B07 input-transfer failure and bounded repair — November 17

PRs #90–92 installed the pinned S2V adapter, resident queue, 68 real audio
windows and ten anchors. First B07 batch `7e89330141794b85827d48341def92fe`
used H100 Pod `22hk9nt6u1t76z` at $4.39/hour. All model files downloaded, but
both first-shot attempts failed before inference. No take exists. Cleanup is
confirmed; complete provider inventory is empty. The current bill is not yet
reported. An empty billing response is not a zero bill.

Owner HTTP reads isolated the problem: first reference image 200, conditioning
WAV 500. Root preparation creates private WAVs that the unprivileged controller
cannot read. The repair verifies original checksums, changes only root-owned
conditioning WAVs to the existing asset service identity (mode 0600), and reads
all inputs under that identity. Preparation, admission and launch now require
this check. It does not make media public or broaden worker access.

A separate `singing-recovery` scope admits only this input correction after the
original failed batch has confirmed cleanup and no accepted take. It preserves
all original records and pending invoices. A signed, separate liability hold
conservatively covers the entire elapsed interval since original admission at
$4.50/hour, plus a preparation buffer. Original reservation rows are immutable;
project totals use the audited hold plus the new remaining reservation, at most
$18. No invoice is invented or settled. Time and price bounds must both fit,
and the original hard deadline remains 2026-11-17 12:46:41 UTC (7:46 a.m.
Eastern); this recovery can end earlier. A fresh exact-batch independent guard
is required. Further recovery cannot replay this grant.

Validation: root suite 213 checks (212 passed; root-only OS ownership case
skipped locally), 65 affected admission/cleanup/backup checks passed, 14 final
backup checks passed, contract and shell syntax passed. The root-only ownership
regression must run on the host before its source swap. Corrected GPU retry not
yet launched; full video and creative acceptance remain pending. Historical scopes,
the exact older unresolved request, and persistent cleanup remain preserved.
