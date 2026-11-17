"""Fetch only pinned weights, verify them, then run the resident probe."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    root = Path('/work')
    root.mkdir(exist_ok=True)
    out = root / 'output'
    out.mkdir(exist_ok=True)
    deadline = int(os.environ['BENCHMARK_DEADLINE'])
    if not time.time() < deadline <= time.time() + 900:
        raise ValueError('Fixed deadline missing or expired')
    started = time.time()
    def event(kind, **data):
        row = dict(event=kind, at=time.time(), **data)
        with (out / 'bootstrap.jsonl').open('a') as f:
            f.write(json.dumps(row)+'\n'); f.flush(); os.fsync(f.fileno())
        print(json.dumps(row), flush=True)
    event('container_ready')
    from huggingface_hub import hf_hub_download
    manifest = json.loads(Path('/benchmark/model_manifest.json').read_text())
    def download(model, item):
        if time.time() >= deadline - 150:
            raise TimeoutError('Insufficient rental time remains')
        path = Path(hf_hub_download(repo_id=model['repository'], revision=model['revision'],
            filename=item['path'], local_dir=root/'weights'/model['repository'].split('/')[-1]))
        if path.stat().st_size != item['bytes'] or (item['sha256'] and digest(path) != item['sha256']):
            raise ValueError('Weight integrity failed: '+item['path'])
        event('weight_verified', file=item['path'], bytes=item['bytes'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(download, m, f) for m in manifest['models'] for f in m['files']]
        for future in concurrent.futures.as_completed(futures):
            future.result()
    event('weights_ready', elapsed_seconds=time.time()-started)
    while not (root/'inputs/READY').exists():
        if time.time() >= deadline - 120:
            raise TimeoutError('Inputs not ready within rental allowance')
        time.sleep(1)
    # Explicit FA2 baseline. Compilation and FA3 have not been measured here.
    config = root/'weights/LongCat-Video-Avatar-1.6/base_model_int8/config.json'
    value = json.loads(config.read_text())
    value.update(enable_flashattn2=True, enable_flashattn3=False)
    config.write_text(json.dumps(value))
    remaining = int(deadline-time.time()-35)
    if remaining < 90:
        raise TimeoutError('Insufficient time for first measured shot')
    event('probe_started', remaining_seconds=remaining, preset='INT8-eight-step-FA2-no-compile')
    with (out/'inference.log').open('w') as log:
        result = subprocess.run(['timeout','--signal=TERM','--kill-after=10s',str(remaining),
            'torchrun','--nproc_per_node=2','/benchmark/probe.py'], stdout=log, stderr=subprocess.STDOUT)
    event('probe_finished', exit_code=result.returncode, elapsed_seconds=time.time()-started)
    # Keep the container available briefly for evidence retrieval; the external
    # guard terminates the actual Pod. Exiting Python is not provider teardown.
    (out/'DONE').write_text(str(result.returncode))
    while time.time() < deadline:
        time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        out=Path('/work/output');out.mkdir(parents=True,exist_ok=True)
        (out/'failure.json').write_text(json.dumps({'type':type(error).__name__,'message':str(error)}))
        print('LONGCAT_BOOTSTRAP_FAILED '+type(error).__name__,flush=True)
        while time.time() < int(os.environ.get('BENCHMARK_DEADLINE','0')):
            time.sleep(1)
