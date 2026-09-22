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
import inspect
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii3.live import judge as v3_judge
from bench.agentpii4 import harness as v4_harness
from bench.agentpii4.compare import ArmRun, ObservedCall
from bench.agentpii4.gateway import HarnessError
from bench.agentpii4.records import ArmMeta
from bench.agentpii5 import harness as h
from bench.agentpii5 import records as r
from bench.agentpii5.contracts import (
    PSEUDEX_ALLOWED_MODULES, QUERY_CAP_USD, RETRIES, RUN_FILES, ArmRunV5, CaseV5,
    HopObservation, JudgeRow, JudgeVerdict, MentionRecord, ToolResultRecord)
from bench.agentpii5.fixtures import NAME_ITEM, PHONE_ITEM, _case, _hop
from bench.agentpii5.form import form_match
from bench.agentpii5.judge import JUDGE_TEMPERATURE, JudgeConfig, prompt_sha256

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
                    call_turns=(0,), request_count=2, stream_mismatch=False,
                    reply_whole="", turn_residual=0)


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
    # The two totals through the WRITER the harness uses (`h.triple_totals` →
    # `r.triple_totals_to_json`), never spelled here: a canned row that carries
    # different keys from the live one tests the reader against a fixture
    # nobody writes, which is how the report came to read `row.get(key) or 0`.
    triple = {"case_id": case.base.id, "repeat": 0, "kind": case.base.kind,
              "behaviour": case.behaviour, "register": case.base.register,
              "cluster": case.base.cluster, "cap_usd": 0.5,
              "cost_usd": h.charged(0.01, judged.verdict.cost_usd),
              **r.triple_totals_to_json(h.triple_totals(judged, 0)),
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
                             query_cap_usd=QUERY_CAP_USD, retries=RETRIES, trace_path=None,
                             temperature=JUDGE_TEMPERATURE)
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
        h.write_meta(run_dir, RUN_ID, model="claude-haiku-4-5-20251001",
                     judge_model="claude-sonnet-5", tier="nano", repeats=1,
                     digest="deadbeef", ceiling_usd=12.0, spent_usd=0.03)
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
                    stream_mismatch=False, reply_whole="", turn_residual=0)


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
    # `LeakedPrompt`, not the bare `OracleLeak`: `judge_triple` wraps every
    # leak of the build into it (asserted below), and the narrower name is what
    # carries the turn count into the recorded row (R-54). A handler on the
    # parent class would catch the same leaks and read a zero.
    if not _handles(here / "harness.py", "run_triple_v5", "LeakedPrompt"):
        failures.append("run_triple_v5 не ловит LeakedPrompt — одна утечка снова убьёт прогон")
    if not issubclass(h.LeakedPrompt, h.OracleLeak):
        failures.append("LeakedPrompt перестал быть утечкой — перехват сузился молча")
    # The walk must be able to say «нет», or the check above passes on anything.
    with tempfile.TemporaryDirectory() as tmp:
        naked = Path(tmp) / "naked.py"
        naked.write_text("def run_triple_v5() -> None:\n    \"\"\"LeakedPrompt\"\"\"\n    pass\n",
                         encoding="utf-8")
        if _handles(naked, "run_triple_v5", "LeakedPrompt"):
            failures.append("обход ast принял упоминание в строке документации за перехват")
    # And the leak is still LOUD where it is ours: the oracle list. It arrives
    # as a `LeakedPrompt` CARRYING the count the build had already measured —
    # the dialogue is read before the sections are checked, so «сколько ходов
    # несли подмену» is known even on a triple nobody will judge.
    case = _fixture_case()
    faked = _run_with_turns(case, (f"Нашёл {REAL_NAME}.", f"Готово, {REAL_NAME}."),
                            f"Готово, {REAL_NAME}.")
    try:
        asyncio.run(h.judge_triple(case, faked, _MintedOnly((REAL_NAME,)),  # type: ignore[arg-type]
                                   None))
        failures.append("подмена, совпавшая с оракулом, не подняла OracleLeak")
    except h.LeakedPrompt as leak:
        # ONE, and the number is the fixture's: here the «minted substitute» is
        # the real name itself, so it stands in the customer's message AND in
        # the agent's kept turn. Both are masked — the judge reads a substitute
        # nowhere — and only the agent's is COUNTED, because `turn_residual`
        # says «the agent's earlier turns» and a user turn inside it would
        # publish a defect of the gateway that the gateway never had. What
        # matters besides is that a count MEASURED before the refusal reaches
        # the handler: a zero would be indistinguishable from «ни один ход не
        # нёс подмену».
        if leak.turn_residual != 1:
            failures.append(f"утечка унесла с собой {leak.turn_residual} нераскрытых подмен "
                            f"в ходах, а в диалоге фикстуры её несёт один ход агента")
    except h.OracleLeak as bare:
        failures.append(f"утечка сборки промпта пришла без счётчика ходов: {bare}")
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
        if "cost_usd" not in refused.triple:
            failures.append("в строке тройки нет поля cost_usd")
        # Through records' READER, which refuses a missing or non-numeric
        # field by name: a refused triple that simply lacked the two columns
        # read as «судья был бесплатным», and the report could not tell that
        # from «судью не звали».
        try:
            r.triple_totals_from_json(refused.triple)
        except r.RecordError as broken:
            failures.append(f"отказанная тройка не несёт итогов: {broken}")
    return failures


