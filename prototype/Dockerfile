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

# Persistent vault + audit mount point (compose mounts a named volume here).
ENV OBSCURA_DB_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

# Single worker keeps the in-process vault cache coherent; scale via the
# persistent SQLite vault + more replicas if ever needed.
CMD ["uvicorn", "obscura.service:app", "--host", "0.0.0.0", "--port", "8000"]
