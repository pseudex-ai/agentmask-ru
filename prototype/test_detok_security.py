"""Detok surface hardening (pentest B1/B2/B4).

B1 — /unmask* wrote no audit row, so a compromised gateway credential could trawl
     the vault leaving no trace. Now every /unmask and /unmask_arguments call
     records a COUNTS-ONLY detok row (resolved + misses, never values) and is
     rate-limited per org.
B2 — org_id came from the body, unbound to the credential; a bound container
     (PSEUDEX_ORG) now refuses any other org (one tenant per container).
B4 — the audit preview disclosed first-2 + last-2 chars; narrowed to at most one
     char at each end, and nothing for a short value.

Not B3: /unmask stays reachable on an expired lease BY DESIGN (the customer's own
vault, and /mask being down already stops the agent) — that decision is left to
the owner; see the report.

Run:  python3 test_detok_security.py
"""
import os
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# A temp DB dir + a bound org, set BEFORE importing the app (read at import time).
_TMP = tempfile.mkdtemp(prefix="pseudex-detok-test-")
os.environ["PSEUDEX_DB_DIR"] = _TMP
os.environ["PSEUDEX_VAULT_ENCRYPTION"] = "off"
os.environ.setdefault("PSEUDEX_GATEWAY_TOKEN", "test-gw")

import httpx  # noqa: E402
import testkit  # noqa: E402
from pseudex import service  # noqa: E402
from pseudex.audit import AuditLog, _preview  # noqa: E402

# Fake pools are leased (WS-2), so /unmask* (token recognition) needs a bundle.
testkit.load_dev_bundle()

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def test_preview_narrowed() -> None:
    """B4: a short value discloses nothing; a long one at most first+last."""
    short = _preview("14")          # house number
    code = _preview("4821")         # 4-digit
    phone = _preview("+79991234567")
    ok = (set(short) == {"•"}
          and code.count("•") >= 3
          and phone[0] == "+" and phone[-1] == "7" and phone.count("•") == len(phone) - 2)
    check(ok, "B4 preview narrowed (short hidden, long ≤2 chars)",
          f"'14'->{short!r} '4821'->{code!r} phone->{phone!r}")


def test_record_detok_counts_only() -> None:
    """B1: record_detok stores counts, never values; a sweep shows as volume."""
    a = AuditLog(os.path.join(_TMP, "audit_probe.db"))
    import time as _t
    since = _t.time() - 1
    for _ in range(5):
        a.record_detok("acme", "gateway", resolved=0, misses=20)  # sweep shape
    a.record_detok("acme", "gateway", resolved=3, misses=0)       # legit shape
    calls = a.detok_calls_since("acme", since)
    check(calls == 6, "B1 detok calls recorded (counts only)", f"calls={calls}")


def test_rate_limit() -> None:
    """B1: over the per-org cap → refused. The cap is counted from the SHARED audit
    (cross-worker), so recording rows is what trips it — not a per-worker counter."""
    saved = service._DETOK_MAX_PER_MIN
    service._DETOK_MAX_PER_MIN = 3
    try:
        org = "ratelimit-test-org"
        fresh = service._detok_rate_ok(org)                 # 0 rows -> allowed
        for _ in range(3):
            service.AUDIT.record_detok(org, "gateway", 1, 0)
        over = service._detok_rate_ok(org)                  # 3 >= 3 -> refused
        check(fresh and not over,
              "B1 detok rate limit trips over the cap (cross-worker, from audit)",
              f"fresh={fresh} over={over}")
    finally:
        service._DETOK_MAX_PER_MIN = saved


