"""Our own row in the public benchmark, produced the way anybody else's is.

The public benchmark (`public/agentmask-ru/`) must never import this engine,
and this script is the only bridge: it starts the sidecar the way the gates
do, then runs the PUBLIC harness against it over HTTP through the public
`pseudex_sidecar` adapter. Nothing about our engine reaches the benchmark
except the answers its endpoints give — the same surface Cloud.ru's filter
or Presidio present.

    python3 bench/public_row.py                      # run and print
    python3 bench/public_row.py --out ../public/agentmask-ru/results/

IT ALSO PRINTS WHAT THE BENCHMARK CANNOT SEE: how much of the corpus's
names our own leased dictionaries already hold. A benchmark of names a
gazetteer contains cannot fail that gazetteer, so the manifest carries the
overlap and the report reads the out-of-dictionary tiers separately.
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT.parent / "public" / "agentmask-ru"
sys.path.insert(0, str(ROOT))

import testkit  # noqa: E402  — must follow the sys.path line above


def _free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait(url: str, token: str, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    return False


def start_sidecar(db_dir: Path, token: str) -> tuple[object, int]:
    """The sidecar in this process, on a real port, with a dev bundle."""
    os.environ["PSEUDEX_DB_DIR"] = str(db_dir)
    os.environ["PSEUDEX_GATEWAY_TOKEN"] = token
    os.environ["PSEUDEX_VAULT_ENCRYPTION"] = "off"
    testkit.start_local_license()
    testkit.load_dev_bundle()

    import uvicorn

    from pseudex import service

    service.LICENSE.acquire()
    service.LICENSE.start()
    port = _free_port()
    config = uvicorn.Config(service.app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    return server, port


def gazetteer_overlap(cases_dir: Path) -> dict[str, object]:
    """How many of the corpus's names our own leased dictionaries hold.

    This is the number a vendor-authored benchmark owes the reader: a name
    the gazetteer already knows is a name this corpus cannot use to fail us.
    """
    from pseudex import names

    given: set[str] = set()
    surnames: set[str] = set()
    for path in sorted(cases_dir.rglob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        for item in case["pii"]:
            if item["type"] != "NAME":
                continue
            parts = item["value"].split()
            if parts:
                given.add(parts[0].strip(",.").lower())
            if len(parts) > 1:
                surnames.add(parts[1].strip(",.").lower())
    known_given = sum(1 for name in given if names.is_known_name(name))
    # `is_surname_shaped` is the engine's own test: in the dictionary, or
    # carrying a Russian surname suffix. Both are reasons the corpus cannot
    # use that surname to make us fail.
    known_surname = sum(1 for name in surnames if names.is_surname_shaped(name))
    return {
        "distinct_given_names": len(given),
        "in_our_gazetteer": known_given,
        "distinct_surnames": len(surnames),
        "surnames_in_our_gazetteer": known_surname,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=None, help="каталог results/ публичного бенчмарка")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--name", default="pseudex")
    args = parser.parse_args()
    if not PUBLIC.exists():
        print(f"публичный бенчмарк не найден в {PUBLIC}", file=sys.stderr)
        return 1

    token = "public-row-token"
    db_dir = Path(os.environ.get("PSEUDEX_DB_DIR", "/tmp/agentmask-public-row"))
    db_dir.mkdir(parents=True, exist_ok=True)
    server, port = start_sidecar(db_dir, token)
    base_url = f"http://127.0.0.1:{port}"
    if not _wait(f"{base_url}/health", token, 30):
        print("сайдкар не поднялся", file=sys.stderr)
        return 1

    overlap = gazetteer_overlap(PUBLIC / "cases")
    notes = ("движок запущен из исходников с dev-бандлом; "
             f"имён корпуса в нашем газетире: {overlap['in_our_gazetteer']}/{overlap['distinct_given_names']} личных, "
             f"{overlap['surnames_in_our_gazetteer']}/{overlap['distinct_surnames']} фамилий")
    command = [
        sys.executable, "-m", "agentmask_ru.cli", "run",
        "--adapter", "pseudex_sidecar", "--name", args.name,
        "--base-url", base_url, "--api-key", token,
        "--submitted-by", "AgentMask-RU maintainers (vendor-submitted)",
        "--notes", notes,
    ]
    if args.limit:
        command += ["--limit", str(args.limit)]
    if args.out:
        command += ["--out", str(Path(args.out).resolve())]
    print(json.dumps(overlap, ensure_ascii=False))
    result = subprocess.run(command, cwd=PUBLIC, env={**os.environ, "PYTHONPATH": str(PUBLIC / "src")})
    server.should_exit = True
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
