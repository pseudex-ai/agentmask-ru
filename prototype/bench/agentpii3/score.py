"""Score a masking gateway on AgentPII-RU v3. THREE AXES, and only three.

    python3 bench/agentpii3/score.py                       # весь корпус, бесплатно
    python3 bench/agentpii3/score.py --tier nano --dump 20
    python3 bench/agentpii3/score.py --family wordnum --type LOC

ОСЬ 1 — ДЕТЕКЦИЯ. Per type, per register, per family, per length rung.

  ПОЛНОТА  — the span was found AND CARRIES THE SAME TYPE. An overlap of the
             wrong type is not recall: a СНИЛС masked as a street is not a found
             СНИЛС, it is a broken call, and a counter that accepts any overlap
             would rank that gateway above one that found nothing while both
             leaked the same digits. `schema.span_verdict` states the rule; this
             file never restates it.
  ПОКРЫТИЕ — the span was found WHOLE. Printed beside recall and NEVER merged
             with it: «Кзнецов Дмитрий» detected as «Дмитрий» is recall AND a
             leaked surname, and the difference between the two numbers is the
             leaked tail. v1 published 97.6% against 95.0% — sixty-nine partial
             leaks a single number hid.
  ТОЧНОСТЬ — the declared negatives, scored as hard as recall. A masked cabinet
             number breaks the conversation as surely as a leaked one breaks the
             law, and «три четырнадцатый кабинет» occurs 528 times in the call
             corpus this register comes from.

  Beside every share stands the number of DISTINCT values, because one address
  said by seven callers is one value and seven occurrences, and an interval over
  occurrences is narrower than the truth in our favour. The selection strata are
  broken out and weighted (`Provenance.weight`) rather than averaged: the marker
  stratum is selected by the words the detector itself reads and is biased upward
  by construction.

ОСЬ 2 — ВЫЗОВ ИНСТРУМЕНТА ПРОТИВ ЭТАЛОНА. Against the REFERENCE call, never
against an arm without the gateway. Three questions, kept apart because a single
rate cannot distinguish them:

  тот ли инструмент — did the gateway leave dispatch possible? Tool names,
      parameter names and enum values must survive `mask_tools` byte-identical,
      and a tool name the system prompt mentions must still be there after
      masking. A gateway that renames a tool has broken the call before the
      model ever ran.
  те ли аргументы  — a judged argument carrying NO personal datum (an order id,
      a customer id) must come back byte-identical. This is the precision half of
      the call axis and it is where a masked order number shows up.
  дошло ли настоящее значение — the argument that carries a person. Simulated
      through the PRODUCTION path: the arguments go through `unmask_arguments` as
      JSON — never `unmask_chunk`, which flat-substitutes and injects bare quotes
      into «ООО "Заря"» — and what comes back is compared with the reference.
      Divergences are named with `schema.classify_break` — подмена не
      разрешилась, чужой человек, склонение, обрезка — never summed into one rate.

  THE PERFECT-MODEL FICTION IS THE POINT, and it has two halves. The owner ruled
  model behaviour out of scope, so the model here is defined as one that emits
  the reference call if there is no gateway in the path. WHERE THE GATEWAY
  SUBSTITUTED, it can only copy the substitute — it never saw anything else, and
  everything that goes wrong after that is the gateway's. WHERE THE GATEWAY
  TOUCHED NOTHING, it emits the reference, because that is what it would have
  emitted anyway; charging this axis for the raw surface there would count a
  DETECTION miss twice, once in each axis, and leave a reader unable to tell how
  many defects there were. Both counts are printed, and the second is the
  gateway's own contribution.

ОСЬ 3 — УТЕЧКА В ИТОГОВОМ ОТВЕТЕ. Two questions, both required:

  а) real personal data left standing in the text the agent hands the customer;
  б) A SUBSTITUTE PASSED OFF AS REAL — «вы находитесь на Пушкина 18» where the
     customer said «Ленина 14». The owner named this the main one, and this
     benchmark can answer it where an LLM-judged one cannot: the vault knows
     exactly which strings it minted.

  Offline the reply is simulated the same way axis 2 simulates the call — the
  perfect agent writes back what it saw — and run through `unmask_text`, the real
  outbound leg. Anything needing judgement about a real transcript (a closed
  да/нет, a free-text disclosure) is handed to the JUDGE SEAM below and is
  `unjudged` until a model fills it.

THE «ПРОЗРАЧНОСТЬ» AXIS IS NOT HERE. The owner deleted it: measuring how the
model uses its tools is not this benchmark's job. It is not to be revived under
another name.

WHAT THIS FILE MAY NOT DO. Every comparison rule — what counts as found, what
counts as the same value, how a break is named, when a rate may be printed as a
percentage — lives in `schema.py` and is imported. A scorer that invents its own
rule makes last month's number incomparable with this month's, and the corpus's
whole claim is that a third party can re-score a COMPETING gateway with it.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, conversation_key, mask_tools  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
# `_splice` and `_token_for_text` are private and imported ANYWAY, deliberately.
# The substitute the model copies is the token INFLECTED INTO THE SENTENCE —
# `peek_token` returns a different string — and the splice is what decides where
# it lands. Re-implementing either here would give this benchmark its own
# masking, which is the one thing an instrument measuring masking may not have.
from pseudex.redact import (  # noqa: E402
    _splice,
    _token_for_text,
    is_own_substitute,
    residual_tokens,
    unmask_arguments,
    unmask_text,
)
from pseudex.vault import Vault  # noqa: E402
from bench.agentpii3 import rewrite  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

if __package__ in (None, ""):
    sys.path.insert(0, str(_HERE.parent))
    import schema  # type: ignore[import-not-found]
else:
    from bench.agentpii3 import schema


# --- the adapter ----------------------------------------------------------
#
# THE ONLY PLACE THIS SCORER KNOWS WHOSE GATEWAY IT IS SCORING. A competitor
# supplies its own table and everything below is unchanged; `schema.TYPES` is the
# vocabulary both sides meet in.
#
# `DATE` -> `DOB` and not the other way round: the engine detects a date and
# decides by CONTEXT whether it is personal, and the corpus only ever labels the
# personal ones. Engine types with no corpus counterpart (OPAQUE, SECRET, AGE,
# MEDICAL) are deliberately left unmapped — they can then never be credited as
# recall for any type, while still counting as a false mask when they land on a
# declared negative, which is exactly their standing.
ENGINE_TYPES: dict[str, str] = {
    "NAME": "NAME",
    "LOC": "LOC",
    "ADDR": "LOC",
    "PHONE": "PHONE",
    "EMAIL": "EMAIL",
    "DATE": "DOB",
    "SNILS": "SNILS",
    "INN": "INN",
    "CARD": "CARD",
    "PASSPORT": "PASSPORT",
    "PLATE": "PLATE",
}

# A surviving token of THIS shape is visible garbage a human notices; anything
# else that survives is a plausible fake presented as somebody's real datum, and
# that is the worse of the two. See `schema.ANSWER_VERDICTS`.
_OPAQUE_PREFIX = "REDACTED"

_ORG = "agentpii3"
_AGENT = "bench"


# --- the judge seam -------------------------------------------------------
#
# ONE FUNCTION, AND IT IS THE WHOLE CONTRACT WITH THE NEXT PHASE. The LLM judge
# (Agent SDK, claude-sonnet-5) replaces `deterministic_judge` and nothing else.
#
# THE VAULT FACTS ARE COMPUTED BY THE SCORER, NEVER BY THE JUDGE. Which strings
# this case's vault minted, and which of them survived detokenisation, are facts
# only the gateway's own vault can supply — a model asked to guess them would
# invent them. So they arrive already decided, and the judge is left with what a
# model is actually for: whether a reply DISCLOSES something, whether it answers
# the closed question, whether a free-text argument still names the same thing.


@dataclass(frozen=True)
class JudgeRequest:
    """One question about one agent reply, with everything needed to answer it."""

    case_id: str
    question: str                        # one line, what has to be decided
    answer: str                          # the reply AS THE CUSTOMER SEES IT
    must_contain: tuple[str, ...]        # real values the reply has to carry
    must_not_contain: tuple[str, ...]    # real values whose appearance discloses
    closed_answer: str                   # "да" | "нет" | ""
    substitutes_present: tuple[str, ...] # minted fakes still standing in `answer`
    # ВСЕ подмены, отчеканенные для случая, а не только уцелевшие в тексте.
    # `substitutes_present` — это лёгкая половина: то, что уже нашёл строковый
    # поиск. Судье нужна вторая половина, иначе он отвечает на вопрос, который
    # ему ещё не задали (см. `judge.only_what_the_vault_matched`).
    substitutes_minted: tuple[str, ...]
    residual_present: tuple[str, ...]    # of those, the visibly-opaque ones
    # Of `must_contain`, the values the SCORER could not find in `answer`. It is
    # decided outside the judge for the same reason the vault facts are: matching
    # «Гусева, 81, кв. 117» against the spoken form it came back in is
    # `schema.same_value`'s job, and a model asked to re-decide it would answer
    # differently on different days.
    missing: tuple[str, ...]


@dataclass(frozen=True)
class JudgeVerdict:
    """One of `schema.ANSWER_VERDICTS`, or `unjudged`.

    `unjudged` is not a failure and not a pass — it is the deterministic judge
    saying «this needs a model», and it is COUNTED APART so a run without one
    cannot quietly report a smaller denominator as a better score.
    """

    verdict: str
    why: str
    judged_by: str


UNJUDGED: str = "unjudged"

# THE SEAM, NAMED. The next phase writes one function of this type on the Agent
# SDK (claude-sonnet-5) and passes it to `score()`. Nothing else in this file
# changes, and `deterministic_judge` stays as the offline default so axes 1 and 2
# — and the string-decidable half of axis 3 — keep running over the whole corpus
# with no model and no money.
Judge = Callable[[JudgeRequest], JudgeVerdict]


def deterministic_judge(request: JudgeRequest) -> JudgeVerdict:
    """Everything decidable by string comparison, and an honest refusal for the rest.

    ORDER MATTERS AND IS THE PRODUCT'S OWN RANKING. `substitute_shown` comes
    first because it is the worst outcome the owner named: a plausible fake
    address handed to the customer as their own is noticed by nobody, while a
    `REDACTED…` string is noticed by everybody.
    """
    plausible = tuple(value for value in request.substitutes_present
                      if value not in request.residual_present)
    if plausible:
        return JudgeVerdict(
            verdict="substitute_shown",
            why=f"подмена стоит в ответе как настоящее значение: {plausible[0]!r}",
            judged_by="deterministic")
    if request.residual_present:
        return JudgeVerdict(
            verdict="token_shown",
            why=f"токен пережил детокенизацию: {request.residual_present[0]!r}",
            judged_by="deterministic")
    folded = request.answer.casefold()
    for forbidden in request.must_not_contain:
        if forbidden.casefold() in folded:
            return JudgeVerdict(
                verdict="third_party",
                why=f"в ответе чужие данные: {forbidden!r}",
                judged_by="deterministic")
    if request.missing:
        # WHAT CAME BACK IS PRINTED BESIDE WHAT WAS ASKED FOR, always. Most of
        # these are a FORM: the corpus asks for «Баранова, 24, подъезд 6» and the
        # customer said «баранова двадцать четыре шестой подъезд», which is the
        # form the vault stores and therefore the form it returns. Forgiving that
        # in the comparison would also forgive «ленина пятидесяти» — a declined
        # address read back to a customer — so it is reported strictly and the
        # evidence is shown rather than the number quietly adjusted.
        return JudgeVerdict(
            verdict="value_missing",
            why=(f"требовалось {request.missing[0]!r}, вернулось "
                 f"{request.answer[:60]!r}"),
            judged_by="deterministic")
    if request.closed_answer:
        # A closed да/нет is the MODEL's answer, not the gateway's. Parsing it
        # off a real transcript needs a model; refusing to guess is the point of
        # `unjudged`.
        return JudgeVerdict(
            verdict=UNJUDGED,
            why="закрытый ответ да/нет — поведение модели, нужен судья",
            judged_by="deterministic")
    return JudgeVerdict(verdict="clean", why="", judged_by="deterministic")


# --- one message through the gateway --------------------------------------


@dataclass(frozen=True)
class Piece:
    """One span the gateway replaced, and what it put there."""

    start: int
    end: int
    substitute: str
    engine_type: str


@dataclass(frozen=True)
class Masked:
    """One message before and after the gateway saw it."""

    text: str
    masked: str
    pieces: tuple[Piece, ...]


# КАК ПРИБОР МОДЕЛИРУЕТ МОДЕЛЬ. `True` — подмена переписывается так, как её
# переписывает настоящая модель (`rewrite.py`); `False` — прежнее допущение
# «копирует дословно», оставленное ради одного сравнения: показать, на сколько
# это допущение завышало ось 2. По умолчанию честный режим.
REWRITE_LIKE_A_MODEL = True


def _model_writes(seen: str, expected: str, argument: str, how: str,
                  item: schema.PiiItem | None, key: str) -> str:
    """Что модель ПОЛОЖИТ в аргумент, увидев подмену `seen`.

    Три ветки, и каждая отвечает форме, которую живой прогон показал:

      1. Поле схемы называет ЧАСТЬ адреса (`street`, `house`, `flat`) — модель
         кладёт туда соответствующую часть подмены. Пустая часть (у подмены нет
         подъезда) остаётся пустой: подставить туда всю фразу значило бы
         утверждать, что модель кладёт весь адрес в поле `entrance`, а живьём
         она кладёт выдуманное число.
      2. Поле принимает адрес целиком — модель его ПЕРЕФОРМАТИРУЕТ.
      3. Поле принимает часть имени — модель берёт слово той же позиции.

    Вне этих форм подмена копируется дословно, как и раньше.
    """
    if not REWRITE_LIKE_A_MODEL or item is None:
        return seen
    if item.type == "LOC":
        if rewrite.role_of(argument):
            return rewrite.decompose_for_role(seen, argument)
        return rewrite.reformat_address(seen, key)
    if item.type == "NAME" and how == "часть значения":
        return rewrite.name_part(seen, item.value, expected)
    return seen


def _mask_message(text: str, detector: Detector, vault: Vault) -> Masked:
    """The production masking of one message, with the pieces kept.

    This is `envelope.mask_one`'s `_compute` minus the cache and the audit —
    neither of which can change WHAT the model sees — composed from the same two
    functions production composes it from. The spans a minted token sits on are
    dropped first, exactly as `mask_text` drops them, because the model echoes
    its own substitutes back constantly and masking one a second time makes the
    person's identity change every turn.
    """
    spans = [span for span in detector.detect(text)
             if not is_own_substitute(span, vault)]
    pieces = tuple(
        Piece(start=span.start, end=span.end,
              substitute=_token_for_text(span, vault),
              engine_type=span.entity_type)
        for span in spans)
    masked = _splice(text, [(p.start, p.end, p.substitute) for p in pieces])
    return Masked(text=text, masked=masked, pieces=pieces)


def _seen(message: Masked, low: int, high: int) -> str:
    """What stood in [low, high) after masking — what a perfect model copies.

    A span the region only clips is emitted WHOLE: the model cannot copy half a
    fake, and the half it would have to copy is precisely the case this
    benchmark exists to notice — an address masked into a bare settlement leaves
    a `house` argument with nothing to put in it.
    """
    out: list[str] = []
    cursor = low
    for piece in sorted(message.pieces, key=lambda p: p.start):
        if piece.end <= low or piece.start >= high:
            continue
        if piece.start > cursor:
            out.append(message.text[cursor:piece.start])
        out.append(piece.substitute)
        cursor = max(cursor, piece.end)
    if cursor < high:
        out.append(message.text[cursor:high])
    return "".join(out)


def _leaked_tail(item: schema.PiiItem, produced: list[schema.MaskedSpan],
                 text: str) -> str:
    """The characters of a PARTIALLY found item that went to the model in the clear.

    Printed instead of the masked rendering, because the rendering looks
    innocent: a two-span address with a comma between them reads as fully masked
    and the tail is «, ». The reader has to see WHICH characters leaked to know
    whether the gap between recall and coverage is a surname or punctuation.
    """
    covered: set[int] = set()
    for span in produced:
        if span.msg != item.msg or span.type != item.type:
            continue
        for position in range(max(span.start, item.start),
                              min(span.end, item.end)):
            covered.add(position)
    return "".join(text[position] for position in range(item.start, item.end)
                   if position not in covered)


def _observed(messages: tuple[Masked, ...]) -> list[schema.MaskedSpan]:
    """Everything the gateway masked, in the form `schema` compares against."""
    return [
        schema.MaskedSpan(msg=index, start=piece.start, end=piece.end,
                          type=ENGINE_TYPES.get(piece.engine_type,
                                                piece.engine_type))
        for index, message in enumerate(messages)
        for piece in message.pieces
    ]


# --- axis 2: locating an argument in the transcript -----------------------


@dataclass(frozen=True)
class Located:
    """Where a reference argument's value physically sits, and whose it is."""

    msg: int
    start: int
    end: int
    item_id: str        # "" when the argument carries no personal datum
    how: str


