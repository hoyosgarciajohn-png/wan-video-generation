"""Prepare image-verification evidence; execute only on an explicitly selected local Docker host.

Default operation is plan-only. No CI, remote daemon, registry push, GPU access,
weight download, provider API, or deployment is performed by this program.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {'cpu': 'deployment/Dockerfile', 'gpu': 'workers/gpu/Dockerfile'}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def allowed_source(path, target):
    if any(part.startswith('.') or part in {'node_modules', 'dist', 'models', 'weights', 'outputs', '__pycache__'} for part in Path(path).parts):
        return False
    if Path(path).suffix in {'.pth', '.safetensors', '.ckpt', '.bin', '.sqlite'}:
        return False
    common = ('contracts/', 'fixtures/', 'workers/gpu/')
    if path.startswith(common):
        return True
    if target == 'cpu':
        return (path.startswith(('apps/studio/', 'services/controller/', 'workers/media/', 'src/wan_platform/')) or
                path in {'scripts/validate_contract.py', 'deployment/Dockerfile',
                         'deployment/Dockerfile.dockerignore', 'deployment/requirements.lock',
                         'deployment/local_stage.py', 'deployment/healthcheck.py'})
    return False


def write_manifest(output, value):
    temporary = output / 'manifest.tmp'
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(output / 'manifest.json')


def prepare(target, output, weights=None):
    output = Path(output).resolve()
    if output == ROOT or ROOT in output.parents or ',' in str(output):
        raise ValueError('Evidence/context must be outside the repository, without commas in the path')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new empty evidence directory; existing evidence is never overwritten')
    output.mkdir(parents=True, exist_ok=True)
    context = output / 'context'
    context.mkdir()
    (output / 'fixture').mkdir()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT))
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    inventory = {}
    for relative in sorted(path for path in files if path and allowed_source(path, target)):
        source = ROOT / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError('Build context must contain ordinary tracked files: ' + relative)
        destination = context / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        inventory[relative] = digest(destination)
    if not (context / TARGETS[target]).is_file():
        raise ValueError('Commit the Dockerfile before preparing verification')
    helper = output / 'container_smoke.py'
    shutil.copy2(ROOT / 'deployment/container_smoke.py', helper)
    tag = f'wan-{target}-verify:{commit[:12]}'
    runtime = ['docker', 'run', '--rm', '--runtime', 'runc', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
               '--security-opt', 'no-new-privileges', '--user', f'{os.getuid()}:{os.getgid()}',
               '--tmpfs', '/tmp:rw,nosuid,nodev,mode=1777', '-e', 'HOME=/tmp',
               '-e', 'NVIDIA_VISIBLE_DEVICES=void', '-e', 'CUDA_VISIBLE_DEVICES=',
               '--entrypoint', 'python']
    commands = [
        ('image_build', ['docker', 'build', '--platform', 'linux/amd64', '--progress', 'plain',
                         '-f', str(context / TARGETS[target]), '--iidfile', str(output / 'built-image-id.txt'), '-t', tag, str(context)]),
        ('image_identity', ['docker', 'image', 'inspect', tag]),
        ('runtime_smoke', runtime + ['--mount', f'type=bind,src={helper},dst=/check.py,readonly', tag, '/check.py', target]),
        ('fixture_smoke', runtime + ['--mount', f'type=bind,src={output / "fixture"},dst=/outputs', tag,
                                    '-m', 'workers.gpu.cli', 'fixture', '--output-root', '/outputs',
                                    '--result', '/outputs/result.json']),
    ]
    if weights is not None:
        weights = Path(weights).resolve(strict=True)
        if not weights.is_dir() or ',' in str(weights):
            raise ValueError('Use an existing weight directory without commas')
        commands.append(('weights_verification', runtime + ['--mount', f'type=bind,src={weights},dst=/models,readonly',
                                                           tag, '-m', 'workers.gpu.weights', 'verify', '/models']))
    gates = {name: 'UNVERIFIED' for name in ['image_build', 'image_identity', 'runtime_smoke', 'fixture_smoke',
                                          'weights_verification', 'cuda_inference', 'gpu_benchmark', 'hosted_deployment']}
    manifest = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                'target': target, 'mode': 'PLAN_ONLY', 'source_commit': commit, 'source_dirty': dirty,
                'source_sha256': inventory, 'smoke_helper_sha256': digest(helper), 'verifier_sha256': digest(__file__),
                'docker_executable': shutil.which('docker'), 'image_tag': tag, 'image_id': None,
                'repo_digests': [], 'gates': gates,
                'planned_commands': [{'gate': name, 'argv': argv} for name, argv in commands], 'executed_commands': []}
    write_manifest(output, manifest)
    return output, manifest


def daemon_environment(endpoint, environment=None):
    value = dict(os.environ if environment is None else environment)
    value['DOCKER_HOST'] = endpoint
    for key in ['DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH']:
        value.pop(key, None)
    return value


def local_daemon(environment=None, run=subprocess.check_output):
    environment = os.environ if environment is None else environment
    context = environment.get('DOCKER_CONTEXT')
    endpoint = environment.get('DOCKER_HOST') if not context else None
    if not endpoint:
        command = ['docker', 'context', 'inspect'] + ([context] if context else [])
        endpoint = json.loads(run(command + ['--format', '{{json .Endpoints.docker.Host}}'], text=True, env=dict(environment)))
    if not isinstance(endpoint, str) or not endpoint.startswith('unix:///'):
        raise ValueError('Only a local Unix-socket Docker daemon is allowed; remote contexts are refused')
    platform = run(['docker', 'version', '--format', '{{.Server.Os}}/{{.Server.Arch}}'], text=True,
                   env=daemon_environment(endpoint, environment)).strip()
    if platform != 'linux/amd64':
        raise ValueError('Use a native Linux amd64 daemon; automatic cross-platform emulation is disabled')
    return endpoint


def verify_fixture(output):
    root = (output / 'fixture').resolve()
    result_path = root / 'result.json'
    result = json.loads(result_path.read_text())
    asset = result['asset']
    path = (root / asset['object_key']).resolve(strict=True)
    path.relative_to(root)
    if (result.get('contract_version') != '0.1.0' or result['metrics']['mode'] != 'fixture' or
            result['metrics']['cost_cents'] != 0 or path.stat().st_size != asset['bytes'] or
            digest(path) != asset['sha256'] or result['take']['asset_id'] != asset['id']):
        raise ValueError('Fixture result/output evidence mismatch')
    return {'result_sha256': digest(result_path), 'asset_sha256': asset['sha256'], 'bytes': asset['bytes'], 'media': result['media']}


def verify_context(output, manifest):
    context = output / 'context'
    paths = list(context.rglob('*'))
    if any(path.is_symlink() for path in paths):
        raise ValueError('Prepared context contains symlinks')
    actual = {str(path.relative_to(context)) for path in paths if path.is_file()}
    if actual != set(manifest['source_sha256']):
        raise ValueError('Prepared context inventory changed')
    if any(digest(context / name) != value for name, value in manifest['source_sha256'].items()):
        raise ValueError('Prepared context source bytes changed')
    helper = output / 'container_smoke.py'
    if helper.is_symlink() or digest(helper) != manifest['smoke_helper_sha256'] or digest(__file__) != manifest['verifier_sha256']:
        raise ValueError('Verification helper bytes changed')


def execute(output, manifest):
    if manifest['source_dirty'] or subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ValueError('Commit/review source changes before executing a verification build')
    if not manifest['docker_executable']:
        raise ValueError('Docker unavailable; all image gates remain UNVERIFIED')
    verify_context(output, manifest)
    endpoint = local_daemon()
    manifest['docker_endpoint'] = endpoint
    manifest['mode'] = 'LOCAL_EXECUTION'
    write_manifest(output, manifest)
    for item in manifest['planned_commands']:
        gate, argv = item['gate'], list(item['argv'])
        if gate != 'image_build':
            image_id = manifest.get('image_id') or manifest.get('built_image_id')
            argv = [image_id if argument == manifest['image_tag'] else argument for argument in argv]
        log = output / f'{gate}.log'
        with log.open('w') as stream:
            result = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, env=daemon_environment(endpoint))
        manifest['executed_commands'].append({'gate': gate, 'argv': argv, 'exit_code': result.returncode,
                                              'log': log.name, 'log_sha256': digest(log)})
        manifest['gates'][gate] = 'PASS' if result.returncode == 0 else 'FAIL'
        if result.returncode == 0 and gate == 'image_build':
            try:
                image_id = (output / 'built-image-id.txt').read_text().strip()
                if not re.fullmatch(r'sha256:[a-f0-9]{64}', image_id):
                    raise ValueError('Missing Docker build image ID')
                manifest['built_image_id'] = image_id
            except (OSError, ValueError):
                manifest['gates'][gate] = 'FAIL'
        if result.returncode == 0 and gate == 'image_identity':
            try:
                record = json.loads(log.read_text())[0]
                if record.get('Architecture') != 'amd64' or record.get('Os') != 'linux' or record.get('Id') != manifest.get('built_image_id'):
                    raise ValueError('Invalid image identity')
                manifest['image_id'] = record['Id']
                manifest['repo_digests'] = record.get('RepoDigests') or []
            except (ValueError, TypeError, KeyError, IndexError):
                manifest['gates'][gate] = 'FAIL'
        if result.returncode == 0 and gate == 'fixture_smoke':
            try:
                manifest['fixture_evidence'] = verify_fixture(output)
            except (OSError, ValueError, KeyError, TypeError):
                manifest['gates'][gate] = 'FAIL'
        write_manifest(output, manifest)
        if manifest['gates'][gate] == 'FAIL':
            raise RuntimeError(f'{gate} failed; see {log}')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=TARGETS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--weights', type=Path, help='Optional existing weights for read-only verification; never downloaded')
    parser.add_argument('--execute', action='store_true', help='Explicitly build and smoke on a local compatible Docker host')
    args = parser.parse_args()
    directory, evidence = prepare(args.target, args.output, args.weights)
    if args.execute:
        execute(directory, evidence)
    print(f'{evidence["mode"]}: {directory / "manifest.json"}; CUDA inference and hosted deployment remain UNVERIFIED')
