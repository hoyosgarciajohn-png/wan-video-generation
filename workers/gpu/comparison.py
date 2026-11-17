"""Private duration-comparison protocol v1; canonical bundle 0.1.0 is unchanged."""
import hashlib
import json
import math
import re

PROTOCOL = 'wan-duration-comparison-v1'
GPU = 'NVIDIA H100 80GB HBM3'
PROMPT = ('One small blue sailboat with a single white sail moves slowly from left to right across a calm lake at sunrise. '
          'A fixed wide camera keeps the entire boat visible. Keep the boat\'s shape, sail, colors, shoreline and mountains '
          'consistent. Gentle continuous ripples, natural light, one uninterrupted shot, no cuts, no text.')
SETTINGS = dict(width=1280, height=704, steps=50, seed=42, frame_rate={'numerator':24,'denominator':1})


def require(value, message):
    if not value: raise ValueError(message)


def policy(shot_ids, image_ref):
    return dict(protocol=PROTOCOL, shot_ids=list(shot_ids), durations_ms=[5000,15000], image_ref=image_ref,
                gpu_type=GPU, max_render_attempts=2, retries_per_shot=0,
                minimum_remaining_seconds=600, generation_time_multiplier=9, memory_headroom_percent=10)


def validate_policy(value):
    require(isinstance(value,dict), 'Comparison policy required')
    ids=value.get('shot_ids')
    require(isinstance(ids,list) and len(ids)==2 and len(set(ids))==2 and
            all(isinstance(x,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,199}',x) for x in ids), 'Two ordered shot IDs required')
    require(isinstance(value.get('image_ref'),str) and re.fullmatch(r'[^\s]+@sha256:[a-f0-9]{64}',value['image_ref']), 'Comparison image digest required')
    require(value==policy(ids,value['image_ref']), 'Unsupported comparison policy')
    return value


def validate_snapshots(value, snapshots):
    validate_policy(value)
    require([s['shot_id'] for s in snapshots]==value['shot_ids'], 'Comparison order differs from approval')
    for s,duration in zip(snapshots,value['durations_ms']):
        require(s['target_duration_ms']==duration and s['settings']==SETTINGS and s['prompt']==PROMPT
                and s['reference_asset_ids']==[], 'Comparison settings differ from approval')


def receipt(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate_metrics(value, experiment, attempt, snapshot):
    from .common import LOCK, frame_count
    require(isinstance(value,dict) and len(json.dumps(value,allow_nan=False))<16384, 'Invalid telemetry')
    fields={'protocol','attempt_id','batch_id','image_ref','model_profile','gpu_name','gpu_total_bytes','driver_version',
            'frames','width','height','fps','target_duration_ms','model_load_seconds','generation_seconds',
            'decode_encode_seconds','upload_seconds','render_and_verify_seconds','gpu_peak_allocated_bytes',
            'gpu_peak_reserved_bytes','gpu_model_loaded_reserved_bytes','asset_sha256','asset_bytes','torch_version',
            'cuda_version','memory_policy'}
    require(set(value)==fields, 'Exact telemetry fields required')
    require(value['protocol']==PROTOCOL and value['attempt_id']==attempt['id'] and value['batch_id']==attempt['batch_id']
            and value['image_ref']==experiment['image_ref'] and value['model_profile']==LOCK['profile'], 'Telemetry identity mismatch')
    require(value['gpu_name']==experiment['gpu_type'] and value['memory_policy']=='sequential-gpu-text-bf16-vae-v1', 'Comparison hardware or memory policy changed')
    require((value['frames'],value['width'],value['height'],value['fps'],value['target_duration_ms'])==
            (frame_count(snapshot,'runpod'),1280,704,24,snapshot['target_duration_ms']), 'Telemetry media mismatch')
    for key in ('model_load_seconds','generation_seconds','decode_encode_seconds','upload_seconds','render_and_verify_seconds'):
        require(type(value[key]) in (int,float) and math.isfinite(value[key]) and 0<=value[key]<=2700, 'Invalid telemetry timing')
    require(value['generation_seconds']>0, 'Generation timing missing')
    for key in ('gpu_total_bytes','gpu_peak_allocated_bytes','gpu_peak_reserved_bytes','gpu_model_loaded_reserved_bytes','asset_bytes'):
        require(type(value[key]) is int and value[key]>0, 'Invalid telemetry size')
    require(value['gpu_peak_allocated_bytes']<=value['gpu_peak_reserved_bytes']<=value['gpu_total_bytes']
            and value['gpu_model_loaded_reserved_bytes']<=value['gpu_peak_reserved_bytes'], 'Invalid memory telemetry')
    require(isinstance(value['asset_sha256'],str) and re.fullmatch('[a-f0-9]{64}',value['asset_sha256']), 'Invalid telemetry checksum')
    for key in ('driver_version','torch_version','cuda_version'):
        require(isinstance(value[key],str) and 0<len(value[key])<=64 and re.fullmatch(r'[A-Za-z0-9.+_-]+',value[key]), 'Invalid software identity')
    return value


def continuation_gate(metrics, remaining_seconds):
    """Conservative planning estimates, not guarantees of runtime or memory fit."""
    required=max(600,metrics['model_load_seconds'] + 9*metrics['generation_seconds']
                 + 3*metrics['decode_encode_seconds'] + metrics['upload_seconds'] + 120)
    projected=metrics['gpu_model_loaded_reserved_bytes'] + 3*(metrics['gpu_peak_reserved_bytes']-metrics['gpu_model_loaded_reserved_bytes'])
    allowed=remaining_seconds>=required and projected<=metrics['gpu_total_bytes']*.90
    return dict(allowed=allowed, remaining_seconds=remaining_seconds, required_seconds=required,
                projected_reserved_bytes=projected, memory_limit_bytes=int(metrics['gpu_total_bytes']*.90),
                reason='eligible' if allowed else 'insufficient_time_or_memory_headroom')
