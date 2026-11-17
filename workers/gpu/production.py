"""Versioned full-song capability, supplied only through authenticated claims."""
import hashlib
import json
import re

from .common import require

PROTOCOL = 'wan-song-queue-v1'
GPU = 'NVIDIA H100 80GB HBM3'


def snapshot_hash(snapshots):
    return hashlib.sha256(json.dumps(snapshots, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_policy(value):
    require(isinstance(value, dict) and set(value) == {'protocol','shot_ids','snapshots_sha256',
        'max_attempts_per_shot','max_runtime_seconds','gpu_cap_cents','total_cap_cents',
        'storage_reserve_cents','max_hourly_cents','image_ref'}, 'Exact production policy required')
    require(value['protocol'] == PROTOCOL, 'Unknown production protocol')
    ids = value['shot_ids']
    require(isinstance(ids, list) and 1 <= len(ids) <= 100 and
        all(isinstance(x, str) and x for x in ids) and len(ids) == len(set(ids)), 'Invalid production shots')
    require(re.fullmatch('[a-f0-9]{64}', value['snapshots_sha256']) is not None, 'Snapshot digest required')
    require(all(type(value[k]) is int for k in ('max_attempts_per_shot','max_runtime_seconds',
        'gpu_cap_cents','total_cap_cents','storage_reserve_cents','max_hourly_cents')), 'Integer production limits required')
    require((value['max_attempts_per_shot'], value['max_runtime_seconds'], value['gpu_cap_cents'],
        value['total_cap_cents'], value['storage_reserve_cents'], value['max_hourly_cents']) ==
        (2,14400,1800,2000,200,450), 'Production spending or runtime limits changed')
    require(isinstance(value['image_ref'], str) and re.fullmatch(
        r'[A-Za-z0-9][A-Za-z0-9._/:-]*@sha256:[a-f0-9]{64}', value['image_ref']), 'Immutable production image required')
    return value


def validate_snapshots(policy, snapshots):
    validate_policy(policy)
    require([s['shot_id'] for s in snapshots] == policy['shot_ids'] and
        snapshot_hash(snapshots) == policy['snapshots_sha256'], 'Production snapshots changed')
    require(sum(s['target_duration_ms'] for s in snapshots) <= 360000, 'Production exceeds music runtime')
