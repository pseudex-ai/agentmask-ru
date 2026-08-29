"""The closing gate for packaging: P1-P9 against the compiled image.

Same rules as `gates.py`: every check runs against a real container, nothing is
mocked, and each gate proves its precondition before checking its consequence.

The gate that matters most is P3. "The compiled image starts" proves almost
nothing — Nuitka rewrites the program, so the way this breaks is subtle: a lost
regex flag, a dictionary that did not get bundled, a code path stripped with the
docstrings. P3 therefore re-runs the entire detection suite through HTTP against
both images and compares the results digit for digit.

usage:
    python3 e2e/pack_gates.py                       # builds both images
    python3 e2e/pack_gates.py --only P1,P2
    PSEUDEX_SIGNING_KEY=... python3 e2e/pack_gates.py --skip-build

The verification key is compiled into the binary, so a fresh key means a fresh
~30-minute Nuitka compile. Pass a fixed PSEUDEX_SIGNING_KEY to keep the built
image valid across runs while iterating.
"""

import argparse
import base64
import json
import os
import sqlite3
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from e2e import certs, fixtures  # noqa: E402
from e2e.gates import (RESULTS, ADMIN, ORG, SIDECAR, compose, gate,  # noqa: E402
                       gateway_headers, sh, set_env, wait_until)
from licensing import assets_source  # noqa: E402
from licensing.keys import encode_private, encode_public  # noqa: E402

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_ENV_FILE = _HERE / ".env"

SOURCE_IMAGE = "pseudex:source"
COMPILED_IMAGE = "pseudex:compiled"
# NOT 5000, the conventional registry port: on macOS it is already held by
# ControlCenter (AirPlay Receiver), so the registry silently never becomes
# reachable and the gate fails with "registry never came up".
REGISTRY_PORT = int(os.environ.get("PSEUDEX_REGISTRY_PORT", "5555"))
REGISTRY = f"localhost:{REGISTRY_PORT}"
REGISTRY_CONTAINER = "pseudex-e2e-registry"
REGISTRY_USER = "pseudex"
REGISTRY_PASSWORD = "e2e-registry-secret"


# --- stand ---------------------------------------------------------------

def build_images(skip_build: bool) -> str:
    print("== building ==")
    # The verification key is compiled INTO the binary, so a fresh key on every
    # run invalidates the Nuitka layer and forces a ~30 min recompile. Passing
    # PSEUDEX_SIGNING_KEY in keeps the image cached across runs, which is what
    # makes `--skip-build` usable while iterating on the gates themselves.
    existing = os.environ.get("PSEUDEX_SIGNING_KEY", "")
    signing_key = (Ed25519PrivateKey.from_private_bytes(base64.b64decode(existing))
                   if existing else Ed25519PrivateKey.generate())
    private_b64 = encode_private(signing_key)
    public_b64 = encode_public(signing_key.public_key())
    certs.generate(_HERE / "certs", "license")

    # The licensing image is always rebuilt, even with --skip-build: it takes
    # seconds, and skipping it would silently test yesterday's server against
    # today's client.
    sh(["docker", "build", "-f", str(_ROOT / "licensing" / "Dockerfile"),
        "-t", "pseudex-licensing:e2e", str(_ROOT)], True, 1800)
    if not skip_build:
        for dockerfile, tag in ((_ROOT / "Dockerfile", SOURCE_IMAGE),
                                (_ROOT / "Dockerfile.nuitka", COMPILED_IMAGE)):
            started = time.monotonic()
            sh(["docker", "build", "-f", str(dockerfile),
                "--build-arg", f"PSEUDEX_LICENSE_PUBKEY={public_b64}",
                "-t", tag, str(_ROOT)], True, 5400)
            print(f"  {tag} built in {(time.monotonic() - started) / 60:.1f} min")

    _ENV_FILE.write_text(
        f"PSEUDEX_SIGNING_KEY={private_b64}\n"
        f"PSEUDEX_IMAGE={COMPILED_IMAGE}\n"
        f"PSEUDEX_KEY=\n"
        f"PSEUDEX_WORKERS=4\n"
        f"PSEUDEX_LEASE_TTL_SECONDS=600\n"
        f"PSEUDEX_GRACE_SECONDS=600\n"
        f"PSEUDEX_FAULT_INJECT=\n"
        f"PSEUDEX_LOG_RAW_BODY=\n"
        f"PSEUDEX_VAULT_ENCRYPTION=\n"
        f"PSEUDEX_VAULT_KEY=\n"
    )
    return public_b64


