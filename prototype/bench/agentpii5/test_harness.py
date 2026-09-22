"""`harness.py` pinned OFFLINE: one importer of the engine, one ledger, every run file.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_harness

No model, no key, no money. The live path is driven by a CANNED
`TripleRunner`: `drive_v5` takes the runner as a parameter precisely so the
writer can be exercised without the SDK, and a seam that exists only inside a
test is a seam nobody ever looked at.

WHAT IS ACTUALLY PROVEN HERE.
* only `harness.py` names `pseudex` in an import, walked with `ast` over every
  module of the package (a grep would count this file's own docstring);
* the ledger that admits an agent triple is the SAME object the judge config
  holds — asserted by identity AND by driving a triple against a ledger with a
  zero ceiling and watching it be RECORDED as refused rather than dropped;
* a run directory ends up holding every name in `contracts.RUN_FILES`, the
  last two written by the report itself.
"""
import ast
import asyncio
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii3.live import judge as v3_judge
from bench.agentpii4 import harness as v4_harness
from bench.agentpii4.compare import ArmRun, ObservedCall
from bench.agentpii4.records import ArmMeta
from bench.agentpii5 import harness as h
from bench.agentpii5 import records as r
from bench.agentpii5.contracts import (
    PSEUDEX_ALLOWED_MODULES, QUERY_CAP_USD, RETRIES, RUN_FILES, ArmRunV5, CaseV5,
    HopObservation, JudgeRow, JudgeVerdict, MentionRecord, ToolResultRecord)
from bench.agentpii5.fixtures import NAME_ITEM, PHONE_ITEM, _case, _hop
from bench.agentpii5.form import form_match
from bench.agentpii5.judge import JudgeConfig, prompt_sha256

RUN_ID: str = "abc123"
REAL_NAME: str = NAME_ITEM.value
SUBSTITUTE: str = "Пахомова Ольга"


def _fixture_case() -> CaseV5:
    hops = (_hop("IN", "user", "p1", 0, 0, "", -1, -1, ""),
            _hop("OUT", "answer", "p1", 1, 0, "", -1, -1, ""))
    return _case("c-0001", "single", (f"{REAL_NAME}, {PHONE_ITEM.value}",),
                 (NAME_ITEM, PHONE_ITEM), hops)


def _meta() -> ArmMeta:
    return ArmMeta(model="claude-haiku-4-5-20251001", turns=2, duration_ms=1200,
                   session_id="sess", subtype="success", is_error=False, api_error_status=None,
                   errors=(), reason="", cap_usd=0.5)


def _arm(case: CaseV5, arm: str, reply: str) -> v4_harness.ArmOutcome:
    call = ObservedCall(name="crm_find_contact", written={"name": SUBSTITUTE},
                        restored={"name": REAL_NAME}, residual={"name": ()},
                        refusal_path="", refusal_rule="", parsed={"name": SUBSTITUTE}, seq=1)
    run = ArmRun(case_id=case.base.id, arm=arm, repeat=0, calls=(call,), state=(), reply=reply,
                 termination="done", cost_usd=0.01,
                 substitutes={"p1": (SUBSTITUTE, {})} if arm == "I" else {},
                 masked_spans={0: ((0, len(REAL_NAME)),)} if arm == "I" else {})
    return v4_harness.ArmOutcome(run, _meta())


def _gateway_run(case: CaseV5) -> ArmRunV5:
    base = _arm(case, "I", f"Нашёл {REAL_NAME}.").run
    result = ToolResultRecord(
        tool_name="crm_find_contact", seq=1, call_ordinal=0, turn=0, return_form="single",
        text_real=f"{REAL_NAME}", text_masked=SUBSTITUTE,
        spans_real={"p1": (0, len(REAL_NAME))},
        pieces=((0, len(REAL_NAME), SUBSTITUTE, "NAME"),), forced=False)
    return ArmRunV5(base=base, reply_raw=f"Нашёл {SUBSTITUTE}.",
                    control_reply=f"Нашёл {REAL_NAME}.", tool_results=(result,),
                    mentions=(MentionRecord(item_id="p1", msg=0, result_seq=-1,
                                            substitute=SUBSTITUTE, request_index=1),),
                    turn_replies=(f"Нашёл {REAL_NAME}.",),
                    call_turns=(0,), request_count=2, stream_mismatch=False)


