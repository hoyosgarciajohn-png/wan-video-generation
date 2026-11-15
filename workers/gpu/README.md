# B01 Wan GPU worker

Issue [#2](https://github.com/hoyosgarciajohn-png/wan-video-generation/issues/2). Shared contract 0.1.0. Source baseline `c9c364ab3f68cfca24489715ab0cd8419d0d4f60`. Owned paths are `workers/gpu/` and its tests.

This worker processes one frozen attempt, maintains its lease, validates output with ffprobe, uploads it to the controller through an authenticated stream, and submits a completion manifest. A controller determines whether another attempt may start. Fixture execution uses synthetic silent blue video and performs zero provider requests.

## Local verification

Run from the repository root with the B00 development environment and FFmpeg installed.

```sh
.venv/bin/python scripts/validate_contract.py --media-root fixtures
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s workers/gpu/tests -v
.venv/bin/python -m workers.gpu.cli fixture \
  --output-root /tmp/wan-b01-smoke \
  --result /tmp/wan-b01-smoke/result.json
```

The result includes shared `asset` and `take` records, measured media metadata and execution metrics. The video resides under `projects/{project_id}/attempts/{attempt_id}/output.mp4`. `completion.json` stores the frozen input identity and manifest. A process lock serializes attempts sharing that path. Publishing uses fsync and an atomic link. Identical completion replay reuses the saved output. Conflicting inputs, corrupt bytes and incompatible output metadata are rejected.

## Pinned runtime

`model.lock.json` records the official source revision, source archive SHA-256, checkpoint revision, SHA-256 and size for all 13 required checkpoint/config/tokenizer/model-card files, and runtime image digests. Checkpoint download totals 34,201,537,147 bytes. Weights stay on the model mount.

The source pin is an official July 2025 TI2V-capable revision. This bounds the import surface to the initial Wan models. Python 3.11, PyTorch 2.8.0, CUDA 12.8, torchvision 0.23.0 and FlashAttention 2.8.3 form the selected runtime. `requirements.lock` hashes the resolved Python dependencies. `flash-attention.lock` pins the official CPython 3.11, CUDA 12, Torch 2.8, C++11 ABI wheel and its published digest. The Docker build checks the Python/Torch ABI and imports both FlashAttention and WanTI2V. CPU tests currently ran on Python 3.12.14.

```sh
docker build --platform linux/amd64 --progress plain \
  -f workers/gpu/Dockerfile -t wan-worker:b01 .
docker image inspect wan-worker:b01 --format '{{.Id}}'
docker run --rm --network none \
  --mount type=bind,src=/tmp/wan-b01-smoke,dst=/outputs \
  wan-worker:b01 fixture --output-root /outputs --result /outputs/container-result.json
```

Record the final built image digest and build log before B01 acceptance. The current host has no Docker/Podman or CUDA GPU. A subsequent local attempt installed checksum-verified BuildKit 0.35.0, but its required internal Unix socket was denied by the host. Image build and runtime import verification remain pending. The exact attempt is recorded in `evidence/BUILD_ATTEMPT.md`. Dependency resolution and image digest lookup succeeded. Reproducibility covers pinned build inputs. GPU bitwise determinism requires measurement on the target host.

## Model and duration profile

Use `model.lock.json`'s exact `profile` for both the batch and attempt. Revision 1 accepts 1280×704 or 704×1280, 24 fps, 50 steps, a fixed integer seed and up to 5,000 ms. The sampling solver is UniPC, shift 5, guidance 5, CPU T5 and model offload enabled, with converted model dtype. Prompt expansion is disabled. An optional single image must match the frozen output dimensions, belong to the same project/owner, and pass the shared size/checksum check.

Requested duration rounds upward to the first `4n+1` frame count covering the request. A 2,000 ms shot renders 49 frames, reported as 2,042 ms. A 5,000 ms shot renders 121 frames, reported as 5,042 ms. The timeline can trim to the requested duration. Creative acceptance remains with John in the live session.

## Scoped remote transport

The 0.1.0 shared records stay intact. The controller implements these authenticated envelopes; the current integrated server admits only synthetic fixture rendering.

| Operation | Request | Response expected by B01 |
|---|---|---|
| POST `/v1/worker/claim` | Empty JSON object, bearer credential scoped by B02 | 204, or `{contract_version, project, batch, attempt, shot_snapshot, input_assets}` using shared record definitions |
| POST `/v1/worker/attempts/{id}/heartbeat` | `{lease_id, progress}` with progress from 0 to 1 | `{lease_expires_at}` with a timezone-bearing timestamp |
| POST `/v1/worker/attempts/{id}/complete` | `{lease_id, output_asset_manifest: {asset, media}}` | One shared take record, including on identical replay |
| PUT `/v1/worker/attempts/{id}/artifact` | Raw MP4, exact Content-Length, X-WAN-Lease-ID and X-WAN-SHA256 | `{bytes, sha256, object_key}`; identical replay accepted |
| GET `/v1/worker/attempts/{id}/inputs/{asset_id}` | Lease header; reference must belong to frozen claim | Bounded bytes verified against frozen size/checksum |
| POST `/v1/worker/attempts/{id}/fail` | `{lease_id, code}` | Any successful JSON acknowledgment or 204 |

`media` contains `duration_ms`, `width`, `height` and `frame_rate`. The worker requires an HTTPS backend, disables redirects and reads the bearer credential only from the environment. Claims receive no automatic network retry because an ambiguous claim needs server reconciliation. Completion ambiguity retains the journal and never sends a render-failure event. B02 must support completion replay after a committed take even if that lease has since expired. An uncommitted fenced lease must be rejected.

The controller and worker use separate filesystem roots. Outputs stream to the controller before completion; the controller validates size, checksum, namespace, lease and MP4 metadata before committing a take. Artifact transfer is capped at 32 MiB. References download into a writable worker input cache and are checksum-verified before publication. Current fixture claims contain no references; real Wan admission remains pending.

Run one remote fixture attempt with service-issued credentials supplied through the environment (never command-line arguments):

```sh
# WAN_WORKER_API_URL and WAN_WORKER_TOKEN are injected by secret configuration.
python -m workers.gpu.cli worker \
  --output-root /srv/wan/worker-state --input-root /srv/wan/input-cache \
  --result /srv/wan/worker-state/result.json
```

HTTPS is required and redirects are refused. For local TCP tests only, `--allow-local-http` permits an HTTP origin whose hostname is exactly `127.0.0.1` or `localhost`. The controller issues short-lived, owner/project/batch/worker-scoped credentials through a trusted Python API; there is no public credential-issuance route. Errors redact response bodies and credentials.

Keep the worker state directory private and persistent across process retries. `worker-claim.json` saves the frozen claim and a SHA-256 origin/credential binding, never the bearer token. A process lock prevents concurrent claims in this directory. Once upload is confirmed, `completion.json` durably records its receipt before completion. An ambiguous upload replays identical bytes; an ambiguous completion reuses the saved receipt and output without rendering or uploading again. A successful result is persisted before removing the claim journal. A lost claim response is reconciled by the controller for the same assigned worker on the next explicit invocation.

Recovery requires the same still-valid credential. A rotated credential fails the local binding check; expired or fenced attempts require trusted controller reconciliation rather than deleting journals and blindly retrying. Retain both journals and output for that reconciliation. Remote transport is implemented, but hosted TLS, production secret delivery, object-store integration and real GPU inference remain unverified.

## Exact B06 benchmark invocation

First build and record the image digest, provision durable mounts, stage pinned weights, and admit the frozen benchmark shot below through B02. B06 requires the approved project dollar ceiling and maximum runtime. The backend supplies an attempt-scoped credential, deadline, budget approval and worker assignment.

```sh
# Explicit preparation on the chosen storage host, before GPU launch.
docker run --rm --entrypoint python \
  --mount type=bind,src=/srv/wan/models,dst=/models \
  wan-worker:b01 -m workers.gpu.weights download /models

# Use the recorded sha256 image ID from the build evidence.
# Supply these environment variables from service secret configuration.
docker run --rm --gpus device=0 \
  -e WAN_WORKER_API_URL -e WAN_WORKER_TOKEN \
  --mount type=bind,src=/srv/wan/models,dst=/models,readonly \
  --mount type=bind,src=/srv/wan/inputs,dst=/inputs \
  --mount type=bind,src=/srv/wan/outputs,dst=/outputs \
  "$WAN_WORKER_IMAGE_DIGEST" worker \
  --weights /models --input-root /inputs --output-root /outputs \
  --result /outputs/benchmark-result.json
```

The fictional benchmark prompt is `A small blue sailboat moves slowly across a calm lake at sunrise, steady wide camera, no text.` Set seed 42, 50 steps, 1280×704, 24/1 fps and target duration 5,000 ms with no reference image. Copy the exact model profile from `model.lock.json`. Use a fresh attempt for each measured sample. Record provider GPU, driver, image digest, checkpoint verification time, provisioning/download time, wall time, model-load time, generation time, PyTorch peak allocated/reserved VRAM, upload/commit time, billed cost and cleanup confirmation.

Each attempt currently starts a fresh model process. Repeated runs measure a warm filesystem cache with a cold model process. Resident-model warm inference, sustained throughput, creative quality and cost per accepted second remain B06 measurements. `cost_cents` is null for real inference until provider billing is reconciled. The worker performs no provisioning or billing operations.

## Next recipients

B02 receives the client, transport envelope and durable filesystem requirements. QA/B05 receives the fictional smoke result and regression suite. The Command Center must retain B01 as open until a Docker-capable host builds the container and records its digest. B06 then needs integrated lifecycle verification and John's GPU budget/runtime envelope.

