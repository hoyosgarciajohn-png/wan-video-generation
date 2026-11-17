"""Download only explicit pinned model files and verify every byte before inference."""
import argparse
from pathlib import Path
import os
import tempfile
from urllib.request import urlopen

from .common import LOCK, digest, require, scoped


def verify(root, *, lock=LOCK):
    for item in lock['files']:
        path = scoped(root, item['path'])
        require(path.stat().st_size == item['bytes'] and digest(path) == item['sha256'],
                'Pinned model file mismatch: ' + item['path'])


def download(root, *, lock=LOCK):
    for item in lock['files']:
        path = scoped(root, item['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size == item['bytes'] and digest(path) == item['sha256']:
            continue
        url = f"https://huggingface.co/{lock['weight_repo']}/resolve/{lock['weight_revision']}/{item['path']}"
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
            temp = Path(out.name)
            try:
                with urlopen(url, timeout=60) as source:
                    count = 0
                    while chunk := source.read(1024 * 1024):
                        count += len(chunk)
                        require(count <= item['bytes'], 'Model download exceeds expected size')
                        out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
                require(count == item['bytes'] and digest(temp) == item['sha256'], 'Download mismatch')
                os.replace(temp, path)
            finally:
                temp.unlink(missing_ok=True)
    verify(root, lock=lock)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['verify', 'download'])
    parser.add_argument('directory', type=Path)
    parser.add_argument('--singing', action='store_true')
    args = parser.parse_args()
    from .profiles import model_lock, singing_profile
    lock = model_lock(singing_profile()) if args.singing else LOCK
    (download if args.action == 'download' else verify)(args.directory, lock=lock)
    print('PASS: pinned checkpoint files verified')

