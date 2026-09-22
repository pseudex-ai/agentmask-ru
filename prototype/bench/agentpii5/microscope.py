"""ОДИН СЛУЧАЙ ОДНОЙ КОМАНДОЙ: что показали модели, что она написала, что вернулось.

    python3 -m bench.agentpii5.microscope <id случая> --run <каталог прогона>
    python3 -m bench.agentpii5.microscope <id случая> --run A --run B
    python3 -m bench.agentpii5.microscope <id случая> --run A --repeat 2

Spec `docs/tz-bench-harness.md` §2.3 (item 7). NO MODEL AND NO SPEND: everything
printed here is already in the files of a finished run (`contracts.RUN_FILES`).
Nothing is recomputed — not a hop, not a verdict: `observe.py` ran during the
run and the judge spoke then, and the tape shows THEIR result. A tape that
re-derived a hop's status would show today's observer over yesterday's run,
which is not what the run measured.

WHAT THE TAPE SHOWS, IN THE ORDER THE CONVERSATION HAPPENED:

  1. **What the model saw.** The message with the substitutes put in — built
     from `Case.messages` and `ArmRun.masked_spans`, that is, from what the
     gateway ACTUALLY replaced and not from what the corpus declared to be
     personal data. The difference between those two is a LEAK, and it gets a
     line of its own: a value that reached the model in the clear is exactly
     the failure the product exists to prevent, and it is invisible in the
     aggregates (a leaked value makes the arms AGREE).
  2. **What came back to the model** — the tool results: what it read, and what
     actually stood there.
  3. **What it wrote** — the call arguments as written and as restored, the
     answer as written (substitutes still in it) and as the customer reads it.
  4. **Hops: declared and read.** Every hop the case declares beside the
     observer's own row; a declared hop with no row in `<run>.hops.jsonl` is a
     HOLE and is named rather than skipped (report finding №5: `residual`
     printed 1/1 over observations whose hops it had never read). Hops the case
     did not declare are printed in a list of their own — the agent carried a
     value somewhere nobody asked it to.
  5. **The judge's verdict with its quote** — the label, who gave it (the model
     or the deterministic pre-gate) and the quote it stands on.

TWO TAPES RUN ONE AFTER THE OTHER, NOT IN TWO COLUMNS, and that is not
laziness: a Russian reply and a JSON argument in a 40-character column are
unreadable, and what the reader wants is not «side by side» but «what changed».
So a difference block follows the two tapes — hop by hop, the judge, the calls,
the answer — and it is the thing two tapes are opened for.
"""
import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from bench.agentpii4.compare import ObservedCall
from bench.agentpii4.schema import PiiItem
from bench.agentpii5 import records, report
from bench.agentpii5.contracts import ArmRunV5, CaseV5, HopObservation, JudgeRow

# What stands in a masked span the run replaced and no declared item claims.
# Printed rather than guessed: the span is evidence the gateway acted, and a
# microscope that silently rendered the original text there would show a
# message the model never read.
UNCLAIMED_SPAN: str = "«‹замена без объявленного значения›»"
# How much of a long value or reply one line of the tape carries. The tape is
# read in a terminal; a 4 KiB tool result on one line is a tape nobody scrolls.
WIDTH: int = 300


class MicroscopeError(ValueError):
    """A case the run does not hold, or a directory that is not a run.

    Named rather than printed empty: «нет такого случая» and «нет такого
    прогона» send a reader to different places, and a microscope that printed
    an empty tape for both would send them to neither.
    """


# --- reading one tape ---------------------------------------------------------------------

@dataclass(frozen=True)
class Tape:
    """Everything one run recorded about ONE (case, repeat) of the gateway arm.

    `judge` is None when the run asked no judge of this answer (`--no-judge`,
    or a triple that never reached one) and that is printed as such: a missing
    verdict is not a verdict of «верно».
    """

    run_dir: Path
    run_id: str
    case: CaseV5
    run: ArmRunV5
    hops: tuple[HopObservation, ...]
    judge: JudgeRow | None
    triple: dict[str, object] | None


