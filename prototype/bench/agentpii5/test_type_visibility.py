# test_type_visibility.py — the S7/G8 instrument over `type_visibility.py`.
#
#     cd prototype && source .venv/bin/activate
#     python3 -m bench.agentpii5.test_type_visibility
#
# WHAT IT PINS, and why each rule has a NEGATIVE half (an instrument that cannot
# fail is not an instrument):
#
#   1. ALL 55 v6 item types are visible, one row each, all four axes present,
#      and the row set is the LIVE registry's — a 56th record appears here
#      without anyone editing this file.
#   2. NOT ONE is marked supported. `supported_by_engine` is False for every
#      row and the claim's count is 0; the negative control shows that even an
#      `engine_labels` hint naming a live v5 type (`NAME`) does not flip it.
#   3. AN UNSUPPORTED TYPE CANNOT BE ALIASED INTO A v5 TYPE TO PASS. A v6 row is
#      keyed by its own id (`resolved_id`), the six hints stay metadata, and the
#      negative control — a v6 record whose id IS a v5 id — is caught by
#      `alias_violations`.
#   4. The axis statuses are closed and honest: `COVERED` only where the axis
#      applies, `NOT_APPLICABLE` never citing a decision, and `all_parts` names
#      the v5 NAME record as its carrier instead of vanishing.
#   5. The counts the V1 DESIGN declares are reproduced from the LIVE registry:
#      11 checksum-carrying, 9 grammar-uncertain, 6 notation-unasserted, 17
#      mint-unasserted, classes K 50 / KC 4 / C 1.
#
# NO ENGINE, NO MODEL, NO NETWORK: this module imports `type_visibility`, which
# imports only `pii_types`.
from __future__ import annotations

import dataclasses
import sys
from collections.abc import Callable

from bench.agentpii5 import pii_types, type_visibility as tv

# The counts V1 SPEC §3 declares ("Counts reproduced"). They are asserted
# against the LIVE registry below: if the registry moved and this file did not,
# the test says so instead of quietly printing a new number.
DECLARED: dict[str, int] = {
    "type_count": 55,
    "checksum_carrying": 11,
    "grammar_uncertain": 9,
    "notation_unasserted": 6,
    "mint_unasserted": 17,
    "typed_context_declared": 55,
    "agent_form_declared": 55,
}
DECLARED_CLASSES: dict[str, int] = {"K": 50, "KC": 4, "C": 1}
# The six records whose `engine_labels` name existing v5 engine vocabulary
# (SPEC §3.3) — the exact set the alias guard is about.
DECLARED_LABELLED: dict[str, tuple[str, ...]] = {
    "BANK_ACCOUNT": ("ACCOUNT",),
    "OGRNIP": ("OGRN",),
    "OMS_ENP": ("OMS",),
    "STS_NUMBER": ("VEHICLE_DOC",),
    "PTS_NUMBER": ("VEHICLE_DOC",),
    "IP_ADDRESS": ("IP",),
}


def _with(**changes) -> tuple[pii_types.TypeSpec, ...]:
    """The live registry with the FIRST v6 item record replaced by a copy
    carrying `changes` — the seam every negative control below drives."""
    registry = list(pii_types.TYPE_REGISTRY)
    index = next(i for i, spec in enumerate(registry)
                 if spec.item_type and spec.origin == pii_types.ORIGIN_V6)
    registry[index] = dataclasses.replace(registry[index], **changes)
    return tuple(registry)


