"""`microscope.py` pinned on REAL run directories, offline, from the run's own files.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_microscope

THE RUNS ARE THE ONES `test_compare.py` WRITES. The tape is a reader of a
finished run, so what it has to be tested against is a run directory written by
the writers — and building a second one here would be a second fixture corpus
to keep in step with the first.

EVERY CHECK NAMES A CLAUSE AND GOES RED WITHOUT IT. The four that carry the
point of §2.3:

  * the tape shows the message as the MODEL read it — the substitute in the
    span the run says the gateway replaced, not the corpus's own text. A tape
    that printed the customer's text would show a conversation that never
    happened.
  * a declared value the run did NOT mask is named as a LEAK. That is the one
    failure the product exists to prevent and the one the aggregates cannot
    see — a value that reached the model in the clear makes the arms AGREE.
  * a declared hop with no row in `<run>.hops.jsonl` is a HOLE and says so.
    Report finding №5 is exactly this shape: `residual` printed 1/1 over
    observations whose hops it had never read.
  * a missing judge verdict is printed as missing. «Нет вердикта» and «верно»
    are not the same fact, and a tape that showed nothing for the first would
    let a reader supply the second.
"""
import sys
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from bench.agentpii4.records import ArmMeta, arm_record
from bench.agentpii5 import contracts, records
from bench.agentpii5.microscope import (
    MicroscopeError,
    differences,
    main as microscope_main,
    read_tape,
    render_tape,
    repeats_of,
    shown_message,
    tapes,
)
from bench.agentpii5.fixtures import FAKE_NAME, REAL_NAME
from bench.agentpii5.metrics import coverage
from bench.agentpii5.observe import observe
from bench.agentpii5.test_compare import (
    CASE_IDS,
    DIGEST,
    RUN_A,
    both,
    broken_arm,
    build_run,
    fixture_case,
    good_arm,
)

CASE = CASE_IDS[0][0]
WIDTH = 400


def _tape_text(run_dir: Path, case_id: str) -> str:
    return "\n".join(render_tape(read_tape(run_dir, case_id, 0), WIDTH))


def _with_argv(argv: list[str], entry: Callable[[], int]) -> int:
    """Run a module's `main()` on a chosen command line.

    The package's entry points read `sys.argv` and take no argument — the house
    shape — so the command line is set here rather than by giving `main` a
    parameter no production caller would ever pass.
    """
    saved = sys.argv
    sys.argv = ["prog", *argv]
    try:
        return entry()
    finally:
        sys.argv = saved


def test_no_pseudex() -> list[str]:
    """The tape reads files. An engine import would make what a run «showed»
    depend on the branch the microscope is run from."""
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_shows_the_message_the_model_read() -> list[str]:
    """Пункт 7, first half. The substitute stands where the gateway replaced the
    value, the real value is named beside it, and the model's own text does NOT
    carry the real one."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        tape = read_tape(a_dir, CASE, 0)
        shown, notes = shown_message(tape.case, tape.run, 1)
        if FAKE_NAME not in shown:
            problems.append(f"the substitute is not in the message the model read: {shown!r}")
        if REAL_NAME in shown:
            problems.append(f"the real value stands in the text shown to the model: {shown!r}")
        if not any(REAL_NAME in note and FAKE_NAME in note for note in notes):
            problems.append(f"the note does not say which value became which: {notes}")
        text = _tape_text(a_dir, CASE)
        if "что показали модели" not in text or shown not in text:
            problems.append("the rendered tape does not carry the masked message")
    return problems


def test_an_unmasked_value_is_named_a_leak() -> list[str]:
    """A declared value the run left untouched reached the model in the clear.
    The aggregates cannot see it — a leaked value makes the arms AGREE — so the
    tape has to."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        tape = read_tape(a_dir, CASE, 0)
        # The PHONE of the fixture case is declared and never masked: the run
        # records a span for the name alone.
        _shown, notes = shown_message(tape.case, tape.run, 1)
        leaks = [note for note in notes if note.startswith("УТЕЧКА")]
        if len(leaks) != 1 or "p2" not in leaks[0]:
            problems.append(f"the unmasked declared value is not named as a leak: {notes}")
        if "УТЕЧКА" not in _tape_text(a_dir, CASE):
            problems.append("the rendered tape does not print the leak")
    return problems


