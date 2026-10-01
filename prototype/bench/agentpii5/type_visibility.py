# type_visibility.py — S7/G8: the visibility of ALL 55 v6 item types, the four
# coverage AXES each one is read on, and the exact place the claim stops.
#
#     cd prototype && source .venv/bin/activate
#     python3 -m bench.agentpii5.type_visibility            # print the matrix
#     python3 -m bench.agentpii5.type_visibility --write     # + the JSON artifact
#
# WHY THIS MODULE EXISTS (V1 SPEC §3, §6 S7). V0 asked whether the engine
# supports the 55 new types, and V1's answer is a COUNT, not an adjective: every
# one of the 55 is VISIBLE in one matrix with its axis status, and NOT ONE of
# them is claimed supported. Two failures this instrument is built to make
# impossible:
#
#   1. A TYPE THAT IS NOT MEASURED DISAPPEARS. A registry record no matrix row
#      names is a type the report silently does not have. `rows()` iterates the
#      LIVE registry (`pii_types.TYPE_REGISTRY`), never a hand copy, so a 56th
#      record cannot be added without a row appearing here.
#   2. AN UNSUPPORTED TYPE IS ALIASED INTO A v5 TYPE AND PASSES. Six v6 records
#      carry an `engine_labels` hint (SPEC §3.3) that names existing v5 engine
#      vocabulary — `BANK_ACCOUNT → ACCOUNT`, `IP_ADDRESS → IP`, and four more.
#      A label is a mapping hint, NOT a detection claim; `supported_by_engine`
#      is therefore False BY CONSTRUCTION (see `supported_by_engine`) and is
#      never read off `engine_labels`. `resolved_id` pins the other half: a
#      metric row for a v6 type is keyed by the v6 id, never by the v5 name it
#      maps onto, so «count it under ACCOUNT» cannot earn it a pass either.
#
# WHAT A ROW DOES *NOT* SAY. Nothing here is a statement that the engine
# detects, substitutes or restores any of the 55. The axes below are coverage
# dispositions copied from the accepted owner decisions
# (`work/contracts-revision-2/DECISION-COVERAGE.json`, literals recorded in the
# V1 plan's `type_coverage`); «COVERED_BY_OWNER_DECISION» means the DECISION
# exists, and the per-type open items say what is still unproven. `claim()` is
# the machine-readable form of that boundary.
#
# PURE AND ENGINE-FREE, like `pii_types.py`: this module imports nothing from
# `pseudex`, `licensing` or any other module of this package.
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from bench.agentpii5 import pii_types

HERE: Path = Path(__file__).resolve().parent
OUT_PATH: Path = HERE / "review" / "type-visibility-55.json"

GENERATED_BY: str = "bench.agentpii5.type_visibility"

# The four axes S7 requires every one of the 55 to be visible on.
AXIS_IDS: tuple[str, ...] = ("checksum", "agent_form", "typed_invalid", "all_parts")
# The accepted owner decision each axis is covered by. A status is never
# invented below: it is either one of these decisions or NOT_APPLICABLE.
AXIS_DECISIONS: dict[str, str] = {
    "checksum": "COV-CHECKSUM-INHERIT",
    "agent_form": "COV-AGENT-FORM",
    "typed_invalid": "COV-TYPED-INVALID",
    "all_parts": "COV-ALL-PARTS",
}
COVERED: str = "COVERED_BY_OWNER_DECISION"
NOT_APPLICABLE: str = "NOT_APPLICABLE"

# The closed set of open items a row may carry (§3.2). A row that opened a
# fifth kind would have to name it here first, so the vocabulary cannot drift.
OPEN_ITEM_IDS: tuple[str, ...] = (
    "GRAMMAR_UNASSERTED",
    "NOTATION_UNASSERTED",
    "MINT_UNASSERTED",
    "TYPED_INVALID_PATH_UNTESTED",
    "ENGINE_SUPPORT_NOT_CLAIMED",
)
UNSUPPORTED_REASON: str = "registry record only; native support is proven per type after V1/N1"


