"""`judge.py` pinned: blind by construction, four questions, no form, a quote or nothing.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_judge

Offline: no model, no key, no money. Every check is shown to FAIL on a negative
fixture as well as to pass on a good one — a blindness guard that has never
refused a prompt is a comment, and the whole point of this module is that the
guard runs on the paid path.
"""
import hashlib
import sys
from collections.abc import Callable

from bench.agentpii4.compare import ArmRun
from bench.agentpii4.schema import (Case, Expectation, Locus, Message, PiiItem, Provenance,
                                    SeedRecord)
from bench.agentpii5 import judge
from bench.agentpii5.contracts import (
    JUDGE_LABELS, ArmRunV5, CaseV5, DialogueTurn, JudgeInput, ToolResultRecord)

SUBSTITUTE: str = "Пахомова Ольга"
REAL: str = "Иванова Елена"


def _request(answer: str, dialogue: tuple[DialogueTurn, ...]) -> JudgeInput:
    return JudgeInput(case_id="c-0001", restored_answer=answer,
                      oracle_literals=(REAL, "+7 916 402-11-87"),
                      dialogue_context=dialogue,
                      customer_question="когда приедет курьер")


def _two_turn_case() -> CaseV5:
    """Two user turns, so «the agent's earlier words» is a thing that exists."""
    messages = (
        Message(role="system", content="ты оператор", source=None, name=""),
        Message(role="user", content=f"это {REAL}", source=None, name=""),
        Message(role="user", content="а когда приедет курьер", source=None, name=""))
    base = Case(
        id="c-0001", kind="long_support", register="chat",
        provenance=Provenance(kind="authored", corpus="authored", key="", shape="",
                              selection="census", weight=1.0, licence="authored"),
        cluster="NAME:иванова елена", conversation_id="c-0001", now="2026-09-01",
        messages=messages, tools=("crm_find_contact",),
        seed_records=(SeedRecord(id="s1", table="contacts", fields={}, pii_ids=()),),
        pii=(PiiItem(id="p1", type="NAME", identity="i1", value=REAL, canonical=REAL,
                     parts={}, where=Locus(kind="message", msg=1, start=5, end=5 + len(REAL),
                                           record="", path=""),
                     duty="required", spoken=False, stale=False),),
        plain=(), negatives=(),
        expects=Expectation(reachable_tools=("crm_find_contact",), primary_identity="i1",
                            must_contain=(), must_not_contain=(), validate_types=()),
        trace=(), note="фикстура судьи")
    return CaseV5(base=base, behaviour="memory_anaphora", hops=(), returns=(), forced=(),
                  memory=(), pick=None, branch=None, loop=None, rag=None, document=None,
                  has_result=True, streaming=False, revised_from_v4=False)


def _run_with_turns(turn_replies: tuple[str, ...]) -> ArmRunV5:
    base = ArmRun(case_id="c-0001", arm="I", repeat=0, calls=(), state=(),
                  reply="Курьер приедет к Ивановой Елене в 14:00.", termination="done",
                  cost_usd=0.0, substitutes={"p1": (SUBSTITUTE, {})}, masked_spans={})
    result = ToolResultRecord(tool_name="crm_find_contact", seq=1, call_ordinal=0, turn=1,
                              return_form="single", text_real=f"клиент: {REAL}",
                              text_masked=f"клиент: {SUBSTITUTE}", spans_real={"p1": (8, 8 + len(REAL))},
                              pieces=(), forced=False)
    return ArmRunV5(base=base, reply_raw=f"Курьер приедет к {SUBSTITUTE}.",
                    control_reply="", tool_results=(result,), mentions=(),
                    turn_replies=turn_replies, call_turns=(1,), request_count=2,
                    stream_mismatch=False)


def test_dialogue_carries_the_agents_turns() -> list[str]:
    """Ruling R-40: question 4 asks whether the answer took the dialogue into
    account, and on an anaphoric case («ему», «на тот адрес») it was the AGENT
    that established what the pronoun points at. Judging that against the user's
    messages alone asked about context the judge was never shown."""
    failures: list[str] = []
    case = _two_turn_case()
    spoken = f"Нашёл карточку: {REAL}."
    final = "Курьер приедет к Ивановой Елене в 14:00."
    turns = judge.dialogue_context(case, _run_with_turns((spoken, final)))
    roles = tuple(turn.role for turn in turns)
    if roles != ("user", "tool", "assistant", "user"):
        failures.append(f"порядок реплик не тот: {roles}")
    if not any(turn.role == "assistant" and turn.text == spoken for turn in turns):
        failures.append("реплика агента из первого хода не попала в диалог")
    # The final answer is the EVIDENCE and has its own section; quoting it in
    # the dialogue too would show the judge the thing it is judging twice.
    if any(turn.text == final for turn in turns):
        failures.append("финальный ответ попал и в диалог, и в доказательство")
    # The NEGATIVE: without the field there are no assistant turns at all, so
    # the check above reads the record rather than something always true.
    bare = judge.dialogue_context(case, _run_with_turns(()))
    if any(turn.role == "assistant" for turn in bare):
        failures.append("реплики агента взялись не из turn_replies")
    if tuple(turn.role for turn in bare) != ("user", "tool", "user"):
        failures.append(f"без turn_replies диалог изменился: {[t.role for t in bare]}")
    return failures


