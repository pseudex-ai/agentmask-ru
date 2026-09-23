"""G-01…G-07: the RELEASED image against the NEW licensing server.

WHY THIS FILE EXISTS, AND WHY IT IS THE LAST THING BEFORE THE PLATFORM RELEASE.

`docs/tz-license-slots-and-epochs.md` §7.3 orders the rollout server-first
(platform release P, then engine release E), so between those two releases the
WHOLE fleet is a released engine talking to a server it has never met. That is
the one scenario where everything breaks at once, and it is the scenario no gate
covered: §9.2 names G-05 «выпущенный образ против НОВОГО сервера» with the note
«сценария нет ни в одном гейте». We have already been wrong here once — a
skeptic found that the released engine LOCKED UP on a cold start against the new
construction, and found it by reading code, not by a gate going red. A defect
class that is found by reading twice is a missing instrument, not bad luck.

WHAT «AS A REAL CLIENT» MEANS HERE, because it decides several details:

  * the engine is started the way the site tells a customer to start it
    (`storefront/templates/welcome.html`): `docker run` with a key, a volume and
    nothing else. In particular `PSEUDEX_INSTANCE_ID` is NOT set — the released
    `entrypoint.sh` mints a fresh random one on EVERY start, and pinning it here
    would hide exactly the behaviour the fleet has;
  * a restart is a real restart (`docker rm` + `docker run` on the same volume,
    which is what `docker compose up -d` does after an image change), and a kill
    is a real `docker kill -s KILL`;
  * the licensing server is the real one built from this worktree, over TLS, with
    its own database on a volume. Nothing is mocked and no test hook exists in
    either side.

WHAT IS COMPRESSED, AND IT IS CONFIGURATION RATHER THAN A HOOK — the same licence
`e2e/gates.py` takes for TTL and grace. The stand defines its own PLAN ROWS
through `/admin/plans` (a real admin endpoint, used by the console) with a small
`quantum_min`, so the band a fenced generation drains is tens of requests rather
than two hundred. The arithmetic under test is untouched; only the size of the
number it works on is.

THE DISCIPLINE, and it outranks coverage:

  * every gate proves its PRECONDITION first. «Nothing was refused» means
    nothing if no lease was attempted, and «it kept masking» means nothing if the
    container never came up. Each gate therefore asserts the positive fact
    (container active, lease issued, mask returned masked text) before it asserts
    the absence of anything;
  * every NEGATIVE atom is paired with a POSITIVE atom over the SAME source, the
    rule `e2e/audit_gates.py` enforces mechanically. Where a gate greps the
    licence log for `409`, it also greps the same log for the `lease issued` line
    that proves the log is the right log and was actually written;
  * the gate must be able to fail, and `--prove-red` shows it: it rebuilds the
    licensing image from a MUTATED copy of the tree (the old refusal code
    restored, or fencing removed) and runs the roster against it, expecting red.

usage:
    python3 e2e/slot_gates.py                      # the whole roster
    python3 e2e/slot_gates.py --only G-01,G-05
    python3 e2e/slot_gates.py --prove-red answer_code    # Б30: the old refusal code
    python3 e2e/slot_gates.py --prove-red no_fence       # no fencing at all
    python3 e2e/slot_gates.py --prove-red lease_refuse   # a lease refused again
    python3 e2e/slot_gates.py --prove-red free_first     # the letter of ТЗ §3.2

    # the RELEASED BINARY rather than its source, when its signing key is at hand:
    PSEUDEX_SIGNING_KEY=<base64 of the key that image was built with> \
      python3 e2e/slot_gates.py --released-image cr.yandex/.../pseudex:0.3.17

THE TWO WAYS TO NAME THE RELEASED ENGINE, and the gate refuses to be vague about
which one it ran. `--released-image` points at the artifact that actually
shipped; its verification key is COMPILED IN, so the stand can only lease to it
when `PSEUDEX_SIGNING_KEY` is the key it was built with, and the gate proves that
by deriving the public half and comparing it against the key it reads out of the
image. Without that key the gate falls back to building the released engine from
its own release tag (`--released-tag`, default `v0.3.17`) with a key the stand
owns — the same licensing client, entrypoint and surfaces, byte for byte, built
the way `e2e/gates.py` builds `pseudex:source`. The fallback is NEVER silent: it
is proved by comparing `/app/entrypoint.sh` of the released image against the tag,
it is printed in the mode line, and the final report says in one line that the
compiled artifact itself was not exercised.
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from e2e import certs, fixtures  # noqa: E402
from licensing.keys import encode_private, encode_public  # noqa: E402

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent          # prototype/
_REPO = _ROOT.parent          # repository root
_CERTS = _HERE / "certs-slots"

NETWORK = "pseudex-slots"
LICENSE_CONTAINER = "pseudex-slots-license"
LICENSE_VOLUME = "pseudex-slots-license-data"
ADMIN = "http://127.0.0.1:19543"
ORG = "slotgate"
# The org named in a /mask BODY is the tenant of the vault inside the container;
# it has nothing to do with the licence org, and keeping it constant keeps the
# masking comparable across gates.
MASK_ORG = "acme"

ADMIN_TOKEN = "slots-admin-token"
ADMIN_AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
GATEWAY_TOKEN = "slots-gateway-token"
GATEWAY_AUTH = {"Authorization": f"Bearer {GATEWAY_TOKEN}"}

# Lease TTL long enough that no gate accidentally measures expiry, short enough
# that a renewal is observable. Grace likewise. Configuration, as in gates.py.
TTL_SECONDS = 300
GRACE_SECONDS = 600

# The stand's own plan rows. `quantum_min == quantum_max` pins the band, so the
# number of requests a fenced generation may still serve is known rather than
# inferred; `reserve_max = 1` is the smallest the server accepts (`/admin/plans`
# refuses 0) and `PSEUDEX_RESERVE_SECONDS=1` on the container keeps the computed
# reserve at that floor.
QUANTUM = 12
PLAN_ONE = "slotgate1"      # 1 slot — the tightest plan we sell
PLAN_FOUR = "slotgate4"     # 4 slots — where an occupancy screen can lie

# How long a container is given to import the model stack and reach `active`.
BOOT_SECONDS = 180


@dataclass
class Result:
    name: str
    ok: bool
    detail: str


RESULTS: list[Result] = []
NOTES: list[str] = []


@dataclass
class Mode:
    """Which artifact stood in for «the released engine», and what proves it."""
    image: str
    kind: str          # "binary" | "source@<tag>"
    evidence: str
    released_image: str
    tag: str
    exercised_binary: bool = False
    facts: list[str] = field(default_factory=list)


# --- plumbing -------------------------------------------------------------


def sh(args: list[str], check: bool, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=check,
                          timeout=timeout)


def gate(name: str, ok: bool, detail: str) -> bool:
    RESULTS.append(Result(name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")
    return ok


def run_gate(name: str, fn, *args) -> None:
    """One gate's bug must not hide the other six (same rule as gates.py)."""
    try:
        fn(*args)
    except Exception as error:  # noqa: BLE001 — a gate may fail any way it likes
        gate(name, False, f"gate raised {type(error).__name__}: {error}")


