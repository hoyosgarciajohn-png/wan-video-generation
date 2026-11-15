"""Build helper verifying the official source archive before extraction."""
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
from urllib.request import urlopen

lock = json.loads(Path('/app/workers/gpu/model.lock.json').read_text())
with tempfile.TemporaryDirectory() as work:
    archive = Path(work) / 'source.tar.gz'
    archive.write_bytes(urlopen(lock['source_url'], timeout=60).read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != lock['source_sha256']:
        raise RuntimeError('Upstream source checksum mismatch')
    with tarfile.open(archive) as source:
        source.extractall(work, filter='data')
    directory = Path(work) / ('Wan2.2-' + lock['profile']['code_revision'])
    directory.rename('/opt/wan')
Path('/opt/wan/REVISION').write_text(lock['profile']['code_revision'] + '\n')
