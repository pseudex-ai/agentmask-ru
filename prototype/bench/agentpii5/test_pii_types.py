# test_pii_types.py — the registry is the single home and reproduces v5 exactly
# (W0-R1, W0-R2, W0-R10 of docs/tz-agentpii6.md §8.1).
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


# --- the v5 literals, hand-copied (the spec is written twice) --------------------
# These are the values the registry's derivatives must reproduce byte-for-byte.
# They are NOT read from `contracts` — `contracts` now DERIVES its tables from
# the registry, so reading them there would compare the registry to itself and
# prove nothing.

_LITERAL_FORM_FEATURES: dict[str, tuple[str, ...]] = {
    "NAME": ("case_class", "gram_case", "order", "parts", "initials", "script", "hyphen_particle"),
    "PHONE": ("prefix", "grouping", "separators", "parens"),
    "LOC": ("case_class", "generic", "generic_position", "house_marker", "flat_marker", "commas",
            "city_present", "city_position", "by_fields", "building_entrance_markers"),
    "DOB": ("notation", "separator", "padding", "year_len", "month_form"),
    "DATE": ("notation", "separator", "padding", "year_len", "month_form"),
    "EMAIL": ("case_class",),
    "CARD": ("grouping", "separator"),
    "SNILS": ("separators",),
    "INN": ("length", "separators"),
    "PASSPORT": ("series_number_split",),
    "PLATE": ("case_class", "spaces", "region_sep"),
}

_LITERAL_FEATURE_LABELS: dict[tuple[str, str], tuple[str, ...]] = {
    ("NAME", "case_class"): ("lower", "title", "upper", "mixed", "none"),
    ("NAME", "gram_case"): ("nomn", "gent", "datv", "accs", "ablt", "loct", "unknown"),
    ("NAME", "order"): ("F-I-O", "I-F", "I-O-F", "single", "other"),
    ("NAME", "parts"): ("1", "2", "3", "4+"),
    ("NAME", "initials"): ("none", "given", "given_patronymic"),
    ("NAME", "script"): ("cyrillic", "latin:gost", "latin:icao", "latin:bgn", "latin:unknown", "mixed", "none"),
    ("NAME", "hyphen_particle"): ("none", "hyphen", "particle", "both"),
    ("PHONE", "prefix"): ("plus7", "eight", "seven", "bare", "other"),
    ("PHONE", "grouping"): ("3-3-2-2", "3-3-4", "solid", "other"),
    ("PHONE", "separators"): ("none", "space", "hyphen", "dot", "mixed"),
    ("PHONE", "parens"): ("yes", "no"),
    ("LOC", "case_class"): ("lower", "title", "upper", "mixed", "none"),
    ("LOC", "generic"): ("none", "full:*", "abbr:*"),
    ("LOC", "generic_position"): ("before", "after", "none"),
    ("LOC", "house_marker"): ("none", "d_dot_space", "d_dot_nospace", "d_nodot", "dom", "other"),
    ("LOC", "flat_marker"): ("none", "kv_dot_space", "kv_dot_nospace", "kv_nodot", "kvartira", "other"),
    ("LOC", "commas"): ("yes", "no"),
    ("LOC", "city_present"): ("yes", "no"),
    ("LOC", "city_position"): ("first", "last", "middle", "none"),
    ("LOC", "by_fields"): ("fields", "string"),
    ("LOC", "building_entrance_markers"): ("none", "markers:*"),
    ("DOB", "notation"): ("dmy_dots", "dmy_slashes", "iso", "words", "solid", "other"),
    ("DOB", "separator"): ("dot", "slash", "hyphen", "space", "none"),
    ("DOB", "padding"): ("padded", "unpadded"),
    ("DOB", "year_len"): ("2", "4", "none"),
    ("DOB", "month_form"): ("number", "word_nominative", "word_genitive"),
    ("DATE", "notation"): ("dmy_dots", "dmy_slashes", "iso", "words", "solid", "other"),
    ("DATE", "separator"): ("dot", "slash", "hyphen", "space", "none"),
    ("DATE", "padding"): ("padded", "unpadded"),
    ("DATE", "year_len"): ("2", "4", "none"),
    ("DATE", "month_form"): ("number", "word_nominative", "word_genitive"),
    ("EMAIL", "case_class"): ("lower", "upper", "mixed", "none"),
    ("CARD", "grouping"): ("4x4", "solid", "other"),
    ("CARD", "separator"): ("space", "hyphen", "none", "other"),
    ("SNILS", "separators"): ("canonical", "solid", "other"),
    ("INN", "length"): ("10", "12", "other"),
    ("INN", "separators"): ("none", "space", "other"),
    ("PASSPORT", "series_number_split"): ("2-2-6", "4-6", "solid", "other"),
    ("PLATE", "case_class"): ("lower", "upper", "mixed", "none"),
    ("PLATE", "spaces"): ("yes", "no"),
    ("PLATE", "region_sep"): ("space", "none", "other"),
}

