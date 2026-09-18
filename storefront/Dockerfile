# The storefront. Runs on OUR infrastructure, never in a customer's contour.
#
# Nothing from prototype/ is copied in, and that is enforced by the build
# context being this directory: the engine must not depend on the shop, and the
# shop must never become a route by which personal data could reach us.

FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=pseudex_site.settings

WORKDIR /app

# ОБНОВЛЕНИЕ ПАКЕТОВ БАЗОВОГО ОБРАЗА, А НЕ ТОЛЬКО УСТАНОВКА СВОИХ.
# `python:3.12-slim-trixie` фиксирует срез Debian на день сборки тега,
# поэтому perl-base в нём остаётся прежним, пока образ не пересоберут.
# Сканер нашёл в нём три исправимых CRITICAL (5.40.1-6 → +deb13u1) —
# правится ровно этой строкой.
RUN apt-get update && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collected at BUILD time, not on start: a container that rewrites its own
# static files on every boot is a container whose start can fail on a read-only
# filesystem, and whose first request after a deploy waits for it.
#
# The manifest storage hashes filenames, and a missing SECRET_KEY would abort
# the settings import, so a throwaway one is supplied for this step alone. It
# never reaches a running process — the real one comes from the environment.
RUN PSEUDEX_SECRET_KEY=build-time-only PSEUDEX_DEBUG=0 \
    PSEUDEX_ALLOWED_HOSTS=build \
    python manage.py collectstatic --noinput

# Non-root, and the whole tree stays owned by root: the process may read its own
# code but not rewrite it.
RUN useradd --system --uid 10001 pseudex \
    && mkdir -p /data && chown pseudex:pseudex /data
USER pseudex

EXPOSE 8000

# The check hits the app's own liveness route, which deliberately does not touch
# the licensing server: folding that dependency in would make an outage there
# restart a healthy web container and turn one failure into two.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# Threads, not processes: this app is I/O-bound (Postgres and one HTTP call to
# the licensing server) and holds no model. Workers stay at 2 so a single
# container survives one wedged request.
CMD ["gunicorn", "pseudex_site.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", "--threads", "4", \
     "--timeout", "30", "--graceful-timeout", "30", \
     "--access-logfile", "-", "--error-logfile", "-"]