def test_agents_turns_are_restored() -> list[str]:
    """`turn_replies` is the RESTORED reply per turn. A harness that stored the
    raw one would put a substitute in front of a judge the whole module is
    built to keep blind — so the blindness guard must refuse that prompt."""
    case = _two_turn_case()
    raw = judge.judge_input(case, _run_with_turns((f"Нашёл карточку: {SUBSTITUTE}.", "готово")))
    try:
        judge.build_prompt(raw, (SUBSTITUTE,))
    except judge.OracleLeak as refused:
        return [] if SUBSTITUTE in str(refused) else [f"OracleLeak не называет подмену: {refused}"]
    return ["промпт с подменой в реплике агента собрался"]


def test_no_pseudex() -> list[str]:
    loaded = sorted(name for name in sys.modules if name.startswith("pseudex"))
    return [] if not loaded else [f"судья потянул движок: {loaded}"]


def test_input_is_blind() -> list[str]:
    failures: list[str] = []
    named = [name for name in JudgeInput.__dataclass_fields__ if "substitut" in name.casefold()
             or "подмен" in name.casefold() or "fake" in name.casefold()]
    if named:
        failures.append(f"у JudgeInput есть поле для подмен: {named}")
    # The POSITIVE: an honest prompt is built.
    clean = _request("Курьер приедет к Ивановой Елене в 14:00.",
                     (DialogueTurn(role="user", text=f"это {REAL}"),))
    prompt = judge.build_prompt(clean, (SUBSTITUTE,))
    for heading in judge.HEADINGS:
        if heading not in prompt:
            failures.append(f"в промпте нет раздела «{heading}»")
    # The NEGATIVE: the harness left a substitute in the dialogue it restored.
    leaked = _request("Курьер приедет.", (DialogueTurn(role="tool", text=f"клиент: {SUBSTITUTE}"),))
    try:
        judge.build_prompt(leaked, (SUBSTITUTE,))
        failures.append("build_prompt собрал промпт с подменой в диалоге")
    except judge.OracleLeak as refused:
        if SUBSTITUTE not in str(refused):
            failures.append(f"OracleLeak не называет подмену: {refused}")
    # And the same leak in the oracle list, which is the likelier slip: a
    # caller that passed the MASKED values as the oracle.
    faked = JudgeInput(case_id="c-0001", restored_answer="ok", oracle_literals=(SUBSTITUTE,),
                       dialogue_context=(), customer_question="?")
    try:
        judge.build_prompt(faked, (SUBSTITUTE,))
        failures.append("build_prompt принял подмену в списке оракула")
    except judge.OracleLeak:
        pass
    return failures


def test_rubric_names_four_questions() -> list[str]:
    failures: list[str] = []
    if len(judge.RUBRIC_QUESTIONS) != 4:
        failures.append(f"вопросов не четыре, а {len(judge.RUBRIC_QUESTIONS)}")
    prompt = judge.build_prompt(_request("ответ", ()), ())
    for question in judge.RUBRIC_QUESTIONS:
        if question not in judge.RUBRIC:
            failures.append(f"вопрос не попал в рубрику: {question[:40]!r}")
    for label in JUDGE_LABELS:
        if label not in judge.RUBRIC:
            failures.append(f"метка {label!r} не объяснена в рубрике")
    if "quote" not in judge.RUBRIC:
        failures.append("рубрика не требует цитаты")
    if judge.ANSWER_HEADING not in prompt:
        failures.append("в промпте нет раздела с ответом агента")
    return failures


def test_rubric_has_no_form_rules() -> list[str]:
    """The words the comparator owns. Checked over the whole prompt, not the
    rubric alone: a heading naming form would steer the judge just as well."""
    failures: list[str] = []
    prompt = judge.build_prompt(_request("ответ", ()), ()).casefold()
    for word in ("падеж", "регистр", "формат", "форма"):
        if word in prompt:
            failures.append(f"промпт судьи называет форму: {word!r}")
    # The negative: the guard is a real check, so a rubric that DID name form
    # must be caught by the same test the module runs at import.
    if not any(word in "проверь падеж и формат" for word in ("падеж", "формат")):
        failures.append("проверка слов сама не ловит пример со словами формы")
    return failures


