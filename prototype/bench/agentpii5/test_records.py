"""`records.py` pinned: every row round-trips, a v4 reader reads a v5 run, and
a malformed row is REFUSED by the name of the field it is missing.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_records

Every check here is shown to fail on a negative fixture as well as to pass on
a good one. A serialiser tested only on its own output is a mirror: it agrees
with itself on a row the harness could never write, and the first thing a
replay of a real run meets is a row somebody wrote by hand.

The v4 interoperation is asserted by RUNNING v4's own reader
(`bench.agentpii4.autopsy._load_run`) on a fixture run directory, not by
comparing key sets: the promise of §8 is that v4's tools read a v5 run, and
only v4's code can testify to that.
"""
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii3.schema import Source
from bench.agentpii4.compare import ArmRun, ObservedCall
from bench.agentpii4.records import ArmMeta, arm_from_record, arm_record
from bench.agentpii4.schema import (
    Case, Expectation, Locus, Message, PiiItem, Provenance, SeedRecord)
from bench.agentpii5 import records as r
from bench.agentpii5.contracts import (
    AnswerSpan, ArmRunV5, CalibrationRecord, CalibrationStamp, FormVerdict, Hop,
    HopObservation, JudgeVerdict, MentionRecord, ToolResultRecord)



def _case(licence: str) -> Case:
    """The smallest case v4's `case_from_json` accepts, with one item."""
    source = None if licence == "" else Source(corpus="speech_calls", key="k1", line=1,
                                               sha256="0" * 64, licence=licence)
    return Case(
        id="c-0001", kind="chain", register="chat",
        provenance=Provenance(kind="authored", corpus="authored", key="", shape="",
                              selection="census", weight=1.0, licence=licence or "authored"),
        cluster="NAME:иванова елена", conversation_id="", now="2026-09-01",
        messages=(Message(role="system", content="ты оператор", source=None, name=""),
                  Message(role="user", content="Лена Иванова, Гоголя 12", source=source, name="")),
        tools=(), seed_records=(SeedRecord(id="s1", table="contacts", fields={"name": "Иванова Елена"},
                                           pii_ids=("p1",)),),
        pii=(PiiItem(id="p1", type="NAME", identity="i1", value="Лена Иванова",
                     canonical="Иванова Елена", parts={"given": "Елена", "surname": "Иванова"},
                     where=Locus(kind="message", msg=1, start=0, end=12, record="", path=""),
                     duty="required", spoken=False, stale=False),),
        plain=(), negatives=(),
        expects=Expectation(reachable_tools=("crm_find_contact",), primary_identity="i1",
                            must_contain=(), must_not_contain=(), validate_types=()),
        trace=(), note="фикстура сериализации")


def _arm(case_id: str, arm: str) -> ArmRun:
    call = ObservedCall(name="crm_find_contact", written={"name": "Пахомова Ольга"},
                        restored={"name": "Иванова Елена"}, residual={"name": ()},
                        refusal_path="", refusal_rule="", parsed={"name": "Пахомова Ольга"}, seq=0)
    return ArmRun(case_id=case_id, arm=arm, repeat=0, calls=(call,),
                  state=({"table": "contacts", "id": "s1"},), reply="Нашёл Елену Иванову.",
                  termination="done", cost_usd=0.0123,
                  substitutes={"p1": ("Пахомова Ольга", {"given": "Ольга", "surname": "Пахомова"})},
                  masked_spans={1: ((0, 12),)})


def _tool_result() -> ToolResultRecord:
    return ToolResultRecord(
        tool_name="crm_find_contact", seq=0, call_ordinal=0, turn=1, return_form="json",
        text_real='{"name": "Иванова Елена"}', text_masked='{"name": "Пахомова Ольга"}',
        spans_real={"p1": (10, 24), "echo:p1": (10, 24)},
        pieces=((10, 24, "Пахомова Ольга", "NAME"),), forced=False)


