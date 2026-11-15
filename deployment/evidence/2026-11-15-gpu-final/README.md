# Actual Wan worker image build evidence

Run: https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43774509988
Source checkout: `423d1fdcab7dedc442714079b5a591bbf78095ec`, the synthetic merge
ref of validation PR #40. The allowlisted source and verifier/helper match main
`f6c8ab126b9c0311f8c4c6a7c3aee53f289af45c`. The temporary workflow is excluded
from the image context and was closed without merging after the successful run.

Original downloaded evidence and fixture bytes are preserved. See review.json
for checked artifact digest, source/log/output checks and full H.264 decode.
Image build/identity, Torch/FlashAttention loading, 28 Wan Python files compiled
without execution, and synthetic worker fixture passed. Wan CUDA import, model
weights and GPU inference were not performed. No CUDA device was mocked.

Reconstruction follows ../2026-11-15-cpu/README.md using this source and manifest.
The actual source archive SHA is checked by install_source.py during build.
Original paths remain in command logs; this is historical evidence, not installed
launch authority. The image was transient and was not published to a registry.

Runner cleanup reached 40.68 GiB free before the Haskell fallback was needed.
That fallback is configured for smaller runners but was not exercised in this
successful run. Future runners must still pass the free-space guard.
