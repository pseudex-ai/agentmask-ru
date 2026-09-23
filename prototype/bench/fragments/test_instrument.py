"""ПРИЁМКА САМОГО ПРИБОРА: он обязан УМЕТЬ ПРОВАЛИТЬСЯ, и провалиться там, где надо.

    cd prototype && source .venv/bin/activate
    python3 -m bench.fragments.test_instrument
    python3 -m bench.fragments.test_instrument --fill 10   # тот же лист на полном волте

Две половины, и поодиночке ни одна ничего не стоит:

  * ПРАВИЛЬНЫЙ шлюз (`_perfect`) обязан напечатать нули на ВСЕХ шести строках —
    иначе прибор кричит волком и его числа нельзя предъявить турниру;
  * ПЯТЬ НЕПРАВИЛЬНЫХ шлюзов обязаны провалить каждый СВОЮ строку и НЕ ТРОГАТЬ
    чужие — иначе прибор различает «что-то где-то изменилось», а это не прибор.

ПОЧЕМУ ШЛЮЗЫ ПОДДЕЛЬНЫЕ, А ЧЕКАНКА НАСТОЯЩАЯ. Подделывается ровно ответ на
вопрос «этот кусок — моя подмена?» — то есть то, что прибор и меряет. Всё
остальное (обнаружение, чеканка, наполнение волта, построение столкновений)
остаётся продуктовым путём: подделка чеканки была бы второй реализацией
чеканки, и приёмка удостоверяла бы прибор против неё, а не против движка.

ОТКУДА ПОДДЕЛЬНЫЙ ШЛЮЗ ЗНАЕТ, ЧТО «ПРАВИЛЬНО». Писатель случая возвращает
`Written` — куски вместе с `accepted`, то есть с ответом. Приёмка подсматривает
этот `Written` на выходе из писателя (`_recording`), а не разбирает готовый
лист: разбор был бы второй реализацией корпуса, и его ошибки легли бы на прибор.
Поддельный шлюз получается всеведущим, и так и задумано — он не модель движка,
он ЛИНЕЙКА, по которой проверяется, что приговор читает то, что называет.

ПЯТЫЙ ШЛЮЗ — НЕ УКРАШЕНИЕ. Задача называет четыре, но валют у прибора ТРИ:
потеря, порча и напрасная тревога. Строку, которую не может сдвинуть ни одна
подделка, невозможно провалить — ровно та болезнь, из-за которой v4 напечатал
18 из 18. Поэтому есть `тревога-на-чужое`, а `test_every_line_is_claimed`
требует, чтобы у каждой строки нашёлся свой обвинитель.

ЖИВЫЕ ПОВЕРХНОСТИ ИДУТ В ТОМ ЖЕ ПРОГОНЕ. Настоящие четыре ручки прогоняются по
тому же корпусу — не ради их чисел (за ними `measure.py`), а ради двух
утверждений, которые иначе никто не проверяет: поток и прокси НЕ ТЕРЯЮТ ТЕКСТ
САМИ, и заголовок прокси `X-Pseudex-Residual` шевелится, то есть его слепота —
слепота к АДРЕСАТУ отказа, а не к самому отказу.
"""

import argparse
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

from bench.fragments import measure as runner
from bench.fragments.cases import CORPUS, Case, Foreign, Piece, Written
from bench.fragments.engine import Engine, Minted, workspace
from bench.fragments.measure import (
    NOTE_FALSE_ALARM, NOTE_MISSING, NOTE_THIRD_VALUE, Verdict,
)
from bench.fragments.surfaces import (
    SIDE_FOREIGN, SIDE_OURS, Passage, Returned, Scope, Surface, available,
)

