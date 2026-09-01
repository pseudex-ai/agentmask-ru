"""Load the detection bundle straight from source, for tests and evals.

Every test and eval in this repo runs the real detector, and the real detector
refuses to work without a leased bundle. Going through the licensing server for a
unit-level script would make the test suite depend on a running service, so these
scripts build the bundle from `licensing/pack.py` and load it directly.

This is a DEVELOPMENT path only. It has no equivalent in the shipped image: the
engine ships with no assets and no way to build them, so nothing here weakens the
lease. The e2e gates deliberately do NOT use this — they run the packaged image
against a real licensing server, which is the only thing that proves the lease
works (docs/tz-license-packaging.md §4.1).
"""

import os
import secrets
import socket
import tempfile
import threading
import time

import httpx

from licensing.pack import build_plaintext
from pseudex.assets import ASSETS



# Учётные данные админки лицензионного сервера.
#
# СТЕНД ВЛАДЕЕТ ОБОИМИ КОНЦАМИ, ПОЭТОМУ САМ И ЧЕКАНИТ ТОКЕН. Раньше он читался
# из окружения, и пусто означало «заголовка нет» — а сервер с тех пор требует
# токен на каждой админской ручке. В CI переменная не задана, поэтому
# `/admin/issue` отвечал 401, ключ не выпускался, и `test_localui.py` падал
# `KeyError: 'key'` — то есть проверка операторской поверхности не выполнялась
# вообще, а сообщение об этом не называло причину.
#
# Здесь генерировать его правильно ровно потому, почему на лицензионном
# сервере — нельзя: там процесс наш и «сгенерировали и написали в лог» означает
# «витрина не подключится, а кто читает логи — войдёт». Тут оба конца в одном
# процессе и живут секунды.
ADMIN_TOKEN = (os.environ.get("PSEUDEX_LICENSE_ADMIN_TOKEN")
               or "testkit-" + secrets.token_urlsafe(16))
os.environ["PSEUDEX_LICENSE_ADMIN_TOKEN"] = ADMIN_TOKEN
ADMIN_AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

def load_dev_bundle() -> None:
    """Make the detector usable in-process. Idempotent."""
    if not ASSETS.is_loaded:
        ASSETS.load(build_plaintext())


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_local_license() -> str:
    """Run the REAL licensing server in a thread and point the engine at it.

    `test_perf_masking.py` drives `service.app` through an ASGI transport, which
    does not run the lifespan — so nothing would ever acquire a lease and every
    /mask would answer 503. Rather than teach the app a test-only bypass (which
    would be a hole in the very thing the licence is for), the test gets a real
    server on a loopback port.

    MUST be called BEFORE importing `pseudex.service` or `licensing.server`:
    both read their configuration from the environment at import time.

    Returns the issued key."""
    port, admin_port = _free_port(), _free_port()
    database = os.path.join(tempfile.mkdtemp(prefix="pseudex-license-"), "license.db")
    os.environ["PSEUDEX_LICENSE_DB"] = database
    os.environ.setdefault("PSEUDEX_LEASE_TTL_SECONDS", "3600")
    os.environ.setdefault("PSEUDEX_GRACE_SECONDS", "3600")

    # Imported here, not at module top, and that is load-bearing: both modules
    # read their configuration from the environment at IMPORT time, and the
    # environment is only complete a few lines above.
    import uvicorn  # noqa: PLC0415

    from licensing import server  # noqa: PLC0415

    for app, app_port in ((server.app, port), (server.admin_app, admin_port)):
        instance = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=app_port,
                                                 log_level="error"))
        threading.Thread(target=instance.run, daemon=True).start()

    admin = f"http://127.0.0.1:{admin_port}"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            httpx.get(f"{admin}/admin/list", timeout=2, headers=ADMIN_AUTH)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        raise RuntimeError("local licensing server did not start")

    issued = httpx.post(f"{admin}/admin/issue", json={"org_id": "testkit"},
                        timeout=10, headers=ADMIN_AUTH)
    if issued.status_code != 200 or "key" not in issued.json():
        # Своими словами, а не `KeyError: 'key'` двадцатью строками ниже.
        raise RuntimeError(
            f"local licensing server refused to issue a key: "
            f"{issued.status_code} {issued.text[:200]}")
    key = issued.json()["key"]
    os.environ["PSEUDEX_LICENSE_URL"] = f"http://127.0.0.1:{port}"
    os.environ["PSEUDEX_LICENSE_KEY"] = key
    os.environ["PSEUDEX_LICENSE_PUBKEY"] = server.PUBLIC_KEY
    return key
