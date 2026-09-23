"""The closing gate for the licensing layer: L1-L25 against a real local instance.

RULES THIS FILE OBEYS (docs/tz-license-packaging.md §4.1), because a gate that
cheats is worse than no gate:

  * No unit tests. Every scenario talks to a container over the network.
  * No mock licensing server. The stand runs the same `licensing/` image that
    would go to production, with shorter TTL/grace supplied as CONFIGURATION.
  * No test hooks in the product. Time is never faked inside the app — the clock
    rollback gate lies to the running process from OUTSIDE, with libfaketime
    injected through the environment.
  * No collateral damage to the machine. The first version of that gate used
    `cap_add: SYS_TIME` and `date -s`; the kernel does not isolate the clock per
    container, so it moved the whole Docker VM's wall clock and every unrelated
    container with it.
  * No manual step. One command, from a clean state, exit code decides.
  * Every gate proves its PRECONDITION before checking its consequence — a gate
    that passes because the container never reached the state is a false green.

usage:
    python3 e2e/gates.py                    # source image
    python3 e2e/gates.py --image pseudex:compiled          # gate P7
    python3 e2e/gates.py --only L4,L5       # a subset, for iterating

    PSEUDEX_SIGNING_KEY=... python3 e2e/gates.py --image pseudex:compiled --skip-build

The verification key is compiled into the release binary, so a fresh key means a
fresh Nuitka compile. Pass the key the image was built with, plus --skip-build,
to reuse it.
"""

import argparse
import base64
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from e2e import certs, fixtures  # noqa: E402
from licensing.keys import encode_private, encode_public  # noqa: E402

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_COMPOSE = _HERE / "compose.yml"
_ENV_FILE = _HERE / ".env"

SIDECAR = "http://127.0.0.1:18000"
UI = "http://127.0.0.1:18081"
ADMIN = "http://127.0.0.1:19443"
NETWORK = "pseudex-e2e_default"
ORG = "acme"

TTL_SECONDS = 60
GRACE_SECONDS = 120
# The ladder needs TTL + grace + one tick to be certain, plus slack for a slow
# machine. Everything that waits for expiry uses this.
EXPIRY_WAIT = TTL_SECONDS + GRACE_SECONDS + 45


@dataclass
class Result:
    name: str
    ok: bool
    detail: str


RESULTS: list[Result] = []


# --- plumbing ------------------------------------------------------------


# Учётные данные админки лицензионного сервера. Пусто — заголовка нет, и сервер
# ответит 401: ходить молча без токена хуже, чем громко не дойти.
ADMIN_TOKEN = os.environ.get("PSEUDEX_LICENSE_ADMIN_TOKEN", "e2e-admin-token")
ADMIN_AUTH = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

def sh(args: list[str], check: bool, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=check, timeout=timeout)


def sh_input(args: list[str], stdin: str, timeout: int) -> subprocess.CompletedProcess:
    """`sh`, но данные уходят через stdin, а не через командную строку.

    Нужен там, где данных много или они несут кавычки и кириллицу: вписанные в
    `sh -c` они рвут команду, и проверка молча вырождается в проверку того, что
    в неё поместилось."""
    return subprocess.run(args, input=stdin, capture_output=True, text=True,
                          check=False, timeout=timeout)


def compose(args: list[str], check: bool, timeout: int) -> subprocess.CompletedProcess:
    return sh(["docker", "compose", "-f", str(_COMPOSE), *args], check, timeout)


def logs(service: str) -> str:
    return compose(["logs", "--no-color", service], False, 60).stdout


# Some gates need a fresh stand, and `down -v` throws the logs away with it. L15
# has to see EVERY scenario's output, not just the last one, so logs are archived
# before anything is torn down.
_LOG_ARCHIVE: list[str] = []


def compose_down() -> None:
    for service in ("sidecar", "license"):
        _LOG_ARCHIVE.append(logs(service))
    compose(["down", "-v"], True, 300)


def all_logs() -> str:
    return "\n".join(_LOG_ARCHIVE) + logs("sidecar") + logs("license")


def sidecar_exec(args: list[str]) -> subprocess.CompletedProcess:
    return compose(["exec", "-T", "sidecar", *args], False, 120)


# The two credentials the stand pins in compose.yml. The product generates them
# when unset; the stand fixes them so a gate can present what a customer would
# read out of their own container log.
GATEWAY_TOKEN = "e2e-gateway-token"
ADMIN_TOKEN = "e2e-admin-token"


def gateway_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {GATEWAY_TOKEN}"}


def operator_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def post_mask(timeout: float) -> httpx.Response:
    return httpx.post(f"{SIDECAR}/mask", json=fixtures.mask_body(ORG),
                      timeout=timeout, headers=gateway_headers())


def license_state() -> dict[str, object]:
    return httpx.get(f"{SIDECAR}/license", timeout=10).json()


def license_probe() -> tuple[int, dict[str, object]]:
    """The body AND the status code.

    `license_state` reads only `.json()`, and that is how `/license` came to
    answer 503 on a healthy container for its whole life: `service.py` compared
    the state against the literal `"leased"` while the wire value of
    `STATE_LEASED` is `"active"`. L7 and L8 both assert on the body's `state`
    field, so the ladder looked correct from here while the one signal the
    documentation tells customers to alert on was stuck on.

    The code is the contract — `/health` is liveness and stays 200 while serving,
    `/license` is the alarm and goes 503 the moment the state is not LEASED — so
    it is checked at both ends of the ladder, in L4 and in L8.
    """
    response = httpx.get(f"{SIDECAR}/license", timeout=10)
    return response.status_code, response.json()


def wait_until(predicate, timeout: float, interval: float, what: str) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except (httpx.HTTPError, KeyError, ValueError):
            pass
        time.sleep(interval)
    print(f"      timed out waiting for {what} after {timeout:.0f}s")
    return False


def run_disposable_sidecar(image: str, env: dict[str, str], timeout: int,
                           flags: list[str] | None = None) -> tuple[int, str]:
    """Start a one-shot sidecar and report how it died.

    Used by the startup gates. Returns (exit_code, logs). A container still alive
    at the timeout is reported as exit code 0, which those gates treat as a
    failure — 'it kept running' is exactly what must not happen."""
    name = f"pseudex-oneshot-{int(time.monotonic() * 1000)}"
    args = ["docker", "run", "--name", name, "--network", NETWORK,
            "-v", f"{_HERE / 'certs'}:/certs:ro", *(flags or [])]
    for key, value in env.items():
        args += ["-e", f"{key}={value}"]
    args.append(image)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        code = proc.returncode
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        sh(["docker", "kill", name], False, 30)
        output = sh(["docker", "logs", name], False, 30).stdout
        code = 0  # still running at the deadline
    finally:
        sh(["docker", "rm", "-f", name], False, 30)
    return code, output