def start_stand(image: str, workers: int) -> float:
    """Bring up the stand on `image`. Returns seconds from up to license=active."""
    compose(["down", "-v"], False, 300)
    set_env("PSEUDEX_IMAGE", image)
    set_env("PSEUDEX_WORKERS", str(workers))
    compose(["up", "-d", "license"], True, 600)
    wait_until(lambda: httpx.get(f"{ADMIN}/admin/list", timeout=5).status_code == 200,
               120, 2, "licensing admin")
    key = httpx.post(f"{ADMIN}/admin/issue", json={"org_id": ORG}, timeout=15).json()["key"]
    set_env("PSEUDEX_KEY", key)
    started = time.monotonic()
    compose(["up", "-d", "sidecar"], True, 600)
    ok = wait_until(lambda: httpx.get(f"{SIDECAR}/health", timeout=5).json()["license"] == "active",
                    240, 1, "sidecar active")
    return time.monotonic() - started if ok else -1.0


# --- gates ---------------------------------------------------------------

def gate_p1() -> bool:
    """Nothing readable of the source ships: no files, no code text, no prose.

    The customer's own bar, stated plainly: they may see the bundle, they may not
    see the source. So this checks three separate things, because they leak
    through different holes:

      * `.py`/`.pyc` FILES — the obvious one, and the one Nuitka already solves;
      * CODE TEXT inside the binary — statements as literal strings;
      * DOCSTRINGS inside the binary — the one that actually failed. Nuitka's
        `--python-flag=no_docstrings` stops `__doc__` being set but leaves the
        literals in the constants blob, and in this repo the docstrings carry the
        design rationale, i.e. the part worth stealing.

    Symbol names and module paths DO survive, for tracebacks, and that is
    accepted: a name is not a source line, and a native binary keeping its symbol
    table is exactly where shipped software normally sits."""
    listing = sh(["docker", "run", "--rm", "--entrypoint", "sh", COMPILED_IMAGE, "-c",
                  "find / -xdev \\( -name '*.py' -o -name '*.pyc' \\) 2>/dev/null | head -50"],
                 False, 300).stdout
    ours = [line for line in listing.splitlines() if "pseudex" in line or "serve_main" in line]
    has_pseudex_dir = sh(["docker", "run", "--rm", "--entrypoint", "sh", COMPILED_IMAGE, "-c",
                          "ls /app/pseudex 2>&1 || true"], False, 120).stdout

    # Probes taken from the real tree: two docstrings and two statements that
    # exist verbatim in our sources and nowhere else.
    probes = [
        "Connector to the leased asset state",
        "The 503 that makes the subscription real",
        "if ASSETS.is_loaded:",
        "raise BundleNotLeased",
    ]
    # `grep -c` prints the count AND exits 1 when it is zero, so `|| echo 0`
    # appends a SECOND zero on its own line — which then parsed as a finding and
    # failed the gate on a clean binary. `|| true` keeps the single count.
    checks = " ; ".join(
        f"echo \"{probe}|$(grep -c -a -F -- '{probe}' /app/pseudex-serve 2>/dev/null || true)\""
        for probe in probes
    )
    found = []
    for line in sh(["docker", "run", "--rm", "--entrypoint", "sh", COMPILED_IMAGE, "-c", checks],
                   False, 600).stdout.splitlines():
        probe, _, count = line.rpartition("|")
        if probe and count.strip().isdigit() and int(count) > 0:
            found.append(probe)

    ok = not ours and "No such file" in has_pseudex_dir and not found
    return gate("P1 no source text or docstrings in the release image", ok,
                f"our_py_files={ours[:2] or 'none'} readable_in_binary={found or 'none'}")


