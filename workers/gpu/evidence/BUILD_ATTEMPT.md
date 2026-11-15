# Local container build investigation

November 15, 2026. Issue #2 and draft PR #16. Implementation head at investigation start was `5bd099a02ce33f41ce0c855e0281d255fce62fc1`.

Docker and Podman remain unavailable. A rootless build was attempted using an upstream BuildKit binary in temporary tooling. No application code or runtime pins changed.

## Verified tooling

[Official BuildKit 0.35.0 Linux amd64 archive](https://github.com/moby/buildkit/releases/download/v0.35.0/buildkit-v0.35.0.linux-amd64.tar.gz)

SHA-256 `37b3befbed28fb72a44d72bf42362c268610386c42feafa27cb45ee0b531369c` matched the digest published in the upstream GitHub release. The archive was extracted locally after verification.

## Commands and observed results

`unshare -Ur true` succeeded. A rootless overlay mount on the workspace filesystem failed because that filesystem does not support the overlay upper directory. The BuildKit daemon was therefore tried with its native snapshotter.

The initial daemon command was executed with the following local paths.

```sh
unshare -Urmpf --mount-proc \
  /workspace/scratch/70f65dc23330/build-tools/bin/buildkitd \
  --root /workspace/scratch/70f65dc23330/build-tools/state \
  --addr unix:///workspace/scratch/70f65dc23330/build-tools/buildkit.sock \
  --oci-worker-snapshotter native \
  --oci-worker-binary /workspace/scratch/70f65dc23330/build-tools/bin/buildkit-runc \
  --containerd-worker=false
```

It exited with status 1 and reported the following error.

```text
failed to create unix socket on /workspace/scratch/70f65dc23330/build-tools/buildkit.sock
socket: operation not permitted
```

A supported loopback TCP listener was then tried using the same command with `--addr tcp://127.0.0.1:18234`. The daemon reached initialization and exited with status 1 on its internal socket.

```text
failed to create unix socket on /run/buildkit/otel-grpc.sock
socket: operation not permitted
creating trace controller listener
```

## Acceptance status

The daemon never became ready to accept a build. No `buildctl build`, image export, container fixture check, CUDA inference or paid resource operation ran. There is no built image digest to report. Both daemon processes exited. Infrastructure spending for this investigation was $0.

The next build host needs a working container daemon or rootless BuildKit with its required filesystem and Unix socket support. Run the exact build and container fixture commands in `workers/gpu/README.md`, record the final image digest and retain the build log. Actual GPU inference remains in B06 after the budget and runtime envelope are approved. The established B00 and worker test evidence totals 31 passing tests and was preserved during this documentation-only follow-up.
