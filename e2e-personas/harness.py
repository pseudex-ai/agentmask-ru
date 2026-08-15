"""Allocate and tear down isolated customer environments for persona testing.

Each persona is a SEPARATE CUSTOMER and must be isolated exactly the way two real
customers are, or the test proves nothing about the product:

  * its own email, so the storefront issues its own account and org_id;
  * its own licence key, so the licensing server sees a separate organisation;
  * its own container, which generates its own gateway, operator and sign-in
    tokens at startup — they are per-container by construction;
  * its own PORT PAIR, because ten containers cannot share :8000, and this is
    the one thing that does not fall out of the product's own design;
  * its own working directory, containing only its fictional project.

WHAT IS DELIBERATELY SHARED: the storefront and the licensing server. Those are
US. Every customer in the world talks to the same two, and giving each persona a
private copy would test a deployment that does not exist.

Run:
    python3 e2e-personas/harness.py up --count 3
    python3 e2e-personas/harness.py status
    python3 e2e-personas/harness.py down
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_STATE = Path("/tmp/veilgate-personas.json")

# Chosen high and contiguous so a stray container is obvious in `docker ps` and
# cannot collide with the walkthrough stand on 8000/8081/8080.
BASE_ENGINE_PORT = 18100
BASE_UI_PORT = 18200

SITE = "http://localhost:8080"
IMAGE = "veilgate:source"


def sh(args: list[str], check: bool) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=check, timeout=180)


def _stack_is_up() -> bool:
    import httpx
    try:
        return httpx.get(SITE + "/", timeout=5).status_code == 200
    except httpx.HTTPError:
        return False


def up(count: int) -> int:
    if not _stack_is_up():
        print("the storefront is not answering on :8080 — run deploy/local.sh first")
        return 1

    personas = []
    for index in range(count):
        name = f"persona{index + 1}"
        personas.append({
            "name": name,
            "container": f"veilgate-{name}",
            "engine_port": BASE_ENGINE_PORT + index,
            "ui_port": BASE_UI_PORT + index,
            "email": f"{name}@example.com",
            "workdir": f"/tmp/veilgate-persona-{name}",
            # Filled in by the persona itself, by going through the site. The
            # harness deliberately does NOT register for them: signing up is the
            # first thing being tested, and doing it here would skip it.
            "org_id": None,
            "key": None,
        })
        Path(personas[-1]["workdir"]).mkdir(parents=True, exist_ok=True)

    _STATE.write_text(json.dumps({"personas": personas}, ensure_ascii=False, indent=2))
    print(f"allocated {count} persona environment(s):\n")
    for persona in personas:
        print(f"  {persona['name']}: engine :{persona['engine_port']}  "
              f"ui :{persona['ui_port']}  dir {persona['workdir']}")
    print(f"\nstate: {_STATE}")
    print("\nEach persona registers itself through the site — the harness does "
          "not, because signing up is the first thing under test.")
    return 0


def status() -> int:
    if not _STATE.exists():
        print("no personas allocated")
        return 1
    state = json.loads(_STATE.read_text())
    running = sh(["docker", "ps", "--format", "{{.Names}}"], False).stdout.split()
    print(f"{'persona':<12} {'engine':<8} {'ui':<8} {'container':<24} state")
    for persona in state["personas"]:
        alive = "up" if persona["container"] in running else "-"
        print(f"{persona['name']:<12} {persona['engine_port']:<8} "
              f"{persona['ui_port']:<8} {persona['container']:<24} {alive}")
    return 0


def down() -> int:
    if not _STATE.exists():
        print("no personas allocated")
        return 0
    state = json.loads(_STATE.read_text())
    for persona in state["personas"]:
        sh(["docker", "rm", "-f", persona["container"]], False)
        # The volume too: a persona that reruns must start from an empty vault,
        # or its "first request" is not its first and the counters lie.
        sh(["docker", "volume", "rm", "-f", f"{persona['container']}-data"], False)
        print(f"  removed {persona['container']}")
    _STATE.unlink()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["up", "status", "down"])
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()
    if args.command == "up":
        return up(args.count)
    if args.command == "status":
        return status()
    return down()


if __name__ == "__main__":
    sys.exit(main())
