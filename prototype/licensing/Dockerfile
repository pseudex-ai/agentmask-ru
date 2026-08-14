# Obscura licensing server — the only component that runs on OUR hardware.
#
# It holds what the sidecar image does not: the authored detection assets and the
# Ed25519 signing key. It never receives personal data; the traffic is a key, a
# process public key, and aggregate counters.
#
# Build context is `prototype/`, because the server shares obscura/bundle.py and
# obscura/sqlite_setup.py with the engine — one format, one implementation:
#
#   docker build -f licensing/Dockerfile -t obscura-licensing:latest .
#
FROM python:3.12-slim-trixie

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools

# Only what the server needs. Notably NOT natasha/pymorphy3: the licensing server
# packs assets, it does not detect anything.
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" pyrage cryptography

# The engine modules the server genuinely shares (bundle format, sqlite setup),
# plus the licensing package with the assets themselves.
COPY obscura/__init__.py obscura/bundle.py obscura/sqlite_setup.py obscura/profiling.py ./obscura/
COPY licensing/ ./licensing/

ENV OBSCURA_LICENSE_DB=/data/license.db \
    OBSCURA_LEASE_TTL_SECONDS=86400 \
    OBSCURA_GRACE_SECONDS=172800 \
    OBSCURA_LICENSE_PORT=8443 \
    OBSCURA_LICENSE_ADMIN_PORT=9443
RUN mkdir -p /data

EXPOSE 8443 9443

CMD ["python", "-m", "licensing.devserver"]