def _registry(registry: tuple[pii_types.TypeSpec, ...] | None) -> tuple[pii_types.TypeSpec, ...]:
    return pii_types.TYPE_REGISTRY if registry is None else registry


def v5_ids(registry: tuple[pii_types.TypeSpec, ...] | None = None) -> tuple[str, ...]:
    """The eleven v5 records of the LIVE registry — the ids a v6 row must never
    be reported under."""
    return tuple(spec.id for spec in _registry(registry)
                 if spec.origin == pii_types.ORIGIN_V5)


def v6_item_ids(registry: tuple[pii_types.TypeSpec, ...] | None = None) -> tuple[str, ...]:
    """The 55 v6 item types, in registry order (the order the matrix prints)."""
    return tuple(spec.id for spec in _registry(registry)
                 if spec.item_type and spec.origin == pii_types.ORIGIN_V6)


def supported_by_engine(spec: pii_types.TypeSpec) -> bool:
    """False for every one of the 55, BY CONSTRUCTION.

    Not measured, not derived — there is no engine evidence to derive it from
    and no registry field that could stand in for one. `engine_labels` is
    deliberately NOT read: it is a mapping hint onto existing v5 vocabulary
    (SPEC §3.3), and a hint that pointed at a supported v5 type is exactly the
    alias that must not buy a pass. The negative control for this function is
    `test_type_visibility.test_an_engine_label_never_buys_support`."""
    return False


def resolved_id(type_id: str, registry: tuple[pii_types.TypeSpec, ...] | None = None) -> str:
    """The id a report row for `type_id` MUST be keyed by: the id itself.

    A v6 type that maps onto v5 vocabulary keeps its OWN id here. `ACCOUNT` is
    what `BANK_ACCOUNT` may be counted *beside*; it is never what it is counted
    *as*. Raises for an id the registry does not hold, so a typo cannot resolve
    to a plausible neighbour."""
    known = {spec.id for spec in _registry(registry)}
    if type_id not in known:
        raise ValueError(f"type_visibility: {type_id!r} is not a registry id")
    return type_id


def _carrier(axis: str, registry: tuple[pii_types.TypeSpec, ...]) -> str:
    """The registry record that carries `axis` for the whole registry when a
    given row does not — `all_parts` is carried by the v5 NAME record (the only
    `identifying_roles` with more than one part), and naming it is what keeps
    the axis visible instead of silently absent."""
    if axis == "all_parts":
        for spec in registry:
            if len(spec.identifying_roles) > 1:
                return spec.id
    return ""


def axes_for(spec: pii_types.TypeSpec,
             registry: tuple[pii_types.TypeSpec, ...] | None = None) -> tuple[AxisView, ...]:
    """The four axis rows for one record. `applies` is the live registry fact;
    `status` is the accepted owner decision when it applies, NOT_APPLICABLE when
    it does not. `carrier` names the record that holds the axis for the registry
    when this row does not."""
    reg = _registry(registry)
    applies = {
        "checksum": bool(spec.generated_checksum),
        "agent_form": bool(spec.form_features),
        "typed_invalid": bool(spec.cues or spec.field_keys or spec.pd_context),
        "all_parts": len(spec.identifying_roles) > 1,
    }
    out: list[AxisView] = []
    for axis in AXIS_IDS:
        holds = applies[axis]
        out.append(AxisView(
            axis=axis,
            applies=holds,
            status=COVERED if holds else NOT_APPLICABLE,
            decision_id=AXIS_DECISIONS[axis] if holds else "",
            carrier="" if holds else _carrier(axis, reg),
        ))
    return tuple(out)


@dataclass(frozen=True)
class AxisView:
    axis: str                        # one of AXIS_IDS
    applies: bool                    # the live registry fact
    status: str                      # COVERED | NOT_APPLICABLE
    decision_id: str                 # "" when NOT_APPLICABLE
    carrier: str                     # the record that holds it, when this row does not