def _wide_arm(case: contracts.CaseV5) -> contracts.ArmRunV5:
    """The gateway that masked MORE than the corpus declared.

    The ordinary case on Russian traffic and the reason this check exists: the
    detector finds «ул. Ленина, 14» whole and replaces a span that CONTAINS the
    street the corpus declared inside it. Here the name's span [0:13] sits
    inside a replacement of [0:15]; the PHONE at [15:27] is outside it and stays
    the leak the fixture is built to show."""
    run = good_arm(case)
    return replace(run, base=replace(run.base, masked_spans={1: ((0, 15),)}))


def _half_arm(case: contracts.CaseV5) -> contracts.ArmRunV5:
    """The gateway that masked HALF the name — a replacement that touches the
    value without covering it."""
    run = good_arm(case)
    return replace(run, base=replace(run.base, masked_spans={1: ((0, 8),)}))


def test_a_wider_masked_span_is_not_a_leak() -> list[str]:
    """THE MICROSCOPE MAY NOT CALL A PROTECTED VALUE A LEAK.

    `metrics.coverage` asks containment — `start <= item.start and item.end <=
    end` — so a value inside a wider replacement is PROTECTED and counted as a
    hit. The tape matched span to item by `(start, end)` equality, so the same
    run read as «замена, не совпавшая ни с одним объявленным значением» beside
    «УТЕЧКА: модель прочитала настоящее значение» — two false statements about
    one masked message, and a reader sent hunting a defect the run does not
    hold.

    The check pins the two to AGREE rather than restating the rule: the metric
    is asked on the same run, and its verdict is the one the tape must match.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cases = [fixture_case(case_id, behaviour) for case_id, behaviour in CASE_IDS]
        run_dir = build_run(root, "wideA0001", DIGEST, cases, _wide_arm, "шире объявленного")
        case = next(one for one in cases if one.base.id == CASE)
        line = coverage([observe(case, _wide_arm(case), None, None)])
        if not line.total or line.hits != line.total:
            problems.append(f"metrics.coverage does not call the wider replacement "
                            f"protected — the fixture proves nothing: {line}")
        tape = read_tape(run_dir, CASE, 0)
        shown, notes = shown_message(tape.case, tape.run, 1)
        if any(note.startswith("УТЕЧКА") and "p1" in note for note in notes):
            problems.append(f"a value the metric counts as protected is called a leak: {notes}")
        if any("не покрыла ни одного" in note for note in notes):
            problems.append(f"the replacement that covers the name is called unclaimed: {notes}")
        if REAL_NAME in shown or FAKE_NAME not in shown:
            problems.append(f"the wider span is not rendered with the substitute: {shown!r}")
        if not any("шире" in note and "p1" in note for note in notes):
            problems.append(f"the note does not say the replacement was wider than the "
                            f"declared value: {notes}")
        # The other side, in the same run: the PHONE outside the replacement is
        # still the leak the aggregates cannot see.
        if not any(note.startswith("УТЕЧКА") and "p2" in note for note in notes):
            problems.append(f"the value outside the replacement stopped being a leak: {notes}")
        if "УТЕЧКА" not in _tape_text(run_dir, CASE):
            problems.append("the rendered tape of the wider run prints no leak at all")
        # And the third reading: a replacement that TOUCHES the value without
        # covering it is a miss for `coverage` too, and the tape says which
        # miss it is.
        half = _half_arm(case)
        half_line = coverage([observe(case, half, None, None)])
        if half_line.hits:
            problems.append(f"metrics.coverage counts a half-masked value as protected: "
                            f"{half_line}")
        _half_shown, half_notes = shown_message(case, half, 1)
        if not any(note.startswith("УТЕЧКА (частичная)") and "p1" in note
                   for note in half_notes):
            problems.append(f"a half-masked value is not named as a partial leak: {half_notes}")
    return problems


def test_shows_what_the_model_wrote_and_what_came_back() -> list[str]:
    """Пункт 7, second half: the arguments as written and as restored, the
    answer as written and as the customer reads it."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), broken_arm, DIGEST, None)
        good = _tape_text(a_dir, CASE)
        for needed in ("написано:", "восстановлено:", "ответ как написан",
                       "ответ как читает клиент", "crm_upsert_contact"):
            if needed not in good:
                problems.append(f"the tape does not show {needed!r}")
        if "Ивановой" not in good:
            problems.append("the restored argument is not printed")
        bad = _tape_text(b_dir, CASE)
        if "ПОДМЕНА ДОШЛА ДО ИНСТРУМЕНТА" not in bad:
            problems.append("a residual in the tool call is not named on the tape")
    return problems