def _arm_v5(case_id: str) -> ArmRunV5:
    return ArmRunV5(
        base=_arm(case_id, "I"), reply_raw="Нашёл Пахомову Ольгу.",
        control_reply="Нашёл Елену Иванову.", tool_results=(_tool_result(),),
        mentions=(MentionRecord(item_id="p1", msg=-1, result_seq=0,
                                substitute="Пахомова Ольга", request_index=2),),
        turn_replies=("Секунду, ищу.", "Нашёл Елену Иванову."),
        call_turns=(1,), request_count=3, stream_mismatch=False)


def _hop() -> Hop:
    return Hop(kind="IN", owner="tool", item_id="p1", hop_index=1, turn=1,
               tool_name="crm_find_contact", call_ordinal=0, parallel_group="",
               source_hop=-1, path="contact.name", optional=False)


def _observation(status: str, verdict: FormVerdict | None) -> HopObservation:
    return HopObservation(case_id="c-0001", repeat=0, hop=_hop(), declared=True,
                          pii_type="NAME", produced="Пахомова Ольга", reference="Иванова Елена",
                          status=status, verdict=verdict)


def _calibration_record() -> CalibrationRecord:
    return CalibrationRecord(
        sample_id="s-001", case_id="c-0001", pii_types=("NAME", "LOC"), family="chain",
        register="chat", holdout=True, human_label="верно", judge_label="частично",
        judge_reason="«Нашёл Елену Иванову» — запись та, но телефон не назван",
        repeat_index=1, judge_model="claude-sonnet-5", prompt_sha256="ab" * 32)


def _stamp() -> CalibrationStamp:
    return CalibrationStamp(judge_model="claude-sonnet-5", prompt_sha256="ab" * 32, n=300,
                            raw_agreement=0.91, kappa=0.78, per_type_kappa={"NAME": 0.81},
                            repeat_disagreement=0.04, calibrated=True)


def _through_json(row: dict[str, object]) -> dict[str, object]:
    """Force the row through real JSON: a tuple that survives in memory as a
    tuple is a field that changes type on the first replay."""
    return json.loads(json.dumps(row, ensure_ascii=False))


def _refused(call: Callable[[], object], needle: str, label: str) -> list[str]:
    """The check must FAIL on this input, and its message must name `needle`."""
    try:
        call()
    except r.RecordError as error:
        if needle in str(error):
            return []
        return [f"{label}: refused, but the message does not name {needle!r}: {error}"]
    return [f"{label}: accepted a row it must refuse"]


def test_no_pseudex() -> list[str]:
    loaded = sorted(name for name in sys.modules if name.startswith("pseudex"))
    return [] if not loaded else [f"records pulled in the engine: {loaded}"]