def _judge_rows(run_dir: Path, run_id: str) -> list[JudgeRow]:
    """The judge's rows of a run, the calibration stamp in row 0 skipped.

    The stamp is recognised the way `report.judge_half` recognises it — by the
    `calibrated` key — so the two readers cannot disagree about which row is
    the stamp and start counting it as a verdict.
    """
    path = records.run_file(run_dir, run_id, "<run>.judge.jsonl")
    if not path.exists():
        return []
    rows = records.read_rows(path)
    body = rows[1:] if rows and "calibrated" in rows[0] else rows
    return [records.judge_row_from_json(row) for row in body]


def _rows_of(run_dir: Path, run_id: str, name: str) -> list[dict[str, object]]:
    path = records.run_file(run_dir, run_id, name)
    return records.read_rows(path) if path.exists() else []


@dataclass(frozen=True)
class RunFiles:
    """One run directory, read ONCE.

    Every tape needs the corpus, the arm rows, the hops, the judge and the
    triples, and a `--run` with three repeats asked for them three times: the
    v5 corpus snapshot is tens of megabytes, so «read per tape» is «parse the
    corpus three times to print one case». The files are read here and sliced
    per (case, repeat) below.
    """

    run_dir: Path
    run_id: str
    cases: dict[str, CaseV5]
    arms: tuple[dict[str, object], ...]
    hops: tuple[HopObservation, ...]
    judge: tuple[JudgeRow, ...]
    triples: tuple[dict[str, object], ...]


def open_run(run_dir: Path) -> RunFiles:
    """Every file of one run the microscope reads, through the readers that own
    them.

    The arm rows come through `records.merged_v5_records`, which lets a
    COMPLETED row beat a resumed one — the rule the report scores by. Reading
    the one line that mentions the case would be faster and would show
    whichever attempt was written last, which is not the attempt the numbers
    were made of.
    """
    run_id = report.run_id_of(run_dir)
    hops = tuple(records.hop_observation_from_json(row)
                 for row in _rows_of(run_dir, run_id, "<run>.hops.jsonl"))
    return RunFiles(run_dir=run_dir, run_id=run_id, cases=report.v5_cases(run_dir),
                    arms=tuple(records.merged_v5_records(run_dir)), hops=hops,
                    judge=tuple(_judge_rows(run_dir, run_id)),
                    triples=tuple(_rows_of(run_dir, run_id, "<run>.triples.jsonl")))


def case_of(files: RunFiles, case_id: str) -> CaseV5:
    """The case, or a refusal that names the CORPUS.

    Asked BEFORE the repeats, and that order is the whole point: without it an
    unknown id falls through to the arm lookup and is refused with «нет плеча с
    повтором 0; записаны повторы ни одного», which is true and sends the reader
    to look for a repeat of a case that does not exist.
    """
    case = files.cases.get(case_id)
    if case is None:
        raise MicroscopeError(
            f"{files.run_dir}: случая {case_id!r} нет в corpus.v5.json этого прогона "
            f"({len(files.cases)} случаев)")
    return case


def repeats_in(files: RunFiles, case_id: str) -> list[int]:
    """Every repeat of this case the run recorded a gateway arm for."""
    found = {int(row["repeat"]) for row in files.arms
             if row.get("case_id") == case_id and isinstance(row.get("repeat"), int)}
    return sorted(found)


def tape_of(files: RunFiles, case: CaseV5, repeat: int) -> Tape:
    """One (case, repeat) sliced out of the files already read."""
    case_id = case.base.id
    rows = [row for row in files.arms
            if row.get("case_id") == case_id and row.get("repeat") == repeat]
    if not rows:
        raise MicroscopeError(
            f"{files.run_dir}: у случая {case_id!r} нет плеча с повтором {repeat}; "
            f"записаны повторы {repeats_in(files, case_id) or 'ни одного'}")
    return Tape(
        run_dir=files.run_dir, run_id=files.run_id, case=case,
        run=records.arm_v5_from_record(rows[0]),
        hops=tuple(one for one in files.hops
                   if one.case_id == case_id and one.repeat == repeat),
        judge=next((one for one in files.judge
                    if one.case_id == case_id and one.repeat == repeat), None),
        triple=next((row for row in files.triples
                     if row.get("case_id") == case_id and row.get("repeat") == repeat), None))