# Поверхности, которые обязаны стоять в таблице.
REQUIRED_SURFACES: tuple[str, ...] = ("argument", "prose", "stream", "proxy")
# Огранки поддельного шлюза: одна читается по полям, другая по прозе.
FLAVOURS: tuple[str, ...] = ("поля", "проза")
# Лист, в котором нашего нет ничего. Без единой цифры и длиннее окна переноса
# движка (64 символа): короче — и поток выродился бы в один закрывающий вызов,
# то есть проверил бы не поток.
NEUTRAL = ("Заказ принят, курьер выедет завтра утром, о времени доставки "
           "сообщим отдельным сообщением.")
NEUTRAL_FIELD = "comment"


# --- линейка: что поддельный шлюз возвращает на месте куска ---------------------------

Restore = Callable[[Piece, Written], str]
Residual = Callable[[Written], tuple[str, ...]]


def _ours_pieces(written: Written) -> tuple[Piece, ...]:
    return tuple(one for one in written.pieces if one.side == SIDE_OURS)


def _is_part_of_a_record(written: Written) -> bool:
    """Запись, РАЗЛОЖЕННАЯ ПО ПОЛЯМ СХЕМЫ: два и больше наших куска в одном вызове.

    Ровно `addr_fields`, `passport_two_fields` и `mixed_address_and_quantity` —
    тот класс, которого предшественники не видели, потому что слали `street` и
    `house` порознь. Признак структурный (сколько кусков вырезано из одной
    подмены), а не список имён полей: список пришлось бы дописывать на каждый
    новый случай, и молча пропущенный случай стал бы зелёной клеткой.
    """
    return len(_ours_pieces(written)) >= 2


def _shift_digits(value: str) -> str:
    """Те же цифры, сдвинутые на единицу: форма сохранена, значение — нет.

    Так Б29 и выглядит в жизни: `{"quantity": "893"} -> "684"` — длина та же,
    поле то же, число чужое. Замена на константу («0000») отличалась бы по форме
    и проверяла бы приговор слабее, чем надо.
    """
    return "".join(str((int(one) + 1) % 10) if one.isdigit() else one for one in value)


def _perfect(piece: Piece, _written: Written) -> str:
    return piece.accepted[0] if piece.side == SIDE_OURS else piece.written


def _restores_nothing(piece: Piece, _written: Written) -> str:
    return piece.written


def _rewrites_foreign_numbers(piece: Piece, _written: Written) -> str:
    if piece.side == SIDE_OURS:
        return piece.accepted[0]
    return _shift_digits(piece.written)


def _whole_substitutes_only(piece: Piece, written: Written) -> str:
    if piece.side == SIDE_FOREIGN:
        return piece.written
    return piece.written if _is_part_of_a_record(written) else piece.accepted[0]


def _says_nothing(_written: Written) -> tuple[str, ...]:
    return ()


def _names_our_survivors(written: Written) -> tuple[str, ...]:
    """Остаток шлюза, который ничего не восстановил: все наши подмены ещё стоят."""
    return tuple(one.written for one in _ours_pieces(written))


def _names_the_customers_numbers(written: Written) -> tuple[str, ...]:
    """Остаток, объявляющий НАШИМИ собственные числа заказчика. Напрасный отказ."""
    return tuple(one.written for one in written.pieces if one.side == SIDE_FOREIGN)


# --- поддельные поверхности ----------------------------------------------------------


class FieldGateway:
    """Поддельный шлюз, отвечающий вызовом инструмента (приговор читается по полям)."""

    carries_fields = True
    carries_prose = False
    reports_residual = True
    honours_conversation_id = True

    def __init__(self, label: str, restore: Restore, residual: Residual,
                 ledger: Mapping[Passage, Written]) -> None:
        self.name = f"{label}/{FLAVOURS[0]}"
        self._restore = restore
        self._residual = residual
        self._ledger = ledger

    def carry(self, _org_id: str, passage: Passage, _scope: Scope) -> Returned:
        # KeyError здесь означает «писателя случая никто не записал», то есть
        # приёмка меряет лист, которого корпус не составлял. Падать, а не
        # подставлять пустое.
        written = self._ledger[passage]
        return Returned(
            surface=self.name,
            fields=tuple((one.field, self._restore(one, written))
                         for one in written.pieces),
            prose="",
            residual=self._residual(written),
        )


