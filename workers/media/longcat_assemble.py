"""Assemble a private review video from authenticated durable LongCat receipts.

This does not fabricate Studio take approvals or mark the video creatively final.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import wave

from workers.gpu.common import atomic_json, digest, require, scoped
from workers.gpu.longcat_batch import fingerprint, verify_output
from workers.media.export import encode, probe


def assemble_review(manifest, receipts, asset_root, master, master_sha256, destination):
    destination=Path(destination);master=Path(master)
    require(not destination.exists(), 'Review output exists; do not overwrite')
    require(digest(master)==master_sha256, 'Complete master changed')
    frames=manifest['duration_frames']
    with wave.open(str(master)) as source:
        require((source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getnframes())
                ==(2,2,48000,frames*1920), 'Complete stereo 48 kHz master must match timeline')
    require(len(receipts)==len(manifest['shots']), 'Every shot needs a durable receipt')
    binding=fingerprint(manifest);sources=[];cursor=0;scope=None
    for shot,receipt in zip(manifest['shots'],receipts):
        require(receipt['binding']==binding and receipt['shot_id']==shot['id'], 'Receipt order or binding changed')
        if scope is None:scope=receipt['scope_id']
        require(receipt['scope_id']==scope, 'Mixed execution receipts')
        require(shot['in_frame']==cursor and 0<shot['frames']<=93 and
                0<=shot['trim_in_frames']<=93-shot['frames'], 'Invalid edit trim')
        path=scoped(asset_root,receipt['object_key']);metadata=verify_output(path)
        require((metadata['sha256'],metadata['bytes'])==(receipt['sha256'],receipt['bytes']), 'Saved take changed')
        sources.append(path);cursor+=shot['frames']
    require(cursor==frames, 'Review timeline duration mismatch')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='longcat-review-',dir=destination.parent) as temporary:
        root=Path(temporary)
        for index,(shot,source) in enumerate(zip(manifest['shots'],sources)):
            start=shot['trim_in_frames'];end=start+shot['frames']
            encode(root/f'{index:03}.mp4',['-i',str(source),'-map','0:v:0','-an',
                '-vf',f'trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS',
                '-r','25','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p'])
        listing=root/'concat.txt'
        listing.write_text(''.join(f"file '{index:03}.mp4'\n" for index in range(len(sources))))
        # No shortest flag, speed change, loop, audio trim, gain or fade.
        encode(root/'review.mp4',['-f','concat','-safe','1','-i',str(listing),'-i',str(master),
            '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','320k','-movflags','+faststart'])
        video=probe(root/'review.mp4','v:0');audio=probe(root/'review.mp4','a:0')
        require(int(video['nb_frames'])==frames and video['avg_frame_rate']=='25/1', 'Assembled frame count changed')
        require(abs(float(audio['duration'])-frames/25)<=.04,'Assembled audio duration changed')
        subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(root/'review.mp4'),
                        '-f','null','-'],check=True,capture_output=True)
        (root/'review.mp4').replace(destination)
    result=dict(status='REVIEW_VIDEO_ASSEMBLED_NOT_CREATIVE_APPROVAL',manifest_sha256=binding,
        scope_id=scope,sha256=digest(destination),frames=frames,duration_seconds=frames/25,
        width=864,height=448,master_wav_sha256=master_sha256)
    atomic_json(destination.with_suffix('.json'),result)
    return result
