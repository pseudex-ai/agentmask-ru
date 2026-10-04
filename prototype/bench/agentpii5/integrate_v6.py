"""AgentPII-RU v6 — the integration report writer (tz-agentpii6.md §7.2, §14.3).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.integrate_v6 --phase full
    python3 -m bench.agentpii5.integrate_v6 --phase pilot

WHAT THIS IS. The one script that turns the G1–G4 runs into the acceptance file
`review/v6-integration.json`. It loads the v6 corpus and ladder (rebuilding the
corpus via `build_full` when absent), runs the PERFECT gateway over every case
and the twelve §7.3 wrong-gateway mutants, and writes the §7.2 fields:

    corpus_sha256, ladder_sha256, registry_sha256, ladder_stamp,
    l1 (perfect + mutants per tier), l7 (checksum generator/validator),
    l8 (hops declared/proven/unprovable), l9 (per registered type),
    regress (baseline + identity), generated_by

DETERMINISTIC AND ENGINE-FREE. Nothing here imports `pseudex`; the gateway arm
is `perfect.simulate`, every score is `observe.observe` + `metrics`, and every
digest is a hash of the inputs — so two processes write the same bytes (the same
discipline `regress_print` holds for its product path, W0-R7).

THE REGISTRY MERGE. `scenarios6.common6` widens v4's `REGISTRY` AND the v5
`REGISTRY_V5` with the v6 tools at import time; importing it here is what lets
`perfect.simulate` mint a v6 leaf through the same `spec_v5_for` the live
harness resolves (a v6 tool not in the registry is a KeyError, not a missing
mask).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, replace
from pathlib import Path

from bench.agentpii4 import schema as v4
from bench.agentpii4.compare import ArmRun
from bench.agentpii4.tools import flatten
from bench.agentpii5 import build_v6, checksum_v6, contracts, gen_v6, metrics, observe, perfect, pii_types
from bench.agentpii5.contracts import ArmRunV5, CaseV5, Line
from bench.agentpii5.form_tables import CYRILLIC_TO_LATIN
from bench.agentpii5.schema import case_v5_from_json, corpus_digest_v5
from bench.agentpii5.schema_v6 import PILOT_INDUSTRIES, _admitted_types, _industry
from bench.agentpii5.scenarios6 import build_full, common6  # noqa: F401 - the registry merge

HERE: Path = Path(__file__).resolve().parent
V6_DIR: Path = HERE / "v6"
CORPUS_PATH: Path = V6_DIR / "corpus.v5.json"
LADDER_PATH: Path = V6_DIR / "ladder.json"
OUT_PATH: Path = HERE / "review" / "v6-integration.json"

GENERATED_BY: str = "bench.agentpii5.integrate_v6"
PHASES: tuple[str, ...] = ("pilot", "full")
TIERS: tuple[str, ...] = ("nano", "small", "medium", "max")

_NEW_TYPES: frozenset[str] = frozenset(pii_types.NEW_ITEM_TYPES)
_SPECS: dict[str, pii_types.TypeSpec] = {t.id: t for t in pii_types.TYPE_REGISTRY}


# --- digests -------------------------------------------------------------------------


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registry_sha256() -> str:
    """A content hash of the whole type registry (the input every l9 row reads)."""
    rows = [asdict(spec) for spec in pii_types.TYPE_REGISTRY]
    return _sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def ladder_stamp(ladder: dict[str, object]) -> str | None:
    """The freeze hash of the ladder composition (§3.5, §4.6): `tier_sha256`
    serialized. None while the ladder carries no tier freeze — the phase has not
    been stamped, and the per-type leak table must not be written (R6-33)."""
    tiers = ladder.get("tier_sha256")
    if not isinstance(tiers, dict) or not tiers:
        return None
    return _sha256(json.dumps(tiers, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


# --- corpus / ladder loading ---------------------------------------------------------


def _load_cases(path: Path) -> list[CaseV5]:
    return [case_v5_from_json(row)
            for row in json.loads(path.read_text(encoding="utf-8"))["corpus"]]


def load_corpus_and_ladder(phase: str) -> tuple[list[CaseV5], dict[str, object], Path]:
    """The phase's cases and the ladder object, rebuilding the corpus when absent.

    `full` is every case; `pilot` is the cases whose industry is in
    `PILOT_INDUSTRIES` (§4.5). The ladder file is the frozen one — never
    rewritten here (build_v6 owns it)."""
    if phase not in PHASES:
        raise ValueError(f"phase {phase!r} is not one of {PHASES}")
    if not CORPUS_PATH.exists() or not LADDER_PATH.exists():
        cases = build_full.build_full()
        digest = build_v6.write_corpus(cases, V6_DIR)
        build_v6.write_ladder_v6(cases, V6_DIR)
        print(f"integrate_v6: rebuilt corpus {digest[:12]} and ladder (they were absent)")
    cases = _load_cases(CORPUS_PATH)
    ladder = json.loads(LADDER_PATH.read_text(encoding="utf-8"))
    if phase == "pilot":
        cases = [case for case in cases if _industry(case) in PILOT_INDUSTRIES]
    return cases, ladder, LADDER_PATH


def tier_ids(ladder: dict[str, object], name: str) -> frozenset[str]:
    if name == "max":
        return frozenset()
    return frozenset(ladder.get("tiers", {}).get(name, ()))


def cases_of_tier(cases: Sequence[CaseV5], ladder: dict[str, object], name: str) -> list[CaseV5]:
    if name == "max":
        return list(cases)
    ids = tier_ids(ladder, name)
    return [case for case in cases if case.base.id in ids]


# --- the perfect gateway, reassembled so a mutant can vary the substitutes ----------


def _items_of(case: CaseV5) -> dict[str, object]:
    return {item.id: item for item in case.base.pii}


def _subs_of(case: CaseV5) -> tuple[dict[str, object], dict[str, str], dict[str, perfect.Substitute]]:
    items = _items_of(case)
    fakes = perfect.name_pool_map(case.base.pii)
    subs = {iid: perfect._substitute_for(item, fakes) for iid, item in items.items()}
    return items, fakes, subs


def _assemble(case: CaseV5, subs: dict[str, perfect.Substitute]) -> ArmRunV5:
    """The ArmRunV5 a right gateway leaves behind, mirroring `perfect.simulate`
    but over a CALLER-provided substitute map — the seam every mutant below
    drives. The body is `simulate`'s own, so the perfect run is byte-equivalent
    to `perfect.simulate(case)` when `subs` is `_subs_of`'s."""
    items = _items_of(case)
    masked_spans, message_mentions = perfect._masked_messages(case, subs)
    results, result_mentions = perfect._tool_results(case, items, subs)
    calls, call_turns = perfect._calls(case, items, subs)
    reply_raw, reply = perfect._answer(case, items, subs)
    base = ArmRun(case_id=case.base.id, arm="I", repeat=0, calls=tuple(calls), state=(),
                  reply=reply, termination="done", cost_usd=0.0,
                  substitutes={item_id: (fake.value, dict(fake.parts))
                               for item_id, fake in subs.items()},
                  masked_spans=masked_spans)
    # `model_trace` has NO default on purpose (see `contracts.ArmRunV5`). This
    # arm is assembled from `perfect`'s own helpers — no provider was observed,
    # so the explicit statement is `None` (the same one `perfect.simulate`
    # makes), never a silently defaulted field.
    return ArmRunV5(
        base=base, reply_raw=reply_raw, control_reply=reply + " ",
        tool_results=tuple(results), mentions=tuple(message_mentions + result_mentions),
        turn_replies=(reply,), call_turns=tuple(call_turns),
        request_count=max(len(case.base.messages) + len(results), 1),
        stream_mismatch=False, reply_whole=reply if case.streaming else "", turn_residual=0,
        model_trace=None)