def _locate(case: schema.Case, call: schema.ExpectedCall, argument: str,
            expected: str, messages: tuple[Masked, ...]) -> Located | None:
    """Find the text the model would have copied into this argument.

    FOUR RULES, IN ORDER, and each one is a shape the corpus actually contains:

      1. `tool_param` names this argument. The item IS the argument, whether the
         reference wants the surface form («ленина пятьдесят») or the canonical
         one («игорь» for «игоря») — the case decides which, and this scorer
         never second-guesses it.
      2. The argument is a PART of one item («street» and «house» carved out of
         one spoken address). The offset inside `item.value` maps straight into
         the message, because `item.value` is the exact slice — that is what
         makes the ground truth derivable rather than searched.
      3. The argument appears verbatim in the transcript and belongs to nobody —
         an order id, a customer id. Located anyway, because the demand on it is
         that the gateway did NOT touch it.
      4. Nothing. Reported as its own count and never silently passed: on this
         corpus rule 4 fires zero times, and if a future corpus makes it fire the
         reader has to see that before reading the rate.

    Rule 3 prefers the LATEST mention at or before `after_msg`. A model answering
    at that point is working from the most recent thing it was told; the earliest
    match would anchor on a mention the conversation has since corrected.
    """
    by_id = {item.id: item for item in case.pii}
    bound = [by_id[item_id] for item_id in call.pii_items if item_id in by_id]

    for item in bound:
        if item.tool_param == argument:
            return Located(msg=item.msg, start=item.start, end=item.end,
                           item_id=item.id, how="tool_param")
    for item in bound:
        offset = item.value.find(expected)
        if not expected or offset < 0:
            continue
        start = item.start + offset
        # The offset maps into the message only because `item.value` IS the
        # slice. `_score_case` refuses a corpus where that stopped being true;
        # this is the same claim made where it is used.
        if messages[item.msg].text[start:start + len(expected)] != expected:
            continue
        return Located(msg=item.msg, start=start, end=start + len(expected),
                       item_id=item.id, how="часть значения")
    if expected:
        hits = [(index, message.text.find(expected))
                for index, message in enumerate(messages)]
        hits = [(index, offset) for index, offset in hits if offset >= 0]
        if hits:
            early = [pair for pair in hits if pair[0] <= call.after_msg]
            index, offset = (early[-1] if early else hits[0])
            return Located(msg=index, start=offset, end=offset + len(expected),
                           item_id="", how="дословно в тексте")
    return None


