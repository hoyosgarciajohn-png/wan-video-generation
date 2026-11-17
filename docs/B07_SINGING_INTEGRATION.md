# Singing model and resident production queue

Prepared November 17, 2026 for issue #8. Native generation is 832x448 at 16 fps,
40 UniPC steps, using pinned official Wan2.2-S2V-14B source/checkpoints. Final HD
exports are upscaled, not native HD. Actual GPU speed, singing synchronization,
identity, choreography and visual quality remain unverified until the live run.

The signed full-song scope freezes ordered shot snapshots, image/audio hashes,
model, container, one H100 at <=$4.50/hour, $18 GPU plus $2 storage reserve, and a
fixed four-hour admission deadline. At most two attempts per shot are permitted.
A new grant cannot reset the project envelope. Historical grants stay consumed.

One subprocess loads/verifies the model once and renders serially. Audio is exact
mono 16kHz PCM16 at the model's frame-aligned duration. The first frame is retained
so upstream frame trimming cannot introduce a 187.5ms synchronization offset.
Every accepted file and its timing/VRAM telemetry are durable outside the Pod
before claiming another shot. Ambiguous completion replays the same output.
Lease expiry kills the inference process. OOM/model-load failures stop the batch
for cleanup and diagnosis, preserving completed takes. Remaining-time checks
close the queue before another shot cannot safely fit.

CPU verification: 207 controller/integration checks and 46 worker checks passed.
These use fictional media, including real FFmpeg encoding/probing, and establish
protocol/recovery behavior only. Live owner creative acceptance remains pending.

The operational song asset import, four-hour independent guard, image publication,
controller deployment and paid execution are subsequent preparation steps. No new
Pod was created by this implementation checkpoint.
