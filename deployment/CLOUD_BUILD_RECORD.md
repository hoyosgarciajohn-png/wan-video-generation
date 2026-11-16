# Cloud build execution record — November 15, 2026

John selected cloud builds. Docker Desktop is not required on his Windows PC.
The private repository uses manual GitHub Actions on standard Ubuntu 24.04
runners, with one target at a time and a 35-minute job ceiling. No Runpod key,
GPU device or model checkpoint is supplied. The existing $0 Actions paid budget
was observed with usage blocking and was left unchanged.

## Observed runs

| Run | Target | Observed outcome |
|---|---|---|
| [43772264998](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43772264998) | CPU | PASS: actual build, image identity, HTTP/auth smoke and synthetic worker fixture; downloaded evidence verified and video fully decoded. |
| [43772384860](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43772384860) | GPU | Stopped before build: 34.69 GiB free, below the 40 GiB floor. Expanded only the unused SDK cleanup list. |
| [43772649695](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43772649695) | GPU | Stopped before build: Android SDK cleanup exceeded 120 seconds. Raised its per-directory timeout to 300 seconds; overall job limit unchanged. |
| [43773064856](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43773064856) | GPU | Runner capacity PASS; image build stopped at Wan eager CUDA import. The CPU builder has no NVIDIA driver. |

The initial workflow parser rejected a job-level `runner.temp` expression before
allocating a runner. PR #35 moved this lookup into shell steps. PR #34 added the
workflow; PR #36 retained CPU evidence and expanded cleanup; PR #37 bounded the
slower cleanup operation. YAML parsing alone did not catch the GitHub expression
context error. All corrections are reviewable in the repository.

## CPU evidence

Source: `18bbdfdcbe266d11db48b6f21cfa9441775cf5c3`.
Actual local image ID:
`sha256:6ce961dc0e796175c7755d4723599aa73ec60bf47b40419374f819597f54263e`.

`deployment/evidence/2026-11-15-cpu` retains original logs/manifest, runner report,
fixture bytes and review. The fixture is H.264, 320x180, 24 fps, 48 frames, two
seconds. It is synthetic, not Wan-generated. Source/context/helper checksums,
four command logs and output hashes were verified after artifact download.
The original image existed only on the temporary runner and was not published.
A local image content ID is not an available registry digest.

## Current deployment work

Private publication is complete; see the latest record below. Runpod's actual
layer download is still unverified. Finish the private pull credential, funded
account, approved controller host, HTTPS/storage and installed live authority
plus both cleanup monitors before using the approved $5 / 1,800-second /
one-attempt trial. The trial remains unused.

GHCR publication used the workflow's temporary GITHUB_TOKEN. External Runpod
pulls require a separately provisioned scoped credential; none has been installed.

Sources reviewed November 15, 2026:
- https://docs.github.com/en/billing/concepts/product-billing/github-packages
- https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry

## GPU import correction

The locked Wan source calls `torch.cuda.current_device()` while defining its T5
class. The CPU-only build now verifies Torch/FlashAttention linking and Wan
source compilation without executing Wan. It explicitly leaves Wan CUDA import
unverified. No CUDA monkeypatch, upstream source change or fake device is used.
Two targeted tests prove source checking does not execute import-time GPU code
and rejects broken/missing source. Seven preflight tests also pass. The offline
source-bound plan was regenerated and remains disarmed with all nine gates open.

## Accepted cloud checkpoint

- Corrected CPU: [run 43773935725](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43773935725), all four image/identity/runtime/fixture gates PASS.
- Wan worker image: [run 43774509988](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43774509988), all four offline gates PASS; actual Torch/FlashAttention import and 28 Wan Python source files compiled. Wan CUDA import remains UNVERIFIED_REQUIRES_GPU.
- Both downloaded artifacts passed source/context/helper, command log, image identity and fixture checksum review. Both two-second synthetic H.264 clips were fully decoded. Final evidence is in `deployment/evidence/2026-11-15-{cpu,gpu}-final`.
- GPU run 43773913410 was stopped at capacity on a smaller runner before image build; PR #39 adds the unused Haskell SDK fallback without lowering the 40 GiB floor. The successful final runner had 40.68 GiB free before needing that fallback. Future runners still must pass the guard.
- The browser connection timed out before the last manual dispatch. A temporary PR-opened workflow ran the same reviewed source through the connected repository controls. PR #40 was closed without merging; main retains only manual dispatch.

CPU source checkout: `a5af75b5da18bb668a8334b6418333dec2f5dc77`. GPU checkout:
`423d1fdcab7dedc442714079b5a591bbf78095ec` (PR #40 synthetic merge ref). Their
allowlisted image inputs and verifier/helper match the final reviewed main source.
Images were discarded with the temporary runners; publication and authenticated
pull remain the next task. No paid builder, Runpod Pod, storage volume, model
download, GPU render or production deployment was created.

At the pre-dispatch billing review, $4.91 included compute and 0.5 GB artifact
allowance remained, with $0 billable Actions usage and an existing $0 paid budget.
Only small artifacts were retained for one day. These are allowance observations,
not a finalized post-run bill. No billing limit, plan or subscription was changed.


## Private publication accepted — November 16 UTC

[Run 43777990153](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43777990153)
completed successfully in 12 minutes 28 seconds on source
`e9f37eddf3297695af7f4f2ed5544c17f0885039` (PR #42). This publication workflow has
50-minute job, 30-minute build and 17-minute push/verification limits. It uses the
existing standard CPU runner and never receives a Runpod credential or GPU.
The tested image is now retained privately:

`ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:c1b181cf4fb83f6451c721dc1035d55966a3757bf6567636bcbeff77f740fbe2`

Private visibility, denied anonymous access and authenticated registry manifest/
config verification passed. Registry config matches tested Docker image ID
`sha256:a613ab8cf437275833720e431538d87df9164e31bdf7509733cd6f1fcce9f5d0`.
Compressed layers are 5,220,107,260 bytes without model weights. Runpod layer
pull remains unverified. Original build/publication evidence and fixture bytes
are retained in `deployment/evidence/2026-11-15-private-publication`; all 32 source
files, four log hashes, helper hashes, image identity and fixture checksum matched,
and the actual downloaded synthetic fixture fully decoded.

PR #43 prepared the production WSGI host and two cleanup layers. Their source
checks pass, but no host, TLS, storage recovery or shutdown service is installed.
Runpod currently shows zero balance and no private registry credential. The
minimum top-up displayed is $10; none was submitted. No GPU, network volume,
hosting subscription or paid builder was purchased. Final post-run GitHub billing
was not retrieved. The approved $5 / 30-minute / one-attempt trial is unused.
