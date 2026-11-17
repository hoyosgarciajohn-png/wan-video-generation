"""Upload a frozen song asset package to its owner's authenticated Studio project."""
import argparse
import hashlib
import http.cookiejar
import json
from pathlib import Path
import urllib.request

ORIGIN='https://wan-64-225-114-46.sslip.io'

class SongClient:
    def __init__(self,token_path):
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.call('/v1/studio/session','POST',{'token':Path(token_path).read_text().strip()})
    def call(self,path,method='GET',value=None):
        raw=isinstance(value,bytes)
        headers={'Origin':ORIGIN,'X-WAN-Request':'studio','Content-Type':'application/octet-stream' if raw else 'application/json'}
        data=value if raw else json.dumps(value).encode() if value is not None else None
        request=urllib.request.Request(ORIGIN+path,data=data,headers=headers,method=method)
        with self.opener.open(request,timeout=90) as response:return json.load(response)
    def workspace(self):return self.call('/v1/studio/workspaces/default')['workspace']


def upload(client,proposal,root):
    workspace=client.workspace()
    found=[p for p in workspace['projects'] if p['bundle']['project']['title']==proposal['title']]
    if not found:
        workspace=client.call('/v1/studio/workspaces','POST',dict(title=proposal['title'],kind='music_video',expected_revision=workspace['revision']))['workspace']
        found=[p for p in workspace['projects'] if p['bundle']['project']['title']==proposal['title']]
    assert len(found)==1
    project=found[0]['bundle']['project']['id'];assert found[0]['bundle']['project']['runtime_limit_ms']>=340126
    for name,expected in proposal['assets'].items():
        path=root/name;data=path.read_bytes();checksum=hashlib.sha256(data).hexdigest();assert checksum==expected
        workspace=client.workspace();p=next(p for p in workspace['projects'] if p['bundle']['project']['id']==project)
        matches=[a for a in p['bundle']['assets'] if p['assetNames'].get(a['id'])==name]
        if matches:
            assert len(matches)==1 and matches[0]['sha256']==checksum
            continue
        prefix=f'/v1/studio/projects/{project}/uploads'
        receipt=root/(name+'.upload.json')
        if receipt.exists():session=json.loads(receipt.read_text())
        else:
            request=dict(name=name,mime_type='audio/mp4' if name.endswith('.m4a') else 'image/png',
                bytes=len(data),expected_revision=workspace['revision'],idempotency_key='b07-'+checksum)
            # Persist request before its replay-safe admission.
            request_path=root/(name+'.request.json')
            if request_path.exists():request=json.loads(request_path.read_text())
            else:request_path.write_text(json.dumps(request))
            session=client.call(prefix,'POST',request)['upload'];receipt.write_text(json.dumps(session))
        session=client.call(prefix+'/'+session['id'])['upload'];hashes=[]
        for i,start in enumerate(range(0,len(data),1048576)):
            chunk=data[start:start+1048576];sha=hashlib.sha256(chunk).hexdigest();hashes.append(sha)
            if i<len(session['chunk_sha256']):assert session['chunk_sha256'][i]==sha
            else:client.call(prefix+'/'+session['id']+'/chunks/'+str(i),'PUT',chunk)
        result=client.call(prefix+'/'+session['id']+'/finish','POST',dict(chunk_sha256=hashes))
        assert result['asset']['sha256']==checksum
        print(json.dumps(dict(uploaded=name,bytes=len(data),project=project)),flush=True)
    return project

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--token-file',required=True,type=Path)
    parser.add_argument('--assets',required=True,type=Path);parser.add_argument('--proposal',required=True,type=Path)
    args=parser.parse_args()
    project=upload(SongClient(args.token_file),json.loads(args.proposal.read_text()),args.assets)
    print(json.dumps(dict(status='ALL_SONG_INPUTS_UPLOADED',project=project)))
