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
from pseudex import service  # noqa: E402
from pseudex.audit import AuditLog, _preview  # noqa: E402

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
    """B1: over the per-org cap → refused."""
    saved = service._DETOK_MAX_PER_MIN
    service._DETOK_MAX_PER_MIN = 3
    service._DETOK_HITS.clear()
    try:
        oks = [service._detok_rate_ok("acme") for _ in range(5)]
        check(oks == [True, True, True, False, False],
              "B1 detok rate limit trips over the cap", f"{oks}")
    finally:
        service._DETOK_MAX_PER_MIN = saved
        service._DETOK_HITS.clear()


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


def main() -> None:
    test_preview_narrowed()
    test_record_detok_counts_only()
    test_rate_limit()
    test_app_org_bind_and_audit()
    failed = [n for ok, n, _ in RESULTS if not ok]
    print("=" * 60)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("detok hardening not in place:", failed)
        raise SystemExit(1)
    print("detok: /unmask* audited + org-bound + rate-limited; preview narrowed.")


if __name__ == "__main__":
    main()