def test_shows_declared_hops_and_how_the_observer_read_them() -> list[str]:
    """Пункт 7, third half. Every hop the case declares, with the status the
    observer gave it and the form verdict — read from `<run>.hops.jsonl`, never
    recomputed."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        tape = read_tape(a_dir, CASE, 0)
        text = _tape_text(a_dir, CASE)
        if "хопы: объявлено и прочитано" not in text:
            problems.append("the tape has no hop section")
        for hop in tape.case.hops:
            marker = f"#{hop.hop_index:>3} {hop.kind + '/' + hop.owner:14}"
            if marker not in text:
                problems.append(f"the declared hop {hop.hop_index} {hop.kind}/{hop.owner} "
                                f"is missing from the tape")
        statuses = {one.status for one in tape.hops}
        if not statuses:
            problems.append("the tape read no hop rows at all")
        for status in statuses:
            if status not in text:
                problems.append(f"the observer's status {status!r} is not printed")
    return problems


def test_a_declared_hop_without_a_row_is_a_hole() -> list[str]:
    """Report finding №5, in the microscope: a declared hop the observer never
    recorded must be NAMED, never skipped. A tape that printed the two hops it
    found and said nothing about the third reads as a case with two hops."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        hops_path = records.run_file(a_dir, RUN_A, "<run>.hops.jsonl")
        rows = records.read_rows(hops_path)
        dropped = [row for row in rows
                   if not (row["case_id"] == CASE and row["hop"]["hop_index"] == 1)]  # type: ignore[index]
        if len(dropped) == len(rows):
            problems.append("the fixture case declares no hop index 1 — nothing was dropped")
        hops_path.write_text("", encoding="utf-8")
        for row in dropped:
            records.append_row(hops_path, row)
        text = _tape_text(a_dir, CASE)
        if "ДЫРА" not in text:
            problems.append("a declared hop with no observer row was not named as a hole")
    return problems


def test_an_undeclared_hop_is_printed_apart() -> list[str]:
    """A crossing the agent made that the case did not declare belongs on the
    tape and NOT among the declared ones: it counts in the form lines and in no
    denominator the case owns, and a reader must be able to see which is which."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        tape = read_tape(a_dir, CASE, 0)
        hops_path = records.run_file(a_dir, RUN_A, "<run>.hops.jsonl")
        extra = tape.hops[0]
        records.append_row(hops_path, records.hop_observation_to_json(
            contracts.HopObservation(
                case_id=extra.case_id, repeat=extra.repeat,
                hop=contracts.Hop(kind="OUT", owner="tool_arg", item_id="p2", hop_index=-1,
                                  turn=1, tool_name="crm_upsert_contact", call_ordinal=0,
                                  parallel_group="", source_hop=-1, path="contact.phone",
                                  optional=False),
                declared=False, pii_type="PHONE", produced="+79164021187",
                reference="+79164021187", status="observed",
                verdict=contracts.FormVerdict(same=True, differs=frozenset()))))
        text = _tape_text(a_dir, CASE)
        if "которых случай не объявлял" not in text:
            problems.append("an undeclared hop is not printed under its own heading")
        if "contact.phone" not in text:
            problems.append("the undeclared hop's path is not printed")
    return problems


def test_the_judge_verdict_with_its_quote() -> list[str]:
    """Пункт 7, last half: the label, who gave it and the quote it stands on."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        text = _tape_text(a_dir, CASE)
        if "верно · вынес model" not in text:
            problems.append("the tape does not print the label and who gave it")
        if "цитата: «Ивановой»" not in text:
            problems.append("the tape does not print the judge's quote")
    return problems


