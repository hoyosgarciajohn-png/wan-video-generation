# Third-party source and artifacts

The worker imports official Wan2.2 inference source. Copyright 2024–2025 The Alibaba Wan Team Authors. The source archive retains its copyright notices and `LICENSE.txt`. A copy is included in `licenses/Wan-Apache-2.0.txt`.

- Wan source pin and model revision are recorded in `model.lock.json`. [Official Wan source](https://github.com/Wan-Video/Wan2.2/tree/e5058c08fada388b04bb3d1a4734bddbd2fdeac5)
- The pinned model card is included in checkpoint verification and remains with the weights. [Pinned model card](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B/blob/921dbaf3f1674a56f47e83fb80a34bac8a8f203e/README.md)
- The official FlashAttention binary and its checksum are specified in `flash-attention.lock`. Its package retains upstream license metadata. [FlashAttention release](https://github.com/Dao-AILab/flash-attention/releases/tag/v2.8.3)
- The FFmpeg/ffprobe binary source image is pinned in `model.lock.json`. Preserve applicable license and corresponding-source obligations when distributing a built image. [Static FFmpeg build source](https://github.com/wader/static-ffmpeg/tree/7.1)
- Runtime and dependency package notices remain in the base image and installed distributions. [PyTorch source](https://github.com/pytorch/pytorch/tree/v2.8.0)

Application ownership and checkpoint provenance are recorded independently. Model weights and user media remain outside this repository.

