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
# sqlcipher3 is here even though this server's own store is NOT encrypted (see
# below): `pseudex/sqlite_setup.py` has ONE driver and no import branch, which
# is the property that stops a build from silently degrading to stdlib sqlite3
# and writing plain text. The cost of that guarantee is this line.
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" pyrage cryptography sqlcipher3

# The engine modules the server genuinely shares (bundle format, sqlite setup),
# plus the licensing package with the assets themselves.
#
# СПИСОК ПОИМЁННЫЙ, ПОЭТОМУ НОВЫЙ ИМПОРТ ЛОМАЕТ ОБРАЗ, А НЕ ТЕСТЫ. `metrics.py`
# приехал сюда вместе со скрейпом: без него `licensing/server.py` падает на
# импорте, то есть боевой контейнер лицензий НЕ СТАРТУЕТ — а это единственный
# отказ, после которого весь флот начинает жечь grace. В репозитории и в тестах
# файл лежит рядом и импортируется, поэтому увидеть это можно было только
# собрав образ.
COPY pseudex/__init__.py pseudex/bundle.py pseudex/sqlite_setup.py \
     pseudex/vault_key.py pseudex/vault_migrate.py pseudex/profiling.py \
     pseudex/metrics.py ./pseudex/
COPY licensing/ ./licensing/

# THIS SERVER'S OWN DATABASE STAYS IN PLAIN TEXT, and that is a decision rather
# than an omission. It holds no personal data — customer keys are stored as
# unsalted SHA-256 and the rest is org ids, plans and counters — while encrypting
# it would break the two things that guard the one database nobody can rebuild
# from code: `deploy/backup.sh` uses the host's `sqlite3 .backup`, which cannot
# open a SQLCipher file and would silently fall back to `cp` of a live WAL
# database (a torn page that restores as a file which opens and is wrong), and
# `deploy/restore-drill.sh` counts rows in the copy every week — against an
# encrypted file it would raise a false catastrophe alarm every Sunday.
#
# Trading zero personal data against the availability of every deployment in the
# field is not a close call. Set PSEUDEX_VAULT_ENCRYPTION=auto here only together
# with SQLCipher tooling in both of those scripts.
ENV PSEUDEX_VAULT_ENCRYPTION=off \
    PSEUDEX_LICENSE_DB=/data/license.db \
    PSEUDEX_LEASE_TTL_SECONDS=86400 \
    PSEUDEX_GRACE_SECONDS=172800 \
    PSEUDEX_LICENSE_PORT=8443 \
    PSEUDEX_LICENSE_ADMIN_PORT=9443
RUN mkdir -p /data

EXPOSE 8443 9443

CMD ["python", "-m", "licensing.devserver"]