def gate_p2() -> bool:
    """The tuned vocabulary must not be sitting in the shipped image as bytes.

    Checked against words that are ASSETS — they belong to the leased bundle —
    never against anything the engine legitimately contains. If this passes, the
    asset split alone did the job and Nuitka Commercial's constant encryption is
    not needed; if it fails, that plugin is what the €250/year buys."""
    # THE PROBES MUST BE UNAMBIGUOUSLY OURS. Common words are useless here and
    # the first version of this gate proved it: "саша" was found in
    # /app/natasha/data/dict/first.txt — natasha's OWN name dictionary, a
    # third-party open artifact we legitimately ship — and "мира" matched as a
    # substring of ordinary Russian words. Neither says anything about whether
    # our tuned vocabulary leaked.
    #
    # So the probes are long authored strings that exist nowhere but our source:
    # a regex we wrote, a compound key we invented, a cue phrase we chose, and a
    # dictionary entry that only lives in the bundle.
    samples = [
        assets_source.ADDRESS_PATTERNS["street_first"][:60],
        assets_source.MEDICAL_PATTERN[:60],
        "контактныйтелефон",
        "появил на свет",
        "оформить на",
        fixtures.marker_surname(),
    ]
    # `grep -a`, not `strings`: debian-slim has no binutils, and more importantly
    # `strings` scans single-byte encodings while every word here is Cyrillic —
    # it would report a clean binary no matter what was inside. grep on the raw
    # bytes finds the UTF-8 runs that actually matter.
    #
    # The whole /app tree, not just the executable: Nuitka standalone spreads
    # constants across the bundled shared objects too.
    checks = " ; ".join(
        f"echo \"{word}:$(grep -ral -F -- '{word}' /app 2>/dev/null | head -1)\""
        for word in samples
    )
    out = sh(["docker", "run", "--rm", "--entrypoint", "sh", COMPILED_IMAGE, "-c", checks],
             False, 900).stdout
    found = [line for line in out.splitlines() if line.strip() and not line.rstrip().endswith(":")]
    return gate("P2 leased vocabulary not extractable from the binary", not found,
                f"found_in_image={found[:3] or 'none'} checked={len(samples)}")


def gate_p3(source_report: Path, compiled_report: Path) -> bool:
    left = json.loads(source_report.read_text())
    right = json.loads(compiled_report.read_text())
    differences = [key for key in set(left) | set(right) if left.get(key) != right.get(key)]
    detail = f"coverage_missed={right['coverage']['missed']} "
    if "dirty" in right and "recall" in right["dirty"]:
        detail += (f"recall={right['dirty']['recall']:.0%} "
                   f"precision={right['dirty']['precision']:.0%} "
                   f"leaks={right['dirty']['true_leaks']} ")
    detail += f"differs={differences or 'nothing'}"
    return gate("P3 compiled image detects exactly what the source does",
                not differences, detail)


_LATENCY_COUNTER = 0


def _latency_sample(count: int) -> list[float]:
    global _LATENCY_COUNTER
    samples = []
    for _ in range(count):
        _LATENCY_COUNTER += 1
        started = time.monotonic()
        response = httpx.post(f"{SIDECAR}/mask", timeout=300,
                              headers=gateway_headers(),
                              json=fixtures.mask_body_variant("perf", _LATENCY_COUNTER))
        response.raise_for_status()
        samples.append((time.monotonic() - started) * 1000)
    return samples


