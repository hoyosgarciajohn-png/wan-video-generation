"""CPU-only discovery: freeze official S2V source and checkpoint metadata.

Does not create compute, download large weights, or authorize generation. Review
the resulting lock and source before building a separately pinned worker image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
from urllib.request import Request, urlopen


def get(url):
    request = Request(url, headers={'User-Agent': 'wan-singing-preparation/1'})
    with urlopen(request, timeout=60) as response:
        return response.read()


def prepare(destination):
    destination.mkdir(parents=True, exist_ok=False)
    repo = 'Wan-AI/Wan2.2-S2V-14B'
    # Resolve once, then every request is bound to these immutable revisions.
    revision = json.loads(get('https://huggingface.co/api/models/' + repo))['sha']
    metadata = json.loads(get(f'https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true'))
    code = json.loads(get('https://api.github.com/repos/Wan-Video/Wan2.2/commits/main'))['sha']
    source_url = f'https://codeload.github.com/Wan-Video/Wan2.2/tar.gz/{code}'
    source = get(source_url)
    archive = destination / 'upstream.tar.gz'
    archive.write_bytes(source)
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination / 'source', filter='data')
    source_root = destination / 'source' / ('Wan2.2-' + code)
    assert (source_root / 'wan/speech2video.py').is_file(), 'S2V source missing'
    files = []
    for entry in metadata['siblings']:
        name = entry['rfilename']
        if name.startswith(('assets/', '.')) or name.endswith('.md'):
            continue
        # The CTC encoder does not use external decoder language-model files.
        if '/language_model/' in name or name.endswith(('.arpa', '.bin')) and 'pytorch_model' not in name:
            continue
        if entry.get('lfs'):
            size, checksum = entry['lfs']['size'], entry['lfs']['sha256']
        else:
            data = get(f'https://huggingface.co/{repo}/resolve/{revision}/{name}')
            size, checksum = len(data), hashlib.sha256(data).hexdigest()
            target = destination / 'small-files' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        files.append(dict(path=name, bytes=size, sha256=checksum))
    lock = dict(profile=dict(id='wan22-s2v-14b', revision='1',
        checkpoint_ref=repo + '@' + revision, code_revision=code),
        source_url=source_url, source_sha256=hashlib.sha256(source).hexdigest(),
        weight_repo=repo, weight_revision=revision, files=files)
    (destination / 'singing-model.lock.json').write_text(json.dumps(lock, indent=2) + '\n')
    (destination / 'summary.json').write_text(json.dumps(dict(
        status='metadata_prepared_not_gpu_validated', files=len(files),
        total_weight_bytes=sum(x['bytes'] for x in files), profile=lock['profile'],
        compute_created=False), indent=2) + '\n')
    print('Prepared official pinned source and checkpoint metadata; no GPU allocated.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    prepare(parser.parse_args().output)
