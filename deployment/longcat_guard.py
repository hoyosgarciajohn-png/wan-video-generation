"""Independent read/delete-only cleanup for one exact new LongCat production name."""
import json
import os
import re
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request,urlopen


def validate(name,admitted_at,deadline,now):
    if not re.fullmatch(r'wan-longcat-song-[a-f0-9]{16}',name):raise ValueError('Exact new production name required')
    if not (type(admitted_at) is int and type(deadline) is int and
            admitted_at <= now < deadline and 0 < deadline-admitted_at <= 4800):
        raise ValueError('Original fixed production envelope required')


def watch(name,admitted_at,deadline,request,*,clock=time.time,pause=time.sleep,emit=print):
    validate(name,admitted_at,deadline,clock())
    def matching():
        path='/pods';seen=set();matches=[]
        for _ in range(100):
            page=request('GET',path)
            matches.extend(p for p in page['pods'] if p.get('name')==name)
            if type(page['pagination']['hasNextPage']) is not bool:raise ValueError('Malformed inventory')
            if not page['pagination']['hasNextPage']:return matches
            cursor=page['pagination']['nextCursor']
            if not isinstance(cursor,str) or not cursor:raise ValueError('Missing provider cursor')
            if cursor in seen:raise ValueError('Repeated provider cursor')
            seen.add(cursor);path='/pods?cursor='+quote(cursor,safe='')
        raise ValueError('Incomplete inventory')
    matching();observed=set();clean=False
    emit(json.dumps(dict(status='READY',name=name,admitted_at=admitted_at,deadline=deadline,at=clock())),flush=True)
    while clock()<deadline+180:
        try:
            pods=matching();observed.update(p['id'] for p in pods)
            if clock()>=deadline-30:
                for pod in pods:request('DELETE','/pods/'+quote(pod['id'],safe=''))
                clean=not matching()
                emit(json.dumps(dict(status='ABSENCE_CONFIRMED' if clean else 'CLEANUP_PENDING',
                                     observed_ids=sorted(observed),at=clock())),flush=True)
        except Exception as error:
            clean=False;emit(json.dumps(dict(status='CLEANUP_UNAVAILABLE',type=type(error).__name__)),flush=True)
        pause(5)
    if not clean:raise SystemExit('Cleanup unresolved; no additional allocation')


def main():
    name=os.environ['LONGCAT_POD_NAME'];admitted_at=int(os.environ['LONGCAT_ADMITTED_AT'])
    deadline=int(os.environ['LONGCAT_DEADLINE']);validate(name,admitted_at,deadline,time.time())
    token=os.environ['RUNPOD_CLEANUP_TOKEN']
    def request(method,path):
        if method not in ('GET','DELETE'):raise ValueError('Cleanup only')
        try:
            with urlopen(Request('https://api.runpod.io/v2'+path,method=method,
                         headers={'Authorization':'Bearer '+token}),timeout=15) as response:
                return None if method=='DELETE' else json.load(response)
        except HTTPError as error:
            if error.code==404 and path.startswith('/pods/'):return None
            raise
    watch(name,admitted_at,deadline,request)


if __name__=='__main__':main()
