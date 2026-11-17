"""Independent read/delete-only guard for exactly this approved benchmark."""
import json
import os
import re
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import quote


def validate(name,deadline,now):
    if not re.fullmatch(r'wan-longcat-20261117-[a-f0-9]{12}',name):
        raise ValueError('Exact benchmark name required')
    if type(deadline) is not int or not now < deadline <= now+900:
        raise ValueError('Deadline exceeds approved 15-minute envelope')


def main():
    name=os.environ['BENCHMARK_NAME'];deadline=int(os.environ['BENCHMARK_DEADLINE'])
    validate(name,deadline,time.time())
    token=os.environ['RUNPOD_CLEANUP_TOKEN']
    def request(method,path):
        if method not in ('GET','DELETE'):raise ValueError('Cleanup only')
        try:
            with urlopen(Request('https://api.runpod.io/v2'+path,method=method,
                headers={'Authorization':'Bearer '+token}),timeout=15) as r:
                return None if method=='DELETE' else json.load(r)
        except HTTPError as error:
            if error.code==404 and path.startswith('/pods/'):
                return None
            raise
    def matching():
        matches=[];path='/pods';seen=set()
        for _ in range(100):
            page=request('GET',path)
            matches.extend(p for p in page['pods'] if p.get('name')==name)
            pagination=page['pagination']
            if not pagination['hasNextPage']:return matches
            cursor=pagination['nextCursor']
            if cursor in seen:raise ValueError('Repeated provider cursor')
            seen.add(cursor);path='/pods?cursor='+quote(cursor,safe='')
        raise ValueError('Incomplete inventory')
    matching()
    print(json.dumps({'status':'READY','name':name,'deadline':deadline,'at':time.time()}),flush=True)
    observed=set();clean=False
    while time.time()<deadline+180:
        try:
            pods=matching();observed.update(p['id'] for p in pods)
            # Begin termination 30s before the approved ceiling.
            if time.time()>=deadline-30:
                for p in pods:request('DELETE','/pods/'+quote(p['id'],safe=''))
                clean=not matching()
                print(json.dumps({'status':'ABSENCE_CONFIRMED' if clean else 'CLEANUP_PENDING',
                                  'observed_ids':sorted(observed),'at':time.time()}),flush=True)
            else:
                print(json.dumps({'status':'WATCHING','observed_ids':sorted(observed),'at':time.time()}),flush=True)
        except Exception as e:
            clean=False
            print(json.dumps({'status':'READ_OR_CLEANUP_UNAVAILABLE','error_type':type(e).__name__,'at':time.time()}),flush=True)
        time.sleep(5)
    if not clean:raise SystemExit('Cleanup unresolved; do not allocate another Pod')


if __name__=='__main__':main()
