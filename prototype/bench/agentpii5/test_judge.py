"""`judge.py` pinned: blind by construction, four questions, no form, a quote or nothing.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_judge

Offline: no model, no key, no money. Every check is shown to FAIL on a negative
fixture as well as to pass on a good one — a blindness guard that has never
refused a prompt is a comment, and the whole point of this module is that the
guard runs on the paid path.
"""
import ast
import hashlib
import inspect
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii4.compare import ArmRun
from bench.agentpii4.parts import parts_of
from bench.agentpii4.schema import (Case, Expectation, Locus, Message, PiiItem, Provenance,
                                    SeedRecord)
from bench.agentpii5 import judge, observe
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
                  has_result=True, streaming=False, revised_from_v4=False, v6=None)


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
                    stream_mismatch=False, reply_whole="", turn_residual=0)


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
    """`turn_replies` is the RESTORED reply per turn — and a substitute the
    restorer LEFT STANDING there is measured, not fatal (F3.2).

    The engine does not restore a lower-cased substitute, which is the form it
    mints for the corpus's chat / sloppy / voice registers, so «the agent
    restated a value in the register it read it in» is the common case and not
    an edge one: 62 of 66 multi-turn cases in the reviewer's sample. Raising
    there discarded three paid arms, killed `drive_v5` before a single row was
    written and made `--resume` re-pay for the same leak for ever.
    """
    failures: list[str] = []
    case = _two_turn_case()
    raw = judge.judge_input(case, _run_with_turns((f"Нашёл карточку: {SUBSTITUTE}.", "готово")))
    # THE REPRODUCTION (reviewers' f2_oracleleak.py / f2e_endtoend.py, half B):
    # this call used to raise OracleLeak.
    try:
        prompt = judge.build_prompt(raw, (SUBSTITUTE,))
    except judge.OracleLeak as refused:
        return [f"подмена в реплике агента убила сборку промпта: {refused}"]
    if SUBSTITUTE.casefold() in prompt.casefold():
        failures.append("подмена из реплики агента доехала до судьи")
    if judge.RESIDUAL_MARKER not in prompt:
        failures.append("подмену вырезали, но маркер на её место не поставили — "
                        "предложение изменилось молча")
    _, flagged = judge.masked_dialogue(raw, (SUBSTITUTE,))
    if flagged != 1:
        failures.append(f"ходов с нераскрытой подменой насчитано {flagged}, а он один")
    # The lower-cased form the engine really leaves standing, and the surname
    # alone: both are the same defect and both must be caught.
    for written in (SUBSTITUTE.casefold(), SUBSTITUTE.split()[0]):
        one = judge.judge_input(case, _run_with_turns((f"передал {written} в доставку.", "готово")))
        text = judge.build_prompt(one, (SUBSTITUTE,))
        if written.casefold() in text.casefold():
            failures.append(f"подмена в написании {written!r} доехала до судьи")
    # The NEGATIVE: a turn that carries NO substitute is not touched, or the
    # masking would eat the context question 4 is asked about.
    honest = judge.judge_input(case, _run_with_turns((f"Нашёл карточку: {REAL}.", "готово")))
    clean, untouched = judge.masked_dialogue(honest, (SUBSTITUTE,))
    if untouched != 0:
        failures.append(f"честный ход посчитан за подменённый: {[t.text for t in clean]}")
    if not any(REAL in turn.text for turn in clean):
        failures.append("настоящее значение клиента вырезано из диалога")
    return failures


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
    # The DIALOGUE is masked rather than refused (F3.2) — but the substitute
    # must be gone from the prompt either way, and that is what is asserted.
    leaked = _request("Курьер приедет.", (DialogueTurn(role="tool", text=f"клиент: {SUBSTITUTE}"),))
    try:
        served = judge.build_prompt(leaked, (SUBSTITUTE,))
    except judge.OracleLeak as refused:
        # Reported, not raised: a check that dies takes the other nine with it,
        # and this is the exact failure F3.2 closed.
        failures.append(f"подмена в диалоге снова роняет сборку промпта: {refused}")
        served = ""
    if SUBSTITUTE.casefold() in served.casefold():
        failures.append("подмена из диалога доехала до судьи")
    # …and a substitute split across a line break is the same leak: the guard
    # compares under collapsed whitespace, so the mask must too.
    wrapped = _request("Курьер приедет.",
                       (DialogueTurn(role="tool", text="клиент: Пахомова\nОльга"),))
    try:
        if "Пахомова" in judge.build_prompt(wrapped, (SUBSTITUTE,)):
            failures.append("подмена, перенесённая по строкам, доехала до судьи")
    except judge.OracleLeak as refused:
        failures.append(f"перенос по строкам не замаскирован, а уронил сборку: {refused}")
    # A leak in the QUESTION is still a hard error: the customer's own message
    # cannot legitimately carry something we minted, so it is ours.
    asked = JudgeInput(case_id="c-0001", restored_answer="ok", oracle_literals=(REAL,),
                       dialogue_context=(), customer_question=f"где {SUBSTITUTE}?")
    try:
        judge.build_prompt(asked, (SUBSTITUTE,))
        failures.append("build_prompt принял подмену в вопросе клиента")
    except judge.OracleLeak:
        pass
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
    """The words the comparator owns, hunted by `form_words_in` — the same
    function the module runs at import (F3.6).

    The old test was four stems compared with `in`, and it was wrong in both
    directions: it missed «склонение», «написание», «орфография», «нотация» —
    the synonyms a helpful editor reaches for — and it fired on «инФОРМАция»,
    so an ordinary word could not be written in the rubric. The guard now
    matches at a WORD START and is run over the rubric MINUS its own «чего ты
    не судишь» clause, which is the one sentence allowed to name form because
    it forbids judging it.
    """
    failures: list[str] = []
    said = judge.form_words_in(judge.RUBRIC.replace(judge._NOT_JUDGED, "")
                               + " " + " ".join(judge.HEADINGS))
    if said:
        failures.append(f"рубрика судьи называет форму: {said}")
    # THE NEGATIVE, one sentence per synonym: the guard must go red on each.
    for sentence, expected in (("Проверь, в каком падеже написано имя.", "падеж"),
                               ("Учти склонение фамилии.", "склонен"),
                               ("Оцени написание адреса.", "написани"),
                               ("Смотри на орфографию.", "орфограф"),
                               ("Важна нотация даты.", "нотаци"),
                               ("Проверь формат телефона.", "формат"),
                               ("Сверь регистр букв.", "регистр"),
                               ("Форма записи должна совпасть.", "форма"),
                               ("Проверь транслитерацию.", "транслит")):
        if expected not in judge.form_words_in(sentence):
            failures.append(f"страж не увидел слово формы в {sentence!r}")
    # …and it must NOT fire on ordinary Russian that merely contains a stem:
    # «информация» carries «форма» and the flat substring test banned it.
    for allowed in ("информация о клиенте", "трансформация данных", "платформа доставки"):
        fired = judge.form_words_in(allowed)
        if fired:
            failures.append(f"страж сработал на обычном слове {allowed!r}: {fired}")
    # The clause that FORBIDS judging form still names it, or the rubric would
    # have stopped saying what it must say.
    if not judge.form_words_in(judge._NOT_JUDGED):
        failures.append("в «чего ты не судишь» больше нет ни одного слова о форме")
    if judge._NOT_JUDGED not in judge.RUBRIC:
        failures.append("рубрика больше не запрещает судить форму")
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


