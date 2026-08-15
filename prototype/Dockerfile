# Pseudex PII gateway sidecar — source image.
#
# DEVELOPMENT SHAPE — NEVER SHIP THIS TO A CUSTOMER. It runs the engine from .py
# files, so it hands over the source and every docstring with it. It exists to be
# the parity baseline the release image is compared against (gate P3), and to
# iterate on the gates without paying a Nuitka compile each time.
#
# The release image is Dockerfile.nuitka: same tree, native binary, docstrings
# stripped (docs/tz-license-packaging.md §3.4). Both must pass the same gates.
#
# WHAT IS DELIBERATELY NOT IN HERE: the detection assets. No gazetteers, no
# street vocabulary, no priority table — those are leased at runtime from the
# licensing server and exist only in memory. `licensing/` is not copied either;
# it holds the authored assets and never ships.
#
# Natasha's NER models and pymorphy3's dictionaries DO ship: they are third-party
# open artifacts, not our moat, and leasing them would buy nothing.
#
#   docker build -t pseudex:source .
#
# Pinned to the same Debian release as Dockerfile.nuitka. Parity (gate P3/P4)
# compares this image against the compiled one, so they must differ only in HOW
# the engine is built — not in which libc, OpenSSL or timezone data they carry.
FROM python:3.12-slim-trixie

WORKDIR /app

# setuptools is needed by pymorphy3 dict loading on 3.12+.
RUN pip install --no-cache-dir --upgrade pip setuptools

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pseudex/ ./pseudex/
COPY serve_main.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

# The verification key is BAKED IN at build time, not read from the environment.
# If the customer could point it at a key of their own, they could sign their own
# bundles and the signature would prove nothing. `pseudex/license.py` only falls
# back to the environment when this file is absent, which is a dev checkout.
ARG PSEUDEX_LICENSE_PUBKEY
RUN test -n "$PSEUDEX_LICENSE_PUBKEY" || (echo "PSEUDEX_LICENSE_PUBKEY build-arg is required" && exit 1) \
    && printf 'LICENSE_PUBKEY = "%s"\n' "$PSEUDEX_LICENSE_PUBKEY" > ./pseudex/_release.py

# Fail the build rather than ship assets by accident. Both checks guard the same
# thing from different directions: the gazetteers must not be on the customer's
# disk, and the engine must not be able to reach the package that holds them.
RUN if [ -d ./pseudex/data ]; then echo "pseudex/data must not ship"; exit 1; fi
RUN if grep -rn "^[[:space:]]*\(from\|import\)[[:space:]]\+licensing" ./pseudex/; then \
        echo "pseudex/ must never import licensing/ — that would drag the assets in"; \
        exit 1; \
    fi

# Persistent vault + audit mount point (compose mounts a named volume here).
ENV PSEUDEX_DB_DIR=/data
RUN mkdir -p /data

# Licensing (no defaults for the key — absent means the process must not start):
#   PSEUDEX_LICENSE_KEY   the customer's opaque key
#   PSEUDEX_LICENSE_URL   our licensing server
#   PSEUDEX_LICENSE_CA    custom CA bundle, for a private deployment
#
# High-load tuning:
#   PSEUDEX_WORKERS          worker processes = real CPU parallelism (default: nproc)
#   PSEUDEX_MASK_CONCURRENCY per-worker cap on concurrent morphology passes
#   PSEUDEX_MASK_CACHE_SIZE  bounded LRU of (org,content)->masked entries
# No __pycache__: the engine must not write anything to its own filesystem, so
# that "did the container write a file" is a question with a clean answer (gate
# L5). Bytecode caches would bury a real finding in 80 lines of noise.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PSEUDEX_WORKERS="" \
    PSEUDEX_MASK_CONCURRENCY=8 \
    PSEUDEX_MASK_CACHE_SIZE=20000 \
    PSEUDEX_SERVE_CMD="python serve_main.py"

EXPOSE 8000 8081

CMD ["./entrypoint.sh"]
