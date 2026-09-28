"""Every v5 record on disk, and back. The ONE serialisation of the v5 run.

`harness.py` writes these rows while a run is live; `observe.py`, `metrics.py`
and `report.py` read them back with no model and no money. A field that does
not round-trip is a field a `--report` replay would silently score
differently, so every dataclass of `contracts` §5-§6 gets a pair here and
`test_records.test_round_trips` asserts the pair on a fixture of each.

TWO RULES DECIDE THE LAYOUT.

1. **A v5 arm row is a v4 arm row plus one key.** `<run>.arms.jsonl` holds
   v4's `arm_record` bytes, unchanged, produced from `ArmRunV5.base`; the v5
   fields ride in `<run>.arms.v5.jsonl` under `"v5"` beside the SAME v4 keys.
   So `bench.agentpii4.records.arm_from_record` reads a v5 row by ignoring one
   key, and v4's own `autopsy.py` / `compare_runs.py` read a v5 run directory
   without being touched. A v5-shaped arm record was the alternative and it
   would have made the baseline comparison a v5 program comparing v5 to
   itself — exactly what §8 of the spec forbids.

2. **A malformed row is refused by name, never defaulted.** Every reader goes
   through `_text` / `_whole` / `_flag` / `_amount` / `_table` / `_rows`,
   which raise `RecordError` naming the record kind, the field and what was
   found. `row.get(key, "")` would turn a harness bug (a field the writer
   forgot) into a metric that quietly counts zero, and a metric that counts
   zero for a reason nobody can see is the v4 defect class this benchmark
   exists to avoid.

The closed vocabularies (`HOP_KINDS`, `HOP_OWNERS`, `HOP_STATUSES`,
`JUDGE_LABELS`, `JUDGED_BY`) are checked on READ, not only on write: the file
is the only thing a replay has, and a typo that survived the writer must not
survive the reader.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from bench.agentpii4.records import ArmMeta, arm_from_record, arm_record, shippable
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import (
    HOP_KINDS, HOP_OWNERS, HOP_STATUSES, JUDGE_LABELS, JUDGED_BY, RUN_FILES,
    AnswerSpan, ArmRunV5, CalibrationRecord, CalibrationStamp, FormVerdict, Hop,
    HopObservation, JudgeVerdict, MentionRecord, ToolResultRecord, JudgeRow)

# The one key a v4 reader must ignore. Named here so the harness, the readers
# and the test that pins rule 1 above cannot drift apart by a string literal.
V5_KEY: str = "v5"
# What a licensed case's text is replaced by, exactly v4's marker: measuring
# with a corpus is not permission to ship it, and a run file is shipping.
SCRUB_MARKER: str = "<лицензионный источник>"
RUN_PLACEHOLDER: str = "<run>"


class RecordError(ValueError):
    """A row that cannot be read as the record it claims to be.

    Carries the record kind, the field and the offending value: a replay
    failing three files deep needs to name the row, not the reader.
    """


def _field(row: dict[str, object], key: str, kind: str) -> object:
    if key not in row:
        raise RecordError(f"{kind}: field {key!r} is missing; the row has {sorted(row)}")
    return row[key]


def _text(row: dict[str, object], key: str, kind: str) -> str:
    value = _field(row, key, kind)
    if not isinstance(value, str):
        raise RecordError(f"{kind}.{key}: expected a string, found {type(value).__name__} {value!r}")
    return value


def _whole(row: dict[str, object], key: str, kind: str) -> int:
    value = _field(row, key, kind)
    # `bool` is an `int` in Python and `True` would read as 1 — a masked index
    # or a turn number of «True» is a writer bug worth a red line, not a 1.
    if not isinstance(value, int) or isinstance(value, bool):
        raise RecordError(f"{kind}.{key}: expected an integer, found {type(value).__name__} {value!r}")
    return value


def _flag(row: dict[str, object], key: str, kind: str) -> bool:
    value = _field(row, key, kind)
    if not isinstance(value, bool):
        raise RecordError(f"{kind}.{key}: expected a boolean, found {type(value).__name__} {value!r}")
    return value


def _amount(row: dict[str, object], key: str, kind: str) -> float:
    value = _field(row, key, kind)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecordError(f"{kind}.{key}: expected a number, found {type(value).__name__} {value!r}")
    return float(value)


def _rows(row: dict[str, object], key: str, kind: str) -> list[object]:
    value = _field(row, key, kind)
    if not isinstance(value, list):
        raise RecordError(f"{kind}.{key}: expected a list, found {type(value).__name__} {value!r}")
    return value


def _table(row: dict[str, object], key: str, kind: str) -> dict[str, object]:
    value = _field(row, key, kind)
    if not isinstance(value, dict):
        raise RecordError(f"{kind}.{key}: expected an object, found {type(value).__name__} {value!r}")
    return {str(name): item for name, item in value.items()}


def _one_of(value: str, allowed: tuple[str, ...], kind: str, key: str) -> str:
    if value not in allowed:
        raise RecordError(f"{kind}.{key}: {value!r} is not one of {allowed}")
    return value


def _strings(values: list[object], kind: str, key: str) -> tuple[str, ...]:
    for one in values:
        if not isinstance(one, str):
            raise RecordError(f"{kind}.{key}: expected strings, found {type(one).__name__} {one!r}")
    return tuple(str(one) for one in values)


def _span(value: object, kind: str, key: str) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise RecordError(f"{kind}.{key}: expected a [start, end] pair, found {value!r}")
    start, end = value[0], value[1]
    if not isinstance(start, int) or not isinstance(end, int) or isinstance(start, bool) or isinstance(end, bool):
        raise RecordError(f"{kind}.{key}: span bounds must be integers, found {value!r}")
    return int(start), int(end)


# --- §1 the hop ------------------------------------------------------------

def hop_to_json(hop: Hop) -> dict[str, object]:
    return {"kind": hop.kind, "owner": hop.owner, "item_id": hop.item_id,
            "hop_index": hop.hop_index, "turn": hop.turn, "tool_name": hop.tool_name,
            "call_ordinal": hop.call_ordinal, "parallel_group": hop.parallel_group,
            "source_hop": hop.source_hop, "path": hop.path, "optional": hop.optional}


def hop_from_json(row: dict[str, object]) -> Hop:
    kind = "Hop"
    return Hop(
        kind=_one_of(_text(row, "kind", kind), HOP_KINDS, kind, "kind"),
        owner=_one_of(_text(row, "owner", kind), HOP_OWNERS, kind, "owner"),
        item_id=_text(row, "item_id", kind), hop_index=_whole(row, "hop_index", kind),
        turn=_whole(row, "turn", kind), tool_name=_text(row, "tool_name", kind),
        call_ordinal=_whole(row, "call_ordinal", kind),
        parallel_group=_text(row, "parallel_group", kind),
        source_hop=_whole(row, "source_hop", kind), path=_text(row, "path", kind),
        optional=_flag(row, "optional", kind))


# --- §4 the form verdict ----------------------------------------------------

def form_verdict_to_json(verdict: FormVerdict) -> dict[str, object]:
    # `differs` is sorted on the way out: a frozenset iterates in hash order,
    # and a run file that differs byte for byte between two writes of the same
    # verdict cannot be diffed between runs.
    return {"same": verdict.same, "differs": sorted(verdict.differs)}


def form_verdict_from_json(row: dict[str, object]) -> FormVerdict:
    kind = "FormVerdict"
    same = _flag(row, "same", kind)
    differs = frozenset(_strings(_rows(row, "differs", kind), kind, "differs"))
    if same != (not differs):
        raise RecordError(f"{kind}: same={same} contradicts differs={sorted(differs)}")
    return FormVerdict(same=same, differs=differs)


# --- §5 what the metrics read ------------------------------------------------

def mention_to_json(mention: MentionRecord) -> dict[str, object]:
    return {"item_id": mention.item_id, "msg": mention.msg, "result_seq": mention.result_seq,
            "substitute": mention.substitute, "request_index": mention.request_index}


def mention_from_json(row: dict[str, object]) -> MentionRecord:
    kind = "MentionRecord"
    return MentionRecord(
        item_id=_text(row, "item_id", kind), msg=_whole(row, "msg", kind),
        result_seq=_whole(row, "result_seq", kind), substitute=_text(row, "substitute", kind),
        request_index=_whole(row, "request_index", kind))


def tool_result_to_json(result: ToolResultRecord) -> dict[str, object]:
    return {"tool_name": result.tool_name, "seq": result.seq, "call_ordinal": result.call_ordinal,
            "turn": result.turn, "return_form": result.return_form,
            "text_real": result.text_real, "text_masked": result.text_masked,
            "spans_real": {tag: [start, end] for tag, (start, end) in result.spans_real.items()},
            "pieces": [[start, end, substitute, engine_type]
                       for start, end, substitute, engine_type in result.pieces],
            "forced": result.forced}


def tool_result_from_json(row: dict[str, object]) -> ToolResultRecord:
    kind = "ToolResultRecord"
    spans_real = {tag: _span(value, kind, f"spans_real[{tag}]")
                  for tag, value in _table(row, "spans_real", kind).items()}
    pieces: list[tuple[int, int, str, str]] = []
    for piece in _rows(row, "pieces", kind):
        if not isinstance(piece, (list, tuple)) or len(piece) != 4:
            raise RecordError(f"{kind}.pieces: expected [start, end, substitute, type], found {piece!r}")
        start, end, substitute, engine_type = piece[0], piece[1], piece[2], piece[3]
        if (not isinstance(start, int) or not isinstance(end, int)
                or isinstance(start, bool) or isinstance(end, bool)
                or not isinstance(substitute, str) or not isinstance(engine_type, str)):
            raise RecordError(f"{kind}.pieces: malformed piece {piece!r}")
        pieces.append((int(start), int(end), substitute, engine_type))
    return ToolResultRecord(
        tool_name=_text(row, "tool_name", kind), seq=_whole(row, "seq", kind),
        call_ordinal=_whole(row, "call_ordinal", kind), turn=_whole(row, "turn", kind),
        return_form=_text(row, "return_form", kind), text_real=_text(row, "text_real", kind),
        text_masked=_text(row, "text_masked", kind), spans_real=spans_real,
        pieces=tuple(pieces), forced=_flag(row, "forced", kind))


def answer_span_to_json(span: AnswerSpan) -> dict[str, object]:
    return {"item_id": span.item_id, "raw_start": span.raw_start, "raw_end": span.raw_end,
            "restored_start": span.restored_start, "restored_end": span.restored_end}


def answer_span_from_json(row: dict[str, object]) -> AnswerSpan:
    kind = "AnswerSpan"
    return AnswerSpan(
        item_id=_text(row, "item_id", kind), raw_start=_whole(row, "raw_start", kind),
        raw_end=_whole(row, "raw_end", kind), restored_start=_whole(row, "restored_start", kind),
        restored_end=_whole(row, "restored_end", kind))


def _v5_block(run: ArmRunV5) -> dict[str, object]:
    block = {"reply_raw": run.reply_raw, "control_reply": run.control_reply,
             "tool_results": [tool_result_to_json(one) for one in run.tool_results],
             "mentions": [mention_to_json(one) for one in run.mentions],
             "turn_replies": list(run.turn_replies),
             "call_turns": list(run.call_turns), "request_count": run.request_count,
             "stream_mismatch": run.stream_mismatch, "reply_whole": run.reply_whole,
             "turn_residual": run.turn_residual}
    # OD-76: the message-piece record is OMITTED when empty, exactly like
    # `CaseV5.v6` is omitted at None — so a v5 arm record stays byte-for-byte
    # the row it was before the field existed and the old-corpus replay is
    # unchanged. A v6 run carries the key only when it actually recorded a
    # piece, never as a trailing `[]`.
    if run.message_pieces:
        block["message_pieces"] = [list(piece) for piece in run.message_pieces]
    return block


def _scrubbed_v5_block(block: dict[str, object]) -> dict[str, object]:
    """A licensed case keeps its SHAPE and loses every value it carried.

    The counts stay (`call_turns`, `request_count`, `stream_mismatch` carry no
    text), so a scrubbed run still answers «did the streaming leg disagree»
    and «how many requests» — the two questions that need no corpus value.
    """
    out = dict(block)
    out["reply_raw"] = SCRUB_MARKER
    out["control_reply"] = SCRUB_MARKER
    out["tool_results"] = []
    out["mentions"] = []
    # The COUNT of turns the agent answered is a count, not a value, and
    # `--report` reads it to say how far a run got; the text goes. Dropping the
    # list to `[]` would have said the agent never spoke.
    out["turn_replies"] = [SCRUB_MARKER for _ in _rows(block, "turn_replies", "ArmRunV5")]
    # `reply_whole` is the agent's own text and goes the way `reply_raw` does;
    # `turn_residual` is a COUNT of turns that held a substitute and stays, so
    # a scrubbed run still answers «did a fake stand in an earlier turn» — the
    # question `residual` asks of it, and one that needs no corpus value.
    out["reply_whole"] = SCRUB_MARKER
    return out


def arm_v5_record(run: ArmRunV5, meta: ArmMeta, case: Case) -> dict[str, object]:
    """The `<run>.arms.v5.jsonl` row: v4's own record plus the `"v5"` key."""
    record = arm_record(run.base, meta, case)
    block = _v5_block(run)
    record[V5_KEY] = block if shippable(case) else _scrubbed_v5_block(block)
    return record


