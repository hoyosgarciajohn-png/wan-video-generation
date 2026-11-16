"""Run one synthetic HTTPS workflow and an isolated, checksummed recovery drill.

Reads the existing owner credential only on the approved host. No provider create,
live approval or credential mutation. Existing user projects are retained.
"""
import argparse
import base64
import copy
import hashlib
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor

from services.controller.backup import create_backup, restore_backup
from services.controller.service import ControlService
from workers.gpu.common import atomic_json, digest

ORIGIN = 'https://wan-64-225-114-46.sslip.io'
ROOT = Path(os.environ.get('WAN_SOURCE_ROOT', Path(__file__).resolve().parents[1]))
STATE = Path('/var/lib/wan')
TITLE = 'Fictional hosted recovery rehearsal 2026-11-16'


class Client:
    def __init__(self, origin):
        self.origin = origin
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def call(self, route, method='GET', value=None, binary=False):
        headers = {'Sec-Fetch-Site': 'same-origin'}
        if method != 'GET':
            headers.update({'Origin': self.origin, 'Content-Type': 'application/json', 'X-WAN-Request': 'studio'})
        req = Request(self.origin + '/v1/studio/' + route,
                      data=None if value is None else json.dumps(value).encode(), headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=45) as response:
                data = response.read(33 * 1024 * 1024)
                return data if binary else json.loads(data)
        except HTTPError as error:
            status = error.code
            error.close()
            raise RuntimeError(f'Hosted request rejected: HTTP {status}') from None

    def workspace(self):
        return self.call('workspaces/default')['workspace']


def project(workspace, identity):
    return next(p for p in workspace['projects'] if p['bundle']['project']['id'] == identity)


def wait_for(fetch, predicate, timeout=90):
    end = time.monotonic() + timeout
    while True:
        value = fetch()
        if predicate(value):
            return value
        if time.monotonic() >= end:
            raise TimeoutError('Bounded acceptance wait expired')
        time.sleep(1)


def fictional_flow(client, token, output):
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    session = client.call('session', 'POST', {'token': token})
    owner = session['owner_id']
    workspace = client.workspace()
    if any(p['bundle']['project']['title'] == TITLE for p in workspace['projects']):
        raise ValueError('Prior rehearsal retained; inspect it before resuming')
    workspace = client.call('workspaces', 'POST', {'title': TITLE, 'kind': 'music_video',
                            'expected_revision': workspace['revision']})['workspace']
    p = next(p for p in workspace['projects'] if p['bundle']['project']['title'] == TITLE)
    identity = p['bundle']['project']['id']
    atomic_json(output / 'progress.json', {'project': identity, 'phase': 'created'})
    shot = copy.deepcopy(json.loads((ROOT / 'fixtures/project.json').read_text())['shots'][0])
    shot.update(project_id=identity, scene_id=p['scenes'][0]['id'])
    p['bundle']['shots'] = [shot]
    workspace = client.call('workspaces/default', 'PUT', {'workspace': workspace,
                            'expected_revision': workspace['revision']})['workspace']
    prefix = f'projects/{identity}/'
    audio = client.call(prefix + 'assets', 'POST', {
        'name': 'Synthetic recovery soundtrack.wav', 'mime_type': 'audio/wav',
        'data_base64': base64.b64encode((ROOT / 'fixtures/media/audio.wav').read_bytes()).decode(),
        'expected_revision': workspace['revision'], 'idempotency_key': 'host-recovery-audio'})
    workspace = audio['workspace']
    submitted = client.call(prefix + 'batches', 'POST', {'shot_ids': [shot['id']],
        'expected_revision': workspace['revision'], 'idempotency_key': 'host-recovery-render'})
    batch_id = submitted['batch']['id']
    workspace = wait_for(client.workspace, lambda w: next(b for b in project(w, identity)['bundle']['batches']
                        if b['id'] == batch_id)['state'] in ('succeeded','failed','canceled'))
    bundle = project(workspace, identity)['bundle']
    assert next(b for b in bundle['batches'] if b['id'] == batch_id)['state'] == 'succeeded'
    take = bundle['takes'][-1]
    workspace = client.call(prefix + f"takes/{take['id']}/review", 'POST', {'decision': 'approved',
        'expected_revision': workspace['revision'], 'idempotency_key': 'host-recovery-review'})['workspace']
    timeline = client.call(prefix + 'timelines', 'POST', {'audio_asset_id': audio['asset']['id'],
        'expected_revision': workspace['revision'], 'idempotency_key': 'host-recovery-timeline'})['timeline']
    exported = client.call(prefix + 'exports', 'POST', {'timeline_id': timeline['id'],
        'timeline_revision': timeline['revision'], 'idempotency_key': 'host-recovery-export'})['export']
    workspace = wait_for(client.workspace, lambda w: next(e for e in project(w, identity)['bundle']['exports']
                        if e['id'] == exported['id'])['state'] in ('succeeded','failed'))
    bundle = project(workspace, identity)['bundle']
    export = next(e for e in bundle['exports'] if e['id'] == exported['id'])
    assert export['state'] == 'succeeded'
    asset = next(a for a in bundle['assets'] if a['id'] == export['output_asset_id'])
    media = client.call(prefix + f"assets/{asset['id']}/content", binary=True)
    assert hashlib.sha256(media).hexdigest() == asset['sha256'] and len(media) == asset['bytes']
    (output / 'synthetic-export.mp4').write_bytes(media)
    decode(output / 'synthetic-export.mp4')
    result = {'owner': owner, 'project': identity, 'batch': batch_id, 'export': export['id'],
              'asset': asset, 'takes': bundle['takes'], 'reviews': bundle['reviews'],
              'timelines': bundle['timelines'], 'fixture_only': True}
    atomic_json(output / 'workflow.json', result)
    return result


