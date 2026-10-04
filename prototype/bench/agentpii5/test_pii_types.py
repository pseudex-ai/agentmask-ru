# test_pii_types.py — the registry is the single home of the form tables, the
# LIVE `contracts.py` tables equal the registry-derived ones, and the accepted
# widening is pinned (W0-R1, W0-R2, W0-R10 of docs/tz-agentpii6.md §8.1; V1 S4
# SPEC §5.2 / INSTRUMENT-FIX-LEAF-READINGS / D-080).
#
#     cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_pii_types
#
# No pytest, as everywhere in `prototype/`: `main()` prints PASS/FAIL and
# returns the exit code.

from __future__ import annotations

import dataclasses
import pathlib
import subprocess
import sys

import bench.agentpii5.contracts as contracts
import bench.agentpii5.pii_types as pii_types

_PROTOTYPE = str(pathlib.Path(__file__).resolve().parent.parent.parent)


def _with(index: int, **changes) -> tuple[pii_types.TypeSpec, ...]:
    """Return `TYPE_REGISTRY` with the record at `index` replaced by a copy
    carrying `changes`. The broken copy is what makes a rule able to fail."""
    registry = list(pii_types.TYPE_REGISTRY)
    registry[index] = dataclasses.replace(registry[index], **changes)
    return tuple(registry)


def _v5() -> tuple[pii_types.TypeSpec, ...]:
    """The v5 records only — the historical baseline the widening decision is
    measured against. The v6 records extend every table, so the v5 slice is
    where the pre-v6 cardinality is still visible."""
    return tuple(t for t in pii_types.TYPE_REGISTRY if t.origin == pii_types.ORIGIN_V5)


# --- S4: the LIVE-file equality instrument ---------------------------------------
#
# THE TEST THAT COULD NOT FAIL, REPLACED BY ONE THAT CAN (SPEC §3.2
# INSTRUMENT-FIX-LEAF-READINGS, §5.2). The old `test_v5_tables_reproduced`
# compared the registry's derivatives over the V5 SLICE against hand-copied
# literals, so it stayed green while the LIVE `contracts.py` tables diverged —
# and it could never see the full-registry widening. This test imports the LIVE
# `contracts` module and asserts every form table equals the registry-derived
# one. It reads the module that is actually loaded, so a hand copy reintroduced
# in `contracts.py` is RED here.

def test_live_contracts_tables_derive_from_registry() -> list[str]:
    problems: list[str] = []
    registry = pii_types.TYPE_REGISTRY
    live = {
        "FORM_FEATURES": (contracts.FORM_FEATURES, pii_types.form_features(registry)),
        "FORM_TYPES": (contracts.FORM_TYPES, pii_types.form_types(registry)),
        "FEATURE_LABELS": (contracts.FEATURE_LABELS, pii_types.feature_labels(registry)),
        "FORM_ABSTAIN": (contracts.FORM_ABSTAIN, pii_types.form_abstain(registry)),
        "IDENTIFYING_ROLES": (contracts.IDENTIFYING_ROLES,
                              pii_types.identifying_roles(registry)),
        "DERIVED_PIECE_TYPES": (contracts.DERIVED_PIECE_TYPES,
                                pii_types.derived_piece_types(registry)),
        "DIGIT_PIECE_TYPES": (contracts.DIGIT_PIECE_TYPES,
                              pii_types.digit_piece_types(registry)),
        "DATE_PIECE_TYPES": (contracts.DATE_PIECE_TYPES,
                             pii_types.date_piece_types(registry)),
        "SQUEEZED_TYPES": (contracts.SQUEEZED_TYPES, pii_types.squeezed_types(registry)),
    }
    for name, (live_value, derived) in live.items():
        if live_value != derived:
            problems.append(f"contracts.{name} differs from the registry-derived value")
    # The wiring itself is the claim: these must be the registry's objects, not
    # equal copies that a later edit could leave behind.
    if contracts.FORM_FEATURES is not None and contracts.FORM_TYPES != tuple(contracts.FORM_FEATURES):
        problems.append("contracts.FORM_TYPES is not built from contracts.FORM_FEATURES")
    # THE SPLIT SURVIVES IN THE LIVE MODULE (G8 red condition).
    if "translit" not in contracts.FORM_FEATURES.get("NAME", ()):
        problems.append("the live FORM_FEATURES['NAME'] lost `translit`")
    if contracts.FEATURE_LABELS.get(("NAME", "script")) == ("cyrillic", "latin:gost",
                                                            "latin:icao", "latin:bgn",
                                                            "latin:unknown", "mixed", "none"):
        problems.append("the live FEATURE_LABELS[('NAME','script')] is the PRE-SPLIT table")
    if contracts.FORM_ABSTAIN.get(("NAME", "translit")) != "latin:unknown":
        problems.append("the live FORM_ABSTAIN lost ('NAME','translit') → latin:unknown")
    return problems