def admin_get(path: str, **params) -> dict:
    response = httpx.get(f"{ADMIN}{path}", params=params, timeout=30,
                         headers=ADMIN_AUTH)
    response.raise_for_status()
    return response.json()


def admin_post(path: str, body: dict) -> httpx.Response:
    return httpx.post(f"{ADMIN}{path}", json=body, timeout=30, headers=ADMIN_AUTH)


def license_logs() -> str:
    out = sh(["docker", "logs", LICENSE_CONTAINER], False, 60)
    return out.stdout + out.stderr


def container_logs(name: str) -> str:
    out = sh(["docker", "logs", name], False, 60)
    return out.stdout + out.stderr


def wait_until(predicate, timeout: float, interval: float, what: str) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            pass
        time.sleep(interval)
    print(f"      timed out waiting for {what} after {timeout:.0f}s")
    return False


# --- the stand ------------------------------------------------------------


def _rm_container(name: str) -> None:
    sh(["docker", "rm", "-f", name], False, 120)


def _rm_volume(name: str) -> None:
    sh(["docker", "volume", "rm", "-f", name], False, 60)


def tear_down(volumes: list[str]) -> None:
    _rm_container(LICENSE_CONTAINER)
    for volume in volumes:
        _rm_volume(volume)
    _rm_volume(LICENSE_VOLUME)
    sh(["docker", "network", "rm", NETWORK], False, 60)


def start_license(image: str, signing_key: str) -> None:
    """Bring the licensing server up on its own network, over TLS, and prove it."""
    _rm_container(LICENSE_CONTAINER)
    sh(["docker", "network", "create", NETWORK], False, 60)
    args = ["docker", "run", "-d", "--name", LICENSE_CONTAINER,
            "--network", NETWORK, "--network-alias", "license",
            "-v", f"{_CERTS}:/certs:ro",
            "-v", f"{LICENSE_VOLUME}:/data",
            "-p", "19543:9443", "-p", "18543:8443",
            "-e", f"PSEUDEX_SIGNING_KEY={signing_key}",
            "-e", f"PSEUDEX_LICENSE_ADMIN_TOKEN={ADMIN_TOKEN}",
            "-e", f"PSEUDEX_LEASE_TTL_SECONDS={TTL_SECONDS}",
            "-e", f"PSEUDEX_GRACE_SECONDS={GRACE_SECONDS}",
            # The reserve is a multiple of the observed rate; pinning the window
            # to one second keeps it at the plan floor so the drained band is the
            # quantum and not a day of traffic.
            "-e", "PSEUDEX_RESERVE_SECONDS=1",
            "-e", "PSEUDEX_LICENSE_CERT=/certs/server.pem",
            "-e", "PSEUDEX_LICENSE_KEYFILE=/certs/server.key",
            image]
    sh(args, True, 180)
    if not wait_until(lambda: httpx.get(f"{ADMIN}/admin/list", timeout=5,
                                        headers=ADMIN_AUTH).status_code == 200,
                      120, 2, "licensing admin"):
        raise SystemExit("licensing server did not come up")


def define_plans() -> None:
    for code, slots in ((PLAN_ONE, 1), (PLAN_FOUR, 4)):
        response = admin_post("/admin/plans", {
            "code": code, "actor": "slot_gates",
            "max_instances": slots, "processes_per_instance": 32,
            "grant_size": 100_000, "quantum_min": QUANTUM,
            "quantum_max": QUANTUM, "reserve_max": 1})
        if response.status_code != 200:
            raise SystemExit(f"could not define plan {code}: "
                             f"{response.status_code} {response.text}")


def issue_key(org: str, plan: str) -> str:
    response = admin_post("/admin/issue", {"org_id": org, "plan": plan})
    if response.status_code != 200:
        raise SystemExit(f"could not issue a key: {response.status_code} {response.text}")
    return response.json()["key"]


# --- the engine, started the way a customer starts it ---------------------


def engine_run(name: str, image: str, volume: str, port: int, key: str,
               extra_env: dict[str, str] | None = None) -> None:
    """`docker run` as the site prints it: a key, a volume, nothing else.

    `PSEUDEX_INSTANCE_ID` is deliberately absent — the released entrypoint mints
    a fresh random one on every start, and a stand that pinned it would be
    testing a fleet that does not exist."""
    _rm_container(name)
    args = ["docker", "run", "-d", "--name", name, "--network", NETWORK,
            "-v", f"{_CERTS}:/certs:ro", "-v", f"{volume}:/data",
            "-p", f"{port}:8000",
            "-e", "PSEUDEX_LICENSE_URL=https://license:8443",
            "-e", "PSEUDEX_LICENSE_CA=/certs/ca.pem",
            "-e", f"PSEUDEX_LICENSE_KEY={key}",
            "-e", f"PSEUDEX_GATEWAY_TOKEN={GATEWAY_TOKEN}",
            "-e", f"PSEUDEX_ADMIN_TOKEN={ADMIN_TOKEN}",
            "-e", "PSEUDEX_WORKERS=1"]
    for env_name, value in (extra_env or {}).items():
        args += ["-e", f"{env_name}={value}"]
    args.append(image)
    sh(args, True, 300)


def engine_active(port: int) -> bool:
    body = httpx.get(f"http://127.0.0.1:{port}/health", timeout=5).json()
    return body.get("license") == "active"


