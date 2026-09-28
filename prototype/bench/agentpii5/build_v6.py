"""AgentPII-RU v6 — write the v6 corpus and ladder into `bench/agentpii5/v6/`.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_build_v6

THE FILES. `write_corpus` writes `corpus.v5.json` (the v5 shape, every v6 case
with its `v6` meta) and `corpus.json` (the v4 view of `.base`, for the v4 readers
that must keep opening a v6 corpus unchanged). `write_ladder_v6` writes
`ladder.json` — a MINIATURE of the corpus (K6-13) with a frozen holdout (K6-12).

NOT THE PINNED FILES, EVER. `corpus.v5.json` / `corpus.json` / `ladder.json` in
`bench/agentpii5/` are the frozen v5 baseline; `build_v6` refuses `out == HERE`
(R6-32). The v6 corpus lives only under `contracts_v6.V6_DIR` (`bench/agentpii5/v6`).

THE MINIATURE LADDER (K6-13, §4.6). The debug tiers are prefixes of one
stratified order over the pool (corpus minus holdout), so nano ⊂ small ⊂ medium
⊂ pool by construction. The order is a miniature by `industry` (proportion with
tolerance) and covers every `industry`, `type_class` and `pii_type` value from
`small`. The holdout is 20% drawn BEFORE any debug tier exists — its value is
that it was drawn before anybody looked — and a redraw that moves an existing id
is refused (K6-12).

THE TRUNCATED TIER IS REFUSED (R6-37, §4.6). v5's `build_ladder_v5` silently
truncates a tier to the pool (`min(TIER_SIZES[name], len(order))`) and a tier
that is «nano 30» but holds 12 cases would print under the full name. v6 refuses
a draw whose pool cannot fill a declared tier size, so no tier ever wears a name
it does not have the size for.

NOTHING HERE IMPORTS `pseudex`.
"""
import hashlib
import json
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from bench.agentpii4 import schema as v4
from bench.agentpii5 import contracts_v6
from bench.agentpii5 import pii_types
from bench.agentpii5.contracts import CaseV5
from bench.agentpii5.schema import case_v5_to_json, corpus_digest_v5
from bench.agentpii5.schema_v6 import (_admitted_types, _industry, merged_registry,
                                       PILOT_INDUSTRIES)
from bench.agentpii5.tools_v6 import TOOLS_V6, V6_META

HERE: Path = Path(__file__).resolve().parent
V6_OUT: Path = HERE / "v6"
SEED: int = 6

V6_HOLDOUT_SHARE: float = 0.20
# The §4.6 tier table for N = 500: nano 30, small 120, medium 300, пул 400.
V6_TIER_SIZES: dict[str, int] = {"nano": 30, "small": 120, "medium": 300, "pool": 400,
                                 "max": 0, "holdout": 0}
V6_DEBUG_TIERS: tuple[str, ...] = ("nano", "small", "medium", "pool")
# The axes the ladder is a miniature OF: industry is single-valued (proportion
# AND coverage); type_class and pii_type are multi-valued (coverage only, like
# v5's `vertical`/`pii_type` — a case carries several types of several classes,
# so a share over them is not a share).
V6_PROPORTION_AXES: tuple[str, ...] = ("industry",)
V6_COVERAGE_AXES: tuple[str, ...] = ("industry", "type_class", "pii_type")
# The ladder share tolerance, inherited from v5's miniature discipline.
LADDER_SHARE_TOLERANCE: float = 0.025
LADDER_ABSOLUTE_SLACK: float = 1.0


class PinnedPathRefused(ValueError):
    """`out` points at the frozen v5 files; the v6 corpus lives under `v6/`."""


class TruncatedTier(ValueError):
    """A tier whose declared size the pool cannot fill — refused, not truncated."""


# --- axis values of one case --------------------------------------------------------

def _v6_types() -> frozenset[str]:
    return frozenset(t.id for t in pii_types.TYPE_REGISTRY
                     if t.item_type and t.origin == pii_types.ORIGIN_V6)


_V6_TYPE_IDS: frozenset[str] = _v6_types()


def _type_class_of(type_id: str) -> str:
    for t in pii_types.TYPE_REGISTRY:
        if t.id == type_id:
            return t.type_class
    return ""


def case_axis_values(case: CaseV5, axis: str) -> frozenset[str]:
    """The values a case carries on one ladder axis, read the ONE way the draw and
    the check both read it (mirrors `build.case_slice_values`'s discipline)."""
    if axis == "industry":
        return frozenset({_industry(case)})
    if axis == "type_class":
        return frozenset({_type_class_of(item.type) for item in case.base.pii
                          if item.type in _V6_TYPE_IDS})
    if axis == "pii_type":
        crossed = {hop.item_id for hop in case.hops}
        return frozenset({item.type for item in case.base.pii
                          if item.id in crossed and item.type in _V6_TYPE_IDS})
    raise ValueError(f"case_axis_values: no axis {axis!r}")