def read_tape(run_dir: Path, case_id: str, repeat: int) -> Tape:
    """One tape, for a caller that holds nothing but the directory."""
    files = open_run(run_dir)
    return tape_of(files, case_of(files, case_id), repeat)


def repeats_of(run_dir: Path, case_id: str) -> list[int]:
    """Every recorded repeat of one case, for a caller that holds nothing but
    the directory."""
    files = open_run(run_dir)
    # `case_of` first, for its refusal: an id the corpus does not hold must be
    # named as a missing CASE, not answered with an empty list of repeats.
    return repeats_in(files, case_of(files, case_id).base.id)


# --- what the model was shown ---------------------------------------------------------------

def _items_in_message(case: CaseV5, index: int) -> list[PiiItem]:
    return [item for item in case.base.pii
            if item.where.kind == "message" and item.where.msg == index]


def shown_message(case: CaseV5, run: ArmRunV5, index: int) -> tuple[str, list[str]]:
    """The message as the MODEL read it, and what to say about it.

    Built by putting each substitute into the span the run says the gateway
    replaced, right to left so an earlier replacement cannot move a later
    offset. A message carried by reference and never hydrated (a licensed
    source) has no text in the run directory, and that is said rather than
    rendered as an empty message.
    """
    message = case.base.messages[index]
    if message.source is not None and not message.content:
        return ("‹текст не в прогоне: сообщение несёт лицензированный источник›", [])
    text = message.content
    spans = sorted(run.base.masked_spans.get(index, ()))
    items = _items_in_message(case, index)
    by_span = {(item.where.start, item.where.end): item for item in items}
    notes: list[str] = []
    for start, end in reversed(spans):
        item = by_span.get((start, end))
        if item is None:
            text = text[:start] + UNCLAIMED_SPAN + text[end:]
            notes.append(f"замена [{start}:{end}] не совпала ни с одним объявленным значением")
            continue
        surface = run.base.substitutes.get(item.id)
        shown = surface[0] if surface is not None else UNCLAIMED_SPAN
        text = text[:start] + shown + text[end:]
        notes.append(f"{item.id} {item.type} «{item.value}» → «{shown}»")
    for item in items:
        if (item.where.start, item.where.end) not in set(spans):
            notes.append(f"УТЕЧКА: {item.id} {item.type} «{item.value}» — модель прочитала "
                         f"настоящее значение, гейтвей этот отрезок не заменял")
    return text, notes


def _short(value: object, width: int) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= width else text[:width - 1] + "…"


def _json(value: object, width: int) -> str:
    return _short(json.dumps(value, ensure_ascii=False, sort_keys=True), width)


def _call_lines(call: ObservedCall, width: int) -> list[str]:
    out = [f"   вызов {call.seq} · {call.name}",
           f"     написано:      {_json(call.written, width)}",
           f"     восстановлено: {_json(call.restored, width)}"]
    if call.residual:
        out.append(f"     ПОДМЕНА ДОШЛА ДО ИНСТРУМЕНТА: {_json(call.residual, width)}")
    if call.refusal_rule:
        out.append(f"     инструмент отказал: {call.refusal_rule} ({call.refusal_path})")
    return out


def _hop_name(hop: HopObservation) -> str:
    where = hop.hop.tool_name or "—"
    path = hop.hop.path or "—"
    return (f"#{hop.hop.hop_index:>3} {hop.hop.kind + '/' + hop.hop.owner:14}{hop.hop.item_id:5} "
            f"ход {hop.hop.turn} {where}:{path}")


def _hop_reading(hop: HopObservation, width: int) -> str:
    """The observer's own reading of one crossing.

    «получено» / «сверено с» rather than «написано» / «эталон», because the two
    sides swap direction with the hop: on an IN hop the arm produced the
    SUBSTITUTE and it is compared with the real value, on an OUT hop it
    produced the RESTORED value and it is compared with the substitute the
    agent wrote. One pair of words that is true both ways beats two that are
    each true half the time.
    """
    verdict = "—"
    if hop.verdict is not None:
        verdict = "форма совпала" if hop.verdict.same else (
            "форма разошлась: " + ", ".join(sorted(hop.verdict.differs)))
    return (f"{hop.status:9} {hop.pii_type:6} получено «{_short(hop.produced, width)}» · "
            f"сверено с «{_short(hop.reference, width)}» · {verdict}")