def _canned(case: CaseV5) -> h.TripleResult:
    run = _gateway_run(case)
    outcomes = [_arm(case, "C", f"Нашёл {REAL_NAME}."),
                v4_harness.ArmOutcome(run.base, _meta()),
                _arm(case, "C2", f"Нашёл {REAL_NAME}.")]
    # Both declared hops, and the OUT/answer one on purpose: the calibration
    # sample is stratified by the types the ANSWER carried, so a fixture with
    # only an IN hop would exercise the writer and nothing downstream of it.
    hops = tuple(HopObservation(
        case_id=case.base.id, repeat=0, hop=one, declared=True, pii_type="NAME",
        produced=SUBSTITUTE, reference=REAL_NAME, status="observed",
        verdict=form_match("NAME", SUBSTITUTE, REAL_NAME)) for one in case.hops)
    judged = JudgeRow(case_id=case.base.id, repeat=0, input_sha256="0" * 64,
                      verdict=JudgeVerdict(label="верно", reason="запись та же · цитата: «Нашёл»",
                                           judged_by="model", cost_usd=0.02))
    triple = {"case_id": case.base.id, "repeat": 0, "kind": case.base.kind,
              "behaviour": case.behaviour, "register": case.base.register,
              "cluster": case.base.cluster, "cap_usd": 0.5, "cost_usd": 0.03,
              "status": "complete", "reason": "", "arms": {}, "judge": {}}
    return h.TripleResult(outcomes, run, hops, judged, triple)


def test_only_harness_imports_pseudex() -> list[str]:
    """One MODULE of the package imports the engine, and one TEST runs it.

    The instrument's modules are the closed list `PSEUDEX_ALLOWED_MODULES`.
    Tests are a separate question with a separate answer: `test_harness_stream`
    must run the real restoration leg in process (that is what it measures),
    and every other test must stay engine-free or its own `test_no_pseudex`
    would be a formality. Both halves are asserted, so neither list can grow
    quietly.
    """
    here = Path(__file__).resolve().parent
    importers = h.pseudex_importers(here)
    allowed = tuple(name.rsplit(".", 1)[-1] for name in PSEUDEX_ALLOWED_MODULES)
    failures: list[str] = []
    modules = tuple(name for name in importers if not name.startswith("test_"))
    tests = tuple(name for name in importers if name.startswith("test_"))
    if sorted(modules) != sorted(allowed):
        failures.append(f"движок импортируют модули {modules}, а можно только {allowed}")
    if sorted(tests) != ["test_harness_stream"]:
        failures.append(f"движок импортируют тесты {tests}, а можно только test_harness_stream")
    # The walk must be able to FIND one: a checker that returns () on everything
    # would pass this package for ever.
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "leaky.py").write_text("from pseudex.vault import Vault\n", encoding="utf-8")
        (Path(tmp) / "clean.py").write_text("# pseudex is only a word here\nimport json\n",
                                            encoding="utf-8")
        found = h.pseudex_importers(Path(tmp))
        if found != ("leaky",):
            failures.append(f"обход ast нашёл {found}, а должен был найти ровно ('leaky',)")
    # And the loaded modules agree with the source: something imported lazily
    # inside a function would not show in the ast walk but would show here.
    if "pseudex.vault" not in sys.modules:
        failures.append("harness импортирован, а движок не загружен — проверка ни о чём")
    return failures


def test_ledger_shared() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        ledger = v3_judge.SpendLedger(Path(tmp) / "spend.tsv", 0.0)
        config = JudgeConfig(model="claude-sonnet-5", ledger=ledger,
                             query_cap_usd=QUERY_CAP_USD, retries=RETRIES, trace_path=None)
        if config.ledger is not ledger:
            failures.append("у судьи своя копия потолка")
        # A ceiling of zero admits nothing, so the triple is RECORDED as refused
        # and no arm runs — which also proves the agent leg reserves on the SAME
        # ledger the judge holds.
        case = _fixture_case()
        result = asyncio.run(h.run_triple_v5(case, 0, None, ledger, config,  # type: ignore[arg-type]
                                             "claude-haiku-4-5-20251001", RUN_ID))
        if result.triple["status"] != "refused":
            failures.append(f"при нулевом потолке тройка получила статус {result.triple['status']}")
        if result.outcomes or result.gateway_run is not None:
            failures.append("при нулевом потолке что-то всё-таки побежало")
        if "потолок" not in str(result.triple["reason"]):
            failures.append(f"причина отказа не называет потолок: {result.triple['reason']}")
        # The refused triple is a ROW, not a silence: a run that sheds what it
        # cannot afford reports only the cheap cases (v4's rule).
        if result.triple["case_id"] != case.base.id:
            failures.append("отказанная тройка не назвала случай")
        # The NEGATIVE: with a real ceiling the same ledger admits the reservation.
        roomy = v3_judge.SpendLedger(Path(tmp) / "spend2.tsv", 10.0)
        asyncio.run(roomy.reserve(1.0))
        if roomy.reserved() != 1.0:
            failures.append("потолок с местом не принял резерв — проверка отказа ни о чём")
    return failures