def engine_wait_active(name: str, port: int, seconds: int = BOOT_SECONDS) -> bool:
    """Wait for `license=active`, and STOP WAITING once the container is gone.

    A refused cold start exits within seconds; polling its port for the whole
    boot budget afterwards costs three minutes per cycle and, worse, reports the
    failure as «timed out» when what happened was «it was refused and died»."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if engine_active(port):
                return True
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            pass
        if not engine_alive(name):
            print(f"      {name} is no longer running "
                  f"(exit {engine_exit_code(name)}) — it will not become active")
            return False
        time.sleep(2)
    print(f"      timed out waiting for {name} on :{port} to reach license=active")
    return False


def engine_alive(name: str) -> bool:
    out = sh(["docker", "inspect", "-f", "{{.State.Running}}", name], False, 60)
    return out.stdout.strip() == "true"


def engine_exit_code(name: str) -> int:
    out = sh(["docker", "inspect", "-f", "{{.State.ExitCode}}", name], False, 60)
    try:
        return int(out.stdout.strip())
    except ValueError:
        return -1


def mask(port: int, index: int = 0) -> httpx.Response:
    body = (fixtures.mask_body(MASK_ORG) if index == 0
            else fixtures.mask_body_variant(MASK_ORG, index))
    return httpx.post(f"http://127.0.0.1:{port}/mask", json=body,
                      timeout=120, headers=GATEWAY_AUTH)


def masked_text(response: httpx.Response) -> str:
    return json.dumps(response.json().get("messages", []), ensure_ascii=False)


def mask_is_real(response: httpx.Response) -> tuple[bool, str]:
    """Did that answer actually mask, or merely answer 200?

    Two atoms over ONE source (the same response body): the real phone is GONE
    (negative) and a substitute phone is THERE (positive). Either alone is
    decorative — an empty body satisfies the first, and an unmasked body that
    happens to mention some other number satisfies the second."""
    if response.status_code != 200:
        return False, f"status={response.status_code}"
    text = masked_text(response)
    real = fixtures.PII_PAYLOAD["phone"]
    real_digits = re.sub(r"\D", "", real)
    digits = re.sub(r"\D", "", text)
    has_real = real in text or real_digits in digits
    substitutes = re.findall(r"[+]?7[\s\-(]*\d{3}", text)
    return (not has_real) and bool(substitutes) and len(text) > 40, (
        f"real_present={has_real} substitute_shapes={len(substitutes)} chars={len(text)}")


def masks_until_blocked(port: int, limit: int, start_index: int) -> tuple[int, str, int]:
    """Push masks until one is refused. Returns (served, code, status)."""
    served = 0
    for index in range(limit):
        response = mask(port, start_index + index)
        if response.status_code == 200:
            served += 1
            continue
        try:
            code = str(response.json().get("error", ""))
        except ValueError:
            code = "(unparsable body)"
        return served, code, response.status_code
    return served, "", 200


# --- counting what the server wrote ---------------------------------------


def instances(org: str = ORG) -> dict:
    return admin_get("/admin/instances", org_id=org)


def usage(org: str = ORG) -> dict:
    return admin_get("/admin/usage", org_id=org)["usage"]


_LEASE_LINE = re.compile(r"lease issued org=(\S+) instance=(\S+) plan=(\S+) "
                         r"ttl=(\S+) slot=(\S+) epoch=(\S+)")
_FENCE_LINE = re.compile(r"capacity fenced for org=")


def lease_lines(log: str) -> list[tuple[str, ...]]:
    return _LEASE_LINE.findall(log)


_LEASE_4XX = re.compile(r'"POST /v1/lease HTTP/[\d.]+" 4\d\d')


def refusals_on_lease(log: str) -> list[str]:
    """Every line that would mean a lease was REFUSED.

    TWO INDEPENDENT READINGS OF THE SAME LOG, because either alone has been
    wrong here. The transport reading — any 4xx on `POST /v1/lease` in the access
    log — cannot be defeated by renaming a code, and it is the one that caught
    the `lease_refuse` mutant. The vocabulary reading names the refusals of all
    six previous attempts plus the server's own «lease refused» phrase, and it
    survives a change of access-log format. The first version of this function
    had only the vocabulary, EXCLUDED every line mentioning `/v1/lease` to skip
    the access log, and therefore reported «0 refusals» while every restart was
    being refused — the gate's own red proof is what showed it."""
    words = ("lease refused", "instance_limit", "release_budget",
             "too_many_instances", "reclaimed", "turnover", "processes_exhausted")
    found = []
    for line in log.splitlines():
        if _LEASE_4XX.search(line):
            found.append(line)
        elif "/v1/lease" not in line and any(word in line for word in words):
            found.append(line)
    return found


# --- the released artifact ------------------------------------------------


_BASE64_32 = re.compile(rb"[A-Za-z0-9+/]{43}=")


def baked_pubkey(image: str) -> str:
    """The verification key COMPILED INTO an image, read out of the image.

    For a source image it is the literal in `pseudex/_release.py`; for the
    compiled one it is the only Ed25519-shaped base64 constant in the binary.
    Reading it rather than being told it is what lets the gate REFUSE when the
    signing key it was handed is not the one that image will trust — the
    alternative is a stand that comes up, fails every lease, and reports that
    the released engine «locked up»."""
    blob = b""
    for path in ("/app/pseudex/_release.py", "/app/pseudex-serve"):
        out = subprocess.run(["docker", "run", "--rm", "--entrypoint", "cat",
                              image, path], capture_output=True, timeout=1200)
        if out.returncode == 0 and out.stdout:
            blob = out.stdout
            break
    if not blob:
        raise RuntimeError(f"{image} carries neither pseudex/_release.py nor "
                           f"a compiled pseudex-serve — nothing to read a key out of")
    found = []
    for candidate in dict.fromkeys(_BASE64_32.findall(blob)):
        try:
            raw = base64.b64decode(candidate)
        except ValueError:
            continue
        if len(raw) == 32:
            found.append(candidate.decode())
    if len(found) != 1:
        raise RuntimeError(f"expected exactly one baked key in {image}, found {len(found)}")
    return found[0]


def released_entrypoint(image: str) -> bytes:
    out = subprocess.run(["docker", "run", "--rm", "--entrypoint", "cat", image,
                          "/app/entrypoint.sh"], capture_output=True, timeout=600)
    return out.stdout


def build_from_tag(tag: str, pubkey: str) -> str:
    """Build the released engine from its own release tag, with OUR key."""
    workdir = Path(f"/tmp/pseudex-tag-{tag}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    archive = subprocess.run(["git", "archive", tag, "prototype"],
                             cwd=_REPO, capture_output=True, timeout=300)
    if archive.returncode != 0:
        raise RuntimeError(f"git archive {tag} failed: {archive.stderr.decode()[:400]}")
    subprocess.run(["tar", "-x", "-C", str(workdir)], input=archive.stdout,
                   check=True, timeout=300)
    image = f"pseudex:slots-{tag}"
    sh(["docker", "build", "-f", "Dockerfile",
        "--build-arg", f"PSEUDEX_LICENSE_PUBKEY={pubkey}",
        "-t", image, str(workdir / "prototype")], True, 3600)
    return image


def build_worktree(pubkey: str) -> str:
    image = "pseudex:slots-new"
    sh(["docker", "build", "-f", "Dockerfile",
        "--build-arg", f"PSEUDEX_LICENSE_PUBKEY={pubkey}",
        "-t", image, str(_ROOT)], True, 3600)
    return image