def render_tape(tape: Tape, width: int) -> list[str]:
    """One tape, in the order the conversation happened."""
    case = tape.case
    run = tape.run
    out = [f"=== {case.base.id}|{run.base.repeat} · {tape.run_dir} (прогон {tape.run_id}) ===",
           f"   семья {case.base.kind} · регистр {case.base.register} · "
           f"поведение {case.behaviour} · вертикаль {case.base.provenance.corpus} · "
           f"завершение {run.base.termination} · потоковый {'да' if case.streaming else 'нет'}",
           "", "   --- что показали модели ---"]
    for index, message in enumerate(case.base.messages):
        text, notes = shown_message(case, run, index)
        out.append(f"   [{index}] {message.role}: {_short(text, width)}")
        out += [f"       {note}" for note in notes]
    if run.tool_results:
        out += ["", "   --- что вернулось модели из инструментов ---"]
    for result in run.tool_results:
        out.append(f"   [рез {result.seq}] {result.tool_name} ход {result.turn} "
                   f"форма {result.return_form}"
                   + ("  (вынужденный)" if result.forced else ""))
        out.append(f"     модели:        {_short(result.text_masked, width)}")
        out.append(f"     на самом деле: {_short(result.text_real, width)}")
    out += ["", "   --- что написала модель ---"]
    if not run.base.calls:
        out.append("   вызовов нет")
    for call in run.base.calls:
        out += _call_lines(call, width)
    out.append(f"   ответ как написан (подмены в нём): {_short(run.reply_raw, width)}")
    out.append(f"   ответ как читает клиент:           {_short(run.base.reply, width)}")
    if run.turn_residual:
        out.append(f"   подмена стояла в {run.turn_residual} более ранних ходах ответа")
    out += ["", "   --- хопы: объявлено и прочитано ---"]
    read = {hop.hop.hop_index: hop for hop in tape.hops if hop.declared}
    for hop in case.hops:
        seen = read.get(hop.hop_index)
        label = (f"   #{hop.hop_index:>3} {hop.kind + '/' + hop.owner:14}{hop.item_id:5} "
                 f"ход {hop.turn} {hop.tool_name or '—'}:{hop.path or '—'}"
                 + ("  (необязательный)" if hop.optional else ""))
        if seen is None:
            out.append(f"{label}  ДЫРА: наблюдатель не записал этот хоп в <run>.hops.jsonl")
            continue
        out.append(f"{label}  {_hop_reading(seen, width)}")
    extra = [hop for hop in tape.hops if not hop.declared]
    if extra:
        out.append("   хопы, которых случай не объявлял (агент перенёс значение сам):")
        out += [f"     {_hop_name(hop)}  {_hop_reading(hop, width)}" for hop in extra]
    out += ["", "   --- судья ---"]
    if tape.judge is None:
        out.append("   вердикта нет: судья этот ответ не смотрел (прогон без судьи или "
                   "тройка до него не дошла) — это НЕ «верно»")
    else:
        verdict = tape.judge.verdict
        out.append(f"   {verdict.label or '—'} · вынес {verdict.judged_by} · "
                   f"${verdict.cost_usd:.4f}")
        out.append(f"   цитата: {_short(verdict.reason, width)}")
    if tape.triple is not None:
        # The judge's share comes through `records.triple_totals_from_json`,
        # which refuses a missing or negative field by name: a tape that
        # printed «судья: $0.00» for a triple whose row never carried the key
        # would say the same thing as a run that asked no judge.
        totals = records.triple_totals_from_json(tape.triple)
        out.append(f"   тройка: статус {tape.triple.get('status')} · "
                   f"судья ${totals.judge_cost_usd:.4f}")
    return out


# --- two tapes ---------------------------------------------------------------------------

def _hop_key(hop: HopObservation) -> tuple[int, str, str, str]:
    return (hop.hop.hop_index, hop.hop.kind, hop.hop.owner, hop.hop.item_id)


