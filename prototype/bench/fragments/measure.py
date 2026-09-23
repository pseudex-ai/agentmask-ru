"""Бегун Б29: числа по КЛЕТКАМ, а не одно среднее, и дамп провалов с точным листом.

Клетка — это (сторона × поверхность × область × наполненность). Среднее по этим
осям бессмысленно: на пустом волте дефект не воспроизводится вовсе, на плече
без разговора он молчит, а на плече с разговором — кричит ложной тревогой, и
одно число спрятало бы все три факта разом.

НАПОЛНЕННОСТЬ МЕРИТСЯ НА ОДНОМ РАСТУЩЕМ ВОЛТЕ, а не на трёх разных: у
заказчика волт именно растёт, и «1, 10, 50 диалогов» — это три снимка одного
хранилища, а не три независимых мира.

    cd prototype && source .venv/bin/activate
    python3 -m bench.fragments.measure
    python3 -m bench.fragments.measure --fills 1,10 --dump 10
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from bench.fragments.cases import (
    CORPUS, Case, Piece, background_seeds, digits, forge_foreign,
)
from bench.fragments.engine import (
    Engine, Minted, SubstituteCoincided, workspace,
)
from bench.fragments.surfaces import (
    SIDE_FOREIGN, SIDE_OURS, Passage, Returned, Scope, Surface, available,
)

NOTE_FAKE_STOOD = "подмена устояла"
NOTE_THIRD_VALUE = "третье значение"
NOTE_MISSING = "поля нет в ответе"
NOTE_FALSE_ALARM = "ложная тревога"


@dataclass(frozen=True)
class ScopeSpec:
    """Область, в которой шлюз задаёт вопрос о принадлежности куска."""

    name: str
    short: str
    names_conversation: bool
    pseudonym_scope: str


SCOPES: tuple[ScopeSpec, ...] = (
    ScopeSpec("разговор назван", "назван", True, "conversation"),
    ScopeSpec("разговор не назван", "не назван", False, "conversation"),
    ScopeSpec("память агента", "память", True, "customer"),
)


@dataclass(frozen=True)
class Verdict:
    """Приговор по ОДНОМУ куску одного случая на одной поверхности в одной клетке."""

    case_id: str
    family: str
    form: str
    surface: str
    scope: str
    fill: int
    repeat: int
    side: str
    label: str
    field: str
    written: str
    came_back: str
    ok: bool
    silent: bool
    collides: bool
    note: str


def _fields_of(returned: Returned) -> Mapping[str, str]:
    return dict(returned.fields)


def _digit_match(value: str, accepted: Sequence[str]) -> bool:
    body = digits(value)
    if not body:
        return False
    return any(digits(one) == body for one in accepted if digits(one))


def _ours_in_field(value: str, piece: Piece) -> bool:
    """Наше вернулось, если поле несёт настоящее значение в ЛЮБОМ принятом написании.

    Широко, а не узко, и намеренно: узкий список объявил бы поломкой законную
    форму, которую движок имеет право выбрать (агентская форма, согласование,
    ведущий ноль). Прибор, кричащий волк, стоит ровно столько же, сколько
    слепой, — урок v4 про транслит.
    """
    return value in piece.accepted or _digit_match(value, piece.accepted)


def _ours_in_prose(prose: str, piece: Piece) -> bool:
    if any(one in prose for one in piece.accepted):
        return True
    body = digits(prose)
    return any(digits(one) and digits(one) in body for one in piece.accepted)


def _named_in_residual(piece: Piece, residual: Sequence[str]) -> bool:
    """Назвал ли остаток ИМЕННО ЭТОТ кусок.

    ВХОЖДЕНИЕ ПОДСТРОКОЙ НЕ ГОДИТСЯ, и это найдено этим же прибором: в листе
    `{"quantity": "100", "amount": "1000", "article": "100000"}` остаток назвал
    «100», а подстрочная проверка записала ложную тревогу всем трём полям и
    утроила число. Куском владеет тот, кто равен ему целиком.

    Две поблажки, обе по одной причине — движок называет подмену в СВОЕЙ форме,
    а не в той, в которой её переписал агент: равенство по цифрам и равенство по
    последним десяти цифрам (телефон, записанный через 8, несёт те же десять).
    """
    written = digits(piece.written)
    for one in residual:
        if piece.written == one:
            return True
        body = digits(one)
        if written and body == written:
            return True
        if len(written) >= 10 and len(body) >= 10 and written[-10:] == body[-10:]:
            return True
    return False


def _judge(case: Case, piece: Piece, surface: Surface, returned: Returned,
           scope: ScopeSpec, fill: int, repeat: int,
           known_fakes: Sequence[str]) -> Verdict:
    collides = bool(digits(piece.written)) and any(
        digits(piece.written) in digits(fake) for fake in known_fakes)
    named = _named_in_residual(piece, returned.residual)
    if surface.carries_fields:
        fields = _fields_of(returned)
        if piece.field not in fields:
            came_back, held, note = "", False, NOTE_MISSING
        else:
            came_back = fields[piece.field]
            if piece.side == SIDE_OURS:
                held = _ours_in_field(came_back, piece)
                note = "" if held else (NOTE_FAKE_STOOD if came_back == piece.written
                                        else NOTE_THIRD_VALUE)
            else:
                held = came_back == piece.written
                note = "" if held else NOTE_THIRD_VALUE
    else:
        came_back = returned.prose
        if piece.side == SIDE_OURS:
            held = _ours_in_prose(came_back, piece)
            note = "" if held else (NOTE_FAKE_STOOD if piece.written in came_back
                                    else NOTE_THIRD_VALUE)
        else:
            held = f"{piece.anchor} {piece.written}" in came_back
            note = "" if held else NOTE_THIRD_VALUE
    if held and piece.side == SIDE_FOREIGN and named:
        # Чужое уцелело, но остаток назвал его нашей подменой: порчи нет, зато
        # шлюз заказчика получил сигнал отказаться от совершенно верного вызова.
        note = NOTE_FALSE_ALARM
    # ТИХИЙ ОТКАЗ СТРАШНЕЕ ВИДИМОГО, и «тихий по построению» — это третье
    # состояние, а не чистая клетка: поверхность, которая не умеет отдавать
    # остаток, обязана печататься слепой.
    silent = not named if surface.reports_residual else True
    return Verdict(
        case_id=case.case_id, family=case.family, form=case.form,
        surface=surface.name, scope=scope.name, fill=fill, repeat=repeat,
        side=piece.side,
        label=piece.label, field=piece.field, written=piece.written,
        came_back=came_back, ok=held and note != NOTE_FALSE_ALARM,
        silent=silent, collides=collides, note=note,
    )


@dataclass(frozen=True)
class Skipped:
    """Клетка, в которой случай не удалось провести, и почему."""

    case_id: str
    surface_free: str
    scope: str
    fill: int
    repeat: int
    reason: str


@dataclass(frozen=True)
class Failure:
    verdict: Verdict
    sheet: str
    answer: str
    residual: tuple[str, ...]


def _sheet(passage: Passage, surface: Surface) -> str:
    return passage.arguments_json() if surface.carries_fields else passage.prose


def _answer(returned: Returned, surface: Surface) -> str:
    if surface.carries_fields:
        return json.dumps(dict(returned.fields), ensure_ascii=False)
    return returned.prose


@dataclass(frozen=True)
class Harvest:
    """Всё, что принёс прогон, включая то, что провести не удалось."""

    verdicts: tuple[Verdict, ...]
    failures: tuple[Failure, ...]
    design: tuple[str, ...]
    skipped: tuple[Skipped, ...]
    attempted: int


def run(engine: Engine, surfaces: Sequence[Surface], fills: Sequence[int],
        repeats: int) -> Harvest:
    """Прогнать корпус по всем клеткам, `repeats` раз на независимых волтах.

    ПОВТОРЫ ЕСТЬ, ПОТОМУ ЧТО ПОДМЕНУ ВЫБИРАЕТ `secrets`. Она не сеется и не
    должна: предсказуемая подмена — это дыра, а не удобство. Значит один прогон
    — это один бросок, и сравнивать четыре конструкции турнира по одному броску
    нельзя: разница между ними утонет в разнице между попаданием и непопаданием
    цифр. Повтор — это другой орг, то есть другой волт с нуля, а не второй
    вопрос к тому же.
    """
    verdicts: list[Verdict] = []
    failures: list[Failure] = []
    design: list[str] = []
    skipped: list[Skipped] = []
    attempted = 0
    for repeat in range(repeats):
        for spec in SCOPES:
            org = (f"b29-{spec.pseudonym_scope}-"
                   f"{'named' if spec.names_conversation else 'derived'}-r{repeat}")
            background: list[str] = []
            filled = 0
            for fill in fills:
                while filled < fill:
                    conversation = f"bg-{filled}" if spec.names_conversation else ""
                    for pair in engine.fill(org, conversation, spec.pseudonym_scope,
                                            background_seeds(filled)):
                        background.append(pair.fake)
                    filled += 1
                numbers = forge_foreign(background)
                design.append(f"повтор {repeat} · {spec.name} · {fill} диалогов · "
                              + " · ".join(numbers.sources))
                for case in CORPUS:
                    conversation = (f"probe-{case.case_id}"
                                    if spec.names_conversation else "")
                    attempted += 1
                    try:
                        minted = engine.mint(org, conversation, spec.pseudonym_scope,
                                             case.seeds)
                    except SubstituteCoincided as coincided:
                        # НЕ ЗЕЛЁНАЯ, А ОТСУТСТВУЮЩАЯ. Пропуск печатается
                        # отдельным разделом, а доля пропусков сверяется с
                        # порогом: систематический пропуск — это сломанное
                        # обнаружение, а не редкая монета.
                        skipped.append(Skipped(
                            case_id=case.case_id, surface_free="все",
                            scope=spec.name, fill=fill, repeat=repeat,
                            reason=str(coincided)))
                        continue
                    by_role: dict[str, Minted] = {pair.role: pair for pair in minted}
                    written = case.write(by_role, numbers)
                    known = tuple(background) + tuple(pair.fake for pair in minted)
                    scope = Scope(name=spec.name, conversation_id=conversation,
                                  pseudonym_scope=spec.pseudonym_scope)
                    for surface in surfaces:
                        returned = surface.carry(org, written.passage, scope)
                        for piece in written.pieces:
                            verdict = _judge(case, piece, surface, returned, spec,
                                             fill, repeat, known)
                            verdicts.append(verdict)
                            if not verdict.ok:
                                failures.append(Failure(
                                    verdict=verdict,
                                    sheet=_sheet(written.passage, surface),
                                    answer=_answer(returned, surface),
                                    residual=returned.residual,
                                ))
    return Harvest(verdicts=tuple(verdicts), failures=tuple(failures),
                   design=tuple(design), skipped=tuple(skipped), attempted=attempted)


def _chosen(verdicts: Sequence[Verdict], side: str, surface: str, scope: str,
            fill: int) -> tuple[Verdict, ...]:
    return tuple(one for one in verdicts if one.side == side and one.surface == surface
                 and one.scope == scope and one.fill == fill)


def _header(surfaces: Sequence[Surface], fills: Sequence[int], title: str) -> None:
    print()
    print(title)
    head = f"  {'поверхность':<12}{'область':<22}"
    for fill in fills:
        head += f"{'диалогов ' + str(fill):>26}"
    print(head)


def _table_ours(verdicts: Sequence[Verdict], surfaces: Sequence[Surface],
                fills: Sequence[int]) -> None:
    """Потеряно / всего, и сколько из потерь МОЛЧИТ.

    Тихая потеря печатается отдельно, а не растворяется в общей доле: видимый
    отказ шлюз заказчика может перехватить по `residual_tokens`, а тихий уезжает
    в инструмент с двумястами и пустым списком.
    """
    _header(surfaces, fills, "СТОРОНА 1 — НАШЕ НЕ ВЕРНУЛОСЬ (фейк доехал до инструмента)")
    for surface in surfaces:
        for spec in SCOPES:
            row = f"  {surface.name:<12}{spec.name:<22}"
            for fill in fills:
                chosen = _chosen(verdicts, SIDE_OURS, surface.name, spec.name, fill)
                bad = [one for one in chosen if not one.ok]
                silent = [one for one in bad if one.silent]
                row += f"{f'{len(bad)}/{len(chosen)} (молча {len(silent)})':>26}"
            print(row)


def _table_foreign(verdicts: Sequence[Verdict], surfaces: Sequence[Surface],
                   fills: Sequence[int]) -> None:
    """Переписано / всего, и сколько из переписанного пришлось на СТОЛКНУВШИЕСЯ числа.

    Разделено по столкновению, потому что так проверяется сам замысел корпуса:
    если бы переписывались и чистые числа наравне со столкнувшимися, дефект был
    бы не арифметическим, а каким-то другим, и правку выбирали бы не ту.
    """
    _header(surfaces, fills,
            "СТОРОНА 2 — ЧУЖОЕ ПЕРЕПИСАНО (порча данных в CRM заказчика, всегда молча)")
    for surface in surfaces:
        for spec in SCOPES:
            row = f"  {surface.name:<12}{spec.name:<22}"
            for fill in fills:
                chosen = _chosen(verdicts, SIDE_FOREIGN, surface.name, spec.name, fill)
                bad = [one for one in chosen if one.note == NOTE_THIRD_VALUE
                       or one.note == NOTE_MISSING]
                hit = [one for one in bad if one.collides]
                row += f"{f'{len(bad)}/{len(chosen)} (⊂ подмены {len(hit)})':>26}"
            print(row)


def _table_false_alarm(verdicts: Sequence[Verdict], surfaces: Sequence[Surface],
                       fills: Sequence[int]) -> None:
    """Чужое уцелело, но остаток объявил его нашей подменой.

    Не порча и не потеря — цена в третьей валюте: шлюз заказчика получает повод
    отказаться от совершенно верного вызова. Предшественники мерили ТОЛЬКО это.
    """
    _header(surfaces, fills,
            "СТОРОНА 2bis — ЛОЖНАЯ ТРЕВОГА (чужое цело, но остаток назвал его нашим)")
    for surface in surfaces:
        for spec in SCOPES:
            row = f"  {surface.name:<12}{spec.name:<22}"
            for fill in fills:
                chosen = _chosen(verdicts, SIDE_FOREIGN, surface.name, spec.name, fill)
                alarms = [one for one in chosen if one.note == NOTE_FALSE_ALARM]
                row += f"{f'{len(alarms)}/{len(chosen)}':>26}"
            print(row)


def _columns(surfaces: Sequence[Surface]) -> tuple[tuple[str, str, str], ...]:
    return tuple((surface.name, spec.name, spec.short)
                 for surface in surfaces for spec in SCOPES)


def _case_head(surfaces: Sequence[Surface], fill: int, title: str) -> None:
    print()
    print(f"{title} · на {fill} диалогах, по типу и форме (пустые строки опущены)")
    head = f"  {'случай':<32}{'форма':<28}"
    for surface_name, _scope, short in _columns(surfaces):
        head += f"{surface_name[:4] + '/' + short:>16}"
    print(head)


def _by_case_ours(verdicts: Sequence[Verdict], surfaces: Sequence[Surface],
                  fill: int) -> None:
    _case_head(surfaces, fill, "СТОРОНА 1 · потеряно/всего")
    for case in CORPUS:
        cells: list[str] = []
        for surface_name, scope_name, _short in _columns(surfaces):
            chosen = [one for one in _chosen(verdicts, SIDE_OURS, surface_name,
                                             scope_name, fill)
                      if one.case_id == case.case_id]
            if not chosen:
                cells.append("—")
                continue
            bad = [one for one in chosen if not one.ok]
            cells.append(f"{len(bad)}/{len(chosen)}")
        if all(cell == "—" or cell.startswith("0/") for cell in cells):
            continue
        row = f"  {case.case_id:<32}{case.form:<28}"
        for cell in cells:
            row += f"{cell:>16}"
        print(row)


def _by_case_foreign(verdicts: Sequence[Verdict], surfaces: Sequence[Surface],
                     fill: int) -> None:
    """Переписано + ложных тревог / всего.

    Две цифры, а не одна: порча данных и напрасный отказ стоят заказчику
    разного, и клетка «1/1» скрыла бы, какая из двух бед произошла.
    """
    _case_head(surfaces, fill,
               "СТОРОНА 2 · переписано + ложных тревог / всего")
    for case in CORPUS:
        cells: list[str] = []
        for surface_name, scope_name, _short in _columns(surfaces):
            chosen = [one for one in _chosen(verdicts, SIDE_FOREIGN, surface_name,
                                             scope_name, fill)
                      if one.case_id == case.case_id]
            if not chosen:
                cells.append("—")
                continue
            rewritten = [one for one in chosen
                         if one.note in (NOTE_THIRD_VALUE, NOTE_MISSING)]
            alarms = [one for one in chosen if one.note == NOTE_FALSE_ALARM]
            cells.append(f"{len(rewritten)}+{len(alarms)}/{len(chosen)}")
        if all(cell == "—" or cell.startswith("0+0/") for cell in cells):
            continue
        row = f"  {case.case_id:<32}{case.form:<28}"
        for cell in cells:
            row += f"{cell:>16}"
        print(row)


def _dump(failures: Sequence[Failure], limit: int) -> None:
    print()
    print(f"ДАМП ПРОВАЛОВ · {len(failures)} всего, печатается до {limit}")
    for failure in failures[:limit]:
        one = failure.verdict
        silence = "МОЛЧА" if one.silent else "видно по остатку"
        collision = "цифры ⊂ подмены" if one.collides else "без столкновения"
        print()
        print(f"  [{one.side}] {one.case_id} · {one.surface} · {one.scope} · "
              f"{one.fill} диалогов · {silence} · {collision}")
        print(f"    кусок     : {one.label} (поле {one.field}) — {one.note}")
        print(f"    написано  : {one.written!r}")
        print(f"    вернулось : {one.came_back!r}")
        print(f"    лист      : {failure.sheet}")
        print(f"    ответ     : {failure.answer}")
        print(f"    остаток   : {list(failure.residual)}")
    if len(failures) > limit:
        print(f"\n  … ещё {len(failures) - limit}; полный список — --dump {len(failures)}")


def _spread(verdicts: Sequence[Verdict], repeats: int) -> None:
    """Итог каждого повтора отдельно: сколько одна и та же клетка гуляет от броска к броску."""
    print()
    print("РАЗБРОС ПО ПОВТОРАМ (один прогон — один бросок `secrets`)")
    print(f"  {'повтор':<10}{'наше не вернулось':>22}{'чужое переписано':>22}"
          f"{'ложных тревог':>20}")
    for repeat in range(repeats):
        taken = [one for one in verdicts if one.repeat == repeat]
        ours = [one for one in taken if one.side == SIDE_OURS]
        alien = [one for one in taken if one.side == SIDE_FOREIGN]
        lost = len([one for one in ours if not one.ok])
        rewritten = len([one for one in alien
                         if one.note in (NOTE_THIRD_VALUE, NOTE_MISSING)])
        alarms = len([one for one in alien if one.note == NOTE_FALSE_ALARM])
        print(f"  {repeat:<10}{f'{lost}/{len(ours)}':>22}"
              f"{f'{rewritten}/{len(alien)}':>22}{f'{alarms}/{len(alien)}':>20}")


def _skipped(harvest: Harvest) -> None:
    """Клетки, в которых случай не проводился — и порог, за которым это не монета."""
    print()
    share = len(harvest.skipped) / harvest.attempted if harvest.attempted else 0.0
    print(f"НЕ ИЗМЕРЕНО · {len(harvest.skipped)} из {harvest.attempted} "
          f"проведённых случаев ({share:.1%})")
    for one in harvest.skipped:
        print(f"  повтор {one.repeat} · {one.scope} · {one.fill} диалогов · "
              f"{one.case_id}: {one.reason}")
    if share > 0.02:
        raise SystemExit(
            f"пропущено {share:.1%} случаев — это уже не совпадение подмены с "
            f"настоящим значением, а сломанное обнаружение; числа ниже не печатаются")


def _traits(surfaces: Sequence[Surface]) -> None:
    print()
    print("ПОВЕРХНОСТИ ЭТОГО ПРОГОНА")
    print(f"  {'имя':<14}{'поля':<8}{'проза':<8}{'отдаёт остаток':<18}"
          f"{'слышит conversation_id'}")
    for surface in surfaces:
        print(f"  {surface.name:<14}{str(surface.carries_fields):<8}"
              f"{str(surface.carries_prose):<8}{str(surface.reports_residual):<18}"
              f"{surface.honours_conversation_id}")
    missing = {"stream", "proxy"} - {surface.name for surface in surfaces}
    if missing:
        print(f"  НЕ ПОДКЛЮЧЕНЫ: {', '.join(sorted(missing))} — "
              f"их клетки в таблицах отсутствуют, а не чисты (см. README, шов)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fills", default="1,10,50",
                        help="наполненность волта в диалогах, через запятую")
    parser.add_argument("--dump", type=int, default=40,
                        help="сколько провалов печатать с точным листом")
    parser.add_argument("--repeats", type=int, default=3,
                        help="сколько независимых волтов пройти: подмену выбирает "
                             "secrets, и один прогон — это один бросок")
    options = parser.parse_args()
    fills = tuple(int(one) for one in options.fills.split(","))
    if sorted(fills) != list(fills):
        raise SystemExit("--fills должен идти по возрастанию: волт растёт, а не скачет")

    engine = Engine(workspace())
    engine.start()
    try:
        surfaces = available(engine)
        _traits(surfaces)
        harvest = run(engine, surfaces, fills, options.repeats)
    finally:
        engine.stop()

    verdicts, failures = harvest.verdicts, harvest.failures
    print()
    print("КАК ПОСТРОЕНО СТОЛКНОВЕНИЕ (цифры взяты из середины выданных подмен)")
    for line in harvest.design:
        print(f"  {line}")
    _skipped(harvest)

    _table_ours(verdicts, surfaces, fills)
    _table_foreign(verdicts, surfaces, fills)
    _table_false_alarm(verdicts, surfaces, fills)
    _spread(verdicts, options.repeats)
    _by_case_ours(verdicts, surfaces, fills[-1])
    _by_case_foreign(verdicts, surfaces, fills[-1])
    _dump(failures, options.dump)

    ours = [one for one in verdicts if one.side == SIDE_OURS]
    ours_bad = [one for one in ours if not one.ok]
    alien = [one for one in verdicts if one.side == SIDE_FOREIGN]
    rewritten = [one for one in alien if one.note in (NOTE_THIRD_VALUE, NOTE_MISSING)]
    alarms = [one for one in alien if one.note == NOTE_FALSE_ALARM]
    print()
    print(f"ИТОГО · наше не вернулось {len(ours_bad)}/{len(ours)} "
          f"(молча {len([one for one in ours_bad if one.silent])}) · "
          f"чужое переписано {len(rewritten)}/{len(alien)} · "
          f"ложных тревог {len(alarms)}/{len(alien)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
