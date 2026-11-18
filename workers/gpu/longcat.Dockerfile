FROM --platform=linux/amd64 ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:a0f9dbfa1f49d21e6bb2cc30fc8411f4278bfdb9133cff76dea6615a6f43f46a
USER root
WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4
COPY contracts /app/contracts
COPY workers/gpu /app/workers/gpu
COPY benchmarks/longcat/model_manifest.json /app/benchmarks/longcat/model_manifest.json
RUN python - <<'PY'
import pathlib,sys
from workers.gpu.longcat_resident import resident_source
from workers.gpu.longcat_bootstrap import bounded_process
from workers.gpu.longcat_client import LongCatClient
resident_source(pathlib.Path('/opt/longcat/run_demo_avatar_single_audio_to_video.py').read_text())
sys.path.insert(0,'/opt/longcat')
import run_demo_avatar_single_audio_to_video
print('LONGCAT_PRODUCTION_CPU_IMPORT_PASS')
PY
ENTRYPOINT ["python", "-m", "workers.gpu.longcat_bootstrap"]