def arm_v5_from_record(record: dict[str, object]) -> ArmRunV5:
    kind = "ArmRunV5"
    base = arm_from_record(record)
    block = _table(record, V5_KEY, kind)
    tool_results = tuple(tool_result_from_json(_as_object(one, kind, "tool_results"))
                         for one in _rows(block, "tool_results", kind))
    mentions = tuple(mention_from_json(_as_object(one, kind, "mentions"))
                     for one in _rows(block, "mentions", kind))
    turns = _rows(block, "call_turns", kind)
    for turn in turns:
        if not isinstance(turn, int) or isinstance(turn, bool):
            raise RecordError(f"{kind}.call_turns: expected integers, found {turn!r}")
    replies = _rows(block, "turn_replies", kind)
    for reply in replies:
        if not isinstance(reply, str):
            raise RecordError(f"{kind}.turn_replies: expected strings, found {reply!r}")
    # OD-76: an OLD record (written before the field existed) carries no
    # `message_pieces` key; reading it as () is what lets the old replay print
    # «н/п» for `typed_user` rather than refuse the row. The key is OPTIONAL by
    # contract, so it is read with a default — the one place in this module a
    # missing field is a legal state and not a writer bug.
    pieces: list[tuple[int, int, int, str]] = []
    for piece in _rows(block, "message_pieces", kind) if "message_pieces" in block else []:
        if not isinstance(piece, (list, tuple)) or len(piece) != 4:
            raise RecordError(f"{kind}.message_pieces: expected [msg, start, end, type], "
                              f"found {piece!r}")
        msg, start, end, engine_type = piece[0], piece[1], piece[2], piece[3]
        if (not isinstance(msg, int) or isinstance(msg, bool)
                or not isinstance(start, int) or isinstance(start, bool)
                or not isinstance(end, int) or isinstance(end, bool)
                or not isinstance(engine_type, str)):
            raise RecordError(f"{kind}.message_pieces: malformed piece {piece!r}")
        pieces.append((int(msg), int(start), int(end), engine_type))
    return ArmRunV5(
        base=base, reply_raw=_text(block, "reply_raw", kind),
        control_reply=_text(block, "control_reply", kind),
        tool_results=tool_results, mentions=mentions,
        turn_replies=tuple(str(reply) for reply in replies),
        call_turns=tuple(int(turn) for turn in turns),
        request_count=_whole(block, "request_count", kind),
        stream_mismatch=_flag(block, "stream_mismatch", kind),
        reply_whole=_text(block, "reply_whole", kind),
        turn_residual=_whole(block, "turn_residual", kind),
        message_pieces=tuple(pieces))