# --- the stratified order (the miniature) -------------------------------------------

def _tie_key(case_id: str, seed: int) -> str:
    """The tie-break: a hash of (seed, id), never the input order (mirrors
    `build._tie_key` — a generator that varies a family by index must not have
    its first eight cases taken by «first by name»)."""
    return hashlib.sha256(f"v6-ladder:{seed}:{case_id}".encode("utf-8")).hexdigest()


def stratified_order_v6(cases: Sequence[CaseV5], seed: int) -> list[CaseV5]:
    """One order whose every prefix is a miniature by `industry`, and which covers
    every `industry`/`type_class`/`pii_type` value before it spends a case on
    proportion (the two passes of `build.stratified_order`, on the v6 axes)."""
    pool = sorted(cases, key=lambda case: _tie_key(case.base.id, seed))
    share_cells: dict[str, tuple[tuple[str, str], ...]] = {
        case.base.id: tuple((axis, next(iter(case_axis_values(case, axis))))
                            for axis in V6_PROPORTION_AXES) for case in pool}
    floor_cells: dict[str, set[tuple[str, str]]] = {
        case.base.id: {cell for axis in V6_COVERAGE_AXES
                       for cell in ((axis, value) for value in case_axis_values(case, axis))}
        for case in pool}
    total = len(pool)
    if total == 0:
        return []
    weight: Counter[tuple[str, str]] = Counter()
    for case in pool:
        weight.update(share_cells[case.base.id])
    share = {cell: count / total for cell, count in weight.items()}

    order: list[CaseV5] = []
    taken: set[str] = set()
    count: Counter[tuple[str, str]] = Counter()
    missing: set[tuple[str, str]] = {cell for case in pool for cell in floor_cells[case.base.id]}
    while missing:
        best: CaseV5 | None = None
        best_key: tuple[int, str] | None = None
        for case in pool:
            if case.base.id in taken:
                continue
            covered = len(missing.intersection(floor_cells[case.base.id]))
            if not covered:
                continue
            key = (-covered, _tie_key(case.base.id, seed))
            if best_key is None or key < best_key:
                best, best_key = case, key
        if best is None:
            raise RuntimeError(f"stratified_order_v6: cells {sorted(missing)[:3]} are carried "
                               f"by no case, though they were read off the pool")
        order.append(best)
        taken.add(best.base.id)
        count.update(share_cells[best.base.id])
        missing.difference_update(floor_cells[best.base.id])
    rest = [case for case in pool if case.base.id not in taken]
    while rest:
        step = len(order) + 1
        deficit = {cell: value * step - count[cell] for cell, value in share.items()}
        best = None
        best_score: tuple[float, str] | None = None
        for case in rest:
            score = -sum(deficit[cell] for cell in share_cells[case.base.id])
            key = (score, _tie_key(case.base.id, seed))
            if best_score is None or key < best_score:
                best, best_score = case, key
        if best is None:
            raise RuntimeError("stratified_order_v6: the deficit rule returned no case")
        order.append(best)
        count.update(share_cells[best.base.id])
        rest.remove(best)
    return order


def _tier_sha256(identifiers: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(sorted(identifiers)).encode("utf-8")).hexdigest()


def draw_holdout_v6(cases: Sequence[CaseV5], seed: int) -> frozenset[str]:
    """The 20% holdout, drawn BY PHASE: 20% of the pilot cases first, then 20% of
    the extension. A later extension re-orders only the extension draw, so the
    pilot ids already frozen stay exactly where they were (K6-12, §4.6)."""
    pilot = [case for case in cases if _industry(case) in PILOT_INDUSTRIES]
    extension = [case for case in cases if _industry(case) not in PILOT_INDUSTRIES]
    held: list[CaseV5] = []
    if pilot:
        held.extend(stratified_order_v6(pilot, seed)[:round(V6_HOLDOUT_SHARE * len(pilot))])
    if extension:
        held.extend(stratified_order_v6(extension, seed)[:round(V6_HOLDOUT_SHARE * len(extension))])
    return frozenset(case.base.id for case in held)


def build_ladder_v6(cases: Sequence[CaseV5], seed: int) -> dict[str, object]:
    """The v6 ladder object: a phase-aware 20% holdout drawn first, then the debug
    tiers as prefixes of a stratified order over the pool."""
    held_ids = draw_holdout_v6(cases, seed)
    pool = [case for case in cases if case.base.id not in held_ids]
    order = stratified_order_v6(pool, seed)
    tiers: dict[str, tuple[str, ...]] = {"holdout": tuple(sorted(held_ids))}
    for name in V6_DEBUG_TIERS:
        size = V6_TIER_SIZES[name]
        if size > len(order):
            raise TruncatedTier(
                f"ярус {name} просит {size} случаев, а пул держит {len(order)} — "
                f"усечённый ярус под полным именем не пишется (R6-37)")
        tiers[name] = tuple(sorted(case.base.id for case in order[:size]))
    tiers["max"] = tuple(sorted(case.base.id for case in cases))
    return {"version": 5, "seed": seed, "corpus_sha256": corpus_digest_v5(cases),
            "tiers": tiers, "tier_sha256": {name: _tier_sha256(list(ids))
                                            for name, ids in tiers.items()}}