def gate(name: str, ok: bool, detail: str) -> bool:
    RESULTS.append(Result(name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")
    return ok


def run_gate(name: str, fn, *args) -> None:
    """Call one gate so that a bug IN THE GATE cannot hide the other fifteen.

    A gate that raises used to abort the whole suite: an empty sign-in token
    flowed into an Authorization header, httpx raised, and a run that had
    already proved fourteen things reported nothing but a stack trace. An
    exception here is a failure of that gate and of nothing else — and it is
    reported with its type and message, so it is still diagnosable.
    """
    try:
        fn(*args)
    except Exception as error:  # noqa: BLE001 — a gate may fail any way it likes
        gate(name, False, f"gate raised {type(error).__name__}: {error}")


# --- setup ---------------------------------------------------------------

# THE STAND RUNS ON THE ONE-SLOT PLAN, AND THAT IS THE POINT (ТЗ §9.2, G-04).
#
# It used to be "industrial", and the comment here said why: the gates start
# SEVERAL containers in sequence, the startup-refusal gates use disposable ones,
# and `docker rm -f` kills them without the graceful shutdown that would release
# their instance slot — so on the one-instance plan the healthy sidecar was
# refused with `instance_limit` and the suite stopped at SETUP. The stand was
# buying headroom to walk past the product's own defect, which means no gate
# ever ran against the plan most customers are on.
#
# Slots removed the reason: a container killed with SIGKILL holds nothing that
# has to be released, the returning installation takes ITS OWN slot back by
# identity, and a stranger takes the least recently heard one. Nothing is
# refused on a lease. Keeping "industrial" here would hide a regression of
# exactly that property, so the plan is the tightest one we sell.
_GATE_PLAN = "start"


def build_stand(image: str, workers: int, skip_build: bool) -> str:
    """Sign, certify, build, start. Returns the issued customer key."""
    print("== stand ==")
    # A fixed key can be supplied so an already-built image stays valid: the
    # verification key is compiled in, so generating a fresh one would force a
    # full Nuitka recompile of the release image on every run.
    existing = os.environ.get("PSEUDEX_SIGNING_KEY", "")
    signing_key = (Ed25519PrivateKey.from_private_bytes(base64.b64decode(existing))
                   if existing else Ed25519PrivateKey.generate())
    private_b64 = encode_private(signing_key)
    public_b64 = encode_public(signing_key.public_key())
    print(f"  signing key {'reused' if existing else 'generated'}, public {public_b64[:16]}...")
    # The tuning now travels in the lease, not the image — no tuning key to
    # seal or deliver (docs/tz-tuning-in-lease.md).

    certs.generate(_HERE / "certs", "license")
    print("  self-signed CA + server cert written")

    # THE FAKETIME MOUNT MUST EXIST BEFORE THE STAND FIRST COMES UP, owned by
    # US. `compose.yml` binds `./faketime:/faketime` for every sidecar start,
    # and when the source directory is missing Docker creates it AS ROOT. L11
    # then finds a directory it cannot write into and dies on `ts` with
    # `Permission denied` — the same shape as P6's cosign key directory, and
    # equally invisible on macOS, where Docker Desktop remaps ownership.
    # Creating it here, from the runner's own uid, is the whole fix.
    (_HERE / "faketime").mkdir(exist_ok=True)

    sh(["docker", "build", "-f", str(_ROOT / "licensing" / "Dockerfile"),
        "-t", "pseudex-licensing:e2e", str(_ROOT)], True, 1200)
    if skip_build:
        print(f"  reusing the existing {image}")
    elif image == "pseudex:source":
        # The verification key is baked in at BUILD time, as it is for a release:
        # a key the customer could override in the environment would let them
        # sign their own bundles.
        sh(["docker", "build", "-f", str(_ROOT / "Dockerfile"),
            "--build-arg", f"PSEUDEX_LICENSE_PUBKEY={public_b64}",
            "-t", image, str(_ROOT)], True, 1800)
        print(f"  images built ({image})")
    else:
        sh(["docker", "build", "-f", str(_ROOT / "Dockerfile.nuitka"),
            "--build-arg", f"PSEUDEX_LICENSE_PUBKEY={public_b64}",
            "-t", image, str(_ROOT)], True, 3600)
        print(f"  images built ({image})")

    _ENV_FILE.write_text(
        f"PSEUDEX_SIGNING_KEY={private_b64}\n"
        f"PSEUDEX_IMAGE={image}\n"
        f"PSEUDEX_KEY=\n"
        f"PSEUDEX_WORKERS={workers}\n"
        f"PSEUDEX_LEASE_TTL_SECONDS={TTL_SECONDS}\n"
        f"PSEUDEX_GRACE_SECONDS={GRACE_SECONDS}\n"
        f"PSEUDEX_FAULT_INJECT=\n"
        f"PSEUDEX_LOG_RAW_BODY=\n"
        f"PSEUDEX_LD_PRELOAD=\n"
        f"PSEUDEX_FAKETIME_FILE=\n"
        f"PSEUDEX_VAULT_ENCRYPTION=\n"
        f"PSEUDEX_VAULT_KEY=\n"
    )
    compose(["up", "-d", "license"], True, 600)
    if not wait_until(lambda: httpx.get(f"{ADMIN}/admin/list", timeout=5, headers=ADMIN_AUTH).status_code == 200,
                      120, 2, "licensing admin"):
        raise SystemExit("licensing server did not come up")

    key = httpx.post(f"{ADMIN}/admin/issue",
                     json={"org_id": ORG, "plan": _GATE_PLAN}, timeout=15, headers=ADMIN_AUTH).json()["key"]
    print(f"  key issued for {ORG}: {key[:18]}...")
    set_env("PSEUDEX_KEY", key)
    return key


def set_env(name: str, value: str) -> None:
    lines = [line for line in _ENV_FILE.read_text().splitlines()
             if not line.startswith(f"{name}=")]
    lines.append(f"{name}={value}")
    _ENV_FILE.write_text("\n".join(lines) + "\n")


def start_sidecar() -> bool:
    compose(["up", "-d", "sidecar"], True, 600)
    return wait_until(
        lambda: httpx.get(f"{SIDECAR}/health", timeout=5).json()["license"] == "active",
        180, 3, "sidecar to reach license=active",
    )


# --- gates: startup refuses ----------------------------------------------

def gate_l1(image: str) -> bool:
    code, output = run_disposable_sidecar(image, {
        "PSEUDEX_LICENSE_URL": "https://license:8443",
        "PSEUDEX_LICENSE_CA": "/certs/ca.pem",
    }, 90)
    could_ask, served = _port_probe()
    return gate("L1 no key -> refuses to start",
                code != 0 and "license_missing" in output and could_ask and not served,
                f"exit={code} license_missing={'license_missing' in output} "
                f"stand_reachable={could_ask} port_answered={served}")


def gate_l2(image: str) -> bool:
    code, output = run_disposable_sidecar(image, {
        "PSEUDEX_LICENSE_URL": "https://license:8443",
        "PSEUDEX_LICENSE_CA": "/certs/ca.pem",
        "PSEUDEX_LICENSE_KEY": "ps_live_totally_made_up_key",
    }, 90)
    return gate("L2 unknown key -> refuses to start",
                code != 0 and "license_invalid" in output,
                f"exit={code} license_invalid={'license_invalid' in output}")


def gate_l2b(image: str, key: str) -> bool:
    """The customer cannot substitute their own verification key.

    The whole signature is worthless if the key that checks it can be replaced
    from the environment: anyone could then run their own server, sign their own
    bundle, and keep a cancelled subscription alive forever. The release image
    bakes the key at build time and must ignore the environment entirely — which
    shows up as a container that starts NORMALLY even when the variable is set to
    garbage."""
    name = f"pseudex-keytest-{int(time.monotonic() * 1000)}"
    args = ["docker", "run", "-d", "--name", name, "--network", NETWORK,
            "-v", f"{_HERE / 'certs'}:/certs:ro",
            "-e", "PSEUDEX_LICENSE_URL=https://license:8443",
            "-e", "PSEUDEX_LICENSE_CA=/certs/ca.pem",
            "-e", f"PSEUDEX_LICENSE_KEY={key}",
            "-e", "PSEUDEX_LICENSE_PUBKEY=bm90LW91ci1rZXktYXQtYWxs",
            image]
    sh(args, False, 120)

    def _leased() -> bool:
        logs_now = sh(["docker", "logs", name], False, 60)
        return "lease acquired" in logs_now.stdout + logs_now.stderr

    # Polled rather than slept: a fixed wait long enough for the source image is
    # not necessarily long enough for the compiled one on a loaded machine, and
    # "we did not wait long enough" would read as "the key was rejected".
    wait_until(_leased, 180, 3, "the container to acquire a lease")
    output = sh(["docker", "logs", name], False, 60)
    running = sh(["docker", "inspect", "-f", "{{.State.Running}}", name], False, 60).stdout.strip()
    combined = output.stdout + output.stderr
    sh(["docker", "rm", "-f", name], False, 60)
    ok = running == "true" and "lease acquired" in combined
    return gate("L2b baked verification key ignores the environment", ok,
                f"running={running} leased={'lease acquired' in combined}")


def gate_l3(image: str, key: str) -> bool:
    compose(["stop", "license"], True, 120)
    try:
        code, output = run_disposable_sidecar(image, {
            "PSEUDEX_LICENSE_URL": "https://license:8443",
            "PSEUDEX_LICENSE_CA": "/certs/ca.pem",
            "PSEUDEX_LICENSE_KEY": key,
        }, 150)
    finally:
        compose(["start", "license"], True, 120)
        wait_until(lambda: httpx.get(f"{ADMIN}/admin/list", timeout=5, headers=ADMIN_AUTH).status_code == 200,
                   120, 2, "licensing admin back up")
    return gate("L3 cold start with our server down -> refuses (no grace)",
                code != 0 and "bundle_unavailable" in output,
                f"exit={code} bundle_unavailable={'bundle_unavailable' in output}")


def _port_probe() -> tuple[bool, bool]:
    """(the stand was reachable at all, the sidecar port answered).

    A bare `except HTTPError: return False` cannot separate "the container
    refused to serve, exactly as the gate demands" from "we asked the wrong
    address" or "the machine was too busy to answer in three seconds" — and both
    gates that read this assert the NEGATIVE, so the second reading is a false
    pass on the two gates that prove a container REFUSES to start. The licensing
    admin is up throughout both, so it is asked as a control: if it does not
    answer either, nothing was learned about the sidecar and the caller is told
    so rather than handed a comfortable False.
    """
    try:
        httpx.get(f"{SIDECAR}/health", timeout=3)
        return True, True
    except httpx.HTTPError:
        pass
    try:
        httpx.get(f"{ADMIN}/admin/list", timeout=5, headers=ADMIN_AUTH)
    except httpx.HTTPError:
        return False, False
    return True, False


# --- gates: healthy ------------------------------------------------------

def gate_l4() -> bool:
    health = httpx.get(f"{SIDECAR}/health", timeout=15).json()
    response = post_mask(90)
    masked = json.dumps(response.json(), ensure_ascii=False)
    leaked = [value for value in fixtures.PII_PAYLOAD.values() if value in masked]

    # Round trip: what the tool would receive must be the ORIGINAL surface form.
    content = response.json()["messages"][0]["content"]
    restored = httpx.post(f"{SIDECAR}/unmask", timeout=60, headers=gateway_headers(), json={
        "org_id": ORG, "response": {"choices": [{"message": {"content": content}}]},
    }).json()["response"]["choices"][0]["message"]["content"]
    round_tripped = [value for value in fixtures.PII_PAYLOAD.values() if value in restored]

    # The alarm endpoint must be SILENT while everything is fine. Checked here
    # rather than in its own gate because "healthy" is exactly what L4 sets up,
    # and an alarm that cannot be off is as useless as one that cannot fire.
    licence_code, licence_body = license_probe()

    ok = (health.get("license") == "active" and response.status_code == 200
          and licence_code == 200 and not leaked and len(round_tripped) >= 6)
    return gate("L4 happy path masks and round-trips", ok,
                f"health={health.get('license')} leaked={leaked} "
                f"restored={len(round_tripped)}/{len(fixtures.PII_PAYLOAD)} "
                f"license={licence_code}/{licence_body.get('state')}")



def gate_l18() -> bool:
    """The STREAMING leg, in the container, both halves and the wrong one refused.

    L4 proves the non-streamed path only, so a container could ship with the
    streaming endpoints missing, or broken by packaging, and pass every gate we
    had. That surface is what a host gateway actually uses on a live answer.

    Two halves, and they behave oppositely on purpose:

      * `delta.content` -> /unmask_chunk, fed in pieces that SPLIT a token, which
        is the case the carry buffer exists for;
      * a tool call's arguments -> /unmask_arguments, whose whole reason to exist
        is that a real value carrying quotes breaks a JSON object when
        substituted as flat text.

    Both are asserted, and so is the failure of the wrong path: routing arguments
    through /unmask_chunk must still produce something unparseable. That is the
    tempting simplification, and a gate that only checked the good path would not
    notice it being taken.
    """
    real = 'ООО "Заря"'
    masked = httpx.post(f"{SIDECAR}/mask", timeout=60, headers=gateway_headers(), json={
        "org_id": ORG, "messages": [{"role": "user", "content": f"получатель: {real}"}],
    }).json()["messages"][0]["content"]
    fake = masked.split(": ", 1)[1] if ": " in masked else masked

    # A phone, split across two deltas, through the text leg.
    phone_masked = httpx.post(f"{SIDECAR}/mask", timeout=60, headers=gateway_headers(), json={
        "org_id": ORG, "messages": [{"role": "user", "content": "телефон +7 999 123-45-67"}],
    }).json()["messages"][0]["content"]
    token = re.search(r"\+7\d{10}", phone_masked.replace(" ", "").replace("-", ""))
    fake_phone = phone_masked.split("телефон ", 1)[1].strip() if "телефон " in phone_masked else ""
    carry, streamed = "", ""
    for delta in ("Перезвоню на ", fake_phone[:5], fake_phone[5:], " завтра"):
        body = httpx.post(f"{SIDECAR}/unmask_chunk", timeout=30, headers=gateway_headers(),
                          json={"org_id": ORG, "delta": delta, "carry": carry}).json()
        streamed += body["text"]
        carry = body["carry"]
    tail = httpx.post(f"{SIDECAR}/unmask_chunk", timeout=30, headers=gateway_headers(),
                      json={"org_id": ORG, "delta": "", "carry": carry, "flush": True}).json()
    streamed += tail["text"]

    arguments = json.dumps({"company": fake}, ensure_ascii=False)
    restored = httpx.post(f"{SIDECAR}/unmask_arguments", timeout=30, headers=gateway_headers(),
                          json={"org_id": ORG, "arguments": [arguments]}).json()["arguments"][0]
    try:
        parsed_ok = json.loads(restored).get("company") == real
    except json.JSONDecodeError:
        parsed_ok = False

    flat = httpx.post(f"{SIDECAR}/unmask_chunk", timeout=30, headers=gateway_headers(),
                      json={"org_id": ORG, "delta": arguments, "carry": "",
                            "flush": True}).json()["text"]
    try:
        json.loads(flat)
        text_leg_refuses = False
    except json.JSONDecodeError:
        text_leg_refuses = True

    split_ok = ("+7 999 123-45-67" in streamed and fake_phone not in streamed
                and tail["carry"] == "")
    ok = split_ok and parsed_ok and text_leg_refuses and token is not None
    return gate("L18 streaming leg: split token and tool arguments", ok,
                f"split_restored={split_ok} arguments_parse={parsed_ok} "
                f"text_leg_refuses_json={text_leg_refuses}")


def gate_l5() -> bool:
    marker = fixtures.marker_surname()
    for _ in range(20):
        post_mask(90)

    # `docker diff` is the strong check and it covers the WHOLE image: anything
    # the process created or modified anywhere shows up here. /data is the vault
    # volume and is expected to change; the rest must not.
    container_id = compose(["ps", "-q", "sidecar"], False, 30).stdout.strip().splitlines()[0]
    # `check=False`, so a diff that fails returns an empty stdout — and an empty
    # diff reads as "the container created nothing", which is the verdict this
    # gate exists to reach. The exit code is the only thing that separates the
    # two, so it is carried into the verdict.
    diff_proc = sh(["docker", "diff", container_id], False, 120)
    changed = diff_proc.stdout
    # Deliberately narrow ignore list, so this stays a real check: /data is the
    # vault volume, /certs is the stand's read-only mount, and the
    # ca-certificates entry is injected by the local Docker provider (OrbStack).
    # Anything else appearing in the container's filesystem is a finding — which
    # is why the image sets PYTHONDONTWRITEBYTECODE, so bytecode caches do not
    # bury one in 80 lines of noise.
    # /faketime is the stand's own mount for gate L11's libfaketime injection.
    ignored = ("/data", "/tmp", "/run", "/certs", "/faketime",
               # The local Docker provider (OrbStack) injects its own root CA into
               # every container it starts. Matched by these exact paths rather
               # than by ignoring /etc wholesale, so a file written under /etc by
               # the engine would still be caught.
               "/usr/local/share/ca-certificates", "/etc/ssl/certs/orbstack-root.crt",
               "/etc/ca-certificates/trust-source")
    outside_data = [
        line for line in changed.splitlines()
        if line.split(" ", 1)[0] == "A" and not line.split(" ", 1)[-1].startswith(ignored)
    ]

    # Then a content grep of every writable location, for the marker that exists
    # ONLY in the leased dictionary. Scoped to real directories rather than `/`:
    # a full-root walk spends its time in /proc and /sys, which are not files the
    # process could have written the bundle to.
    found = sidecar_exec(["sh", "-c",
                          f"grep -rlF '{marker}' /app /data /tmp /var /etc /root /home /usr "
                          f"2>/dev/null | head -5 || true"]).stdout.strip()
    data_dir = sidecar_exec(["sh", "-c", "ls /app/pseudex/data 2>&1 || true"]).stdout

    ok = (diff_proc.returncode == 0 and not found and not outside_data
          and "No such file" in data_dir)
    return gate("L5 bundle never touches disk", ok,
                f"diff_ran={diff_proc.returncode == 0} marker_on_disk={found or 'none'} "
                f"changed_outside_data={len(outside_data)} "
                f"data_dir_absent={'No such file' in data_dir}")


def gate_l6() -> bool:
    """Renewal must be invisible: no failed request, and the SAME token for the
    same input across it — a token that moved would mean the bundle changed."""
    before = post_mask(90).json()["messages"][0]["content"]
    start_renewals = logs("sidecar").count("lease renewed")
    # Two independent signals, because they fail differently: the log proves the
    # customer can SEE renewals happening, and the lease id proves they actually
    # ARE. The first run of this gate had renewals working perfectly and the log
    # completely silent.
    first_lease = license_state()["lease_id"]
    errors = 0
    calls = 0
    deadline = time.monotonic() + TTL_SECONDS * 4 + 30
    while time.monotonic() < deadline:
        try:
            if post_mask(90).status_code != 200:
                errors += 1
        except httpx.HTTPError:
            errors += 1
        calls += 1
        time.sleep(2)
    after = post_mask(90).json()["messages"][0]["content"]
    renewals = logs("sidecar").count("lease renewed") - start_renewals
    last_lease = license_state()["lease_id"]

    ok = renewals >= 3 and last_lease != first_lease and errors == 0 and before == after
    return gate("L6 renewal is invisible and tokens are stable", ok,
                f"renewals_logged={renewals} lease_id_changed={last_lease != first_lease} "
                f"calls={calls} errors={errors} token_stable={before == after}")


_LEASED_RSS_KB = 0
_LEASED_PIDS: set[int] = set()


def worker_pids(probes: int) -> set[int]:
    """Which worker processes are answering right now.

    A SET, not one PID. The container runs N workers behind one SO_REUSEPORT
    socket, so consecutive /health calls are answered by different processes —
    comparing a single pid across two moments reports a change that is just the
    kernel balancing, and L14b failed on exactly that. What the gate actually
    wants to know is whether the workers that were serving are still serving."""
    seen: set[int] = set()
    for _ in range(probes):
        try:
            seen.add(int(httpx.get(f"{SIDECAR}/health", timeout=10).json()["pid"]))
        except (httpx.HTTPError, KeyError, ValueError):
            continue
    return seen


def gate_l14a() -> bool:
    """Precondition for L14b: while leased, the marker IS in the worker's memory
    and the scanner can see it. Without this, L14b's verdict would be worthless —
    a scanner that can never find anything reports every process as clean."""
    global _LEASED_RSS_KB, _LEASED_PIDS
    hits, _LEASED_RSS_KB = _memscan()
    _LEASED_PIDS = worker_pids(24)
    return gate("L14a marker present in memory while leased", hits > 0,
                f"regions={hits} rss={_LEASED_RSS_KB // 1024}MB "
                f"workers={sorted(_LEASED_PIDS)}")


def _memscan() -> tuple[int, int]:
    """(regions containing the marker, total RSS in KB) across the workers."""
    marker = fixtures.marker_surname()
    container_id = compose(["ps", "-q", "sidecar"], False, 30).stdout.strip().splitlines()[0]
    proc = sh(["docker", "run", "--rm", f"--pid=container:{container_id}",
               "--cap-add=SYS_PTRACE", "-v", f"{_HERE}:/e2e:ro",
               # "serve" matches both shapes of the worker: `python serve_main.py`
               # in the source image and `./pseudex-serve` in the compiled one.
               "python:3.12-slim", "python", "/e2e/memscan.py", marker, "serve"], False, 300)
    hits = re.search(r"HITS (\d+)", proc.stdout)
    rss = re.search(r"RSS_KB (\d+)", proc.stdout)
    if hits is None:
        print(f"      memscan produced no verdict: {proc.stdout.strip()} "
              f"{proc.stderr.strip()[:200]}")
        return -1, 0
    return int(hits.group(1)), int(rss.group(1)) if rss else 0


# --- gates: degradation --------------------------------------------------

def gate_l7() -> bool:
    """Our outage: every worker goes STALE, and stale still serves.

    TWO READS, TWO WORKERS. The stand runs four workers on one SO_REUSEPORT
    port, and each holds its own lease with its own clock: they were leased a
    few seconds apart at start-up, so they go stale a few seconds apart too.
    `wait_until` on `/license` returns the moment the FIRST worker says stale;
    a single `/health` read a second later may land on a worker still inside
    its TTL and say `active` — which is what one release run printed
    (`stale=True health=active`) after three green ones. Neither answer was
    wrong; the gate compared two workers and called the difference a defect.

    So the gate waits until EVERY worker has answered `/health` with stale —
    `/health` names its pid, and the set of workers is what `worker_pids`
    already collects — with its own budget: the spread between workers is
    bounded by one renewal period (< TTL), and the stale window is
    GRACE_SECONDS, so waiting up to TTL_SECONDS here cannot run into EXPIRED.
    The mask call comes AFTER that — «stale still serves» is the claim, and it
    must be made against a worker that is stale."""
    compose(["stop", "license"], True, 120)
    workers = worker_pids(24)
    reached_stale = wait_until(lambda: license_state()["state"] == "stale",
                               TTL_SECONDS + 40, 3, "state=stale")
    stale_pids: set[int] = set()

    def every_worker_stale() -> bool:
        body = httpx.get(f"{SIDECAR}/health", timeout=15).json()
        if body.get("license") == "stale":
            stale_pids.add(int(body["pid"]))
        return workers <= stale_pids

    all_stale = wait_until(every_worker_stale, TTL_SECONDS, 0.5,
                           f"/health license=stale from all {len(workers)} workers")
    status = post_mask(90).status_code
    warned = "license STALE" in logs("sidecar")
    ok = reached_stale and bool(workers) and all_stale and status == 200 and warned
    return gate("L7 our outage -> grace, still serving", ok,
                f"stale={reached_stale} workers={len(workers)} stale_workers={len(stale_pids)} "
                f"mask={status} warned={warned}")


def gate_l8() -> bool:
    reached = wait_until(lambda: license_state()["state"] == "expired",
                         EXPIRY_WAIT, 5, "state=expired")
    response = post_mask(90)
    body = response.json()
    health = httpx.get(f"{SIDECAR}/health", timeout=15)
    # The other end of the contract L4 checks: here the alarm MUST fire.
    licence_code, licence_body = license_probe()
    assets = licence_body["assets_loaded"]
    leaked = [v for v in fixtures.PII_PAYLOAD.values() if v in json.dumps(body, ensure_ascii=False)]
    ok = (reached and response.status_code == 503 and health.status_code == 503
          and licence_code == 503 and assets is False and not leaked)
    return gate("L8 grace exhausted -> 503, assets unloaded", ok,
                f"expired={reached} mask={response.status_code} health={health.status_code} "
                f"license={licence_code} assets_loaded={assets} error={body.get('error')}")


def gate_l14b() -> bool:
    """The assets were GIVEN UP by a process that is still alive and healthy.

    That is the distinction worth testing. A process that died would REFUSE THE
    CONNECTION; a genuine unload produces a live process that still ANSWERS — with
    a structured 503, not a dropped socket — while: same workers still running,
    registry reporting nothing loaded, and every asset-backed endpoint (mask,
    spans, AND unmask) refusing 503.

    /unmask 503s here too, by decision (pentest B3): detok recognises tokens with
    the LEASED bundle (`token_re`, version-keyed since WS-2 moved the tuning to the
    lease), so with assets unloaded it cannot run. The reversible-PII promise holds
    throughout LEASED + the whole grace window; EXPIRED is terminal and the engine
    is off. Liveness is proved by the process ANSWERING (503, not a refused socket)
    and the workers surviving — not by unmask returning 200.

    TWO THINGS THIS DELIBERATELY DOES NOT CLAIM, because neither is true:

      * that the marker's bytes are gone from the address space. `free()` does
        not scrub, so freed pages keep their contents until the allocator reuses
        them. Asserting byte-absence gave a gate that passed or failed depending
        on how much unrelated traffic had churned the heap — it measured luck.
      * that RSS drops by the size of the gazetteers. Measured: 490 MB -> 487 MB.
        CPython's allocator returns an arena to the OS only when it is entirely
        free, and 225k small strings are spread across arenas that also hold live
        objects. The memory is available for reuse, not returned.

    Both were assumptions written before measuring; the numbers say otherwise, so
    the claims go rather than the numbers."""
    hits, rss = _memscan()
    state = license_state()
    masked = post_mask(90)
    spans = httpx.post(f"{SIDECAR}/spans", timeout=60, headers=gateway_headers(),
                       json={"org_id": ORG, "texts": ["Иван Петров"]})
    # A live process ANSWERS (503) where a dead one refuses the socket — this is
    # what separates "gave up the assets" from "the process fell over".
    still_alive = worker_pids(24)
    unmasked = httpx.post(f"{SIDECAR}/unmask", timeout=60, headers=gateway_headers(), json={
        "org_id": ORG, "response": {"choices": [{"message": {"content": "нет токенов"}}]},
    })
    # Every worker that was serving must still be serving: none of them died to
    # produce this state, they gave the assets up and stayed.
    workers_intact = bool(_LEASED_PIDS) and _LEASED_PIDS <= still_alive
    # unmask 503 too (B3): detok needs the leased bundle, gone with the assets.
    ok = (state["assets_loaded"] is False
          and masked.status_code == 503 and spans.status_code == 503
          and unmasked.status_code == 503 and workers_intact)
    return gate("L14b assets given up by a live process", ok,
                f"assets_loaded={state['assets_loaded']} mask={masked.status_code} "
                f"spans={spans.status_code} unmask={unmasked.status_code} "
                f"workers {sorted(_LEASED_PIDS)}->{sorted(still_alive)} "
                f"| observed only: rss {_LEASED_RSS_KB // 1024}->{rss // 1024}MB, "
                f"{hits} freed-heap remnant region(s)")


def gate_l9() -> bool:
    pid_before = sidecar_exec(["sh", "-c", "echo $$"]).stdout.strip()
    started = compose(["ps", "-q", "sidecar"], False, 30).stdout.strip()
    compose(["start", "license"], True, 120)
    recovered = wait_until(lambda: post_mask(90).status_code == 200,
                           TTL_SECONDS * 3, 5, "mask to work again")
    same_container = compose(["ps", "-q", "sidecar"], False, 30).stdout.strip() == started
    restarts = sh(["docker", "inspect", "-f", "{{.RestartCount}}", started], False, 30).stdout.strip()
    ok = recovered and same_container and restarts == "0"
    return gate("L9 recovers without a restart", ok,
                f"recovered={recovered} same_container={same_container} restarts={restarts} "
                f"pid_probe={pid_before != ''}")


_FAKETIME_DIR = _HERE / "faketime"
_FAKETIME_SO = "/faketime/libfaketime.so.1"
_FAKETIME_TS = _FAKETIME_DIR / "ts"


def prepare_faketime() -> bool:
    """Extract libfaketime from a Debian image into a directory the stand mounts.

    Injected, not baked in: the image under test must stay byte-identical to the
    one that ships. This also models the threat honestly — someone who wants free
    grace controls the container's environment, not our Dockerfile."""
    _FAKETIME_DIR.mkdir(exist_ok=True)
    # A DIRECTORY WE CANNOT WRITE INTO IS A FAILED GATE WITH A NAMED CAUSE,
    # not a traceback. `build_stand` creates it first so this should not
    # happen; if it does anyway (a stale root-owned directory from an older
    # run), a root container can hand it back, and the gate says so.
    if not os.access(_FAKETIME_DIR, os.W_OK):
        print("      faketime/ is not writable (root-owned by an earlier docker run) — repairing")
        sh(["docker", "run", "--rm", "-v", f"{_FAKETIME_DIR}:/out", "alpine:3.21",
            "chmod", "777", "/out"], False, 120)
    if not os.access(_FAKETIME_DIR, os.W_OK):
        print("      faketime/ still not writable")
        return False
    if not (_FAKETIME_DIR / "libfaketime.so.1").exists():
        result = sh(["docker", "run", "--rm", "-v", f"{_FAKETIME_DIR}:/out",
                     "debian:12-slim", "sh", "-c",
                     "apt-get update -qq >/dev/null 2>&1 && "
                     "apt-get install -y -qq faketime >/dev/null 2>&1 && "
                     "cp \"$(find / -name 'libfaketime.so.1' 2>/dev/null | head -1)\" /out/ && "
                     "chmod 644 /out/libfaketime.so.1"], False, 900)
        if result.returncode != 0:
            print(f"      could not extract libfaketime: {result.stderr.strip()[:200]}")
    _FAKETIME_TS.write_text("+0\n")
    return (_FAKETIME_DIR / "libfaketime.so.1").exists()


def gate_l11() -> bool:
    """Winding the wall clock back must not buy grace.

    Grace is counted with `time.monotonic()`, which the kernel will not move
    backwards, and a restart discards the in-memory bundle and needs a fresh
    lease — so there is no persisted expiry to edit. This gate proves that from
    the outside, by actually lying to the process about what time it is."""
    if not prepare_faketime():
        return gate("L11 clock rollback does not extend grace", False,
                    "libfaketime unavailable — the scenario could not be run")

    _FAKETIME_TS.write_text("+0\n")
    set_env("PSEUDEX_LD_PRELOAD", _FAKETIME_SO)
    set_env("PSEUDEX_FAKETIME_FILE", "/faketime/ts")
    compose(["up", "-d", "--force-recreate", "sidecar"], True, 600)
    if not wait_until(lambda: license_state()["state"] == "active", 240, 3,
                      "sidecar active under libfaketime"):
        _clear_faketime()
        return gate("L11 clock rollback does not extend grace", False,
                    "sidecar did not start with libfaketime preloaded")

    # Prove the lie actually lands, otherwise a passing gate would only mean
    # "nothing happened".
    before = sidecar_exec(["date", "-u", "+%s"]).stdout.strip()
    compose(["stop", "license"], True, 120)
    if not wait_until(lambda: license_state()["state"] == "stale",
                      TTL_SECONDS + 40, 3, "state=stale before the clock moves"):
        compose(["start", "license"], True, 120)
        _clear_faketime()
        return gate("L11 clock rollback does not extend grace", False, "never reached stale")

    _FAKETIME_TS.write_text("-72h\n")
    time.sleep(3)
    after = sidecar_exec(["date", "-u", "+%s"]).stdout.strip()
    moved = (before.isdigit() and after.isdigit()
             and int(before) - int(after) > 60 * 60 * 71)

    expired = wait_until(lambda: license_state()["state"] == "expired",
                         EXPIRY_WAIT, 5, "state=expired despite the clock going backwards")

    _FAKETIME_TS.write_text("+0\n")
    compose(["start", "license"], True, 120)
    _clear_faketime()
    wait_until(lambda: post_mask(90).status_code == 200, TTL_SECONDS * 3, 5, "recovery")
    return gate("L11 clock rollback does not extend grace", moved and expired,
                f"clock_moved_back={moved} ({before}->{after}) expired_on_time={expired}")


def _clear_faketime() -> None:
    set_env("PSEUDEX_LD_PRELOAD", "")
    set_env("PSEUDEX_FAKETIME_FILE", "")
    compose(["up", "-d", "--force-recreate", "sidecar"], False, 600)
    wait_until(lambda: license_state()["state"] in ("active", "stale", "expired"),
               240, 3, "sidecar back without libfaketime")


def gate_l10() -> bool:
    """Revocation is an ANSWER, not an outage: it must bypass grace entirely."""
    if not wait_until(lambda: license_state()["state"] == "active", 120, 3, "active before revoke"):
        return gate("L10 revocation bypasses grace", False, "sidecar was not active")
    httpx.post(f"{ADMIN}/admin/revoke", json={"org_id": ORG}, timeout=15, headers=ADMIN_AUTH)
    revoked_at = time.monotonic()
    stopped = wait_until(lambda: post_mask(90).status_code == 503,
                         TTL_SECONDS * 2 + 30, 3, "mask to start refusing")
    elapsed = time.monotonic() - revoked_at
    state = license_state()
    # The whole point: it must NOT have taken the grace window.
    bypassed_grace = elapsed < GRACE_SECONDS
    revoked_ok = stopped and bypassed_grace and state.get("code") == "license_revoked"

    # AND IT MUST COME BACK. Paying an invoice cannot require restarting every
    # container, so the licence thread has to survive the terminal state and keep
    # asking. This half is not decoration: the loop referenced an undefined
    # constant on exactly this path, so the thread died of a NameError the moment
    # a licence was revoked. Everything the gate checked above still passed —
    # `_terminal_code` is set before the crash and the state is read from it — so
    # a dead renewal thread looked identical to a healthy one from outside.
    container_before = compose(["ps", "-q", "sidecar"], False, 30).stdout.strip()
    httpx.post(f"{ADMIN}/admin/resume", json={"org_id": ORG}, timeout=15, headers=ADMIN_AUTH)
    recovered = wait_until(lambda: post_mask(90).status_code == 200,
                           TTL_SECONDS * 4, 5, "service to resume after payment")
    same_container = compose(["ps", "-q", "sidecar"], False, 30).stdout.strip() == container_before

    ok = revoked_ok and recovered and same_container
    return gate("L10 revocation bypasses grace, payment restores without restart", ok,
                f"stopped_after={elapsed:.0f}s (grace={GRACE_SECONDS}s) "
                f"code={state.get('code')} recovered={recovered} "
                f"same_container={same_container}")


# --- gates: integrity and counters ---------------------------------------

_SIGNIN_URL_RE = re.compile(r"https?://[^\s]+/\?\w+=([^\s&]+)")


def ui_signin_token() -> str:
    """The sign-in token, read the way the customer is told to read it.

    Returns "" when the line is absent, and the callers report that as a plain
    failure. The first version let the empty string flow into an Authorization
    header, where httpx raised `Illegal header value b'Bearer '` — the gate died
    mid-suite and took every result after it with it, so a real product bug (the
    UI process had no logging configuration, and the line was never printed)
    surfaced as a stack trace instead of as the FAIL that names it.
    """
    # THE PARAMETER NAME IS NOT HARDCODED, and that is the whole repair. The
    # gate looked for «?token=»; the interface prints «?secret=» and has for a
    # while, so L16 and L17 failed with "no sign-in url in the container log"
    # while the product worked perfectly. A gate that names an implementation
    # detail goes stale the first time that detail is renamed, and then reports
    # a healthy product as broken — which is how a red suite teaches people to
    # ignore it.
    #
    # Anchored on the URL instead: the customer is told to look for a link, so
    # the gate looks for one and takes its query value, whatever it is called.
    for line in logs("sidecar").splitlines():
        match = _SIGNIN_URL_RE.search(line)
        if match:
            return match.group(1).strip()
    return ""


def ui_session() -> tuple[str, str]:
    """(session, why_not). Never raises, never returns a half-usable header."""
    token = ui_signin_token()
    if not token:
        return "", "no sign-in url in the container log"
    response = httpx.post(f"{UI}/api/signin", timeout=15, json={"secret": token})
    if response.status_code != 200:
        return "", f"signin returned {response.status_code}"
    session = response.json().get("session", "")
    return (session, "") if session else ("", "signin returned no session")


def gate_l16() -> bool:
    """The operator interface, in the real container, end to end.

    Three things that only a container can prove, because each of them is a
    property of how the image is assembled rather than of the code:

      * the page and its files actually SHIPPED — the release image builds them
        into /app/ui by a different mechanism than the source image, and a
        missing --include-data-dir shows up here and nowhere else;
      * the sign-in token is discoverable the way the customer is told to find
        it, by reading the container log;
      * one operator token is shared by every worker. With SO_REUSEPORT the
        kernel moves consecutive calls between processes, so a per-process token
        passes any single-request check and then 401s in production.
    """
    page = httpx.get(f"{UI}/", timeout=15)
    assets = [httpx.get(f"{UI}/static/{name}", timeout=15)
              for name in ("app.js", "app.css", "vendor/preact.mjs")]
    anonymous = httpx.get(f"{UI}/api/engine/status", timeout=15)

    # The customer's own instruction is "read the log", so the gate reads it.
    session, why_not = ui_session()
    if not session:
        return gate("L16 operator interface works in the container", False,
                    f"page={page.status_code} anon={anonymous.status_code} "
                    f"could_not_sign_in={why_not}")
    auth = {"Authorization": f"Bearer {session}"}

    # Ten calls, because one proves nothing about a per-worker token: the point
    # is that the kernel hands these to different processes and every one of
    # them accepts the same credential.
    codes = {httpx.get(f"{UI}/api/engine/status", timeout=30, headers=auth,
                       params={"org_id": ORG}).status_code for _ in range(10)}
    body = httpx.get(f"{UI}/api/engine/status", timeout=30, headers=auth,
                     params={"org_id": ORG}).json() if codes == {200} else {}
    workers = {process["pid"] for process in body.get("engine", {}).get("processes", [])}

    ok = (page.status_code == 200 and all(a.status_code == 200 for a in assets)
          and anonymous.status_code == 401 and codes == {200}
          and len(workers) >= 2)
    return gate("L16 operator interface works in the container", ok,
                f"page={page.status_code} assets={[a.status_code for a in assets]} "
                f"anon={anonymous.status_code} signed_in=True "
                f"status_codes={sorted(codes)} workers_seen={len(workers)}")


def gate_l17() -> bool:
    """A reveal through the interface is recorded, and the record cannot lie.

    The access log is the thing that keeps this product from handing the
    customer an unaudited disclosure channel, so the gate checks the property
    that makes it worth having: the actor is stamped by the server, not chosen
    by whoever is at the keyboard.
    """
    session, why_not = ui_session()
    if not session:
        return gate("L17 reveals are audited and the actor cannot be forged",
                    False, f"could_not_sign_in={why_not}")
    auth = {"Authorization": f"Bearer {session}"}

    events = httpx.get(f"{UI}/api/engine/events", timeout=30, headers=auth,
                       params={"org_id": ORG, "limit": 5}).json()
    if not events.get("events"):
        return gate("L17 reveals are audited and the actor cannot be forged",
                    False, "no events in the log to reveal")
    target = events["events"][0]

    revealed = httpx.post(f"{UI}/api/engine/reveal", timeout=30, headers=auth, json={
        "org_id": ORG, "token": target["token"], "actor": "кто-то другой",
    })
    log = httpx.get(f"{UI}/api/engine/reveals", timeout=30, headers=auth,
                    params={"org_id": ORG}).json()
    latest = log.get("reveals", [{}])[0]
    value = revealed.json().get("value") if revealed.status_code == 200 else None

    # Straight at the engine, with no operator token: the disclosure endpoint
    # must not be open to anything that can merely reach the port.
    direct = httpx.post(f"{SIDECAR}/reveal", timeout=15,
                        json={"org_id": ORG, "token": target["token"], "actor": "x"})

    ok = (revealed.status_code == 200 and value
          and latest.get("actor", "").startswith("ui:")
          and latest.get("actor") != "кто-то другой"
          and str(value) not in json.dumps(log, ensure_ascii=False)
          and direct.status_code == 401)
    return gate("L17 reveals are audited and the actor cannot be forged", ok,
                f"reveal={revealed.status_code} actor={latest.get('actor')!r} "
                f"value_in_log={str(value) in json.dumps(log, ensure_ascii=False)} "
                f"unauthenticated_direct={direct.status_code}")


def gate_l13(image: str) -> bool:
    """A broken bundle must stop the process, not half-configure the detector."""
    compose_down()
    set_env("PSEUDEX_FAULT_INJECT", "corrupt_bundle")
    compose(["up", "-d", "license"], True, 600)
    wait_until(lambda: httpx.get(f"{ADMIN}/admin/list", timeout=5, headers=ADMIN_AUTH).status_code == 200,
               120, 2, "licensing admin")
    key = httpx.post(f"{ADMIN}/admin/issue",
                     json={"org_id": ORG, "plan": _GATE_PLAN}, timeout=15, headers=ADMIN_AUTH).json()["key"]
    code, output = run_disposable_sidecar(image, {
        "PSEUDEX_LICENSE_URL": "https://license:8443",
        "PSEUDEX_LICENSE_CA": "/certs/ca.pem",
        "PSEUDEX_LICENSE_KEY": key,
    }, 150)
    set_env("PSEUDEX_FAULT_INJECT", "")
    ok = code != 0 and "bundle_corrupt" in output
    return gate("L13 corrupt bundle -> refuses, never degrades", ok,
                f"exit={code} bundle_corrupt={'bundle_corrupt' in output}")


def gate_l12() -> bool:
    """Counters must reach us, match the sidecar, and carry no personal data."""
    compose_down()
    set_env("PSEUDEX_LOG_RAW_BODY", "1")
    compose(["up", "-d", "license"], True, 600)
    wait_until(lambda: httpx.get(f"{ADMIN}/admin/list", timeout=5, headers=ADMIN_AUTH).status_code == 200,
               120, 2, "licensing admin")
    key = httpx.post(f"{ADMIN}/admin/issue",
                     json={"org_id": ORG, "plan": _GATE_PLAN}, timeout=15, headers=ADMIN_AUTH).json()["key"]
    set_env("PSEUDEX_KEY", key)
    if not start_sidecar():
        return gate("L12 counters match and carry no PII", False, "sidecar did not start")

    calls = 12
    for _ in range(calls):
        post_mask(90)
    # /usage is on the OPERATOR surface now: it lists tokens and previews, which
    # is the same disclosure /events makes, and it was the one endpoint the
    # closing of that surface missed.
    local = httpx.get(f"{SIDECAR}/usage", params={"org_id": ORG}, timeout=30,
                      headers=operator_headers()).json()

    # Counters ride on the renewal, so wait for one to happen — specifically for
    # one carrying DATA. Waiting merely for "a report arrived" fires on the first
    # renewal, which legitimately reports zero because it happens before any
    # traffic; the gate then read those zeros and called it a failure.
    # `> 0` WAS THE WHOLE ASSERTION, AND IT GUARDS THE INVOICE. Twelve calls
    # were made and any non-zero number passed, so an engine reporting one
    # request in twelve — the exact fraud this gate exists to make impossible —
    # cleared it. The wait is for the counter to REACH the number we produced,
    # and the verdict then demands equality: if the accounting is per-report
    # rather than a running total the wait times out and the gate goes red with
    # the real number in the detail, which is the outcome worth having.
    reported = wait_until(
        lambda: httpx.get(f"{ADMIN}/admin/usage", params={"org_id": ORG},
                          timeout=15, headers=ADMIN_AUTH).json()["usage"]["requests"] >= calls,
        TTL_SECONDS * 4, 5, "a usage report carrying every request we made",
    )
    remote = httpx.get(f"{ADMIN}/admin/usage", params={"org_id": ORG}, timeout=15, headers=ADMIN_AUTH).json()

    raw_bodies = "\n".join(line for line in logs("license").splitlines()
                           if "RAW_LEASE_BODY" in line)
    # PRECONDITION: a body was actually logged. `PSEUDEX_LOG_RAW_BODY` is set
    # from outside, and if it does not reach the server there are no such lines,
    # nothing matches, and "no personal data on the wire" is certified over an
    # empty string.
    wire_seen = bool(raw_bodies.strip())
    on_wire = [value for value in fixtures.leak_values() if value in raw_bodies]
    entity_types = set(remote["usage"]["entities"]) if remote["usage"]["entities"] else set()
    local_types = set(local.get("protected_counts", {}))
    billed = remote["usage"]["requests"]
    ok = (reported and billed == calls and wire_seen and not on_wire
          and entity_types and entity_types <= local_types)
    set_env("PSEUDEX_LOG_RAW_BODY", "")
    return gate("L12 counters match and carry no PII", ok,
                f"billed={billed}/{calls} reports={remote['usage']['reports']} "
                f"entities={len(entity_types)} raw_bodies_logged={wire_seen} "
                f"subset_of_local={entity_types <= local_types} pii_on_wire={on_wire}")


# --- gates: the volume at rest -------------------------------------------

def data_dir_listing() -> str:
    return sidecar_exec(["sh", "-c", "ls -la /data 2>&1 || true"]).stdout


def readable_pii_in_data() -> tuple[bool, list[str]]:
    """(the search actually ran, which files disclose one of the real values).

    THE FIRST HALF IS RETURNED RATHER THAN ASSUMED, and it belongs here rather
    than beside each caller: the command ends in `|| true`, so a grep that could
    not run — missing binary in a slimmed image, an unmounted volume, a pattern
    list that failed to quote — produces no output, and no output is precisely
    the answer every caller wants to hear. L20 happened to be safe because it
    greps for plaintext BEFORE the migration and requires a hit; L19 had no such
    half and would have certified an encrypted volume it never searched. A
    helper that can answer "clean" without having looked is the defect, so it
    now answers both questions at once and neither caller can take one without
    the other.

    BY DIRECTORY, NEVER BY FILE, and that distinction is the gate. Personal data
    lives in `vault.db-wal` until a checkpoint moves it: measured on a live
    vault, zero matches inside `vault.db` and both the phone and the name present
    in the `-wal` beside it. A check that greps the database file alone therefore
    PASSES on a completely unencrypted vault, which is the one outcome a gate
    like this must never produce.
    """
    patterns = " ".join(f"-e {shlex.quote(value)}" for value in fixtures.PII_PAYLOAD.values())
    found = sidecar_exec(["sh", "-c",
                          f"grep -rlF {patterns} /data 2>/dev/null || true"]).stdout
    return grep_instrument_works(), [line for line in found.splitlines() if line.strip()]


_GREP_CONTROL = "pseudex-grep-control-9f3a2c"


def grep_instrument_works() -> bool:
    """Can the search that is about to declare the volume clean find ANYTHING?

    `readable_pii_in_data` ends in `|| true`, so a grep that could not run —
    missing binary in a slimmed image, an unmounted volume, a pattern list that
    failed to quote — produces no output, and no output is exactly the answer
    the gate wants to hear. L20 is safe by construction because it greps for
    plaintext BEFORE the migration and requires a hit; L19 had no such half and
    would have certified an encrypted volume it never actually searched.

    So: write one known string into the volume, search for it with the same
    command shape, remove it. A false green now needs the probe to fail and the
    sweep to succeed at the same time, which is not a thing that happens.
    """
    sidecar_exec(["sh", "-c", f"printf '%s' {_GREP_CONTROL} > /data/.grep-control"])
    found = sidecar_exec(["sh", "-c",
                          f"grep -rlF {_GREP_CONTROL} /data 2>/dev/null || true"]).stdout
    sidecar_exec(["sh", "-c", "rm -f /data/.grep-control"])
    return bool(found.strip())


def restart_stand() -> bool:
    """Down to an EMPTY volume, then back up. Returns whether it came up.

    `down -v` removes the named volumes, which is exactly the point: these gates
    are about what a volume CONTAINS, so each has to start from one whose whole
    history it controls. The licence key goes with the volume, so a new one is
    issued each time.
    """
    compose_down()
    compose(["up", "-d", "license"], True, 600)
    if not wait_until(lambda: httpx.get(f"{ADMIN}/admin/list", timeout=5, headers=ADMIN_AUTH).status_code == 200,
                      120, 2, "licensing admin"):
        return False
    key = httpx.post(f"{ADMIN}/admin/issue",
                     json={"org_id": ORG, "plan": _GATE_PLAN}, timeout=15, headers=ADMIN_AUTH).json()["key"]
    set_env("PSEUDEX_KEY", key)
    return start_sidecar()


def recreate_sidecar() -> bool:
    """Restart the sidecar KEEPING its volume, so the environment changes and the
    data does not. `down -v` would delete the very thing under test."""
    compose(["stop", "sidecar"], False, 120)
    compose(["up", "-d", "--force-recreate", "sidecar"], True, 600)
    return wait_until(
        lambda: httpx.get(f"{SIDECAR}/health", timeout=5).json()["license"] == "active",
        180, 3, "sidecar to reach license=active",
    )


def post_unmask(content: str, timeout: float) -> str:
    body = {"org_id": ORG,
            "response": {"choices": [{"message": {"role": "assistant",
                                                  "content": content}}]}}
    answer = httpx.post(f"{SIDECAR}/unmask", json=body, timeout=timeout,
                        headers=gateway_headers()).json()
    return answer["response"]["choices"][0]["message"]["content"]


def gate_l19() -> bool:
    """Nothing of the customer's real data is readable in the volume.

    The precondition is the half that makes it a gate rather than a tautology:
    the same values must come back out through `/unmask`, so the vault provably
    HOLDS them while the volume provably does not disclose them. Without that,
    an empty volume passes.
    """
    set_env("PSEUDEX_VAULT_ENCRYPTION", "")
    set_env("PSEUDEX_VAULT_KEY", "")
    if not restart_stand():
        return gate("L19 the volume discloses no real value", False, "stand did not start")
    for _ in range(5):
        post_mask(90)
    masked = post_mask(90).json()["messages"][0]["content"]
    restored = post_unmask(masked, 60)

    held = [value for value in fixtures.PII_PAYLOAD.values() if value in restored]
    listing = data_dir_listing()
    # The -wal has to be THERE while we grep, or "by directory" and "by file"
    # would be the same check and the gate would not be testing what it claims.
    wal_present = "vault.db-wal" in listing
    searchable, leaked = readable_pii_in_data()

    return gate("L19 the volume discloses no real value",
                bool(held) and wal_present and searchable and not leaked,
                f"vault_holds={len(held)}/{len(fixtures.PII_PAYLOAD)} "
                f"wal_present={wal_present} grep_works={searchable} "
                f"readable={leaked or 'none'}")


def gate_l20() -> bool:
    """A volume written in plain text keeps working, and its tokens, after a key.

    This is the migration's whole promise. The substitutes are already sitting in
    the customer's CRM by the time they decide to encrypt, so the one thing that
    may not change is what a token resolves to — which is why the SAME masked
    text is sent to `/unmask` on both sides of the restart and compared.
    """
    set_env("PSEUDEX_VAULT_ENCRYPTION", "off")
    set_env("PSEUDEX_VAULT_KEY", "")
    if not restart_stand():
        set_env("PSEUDEX_VAULT_ENCRYPTION", "")
        return gate("L20 a plaintext volume migrates without losing a token",
                    False, "stand did not start unencrypted")
    masked = post_mask(90).json()["messages"][0]["content"]
    before = post_unmask(masked, 60)
    # PRECONDITION: it really was plain text. If this is empty the rest of the
    # gate is measuring encryption against encryption.
    plain_searchable, plain_hits = readable_pii_in_data()

    set_env("PSEUDEX_VAULT_ENCRYPTION", "")
    if not recreate_sidecar():
        return gate("L20 a plaintext volume migrates without losing a token",
                    False, "sidecar did not come back with a key")
    after = post_unmask(masked, 60)
    # The container was RECREATED between the two sweeps, so `plain_hits` proves
    # the search worked in the previous one and says nothing about this one.
    searchable, encrypted_hits = readable_pii_in_data()

    return gate("L20 a plaintext volume migrates without losing a token",
                bool(plain_hits) and plain_searchable and after == before
                and searchable and not encrypted_hits,
                f"was_plaintext={len(plain_hits)} same_values={after == before} "
                f"grep_works={searchable} readable_after={encrypted_hits or 'none'}")


def gate_l21() -> bool:
    """A key that does not open the volume stops the container, and says why.

    SQLCipher answers `file is not a database` to a wrong key, to a corrupt file
    and to an unencrypted database alike. An operator who is shown that sentence
    goes looking for a broken disk. The gate is that OUR explanation reaches the
    log and the port stays shut — a gateway that came up on a vault it cannot
    read would mint a second substitute for every person who already has one.
    """
    # Runs on the volume L20 left behind: encrypted, with real rows in it.
    set_env("PSEUDEX_VAULT_KEY", "b" * 64)
    compose(["stop", "sidecar"], False, 120)
    compose(["up", "-d", "--force-recreate", "sidecar"], False, 600)

    ours = "не открывает"
    spoke = wait_until(lambda: ours in logs("sidecar"), 180, 3, "our own refusal message")
    output = logs("sidecar")
    could_ask, served = _port_probe()
    set_env("PSEUDEX_VAULT_KEY", "")

    return gate("L21 a wrong key refuses to start, in our words",
                spoke and could_ask and not served,
                f"our_message={spoke} stand_reachable={could_ask} still_serving={served} "
                f"driver_sentence_alone={'file is not a database' in output and not spoke}")


def gate_l22(image: str) -> bool:
    """Too little memory stops the container with a sentence, not with 137.

    BOTH HALVES ARE THE GATE, and the refusal alone would be the weaker one: a
    preflight that refuses everything also passes it. So the same image is
    started twice, and what separates the runs is only `--memory`.

    The refusal is also proof of ORDER. `--memory=384m` is given with NO licence
    key at all, so the container has two reasons to stop — and it must stop on
    ours, before the licence layer is ever reached. A container that answers
    `license_missing` here would be one whose workers had already been started
    and had already asked for the memory that is not there; the OOM killer would
    then decide the outcome, and its verdict is status 137, which names neither
    memory nor us.
    """
    # ОДИН ВОРКЕР В ОБЕИХ ПОЛОВИНАХ, ЯВНО. Без этого число берётся из ядер
    # РАННЕРА: на шестнадцати ядрах просторная половина запускает шестнадцать
    # воркеров, каждый строит модель при импорте — то есть ДО того, как дойдёт
    # до лицензии, — и два гигабайта кончаются раньше, чем гейт добирается до
    # того, что проверяет. Красный, зависящий от машины, хуже отсутствующего.
    small_code, small_output = run_disposable_sidecar(image, {
        "PSEUDEX_LICENSE_URL": "https://license:8443",
        "PSEUDEX_LICENSE_CA": "/certs/ca.pem",
        "PSEUDEX_WORKERS": "1",
    }, 120, ["--memory=384m"])
    refused = "preflight" in small_output and "не помещается" in small_output
    before_licence = "license_missing" not in small_output

    big_code, big_output = run_disposable_sidecar(image, {
        "PSEUDEX_LICENSE_URL": "https://license:8443",
        "PSEUDEX_LICENSE_CA": "/certs/ca.pem",
        "PSEUDEX_WORKERS": "1",
    }, 120, ["--memory=2g"])
    # It has enough memory, so it gets far enough to fail for the reason L1
    # already pins. That is the point: the preflight let it through.
    passed_through = "license_missing" in big_output

    return gate("L22 too little memory stops it with words, enough lets it through",
                small_code == 4 and refused and before_licence and passed_through,
                f"exit={small_code} refused={refused} before_licence={before_licence} "
                f"roomy_exit={big_code} roomy_reached_licence={passed_through}")


def gate_l23() -> bool:
    """The worker hardens its own memory: no core file, non-dumpable, swap-locked.

    The tuning lives decrypted in RAM while the engine serves — root with
    CAP_SYS_PTRACE can read it (a theorem, and the POSITIVE CONTROL here: the
    privileged `_memscan` still finds the marker, so the memory IS scannable and
    this gate is not one that cannot go red). What this gate asserts is the bar
    that was raised (pseudex/hardening.py, docs/tz-tuning-in-lease.md):

      * VmLck > 0     — mlockall took, the tuning is never swapped to disk;
      * non-dumpable  — an UNPRIVILEGED sibling (no SYS_PTRACE) is refused at OPEN
                        of /proc/<pid>/mem where the privileged one succeeds. That
                        gap is the whole point of PR_SET_DUMPABLE=0;
      * core off      — the startup line reports RLIMIT_CORE=0 (no crash-time dump).
    """
    # L22 (right before this in the run order) STOPS the sidecar to prove the
    # low-memory refusal, and does not bring it back. Re-establish a healthy,
    # leased sidecar before probing its memory, or `compose ps`/`worker_pids`
    # return empty and this gate dies with an IndexError instead of a verdict.
    if not start_sidecar():
        return gate("L23 the worker hardens its memory (no core, non-dumpable, mlock)",
                    False, "sidecar did not come back up after L22 — cannot probe memory")
    privileged_hits, _ = _memscan()   # positive control: root CAN read the RAM
    lines = compose(["ps", "-q", "sidecar"], False, 30).stdout.strip().splitlines()
    workers = sorted(worker_pids(24))
    if not lines or not workers:
        return gate("L23 the worker hardens its memory (no core, non-dumpable, mlock)",
                    False, "no running sidecar worker to probe")
    cid = lines[0]
    pid = workers[0]

    status = sh(["docker", "run", "--rm", f"--pid=container:{cid}",
                 "python:3.12-slim", "sh", "-c",
                 f"grep VmLck /proc/{pid}/status 2>/dev/null || echo 'VmLck: -1 kB'"],
                False, 60).stdout
    match = re.search(r"VmLck:\s*(-?\d+)", status)
    vmlck = int(match.group(1)) if match else -1

    # UNPRIVILEGED open must be refused; python's PermissionError is the clean
    # signal (dd's offset-0 read can fail for unrelated reasons).
    unpriv = sh(["docker", "run", "--rm", f"--pid=container:{cid}",
                 "python:3.12-slim", "python3", "-c",
                 f"open('/proc/{pid}/mem','rb')"], False, 60)
    unpriv_refused = unpriv.returncode != 0 and "PermissionError" in unpriv.stderr

    hardening_logged = "hardening:" in logs("sidecar") and "core=ok" in logs("sidecar")

    ok = privileged_hits > 0 and vmlck > 0 and unpriv_refused and hardening_logged
    return gate("L23 the worker hardens its memory (no core, non-dumpable, mlock)",
                ok, f"root_can_read={privileged_hits > 0} VmLck={vmlck}kB "
                    f"unpriv_open_refused={unpriv_refused} core_off_logged={hardening_logged}")


# --- gates: the schema of the volume (D-058, D-059) -----------------------

_VOLUME_KEY = "c" * 64
_TOOL_IMAGE = "pseudex:source"


def volume_tool(script: str) -> subprocess.CompletedProcess:
    """Run a snippet against the stand's volume with the product's OWN driver
    setup, from the source image. The image under test may be the compiled one,
    which carries no Python; the source image always exists beside it in the
    battery (pack_gates builds both), and using `pseudex.sqlite_setup` from it
    means the volume is opened exactly as the sidecar opens it — same key
    derivation, same cipher settings — rather than by a second, hand-written
    path that could disagree with the first."""
    return sh(["docker", "run", "--rm", "--network", "none",
               "-v", "pseudex-e2e_sidecar-data:/data",
               "-e", f"PSEUDEX_VAULT_KEY={_VOLUME_KEY}",
               "-e", "PSEUDEX_DB_DIR=/data",
               "--entrypoint", "python3", _TOOL_IMAGE, "-c", script], False, 180)


def stamp_vault(user_version: int, application_id: int | None) -> subprocess.CompletedProcess:
    """Write the header numbers of the stand's vault — what an older image
    (0 / 0) or a future one (999) would have left."""
    lines = ["from pseudex import sqlite_setup as s",
             "c = s.connect('/data/vault.db', s.VAULT_STORE)",
             "print('before', c.execute('PRAGMA user_version').fetchone()[0])",
             f"c.execute('PRAGMA user_version = {int(user_version)}')"]
    if application_id is not None:
        lines.append(f"c.execute('PRAGMA application_id = {int(application_id)}')")
    lines += ["c.execute('PRAGMA wal_checkpoint(TRUNCATE)')", "c.commit()",
              "print('after', c.execute('PRAGMA user_version').fetchone()[0])"]
    return volume_tool("\n".join(lines))


def sidecar_exit_code() -> int | None:
    container = compose(["ps", "-a", "-q", "sidecar"], False, 60).stdout.strip().splitlines()
    if not container:
        return None
    result = sh(["docker", "inspect", "-f", "{{.State.ExitCode}}", container[0]], False, 30)
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def gate_l25() -> bool:
    """A pre-versioned volume is snapshotted, brought forward, and every token
    still resolves to the same value.

    The precondition is written by hand: the vault L1 created is already
    stamped, so the gate first turns it back into what every volume in the
    field is — `user_version` 0, no application id, rows in it — and only then
    recreates the sidecar. The consequence is three things at once: the
    snapshot `vault.db.pre-0-<n>.db` exists beside the store, the log names it,
    and the SAME masked text detokenizes to the same values on both sides.
    """
    set_env("PSEUDEX_VAULT_ENCRYPTION", "")
    set_env("PSEUDEX_VAULT_KEY", _VOLUME_KEY)
    if not restart_stand():
        return gate("L25 a pre-versioned volume is snapshotted and brought forward",
                    False, "stand did not start")
    if sh(["docker", "image", "inspect", _TOOL_IMAGE], False, 30).returncode != 0:
        return gate("L25 a pre-versioned volume is snapshotted and brought forward",
                    False, f"tool image {_TOOL_IMAGE} is missing — build it first")
    for _ in range(3):
        post_mask(90)
    masked = post_mask(90).json()["messages"][0]["content"]
    before = post_unmask(masked, 60)
    compose(["stop", "sidecar"], False, 120)
    unstamped = stamp_vault(0, 0)
    was_stamped = "before 0" not in unstamped.stdout and "after 0" in unstamped.stdout
    if not recreate_sidecar():
        return gate("L25 a pre-versioned volume is snapshotted and brought forward",
                    False, f"sidecar did not come back; tool={unstamped.stdout[-200:]!r} "
                           f"{unstamped.stderr[-200:]!r}")
    after = post_unmask(masked, 60)
    listing = data_dir_listing()
    snapshot_named = re.search(r"vault\.db\.pre-0-\d+\.db", listing)
    output = logs("sidecar")
    logged = "снимок" in output and "схема 0 →" in output
    return gate("L25 a pre-versioned volume is snapshotted and brought forward",
                was_stamped and snapshot_named is not None and logged and after == before,
                f"unstamped={was_stamped} snapshot={snapshot_named.group(0) if snapshot_named else 'none'} "
                f"logged={logged} same_values={after == before}")


def gate_l24() -> bool:
    """A volume a NEWER image wrote is refused before any worker starts, in
    our words, with exit code 6 — and it is not touched: put the stamp back and
    the same sidecar serves the same tokens again.

    Runs on the volume L25 left behind (stamped, with rows). The refusal alone
    would be the weak half — a container that refuses everything passes it —
    so the gate also proves the volume was left intact by restoring the header
    and reading the values back.
    """
    masked = post_mask(90).json()["messages"][0]["content"]
    before = post_unmask(masked, 60)
    compose(["stop", "sidecar"], False, 120)
    future = stamp_vault(999, None)
    original = re.search(r"before (\d+)", future.stdout)
    compose(["up", "-d", "--force-recreate", "sidecar"], False, 600)
    ours = "новее этого образа"
    spoke = wait_until(lambda: ours in logs("sidecar"), 180, 3, "our refusal of a future volume")
    output = logs("sidecar")
    named = "ТОМ НОВЕЕ ОБРАЗА" in output and "999" in output
    exited = wait_until(lambda: sidecar_exit_code() not in (None, 0) or "exited" in
                        compose(["ps", "-a", "sidecar"], False, 60).stdout, 120, 3,
                        "sidecar to stop")
    code = sidecar_exit_code()
    could_ask, served = _port_probe()
    # Put the stamp back — the volume must be exactly as it was.
    restored = stamp_vault(int(original.group(1)) if original else 0, None)
    came_back = recreate_sidecar()
    after = post_unmask(masked, 60) if came_back else ""
    return gate("L24 a volume from the future is refused untouched, exit 6",
                spoke and named and exited and code == 6 and could_ask and not served
                and came_back and after == before,
                f"our_message={spoke} named={named} exit={code} still_serving={served} "
                f"restored_to={original.group(1) if original else '?'} came_back={came_back} "
                f"same_values={after == before} tool={restored.returncode}")


def gate_l15() -> bool:
    """No real value in any log — and the logs must be REAL logs.

    `log_bytes` was already printed in the detail and read by nobody: the
    verdict was one negative term over `all_logs()`, so an archive that came
    back empty — a torn-down stand, a `compose logs` that errored, a service
    name that stopped matching — certified the whole run clean. Both services
    are named in the verdict now, because `docker compose logs` prefixes every
    line with the service that wrote it, and their presence is the cheapest
    available proof that the sweep had something to sweep.
    """
    combined = all_logs()
    both_services = "sidecar" in combined and "license" in combined
    leaked = [value for value in fixtures.leak_values() if value in combined]
    return gate("L15 no PII in any container log", both_services and not leaked,
                f"leaked={leaked or 'none'} log_bytes={len(combined)} "
                f"both_services_logged={both_services}")


# --- driver --------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="pseudex:source")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--only", default="")
    parser.add_argument("--keep", action="store_true",
                        help="leave the stand running for inspection")
    parser.add_argument("--skip-build", action="store_true",
                        help="reuse the existing image (needs a matching PSEUDEX_SIGNING_KEY)")
    args = parser.parse_args()
    selected = {name.strip() for name in args.only.split(",") if name.strip()}

    def wanted(name: str) -> bool:
        return not selected or name in selected

    started = time.monotonic()
    compose(["down", "-v"], False, 300)
    key = build_stand(args.image, args.workers, args.skip_build)

    try:
        print("== startup refusal ==")
        if wanted("L1"):
            run_gate("L1", gate_l1, args.image)
        if wanted("L2"):
            run_gate("L2", gate_l2, args.image)
        if wanted("L2b"):
            run_gate("L2b", gate_l2b, args.image, key)
        if wanted("L3"):
            run_gate("L3", gate_l3, args.image, key)

        print("== healthy instance ==")
        if not start_sidecar():
            gate("SETUP sidecar reaches active", False, "never became active")
            raise SystemExit(_report(started))
        if wanted("L4"):
            run_gate("L4", gate_l4)
        if wanted("L18"):
            run_gate("L18", gate_l18)
        if wanted("L5"):
            run_gate("L5", gate_l5)
        if wanted("L14"):
            run_gate("L14a", gate_l14a)
        if wanted("L6"):
            run_gate("L6", gate_l6)
        if wanted("L16"):
            run_gate("L16", gate_l16)
        if wanted("L17"):
            run_gate("L17", gate_l17)

        print("== degradation ladder ==")
        if wanted("L7"):
            run_gate("L7", gate_l7)
        if wanted("L8"):
            run_gate("L8", gate_l8)
        if wanted("L14"):
            run_gate("L14b", gate_l14b)
        if wanted("L9"):
            run_gate("L9", gate_l9)
        if wanted("L11"):
            run_gate("L11", gate_l11)
        if wanted("L10"):
            run_gate("L10", gate_l10)

        print("== integrity and counters ==")
        if wanted("L13"):
            run_gate("L13", gate_l13, args.image)
        if wanted("L12"):
            run_gate("L12", gate_l12)

        # BEFORE L15, deliberately: these three restart the stand several times
        # and push real personal data through it, so their logs are exactly the
        # ones the leak sweep should also be reading.
        print("== the volume at rest ==")
        if wanted("L19"):
            run_gate("L19", gate_l19)
        if wanted("L20"):
            run_gate("L20", gate_l20)
        if wanted("L21"):
            run_gate("L21", gate_l21)
        if wanted("L22"):
            run_gate("L22", gate_l22, args.image)

        if wanted("L23"):
            run_gate("L23", gate_l23)

        # L25 before L24: L25 builds the stamped volume with rows that L24 then
        # pushes into the future and back.
        print("== the schema of the volume ==")
        if wanted("L25"):
            run_gate("L25", gate_l25)
        if wanted("L24"):
            run_gate("L24", gate_l24)

        if wanted("L15"):
            run_gate("L15", gate_l15)
    finally:
        if not args.keep:
            compose(["down", "-v"], False, 300)

    raise SystemExit(_report(started))


def _report(started: float) -> int:
    print("\n" + "=" * 64)
    failed = [result for result in RESULTS if not result.ok]
    for result in RESULTS:
        print(f"  {'PASS' if result.ok else 'FAIL'}  {result.name}")
    print("=" * 64)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} gates passed "
          f"in {(time.monotonic() - started) / 60:.1f} min")
    # A RUN THAT MEASURED NOTHING IS A FAILURE, NOT A PASS. `0/0` with exit 0
    # reads as "everything green" to a human and to CI alike, and that is how a
    # `--only` name nobody mounts — a typo, or a gate whose call site sits behind
    # a condition its name was left out of — turns into a clean bill of health.
    # Costs nothing when gates ran; catches the whole class when they did not.
    if not RESULTS:
        print("NO GATE RAN. Check the --only names against the roster above.")
        return 1
    return 1 if failed else 0


if __name__ == "__main__":
    main()