_LITERAL_FORM_ABSTAIN: dict[tuple[str, str], str] = {
    ("NAME", "gram_case"): "unknown",
    ("LOC", "generic_position"): "none",
    ("NAME", "case_class"): "none",
    ("LOC", "case_class"): "none",
    ("EMAIL", "case_class"): "none",
    ("PLATE", "case_class"): "none",
    ("NAME", "script"): "none",
    ("NAME", "order"): "other",
}

_LITERAL_IDENTIFYING_ROLES: dict[str, tuple[str, ...]] = {
    "NAME": ("surname", "given", "patronymic"),
    "LOC": ("street",),
    "EMAIL": ("local",),
    "PHONE": ("digits",),
    "CARD": ("digits",),
    "SNILS": ("digits",),
    "INN": ("digits",),
    "PASSPORT": ("digits",),
    "DOB": ("iso",),
    "DATE": ("iso",),
    "PLATE": (),
}

_LITERAL_DIGIT_PIECE_TYPES: frozenset[str] = frozenset({"PHONE", "CARD", "SNILS", "INN", "PASSPORT"})
_LITERAL_DATE_PIECE_TYPES: frozenset[str] = frozenset({"DOB", "DATE"})
_LITERAL_DERIVED_PIECE_TYPES: frozenset[str] = frozenset({"NAME"})
_LITERAL_SQUEEZED_TYPES: frozenset[str] = frozenset({"PLATE"})
_LITERAL_NEEDLE_KINDS: tuple[str, ...] = ("whole", "stem", "digits", "date", "initials", "squeezed")


def _with(index: int, **changes) -> tuple[pii_types.TypeSpec, ...]:
    """Return `TYPE_REGISTRY` with the record at `index` replaced by a copy
    carrying `changes`. The broken copy is what makes a rule able to fail."""
    registry = list(pii_types.TYPE_REGISTRY)
    registry[index] = dataclasses.replace(registry[index], **changes)
    return tuple(registry)


def test_v5_tables_reproduced() -> list[str]:
    problems: list[str] = []
    if pii_types.form_features(pii_types.TYPE_REGISTRY) != _LITERAL_FORM_FEATURES:
        problems.append("FORM_FEATURES differs from the literal")
    if pii_types.form_types(pii_types.TYPE_REGISTRY) != tuple(_LITERAL_FORM_FEATURES):
        problems.append("FORM_TYPES differs from the literal")
    if pii_types.feature_labels(pii_types.TYPE_REGISTRY) != _LITERAL_FEATURE_LABELS:
        problems.append("FEATURE_LABELS differs from the literal")
    if pii_types.form_abstain(pii_types.TYPE_REGISTRY) != _LITERAL_FORM_ABSTAIN:
        problems.append("FORM_ABSTAIN differs from the literal")
    if pii_types.identifying_roles(pii_types.TYPE_REGISTRY) != _LITERAL_IDENTIFYING_ROLES:
        problems.append("IDENTIFYING_ROLES differs from the literal")
    if pii_types.digit_piece_types(pii_types.TYPE_REGISTRY) != _LITERAL_DIGIT_PIECE_TYPES:
        problems.append("DIGIT_PIECE_TYPES differs from the literal")
    if pii_types.date_piece_types(pii_types.TYPE_REGISTRY) != _LITERAL_DATE_PIECE_TYPES:
        problems.append("DATE_PIECE_TYPES differs from the literal")
    if pii_types.derived_piece_types(pii_types.TYPE_REGISTRY) != _LITERAL_DERIVED_PIECE_TYPES:
        problems.append("DERIVED_PIECE_TYPES differs from the literal")
    if pii_types.squeezed_types(pii_types.TYPE_REGISTRY) != _LITERAL_SQUEEZED_TYPES:
        problems.append("SQUEEZED_TYPES differs from the literal")
    if pii_types.NEEDLE_KINDS != _LITERAL_NEEDLE_KINDS:
        problems.append("NEEDLE_KINDS differs from the literal")
    if pii_types.NEW_ITEM_TYPES != ():
        problems.append("NEW_ITEM_TYPES must be empty before any v6 case is admitted")
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


CHECKS = (test_v5_tables_reproduced, test_registry_rules, test_no_engine,
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