# --- axis 2: one argument, end to end -------------------------------------


@dataclass(frozen=True)
class ArgumentOutcome:
    """One judged argument, from what the model saw to what the tool received."""

    case_id: str
    register: str
    family: str
    tool: str
    argument: str
    pii_type: str        # "" when the argument carries no personal datum
    kind: str            # one of `schema.BREAK_KINDS`, or "" for a non-PII arg
    intact: bool         # non-PII only: did it arrive byte-identical
    touched: bool        # the gateway substituted something inside this argument
    expected: str
    model_saw: str
    restored: str
    how: str


def _restore_call(call: schema.ExpectedCall, model_args: dict[str, str],
                  vault: Vault) -> dict[str, str]:
    """The tool call as the customer's tool receives it.

    Through `unmask_arguments`, which is the production endpoint for this leg and
    is NOT `unmask_chunk`: a real value is arbitrary text and «ООО "Заря"»
    spliced into a JSON string by flat replacement injects two bare quotes. On
    Russian business traffic that is the common case.
    """
    payload = dict(call.arguments)
    payload.update(model_args)
    restored = unmask_arguments(
        json.dumps(payload, ensure_ascii=False), vault)
    try:
        parsed = json.loads(restored)
    except json.JSONDecodeError:
        # The gateway returned something that is no longer JSON. That is a broken
        # call and it must not disappear into an exception — every judged
        # argument is reported as unrecoverable.
        return {name: "" for name in payload}
    return {str(name): str(value) for name, value in parsed.items()}


def _break_kind(item: schema.PiiItem, expected: str, model_saw: str,
                restored: str, substituted: bool,
                others: list[tuple[str, str]], vault: Vault) -> str:
    """Name what happened to one value between the customer and the tool.

    `residual` and `not_resolved` are decided HERE and not in
    `schema.classify_break`, which says so itself: both need the vault, and both
    describe a substitute that came back as a substitute rather than a value that
    came back wrong.

      residual      — a WHOLE minted token still stands in the argument. The
                      customer's tool executed on a person who does not exist,
                      with a 200 and nothing in the log.
      not_resolved  — the gateway substituted and nothing came back, because what
                      the model copied was not a token the vault could find. The
                      shape that produces it is a substitute the model only had
                      PART of: an address masked into one phrase cannot fill
                      `street` and `house` apart, and half a fake is in no vault.

    The order is specific-first. A whole surviving token is a stronger statement
    than «nothing came back», and reporting the weaker one would lose the fact
    that this exact string is ours.
    """
    if schema.same_value(restored, expected, item.type):
        return "ok"
    if residual_tokens(restored, vault):
        return "residual"
    if substituted and restored == model_saw:
        return "not_resolved"
    return schema.classify_break(item, expected, restored, others)


def _score_call(case: schema.Case, call: schema.ExpectedCall,
                messages: tuple[Masked, ...],
                values: list[tuple[str, str, str]],
                vault: Vault) -> tuple[list[ArgumentOutcome], int]:
    """One reference call, simulated through the gateway.

    `values` holds (identity, type, canonical) for every person and place in this
    case AND in its `preceded_by` chain. A restored value matching one of them
    that belongs to somebody ELSE is `other_person` — the worst outcome the
    product has, because the tool returned 200 and acted on a real human being
    who is not the one the conversation was about.
    """
    by_id = {item.id: item for item in case.pii}
    model_args: dict[str, str] = {}
    located: dict[str, Located] = {}
    touched: dict[str, bool] = {}
    unlocatable = 0
    for argument in call.judged_args:
        expected = call.arguments.get(argument, "")
        where = _locate(case, call, argument, expected, messages)
        if where is None:
            unlocatable += 1
            model_args[argument] = expected
            continue
        located[argument] = where
        raw = messages[where.msg].text[where.start:where.end]
        seen = _seen(messages[where.msg], where.start, where.end)
        # THE FICTION, STATED EXACTLY. Where the gateway SUBSTITUTED, the model
        # can only copy the substitute — it never saw anything else, and what
        # happens next is the gateway's doing. Where the gateway touched nothing,
        # the model saw the real value and emits the reference argument, because
        # that is what it would have emitted with no gateway in the path at all.
        #
        # Using the raw surface there instead would charge this axis for a
        # DETECTION miss: «широкову» went to the model in the clear, the reference
        # wants «Широкова», and the normalisation between them is the model's own
        # — it would have happened either way. Axis 1 already counts that miss,
        # and one defect moving two numbers leaves a reader unable to tell how
        # many defects there were.
        touched[argument] = seen != raw
        model_args[argument] = (
            _model_writes(seen, expected, argument, where.how,
                          by_id.get(where.item_id or ""),
                          f"{case.id}|{call.name}|{argument}")
            if seen != raw else expected)

    restored = _restore_call(call, model_args, vault)

    outcomes: list[ArgumentOutcome] = []
    for argument in call.judged_args:
        if argument not in located:
            continue
        where = located[argument]
        expected = call.arguments.get(argument, "")
        model_saw = model_args[argument]
        came_back = restored.get(argument, "")
        substituted = touched[argument]
        if where.item_id:
            item = by_id[where.item_id]
            others = [(kind, value) for identity, kind, value in values
                      if identity != item.identity]
            kind = _break_kind(item, expected, model_saw, came_back,
                               substituted, others, vault)
            outcomes.append(ArgumentOutcome(
                case_id=case.id, register=case.register, family=case.family,
                tool=call.name, argument=argument, pii_type=item.type,
                kind=kind, intact=(kind == "ok"), touched=substituted,
                expected=expected, model_saw=model_saw, restored=came_back,
                how=where.how))
            continue
        # NO PERSONAL DATUM HERE, so the demand is byte identity and nothing
        # softer. An order number that comes back as a different order number is
        # a broken call even though every character of it is well formed, and
        # this is the column a masked «заказ сорок семь» lands in.
        outcomes.append(ArgumentOutcome(
            case_id=case.id, register=case.register, family=case.family,
            tool=call.name, argument=argument, pii_type="", kind="",
            intact=(came_back == expected), touched=substituted,
            expected=expected, model_saw=model_saw, restored=came_back,
            how=where.how))
    return outcomes, unlocatable