def test_run_files_written() -> list[str]:
    failures: list[str] = []
    case = _fixture_case()

    async def runner(one: CaseV5, repeat: int) -> h.TripleResult:
        return _canned(one)

    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "v5-live-nano"
        run_dir.mkdir()
        h.write_corpus(run_dir, [case], "deadbeef")
        asyncio.run(h.drive_v5([case], 1, runner, run_dir, RUN_ID, 1, frozenset()))
        ledger = v3_judge.SpendLedger(r.run_file(run_dir, RUN_ID, "<run>.spend.tsv"), 1.0)
        asyncio.run(ledger.settle("agent/c-0001/0", 0.5, 0.03))
        h.stamp_judge_file(run_dir, RUN_ID, h.CalibrationStamp(
            judge_model="claude-sonnet-5", prompt_sha256=prompt_sha256(), n=0,
            raw_agreement=0.0, kappa=0.0, per_type_kappa={}, repeat_disagreement=1.0,
            calibrated=False))
        h.finish_run(run_dir, run_dir)
        for name in RUN_FILES:
            path = r.run_file(run_dir, RUN_ID, name)
            if not path.exists():
                failures.append(f"прогон не написал {name} ({path.name})")
        arms = r.read_rows(r.run_file(run_dir, RUN_ID, "<run>.arms.jsonl"))
        if sorted(str(row["arm"]) for row in arms) != ["C", "C2", "I"]:
            failures.append(f"в arms.jsonl не три плеча: {[row.get('arm') for row in arms]}")
        v5_rows = r.read_rows(r.run_file(run_dir, RUN_ID, "<run>.arms.v5.jsonl"))
        if len(v5_rows) != 1 or v5_rows[0]["arm"] != "I":
            failures.append(f"в arms.v5.jsonl не одно плечо I: {v5_rows}")
        restored = r.arm_v5_from_record(v5_rows[0])
        if restored.control_reply != f"Нашёл {REAL_NAME}.":
            failures.append("ответ контроля не доехал до записи — rewrite_ratio будет Line(0,0)")
        judge_rows = r.read_rows(r.run_file(run_dir, RUN_ID, "<run>.judge.jsonl"))
        if not judge_rows or "calibrated" not in judge_rows[0]:
            failures.append("штамп калибровки не первой строкой judge.jsonl — report.judge_half "
                            "его не найдёт")
        if len(judge_rows) != 2:
            failures.append(f"в judge.jsonl {len(judge_rows)} строк, ожидались штамп + вердикт")
        report = r.run_file(run_dir, RUN_ID, "<run>.report.txt").read_text(encoding="utf-8")
        if "v5" not in report:
            failures.append("отчёт не назвал прогон v5")
        gate = json.loads(r.run_file(run_dir, RUN_ID, "<run>.gate.json").read_text(encoding="utf-8"))
        if not gate:
            failures.append("gate.json пуст — нечем доказать, что отчёту разрешили печатать")
        # The NEGATIVE: a run directory nobody drove has none of the per-run
        # files, so «все файлы на месте» is a statement about the writer.
        empty = Path(tmp) / "empty"
        empty.mkdir()
        missing = [name for name in RUN_FILES
                   if not r.run_file(empty, RUN_ID, name).exists()]
        if len(missing) != len(RUN_FILES):
            failures.append(f"пустой каталог уже содержит файлы прогона: {missing}")
    return failures


