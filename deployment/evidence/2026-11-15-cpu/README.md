# Actual CPU cloud verification evidence

Source commit: `18bbdfdcbe266d11db48b6f21cfa9441775cf5c3`.
Run: https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43772264998
Artifact 14184507441, ZIP SHA-256 `7867dec60b9b444f2d91b5ce73c0e4fd7cd42ab1677926ba282a573085c01b18`.

Downloaded original evidence passed context/helper, command log, image identity
and fixture byte/checksum checks. The originals here retain runner paths; they
are historical build evidence and are not installed launch authority. The image
was not published and no longer exists after runner teardown.

To reconstruct the small original context, check out the source commit and copy
its manifest-listed files into `context/`, plus `deployment/container_smoke.py`
as `container_smoke.py`. Restore `fixture-result.json` as `fixture/result.json`
and decode `fixture.mp4.base64` to the exact object key in that result. Preserve
all bytes. Hashes in the manifest must match. Absolute argv paths must not be
rewritten to manufacture hosted acceptance.

CUDA inference, model bytes and hosted deployment remain unverified. The video
is the worker's synthetic two-second fixture, not Wan output or user content.