# --- axis 2: the tool contract --------------------------------------------


def _contract(tools: tuple[dict[str, object], ...]) -> str:
    """The part of a tool schema the model dispatches on.

    Names, parameter names, enum values and the required list — everything a
    change to which makes the reference call unreachable. Descriptions are NOT
    here: masking a worked example inside one is the product working as designed.
    """
    shape: list[object] = []
    for tool in tools:
        function = tool.get("function")
        if not isinstance(function, dict):
            shape.append(sorted(tool.keys()))
            continue
        parameters = function.get("parameters")
        properties: dict[str, object] = {}
        required: list[object] = []
        if isinstance(parameters, dict):
            raw = parameters.get("properties")
            if isinstance(raw, dict):
                properties = {
                    str(name): (sorted(str(v) for v in field["enum"])
                                if isinstance(field, dict)
                                and isinstance(field.get("enum"), list)
                                else "")
                    for name, field in raw.items()}
            if isinstance(parameters.get("required"), list):
                required = sorted(str(v) for v in parameters["required"])
        shape.append([str(function.get("name", "")),
                      sorted(properties.items()), required])
    return json.dumps(shape, ensure_ascii=False, sort_keys=True)


def _dispatch_intact(case: schema.Case, masked_tools: object,
                     messages: tuple[Masked, ...]) -> str:
    """"" when dispatch survived masking, else what broke.

    Two ways it can break and both have shipped elsewhere: the schema itself is
    rewritten, or the tool NAME is masked out of the system prompt that tells the
    model to use it. The second is invisible to a schema comparison, and a
    gateway that masks a system prompt is one instruction away from it.
    """
    if not isinstance(masked_tools, (list, tuple)):
        return "инструменты вернулись не списком"
    before = _contract(tuple(case.tools))
    after = _contract(tuple(tool for tool in masked_tools
                            if isinstance(tool, dict)))
    if before != after:
        return "контракт инструмента изменён маскировкой"
    names = {call.name for call in case.calls}
    for name in sorted(names):
        for message in messages:
            if name in message.text and name not in message.masked:
                return f"имя инструмента {name!r} замаскировано в подсказке"
    return ""


# --- axis 3: the simulated reply ------------------------------------------


def _simulated_reply(case: schema.Case,
                     messages: tuple[Masked, ...]) -> tuple[tuple[str, str, str], ...]:
    """What a perfect agent would write back, in the form it saw.

    Returns one (required value, its type, the line the agent writes) per demand.

    THE SUBSTITUTES ALONE, ONE PER LINE, AND NO PROSE. Any frame we add is our
    invention and could itself change what `unmask_text` does with the value —
    the name and place windows it scans are sensitive to neighbouring words. A
    reply made of exactly the values the case demands is the only version of this
    fiction that measures the gateway and not our writing.
    """
    lines: list[tuple[str, str, str]] = []
    for required in case.final.must_contain:
        placed = False
        for item in case.pii:
            if item.canonical == required or item.value == required:
                lines.append((required, item.type,
                              _seen(messages[item.msg], item.start, item.end)))
                placed = True
                break
        if placed:
            continue
        for index, message in enumerate(messages):
            offset = message.text.find(required)
            if offset >= 0:
                lines.append((required, "",
                              _seen(messages[index], offset,
                                    offset + len(required))))
                placed = True
                break
        if not placed:
            # The value the reply must carry is nowhere in the transcript, so the
            # agent would have to produce it from a tool result the corpus did
            # not script. Written as-is: the gateway had no chance to touch it.
            lines.append((required, "", required))
    return tuple(lines)


def _missing(demands: tuple[tuple[str, str, str], ...],
             restored: list[str]) -> tuple[str, ...]:
    """Which demanded values did NOT come back, compared the way the type allows.

    A SUBSTRING TEST ALONE MANUFACTURES FAILURES HERE, and 27 of the corpus's 181
    demands are the shape that does it: `must_contain` holds «Гусева, 81, кв.
    117» while the customer SAID «гусева восемьдесят один квартира сто
    семнадцать», so the detokeniser returns a form no substring of the reference
    matches. That is a difference of FORM, and `schema.same_value` is the project's
    one rule about when two forms are the same value — a phone by its last ten
    digits, a document by all of them, text by casefold.

    The substring test stays as the fallback, because a REAL agent's reply is
    prose with the value inside it and there is nothing to line up against.
    """
    absent: list[str] = []
    paired = len(restored) == len(demands)
    for index, (required, kind, _line) in enumerate(demands):
        if paired and kind in schema.TYPES:
            if schema.same_value(restored[index], required, kind):
                continue
        if required.casefold() in "\n".join(restored).casefold():
            continue
        absent.append(required)
    return tuple(absent)


def _answer_request(case: schema.Case,
                    demands: tuple[tuple[str, str, str], ...],
                    vault: Vault) -> JudgeRequest:
    """The reply as the CUSTOMER sees it, with the vault facts already decided."""
    reply = "\n".join(line for _value, _kind, line in demands)
    restored = unmask_text(reply, vault)
    surviving = tuple(residual_tokens(restored, vault))
    opaque = tuple(value for value in surviving
                   if value.startswith(_OPAQUE_PREFIX))
    return JudgeRequest(
        case_id=case.id,
        question=("остались ли настоящие ПД в ответе клиенту, и не выдана ли "
                  "подмена за настоящее значение"),
        answer=restored,
        must_contain=case.final.must_contain,
        must_not_contain=case.final.must_not_contain,
        closed_answer=case.final.answer,
        substitutes_present=surviving,
        substitutes_minted=tuple(vault.minted_tokens()),
        residual_present=opaque,
        missing=_missing(demands, restored.split("\n")))


# --- links: whose call is it ----------------------------------------------


_STEM = 4


def _one_person(left: str, right: str) -> bool:
    """Whether two restored values name the same person or place.

    THREE THINGS THIS IS NOT, and each was tried:

      * not byte equality. A dialogue saying «Иванов Пётр Сергеевич» once and
        «Петру» later is one person mentioned two ways, and the product follows
        both rules — same identity, and a one-word mention still gets one word.
        The shorter being made of the longer's words is what says so.
      * not a whole-word subset either. Detokenisation puts the value back IN THE
        CASE THE SENTENCE ASKED FOR (`redact._in_case_of`), so «Леонид Макаров»
        and «Леониду» are one man and share no whole word. Judging that a defect
        would report the product's own grammatical agreement as a broken link.
      * NOT MORPHOLOGY. A benchmark that has to be runnable against a competing
        gateway may not import pymorphy to decide who somebody is. A four-letter
        prefix is the smallest thing that outlives a Russian case ending, and it
        errs toward NOT reporting a violation — the safe direction for a
        diagnostic, which invents no defect it cannot see.
    """
    left_stems = {word.casefold()[:_STEM] for word in left.split()}
    right_stems = {word.casefold()[:_STEM] for word in right.split()}
    return left_stems <= right_stems or right_stems <= left_stems


