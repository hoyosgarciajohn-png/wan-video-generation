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

## Next deployment work

1. Finish the GPU image build and offline imports/fixture verification.
2. Publish the verified image privately, capture its registry digest, and verify
   an authenticated pull. Keep credentials out of source and evidence.
3. Verify controller HTTPS, durable storage, independent watchdog and actual
   installed authority before using the approved $5 / 1,800-second / one-attempt
   Runpod trial. The trial has not been used.

GitHub Container Registry is a suitable next candidate: its official billing
page currently states that container image storage and bandwidth are free,
including private images. New packages default to private. This is a researched
option, not a registry already configured for Runpod. External private pulls
require scoped credentials; no new token or broader access was created here.

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
