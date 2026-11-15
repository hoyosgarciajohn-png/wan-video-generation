# Build from the repository root. Both runtime stages are immutable image digests.
FROM --platform=linux/amd64 mwader/static-ffmpeg:7.1@sha256:a8090df5f5608daef387e1b2e93b98aaacb4d92153ad904e7d715c725724fca4 AS ffmpeg
FROM --platform=linux/amd64 pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385
WORKDIR /app
COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /ffprobe /usr/local/bin/ffprobe
COPY workers/gpu/requirements.lock /app/workers/gpu/requirements.lock
RUN python -m pip install --require-hashes --only-binary=:all: -r workers/gpu/requirements.lock
COPY workers/gpu/flash-attention.lock /app/workers/gpu/flash-attention.lock
RUN python -m pip install --no-deps --require-hashes -r workers/gpu/flash-attention.lock
COPY contracts /app/contracts
COPY fixtures /app/fixtures
COPY workers/gpu /app/workers/gpu
RUN python /app/workers/gpu/install_source.py
RUN python -c "import sys, torch; assert sys.version_info[:2] == (3, 11); assert torch.__version__.split('+')[0] == '2.8.0'; assert torch._C._GLIBCXX_USE_CXX11_ABI"
# Wan's T5 class default initializes CUDA during import. A CPU builder must not
# import Wan or pretend a CUDA device exists. Check native library linking and
# source syntax here; actual Wan/CUDA import belongs to the real GPU trial.
RUN python -c "import flash_attn, compileall; assert compileall.compile_dir('/opt/wan/wan', quiet=1)"
ENV WAN_SOURCE=/opt/wan HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 IMAGEIO_FFMPEG_EXE=/usr/local/bin/ffmpeg PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "-m", "workers.gpu.cli"]