def test_round_trips() -> list[str]:
    failures: list[str] = []
    pairs: tuple[tuple[str, object, Callable[[], dict[str, object]], Callable[[dict[str, object]], object]], ...] = (
        ("Hop", _hop(), lambda: r.hop_to_json(_hop()), r.hop_from_json),
        ("FormVerdict.same", FormVerdict(True, frozenset()),
         lambda: r.form_verdict_to_json(FormVerdict(True, frozenset())), r.form_verdict_from_json),
        ("FormVerdict.differs", FormVerdict(False, frozenset({"gram_case", "case_class"})),
         lambda: r.form_verdict_to_json(FormVerdict(False, frozenset({"gram_case", "case_class"}))),
         r.form_verdict_from_json),
        ("MentionRecord", _arm_v5("c-0001").mentions[0],
         lambda: r.mention_to_json(_arm_v5("c-0001").mentions[0]), r.mention_from_json),
        ("ToolResultRecord", _tool_result(), lambda: r.tool_result_to_json(_tool_result()),
         r.tool_result_from_json),
        ("AnswerSpan", AnswerSpan("p1", 6, 20, 6, 19),
         lambda: r.answer_span_to_json(AnswerSpan("p1", 6, 20, 6, 19)), r.answer_span_from_json),
        ("HopObservation.observed", _observation("observed", FormVerdict(False, frozenset({"gram_case"}))),
         lambda: r.hop_observation_to_json(_observation("observed", FormVerdict(False, frozenset({"gram_case"})))),
         r.hop_observation_from_json),
        ("HopObservation.leaked", _observation("leaked", None),
         lambda: r.hop_observation_to_json(_observation("leaked", None)), r.hop_observation_from_json),
        ("JudgeVerdict.model", JudgeVerdict("частично", "«Нашёл Елену»", "model", 0.0031),
         lambda: r.judge_verdict_to_json(JudgeVerdict("частично", "«Нашёл Елену»", "model", 0.0031)),
         r.judge_verdict_from_json),
        ("JudgeVerdict.none", JudgeVerdict("", "цитата не стоит в ответе", "none", 0.0),
         lambda: r.judge_verdict_to_json(JudgeVerdict("", "цитата не стоит в ответе", "none", 0.0)),
         r.judge_verdict_from_json),
        ("JudgeRow", r.JudgeRow("c-0001", 0, "cd" * 32, JudgeVerdict("верно", "«Елену»", "model", 0.002)),
         lambda: r.judge_row_to_json(r.JudgeRow("c-0001", 0, "cd" * 32,
                                                JudgeVerdict("верно", "«Елену»", "model", 0.002))),
         r.judge_row_from_json),
        ("CalibrationRecord", _calibration_record(),
         lambda: r.calibration_record_to_json(_calibration_record()), r.calibration_record_from_json),
        ("CalibrationStamp", _stamp(), lambda: r.calibration_stamp_to_json(_stamp()),
         r.calibration_stamp_from_json),
    )
    for label, original, dump, load in pairs:
        back = load(_through_json(dump()))
        if back != original:
            failures.append(f"{label}: round trip differs\n    was {original}\n    now {back}")
    # The arm record needs a case and a meta, so it is not in the table above.
    case = _case("")
    run = _arm_v5(case.id)
    back_arm = r.arm_v5_from_record(_through_json(r.arm_v5_record(run, _meta(), case)))
    if back_arm != run:
        failures.append(f"ArmRunV5: round trip differs\n    was {run}\n    now {back_arm}")
    return failures


def _meta() -> ArmMeta:
    return ArmMeta(model="claude-haiku-4-5-20251001", turns=4, duration_ms=8123,
                   session_id="sess", subtype="success", is_error=False, api_error_status=None,
                   errors=(), reason="", cap_usd=0.5)


def test_v4_reader_ignores_v5_key() -> list[str]:
    case = _case("")
    run = _arm_v5(case.id)
    record = _through_json(r.arm_v5_record(run, _meta(), case))
    failures: list[str] = []
    if r.V5_KEY not in record:
        failures.append("the v5 row carries no 'v5' key")
    stripped = {key: value for key, value in record.items() if key != r.V5_KEY}
    if arm_from_record(record) != arm_from_record(stripped):
        failures.append("v4's reader sees a different arm with and without the v5 key")
    if arm_from_record(record) != run.base:
        failures.append("v4's reader does not reproduce ArmRunV5.base")
    # The v4 row and the v5 row must agree on every v4 field, or the baseline
    # block would be computed from other bytes than the treatment.
    v4_row = _through_json(arm_record(run.base, _meta(), case))
    if v4_row != stripped:
        failures.append("the v4 fields of a v5 row differ from v4's own record")
    return failures


def test_scrub_blanks_a_licensed_case() -> list[str]:
    case = _case("CC BY-NC 4.0")
    record = r.arm_v5_record(_arm_v5(case.id), _meta(), case)
    block = record[r.V5_KEY]
    if not isinstance(block, dict):
        return ["the v5 block is not an object"]
    if block["reply_raw"] != r.SCRUB_MARKER or block["tool_results"] != [] or block["mentions"] != []:
        return [f"a licensed case kept its values: {block}"]
    if block["request_count"] != 3 or block["stream_mismatch"] is not False:
        return ["the scrub dropped the counts it does not need to drop"]
    return []