def _as_object(value: object, kind: str, key: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RecordError(f"{kind}.{key}: expected objects, found {type(value).__name__} {value!r}")
    return {str(name): item for name, item in value.items()}


def hop_observation_to_json(observation: HopObservation) -> dict[str, object]:
    return {"case_id": observation.case_id, "repeat": observation.repeat,
            "hop": hop_to_json(observation.hop), "declared": observation.declared,
            "pii_type": observation.pii_type, "produced": observation.produced,
            "reference": observation.reference, "status": observation.status,
            "verdict": None if observation.verdict is None else form_verdict_to_json(observation.verdict)}


def hop_observation_from_json(row: dict[str, object]) -> HopObservation:
    kind = "HopObservation"
    status = _one_of(_text(row, "status", kind), HOP_STATUSES, kind, "status")
    raw_verdict = _field(row, "verdict", kind)
    verdict = None if raw_verdict is None else form_verdict_from_json(_as_object(raw_verdict, kind, "verdict"))
    # The dataclass states it: a verdict exists iff the hop was observed. A row
    # breaking that would make `form_hIN`/`form_hOUT` count a comparison that
    # was never made (status `leaked`) or drop one that was.
    if (status == "observed") != (verdict is not None):
        raise RecordError(f"{kind}: status {status!r} with verdict {'set' if verdict else 'null'}")
    return HopObservation(
        case_id=_text(row, "case_id", kind), repeat=_whole(row, "repeat", kind),
        hop=hop_from_json(_as_object(_field(row, "hop", kind), kind, "hop")),
        declared=_flag(row, "declared", kind), pii_type=_text(row, "pii_type", kind),
        produced=_text(row, "produced", kind), reference=_text(row, "reference", kind),
        status=status, verdict=verdict)


# --- §6 the judge ------------------------------------------------------------

def judge_verdict_to_json(verdict: JudgeVerdict) -> dict[str, object]:
    return {"label": verdict.label, "reason": verdict.reason,
            "judged_by": verdict.judged_by, "cost_usd": round(verdict.cost_usd, 6)}


def judge_verdict_from_json(row: dict[str, object]) -> JudgeVerdict:
    kind = "JudgeVerdict"
    # A verdict the model refused to give is recorded as `judged_by="none"`
    # with an empty label — v3's rule, kept: a verdict without a quote that
    # stands is discarded, never rounded into a label.
    label = _text(row, "label", kind)
    judged_by = _one_of(_text(row, "judged_by", kind), JUDGED_BY, kind, "judged_by")
    if judged_by == "none":
        if label != "":
            raise RecordError(f"{kind}.label: judged_by 'none' must carry an empty label, found {label!r}")
    else:
        _one_of(label, JUDGE_LABELS, kind, "label")
    return JudgeVerdict(label=label, reason=_text(row, "reason", kind),
                        judged_by=judged_by, cost_usd=_amount(row, "cost_usd", kind))


# `JudgeRow` is normative in contracts.py (RULINGS.md R-08); imported above.


def judge_row_to_json(row: JudgeRow) -> dict[str, object]:
    return {"case_id": row.case_id, "repeat": row.repeat, "input_sha256": row.input_sha256,
            "verdict": judge_verdict_to_json(row.verdict)}


def judge_row_from_json(row: dict[str, object]) -> JudgeRow:
    kind = "JudgeRow"
    return JudgeRow(
        case_id=_text(row, "case_id", kind), repeat=_whole(row, "repeat", kind),
        input_sha256=_text(row, "input_sha256", kind),
        verdict=judge_verdict_from_json(_as_object(_field(row, "verdict", kind), kind, "verdict")))


def calibration_record_to_json(record: CalibrationRecord) -> dict[str, object]:
    return {"sample_id": record.sample_id, "case_id": record.case_id,
            "pii_types": list(record.pii_types), "family": record.family,
            "register": record.register, "holdout": record.holdout,
            "human_label": record.human_label, "judge_label": record.judge_label,
            "judge_reason": record.judge_reason, "repeat_index": record.repeat_index,
            "judge_model": record.judge_model, "prompt_sha256": record.prompt_sha256}


def calibration_record_from_json(row: dict[str, object]) -> CalibrationRecord:
    kind = "CalibrationRecord"
    # "" is the UNLABELLED state `draw_sample` writes into the sheet; anything
    # else must be a label. `calibration.py` refuses an imported sheet whose
    # human label is empty — here the empty one is legal because the sheet is
    # read back before it is filled.
    human = _text(row, "human_label", kind)
    if human != "":
        _one_of(human, JUDGE_LABELS, kind, "human_label")
    judge = _text(row, "judge_label", kind)
    if judge not in ("", "none"):
        _one_of(judge, JUDGE_LABELS, kind, "judge_label")
    return CalibrationRecord(
        sample_id=_text(row, "sample_id", kind), case_id=_text(row, "case_id", kind),
        pii_types=_strings(_rows(row, "pii_types", kind), kind, "pii_types"),
        family=_text(row, "family", kind), register=_text(row, "register", kind),
        holdout=_flag(row, "holdout", kind), human_label=human, judge_label=judge,
        judge_reason=_text(row, "judge_reason", kind),
        repeat_index=_whole(row, "repeat_index", kind),
        judge_model=_text(row, "judge_model", kind),
        prompt_sha256=_text(row, "prompt_sha256", kind))


def calibration_stamp_to_json(stamp: CalibrationStamp) -> dict[str, object]:
    return {"judge_model": stamp.judge_model, "prompt_sha256": stamp.prompt_sha256,
            "n": stamp.n, "raw_agreement": stamp.raw_agreement, "kappa": stamp.kappa,
            "per_type_kappa": dict(stamp.per_type_kappa),
            "repeat_disagreement": stamp.repeat_disagreement, "calibrated": stamp.calibrated}


def calibration_stamp_from_json(row: dict[str, object]) -> CalibrationStamp:
    kind = "CalibrationStamp"
    per_type = _table(row, "per_type_kappa", kind)
    kappas: dict[str, float] = {}
    for name, value in per_type.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RecordError(f"{kind}.per_type_kappa[{name}]: expected a number, found {value!r}")
        kappas[name] = float(value)
    return CalibrationStamp(
        judge_model=_text(row, "judge_model", kind), prompt_sha256=_text(row, "prompt_sha256", kind),
        n=_whole(row, "n", kind), raw_agreement=_amount(row, "raw_agreement", kind),
        kappa=_amount(row, "kappa", kind), per_type_kappa=kappas,
        repeat_disagreement=_amount(row, "repeat_disagreement", kind),
        calibrated=_flag(row, "calibrated", kind))


# --- the triple row ------------------------------------------------------------

TRIPLE_KIND: str = "triple"


@dataclass(frozen=True)
class TripleTotals:
    """What a `<run>.triples.jsonl` row carries beyond v4's own fields.

    Two numbers, one writer, one reader, because both were being read with
    `row.get(key) or 0`: `judge_cost_usd` is what the JUDGE drew from the
    shared ledger for this triple (the report prints it apart from the arms'
    share, and a triple file copied from a run that never wrote it read as a
    free judge), and `turn_residual` is how many of the agent's earlier turns
    still carried a minted substitute when the judge prompt was built. A
    default of zero for either is the v4 defect class this benchmark exists
    to avoid — a number that means «nothing happened» and «nobody wrote it
    down» at once.
    """

    judge_cost_usd: float
    turn_residual: int


def triple_totals_to_json(totals: TripleTotals) -> dict[str, object]:
    """The two keys, ready to be merged into the triple row the harness builds.

    Rounded where the ledger rounds, so the file and the ledger cannot
    disagree by a cent.
    """
    return {"judge_cost_usd": round(totals.judge_cost_usd, 6),
            "turn_residual": totals.turn_residual}


def triple_totals_from_json(row: dict[str, object]) -> TripleTotals:
    """The two numbers off a triple row, refused by name when either is missing
    or is not a number. Negative is refused too: a judge that earned money and
    a run whose earlier turns held minus two substitutes are both writer bugs,
    and a report that printed them would be arguing with its own arithmetic."""
    cost = _amount(row, "judge_cost_usd", TRIPLE_KIND)
    residual = _whole(row, "turn_residual", TRIPLE_KIND)
    if cost < 0.0:
        raise RecordError(f"{TRIPLE_KIND}.judge_cost_usd: a judge cannot spend {cost}")
    if residual < 0:
        raise RecordError(f"{TRIPLE_KIND}.turn_residual: {residual} turns cannot hold a substitute")
    return TripleTotals(judge_cost_usd=cost, turn_residual=residual)


# --- §8 the run directory -----------------------------------------------------

def run_file(run_dir: Path, run_id: str, name: str) -> Path:
    """The path of one `RUN_FILES` entry. The names live in `contracts`, so a
    file a component invents is a red line here rather than a file the report
    never finds."""
    if name not in RUN_FILES:
        raise RecordError(f"run_file: {name!r} is not one of RUN_FILES {sorted(RUN_FILES)}")
    return run_dir / name.replace(RUN_PLACEHOLDER, run_id)


def read_rows(path: Path) -> list[dict[str, object]]:
    """Every JSON object of a `.jsonl` file, blank lines skipped."""
    rows: list[dict[str, object]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as error:
            raise RecordError(f"{path}:{number}: not JSON ({error})") from error
        if not isinstance(parsed, dict):
            raise RecordError(f"{path}:{number}: expected an object, found {type(parsed).__name__}")
        rows.append({str(key): value for key, value in parsed.items()})
    return rows


def append_row(path: Path, row: dict[str, object]) -> None:
    """One row, flushed to its own line.

    Append, never rewrite: v4's rule is that a triple's rows are on disk
    before the next triple starts, so an outage costs one triple and not the
    run. `ensure_ascii=False` because every value here is Russian and an
    escaped file is unreadable to the person who has to audit it.
    """
    with path.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def merged_v5_records(run_dir: Path) -> list[dict[str, object]]:
    """Every v5 arm row of a run directory, deduplicated, the COMPLETED one
    winning — v4's `merged_arm_records` rule, over `*.arms.v5.jsonl`.

    The rule is copied rather than shared because the v4 function globs
    `*.arms.jsonl`, which does not match `*.arms.v5.jsonl`; parameterising v4's
    function would be an edit to v4, and v5 never edits v4.
    """
    best: dict[tuple[str, int, str], dict[str, object]] = {}
    for path in sorted(run_dir.glob("*.arms.v5.jsonl")):
        for row in read_rows(path):
            key = (_text(row, "case_id", "ArmRunV5"), _whole(row, "repeat", "ArmRunV5"),
                   _text(row, "arm", "ArmRunV5"))
            previous = best.get(key)
            if previous is None or (previous.get("termination") != "done"
                                    and row.get("termination") == "done"):
                best[key] = row
    return list(best.values())
