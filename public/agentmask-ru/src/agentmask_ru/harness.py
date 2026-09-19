"""Run one masker over the corpus and record what happened, per item.

One case is a short conversation. The harness replays it turn by turn: it
hands the masker the transcript so far, the masker shows the scripted model
whatever it shows, the model answers (and on the last turn emits the tool
call), the masker restores the arguments, and the harness writes down what
the tool received.

WHAT IS RECORDED IS AN OBSERVATION, NOT A SCORE. `score.py` turns these
rows into lines; keeping them apart is what lets a third party re-derive a
published number from the run file without trusting our arithmetic.
"""

import json
import random
from dataclasses import asdict, dataclass, field

from agentmask_ru.adapters.base import Masker, MaskedView, TurnResult
from agentmask_ru.align import digits_of, is_number_like, norm, project, rewrite_ratio
from agentmask_ru.policy import decide
from agentmask_ru.schema import Case

REWRITE_FLAG = 0.3


@dataclass
class ItemObservation:
    case_id: str
    item_id: str
    type: str
    register: str
    family: str
    tier: str | None
    cue: bool
    turn: int
    tool_param: str | None
    substitute: str          # what stood where the value was
    altered: bool
    covered: bool
    typed_as: str | None     # the type the masker declared, when it exposes spans
    delivered: str | None    # what the tool received for this parameter
    round_trip: bool | None  # delivered == canonical; None when no parameter
    identity: str


@dataclass
class NegativeObservation:
    case_id: str
    value: str
    kind: str
    register: str
    family: str
    touched: bool            # the masker altered a value that is not personal data


@dataclass
class CaseObservation:
    case_id: str
    family: str
    register: str
    subcase: str | None
    hard: bool
    error: str | None
    call_made: bool
    call_name: str | None
    arguments_parse: bool    # the restored arguments were still valid JSON
    rewrite_ratio: float
    consistency: bool | None  # second mention got the first mention's substitute
    stability: bool | None    # the first mention's substitute did not move between requests
    items: list[ItemObservation] = field(default_factory=list)
    negatives: list[NegativeObservation] = field(default_factory=list)


def _same_value(produced: str, canonical: str) -> bool:
    """Did the tool receive the value?

    Text is compared case-insensitively after collapsing whitespace and
    folding «ё»; a number by its digits, tail-anchored at ten, so «+7 907 …»
    and «8907…» agree and a truncated number does not.

    BOTH SIDES MUST BE NUMBER-LIKE for the digit rule to apply. Without
    that guard «8 935 7476622-ерунда» passed as the phone, because its
    digit tail is the phone's — an argument carrying a real value plus
    something else is not the real value.
    """
    if norm(produced) == norm(canonical):
        return True
    right_digits = digits_of(canonical)
    if len(right_digits) < 6 or not is_number_like(canonical) or not is_number_like(produced):
        return False
    left_digits = digits_of(produced)
    if not left_digits:
        return False
    if len(right_digits) >= 10:
        return left_digits[-10:] == right_digits[-10:]
    return left_digits == right_digits


def _typed_as(session: object, case: Case, item_id: str) -> str | None:
    item = next(p for p in case.pii if p.id == item_id)
    spans = getattr(session, "spans", None)
    if spans is None:
        return None
    found = spans(case.messages[item.turn]["content"])
    if found is None:
        return None
    for span in found:
        if span.start < item.end and item.start < span.end:
            return span.type
    return None


