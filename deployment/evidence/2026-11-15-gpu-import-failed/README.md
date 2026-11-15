# GPU image build stopped at eager CUDA import

Run: https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43773064856
Artifact 14184553538, ZIP SHA-256 `201b941857fbf4a3383b7f471f90d4a433b75268539a0fa5bd5db2164e88df82`.
Original downloaded evidence; no completed image or CUDA result.
The runner passed the 40 GiB disk check. Dependency/source checksum checks and
FlashAttention import passed during build. Wan's T5 class default invoked
`torch.cuda.current_device()` at import time and failed on the CPU builder.
The correction separates actual library imports/source syntax from GPU-only
Wan import. It does not monkeypatch CUDA or modify the locked upstream source.