def observations(cases: Sequence[CaseV5],
                 simulate: Callable[[CaseV5], ArmRunV5]) -> tuple[object, ...]:
    return tuple(observe.observe(case, simulate(case), None, None) for case in cases)


# The single-arm lines the perfect gateway prints, plus the three OD-54 v6 rows
# (§6.3) — `typed_user` / `fake_checksum_invalid` / `overmask_result` — which are
# the catch rows of M7/M8/M9 and live in `metrics.V6_METRIC_FUNCTIONS`, not in
# `contracts.METRIC_NAMES`.
MEASURED_METRICS: tuple[str, ...] = tuple(perfect.SINGLE_ARM_METRICS) \
    + tuple(sorted(metrics.V6_METRIC_FUNCTIONS))


def measure(cases: Sequence[CaseV5],
            simulate: Callable[[CaseV5], ArmRunV5]) -> dict[str, Line]:
    seen = observations(cases, simulate)
    out = {name: metrics.METRIC_FUNCTIONS[name](seen) for name in perfect.SINGLE_ARM_METRICS}
    out.update({name: fn(seen) for name, fn in metrics.V6_METRIC_FUNCTIONS.items()})
    return out


def _map_calls(run: ArmRunV5,
               fn: Callable[[dict[str, str], dict[str, str]],
                            tuple[dict[str, str], dict[str, str]]]) -> ArmRunV5:
    """Rewrite every call's leaves through `fn(written, restored)` — the seam
    `test_perfect.py` uses for the v5 wrong gateways, kept identical here."""
    calls = []
    for call in run.base.calls:
        written, restored = fn(dict(flatten(call.written)), dict(flatten(call.restored)))
        calls.append(replace(call, written=perfect.unflatten(written),
                             restored=perfect.unflatten(restored)))
    return replace(run, base=replace(run.base, calls=tuple(calls)))


