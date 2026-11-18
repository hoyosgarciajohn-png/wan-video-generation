"""Bounded production bootstrap; authenticated input fetch, pinned weights, one torchrun.

The process-group deadline supplements the separately verified provider guard.
Exiting this process is not evidence of provider teardown.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from .common import atomic_json, digest, require
from .longcat_batch import fingerprint, validate_execution, validate_manifest
from .longcat_client import LongCatClient


def bounded_process(command, deadline, *, log):
    remaining = deadline - time.time() - 35
    require(remaining > 90, 'Insufficient time for model work and recovery')
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        return process.wait(timeout=remaining)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        except ProcessLookupError:
            pass
        raise


def child():
    root = Path('/work'); inputs = root/'inputs'
    manifest = json.loads((inputs/'manifest.json').read_text())
    execution = validate_execution(json.loads((inputs/'execution.json').read_text()), time.time())
    require(execution['manifest_sha256'] == fingerprint(manifest), 'Execution manifest changed')
    client = LongCatClient(os.environ['LONGCAT_ORIGIN'], os.environ['LONGCAT_TOKEN'], timeout=25)
    client.download(manifest, inputs)
    validate_manifest(manifest, inputs)
    # If every take is already durable, avoid downloading/loading the model.
    if all(client.receipt(s['id']) is not None for s in manifest['shots']): return 0
    from huggingface_hub import hf_hub_download
    weights = json.loads(Path('/app/benchmarks/longcat/model_manifest.json').read_text())

    def download(model, asset):
        require(time.time() < execution['deadline']-150, 'Weight preparation deadline reached')
        path = Path(hf_hub_download(repo_id=model['repository'], revision=model['revision'],
            filename=asset['path'], local_dir=root/'weights'/model['repository'].split('/')[-1]))
        require(path.stat().st_size == asset['bytes'] and
                (not asset['sha256'] or digest(path) == asset['sha256']), 'Weight integrity failed')
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(download,m,a) for m in weights['models'] for a in m['files']]
        for future in concurrent.futures.as_completed(futures): future.result()
    config = root/'weights/LongCat-Video-Avatar-1.6/base_model_int8/config.json'
    value = json.loads(config.read_text()); value.update(enable_flashattn2=True, enable_flashattn3=False)
    atomic_json(config, value)
    require(time.time() + 150 < execution['deadline'], 'No time for inference and recovery')
    # Inherit this child's supervised process group, including both GPU ranks.
    return subprocess.run(['torchrun', '--nproc_per_node=2', '-m', 'workers.gpu.longcat_resident']).returncode


def main():
    if sys.argv[1:] == ['--child']: raise SystemExit(child())
    require(not sys.argv[1:], 'Unsupported bootstrap arguments')
    root = Path('/work'); inputs=root/'inputs'; output=root/'output'
    inputs.mkdir(parents=True, exist_ok=True); output.mkdir(exist_ok=True)
    client = LongCatClient(os.environ['LONGCAT_ORIGIN'], os.environ['LONGCAT_TOKEN'], timeout=25)
    configuration = client.configuration()
    execution = validate_execution(configuration['execution'], time.time())
    require(fingerprint(configuration['manifest']) == execution['manifest_sha256'], 'Manifest grant mismatch')
    # Never overwrite a previous run with another scope, manifest or deadline.
    for name,key in [('manifest.json','manifest'),('execution.json','execution')]:
        path=inputs/name
        if path.exists(): require(json.loads(path.read_text()) == configuration[key], 'Mounted scope changed')
        else: atomic_json(path, configuration[key])
    started=time.time()
    try:
        with (output/'inference.log').open('a') as log:
            code=bounded_process([sys.executable,'-m','workers.gpu.longcat_bootstrap','--child'],
                                 execution['deadline'],log=log)
        atomic_json(output/'result.json',dict(exit_code=code,elapsed_seconds=time.time()-started,
                    scope_id=execution['scope_id'],provider_cleanup='independent guard required'))
        raise SystemExit(code)
    except Exception as error:
        atomic_json(output/'failure.json',dict(type=type(error).__name__,scope_id=execution['scope_id']))
        raise SystemExit(1) from None


if __name__ == '__main__': main()
