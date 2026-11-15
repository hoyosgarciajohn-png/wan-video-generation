# First real Wan run: launch prerequisites

Status on 2026-11-15: **BLOCKED; no image built and no Wan inference run.**
This is an operator handoff, not a launch authorization. The existing public remote
worker integration renders CPU fixtures only. A separate trusted test bridge can
rehearse pinned Wan-profile records with synthetic CPU-generated media and a fake
provider; it has no live-provider factory. Passing that integration does not
establish CUDA compatibility, creative quality or cost.

## Fresh host investigation

The available workspace is Linux x86_64, Python 3.12.14, with approximately
57 GiB free at inspection. Command lookup found no Docker, Podman, buildctl,
buildkitd, nerdctl, runc, nvidia-smi or nvcc. Neither the Docker socket nor the
containerd socket exists at its standard path. There are no `/dev/nvidia*`
devices. Python module discovery found no torch, flash_attn or wan installation.
A temporary AF_UNIX socket bind failed with `PermissionError`, errno 1; the
probe cleaned up its path. Thus the earlier BuildKit socket restriction still
applies. Merely installing a client or another BuildKit binary is not a fix.

The currently exposed service tool catalog provides no RunPod, SSH, Docker or
compute-host connection. No existing compatible free build host was discoverable
through those capabilities. Account credentials, private hosts and environment
secret values were not searched. No remote CI, installation, large download,
container, provider resource or public deployment was started.

## Required inputs and acceptance evidence

| Requirement | Input needed | Evidence before progressing |
|---|---|---|
| Reviewed source | Exact reviewed commit | Clean source inventory in build manifest |
| Build host | Existing approved Linux amd64 host with local Docker/runc daemon and sufficient disk/network | Native daemon preflight passes; no remote paid context |
| GPU image | Build from `workers/gpu/Dockerfile` through `build_verify.py` | Actual immutable image ID, successful build/import/fixture logs |
| Model storage | Persistent local directory holding the exact 13 locked files, 34,201,537,147 bytes total | `workers.gpu.weights verify` or verifier checksum gate passes |
| GPU host | Explicit GPU model, memory capacity, driver and NVIDIA container runtime | Recorded device/driver information and successful container CUDA check; memory sufficiency measured, not assumed |
| Network/storage | Trusted HTTPS controller origin, worker outbound access, private persistent worker state and writable input cache | TLS verification; separate-root upload/completion replay exercised for chosen deployment |
| Worker authorization | Trusted issuance for owner/project/batch/worker, appropriate token lifetime | Secret injected as `WAN_WORKER_TOKEN`; never an argv value or report attachment |
| Budget | Project dollar ceiling, maximum runtime, permitted retry count | Explicit approval recorded and admission enforced server-side |
| Cleanup | Provider resource identifier and independent deadline/cleanup monitor | Stop/delete observed and billing reconciled, including failed worker paths |
| Wan admission | Reviewed real-execution controller/provider adapter | Real model allowlist, reservation, deadline and fencing checks pass before credential issuance |

Do not select a GPU or claim a minimum VRAM from the CPU fixture. The pinned
TI2V-5B profile and its CPU offload behavior need a real benchmark. Build capacity,
model storage and GPU capacity are separate requirements. Preserve room for image
layers, build cache, model files, output and temporary files; the model size alone
is not a safe disk allocation.

## Software blocker before remote Wan execution

`services/controller/worker_transport.py` rejects non-fixture/nonzero-budget jobs
by default. A trusted server may explicitly install `RealJobBridge.for_testing`,
which accepts only the built-in fake provider and durable simulated authority.
It links canonical pinned-profile batches to reservation, lifecycle, scoped
credentials and verified completion, but is not live activation. Therefore renting
a GPU and setting the worker URL will not make the product render Wan jobs.

The next implementation must add a separately reviewed live-provider factory,
authenticated approval and provider/configuration binding to the rehearsed
admission/lifecycle/credential path. Do not remove the fixture guard to bypass this work. Token
expiry must cover the bounded operation and recovery window, or credential
rotation/recovery must be implemented: the existing worker journal binds to the
same credential and fails closed after rotation. Model verification currently
runs in each inference process and belongs in the runtime budget.

The worker transport caps an MP4 at 32 MiB. The first benchmark must verify output
size fits; changing this cap requires a coordinated server/client review.

## Build and stage, in order

1. On the approved compatible build host, execute the commands in
   `deployment/BUILD_VERIFICATION.md`. Keep manifests, logs and immutable image
   identity. GPU image import verification requires no GPU, but it is a real
   image operation and remains unverified here.
2. Stage the locked weights once on persistent storage using
   `python -m workers.gpu.weights download /models` in the built image. This is
   an explicit future 34.2 GB download, not an operation run in this workspace.
   Verify all files before the GPU billing window where possible.
3. Complete the real-execution admission/provider work above. Validate the
   chosen TLS controller and secret injection without printing tokens. Use
   writable private mounts for worker output/journals and reference cache;
   model weights are read-only during inference.
4. Obtain the specific budget/runtime approval and arrange independently
   enforceable cleanup. Confirm the selected GPU and driver work with the
   pinned image before admitting the one-shot benchmark.
5. Use the benchmark profile and invocation in `workers/gpu/README.md` with
   the actual image ID. Start with one 5-second, no-reference fictional shot,
   fixed seed42, 1280x704,24fps,50steps. Do not schedule a music video or film
   until the one-shot cost, time and cleanup evidence is reviewed.
6. Record load/generation/upload/commit times, peak allocated/reserved VRAM,
   actual provider charge, output checksum and cleanup result. Human creative
   acceptance remains a separate decision. A failed run is useful evidence;
   it must not be recorded as a successful inference gate.

## Static Dockerfile audit scope

The Dockerfile pins both base images by digest, installs hash-locked dependencies,
checks Python3.11/Torch2.8/C++11 ABI, verifies the official source archive checksum,
and imports FlashAttention/WanTI2V during the build. The wheel filename matches
that declared Python/Torch/ABI combination. Required local worker contracts,
fixtures and source are copied. The worker uses `jsonschema` directly and does
not require the controller's `scripts.validate_contract` module.

No concrete missing local import or conflicting declared pin was found in this
inspection. The checks in a Dockerfile are executable requirements, not evidence
that they have passed. Resolving all package wheels, loading shared libraries,
importing upstream code, runtime CUDA compatibility and sufficient VRAM remain
unverified until the corresponding commands actually run. Existing image gate
statuses remain unchanged.
