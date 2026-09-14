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
# Attribution for the CC BY-SA 3.0 dictionary data. Shipping it is the
# obligation the licence actually imposes — see the file for why it does
# not make the product itself share-alike.
COPY THIRD-PARTY-NOTICES.md .
RUN pip install --no-cache-dir -r requirements.txt

COPY pseudex/ ./pseudex/
COPY serve_main.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Compile the authored TUNING into the engine (docs/tz-license-packaging §2.2).
# The cue words, address regex, priority table and look-alike folds no longer
# travel in the lease — a client used to read them by decrypting their own
# bundle — so they are baked in here as an opaque blob. Needs ONLY assets_source
# (no bulk dictionaries, no ГАР dump), so three files go to a temporary path, get
# used, and are removed: `licensing/` itself must never ship. The generated
# module holds only `BLOB`/`VERSION`, so the "no import licensing" check below
# still passes.
# PSEUDEX_TUNING_KEY seals the blob (docs/tz-license-packaging §2.2, anti-patch
# tie). The SAME key must reach the licensing server, which delivers it in every
# lease so the engine can open its own tuning.
#
# A SECRET MOUNT, NOT A BUILD-ARG — and this single-stage image is the reason
# (Dockerfile.nuitka has the long version). An `ARG` lands in the metadata of
# every later layer, and `docker history pseudex:source` printed the production
# key seven times. `required=true` replaces the old `test -n` guard.
COPY licensing/__init__.py licensing/assets_source.py licensing/pack.py /tmp/lic/licensing/
#
# THE FINGERPRINT IS THE CACHE KEY. BuildKit leaves secret contents out of the
# layer cache on purpose, so a rotated key alone would hit the cache and ship
# a blob sealed to the PREVIOUS key (measured: two keys, one blob). Sixteen hex
# characters of the key's SHA-256 enter as an ordinary ARG — not the key — and
# the RUN recomputes them from the mounted secret: a stale or invented id
# stops the build instead of quietly reusing the cache.
ARG PSEUDEX_TUNING_KEY_ID
RUN --mount=type=secret,id=pseudex_tuning_key,required=true \
       test -n "$PSEUDEX_TUNING_KEY_ID" || (echo "PSEUDEX_TUNING_KEY_ID build-arg is required" && exit 1) \
    && [ "$(sha256sum /run/secrets/pseudex_tuning_key | cut -c1-16)" = "$PSEUDEX_TUNING_KEY_ID" ] \
       || (echo "PSEUDEX_TUNING_KEY_ID does not match the mounted key" && exit 1) \
    && PSEUDEX_TUNING_KEY="$(cat /run/secrets/pseudex_tuning_key)" PYTHONPATH=/tmp/lic \
       python -m licensing.pack --emit-tuning ./pseudex/_tuning_blob.py \
    && rm -rf /tmp/lic

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
RUN if grep -rn "^[[:space:]]*\(from\|import\)[[:space:]]\+sqlite3" ./pseudex/; then \
        echo "pseudex/ must reach SQLite only through sqlite_setup: stdlib sqlite3"; \
        echo "accepts PRAGMA key WITHOUT raising and writes plain text, so any"; \
        echo "import of it here is a product that claims encryption and has none"; \
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
# Stated here too, and not left to the base image, so the two images agree about
# it: the release runtime has no locale at all and needed this to print a Russian
# sentence. Parity gates compare behaviour, and behaviour includes the log.
ENV LANG=C.UTF-8 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PSEUDEX_WORKERS="" \
    PSEUDEX_MASK_CONCURRENCY=8 \
    PSEUDEX_MASK_CACHE_SIZE=20000 \
    PSEUDEX_SERVE_CMD="python serve_main.py"

EXPOSE 8000 8081

CMD ["./entrypoint.sh"]