def measure_latency() -> dict[str, float]:
    """Latency of the arm, plus this machine's own noise floor.

    The noise floor is measured, not assumed: the samples are taken in two
    independent halves and the ratio of their medians says how much the same
    binary disagrees with itself right now. Without it there is no way to know
    whether a difference between arms means anything."""
    _latency_sample(5)  # warm the cache paths and the model
    first = _latency_sample(30)
    second = _latency_sample(30)
    samples = sorted(first + second)
    half_a, half_b = statistics.median(first), statistics.median(second)
    return {
        "p50": statistics.median(samples),
        "p95": samples[int(len(samples) * 0.95) - 1],
        # >= 1.0; how far the same image drifts from itself between two blocks.
        "noise": max(half_a, half_b) / min(half_a, half_b),
    }


def gate_p4(source: dict[str, float], compiled: dict[str, float]) -> bool:
    """Compiling must not make the product materially slower.

    THE THRESHOLD IS SET BY THE MEASUREMENT, NOT BY TASTE. Three runs of this
    gate on unchanged code gave p50 ratios of 0.82x, 0.94x and 1.16x — the sign
    flips run to run, because the machine also runs a dozen unrelated containers
    and had just finished a nine-core build. A 10% threshold sits BELOW that
    spread, so it was passing or failing on luck rather than on the binary.

    So: assert on p50 against a bound derived from the noise actually observed in
    this run, and treat p95 as an observation. p95 over 60 samples is three
    samples — it moves on a single stall and cannot carry an assertion."""
    p50_ratio = compiled["p50"] / source["p50"]
    p95_ratio = compiled["p95"] / source["p95"]
    # Never tighter than 1.25x (compiling should not cost anything real), never
    # tighter than twice the noise the machine just demonstrated.
    noise = max(source["noise"], compiled["noise"])
    bound = max(1.25, noise * 2.0)
    ok = p50_ratio <= bound
    return gate("P4 no performance regression from compiling", ok,
                f"p50 {source['p50']:.0f}->{compiled['p50']:.0f}ms ({p50_ratio:.2f}x, "
                f"bound {bound:.2f}x from noise {noise:.2f}x) "
                f"| observed only: p95 {source['p95']:.0f}->{compiled['p95']:.0f}ms "
                f"({p95_ratio:.2f}x)")


def gate_p5(workers: int) -> bool:
    """N processes must really share the port and really absorb a burst."""
    def health_pid(_index: int) -> int:
        with httpx.Client(timeout=30) as client:
            return client.get(f"{SIDECAR}/health").json()["pid"]

    with ThreadPoolExecutor(max_workers=16) as pool:
        pids = set(pool.map(health_pid, range(120)))

    def one_mask(index: int) -> tuple[bool, str]:
        """Returns (ok, reason). The REASON matters: a burst failing because the
        machine is busy and a burst failing because the service returned 5xx are
        opposite verdicts, and a bare failure count cannot tell them apart — it
        invites 'probably contention', which is a guess."""
        try:
            response = httpx.post(f"{SIDECAR}/mask", timeout=120,
                                  headers=gateway_headers(),
                                  json=fixtures.mask_body_variant("load", index))
            if response.status_code == 200:
                return True, ""
            return False, f"HTTP {response.status_code}: {response.text[:120]}"
        except httpx.HTTPError as error:
            return False, f"{type(error).__name__}: {error}"

    health_latencies: list[float] = []

    def probe_health() -> None:
        for _ in range(20):
            started = time.monotonic()
            try:
                httpx.get(f"{SIDECAR}/health", timeout=30)
                health_latencies.append((time.monotonic() - started) * 1000)
            except httpx.HTTPError:
                health_latencies.append(30_000)
            time.sleep(0.5)

    with ThreadPoolExecutor(max_workers=17) as pool:
        probe = pool.submit(probe_health)
        outcomes = list(pool.map(one_mask, range(64)))
        probe.result()

    reasons = [reason for ok, reason in outcomes if not ok]
    health_p95 = sorted(health_latencies)[int(len(health_latencies) * 0.95) - 1]
    spread_ok = len(pids) >= max(2, workers - 1)
    ok = not reasons and spread_ok and health_p95 < 1000
    distinct = sorted({reason.split(":")[0] for reason in reasons})
    return gate("P5 N processes share the port and absorb a burst", ok,
                f"distinct_pids={len(pids)}/{workers} mask_failures={len(reasons)}/64 "
                f"health_p95={health_p95:.0f}ms"
                + (f" reasons={distinct} first={reasons[0][:90]!r}" if reasons else ""))