def _write_run(root: Path) -> Path:
    """A v4-shaped run directory: corpus.json + one complete triple."""
    run_dir = root / "v5-nano"
    run_dir.mkdir()
    case = _case("")
    (run_dir / "corpus.json").write_text(
        json.dumps({"corpus": [case.to_json()], "digest": "deadbeef"}, ensure_ascii=False),
        encoding="utf-8")
    arms = run_dir / "abc123.arms.jsonl"
    for arm in ("C", "I", "C2"):
        r.append_row(arms, arm_record(_arm(case.id, arm), _meta(), case))
    r.append_row(r.run_file(run_dir, "abc123", "<run>.arms.v5.jsonl"),
                 r.arm_v5_record(_arm_v5(case.id), _meta(), case))
    return run_dir


def test_v4_readers_accept_v5_run() -> list[str]:
    from bench.agentpii4.autopsy import _load_run
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _write_run(Path(tmp))
        corpus, triples, excluded = _load_run(run_dir)
        failures: list[str] = []
        if sorted(corpus) != ["c-0001"]:
            failures.append(f"v4 read another corpus: {sorted(corpus)}")
        if len(triples) != 1 or triples[0].case_id != "c-0001":
            failures.append(f"v4 built {len(triples)} triples, excluded={excluded}")
        # The negative: the SAME reader must come back empty when the run is
        # incomplete, or «1 triple» would prove nothing about the reader.
        broken = Path(tmp) / "broken"
        broken.mkdir()
        (broken / "corpus.json").write_text(
            (run_dir / "corpus.json").read_text(encoding="utf-8"), encoding="utf-8")
        rows = r.read_rows(run_dir / "abc123.arms.jsonl")
        r.append_row(broken / "abc123.arms.jsonl", rows[0])
        if _load_run(broken)[1]:
            failures.append("v4's reader built a triple out of one arm")
        return failures


def test_merged_done_wins() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        case = _case("")
        failed = _arm_v5(case.id)
        broken_base = ArmRun(case_id=case.id, arm="I", repeat=0, calls=(), state=(),
                             reply="", termination="error", cost_usd=0.0,
                             substitutes={}, masked_spans={})
        broken = ArmRunV5(base=broken_base, reply_raw="", control_reply="", tool_results=(),
                          mentions=(), turn_replies=(), call_turns=(), request_count=0,
                          stream_mismatch=False)
        # The failure sorts FIRST by file name and the retry second, and then
        # the other way round: «prefer done» must not be «prefer the later file».
        r.append_row(run_dir / "111.arms.v5.jsonl", r.arm_v5_record(broken, _meta(), case))
        r.append_row(run_dir / "222.arms.v5.jsonl", r.arm_v5_record(failed, _meta(), case))
        merged = r.merged_v5_records(run_dir)
        if len(merged) != 1 or merged[0]["termination"] != "done":
            failures.append(f"done did not win over error: {[row['termination'] for row in merged]}")
        (run_dir / "111.arms.v5.jsonl").unlink()
        (run_dir / "222.arms.v5.jsonl").rename(run_dir / "000.arms.v5.jsonl")
        r.append_row(run_dir / "999.arms.v5.jsonl", r.arm_v5_record(broken, _meta(), case))
        merged = r.merged_v5_records(run_dir)
        if len(merged) != 1 or merged[0]["termination"] != "done":
            failures.append("a later FAILURE overwrote the completed record")
        if r.arm_v5_from_record(merged[0]).reply_raw != failed.reply_raw:
            failures.append("the merged row does not read back as the completed arm")
    return failures