async def _app_calls() -> None:
    """B2 at the HTTP layer: bound container refuses another org; the bound org's
    /unmask writes a detok audit row."""
    service._BOUND_ORG = "acme"
    gw = {"Authorization": f"Bearer {os.environ['PSEUDEX_GATEWAY_TOKEN']}"}
    transport = httpx.ASGITransport(app=service.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        wrong = await client.post("/unmask", headers=gw,
            json={"org_id": "globex", "response": {"choices": []}})
        right = await client.post("/unmask", headers=gw,
            json={"org_id": "acme", "response": {"choices": [
                {"message": {"content": "nothing to resolve"}}]}})
    before = service.AUDIT.detok_calls_since("acme", 0)
    check(wrong.status_code == 403, "B2 bound container refuses another org",
          f"globex->{wrong.status_code} acme->{right.status_code}")
    check(right.status_code == 200 and before >= 1,
          "B1 /unmask on the bound org writes a detok audit row",
          f"acme->{right.status_code} detok_rows={before}")


def test_app_org_bind_and_audit() -> None:
    import anyio
    try:
        anyio.run(_app_calls)
    finally:
        service._BOUND_ORG = ""


def test_detok_counts_values_not_calls() -> None:
    """F2: one call resolving N values records N, not 1 — a batch of many values in
    ONE call cannot hide under a per-CALL cap. Counts the actual minted tokens the
    call resolved (present in input, gone from output), via the same residual_tokens
    the residual signal already uses."""
    org = "batch-values-org"
    v = service._vault(org)
    toks = [v.tokenize(f"+7 999 111 22 {i:02d}", "PHONE") for i in range(3)]
    one_arg = "звоните " + " и ".join(toks)              # 3 values, ONE call/arg
    _restored, _residual, disclosed = service._unmask_arguments_for([one_arg], org)
    check(disclosed == 3,
          "F2 one batched call counts 3 resolved VALUES (a call-counter sees 1)",
          f"disclosed={disclosed}")


def test_rate_limit_by_values() -> None:
    """F2: the cap is on VALUES disclosed, not calls. One call disclosing `cap`
    values trips it; a pure-miss sweep does not consume the disclosure budget."""
    saved = service._DETOK_MAX_PER_MIN
    service._DETOK_MAX_PER_MIN = 5
    try:
        org = "values-cap-org"
        fresh = service._detok_rate_ok(org)                   # 0 -> allowed
        service.AUDIT.record_detok(org, "gateway", 5, 0)      # ONE call, 5 values
        over = not service._detok_rate_ok(org)                # 5 >= 5 -> refused
        calls = service.AUDIT.detok_calls_since(org, 0)
        values = service.AUDIT.detok_values_since(org, 0)
        service.AUDIT.record_detok(org, "gateway", 0, 50)     # sweep, no values
        after_sweep = service.AUDIT.detok_values_since(org, 0)
        check(fresh and over and calls == 1 and values == 5 and after_sweep == 5,
              "F2 rate limit counts VALUES not calls (one batched call trips it)",
              f"calls={calls} values={values} after_sweep={after_sweep}")
    finally:
        service._DETOK_MAX_PER_MIN = saved


async def _chunk_audit_calls() -> None:
    """F1: /unmask_chunk writes a counts-only detok row when it discloses a value."""
    service._BOUND_ORG = ""
    org = "chunk-audit-org"
    tok = service._vault(org).tokenize("+7 999 777 66 55", "PHONE")
    gw = {"Authorization": f"Bearer {os.environ['PSEUDEX_GATEWAY_TOKEN']}"}
    before = service.AUDIT.detok_calls_since(org, 0)
    transport = httpx.ASGITransport(app=service.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/unmask_chunk", headers=gw, json={
            "org_id": org, "delta": f"на {tok} перезвоним", "carry": "", "flush": True})
    after = service.AUDIT.detok_calls_since(org, 0)
    summary = service.AUDIT.detok_summary(org, 0)
    real_back = "777" in r.json().get("text", "")
    check(r.status_code == 200 and after == before + 1
          and summary["resolved"] >= 1 and real_back,
          "F1 /unmask_chunk writes a detok audit row on disclosure",
          f"status={r.status_code} rows {before}->{after} "
          f"resolved={summary['resolved']} real={real_back}")


async def _chunk_limit_calls() -> None:
    """F1: /unmask_chunk is under the same value cap as /unmask."""
    service._BOUND_ORG = ""
    saved = service._DETOK_MAX_PER_MIN
    service._DETOK_MAX_PER_MIN = 1
    try:
        org = "chunk-cap-org"
        tok = service._vault(org).tokenize("+7 999 500 40 30", "PHONE")   # a real minted token
        service.AUDIT.record_detok(org, "gateway", 5, 0)      # already over the cap
        gw = {"Authorization": f"Bearer {os.environ['PSEUDEX_GATEWAY_TOKEN']}"}
        transport = httpx.ASGITransport(app=service.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            # A delta carrying a MINTED token — a chunk that could disclose is what the cap
            # gates; a chunk with no minted token discloses nothing and is not rate-limited
            # (the minted-token early-out).
            r = await client.post("/unmask_chunk", headers=gw, json={
                "org_id": org, "delta": f"на {tok} перезвоним", "carry": "", "flush": True})
        check(r.status_code == 429, "F1 /unmask_chunk honors the detok rate limit",
              f"status={r.status_code}")
    finally:
        service._DETOK_MAX_PER_MIN = saved


def test_unmask_chunk_audited_and_limited() -> None:
    import anyio
    try:
        anyio.run(_chunk_audit_calls)
        anyio.run(_chunk_limit_calls)
    finally:
        service._BOUND_ORG = ""


def test_name_trawl_visible() -> None:
    """WS-7 exfiltrator #2: a NAME/VALUE-guess sweep resolves nothing AND leaves no
    residual, so `miss_rate` stays 0.0 and the trawl used to hide. It now shows as
    `unproductive` calls (resolved nothing) — the sweep signal that catches BOTH a
    token-guess (high miss_rate) and a name-guess (miss_rate 0) trawl."""
    legit_org, trawl_org = "trawl-legit", "trawl-sweep"
    for _ in range(10):
        service.AUDIT.record_detok(legit_org, "gateway", resolved=3, misses=0)
    for _ in range(200):
        service.AUDIT.record_detok(trawl_org, "gateway", resolved=0, misses=0)  # guessed non-tokens
    legit = service.AUDIT.detok_summary(legit_org, 0)
    trawl = service.AUDIT.detok_summary(trawl_org, 0)
    check(legit["unproductive"] == 0
          and trawl["unproductive"] == 200 and trawl["unproductive_rate"] == 1.0
          and trawl["miss_rate"] == 0.0,
          "name-trawl (miss_rate=0) is visible as unproductive calls",
          f"legit_unprod={legit['unproductive']} trawl_unprod={trawl['unproductive']} "
          f"trawl_miss_rate={trawl['miss_rate']}")


def main() -> None:
    test_preview_narrowed()
    test_record_detok_counts_only()
    test_rate_limit()
    test_rate_limit_by_values()
    test_detok_counts_values_not_calls()
    test_app_org_bind_and_audit()
    test_unmask_chunk_audited_and_limited()
    test_name_trawl_visible()
    failed = [n for ok, n, _ in RESULTS if not ok]
    print("=" * 60)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("detok hardening not in place:", failed)
        raise SystemExit(1)
    print("detok: /unmask* audited + org-bound + rate-limited; preview narrowed.")


if __name__ == "__main__":
    main()
