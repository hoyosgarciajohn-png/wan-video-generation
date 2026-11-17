FROM --platform=linux/amd64 ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:08095101e28e595be00d5244277f91d2aa60585212c0e03eae4278dd91541fb5
USER root
ENV HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4
RUN python -m pip install --no-cache-dir numpy==1.26.4 transformers==4.41.0 diffusers==0.35.1 loguru==0.7.2 einops==0.8.0 ftfy==6.2.0 psutil==6.0.0 av==12.0.0 opencv-python==4.9.0.80 imageio==2.37.0 imageio-ffmpeg==0.6.0 scikit-learn==1.6.1 scikit-image==0.25.2 scipy==1.15.3 soundfile==0.13.1 soxr==0.5.0.post1 librosa==0.11.0 audio-separator==0.30.2 pyloudnorm==0.1.1 onnx==1.18.0 onnxruntime-gpu==1.20.2 nvidia-ml-py==13.580.65
RUN python - <<'PY'
import io,tarfile,urllib.request,pathlib
url='https://github.com/meituan-longcat/LongCat-Video/archive/58eb336edc5c8c63389838727e40b8c18434e54e.tar.gz'
with urllib.request.urlopen(url) as r: data=r.read()
with tarfile.open(fileobj=io.BytesIO(data)) as t:t.extractall('/opt',filter='data')
pathlib.Path('/opt/LongCat-Video-58eb336edc5c8c63389838727e40b8c18434e54e').rename('/opt/longcat')
PY
COPY benchmarks/longcat /benchmark
WORKDIR /opt/longcat
RUN python - <<'PY'
import sys, pathlib,hashlib,torch,flash_attn
sys.path.insert(0,'/benchmark')
from probe import resident_source
source=pathlib.Path('run_demo_avatar_single_audio_to_video.py').read_text()
resident_source(source)
import run_demo_avatar_single_audio_to_video
print('LONGCAT_CPU_IMPORT_PASS',torch.__version__,flash_attn.__version__)
PY
ENTRYPOINT ["python", "/benchmark/bootstrap.py"]
