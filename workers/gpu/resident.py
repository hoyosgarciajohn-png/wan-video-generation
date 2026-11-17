"""Lease-cancellable serial model subprocess, retained between accepted takes."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from .common import ROOT, atomic_json, require
from .worker import RenderProcessFailed, process_failure, process_phase


class ResidentRenderer:
    def __init__(self):
        self.process = None
        self.log = None
        self.binding = None

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.log is not None:
            self.log.close()
        self.process = self.log = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def render(self, spec, lease):
        binding = (spec['weights'], spec['model_profile'])
        require(self.binding is None or binding == self.binding, 'Resident profile changed')
        lease.check()
        path = Path(spec['output']).with_suffix('.json')
        receipt = path.with_suffix('.done.json')
        require(not receipt.exists(), 'Stale render receipt')
        atomic_json(path, spec)
        if self.process is None:
            self.log = tempfile.TemporaryFile()
            self.process = subprocess.Popen([sys.executable, '-m', 'workers.gpu.inference', '--serve'],
                cwd=ROOT, stdin=subprocess.PIPE, stdout=self.log, stderr=self.log, text=True)
            self.binding = binding
        try:
            self.process.stdin.write(json.dumps({'spec': str(path)}) + '\n')
            self.process.stdin.flush()
            while not receipt.exists():
                lease.check()
                if self.process.poll() is not None:
                    raise RenderProcessFailed(process_failure(self.log), process_phase(self.log))
                time.sleep(0.1)
            require(json.loads(receipt.read_text()) == {'output': spec['output']}, 'Render receipt mismatch')
            lease.check()
        except BaseException:
            self.close()
            raise
