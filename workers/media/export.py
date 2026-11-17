"""Local CPU worker for server-authorized WAN 0.1.0 export snapshots."""

import fcntl
import hashlib
import json
import subprocess
from datetime import datetime
from fractions import Fraction
from pathlib import Path

RUNTIME_CAPS = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts" / "runtime-policy.json").read_text()
)["runtime_caps_ms"]


def probe(path, stream):
    result = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", stream,
        "-show_streams", "-of", "json", str(path),
    ])
    streams = json.loads(result)["streams"]
    if not streams:
        raise ValueError(f"Missing {stream} stream")
    return streams[0]


def encode(target, args):
    partial = target.with_suffix(".partial.mp4")
    try:
        subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-y", "-threads", "1",
            "-filter_threads", "1", "-filter_complex_threads", "1",
            *args, "-threads", "1", str(partial),
        ], check=True)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def cache_valid(path):
    """Only reuse bytes recorded after successful verification in this job."""
    try:
        return digest(path) == path.with_suffix(".sha256").read_text()
    except (FileNotFoundError, UnicodeError):
        return False


def record_cache(path):
    checksum = path.with_suffix(".sha256")
    temporary = checksum.with_suffix(".tmp")
    temporary.write_text(digest(path))
    temporary.replace(checksum)


def ffseconds(ms):
    return f"{ms / 1000:.3f}"


def frame_rate(record):
    return Fraction(record["numerator"], record["denominator"])


