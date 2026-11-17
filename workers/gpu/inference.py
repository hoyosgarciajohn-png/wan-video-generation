"""Isolated official WanTI2V call, allowing the parent to terminate lost leases."""
import json
import os
from pathlib import Path
import sys
import subprocess
import time

from .common import LOCK, atomic_json, require
from .weights import verify


def stage(name):
    # Fixed labels only: never expose prompts, paths or raw exception messages.
    print('WAN_STAGE:' + name, flush=True)


class ObservedTextEncoder:
    def __init__(self, encoder):
        self.encoder = encoder

    def __getattr__(self, name):
        return getattr(self.encoder, name)

    def __call__(self, *args, **kwargs):
        stage('text_encode')
        result = self.encoder(*args, **kwargs)
        stage('generation')
        return result


def configure_memory(model, torch, timings=None):
    # The pinned upstream VAE defaults to float32. Use BF16 parameters and its
    # own BF16 autocast context, rather than keeping FP32 decode activations.
    # This candidate requires a new GPU validation; CPU mocks cannot prove fit.
    model.vae.model.to(dtype=torch.bfloat16)
    model.vae.dtype = torch.bfloat16
    model.text_encoder = ObservedTextEncoder(model.text_encoder)
    decode = model.vae.decode

    def observed_decode(*args, **kwargs):
        stage('video_decode')
        if timings is None:return decode(*args, **kwargs)
        torch.cuda.synchronize()
        started=time.monotonic()
        value=decode(*args, **kwargs)
        torch.cuda.synchronize()
        timings['decode_seconds']=timings.get('decode_seconds',0)+(time.monotonic()-started)
        return value

    model.vae.decode = observed_decode


def reference_image(path, size):
    if not path:
        return None
    from PIL import Image
    # Decode before loading weights or allocating GPU model memory. Only a single
    # raster frame is part of the frozen conditioning contract.
    with Image.open(path, formats=('PNG', 'JPEG', 'WEBP')) as opened:
        require(opened.size == size, 'Reference must match frozen dimensions')
        require(getattr(opened, 'n_frames', 1) == 1, 'Animated references unsupported')
        return opened.convert('RGB')


def main(spec_path):
    spec = json.loads(Path(spec_path).read_text())
    s = spec['snapshot']
    size = (s['settings']['width'], s['settings']['height'])
    image = reference_image(spec['image'], size)
    verify(spec['weights'])
    source = Path(os.environ.get('WAN_SOURCE', '/opt/wan'))
    require(source.joinpath('REVISION').read_text().strip() == LOCK['profile']['code_revision'],
            'Upstream revision mismatch')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    sys.path.insert(0, str(source))
    import torch
    import wan
    from wan.configs import WAN_CONFIGS
    from wan.utils.utils import save_video
    require(torch.cuda.is_available(), 'CUDA GPU required')
    require(torch.cuda.is_bf16_supported(), 'BF16 CUDA GPU required')
    require(torch.__version__.split('+')[0] == '2.8.0', 'Unexpected torch version')
    torch.cuda.reset_peak_memory_stats()
    start = time.monotonic()
    stage('model_load')
    model = wan.WanTI2V(config=WAN_CONFIGS['ti2v-5B'], checkpoint_dir=spec['weights'],
                       device_id=0, rank=0, t5_cpu=False, init_on_cpu=True,
                       convert_model_dtype=True)
    # Keep DiT on CPU until upstream generate() has encoded text on GPU and
    # moved T5 back to CPU. Upstream offload_model=True implements that order.
    timings={}
    configure_memory(model, torch, timings)
    torch.cuda.synchronize()
    loaded = time.monotonic()
    baseline_reserved=torch.cuda.memory_reserved()
    stage('generation')
    video = model.generate(s['prompt'], img=image, size=size, max_area=size[0]*size[1],
                           frame_num=spec['frames'], shift=5.0, sample_solver='unipc',
                           sampling_steps=50, guide_scale=5.0, seed=s['settings']['seed'],
                           offload_model=True)
    torch.cuda.synchronize()
    generated = time.monotonic()
    stage('video_encode')
    save_video(tensor=video[None], save_file=spec['output'], fps=24, nrow=1,
               normalize=True, value_range=(-1, 1))
    atomic_json(Path(spec['output']).with_suffix('.metrics.json'), {
        'mode': 'wan', 'model_load_seconds': loaded-start,
        'generation_seconds': generated-loaded-timings.get('decode_seconds',0),
        'decode_encode_seconds':timings.get('decode_seconds',0)+time.monotonic()-generated,
        'gpu_model_loaded_reserved_bytes':baseline_reserved,
        'gpu_total_bytes':torch.cuda.get_device_properties(0).total_memory,
        'driver_version':subprocess.check_output(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],text=True,timeout=10).strip(), 'gpu_name': torch.cuda.get_device_name(0),
        'gpu_peak_allocated_bytes': torch.cuda.max_memory_allocated(),
        'gpu_peak_reserved_bytes': torch.cuda.max_memory_reserved(),
        'torch_version': torch.__version__, 'cuda_version': torch.version.cuda,
        'model_profile': LOCK['profile'], 'cost_cents': None,
        'process_start': 'cold', 'attention_backend': 'flash-attention-2.8.3',
        'memory_policy': 'sequential-gpu-text-bf16-vae-v1',
    })


if __name__ == '__main__':
    main(sys.argv[1])