def test_control_reply_is_copied() -> list[str]:
    """`rewrite_ratio` is a diagnostic that must be able to fire, and it can
    only fire when the I record carries the C arm's reply of the SAME triple."""
    case = _fixture_case()
    run = _gateway_run(case)
    failures: list[str] = []
    copied = h.with_control_reply(run, "Контрольный ответ.")
    if copied.control_reply != "Контрольный ответ.":
        failures.append("ответ контроля не скопирован на запись плеча I")
    for field in ("reply_raw", "turn_replies", "call_turns", "request_count", "stream_mismatch"):
        if getattr(copied, field) != getattr(run, field):
            failures.append(f"копирование ответа контроля изменило {field}")
    if copied.base is not run.base:
        failures.append("копирование ответа контроля подменило запись v4")
    if h.with_control_reply(run, "").control_reply != "":
        failures.append("пустой ответ контроля не сохранился как пустой — "
                        "нечем отличить «контроль молчал» от «мы забыли скопировать»")
    return failures


def test_turn_replies_are_restored() -> list[str]:
    """Ruling R-40: the judge reads the agent's earlier turns, so the record
    must hold them RESTORED. Pinned offline with a stand-in for the vault, the
    way `with_control_reply` is: the claim belongs to a function that needs a
    live model, and a claim only a paid run can check is a claim nobody checks.
    """
    failures: list[str] = []

    def restore(text: str) -> str:
        return text.replace(SUBSTITUTE, REAL_NAME)

    replies = (f"Нашёл {SUBSTITUTE}.", "", f"Записал {SUBSTITUTE} на 14:00.")
    got = h.restored_turn_replies(replies, restore)
    if got != (f"Нашёл {REAL_NAME}.", "", f"Записал {REAL_NAME} на 14:00."):
        failures.append(f"реплики по ходам восстановлены не так: {got}")
    if len(got) != len(replies):
        failures.append("восстановление потеряло ход — выравнивание с ходами сломано")
    # The NEGATIVE the empty branch exists for: an empty turn must not be sent
    # through the vault at all, or a restorer with a side effect would be
    # called for a turn the agent never spoke.
    seen: list[str] = []

    def counting(text: str) -> str:
        seen.append(text)
        return text

    h.restored_turn_replies(("", "   ", "сказал"), counting)
    if seen != ["сказал"]:
        failures.append(f"восстановление позвали на пустом ходе: {seen}")
    return failures


def test_baseline_flag_reads_v4_dir() -> list[str]:
    """`--baseline` points the comparison at ANOTHER directory, and the v4
    block then comes from that run's files. Without it the run is compared with
    itself, which is honest and visibly useless."""
    failures: list[str] = []
    case = _fixture_case()

    async def runner(one: CaseV5, repeat: int) -> h.TripleResult:
        return _canned(one)

    with tempfile.TemporaryDirectory() as tmp:
        own = Path(tmp) / "v5"
        other = Path(tmp) / "v4"
        for run_dir in (own, other):
            run_dir.mkdir()
            h.write_corpus(run_dir, [case], "deadbeef")
            asyncio.run(h.drive_v5([case], 1, runner, run_dir, RUN_ID, 1, frozenset()))
        lines = h.finish_run(own, other)
        header = "\n".join(lines[:12])
        if other.name not in header and str(other) not in "\n".join(lines):
            failures.append(f"в отчёте не назван каталог базы {other}: {header[:200]}")
        # The same run compared with itself must name ITSELF, or `--baseline`
        # changes nothing and the flag is decoration.
        alone = h.finish_run(own, own)
        if alone == lines:
            failures.append("отчёт с базой и без базы совпал — --baseline ни на что не влияет")
    return failures


class _MintedOnly:
    """A stand-in for `GatewayV5` with the ONE method `judge_triple` reads.

    The real gateway needs a detector, a vault, an audit log and a cache, and
    `judge_triple` asks it for exactly one thing — the substitutes the run
    minted. Building the whole engine to answer that would make this check
    depend on the engine's state, which is not what it is about.
    """

    def __init__(self, substitutes: tuple[str, ...]) -> None:
        self._substitutes = substitutes

    def substitutes(self) -> tuple[str, ...]:
        return self._substitutes


