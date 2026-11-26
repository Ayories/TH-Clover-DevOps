# Pinned by tag and digest (checked against Docker Hub on 2026-11-26).
FROM python:3.12.16-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b

# CI passes the Git commit: docker build --build-arg REVISION=<40-character SHA>
ARG REVISION=unknown
LABEL org.opencontainers.image.title="th-clover-customer-service" \
      org.opencontainers.image.description="Evolving Ltd customer-service app (CMP6237 proof of concept)" \
      org.opencontainers.image.source="https://github.com/Ayories/TH-Clover-DevOps" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.base.name="docker.io/library/python:3.12.16-slim-trixie"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /service
# The pinned base image ships a libzstd1 with a fixed HIGH vulnerability (CVE-2026-124851),
# found by the Trivy gate. Upgrade only that package; drop this once the base image has the fix.
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade libzstd1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --uid 10001 --user-group --no-create-home appuser

# pip is not needed at run time, so remove it to shrink the attack surface.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && pip uninstall -y pip

# Application files stay owned by root, so the app user cannot change them.
COPY app/ ./app/

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

# One worker with threads: the Prometheus counter lives in process memory.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--worker-class", "gthread", \
     "--threads", "8", "--worker-tmp-dir", "/dev/shm", "--no-control-socket", "app.main:app"]
