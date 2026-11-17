"""Run three independent native shots with one resident LongCat initialization.

Only the pinned upstream function is transformed. No provider credentials or
resource creation. The external guard owns the paid deadline.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import time

SOURCE_SHA256 = '4a8abbf73385af5369399b18046325b8d322ba8a7998df34e92095d2dad21fa8'


def resident_source(source):
    if hashlib.sha256(source.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unreviewed LongCat entry point')
    tree = ast.parse(source)
    generate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'generate')
    indices = [i for i, n in enumerate(generate.body)
               if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
               and ast.unparse(n.value.func) == 'os.makedirs'
               and n.value.args and ast.unparse(n.value.args[0]) == 'output_dir']
    if len(indices) != 1:
        raise ValueError('Unexpected upstream initialization boundary')
    split = indices[0]
    prefix = ast.parse('''
for case_index, case in enumerate(BENCHMARK_CASES):
    if time.time() >= BENCHMARK_DEADLINE - 60:
        benchmark_event('remaining_time_gate', case_index=case_index)
        break
    with open(case['input_json'], encoding='utf-8') as handle:
        input_data = json.load(handle)
    prompt = input_data['prompt']
    raw_speech_path = input_data['cond_audio']['person1']
    output_dir = str(Path(BENCHMARK_OUTPUT) / case['id'])
    dist.barrier()
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    case_started = time.monotonic()
    benchmark_event('case_started', case_index=case_index, case_id=case['id'], resident=case_index > 0)
''').body[0]
    suffix = ast.parse('''
torch.cuda.synchronize()
dist.barrier()
benchmark_event('case_completed', case_index=case_index, case_id=case['id'],
    elapsed_seconds=time.monotonic()-case_started,
    peak_allocated_bytes=torch.cuda.max_memory_allocated(),
    peak_reserved_bytes=torch.cuda.max_memory_reserved(),
    generated_frames=93, fps=25, generated_seconds=3.72)
''').body
    prefix.body.extend(generate.body[split:])
    prefix.body.extend(suffix)
    generate.body = generate.body[:split] + [ast.parse("benchmark_event('model_ready', elapsed_seconds=time.monotonic()-BENCHMARK_STARTED)").body[0], prefix]
    ast.fix_missing_locations(tree)
    return compile(tree, 'pinned_longcat_resident.py', 'exec')


def main():
    root = Path('/opt/longcat')
    output = Path('/work/output')
    output.mkdir(parents=True, exist_ok=True)
    cases = json.loads(Path('/work/inputs/cases.json').read_text())
    if len(cases) != 3 or len({c['id'] for c in cases}) != 3:
        raise ValueError('Exactly three distinct benchmark cases required')
    deadline = int(os.environ['BENCHMARK_DEADLINE'])
    if not time.time() < deadline <= time.time() + 900:
        raise ValueError('Invalid fixed deadline')
    rank = int(os.environ['RANK'])
    def event(kind, **values):
        row = dict(event=kind, rank=rank, at=time.time(), **values)
        with (output / f'metrics-rank-{rank}.jsonl').open('a') as handle:
            handle.write(json.dumps(row) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        print('LONGCAT_METRIC ' + json.dumps(row), flush=True)
    os.chdir(root)
    sys.path.insert(0, str(root))
    sys.argv = ['run_demo_avatar_single_audio_to_video.py',
        '--input_json', cases[0]['input_json'], '--output_dir', str(output),
        '--checkpoint_dir', '/work/weights/LongCat-Video-Avatar-1.6',
        '--stage_1', 'ai2v', '--model_type', 'avatar-v1.6', '--resolution', '480p',
        '--context_parallel_size', '2', '--num_segments', '1', '--use_distill',
        '--use_int8', '--mix_steps', '4', '--mix_alpha', '1.0',
        '--lora_path', 'loraB/lora.safetensors']
    namespace = dict(__name__='__main__', __file__=str(root / sys.argv[0]),
        BENCHMARK_CASES=cases, BENCHMARK_OUTPUT=str(output),
        BENCHMARK_DEADLINE=deadline, BENCHMARK_STARTED=time.monotonic(),
        benchmark_event=event, time=time)
    exec(resident_source((root / sys.argv[0]).read_text()), namespace)


if __name__ == '__main__':
    main()
