# CPU local staging only; registry index digests resolved November 15, 2026.
FROM --platform=linux/amd64 node:22-bookworm-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee AS studio
WORKDIR /app/apps/studio
COPY apps/studio/package.json apps/studio/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/studio/ ./
COPY contracts /app/contracts
COPY fixtures /app/fixtures
RUN npm run build

FROM --platform=linux/amd64 mwader/static-ffmpeg:7.1@sha256:a8090df5f5608daef387e1b2e93b98aaacb4d92153ad904e7d715c725724fca4 AS ffmpeg
FROM --platform=linux/amd64 python:3.11-slim-bookworm@sha256:a83ba18aef0f865b1a4a611c2cf460fe446f2795673bbb9fe43be570439e3b39
WORKDIR /app
COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /ffprobe /usr/local/bin/ffprobe
COPY deployment/requirements.lock /app/deployment/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r deployment/requirements.lock
COPY contracts /app/contracts
COPY fixtures /app/fixtures
COPY scripts/validate_contract.py /app/scripts/validate_contract.py
COPY services/controller /app/services/controller
COPY src/wan_platform/*.py /app/src/wan_platform/
COPY workers/gpu/*.py workers/gpu/model.lock.json /app/workers/gpu/
COPY workers/media/*.py /app/workers/media/
COPY deployment/local_stage.py deployment/healthcheck.py /app/deployment/
COPY --from=studio /app/apps/studio/dist /app/apps/studio/dist
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WAN_STUDIO_ORIGIN=http://127.0.0.1:8080
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=6s --start-period=15s --retries=3 CMD ["python", "deployment/healthcheck.py"]
ENTRYPOINT ["python", "-m", "deployment.local_stage", "--container", "--state", "/data", "--static", "/app/apps/studio/dist", "--port", "8080"]