def test_residual_pregate_short_circuits() -> list[str]:
    failures: list[str] = []
    fired = judge.residual_pregate_of(f"Записал на {SUBSTITUTE}.", (SUBSTITUTE,), ())
    if fired is None or fired.label != "неверно" or fired.judged_by != "residual_gate":
        failures.append(f"целая подмена в ответе не остановила судью: {fired}")
    if fired is not None and fired.cost_usd != 0.0:
        failures.append("претгейт потратил деньги")
    piece = judge.residual_pregate_of("Курьер приедет к Пахомова в 14:00.", (SUBSTITUTE,), ())
    if piece is None or piece.judged_by != "residual_gate":
        failures.append("часть подмены (фамилия) в ответе не остановила судью")
    # The real value alone is the product WORKING: the customer reads their own
    # name back, and a gate that fired here would report every honest reply.
    if judge.residual_pregate_of(f"Курьер приедет к {REAL}.", (SUBSTITUTE,), ()) is not None:
        failures.append("претгейт сработал на настоящем значении клиента")
    # A piece that is ALSO a real part of the customer's value: the vault mints
    # «Иванова Дарья» for «Иванова Елена» and the surname is the customer's own.
    shared = judge.residual_pregate_of(f"Курьер приедет к {REAL}.", ("Иванова Дарья",),
                                       ("Иванова", "Елена"))
    if shared is not None:
        failures.append(f"претгейт посчитал своей настоящую часть клиента: {shared.reason}")
    # …and without the real parts the SAME answer fires, which proves the third
    # argument does something rather than decorating the signature.
    if judge.residual_pregate_of(f"Курьер приедет к {REAL}.", ("Иванова Дарья",), ()) is None:
        failures.append("без списка настоящих частей претгейт ничего не заметил — "
                        "значит и с ним он ничего не делает")
    if judge.residual_pregate("чистый ответ", (SUBSTITUTE,)) is not None:
        failures.append("адаптер протокола сработал на ответе без подмены")
    return failures


def test_quote_must_stand() -> list[str]:
    answer = "Курьер приедет к Ивановой Елене в 14:00."
    failures: list[str] = []
    good = judge.parse_verdict({"label": "верно", "quote": "приедет к Ивановой Елене",
                                "reason": "запись та же"}, answer, 0.01)
    if good is None or good.label != "верно" or good.judged_by != "model":
        failures.append(f"вердикт с настоящей цитатой отвергнут: {good}")
    invented = judge.parse_verdict({"label": "неверно", "quote": "приедет к Петровой Анне",
                                    "reason": "другая запись"}, answer, 0.01)
    if invented is not None:
        failures.append("вердикт с выдуманной цитатой засчитан")
    unknown = judge.parse_verdict({"label": "ок", "quote": "приедет к Ивановой Елене",
                                   "reason": ""}, answer, 0.01)
    if unknown is not None:
        failures.append("вердикт с меткой вне JUDGE_LABELS засчитан")
    empty = judge.parse_verdict({"label": "верно", "quote": "  ", "reason": ""}, answer, 0.01)
    if empty is not None:
        failures.append("вердикт с пустой цитатой засчитан")
    # Case and whitespace are forgiven and nothing else is (v3's rule).
    lax = judge.parse_verdict({"label": "верно", "quote": "ПРИЕДЕТ   К  ивановой Елене",
                               "reason": ""}, answer, 0.0)
    if lax is None:
        failures.append("цитата, отличающаяся регистром и пробелами, отвергнута")
    return failures


def test_prompt_sha_changes_with_rubric() -> list[str]:
    failures: list[str] = []
    material = judge.RUBRIC + "\n" + "\n".join(judge.HEADINGS)
    if judge.prompt_sha256() != hashlib.sha256(material.encode("utf-8")).hexdigest():
        failures.append("prompt_sha256 считается не по рубрике и заголовкам")
    moved = hashlib.sha256((material + " и ещё одна полезная строка").encode("utf-8")).hexdigest()
    if moved == judge.prompt_sha256():
        failures.append("правка рубрики не меняет хэш — калибровка не устареет никогда")
    # The per-case sections must NOT move it, or every answer would invalidate
    # the calibration of the run it belongs to.
    one = judge.build_prompt(_request("а", ()), ())
    other = judge.build_prompt(_request("б", ()), ())
    if one == other:
        failures.append("промпт не зависит от ответа — судить нечего")
    return failures


def test_judged_by_none_carries_no_label() -> list[str]:
    """Ruling R-03: `judged_by == "none"` ⇔ `label == ""`. A reader refuses any
    other combination, so a writer that produced one would break a replay."""
    failures: list[str] = []
    verdict = judge.parse_verdict({"label": "верно", "quote": "нет такого", "reason": ""},
                                  "ответ", 0.0)
    if verdict is not None:
        failures.append("несчётный вердикт вернулся с меткой вместо None")
    return failures


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("input_is_blind", test_input_is_blind),
        ("rubric_names_four_questions", test_rubric_names_four_questions),
        ("rubric_has_no_form_rules", test_rubric_has_no_form_rules),
        ("residual_pregate_short_circuits", test_residual_pregate_short_circuits),
        ("quote_must_stand", test_quote_must_stand),
        ("prompt_sha_changes_with_rubric", test_prompt_sha_changes_with_rubric),
        ("judged_by_none_carries_no_label", test_judged_by_none_carries_no_label),
        ("dialogue_carries_the_agents_turns", test_dialogue_carries_the_agents_turns),
        ("agents_turns_are_restored", test_agents_turns_are_restored),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("judge: PASS" if not failures else "judge: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
