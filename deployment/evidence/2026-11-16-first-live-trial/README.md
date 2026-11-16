# First live Wan trial — November 16, 2026 UTC

**Later continuation:** browser access resumed, the post-trial controller fixes were deployed, a new private worker was published, and provisional provider charges were imported. See [resumed deployment](../2026-11-16-resumed-deployment/README.md). The observed failed render and consumed allowance below remain unchanged; statements about the disconnected browser, undeployed fixes and zero billing records describe the earlier checkpoint.

Issue [B06 / #7](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/7), contract 0.1.0. This is the single authorized five-second shot, not the six-shot benchmark described in the original issue. Owner creative acceptance remains pending.

## Scope and immutable launch

- Owner `john-hoyos`; project `project-d5ec9ddbe55c4e12901fc2273bc4ea3d`; batch `7c811e6ab21a4392b0e3a80e331fc57a`.
- Approval: $5 total, $4 Pod reservation and $1 storage allowance, one Pod-create attempt, one render attempt, 1,800 seconds from admission. The separate DigitalOcean recurring rate is $14.40/month before tax. No new host, storage volume or domain was purchased.
- Admission 03:58:34 UTC; original deadline 04:28:34 UTC. Startup and downloads consume this deadline. The clock was never reset.
- Installed host/source `387555fd40a57f1fcda2d0abff1fff20d93e4075`, verified upgrade [43801074417](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43801074417).
- Prepare [43801160386](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43801160386), admit [43801254838](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43801254838), launch [43801863653](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43801863653).
- Pod `xhd7cd3nqsrcca`, Secure Cloud, EU-RO-1, RTX 4090 24 GB, host CUDA 13.2, quoted and observed GPU rate $0.89/hour, 80GB ephemeral disk, no public inbound ports or persistent volume. Allocated 04:04:53.707 UTC. The create allowance is consumed.
- Private image `ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:c1b181cf4fb83f6451c721dc1035d55966a3757bf6567636bcbeff77f740fbe2`.
- Prompt: “A small blue sailboat moves slowly across a calm lake at sunrise, steady wide camera, no text.” Frozen 1280×704, 24 fps, 50 steps, seed 42, five-second target; Wan2.2 TI2V-5B, pinned upstream/model revisions in startup.json.

## Observed execution

`startup.json` retains bounded provider metadata and actual boot-log lines. Runpod successfully downloaded the private image at 04:05:33 UTC. The container started 04:05:35 UTC and all 13 pinned model files, 34,201,537,147 bytes, passed their hashes at 04:07:50.585 UTC. The worker claimed the admitted shot with its scoped credential.

Several samples during preparation showed roughly 3,196 MiB GPU memory and 0% GPU use while inference PID 74 consumed CPU. The allocated CPU was AMD EPYC 7352 with AVX2, no `avx512_bf16`, 13.6-core quota, 82,999,996,416-byte memory limit, and 76 inference threads. Pinned upstream code uses a bfloat16 T5 encoder on CPU in this profile. Slow CPU text encoding is a plausible bottleneck, not a profiler-proved attribution. A follow-up should compare GPU text encoding or a supported CPU dtype/thread setting under a newly approved trial; no performance speedup is claimed here.

At 04:17:52 UTC the GPU was observed at 100% utilization and 21,750 MiB allocated while the 50-step denoising loop began. The last captured sampling progress was 49/50 at 04:25:25 UTC. At04:25:42.606UTC the attempt failed with `render_failed`; no take or durable video was committed. Detailed child diagnostics were discarded by the original worker, so the exact failure is unknown. A GPU-memory or output-encoding cause is not established. This is not successful Wan output acceptance.

`final.json` records batch `failed`, cleanup`confirmed`, one failed attempt and zero takes. The operator confirmed deletion at 04:28:40.386 UTC,6.386 seconds after the original deadline. Independent provider inventory returned no Pods, and GET for the exact Pod returned 404. No assistant/manual DELETE was used. This proves automatic deadline deletion; failure-triggered immediate deletion did not work in the deployed release. The failed attempt did not close its batch until deadline reconciliation. Container restart attempts were observed, but the failed lease prevented another admitted render attempt.

Estimated GPU compute through the confirming observation is about $0.35 from elapsed time at $0.89/hour, plus disk charges; this is not the final provider bill. No successful output exists to test retention after this GPU deletion. Synthetic retained-media/recovery acceptance remains separately proved.

## Independent shutdown coverage

The persistent cleanup service runs outside the web process. The private operator also reconciles terminal/deadline cleanup. Independent GitHub guard [43801296860](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43801296860) started with the exact original scope and deadline. Its one-time receipt aged beyond the launch freshness window during setup, so guard [43801724802](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43801724802) refreshed readiness against the same batch and same original deadline. The first guard was not canceled. The second confirmed provider access, delivered its receipt and was independently verified `in_progress` at the same reviewed commit before the sole create.

Both deployed guards initially saw no Pod and only rescan after the deadline. If primary cleanup removes the Pod early, their final `NO_ALLOCATION_OBSERVED` is an evidence limitation; it is not proof of failed primary deletion or a successful backup deletion. A subsequent source fix refreshes readiness while watching and remembers matching Pods before the deadline. It also keeps watching if later receipt delivery fails. Four targeted fictional guard/freshness tests and shell syntax checks passed. This fix does not alter the current running trial or claim a second GPU test.

## Cost and release boundaries

Connected Runpod billing initially returned no records. This is billing lag, not a final zero-cost invoice. Cumulative authoritative observations can be imported with `trial-observe`; fully automatic application-side billing retrieval remains pending. Preserve the reservation until final settlement is independently confirmed.

Owner browser access and independent recovery are verified in the [access/recovery record](../2026-11-16-access-recovery/README.md). Public Studio render controls still generate synthetic fixtures. The private one-attempt operator and real worker receiver do not authorize unrestricted paid rendering, another trial, or human creative approval.

## Prepared corrections and next gate

The reviewed follow-up source closes an exhausted batch in the failure transaction and during reconciliation, so cleanup no longer depends on another claim or the final deadline. Worker failures now persist a local terminal marker to prohibit rerender on container restart, classify bounded diagnostics into safe codes (including GPU OOM/model-load/generation/video-encoding/output-validation), and preserve those codes in the controller. Raw prompts and exception text are not logged or sent as diagnostics. The original failure's exact cause remains unknown; these changes improve the next diagnosis and do not claim to fix that unknown cause.

The post-trial upgrade path permits preserved historical jobs only when every lifecycle row is terminal and cleanup confirmed; unsettled billing remains intact. Deploy the controller before publishing/using a rebuilt worker, because the old host accepts only the former generic failure codes. Rebuild and privately publish a new immutable worker digest, verify it, and update the concrete next-trial proposal before seeking authority for another paid attempt. The existing one-attempt allowance is consumed.

The connected browser disconnected after successful sign-in and workflow dispatch. Final hosted state was independently read through authenticated HTTPS. Browser disconnection blocks the currently available workflow-dispatch route; source fixes are prepared, not deployed, and the old worker image remains installed. Reconnect the browser to complete deployment/build preparation. No second paid trial was launched.

## Final guard outcomes and validation

Guard43801724802 observed the allocation and first reported `ABSENCE_CONFIRMED` at04:28:37.627UTC,3.627seconds after the deadline, then repeatedly confirmed absence through its five-minute reconciliation window. Original guard43801296860 first scanned after the Pod had disappeared; it reported `NO_ALLOCATION_OBSERVED` and exited1. This is the documented early-removal evidence limitation, not a remaining live resource. The evidence does not isolate which concurrent automatic cleanup process issued the winning DELETE.

Post-trial source validation:29worker/live-execution/integration tests passed;8hosting tests plus the updated safe-code failure/cleanup regression passed;3guard tests and1freshness regression passed; Python compile, shell syntax and git whitespace checks passed. Initial local test-edit mistakes were corrected before the passing runs. No second GPU render was performed. Final owner HTTPS observation showed failed batch, confirmed cleanup, one failed attempt and no take.

The latest connected billing observation at04:33UTC still contained zero records. No settlement was fabricated and no reservation was released. Browser disconnection also prevented importing that observation through the hosting workflow; the raw provider observation is retained here for later reconciliation.
