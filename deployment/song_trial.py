"""Prepare the owner's uploaded full song; never starts compute."""
import base64
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import secrets
import subprocess
import wave

from services.controller.media_commands import MediaCommands
from services.controller.service import stamp
from services.controller.studio import StudioWorkspace
from services.controller.live_admission import configuration_hash, APPROVAL_DOMAIN, HOST_DOMAIN
from services.controller.live_execution import PRODUCTION_CMD, BOOTSTRAP_ENTRYPOINT
from services.controller.preflight import _sources
from services.controller.allocation_retry import POLICY
from workers.gpu.common import atomic_json, digest, scoped, utcnow
from workers.gpu.production import PROTOCOL, snapshot_hash
from workers.gpu.profiles import singing_profile


def prepare(op):
    op.primary_ready()
    assert not op.TRIAL.exists() and not op.AUTH.exists(), 'Scope already prepared; never replace it'
    c=op.control()
    with c.transaction() as db:op.prior_history_closed(db)
    studio=StudioWorkspace(c);workspace=studio.get(op.OWNER)
    matches=[p for p in workspace['projects'] if p['bundle']['project']['title']==op.TITLE]
    assert len(matches)==1, 'Upload the exact song project first'
    p=matches[0];project=p['bundle']['project']['id'];bundle=p['bundle']
    assert not bundle['shots'] and not bundle['batches'] and not bundle['takes']
    proposal=op.read(op.ROOT/'deployment/song-production.json')
    assets={p['assetNames'][a['id']]:a for a in bundle['assets']}
    assert len(assets)==11 and set(assets)==set(proposal['assets']), 'Exactly ten anchors and original song required'
    for name,checksum in proposal['assets'].items():
        asset=assets[name];path=scoped(c.asset_root,asset['object_key'])
        assert asset['sha256']==checksum==digest(path) and asset['bytes']==path.stat().st_size
    song=assets['Busca-adentro-de-ti-original.m4a']
    assert song['kind']=='audio' and song['duration_ms']==340126
    assert all(assets[x['image']]['kind']=='image' for x in proposal['cities'])
    pricing=op.checked_quote()
    op.TRIAL.mkdir(mode=0o700);build=op.materialize_build(op.TRIAL/'build')
    atomic_json(op.AUTH,{k:secrets.token_hex(32) for k in ('owner','host','billing')})
    mono=op.TRIAL/'conditioning.wav'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(scoped(c.asset_root,song['object_key'])),
                    '-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(mono)],check=True)
    with wave.open(str(mono),'rb') as source:
        assert source.getparams()[:3]==(1,2,16000)
        pcm=source.readframes(source.getnframes())
    media=MediaCommands(studio);shots=[];start=0
    scene_ids=[f'song-city-{i:02d}' for i in range(10)]
    for i,item in enumerate(proposal['shots']):
        duration=item['duration_ms'];frames=((duration*16+999)//1000+3)//4*4
        samples=frames*1000
        data=pcm[start*32:(start+duration)*32]
        data=(data+bytes(samples*2))[:samples*2]
        audio=op.TRIAL/f'conditioning-{i:03d}.wav'
        with wave.open(str(audio),'wb') as output:
            output.setparams((1,2,16000,0,'NONE','not compressed'));output.writeframes(data)
        reply=media.upload(op.OWNER,project,dict(name=audio.name,mime_type='audio/wav',
            data_base64=base64.b64encode(audio.read_bytes()).decode(),expected_revision=studio.get(op.OWNER)['revision'],
            idempotency_key=f'full-song-audio-{i:03d}'))
        shot=dict(id=f'song-{i:03d}',project_id=project,scene_id=scene_ids[item['city']],revision=1,
            prompt=item['prompt'],target_duration_ms=duration,
            reference_asset_ids=[assets[proposal['cities'][item['city']]['image']]['id'],reply['asset']['id']],
            settings=dict(width=832,height=448,steps=40,seed=17000+i,frame_rate=dict(numerator=16,denominator=1)))
        shots.append(shot);start+=duration
    assert start==340126 and len(shots)==68
    workspace=studio.get(op.OWNER);p=next(p for p in workspace['projects'] if p['bundle']['project']['id']==project)
    p['scenes']=[dict(id=scene_ids[i],title=city['name']) for i,city in enumerate(proposal['cities'])]
    p['bundle']['shots']=shots;p['script']=proposal['treatment']
    workspace=studio.save(op.OWNER,workspace,workspace['revision'])
    snapshots=[dict(shot_id=s['id'],**{k:v for k,v in s.items() if k not in ('id','project_id','scene_id')}) for s in shots]
    profile=dict(model_profile=singing_profile(),image_ref=op.IMAGE,gpu_type=op.GPU,gpu_count=1,
        region=pricing['region'],worker_endpoint=op.ORIGIN,storage_id='wan-controller-01-artifacts')
    launch=dict(image=op.IMAGE,gpu=dict(id=op.GPU,count=1,minCudaVersion='12.8',minRamPerGpu=64),
        cloud='SECURE',disk=100,dataCenterIds=pricing['data_center_ids'],mounts={},ports=[],env={},registry=op.REGISTRY,
        entrypoint=BOOTSTRAP_ENTRYPOINT,cmd=PRODUCTION_CMD)
    queue=dict(protocol=PROTOCOL,shot_ids=[s['id'] for s in shots],snapshots_sha256=snapshot_hash(snapshots),
        max_attempts_per_shot=2,max_runtime_seconds=14400,gpu_cap_cents=1800,total_cap_cents=2000,
        storage_reserve_cents=200,max_hourly_cents=450,image_ref=op.IMAGE)
    expires=stamp(utcnow()+timedelta(hours=6))
    grant=dict(id=op.APPROVAL_ID,owner=op.OWNER,project=project,currency='USD',approved_cents=1800,
        max_runtime_seconds=14400,valid_until=expires,profile=profile,launch_profile=launch,source_sha256=_sources(),
        capacity_retry=dict(POLICY),continuous_queue=queue)
    host=dict(owner=op.OWNER,project=project,config_hash=configuration_hash(profile,launch,None,None,queue),
        source_sha256=grant['source_sha256'],build_manifest_sha256=build['manifest_sha256'],valid_until=expires,
        worker_endpoint=op.ORIGIN,storage_id=profile['storage_id'])
    atomic_json(op.TRIAL/'approval.json',op.sign(grant,'owner',APPROVAL_DOMAIN))
    atomic_json(op.TRIAL/'host.json',op.sign(host,'host',HOST_DOMAIN))
    atomic_json(op.TRIAL/'prepared.json',dict(owner=op.OWNER,project=project,shot=shots[0]['id'],shot_ids=queue['shot_ids'],
        pricing=pricing,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),build=build,
        overall_cap_cents=2000,pod_cap_cents=1800,storage_allowance_cents=200,runtime_seconds=14400,max_attempts=136,
        max_create_requests=3,original_song_asset_id=song['id'],original_song_sha256=song['sha256']))
    print(json.dumps(dict(status='FULL_SONG_PREPARED_NO_GPU',project=project,shots=68,duration_ms=start,quote=pricing)))


