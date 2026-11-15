# Architecture baseline
Version 0.1.0 | November 15, 2026

The studio manages projects, storyboards, approved references, takes and timelines. The backend owns authorization, durable metadata, budget reservations and the job queue. GPU workers claim attempts and write durable assets. CPU media workers assemble a captured timeline revision. The lifecycle controller and an independent cleanup watchdog run outside the GPU they manage.

## Implementation defaults

Use a monorepo. Reserve `apps/studio/` for a React/TypeScript interface, `services/api/` and `services/controller/` for Python services, `workers/gpu/` for Wan inference, and `workers/media/` for FFmpeg export. These are implementation choices for B01–B04. The B00 package itself uses Python and JSON Schema and supplies a process-local provider fake.

Target PostgreSQL for durable project/job metadata and an S3-compatible object-store interface for assets. B02 may develop with a local database and filesystem adapter. The hosted vendors, authentication provider, deployment target and asset retention period remain undecided. Choose them before staging or uploading owner media. The cost controller must use transactional reservations and a durable queue/outbox or equivalent so retries cannot double-submit batches.

The starting inference candidate is Wan2.2 TI2V-5B on one 24 GB RTX 4090. B01 must pin the actual upstream revision, checkpoint revision, checksums, license notices and runtime image before a real benchmark. The fixture model profile only generates deterministic test media. Keep model downloads and upstream weight licenses separate from application source ownership.

## Render and cleanup

A short transaction admits an immutable batch snapshot and reserves its cost ceiling. A controller claims provisioning with a lease and unique launch key, creates a Pod, then reconciles by recorded provider ID or launch tag if the response is ambiguous. Inventory uncertainty pauses a retry. Never hold a database transaction open while waiting for the provider.

Workers receive attempt-scoped access to inputs and output paths. Lease expiry fences old workers. Upload completion must verify object size, checksum and ownership before accepting a take. A duplicate completion with the same manifest returns the existing take. Conflicting content returns a conflict. New creative takes receive new attempt IDs.

Cancellation stops future claims, fences obsolete attempts and requests cleanup. Runtime, batch budget, account concurrency and shutdown reserve bound new launches. A pricing estimate is not a provider-enforced spending ceiling. B06 must measure billing lag and teardown latency and disclose any unavoidable overshoot envelope.

Deletion is confirmed by a successful inventory/get response establishing absence. A provider error or timeout leaves cleanup pending or failed. An independent scheduled watchdog retries cleanup and alerts the owner. A failed render can still have confirmed cleanup and a successful render can still need cleanup.

## Persistence and privacy

Derive identity from authenticated server context. Resolve project membership before processing IDs. Keep signed asset URLs short-lived, write paths scoped, credentials server-side and logs redacted. Backend validates approved storage locations before workers read remote assets. Test ownership boundaries with fictional owners.

Model cache retention trades idle storage cost against cold-start download time. Keep it optional and decide from measured use. Back up database and assets and verify recovery before production. A finished 30-minute timeline built from fixtures verifies duration support. Creative continuity needs live-owner acceptance on generated footage.