def test_malformed_rows_are_refused() -> list[str]:
    """Each reader is shown to REFUSE, and to name the field it refused on."""
    failures: list[str] = []
    hop = r.hop_to_json(_hop())
    without_turn = {key: value for key, value in hop.items() if key != "turn"}
    failures += _refused(lambda: r.hop_from_json(without_turn), "'turn'", "Hop without turn")
    failures += _refused(lambda: r.hop_from_json({**hop, "kind": "THROUGH"}), "kind",
                         "Hop with an unknown kind")
    failures += _refused(lambda: r.hop_from_json({**hop, "owner": "operator"}), "owner",
                         "Hop with an unknown owner")
    failures += _refused(lambda: r.hop_from_json({**hop, "turn": "1"}), "turn",
                         "Hop whose turn is a string")
    failures += _refused(lambda: r.hop_from_json({**hop, "optional": 0}), "optional",
                         "Hop whose flag is an integer")

    mention = r.mention_to_json(_arm_v5("c-0001").mentions[0])
    failures += _refused(lambda: r.mention_from_json({key: value for key, value in mention.items()
                                                      if key != "substitute"}),
                         "'substitute'", "MentionRecord without substitute")

    result = _through_json(r.tool_result_to_json(_tool_result()))
    failures += _refused(lambda: r.tool_result_from_json({key: value for key, value in result.items()
                                                          if key != "spans_real"}),
                         "'spans_real'", "ToolResultRecord without spans_real")
    failures += _refused(lambda: r.tool_result_from_json({**result, "pieces": [[1, 2, "x"]]}),
                         "pieces", "ToolResultRecord with a 3-element piece")
    failures += _refused(lambda: r.tool_result_from_json({**result, "spans_real": {"p1": [1, 2, 3]}}),
                         "spans_real", "ToolResultRecord with a 3-bound span")

    observed = r.hop_observation_to_json(_observation("observed", FormVerdict(True, frozenset())))
    failures += _refused(lambda: r.hop_observation_from_json({**observed, "verdict": None}),
                         "observed", "an observed hop with no verdict")
    failures += _refused(lambda: r.hop_observation_from_json({**observed, "status": "leaked"}),
                         "leaked", "a leaked hop carrying a form verdict")
    failures += _refused(lambda: r.hop_observation_from_json({**observed, "status": "compared"}),
                         "status", "a hop with an unknown status")
    failures += _refused(lambda: r.form_verdict_from_json({"same": True, "differs": ["gram_case"]}),
                         "contradicts", "a verdict that is `same` and differs")

    verdict = r.judge_verdict_to_json(JudgeVerdict("верно", "«Елену»", "model", 0.001))
    failures += _refused(lambda: r.judge_verdict_from_json({**verdict, "label": "правильно"}),
                         "label", "a judge label outside JUDGE_LABELS")
    failures += _refused(lambda: r.judge_verdict_from_json({**verdict, "judged_by": "gate"}),
                         "judged_by", "an unknown judged_by")
    failures += _refused(lambda: r.judge_verdict_from_json({**verdict, "judged_by": "none"}),
                         "label", "judged_by 'none' with a label")
    failures += _refused(lambda: r.judge_verdict_from_json({key: value for key, value in verdict.items()
                                                            if key != "cost_usd"}),
                         "'cost_usd'", "a verdict without its cost")

    record = _through_json(r.calibration_record_to_json(_calibration_record()))
    failures += _refused(lambda: r.calibration_record_from_json({**record, "human_label": "ок"}),
                         "human_label", "a human label outside JUDGE_LABELS")
    if r.calibration_record_from_json({**record, "human_label": ""}).human_label != "":
        failures.append("the unlabelled sheet row must be readable")

    stamp = _through_json(r.calibration_stamp_to_json(_stamp()))
    failures += _refused(lambda: r.calibration_stamp_from_json({**stamp, "per_type_kappa": {"NAME": "0.8"}}),
                         "per_type_kappa", "a stamp whose kappa is a string")

    arm = _through_json(r.arm_v5_record(_arm_v5("c-0001"), _meta(), _case("")))
    failures += _refused(lambda: r.arm_v5_from_record({key: value for key, value in arm.items()
                                                       if key != r.V5_KEY}),
                         "'v5'", "a v4 row read as a v5 row")
    block = arm[r.V5_KEY]
    assert isinstance(block, dict)
    failures += _refused(
        lambda: r.arm_v5_from_record({**arm, r.V5_KEY: {key: value for key, value in block.items()
                                                        if key != "control_reply"}}),
        "'control_reply'", "an ArmRunV5 without the control reply")
    failures += _refused(
        lambda: r.arm_v5_from_record({**arm, r.V5_KEY: {**block, "call_turns": [1, "2"]}}),
        "call_turns", "an ArmRunV5 whose call turns are strings")
    failures += _refused(
        lambda: r.arm_v5_from_record({**arm, r.V5_KEY: {key: value for key, value in block.items()
                                                        if key != "turn_replies"}}),
        "'turn_replies'", "an ArmRunV5 without the agent's turns")
    failures += _refused(
        lambda: r.arm_v5_from_record({**arm, r.V5_KEY: {**block, "turn_replies": ["ok", 2]}}),
        "turn_replies", "an ArmRunV5 whose turn replies are not all text")
    return failures


