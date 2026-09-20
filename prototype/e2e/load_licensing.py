"""Load test for the licensing server — the shared bottleneck of the whole fleet.

`docs/tz-license-packaging.md` §2.6.4 makes this mandatory BEFORE advertising:
every container in the field talks to ONE licensing server, and `/v1/lease`
rebuilds and age-encrypts the whole ~1.5 MB bundle synchronously on a
single-process uvicorn (see the note on `licensing/server.py::meter`). If that
endpoint folds under a real fleet, every customer's engine degrades at once.

WHAT THIS MEASURES (server side, the 10k-process pressure point):
  * `/v1/lease`, `/v1/meter`, `/v1/usage` — p50/p99 latency and throughput;
  * error rate under concurrency;
  * licensing DB growth per process (meter + usage rows).

The acceptance thresholds are NAMED HERE, before the run, on purpose: a bar
chosen after seeing the numbers certifies nothing (the same discipline the eval
suite uses). Change them in ONE place — the constants below — and say why.

WHAT THIS DOES NOT COVER, and how to measure it (container side): the per-
container `vault.db` / `audit.db` growth and worker RSS are a soak on a SINGLE
engine, not a function of fleet size — push volume through one container and
watch its volume and `docker stats`. Its thresholds are named in
`CONTAINER_THRESHOLDS` below so the acceptance bar exists for that half too; it
is run separately because it needs a built image, not this in-process server.

MEASUREMENT CAVEATS (read before trusting the absolute numbers):
  * `/v1/lease` is SINGLE-CORE-bound: it age-seals the ~1.5 MB bundle, and pyrage
    holds the GIL during that seal (measured: 8 threads seal at 1× the speed of 1).
    So server throughput scales with WORKER PROCESSES, not threads — a threadpool
    offload does nothing here. Steady state is easy (10k containers renewing every
    ~8 h ≈ 0.35 leases/s vs a ~77/s single-core ceiling); the only real risk is a
    SYNCHRONISED burst (mass restart / aligned TTLs). Renewal jitter in
    `pseudex/license.py` spreads that herd; multiple server workers raise the ceiling.
  * This harness co-locates the load CLIENT and the SERVER in one process, and the
    client also holds the GIL (age keygen), so the reported latencies are INFLATED
    by contention that production does not have. A true acceptance run puts the load
    client on a SEPARATE host from the server; treat the in-process numbers as a
    lower bound on capacity, not a verdict.

RUN:
    python3 e2e/load_licensing.py                     # full: 10 000 processes
    python3 e2e/load_licensing.py --processes 200     # quick smoke
    python3 e2e/load_licensing.py --concurrency 200   # in-flight requests cap

The server is the REAL `licensing/server.py`, booted in-process (its bundle is
built at import), never a double — a stand that runs different code proves
nothing about the code that ships.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import os
import socket
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field

import httpx

# ── acceptance thresholds (SERVER side), named before the run ────────────────
LEASE_P50_MS = 100.0
LEASE_P99_MS = 500.0
METER_P99_MS = 200.0
USAGE_P99_MS = 500.0
ERROR_RATE_MAX = 0.001                 # 0.1 % of requests may fail
LICENSE_DB_BYTES_PER_PROCESS_MAX = 8192  # meter + usage rows for one process/period

# ── acceptance thresholds (CONTAINER side), named here, measured separately ──
CONTAINER_THRESHOLDS = {
    "worker_rss_mb_max": 450,          # ~350 MB model stack + headroom
    "vault_db_bytes_per_value_max": 512,
    "audit_db_bytes_per_request_max": 256,
}

DEFAULT_PROCESSES = 10_000
DEFAULT_CONCURRENCY = 100
LOAD_PLAN = "enterprise"               # highest instance cap (100), so fewest keys
ENGINE_VERSION = "1.4.0"


@dataclass
class Samples:
    """Latencies (ms) and outcomes for one endpoint."""
    latencies: list[float] = field(default_factory=list)
    errors: int = 0

    def add(self, ms: float, ok: bool) -> None:
        self.latencies.append(ms)
        if not ok:
            self.errors += 1

    def pct(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        ordered = sorted(self.latencies)
        # Nearest-rank percentile: exact, no interpolation, matches how the eval
        # suite reads a percentile so two reports cannot disagree about the data.
        rank = max(1, math.ceil(p / 100 * len(ordered)))
        return ordered[rank - 1]

    def rps(self, wall_seconds: float) -> float:
        return len(self.latencies) / wall_seconds if wall_seconds > 0 else 0.0


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _boot_server() -> tuple[object, int, int, str, str]:
    """Boot the REAL licensing server in-process. Returns (module, public_port,
    admin_port, admin_token, db_path). The bundle is built at import."""
    db_path = os.path.join(tempfile.mkdtemp(prefix="pseudex-load-"), "license.db")
    admin_token = "loadtest-admin-token"
    os.environ["PSEUDEX_LICENSE_DB"] = db_path
    os.environ["PSEUDEX_LICENSE_ADMIN_TOKEN"] = admin_token
    # A generated ephemeral signing key is fine: we measure throughput, not
    # signature provenance, and a stand key must never be a production one.
    os.environ.pop("PSEUDEX_SIGNING_KEY", None)
    # Silence the per-request access log — 10k lines would dwarf the report and
    # add IO the production server does not do at INFO.
    os.environ.setdefault("PSEUDEX_LOG_LEVEL", "ERROR")
    logging.basicConfig(level=logging.ERROR)

    import uvicorn  # local import: only the load path needs it
    from licensing import server  # import builds the bundle (build_plaintext)

    public_port, admin_port = _free_port(), _free_port()

    def _run(app: object, port: int) -> None:
        uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="warning",
            access_log=False)).run()

    threading.Thread(target=_run, args=(server.admin_app, admin_port),
                     name="load-admin", daemon=True).start()
    threading.Thread(target=_run, args=(server.app, public_port),
                     name="load-public", daemon=True).start()

    # Wait for readiness rather than sleeping a guessed interval.
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{public_port}/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        raise RuntimeError("licensing server did not become ready in 30 s")
    return server, public_port, admin_port, admin_token, db_path


def _issue_keys(admin_port: int, admin_token: str, count: int) -> list[str]:
    headers = {"Authorization": f"Bearer {admin_token}"}
    keys: list[str] = []
    with httpx.Client(base_url=f"http://127.0.0.1:{admin_port}", headers=headers,
                      timeout=30) as client:
        for i in range(count):
            resp = client.post("/admin/issue",
                               json={"org_id": f"load-org-{i}", "plan": LOAD_PLAN})
            resp.raise_for_status()
            keys.append(resp.json()["key"])
    return keys


async def _run_load(public_port: int, keys: list[str], processes: int,
                    concurrency: int, cap_per_key: int,
                    report_usage: bool) -> dict[str, Samples]:
    from pseudex.bundle import generate_process_key

    base = f"http://127.0.0.1:{public_port}"
    lease, meter, usage = Samples(), Samples(), Samples()
    limiter = asyncio.Semaphore(concurrency)

    # Each simulated process is a unique (key, instance_id, process pubkey). The
    # instance cap is per key, so processes are spread cap_per_key at a time —
    # this is a real fleet of `processes` engines across `len(keys)` tenants,
    # not one tenant hammering past its own ceiling (that is a 409, not load).
    async def one(client: httpx.AsyncClient, index: int) -> None:
        key = keys[index // cap_per_key]
        pub = generate_process_key().public
        instance_id, process_id = f"inst-{index}", f"proc-{index}"
        async with limiter:
            await _timed(client, "POST", "/v1/lease", lease, json={
                "key": key, "engine_version": ENGINE_VERSION, "pubkey": pub,
                "instance_id": instance_id, "process_id": process_id})
            await _timed(client, "POST", "/v1/meter", meter, json={
                "key": key, "pubkey": pub, "nonce": f"n{index}"})
            if report_usage:
                await _timed(client, "POST", "/v1/usage", usage, json={
                    "key": key, "instance_id": instance_id, "pubkey": pub,
                    "usage": {"requests": 100, "values": 40, "seq": 1,
                              "entities": {"PHONE": 12, "NAME": 8}}})

    async with httpx.AsyncClient(base_url=base, timeout=60) as client:
        await asyncio.gather(*(one(client, i) for i in range(processes)))

    return {"lease": lease, "meter": meter, "usage": usage}


async def _timed(client: httpx.AsyncClient, method: str, path: str,
                 samples: Samples, json: dict) -> None:
    start = time.perf_counter()
    ok = False
    try:
        resp = await client.request(method, path, json=json)
        ok = resp.status_code == 200
    except httpx.HTTPError:
        ok = False
    samples.add((time.perf_counter() - start) * 1000, ok)


def _verdict(name: str, value: float, limit: float, unit: str,
             lower_is_better: bool = True) -> bool:
    ok = value <= limit if lower_is_better else value >= limit
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  {name}: {value:.1f}{unit} (порог {limit:g}{unit})")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processes", type=int, default=DEFAULT_PROCESSES)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--no-usage", action="store_true",
                        help="не слать /v1/usage (мерить только lease+meter)")
    args = parser.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print(f"Нагрузочный тест лицензионного сервера: {args.processes} процессов, "
          f"{args.concurrency} в полёте (§2.6.4)")
    server, public_port, admin_port, admin_token, db_path = _boot_server()

    cap_per_key = (server.STORE.plan_row(LOAD_PLAN) or {"max_instances": 1})["max_instances"]
    keys_needed = math.ceil(args.processes / cap_per_key)
    print(f"  тариф {LOAD_PLAN}: {cap_per_key} инстансов/ключ → выпускаю "
          f"{keys_needed} ключей")
    keys = _issue_keys(admin_port, admin_token, keys_needed)

    db_before = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    wall_start = time.perf_counter()
    result = asyncio.run(_run_load(public_port, keys, args.processes,
                                   args.concurrency, cap_per_key,
                                   report_usage=not args.no_usage))
    wall = time.perf_counter() - wall_start
    db_after = os.path.getsize(db_path) if os.path.exists(db_path) else db_before

    lease, meter, usage = result["lease"], result["meter"], result["usage"]
    total_req = sum(len(s.latencies) for s in result.values())
    total_err = sum(s.errors for s in result.values())
    err_rate = total_err / total_req if total_req else 1.0
    db_per_proc = (db_after - db_before) / args.processes if args.processes else 0

    print(f"\nОтработано за {wall:.1f} с · {total_req} запросов · "
          f"{total_req / wall:.0f} rps суммарно · ошибок {total_err}")
    print(f"  /v1/lease : p50 {lease.pct(50):.0f} мс · p99 {lease.pct(99):.0f} мс · "
          f"{lease.rps(wall):.0f} rps")
    print(f"  /v1/meter : p50 {meter.pct(50):.0f} мс · p99 {meter.pct(99):.0f} мс · "
          f"{meter.rps(wall):.0f} rps")
    if usage.latencies:
        print(f"  /v1/usage : p50 {usage.pct(50):.0f} мс · p99 {usage.pct(99):.0f} мс · "
              f"{usage.rps(wall):.0f} rps")
    print(f"  БД лицензий: +{db_after - db_before} байт "
          f"({db_per_proc:.0f} байт/процесс)")

    print("\nПриёмка (пороги названы ДО прогона):")
    ok = True
    ok &= _verdict("/v1/lease p50", lease.pct(50), LEASE_P50_MS, " мс")
    ok &= _verdict("/v1/lease p99", lease.pct(99), LEASE_P99_MS, " мс")
    ok &= _verdict("/v1/meter p99", meter.pct(99), METER_P99_MS, " мс")
    if usage.latencies:
        ok &= _verdict("/v1/usage p99", usage.pct(99), USAGE_P99_MS, " мс")
    ok &= _verdict("доля ошибок", err_rate * 100, ERROR_RATE_MAX * 100, " %")
    ok &= _verdict("рост БД на процесс", db_per_proc,
                   LICENSE_DB_BYTES_PER_PROCESS_MAX, " Б")

    print("\nКонтейнерная часть (§2.6.4) меряется отдельным замачиванием одного "
          "образа; её пороги названы в CONTAINER_THRESHOLDS этого файла:")
    for name, limit in CONTAINER_THRESHOLDS.items():
        print(f"    {name} ≤ {limit}")

    print("\n" + ("НАГРУЗКА OK" if ok else "НАГРУЗКА НЕ ПРОШЛА — см. FAIL выше"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
