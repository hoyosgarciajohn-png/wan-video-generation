"""Offline container checks. This never downloads weights or runs CUDA inference."""
import argparse
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, '/app')


def cpu():
    from deployment.local_stage import create_server
    from services.controller.service import ControlService
    from services.controller.budget import BudgetLedger
    from services.controller.lifecycle import Lifecycle
    from services.controller.orchestration import SimulationCoordinator
    static = Path('/app/apps/studio/dist')
    assert (static / 'index.html').is_file()
    with tempfile.TemporaryDirectory() as directory:
        control = ControlService(Path(directory) / 'studio.sqlite', Path(directory) / 'assets')
        server = create_server(control, {'fictional-container-token-at-least-32-chars': 'fictional-owner'},
                               static, 'http://127.0.0.1:8080', ('127.0.0.1', 0))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for path, status in [('/', 200), ('/healthz', 200), ('/v1/studio/session', 401)]:
                connection = http.client.HTTPConnection(*server.server_address, timeout=5)
                connection.request('GET', path)
                response = connection.getresponse()
                assert response.status == status, (path, response.status)
                response.read()
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
    return {'static_http': 'PASS', 'controller_import': 'PASS', 'cuda_inference': 'UNVERIFIED'}


def source_syntax(root):
    files = sorted(Path(root).rglob('*.py'))
    if not files:
        raise ValueError('Wan Python source is missing')
    for path in files:
        compile(path.read_bytes(), str(path), 'exec')
    return len(files)


def gpu():
    import torch
    import flash_attn
    lock = json.loads(Path('/app/workers/gpu/model.lock.json').read_text())
    assert Path('/opt/wan/REVISION').read_text().strip() == lock['profile']['code_revision']
    assert torch.__version__.split('+')[0] == '2.8.0'
    assert torch._C._GLIBCXX_USE_CXX11_ABI
    assert sys.version_info[:2] == (3, 11)
    assert flash_attn
    source_files = source_syntax('/opt/wan/wan')
    import librosa
    import decord
    import peft
    singing = json.loads(Path('/app/workers/gpu/singing-model.lock.json').read_text())
    assert Path('/opt/wan-s2v/REVISION').read_text().strip() == singing['profile']['code_revision']
    source_syntax('/opt/wan-s2v/wan')
    return {'runtime_import': 'PASS', 'source_revision': lock['profile']['code_revision'],
            'torch': torch.__version__, 'runtime_import_scope': 'torch_and_flash_attn_only',
            'wan_source_syntax': 'PASS', 'wan_source_files': source_files,
            'wan_cuda_import': 'UNVERIFIED_REQUIRES_GPU',
            'cuda_inference': 'UNVERIFIED', 'weights': 'UNVERIFIED'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=['cpu', 'gpu'])
    args = parser.parse_args()
    print(json.dumps(cpu() if args.target == 'cpu' else gpu(), sort_keys=True))