def test_a_missing_verdict_is_not_a_good_one() -> list[str]:
    """«Нет вердикта» and «верно» are different facts. A tape that showed
    nothing for the first would let a reader supply the second."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        judge_path = records.run_file(a_dir, RUN_A, "<run>.judge.jsonl")
        rows = records.read_rows(judge_path)
        judge_path.write_text("", encoding="utf-8")
        for row in rows:
            if row.get("case_id") != CASE:
                records.append_row(judge_path, row)
        text = _tape_text(a_dir, CASE)
        if "вердикта нет" not in text or "НЕ «верно»" not in text:
            problems.append("a case with no verdict does not say so on the tape")
    return problems


def test_two_tapes_and_the_difference_block() -> list[str]:
    """Пункт 7: `--run A --run B` prints both tapes and then what changed —
    the block a reader actually opens two tapes for."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), broken_arm, DIGEST, None)
        lines = tapes([a_dir, b_dir], CASE, 0, WIDTH)
        text = "\n".join(lines)
        if text.count(f"=== {CASE}|0") != 2:
            problems.append("two runs did not produce two tapes")
        if "что изменилось" not in text:
            problems.append("no difference block was printed")
        a_tape, b_tape = read_tape(a_dir, CASE, 0), read_tape(b_dir, CASE, 0)
        block = "\n".join(differences(a_tape, b_tape, WIDTH))
        if "ни один статус" in block:
            problems.append("a run with a residual on every hop is reported as unchanged")
        if "ответ клиенту:" not in block or "тот же текст" in block:
            problems.append("the answer moved and the difference block says it did not")
    return problems


def test_identical_runs_say_nothing_moved() -> list[str]:
    """The negative of the check above: a difference block that always found
    something would find something on two copies of one run."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        block = "\n".join(differences(read_tape(a_dir, CASE, 0), read_tape(b_dir, CASE, 0), WIDTH))
        if "ни один статус" not in block:
            problems.append(f"two identical runs were reported as differing:\n{block}")
        if "тот же текст" not in block:
            problems.append("the answers are identical and the block does not say so")
    return problems


def test_one_tape_prints_no_difference_block() -> list[str]:
    """One run is one tape: a difference block over one run would be a
    comparison with nothing."""
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        text = "\n".join(tapes([a_dir], CASE, 0, WIDTH))
        return ["a single run printed a difference block"] if "что изменилось" in text else []


def test_an_unknown_case_is_refused_by_name() -> list[str]:
    """«Нет такого случая» and «нет такого прогона» send a reader to different
    places; an empty tape sends them to neither."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        refused = False
        try:
            read_tape(a_dir, "нет-такого", 0)
        except MicroscopeError as error:
            refused = True
            if "нет-такого" not in str(error):
                problems.append(f"the refusal does not name the case: {error}")
            # The refusal must be the CASE's, not the arm lookup's downstream
            # «нет плеча с повтором 0; записаны повторы ни одного» — which is
            # true and sends the reader to look for a repeat of a case that
            # does not exist.
            if "corpus.v5.json" not in str(error):
                problems.append(f"an unknown case was refused by the arm lookup instead of by "
                                f"the corpus: {error}")
        if not refused:
            problems.append("a case the run does not hold produced a tape")
        refused = False
        try:
            read_tape(a_dir, CASE, 7)
        except MicroscopeError as error:
            refused = True
            if "7" not in str(error) or "0" not in str(error):
                problems.append(f"the refusal names neither the repeat asked for nor the "
                                f"repeats recorded: {error}")
        if not refused:
            problems.append("a repeat the run never wrote produced a tape")
        # THE SAME REFUSAL THROUGH THE COMMAND'S OWN PATH. `tapes` asks for the
        # repeats before it asks for the case, and without `case_of` first an
        # unknown id came back as «нет ни одного записанного плеча» — a sentence
        # that sends the reader looking for a repeat of a case that is not there.
        refused = False
        try:
            tapes([a_dir], "нет-такого", None, WIDTH)
        except MicroscopeError as error:
            refused = True
            if "corpus.v5.json" not in str(error):
                problems.append(f"the command's own path refuses an unknown case with the "
                                f"wrong reason: {error}")
        if not refused:
            problems.append("the command's own path produced a tape for an unknown case")
    return problems


def _add_second_repeat(run_dir: Path, case_id: str) -> None:
    """A second repeat of one case, written the way the harness writes the
    first. A fixture with one repeat cannot tell «all repeats» from «repeat 0»."""
    case = next(fixture_case(one, behaviour) for one, behaviour in CASE_IDS if one == case_id)
    run = good_arm(case)
    run = replace(run, base=replace(run.base, repeat=1))
    meta = ArmMeta("fixture", 1, 1, "sess", "success", False, None, (), "", 0.0)
    for arm in ("C", "I", "C2"):
        records.append_row(records.run_file(run_dir, RUN_A, "<run>.arms.jsonl"),
                           arm_record(replace(run.base, arm=arm), meta, case.base))
    records.append_row(records.run_file(run_dir, RUN_A, "<run>.arms.v5.jsonl"),
                       records.arm_v5_record(run, meta, case.base))
    for hop in observe(case, run, None, None).hops:
        records.append_row(records.run_file(run_dir, RUN_A, "<run>.hops.jsonl"),
                           records.hop_observation_to_json(replace(hop, repeat=1)))