def _calls(source: Path, function: str, callee: str) -> bool:
    """Does `function` in `source` call `callee`? Walked with `ast`.

    A text scan would find the name in the docstring that explains why the call
    is there — the one place it is guaranteed to appear whether or not the call
    survived an edit. Same reason as `_handles`, one question over.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != function:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                name = getattr(inner.func, "id", "") or getattr(inner.func, "attr", "")
                if name == callee:
                    return True
    return False


def test_turn_residual_reaches_the_record() -> list[str]:
    """R-54: the count of earlier turns that held a substitute lands on
    `ArmRunV5`, not only on the triple row.

    `residual` is a per-observation line and reads the arm record; while the
    number lived on the triple alone, a substitute the customer read in turn 2
    and never in the final answer was counted by nothing at all — the run
    printed a clean `residual` for a conversation that showed a fake.
    """
    failures: list[str] = []
    case = _fixture_case()
    run = _gateway_run(case)
    laid = h.with_turn_residual(run, 2)
    if laid.turn_residual != 2:
        failures.append(f"на запись легло {laid.turn_residual} вместо 2")
    for field in ("reply_raw", "control_reply", "turn_replies", "call_turns", "request_count",
                  "stream_mismatch", "reply_whole"):
        if getattr(laid, field) != getattr(run, field):
            failures.append(f"проставление нераскрытых подмен изменило {field}")
    if laid.base is not run.base:
        failures.append("проставление нераскрытых подмен подменило запись v4")
    # It SURVIVES THE FILE, or the metric reads a zero the run never wrote.
    restored = r.arm_v5_from_record(r.arm_v5_record(laid, _meta(), case.base))
    if restored.turn_residual != 2:
        failures.append(f"в файле нераскрытых подмен {restored.turn_residual}, а было 2")
    # The NEGATIVE: an honest run keeps its zero, so «2» above reads the value
    # and not the presence of a field.
    if r.arm_v5_from_record(r.arm_v5_record(run, _meta(), case.base)).turn_residual != 0:
        failures.append("честный прогон приехал в файл с ненулевым счётчиком")
    # A count cannot be negative, and a writer bug is refused by name rather
    # than written into a record the report would have to argue with.
    try:
        h.with_turn_residual(run, -1)
        failures.append("отрицательное число нераскрытых подмен приняли молча")
    except HarnessError:
        pass
    # And `run_triple_v5` is what lays it on: the number is known only after
    # the judge prompt is built, three arms in, and a live model is the only
    # way to reach that line for real.
    here = Path(__file__).resolve().parent
    if not _calls(here / "harness.py", "run_triple_v5", "with_turn_residual"):
        failures.append("run_triple_v5 не проставляет нераскрытые подмены на запись плеча I")
    with tempfile.TemporaryDirectory() as tmp:
        naked = Path(tmp) / "naked.py"
        naked.write_text("def run_triple_v5() -> None:\n"
                         "    \"\"\"with_turn_residual\"\"\"\n    pass\n", encoding="utf-8")
        if _calls(naked, "run_triple_v5", "with_turn_residual"):
            failures.append("обход ast принял упоминание в строке документации за вызов")
    return failures


def test_the_triple_carries_both_totals() -> list[str]:
    """R-54: `judge_cost_usd` and `turn_residual` are written by records' own
    writer and read back by its reader — never `row.get(key) or 0`.

    One place computes the judge's share (`triple_totals`), and both readers
    take it from there: the column the report prints and the `cost_usd` that
    bounds a resumed run. Two expressions over one verdict is how a rounding
    of one and not the other becomes a ceiling nobody can reconcile.
    """
    failures: list[str] = []
    judged = JudgeRow(case_id="c-0001", repeat=0, input_sha256="0" * 64,
                      verdict=JudgeVerdict(label="верно", reason="цитата: «Нашёл»",
                                           judged_by="model", cost_usd=0.02))
    totals = h.triple_totals(judged, 1)
    if totals.judge_cost_usd != 0.02 or totals.turn_residual != 1:
        failures.append(f"итоги тройки посчитаны как {totals}")
    read = r.triple_totals_from_json(r.triple_totals_to_json(totals))
    if read != totals:
        failures.append(f"итоги тройки не пережили запись и чтение: {read} != {totals}")
    # The NEGATIVE the field exists for: no judge is a MEASURED zero, and a row
    # that simply lacks the key is refused rather than read as a free judge.
    if h.triple_totals(None, 0).judge_cost_usd != 0.0:
        failures.append("тройка без вердикта насчитала судье расход")
    try:
        r.triple_totals_from_json({"turn_residual": 0})
        failures.append("строку без judge_cost_usd прочитали как бесплатного судью")
    except r.RecordError:
        pass
    return failures


def test_the_answer_leg_keeps_the_whole_restoration() -> list[str]:
    """R-54, the half that is engine-free: an ORDINARY case has one
    restoration, and `reply_whole` stays empty.

    The streaming half — where the two restorations really differ and the
    record must keep both — needs the engine and lives in
    `test_harness_stream`; here the point is that a non-streaming case does
    not put its answer on disk twice, which is what invites a reader to
    compare a field with itself.
    """
    failures: list[str] = []
    leg = h.answer_leg(f"Нашёл {SUBSTITUTE}.", False, None,  # type: ignore[arg-type]
                       lambda text: text.replace(SUBSTITUTE, REAL_NAME))
    if leg.reply != f"Нашёл {REAL_NAME}.":
        failures.append(f"обычный случай восстановлен не целиком: {leg.reply!r}")
    if leg.reply_whole != "" or leg.mismatch:
        failures.append(f"обычный случай записал вторую копию ответа: {leg!r}")
    silent = h.answer_leg("", False, None,  # type: ignore[arg-type]
                          lambda text: text.replace(SUBSTITUTE, REAL_NAME))
    if silent != h.AnswerLeg(reply="", reply_whole="", mismatch=False):
        failures.append(f"молчавший агент получил ответ: {silent!r}")
    # The NEGATIVE: the restorer must actually have been called, or «восстановлено»
    # above would hold for a leg that returned the raw text.
    if leg.reply == f"Нашёл {SUBSTITUTE}.":
        failures.append("ответ уехал с подменой — восстановитель не звали")
    return failures


# --- G3.5 / G3.7: the run survives its own ceiling, and one directory holds one run ---

class _RefusingLedger:
    """A ledger with no room left: `reserve` raises, `settle` still books.

    A class because a ledger is a connector to state the run shares, and this
    is the smallest one that can say «нет» — the real `SpendLedger` would need
    a file and a ceiling arranged so that three arms fit and the judge does not,
    which is an arrangement the test would then be about.
    """

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.settled: list[str] = []

    async def reserve(self, cap_usd: float) -> None:
        raise self._error

    async def settle(self, label: str, cap_usd: float, actual_usd: float) -> float:
        self.settled.append(label)
        return 0.0


class _Minted:
    """The only thing `judge_triple` asks a gateway for: what it minted.

    `GatewayV5` itself imports the engine, and this module may not
    (`test_only_harness_imports_pseudex`), so the seam is taken at the one
    method — `harness.minted_substitutes` calls `substitutes()` and nothing
    else.
    """

    def __init__(self, values: tuple[str, ...]) -> None:
        self._values = values

    def substitutes(self) -> tuple[str, ...]:
        return self._values


def _run_with_an_earlier_turn(case: CaseV5) -> ArmRunV5:
    """A run whose INTERMEDIATE turn still carries the substitute, so
    `turn_residual` is 1 and can be shown to survive the budget refusal."""
    run = _gateway_run(case)
    return ArmRunV5(**{**run.__dict__,
                       "turn_replies": (f"Секунду, смотрю карточку {SUBSTITUTE}.",
                                        f"Нашёл {REAL_NAME}.")})


def _call_lines(function: Callable[..., object], name: str) -> list[int]:
    """The lines of `function`'s own source where `name(...)` is called."""
    tree = ast.parse(inspect.getsource(function).lstrip())
    return sorted(node.lineno for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id == name)


