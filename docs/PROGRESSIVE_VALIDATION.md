# Progressive validation — November 16, 2026

John instructed implementing the progression: repaired one-second worker,
five-second acceptance, production-resolution export, then a one-minute project.
A successful synthetic test is not actual Wan or human creative acceptance.

## Stages and evidence

| Stage | Footage | Five-second shots | Acceptance |
|---|---:|---:|---|
| Repair | 1 second | One short shot | Actual repaired GPU inference, valid saved take, full decode after deletion, billing observation |
| Basic | 5 seconds | 1 | Same plus measured peak VRAM and timing at full shot duration |
| Small project | 1 minute | 12 | Queue, review, timeline/audio, output persistence, resource usage |
| Music-video | 5 minutes | 60 | Sustained throughput, full-song assembly and measured usable-second cost |
| Extended | 15 minutes | 180 | Larger queues, recovery and resource limits |
| Film | 30 minutes | 360 | Planned maximum length; separate creative review |

The repaired one-second scope keeps the previously proposed $5 total maximum,
1,800 seconds from admission and one create/render attempt. $4 is reserved for the
Pod and $1 remains a separately tracked storage allowance. It uses the immutable
repaired image ending `ed50`, fresh exact source/build/host authority, and a separate
independent guard. Both old trials and unsettled liabilities remain untouched.
No five-second or 12-shot paid grant is installed by this increment. Later paid
stages need a measured budget and their own bounded authorization.

## Export change

New connected exports capture 1280x704 at 24 fps in their immutable profile.
MP4/H.264 and optional AAC remain unchanged. Old queued/completed 320x180 jobs keep
their original profile; output verification uses the captured profile, never the
new default. Studio displays each export's dimensions. The media worker limits
FFmpeg codec and filter threads to one for the 1-vCPU/2-GiB controller.

Contract remains 0.1.0; there are no wire-field changes. The default behavior
changes for new jobs only. Consumers: controller admission and runner, media worker,
Studio export display. Tracked under issues #5 and #7.

## Fictional rehearsal

`python -m deployment.scale_rehearsal --directory <new-private-directory>` creates
an isolated database, 12 five-second synthetic jobs and a 60-second tone. It uses
normal admission/review/assembly/export operations, reopens state between shots,
verifies 1,440 frames at 1280x704/24fps, checks audio duration, fully decodes the MP4
and confirms replay returns the same saved export. Existing directories are refused.
No provider call or credential is used. Original footage is synthetic 320x180;
enlarging it tests HD export mechanics, not image detail or Wan quality.

The hosted `scale-rehearsal` operation runs as the existing `wan` service user in
its own directory, not against the owner's live database. Local and hosted resource
measurements are recorded separately. Fifteen/thirty-minute scale is not claimed.

## Release boundaries

The repaired worker image does not need rebuilding: this increment does not alter
its pinned context. Host source is upgraded before any preparation/admission.
Production paid Studio dispatch remains disabled. If the repaired one-second run
fails, stop paid progression and investigate its safe stage diagnostics.
