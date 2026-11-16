# Approved one-second diagnostic — November 16, 2026

Status: FAILED — `gpu_out_of_memory`; zero takes. Automatic cleanup CONFIRMED.
The sole authorized create/render attempt is consumed. No third attempt is authorized.

John approved one additional shot, one Pod create and one render, at most $5 total
($4 Pod reservation plus $1 storage allowance), and 1,800 seconds from admission.
The first failed trial and its unsettled reservation remain preserved.

## Exact run

- Installed controller: `8e07ba3e8dfb9a250424bb4c8607cd1cac36cfe6` (PR #68).
- Upgrade: 43811745342; prepare: 43811849345; admission: 43811927800.
- Launch: 43812096376; independent deadline guard: 43811980342.
- Owner: `john-hoyos`; project: `project-894af8d869d6448290d34a762a736781`.
- Batch: `def5478dc85949139ca1c0ae404f9d1f`; Pod: `hzprkb5xllm8p0`.
- Admission: 2026-11-16T05:42:07Z. Fixed deadline: 2026-11-16T06:12:07Z.
- SECURE EU-RO-1, RTX 4090, $0.89/hour, 80 GB ephemeral disk, no persistent volume.
- Image: `ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:f724b9f32ac4ac780702072fd32e9d08254524ca81afd6aadeb87169904f993b`.
- Pinned Wan2.2 TI2V-5B, 1280x704, 24 fps, 25 frames, 50 steps, seed 42.
- Public Studio paid dispatch remains disabled; this is the isolated operator trial.

## Observed startup

- Provider allocation: 05:43:47.634 UTC.
- Private image download completed: 05:49:09 UTC; container start began 05:49:11 UTC.
- All pinned checkpoint files verified: 05:51:38.396 UTC.
- Worker claimed one attempt. Read-only process observations showed model load
  followed by generation preparation, with no traceback or CUDA OOM as of 05:54:46 UTC.
- RTX 4090 reports 24,564 MiB VRAM; container RAM limit is 82,999,996,416 bytes.
- Preparation was still CPU-active at 05:56:45 UTC: 1,044.28 cumulative CPU seconds,
  approximately 21.2 GiB process RSS and 76 threads. This does not establish a root cause.

The independent guard verified the exact owner/project/batch/deadline and matching
installed source before creation. Startup time counts against the same deadline.
An Actions success conclusion alone will not be treated as successful rendering.

## Validation of orchestration changes

Ten targeted fictional tests passed (trial gates and deadline guard), plus shell
syntax and whitespace checks. Existing historical recovery checks were preserved.
No extra render, Pod, paid generation API or paid host was introduced.

## Terminal outcome

- At 06:02:40.994 UTC the read-only snapshot captured 39/50 sampling steps,
  14,860 MiB GPU use and 100% utilization, with no captured traceback yet.
- The container emitted `gpu_out_of_memory` at 06:03:10.958 UTC; the controller
  recorded the sole attempt failed at 06:03:11.408 UTC.
- The controller confirmed automatic deletion at 06:03:19.988 UTC, approximately
  nine seconds after the failure and nearly nine minutes before the deadline.
- Connected Runpod inventory was empty and exact-Pod GET returned 404. No manual
  DELETE or second create/render occurred. No video was saved or accepted.
- Launch workflow success means cleanup completed, not successful rendering.

The exact failing allocation and whether all sampling steps completed were not
captured. Do not infer a proven VAE failure or relabel the first trial's unknown
failure as OOM. The candidate in draft PR #69 adds lower-memory execution and
safe phase retention; it is not built, installed or GPU-validated.

## Billing and remaining boundaries

Connected billing returned zero records at the post-deletion observation. Import
43814346326 completed at 06:04:59 UTC with `RETRIEVED_NOT_FINAL`, zero observed
cents and the full $4 reservation retained. This is reporting lag, not a zero-cost
settlement. Approximate GPU-only allocation cost was $0.29 at $0.89/hour, plus disk;
the actual final provider bill remains pending. The earlier trial's unsettled
liability remains separate and preserved.

Independent guard 43811980342 completed successfully. It remembered the allocation
removed by primary cleanup and emitted 27 ABSENCE_CONFIRMED records from
06:12:17.762 through 06:17:00.647 UTC. The fixed deadline plus five-minute observation
window is complete; no GPU remains. See guard-events.json. Automatic application-side
billing collection and broader B06 acceptance remain incomplete.