def _guarded_by(function: Callable[..., object], name: str) -> list[str]:
    """The conditions a call of `name` inside `function` hangs off.

    An `if`/`else` EXPRESSION around the call and an `if` STATEMENT containing
    it are the two ways to make a guard fire on one path only, and the defect
    this reads for was the first of them (`foreign_run_ids(...) if args.resume
    else ()`). Read off the source rather than by driving `main`, which needs a
    corpus, a ladder and a model — the same reason `_call_lines` exists.
    """
    def calls(node: ast.AST) -> bool:
        return any(isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
                   and inner.func.id == name for inner in ast.walk(node))

    tree = ast.parse(inspect.getsource(function).lstrip())
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.IfExp) and calls(node):
            out.append(ast.unparse(node.test))
        elif isinstance(node, ast.If) and any(calls(one) for one in node.body):
            out.append(ast.unparse(node.test))
    return out


def test_a_refused_judge_budget_never_kills_the_triple() -> list[str]:
    """G3.5: the judge reserves from the SAME ledger as the arms, and the
    refusal used to escape every handler on the way out.

    `judge._ask` reserves AFTER C, I and C′ have finished and been charged;
    `BudgetExhausted` travelled out of `judge_prompt`, out of `judge_triple`,
    past `run_triple_v5` (whose handlers are the OUTER reservation and
    `LeakedPrompt`) and out of `drive_v5`, which has none — three paid arms
    unrecorded and the whole run dead. The verdict is now `judged_by="none"`,
    which counts nowhere, and the triple row says WHY.

    NO MODEL IS REACHED IN EITHER DIRECTION: the refusal happens at the
    reservation, before the transport is touched, which is also why the
    negative below uses a different exception rather than a granting ledger.
    """
    failures: list[str] = []
    case = _fixture_case()
    run = _run_with_an_earlier_turn(case)
    gateway = _Minted((SUBSTITUTE,))
    config = JudgeConfig(model="claude-sonnet-5", trace_path=None,
                         ledger=_RefusingLedger(v3_judge.BudgetExhausted("потолок $0.00 исчерпан")),
                         query_cap_usd=QUERY_CAP_USD, retries=RETRIES,
                         temperature=JUDGE_TEMPERATURE)
    try:
        outcome = asyncio.run(h.judge_triple(case, run, gateway, config))  # type: ignore[arg-type]
    except v3_judge.BudgetExhausted as escaped:
        # REPORTED, NEVER RE-RAISED: an escape here is the defect itself, and
        # letting it out of the check would kill the suite the way it killed the
        # run — the remaining checks would never say anything.
        return [f"отказ потолка вышел из judge_triple и снова убьёт прогон: {escaped}"]
    if outcome.row.verdict.judged_by != "none" or outcome.row.verdict.label != "":
        failures.append(f"отказ потолка дал счётный вердикт: {outcome.row.verdict}")
    if h.JUDGE_SKIPPED_BUDGET not in outcome.row.verdict.reason:
        failures.append(f"причина не называет потолок: {outcome.row.verdict.reason!r}")
    if outcome.row.verdict.cost_usd != 0.0:
        failures.append("несостоявшийся вызов судьи чего-то стоил")
    if not outcome.row.input_sha256:
        failures.append("отказ потолка унёс хэш промпта — переджудить нечем")
    if outcome.turn_residual != 1:
        failures.append(f"отказ потолка унёс счётчик ходов: {outcome.turn_residual}")
    summary = h.judge_summary(outcome.row.verdict)
    if h.JUDGE_SKIPPED_BUDGET not in str(summary.get("reason")):
        failures.append(f"строка тройки не говорит, почему судьи не было: {summary}")
    if set(summary) != {"label", "judged_by", "cost_usd", "reason"}:
        failures.append(f"строка тройки сменила форму: {sorted(summary)}")
    # THE NEGATIVE: the catch is for a ceiling, not for everything. A ledger
    # that fails for any other reason must still stop the run — `BudgetExhausted`
    # IS a `RuntimeError`, so a lazy `except RuntimeError` would pass silently.
    broken = JudgeConfig(model="claude-sonnet-5", trace_path=None,
                         ledger=_RefusingLedger(RuntimeError("журнал трат не открылся")),
                         query_cap_usd=QUERY_CAP_USD, retries=RETRIES,
                         temperature=JUDGE_TEMPERATURE)
    try:
        asyncio.run(h.judge_triple(case, run, gateway, broken))  # type: ignore[arg-type]
        failures.append("поломка журнала трат проглочена как отказ потолка")
    except RuntimeError as failure:
        if isinstance(failure, v3_judge.BudgetExhausted):
            failures.append("негатив поднял тот же самый отказ — проверка ни о чём")
    return failures