def resolve_released(args, signing_key: str, pubkey: str) -> Mode:
    """Decide WHICH artifact plays «the released engine», and prove the choice.

    This is a gate, not a setup step: an unproved answer here would make every
    later verdict a claim about an artifact nobody identified."""
    released_image = args.released_image
    have_image = bool(sh(["docker", "image", "inspect", released_image],
                         False, 120).stdout.strip().startswith("["))
    if not have_image:
        sh(["docker", "pull", released_image], False, 1800)
        have_image = bool(sh(["docker", "image", "inspect", released_image],
                             False, 120).stdout.strip().startswith("["))
    if not have_image:
        raise SystemExit(f"the released image {released_image} is not here and could "
                         f"not be pulled — this gate is about that artifact")

    baked = baked_pubkey(released_image)
    if baked == pubkey:
        gate("PRE-1 released artifact is the COMPILED image", True,
             f"image={released_image} baked_key={baked[:12]}… matches the stand's "
             f"signing key — the shipped binary itself is under test")
        return Mode(image=released_image, kind="binary",
                    evidence=f"baked verification key {baked[:12]}… equals the "
                             f"public half of PSEUDEX_SIGNING_KEY",
                    released_image=released_image, tag=args.released_tag,
                    exercised_binary=True,
                    facts=[f"baked_pubkey={baked}"])

    # The compiled image will not trust our leases. Stand in with the SAME
    # source, built the same way `gates.py` builds `pseudex:source`, and prove
    # the substitution by bytes rather than by assertion.
    from_image = released_entrypoint(released_image)
    from_tag = subprocess.run(["git", "show", f"{args.released_tag}:prototype/entrypoint.sh"],
                              cwd=_REPO, capture_output=True, timeout=120).stdout
    same = bool(from_image) and from_image == from_tag
    image = args.substitute_image or build_from_tag(args.released_tag, pubkey)
    gate("PRE-1 released artifact is its SOURCE TAG (binary key not available)", same,
         f"entrypoint of {released_image} == {args.released_tag}:prototype/entrypoint.sh "
         f"({len(from_image)}B vs {len(from_tag)}B, equal={same}); standing in with {image}")
    NOTES.append(
        f"G-01…G-07 ran against {image}, built from {args.released_tag} — the released "
        f"ENGINE SOURCE. The compiled artifact {released_image} was NOT exercised: its "
        f"verification key is baked in and the stand does not hold the matching signing "
        f"key. Re-run with PSEUDEX_SIGNING_KEY set to that key to close the gap.")
    return Mode(image=image, kind=f"source@{args.released_tag}",
                evidence=f"/app/entrypoint.sh of {released_image} is byte-identical to "
                         f"{args.released_tag}:prototype/entrypoint.sh",
                released_image=released_image, tag=args.released_tag,
                exercised_binary=False,
                facts=[f"entrypoint_bytes={len(from_image)}"])


# --- PRE-2: the stand really is the new construction ----------------------


_REMOVED_WORDS = ("silent", "reclaimed", "held_places", "live_processes",
                  "turnover", "alive_seconds")


def gate_pre2(org: str) -> bool:
    """The server the roster is about to judge is the new construction.

    Both directions over ONE body: the slot fields are THERE with the values the
    plan says (positive — an error body or an old server cannot produce them),
    and none of the six words §5 deletes is anywhere in it (negative)."""
    body = instances(org)
    missing = [word for word in
               ("slots", "occupied", "slot_count", "epochs_unacked_24h",
                "slot_contention_24h", "generations_24h") if word not in body]
    raw = json.dumps(body, ensure_ascii=False)
    stale = [word for word in _REMOVED_WORDS if word in raw]
    shaped = (body.get("slot_count") == 1 and isinstance(body.get("slots"), list)
              and len(body["slots"]) == 1)
    return gate("PRE-2 the stand's server is the SLOTS construction",
                shaped and not missing and not stale,
                f"slot_count={body.get('slot_count')} slots_listed="
                f"{len(body.get('slots') or [])} missing_fields={missing or 'none'} "
                f"removed_words={stale or 'none'}")


# --- G-01: cold start -----------------------------------------------------


def gate_g01(mode: Mode, key: str, org: str, volume: str) -> bool:
    """A released engine meeting the new server for the first time must SERVE.

    This is the one the skeptic found by reading: `acquire()` buys the first
    quantum inside itself, so a verdict arriving in that window used to be a
    container that never starts."""
    _rm_volume(volume)
    name = "slotgate-cold"
    before = len(lease_lines(license_logs()))
    engine_run(name, mode.image, volume, 18100, key)
    active = engine_wait_active(name, 18100)
    response = mask(18100) if active else None
    real, detail = mask_is_real(response) if response is not None else (False, "never asked")

    log = license_logs()
    leases = lease_lines(log)[before:]
    refused = refusals_on_lease(log)
    view = instances(org)
    generations = [g for slot in view["slots"] for g in ([slot["holder"]] if slot["holder"] else [])]
    legacy = [g for g in generations if str(g["start_id"]).startswith("legacy:")]

    ok = (active and real and bool(leases) and not refused
          and view["occupied"] == 1 and bool(legacy))
    return gate("G-01 cold start of the released image on a fresh volume", ok,
                f"active={active} masked=({detail}) leases_issued={len(leases)} "
                f"refusals={len(refused)} occupied={view['occupied']}/{view['slot_count']} "
                f"legacy_generation={bool(legacy)}")


# --- G-02: ordinary restarts ---------------------------------------------


def _restart_cycles(image: str, key: str, org: str, volume: str, port: int,
                    name: str, cycles: int) -> dict[str, object]:
    """Start, mask, stop — `cycles` times on ONE volume. What the server wrote.

    A real restart: the container is removed and started again on the same
    volume, which is what `docker compose up -d` does after an image change and
    what `docker restart` amounts to for the engine (the released entrypoint
    mints a fresh `PSEUDEX_INSTANCE_ID` either way)."""
    _rm_volume(volume)
    before = len(lease_lines(license_logs()))
    served = 0
    occupancy: list[int] = []
    for cycle in range(cycles):
        engine_run(name, image, volume, port, key)
        if not engine_wait_active(name, port):
            break
        if mask_is_real(mask(port, cycle + 1))[0]:
            served += 1
        occupancy.append(instances(org)["occupied"])
        sh(["docker", "stop", "-t", "20", name], False, 120)
    _rm_container(name)
    log = license_logs()
    view = instances(org)
    return {"served": served, "cycles": cycles, "occupancy": occupancy,
            "leases": lease_lines(log)[before:],
            "refused": refusals_on_lease(log), "view": view}


