"""Turn observations into the report lines, and never merge two of them.

  leak        the value was altered before the model saw it (type-blind)
  coverage    ALL of it was altered — a surname that survived «Кзнецов
              Дмитрий» → «Дмитрий» is a leak the leak line does not see
  typed       the masker also called it the right type (only where the
              masker exposes types; elsewhere the line is absent, not zero)
  round_trip  the tool received the real value — counted over the items the
              masker ALTERED, because restoring a value nobody masked is not
              an achievement
  round_trip_repaired
              the same, counting a value that arrived REPAIRED (canonical
              date notation, the nominative of a name, a folded look-alike
              digit) beside one that arrived as written — the two lines
              differ by exactly what the masker's normalisation costs the
              reader who wanted the text verbatim, and by nothing else
  end_to_end  the tool received the real value, over ALL items — the
              passthrough scores 100% here and that is the point: this line
              says «the agent still works», the leak line says «the data was
              protected», and a product needs both
  overmask    a negative was NOT altered
  consistency the second mention of a person got the first one's substitute
  stability   the first mention's substitute did not change between requests

Each line is x/n with an exact Clopper–Pearson interval; when x = n the
report prints what that certifies, never «100%».
"""

from dataclasses import dataclass

from agentmask_ru.harness import CaseObservation
from agentmask_ru.stats import clopper_pearson, zero_failure_floor


@dataclass(frozen=True)
class Line:
    name: str
    hits: int
    total: int

    @property
    def rate(self) -> float:
        return self.hits / self.total if self.total else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return clopper_pearson(self.hits, self.total)

    @property
    def certified(self) -> float | None:
        """What a flawless line certifies. None unless x = n > 0."""
        if self.total and self.hits == self.total:
            return zero_failure_floor(self.total)
        return None


@dataclass(frozen=True)
class Scores:
    lines: dict[str, Line]
    errors: int
    calls_made: int
    calls_parsed: int
    cases: int
    rewrite_flagged: int
    unattributable: int      # substitutes the alignment could not assign to one span
    normalised: int          # misses where the tool got the value repaired, not lost


def _line(name: str, hits: int, total: int) -> Line:
    return Line(name=name, hits=hits, total=total)


def score(observations: list[CaseObservation]) -> Scores:
    items = [i for o in observations for i in o.items]
    negatives = [n for o in observations for n in o.negatives]

    leak_hits = sum(1 for i in items if i.altered)
    coverage_hits = sum(1 for i in items if i.covered)

    typed_items = [i for i in items if i.typed_as is not None]
    typed_hits = sum(1 for i in typed_items if i.typed_as == i.type)

    with_param = [i for i in items if i.tool_param and i.round_trip is not None]
    altered_with_param = [i for i in with_param if i.altered]
    round_trip_hits = sum(1 for i in altered_with_param if i.round_trip)
    repaired_hits = sum(1 for i in altered_with_param if i.round_trip or i.normalised)
    end_to_end_hits = sum(1 for i in with_param if i.round_trip)

    overmask_hits = sum(1 for n in negatives if not n.touched)

    consistency = [o.consistency for o in observations if o.consistency is not None]
    stability = [o.stability for o in observations if o.stability is not None]

    lines = {
        "leak": _line("leak", leak_hits, len(items)),
        "coverage": _line("coverage", coverage_hits, len(items)),
        "round_trip": _line("round_trip", round_trip_hits, len(altered_with_param)),
        "round_trip_repaired": _line("round_trip_repaired", repaired_hits, len(altered_with_param)),
        "end_to_end": _line("end_to_end", end_to_end_hits, len(with_param)),
        "overmask": _line("overmask", overmask_hits, len(negatives)),
    }
    if typed_items:
        lines["typed"] = _line("typed", typed_hits, len(typed_items))
    if consistency:
        lines["consistency"] = _line("consistency", sum(1 for c in consistency if c), len(consistency))
    if stability:
        lines["stability"] = _line("stability", sum(1 for s in stability if s), len(stability))

    return Scores(
        lines=lines,
        errors=sum(1 for o in observations if o.error),
        calls_made=sum(1 for o in observations if o.call_made),
        calls_parsed=sum(1 for o in observations if o.arguments_parse),
        cases=len(observations),
        rewrite_flagged=sum(1 for o in observations if o.rewrite_ratio > 0.3),
        unattributable=sum(1 for i in items if i.shared_block and i.tool_param),
        normalised=sum(1 for i in items if i.normalised),
    )


def by_axis(observations: list[CaseObservation], axis: str) -> dict[str, Scores]:
    """Split along ONE axis — register, family, tier or cue. Crossing two of
    them at this corpus size would produce cells of eight items, where the
    interval is wider than any difference worth reading."""
    groups: dict[str, list[CaseObservation]] = {}
    if axis in ("register", "family"):
        for observation in observations:
            groups.setdefault(getattr(observation, axis), []).append(observation)
        return {key: score(value) for key, value in sorted(groups.items())}
    if axis in ("tier", "cue"):
        # These live on items, so the group is a synthetic observation that
        # carries only the items of that group.
        item_groups: dict[str, list[CaseObservation]] = {}
        for observation in observations:
            for item in observation.items:
                key = item.tier if axis == "tier" else ("cued" if item.cue else "no cue")
                if key is None:
                    continue
                bucket = item_groups.setdefault(key, [])
                bucket.append(CaseObservation(
                    case_id=observation.case_id, family=observation.family, register=observation.register,
                    subcase=observation.subcase, hard=observation.hard, error=observation.error,
                    call_made=observation.call_made, call_name=observation.call_name,
                    arguments_parse=observation.arguments_parse, rewrite_ratio=observation.rewrite_ratio,
                    consistency=None, stability=None, items=[item], negatives=[],
                ))
        return {key: score(value) for key, value in sorted(item_groups.items())}
    raise ValueError(f"unknown axis {axis}")


def paired(left: list[CaseObservation], right: list[CaseObservation], line: str) -> tuple[int, int]:
    """Discordant pairs (b, c) for McNemar on one line, item by item over
    the cases both systems ran."""
    def outcomes(observations: list[CaseObservation]) -> dict[tuple[str, str], bool]:
        out: dict[tuple[str, str], bool] = {}
        for observation in observations:
            for item in observation.items:
                if line == "leak":
                    out[(item.case_id, item.item_id)] = item.altered
                elif line == "coverage":
                    out[(item.case_id, item.item_id)] = item.covered
                elif line == "end_to_end":
                    if item.round_trip is not None:
                        out[(item.case_id, item.item_id)] = item.round_trip
                else:
                    raise ValueError(f"line {line} is not paired-comparable item by item")
            if line == "overmask":
                for negative in observation.negatives:
                    out[(negative.case_id, negative.value)] = not negative.touched
        return out

    a, b = outcomes(left), outcomes(right)
    shared = set(a) & set(b)
    only_left = sum(1 for key in shared if a[key] and not b[key])
    only_right = sum(1 for key in shared if b[key] and not a[key])
    return only_left, only_right
