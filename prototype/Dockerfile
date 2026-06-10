# Obscura PII gateway sidecar.
# Builds the /mask + /unmask service used by the Diva LiteLLM callback.
# Natasha's NER models (navec/slovnet) ship INSIDE the pip package, so no
# separate model download is needed — the image is self-contained + offline.
#
#   docker build -t obscura:latest .
#
FROM python:3.12-slim

WORKDIR /app

# setuptools is needed by pymorphy3 dict loading on 3.12+.
RUN pip install --no-cache-dir --upgrade pip setuptools

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY obscura/ ./obscura/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Persistent vault + audit mount point (compose mounts a named volume here).
ENV OBSCURA_DB_DIR=/data
RUN mkdir -p /data

# High-load tuning (all overridable at runtime):
#   OBSCURA_WORKERS         uvicorn worker processes = real CPU parallelism
#                           (pymorphy3 holds the GIL -> processes, not threads).
#                           Default = CPU count. ~300 MB RAM per worker, so size
#                           against the container memory limit (N*300 MB).
#   OBSCURA_MASK_CONCURRENCY per-worker cap on concurrent morphology passes
#                           (backpressure: bursts queue, don't thrash the core).
#   OBSCURA_MASK_CACHE_SIZE  bounded LRU of (org,content)->masked entries.
# The persistent SQLite Vault + audit (mounted volume) are shared across all
# workers, so tokens stay consistent + reversible regardless of worker count.
ENV OBSCURA_WORKERS="" \
    OBSCURA_MASK_CONCURRENCY=8 \
    OBSCURA_MASK_CACHE_SIZE=20000

EXPOSE 8000

# Detection runs OFF the event loop (anyio.to_thread) so /health stays responsive
# while a mask is in flight; multiple workers give real CPU parallelism.
CMD ["./entrypoint.sh"]
