"""Isolated official WanTI2V call, allowing the parent to terminate lost leases."""
import json
import os
from pathlib import Path
import sys
import subprocess
import time
import wave

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


def reference_audio(path, frames):
    with wave.open(str(path), 'rb') as audio:
        require((audio.getnchannels(), audio.getframerate(), audio.getsampwidth(), audio.getcomptype()) ==
                (1,16000,2,'NONE'), 'Requires mono 16 kHz PCM16 audio')
        require(audio.getnframes() == frames * 1000, 'Conditioning audio duration mismatch')
        require(len(audio.readframes(audio.getnframes())) == audio.getnframes()*2, 'Truncated audio')


class ModelSession:
    """One verified checkpoint and one model instance for a serial worker session."""
    def __init__(self):
        self.model = None
        self.binding = None
        self.calls = 0

    def run(self, spec):
        from .profiles import model_lock
        lock = model_lock(spec.get('model_profile', LOCK['profile']))
        s = spec['snapshot']
        size = (s['settings']['width'], s['settings']['height'])
        image = reference_image(spec['image'], size)
        if lock['profile']['id'] == 'wan22-s2v-14b':
            require(image is not None and spec.get('audio'), 'Singing requires image and audio')
            reference_audio(spec['audio'], spec['frames'])
        binding = (str(Path(spec['weights']).resolve()), lock['profile'])
        require(self.binding is None or self.binding == binding, 'Resident model scope changed')
        started = time.monotonic()
        if self.model is None:
            verify(spec['weights'], lock=lock)
            source_name = 'WAN_SINGING_SOURCE' if lock['profile']['id'] == 'wan22-s2v-14b' else 'WAN_SOURCE'
            default = '/opt/wan-s2v' if source_name == 'WAN_SINGING_SOURCE' else '/opt/wan'
            source = Path(os.environ.get(source_name, default))
            require(source.joinpath('REVISION').read_text().strip() == lock['profile']['code_revision'],
                    'Upstream revision mismatch')
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
            sys.path.insert(0, str(source))
            import torch
            import wan
            from wan.configs import WAN_CONFIGS
            from wan.utils.utils import save_video
            require(torch.cuda.is_available() and torch.cuda.is_bf16_supported(), 'BF16 CUDA GPU required')
            require(torch.__version__.split('+')[0] == '2.8.0', 'Unexpected torch version')
            self.torch, self.save_video = torch, save_video
            stage('model_load')
            self.singing = lock['profile']['id'] == 'wan22-s2v-14b'
            constructor = wan.WanS2V if self.singing else wan.WanTI2V
            self.model = constructor(config=WAN_CONFIGS['s2v-14B' if self.singing else 'ti2v-5B'],
                checkpoint_dir=spec['weights'], device_id=0, rank=0, t5_cpu=False,
                init_on_cpu=True, convert_model_dtype=True)
            if self.singing:
                self.model.noise_model.cpu()
            self.timings = {}
            configure_memory(self.model, torch, self.timings)
            torch.cuda.synchronize()
            self.binding = binding
        loaded = time.monotonic()
        torch = self.torch
        torch.cuda.reset_peak_memory_stats()
        self.timings.clear()
        baseline_reserved = torch.cuda.memory_reserved()
        stage('generation')
        if self.singing:
            require(image is not None and spec.get('audio'), 'Singing requires image and audio')
            # init_first_frame avoids upstream dropping the first three frames;
            # that would shift every lip-synced shot by 187.5 ms at 16 fps.
            with torch.inference_mode():
                video = self.model.generate(input_prompt=s['prompt'], ref_image_path=spec['image'],
                audio_path=spec['audio'], enable_tts=False, tts_prompt_audio=None,
                tts_prompt_text=None, tts_text=None, num_repeat=1, pose_video=None,
                max_area=size[0]*size[1], infer_frames=spec['frames'], shift=3.0,
                sample_solver='unipc', sampling_steps=s['settings']['steps'], guide_scale=4.5,
                seed=s['settings']['seed'], offload_model=True, init_first_frame=True,
                n_prompt='blurred face, distorted hands, extra fingers, duplicate singer, subtitles, watermark')
            fps = 16
        else:
            video = self.model.generate(s['prompt'], img=image, size=size, max_area=size[0]*size[1],
                frame_num=spec['frames'], shift=5.0, sample_solver='unipc', sampling_steps=50,
                guide_scale=5.0, seed=s['settings']['seed'], offload_model=True)
            fps = 24
        torch.cuda.synchronize()
        generated = time.monotonic()
        stage('video_encode')
        require(tuple(video.shape) == (3, spec['frames'], size[1], size[0]), 'Generated tensor shape mismatch')
        self.save_video(tensor=video[None], save_file=spec['output'], fps=fps, nrow=1,
                        normalize=True, value_range=(-1, 1))
        del video
        metrics = {
            'mode': 'wan', 'model_load_seconds': loaded-started if self.calls == 0 else 0,
            'generation_seconds': generated-loaded-self.timings.get('decode_seconds',0),
            'decode_encode_seconds': self.timings.get('decode_seconds',0)+time.monotonic()-generated,
            'gpu_model_loaded_reserved_bytes': baseline_reserved,
            'gpu_total_bytes': torch.cuda.get_device_properties(0).total_memory,
            'driver_version': subprocess.check_output(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],text=True,timeout=10).strip(),
            'gpu_name': torch.cuda.get_device_name(0),
            'gpu_peak_allocated_bytes': torch.cuda.max_memory_allocated(),
            'gpu_peak_reserved_bytes': torch.cuda.max_memory_reserved(),
            'torch_version': torch.__version__, 'cuda_version': torch.version.cuda,
            'model_profile': lock['profile'], 'cost_cents': None,
            'process_start': 'warm' if self.calls else 'cold',
            'session_render_index': self.calls, 'attention_backend': 'flash-attention-2.8.3',
            'memory_policy': 'sequential-gpu-text-bf16-vae-v1',
        }
        self.calls += 1
        atomic_json(Path(spec['output']).with_suffix('.metrics.json'), metrics)


def serve(stream, factory=ModelSession):
    session = factory()
    for line in stream:
        path = Path(json.loads(line)['spec'])
        spec = json.loads(path.read_text())
        session.run(spec)
        atomic_json(path.with_suffix('.done.json'), {'output': spec['output']})


def main(spec_path):
    ModelSession().run(json.loads(Path(spec_path).read_text()))


if __name__ == '__main__':
    if sys.argv[1:] == ['--serve']:
        serve(sys.stdin)
    else:
        main(sys.argv[1])