def differences(a: Tape, b: Tape, width: int) -> list[str]:
    """What the two runs did differently on this one case.

    Hop by hop first, because that is where a gateway change shows; then the
    judge, the calls and the answer. A hop one run recorded and the other did
    not is NAMED — a difference that consists of a missing observation is still
    a difference, and the tempting reading («both clean») is the one this
    benchmark exists to refuse.
    """
    out = [f"=== что изменилось: A {a.run_dir} → B {b.run_dir} ==="]
    a_hops = {_hop_key(hop): hop for hop in a.hops}
    b_hops = {_hop_key(hop): hop for hop in b.hops}
    moved = 0
    for key in sorted(set(a_hops) | set(b_hops)):
        left, right = a_hops.get(key), b_hops.get(key)
        if left is None or right is None:
            moved += 1
            side = "B" if left is not None else "A"
            present = left if left is not None else right
            out.append(f"   {_hop_name(present)}: строки нет в {side}")
            continue
        if (left.status, left.produced, None if left.verdict is None else left.verdict.differs) == (
                right.status, right.produced,
                None if right.verdict is None else right.verdict.differs):
            continue
        moved += 1
        out.append(f"   {_hop_name(left)}")
        out.append(f"     A: {_hop_reading(left, width)}")
        out.append(f"     B: {_hop_reading(right, width)}")
    if not moved:
        out.append("   хопы: ни один статус, ни одно написанное значение, ни одна форма "
                   "не изменились")
    a_label = "—" if a.judge is None else (a.judge.verdict.label or "—")
    b_label = "—" if b.judge is None else (b.judge.verdict.label or "—")
    out.append(f"   судья: A {a_label} → B {b_label}"
               + ("" if a_label != b_label else " (без изменений)"))
    a_calls = [call.name for call in a.run.base.calls]
    b_calls = [call.name for call in b.run.base.calls]
    out.append(f"   вызовы: A {a_calls or '—'} → B {b_calls or '—'}"
               + ("" if a_calls != b_calls else " (без изменений)"))
    out.append("   ответ клиенту: " + ("тот же текст" if a.run.base.reply == b.run.base.reply
                                       else f"A «{_short(a.run.base.reply, width)}» → "
                                            f"B «{_short(b.run.base.reply, width)}»"))
    return out


def tapes(run_dirs: Sequence[Path], case_id: str, repeat: int | None,
          width: int) -> list[str]:
    """The tapes of one case in one or two runs, and the difference block when
    there are two."""
    out: list[str] = []
    read: list[Tape] = []
    for run_dir in run_dirs:
        files = open_run(run_dir)
        case = case_of(files, case_id)
        wanted = repeats_in(files, case_id) if repeat is None else [repeat]
        if not wanted:
            raise MicroscopeError(f"{run_dir}: случай {case_id!r} есть в корпусе прогона, "
                                  f"а плеча ни одного повтора не записано")
        for one in wanted:
            tape = tape_of(files, case, one)
            read.append(tape)
            out += render_tape(tape, width) + [""]
    if len(run_dirs) == 2 and len(read) == 2:
        out += differences(read[0], read[1], width)
    elif len(run_dirs) == 2:
        out.append(f"=== блок различий не печатается: повторов {len(read)}, а не два; "
                   f"назовите повтор через --repeat ===")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case_id", help="id случая")
    parser.add_argument("--run", type=Path, action="append", required=True,
                        help="каталог прогона; дважды — две ленты и блок различий")
    parser.add_argument("--repeat", type=int, default=None,
                        help="один повтор; по умолчанию все записанные")
    parser.add_argument("--width", type=int, default=WIDTH, help="длина строки ленты")
    args = parser.parse_args()
    if len(args.run) > 2:
        parser.error("две ленты — это две: --run можно передать один или два раза")
    try:
        lines = tapes(args.run, args.case_id, args.repeat, args.width)
    # `report.ReportError` too: a directory with no `corpus.v5.json` and no
    # `*.arms.jsonl` is refused by the readers that own those files, and a
    # traceback would tell the reader their tool is broken when their path is.
    except (MicroscopeError, report.ReportError) as error:
        print(f"микроскоп отказал: {error}")
        return 2
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