class ProseGateway:
    """Тот же шлюз, отвечающий прозой (приговор читается по тексту).

    Обе огранки нужны, потому что приговор у них РАЗНЫЙ: в полях кусок ищется в
    своём поле, в прозе — вхождением в текст. Одна огранка удостоверила бы
    половину приговора и промолчала о второй.
    """

    carries_fields = False
    carries_prose = True
    reports_residual = True
    honours_conversation_id = True

    def __init__(self, label: str, restore: Restore, residual: Residual,
                 ledger: Mapping[Passage, Written]) -> None:
        self.name = f"{label}/{FLAVOURS[1]}"
        self._restore = restore
        self._residual = residual
        self._ledger = ledger

    def carry(self, _org_id: str, passage: Passage, _scope: Scope) -> Returned:
        written = self._ledger[passage]
        return Returned(
            surface=self.name,
            fields=(),
            prose="; ".join(f"{one.anchor} {self._restore(one, written)}"
                            for one in written.pieces),
            residual=self._residual(written),
        )


# --- строки, по которым читается приговор ---------------------------------------------


@dataclass(frozen=True)
class Line:
    """Одна строка отчёта. `total = 0` — это не ноль, а «мерить нечего»."""

    hits: int
    total: int

    @property
    def rate(self) -> float:
        return self.hits / self.total if self.total else 0.0

    def __str__(self) -> str:
        return f"{self.rate:.3f} ({self.hits}/{self.total})"


LOST = "наше не вернулось"
LOST_SILENT = "наше не вернулось МОЛЧА"
REWRITTEN = "чужое переписано"
ALARM = "ложная тревога"
LOST_PART = "кусок записи не вернулся"
LOST_WHOLE = "целая подмена не вернулась"
LINES: tuple[str, ...] = (LOST, LOST_SILENT, REWRITTEN, ALARM, LOST_PART, LOST_WHOLE)


def _lost(verdicts: Sequence[Verdict]) -> Line:
    chosen = [one for one in verdicts if one.side == SIDE_OURS]
    return Line(len([one for one in chosen if not one.ok]), len(chosen))


def _lost_silently(verdicts: Sequence[Verdict]) -> Line:
    chosen = [one for one in verdicts if one.side == SIDE_OURS]
    return Line(len([one for one in chosen if not one.ok and one.silent]), len(chosen))


def _rewritten(verdicts: Sequence[Verdict]) -> Line:
    chosen = [one for one in verdicts if one.side == SIDE_FOREIGN]
    return Line(len([one for one in chosen
                     if one.note in (NOTE_THIRD_VALUE, NOTE_MISSING)]), len(chosen))


def _false_alarms(verdicts: Sequence[Verdict]) -> Line:
    chosen = [one for one in verdicts if one.side == SIDE_FOREIGN]
    return Line(len([one for one in chosen if one.note == NOTE_FALSE_ALARM]), len(chosen))


def _six_lines(verdicts: Sequence[Verdict], split: frozenset[str]) -> dict[str, Line]:
    """Шесть строк по приговорам ОДНОЙ поверхности.

    `split` — случаи, у которых наших кусков больше одного, то есть запись,
    разложенная по полям схемы. Потеря делится на «кусок записи» и «целая
    подмена» ровно потому, что третья подделка обязана провалить первую и не
    тронуть вторую; одно общее число объявило бы её одинаково плохой везде.
    """
    parts = [one for one in verdicts if one.case_id in split]
    wholes = [one for one in verdicts if one.case_id not in split]
    return {
        LOST: _lost(verdicts),
        LOST_SILENT: _lost_silently(verdicts),
        REWRITTEN: _rewritten(verdicts),
        ALARM: _false_alarms(verdicts),
        LOST_PART: _lost(parts),
        LOST_WHOLE: _lost(wholes),
    }


