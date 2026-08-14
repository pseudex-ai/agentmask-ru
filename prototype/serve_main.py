"""Entry point for one Veilgate worker process.

WHY THIS EXISTS INSTEAD OF `uvicorn --workers N`

Real CPU parallelism has to come from processes: pymorphy3 holds the GIL during
morphology, so N threads in one process still serialize on one core. That was
fine while we shipped source, but a Nuitka-compiled binary cannot use uvicorn's
worker manager at all — frozen executables have no working `spawn`/`forkserver`
start method on Unix, and `uvicorn --workers > 1` dies on a vanishing
semaphore tracker (Nuitka #1063, #1581).

So the fan-out moves out of Python entirely. `entrypoint.sh` starts N copies of
this program; each binds its OWN socket to the same port with `SO_REUSEPORT` and
the KERNEL load-balances between them. No multiprocessing, nothing to freeze.

Measured on `python:3.12-slim`: 4 processes, 60 fresh connections -> 18/18/13/11.
NOT reproducible on macOS, where `SO_REUSEPORT` has BSD semantics and every
connection lands on one process — check parallelism in a Linux container.

Distribution is PER CONNECTION, so a caller holding one keep-alive connection
talks to one process. That is not new (uvicorn's own workers share one listening
socket and race on accept the same way); it means the host gateway's pool should
be at least 2N connections.
"""

import os
import socket

import uvicorn


def _listening_socket(port: int, backlog: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # The whole point: several processes may hold the same port and the kernel
    # spreads incoming connections across them.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("0.0.0.0", port))
    sock.listen(backlog)
    return sock


def _serve_ui(log_level: str) -> None:
    """The operator interface, in this same binary under a different role.

    A second Nuitka target would double the compile and add its own copy of the
    Python runtime to the image for what is a few hundred lines of proxy. The
    role switch costs one branch.

    One process, no SO_REUSEPORT: this serves a handful of humans, and the
    engine's parallelism exists for morphology, which the UI never runs. It also
    never leases — importing the UI app does not import the engine, so a UI
    process holds no bundle and cannot be a way to obtain one.
    """
    from veilgate.localui.server import app as ui_app  # noqa: PLC0415 (role-local)

    port = int(os.environ.get("VEILGATE_UI_PORT", "8081"))
    uvicorn.Server(uvicorn.Config(
        ui_app, host="0.0.0.0", port=port, log_level=log_level
    )).run()


def main() -> None:
    # Lowercased: the same variable is read by `logging.basicConfig` in
    # service.py, which wants "INFO", while uvicorn rejects anything but
    # lowercase. One variable, two consumers, so normalize at each of them.
    log_level = os.environ.get("VEILGATE_LOG_LEVEL", "info").lower()
    if os.environ.get("VEILGATE_ROLE", "engine") == "ui":
        _serve_ui(log_level)
        return
    # Imported inside the role, not at module scope: the engine module builds the
    # detector, the audit connection and a licence client at import time, and a
    # UI process has no use for any of them. It also keeps the claim above
    # true — a UI process really does not load the engine.
    from veilgate.service import app  # noqa: PLC0415 (role-local)

    port = int(os.environ.get("VEILGATE_PORT", "8000"))
    backlog = int(os.environ.get("VEILGATE_BACKLOG", "2048"))
    sock = _listening_socket(port, backlog)
    uvicorn.Server(uvicorn.Config(app, fd=sock.fileno(), log_level=log_level)).run()


if __name__ == "__main__":
    main()