def decode(path):
    subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(path),'-map','0','-f','null','-'],
                   check=True, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def verify_restored(backup, destination, result):
    restored = restore_backup(backup, destination)
    control = ControlService(restored['database'], restored['assets'])
    bundle = control.bundle(result['owner'], result['project'])
    for collection in ('takes','reviews','timelines'):
        assert bundle[collection] == result[collection]
    assert next(e for e in bundle['exports'] if e['id'] == result['export'])['state'] == 'succeeded'
    asset = next(a for a in bundle['assets'] if a['id'] == result['asset']['id'])
    assert asset == result['asset']
    media = Path(restored['assets']) / asset['object_key']
    assert digest(media) == asset['sha256']
    decode(media)
    try:
        control.bundle('fictional-foreign-owner', result['project'])
    except KeyError:
        pass
    else:
        raise AssertionError('Restored owner isolation failed')
    return {'recovered_project': result['project'], 'media_sha256': asset['sha256'],
            'history_preserved': True, 'media_decoded': True, 'owner_isolation': True}


def host_rehearsal():
    assert os.geteuid() == 0 and subprocess.check_output(['hostname'], text=True).strip() == 'wan-controller-01'
    with sqlite3.connect(STATE / 'studio.sqlite') as db:
        assert db.execute('SELECT count(*) FROM live_job_links').fetchone()[0] == 0
        # This first-install drill exports only its newly created fictional work.
        assert db.execute('SELECT count(*) FROM projects').fetchone()[0] == 0
    tokens = json.loads(Path('/etc/wan/studio-tokens.json').read_text())
    assert len(tokens) == 1 and list(tokens.values()) == ['john-hoyos']
    token = next(iter(tokens))
    output = STATE / 'acceptance-20261116'
    client = Client(ORIGIN)
    result = fictional_flow(client, token, output)
    before = json.loads((STATE / 'cleanup-status.json').read_text())
    assert before['ready'] and time.time() - before['checked_at'] < 45
    # Completed synthetic work only; retain cleanup while the web service is stopped.
    subprocess.run(['systemctl','stop','wan-controller'], check=True)
    try:
        fresh = wait_for(lambda: json.loads((STATE / 'cleanup-status.json').read_text()),
                         lambda s: s['ready'] and s['checked_at'] > before['checked_at'], timeout=35)
    finally:
        subprocess.run(['systemctl','start','wan-controller'], check=True)
    subprocess.run(['curl','--fail','--silent','--show-error','--retry','10','--retry-delay','2',
                    '--retry-connrefused', ORIGIN + '/healthz'], check=True, stdout=subprocess.DEVNULL)
    client = Client(ORIGIN)
    client.call('session','POST',{'token': token})
    retained = project(client.workspace(), result['project'])['bundle']
    assert retained['takes'] == result['takes'] and retained['timelines'] == result['timelines']
    create_backup(STATE / 'studio.sqlite', STATE / 'assets', output / 'backup')
    recovery = verify_restored(output / 'backup', output / 'restored', result)
    atomic_json(output / 'result.json', {'http_workflow': 'PASS', 'restart_persistence': 'PASS',
        'cleanup_during_controller_stop': 'PASS', 'cleanup_checked_at': fresh['checked_at'],
        'same_host_restore': recovery, 'paid_dispatch': False})
    print(json.dumps(json.loads((output / 'result.json').read_text())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['host','off-host'])
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    if args.operation == 'host':
        host_rehearsal()
    else:
        result = json.loads((args.directory / 'workflow.json').read_text())
        recovered = verify_restored(args.directory / 'backup', args.directory / 'off-host-restored', result)
        atomic_json(args.directory / 'off-host-result.json', recovered)
        print(json.dumps({'off_host_restore': 'PASS', **recovered}))