def gate_g02(mode: Mode, new_image: str, key: str, org: str, volume: str,
             key_new: str, org_new: str, volume_new: str) -> bool:
    """Three ordinary restarts on a four-slot plan.

    THREE verdicts, reported apart because they fail apart and because the third
    is what makes the second attributable:
      (a) nobody is locked out — every cycle masks, no lease is refused;
      (b) the SCREEN does not lie — one container with three restarts must not
          read as «занято 4 из 4» (ТЗ §3.5; the Б26bis class this construction
          exists to close);
      (c) the same four cycles with the NEW engine. It is the positive control
          for (b): if (b) is red and (c) is green, the occupancy is inflated by
          the released fleet's random per-start installation id and not by the
          slot mechanism, and the fix lives in one of those two places rather
          than in «somewhere».
    """
    old = _restart_cycles(mode.image, key, org, volume, 18101,
                          "slotgate-restart", 4)
    gate("G-02a three ordinary restarts lock nobody out",
         old["served"] == old["cycles"] and bool(old["leases"]) and not old["refused"],
         f"masked_cycles={old['served']}/{old['cycles']} "
         f"leases_issued={len(old['leases'])} refusals={len(old['refused'])}")
    released_view = old["view"]
    gate("G-02b one container, three restarts is not «занято 4 из 4»",
         released_view["occupied"] == 1 and bool(old["leases"]),
         f"occupied={released_view['occupied']}/{released_view['slot_count']} "
         f"after each cycle={old['occupancy']} "
         f"generations_24h={released_view['generations_24h']} "
         f"leases_issued={len(old['leases'])}")
    new = _restart_cycles(new_image, key_new, org_new, volume_new, 18110,
                          "slotgate-restart-new", 4)
    new_view = new["view"]
    return gate("G-02c the same four cycles with the NEW engine hold one slot",
                new_view["occupied"] == 1 and new["served"] == new["cycles"]
                and bool(new["leases"]) and not new["refused"],
                f"occupied={new_view['occupied']}/{new_view['slot_count']} "
                f"after each cycle={new['occupancy']} "
                f"masked_cycles={new['served']}/{new['cycles']} "
                f"leases_issued={len(new['leases'])} refusals={len(new['refused'])}")


# --- G-03: SIGKILL ---------------------------------------------------------


def gate_g03(mode: Mode, key: str, org: str, volume_kill: str,
             key_stop: str, org_stop: str, volume_stop: str) -> bool:
    """A kill with nothing to say goodbye with is indistinguishable from a stop.

    Run BOTH — the same code with one flag — and compare what the server wrote.
    A gate that only killed something would pass on a server that refuses every
    restart equally."""
    outcomes = {}
    for label, volume, port, name, this_key, this_org in (
            ("kill", volume_kill, 18102, "slotgate-kill", key, org),
            ("stop", volume_stop, 18103, "slotgate-stop", key_stop, org_stop)):
        _rm_volume(volume)
        engine_run(name, mode.image, volume, port, this_key)
        first = engine_wait_active(name, port)
        first_mask = mask_is_real(mask(port, 1))[0] if first else False
        if label == "kill":
            sh(["docker", "kill", "-s", "KILL", name], False, 120)
            # 137 = 128 + SIGKILL. The PRECONDITION: without it «it came back»
            # says nothing about a kill.
            wait_until(lambda n=name: not engine_alive(n), 60, 1, "the kill to land")
            signal_seen = engine_exit_code(name) == 137
        else:
            sh(["docker", "stop", "-t", "20", name], False, 180)
            signal_seen = True
        engine_run(name, mode.image, volume, port, this_key)
        second = engine_wait_active(name, port)
        second_mask = mask_is_real(mask(port, 2))[0] if second else False
        view = instances(this_org)
        outcomes[label] = {
            "signal": signal_seen, "up_again": second,
            "masked_before": first_mask, "masked_after": second_mask,
            "occupied": view["occupied"],
            "epochs": [slot["epoch"] for slot in view["slots"]],
            "generations": view["generations_24h"],
        }
        sh(["docker", "stop", "-t", "20", name], False, 180)

    kill, stop = outcomes["kill"], outcomes["stop"]
    decisive = ("occupied", "epochs", "generations", "up_again", "masked_after")
    kill_record = {name: kill[name] for name in decisive}
    stop_record = {name: stop[name] for name in decisive}
    # THE DIFF NEEDS A POSITIVE CONTROL OVER THE SAME RECORDS. Two dictionaries
    # of Nones are identical too, and «identical» is the whole verdict here, so
    # each side must first be shown to contain a run that happened: two
    # generations (start and restart) and an occupied slot.
    both_ran = (kill["generations"] >= 2 and stop["generations"] >= 2
                and kill["occupied"] == 1 and stop["occupied"] == 1)
    ok = (kill["signal"] and kill["masked_before"] and kill["up_again"]
          and kill["masked_after"] and both_ran and kill_record == stop_record)
    return gate("G-03 SIGKILL and a graceful stop are one path", ok,
                f"kill_exit_137={kill['signal']} both_arms_really_ran={both_ran} "
                f"kill={kill_record} stop={stop_record} "
                f"identical={kill_record == stop_record}")


# --- G-04: the ring --------------------------------------------------------


def gate_g04(mode: Mode, key: str, org: str) -> bool:
    """lease → release → lease, many turns. What does it carry away, and is it seen?

    The number printed here is the остаток §8 names, not a pass mark: the point
    is that the ring leaves a TRAIL (`epochs_unacked`, `generations_24h`) and
    that it carries away no more than one quantum per turn."""
    turns = 4
    name = "slotgate-ring"
    before = usage(org)
    granted_before = int(before.get("capacity_granted", 0))
    for turn in range(turns):
        volume = f"pseudex-slots-ring-{turn}"
        _rm_volume(volume)
        engine_run(name, mode.image, volume, 18104, key)
        up = engine_wait_active(name, 18104)
        if not up:
            break
        # A polite ring: stop gracefully so `/v1/release` is actually called —
        # the version of the ring that used to be free.
        sh(["docker", "stop", "-t", "20", name], False, 180)
        _rm_container(name)
        _rm_volume(volume)
    after = usage(org)
    granted_after = int(after.get("capacity_granted", 0))
    carried = granted_after - granted_before
    view = instances(org)

    trail = (view["generations_24h"] >= turns
             and view["epochs_unacked_24h"] >= turns)
    bounded = 0 < carried <= QUANTUM * turns
    ok = trail and bounded
    return gate("G-04 the lease→release→lease ring is bounded and visible", ok,
                f"turns={turns} capacity_granted+={carried} "
                f"(ceiling {QUANTUM * turns} = quantum×turns) "
                f"generations_24h={view['generations_24h']} "
                f"epochs_unacked_24h={view['epochs_unacked_24h']} "
                f"billable={after.get('capacity_billable')}")