def test_all_55_are_visible() -> list[str]:
    problems: list[str] = []
    live = pii_types.NEW_ITEM_TYPES
    rows = tv.rows()
    ids = [row.type_id for row in rows]
    if len(rows) != len(live):
        problems.append(f"{len(rows)} rows for {len(live)} registered v6 item types")
    if len(set(ids)) != len(ids):
        problems.append(f"duplicate ids in the matrix: {sorted(ids)}")
    if ids != list(live):
        problems.append("the matrix rows are not the registry's v6 item types in order")
    if set(ids) != set(live):
        problems.append(f"rows {sorted(set(ids) - set(live))} are not registered")
    for row in rows:
        axes = {axis.axis for axis in row.axes}
        if axes != set(tv.AXIS_IDS):
            problems.append(f"{row.type_id}: axes {sorted(axes)} != {list(tv.AXIS_IDS)}")
        for axis in row.axes:
            if axis.status not in (tv.COVERED, tv.NOT_APPLICABLE):
                problems.append(f"{row.type_id}.{axis.axis}: status {axis.status!r}")
            if axis.status == tv.COVERED and not axis.applies:
                problems.append(f"{row.type_id}.{axis.axis}: COVERED without applying")
            if axis.status == tv.NOT_APPLICABLE and axis.decision_id:
                problems.append(f"{row.type_id}.{axis.axis}: NOT_APPLICABLE cites "
                                f"{axis.decision_id}")
            if axis.applies and not axis.decision_id:
                problems.append(f"{row.type_id}.{axis.axis}: applies with no decision")
        for item in row.open_items:
            if item not in tv.OPEN_ITEM_IDS:
                problems.append(f"{row.type_id}: open item {item!r} is not declared")
    # THE NEGATIVE: the instrument reads the REGISTRY, not a snapshot of it. A
    # record with no form feature loses its agent_form coverage; a record with
    # no checksum loses its checksum coverage.
    mutated = tv.rows(_with(form_features=(), generated_checksum=""))
    first = next(row for row in mutated if row.type_id == rows[0].type_id)
    if first.axis("agent_form").applies or first.axis("agent_form").status != tv.NOT_APPLICABLE:
        problems.append("a record with no form feature kept its agent_form coverage")
    if first.axis("checksum").applies:
        problems.append("a record with no checksum kept its checksum coverage")
    return problems


def test_no_type_is_marked_supported() -> list[str]:
    problems: list[str] = []
    rows = tv.rows()
    marked = [row.type_id for row in rows if row.supported_by_engine]
    if marked:
        problems.append(f"{len(marked)} rows claim engine support: {marked}")
    body = tv.claim()
    if body["supported_by_engine"] != 0:
        problems.append(f"the claim counts {body['supported_by_engine']} supported types")
    if body["types"] != len(rows):
        problems.append(f"the claim counts {body['types']} types, the matrix has {len(rows)}")
    if "NOT ENGINE SUPPORT" not in str(body["claim"]).upper():
        problems.append("the claim boundary does not say what it is")
    for row in rows:
        if not row.unsupported_reason:
            problems.append(f"{row.type_id}: unsupported with no stated reason")
    # THE NEGATIVE: an `engine_labels` hint pointing straight at a live v5 type
    # is the most support-looking input the registry can carry — and it still
    # does not flip the flag.
    first = next(spec for spec in pii_types.TYPE_REGISTRY
                 if spec.item_type and spec.origin == pii_types.ORIGIN_V6)
    hint = dataclasses.replace(first, engine_labels=("NAME",))
    if tv.supported_by_engine(hint):
        problems.append("an engine_label naming a v5 type bought engine support")
    return problems


def test_an_unsupported_type_cannot_be_aliased() -> list[str]:
    problems: list[str] = []
    rows = tv.rows()
    registered = set(pii_types.NEW_ITEM_TYPES)
    v5 = set(tv.v5_ids())
    for row in rows:
        if row.type_id not in registered:
            problems.append(f"{row.type_id}: a row that is not a registered v6 type")
        if row.type_id in v5:
            problems.append(f"{row.type_id}: a v5 id reported as a v6 row")
        if tv.resolved_id(row.type_id) != row.type_id:
            problems.append(f"{row.type_id}: resolves to another id")
    labelled = {row.type_id: row.engine_labels for row in rows if row.engine_labels}
    if labelled != DECLARED_LABELLED:
        problems.append(f"the engine-label set moved: {labelled}")
    v6 = set(pii_types.NEW_ITEM_TYPES)
    for type_id, labels in labelled.items():
        for label in labels:
            if tv.resolved_id(type_id) == label:
                problems.append(f"{type_id}: is reported under its label {label!r}")
            # A LABEL IS ENGINE VOCABULARY, NOT A REGISTRY ID: `ACCOUNT`,
            # `OGRN`, `OMS`, `VEHICLE_DOC`, `IP` are names the ENGINE uses for
            # the v5 types. What must never happen is a label colliding with a
            # REGISTERED id, because then two types would share one key.
            if label in v6 or label in v5:
                problems.append(f"{type_id}: label {label!r} collides with a registry id")
            if not label.strip():
                problems.append(f"{type_id}: an empty engine label")
        row = next(r for r in rows if r.type_id == type_id)
        if row.supported_by_engine:
            problems.append(f"{type_id}: labelled AND marked supported")
    if tv.alias_violations():
        problems.append(f"the live registry already violates the alias guard: "
                        f"{tv.alias_violations()}")
    # THE NEGATIVE: a v6 record whose id IS a v5 id is caught, so the guard
    # cannot be satisfied by leaving it unread.
    broken = tv.alias_violations(_with(id="NAME"))
    if not any("NAME" in problem for problem in broken):
        problems.append("a v6 row carrying the v5 id NAME was not caught")
    # and the id itself: an unknown id does not resolve to a plausible neighbour
    try:
        tv.resolved_id("NOT_A_REGISTERED_TYPE")
        problems.append("resolved_id accepted an id the registry does not hold")
    except ValueError:
        pass
    return problems


