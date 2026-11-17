import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import probe
import guard


class BenchmarkTests(unittest.TestCase):
    def test_guard_accepts_only_exact_scope_and_bounded_deadline(self):
        name='wan-longcat-20261117-0123456789ab'
        guard.validate(name,1900,1000)
        for invalid in ('production-pod','wan-longcat-20261117-0123456789abc',''):
            with self.assertRaises(ValueError):guard.validate(invalid,1900,1000)
        for deadline in (1000,1901):
            with self.assertRaises(ValueError):guard.validate(name,deadline,1000)

    def test_upstream_change_refused(self):
        with self.assertRaises(ValueError):probe.resident_source('def generate(args): pass')

    def test_resident_loop_changes_inputs_without_reinitializing(self):
        # Fictional CPU source implements the same initialization boundary.
        source='''
def generate(args):
    initialize()
    os.makedirs(output_dir, exist_ok=True)
    rendered.append((prompt, raw_speech_path, input_data['cond_image'],output_dir))
'''
        class Cuda:
            synchronize=staticmethod(lambda:None)
            reset_peak_memory_stats=staticmethod(lambda:None)
            max_memory_allocated=staticmethod(lambda:100)
            max_memory_reserved=staticmethod(lambda:200)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cases=[];initializations=[];rendered=[];events=[]
            for i in range(3):
                path=root/f'{i}.json'
                path.write_text(json.dumps({'prompt':str(i),'cond_image':f'{i}.png','cond_audio':{'person1':f'{i}.wav'}}))
                cases.append({'id':str(i),'input_json':str(path)})
            namespace={'Path':Path,'json':json,'os':SimpleNamespace(makedirs=lambda *a,**kw:None),
                'time':SimpleNamespace(time=lambda:100,monotonic=lambda:50),
                'dist':SimpleNamespace(barrier=lambda:None),'torch':SimpleNamespace(cuda=Cuda),
                'initialize':lambda:initializations.append(True),'rendered':rendered,
                'benchmark_event':lambda *a,**kw:events.append((a,kw)),
                'BENCHMARK_CASES':cases,'BENCHMARK_DEADLINE':1000,'BENCHMARK_OUTPUT':str(root),
                'BENCHMARK_STARTED':0}
            with patch.object(probe,'SOURCE_SHA256',hashlib.sha256(source.encode()).hexdigest()):
                exec(probe.resident_source(source),namespace)
            namespace['generate'](None)
            self.assertEqual(len(initializations),1)
            self.assertEqual([x[:3] for x in rendered],[(str(i),f'{i}.wav',f'{i}.png') for i in range(3)])
            self.assertEqual(len({x[3] for x in rendered}),3)
            self.assertEqual([e[1]['resident'] for e in events if e[0][0]=='case_started'],[False,True,True])


if __name__=='__main__':unittest.main()