# --- G-05: the ceiling, and Б30 both ways ---------------------------------


def gate_g05(mode: Mode, key: str, org: str, volume_a: str,
             volume_b: str) -> bool:
    """Hit the plan ceiling: drain what was bought, THEN go dark.

    Both halves, because each without the other is the defect:
      * it must NOT go dark at the instant of the verdict (Б30 — the released
        client used to `_expire()` on `instance_limit`, burning paid capacity);
      * it must go dark in the end, or the ceiling enforces nothing.
    """
    _rm_volume(volume_a)
    _rm_volume(volume_b)
    first, second = "slotgate-ceiling-a", "slotgate-ceiling-b"
    engine_run(first, mode.image, volume_a, 18105, key)
    if not engine_wait_active(first, 18105):
        return gate("G-05 ceiling: drain, then stop", False,
                    "the first container never reached active")
    # Cross the prefetch threshold so the holder has bought a SECOND quantum and
    # is therefore in the middle of a band when it is fenced.
    warm, _, _ = masks_until_blocked(18105, QUANTUM, 100)

    # A second container on a DIFFERENT volume: on a one-slot plan it claims the
    # slot by ranking, which is what fences the first.
    engine_run(second, mode.image, volume_b, 18106, key)
    engine_wait_active(second, 18106)

    served_after, code, status = masks_until_blocked(18105, QUANTUM * 6, 300)
    # WHAT THE VERDICT DID TO THE LICENCE ITSELF. Draining and dying look alike
    # from `/mask` alone — both end in a 503 — and the difference is whether the
    # bundle is still loaded. `instance_limit` set `_terminal_code` and called
    # `_expire()`, so the state went `expired` the moment the answer arrived;
    # `fenced` is transient, so the state stays `active` while the band runs out
    # and the 503 is about CAPACITY. That is the whole of Б30 in one field.
    # `/license` answers 503 while degraded and 200 while healthy, and the body
    # parses on either code — so the status is read, not raised on.
    licence = httpx.get("http://127.0.0.1:18105/license", timeout=15).json()
    state = str(licence.get("state", ""))
    loaded = bool(licence.get("assets_loaded"))
    terminal = licence.get("code")
    log = license_logs()
    fenced_logged = bool(_FENCE_LINE.search(log))
    leases = lease_lines(log)
    refused = refusals_on_lease(log)
    view = instances(org)

    # COUNTS, NOT «SOMETHING HAPPENED». The band is the plan's quantum plus the
    # one-unit reserve floor, so the warm-up must serve the whole quantum and the
    # drain must be inside one band — «more than zero» would pass on a single
    # request and read as if the promise had been measured.
    warmed = warm == QUANTUM
    drained = 1 <= served_after <= QUANTUM * 3
    went_dark = code in ("capacity_exhausted", "fenced") and status == 503
    not_expired = state == "active" and loaded and terminal is None
    ok = (warmed and fenced_logged and drained and went_dark and not_expired
          and bool(leases) and not refused)
    return gate("G-05 ceiling: the fenced generation drains its band, then stops", ok,
                f"warm_masks={warm}/{QUANTUM} fence_in_server_log={fenced_logged} "
                f"masks_after_fence={served_after} (band ≤ {QUANTUM * 3}) "
                f"then={status}/{code or '(never blocked)'} licence_state={state!r} "
                f"assets_loaded={loaded} terminal_code={terminal!r} "
                f"lease_refusals={len(refused)} slot_epoch={[s['epoch'] for s in view['slots']]}")


# --- G-06: a mixed fleet ---------------------------------------------------


def gate_g06(mode: Mode, new_image: str, key: str, org: str,
             volume_old: str, volume_new: str) -> bool:
    """One organisation, both engines at once. Neither may lock the other."""
    _rm_volume(volume_old)
    _rm_volume(volume_new)
    old_name, new_name = "slotgate-mixed-old", "slotgate-mixed-new"
    engine_run(old_name, mode.image, volume_old, 18107, key)
    engine_run(new_name, new_image, volume_new, 18108, key)
    old_up = engine_wait_active(old_name, 18107)
    new_up = engine_wait_active(new_name, 18108)

    # Interleave, so «both serve» is about the same window and not about two
    # separate minutes. A container that never came up is NOT asked: a refused
    # connection would leave this gate as «raised ConnectError», which is a red
    # that names the symptom instead of the claim — and the claim («neither one
    # is locked») is already false at that point and must be the thing reported.
    old_ok = new_ok = 0
    for index in range(6):
        if old_up and mask_is_real(mask(18107, 500 + index))[0]:
            old_ok += 1
        if new_up and mask_is_real(mask(18108, 600 + index))[0]:
            new_ok += 1
    log = license_logs()
    refused = refusals_on_lease(log)
    leases = lease_lines(log)
    view = instances(org)

    ok = (old_up and new_up and old_ok == 6 and new_ok == 6
          and bool(leases) and not refused and view["occupied"] == 2)
    return gate("G-06 released and new engine side by side, neither locked", ok,
                f"old_active={old_up} new_active={new_up} old_masks={old_ok}/6 "
                f"new_masks={new_ok}/6 occupied={view['occupied']}/{view['slot_count']} "
                f"lease_refusals={len(refused)}")


# --- G-07: a volume that lived under the OLD server ------------------------