def export_bundle(bundle, export_id, project_id, media_root, job_root, progress=None):
    """Run or retry one immutable export. The caller authorizes project_id.

    Pass a trusted private job root and a staged, immutable local asset root.
    Progress receives (state, completed_video_segments, total_video_segments).
    """
    project = bundle["project"]
    if project["id"] != project_id:
        raise ValueError("Project mismatch")
    exports = [row for row in bundle["exports"] if row["id"] == export_id]
    if len(exports) != 1 or exports[0]["project_id"] != project_id:
        raise ValueError("Export inaccessible")
    job = exports[0]
    timeline, = (
        row for row in bundle["timelines"]
        if row["project_id"] == project_id and row["id"] == job["timeline_id"]
        and row["revision"] == job["timeline_revision"]
    )
    # Freeze the caller's snapshot and use its canonical JSON for retry identity.
    snapshot = json.dumps([project, timeline, job["profile"]], sort_keys=True)
    project, timeline, profile = json.loads(snapshot)
    if (profile["container"], profile["video_codec"], profile["audio_codec"]) != (
        "mp4", "h264", "aac",
    ):
        raise ValueError("Unsupported export profile")
    fps = frame_rate(profile["frame_rate"])
    width, height = profile["width"], profile["height"]
    if fps <= 0 or min(width, height) <= 0 or width % 2 or height % 2:
        raise ValueError("Invalid export dimensions or frame rate")
    root = Path(media_root).resolve()
    assets = {row["id"]: row for row in bundle["assets"]}
    takes = {row["id"]: row for row in bundle["takes"]}
    verified = {}

    def asset(asset_id, kind):
        if (asset_id, kind) not in verified:
            row = assets[asset_id]
            path = (root / row["object_key"]).resolve()
            if (
                row["project_id"] != project_id or row["owner_id"] != project["owner_id"]
                or row["kind"] != kind or not path.is_relative_to(root)
                or path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]
            ):
                raise ValueError("Asset failed project or integrity validation")
            stream = probe(path, "v:0" if kind == "video" else "a:0")
            verified[asset_id, kind] = path, stream, row["sha256"]
        return verified[asset_id, kind]

    segments = []
    elapsed = previous_frame = 0
    timestamp = datetime.fromisoformat(timeline["created_at"])
    for item in timeline["items"]:
        take = takes[item["take_id"]]
        if take["project_id"] != project_id:
            raise ValueError("Take belongs to another project")
        reviews = [
            (datetime.fromisoformat(review["decided_at"]), review["decision"])
            for review in bundle["reviews"]
            if review["project_id"] == project_id and review["take_id"] == take["id"]
            and datetime.fromisoformat(review["decided_at"]) <= timestamp
        ]
        if not reviews or max(reversed(reviews), key=lambda review: review[0])[1] != "approved":
            raise ValueError("Take was not approved at timeline revision")
        start, end = item["source_in_ms"], item["source_out_ms"]
        source, stream, checksum = asset(take["asset_id"], "video")
        actual_fps = Fraction(stream["avg_frame_rate"])
        measured = Fraction(stream["duration"]) * 1000
        if (
            actual_fps <= 0 or actual_fps != frame_rate(take["frame_rate"])
            or (stream["width"], stream["height"]) != (take["width"], take["height"])
            or abs(measured - take["duration_ms"]) > 1
            or not 0 <= start < end <= take["duration_ms"]
        ):
            raise ValueError("Take metadata or trim does not match the source")
        elapsed += end - start
        # Round cumulative boundaries to keep drift bounded to half a frame.
        boundary = round(elapsed * fps / 1000)
        count = boundary - previous_frame
        if count < 1:
            raise ValueError("Shot is shorter than one output frame")
        segments.append((source, start, end, count, checksum))
        previous_frame = boundary

    maximum = RUNTIME_CAPS[project["kind"]]
    if not 0 < elapsed == timeline["duration_ms"] <= min(maximum, project["runtime_limit_ms"]):
        raise ValueError("Invalid timeline duration or project cap exceeded")

    audio = []
    for item in timeline["audio"]:
        source, stream, checksum = asset(item["asset_id"], "audio")
        start, end = item["source_in_ms"], item["source_out_ms"]
        offset = item["timeline_start_ms"]
        if not (
            0 <= start < end <= Fraction(stream["duration"]) * 1000 + 1
            and end <= assets[item["asset_id"]]["duration_ms"]
            and 0 <= offset <= elapsed - (end - start)
        ):
            raise ValueError("Invalid soundtrack trim or offset")
        audio.append((source, start, end, offset, checksum))

    job_dir = Path(job_root) / hashlib.sha256(
        json.dumps([project_id, export_id]).encode()
    ).hexdigest()
    job_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(json.dumps([
        snapshot, [part[-1] for part in segments], [part[-1] for part in audio],
    ]).encode()).hexdigest()
    with (job_dir / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = job_dir / "snapshot"
        if manifest.exists() and manifest.read_text() != fingerprint:
            raise ValueError("Export inputs changed for an existing job")
        if not manifest.exists():
            temporary = manifest.with_suffix(".tmp")
            temporary.write_text(fingerprint)
            temporary.replace(manifest)
        return assemble(job_dir, segments, audio, profile, fps, elapsed, progress)


def assemble(directory, segments, audio, profile, fps, duration, progress):
    output = directory / "output.mp4"
    total = len(segments)
    report = progress or (lambda *_: None)
    if cache_valid(output):
        report("succeeded", total, total)
        return output

    completed = 0
    try:
        report("rendering", completed, total)
        names = []
        width, height = profile["width"], profile["height"]
        for index, (source, start, end, frames, _) in enumerate(segments):
            name = f"shot-{index:06d}.mp4"
            target = directory / name
            names.append(f"file '{name}'\nduration {float(frames / fps):.9f}\n")
            if not cache_valid(target):
                filters = (
                    f"trim=start={ffseconds(start)}:end={ffseconds(end)},"
                    f"setpts=PTS-STARTPTS,fps={fps},"
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
                    f"tpad=stop_mode=clone:stop_duration={float(1 / fps):.9f}"
                )
                encode(target, [
                    "-i", str(source), "-map", "0:v:0", "-vf", filters,
                    "-frames:v", str(frames), "-an", "-c:v", "libx264",
                    "-preset", "veryfast", "-pix_fmt", "yuv420p", "-bf", "0",
                    "-video_track_timescale", str(fps.numerator),
                ])
            if int(probe(target, "v:0")["nb_frames"]) != frames:
                target.unlink()
                raise ValueError("Trim produced the wrong frame count")
            record_cache(target)
            completed += 1
            report("rendering", completed, total)

        playlist = directory / "shots.txt"
        playlist.write_text("".join(names))
        args = ["-f", "concat", "-safe", "1", "-i", str(playlist)]
        mix = []
        for index, (source, start, end, offset, _) in enumerate(audio, 1):
            args.extend(["-i", str(source)])
            mix.append(
                f"[{index}:a]atrim=start={ffseconds(start)}:end={ffseconds(end)},"
                f"asetpts=PTS-STARTPTS,adelay={offset}:all=1,asetpts=N/SR/TB[a{index}]"
            )
        args.extend(["-map", "0:v:0"])
        if mix:
            inputs = "".join(f"[a{index}]" for index in range(1, len(audio) + 1))
            mix.append(
                f"{inputs}amix=inputs={len(audio)}:normalize=0,"
                f"asetpts=N/SR/TB,apad=whole_dur={ffseconds(duration)},atrim=duration={ffseconds(duration)},asetpts=N/SR/TB[sound]"
            )
            args.extend(["-filter_complex", ";".join(mix), "-map", "[sound]", "-c:a", "aac"])
        candidate = directory / "assembled.mp4"
        encode(candidate, [
            *args, "-c:v", "copy", "-video_track_timescale", str(fps.numerator),
            "-movflags", "+faststart",
        ])
        video = probe(candidate, "v:0")
        expected_frames = sum(part[3] for part in segments)
        measured = Fraction(video["duration"])
        if (
            video["codec_name"] != "h264" or int(video["nb_frames"]) != expected_frames
            or Fraction(video["avg_frame_rate"]) != fps
            or abs(measured - Fraction(duration, 1000)) > max(1 / fps, Fraction(1, 1000))
        ):
            raise ValueError("Output video failed codec, frame count or duration verification")
        if audio:
            sound = probe(candidate, "a:0")
            if sound["codec_name"] != "aac" or abs(
                Fraction(sound["duration"]) - Fraction(duration, 1000)
            ) > Fraction(25, 1000):
                raise ValueError("Output soundtrack failed duration verification")
        candidate.replace(output)
        record_cache(output)
    except Exception:
        report("failed", completed, total)
        raise
    report("succeeded", total, total)
    return output

