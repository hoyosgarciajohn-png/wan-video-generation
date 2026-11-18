"""Temporary loopback import/control bridge behind the existing HTTPS proxy.

Four-hour expiration, one production package, one random bearer, no shell or
provider-create route. The proxy's original request-size limit stays unchanged.
"""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path('/root/wan-longcat-session-20261118')
PREFIX='/_longcat_production_20261118/'
CHUNK=24*1024*1024
SIZE=144509707
ROUTE='''    # BEGIN bounded LongCat production
    handle /_longcat_production_20261118/* {
        reverse_proxy 127.0.0.1:8091 {
            transport http {
                response_header_timeout 900s
            }
        }
    }
    # END bounded LongCat production
'''
READ={'status','credential','export','shots'}
WRITE={'prepare','admit','fence-create','cleanup','assemble','close','import'}


def authorized(headers, token):
    return not headers.get('Origin') and hmac.compare_digest(headers.get('Authorization',''),'Bearer '+token)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass

    def reply(self,code,data):
        body=json.dumps(data).encode();self.send_response(code)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)

    def do_GET(self):self.handle_operation()
    def do_POST(self):self.handle_operation()
    def do_PUT(self):self.handle_operation()

    def handle_operation(self):
        if time.time()>=self.server.authority['expires_at'] or not authorized(self.headers,self.server.token):
            self.reply(403,{'error':'unauthorized'});return
        if not self.path.startswith(PREFIX):self.reply(404,{'error':'route'});return
        op=self.path[len(PREFIX):]
        try:
            if self.command=='PUT' and op.startswith('chunk/'):
                index=int(op[6:]);assert str(index)==op[6:] and 0<=index<6
                size=min(CHUNK,SIZE-index*CHUNK);assert int(self.headers['Content-Length'])==size
                chunks=ROOT/'chunks';chunks.mkdir(exist_ok=True)
                target=chunks/str(index);partial=chunks/(str(index)+'.partial')
                assert not target.exists() and not partial.exists()
                with partial.open('xb') as f:
                    remaining=size
                    while remaining:
                        data=self.rfile.read(min(1024*1024,remaining));assert data
                        f.write(data);remaining-=len(data)
                    f.flush();os.fsync(f.fileno())
                partial.rename(target);self.reply(200,{'chunk':index,'bytes':size});return
            assert (self.command=='GET' and op in READ) or (self.command=='POST' and op in WRITE)
            size=int(self.headers.get('Content-Length','0'));assert 0<=size<=128*1024
            payload=self.rfile.read(size);assert len(payload)==size
            env={**os.environ,'PYTHONPATH':'/opt/wan/current','SSH_ORIGINAL_COMMAND':op}
            command=['/opt/wan/venv/bin/python',str(ROOT/'longcat_session.py')]
            if op=='import':
                env['SSH_ORIGINAL_COMMAND']='upload';archive=ROOT/'transport.zip'
                with archive.open('xb') as out:
                    for i in range(6):
                        with (ROOT/'chunks'/str(i)).open('rb') as source:shutil.copyfileobj(source,out)
                with archive.open('rb') as source:result=subprocess.run(command,env=env,stdin=source,capture_output=True,timeout=180)
                archive.unlink()
                if result.returncode:raise ValueError(result.stderr.decode()[:200])
                self.reply(200,json.loads(result.stdout));return
            if op in {'export','shots'}:
                process=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
                self.send_response(200);self.send_header('Content-Type','application/octet-stream')
                self.send_header('Cache-Control','no-store');self.end_headers()
                try:shutil.copyfileobj(process.stdout,self.wfile)
                finally:process.stdout.close();process.wait(timeout=30)
                return
            result=subprocess.run(command,env=env,input=payload,capture_output=True,timeout=850)
            if result.returncode:raise ValueError(result.stderr.decode()[:200])
            self.reply(200,json.loads(result.stdout))
            if op=='close':self.server.closed=True
        except Exception as error:
            self.reply(422,{'error':type(error).__name__,'detail':str(error)[:200]})


def main():
    os.umask(0o077)
    authority=json.loads((ROOT/'authority.json').read_text())
    server=HTTPServer(('127.0.0.1',8091),Handler);server.timeout=1
    server.authority=authority;server.token=(ROOT/'http-token').read_text().strip();server.closed=False
    try:
        while not server.closed and time.time()<authority['expires_at']:server.handle_request()
    finally:
        server.server_close()
        caddy=Path('/etc/wan/Caddyfile');value=caddy.read_text()
        if ROUTE in value:
            caddy.write_text(value.replace(ROUTE,''));subprocess.run(['systemctl','reload','wan-proxy'],check=True)
        (ROOT/'http-token').unlink(missing_ok=True)


if __name__=='__main__':main()