def gate_g07(mode: Mode, old_license_image: str, new_license_image: str,
             signing_key: str, volume: str) -> bool:
    """The real migration: a customer who was already running when we upgraded.

    The engine container is NOT restarted across the server swap — that is what a
    customer experiences — and only then restarted, because both halves can
    break separately."""
    name = "slotgate-migrate"
    _rm_volume(volume)
    _rm_volume(LICENSE_VOLUME)
    _rm_container(LICENSE_CONTAINER)
    start_license(old_license_image, signing_key)
    define_plans()
    org = f"{ORG}-migrate"
    key = issue_key(org, PLAN_FOUR)
    engine_run(name, mode.image, volume, 18109, key)
    before_up = engine_wait_active(name, 18109)
    before_mask = mask_is_real(mask(18109, 700))[0] if before_up else False
    old_shape = admin_get("/admin/instances", org_id=org)
    # BOTH WAYS OVER ONE READ. The negative («no `slots` key») says the server
    # answering us is the old one; alone it is also satisfied by an error body,
    # a wrong org or a typo'd path. The positive says the same body is a real
    # old-shape answer that already holds this customer's instance.
    old_is_old = ("slots" not in old_shape
                  and "cooldown_seconds" in old_shape
                  and bool(old_shape.get("instances")))

    # The platform release: same database volume, new server. The engine keeps
    # running throughout.
    _rm_container(LICENSE_CONTAINER)
    start_license(new_license_image, signing_key)
    define_plans()

    still_masks = mask_is_real(mask(18109, 701))[0]
    # And then the ordinary thing a customer does next.
    sh(["docker", "stop", "-t", "20", name], False, 180)
    engine_run(name, mode.image, volume, 18109, key)
    after_up = engine_wait_active(name, 18109)
    after_mask = mask_is_real(mask(18109, 702))[0] if after_up else False

    view = admin_get("/admin/instances", org_id=org)
    log = license_logs()
    refused = refusals_on_lease(log)
    leases = lease_lines(log)

    ok = (before_up and before_mask and old_is_old and still_masks and after_up
          and after_mask and bool(leases) and not refused
          and view["occupied"] <= 1)
    return gate("G-07 a volume that lived under the OLD server is not locked, "
                "and gains no extra slots", ok,
                f"old_server_shape={'legacy' if old_is_old else 'UNEXPECTED slots'} "
                f"masked_before={before_mask} masked_across_the_swap={still_masks} "
                f"masked_after_restart={after_mask} "
                f"occupied={view['occupied']}/{view['slot_count']} "
                f"lease_refusals={len(refused)}")


# --- breaking it on purpose ------------------------------------------------


# G-07 HAS NO MUTATION THAT TURNS IT RED, AND THAT IS STATED HERE RATHER THAN
# LEFT TO BE NOTICED. Two were built and run against it and neither went red:
# `no_adopt` (the migration never seeds slots) — because slots are also created
# on demand inside `lease_generation` (`store.ensure_slots`), so a broken
# migration cannot lock anybody out; and an «adopt every open lease as a holder»
# mutant — which wrote both the slot holder and its `generations` row and still
# left `occupied` at 1. Until one of them is made to bite, G-07's verdict rests
# on its own atoms rather than on a demonstration that they can fail. The other
# six gates each go red under at least one mutation below.
MUTATIONS = {
    # The code the released fleet reads as terminal. Restoring it is Б30 exactly:
    # the fenced generation must then die instantly instead of draining.
    "answer_code": [(
        "licensing/server.py",
        'return JSONResponse(fenced, status_code=409)',
        'fenced["error"] = "instance_limit"\n        '
        'return JSONResponse(fenced, status_code=409)')],
    # No fencing at all: the ceiling stops enforcing anything.
    "no_fence": [(
        "licensing/store.py",
        'if standing["epoch"] < slot["epoch"] or slot["retired"] or mismatched:',
        'if False:')],
    # THE SEVENTH TIMER: a lease is refused the moment somebody else holds a
    # slot — variant В of §6.1, which the code leaves reachable on purpose
    # (`refusal` → `SlotRefused` → 409 `instance_limit`). This is the shape
    # attempts four, five and six died of, and it is the BROAD control for the
    # roster: every gate whose core claim is «nobody was refused» has to go red
    # under it, or that claim was never being measured.
    "lease_refuse": [
        ("licensing/store.py", '        free = [slot for slot in live if not slot["holder_start_id"]]\n        if free:\n            return {"slot_no": free[0]["slot_no"], "reason": "free", "refusal": ""}\n', '        free = [slot for slot in live if not slot["holder_start_id"]]\n        if free:\n            return {"slot_no": free[0]["slot_no"], "reason": "free",\n                    "refusal": "" if len(free) == len(live) else "instance limit"}\n'),
        ("licensing/store.py", '        return {"slot_no": ranked[0]["slot_no"], "reason": "ranked", "refusal": ""}', '        return {"slot_no": ranked[0]["slot_no"], "reason": "ranked",\n                "refusal": "instance limit"}'),
    ],
    # The LETTER of ТЗ §3.2 (free slot before own installation) — the ordering
    # `admit_generation` deliberately departs from.
    "free_first": [(
        "licensing/store.py",
        '        if mine:\n            return {"slot_no": mine[0]["slot_no"], "reason": "installation",\n'
        '                    "refusal": ""}\n        free = [slot for slot in live if not slot["holder_start_id"]]\n'
        '        if free:\n            return {"slot_no": free[0]["slot_no"], "reason": "free", "refusal": ""}',
        '        free = [slot for slot in live if not slot["holder_start_id"]]\n'
        '        if free:\n            return {"slot_no": free[0]["slot_no"], "reason": "free", "refusal": ""}\n'
        '        if mine:\n            return {"slot_no": mine[0]["slot_no"], "reason": "installation",\n'
        '                    "refusal": ""}')],
}


