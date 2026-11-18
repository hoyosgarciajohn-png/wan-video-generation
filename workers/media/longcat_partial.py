"""Export an explicitly incomplete, contiguous prefix without changing full export.

The manifest and journal must be recovered through the authenticated production
channel. This offline utility never grants authority, allocates a GPU, fills a
gap, or changes the complete original soundtrack.
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import wave

from workers.gpu.common import atomic_json, digest, require
from workers.gpu.longcat_batch import fingerprint, verify_output
from workers.media.export import encode, probe


def assemble_partial_review(manifest, journal, takes, master, master_sha256, destination):
    destination, takes, master = Path(destination), Path(takes), Path(master)
    require(not destination.exists(), 'Review output exists; do not overwrite')
    require(digest(master) == master_sha256, 'Complete master changed')
    with wave.open(str(master)) as audio:
        require((audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes())
                == (2, 2, 48000, manifest['duration_frames'] * 1920), 'Complete master must match timeline')
    binding = fingerprint(manifest)
    require(journal['binding'] == binding, 'Journal belongs to another manifest')
    rows = journal['shots']; selected = []; sources = []; cursor = 0; gap = False
    require(set(rows) <= {s['id'] for s in manifest['shots']}, 'Unknown journal shot')
    for shot in manifest['shots']:
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', shot['id']) is not None, 'Invalid shot ID')
        row = rows.get(shot['id'], {})
        if row.get('status') != 'published':
            gap = True
            continue
        require(not gap, 'Published footage is not a contiguous prefix')
        require(row['input_sha256'] == fingerprint(shot), 'Rendered input changed')
        receipt = row['receipt']
        require(receipt['binding'] == binding and receipt['shot_id'] == shot['id']
                and receipt['scope_id'] == journal['scope_id'], 'Foreign receipt')
        require(shot['in_frame'] == cursor and 0 < shot['frames'] <= 93
                and 0 <= shot['trim_in_frames'] <= 93-shot['frames'], 'Invalid edit trim')
        source = takes / (shot['id'] + '.mp4'); metadata = verify_output(source)
        require((metadata['sha256'], metadata['bytes']) == (receipt['sha256'], receipt['bytes']),
                'Saved footage differs from durable receipt')
        selected.append(shot); sources.append(source); cursor += shot['frames']
    require(0 < len(selected) < len(manifest['shots']), 'Partial export requires an incomplete prefix')
    require(cursor < manifest['duration_frames'], 'Prefix exceeds complete timeline')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='longcat-partial-', dir=destination.parent) as temporary:
        root = Path(temporary)
        for i, (shot, source) in enumerate(zip(selected, sources)):
            start = shot['trim_in_frames']; end = start + shot['frames']
            encode(root/f'{i:03}.mp4', ['-i', str(source), '-map', '0:v:0', '-an', '-vf',
                f'trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS',
                '-r', '25', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p'])
        listing = root/'concat.txt'
        listing.write_text(''.join(f"file '{i:03}.mp4'\n" for i in range(len(selected))))
        # The listening copy ends at the last covered frame; the full WAV is untouched.
        encode(root/'partial.mp4', ['-f', 'concat', '-safe', '1', '-i', str(listing), '-i', str(master),
            '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-af', f'atrim=end_sample={cursor*1920}',
            '-c:a', 'aac', '-b:a', '320k', '-movflags', '+faststart'])
        video = probe(root/'partial.mp4', 'v:0'); audio = probe(root/'partial.mp4', 'a:0')
        require(int(video['nb_frames']) == cursor and video['avg_frame_rate'] == '25/1', 'Frame count changed')
        require(abs(float(audio['duration'])-cursor/25) <= .04, 'Listening-copy duration changed')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(root/'partial.mp4'),
                        '-f', 'null', '-'], check=True, capture_output=True)
        (root/'partial.mp4').replace(destination)
    result = dict(status='INCOMPLETE_RENDERED_PREFIX_NOT_FINAL_VIDEO', manifest_sha256=binding,
        scope_id=journal['scope_id'], sha256=digest(destination), frames=cursor,
        duration_seconds=cursor/25, complete_song_seconds=manifest['duration_frames']/25,
        width=864, height=448, master_wav_sha256=master_sha256,
        included_shots=[s['id'] for s in selected], missing_shots=[s['id'] for s in manifest['shots'][len(selected):]])
    atomic_json(destination.with_suffix('.json'), result)
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'journal', 'takes', 'master', 'master-sha256', 'destination'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    print(json.dumps(assemble_partial_review(json.loads(Path(args.manifest).read_text()),
        json.loads(Path(args.journal).read_text()), args.takes, args.master, args.master_sha256, args.destination)))
