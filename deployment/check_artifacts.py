"""Verify local staging source inputs, pins and optional generated static artifact."""
import argparse
from pathlib import Path
import re
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def check(static=False):
    dockerfile = (ROOT / 'deployment/Dockerfile').read_text()
    images = re.findall(r'^FROM (?:--platform=\S+ )?(\S+)', dockerfile, re.M)
    assert len(images) == 3 and all(re.search(r'@sha256:[a-f0-9]{64}$', image) for image in images)
    assert '--require-hashes' in dockerfile and 'npm ci' in dockerfile
    assert 'USER 10001:10001' in dockerfile
    original = (ROOT / 'workers/gpu/requirements.lock').read_text()
    subset = (ROOT / 'deployment/requirements.lock').read_text()
    names = re.findall(r'^([a-z0-9-]+)==', subset, re.M)
    assert set(names) == {'attrs', 'jsonschema', 'jsonschema-specifications', 'referencing', 'rpds-py', 'typing-extensions'}
    for name in names:
        pattern = r'^' + re.escape(name) + r'==.*(?:\n[ \t].*)*'
        normalize = lambda block: '\n'.join(line for line in block.splitlines() if not line.lstrip().startswith('#')).strip()
        assert normalize(re.search(pattern, subset, re.M)[0]) == normalize(re.search(pattern, original, re.M)[0]), name
    compose = (ROOT / 'deployment/compose.yaml').read_text()
    assert '127.0.0.1:${WAN_PORT:-8080}:8080' in compose
    assert 'read_only: true' in compose and 'no-new-privileges:true' in compose
    assert 'WAN_TOKEN_FILE:?' in compose and 'WAN_STATE_DIR:?' in compose
    if static:
        directory = ROOT / 'apps/studio/dist'
        index = (directory / 'index.html').read_text()
        scripts = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', index)
        assert scripts and all((directory / script.lstrip('/')).is_file() for script in scripts)
        assert not list(directory.rglob('*.map')), 'Do not expose build source maps in staging artifact'
    return len(images), len(names)


def check_runtime_imports():
    # Mirror runtime COPY directives without pulling or claiming to build an image.
    runtime = (ROOT / 'deployment/Dockerfile').read_text().rsplit('\nFROM ', 1)[1]
    with tempfile.TemporaryDirectory(prefix='wan-stage-source-') as directory:
        stage = Path(directory)
        for line in runtime.splitlines():
            if not line.startswith('COPY ') or '--from=' in line:
                continue
            parts = shlex.split(line)[1:]
            sources, destination = parts[:-1], parts[-1]
            assert destination.startswith('/app/')
            target = stage / destination.removeprefix('/app/')
            expanded = [path for source in sources for path in ROOT.glob(source)]
            assert expanded, sources
            for source in expanded:
                if source.is_dir():
                    shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                else:
                    output = target / source.name if len(expanded) > 1 or destination.endswith('/') else target
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, output)
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        subprocess.run([sys.executable, '-s', '-c', 'from deployment.local_stage import create_server; from services.controller.runner import FixtureRunner; from services.controller.export_runner import ExportRunner'], cwd=stage, env=environment, check=True, capture_output=True)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static', action='store_true')
    parser.add_argument('--runtime-import', action='store_true')
    args = parser.parse_args()
    images, packages = check(args.static)
    if args.runtime_import:
        check_runtime_imports()
    print(f'PASS: {images} digest-pinned image inputs; {packages} hash-pinned runtime packages; static={args.static}; runtime-source-import={args.runtime_import}')