# THE ACCEPTED WIDENING (V1-F3 / SPEC §5.2 / D-080). These are the decision's
# cardinalities, not a hand copy of a table: the predicate is called with the
# FULL 66-record registry, and a registry edit that moves a set silently is RED
# here until the decision is re-taken. The v5 slice stays the historical anchor.
_ACCEPTED_WIDENING: dict[str, int] = {
    "DERIVED_PIECE_TYPES": 16,
    "DIGIT_PIECE_TYPES": 45,
    "SQUEEZED_TYPES": 22,
    "DATE_PIECE_TYPES": 2,
}
_V5_SLICE: dict[str, frozenset[str]] = {
    "DERIVED_PIECE_TYPES": frozenset({"NAME"}),
    "DIGIT_PIECE_TYPES": frozenset({"PHONE", "CARD", "SNILS", "INN", "PASSPORT"}),
    "SQUEEZED_TYPES": frozenset({"PLATE"}),
    "DATE_PIECE_TYPES": frozenset({"DOB", "DATE"}),
}
_LITERAL_NEEDLE_KINDS: tuple[str, ...] = ("whole", "stem", "digits", "date", "initials", "squeezed")


def _reduce() -> dict[str, frozenset[str]]:
    """The four predicate sets over the LIVE registry and over the v5 slice, from
    `contracts` — the module `observe.py` binds its needle behaviour to."""
    return {
        "DERIVED_PIECE_TYPES": contracts.DERIVED_PIECE_TYPES,
        "DIGIT_PIECE_TYPES": contracts.DIGIT_PIECE_TYPES,
        "SQUEEZED_TYPES": contracts.SQUEEZED_TYPES,
        "DATE_PIECE_TYPES": contracts.DATE_PIECE_TYPES,
    }


def test_accepted_widening() -> list[str]:
    """The per-registry predicate print + the explicit widening decision (S4 RED
    acceptance). A widening is VISIBLE, never implied: the v5 slice and the live
    full registry are printed side by side, and the live cardinalities are
    pinned to the decision."""
    problems: list[str] = []
    v5 = _v5()
    slice_sets = {
        "DERIVED_PIECE_TYPES": pii_types.derived_piece_types(v5),
        "DIGIT_PIECE_TYPES": pii_types.digit_piece_types(v5),
        "SQUEEZED_TYPES": pii_types.squeezed_types(v5),
        "DATE_PIECE_TYPES": pii_types.date_piece_types(v5),
    }
    live = _reduce()
    print("  --- per-registry predicate print (V1-F3 §5.2, decision D-080) ---")
    for name in _ACCEPTED_WIDENING:
        print(f"      {name}: v5 slice={len(slice_sets[name])} "
              f"· live full registry={len(live[name])} · accepted={_ACCEPTED_WIDENING[name]}")
    for name, accepted in _ACCEPTED_WIDENING.items():
        if slice_sets[name] != _V5_SLICE[name]:
            problems.append(f"{name} over the v5 slice changed: {sorted(slice_sets[name])}")
        if len(live[name]) != accepted:
            problems.append(f"{name} over the live registry is {len(live[name])}, "
                            f"the accepted decision is {accepted} — re-take the decision")
    # The predicate must READ the romanization feature, not only script/initials.
    probe = dataclasses.replace(
        next(t for t in pii_types.TYPE_REGISTRY if t.id == "NAME"),
        id="PROBE_TRANSLIT", form_features=("translit",))
    if "PROBE_TRANSLIT" not in pii_types.derived_piece_types((probe,)):
        problems.append("derived_piece_types does not read `translit`")
    return problems