# --- чего требуют от каждого шлюза ----------------------------------------------------


@dataclass(frozen=True)
class Demand:
    """Требование к ОДНОЙ строке ОДНОГО шлюза. Без причины требование не пишется."""

    line: str
    floor: float | None
    ceiling: float | None
    why: str


@dataclass(frozen=True)
class Fake:
    """Поддельный шлюз и полный список того, что он обязан напечатать."""

    label: str
    restore: Restore
    residual: Residual
    demands: tuple[Demand, ...]


_CLEAN = "этой беды он не делает — строка обязана стоять на нуле"

PERFECT = Fake(
    label="идеальный",
    restore=_perfect,
    residual=_says_nothing,
    demands=tuple(Demand(line, None, 0.0,
                         "правильный шлюз не теряет, не переписывает и не тревожит; "
                         "ненулевое здесь — это прибор, кричащий волком")
                  for line in LINES),
)

FAKES: tuple[Fake, ...] = (
    Fake(
        label="ничего-вслух",
        restore=_restores_nothing,
        residual=_names_our_survivors,
        demands=(
            Demand(LOST, 0.80, None,
                   "не восстановил НИ ОДНОЙ подмены. Пол не 1.000, и причина законная: "
                   "подмена дома или квартиры — одна-две цифры, и она изредка совпадает "
                   "с настоящей (то самое событие, которое меряет test_collisions.py)"),
            Demand(LOST_SILENT, None, 0.0,
                   "каждую уцелевшую подмену он называет в остатке — потеря ВИДНА, и "
                   "колонка «молча» обязана остаться пустой"),
            Demand(LOST_WHOLE, 0.80, None,
                   "целую подмену он теряет ровно так же, как кусок, — и в этом вся "
                   "разница с «только-целое», которое теряет ТОЛЬКО кусок"),
            Demand(LOST_PART, 0.80, None,
                   "и кусок записи тоже: шлюз, не восстанавливающий ничего, обязан "
                   "проваливать обе строки, иначе они не независимы"),
            Demand(REWRITTEN, None, 0.0, _CLEAN),
            Demand(ALARM, None, 0.0,
                   "остаток называет только наши подмены; объявить чужое число нашим "
                   "он не может"),
        ),
    ),
    Fake(
        label="ничего-молча",
        restore=_restores_nothing,
        residual=_says_nothing,
        demands=(
            Demand(LOST, 0.80, None, "тот же отказ, что у «ничего-вслух»"),
            Demand(LOST_SILENT, 0.80, None,
                   "и он о нём МОЛЧИТ. Пара двусторонняя: теряют они одно и то же, "
                   "различает их ровно колонка «молча»"),
            Demand(LOST_WHOLE, 0.80, None, "та же потеря, что у «ничего-вслух»"),
            Demand(LOST_PART, 0.80, None, "та же потеря, что у «ничего-вслух»"),
            Demand(REWRITTEN, None, 0.0, _CLEAN),
            Demand(ALARM, None, 0.0, _CLEAN),
        ),
    ),
    Fake(
        label="чужие-числа",
        restore=_rewrites_foreign_numbers,
        residual=_says_nothing,
        demands=(
            Demand(REWRITTEN, 0.60, None,
                   "переписал цифры в каждом собственном числе заказчика. Не 1.000: "
                   "часть чужих кусков — слова («улица Магистральная»), цифр в них нет "
                   "и переписывать нечего"),
            Demand(LOST, None, 0.0,
                   "наше он восстанавливает безупречно, и прибор обязан это видеть — "
                   "иначе порча данных и потеря подмены слиплись бы в одно число"),
            Demand(ALARM, None, 0.0, _CLEAN),
        ),
    ),
    Fake(
        label="только-целое",
        restore=_whole_substitutes_only,
        residual=_says_nothing,
        demands=(
            Demand(LOST_PART, 0.80, None,
                   "отказывает ровно КУСКУ записи: адресу по полям схемы и паспорту "
                   "двумя полями. Это портрет правки, отклонённой 23.09.2026, — на "
                   "приборах предшественников она давала ноль из 37"),
            Demand(LOST_WHOLE, None, 0.0,
                   "целую подмену он возвращает; прибор, смешавший её с куском, "
                   "объявил бы ту правку одинаково плохой везде"),
            Demand(REWRITTEN, None, 0.0, _CLEAN),
        ),
    ),
    Fake(
        label="тревога-на-чужое",
        restore=_perfect,
        residual=_names_the_customers_numbers,
        demands=(
            Demand(ALARM, 0.60, None,
                   "ничего не испортил и ничего не потерял, но объявил числа заказчика "
                   "нашими подменами: шлюз заказчика получит повод отказаться от "
                   "совершенно верного вызова. Третья валюта прибора, и без этой "
                   "подделки её строку нечем было бы провалить"),
            Demand(LOST, None, 0.0, _CLEAN),
            Demand(REWRITTEN, None, 0.0,
                   "значения он не трогает: тревога — это ЯРЛЫК на целом значении"),
        ),
    ),
)