def ladder_problems_v6(cases: Sequence[CaseV5], ladder: dict[str, object]) -> list[str]:
    """K6-13's checker: every tier is a miniature of the pool by `industry`, and
    every tier (holdout included) covers every `industry`/`type_class`/`pii_type`
    value the corpus carries."""
    by_id = {case.base.id: case for case in cases}
    tiers = ladder.get("tiers")
    if not isinstance(tiers, dict):
        return ["K6-13 the ladder carries no tiers"]
    strangers = sorted({one for members in tiers.values() for one in members} - set(by_id))
    if strangers:
        return [f"K6-13 the ladder names {len(strangers)} cases not in the corpus: "
                f"{strangers[:3]}"]
    problems: list[str] = []
    values: dict[str, set[str]] = {}
    for axis in V6_COVERAGE_AXES:
        values[axis] = {value for case in cases for value in case_axis_values(case, axis)}
    for name in (*V6_DEBUG_TIERS, "holdout", "max"):
        members = [by_id[one] for one in tiers.get(name, ())]
        if not members:
            problems.append(f"K6-13 tier {name} is empty")
            continue
        for axis in V6_COVERAGE_AXES:
            lost = sorted(values[axis] - {value for case in members
                                          for value in case_axis_values(case, axis)})
            if lost:
                problems.append(f"K6-13 tier {name} ({len(members)} cases) does not cover "
                                f"axis {axis}: missing {lost}")
    held = set(tiers.get("holdout", ()))
    pool = [case for case in cases if case.base.id not in held]
    if not pool:
        return problems
    for name in V6_DEBUG_TIERS:
        members = [by_id[one] for one in tiers.get(name, ())]
        if not members:
            continue
        allowed = LADDER_ABSOLUTE_SLACK + LADDER_SHARE_TOLERANCE * len(members)
        for axis in V6_PROPORTION_AXES:
            whole = Counter(next(iter(case_axis_values(case, axis))) for case in pool)
            here = Counter(next(iter(case_axis_values(case, axis))) for case in members)
            for value, count in sorted(whole.items()):
                target = len(members) * count / len(pool)
                if abs(here.get(value, 0) - target) > allowed:
                    problems.append(f"K6-13 tier {name} is not a miniature of the pool on "
                                    f"axis {axis}: {value} — {here.get(value, 0)} cases vs "
                                    f"{target:.1f} by pool share ({count}/{len(pool)}), "
                                    f"tolerance ±{allowed:.1f}")
    return problems


def _refuse_pinned(out: Path) -> None:
    if out.resolve() == HERE.resolve():
        raise PinnedPathRefused(
            f"ОТКАЗ: {out} — это каталог закреплённых v5 файлов; корпус v6 пишется "
            f"в {V6_OUT} (R6-32)")


# --- writing the files --------------------------------------------------------------

