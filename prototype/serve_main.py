"""Entry point for one Obscura worker process.

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

from obscura.service import app


def _listening_socket(port: int, backlog: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # The whole point: several processes may hold the same port and the kernel
    # spreads incoming connections across them.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("0.0.0.0", port))
    sock.listen(backlog)
    return sock


def main() -> None:
    port = int(os.environ.get("OBSCURA_PORT", "8000"))
    backlog = int(os.environ.get("OBSCURA_BACKLOG", "2048"))
    sock = _listening_socket(port, backlog)
    # Lowercased: the same variable is read by `logging.basicConfig` in
    # service.py, which wants "INFO", while uvicorn rejects anything but
    # lowercase. One variable, two consumers, so normalize at each of them.
    log_level = os.environ.get("OBSCURA_LOG_LEVEL", "info").lower()
    uvicorn.Server(uvicorn.Config(app, fd=sock.fileno(), log_level=log_level)).run()


if __name__ == "__main__":
    main()