def test_a_resume_refuses_a_shared_run_directory() -> list[str]:
    """G3.7: two run ids in one directory, and every reader takes the first.

    `report.run_id_of` and `calibration._run_id` both pick
    `sorted(glob("*.arms.jsonl"))[0]`, while `records.merged_v5_records` globs
    EVERY file — so a `--resume` that wrote a fresh uuid into the resumed
    directory (the default `--out` is the same path) left the new run's hops,
    judge file and meta read by nothing and its arm rows merged in as hopless.
    """
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "v5-live-nano"
        if h.foreign_run_ids(run_dir, RUN_ID) != ():
            failures.append("несуществующий каталог объявлен занятым")
        run_dir.mkdir(parents=True)
        if h.foreign_run_ids(run_dir, RUN_ID) != ():
            failures.append("пустой каталог объявлен занятым")
        (run_dir / f"{RUN_ID}.arms.jsonl").write_text("{}\n", encoding="utf-8")
        if h.foreign_run_ids(run_dir, RUN_ID) != ():
            failures.append("собственный прогон прочитан как чужой")
        (run_dir / "0000-older.arms.jsonl").write_text("{}\n", encoding="utf-8")
        found = h.foreign_run_ids(run_dir, RUN_ID)
        if found != ("0000-older",):
            failures.append(f"чужой прогон в каталоге не найден: {found}")
    # The refusal must happen BEFORE `write_corpus`, which overwrites the
    # resumed run's own snapshot of the corpus — the file `--report` replays
    # against. Read off `main`'s own source, because driving `main` needs a
    # corpus, a ladder and a model.
    guard = _call_lines(h.main, "foreign_run_ids")
    snapshot = _call_lines(h.main, "write_corpus")
    if not guard:
        failures.append("main не спрашивает про чужой прогон вообще")
    elif not snapshot:
        failures.append("в main нет записи снимка корпуса — сравнивать не с чем")
    elif guard[0] > snapshot[0]:
        failures.append(f"проверка каталога ({guard[0]}) стоит после снимка корпуса "
                        f"({snapshot[0]}) — снимок продолжаемого прогона уже перезаписан")
    # ON EVERY RUN, NOT ONLY ON `--resume`. The default `--out` is
    # `runs/<today>/v5-live-<tier>` for any run of that tier on that day, so two
    # ORDINARY runs share it without either saying `--resume` — and the guard
    # used to be `foreign_run_ids(out, run_id) if args.resume else ()`, which
    # fires on the path the defect was found on rather than on the path it
    # lives on. Reproduced with the reviewer's own script (`g37_repro.py`):
    # «main's guard on a NON-resume run sees: () -> refuses? False».
    conditions = _guarded_by(h.main, "foreign_run_ids")
    if conditions:
        failures.append(f"проверка каталога висит на условии {conditions} — "
                        f"обычный прогон в тот же каталог её не увидит")
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
        ("turn_residual_reaches_the_record", test_turn_residual_reaches_the_record),
        ("the_triple_carries_both_totals", test_the_triple_carries_both_totals),
        ("the_answer_leg_keeps_the_whole_restoration",
         test_the_answer_leg_keeps_the_whole_restoration),
        ("a_refused_judge_budget_never_kills_the_triple",
         test_a_refused_judge_budget_never_kills_the_triple),
        ("a_resume_refuses_a_shared_run_directory",
         test_a_resume_refuses_a_shared_run_directory),
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
