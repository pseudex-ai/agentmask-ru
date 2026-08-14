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
import socket
import tempfile
import threading
import time

import httpx

from licensing.pack import build_plaintext
from obscura.assets import ASSETS


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

    MUST be called BEFORE importing `obscura.service` or `licensing.server`:
    both read their configuration from the environment at import time.

    Returns the issued key."""
    port, admin_port = _free_port(), _free_port()
    database = os.path.join(tempfile.mkdtemp(prefix="obscura-license-"), "license.db")
    os.environ["OBSCURA_LICENSE_DB"] = database
    os.environ.setdefault("OBSCURA_LEASE_TTL_SECONDS", "3600")
    os.environ.setdefault("OBSCURA_GRACE_SECONDS", "3600")

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
            httpx.get(f"{admin}/admin/list", timeout=2)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        raise RuntimeError("local licensing server did not start")

    key = httpx.post(f"{admin}/admin/issue", json={"org_id": "testkit"}, timeout=10).json()["key"]
    os.environ["OBSCURA_LICENSE_URL"] = f"http://127.0.0.1:{port}"
    os.environ["OBSCURA_LICENSE_KEY"] = key
    os.environ["OBSCURA_LICENSE_PUBKEY"] = server.PUBLIC_KEY
    return key
