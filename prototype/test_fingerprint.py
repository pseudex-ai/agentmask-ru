"""Collusion-resistant fingerprint (Tardos) — attribution survives a coalition.

The single-leaker canary is stripped by two orgs INTERSECTING their bundles (per-org
unique marks are common to none). This proves the Tardos fingerprint traces a pirate
bundle back to a true contributor even when it is fused from several orgs — and never
accuses an innocent.

Run:  python3 test_fingerprint.py
"""
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# Secret BEFORE import (read once into an lru_cache).
os.environ["PSEUDEX_CANARY_SECRET"] = "test-fingerprint-secret"

from licensing import fingerprint as fp  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []
ORGS = [f"org{i}" for i in range(6)]
KIND = "surname"


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _entries(org: str) -> set:
    return set(fp.fingerprint_entries(org, KIND))


def test_universe_shared_and_novel() -> None:
    """One shared universe for every org (not per-org unique), sized to _BITS."""
    uni = fp._universe(KIND)
    # Every org's marks are a SUBSET of the one universe.
    subsets = all(_entries(o) <= set(uni) for o in ORGS)
    # Orgs differ (different codewords) but overlap (shared universe) — the property
    # that makes intersection-collusion traceable, unlike per-org-unique canaries.
    a, b = _entries("org0"), _entries("org1")
    check(len(uni) == fp._BITS and subsets and a != b and (a & b),
          "shared universe: per-org subsets of one novel pool, overlapping",
          f"|U|={len(uni)} |org0|={len(a)} |org0∩org1|={len(a & b)}")


def test_solo_attribution() -> None:
    """Each org's own bundle traces to itself, and to no one else."""
    hits = [fp.accuse(_entries(o), ORGS, KIND) == o for o in ORGS]
    check(all(hits), "solo leaker: every org self-attributes", f"{sum(hits)}/{len(ORGS)}")


def test_union_collusion() -> None:
    """Two orgs fuse bundles by UNION → a true colluder is accused, never an innocent."""
    a, b = "org0", "org3"
    merged = _entries(a) | _entries(b)
    accused = fp.accuse(merged, ORGS, KIND)
    check(accused in {a, b}, "union collusion: a true colluder is traced",
          f"accused={accused}")


def test_intersection_collusion() -> None:
    """The attack that defeats per-org canaries: two orgs keep only the ENTRIES BOTH
    have. A true colluder is still traced, and no innocent is ever accused."""
    a, b = "org1", "org4"
    merged = _entries(a) & _entries(b)
    accused = fp.accuse(merged, ORGS, KIND)
    innocents = [o for o in ORGS if o not in {a, b}]
    check(accused in {a, b}, "intersection collusion: a true colluder is traced",
          f"accused={accused} (|A∩B|={len(merged)})")
    check(accused not in innocents, "intersection collusion: no innocent accused",
          f"accused={accused}")


def test_three_way_union() -> None:
    """A 3-org coalition (union) still yields a true contributor, no innocent."""
    coalition = {"org0", "org2", "org5"}
    merged: set = set()
    for o in coalition:
        merged |= _entries(o)
    accused = fp.accuse(merged, ORGS, KIND)
    check(accused in coalition, "3-way union collusion: a true colluder is traced",
          f"accused={accused}")


def _payload(blob: bytes) -> dict:
    import json
    import zlib
    return json.loads(zlib.decompress(blob).decode("utf-8"))


def test_woven_into_bundle() -> None:
    """The org's fingerprint marks reach the leased gazetteers (surnames + streets),
    novel vs the base dictionary — so a clone built from THIS bundle carries them."""
    from licensing.pack import build_plaintext
    marked = _payload(build_plaintext(org_id="acme"))
    base = _payload(build_plaintext())
    surn = set(marked["names"]["dict_surnames"])
    base_surn = set(base["names"]["dict_surnames"])
    fp_s = set(fp.fingerprint_entries("acme", "surname"))
    fp_t = set(fp.fingerprint_entries("acme", "street"))
    check(fp_s <= surn and fp_s.isdisjoint(base_surn)
          and fp_t <= set(marked["address"]["street_names"]),
          "fingerprint marks woven into the per-org bundle, novel vs base",
          f"surn {len(fp_s)} novel={fp_s.isdisjoint(base_surn)} streets {len(fp_t)}")


def test_leaked_bundle_traced() -> None:
    """A recovered gazetteer (the whole leased surname set of one org) traces to it."""
    from licensing.pack import build_plaintext
    leaked = set(_payload(build_plaintext(org_id="initech"))["names"]["dict_surnames"])
    who = fp.accuse(leaked, ["acme", "globex", "initech", "umbrella"], "surname")
    check(who == "initech", "a leaked per-org bundle is traced to its org", f"traced={who}")


def test_tuning_unchanged() -> None:
    """Fingerprint touches only the gazetteers — the authored tuning is identical, so
    detection of real PII is unaffected."""
    from pseudex.assets import Assets
    from licensing.pack import build_plaintext
    plain = Assets(); plain.load(build_plaintext())
    marked = Assets(); marked.load(build_plaintext(org_id="acme"))
    same = (plain.get().priority == marked.get().priority
            and plain.get().names.cues == marked.get().names.cues
            and plain.get().translit.units == marked.get().translit.units)
    check(same, "fingerprint leaves the authored tuning unchanged", "priority+cues+translit identical")


def test_no_secret_off() -> None:
    """No secret → no fingerprint (empty), no crash."""
    saved = os.environ.pop("PSEUDEX_CANARY_SECRET", None)
    try:
        fp._secret.cache_clear(); fp._universe.cache_clear()
        off = fp.fingerprint_entries("acme", "surname") == [] and fp.accuse(["x"], ["acme"], "surname") is None
        check(off, "no secret → fingerprint off, no crash")
    finally:
        if saved is not None:
            os.environ["PSEUDEX_CANARY_SECRET"] = saved
        fp._secret.cache_clear(); fp._universe.cache_clear()


def main() -> None:
    test_universe_shared_and_novel()
    test_solo_attribution()
    test_union_collusion()
    test_intersection_collusion()
    test_three_way_union()
    test_woven_into_bundle()
    test_leaked_bundle_traced()
    test_tuning_unchanged()
    test_no_secret_off()
    failed = [n for ok, n, _ in RESULTS if not ok]
    print("=" * 60)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("fingerprint collusion-resistance not in place:", failed)
        raise SystemExit(1)
    print("fingerprint: Tardos codeword traces a coalition-fused bundle, no false accuse.")


if __name__ == "__main__":
    main()