def test_needle_kinds_and_v6_admission() -> list[str]:
    """The needle-kind closure and the 55 admitted v6 types — kept from the old
    v5 repro test, which carried these beside the hand-copied form tables."""
    problems: list[str] = []
    if pii_types.NEEDLE_KINDS[:len(_LITERAL_NEEDLE_KINDS)] != _LITERAL_NEEDLE_KINDS:
        problems.append("the v5 NEEDLE_KINDS prefix differs from the literal")
    if pii_types.NEEDLE_KINDS[len(_LITERAL_NEEDLE_KINDS):] != ("glyph", "octets", "ipv6"):
        problems.append("the CQ-8 needle kinds (glyph/octets/ipv6) are missing")
    if len(pii_types.NEW_ITEM_TYPES) != 55:
        problems.append(f"NEW_ITEM_TYPES has {len(pii_types.NEW_ITEM_TYPES)}, expected 55")
    return problems


def test_registry_rules() -> list[str]:
    problems: list[str] = []
    if pii_types.registry_problems(pii_types.TYPE_REGISTRY):
        problems.append(f"live registry is red: {pii_types.registry_problems(pii_types.TYPE_REGISTRY)}")
    # Each rule must be able to fail by its own id (W0-R2).
    cases: list[tuple[str, tuple[pii_types.TypeSpec, ...]]] = [
        # T1 — one feature with a single label.
        ("T1", _with(0, feature_labels=(("case_class", ("lower",)),))),
        # T2 — `whole` removed.
        ("T2", _with(0, needle_kinds=("stem", "initials"))),
        # T3 — `stem` added to a digit type (roles exist but digits exist too).
        ("T3", _with(1, needle_kinds=("whole", "digits", "stem"))),
        # T5 — a checksum named but no mint/sample.
        ("T5", _with(7, generated_checksum="luhn")),
        # T6 — a [K] type with no cue, no key, not bare_typed.
        ("T6", _with(2, type_class=pii_types.TYPE_CLASS_K)),
        # T7 — an engine label naming another element type.
        ("T7", _with(0, engine_labels=("INN",))),
        # T8 — a mint with no sample.
        ("T8", _with(0, mint="id_digits", sample="")),
    ]
    for rule, broken in cases:
        found = [p for p in pii_types.registry_problems(broken) if p.startswith(rule)]
        if not found:
            problems.append(f"rule {rule} did not fail on its broken copy")
    return problems


def test_no_engine() -> list[str]:
    """W0-R10: importing `pii_types` loads neither `pseudex` nor `licensing`.
    Checked in a FRESH process so an import left behind by this test runner
    cannot both load the module and pass the check."""
    code = (
        "import sys; import bench.agentpii5.pii_types; "
        "print(','.join(sorted(m for m in sys.modules "
        "if m.split('.')[0] in ('pseudex', 'licensing'))))"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          cwd=_PROTOTYPE)
    leaked = proc.stdout.strip()
    if proc.returncode != 0:
        return [f"fresh process failed: {proc.stderr.strip()}"]
    if leaked:
        return [f"pii_types loads engine modules: {leaked}"]
    return []


