# Actual private worker publication

Run: https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43777990153
Source: `e9f37eddf3297695af7f4f2ed5544c17f0885039` (PR #42).
Artifact 14187433438; original ZIP SHA-256:
`e5f2bf648e324dc384521b51f9514f168afe81db91515a70bb72b0d3993a1bb3`.

Published private image:
`ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:c1b181cf4fb83f6451c721dc1035d55966a3757bf6567636bcbeff77f740fbe2`

Build, image identity, native Torch/FlashAttention loading, Wan source syntax and
synthetic fixture passed. Publication verified private visibility, denied
anonymous access, and authenticated registry manifest access. The registry config
digest equals the tested Docker image ID. Compressed layers total 5,220,107,260
bytes. No weights are embedded. Actual Runpod layer download is **UNVERIFIED**.

Original build logs and manifest remain unchanged, including the pre-publication
empty `RepoDigests`. Separate `publication.json` and `registry-manifest.json` bind
the published digest to the tested image without inventing an earlier inspection.
All 32 source hashes, four log hashes, helper hashes and fixture checksum matched;
the downloaded H.264 synthetic MP4 fully decoded. The offline build verifier now
accepts relocated evidence while validating original argv path relationships and
the separate publication binding. It does not execute recorded commands.

To reconstruct the original small context: copy the manifest-listed files from
the source commit to `context/`, copy its `deployment/container_smoke.py` to
`container_smoke.py`, restore `fixture-result.json` as `fixture/result.json`, and
decode `fixture.mp4.base64` to its recorded asset object key. Verify all hashes.
Do not rewrite original logs or argv paths. The entire downloaded artifact is
available from the linked run until its one-day retention expires; these retained
records and the reviewed source commit preserve reconstruction afterward.

Wan CUDA import, model checksums on a real volume, inference, benchmark, Runpod
download, production HTTPS/storage and installed cleanup remain unverified.
No Runpod resources were created; the approved $5 / 30-minute trial is unused.
