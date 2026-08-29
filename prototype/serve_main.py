"""Entry point for one Pseudex worker process.

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
import sys

import uvicorn

from pseudex import sqlite_setup, vault_key, vault_migrate

# The three stores of one data directory. Named here rather than derived from
# whichever role is running, because the probe and the decrypt role must cover
# the file the operator is missing even when THIS process would never open it —
# a sidecar deployment has no `tenants.db` and a proxy one has no reason to look
# at it either, and "we did not look" is the least useful answer to "which file
# will not open".
_STORES = (
    ("vault.db", sqlite_setup.VAULT_STORE),
    ("audit.db", sqlite_setup.AUDIT_STORE),
    ("tenants.db", sqlite_setup.TENANTS_STORE),
)


def _data_dir() -> str:
    return os.environ.get("PSEUDEX_DB_DIR", ".")


def _probe() -> int:
    """Report which files open with the configured key, and which do not.

    This role exists because SQLCipher gives ONE answer — `file is not a
    database` — to a wrong key, to a corrupt file and to an unencrypted
    database. An operator staring at that sentence cannot tell a typo in a KMS
    path from a half-finished migration. The header separates encrypted from
    plaintext, and an actual open separates the right key from the wrong one;
    printing both for every file turns three indistinguishable failures into
    three different ones.

    It opens read-only and migrates nothing: a diagnostic that changes the thing
    it is diagnosing is not one.
    """
    directory = _data_dir()
    print(f"pseudex probe: {os.path.abspath(directory)}")
    state = vault_key.state(directory)
    print(f"  шифрование: {'включено' if state['encrypted'] else 'выключено'}"
          f"   ключ: {state['key_source']}")
    if state.get("key_beside_data"):
        print("  ВНИМАНИЕ: ключ лежит рядом с данными — кража тома забирает и его")
    # A KEY THAT DOES NOT RESOLVE IS A FAILURE ON ITS OWN, before any file is
    # looked at. On a FRESH volume there is nothing to fail to open, so counting
    # only unopenable files reported success for
    # PSEUDEX_VAULT_ENCRYPTION=required with no key — and `entrypoint.sh` went on
    # to start ten workers, print the gateway token, and only then take the
    # container down as each worker died of the same thing, ten screens below
    # the sentence that explained it.
    failures = 1 if state.get("error") else 0
    if state.get("error"):
        print(f"  ключ не разрешён: {state['error']}")
    for filename, store in _STORES:
        record = sqlite_setup.describe(os.path.join(directory, filename), store)
        if record["state"] == vault_migrate.MISSING:
            print(f"  {filename:<12} нет файла")
            continue
        verdict = "открывается" if record["opens"] else "НЕ ОТКРЫВАЕТСЯ"
        detail = f"  {record['error']}" if record["error"] else ""
        print(f"  {filename:<12} {record['state']:<9} {verdict}{detail}")
        if not record["opens"]:
            failures += 1
    # Non-zero when something cannot be opened, so this is usable from a script
    # and from a healthcheck, not only by eye.
    return 1 if failures else 0


def _decrypt() -> int:
    """Write the stores back out in plain text. The door is not one-way.

    Deliberately its own role rather than a flag on the engine: it produces
    exactly what the rest of the product exists to prevent, so it has to be an
    act somebody performed, visible in the command that started the container.
    """
    directory = _data_dir()
    secret = vault_key.resolve(directory)
    if secret is None:
        print("pseudex decrypt: PSEUDEX_VAULT_ENCRYPTION=off — нечего расшифровывать",
              file=sys.stderr)
        return 1
    print(f"pseudex decrypt: {os.path.abspath(directory)} — результат ляжет на "
          f"диск ОТКРЫТЫМ ТЕКСТОМ")
    failures = 0
    for filename, store in _STORES:
        path = os.path.join(directory, filename)
        # Every file is attempted and every verdict printed. Stopping at the
        # first refusal would hide that the other two converted — and an operator
        # exporting their data before leaving needs to know exactly which files
        # they now hold, not that the command "failed".
        try:
            print(f"  {filename:<12} "
                  f"{vault_migrate.decrypt_store(path, secret.store_key(store))}")
        except vault_migrate.VaultMigrationError as error:
            print(f"  {filename:<12} ОТКАЗ  {error}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


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
    from pseudex.localui.server import app as ui_app  # noqa: PLC0415 (role-local)

    port = int(os.environ.get("PSEUDEX_UI_PORT", "8081"))
    # 0.0.0.0 INSIDE the container, and that is not the exposure control —
    # binding loopback here would make the port unreachable through Docker at
    # all, since publishing forwards to the container's own address.
    #
    # The control is on the HOST side of `-p`. Every run command we hand out now
    # says `-p 127.0.0.1:8081:8081`, because `-p 8081:8081` publishes on every
    # interface of the customer's Docker host — the internet, on a cloud VM —
    # and this port serves real personal values over plain HTTP. The printed
    # sign-in URL says "localhost" and quietly reinforces the wrong belief.
    host = os.environ.get("PSEUDEX_UI_HOST", "0.0.0.0")
    uvicorn.Server(uvicorn.Config(
        ui_app, host=host, port=port, log_level=log_level
    )).run()


def main() -> None:
    # Lowercased: the same variable is read by `logging.basicConfig` in
    # service.py, which wants "INFO", while uvicorn rejects anything but
    # lowercase. One variable, two consumers, so normalize at each of them.
    log_level = os.environ.get("PSEUDEX_LOG_LEVEL", "info").lower()
    role = os.environ.get("PSEUDEX_ROLE", "engine")
    if role == "ui":
        _serve_ui(log_level)
        return
    if role == "probe":
        raise SystemExit(_probe())
    if role == "decrypt":
        raise SystemExit(_decrypt())
    # Imported inside the role, not at module scope: the engine module builds the
    # detector, the audit connection and a licence client at import time, and a
    # UI process has no use for any of them. It also keeps the claim above
    # true — a UI process really does not load the engine.
    # The stores are opened while these modules are IMPORTED — the audit
    # connection and the tenant table are process singletons built at module
    # scope. So a key that does not open the vault surfaces right here, and it
    # must surface as OUR sentence rather than as a traceback ending in `file is
    # not a database`, which is the driver's one answer to three different
    # situations and sends the operator to check their disk.
    try:
        if role == "proxy":
            # The OpenAI-compatible shape: the customer points their app's base
            # URL here instead of at the provider. Same port and the same
            # SO_REUSEPORT fan-out as the sidecar — masking is morphology-bound
            # either way, so the reason for processes over threads does not
            # change with the shape.
            from pseudex.proxy import app  # noqa: PLC0415 (role-local)
        else:
            from pseudex.service import app  # noqa: PLC0415 (role-local)
    except (sqlite_setup.VaultLocked, vault_key.VaultKeyError,
            vault_migrate.VaultMigrationError) as error:
        print(f"pseudex: {error}", file=sys.stderr)
        # Non-zero, so `entrypoint.sh` takes the container down with it. A
        # gateway that cannot open its vault must not answer /mask: it would mint
        # a second substitute for every person who already has one, and the
        # first set would still be sitting in the customer's CRM.
        raise SystemExit(3) from None

    port = int(os.environ.get("PSEUDEX_PORT", "8000"))
    backlog = int(os.environ.get("PSEUDEX_BACKLOG", "2048"))
    sock = _listening_socket(port, backlog)
    uvicorn.Server(uvicorn.Config(app, fd=sock.fileno(), log_level=log_level)).run()


if __name__ == "__main__":
    main()
