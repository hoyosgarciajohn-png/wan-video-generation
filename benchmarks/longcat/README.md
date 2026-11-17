# Approved LongCat benchmark

Issue #8. Isolated from the production application's consumed Wan grants.
John approved two H100 SXMs, $8.78/hour aggregate, at most 900 seconds including
startup, approximately $2.20 compute plus temporary storage. This does not
authorize another rental, a larger fleet, or a reset of cumulative accounting.

Run the manual `prepare` workflow first. It builds and imports the pinned model
code without GPUs and retrieves private, checksum-verified existing image/audio
inputs. No personal media or model weights go into Git or the container image.
The model manifest excludes duplicate formats and pins 47.34 GB of selected
weights. PyTorch/FlashAttention come from the already pinned Wan runtime; the
baseline uses INT8, eight steps, FA2 and no compilation. FA3/compiled throughput
has not been measured and must not be inferred from this baseline.

The probe transforms one exact SHA-256-checked upstream function to reuse its
model initialization for three independent 93-frame / 25fps shots (3.72s each).
It resets image, audio, prompt, seed and output directory between cases. It does
not use continuation frames to inflate independent-shot throughput. Per-rank
time/memory records include audio preparation, inference and encoding within
each case; startup/download/model loading are separate. Review actual output
dimensions and Spanish singing quality before extrapolating a full-song result.

Before a single connected Runpod create, start the `guard` workflow with a fresh
exact name `wan-longcat-20261117-<12 lowercase hex digits>` and a fixed deadline
no more than 900s ahead. Verify its READY log and running state. The guard has
read/delete access only and begins teardown 30s before the ceiling. Use a
digest-pinned built image, two H100s, Secure Cloud, the existing private registry
credential and 150 GB temporary container disk; no exposed ports or volumes.
Pass `BENCHMARK_DEADLINE` into the Pod. Do not put Runpod/API credentials there.

The image starts pinned weight download immediately. Transfer the input files
through the authenticated Runpod exec API, verify every hash, and write READY
last. Retrieve output bytes and logs to durable storage before deleting the
Pod. Stop early if finished or failed. Verify provider absence and reconcile
posted billing. Never retry an uncertain create. A Python exit is not teardown.

Free preparation, model import and fictional tests are distinct from actual
GPU evidence. No GPU success or creative acceptance is asserted by this source.
