# Private worker rebuild — November 16, 2026

Run [43808492420](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/43808492420) succeeded from source `0f94a1754d03818c04f4376c905a735fd45fa033` (PR #64). Artifact 14199557380 was downloaded and independently reviewed before its one-day expiry. Its ZIP checksum is in `review.json`.

Private image: `ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:f724b9f32ac4ac780702072fd32e9d08254524ca81afd6aadeb87169904f993b`.

Actual Linux amd64 build, runtime imports and synthetic video smoke passed. All source/context and four command-log checksums match; downloaded synthetic H.264 media fully decodes. The offline build-consistency verifier passed, including the registry manifest/config binding to the tested image. Anonymous access was denied and authenticated manifest access passed. Registry visibility remained private. No model weights are embedded.

Worker source inventory is unchanged by controller-only PRs #65/#66 and matches the current checkout. The image contains terminal failure journaling, bounded safe failure categories and inference stage markers. These improve diagnosis and prevent repeat rendering after a recorded terminal failure; they do not establish the cause of the earlier failed render.

This new digest has NOT been downloaded by Runpod or exercised on a real GPU. No second paid attempt was made. The earlier digest's successful pull and automatic deadline shutdown remain separate evidence.

For reconstruction, copy each `manifest.json` source from the source commit to `context/`, its `deployment/container_smoke.py` to `container_smoke.py`, and `fixture-result.json` to `fixture/result.json`. Decode `fixture.mp4.base64` to the recorded asset object key. Preserve original logs/argv and validate their hashes; do not execute logged commands. Separate publication records bind the post-build digest without modifying earlier Docker inspection records.