def export(op):
    """Recover originals and make a technical draft, without fabricating approval."""
    summary=op.observe();assert summary['batch']['cleanup_state']=='confirmed'
    c=op.control();bundle=c.bundle(op.OWNER,summary['batch']['project_id'])
    proposal=op.read(op.ROOT/'deployment/song-production.json');saved=op.read(op.TRIAL/'prepared.json')
    out=op.TRIAL/'song-output';out.mkdir(mode=0o700,exist_ok=True)
    assets={a['id']:a for a in bundle['assets']};takes={t['shot_id']:t for t in bundle['takes']}
    coverage=[];segments=[];previous_frame=0
    song=assets[saved['original_song_asset_id']];source=scoped(c.asset_root,song['object_key'])
    assert digest(source)==saved['original_song_sha256']
    import shutil
    shutil.copyfile(source,out/'original-song.m4a')
    for i,item in enumerate(proposal['shots']):
        shot_id=f'song-{i:03d}';take=takes.get(shot_id)
        if take is None:continue
        asset=assets[take['asset_id']];source=scoped(c.asset_root,asset['object_key'])
        assert digest(source)==asset['sha256'] and source.stat().st_size==asset['bytes']
        target=out/f'shot-{i:03d}-native.mp4';shutil.copyfile(source,target)
        coverage.append(dict(shot_id=shot_id,start_ms=item['start_ms'],duration_ms=item['duration_ms'],
                             file=target.name,sha256=asset['sha256']))
    report=dict(status='FULL_DRAFT_PENDING_OWNER_REVIEW' if len(coverage)==68 else 'PARTIAL_COVERAGE',
        required_shots=68,completed_shots=len(coverage),coverage_ms=sum(x['duration_ms'] for x in coverage),
        required_duration_ms=340126,coverage=coverage,native=dict(width=832,height=448,fps=16),
        upscale=dict(width=1280,height=720,fps=24),owner_creative_acceptance='PENDING',
        original_song_sha256=saved['original_song_sha256'],cost=summary['billing'])
    if len(coverage)==68:
        for i,item in enumerate(proposal['shots']):
            boundary=(item['start_ms']+item['duration_ms'])*24
            end_frame=(boundary+999)//1000;count=end_frame-previous_frame;previous_frame=end_frame
            clip=out/f'encoded-{i:03d}.mp4';segments.append(clip)
            subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(out/f'shot-{i:03d}-native.mp4'),
                '-vf','fps=24,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1',
                '-frames:v',str(count),'-an','-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-threads','1',str(clip)],check=True)
        listing=out/'concat.txt';listing.write_text(''.join("file '"+p.name+"'\n" for p in segments))
        final=out/'Busca-adentro-de-ti-world-concert-draft.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','1','-i',str(listing),
            '-i',str(out/'original-song.m4a'),'-map','0:v:0','-map','1:a:0','-c','copy','-t','340.126','-movflags','+faststart',str(final)],check=True)
        subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(final),'-f','null','-'],check=True)
        report['video']=dict(file=final.name,sha256=digest(final),bytes=final.stat().st_size)
        for clip in segments:clip.unlink()
    atomic_json(out/'coverage.json',report);atomic_json(out/'status.json',summary)
    print(json.dumps({k:report[k] for k in ('status','completed_shots','coverage_ms','owner_creative_acceptance')}))
