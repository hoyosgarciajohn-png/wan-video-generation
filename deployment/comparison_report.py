"""Create exact-duration comparison copies from retained originals; CPU only."""
import argparse
import json
from pathlib import Path
import subprocess
from workers.gpu.common import digest, probe, atomic_json, timestamp
from workers.gpu.comparison import SETTINGS


def make_report(directory):
    directory=Path(directory)
    summary=json.loads((directory/'status.json').read_text())
    assert summary['batch']['cleanup_state']=='confirmed' and summary['batch']['state'] in ('succeeded','failed','canceled')
    results=[]
    for metrics in sorted(summary['telemetry'],key=lambda m:m['target_duration_ms']):
        if not any(t['attempt_id']==metrics['attempt_id'] for t in summary['takes']):continue
        seconds=metrics['target_duration_ms']//1000
        source=directory/f'wan-{seconds:02d}s-original.mp4'
        assert source.stat().st_size==metrics['asset_bytes'] and digest(source)==metrics['asset_sha256']
        probe(source,SETTINGS,metrics['frames'])
        subprocess.run(['ffmpeg','-v','error','-xerror','-nostdin','-i',str(source),'-f','null','-'],check=True)
        output=directory/f'wan-{seconds:02d}s.mp4'
        subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-frames:v',str(seconds*24),'-an',
                        '-c:v','libx264','-crf','18','-preset','medium','-threads','2','-pix_fmt','yuv420p',
                        '-map_metadata','-1','-movflags','+faststart',str(output)],check=True)
        checked=probe(output,SETTINGS,seconds*24)
        subprocess.run(['ffmpeg','-v','error','-xerror','-nostdin','-i',str(output),'-f','null','-'],check=True)
        results.append(dict(seconds=seconds,original=source.name,comparison=output.name,sha256=digest(output),
                            bytes=output.stat().st_size,technical_validation='PASS',media=checked,metrics=metrics))
    if len(results)==2:
        output=directory/'wan-side-by-side-first-5s.mp4'
        filters="[0:v]scale=640:352,drawtext=text='Test A - 5 seconds':x=16:y=16:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[a];[1:v]scale=640:352,drawtext=text='Test B - 15 seconds':x=16:y=16:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[b];[a][b]hstack=inputs=2[v]"
        subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(directory/results[0]['comparison']),
                        '-i',str(directory/results[1]['comparison']),'-filter_complex',filters,'-map','[v]',
                        '-frames:v','120','-an','-c:v','libx264','-crf','18','-threads','2','-movflags','+faststart',str(output)],check=True)
    probe(output,dict(width=1280,height=352,frame_rate={'numerator':24,'denominator':1}),120)
    report=dict(results=results,batch=summary['batch']['id'],cleanup=summary['batch']['cleanup_state'],
                billing=summary['billing'],continuation_gate=summary.get('comparison_gate'),
                quality_acceptance='PENDING_OWNER_LIVE_REVIEW',provider_bill_is_batch_level=True)
    rate=summary.get('pricing',{}).get('usd_per_hour')
    report['quoted_hourly_usd']=rate
    if rate and summary.get('allocation_attempts') and summary.get('attempts'):
        allocated=timestamp(summary['allocation_attempts'][-1]['started_at']).timestamp()
        first_claim=min(timestamp(a['started_at']).timestamp() for a in summary['attempts'])
        report['shared_startup_seconds']=first_claim-allocated
        report['shared_startup_compute_estimate_usd']=(first_claim-allocated)/3600*float(rate)
        ended=summary.get('cleanup_confirmed_observed_at',summary['checked_at'])
        report['total_elapsed_compute_estimate_usd']=(ended-allocated)/3600*float(rate)
        report['elapsed_estimate_basis']='Allocation request through first observed confirmed cleanup; upper estimate, not invoice'
        for result in results:
            m=result['metrics']
            result['attributed_compute_estimate_usd']=(m['render_and_verify_seconds']+m['upload_seconds'])/3600*float(rate)
    atomic_json(directory/'comparison-report.json',report)
    completed=', '.join(f"{result['seconds']}-second" for result in results)
    outcome=(f"Retained output: {completed}." if results else 'No committed video was retained.')
    lines=['# WAN duration comparison','',
           outcome+' The planned comparison uses independently generated continuous clips of the same sailboat scene, with fixed model, H100, prompt, seed 42, 1280×704, 24 fps and 50 steps.','',
           '| Test | Model load | Generation | Decode / encode | Peak allocated VRAM | Peak reserved VRAM | Attributed compute estimate |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for result in results:
        m=result['metrics'];cost=result.get('attributed_compute_estimate_usd')
        cost_label=f'${cost:.4f}' if cost is not None else 'Unavailable'
        lines.append(f"| {result['seconds']} seconds | {m['model_load_seconds']:.1f}s | {m['generation_seconds']:.1f}s | {m['decode_encode_seconds']:.1f}s | {m['gpu_peak_allocated_bytes']/1024**3:.2f} GiB | {m['gpu_peak_reserved_bytes']/1024**3:.2f} GiB | {cost_label} |")
    lines += ['', 'Generation includes text encoding and sampling; decode/encode is reported separately. Each render loads the model in an isolated process; the model download is shared.',
              '', 'Each retained comparison copy trims only the original’s final frame to the exact requested duration; playback speed is unchanged. Originals have one extra frame because Wan requires a 4n+1 frame count.',
              '', 'Technical checks passed for each listed clip: resolution, frame rate, frame count, checksum and full video decoding after confirmed Pod cleanup.',
              '', 'The provider invoice covers the entire Pod. Per-clip and elapsed-time amounts are estimates; shared startup is excluded from each clip’s attributed cost. Final billing: '+str(report['billing']),
              '', 'Owner visual acceptance is pending. Review boat and sail consistency, natural motion, flicker, and stable background. A comparison between durations requires both clips.',
              '', 'Cleanup: '+report['cleanup']+'.']
    if report.get('shared_startup_seconds') is not None:
        lines += ['', f"Shared startup: {report['shared_startup_seconds']:.1f} seconds; estimated compute ${report['shared_startup_compute_estimate_usd']:.4f}."]
    if len(results)<2:lines += ['', 'The missing duration did not produce a committed take. Continuation decision: '+str(report['continuation_gate'])]
    (directory/'WAN_Duration_Comparison.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(status='COMPARISON_COPIES_VERIFIED',clips=len(results),cleanup=report['cleanup'])))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path)
    make_report(parser.parse_args().directory)
