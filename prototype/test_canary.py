"""Per-customer CANARIES woven into the leased gazetteers, so a leaked or cloned
detector NAMES the customer it came from.

Written BEFORE the implementation (plan Phase 0, item 1). The bulk gazetteers are
open data — hiding them is pointless — but we can seed each org's leased copy with
a handful of unique, plausible-but-invented surnames/streets that exist in NO real
dictionary and in NO other org's bundle. If a cloned engine (built from a stolen
tuning dump) masks one of these canaries, the clone is attributable to exactly one
org. This is the cartographer's trap-street / dictionary-Mountweazel trick.

Honest scope (asserted here): canaries are ATTRIBUTION + deterrence, not
prevention. A sophisticated leaker who knows to look could try to strip them, but
they are indistinguishable from real gazetteer entries without the server secret,
and (Phase 1) some are entangled into the detection logic so removal degrades the
product. This test pins: determinism, per-org uniqueness, injection into the
leased bundle, identification, and the no-secret-off path.

Run:  python3 test_canary.py
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
    # The lease is now sectioned-framed (pseudex.bundle), not one zlib(JSON) blob.
    from pseudex import bundle
    return bundle.unframe_payload(blob)


def test_canaries_are_per_org_and_deterministic() -> None:
    """Same org twice → same canaries (renewals don't churn attribution); two orgs
    → disjoint sets (a canary points at exactly one org)."""
    from licensing.canary import canary_surnames
    a1 = set(canary_surnames("acme"))
    a2 = set(canary_surnames("acme"))
    b = set(canary_surnames("globex"))
    check(a1 == a2 and bool(a1) and a1.isdisjoint(b),
          "canaries per-org, deterministic, disjoint across orgs",
          f"acme={len(a1)} globex∩acme={len(a1 & b)}")


def test_canaries_look_like_real_surnames() -> None:
    """A canary must be INDISTINGUISHABLE from a real gazetteer entry: Cyrillic,
    plausible length, and in the SAME CASE as the leased gazetteer — which is
    LOWERCASE (`_load_dictionary`/load_street_vocabulary lowercase it). WS-7
    IP-thief2 showed a Capitalised mark both stood out as an anomaly in an
    all-lowercase dictionary AND was stripped by a one-line `.lower()` of the
    stolen gazetteer, setting attribution to None at zero cost. A lowercase mark
    blends in and survives case normalization."""
    from licensing.canary import canary_surnames, identify
    cs = canary_surnames("acme")
    lowercased = all(4 <= len(c) <= 16 and c == c.lower()
                     and all("а" <= ch <= "я" or ch == "ё" for ch in c) for c in cs)
    # The strip attack: attribution must survive the attacker normalizing case.
    survives = all(identify({fn(c) for c in cs}, ["acme", "globex", "initech"]) == "acme"
                   for fn in (str.lower, str.upper, str.capitalize))
    check(lowercased and survives,
          "canaries match the gazetteer case (lowercase) and survive a case-strip",
          f"lowercased={lowercased} survives_case_strip={survives} e.g. {cs[:4]}")


def test_canaries_not_in_real_dictionary() -> None:
    """Canaries must NOT be real surnames, or a clone masking one proves nothing
    (every clone masks a real name). pack filters any collision with the bulk."""
    from licensing.canary import canary_surnames
    from licensing.pack import build_plaintext
    payload = _payload(build_plaintext(org_id="acme"))
    real = set(payload["names"]["dict_surnames"])
    canaries = set(canary_surnames("acme"))
    # The injected canaries are in the leased set, but each is novel vs the ORIGINAL
    # dictionary. Rebuild the original (no canaries) and confirm zero overlap.
    original = set(_payload(build_plaintext())["names"]["dict_surnames"])
    check(canaries.isdisjoint(original) and canaries <= real,
          "canaries are novel (not real surnames) yet injected into the leased set",
          f"novel={canaries.isdisjoint(original)} injected={canaries <= real}")


def test_canaries_injected_per_org_into_bundle() -> None:
    """The leased bundle for org A carries A's canaries and NOT B's — so a dump of
    A's tuning contains only A's mark."""
    from licensing.canary import canary_surnames
    from licensing.pack import build_plaintext
    a = set(_payload(build_plaintext(org_id="acme"))["names"]["dict_surnames"])
    ca, cb = set(canary_surnames("acme")), set(canary_surnames("globex"))
    check(ca <= a and cb.isdisjoint(a),
          "org bundle carries its own canaries, not another org's",
          f"acme_has_acme={ca <= a} acme_has_globex={len(cb & a)}")


def test_leaked_gazetteer_identifies_org() -> None:
    """Given a recovered surname set (from a leaked/cloned engine) and the org
    list, the server names WHOSE it is — the whole point of attribution."""
    from licensing.canary import identify
    from licensing.pack import build_plaintext
    leaked = set(_payload(build_plaintext(org_id="initech"))["names"]["dict_surnames"])
    who = identify(leaked, ["acme", "globex", "initech", "umbrella"])
    check(who == "initech", "a leaked gazetteer identifies the org", f"identified={who}")


def test_canaries_survive_into_loaded_assets() -> None:
    """After the engine loads the bundle, the canaries are in the live name set —
    so a clone built from a dump of THIS engine masks them, and is attributable."""
    from pseudex.assets import Assets
    from licensing.pack import build_plaintext
    from licensing.canary import canary_surnames
    a = Assets()
    a.load(build_plaintext(org_id="acme"))
    names = a.get().names
    got = getattr(names, "dict_surnames", frozenset())
    cs = set(canary_surnames("acme"))
    check(cs <= set(got), "canaries reach the loaded assets (a clone would mask them)",
          f"present={len(cs & set(got))}/{len(cs)}")


def test_no_secret_no_canaries() -> None:
    """No `PSEUDEX_CANARY_SECRET` → canaries off (empty), not a crash — the server
    still leases, just without attribution."""
    from licensing import canary
    saved = os.environ.pop("PSEUDEX_CANARY_SECRET", None)
    try:
        canary._secret.cache_clear()
        cs = canary.canary_surnames("acme")
        check(cs == [], "no secret → no canaries, no crash", f"canaries={cs!r}")
    finally:
        if saved is not None:
            os.environ["PSEUDEX_CANARY_SECRET"] = saved
        canary._secret.cache_clear()


def test_canaries_do_not_change_detection_of_real_values() -> None:
    """Injecting canaries must not change how real PII is detected — assets built
    with and without canaries agree on the authored tuning."""
    from pseudex.assets import Assets
    from licensing.pack import build_plaintext
    plain = Assets(); plain.load(build_plaintext())
    marked = Assets(); marked.load(build_plaintext(org_id="acme"))
    same = (plain.get().priority == marked.get().priority
            and plain.get().names.cues == marked.get().names.cues)
    check(same, "canaries leave the authored tuning unchanged", "priority+cues identical")


def main() -> None:
    os.environ.setdefault("PSEUDEX_CANARY_SECRET", "test-canary-secret-32-bytes-xxxxx")
    test_canaries_are_per_org_and_deterministic()
    test_canaries_look_like_real_surnames()
    test_canaries_not_in_real_dictionary()
    test_canaries_injected_per_org_into_bundle()
    test_leaked_gazetteer_identifies_org()
    test_canaries_survive_into_loaded_assets()
    test_no_secret_no_canaries()
    test_canaries_do_not_change_detection_of_real_values()
    failed = [n for ok, n, _ in RESULTS if not ok]
    print("=" * 60)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("canaries not in place:", failed)
        raise SystemExit(1)
    print("canaries: every leased gazetteer per-org marked, a clone names its org.")


if __name__ == "__main__":
    main()
