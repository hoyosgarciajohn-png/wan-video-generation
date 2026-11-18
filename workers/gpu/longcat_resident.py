"""Pinned two-rank LongCat adapter. No Pod allocation or automatic retry.

The controller prepares validated per-shot files and external recovery receipts.
This entry point deliberately refuses to proceed without those receipts.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from workers.gpu.longcat_batch import BatchJournal, fingerprint, validate_manifest, verify_output

SOURCE_SHA256 = '4a8abbf73385af5369399b18046325b8d322ba8a7998df34e92095d2dad21fa8'


def resident_source(source):
    if hashlib.sha256(source.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unreviewed LongCat source')
    tree = ast.parse(source)
    generate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'generate')
    matches = [i for i, n in enumerate(generate.body)
               if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
               and ast.unparse(n.value.func) == 'os.makedirs' and n.value.args
               and ast.unparse(n.value.args[0]) == 'output_dir']
    if len(matches) != 1:
        raise ValueError('Upstream model initialization boundary changed')
    split = matches[0]
    body = generate.body[split:]
    replaced = 0
    for i, node in enumerate(body):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'global_seed' for t in node.targets):
            body[i] = ast.parse("global_seed = case['seed']").body[0]
            replaced += 1
    if replaced != 1:
        raise ValueError('Upstream seed boundary changed')
    loop = ast.parse('''
for case in LONGCAT_MANIFEST['shots']:
    decision = longcat_decision(case)
    if decision == 'stop':
        break
    if decision == 'skip':
        continue
    if decision == 'render':
        input_data = {'prompt': case['prompt'],
            'cond_image': str(LONGCAT_INPUT_ROOT / case['image']['path']),
            'cond_audio': {'person1': str(LONGCAT_INPUT_ROOT / case['audio']['path'])}}
        prompt = input_data['prompt']
        negative_prompt = case.get('negative_prompt',
            'subtitles, watermark, text overlay, distorted face, extra fingers, malformed hands, fused limbs, flickering, blurred face')
        raw_speech_path = input_data['cond_audio']['person1']
        output_dir = str(LONGCAT_OUTPUT_ROOT / case['id'])
        height, width = 480, 832
        dist.barrier()
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        shot_started = time.monotonic()
''').body[0]
    render = loop.body[-1]
    render.body.extend(body)
    render.body.extend(ast.parse('''
torch.cuda.synchronize()
dist.barrier()
longcat_rendered(case, time.monotonic() - shot_started)
''').body)
    loop.body.extend(ast.parse('longcat_publish(case)').body)
    generate.body = generate.body[:split] + [loop]
    ast.fix_missing_locations(tree)
    return compile(tree, 'pinned_longcat_full_queue.py', 'exec')


def main():
    import torch.distributed as dist
    root = Path('/work/inputs')
    output = Path('/work/output')
    manifest = validate_manifest(json.loads((root / 'manifest.json').read_text()), root)
    execution = json.loads((root / 'execution.json').read_text())
    rank = int(os.environ['RANK'])
    # Every rank validates the immutable execution before any model initialization.
    from workers.gpu.longcat_batch import validate_execution
    validate_execution(execution, time.time())
    if execution['manifest_sha256'] != fingerprint(manifest):
        raise ValueError('Execution manifest mismatch')
    journal = BatchJournal(output, manifest, execution) if rank == 0 else None
    from workers.gpu.longcat_client import LongCatClient
    client = LongCatClient(os.environ['LONGCAT_ORIGIN'], os.environ['LONGCAT_TOKEN'], timeout=25) if rank == 0 else None

    def collective(call):
        box = [None]
        if rank == 0:
            try:
                box[0] = {'ok': True, 'value': call()}
            except Exception as error:
                box[0] = {'ok': False, 'error': type(error).__name__ + ': ' + str(error)}
        dist.broadcast_object_list(box, src=0)
        if not box[0]['ok']:
            raise RuntimeError(box[0]['error'])
        return box[0]['value']

    def rendered(case, elapsed):
        def commit():
            metadata = verify_output(journal.output_path(case))
            metadata['elapsed_seconds'] = elapsed
            journal.rendered(case, metadata)
        collective(commit)

    def decision(case):
        receipt = client.receipt(case['id'])
        if receipt is not None:
            journal.restore_published(case, receipt)
            return 'skip'
        action = journal.decision(case)
        if action == 'render':
            # Persist the inference start outside the GPU before generating it.
            # An interrupted start cannot be replayed with a fresh local journal.
            client.start(case['id'])
        return action

    first = manifest['shots'][0]
    first_input = root / 'first-input.json'
    if rank == 0:
        from workers.gpu.common import atomic_json
        atomic_json(first_input, {'prompt': first['prompt'],
            'cond_image': str(root / first['image']['path']),
            'cond_audio': {'person1': str(root / first['audio']['path'])}})
    # Init process_group occurs upstream; use the fixed private file as initial
    # config. Nonzero ranks wait boundedly for the atomic write before loading.
    until = min(time.time() + 10, execution['deadline'] - 150)
    while not first_input.exists() and time.time() < until:
        time.sleep(.1)
    if not first_input.exists():
        raise TimeoutError('Initial input not ready')
    upstream = Path('/opt/longcat/run_demo_avatar_single_audio_to_video.py')
    os.chdir(upstream.parent)
    sys.path.insert(0, str(upstream.parent))
    sys.argv = [str(upstream), '--input_json', str(first_input), '--output_dir', str(output),
        '--checkpoint_dir', '/work/weights/LongCat-Video-Avatar-1.6', '--stage_1', 'ai2v',
        '--model_type', 'avatar-v1.6', '--resolution', '480p', '--context_parallel_size', '2',
        '--num_segments', '1', '--use_distill', '--use_int8', '--mix_steps', '4',
        '--mix_alpha', '1.0', '--lora_path', 'loraB/lora.safetensors']
    namespace = dict(__name__='__main__', __file__=str(upstream), time=time,
        LONGCAT_MANIFEST=manifest, LONGCAT_INPUT_ROOT=root, LONGCAT_OUTPUT_ROOT=output,
        longcat_decision=lambda case: collective(lambda: decision(case)),
        longcat_rendered=rendered,
        longcat_publish=lambda case: collective(lambda: journal.publish(case, client.publish)))
    exec(resident_source(upstream.read_text()), namespace)


if __name__ == '__main__':
    main()