def build_mutant(mutation: str) -> str:
    """A licensing image with ONE thing broken, for proving the gate can fail."""
    edits = MUTATIONS[mutation]
    workdir = Path(f"/tmp/pseudex-mutant-{mutation}")
    if workdir.exists():
        shutil.rmtree(workdir)
    # `*.json` IS NOT IGNORED HERE, and that is not an oversight: the licensing
    # image needs `licensing/data/gar_types.json`, and dropping it would give a
    # mutant that fails for a reason having nothing to do with the mutation —
    # the worst possible shape for a red proof. The build context is trimmed by
    # the tree's own `.dockerignore`, which copies across with it.
    shutil.copytree(_ROOT, workdir, ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", "*.db*", "bench", "certs-slots", "certs"))
    for relative, old, new in edits:
        path = workdir / relative
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise SystemExit(f"mutation {mutation}: anchor appears "
                             f"{text.count(old)} times in {relative}, expected 1")
        path.write_text(text.replace(old, new), encoding="utf-8")
    image = f"pseudex-licensing:slots-mutant-{mutation}"
    sh(["docker", "build", "-f", "licensing/Dockerfile", "-t", image, str(workdir)],
       True, 1800)
    print(f"  mutant licensing image built: {image}")
    return image


# --- driver ----------------------------------------------------------------


VOLUMES = ["pseudex-slots-cold", "pseudex-slots-restart",
           "pseudex-slots-restart-new", "pseudex-slots-kill",
           "pseudex-slots-stop", "pseudex-slots-ceiling-a", "pseudex-slots-ceiling-b",
           "pseudex-slots-mixed-old", "pseudex-slots-mixed-new",
           "pseudex-slots-migrate"] + [f"pseudex-slots-ring-{i}" for i in range(6)]

CONTAINERS = ["slotgate-cold", "slotgate-restart", "slotgate-restart-new", "slotgate-kill", "slotgate-stop",
              "slotgate-ring", "slotgate-ceiling-a", "slotgate-ceiling-b",
              "slotgate-mixed-old", "slotgate-mixed-new", "slotgate-migrate"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--released-image",
                        default="cr.yandex/crpkutn2el1knpsbrs2d/pseudex:0.3.17",
                        help="the artifact that actually shipped")
    parser.add_argument("--released-tag", default="v0.3.17",
                        help="its release tag, used when its signing key is not at hand")
    parser.add_argument("--substitute-image", default="",
                        help="skip the tag build and reuse this image for the released engine")
    parser.add_argument("--new-image", default="",
                        help="skip the worktree build and reuse this image")
    parser.add_argument("--license-image", default="",
                        help="skip the licensing build and reuse this image")
    parser.add_argument("--old-license-image", default="",
                        help="the licensing image of the released tag, for G-07")
    parser.add_argument("--only", default="")
    parser.add_argument("--prove-red", default="",
                        choices=("", *MUTATIONS),
                        help="break the server on purpose and expect red")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    selected = {name.strip() for name in args.only.split(",") if name.strip()}

    def wanted(name: str) -> bool:
        return not selected or name in selected

    existing = os.environ.get("PSEUDEX_SIGNING_KEY", "")
    signing = (Ed25519PrivateKey.from_private_bytes(base64.b64decode(existing))
               if existing else Ed25519PrivateKey.generate())
    private_b64 = encode_private(signing)
    public_b64 = encode_public(signing.public_key())
    print(f"== stand ==\n  signing key {'from the environment' if existing else 'generated'}, "
          f"public {public_b64[:16]}…")

    certs.generate(_CERTS, "license")
    for name in CONTAINERS:
        _rm_container(name)
    tear_down(VOLUMES)

    started = time.monotonic()
    mode = resolve_released(args, private_b64, public_b64)
    print(f"  released engine under test: {mode.image}  [{mode.kind}]")
    new_image = args.new_image or build_worktree(public_b64)
    license_image = args.license_image or _build_licensing()
    if args.prove_red:
        license_image = build_mutant(args.prove_red)
        print(f"  !! PROVE-RED: the server is broken on purpose ({args.prove_red})")

    try:
        start_license(license_image, private_b64)
        define_plans()
        key_one = issue_key(ORG, PLAN_ONE)
        key_four = issue_key(f"{ORG}-four", PLAN_FOUR)
        key_four_new = issue_key(f"{ORG}-four-new", PLAN_FOUR)
        key_kill = issue_key(f"{ORG}-kill", PLAN_ONE)
        key_stop = issue_key(f"{ORG}-stop", PLAN_ONE)
        key_ceiling = issue_key(f"{ORG}-ceiling", PLAN_ONE)
        key_ring = issue_key(f"{ORG}-ring", PLAN_ONE)
        key_mixed = issue_key(f"{ORG}-mixed", PLAN_FOUR)
        if wanted("PRE-2"):
            run_gate("PRE-2", gate_pre2, ORG)

        print("== the released image meets the new server ==")
        if wanted("G-01"):
            run_gate("G-01", gate_g01, mode, key_one, ORG, "pseudex-slots-cold")
        if wanted("G-02"):
            run_gate("G-02", gate_g02, mode, new_image, key_four,
                     f"{ORG}-four", "pseudex-slots-restart", key_four_new,
                     f"{ORG}-four-new", "pseudex-slots-restart-new")
        if wanted("G-03"):
            run_gate("G-03", gate_g03, mode, key_kill, f"{ORG}-kill",
                     "pseudex-slots-kill", key_stop, f"{ORG}-stop",
                     "pseudex-slots-stop")
        if wanted("G-04"):
            run_gate("G-04", gate_g04, mode, key_ring, f"{ORG}-ring")
        if wanted("G-05"):
            run_gate("G-05", gate_g05, mode, key_ceiling, f"{ORG}-ceiling",
                     "pseudex-slots-ceiling-a", "pseudex-slots-ceiling-b")
        if wanted("G-06"):
            run_gate("G-06", gate_g06, mode, new_image, key_mixed,
                     f"{ORG}-mixed", "pseudex-slots-mixed-old",
                     "pseudex-slots-mixed-new")
        if wanted("G-07"):
            old_license = args.old_license_image or _build_licensing(args.released_tag)
            run_gate("G-07", gate_g07, mode, old_license, license_image,
                     private_b64, "pseudex-slots-migrate")
    finally:
        if not args.keep:
            for name in CONTAINERS:
                _rm_container(name)
            tear_down(VOLUMES)

    raise SystemExit(_report(started, mode, args))


def _build_licensing(tag: str = "") -> str:
    if not tag:
        image = "pseudex-licensing:slots"
        sh(["docker", "build", "-f", "licensing/Dockerfile", "-t", image, str(_ROOT)],
           True, 1800)
        return image
    workdir = Path(f"/tmp/pseudex-tag-{tag}")
    if not workdir.exists():
        workdir.mkdir(parents=True)
        archive = subprocess.run(["git", "archive", tag, "prototype"],
                                 cwd=_REPO, capture_output=True, timeout=300)
        subprocess.run(["tar", "-x", "-C", str(workdir)], input=archive.stdout,
                       check=True, timeout=300)
    image = f"pseudex-licensing:slots-{tag}"
    sh(["docker", "build", "-f", "licensing/Dockerfile", "-t", image,
        str(workdir / "prototype")], True, 1800)
    return image


def _report(started: float, mode: Mode, args) -> int:
    print("\n" + "=" * 72)
    failed = [result for result in RESULTS if not result.ok]
    for result in RESULTS:
        print(f"  {'PASS' if result.ok else 'FAIL'}  {result.name}")
    print("=" * 72)
    print(f"released engine: {mode.image}  [{mode.kind}]")
    print(f"  evidence: {mode.evidence}")
    for note in NOTES:
        print(f"  NOTE: {note}")
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} gates passed "
          f"in {(time.monotonic() - started) / 60:.1f} min")
    if not RESULTS:
        print("NO GATE RAN. Check the --only names against the roster above.")
        return 1
    if args.prove_red:
        # INVERTED ON PURPOSE. A run whose whole point is to see red reports
        # success when it saw red — and FAILS when the broken server passed
        # everything, because that is a gate that cannot fail.
        print(f"prove-red({args.prove_red}): {len(failed)} gate(s) went red "
              f"— {'the roster can fail' if failed else 'NOTHING WENT RED, the roster is decorative'}")
        return 0 if failed else 1
    return 1 if failed else 0


if __name__ == "__main__":
    main()