def gate_p9() -> bool:
    """What the RELEASE image writes cannot be read by ordinary SQLite.

    THE DANGER THIS GATE EXISTS FOR is one line nobody would notice in review:

        try: from sqlcipher3 import dbapi2 as driver
        except ImportError: import sqlite3 as driver

    Stdlib `sqlite3` accepts `PRAGMA key` WITHOUT RAISING and writes plain text.
    A build where SQLCipher failed to bundle would therefore log that it was
    encrypting, pass every functional test, and store every real value in the
    clear. Nothing inside the product can detect that about itself — the code
    that would report it is the code that is wrong.

    So the gate stands outside and asks the customer's own question: take the
    files this image produced and try to open them with the SQLite that every
    machine already has. The reader is this process's own stdlib, deliberately —
    if SQLCipher had degraded to it, the files would open here.

    Two halves, and both are required. The vault must PROVE it holds the real
    values (through `/unmask`, which is the only supported way to get them back),
    and the volume must then refuse to give them up to a plain reader. Either
    half alone passes on an empty volume or on a broken service.
    """
    marker_values = list(fixtures.PII_PAYLOAD.values())
    masked = httpx.post(f"{SIDECAR}/mask", json=fixtures.mask_body(ORG), timeout=120,
                        headers=gateway_headers()).json()["messages"][0]["content"]
    restored = httpx.post(
        f"{SIDECAR}/unmask", timeout=120, headers=gateway_headers(),
        json={"org_id": ORG, "response": {"choices": [
            {"message": {"role": "assistant", "content": masked}}]}},
    ).json()["response"]["choices"][0]["message"]["content"]
    held = [value for value in marker_values if value in restored]

    # Copied out rather than read in place: the point is what an ordinary tool on
    # an ordinary machine can do with a stolen volume, and that tool is not
    # inside the container.
    container = compose(["ps", "-q", "sidecar"], False, 30).stdout.strip().splitlines()
    if not container:
        return gate("P9 the release image writes nothing ordinary SQLite can read",
                    False, "no sidecar container")
    copied = _HERE / "reports" / "volume"
    sh(["rm", "-rf", str(copied)], False, 60)
    sh(["docker", "cp", f"{container[0]}:/data", str(copied)], True, 300)

    files = sorted(path for path in copied.rglob("*") if path.is_file())
    opened: list[str] = []
    readable: list[str] = []
    for path in files:
        blob = path.read_bytes()
        if any(value.encode("utf-8") in blob for value in marker_values):
            readable.append(path.name)
        # `with` on a sqlite3 connection is a TRANSACTION context manager, not a
        # closer, so it is not used here: this loop opens every file in a volume
        # and leaking a handle per file is how a gate starts failing on the size
        # of the thing it is inspecting.
        plain = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            plain.execute("SELECT count(*) FROM sqlite_master").fetchone()
            opened.append(path.name)
        except sqlite3.DatabaseError:
            pass
        finally:
            plain.close()

    ok = bool(held) and bool(files) and not opened and not readable
    return gate("P9 the release image writes nothing ordinary SQLite can read", ok,
                f"vault_holds={len(held)}/{len(marker_values)} files={len(files)} "
                f"opened_by_stdlib={opened or 'none'} readable={readable or 'none'}")