def _run_with_turns(case: CaseV5, turns: tuple[str, ...], answer: str) -> ArmRunV5:
    run = _gateway_run(case)
    base = ArmRun(case_id=case.base.id, arm="I", repeat=0, calls=run.base.calls, state=(),
                  reply=answer, termination="done", cost_usd=0.01,
                  substitutes={"p1": (SUBSTITUTE, {})}, masked_spans={})
    return ArmRunV5(base=base, reply_raw=answer, control_reply=run.control_reply,
                    tool_results=(), mentions=run.mentions, turn_replies=turns,
                    call_turns=run.call_turns, request_count=run.request_count,
                    stream_mismatch=False)


def test_residual_in_an_earlier_turn_is_measured() -> list[str]:
    """F3.2, the reviewers' `f2_oracleleak.py` turned into the pin: a substitute
    the restorer left in an INTERMEDIATE turn is counted, not fatal.

    The same residual in the FINAL answer was always measured (the pre-gate
    calls it «неверно» for free); one turn earlier it raised `OracleLeak` out
    of `build_prompt`, and `judge_triple` has no `except` — so the exception
    left `run_triple_v5` AFTER all three arms were paid for, left `drive_v5`
    before a single row was appended, and left `main()` before the report, the
    gate file and the stamp. 62 of 66 multi-turn cases in a 150-case sample
    are one agent restatement away from it.
    """
    failures: list[str] = []
    case = _fixture_case()
    gateway = _MintedOnly((SUBSTITUTE,))
    earlier = _run_with_turns(case, (f"Нашёл {SUBSTITUTE}.", f"Готово, {REAL_NAME}."),
                              f"Готово, {REAL_NAME}.")
    try:
        outcome = asyncio.run(h.judge_triple(case, earlier, gateway, None))  # type: ignore[arg-type]
    except h.OracleLeak as leak:
        # Reported rather than propagated: this is the very failure F3.2
        # closed, and a check that dies takes the rest of the file with it.
        return [f"подмена в раннем ходе снова убивает тройку: {leak}"]
    if outcome.turn_residual != 1:
        failures.append(f"нераскрытых подмен в ходах насчитано {outcome.turn_residual}, а она одна")
    if len(outcome.row.input_sha256) != 64:
        failures.append(f"промпт не захэширован: {outcome.row.input_sha256!r}")
    if outcome.row.verdict.judged_by != "none":
        failures.append(f"судья выключен, а вердикт {outcome.row.verdict.judged_by}")
    # The same residual in the ANSWER is the pre-gate's verdict, free and
    # deterministic — and it still does not raise.
    in_answer = _run_with_turns(case, (f"Нашёл {REAL_NAME}.", f"Готово, {SUBSTITUTE}."),
                                f"Готово, {SUBSTITUTE}.")
    gated = asyncio.run(h.judge_triple(case, in_answer, gateway, None))  # type: ignore[arg-type]
    if gated.row.verdict.judged_by != "residual_gate":
        failures.append(f"подмена в ответе не остановила судью: {gated.row.verdict}")
    if gated.row.verdict.cost_usd != 0.0:
        failures.append("претгейт потратил деньги")
    if len(gated.row.input_sha256) != 64:
        failures.append("претгейт оставил тройку без хэша промпта — переджудить нечем")
    # The NEGATIVE: a turn with no substitute is counted as nothing, so the
    # number above reads the record rather than the presence of turns.
    honest = _run_with_turns(case, (f"Нашёл {REAL_NAME}.", f"Готово, {REAL_NAME}."),
                             f"Готово, {REAL_NAME}.")
    clean = asyncio.run(h.judge_triple(case, honest, gateway, None))  # type: ignore[arg-type]
    if clean.turn_residual != 0:
        failures.append(f"честный прогон насчитал {clean.turn_residual} нераскрытых подмен")
    return failures


