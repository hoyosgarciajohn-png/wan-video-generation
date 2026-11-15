# CPU timeline export

Use `export_bundle(bundle, export_id, project_id, media_root, job_root, progress)` from
`workers.media.export` on a Linux CPU worker with Python 3.11+ and FFmpeg with
libx264 and AAC. Pass a persisted, schema-validated contract 0.1.0 bundle,
an authenticated project ID resolved by the backend, and staged immutable local
assets. Run FFmpeg in the worker's isolated filesystem and network environment.
The backend owns job admission, durable queue state, cancellation and result publication.

The worker selects the exact timeline revision and verifies approval at the
revision timestamp. Ordered video trims are converted to the output frame rate
using cumulative frame boundaries. Audio is trimmed and placed in milliseconds.
The original audio file is read-only and the MP4 soundtrack is encoded as AAC.
The worker rejects trims that collapse to zero output frames and requires even
output dimensions for the 4:2:0 export profile.

Use a private persistent job directory. Reinvoke with the same immutable input
after a failed or interrupted attempt. A per-job file lock serializes local
attempts. Validated completed shot files persist across attempts. Checksum records
are written atomically after verification; retries rebuild missing, damaged or
legacy cache files without a checksum, including the final output. The MP4
becomes visible at its final path after output verification. The caller should
publish the final file under the job's project, assign its output asset ID and
release scratch files after durable publication. Progress reports the local
render state and the number of prepared shots.

Run the fictional acceptance checks from the repository root:

```sh
python scripts/validate_contract.py --media-root fixtures
python -m unittest discover -s tests -v
python -m unittest workers.media.test_export -v
```

The long-duration fixtures use low-resolution, low-frame-rate footage for
repeatability. B05 wires the worker to the backend and Studio. Hosted
performance and creative acceptance are later pilot checks.

