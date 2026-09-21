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
import re
from dataclasses import asdict, dataclass, field

from agentmask_ru.adapters.base import Masker, MaskedView, TurnResult
from agentmask_ru.align import digits_of, is_number_like, norm, project_many, rewrite_ratio
from agentmask_ru.parts import cut_address, cut_name
from agentmask_ru.person import looks_like_person, same_person
from agentmask_ru.rewrite import rewrite
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
    round_trip: bool | None  # delivered == canonical; None when no parameter or not attributable
    normalised: bool         # the tool got the value REPAIRED, not lost
    shared_block: bool       # the substitute could not be attributed to this span alone
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


# Latin letters that look like Cyrillic ones. A gateway that folds them
# back has repaired the customer's slip, which is a different outcome from
# losing the value — and telling the two apart needs the same table the
# slip was made with.
_LOOKALIKE: dict[str, str] = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "y": "у", "x": "х"}
# Letters that stand in for digits when somebody types a number. Folded
# ONLY inside a token that is mostly digits — «оля» is a name, «58О2333»
# is a phone with a slip in it, and the rule that tells them apart is the
# same one a detector uses.
_DIGIT_LOOKALIKE: dict[str, str] = {"о": "0", "О": "0", "o": "0", "O": "0", "з": "3", "З": "3", "б": "6"}


def _fold(text: str) -> list[str]:
    """Words and digit runs of a value, look-alikes folded, case ignored."""
    folded = "".join(_LOOKALIKE.get(ch, ch) for ch in norm(text))
    tokens = [part for part in re.split(r"[^\w]+", folded, flags=re.UNICODE) if part]
    out: list[str] = []
    for token in tokens:
        digits = sum(1 for ch in token if ch.isdigit())
        if digits and digits >= len(token) / 2:
            token = "".join(_DIGIT_LOOKALIKE.get(ch, ch) for ch in token)
        out.append(token)
    return out


_MONTHS_GEN: tuple[str, ...] = (
    "январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр",
)


def _as_date(text: str) -> tuple[int, int, int] | None:
    """(day, month, year) if this text is one date, else None. Two-digit years
    pivot on the current year, as every Russian form does."""
    import datetime as _dt

    cleaned = norm(text).strip(" .,")
    numeric = re.fullmatch(r"(\d{1,4})[./ -](\d{1,2})[./ -](\d{1,4})", cleaned)
    if numeric:
        first, middle, last = (int(part) for part in numeric.groups())
        day, month, year = (last, middle, first) if first > 31 else (first, middle, last)
    else:
        worded = re.fullmatch(r"(\d{1,2})\s+([а-я]+)\s+(\d{2,4})", cleaned)
        if not worded:
            return None
        stem = worded.group(2)
        month = next((i + 1 for i, m in enumerate(_MONTHS_GEN) if stem.startswith(m)), 0)
        if not month:
            return None
        day, year = int(worded.group(1)), int(worded.group(3))
    if year < 100:
        year += 2000 if year <= _dt.date.today().year % 100 else 1900
    try:
        _dt.date(year, month, day)
    except ValueError:
        return None
    return day, month, year


