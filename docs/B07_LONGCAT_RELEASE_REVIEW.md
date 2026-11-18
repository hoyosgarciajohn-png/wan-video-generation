# LongCat deployment review

GitHub Actions runs again. Read-only host verification run 44238678234 attempt 2 passed and freshly observed the expected d0543ae baseline. The prior billing failure is historical, not the current blocker.

PR #98 was marked ready and merged after current-head run 44239805091 attempt 2 passed at f23cf48be02bf7a2be9757417524d435dd4e6cf9. Evidence: 227 root tests (one expected non-root skip), 15 queue/media tests, 4 publication boundary tests, 18 Studio tests, contract/compilation checks and an actual production Dockerfile build with offline bootstrap/client imports. The service-account permission test then passed on the real root-run deployment host. Slow dependency downloads accounted for most CI elapsed time; this was not video-generation latency.

Merged and installed source: `9277e14a7d21a4f8bb142c50943fd3f8a1bfce4b`. Controller upgrade [run 44242624619](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/44242624619) passed. The server reports this exact installed SHA; controller, cleanup and proxy services are active and enabled; SQLite integrity and quiescence/provider-absence gates passed; external HTTPS is ready with paid_dispatch=false. The historical unresolved request 249c50635ec84ac38cef0eb66232efed and all financial liabilities were preserved. Cleanup service activity is not a claim that this old uncertain ledger entry is resolved.

Private runtime publication [run 44243001014](https://github.com/hoyosgarciajohn-png/wan-video-generation/actions/runs/44243001014) passed at the same merged source. The actual build/import, private package visibility, authenticated registry manifest/config binding and anonymous-access denial passed. Immutable image: `ghcr.io/hoyosgarciajohn-png/wan-video-generation-gpu@sha256:7ba22cca295fd8290b1df14a349b0e5ee9a2bb46b22af424dc17ade69f23dcf7`. A Runpod pull and GPU execution of this production batch image remain UNVERIFIED; no GPU was allocated here. Runtime policy 1.2.0 (new music project cap 363000 ms) is included in the exact deployed source; existing lower project limits stay binding. Contract remains 0.1.0.

The approved 362.880-second original master, 18 head-covered scene images, all 110 timing-v2 conditioning WAVs and complete labeled still-image preview are unchanged. Preparation fingerprint remains fdc40bdca1da7e4fd8b45d52bcd3de2a8fc3d620f9469d1a1f4c6cb4c11f29a7. Owner playback acceptance and verified lyric phrasing remain open. This deployment is not full-video rendering or proof of 110 distinct camera angles, lip sync, sports physics or crowd choreography.

Next: bind the reviewed package to a real new production project and recompute its fingerprint; reconcile the retained cumulative budget, install/attest the independent exact-name guard and bind current capped private admission to the actual source/image/input identities. Preserve the existing $20/four-hour cumulative envelope and all consumed scopes; historical posted $8.156768710002916 is not a refreshed balance. No new allowance, Pod, payment or model inference was started by this recheck. Full-video rendering has not started.

Live controller: https://wan-64-225-114-46.sslip.io