# --- the run --------------------------------------------------------------


@dataclass(frozen=True)
class Tally:
    """Everything the report prints. Counters only — no rates are stored.

    A stored rate is a rate somebody can compute with the wrong denominator
    later; every share in the report is derived at print time from a pair that
    is printed beside it.
    """

    recall: dict[tuple[str, str], list[int]]
    values: dict[tuple[str, str], set[str]]
    weighted: dict[str, list[tuple[bool, float]]]
    by_selection: dict[str, list[int]]
    optional: list[int]
    negatives: dict[tuple[str, str], list[int]]
    negative_values: dict[tuple[str, str], set[str]]
    unclaimed: list[int]
    dispatch: list[int]
    whole_calls: list[int]
    plain_args: list[int]
    pii_args: list[int]
    touched_args: list[int]
    breaks: dict[str, int]
    breaks_by_type: dict[tuple[str, str], list[int]]
    unlocatable: list[int]
    links: dict[str, list[int]]
    answers: dict[str, int]
    misses: list[tuple[str, str, str, str]]
    partials: list[tuple[str, str, str, str]]
    false_masks: list[tuple[str, str, str, str]]
    broken: list[ArgumentOutcome]
    leaks: list[tuple[str, str, str]]


def _empty_tally() -> Tally:
    return Tally(
        recall=defaultdict(lambda: [0, 0, 0]),
        values=defaultdict(set),
        weighted=defaultdict(list),
        by_selection=defaultdict(lambda: [0, 0, 0]),
        optional=[0, 0],
        negatives=defaultdict(lambda: [0, 0]),
        negative_values=defaultdict(set),
        unclaimed=[0],
        dispatch=[0, 0],
        whole_calls=[0, 0],
        plain_args=[0, 0],
        pii_args=[0, 0],
        touched_args=[0, 0],
        breaks=defaultdict(int),
        breaks_by_type=defaultdict(lambda: [0, 0]),
        unlocatable=[0],
        links=defaultdict(lambda: [0, 0]),
        answers=defaultdict(int),
        misses=[],
        partials=[],
        false_masks=[],
        broken=[],
        leaks=[])


def _order(cases: list[schema.Case]) -> list[schema.Case]:
    """Cases in an order where a `preceded_by` always ran first.

    `scope` is a pair of conversations inside ONE tenant vault and there is no
    honest way to state «these two must NOT be linked» inside one case. Running
    the second half first would ask the vault a question about a row that does
    not exist yet, and it would answer «not linked» for the wrong reason.
    """
    by_id = {case.id: case for case in cases}
    ordered: list[schema.Case] = []
    placed: set[str] = set()

    def place(case: schema.Case, guard: frozenset[str]) -> None:
        if case.id in placed or case.id in guard:
            return
        parent = by_id.get(case.preceded_by)
        if parent is not None:
            place(parent, guard | {case.id})
        if case.id not in placed:
            placed.add(case.id)
            ordered.append(case)

    for case in cases:
        place(case, frozenset())
    return ordered


