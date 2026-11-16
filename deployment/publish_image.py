"""Publish only a verified image to this project's private GHCR package.

The ephemeral workflow token is never written into evidence. This proves registry
publication and authenticated manifest access, not a Runpod download or GPU run.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPOSITORY = 'hoyosgarciajohn-png/wan-video-generation'
PACKAGE = 'wan-video-generation-gpu'
IMAGE = 'ghcr.io/hoyosgarciajohn-png/' + PACKAGE
ACCEPT = 'application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json'


def request(url, headers):
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        body = response.read(2 * 1024 * 1024 + 1)
        if len(body) > 2 * 1024 * 1024:
            raise ValueError('Registry metadata exceeds limit')
        return body


def package_visibility(token, allow_missing=False):
    try:
        value = json.loads(request('https://api.github.com/users/hoyosgarciajohn-png/packages/container/' + PACKAGE,
                                  {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json'}))
    except HTTPError as error:
        if allow_missing and error.code == 404:
            return 'new-private-default'
        raise ValueError('Package visibility could not be verified') from None
    if value.get('visibility') != 'private':
        raise ValueError('Refusing to publish to a non-private package')
    return 'private'


def verified_manifest(path):
    value = json.loads(path.read_text())
    if value.get('target') != 'gpu' or value.get('source_dirty') is not False:
        raise ValueError('Clean GPU build required')
    if any(value['gates'].get(gate) != 'PASS' for gate in
           ('image_build', 'image_identity', 'runtime_smoke', 'fixture_smoke')):
        raise ValueError('All offline build gates must pass before publication')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', value.get('image_id') or ''):
        raise ValueError('Verified Docker image ID required')
    if not re.fullmatch(r'[a-f0-9]{40}', value.get('source_commit') or ''):
        raise ValueError('Exact source commit required')
    return value


def validate_remote(body, image_id):
    value = json.loads(body)
    if value.get('schemaVersion') != 2 or value.get('config', {}).get('digest') != image_id:
        raise ValueError('Registry manifest is not bound to the tested image')
    return 'sha256:' + hashlib.sha256(body).hexdigest()


def publish(output):
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Publication is restricted to reviewed main in this repository')
    value = verified_manifest(output / 'build/manifest.json')
    if value['source_commit'] != os.environ.get('GITHUB_SHA'):
        raise ValueError('Build checkout must match workflow revision')
    token = os.environ['GH_TOKEN']
    actor = os.environ['GITHUB_ACTOR']
    report = {'source_commit': value['source_commit'], 'image_id': value['image_id'],
              'registry_status': 'UNVERIFIED', 'runpod_pull': 'UNVERIFIED',
              'run_id': os.environ['GITHUB_RUN_ID']}
    tag = IMAGE + ':sha-' + value['source_commit']
    try:
        report['visibility_before'] = package_visibility(token, allow_missing=True)
        # Docker credentials live only in a temporary directory outside evidence.
        with tempfile.TemporaryDirectory(prefix='wan-registry-') as directory:
            env = {key: val for key, val in os.environ.items() if key != 'GH_TOKEN'}
            env['DOCKER_CONFIG'] = directory
            subprocess.run(['docker', 'login', 'ghcr.io', '-u', actor, '--password-stdin'],
                           input=token, text=True, check=True, env=env, timeout=60,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['docker', 'tag', value['image_id'], tag], check=True, env=env, timeout=30)
            with (output / 'publish.log').open('w') as log:
                subprocess.run(['docker', 'push', tag], check=True, env=env, timeout=900,
                               stdout=log, stderr=subprocess.STDOUT)
        report['visibility_after'] = package_visibility(token)
        scope = 'repository:hoyosgarciajohn-png/' + PACKAGE + ':pull'
        basic = base64.b64encode((actor + ':' + token).encode()).decode()
        auth_url = 'https://ghcr.io/token?service=ghcr.io&scope=' + scope
        access = json.loads(request(auth_url, {'Authorization': 'Basic ' + basic}))['token']
        manifest_url = 'https://ghcr.io/v2/hoyosgarciajohn-png/' + PACKAGE + '/manifests/sha-' + value['source_commit']
        body = request(manifest_url, {'Authorization': 'Bearer ' + access, 'Accept': ACCEPT})
        digest = validate_remote(body, value['image_id'])
        # An unauthenticated token request must be denied for this private image.
        try:
            anonymous = json.loads(request(auth_url, {}))['token']
            request(manifest_url, {'Authorization': 'Bearer ' + anonymous, 'Accept': ACCEPT})
        except HTTPError as error:
            if error.code not in (401, 403):
                raise ValueError('Unexpected anonymous registry response') from None
        else:
            raise ValueError('Anonymous registry access unexpectedly succeeded')
        (output / 'registry-manifest.json').write_bytes(body)
        report.update(registry_status='PASS', registry_digest=digest, image=IMAGE + '@' + digest,
                      anonymous_access='DENIED', authenticated_manifest='PASS',
                      scope='Registry manifest/config verification; not a fresh layer download')
    finally:
        (output / 'publication.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    publish(parser.parse_args().output)