def test_a_directory_that_is_not_a_run_is_refused_by_the_command() -> list[str]:
    """The CLI answers a wrong path with a refusal and exit 2, not a traceback:
    «нет такого прогона» is an answer, a stack trace is not."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "не-прогон"
        empty.mkdir()
        code = _with_argv([CASE, "--run", str(empty)], microscope_main)
        if code != 2:
            problems.append(f"a directory that is not a run exited {code}, not 2")
    return problems


def test_all_repeats_by_default() -> list[str]:
    """`--repeat` narrows; without it every recorded repeat is shown, because a
    tape of repeat 0 alone hides exactly the instability a reader came for."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        cases = [fixture_case(case_id, behaviour) for case_id, behaviour in CASE_IDS]
        a_dir = build_run(Path(tmp), RUN_A, DIGEST, cases, good_arm, "A")
        _add_second_repeat(a_dir, CASE)
        if repeats_of(a_dir, CASE) != [0, 1]:
            problems.append(f"the fixture run recorded repeats {repeats_of(a_dir, CASE)}")
        text = "\n".join(tapes([a_dir], CASE, None, WIDTH))
        for repeat in (0, 1):
            if f"=== {CASE}|{repeat}" not in text:
                problems.append(f"the default did not print repeat {repeat}")
        narrowed = "\n".join(tapes([a_dir], CASE, 1, WIDTH))
        if f"=== {CASE}|0" in narrowed or f"=== {CASE}|1" not in narrowed:
            problems.append("--repeat did not narrow the tape to the repeat asked for")
    return problems


def test_the_tape_is_read_and_not_recomputed() -> list[str]:
    """The statuses on the tape are the ones the RUN recorded. Editing a row on
    disk must change the tape; a microscope that re-derived the hop would print
    today's observer over yesterday's run — that is, not what the run
    measured."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        hops_path = records.run_file(a_dir, RUN_A, "<run>.hops.jsonl")
        rows = records.read_rows(hops_path)
        hops_path.write_text("", encoding="utf-8")
        for row in rows:
            if row["case_id"] == CASE and row["hop"]["hop_index"] == 0:  # type: ignore[index]
                row = dict(row)
                row["status"] = "leaked"
                row["verdict"] = None
            records.append_row(hops_path, row)
        text = _tape_text(a_dir, CASE)
        if "leaked" not in text:
            problems.append("the tape ignored the status the run recorded")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("shows_the_message_the_model_read", test_shows_the_message_the_model_read),
        ("an_unmasked_value_is_named_a_leak", test_an_unmasked_value_is_named_a_leak),
        ("a_wider_masked_span_is_not_a_leak", test_a_wider_masked_span_is_not_a_leak),
        ("shows_what_the_model_wrote_and_what_came_back",
         test_shows_what_the_model_wrote_and_what_came_back),
        ("shows_declared_hops_and_how_the_observer_read_them",
         test_shows_declared_hops_and_how_the_observer_read_them),
        ("a_declared_hop_without_a_row_is_a_hole", test_a_declared_hop_without_a_row_is_a_hole),
        ("an_undeclared_hop_is_printed_apart", test_an_undeclared_hop_is_printed_apart),
        ("the_judge_verdict_with_its_quote", test_the_judge_verdict_with_its_quote),
        ("a_missing_verdict_is_not_a_good_one", test_a_missing_verdict_is_not_a_good_one),
        ("two_tapes_and_the_difference_block", test_two_tapes_and_the_difference_block),
        ("identical_runs_say_nothing_moved", test_identical_runs_say_nothing_moved),
        ("one_tape_prints_no_difference_block", test_one_tape_prints_no_difference_block),
        ("an_unknown_case_is_refused_by_name", test_an_unknown_case_is_refused_by_name),
        ("a_directory_that_is_not_a_run_is_refused_by_the_command",
         test_a_directory_that_is_not_a_run_is_refused_by_the_command),
        ("all_repeats_by_default", test_all_repeats_by_default),
        ("the_tape_is_read_and_not_recomputed", test_the_tape_is_read_and_not_recomputed),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("microscope: PASS" if not failures else "microscope: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