@dataclass(frozen=True)
class TypeRow:
    """One of the 55, as the matrix prints it — counts, never adjectives."""

    type_id: str
    type_class: str                  # K | KC | C
    origin: str                      # always "v6" here
    supported_by_engine: bool        # always False (see `supported_by_engine`)
    unsupported_reason: str
    axes: tuple[AxisView, ...]
    engine_labels: tuple[str, ...]   # a mapping HINT, never a support claim
    grammar_uncertain: bool
    notation_unasserted: bool
    mint_unasserted: bool
    open_items: tuple[str, ...] = ()

    def axis(self, axis_id: str) -> AxisView:
        for one in self.axes:
            if one.axis == axis_id:
                return one
        raise KeyError(axis_id)


def _open_items(spec: pii_types.TypeSpec) -> tuple[str, ...]:
    items: list[str] = []
    if spec.grammar_status == "ГРАММАТИКА?":
        items.append("GRAMMAR_UNASSERTED")
    if not spec.value_notation:
        items.append("NOTATION_UNASSERTED")
    if not spec.mint:
        items.append("MINT_UNASSERTED")
    items.append("TYPED_INVALID_PATH_UNTESTED")
    items.append("ENGINE_SUPPORT_NOT_CLAIMED")
    return tuple(items)


def rows(registry: tuple[pii_types.TypeSpec, ...] | None = None) -> tuple[TypeRow, ...]:
    """The 55 rows — one per v6 item type of the LIVE registry, in registry
    order. The length is read, never asserted to 55 here; the test asserts it
    against the registry so a widening moves both together."""
    reg = _registry(registry)
    return tuple(
        TypeRow(
            type_id=spec.id,
            type_class=spec.type_class,
            origin=spec.origin,
            supported_by_engine=supported_by_engine(spec),
            unsupported_reason=UNSUPPORTED_REASON,
            axes=axes_for(spec, reg),
            engine_labels=tuple(spec.engine_labels),
            grammar_uncertain=spec.grammar_status == "ГРАММАТИКА?",
            notation_unasserted=not spec.value_notation,
            mint_unasserted=not spec.mint,
            open_items=_open_items(spec),
        )
        for spec in reg
        if spec.item_type and spec.origin == pii_types.ORIGIN_V6
    )


def alias_violations(registry: tuple[pii_types.TypeSpec, ...] | None = None) -> list[str]:
    """Every way a row could turn an unsupported type into a passing one.

    Four rules, each of which has been the tempting shortcut at some point:
      * the row's id is the v6 id — never a v5 id the hint names;
      * `supported_by_engine` is False, whatever `engine_labels` says;
      * a `COVERED` axis status always `applies` (no coverage granted to a type
        that has nothing to cover);
      * a `NOT_APPLICABLE` axis names a real carrier or is genuinely unheld (an
        axis cannot be dropped by leaving the status empty)."""
    reg = _registry(registry)
    problems: list[str] = []
    banned = set(v5_ids(reg))
    known = {spec.id for spec in reg}
    for row in rows(reg):
        if row.type_id in banned:
            problems.append(f"{row.type_id}: a v5 id reported as a v6 type row")
        if row.supported_by_engine:
            problems.append(f"{row.type_id}: supported_by_engine is True — "
                            f"nothing in V1 proves engine support for any of the 55")
        if resolved_id(row.type_id, reg) != row.type_id:
            problems.append(f"{row.type_id}: resolved id is not the type's own id")
        for axis in row.axes:
            if axis.status == COVERED and not axis.applies:
                problems.append(f"{row.type_id}.{axis.axis}: COVERED without applying")
            if axis.status not in (COVERED, NOT_APPLICABLE):
                problems.append(f"{row.type_id}.{axis.axis}: status {axis.status!r} "
                                f"is not a declared disposition")
            if axis.status == NOT_APPLICABLE:
                if axis.decision_id:
                    problems.append(f"{row.type_id}.{axis.axis}: NOT_APPLICABLE "
                                    f"cites {axis.decision_id}")
                if axis.carrier and axis.carrier not in known:
                    problems.append(f"{row.type_id}.{axis.axis}: carrier "
                                    f"{axis.carrier!r} is not a registry id")
    return problems