def _called_names(package: Path) -> set[str]:
    """Every identifier the package READS — `ast`, never a text scan.

    A grep would count the four docstrings that name `judge_with` and call the
    adapter reachable; a load is a load whether the caller imported the name or
    reached it through the module object.
    """
    out: set[str] = set()
    for path in sorted(package.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            if isinstance(node, ast.Name):
                out.add(node.id)
            elif isinstance(node, ast.Attribute):
                out.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                out.update(alias.name for alias in node.names)
    return out


def _unused_public(source: Path, package: Path) -> tuple[str, ...]:
    """Public functions of `source` that nothing in `package` ever reads.

    `main` is excluded: it is the CLI's entry and is named by `__main__`.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    public = [node.name for node in tree.body
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
              and not node.name.startswith("_") and node.name != "main"]
    read = _called_names(package)
    return tuple(name for name in public if name not in read)


def test_no_unreachable_adapters() -> list[str]:
    """F3.6: an adapter no caller spells is a docstring, not a seam.

    `pregate_with` and `judge_with` were both written, both documented as «what
    the harness uses», and both called from nothing — the exact shape CLAUDE.md
    records for `Case.negatives` and `FieldSpec.required`. The check is
    mechanical so the next one cannot be added quietly.
    """
    here = Path(__file__).resolve().parent
    failures: list[str] = []
    orphans = _unused_public(here / "judge.py", here)
    if orphans:
        failures.append(f"судья экспортирует то, что никто не зовёт: {orphans}")
    # The walk must be able to FIND one, or «ничего лишнего» is a statement
    # about the scanner.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "lonely.py").write_text("def used(): ...\n\n\ndef orphan(): ...\n", encoding="utf-8")
        (root / "caller.py").write_text("from lonely import used\nused()\n", encoding="utf-8")
        found = _unused_public(root / "lonely.py", root)
        if found != ("orphan",):
            failures.append(f"обход нашёл {found}, а должен был найти ровно ('orphan',)")
    return failures


def _judge_config_temperatures(source: Path) -> tuple[str, ...]:
    """How every `JudgeConfig(...)` call in `source` spells its temperature.

    Walked with `ast` and reported as SOURCE, not as a value: the claim is that
    the run and the K calibration repeats ask at ONE temperature, and two
    literals that happen to be equal today are two values tomorrow. A call with
    no `temperature` keyword is reported as `"<нет>"` rather than skipped —
    silence is the failure this check exists for.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    spellings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
        if name != "JudgeConfig":
            continue
        keyword = next((one for one in node.keywords if one.arg == "temperature"), None)
        spellings.append("<нет>" if keyword is None else ast.unparse(keyword.value))
    return tuple(spellings)


def test_one_temperature_for_run_and_repeats() -> list[str]:
    """R-56: the temperature is explicit, and the repeats ask at the run's.

    `calibration export --repeats K` is a SECOND PROCESS: it spends K−1 more
    judge calls whose spread becomes `repeat_disagreement`, the threshold that
    refuses an unstable judge. «The same temperature as the run» can therefore
    hold only through one shared constant — a flag is a value a human retypes,
    and a spread measured at another temperature describes another instrument.
    So both construction sites must name `JUDGE_TEMPERATURE` itself.
    """
    here = Path(__file__).resolve().parent
    failures: list[str] = []
    for name in ("harness.py", "calibration.py"):
        spellings = _judge_config_temperatures(here / name)
        if not spellings:
            failures.append(f"{name}: ни одного JudgeConfig — проверка смотрит не туда")
        for spelling in spellings:
            if "JUDGE_TEMPERATURE" not in spelling:
                failures.append(f"{name}: JudgeConfig(temperature={spelling}) — не общая "
                                f"константа, прогон и повторы разъедутся молча")
    # The walk must be able to say «нет», or «все зовут константу» is a
    # statement about the scanner.
    with tempfile.TemporaryDirectory() as tmp:
        naked = Path(tmp) / "naked.py"
        naked.write_text("JudgeConfig(model='m', temperature=0.0)\n"
                         "JudgeConfig(model='m')\n", encoding="utf-8")
        found = _judge_config_temperatures(naked)
        if found != ("0.0", "<нет>"):
            failures.append(f"обход прочитал температуры как {found}")
    return failures


def test_temperature_the_transport_cannot_deliver_is_refused() -> list[str]:
    """A temperature we cannot set is a temperature we must not accept.

    The judge is asked through the Claude Code CLI, which takes no temperature
    — neither a field of `ClaudeAgentOptions` nor a flag. Quietly building the
    options anyway would put a number in the calibration stamp that the model
    never ran at; the refusal names the transport instead.
    """
    failures: list[str] = []
    options = judge._options("claude-sonnet-5", 0.05, judge.JUDGE_TEMPERATURE)
    if options.model != "claude-sonnet-5" or options.max_budget_usd != 0.05:
        failures.append("сессия судьи собрана не с моделью и потолком вызова")
    if any(field == "temperature" for field in options.__dataclass_fields__):
        failures.append("у ClaudeAgentOptions появилось поле temperature — отказ ниже "
                        "больше не нужен, температуру надо ПЕРЕДАВАТЬ")
    try:
        judge._options("claude-sonnet-5", 0.05, 0.0)
        failures.append("температуру, которой транспорт не умеет, приняли молча")
    except judge.TransportError as refused:
        if "0.0" not in str(refused) or "CLI" not in str(refused):
            failures.append(f"отказ не называет ни запрошенную температуру, ни транспорт: {refused}")
    return failures


def test_prompt_hashes_what_was_sent() -> list[str]:
    """`judge_prompt` takes the prompt the caller built, so the hash on disk is
    of the string the model was actually given (F3.2).

    Building it twice — once to ask, once to hash — is two strings that can
    drift, and the second build used to raise `OracleLeak` for a case the
    pre-gate had already decided: the run died over a judge call it was never
    going to make.
    """
    failures: list[str] = []
    request = _request("Курьер приедет к Ивановой Елене в 14:00.",
                       (DialogueTurn(role="user", text=f"это {REAL}"),))
    built = judge.build_prompt(request, (SUBSTITUTE,))
    if judge.build_prompt(request, (SUBSTITUTE,)) != built:
        failures.append("две сборки одного промпта дали разный текст — хэш ничего не пинит")
    signature = inspect.signature(judge.judge_prompt).parameters
    if "prompt" not in signature:
        failures.append(f"judge_prompt не принимает готовый промпт: {list(signature)}")
    if "substitutes_minted" not in inspect.signature(judge.judge_answer).parameters:
        failures.append("judge_answer больше не получает список подмен — страж слеп")
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


# --- G3.2 / G3.3: what the piece hunt must NOT call ours ------------------------------

# The customer's own address, as the corpus writes one, and the substitute the
# engine mints for it: same city, same generic word, different street. Taken
# from `chain-000` / `lookup_list-012` of the real corpus rather than invented,
# because the shape of the collision (a two-word city, a marker-less generic) is
# what the old whole-part comparison could not subtract.
REAL_ADDRESS: str = "нижний новгород переулок барышникова 7кв111"
MINTED_ADDRESS: str = "нижний новгород переулок озёрный 3кв62"
# A DOB dictated aloud. `parts_of` splits it as a street («декабря») and as a
# name («двадцать» / «третьего»), which is how a month name entered the hunt.
MINTED_SPOKEN_DOB: str = "двадцать третьего декабря восемьдесят второго года"


def _needle_texts(surface: str) -> tuple[str, ...]:
    """What the gate looks for, as bare strings — the shape a check can read."""
    return tuple(sorted(needle.text for needle in judge.substitute_needles(surface)))


# ONE MINTED SURFACE PER TYPE THE CORPUS DECLARES, and an answer carrying it in
# a shape a model actually writes: declined, renotated, respaced, refolded,
# transliterated, without its city. The gate must refuse every row, because
# `residual` counts every row a critical defect — and the two asking different
# questions is what let the judge be PAID to read our own fake as the
# customer's value (§5, §8.5).
REWRITTEN: tuple[tuple[str, str, str], ...] = (
    ("NAME", "Пахомова Ольга", "Готово, передал Пахомовой Ольге."),
    ("LOC", "орёл проспект рябиновый 100 кв 102", "Курьер приедет: проспект рябиновый 100 кв 102."),
    ("EMAIL", "olga.pahomova@mail.ru", "Логин Pahomova создан."),
    ("PHONE", "+7 943 239-11-74", "Перезвоню на 8 943 239 11 74."),
    ("CARD", "4276 3800 1234 5678", "Списание с карты 4276380012345678 прошло."),
    ("SNILS", "681-644-063 10", "СНИЛС 68164406310 принят."),
    ("INN", "7736050003", "ИНН 7736 050003 сверен."),
    ("PASSPORT", "4509 123456", "Паспорт 4509123456 проверен."),
    ("DOB", "14.03.1987", "Дата рождения 1987-03-14 подтверждена."),
    ("DATE", "14.03.1987", "Запись на 1987-03-14 сделана."),
    ("PLATE", "а123вс777", "Машина а 123 вс 777 подана."),
)


def test_the_pregate_reads_the_shapes_a_model_writes() -> list[str]:
    """The pre-gate and `residual` answer the SAME question (§5, §8.5).

    Measured over 200 corpus cases masked through the production path, on
    answers carrying the mint in the shape above: the whole-surface-and-whole-
    word rule this gate used to carry caught 2 of 189 declined names, 0 of 169
    renotated phones, 0 of 5 respaced cards and 0 of 10 respaced СНИЛС, while
    `residual` counted every one of them. Those answers went to the judge with
    our fake standing in them — the blindness §8.5 promises, spent on.
    """
    failures: list[str] = []
    for pii_type, surface, answer in REWRITTEN:
        if judge.residual_pregate_of(answer, (surface,), ()) is None:
            failures.append(f"{pii_type}: переписанная подмена прошла претгейт: {answer!r}")
        # THE CONVERGENCE ITSELF: the line and the gate must not disagree about
        # one string, or the report says «критический дефект» about an answer
        # the judge was meanwhile asked to grade.
        if not observe.survives_in(pii_type, surface, answer, frozenset()):
            failures.append(f"{pii_type}: линия residual перестала видеть {answer!r} — "
                            f"таблица разошлась с прибором, а не претгейт с линией")
    # THE NEGATIVE for all eleven at once: an answer that carries none of them
    # is not refused, so the rows above fire on the SUBSTITUTE and not on the
    # gate having become «отказывать всегда».
    honest = "Готово, записал. Курьер приедет завтра до обеда, оператор перезвонит."
    for pii_type, surface, _answer in REWRITTEN:
        if judge.residual_pregate_of(honest, (surface,), ()) is not None:
            failures.append(f"{pii_type}: честный ответ без подмены отказан")
    return failures


def test_an_earlier_turn_is_masked_in_the_same_shapes() -> list[str]:
    """The judge is as blind to a declined substitute one turn back as to one
    in the answer — `mask_residual_turns` asks `residual_spans` too.

    The dialogue is where the engine's own unrestored lower-case mints live
    (the chat / sloppy / voice registers mint exactly those), so a masker that
    only knew whole surfaces handed the judge a fake to read as the customer's
    value and counted `turn_residual` = 0 while it did.
    """
    failures: list[str] = []
    turns = (DialogueTurn(role="user", text="это иванова елена, запишите"),
             DialogueTurn(role="assistant", text="Секунду, открываю карточку Пахомовой Ольги."))
    masked, flagged = judge.mask_residual_turns(turns, (SUBSTITUTE,), (REAL,))
    if "Пахомов" in masked[1].text or judge.RESIDUAL_MARKER not in masked[1].text:
        failures.append(f"склонённая подмена доехала до судьи: {masked[1].text!r}")
    if flagged != 1:
        failures.append(f"ход агента с подменой насчитан {flagged} раз вместо одного")
    if masked[0].text != turns[0].text:
        failures.append(f"собственная реплика клиента искажена: {masked[0].text!r}")
    # THE NEGATIVE: the same turn with the customer's own name is untouched and
    # uncounted, so the marker above is the SUBSTITUTE and not every name.
    honest = (DialogueTurn(role="assistant", text="Секунду, открываю карточку Ивановой Елены."),)
    kept, none = judge.mask_residual_turns(honest, (SUBSTITUTE,), (REAL,))
    if kept[0].text != honest[0].text or none:
        failures.append(f"настоящее имя клиента замаскировано как подмена: {kept[0].text!r}")
    return failures


def test_the_pregate_spares_ordinary_russian() -> list[str]:
    """G3.3: a generic street word, a month name and half a city are not ours.

    All three were measured on the corpus through the production masking path:
    «улица» was the commonest piece of all (48 occurrences over 250 cases), and
    «нижний» / «второго» published «неверно» on 12 of 489 honest answers that
    merely repeated back what the customer had dictated. A pre-gate that fires
    on «улица» is a published false defect of the product, bought for free.
    """
    failures: list[str] = []
    generic = _needle_texts("улица тополиная 5")
    if "улиц" in generic or "улица" in generic:
        failures.append(f"родовое слово адреса осталось иглой: {generic}")
    # THE NEGATIVE for the same split: the street name IS ours, so the absence
    # above is a subtraction and not an empty needle set.
    if "топо" not in generic:
        failures.append(f"разбор не дал ни одной иглы — проверка ни о чём: {generic}")
    dated = _needle_texts(MINTED_SPOKEN_DOB)
    if "дека" in dated:
        failures.append(f"название месяца осталось иглой: {dated}")
    if "трет" not in dated:
        failures.append(f"устная дата не дала ни одной иглы — проверка ни о чём: {dated}")
    own = judge.own_needle_stems((REAL_ADDRESS,))
    if "нижн" not in own or "новг" not in own:
        failures.append(f"половина города клиента не попала в вычитаемые стволы: {sorted(own)[:8]}")
    bare = _needle_texts(MINTED_ADDRESS)
    if "нижн" not in bare or "новг" not in bare:
        failures.append(f"город не стал иглой подмены — вычитать было нечего: {bare}")
    honest = f"Готово, курьер приедет: {REAL_ADDRESS}. Ждите звонка."
    if judge.residual_pregate_of(honest, (MINTED_ADDRESS,), (REAL_ADDRESS,)) is not None:
        failures.append("претгейт отказал честному ответу на собственном адресе клиента")
    # …and the SAME answer without the real list is refused, so the subtraction
    # is what spares it rather than the answer being harmless.
    if judge.residual_pregate_of(honest, (MINTED_ADDRESS,), ()) is None:
        failures.append("без настоящего адреса тот же ответ прошёл — претгейт молчит всегда")
    # THE GATE STILL FIRES on a piece that is really ours: the fake street word
    # stands in the answer as a whole word and nothing about it is the
    # customer's, grammar or a month.
    leaked = judge.residual_pregate_of(f"Курьер приедет: {MINTED_ADDRESS}.",
                                       (MINTED_ADDRESS,), (REAL_ADDRESS,))
    if leaked is None or leaked.judged_by != "residual_gate":
        failures.append("подмена целиком в ответе перестала останавливать судью")
    vocabulary = judge.own_vocabulary((REAL_ADDRESS,))
    for word in ("улица", "декабря", "нижний", "новгород", "переулок"):
        if word not in vocabulary:
            failures.append(f"слово {word!r} не попало в вычитаемый словарь")
    if "озерный" in vocabulary or "тополиная" in vocabulary:
        failures.append("в вычитаемый словарь попало название подменной улицы")
    return failures


def test_the_customers_own_turn_is_never_masked() -> list[str]:
    """G3.2: a `user` turn is the case's own text and can carry no substitute.

    `masked_dialogue` used to eat the customer's own city and the generic word
    out of the customer's own sentence — 17.5 % of CLEAN runs over 400 corpus
    cases got `turn_residual > 0` and the judge lost the words question 4 is
    asked about. The oracle alone could not spare them: `oracle_literals` keeps
    only items whose identity equals the primary one, and every address of this
    corpus hangs off a sub-identity (`p0.home`, `p0.new`).
    """
    failures: list[str] = []
    said = f"записывайте {REAL_ADDRESS}"
    clean = (DialogueTurn(role="user", text=said),
             DialogueTurn(role="assistant", text="Секунду, проверяю."))
    request = JudgeInput(case_id="c-0001", restored_answer="Готово.",
                         oracle_literals=(REAL, "+7 916 402-11-87"),
                         dialogue_context=clean, customer_question=said)
    turns, flagged = judge.masked_dialogue(request, (MINTED_ADDRESS,))
    if flagged:
        failures.append(f"на чистом прогоне насчитано {flagged} нераскрытых подмен")
    if turns[0].text != said:
        failures.append(f"собственная реплика клиента искажена: {turns[0].text!r}")
    # THE NEGATIVE, twice. Without the dialogue's own real turns the very same
    # scan eats the sentence — so the subtraction does the work…
    eaten, eaten_flags = judge.mask_residual_turns(clean, (MINTED_ADDRESS,), ())
    if eaten[0].text == said:
        failures.append("без настоящих строк реплика клиента уцелела — вычитание "
                        "нечего было делать")
    # …and even when it IS eaten, the customer's own turn is not «the agent's
    # earlier turn»: the count is what `ArmRunV5.turn_residual` promises and
    # `residual` scores, so a user turn inside it would publish a defect of the
    # gateway that the gateway never had.
    if eaten_flags:
        failures.append(f"реплика клиента засчитана нераскрытой подменой агента: {eaten_flags}")
    # …and a substitute the restorer really left in the AGENT's turn is still
    # replaced and still counted.
    leaked = (DialogueTurn(role="user", text=said),
              DialogueTurn(role="assistant", text=f"Секунду, смотрю карточку {MINTED_ADDRESS}."))
    request = JudgeInput(case_id="c-0001", restored_answer="Готово.",
                         oracle_literals=(REAL, "+7 916 402-11-87"),
                         dialogue_context=leaked, customer_question=said)
    turns, flagged = judge.masked_dialogue(request, (MINTED_ADDRESS,))
    if flagged != 1:
        failures.append(f"подмена в ходе агента насчитана {flagged} раз вместо одного")
    if judge.RESIDUAL_MARKER not in turns[1].text or MINTED_ADDRESS in turns[1].text:
        failures.append(f"подмена в ходе агента доехала до судьи: {turns[1].text!r}")
    if turns[0].text != said:
        failures.append("маскирование хода агента задело реплику клиента")
    return failures


# A minted address as the spoken and «sloppy» registers write one: no commas,
# the customer's real city in front (the vault keeps the settlement), a fake
# street. `parts.address_parts` lumps the words it cannot type into ONE `street`
# role joined ALPHABETICALLY — «орел рябиновый» — a string that occurs neither
# in the answer nor in the address itself, and the name splitter types the city
# as a surname and the generic word as a given name. So the only piece the old
# rule produced matched nothing.
MINTED_SPOKEN_ADDRESS: str = "орёл проспект рябиновый 100 кв 102"
REAL_SPOKEN_ADDRESS: str = "орёл проспект вишнёвый 7 кв 3"


def test_a_fake_street_without_its_city_is_refused() -> list[str]:
    """The commonest way a model retells an address it was given: without the
    city.

    Measured on 120 corpus cases through the production masking path, over the
    answers that carry the minted surface minus its leading real city AND still
    carry a fake word of it: 10 of 109 passed the gate (90.8 % → 100 %), because
    no piece of a long address survives the splitters. A word of the substitute
    is a part of it, and carries the same filters.
    """
    failures: list[str] = []
    minted, real = (MINTED_SPOKEN_ADDRESS,), (REAL_SPOKEN_ADDRESS,)
    leaked = judge.residual_pregate_of("Курьер приедет: проспект рябиновый 100 кв 102.",
                                       minted, real)
    if leaked is None or leaked.judged_by != "residual_gate":
        failures.append("подменная улица без города прошла претгейт")
    # THE NEGATIVE that says the rule is a rule and not «refuse everything»:
    # the same sentence shapes with the customer's own city, the generic word
    # and the flat — every word of the substitute that is not ours — pass.
    for honest in ("Курьер приедет на тот же проспект в орёл, квартира та же.",
                   "Город орёл подтверждён, дом и квартира прежние.",
                   f"Записал: {REAL_SPOKEN_ADDRESS}."):
        if judge.residual_pregate_of(honest, minted, real) is not None:
            failures.append(f"честный ответ отказан: {honest!r}")
    # …and the needle that does the work is built PER WORD, not from the
    # splitter's blob: the blob is joined alphabetically, carries a space and
    # stands nowhere in the address itself.
    pieces = tuple(sorted(needle.text for needle in judge.substitute_needles(MINTED_SPOKEN_ADDRESS)
                          if needle.role))
    if "ряби" not in pieces:
        failures.append(f"ствол подменной улицы не стал иглой: {pieces}")
    # A needle that NAMES a role is one word: the whole surface has its own
    # needle and a two-word piece would be the splitter's blob back again.
    if any(" " in piece for piece in pieces):
        failures.append(f"игла роли склеила два слова: {pieces}")
    blob = parts_of("LOC", MINTED_SPOKEN_ADDRESS).get("street", "")
    if " " not in blob or blob in MINTED_SPOKEN_ADDRESS:
        failures.append(f"разбор перестал склеивать улицу — негатив ни о чём: {blob!r}")
    return failures


def test_a_tool_echo_is_masked_and_not_counted() -> list[str]:
    """A `tool` turn CAN carry our substitute, and it is not the agent's turn.

    `REAL_DIALOGUE_ROLES` said a tool result «cannot carry a substitute of
    ours», and that is true of what the MOCK invents and false of what it
    echoes: a leaf the restorer left with a fake in it comes back inside
    `ToolResultRecord.text_real` (`ECHO_TAG_PREFIX`), so the string in the turn
    is our own mint repeated. Two things must then hold at once — the judge
    still reads the marker (blindness has no exceptions), and the count stays
    the agent's, because `residual` reads `turn_residual` as «the agent's
    earlier turns» and that leak already has a line with its name on it: the
    OUT hop of the call that wrote it.
    """
    failures: list[str] = []
    echoed = f"карточка: {MINTED_ADDRESS}"
    turns, flagged = judge.mask_residual_turns(
        (DialogueTurn(role="tool", text=echoed),), (MINTED_ADDRESS,), (REAL_ADDRESS,))
    if MINTED_ADDRESS in turns[0].text or judge.RESIDUAL_MARKER not in turns[0].text:
        failures.append(f"эхо инструмента довезло подмену до судьи: {turns[0].text!r}")
    if flagged:
        failures.append(f"эхо инструмента засчитано нераскрытой подменой агента: {flagged}")
    # THE POSITIVE for the same string: in the AGENT's turn it is counted, so
    # the zero above is the ROLE and not a scan that found nothing.
    _, agent_flags = judge.mask_residual_turns(
        (DialogueTurn(role="assistant", text=echoed),), (MINTED_ADDRESS,), (REAL_ADDRESS,))
    if agent_flags != 1:
        failures.append(f"та же строка в ходе агента насчитана {agent_flags} раз вместо одного")
    return failures


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("input_is_blind", test_input_is_blind),
        ("rubric_names_four_questions", test_rubric_names_four_questions),
        ("rubric_has_no_form_rules", test_rubric_has_no_form_rules),
        ("residual_pregate_short_circuits", test_residual_pregate_short_circuits),
        ("the_pregate_reads_the_shapes_a_model_writes",
         test_the_pregate_reads_the_shapes_a_model_writes),
        ("an_earlier_turn_is_masked_in_the_same_shapes",
         test_an_earlier_turn_is_masked_in_the_same_shapes),
        ("quote_must_stand", test_quote_must_stand),
        ("prompt_sha_changes_with_rubric", test_prompt_sha_changes_with_rubric),
        ("judged_by_none_carries_no_label", test_judged_by_none_carries_no_label),
        ("no_unreachable_adapters", test_no_unreachable_adapters),
        ("one_temperature_for_run_and_repeats", test_one_temperature_for_run_and_repeats),
        ("temperature_the_transport_cannot_deliver_is_refused",
         test_temperature_the_transport_cannot_deliver_is_refused),
        ("prompt_hashes_what_was_sent", test_prompt_hashes_what_was_sent),
        ("dialogue_carries_the_agents_turns", test_dialogue_carries_the_agents_turns),
        ("agents_turns_are_restored", test_agents_turns_are_restored),
        ("the_pregate_spares_ordinary_russian", test_the_pregate_spares_ordinary_russian),
        ("the_customers_own_turn_is_never_masked", test_the_customers_own_turn_is_never_masked),
        ("a_fake_street_without_its_city_is_refused",
         test_a_fake_street_without_its_city_is_refused),
        ("a_tool_echo_is_masked_and_not_counted", test_a_tool_echo_is_masked_and_not_counted),
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
