# WAN duration comparison — measured result
November 17, 2026 · John Hoyos · B06

**The five-second video succeeded. The continuous 15-second video was not attempted because the approved continuation check rejected the remaining time. The full comparison is incomplete.**

## Available output

`wan-05s.mp4` is exactly 5.000 seconds, 1280×704, 24 fps, 120 frames, H.264, with no audio. It is a real Wan render, not a fictional test. The preserved original has 121 frames (about 5.042 seconds). The viewing copy removes only the final frame; playback speed is unchanged. No 15-second video or side-by-side comparison was fabricated.

Settings: Wan2.2 TI2V-5B; H100 80GB HBM3; seed 42; 50 sampling steps; blue sailboat on a calm lake at sunrise; one continuous shot. Both planned durations used the same settings and prompt.

## Measurements

| Measurement | Five-second result |
|---|---:|
| Model load | 55.33 seconds |
| Generation, including text encoding and sampling | 177.81 seconds |
| Video decode and encode | 11.95 seconds |
| Render and verification | 273.06 seconds |
| Upload | 0.90 seconds |
| Peak allocated VRAM | 18.94 GiB |
| Peak reserved VRAM | 25.04 GiB |
| Startup before the render claim | 1112.55 seconds (18m 33s) |
| Allocation request through confirmed cleanup | 23m 17s |

Render-and-verification includes overhead beyond the named model stages. Startup includes image transfer, model transfer and verification. A model-file integrity check failed at 1:02:53 a.m. Eastern. The same Pod restarted and downloaded the missing 11.4 GB text encoder again; the other files were retained. All pinned files passed verification at 1:07:09 a.m. The generic failure log does not distinguish a wrong byte count from a checksum mismatch. No inference was retried.

## Why 15 seconds did not run

| Continuation check | Required / allowed | Observed / projected | Result |
|---|---:|---:|---|
| Remaining time | 1812.40s (30m 12s) | 1084.40s (18m 04s) | Failed |
| Reserved-memory projection | Up to 71.26 GiB | 69.68 GiB | Passed |

The time check uses the approved conservative projection: model load + 9× the measured generation time + 3× decode/encode + upload + 120 seconds. Its estimate is not a measured 15-second runtime. The memory projection is also an estimate, not proof that the longer render will fit.

The fixed 45-minute deadline began at admission, 12:44:51 a.m. Eastern. It was not extended. The batch is recorded as failed/incomplete because one of two requested shots is missing; its single actual render attempt succeeded. This consumed scope must not be reset or replayed. Completing the comparison requires a new isolated, separately authorized execution window with enough startup allowance. No further rental or generation has been started.

## Cost and cleanup

| Cost item | USD |
|---|---:|
| Quoted GPU rate | $4.39/hour |
| Five-second render and upload, attributed compute estimate | $0.3341 |
| Startup compute estimate | $1.3567 |
| Total elapsed compute estimate through observed cleanup | $1.7036 |
| Provider charge for this run | Pending |

These estimates are not an invoice and exclude any separately billed disk/storage. The first billing query returned no records; this does not mean a zero charge. The $4 Pod reservation is retained pending reconciliation. The separate earlier one-second run now has a posted $1.3606901543 charge, including disk; it is not included in this comparison's estimate.

One Pod was created on the first allocation request in US-MO-1. The video was committed at 1:11:46 a.m.; cleanup was confirmed at 1:11:53 a.m. Complete provider inventory was empty afterward. The independent guard remains scheduled through 1:34:51 a.m. Eastern, including monitoring the exact historical unresolved request. Persistent cleanup and all earlier reservations are preserved.

## Visual review and limits

Five sampled frames show a coherent blue boat, broadly consistent sails and stable shoreline/mountains. The generated boat visibly has two sails, although the prompt specified one. This is a prompt-adherence miss. Sampling frames does not establish flicker-free motion; full playback and owner creative acceptance remain pending. There is no 15-second output, so no quality comparison between durations is possible. H100 success does not establish compatibility with a 24 GB GPU.

## Evidence

The export workflow verified checksums, resolution, frame rate, frame count and full decoding after Pod deletion. The downloaded ZIP and both video hashes were independently matched to those records. No paid rerender was used for verification. Existing fictional checks were not repeated without a code change; the later report-wording correction passed syntax and whitespace checks.

- [Launch and cleanup](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/44026660382)
- [Export and retained artifact](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/44029555013)
- [Independent deadline guard](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/44026572576)
- Issue: [B06 #7](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/7)
- Deployed commit: `af3b013a1d485cc5278c6a2101ed62a673ef8032` (PR #87).
- Image: `ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:a3bbb9a2aba572de26609c5a4411dd3f705625fa33a9a97ae81193deb1719367`.
- Batch: `1226612319814a0d85c2d0d62a9c4357`; project: `project-0ebe9e6ddab243cf8e91924211593c27`.
- Original SHA256: `d1ca8eb36f151c8ca18fd29a692b531e2476ecdb53f36f1ad29967d84964650d`.
- Exact five-second copy SHA256: `d5b03a8c6a84678b284548c882dc924a817fe0f3d0e4ef35aad9258d0d5228f2`.
- Export artifact 14304462063 ZIP SHA256: `5a98ea02452be2f28ecae5abac70a683e0390aa3b8b281e0f4e0f267f195f533`.

Next recipient: B01/B06 GPU benchmark work. Preserve this take, reconcile billing, review the actual video with John, and use these measurements when preparing the separate continuous 15-second scope.