# --- прогон ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Traits:
    """Признаки живой поверхности, как она их объявила."""

    carries_fields: bool
    carries_prose: bool
    reports_residual: bool
    honours_conversation_id: bool


@dataclass(frozen=True)
class Probe:
    """Один общий прогон: одна чеканка, все шлюзы на ОДНИХ И ТЕХ ЖЕ листах."""

    fill: int
    lines: dict[str, dict[str, Line]]
    split: frozenset[str]
    traits: dict[str, Traits]
    stream_echo: str
    proxy_echo: tuple[tuple[str, str], ...]
    residual_headers: tuple[int, ...]
    skipped: int
    attempted: int


def _recording(ledger: dict[Passage, Written], shapes: dict[str, int]) -> tuple[Case, ...]:
    """Корпус, записывающий КАЖДЫЙ составленный лист вместе с его кусками."""
    def recorder(case: Case) -> Case:
        def recorded(minted: Mapping[str, Minted], numbers: Foreign) -> Written:
            result = case.write(minted, numbers)
            ledger[result.passage] = result
            shapes[case.case_id] = len(_ours_pieces(result))
            return result
        return replace(case, write=recorded)

    return tuple(recorder(case) for case in CORPUS)


def _gateways(ledger: Mapping[Passage, Written]) -> tuple[Surface, ...]:
    built: list[Surface] = []
    for fake in (PERFECT,) + FAKES:
        built.append(FieldGateway(fake.label, fake.restore, fake.residual, ledger))
        built.append(ProseGateway(fake.label, fake.restore, fake.residual, ledger))
    return tuple(built)