def run_case(masker: Masker, case: Case, policy: str, seed: int) -> CaseObservation:
    rng = random.Random(f"{seed}:{case.id}:{policy}")
    session = masker.open(case.id)
    user_turns = [i for i, m in enumerate(case.messages) if m["role"] == "user"]
    observation = CaseObservation(
        case_id=case.id, family=case.family, register=case.register, subcase=case.subcase,
        hard=case.hard is not None, error=None, call_made=False, call_name=None,
        arguments_parse=False, rewrite_ratio=0.0, consistency=None, stability=None,
    )
    first_substitutes: dict[str, str] = {}
    last_result: TurnResult | None = None
    last_masked: MaskedView | None = None
    seen_by_item: dict[str, tuple[str, bool, bool]] = {}

    try:
        for turn in user_turns:
            prefix = [dict(m) for m in case.messages[: turn + 1]]
            captured: dict[str, object] = {}

            def _decide(masked: MaskedView, _turn: int = turn, _captured: dict[str, object] = captured):
                _captured["masked"] = masked
                reply, seen = decide(case, masked, _turn, policy, rng)
                _captured["seen"] = seen
                return reply

            result = session.run_turn(prefix, [dict(t) for t in case.tools], _decide)
            masked = result.masked or captured.get("masked")
            if isinstance(masked, MaskedView):
                last_masked = masked
                for item in case.pii:
                    if item.turn > turn:
                        continue
                    shown = masked.messages[item.turn].get("content")
                    if not isinstance(shown, str):
                        continue
                    substitute = project(case.messages[item.turn]["content"], shown, item.start, item.end)
                    seen_by_item[item.id] = (substitute.text, substitute.altered, substitute.covered)
                    if turn == user_turns[0]:
                        first_substitutes[item.id] = substitute.text
                    elif item.id in first_substitutes and item.turn == user_turns[0]:
                        # The same span, shown again in a later request: a
                        # per-request masker may give it a new substitute.
                        moved = first_substitutes[item.id] != substitute.text
                        observation.stability = not moved if observation.stability is None else (observation.stability and not moved)
            last_result = result
            if result.error:
                observation.error = result.error
                break
    finally:
        close = getattr(session, "close", None)
        if callable(close):
            close()

    if last_masked is not None:
        for turn in user_turns:
            original = case.messages[turn]["content"]
            shown = last_masked.messages[turn].get("content")
            if isinstance(shown, str):
                protected = [(p.start, p.end) for p in case.pii if p.turn == turn]
                protected += [(n.start, n.end) for n in case.negatives if n.turn == turn]
                observation.rewrite_ratio = max(observation.rewrite_ratio, rewrite_ratio(original, shown, protected))
            for negative in (n for n in case.negatives if n.turn == turn):
                if not isinstance(shown, str):
                    continue
                substitute = project(original, shown, negative.start, negative.end)
                observation.negatives.append(NegativeObservation(
                    case_id=case.id, value=negative.value, kind=negative.kind,
                    register=case.register, family=case.family, touched=substitute.altered,
                ))

    delivered: dict[str, str] = {}
    if last_result is not None and last_result.reply is not None and last_result.reply.tool_call is not None:
        observation.call_made = True
        observation.call_name = last_result.reply.tool_call.name
        raw = last_result.restored_arguments
        if raw is not None:
            try:
                parsed = json.loads(raw)
                observation.arguments_parse = isinstance(parsed, dict)
                if isinstance(parsed, dict):
                    delivered = {str(k): v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in parsed.items()}
            except (ValueError, TypeError):
                observation.arguments_parse = False

    for item in case.pii:
        substitute, altered, covered = seen_by_item.get(item.id, ("", False, False))
        received = delivered.get(item.tool_param) if item.tool_param else None
        round_trip = None
        if item.tool_param and observation.call_made:
            round_trip = received is not None and _same_value(received, item.canonical)
        observation.items.append(ItemObservation(
            case_id=case.id, item_id=item.id, type=item.type, register=case.register, family=case.family,
            tier=item.tier, cue=item.cue, turn=item.turn, tool_param=item.tool_param, substitute=substitute,
            altered=altered, covered=covered, typed_as=_typed_as(session, case, item.id), delivered=received,
            round_trip=round_trip, identity=item.identity,
        ))

    if case.family == "second_mention":
        firsts = {i.identity: i for i in observation.items if i.turn == user_turns[0] and i.type == "NAME"}
        seconds = [i for i in observation.items if i.turn != user_turns[0] and i.type == "NAME"]
        for second in seconds:
            first = firsts.get(second.identity)
            if first is None:
                continue
            # Undefined when the masker touched NEITHER mention: a
            # passthrough has no substitutes to be consistent about, and
            # the leak line already says so. One mention altered and the
            # other not IS an inconsistency — that is the half-masked
            # person whose second mention reached the model in the clear.
            if not first.altered and not second.altered:
                continue
            same = " ".join(first.substitute.split()).casefold() == " ".join(second.substitute.split()).casefold()
            observation.consistency = first.altered and second.altered and same
    return observation


def run(masker: Masker, cases: list[Case], policy: str, seed: int) -> list[CaseObservation]:
    return [run_case(masker, case, policy, seed) for case in cases]


def to_json(observations: list[CaseObservation]) -> list[dict[str, object]]:
    return [asdict(o) for o in observations]
