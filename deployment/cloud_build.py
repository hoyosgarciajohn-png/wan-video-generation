"""Capacity and bounded evidence for manual GitHub-hosted container verification.

No provider credentials, registry publication, checkpoint download or GPU launch.
The existing build verifier remains responsible for actual image/smoke evidence.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deployment.build_verify import daemon_environment, local_daemon

GIB = 1024 ** 3
MIN_DISK = {'cpu': 6 * GIB, 'gpu': 40 * GIB}
MAX_EVIDENCE = 64 * 1024 ** 2
# Only unused SDK installations on the disposable GitHub-hosted VM may be removed.
# No Docker images, workspace paths, caches or user files are pruned.
UNUSED_SDKS = ('/usr/share/dotnet', '/usr/local/lib/android', '/opt/ghc',
               '/usr/local/share/powershell', '/usr/share/swift',
               '/usr/lib/jvm', '/opt/hostedtoolcache/CodeQL')


def require_capacity(target, free_bytes, memory_bytes):
    if free_bytes < MIN_DISK[target]:
        raise ValueError(f'{target} needs at least {MIN_DISK[target] // GIB} GiB free Docker disk')
    if memory_bytes < 6 * GIB:
        raise ValueError('At least 6 GiB host RAM is required')


def preflight(target, output):
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise ValueError('Only the explicitly selected disposable GitHub-hosted runner is supported')
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('Native Linux x86_64 runner required')
    output.mkdir(parents=True, exist_ok=False)
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'target': target,
              'source_commit': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'),
              'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'), 'status': 'UNVERIFIED',
              'removed_unused_sdks': [], 'required_free_bytes': MIN_DISK[target]}
    try:
        endpoint = local_daemon()
        docker_root = Path(subprocess.check_output(
            ['docker', 'info', '--format', '{{.DockerRootDir}}'], text=True,
            env=daemon_environment(endpoint)).strip())
        report['docker_endpoint'] = endpoint
        report['docker_root'] = str(docker_root)
        report['free_bytes_before'] = shutil.disk_usage(docker_root).free
        if target == 'gpu' and report['free_bytes_before'] < MIN_DISK[target]:
            for path in UNUSED_SDKS:
                if Path(path).is_symlink():
                    raise ValueError('Refusing to remove a linked SDK directory')
                if Path(path).is_dir():
                    subprocess.run(['sudo', 'rm', '-rf', '--', path], check=True, timeout=300)
                    report['removed_unused_sdks'].append(path)
                if shutil.disk_usage(docker_root).free >= MIN_DISK[target]:
                    break
        report['free_bytes_after'] = shutil.disk_usage(docker_root).free
        report['memory_bytes'] = os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
        require_capacity(target, report['free_bytes_after'], report['memory_bytes'])
        report['status'] = 'PASS'
    except Exception as exc:
        report['status'] = 'FAIL'
        report['error'] = str(exc)
        raise
    finally:
        (output / 'runner.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))


def archive(output):
    """Preserve only regular bounded evidence, never follow links or upload images."""
    output.mkdir(parents=True, exist_ok=True)
    status = {'job_status_before_archive': os.environ.get('VERIFICATION_OUTCOME', 'unknown'),
              'note': 'Completed gates require manifest/log checks. Cancellation or missing evidence is not PASS.'}
    (output / 'workflow-result.json').write_text(json.dumps(status, indent=2) + '\n')
    paths = sorted(output.rglob('*'))
    if any(path.is_symlink() or (not path.is_file() and not path.is_dir()) for path in paths):
        raise ValueError('Evidence contains a link or special file')
    files = [path for path in paths if path.is_file()]
    if sum(path.stat().st_size for path in files) > MAX_EVIDENCE:
        raise ValueError('Evidence exceeds 64 MiB; refusing unbounded artifact storage')
    destination = output.with_name(output.name + '-evidence.tar.gz')
    with tarfile.open(destination, 'x:gz') as bundle:
        for path in files:
            bundle.add(path, arcname=str(path.relative_to(output)), recursive=False)
    print(f'Evidence archive: {destination}')
    manifest_path = output / 'build/manifest.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        summary = json.dumps({key: manifest.get(key) for key in
                              ['source_commit', 'target', 'image_id', 'gates']}, indent=2)
        print(summary)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
                stream.write('```json\n' + summary + '\n```\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['preflight', 'archive'])
    parser.add_argument('--target', choices=['cpu', 'gpu'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    preflight(args.target, args.output) if args.operation == 'preflight' else archive(args.output)