def write_corpus(cases: Sequence[CaseV5], out_dir: Path | str) -> str:
    """Both views of one v6 corpus, from one list of objects. Returns the v5 digest.

    `corpus.v5.json` is the whole case (with its `v6` meta); `corpus.json` is the
    v4 view (`case.base.to_json()`) every v4 reader opens — the two are written
    from the SAME objects so a v4 reader and a v5 reader can never disagree.
    """
    out = Path(out_dir)
    _refuse_pinned(out)
    out.mkdir(parents=True, exist_ok=True)
    digest = corpus_digest_v5(cases)
    (out / "corpus.v5.json").write_text(json.dumps({
        "version": 5, "cases": len(cases), "digest": digest,
        "corpus": [case_v5_to_json(case) for case in cases]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    bases = [case.base for case in cases]
    (out / "corpus.json").write_text(json.dumps({
        "version": 4, "cases": len(bases), "digest": v4.corpus_digest(bases),
        "corpus": [case.to_json() for case in bases]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return digest


def write_ladder_v6(cases: Sequence[CaseV5], out_dir: Path | str) -> dict[str, object]:
    """Write `ladder.json`: a miniature of the corpus with a frozen holdout.

    THE HOLDOUT IS KEPT, NOT REBUILT. If `ladder.json` already names the same
    corpus (same `corpus_sha256`) and the same holdout membership, the file is
    left untouched; a redraw that would move an existing holdout id is refused
    (K6-12). A draw whose pool cannot fill a declared tier is refused (R6-37).
    """
    out = Path(out_dir)
    _refuse_pinned(out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "ladder.json"
    fresh = build_ladder_v6(cases, SEED)
    if path.exists():
        kept = json.loads(path.read_text(encoding="utf-8"))
        if kept.get("corpus_sha256") == fresh["corpus_sha256"]:
            return fresh                              # unchanged: the file is already right
        if isinstance(kept.get("tiers"), dict) and "holdout" in kept["tiers"]:
            moved = (set(kept["tiers"]["holdout"]) ^ set(fresh["tiers"]["holdout"])) \
                & {case.base.id for case in cases}
            if moved:
                raise TruncatedTier(
                    f"ОТКАЗ: {len(moved)} id сменили бы ярус холдаута — холдаут "
                    f"заморожен (K6-12): {sorted(moved)[:5]}")
    path.write_text(json.dumps({
        "version": fresh["version"], "seed": fresh["seed"],
        "corpus_sha256": fresh["corpus_sha256"],
        "tiers": {name: list(ids) for name, ids in fresh["tiers"].items()},
        "tier_sha256": fresh["tier_sha256"]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return fresh


# --- the printable tables (K6-06, K6-20) -------------------------------------------

def provenance_table(cases: Sequence[CaseV5]) -> list[str]:
    """K6-06: the share of each provenance kind, per industry."""
    lines = ["происхождение по отраслям:"]
    per_industry: dict[str, Counter[str]] = {industry: Counter() for industry in
                                             contracts_v6.INDUSTRIES}
    for case in cases:
        ind = _industry(case)
        if ind in per_industry and case.v6 is not None:
            per_industry[ind][case.v6.provenance] += 1
    for industry in contracts_v6.INDUSTRIES:
        counts = per_industry[industry]
        size = sum(counts.values())
        cells = " · ".join(f"{kind} {counts.get(kind, 0)}"
                           f"({counts.get(kind, 0) / size:.1%})" if size else f"{kind} 0"
                           for kind in contracts_v6.V6_PROVENANCE_KINDS)
        lines.append(f"  {industry:<22} {cells}")
    return lines


def tier_type_table(cases: Sequence[CaseV5], ladder: dict[str, object]) -> list[str]:
    """K6-20: the number of cases per (v6) type in every tier."""
    by_id = {case.base.id: case for case in cases}
    tiers = ladder.get("tiers") if isinstance(ladder.get("tiers"), dict) else {}
    admitted = _admitted_types(cases)
    lines = ["число случаев на тип по ярусам:"]
    for name in (*V6_DEBUG_TIERS, "holdout", "max"):
        members = [by_id[one] for one in tiers.get(name, ())]
        per_type: Counter[str] = Counter(item.type for case in members for item in case.base.pii
                                         if item.type in set(admitted))
        cells = " · ".join(f"{t} {per_type.get(t, 0)}" for t in admitted) or "—"
        lines.append(f"  {name:<8} {len(members):>4} · {cells}")
    return lines


# --- the residue of the v6 result_pii column (K6-17) -------------------------------

_UNCROSSED_RESULT_PII_V6: frozenset[str] = frozenset()


def result_pii_residue_v6(cases: Sequence[CaseV5]) -> list[str]:
    """K6-17: how much of the v6 tools' «ПД в результате» column is DECLARED and
    how much is actually crossed, with the never-crossed remainder frozen by name
    (mirrors `build.result_pii_residue`, keyed to `TOOLS_V6`)."""
    crossed: dict[str, set[str]] = {}
    for case in cases:
        for hop in case.hops:
            if hop.kind != "IN" or hop.owner != "tool":
                continue
            crossed.setdefault(hop.tool_name, set()).add(_erase_index(hop.path))
    declared = {f"{spec.base.name}.{leaf}" for spec in TOOLS_V6
                for leaf in spec.base.result_pii}
    now = {one for one in declared
           if one.split(".", 1)[1] not in crossed.get(one.split(".", 1)[0], set())}
    lines = [f"ПД в результате (v6): {len(declared)} объявлений, "
             f"{len(declared) - len(now)} пересечены хопами, {len(now)} держатся объявлением"]
    began = sorted(now - _UNCROSSED_RESULT_PII_V6)
    if began:
        lines.append(f"  ОТКАЗ: {len(began)} объявлений никто не пересекает, а список их "
                     f"не называет: {began[:6]}")
    ended = sorted(_UNCROSSED_RESULT_PII_V6 - now)
    if ended:
        lines.append(f"  ОТКАЗ: {len(ended)} замороженных объявлений теперь пересечены: "
                     f"{ended[:6]}")
    return lines


_ARRAY_INDEX = re.compile(r"\[\d+\]")


def _erase_index(path: str) -> str:
    return _ARRAY_INDEX.sub("[]", path)