# --- the twelve §7.3 mutants ---------------------------------------------------------


def _squeeze(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def _transliterate(text: str) -> str:
    out = []
    for ch in text:
        variants = CYRILLIC_TO_LATIN.get(ch) or CYRILLIC_TO_LATIN.get(ch.lower())
        if variants:
            latin = variants[0]
            out.append(latin.upper() if ch.isupper() else latin)
        else:
            out.append(ch)
    return "".join(out)


def _has_cyrillic(text: str) -> bool:
    return any(ch in CYRILLIC_TO_LATIN or ch.lower() in CYRILLIC_TO_LATIN for ch in text)


def _m1_blind_to_v6(case: CaseV5) -> ArmRunV5:
    """M1 — blind to the new types: the real engine's likely state. The v6 item
    is never minted (empty substitute on IN/user, no piece on IN/tool), so its
    real value reaches the model. The catching row is `leak` in the new-type
    slice."""
    items, _fakes, subs = _subs_of(case)
    v6 = {iid for iid, item in items.items() if item.type in _NEW_TYPES}
    for iid in v6:
        item = items[iid]
        subs[iid] = perfect.Substitute(id=iid, type=item.type, identity=item.identity,
                                       value="", canonical="", parts={})
    run = _assemble(case, subs)
    kept = []
    for record in run.tool_results:
        v6_spans = {span for iid, span in record.spans_real.items() if iid in v6}
        pieces = tuple(p for p in record.pieces
                       if not any(p[0] <= s[0] and s[1] <= p[1] for s in v6_spans))
        kept.append(replace(record, pieces=pieces))
    return replace(run, tool_results=tuple(kept))


def _m2_solid_digits(case: CaseV5) -> ArmRunV5:
    """M2 — restores the digits solid, dropping the agent's separators. Only a
    leaf that actually carries digits changes; `form_hOUT` reads the notation."""
    return _map_calls(_assemble(case, _subs_of(case)[2]),
                      lambda w, r: (w, {k: _squeeze(v) for k, v in r.items()}))


def _m3_residual(case: CaseV5) -> ArmRunV5:
    """M3 — leaves the substitute in the OUT leaf (rearranged by a space), so a
    fake reaches the customer's tool. `residual` counts it."""
    def space_in(text: str) -> str:
        return text if len(text) < 2 else text[:1] + " " + text[1:]

    return _map_calls(_assemble(case, _subs_of(case)[2]),
                      lambda w, r: (w, {k: space_in(w[k]) for k in w if k in r}))


def _m4_open_results(case: CaseV5) -> ArmRunV5:
    """M4 — leaves the new-type values OPEN in tool results: the result renders
    the real value where a substitute should stand. `toolresult_masked` reads
    exactly that. The message leg stays masked (only the result leaks)."""
    items, _fakes, subs = _subs_of(case)
    for iid, item in items.items():
        if item.type in _NEW_TYPES:
            subs[iid] = replace(subs[iid], canonical=item.canonical or item.value)
    return _assemble(case, subs)


def _m5_latin_restore(case: CaseV5) -> ArmRunV5:
    """M5 — restores in Latin where the agent wrote Cyrillic. `form_hOUT`'s
    `script` feature names the defect."""
    def latin(value: str) -> str:
        return _transliterate(value) if _has_cyrillic(value) else value

    return _map_calls(_assemble(case, _subs_of(case)[2]),
                      lambda w, r: (w, {k: latin(v) for k, v in r.items()}))


def _m6_composite(case: CaseV5) -> ArmRunV5:
    """M6 — a composite leaf restores only the prefix and leaves the tail as the
    substitute. `round_trip` asks the leaf's own part; the tail is a residual."""
    def half(value: str, substitute: str) -> str:
        if not substitute or not value:
            return value
        cut = max(1, len(substitute) // 2)
        return value[:cut] + substitute[cut:]

    return _map_calls(_assemble(case, _subs_of(case)[2]),
                      lambda w, r: (w, {k: half(v, w[k]) for k, v in r.items() if k in w}))


def _m7_enp_card(case: CaseV5) -> ArmRunV5:
    """M7 — an OMS_ENP minted as a card-shaped substitute and LABELLED CARD.
    `typed` compares the gateway's label with the item's type; `typed_user` the
    user leg."""
    items, _fakes, subs = _subs_of(case)
    run = _assemble(case, subs)
    relabelled = []
    for record in run.tool_results:
        span_to_item = {span: iid for iid, span in record.spans_real.items()}
        pieces = tuple((s, e, sub, "CARD" if span_to_item.get((s, e)) is not None
                        and items[span_to_item[(s, e)]].type == "OMS_ENP" else et)
                       for s, e, sub, et in record.pieces)
        relabelled.append(replace(record, pieces=pieces))
    message_pieces = []
    for item in case.base.pii:
        if item.type != "OMS_ENP" or item.where.kind != "message":
            continue
        message_pieces.append((item.where.msg, item.where.start, item.where.end, "CARD"))
    return replace(run, tool_results=tuple(relabelled),
                   message_pieces=tuple(message_pieces))


def _m8_checksum_valid(case: CaseV5) -> ArmRunV5:
    """M8 — mints substitutes that PASS their own checksum (no re-mint loop).
    `fake_checksum_invalid` prints 0/1 for a checksum-valid substitute."""
    items, _fakes, subs = _subs_of(case)
    for iid, item in items.items():
        spec = _SPECS.get(item.type)
        if spec is None or not spec.generated_checksum:
            continue
        value, _canonical = gen_v6.generate(item.type, 7)
        subs[iid] = replace(subs[iid], value=value)
    return _assemble(case, subs)


def _m9_overmask_negatives(case: CaseV5) -> ArmRunV5:
    """M9 — masks the NEGATIVES inside tool results (a BIK, an OGRN, a KBC).
    `overmask_result` reads the `neg:` slots the mock tags and their coverage."""
    run = _assemble(case, _subs_of(case)[2])
    masked = []
    for record in run.tool_results:
        parts = list(record.text_masked)
        pieces = list(record.pieces)
        for tag, span in record.spans_real.items():
            if not tag.startswith(metrics.NEG_TAG_PREFIX):
                continue
            # A masked negative: the model reads the substitute piece in its span.
            body = record.text_real[span[0]:span[1]]
            fake = _fake_neg(body)
            for i in range(span[0], span[1]):
                parts[i] = fake[i - span[0]] if i - span[0] < len(fake) else " "
            pieces.append((span[0], span[1], fake, tag))
        masked.append(replace(record, text_masked="".join(parts), pieces=tuple(pieces)))
    return replace(run, tool_results=tuple(masked))


def _fake_neg(text: str) -> str:
    out = []
    for ch in text:
        out.append(str((int(ch) + 3) % 10) if ch.isdigit() else ch)
    return "".join(out)


def _m10_first_lines(case: CaseV5) -> ArmRunV5:
    """M10 — masks only the first N lines of a dump; later renderings of the same
    value stay open. `toolresult_masked` checks every declared result."""
    run = _assemble(case, _subs_of(case)[2])
    masked = []
    for record in run.tool_results:
        if record.forced or "\n" not in record.text_real or len(record.spans_real) <= 1:
            masked.append(record)
            continue
        first_nl = record.text_real.index("\n")
        spans = {tag: span for tag, span in record.spans_real.items()
                 if span[0] < first_nl}
        pieces = tuple(p for p in record.pieces if p[0] < first_nl)
        masked.append(replace(record, spans_real=spans, pieces=pieces))
    return replace(run, tool_results=tuple(masked))


def _m11_wrong_length(case: CaseV5) -> ArmRunV5:
    """M11 — mints a substitute of a DIFFERENT digit length. `form_hIN`'s
    `digit_count` feature reads the mismatch."""
    items, _fakes, subs = _subs_of(case)
    for iid, item in items.items():
        if item.type in _NEW_TYPES and _SPECS.get(item.type) is not None \
                and _SPECS[item.type].value_notation == "digits":
            sub = subs[iid]
            if sub.value:
                subs[iid] = replace(sub, value=sub.value + "0", canonical=sub.canonical + "0")
    return _assemble(case, subs)


def _m12_letters_only(case: CaseV5) -> ArmRunV5:
    """M12 — changes only the LETTERS of a series, keeping the digits right.
    The value line (`round_trip`) catches the wrong value."""
    def flip_letters(value: str) -> str:
        return "".join("А" if ch in "АВЕКМНОРСТУХ" else ch for ch in value)

    return _map_calls(_assemble(case, _subs_of(case)[2]),
                      lambda w, r: (w, {k: flip_letters(v) for k, v in r.items()}))


MUTANTS: tuple[tuple[str, str, Callable[[CaseV5], ArmRunV5], str], ...] = (
    ("M1", "слеп к новым типам", _m1_blind_to_v6, "leak"),
    ("M2", "восстанавливает цифры слитно, выбрасывая разделители", _m2_solid_digits, "form_hOUT"),
    ("M3", "оставляет подмену в переставленном пробелами листе", _m3_residual, "residual"),
    ("M4", "оставляет новые типы открытыми в результатах", _m4_open_results, "toolresult_masked"),
    ("M5", "восстанавливает латиницей там, где агент писал кириллицей", _m5_latin_restore,
     "form_hOUT"),
    ("M6", "составной лист: префикс восстановлен, хвост — подмена", _m6_composite, "round_trip"),
    ("M7", "ЕНП с карто-образной подменой и меткой CARD", _m7_enp_card, "typed"),
    ("M8", "чеканит подмены, проходящие свою КС", _m8_checksum_valid, "fake_checksum_invalid"),
    ("M9", "маскирует негативы в результатах", _m9_overmask_negatives, "overmask_result"),
    ("M10", "маскирует только первые N строк выгрузки", _m10_first_lines, "toolresult_masked"),
    ("M11", "чеканит подмену другой длины", _m11_wrong_length, "form_hIN"),
    ("M12", "меняет только буквы серии при верных цифрах", _m12_letters_only, "round_trip"),
)


# --- report sections -----------------------------------------------------------------


def _line_json(line: Line) -> dict[str, int]:
    return {"hits": line.hits, "total": line.total}


def l1_section(cases: Sequence[CaseV5], ladder: dict[str, object]) -> dict[str, object]:
    """The perfect gateway per tier, plus each mutant's catch row on the whole
    corpus. A mutant whose catch row does not move is a finding, not a pass."""
    perfect_by_tier: dict[str, object] = {}
    for tier in TIERS:
        tier_cases = cases_of_tier(cases, ladder, tier)
        lines = measure(tier_cases, perfect.simulate)
        perfect_by_tier[tier] = {name: _line_json(line)
                                 for name, line in lines.items()}
    perfect_max_lines = measure(cases, perfect.simulate)
    perfect_max = {name: _line_json(line) for name, line in perfect_max_lines.items()}
    mutants: list[object] = []
    for mid, label, gateway, catch in MUTANTS:
        lines = measure(cases, gateway)
        catch_line = lines[catch]
        perfect_catch = perfect_max[catch]
        moved = (catch_line.hits, catch_line.total) != (perfect_catch["hits"],
                                                        perfect_catch["total"])
        changed = lines != perfect_max_lines
        mutants.append({
            "id": mid, "label": label, "catch": catch,
            "perfect": perfect_catch, "mutant": _line_json(catch_line),
            "caught": bool(moved), "changed": bool(changed),
        })
    return {"perfect": perfect_by_tier, "mutants": mutants}


def l7_section() -> dict[str, object]:
    """The checksum generator/validator agreement and the mutation classes,
    reusing the authoritative test homes (§7.2 l7, G2)."""
    from bench.agentpii5 import test_checksum_v6
    primary = test_checksum_v6.test_primary_examples()
    classes = test_checksum_v6.test_mutation_classes()
    by_type: dict[str, object] = {}
    for spec in pii_types.TYPE_REGISTRY:
        if not spec.generated_checksum:
            continue
        value, _canonical = gen_v6.generate(spec.id, 1)
        try:
            valid = checksum_v6.validate(spec.id, value)
        except (KeyError, ValueError):
            valid = False
        by_type[spec.id] = {"generated": value, "validator": valid}
    return {
        "primary_examples": {"problems": primary, "pass": not primary},
        "mutation_classes": {"problems": classes, "pass": not classes},
        "by_type": by_type,
    }


def l8_section(cases: Sequence[CaseV5]) -> dict[str, object]:
    """Hops declared, proven and unprovable — the `build_v6 --check` mock-transition
    proof, NOT the perfect-gateway observation.

    `build_v6.proof_v6` drives every declared return through the real v6 mock
    (`mock_v6.render_problems_v6`, the v6 analog of `mock.render_problems` / F4.1)
    and reports `declared` (required hops), `proven` (hops the mock transition
    declared and the result rendered) and `unprovable` (the crossings the mock
    cannot render, V01-V04). A right gateway cannot make an unprovable crossing
    happen, so `unprovable` must be empty for a shippable corpus."""
    return build_v6.proof_v6(cases)


def l9_section(cases: Sequence[CaseV5], phase: str, stamp: str | None) -> dict[str, object]:
    """One row per registered new type of the phase: cases, hops, exception,
    absent_required, statuses, engine_labels — and the leak table only once the
    ladder is stamped (R6-33).

    THE STATUS HISTOGRAM IS THE v6 FUNNEL, AND IT IS FILLED THROUGH ITS ONE DOOR
    (`contracts.v6_funnel_status`, V1 SPEC §4 `COV-INTEGRATION-KEEP-V5`). The
    observer emits the eight-entry READ vocabulary (`HOP_STATUSES`); the v6 row
    is keyed by the five-entry projection, so `row["statuses"][hop.status]` is a
    `KeyError` the first time a v5-only status (`leaf_foreign`) occurs — which is
    exactly what it was. The v5 split is NOT destroyed by the fold: every read
    status is counted beside it under `read_split`, so the three v5-only causes
    stay legible on the same row."""
    phase_types = tuple(t for t in pii_types.NEW_ITEM_TYPES if phase == "full"
                        or t in _admitted_types(cases))
    seen = observations(cases, perfect.simulate)
    rows: dict[str, dict[str, object]] = {}
    for spec in pii_types.TYPE_REGISTRY:
        if not spec.item_type or spec.origin != pii_types.ORIGIN_V6:
            continue
        in_phase = spec.id in phase_types
        rows[spec.id] = {
            "type": spec.id, "cases": 0, "hops": 0, "exception": 0,
            "absent_required": 0,
            # the v6 five, in `contracts.V6_FUNNEL_STATUSES` order
            "statuses": {name: 0 for name in contracts.V6_FUNNEL_STATUSES},
            # the v5 READ split, beside the projection — never instead of it
            "read_split": {},
            "funnel_denominator": sorted(contracts.V6_FUNNEL_DENOMINATOR),
            "engine_labels": list(spec.engine_labels),
            "in_phase": in_phase,
        }
    case_ids: dict[str, set[str]] = {spec.id: set() for spec in pii_types.TYPE_REGISTRY
                                     if spec.origin == pii_types.ORIGIN_V6}
    for one in seen:
        for hop in one.hops:
            if hop.pii_type not in rows:
                continue
            row = rows[hop.pii_type]
            case_ids[hop.pii_type].add(hop.case_id)
            row["hops"] += 1
            split = row["read_split"]
            assert isinstance(split, dict)
            split[hop.status] = split.get(hop.status, 0) + 1
            row["statuses"][contracts.v6_funnel_status(hop.status)] += 1
            if hop.status == "absent" and hop.hop.kind == "IN" \
                    and hop.hop.owner in ("tool", "document"):
                row["absent_required"] += 1
    for spec_id, row in rows.items():
        row["cases"] = len(case_ids[spec_id])
        if stamp is not None:
            row["leak"] = {"leaked": row["statuses"]["leaked"],
                           "unmasked": row["statuses"]["unmasked"],
                           "observed": row["statuses"]["observed"]}
    return {"phase": phase, "types": list(rows.values())}


# The v4 cap arithmetic, restated engine-free (bench/agentpii4/harness.cap_usd
# imports `pseudex`, which this module must not — the numbers are the same three
# constants, read off the same Case fields).
CAP_BASE_USD: float = 0.12
CAP_PER_TURN_USD: float = 0.04
CAP_PER_TOOL_USD: float = 0.01


def _cap_usd(case: CaseV5) -> float:
    turns = sum(1 for message in case.base.messages if message.role == "user")
    return (CAP_BASE_USD + CAP_PER_TURN_USD * max(0, turns - 1)
            + CAP_PER_TOOL_USD * len(case.base.tools))


def dry_run_cost(cases: Sequence[CaseV5], ladder: dict[str, object]) -> dict[str, object]:
    """The §10.1 demand estimate per tier — no model call, no network. The dollar
    column is the reserved ceiling (cap × 3 arms), the same `harness --dry-run`
    prints when no past run of this model pair exists (reserve_only)."""
    from bench.agentpii5 import runinfo
    out: dict[str, object] = {}
    for tier in TIERS:
        tier_cases = cases_of_tier(cases, ladder, tier)
        demand = runinfo.demand_of(tier_cases, 1)
        reserve = sum(_cap_usd(case) * 3 for case in tier_cases)
        out[tier] = {
            "cases": len(tier_cases),
            "model_calls_low": demand.model_calls_low,
            "model_calls_high": demand.model_calls_high,
            "tool_calls_low": demand.tool_calls_low,
            "tool_calls_high": demand.tool_calls_high,
            "prompt_tokens": demand.prompt_tokens,
            "reserve_usd": round(reserve, 2),
        }
    return out


def regress_section(cases: Sequence[CaseV5], ladder: dict[str, object]) -> dict[str, object]:
    """The baseline (frozen v5 inputs, byte-identical) and the corpus↔ladder
    identity (re-deriving the digest matches the ladder's record).

    THE IDENTITY IS CHECKED AGAINST THE DIGEST THE LADDER ACTUALLY HOLDS. The
    ladder's `corpus_sha256` is v4's digest of the BASES — the one
    `bench.agentpii4.schema.tier` recomputes before the harness plays a tier
    (the pinned v5 ladder carries it the same way). This section first compared
    it to `corpus_digest_v5`, so it reported `identity: true` for a ladder no
    consumer would accept, and printed that over the v6 dry-run's refusal. Both
    digests are reported now; the flag is the consumer's comparison.
    """
    digest = corpus_digest_v5(cases)
    v4_digest = v4.corpus_digest([case.base for case in cases])
    recorded = str(ladder.get("corpus_sha256", ""))
    return {
        "corpus_digest": digest,
        "corpus_v4_digest": v4_digest,
        "ladder_corpus_sha256": recorded,
        "identity": v4_digest == recorded,
        "pinned_v5": {
            "corpus.v5.json": _file_sha256(HERE / "corpus.v5.json"),
            "ladder.json": _file_sha256(HERE / "ladder.json"),
            "v6/corpus.v5.json": _file_sha256(CORPUS_PATH),
            "v6/ladder.json": _file_sha256(LADDER_PATH),
        },
    }


def build_report(cases: Sequence[CaseV5], ladder: dict[str, object], phase: str,
                 ladder_path: Path, stamp: str | None) -> dict[str, object]:
    report: dict[str, object] = {
        "generated_by": GENERATED_BY,
        "phase": phase,
        "corpus_sha256": corpus_digest_v5(cases),
        "ladder_sha256": _file_sha256(ladder_path),
        "registry_sha256": registry_sha256(),
        "l1": l1_section(cases, ladder),
        "l7": l7_section(),
        "l8": l8_section(cases),
        "l9": l9_section(cases, phase, stamp),
        "regress": regress_section(cases, ladder),
    }
    if stamp is not None:
        report["ladder_stamp"] = stamp
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phase", default="full", choices=PHASES)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the per-tier cost estimate and exit; write nothing")
    args = parser.parse_args(sys.argv[1:])

    cases, ladder, ladder_path = load_corpus_and_ladder(args.phase)
    if not cases:
        print(f"integrate_v6: phase {args.phase!r} has no cases", file=sys.stderr)
        return 2
    if args.dry_run:
        for tier, row in dry_run_cost(cases, ladder).items():
            print(f"{tier:<8} cases {row['cases']:<4} "
                  f"model_calls {row['model_calls_low']}–{row['model_calls_high']} "
                  f"tool_calls {row['tool_calls_low']}–{row['tool_calls_high']} "
                  f"prompt_tokens ~{row['prompt_tokens']:,} "
                  f"reserve_usd ${row['reserve_usd']:.2f}".replace(",", " "))
        return 0
    stamp = ladder_stamp(ladder)
    report = build_report(cases, ladder, args.phase, ladder_path, stamp)
    if not report.get("generated_by"):
        print("integrate_v6: refusing to write a report without `generated_by`",
              file=sys.stderr)
        return 2
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(f"integrate_v6: wrote {OUT_PATH} "
          f"(corpus {str(report['corpus_sha256'])[:12]}, "
          f"l9 types {len(report['l9']['types'])}, "
          f"ladder_stamp {'set' if stamp else 'UNSET'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