def _handles(source: Path, function: str, exception: str) -> bool:
    """Does `function` in `source` catch `exception`? Walked with `ast`.

    A text scan would find the name in the docstring that explains why the
    catch is there — which is the one place it is guaranteed to appear whether
    or not the catch survived an edit.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != function:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.ExceptHandler) and isinstance(inner.type, ast.Name):
                if inner.type.id == exception:
                    return True
    return False


def test_a_judge_leak_never_discards_the_arms() -> list[str]:
    """F3.2, half two: a leak we DID cause (a substitute in the oracle or in
    the customer's question) still stops the judging — and no longer the run.

    Shown by the reviewers' `f2b_blast.py`: one `OracleLeak` propagated out of
    `drive_v5`, the triple that had paid for three arms left no row at all, and
    `<run>.spend.tsv`, `<run>.report.txt` and `<run>.gate.json` were never
    written. `--resume` would then re-pay for the same leak for ever.
    """
    failures: list[str] = []
    here = Path(__file__).resolve().parent
    if not _handles(here / "harness.py", "run_triple_v5", "OracleLeak"):
        failures.append("run_triple_v5 не ловит OracleLeak — одна утечка снова убьёт прогон")
    # The walk must be able to say «нет», or the check above passes on anything.
    with tempfile.TemporaryDirectory() as tmp:
        naked = Path(tmp) / "naked.py"
        naked.write_text("def run_triple_v5() -> None:\n    \"\"\"OracleLeak\"\"\"\n    pass\n",
                         encoding="utf-8")
        if _handles(naked, "run_triple_v5", "OracleLeak"):
            failures.append("обход ast принял упоминание в строке документации за перехват")
    # And the leak is still LOUD where it is ours: the oracle list.
    case = _fixture_case()
    faked = _run_with_turns(case, (f"Нашёл {REAL_NAME}.",), f"Готово, {REAL_NAME}.")
    try:
        asyncio.run(h.judge_triple(case, faked, _MintedOnly((REAL_NAME,)),  # type: ignore[arg-type]
                                   None))
        failures.append("подмена, совпавшая с оракулом, не подняла OracleLeak")
    except h.OracleLeak:
        pass
    return failures


def test_the_judge_spend_is_charged_to_the_run() -> list[str]:
    """F3.6: the judge draws on the SAME ledger, so a triple's `cost_usd` that
    counted only the arms let `--resume` re-open a ceiling already spent."""
    failures: list[str] = []
    if h.charged(0.03, 0.02) != 0.05:
        failures.append(f"тройка посчитала себе {h.charged(0.03, 0.02)} вместо 0.05")
    if h.charged(0.03, 0.0) != 0.03:
        failures.append("бесплатный судья изменил цену тройки")
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "v5-live-nano"
        run_dir.mkdir()
        arms = r.run_file(run_dir, RUN_ID, "<run>.arms.jsonl")
        for arm in ("C", "I", "C2"):
            r.append_row(arms, {"case_id": "c-0001", "repeat": 0, "arm": arm,
                                "termination": "done"})
        r.append_row(r.run_file(run_dir, RUN_ID, "<run>.triples.jsonl"),
                     {"case_id": "c-0001", "repeat": 0,
                      "cost_usd": h.charged(0.03, 0.02), "judge_cost_usd": 0.02})
        already, spent = h._resume(run_dir)
        if already != frozenset({("c-0001", 0)}):
            failures.append(f"продолжение не увидело готовую тройку: {already}")
        if abs(spent - 0.05) > 1e-9:
            failures.append(f"продолжение списало с потолка ${spent}, а тройка стоила $0.05")
    # The refused triple carries both numbers too, so a run that spent nothing
    # still has the columns the report's cost lines read.
    with tempfile.TemporaryDirectory() as tmp:
        ledger = v3_judge.SpendLedger(Path(tmp) / "spend.tsv", 0.0)
        refused = asyncio.run(h.run_triple_v5(_fixture_case(), 0, None, ledger, None,  # type: ignore[arg-type]
                                              "claude-haiku-4-5-20251001", RUN_ID))
        for key in ("cost_usd", "judge_cost_usd", "turn_residual"):
            if key not in refused.triple:
                failures.append(f"в строке тройки нет поля {key}")
    return failures


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("only_harness_imports_pseudex", test_only_harness_imports_pseudex),
        ("ledger_shared", test_ledger_shared),
        ("run_files_written", test_run_files_written),
        ("control_reply_is_copied", test_control_reply_is_copied),
        ("turn_replies_are_restored", test_turn_replies_are_restored),
        ("baseline_flag_reads_v4_dir", test_baseline_flag_reads_v4_dir),
        ("residual_in_an_earlier_turn_is_measured", test_residual_in_an_earlier_turn_is_measured),
        ("a_judge_leak_never_discards_the_arms", test_a_judge_leak_never_discards_the_arms),
        ("the_judge_spend_is_charged_to_the_run", test_the_judge_spend_is_charged_to_the_run),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("harness: PASS" if not failures else "harness: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
