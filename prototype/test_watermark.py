"""Every leased bundle is stamped with a per-customer watermark, so a tuning
dump lifted from one customer's RAM names WHOSE it is.

Written BEFORE the implementation (ТЗ docs/tz-tuning-in-lease.md, Ступень 1). The
watermark does not PREVENT extraction — a root customer can read their live RAM
(a theorem) and a sophisticated one can scrub a field they can see. It is
ATTRIBUTION + deterrence: a leaked copy that was not scrubbed points back at the
org whose lease carried it, which turns "someone leaked it" into "this customer
leaked it" — legally actionable. Honest scope, asserted here.

Run:  python3 test_watermark.py
"""
import os
import sys
import zlib
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _payload(blob: bytes) -> dict:
    import json
    return json.loads(zlib.decompress(blob).decode("utf-8"))


def test_watermark_is_per_org_and_deterministic() -> None:
    """Two orgs get two different watermarks; the same org twice gets the same
    one — so a dump maps to exactly one org, and renewals don't churn it."""
    from licensing.watermark import watermark_for
    a1 = watermark_for("acme")
    a2 = watermark_for("acme")
    b = watermark_for("globex")
    check(a1 == a2 and a1 != b and bool(a1),
          "watermark is per-org and deterministic",
          f"acme={a1[:8]}… globex={b[:8]}…")


def test_watermark_maps_back_to_org() -> None:
    """Given a watermark found in a dump and the list of orgs, the server can
    say WHOSE it is — that is the whole point of attribution."""
    from licensing.watermark import watermark_for, identify
    orgs = ["acme", "globex", "initech", "umbrella"]
    leaked = watermark_for("initech")
    who = identify(leaked, orgs)
    check(who == "initech", "a leaked watermark identifies the org",
          f"identified={who}")


def test_watermark_in_leased_bundle() -> None:
    """The bundle the lease delivers carries the org's watermark, and two orgs'
    bundles differ by it — so the mark is in what the engine loads into RAM."""
    from licensing.pack import build_plaintext
    from licensing.watermark import watermark_for
    p_a = _payload(build_plaintext(watermark=watermark_for("acme")))
    p_b = _payload(build_plaintext(watermark=watermark_for("globex")))
    check(p_a.get("_wm") == watermark_for("acme")
          and p_a.get("_wm") != p_b.get("_wm"),
          "leased bundle carries the per-org watermark",
          f"acme_wm={str(p_a.get('_wm'))[:8]}…")


def test_watermark_survives_into_loaded_assets() -> None:
    """After the engine loads the bundle, the watermark is reachable in the
    in-memory assets — a memory dump of a leaked engine therefore contains it."""
    from pseudex.assets import Assets
    from licensing.pack import build_plaintext
    from licensing.watermark import watermark_for
    wm = watermark_for("initech")
    a = Assets()
    a.load(build_plaintext(watermark=wm))
    got = getattr(a.get(), "watermark", None)
    check(got == wm, "watermark survives into the loaded assets (dump-visible)",
          f"assets.watermark={str(got)[:8]}…")


def test_watermark_does_not_change_detection() -> None:
    """The mark is inert: assets built with and without it must detect the same,
    or the watermark would corrupt the product it protects."""
    from pseudex.assets import Assets
    from licensing.pack import build_plaintext
    from licensing.watermark import watermark_for
    plain = Assets(); plain.load(build_plaintext())
    marked = Assets(); marked.load(build_plaintext(watermark=watermark_for("acme")))
    same = (plain.get().priority == marked.get().priority
            and plain.get().names.cues == marked.get().names.cues
            and plain.get().lookalike == marked.get().lookalike)
    check(same, "watermark does not change detection", "priority+names identical")


def test_no_secret_no_watermark() -> None:
    """No `PSEUDEX_WATERMARK_SECRET` → watermarking is off (empty), not a crash —
    the server still leases, just without attribution."""
    from licensing import watermark
    saved = os.environ.pop("PSEUDEX_WATERMARK_SECRET", None)
    try:
        watermark._secret.cache_clear()
        wm = watermark.watermark_for("acme")
        check(wm == "", "no secret → no watermark, no crash", f"wm={wm!r}")
    finally:
        if saved is not None:
            os.environ["PSEUDEX_WATERMARK_SECRET"] = saved
        watermark._secret.cache_clear()


def main() -> None:
    os.environ.setdefault("PSEUDEX_WATERMARK_SECRET", "test-watermark-secret-32-bytes-xx")
    test_watermark_is_per_org_and_deterministic()
    test_watermark_maps_back_to_org()
    test_watermark_in_leased_bundle()
    test_watermark_survives_into_loaded_assets()
    test_watermark_does_not_change_detection()
    test_no_secret_no_watermark()
    failed = [n for ok, n, _ in RESULTS if not ok]
    print("=" * 60)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("watermark not in place:", failed)
        raise SystemExit(1)
    print("watermark: every lease stamped, dump names the org, detection unchanged.")


if __name__ == "__main__":
    main()
