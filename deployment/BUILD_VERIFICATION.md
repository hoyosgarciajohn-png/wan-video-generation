# On-demand image build verification

This is preparation for an operator-selected local build host. No GitHub workflow,
remote CI trigger, registry push or hosted deployment is added. The current host
has no Docker, Podman, buildctl or buildkitd. The checked-in
`BUILD_GATE_STATUS.json` therefore keeps every image/runtime/inference gate
**UNVERIFIED** and every image ID null.

## Plan without building

Run from a reviewed checkout. Choose a fresh output directory outside the repo:

```sh
python deployment/build_verify.py --target cpu --output /home/john/wan-build-evidence/cpu-plan
python deployment/build_verify.py --target gpu --output /home/john/wan-build-evidence/gpu-plan
```

Default execution copies a small allowlisted, tracked-file source context,
records the commit plus dirty-state flag and per-file SHA-256 inventory, copies
and hashes the smoke helper, and writes `manifest.json` with planned argv arrays.
It does not call Docker, pull layers, install tools, download weights or run any
container. Existing evidence directories are never overwritten. Generated
artifacts, node_modules, secrets, weights and arbitrary repository files are
excluded from the build context. This also avoids sending the GPU Dockerfile's
otherwise broad root context to the daemon.

`source_dirty: true` is useful preparation evidence, not a verified release.
Commit and review all source changes before actual build execution. The verifier
rejects modified/missing prepared context files or helpers. It does not silently
upgrade an old plan in place: execution gets a fresh output directory and a fresh
inventory from the current checkout.

## Execute later on a compatible local host

Use a local Unix-socket Docker daemon running native Linux amd64, with the `runc`
runtime and enough disk/network capacity for the pinned image layers and package
installation. Remote SSH/TCP contexts and automatic cross-platform emulation are
refused. DOCKER_CONTEXT cannot override a validated local endpoint during the
build. The GPU image is large even though its verification does not use a GPU.
Do not run these commands on an unapproved paid build host.

```sh
python deployment/build_verify.py --target cpu --output /home/john/wan-build-evidence/cpu-run-001 --execute
python deployment/build_verify.py --target gpu --output /home/john/wan-build-evidence/gpu-run-001 --execute
```

If the exact pinned model files already exist locally, optionally verify them
read-only as part of a separate fresh GPU verification run:

```sh
python deployment/build_verify.py --target gpu --output /home/john/wan-build-evidence/gpu-run-with-weights --weights /home/john/wan-models --execute
```

The program never downloads model weights. Supplying `--weights` requests checksum
verification of existing files; this can read many gigabytes but performs no
inference. Omit it when files are unavailable and retain UNVERIFIED for that gate.

Each command's stdout/stderr goes to a named log; exit status and log SHA-256 are
recorded. Docker `--iidfile` captures the actual build image ID. Inspect and every
smoke run use that immutable ID rather than a mutable local tag. `image_id` is a
local image content ID; `repo_digests` may legitimately be empty for a locally
built image. Neither is invented from a Dockerfile input digest. Keep the
manifest, logs, fixture result and output together for review.

## What each gate proves

| Gate | Actual operation when `--execute` is used | Does not prove |
|---|---|---|
| image_build | Build pinned CPU or GPU Dockerfile from the inventoried isolated context | Runtime, CUDA execution or deployment |
| image_identity | Inspect the build's immutable ID and confirm Linux amd64 | Registry publication |
| CPU runtime_smoke | Import controller, serve built static Studio/health, require session auth on loopback | Production HTTP readiness or browser-native acceptance |
| GPU runtime_smoke | Import Torch 2.8/FlashAttention/WanTI2V, check Python/ABI and installed source revision marker | CUDA inference or valid model bytes; source archive checksum is enforced by the Docker build helper |
| fixture_smoke | Run the actual worker's synthetic CPU fixture, verify durable result/output checksums and zero GPU cost | Wan-generated quality or GPU performance |
| weights_verification | Verify every existing checkpoint file against model.lock.json | Loading/inference performance or correctness |

Smoke containers use `--network none`, `--runtime runc`, a read-only root,
capability removal, no-new-privileges and explicit hidden GPU devices. They do
not receive `--gpus`, provider credentials or a worker service token. Fixture
output is a separate external writable mount. Containers use `--rm`; build
images/cache and evidence remain for review and are not pruned automatically.
No cleanup command removes unrelated local images or data.

CUDA inference, paid GPU benchmarking and hosted deployment remain UNVERIFIED
even after every prepared image/fixture gate passes. B06 needs its own approved
dollar ceiling/runtime envelope and live evidence. The GPU benchmark command in
`workers/gpu/README.md` is a separate operation; this script does not invoke it.

## Evidence collected in this preparation batch

- Fresh command lookup found none of Docker, Podman, buildctl or buildkitd.
- Both CPU/GPU plan paths were exercised in temporary external directories. They
  produced inventories/commands with zero executed Docker commands and only
  UNVERIFIED gates; temporary plan directories were removed afterward.
- `python -m unittest deployment.test_build_verify -v`: 8 tests pass for source
  exclusion, default no-build behavior, unavailable/remote daemon refusal,
  environment precedence, context tampering, immutable image-ID usage and fixture
  checksum failures. The execution-path regression uses a mocked subprocess;
  its temporary PASS records are test data, not image-build evidence.
- No CI was triggered, layers/tools/weights installed, container started, CUDA
  executed, cloud resource created or provider charge incurred in this batch.

After a compatible host runs the explicit commands, the Command Center reviews
its actual manifest/logs before updating image gates. Keep
`docs/DEPLOYMENT_READINESS.md` and the B01 build record honest about any remaining
container, browser, inference and production-release gaps.