def _echo(surfaces: Mapping[str, Surface], org_id: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Что поток и прокси делают с листом, в котором нашего нет ничего.

    Отдельно от корпуса и намеренно: поверхность, теряющая текст сама по себе,
    записала бы каждую свою потерю на счёт движка — ровно так предшественники и
    показывали ноль там, где потерь было двенадцать из двенадцати. Лист без
    единой нашей подмены — единственный, на котором «вернулось ровно то, что
    послали» есть полное и проверяемое требование.
    """
    scope = Scope(name="проверка поверхности", conversation_id="",
                  pseudonym_scope="conversation")
    passage = Passage(tool_name="crm.add_line",
                      fields=((NEUTRAL_FIELD, NEUTRAL),), prose=NEUTRAL)
    return (surfaces["stream"].carry(org_id, passage, scope).prose,
            surfaces["proxy"].carry(org_id, passage, scope).fields)


def probe(engine: Engine, fill: int) -> Probe:
    ledger: dict[Passage, Written] = {}
    shapes: dict[str, int] = {}
    # Подменяется ИМЯ В МОДУЛЕ БЕГУНА, а не сам корпус: бегун читает `CORPUS`
    # своим именем, и правка чужого модуля на месте пережила бы этот прогон.
    runner.CORPUS = _recording(ledger, shapes)
    live = available(engine)
    by_name = {one.name: one for one in live}
    echo, fields = _echo(by_name, "b29-echo")
    harvest = runner.run(engine, tuple(live) + _gateways(ledger), (fill,), 1)
    split = frozenset(case_id for case_id, count in shapes.items() if count >= 2)
    by_surface: dict[str, list[Verdict]] = {}
    for verdict in harvest.verdicts:
        by_surface.setdefault(verdict.surface, []).append(verdict)
    return Probe(
        fill=fill,
        lines={name: _six_lines(found, split) for name, found in by_surface.items()},
        split=split,
        traits={one.name: Traits(one.carries_fields, one.carries_prose,
                                 one.reports_residual, one.honours_conversation_id)
                for one in live},
        stream_echo=echo,
        proxy_echo=fields,
        residual_headers=tuple(by_name["proxy"].header_counts),
        skipped=len(harvest.skipped),
        attempted=harvest.attempted,
    )


# --- проверки -------------------------------------------------------------------------


def test_four_surfaces_attach(found: Probe) -> list[str]:
    """Все четыре поверхности в таблице, и две новые объявлены так, как обязаны.

    `reports_residual = False` у потока и `honours_conversation_id = False` у
    прокси — не оговорки: `/unmask_chunk` остатка не отдаёт вовсе, а у прокси нет
    поля для разговора. Объявленная наоборот, любая из двух напечатала бы нули
    там, где клетка слепа.
    """
    problems = [f"поверхность {name} не подключилась" for name in REQUIRED_SURFACES
                if name not in found.traits]
    if problems:
        return problems
    if found.traits["stream"].reports_residual:
        problems.append("stream объявил, что отдаёт остаток, — ручка его не отдаёт")
    if found.traits["proxy"].honours_conversation_id:
        problems.append("proxy объявил, что слышит conversation_id, — поля для него нет")
    if not found.traits["proxy"].carries_fields:
        problems.append("proxy обязан читаться по вызову инструмента: туда уезжает "
                        "переписанное число заказчика")
    return problems


def test_new_surfaces_carry_what_they_were_given(found: Probe) -> list[str]:
    """Поток и прокси ничего не теряют САМИ — см. `_echo`."""
    problems: list[str] = []
    if found.stream_echo != NEUTRAL:
        problems.append(f"поток вернул не то, что послали: {found.stream_echo!r}")
    if found.proxy_echo != ((NEUTRAL_FIELD, NEUTRAL),):
        problems.append(f"прокси вернул не тот вызов: {found.proxy_echo!r}")
    return problems


def test_proxy_names_the_count_at_least(found: Probe) -> list[str]:
    """Заголовок прокси шевелится: его слепота — слепота к АДРЕСАТУ, а не к факту.

    Прокси отдаёт `X-Pseudex-Residual` — ДЛИНУ списка, а не имена, поэтому
    приписать отказ куску нечем и `reports_residual = False`. Но если бы
    заголовок молчал ВСЕГДА, у этой поверхности не было бы даже счётчика, и
    объявление стоило бы записать иначе. Проверяется здесь, потому что число
    из заголовка в таблицу не попадает.
    """
    if not found.residual_headers:
        return ["прокси не сделал ни одного вызова — заголовок проверять не на чем"]
    if not any(found.residual_headers):
        return ["X-Pseudex-Residual прокси равен нулю на ВСЕХ вызовах прогона, включая "
                "те, где подмена не восстановилась: заголовок не несёт даже счётчика"]
    return []


def test_no_line_is_empty(found: Probe) -> list[str]:
    """У каждой строки каждого шлюза есть что мерить.

    Болезнь v4: пустой знаменатель печатает ноль и удостоверяет ничто
    (`all([])` — истина). «0 из 0» на корпусе из тридцати трёх случаев — дефект,
    откуда бы он ни взялся, и потому провал, а не пропуск.
    """
    return [f"{surface} · {line}: 0 из 0 — мерить нечего, удостоверено ничто"
            for surface, lines in sorted(found.lines.items())
            for line, one in sorted(lines.items()) if one.total == 0]


def test_nothing_went_unmeasured(found: Probe) -> list[str]:
    """Пропуск — это не зелёная клетка. Систематический пропуск — сломанная чеканка."""
    if not found.attempted:
        return ["не проведено ни одного случая"]
    share = found.skipped / found.attempted
    return ([f"пропущено {share:.1%} случаев ({found.skipped} из {found.attempted}) — "
             f"это уже не совпадение подмены с настоящим значением"] if share > 0.02
            else [])


def test_every_line_is_claimed(_found: Probe) -> list[str]:
    """Каждую строку кто-то обязан обнулить и кто-то обязан провалить.

    Строка, которую ни одна подделка не поднимает, не может быть провалена
    ничем — это и есть «прибор, который не может провалиться». Строка, которой
    не требует правильный шлюз, не может быть провалена ложной тревогой.
    """
    problems = [f"{line}: правильный шлюз не обязан её обнулять" for line in LINES
                if line not in {one.line for one in PERFECT.demands}]
    accused = {one.line for fake in FAKES for one in fake.demands if one.floor is not None}
    problems += [f"{line}: ни одна подделка не обязана её поднять — провалить нечем"
                 for line in LINES if line not in accused]
    problems += [f"{fake.label} · {one.line}: требование без причины"
                 for fake in (PERFECT,) + FAKES for one in fake.demands if not one.why]
    problems += [f"{fake.label} · {one.line}: требование ни о чём (ни пола, ни потолка)"
                 for fake in (PERFECT,) + FAKES for one in fake.demands
                 if one.floor is None and one.ceiling is None]
    problems += [f"{fake.label} · {one.line}: строки с таким именем нет"
                 for fake in (PERFECT,) + FAKES for one in fake.demands
                 if one.line not in LINES]
    return problems


def _breaches(fake: Fake, name: str, lines: Mapping[str, Line]) -> list[str]:
    out: list[str] = []
    for demand in fake.demands:
        one = lines[demand.line]
        if demand.floor is not None and one.rate < demand.floor:
            out.append(f"{name} · {demand.line}: {one} ниже пола {demand.floor:.2f} — "
                       f"{demand.why}")
        if demand.ceiling is not None and one.rate > demand.ceiling:
            out.append(f"{name} · {demand.line}: {one} выше потолка {demand.ceiling:.2f} — "
                       f"{demand.why}")
    return out


def test_right_gateway_prints_zeroes(found: Probe) -> list[str]:
    """ПЕРВАЯ ПОЛОВИНА: правильный шлюз не даёт прибору ни одного повода."""
    return [one for flavour in FLAVOURS
            for one in _breaches(PERFECT, f"{PERFECT.label}/{flavour}",
                                 found.lines[f"{PERFECT.label}/{flavour}"])]


def test_wrong_gateways_are_caught(found: Probe) -> list[str]:
    """ВТОРАЯ ПОЛОВИНА, без которой первая ничего не значит.

    Каждая подделка проверяется в ОБЕИХ огранках: приговор по полям и приговор
    по прозе — разные, и совпасть они не обязаны.
    """
    problems: list[str] = []
    for fake in FAKES:
        for flavour in FLAVOURS:
            name = f"{fake.label}/{flavour}"
            lines = found.lines[name]
            if lines == found.lines[f"{PERFECT.label}/{flavour}"]:
                problems.append(f"{name}: напечатал ровно то же, что правильный шлюз — "
                                f"подделка без укуса ничего не доказывает")
                continue
            problems += _breaches(fake, name, lines)
    return problems


def test_silence_is_a_column_of_its_own(found: Probe) -> list[str]:
    """ТИХАЯ ПОТЕРЯ ОТДЕЛЕНА ОТ ВИДИМОЙ, и это проверяется парой, а не порогом.

    «ничего-вслух» и «ничего-молча» теряют ОДНО И ТО ЖЕ и различаются ровно тем,
    говорят ли они об этом. Печатай прибор их одинаково — колонка «молча» была
    бы украшением, и тогда числа на потоке, где остатка нет вовсе, читать было
    бы нельзя.
    """
    problems: list[str] = []
    for flavour in FLAVOURS:
        loud = found.lines[f"ничего-вслух/{flavour}"]
        quiet = found.lines[f"ничего-молча/{flavour}"]
        if loud[LOST] != quiet[LOST]:
            problems.append(f"{flavour}: пара теряет разное ({loud[LOST]} против "
                            f"{quiet[LOST]}) — сравнивать их «молча» не на чем")
        if loud[LOST_SILENT].hits >= quiet[LOST_SILENT].hits:
            problems.append(
                f"{flavour}: молчащий шлюз не отличается от говорящего ("
                f"{quiet[LOST_SILENT]} против {loud[LOST_SILENT]}) — колонка «молча» "
                f"ничего не различает")
    return problems


def _report(found: Probe) -> None:
    print()
    print(f"ПОДДЕЛЬНЫЕ ШЛЮЗЫ · {found.fill} диалогов в волте · записи по полям схемы: "
          f"{', '.join(sorted(found.split))}")
    head = f"  {'шлюз':<22}"
    for line in LINES:
        head += f"{line[:23]:>25}"
    print(head)
    for name in sorted(found.lines):
        row = f"  {name:<22}"
        for line in LINES:
            row += f"{str(found.lines[name][line]):>25}"
        print(row)
    print()
    print("ЖИВЫЕ ПОВЕРХНОСТИ")
    print(f"  поток вернул нейтральный лист дословно  : {found.stream_echo == NEUTRAL}")
    print(f"  прокси вернул нейтральный вызов дословно: "
          f"{found.proxy_echo == ((NEUTRAL_FIELD, NEUTRAL),)}")
    print(f"  X-Pseudex-Residual прокси               : "
          f"{sum(found.residual_headers)} за {len(found.residual_headers)} вызовов, "
          f"ненулевых {len([one for one in found.residual_headers if one])}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fill", type=int, default=3,
                        help="наполненность волта в диалогах: столкновение строится из "
                             "цифр фоновых подмен, и без фона его не построить")
    options = parser.parse_args(argv)

    engine = Engine(workspace())
    engine.start()
    try:
        found = probe(engine, options.fill)
    finally:
        engine.stop()

    _report(found)
    checks: tuple[tuple[str, Callable[[Probe], list[str]]], ...] = (
        ("four_surfaces_attach", test_four_surfaces_attach),
        ("new_surfaces_carry_what_they_were_given",
         test_new_surfaces_carry_what_they_were_given),
        ("proxy_names_the_count_at_least", test_proxy_names_the_count_at_least),
        ("nothing_went_unmeasured", test_nothing_went_unmeasured),
        ("no_line_is_empty", test_no_line_is_empty),
        ("every_line_is_claimed", test_every_line_is_claimed),
        ("right_gateway_prints_zeroes", test_right_gateway_prints_zeroes),
        ("wrong_gateways_are_caught", test_wrong_gateways_are_caught),
        ("silence_is_a_column_of_its_own", test_silence_is_a_column_of_its_own),
    )
    print()
    failures: list[str] = []
    for name, check in checks:
        problems = check(found)
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print()
    if failures:
        print("прибор: FAIL\n  " + "\n  ".join(failures))
        return 1
    print(f"прибор: PASS ({len(CORPUS)} случаев, {len(FAKES)} поддельных шлюзов в двух "
          f"огранках, {len(REQUIRED_SURFACES)} живых поверхностей)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
