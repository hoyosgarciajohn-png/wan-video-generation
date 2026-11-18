"""Publish the import-checked private LongCat image; never allocate a GPU."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError

from deployment.publish_image import (ACCEPT, IMAGE, PACKAGE, REPOSITORY,
    package_visibility, request, validate_remote)


def validate_build(value, commit):
    if not re.fullmatch(r'[a-f0-9]{40}', commit or ''):
        raise ValueError('Exact workflow source required')
    if value.get('source_commit') != commit or value.get('protocol') != 'longcat-song-batch-v1':
        raise ValueError('LongCat build source/protocol mismatch')
    if value.get('offline_import') != 'PASS':
        raise ValueError('Actual offline production import required')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', value.get('image_id', '')):
        raise ValueError('Built image ID required')
    return value


def publish(output):
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Only this reviewed repository main may publish')
    value=validate_build(json.loads((output/'build.json').read_text()), os.environ.get('GITHUB_SHA'))
    tag=IMAGE+':longcat-production-'+value['source_commit']
    local=json.loads(subprocess.check_output(['docker','image','inspect',tag],text=True))[0]
    if local['Id'] != value['image_id'] or local['Config']['Labels'].get('org.opencontainers.image.revision') != value['source_commit']:
        raise ValueError('Publication tag does not identify the checked source/image')
    token=os.environ['GH_TOKEN'];actor=os.environ['GITHUB_ACTOR']
    report=dict(source_commit=value['source_commit'],image_id=value['image_id'],
                run_id=os.environ['GITHUB_RUN_ID'],registry_status='UNVERIFIED',runpod_pull='UNVERIFIED')
    try:
        report['visibility_before']=package_visibility(token)
        env={k:v for k,v in os.environ.items() if k!='GH_TOKEN'}
        with (output/'publish.log').open('w') as log:
            subprocess.run(['docker','push',tag],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
        report['visibility_after']=package_visibility(token)
        auth='https://ghcr.io/token?service=ghcr.io&scope=repository:hoyosgarciajohn-png/'+PACKAGE+':pull'
        basic=base64.b64encode((actor+':'+token).encode()).decode()
        access=json.loads(request(auth,{'Authorization':'Basic '+basic}))['token']
        url='https://ghcr.io/v2/hoyosgarciajohn-png/'+PACKAGE+'/manifests/longcat-production-'+value['source_commit']
        body=request(url,{'Authorization':'Bearer '+access,'Accept':ACCEPT})
        digest=validate_remote(body,value['image_id'])
        try:
            anonymous=json.loads(request(auth,{}))['token']
            request(url,{'Authorization':'Bearer '+anonymous,'Accept':ACCEPT})
        except HTTPError as error:
            if error.code not in (401,403): raise ValueError('Unexpected anonymous registry response') from None
        else:
            raise ValueError('Anonymous registry access unexpectedly succeeded')
        (output/'registry-manifest.json').write_bytes(body)
        report.update(registry_status='PASS',image=IMAGE+'@'+digest,registry_digest=digest,
                      anonymous_access='DENIED',offline_import='PASS')
    finally:
        (output/'publication.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    publish(parser.parse_args().output)