def _normalised(produced: str, canonical: str) -> bool:
    """Did the gateway hand the tool a REPAIRED version of the value?

    Some gateways deliberately normalise what the customer wrote: a Latin
    «a» inside a Cyrillic word folded back, a lower-case street rewritten
    the way the register spells it, a generic word («улицы») inserted. That
    is not the value as written — the round-trip line counts it as a miss,
    because the ground truth here is what the customer typed — but it is
    NOT the same failure as a value that arrived broken or not at all, and
    a reader choosing between gateways needs to tell them apart.

    The test is that NOTHING WAS LOST: every word and digit run of the
    canonical still appears, in order, in what the tool received. Counted
    and printed beside the line, never folded into the pass rate.
    """
    if not produced:
        return False
    # A PERSON IS ONE PERSON HOWEVER THE NAME IS INFLECTED OR ORDERED.
    # «есина рушана» returned as «Рушан Есин» is the customer named a turn
    # earlier, in the nominative a CRM record wants; a string judge read
    # «есина» as a feminine surname and scored the correct answer as a loss.
    # Same lemma per word, any order — see `person.py`. Neutral: a
    # placeholder is not a person shape and is judged below as before.
    if looks_like_person(produced) and looks_like_person(canonical):
        return same_person(produced, canonical)
    # A DATE IS ONE DATE HOWEVER IT IS WRITTEN. «2 июня 1975» returned as
    # «02.06.1975» is the same day in another notation — the tool gets the
    # right date — while «2 июня 1975» returned as «27.01.1975» is a different
    # day and a real break. Parsing both sides is the only way to tell them
    # apart, and it is the same courtesy every masker gets.
    left, right = _as_date(produced), _as_date(canonical)
    if left is not None and right is not None:
        return left == right
    # A number is one value however it is grouped: «220О7282…» repaired and
    # regrouped into «2200 7282 …» lost nothing.
    if is_number_like(canonical.replace("О", "0").replace("о", "0")) or is_number_like(produced):
        left = "".join(_DIGIT_LOOKALIKE.get(ch, ch) for ch in canonical)
        right = "".join(_DIGIT_LOOKALIKE.get(ch, ch) for ch in produced)
        if digits_of(left) and digits_of(left) == digits_of(right):
            return True
    wanted, got = _fold(canonical), _fold(produced)
    if not wanted:
        return False
    position = 0
    for piece in wanted:
        while position < len(got) and got[position] != piece:
            position += 1
        if position == len(got):
            return False
        position += 1
    return True


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
                for message_index in {i.turn for i in case.pii if i.turn <= turn}:
                    shown = masked.messages[message_index].get("content")
                    if not isinstance(shown, str):
                        continue
                    here = [i for i in case.pii if i.turn == message_index]
                    projected = project_many(case.messages[message_index]["content"], shown,
                                             [(i.start, i.end) for i in here])
                    for item, substitute in zip(here, projected):
                        seen_by_item[item.id] = (substitute.text, substitute.altered, substitute.covered, substitute.shared)
                        if turn == user_turns[0]:
                            first_substitutes[item.id] = substitute.text
                for item in case.pii:
                    if item.turn > turn:
                        continue
                    substitute_text = seen_by_item.get(item.id, ("", False, False, False))[0]
                    if turn != user_turns[0] and item.id in first_substitutes and item.turn == user_turns[0]:
                        # The same span, shown again in a later request: a
                        # per-request masker may give it a new substitute.
                        moved = first_substitutes[item.id] != substitute_text
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
            if not isinstance(shown, str):
                continue
            here = [n for n in case.negatives if n.turn == turn]
            for negative, substitute in zip(here, project_many(original, shown, [(n.start, n.end) for n in here])):
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
        substitute, altered, covered, shared = seen_by_item.get(item.id, ("", False, False, False))
        # WHAT THE TOOL IS OWED depends on the agent: a copier owes the value
        # as written; a rewriter owes it in ITS notation — what that agent
        # would have passed without any gateway (`rewrite` on the original).
        owed = rewrite(item.type, item.canonical) if policy == "rewriter" else item.canonical
        received = delivered.get(item.tool_param) if item.tool_param else None
        round_trip = None
        normalised = False
        if item.parts and item.tool_param and observation.call_made and not shared:
            # THE TOOL WANTS THE PARTS: every part the case cut from the gold
            # must arrive in its own field. The gold is cut by the same rule
            # the agent cut the substitute with (`parts.py`), from the owed
            # whole; a placeholder cannot be cut, so its parts arrive as one
            # string in the first field and empties elsewhere.
            owed_parts = (cut_name(owed, tuple(item.parts)) if item.type == "NAME"
                          else cut_address(owed, "city" in item.parts))
            got_parts = {part: delivered.get(part) for part in item.parts}
            received = json.dumps(got_parts, ensure_ascii=False)
            present = all(got_parts[part] is not None for part in item.parts)
            round_trip = present and all(
                _same_value(str(got_parts[part]), owed_parts.get(part, "")) if owed_parts.get(part, "")
                else not str(got_parts[part] or "").strip()
                for part in item.parts)
            if not round_trip and present:
                normalised = all(
                    (_same_value(str(got_parts[part]), owed_parts.get(part, ""))
                     or _normalised(str(got_parts[part]), owed_parts.get(part, "")))
                    if owed_parts.get(part, "") else not str(got_parts[part] or "").strip()
                    for part in item.parts)
        # A substitute the alignment could not attribute to this span alone
        # is not evidence about the round trip in either direction.
        elif item.tool_param and observation.call_made and not shared:
            round_trip = received is not None and _same_value(received, owed)
            if round_trip is False and received is not None:
                normalised = _normalised(received, owed)
        observation.items.append(ItemObservation(
            case_id=case.id, item_id=item.id, type=item.type, register=case.register, family=case.family,
            tier=item.tier, cue=item.cue, turn=item.turn, tool_param=item.tool_param, substitute=substitute,
            altered=altered, covered=covered, typed_as=_typed_as(session, case, item.id), delivered=received,
            round_trip=round_trip, normalised=normalised, shared_block=shared, identity=item.identity,
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
            # ONE SUBSTITUTE IN TWO CASES IS ONE SUBSTITUTE. A masker that
            # inflects its fake to the sentence («Харитон Рыбаков» … «Харитона
            # Рыбакова») kept the identity the model sees; a string
            # comparison called that two people, and the line read 63% for
            # the one system that declines. A placeholder still equals only
            # itself.
            same = (" ".join(first.substitute.split()).casefold() == " ".join(second.substitute.split()).casefold()
                    or (looks_like_person(first.substitute) and looks_like_person(second.substitute)
                        and same_person(first.substitute, second.substitute)))
            observation.consistency = first.altered and second.altered and same
    return observation


def run(masker: Masker, cases: list[Case], policy: str, seed: int) -> list[CaseObservation]:
    return [run_case(masker, case, policy, seed) for case in cases]


def to_json(observations: list[CaseObservation]) -> list[dict[str, object]]:
    return [asdict(o) for o in observations]
