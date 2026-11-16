"""Isolated fictional one-minute HD pipeline rehearsal; no provider or credentials."""
import argparse
import base64
from copy import deepcopy
import json
from pathlib import Path
import resource
import shutil
import subprocess
import time

from services.controller.commands import RenderCommands
from services.controller.export_runner import ExportRunner
from services.controller.media_commands import MediaCommands
from services.controller.runner import FixtureRunner
from services.controller.service import ControlService
from services.controller.studio import StudioWorkspace
from workers.gpu.common import atomic_json, digest


def run(directory):
    root=Path(directory).resolve()
    root.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    control=ControlService(root/'state.sqlite',root/'assets')
    studio=StudioWorkspace(control)
    media=MediaCommands(studio)
    owner='fictional-scale-owner'
    state=studio.create(owner,'Fictional one-minute HD rehearsal','music_video',0)
    project=state['projects'][0]['bundle']['project']['id']
    sound=root/'synthetic-tone.mp3'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
        'sine=frequency=440:sample_rate=48000:duration=60','-threads','1','-c:a','libmp3lame',str(sound)],check=True)
    uploaded=media.upload(owner,project,dict(name='Fictional 60-second tone',mime_type='audio/mpeg',
        data_base64=base64.b64encode(sound.read_bytes()).decode(),expected_revision=state['revision'],idempotency_key='tone'))
    state=uploaded['workspace']; p=state['projects'][0]
    template=json.loads((Path(__file__).resolve().parents[1]/'fixtures/project.json').read_text())['shots'][0]
    for i in range(12):
        shot=deepcopy(template)
        shot.update(id=f'fictional-shot-{i+1:02d}',project_id=project,scene_id=p['scenes'][0]['id'],
                    target_duration_ms=5000,reference_asset_ids=[],prompt=f'Fictional blue test shot {i+1}')
        p['bundle']['shots'].append(shot)
    state=studio.save(owner,state,state['revision'])
    commands=RenderCommands(studio)
    batch=commands.submit(owner,project,dict(shot_ids=[s['id'] for s in p['bundle']['shots']],
        expected_revision=state['revision'],idempotency_key='twelve-fictional-shots'))['batch']
    for _ in range(12):
        # Reopen the persistent queue between shots to exercise process recovery.
        control=ControlService(root/'state.sqlite',root/'assets')
        assert FixtureRunner(control).tick()
    bundle=control.bundle(owner,project)
    assert len(bundle['takes'])==len(bundle['attempts'])==12
    assert all(a['state']=='succeeded' for a in bundle['attempts'])
    assert bundle['batches'][0]['state']=='succeeded'
    studio=StudioWorkspace(control); commands=RenderCommands(studio); media=MediaCommands(studio)
    for take in bundle['takes']:
        state=studio.get(owner)
        commands.review(owner,project,take['id'],dict(decision='approved',expected_revision=state['revision'],
            idempotency_key='accept-'+take['id']))
    timeline=media.assemble(owner,project,dict(expected_revision=studio.get(owner)['revision'],
        idempotency_key='assemble-minute',audio_asset_id=uploaded['asset']['id']))['timeline']
    request=dict(timeline_id=timeline['id'],timeline_revision=timeline['revision'],idempotency_key='export-minute')
    job=media.export(owner,project,request)['export']
    queued_at=time.monotonic()
    assert ExportRunner(ControlService(root/'state.sqlite',root/'assets')).tick()
    exported_at=time.monotonic()
    bundle=control.bundle(owner,project)
    complete=next(e for e in bundle['exports'] if e['id']==job['id'])
    assert complete['state']=='succeeded'
    asset=next(a for a in bundle['assets'] if a['id']==complete['output_asset_id'])
    output=root/'assets'/asset['object_key']
    ExportRunner.verify(output,timeline,job['profile'])
    subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-threads','1','-i',str(output),'-f','null','-'],check=True)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(output)]))
    video=next(s for s in info['streams'] if s['codec_type']=='video')
    audio=next(s for s in info['streams'] if s['codec_type']=='audio')
    assert (video['width'],video['height'],int(video['nb_frames']))==(1280,704,1440)
    assert abs(float(video['duration'])-60)<0.001 and abs(float(audio['duration'])-60)<0.025
    replay=MediaCommands(StudioWorkspace(ControlService(root/'state.sqlite',root/'assets'))).export(owner,project,request)
    assert replay['export']['id']==job['id'] and len(replay['workspace']['projects'][0]['bundle']['exports'])==1
    assert digest(output)==asset['sha256']
    result=dict(status='PASS',mode='fictional_cpu_only',gpu_requests=0,wan_generated_clips=0,
        shots=12,duration_seconds=60,source_resolution=[320,180],output_resolution=[1280,704],fps=24,
        frames=1440,audio_codec=audio['codec_name'],video_codec=video['codec_name'],
        output_bytes=asset['bytes'],output_sha256=asset['sha256'],output_path=str(output),
        export_seconds=round(exported_at-queued_at,3),total_seconds=round(time.monotonic()-started,3),
        peak_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        restart_and_idempotency='PASS',full_decode='PASS',free_disk_bytes=shutil.disk_usage(root).free,
        limitations=['Synthetic blue clips enlarged for export; no real Wan generation or creative acceptance.',
                    'Resource measurements apply only to the machine running this rehearsal.'])
    atomic_json(root/'result.json',result)
    print(json.dumps(result),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    run(parser.parse_args().directory)