def gate_p6() -> bool:
    """A private registry with credentials, and a signature the customer can check."""
    sh(["docker", "rm", "-f", REGISTRY_CONTAINER], False, 60)
    auth_dir = _HERE / "registry-auth"
    auth_dir.mkdir(exist_ok=True)
    htpasswd = sh(["docker", "run", "--rm", "--entrypoint", "htpasswd", "httpd:2",
                   "-Bbn", REGISTRY_USER, REGISTRY_PASSWORD], False, 300).stdout
    if not htpasswd.strip():
        return gate("P6 private registry and signature", False, "could not generate htpasswd")
    (auth_dir / "htpasswd").write_text(htpasswd)

    sh(["docker", "run", "-d", "--name", REGISTRY_CONTAINER,
        "-p", f"{REGISTRY_PORT}:5000",
        "-v", f"{auth_dir}:/auth",
        "-e", "REGISTRY_AUTH=htpasswd",
        "-e", "REGISTRY_AUTH_HTPASSWD_REALM=pseudex",
        "-e", "REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd",
        "registry:2"], True, 600)
    if not wait_until(lambda: httpx.get(f"http://{REGISTRY}/v2/", timeout=5).status_code == 401,
                      120, 2, "registry to demand credentials"):
        return gate("P6 private registry and signature", False, "registry never came up")

    tag = f"{REGISTRY}/pseudex:compiled"
    sh(["docker", "tag", COMPILED_IMAGE, tag], True, 60)

    # 1. Anonymous push must be refused.
    sh(["docker", "logout", REGISTRY], False, 60)
    anon = sh(["docker", "push", tag], False, 600)
    anon_refused = anon.returncode != 0

    # 2. With credentials it works.
    login = subprocess.run(["docker", "login", REGISTRY, "-u", REGISTRY_USER, "--password-stdin"],
                           input=REGISTRY_PASSWORD, capture_output=True, text=True, timeout=120)
    pushed = sh(["docker", "push", tag], False, 1800).returncode == 0

    # 3. Sign it, then verify with the right key and fail with a wrong one.
    keys_dir = _HERE / "cosign"
    sh(["rm", "-rf", str(keys_dir)], False, 60)
    keys_dir.mkdir(parents=True, exist_ok=True)

    cosign_image = "gcr.io/projectsigstore/cosign:v2.4.1"
    common = ["docker", "run", "--rm", "--network", "host",
              "-e", "COSIGN_PASSWORD=", "-v", f"{keys_dir}:/keys", "-w", "/keys"]
    # Credentials passed as FLAGS, not through a mounted ~/.docker. On macOS the
    # docker config holds only `"credsStore": "desktop"` and the real secret lives
    # in the keychain, which a Linux container cannot call — cosign then fails
    # with `UNAUTHORIZED` on an image it had just pushed itself.
    creds = ["--registry-username", REGISTRY_USER, "--registry-password", REGISTRY_PASSWORD]
    # --tlog-upload=false: cosign v2 pushes a transparency-log entry to the public
    # Rekor by default even for key-based signing. That needs the internet and,
    # worse, would publish the digest of a private customer image to a public log.
    insecure = ["--allow-insecure-registry", "--allow-http-registry"]

    generated = sh([*common, cosign_image, "generate-key-pair"], False, 600).returncode == 0
    signed = sh([*common, cosign_image, "sign", "--yes", "--key", "/keys/cosign.key",
                 "--tlog-upload=false", *insecure, *creds, tag], False, 900)
    verified = sh([*common, cosign_image, "verify", "--key", "/keys/cosign.pub",
                   *insecure, *creds, "--insecure-ignore-tlog", tag], False, 900)
    sh([*common, cosign_image, "generate-key-pair", "--output-key-prefix", "other"], False, 600)
    wrong = sh([*common, cosign_image, "verify", "--key", "/keys/other.pub",
                *insecure, *creds, "--insecure-ignore-tlog", tag], False, 900)

    ok = (anon_refused and login.returncode == 0 and pushed and generated
          and signed.returncode == 0 and verified.returncode == 0 and wrong.returncode != 0)
    sh(["docker", "logout", REGISTRY], False, 60)
    sh(["docker", "rm", "-f", REGISTRY_CONTAINER], False, 120)
    return gate("P6 private registry and signature", ok,
                f"anon_push_refused={anon_refused} authed_push={pushed} signed={signed.returncode == 0} "
                f"verify_ok={verified.returncode == 0} wrong_key_rejected={wrong.returncode != 0}")