def test_all_parts_is_carried_not_dropped() -> list[str]:
    """The `all_parts` axis applies to NONE of the 55 — the NAME record carries
    it — and the matrix has to say so rather than leave the axis blank."""
    problems: list[str] = []
    rows = tv.rows()
    applicable = [row.type_id for row in rows if row.axis("all_parts").applies]
    if applicable:
        problems.append(f"all_parts applies to v6 rows: {applicable}")
    carrier = tv.claim()["all_parts_carrier"]
    if carrier != "NAME":
        problems.append(f"the all_parts carrier is {carrier!r}, not the NAME record")
    name = next(spec for spec in pii_types.TYPE_REGISTRY if spec.id == "NAME")
    if name.identifying_roles != ("surname", "given", "patronymic"):
        problems.append(f"NAME identifying_roles moved: {name.identifying_roles}")
    for row in rows:
        axis = row.axis("all_parts")
        if axis.status != tv.NOT_APPLICABLE:
            problems.append(f"{row.type_id}.all_parts: status {axis.status!r}")
        if axis.carrier != "NAME":
            problems.append(f"{row.type_id}.all_parts: carrier {axis.carrier!r}")
    return problems


def test_the_declared_counts_are_reproduced() -> list[str]:
    problems: list[str] = []
    body = tv.claim()
    doc = tv.matrix()
    counts = dict(body)
    counts["type_count"] = doc["type_count"]
    for key, expected in DECLARED.items():
        got = counts.get(key)
        if got != expected:
            problems.append(f"{key}: live registry says {got}, SPEC §3 declares {expected}")
    classes = body.get("type_classes", {})
    if classes != DECLARED_CLASSES:
        problems.append(f"type classes: {classes} != {DECLARED_CLASSES}")
    if body["all_parts_applicable"] != 0:
        problems.append(f"all_parts_applicable is {body['all_parts_applicable']}, not 0")
    if doc["type_count"] != len(pii_types.NEW_ITEM_TYPES):
        problems.append("type_count is not the registry's own v6 item count")
    if doc["registry_records"] != 66:
        problems.append(f"registry_records is {doc['registry_records']}, not 66")
    return problems


def test_the_matrix_artifact_is_printable() -> list[str]:
    """The artifact builder is deterministic and carries every row — the thing
    S8 re-reads without running the test suite."""
    problems: list[str] = []
    first = tv.matrix()
    second = tv.matrix()
    if first != second:
        problems.append("two builds of the matrix differ")
    types = first.get("types", [])
    if len(types) != len(pii_types.NEW_ITEM_TYPES):
        problems.append(f"the artifact holds {len(types)} types")
    ids = [row["type"] for row in types]
    if ids != list(pii_types.NEW_ITEM_TYPES):
        problems.append("the artifact's rows are not the registry's v6 item types in order")
    for row in types:
        if set(row["axes"]) != set(tv.AXIS_IDS):
            problems.append(f"{row['type']}: the artifact is missing an axis")
        if row["supported_by_engine"]:
            problems.append(f"{row['type']}: the artifact claims support")
    return problems


CHECKS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("all_55_are_visible", test_all_55_are_visible),
    ("no_type_is_marked_supported", test_no_type_is_marked_supported),
    ("an_unsupported_type_cannot_be_aliased", test_an_unsupported_type_cannot_be_aliased),
    ("all_parts_is_carried_not_dropped", test_all_parts_is_carried_not_dropped),
    ("the_declared_counts_are_reproduced", test_the_declared_counts_are_reproduced),
    ("the_matrix_artifact_is_printable", test_the_matrix_artifact_is_printable),
)


def main() -> int:
    failures: list[str] = []
    for name, check in CHECKS:
        try:
            problems = check()
        except Exception as error:  # noqa: BLE001 - the exception IS the failure
            problems = [f"raised {error!r}"]
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    broken = {one.split(":")[0] for one in failures}
    print(f"type_visibility: {'PASS' if not failures else 'FAIL'} "
          f"({len(CHECKS) - len(broken)}/{len(CHECKS)} passed)")
    if failures:
        print("\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
