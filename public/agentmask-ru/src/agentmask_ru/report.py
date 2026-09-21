"""Print the lines, with the interval beside every rate.

Conventions the report never breaks: a rate is printed with its n; a
flawless line prints what it certifies instead of «100%»; strata are printed
one axis at a time; a masker that does not expose types shows «—» on the
typed line rather than a zero.
"""

from agentmask_ru.score import Line, Scores, by_axis
from agentmask_ru.harness import CaseObservation

_ORDER: tuple[str, ...] = (
    "leak", "coverage", "typed", "round_trip", "round_trip_repaired", "end_to_end", "overmask", "consistency", "stability",
)

_MEANING: dict[str, str] = {
    "leak": "значение изменено до того, как его увидела модель",
    "coverage": "изменено целиком, хвост не утёк",
    "typed": "тип определён верно (если маскер отдаёт типы)",
    "round_trip": "инструмент получил настоящее значение (из изменённых)",
    "round_trip_repaired": "то же, считая значение, вернувшееся в канонической форме, доставленным",
    "end_to_end": "инструмент получил настоящее значение (из всех)",
    "overmask": "не тронуто то, что не является персональными данными",
    "consistency": "второе упоминание получило ту же подстановку",
    "stability": "подстановка не менялась между запросами",
}


def _format(line: Line) -> str:
    if line.total == 0:
        return f"{'—':>12}  нет наблюдений"
    low, high = line.interval
    body = f"{line.hits:4d}/{line.total:<4d} {line.rate * 100:6.1f}%  [{low * 100:5.1f}, {high * 100:5.1f}]"
    certified = line.certified
    if certified is not None:
        body += f"  сертифицирует ≥{certified * 100:.1f}%"
    return body


def render(name: str, scores: Scores, observations: list[CaseObservation] | None = None) -> str:
    out: list[str] = []
    out.append(f"# {name}")
    out.append(f"  случаев {scores.cases} · вызовов {scores.calls_made} · аргументы разобраны {scores.calls_parsed}"
               f" · ошибок {scores.errors} · переписан текст {scores.rewrite_flagged}"
               f" · не атрибутируется {scores.unattributable}")
    if scores.normalised:
        out.append(f"  из расхождений круга {scores.normalised} — значение вернулось ПОЧИНЕННЫМ "
                   f"(описка исправлена, написание приведено к реестру), а не потерянным")
    out.append("")
    for key in _ORDER:
        line = scores.lines.get(key)
        if line is None:
            out.append(f"  {key:<12} {'—':>28}  {_MEANING[key]} (не измеряется)")
            continue
        out.append(f"  {key:<12} {_format(line)}  {_MEANING[key]}")
    if observations is None:
        return "\n".join(out)
    for axis in ("register", "tier", "cue", "family"):
        groups = by_axis(observations, axis)
        if len(groups) <= 1:
            continue
        out.append("")
        out.append(f"  — по оси «{axis}» —")
        for key, group in groups.items():
            leak = group.lines["leak"]
            round_trip = group.lines["round_trip"]
            rt = f"{round_trip.hits:3d}/{round_trip.total:<3d} {round_trip.rate * 100:5.1f}%" if round_trip.total else f"{'—':>10}"
            out.append(f"    {key:<14} leak {leak.hits:3d}/{leak.total:<3d} {leak.rate * 100:5.1f}%   round_trip {rt}")
    return "\n".join(out)