def test_scrubbed_run_keeps_the_turn_count() -> list[str]:
    """A licensed case loses every value and keeps every count.

    `turn_replies` is the one field where both halves meet: the text is the
    agent's own words (scrubbed) and the LENGTH is how far the dialogue got —
    which `--report` prints and no other field carries. Dropping the list to
    `[]` would have said the agent never spoke, on every licensed case.
    """
    failures: list[str] = []
    run = _arm_v5("c-0001")
    record = _through_json(r.arm_v5_record(run, _meta(), _case("CC BY-NC 4.0")))
    back = r.arm_v5_from_record(record)
    if len(back.turn_replies) != len(run.turn_replies):
        failures.append(f"a scrubbed run lost the turn count: {back.turn_replies}")
    if any(text != r.SCRUB_MARKER for text in back.turn_replies):
        failures.append(f"a scrubbed run kept the agent's words: {back.turn_replies}")
    # The positive atom: the same run under an authored licence keeps them.
    kept = r.arm_v5_from_record(_through_json(r.arm_v5_record(run, _meta(), _case(""))))
    if kept.turn_replies != run.turn_replies:
        failures.append(f"an authored run lost its turns: {kept.turn_replies}")
    return failures


def test_run_files_are_the_contract() -> list[str]:
    failures: list[str] = []
    path = r.run_file(Path("/tmp/run"), "abc123", "<run>.hops.jsonl")
    if path.name != "abc123.hops.jsonl":
        failures.append(f"run_file did not substitute the run id: {path}")
    if r.run_file(Path("/tmp/run"), "abc123", "corpus.v5.json").name != "corpus.v5.json":
        failures.append("a file without <run> must keep its name")
    failures += _refused(lambda: r.run_file(Path("/tmp/run"), "abc123", "<run>.answers.jsonl"),
                         "RUN_FILES", "a file name outside RUN_FILES")
    with tempfile.TemporaryDirectory() as tmp:
        broken = Path(tmp) / "x.jsonl"
        broken.write_text('{"a": 1}\n\nnot json\n', encoding="utf-8")
        failures += _refused(lambda: r.read_rows(broken), "not JSON", "a corrupt jsonl line")
        listed = Path(tmp) / "y.jsonl"
        listed.write_text('[1, 2]\n', encoding="utf-8")
        failures += _refused(lambda: r.read_rows(listed), "expected an object", "a jsonl array row")
    return failures


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("round_trips", test_round_trips),
        ("v4_reader_ignores_v5_key", test_v4_reader_ignores_v5_key),
        ("scrub_blanks_a_licensed_case", test_scrub_blanks_a_licensed_case),
        ("v4_readers_accept_v5_run", test_v4_readers_accept_v5_run),
        ("merged_done_wins", test_merged_done_wins),
        ("malformed_rows_are_refused", test_malformed_rows_are_refused),
        ("scrubbed_run_keeps_the_turn_count", test_scrubbed_run_keeps_the_turn_count),
        ("run_files_are_the_contract", test_run_files_are_the_contract),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("records: PASS" if not failures else "records: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