def gate_p8(startup_seconds: float) -> bool:
    size_bytes = int(sh(["docker", "image", "inspect", COMPILED_IMAGE,
                         "--format", "{{.Size}}"], False, 60).stdout.strip() or 0)
    size_gb = size_bytes / 1024 ** 3
    ok = 0 < startup_seconds < 20 and size_gb < 1.5
    return gate("P8 startup and size budget", ok,
                f"startup={startup_seconds:.1f}s (<20) size={size_gb:.2f}GB (<1.5)")


# --- driver --------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    selected = {name.strip() for name in args.only.split(",") if name.strip()}

    def wanted(name: str) -> bool:
        return not selected or name in selected

    started = time.monotonic()
    build_images(args.skip_build)
    reports = _HERE / "reports"
    reports.mkdir(exist_ok=True)

    try:
        if wanted("P1"):
            gate_p1()
        if wanted("P2"):
            gate_p2()

        # Bringing up two stands and running the whole detection suite through
        # both takes ~20 minutes, so it is skipped entirely when no selected gate
        # needs it — `--only P1,P2` should not pay for parity.
        needs_stand = any(wanted(name) for name in ("P3", "P4", "P5", "P8", "P9"))
        if needs_stand:
            # Baseline on the SOURCE image, so parity has something to compare to.
            print("== source image baseline ==")
            start_stand(SOURCE_IMAGE, args.workers)
            source_latency = measure_latency()
            sh([sys.executable, str(_HERE / "parity.py"), SIDECAR,
                "--dirty", str(_ROOT / "dirty.json"),
                "--out", str(reports / "source.json")], True, 3600)
            print(f"  source p50={source_latency['p50']:.0f}ms p95={source_latency['p95']:.0f}ms")

            print("== compiled image ==")
            startup = start_stand(COMPILED_IMAGE, args.workers)
            if startup < 0:
                gate("SETUP compiled image reaches active", False, "never became active")
                raise SystemExit(_report(started))
            compiled_latency = measure_latency()
            sh([sys.executable, str(_HERE / "parity.py"), SIDECAR,
                "--dirty", str(_ROOT / "dirty.json"),
                "--out", str(reports / "compiled.json")], True, 3600)
            print(f"  compiled p50={compiled_latency['p50']:.0f}ms "
                  f"p95={compiled_latency['p95']:.0f}ms startup={startup:.1f}s")

            if wanted("P3"):
                gate_p3(reports / "source.json", reports / "compiled.json")
            if wanted("P4"):
                gate_p4(source_latency, compiled_latency)
            if wanted("P5"):
                gate_p5(args.workers)
            if wanted("P8"):
                gate_p8(startup)
            # Last of the stand gates: it copies the volume out, so it wants one
            # that has already had real traffic through it.
            if wanted("P9"):
                gate_p9()
        if wanted("P6"):
            gate_p6()
    finally:
        compose(["down", "-v"], False, 300)
        sh(["docker", "rm", "-f", REGISTRY_CONTAINER], False, 120)

    raise SystemExit(_report(started))


def _report(started: float) -> int:
    print("\n" + "=" * 64)
    failed = [result for result in RESULTS if not result.ok]
    for result in RESULTS:
        print(f"  {'PASS' if result.ok else 'FAIL'}  {result.name}")
    print("=" * 64)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} packaging gates passed "
          f"in {(time.monotonic() - started) / 60:.1f} min")
    print("P7 (the whole L1-L21 suite on the compiled image) runs separately:\n"
          f"    python3 e2e/gates.py --image {COMPILED_IMAGE}")
    return 1 if failed else 0


if __name__ == "__main__":
    main()