def _groups(cases: list[schema.Case]) -> list[list[schema.Case]]:
    """Cases grouped by the vault they must share.

    ONE VAULT PER GROUP AND NOT ONE PER RUN. A tenant's vault is shared across
    conversations in production, but a corpus is not a tenant: 2 000 unrelated
    conversations in one vault exhaust the substitute pools, and an exhausted
    pool is a 5xx, not a measurement. A group is the connected component under
    `preceded_by` — exactly the cases whose claims are about each other.
    """
    parent: dict[str, str] = {case.id: case.id for case in cases}

    def root(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    known = {case.id for case in cases}
    for case in cases:
        if case.preceded_by in known:
            parent[root(case.id)] = root(case.preceded_by)
    grouped: dict[str, list[schema.Case]] = defaultdict(list)
    for case in cases:
        grouped[root(case.id)].append(case)
    return list(grouped.values())


def _tally_detection(case: schema.Case, messages: tuple[Masked, ...],
                     produced: list[schema.MaskedSpan], tally: Tally,
                     only_type: str, dump: int) -> None:
    """AXIS 1. Recall, coverage, and the negatives, per every cut."""
    weight = case.provenance.weight
    for item in case.pii:
        if only_type and item.type != only_type:
            continue
        verdict = schema.span_verdict(item, produced)
        if item.duty == "optional":
            # Its own column, never folded into recall. `optional` is a LEGAL
            # category and not a hedge: masking «улица Пушкина» is not an error
            # and missing it is not a leak, so it belongs in neither numerator.
            tally.optional[1] += 1
            tally.optional[0] += int(verdict != "missed")
            continue
        found = verdict != "missed"
        whole = verdict == "covered"
        for key in ((item.type, "type"), (case.register, "register"),
                    (case.family, "family"), (case.context, "context"),
                    ("ВСЕГО", "type")):
            row = tally.recall[key]
            row[0] += 1
            row[1] += int(found)
            row[2] += int(whole)
            tally.values[key].add(item.canonical.casefold())
        tally.weighted["recall"].append((found, weight))
        tally.weighted["coverage"].append((whole, weight))
        stratum = tally.by_selection[case.provenance.selection]
        stratum[0] += 1
        stratum[1] += int(found)
        stratum[2] += int(whole)
        if not found and len(tally.misses) < dump * 8:
            tally.misses.append((case.id, item.type, item.value,
                                 messages[item.msg].text))
        elif found and not whole and len(tally.partials) < dump * 8:
            tally.partials.append((case.id, item.type, item.value,
                                   _leaked_tail(item, produced,
                                                messages[item.msg].text)))

    masked_negatives = {(neg.msg, neg.start, neg.end)
                        for neg in schema.false_masks(case, produced)}
    for negative in case.negatives:
        hit = (negative.msg, negative.start, negative.end) in masked_negatives
        for key in ((negative.family, "family"), (case.register, "register"),
                    ("ВСЕГО", "total")):
            row = tally.negatives[key]
            row[1] += 1
            row[0] += int(not hit)
            tally.negative_values[key].add(negative.value.casefold())
        if hit and len(tally.false_masks) < dump * 8:
            tally.false_masks.append((case.id, negative.value, negative.why,
                                      messages[negative.msg].text))

    # DIAGNOSTIC, NEVER FOLDED INTO PRECISION. The corpus cannot adjudicate a
    # span it never claimed — that is what `audit_unlabelled` is for on the build
    # side — so a count is all this may honestly be.
    claimed = [(item.msg, item.start, item.end) for item in case.pii]
    claimed += [(neg.msg, neg.start, neg.end) for neg in case.negatives]
    for span in produced:
        if not any(msg == span.msg and start < span.end and end > span.start
                   for msg, start, end in claimed):
            tally.unclaimed[0] += 1


def _tally_calls(case: schema.Case, messages: tuple[Masked, ...],
                 masked_tools: object, vault: Vault, tally: Tally,
                 chain: dict[str, list[tuple[str, str, str]]],
                 only_type: str, dump: int) -> None:
    """AXIS 2. Dispatch, the arguments with no personal datum, and the ones with."""
    if case.calls:
        tally.dispatch[1] += 1
        broken = _dispatch_intact(case, masked_tools, messages)
        if not broken:
            tally.dispatch[0] += 1
        elif len(tally.leaks) < dump * 8:
            tally.leaks.append((case.id, "диспетчеризация", broken))

    # Every identity this case can be confused with: its own, plus everything the
    # `preceded_by` chain put in the same tenant vault. `scope` exists to prove
    # the second half of that list stays out of this conversation's answers.
    values = ([(item.identity, item.type, item.canonical) for item in case.pii]
              + chain.get(case.preceded_by, []))
    chain[case.id] = values

    for call in case.calls:
        outcomes, unlocatable = _score_call(case, call, messages, values, vault)
        tally.unlocatable[0] += unlocatable
        if not only_type:
            # THE OWNER'S QUESTION IS AT THE CALL LEVEL — «попал ли агент в
            # ЭТАЛОННЫЙ вызов с ЭТАЛОННЫМИ аргументами» — and one address masked
            # into a bare settlement breaks three arguments of one call. The
            # per-argument rate says how much was lost; this says how often the
            # call the customer needed was made at all, and only every judged
            # argument arriving counts. Suppressed under `--type`, where the
            # other arguments of the call are deliberately not being scored.
            tally.whole_calls[1] += 1
            tally.whole_calls[0] += int(
                all(outcome.intact for outcome in outcomes) and not unlocatable)
        for outcome in outcomes:
            if only_type and outcome.pii_type != only_type:
                continue
            if not outcome.pii_type:
                tally.plain_args[1] += 1
                tally.plain_args[0] += int(outcome.intact)
                if not outcome.intact and len(tally.broken) < dump * 8:
                    tally.broken.append(outcome)
                continue
            tally.pii_args[1] += 1
            tally.pii_args[0] += int(outcome.kind == "ok")
            if outcome.touched:
                tally.touched_args[1] += 1
                tally.touched_args[0] += int(outcome.kind == "ok")
            tally.breaks[outcome.kind] += 1
            row = tally.breaks_by_type[(outcome.pii_type, "type")]
            row[1] += 1
            row[0] += int(outcome.kind == "ok")
            if outcome.kind != "ok" and len(tally.broken) < dump * 8:
                tally.broken.append(outcome)


def _tally_links(case: schema.Case, messages: tuple[Masked, ...], vault: Vault,
                 tally: Tally, substitutes: dict[str, str], dump: int) -> None:
    """WHOSE CALL IT IS. Part of axis 2, not a fourth axis.

    A link expectation decides which real human the tool acts on. Two people
    wearing one pseudonym means whichever of them the call names, the other one's
    call lands on him — and that outcome can be reached with every argument
    comparing equal, which is why it is measured here and not inferred from the
    break kinds.
    """
    for item in case.pii:
        rendered = _seen(messages[item.msg], item.start, item.end)
        if rendered != item.value:
            substitutes[f"{case.id}/{item.id}"] = rendered

    for link in case.links:
        if link.kind == "unjudged":
            tally.links["unjudged"][1] += 1
            continue
        left = substitutes.get(f"{case.id}/{link.left}")
        right = substitutes.get(f"{link.case or case.id}/{link.right}")
        if left is None or right is None:
            # One of the two never got a substitute, so there is no linking
            # decision to judge. Counted apart rather than passed: a link that
            # holds because nothing was masked is not the gateway being right.
            tally.links["не замаскировано"][1] += 1
            continue
        row = tally.links[link.kind]
        row[1] += 1
        if link.kind == "different":
            # THE SUBSTITUTES THEMSELVES, and byte equality is the whole test:
            # one pseudonym for two people is one identity to the model AND one
            # row to the tool.
            held = left.casefold() != right.casefold()
            evidence = f"{left!r} и {right!r} — одна подмена на двоих"
        else:
            # WHAT THE TOOL RECEIVES, not what the model read. One person named
            # «Савва Панов» once and «Савве» later gets one substitute in two
            # forms — `_token_for_text` declines it into the sentence — and
            # comparing the surfaces would call the product's own grammatical
            # agreement a defect. So the question is asked after detokenisation.
            left_real = unmask_text(left, vault)
            right_real = unmask_text(right, vault)
            held = _one_person(left_real, right_real)
            evidence = (f"{left!r} -> {left_real!r} против "
                        f"{right!r} -> {right_real!r}")
        row[0] += int(held)
        if not held and len(tally.leaks) < dump * 8:
            tally.leaks.append((case.id, f"связь {link.kind}",
                                f"{evidence} — {link.why[:52]}"))


def _tally_answer(case: schema.Case, messages: tuple[Masked, ...], vault: Vault,
                  judge: Judge, tally: Tally, dump: int) -> None:
    """AXIS 3. The simulated reply, out through the real detokenisation leg."""
    if "answer" not in schema.judged_axes(case):
        return
    if not case.final.must_contain:
        # NOTHING TO SIMULATE, SO NOTHING TO PASS. A case whose only demand is
        # «this must NOT appear» is satisfied by an empty reply, and scoring an
        # empty reply as clean would turn the hardest claim in the corpus into
        # free marks. It waits for the live run and the judge.
        tally.answers[UNJUDGED] += 1
        return
    demands = _simulated_reply(case, messages)
    verdict = judge(_answer_request(case, demands, vault))
    tally.answers[verdict.verdict] += 1
    if verdict.verdict not in ("clean", UNJUDGED) and len(tally.leaks) < dump * 8:
        tally.leaks.append((case.id, verdict.verdict, verdict.why))


def _score_case(case: schema.Case, detector: Detector, vault: Vault,
                audit: AuditLog, cache: MaskCache, tally: Tally,
                substitutes: dict[str, str],
                chain: dict[str, list[tuple[str, str, str]]],
                judge: Judge, only_type: str, dump: int) -> None:
    """One case through the production path, then the three axes over it."""
    conversation = case.conversation_id or conversation_key(
        [{"role": message.role, "content": message.content}
         for message in case.messages])
    scoped = vault.for_conversation(conversation)
    context = MaskContext(detector=detector, vault=scoped, audit=audit,
                          cache=cache, org_id=_ORG, agent_id=_AGENT,
                          conversation_id=conversation)

    messages = tuple(
        _mask_message(schema.message_text(case, index), detector, scoped)
        for index in range(len(case.messages)))
    # Masked AFTER the messages, as `proxy._mask_request` does: a value first
    # seen in a tool description must get the substitute the conversation
    # already minted, not a second one.
    masked_tools = mask_tools(list(case.tools), context, False)
    produced = _observed(messages)

    # REFUSE RATHER THAN SCORE. Every offset in this file — the leaked tail, the
    # slice a `street` argument is carved out of, the region a simulated reply
    # quotes — indexes the message text through the gold span. A span that no
    # longer holds its own value moves all of them at once, and the report would
    # go on printing numbers that look like numbers.
    for item in case.pii:
        held = messages[item.msg].text[item.start:item.end]
        if held != item.value:
            raise schema.InvalidCase(
                f"{case.id}: item {item.id} claims {item.value!r} at "
                f"[{item.start}:{item.end}] of message {item.msg}, which holds "
                f"{held!r} — every offset in this case is wrong")

    _tally_detection(case, messages, produced, tally, only_type, dump)
    _tally_calls(case, messages, masked_tools, vault, tally, chain,
                 only_type, dump)
    _tally_links(case, messages, vault, tally, substitutes, dump)
    _tally_answer(case, messages, vault, judge, tally, dump)


def score(cases: list[schema.Case], judge: Judge, only_type: str,
          dump: int) -> Tally:
    """Run every case through the gateway and return the counters.

    THE PUBLIC ENTRY POINT, and it takes the judge. The live-run phase imports
    this, hands it an LLM judge, and gets the same Tally back — there is no other
    hook to write and no branch in this file that knows which judge it has.

    `load_dev_bundle()` is NOT called here. Leasing is the caller's decision: a
    harness that already holds a lease must not have a second one built
    underneath it, and a caller that forgot gets `BundleNotLeased` — which is the
    designed failure and says exactly what is missing.
    """
    detector = Detector()
    audit = AuditLog(":memory:")
    cache = MaskCache(4096)
    tally = _empty_tally()
    substitutes: dict[str, str] = {}
    chain: dict[str, list[tuple[str, str, str]]] = {}
    started = time.time()
    done = 0
    for group in _groups(cases):
        vault = Vault(":memory:", _ORG)   # scope: see `_groups`
        for case in _order(group):
            _score_case(case, detector, vault, audit, cache, tally,
                        substitutes, chain, judge, only_type, dump)
            done += 1
            if done % 100 == 0:
                rate = done / max(time.time() - started, 1e-9)
                print(f"  … {done}/{len(cases)} случаев, {rate:.1f}/с",
                      file=sys.stderr)
    return tally


# --- report ---------------------------------------------------------------


def _share(hit: int, total: int) -> str:
    """A percentage, or a COUNT when the denominator cannot carry one.

    `schema.MIN_TYPE_DENOMINATOR` states the rule and the reason: «полнота 99%»
    over two CARD instances is a lie by omission, and at nano every type is below
    it — which is the honest reading of a thirty-case suite.
    """
    if total == 0:
        return "       —"
    if total < schema.MIN_TYPE_DENOMINATOR:
        return f"{hit}/{total}".rjust(8)
    return f"{hit / total * 100:7.1f}%"


def _cut(tally: Tally, axis: str, keys: list[str], title: str) -> None:
    rows = [(key, tally.recall[(key, axis)]) for key in keys
            if tally.recall.get((key, axis), [0])[0]]
    if not rows:
        return
    print(f"\n{title:<14}{'ВХОЖД':>7}{'РАЗЛИЧ':>8}{'ПОЛНОТА':>9}{'ПОКРЫТИЕ':>10}"
          f"{'ХВОСТ':>7}")
    print("-" * 55)
    for key, row in rows:
        distinct = len(tally.values[(key, axis)])
        print(f"{key:<14}{row[0]:>7}{distinct:>8}{_share(row[1], row[0]):>9}"
              f"{_share(row[2], row[0]):>10}{row[1] - row[2]:>7}")


def _report(tally: Tally, cases: list[schema.Case], tier_name: str,
            digest: str, dump: int) -> None:
    print(f"\nAgentPII-RU v3 · случаев: {len(cases)} · ярус: {tier_name} · "
          f"корпус {digest[:12]}")
    print("судья оси 3: детерминированная заглушка "
          "(живой прогон — LLM-as-judge, claude-sonnet-5)")

    print("\n" + "=" * 72)
    print("ОСЬ 1. ДЕТЕКЦИЯ")
    print("=" * 72)
    print("ПОЛНОТА — спан найден И С ТЕМ ЖЕ ТИПОМ. ПОКРЫТИЕ — найден ЦЕЛИКОМ.")
    print("Разница между ними — утёкший хвост, ушедший к модели в открытую.")
    print("РАЗЛИЧ — сколько РАЗНЫХ значений стоит за вхождениями: повтор не есть")
    print("независимое наблюдение, и интервал по вхождениям врёт в нашу пользу.")

    _cut(tally, "type", list(schema.TYPES) + ["ВСЕГО"], "ТИП")
    _cut(tally, "register", list(schema.REGISTERS), "РЕГИСТР")
    _cut(tally, "family", list(schema.FAMILIES), "СЕМЕЙСТВО")
    _cut(tally, "context", list(schema.CONTEXT_RUNGS), "ДЛИНА")

    if tally.by_selection:
        print(f"\n{'СТРАТА':<14}{'ВХОЖД':>7}{'ПОЛНОТА':>9}{'ПОКРЫТИЕ':>10}")
        print("-" * 40)
        for name in schema.SELECTIONS:
            row = tally.by_selection.get(name)
            if not row or not row[0]:
                continue
            print(f"{name:<14}{row[0]:>7}{_share(row[1], row[0]):>9}"
                  f"{_share(row[2], row[0]):>10}")
        recall = schema.weighted_rate(tally.weighted["recall"])
        coverage = schema.weighted_rate(tally.weighted["coverage"])
        print(f"{'взвешенно':<14}{'':>7}{recall * 100:>8.1f}%"
              f"{coverage * 100:>9.1f}%")
        print("  marker отобран теми же словами, что читает детектор, и завышен")
        print("  по построению; взвешенная строка несёт долю выборки (weight).")

    total_negatives = tally.negatives.get(("ВСЕГО", "total"), [0, 0])
    if total_negatives[1]:
        print(f"\n{'НЕГАТИВЫ':<22}{'ВХОЖД':>7}{'РАЗЛИЧ':>8}{'ЧИСТО':>9}")
        print("-" * 46)
        for family in schema.NEGATIVE_FAMILIES:
            row = tally.negatives.get((family, "family"))
            if not row or not row[1]:
                continue
            print(f"{family:<22}{row[1]:>7}"
                  f"{len(tally.negative_values[(family, 'family')]):>8}"
                  f"{_share(row[0], row[1]):>9}")
        print("-" * 46)
        print(f"{'ВСЕГО':<22}{total_negatives[1]:>7}"
              f"{len(tally.negative_values[('ВСЕГО', 'total')]):>8}"
              f"{_share(total_negatives[0], total_negatives[1]):>9}")

    if tally.optional[1]:
        print(f"\nнеобязательные (optional): замаскировано "
              f"{tally.optional[0]}/{tally.optional[1]} — маска не ошибка, "
              f"пропуск не утечка, в полноту не входит")
    print(f"диагностика: спанов вне золота и вне негативов: {tally.unclaimed[0]} "
          f"(корпус их не судит — ни за, ни против)")

    print("\n" + "=" * 72)
    print("ОСЬ 2. ВЫЗОВ ИНСТРУМЕНТА ПРОТИВ ЭТАЛОНА")
    print("=" * 72)
    print("Сверка с ЭТАЛОННЫМ вызовом, не с плечом без шлюза. Модель принята")
    print("идеальной: где шлюз ПОДМЕНИЛ — она копирует подмену, где не тронул —")
    print("пишет эталон, как написала бы и без шлюза. Ломается дальше — шлюз.")
    if tally.dispatch[1]:
        print(f"\nтот ли инструмент  — контракт цел и имя дожило до подсказки: "
              f"{tally.dispatch[0]}/{tally.dispatch[1]} = "
              f"{_share(tally.dispatch[0], tally.dispatch[1]).strip()}")
    if tally.plain_args[1]:
        print(f"те ли аргументы    — без ПД (номер заказа, id клиента), пришли "
              f"дословно: {tally.plain_args[0]}/{tally.plain_args[1]} = "
              f"{_share(tally.plain_args[0], tally.plain_args[1]).strip()}")
    if tally.whole_calls[1]:
        print(f"ЭТАЛОННЫЙ ВЫЗОВ ЦЕЛИКОМ — все судимые аргументы пришли верными: "
              f"{tally.whole_calls[0]}/{tally.whole_calls[1]} = "
              f"{_share(tally.whole_calls[0], tally.whole_calls[1]).strip()}")
    if tally.pii_args[1]:
        print(f"настоящее значение — дошло до аргумента через unmask_arguments: "
              f"{tally.pii_args[0]}/{tally.pii_args[1]} = "
              f"{_share(tally.pii_args[0], tally.pii_args[1]).strip()}")
        print(f"   из них шлюз действительно подменял: "
              f"{tally.touched_args[1]}, дошло "
              f"{tally.touched_args[0]}/{tally.touched_args[1]} = "
              f"{_share(tally.touched_args[0], tally.touched_args[1]).strip()}"
              f" — вторая строка и есть вклад шлюза, первая включает значения,")
        print("   которых он не коснулся (их промах уже посчитан осью 1)")
        print(f"\n{'ТИП':<14}{'АРГУМ':>7}{'ДОШЛО':>9}")
        print("-" * 32)
        for kind in schema.TYPES:
            row = tally.breaks_by_type.get((kind, "type"))
            if not row or not row[1]:
                continue
            print(f"{kind:<14}{row[1]:>7}{_share(row[0], row[1]):>9}")
        broken = {kind: count for kind, count in tally.breaks.items()
                  if kind != "ok"}
        if broken:
            print("\nрасхождения с эталоном:")
            for kind, count in sorted(broken.items(), key=lambda p: -p[1]):
                print(f"  {kind:<20}{count:>6}")
    if tally.unlocatable[0]:
        print(f"\nаргументов, не найденных в стенограмме: {tally.unlocatable[0]} "
              f"— шлюз их не касался, из счёта исключены")
    judged_links = {name: row for name, row in tally.links.items()
                    if name in ("same", "different")}
    if judged_links:
        print("\nсвязи подмен (кому уйдёт вызов):")
        for name, row in sorted(judged_links.items()):
            label = ("один человек — одна подмена" if name == "same"
                     else "разные люди — разные подмены")
            print(f"  {label:<32}{row[0]}/{row[1]} = "
                  f"{_share(row[0], row[1]).strip()}")
        for name in ("unjudged", "не замаскировано"):
            row = tally.links.get(name)
            if row and row[1]:
                print(f"  {name:<32}{row[1]} (не судится)")

    print("\n" + "=" * 72)
    print("ОСЬ 3. УТЕЧКА В ИТОГОВОМ ОТВЕТЕ")
    print("=" * 72)
    print("Офлайн: ответ идеального агента собран из того, ЧТО ОН ВИДЕЛ, и")
    print("прогнан через unmask_text — настоящий обратный путь. Волт знает")
    print("каждую отчеканенную подмену точно, поэтому «выдал подмену за")
    print("настоящее» здесь измеряется, а не оценивается на глаз.")
    print("value_missing включает и РАЗНИЦУ ФОРМЫ (эталон «Баранова, 24»,")
    print("вернулось «баранова двадцать четыре») — что именно, видно в дампе.")
    judged = sum(tally.answers.values())
    if judged:
        for verdict in schema.ANSWER_VERDICTS:
            count = tally.answers.get(verdict, 0)
            if count:
                print(f"  {verdict:<20}{count:>6}  = {count / judged * 100:5.1f}%")
        unjudged = tally.answers.get(UNJUDGED, 0)
        if unjudged:
            print(f"  {UNJUDGED:<20}{unjudged:>6}  = "
                  f"{unjudged / judged * 100:5.1f}%  ждёт LLM-судью")
    else:
        print("  ни одного случая с требованием к ответу в этом срезе")

    if tally.misses:
        print(f"\n--- ПРОПУЩЕНО ({len(tally.misses)}) ---")
        for case_id, kind, value, text in tally.misses[:dump]:
            print(f"  {kind:<9}{value!r:38} в {text[:56]!r}")
    if tally.partials:
        print(f"\n--- НАЙДЕНО ЧАСТИЧНО, ХВОСТ УТЁК ({len(tally.partials)}) ---")
        for case_id, kind, value, tail in tally.partials[:dump]:
            print(f"  {kind:<9}{value!r:38} к модели ушло {tail!r}")
    if tally.false_masks:
        print(f"\n--- ЗАМАСКИРОВАНО ЗРЯ ({len(tally.false_masks)}) ---")
        for case_id, value, why, text in tally.false_masks[:dump]:
            print(f"  {value!r:26} — {why[:44]}")
    if tally.broken:
        print(f"\n--- ЭТАЛОННЫЙ ВЫЗОВ РАЗОШЁЛСЯ ({len(tally.broken)}) ---")
        for outcome in tally.broken[:dump]:
            print(f"  {outcome.case_id:<22} {outcome.tool}.{outcome.argument} "
                  f"[{outcome.kind or 'изменён'}] {outcome.register}/"
                  f"{outcome.family}")
            print(f"      ждали   {outcome.expected!r}")
            print(f"      модель  {outcome.model_saw!r}")
            print(f"      пришло  {outcome.restored!r}")
    if tally.leaks:
        print(f"\n--- ОТВЕТ, СВЯЗИ И ДИСПЕТЧЕРИЗАЦИЯ ({len(tally.leaks)}) ---")
        for case_id, verdict, why in tally.leaks[:dump]:
            print(f"  {case_id:<22} {verdict:<18}{why[:78]}")


# --- entry point ----------------------------------------------------------


def _load(path: Path) -> tuple[list[schema.Case], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [schema.case_from_json(raw) for raw in payload["corpus"]]
    return cases, str(payload["digest"])


def _ladder(path: Path) -> schema.Ladder:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return schema.Ladder(
        version=int(raw["version"]), seed=int(raw["seed"]),
        corpus_sha256=str(raw["corpus_sha256"]),
        tiers={name: tuple(ids) for name, ids in raw["tiers"].items()})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?",
                        default=str(_HERE.parent / "corpus.json"))
    parser.add_argument("--ladder", default=str(_HERE.parent / "ladder.json"))
    parser.add_argument("--tier", default="max", choices=sorted(schema.TIER_SIZES))
    parser.add_argument("--family", default="", choices=[""] + list(schema.FAMILIES))
    parser.add_argument("--register", default="",
                        choices=[""] + list(schema.REGISTERS))
    parser.add_argument("--type", default="", choices=[""] + list(schema.TYPES))
    parser.add_argument("--dump", type=int, default=12,
                        help="сколько расхождений печатать в каждом разделе")
    # СУДЬЯ ПО УМОЛЧАНИЮ ДЕТЕРМИНИРОВАННЫЙ, И ЭТО НЕ ЭКОНОМИЯ. Оси 1 и 2
    # считаются по всему корпусу без модели и без сети — их можно прогнать на
    # любой машине и получить те же числа побитово. Живой судья пересматривает
    # только третью ось и только там, где строковое сравнение сказало «чисто»:
    # модель склоняет подмену, пишет число словами, пересказывает адрес — ничего
    # из этого `casefold() in` не находит.
    parser.add_argument("--judge", default="deterministic",
                        choices=("deterministic", "sdk"),
                        help="кто судит ось 3")
    parser.add_argument("--verbatim-model", action="store_true",
                        help="прежнее допущение: модель копирует подмену "
                             "дословно. Только для сравнения — оно "
                             "завышает ось 2 на ~19 пунктов")
    parser.add_argument("--judge-model", default="claude-sonnet-5")
    parser.add_argument("--judge-budget", type=float, default=2.0,
                        help="потолок трат судьи в долларах, жёсткий")
    parser.add_argument("--judge-cap", type=float, default=0.05,
                        help="потолок на один вердикт")
    args = parser.parse_args()
    global REWRITE_LIKE_A_MODEL
    REWRITE_LIKE_A_MODEL = not args.verbatim_model

    everything, digest = _load(Path(args.corpus))
    cases = schema.tier(everything, _ladder(Path(args.ladder)), args.tier)
    if args.family:
        cases = [case for case in cases if case.family == args.family]
    if args.register:
        cases = [case for case in cases if case.register == args.register]
    if args.type:
        cases = [case for case in cases
                 if any(item.type == args.type for item in case.pii)]
    if not cases:
        print("нечего считать: фильтры не оставили ни одного случая")
        return 1

    load_dev_bundle()
    judge: Judge = deterministic_judge
    if args.judge == "sdk":
        # Импорт ЗДЕСЬ, а не наверху: Agent SDK не нужен для офлайновых осей, и
        # машина без него должна считать их как ни в чём не бывало.
        from bench.agentpii3.live import judge as live
        from bench.agentpii3.live.seam import sdk_judge
        judge = sdk_judge(live.JudgeConfig(
            model=args.judge_model,
            ledger=live.SpendLedger(live.default_ledger_path(),
                                    args.judge_budget),
            query_cap_usd=args.judge_cap, retries=2, trace_path=None))
    started = time.time()
    tally = score(cases, judge, args.type, args.dump)
    _report(tally, cases, args.tier, digest, args.dump)
    bound = schema.TIER_ZERO_FAILURE_BOUND.get(args.tier)
    if bound is not None:
        print(f"\nна ярусе {args.tier} ноль отказов означает не «безошибочно», а "
              f"«истинная доля отказов ниже {bound * 100:.2f}% с 95%»")
    # SAID OUT LOUD BECAUSE IT LOOKS LIKE A DEFECT OTHERWISE. Substitutes are
    # minted with `secrets`, so two runs over the same corpus draw different
    # fakes, and whether one of them declines cleanly or resolves through a
    # partial mention is a property of the draw. A few tenths of a point of
    # movement between identical runs is the pool, not the gateway; a change
    # worth reading is larger than that and moves a named column.
    if args.judge == "sdk":
        print(f"\nсчитано за {time.time() - started:.0f} с, судья "
              f"{args.judge_model}, потолок ${args.judge_budget:.2f}")
    else:
        print(f"\nсчитано за {time.time() - started:.0f} с, без модели и без сети")
    print("ось 1 воспроизводится побитово: детекция детерминирована. оси 2 и 3 "
          "гуляют\nна доли процента — подмены чеканятся случайно (secrets), и "
          "склонится ли\nименно эта подмена, зависит от жребия. это разброс "
          "пула, а не изменение шлюза")
    return 0


if __name__ == "__main__":
    sys.exit(main())