def claim(registry: tuple[pii_types.TypeSpec, ...] | None = None) -> dict[str, object]:
    """The machine-readable boundary. `supported_by_engine` is 0 by definition,
    and the counts below are the registry's own arithmetic."""
    reg = _registry(registry)
    all_rows = rows(reg)
    return {
        "claim": "REGISTRY RECORDS, NOT ENGINE SUPPORT",
        "supported_by_engine": sum(1 for row in all_rows if row.supported_by_engine),
        "types": len(all_rows),
        "checksum_carrying": sum(1 for row in all_rows
                                 if row.axis("checksum").applies),
        "agent_form_declared": sum(1 for row in all_rows
                                   if row.axis("agent_form").applies),
        "typed_context_declared": sum(1 for row in all_rows
                                      if row.axis("typed_invalid").applies),
        "all_parts_applicable": sum(1 for row in all_rows
                                    if row.axis("all_parts").applies),
        "all_parts_carrier": _carrier("all_parts", reg),
        "grammar_uncertain": sum(1 for row in all_rows if row.grammar_uncertain),
        "notation_unasserted": sum(1 for row in all_rows if row.notation_unasserted),
        "mint_unasserted": sum(1 for row in all_rows if row.mint_unasserted),
        "engine_labels": {row.type_id: list(row.engine_labels)
                          for row in all_rows if row.engine_labels},
        "v5_slice": list(v5_ids(reg)),
        "type_classes": {c: sum(1 for row in all_rows if row.type_class == c)
                         for c in sorted({row.type_class for row in all_rows})
                         if c not in ("v5",)},
    }


def _row_json(row: TypeRow) -> dict[str, object]:
    return {
        "type": row.type_id,
        "type_class": row.type_class,
        "origin": row.origin,
        "supported_by_engine": row.supported_by_engine,
        "unsupported_reason": row.unsupported_reason,
        "axes": {axis.axis: {"applies": axis.applies, "status": axis.status,
                             "decision_id": axis.decision_id,
                             "carrier": axis.carrier}
                 for axis in row.axes},
        "engine_labels": list(row.engine_labels),
        "grammar_uncertain": row.grammar_uncertain,
        "notation_unasserted": row.notation_unasserted,
        "mint_unasserted": row.mint_unasserted,
        "open_items": list(row.open_items),
    }


def matrix(registry: tuple[pii_types.TypeSpec, ...] | None = None) -> dict[str, object]:
    """The JSON artifact: the claim boundary, then all 55 rows."""
    reg = _registry(registry)
    out = {
        "generated_by": GENERATED_BY,
        "registry_sha256": hashlib.sha256(
            Path(pii_types.__file__).read_bytes()).hexdigest(),
        "registry_records": len(reg),
        "type_count": len(rows(reg)),
        "axes": list(AXIS_IDS),
        "axis_decisions": dict(AXIS_DECISIONS),
        "open_items": list(OPEN_ITEM_IDS),
        "claim": claim(reg),
        "types": [_row_json(row) for row in rows(reg)],
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true",
                        help=f"write {OUT_PATH.name} as well as printing")
    args = parser.parse_args(sys.argv[1:])
    doc = matrix()
    problems = alias_violations()
    print(f"type_visibility: {doc['type_count']} v6 item types · "
          f"supported_by_engine={doc['claim']['supported_by_engine']} · "
          f"alias violations={len(problems)}")
    for row in doc["types"]:
        axes = ", ".join(f"{name}={'yes' if body['applies'] else 'no'}"
                         for name, body in row["axes"].items())
        print(f"  {row['type']:<24} {row['type_class']:<3} "
              f"supported={row['supported_by_engine']}  {axes}"
              + (f"  labels={row['engine_labels']}" if row["engine_labels"] else ""))
    for problem in problems:
        print(f"  VIOLATION {problem}")
    if args.write:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
        print(f"wrote {OUT_PATH}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
