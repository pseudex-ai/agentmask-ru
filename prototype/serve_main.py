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

from pseudex import preflight, sqlite_setup, vault_key, vault_migrate

# What the volume looks like, in one word, for the header line of the roles
# below. The per-file verdicts follow it — this is the sentence an operator reads
# first and it may not round a half-migrated volume up to «зашифровано».
_ON_DISK = {
    sqlite_setup.ENCRYPTED: "зашифрован",
    sqlite_setup.PLAINTEXT: "ОТКРЫТЫЙ ТЕКСТ",
    sqlite_setup.MIXED: "ЧАСТЬ ФАЙЛОВ ОТКРЫТА",
    sqlite_setup.EMPTY: "пуст",
}


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

    It opens read-only, migrates nothing and CREATES nothing — not even the key.
    It used to create that: with no key variables in its own environment it
    generated one beside the customer's data and then reported every store
    unopenable with it, which is a catastrophe invented by the diagnostic on a
    healthy volume. A diagnostic that changes the thing it is diagnosing is not
    one, and the docstring said so while the code did the opposite.
    """
    directory = _data_dir()
    print(f"pseudex probe: {os.path.abspath(directory)}")
    # From the FILES, not from the configuration: «ключ разрешился» and «том
    # зашифрован» are different facts, and only the second one is the question.
    state = sqlite_setup.volume_state(directory)
    print(f"  том: {_ON_DISK[state['on_disk']]}   ключ: {state['key_source']}")
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
    for filename, store in sqlite_setup.STORES:
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


def _rekey() -> int:
    """Rotate the key of every store in the data directory.

    STOP THE ENGINE FIRST. Nothing here can enforce that — the lock inside the
    connection factory serialises migrations, not a live gateway's traffic — so
    the honest thing is to say it in the output and to report per file, because
    a volume is not atomic across files: an interruption leaves some stores on
    the old key and some on the new, and only naming them makes that recoverable.
    """
    directory = _data_dir()
    current = vault_key.resolve(directory)
    if current is None:
        print("pseudex rekey: PSEUDEX_VAULT_ENCRYPTION=off — вращать нечего",
              file=sys.stderr)
        return 1
    replacement = vault_key.replacement(directory)
    print(f"pseudex rekey: {os.path.abspath(directory)}")
    print(f"  текущий ключ:  {current.source}")
    print(f"  новый ключ:    {replacement.source}")
    print("  движок на этом томе должен быть остановлен")
    moved, failed, plain = [], [], []
    for filename, store in sqlite_setup.STORES:
        path = os.path.join(directory, filename)
        try:
            result = vault_migrate.rekey_store(
                path, current.store_key(store), replacement.store_key(store))
        except vault_migrate.VaultMigrationError as error:
            print(f"  {filename:<12} ОТКАЗ  {error}", file=sys.stderr)
            failed.append(filename)
            continue
        print(f"  {filename:<12} {result}")
        if result == "rekeyed":
            moved.append(filename)
        elif result == vault_migrate.PLAINTEXT:
            plain.append(filename)
    if failed:
        print(f"\n  ТОМ РАЗЪЕХАЛСЯ: на новом ключе {moved or 'ничего'}, "
              f"не переведены {failed}. Старый ключ НЕ выключайте — он всё ещё "
              f"единственный, который открывает {failed}.", file=sys.stderr)
        return 1
    # A PLAINTEXT store counted as neither moved nor failed, and the line below
    # then told the operator every store was on the new key. It is the opposite
    # of a success: that file has no key at all, and the real values in it are
    # readable by anyone holding the volume.
    if plain:
        print(f"\n  НЕ ЗАШИФРОВАНЫ, поэтому и не переведены: {plain}. Вращать в "
              f"них нечего — они лежат ОТКРЫТЫМ ТЕКСТОМ. Их зашифрует движок при "
              f"следующем старте, тем ключом, который ему задан; ротацию имеет "
              f"смысл повторить после этого.", file=sys.stderr)
        return 1
    print("\n  все хранилища на новом ключе; старый можно отзывать")
    return 0


def _decrypt() -> int:
    """Write the stores back out in plain text. The door is not one-way.

    Deliberately its own role rather than a flag on the engine: it produces
    exactly what the rest of the product exists to prevent, so it has to be an
    act somebody performed, visible in the command that started the container.

    STOP THE ENGINE FIRST — the same requirement `_rekey` states, and it was
    missing here. The conversion ends in `os.replace`, so against a live volume
    it swaps the file out from under the running workers: they keep writing to
    the unlinked inode, and every token minted after that moment is lost. It is
    lost from the plaintext copy too, which is the copy a departing customer is
    taking with them — the one run where losing rows is least recoverable.
    """
    directory = _data_dir()
    secret = vault_key.resolve(directory)
    if secret is None:
        print("pseudex decrypt: PSEUDEX_VAULT_ENCRYPTION=off — нечего расшифровывать",
              file=sys.stderr)
        return 1
    print(f"pseudex decrypt: {os.path.abspath(directory)} — результат ляжет на "
          f"диск ОТКРЫТЫМ ТЕКСТОМ")
    print("  движок на этом томе должен быть остановлен")
    failures = 0
    for filename, store in sqlite_setup.STORES:
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


def _preflight() -> int:
    """Say how many workers fit in this container, before any of them starts.

    THE CONTRACT WITH `entrypoint.sh` IS THE STREAM, NOT THE FORMAT: exactly one
    line on stdout — the worker count to run — and every human sentence on
    stderr. The caller substitutes stdout into a variable, so a diagnostic line
    that slipped into it would become the worker count and `seq 1 "…"` would
    start nothing at all. The same split is why this is a role and not a print
    inside the engine.

    Exit code is the refusal: non-zero means do not start, and the reason is
    already on stderr where the operator reads it.
    """
    limit = preflight.memory_limit_mb()
    decision = preflight.plan(limit, preflight.cpus_available())
    print(f"pseudex preflight: {decision['reason']}", file=sys.stderr)
    if decision["verdict"] == "refused":
        return 1
    if decision["verdict"] == "reduced":
        print("           ВНИМАНИЕ: воркеров меньше, чем ядер — это решение "
              "приняли мы, а не вы", file=sys.stderr)
    print(decision["workers"])
    return 0


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
    if role == "preflight":
        raise SystemExit(_preflight())
    if role == "probe":
        raise SystemExit(_probe())
    if role == "rekey":
        raise SystemExit(_rekey())
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
