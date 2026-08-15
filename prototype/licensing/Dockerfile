# Pseudex licensing server — the only component that runs on OUR hardware.
#
# It holds what the sidecar image does not: the authored detection assets and the
# Ed25519 signing key. It never receives personal data; the traffic is a key, a
# process public key, and aggregate counters.
#
# Build context is `prototype/`, because the server shares pseudex/bundle.py and
# pseudex/sqlite_setup.py with the engine — one format, one implementation:
#
#   docker build -f licensing/Dockerfile -t pseudex-licensing:latest .
#
FROM python:3.12-slim-trixie

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools

# Only what the server needs. Notably NOT natasha/pymorphy3: the licensing server
# packs assets, it does not detect anything.
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" pyrage cryptography

# The engine modules the server genuinely shares (bundle format, sqlite setup),
# plus the licensing package with the assets themselves.
COPY pseudex/__init__.py pseudex/bundle.py pseudex/sqlite_setup.py pseudex/profiling.py ./pseudex/
COPY licensing/ ./licensing/

ENV PSEUDEX_LICENSE_DB=/data/license.db \
    PSEUDEX_LEASE_TTL_SECONDS=86400 \
    PSEUDEX_GRACE_SECONDS=172800 \
    PSEUDEX_LICENSE_PORT=8443 \
    PSEUDEX_LICENSE_ADMIN_PORT=9443
RUN mkdir -p /data

EXPOSE 8443 9443

CMD ["python", "-m", "licensing.devserver"]