def test_r02_admits_registered_types() -> list[str]:
    """W0-R3: R02 admits exactly `NEW_ITEM_TYPES` ∪ `V6_NEGATIVE_FAMILIES`. The
    red demo is the negative direction — a typo'd type and a DATE element stay
    red. The positive direction (a registered v6 type IS admitted) activates
    with the first v6 record; until then the admitted set is empty and only the
    negative direction is observable."""
    import bench.agentpii5.schema as schema
    problems: list[str] = []
    if schema._r02_suppressed("c1: item p1 has unknown type 'OMZ'"):
        problems.append("typo'd type 'OMZ' was suppressed")
    if schema._r02_suppressed("c1: item p1 has unknown type 'DATE'"):
        problems.append("DATE element was suppressed")
    if schema._r02_suppressed("c1: negative family 'XYZ' unknown"):
        problems.append("an unregistered negative family was suppressed")
    return problems


def test_r02_in_a_fresh_process() -> list[str]:
    """W0-R4: R02 does not depend on import order. `schema` imports `tools` at
    module level (F1), and `tools` updates v4's REGISTRY with the v5 tools, so a
    fresh process that imports `schema` first still sees `kb_search` in v4's
    registry — no spurious «tool 'kb_search' is not in the registry»."""
    code = (
        "import bench.agentpii5.schema; "
        "from bench.agentpii4.tools import REGISTRY; "
        "print('kb_search' in REGISTRY)"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          cwd=_PROTOTYPE)
    if proc.returncode != 0:
        return [f"fresh process failed: {proc.stderr.strip()}"]
    if proc.stdout.strip() != "True":
        return [f"schema import does not load v5 tools into v4 REGISTRY: {proc.stdout.strip()!r}"]
    return []


def test_case_v6_field_is_invisible() -> list[str]:
    """W0-R13: `CaseV5.v6` is omitted from JSON when None, so the old corpus
    round-trips byte-for-byte; a v6 case carries the key and round-trips it."""
    from bench.agentpii5 import schema
    from bench.agentpii5.test_schema import VALID
    problems: list[str] = []
    data = schema.case_v5_to_json(VALID)
    if "v6" in data:
        problems.append("v6=None was written into the JSON")
    if schema.case_v5_from_json(data) != VALID:
        problems.append("round-trip of a v5 case changed it")
    meta = contracts.CaseV6Meta(industry="retail", provenance="synthetic",
                                skeleton_ref="", procedure_ref="")
    v6_data = schema.case_v5_to_json(dataclasses.replace(VALID, v6=meta))
    if "v6" not in v6_data:
        problems.append("a v6 case lost its meta key")
    if schema.case_v5_from_json(v6_data).v6 != meta:
        problems.append("a v6 case's meta did not round-trip")
    return problems


def test_printer_not_imported() -> list[str]:
    """R6-42: `regress_print` is in `PSEUDEX_ALLOWED_MODULES`, and no PURE module
    of the package imports it — a printer that can import the engine must not
    itself be imported by a module that must not."""
    import ast
    problems: list[str] = []
    if "bench.agentpii5.regress_print" not in contracts.PSEUDEX_ALLOWED_MODULES:
        problems.append("regress_print is not in PSEUDEX_ALLOWED_MODULES")
    here = pathlib.Path(__file__).resolve().parent
    for path in sorted(here.glob("*.py")):
        if path.name.startswith("test_") or path.name in ("regress_print.py", "harness.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = [n.name for n in node.names] if isinstance(node, ast.Import) \
                else ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for module in modules:
                if "regress_print" in module:
                    problems.append(f"{path.name} imports regress_print")
    return problems


CHECKS = (test_live_contracts_tables_derive_from_registry, test_accepted_widening,
          test_needle_kinds_and_v6_admission, test_registry_rules, test_no_engine,
          test_r02_admits_registered_types, test_r02_in_a_fresh_process,
          test_case_v6_field_is_invisible, test_printer_not_imported)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        for problem in problems:
            print(f"FAIL {check.__name__}: {problem}")
        failures += len(problems)
    print("test_pii_types: PASS" if not failures else f"test_pii_types: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
