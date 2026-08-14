"""Run the licensing server locally, exactly as it runs in production.

Two ASGI apps on two ports, so the admin surface is not merely unrouted but
unreachable from the public one.

    python3 -m licensing.devserver            # public :8443, admin :9443

Used by the e2e stand and by `test_perf_masking.py`. It starts the REAL
`licensing/server.py`; there is no test double anywhere in this repo, because a
stand that runs different code proves nothing about the code that ships
(docs/tz-license-packaging.md §4.1).
"""

import os
import threading

import uvicorn

from licensing import server


def serve(app: object, port: int, certfile: str, keyfile: str) -> uvicorn.Server:
    config = uvicorn.Config(
        app, host="0.0.0.0", port=port, log_level="info",
        ssl_certfile=certfile or None, ssl_keyfile=keyfile or None,
    )
    return uvicorn.Server(config)


def main() -> None:
    certfile = os.environ.get("VEILGATE_LICENSE_CERT", "")
    keyfile = os.environ.get("VEILGATE_LICENSE_KEYFILE", "")
    public_port = int(os.environ.get("VEILGATE_LICENSE_PORT", "8443"))
    admin_port = int(os.environ.get("VEILGATE_LICENSE_ADMIN_PORT", "9443"))

    # Admin is plain HTTP on a separate port: it is reachable only from inside
    # the deployment network and never published.
    admin = serve(server.admin_app, admin_port, "", "")
    threading.Thread(target=admin.run, name="licensing-admin", daemon=True).start()
    serve(server.app, public_port, certfile, keyfile).run()


if __name__ == "__main__":
    main()
