"""Score a masking gateway on AgentPII-RU v2. Seven offline axes, reported apart.

Every axis here assumes a PERFECT model — one that copies what it was handed and
reasons correctly over it. That isolates the gateway's own contribution, so a bad
number can never be blamed on the model. The transparency axis needs a live one
and is deliberately absent: `bench/agentrun/` owns it.

THE AXES, and each exists because a defect can pass every other one:

  1 ДЕТЕКЦИЯ     was the span found, with the right type. Beside it ПОКРЫТИЕ —
                 the share found WHOLE — printed apart and never merged, because
                 «Кзнецов Дмитрий» found as «Дмитрий» is recall AND a leaked
                 surname. Negatives are scored as hard as recall.
  2 КРУГ         did the REAL value arrive in the tool argument, through
                 `unmask_arguments` — the production path for a tool call.
  3 СОГЛАСОВАН.  one identity, one substitute; and one mention, ONE SPAN.
  4 СРАВНЕНИЕ    the contract asks whether two protected values are equal. Two
                 numbers, strict and lenient; strict is the headline.
  5 КОСВЕННОЕ    the customer never said the value — it came back from a tool.
                 Did the real one reach the next call.
  6 ПД ИЗ ИНСТР. data arriving FROM the customer's CRM, masked before the model
                 saw it. The leg v1 had no case for at all.
  7 ОБЛАСТЬ      the conversation boundary, in both directions.

CARRIED ACROSS FROM V1 UNCHANGED IN SPIRIT, because every one was paid for:

  * a hit REQUIRES the type to match. The type decides which fake shape is
    minted, and a passport masked as a phone reaches the customer's validator in
    the wrong format.
  * ПОКРЫТИЕ beside ПОЛНОТА, never merged into one number.
  * the round trip takes the value AS DETECTION SAW IT. Masking runs on
    normalised text, so handing the raw surface to the vault measures a path
    production never takes — it reported ~180 phone breaks that do not exist.
  * the vault is read READ-ONLY. The substitute this axis asks about is the one
    masking minted; minting a fresh one makes the axis pass by construction.
  * an undetected item is SKIPPED by the round trip, never failed. Axis 1 already
    counts it, and counting it twice would make one defect move two numbers and
    leave a reader unable to tell how many there were.

THREE THINGS V1 GOT WRONG AND THIS FIXES:

  * `_same_value(None, ...)` raised on `.strip()`, which made `_classify`'s
    «токен не нашёлся» branch — the branch naming the WORST outcome — unreachable
    for the life of the corpus. It survived only because a detected span always
    had a minted token on the path v1 took. The comparison now lives in
    `schema.same_value`, which is None-safe BY CONTRACT and is not restated here:
    a scorer that owns a second copy of the rule is a scorer that can disagree
    with the format about what «the same value» means.
  * the consistency axis tokenised the corpus's own ground-truth STRINGS. It
    never asked detection anything, so a one-person-two-substitutes caused by a
    SPLIT SPAN was invisible to it. It now reads what masking actually produced.
  * `conversation_id=""` everywhere, so the engine's conversation scope — the
    thing that makes a partial mention resolvable at all — was exercised in
    neither direction. Each case is masked under its own conversation, given or
    derived, and a `preceded_by` pair shares ONE tenant vault, which is the only
    way the ACROSS claim can be stated at all.

THE NUMBERS ARE NOT ALL REPRODUCIBLE, AND THAT IS A PROPERTY OF THE PRODUCT.
`vault.py` draws every substitute with `secrets`, which takes no seed — on
purpose: a predictable pool would let anyone holding one substitute predict the
next, and the pool is the whole distance between the model and a real person. So
every axis whose answer depends on WHICH fake came out is a random variable, and
running this file twice gives two slightly different numbers.

  deterministic   ПОЛНОТА, ПОКРЫТИЕ, НЕГАТИВЫ — identical across five full
                  runs, because detection never consults the vault. They are
                  also the three that gate hardest, which is not a coincidence.
  draw-dependent  everything else, marked `~` in the verdict.

AND THE SPREAD IS NOT UNIFORM, which is the part worth knowing. Measured over
five full runs: КРУГ 84.7-85.1, СОГЛАСОВАННОСТЬ 97.6-97.9, КОСВЕННОЕ 98.7-99.2 —
half a point. СРАВНЕНИЕ 60.0-62.0 over a hundred cases — two points. «НЕ
СВЯЗЫВАТЬ ЧЕРЕЗ ГРАНИЦУ» 70.0-90.0, because that cell holds TEN pairs and one
pair is ten points. A floor on that cell can only ever say «did the direction
collapse», and it is set to say exactly that and nothing finer.

Seeding it here was rejected twice over. Monkeypatching `secrets` would make the
eval take a path production does not — the rule this benchmark already learned
when minting a token straight from the corpus reported 180 phone breaks that did
not exist — and it would also hide the one thing the randomness genuinely risks:
two people drawing the SAME substitute, which `разные люди с одной подменой`
exists to count.

WHAT THE MODEL SEES, AND WHY IT IS NOT `peek_token`. The substitute spliced into
the text is INFLECTED to the case of the original (`redact._token_for_text`), and
a LINKED address is stored under a conversation-SCOPED key that `peek_token`,
which canonicalises plainly, cannot find at all. v1's `peek_token` read the
nominative row and would have reported both of those as failures of a different
kind. So the surface is read back out of `mask_text` itself — same function, same
vault, same conversation view. Anything else measures a path that does not exist.

    python3 bench/agentpii2/score.py
    python3 bench/agentpii2/score.py --tier small
    python3 bench/agentpii2/score.py --family compare --dump 40
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.agentpii2 import build  # noqa: E402
from bench.agentpii2.schema import (  # noqa: E402
    REGISTERS, TIER_ZERO_FAILURE_BOUND, Case, Ladder, PiiItem, classify_break,
    message_text, register_weighted, same_value, tier,
)
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, conversation_key, mask_messages  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.redact import mask_text, residual_tokens, unmask_arguments  # noqa: E402
from pseudex.vault import Vault  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

# THE FLOORS, and they are floors rather than targets. Each is the measured
# baseline of 30.08.2026, rounded DOWN, so dropping below one is a regression
# somebody has to explain — never a bar somebody has to reach. A threshold set
# above what the product does would make the gate red on the day it was written,
# and a gate that is red by default gets switched off within a week.
#
# `полнота` is deliberately not the highest: three quarters of this corpus's
# misses are one register — `voice_raw`, numbers spelled out in words — which the
# design doc predicted would score near zero and which nothing in the engine
# addresses. The floor describes the product as it is; the per-register table
# beside it is what says where the number comes from.
#
# A FLOOR IS ONLY AS FINE AS ITS DENOMINATOR, so the verdict prints N beside every
# one of them. «не связывать через границу» rests on TEN pairs and swung 70-90
# across five runs of an unchanged engine, so a floor at the observed minimum
# would have gone red on four of them. It is set at 60 — one pair below the worst
# seen — which is all a ten-pair cell can honestly assert: that the direction did
# not collapse. It is gated at all because it is the safety-critical one, where a
# partial mention resolves into another customer's conversation; making the cell
# meaningfully finer needs more pairs in the corpus, not a tighter number here.
# Ranges are over FIVE full runs of 30.08.2026, and a floor sits below the
# LOWEST of them — never on the last number somebody happened to see.
FLOORS: dict[str, float] = {
    "полнота": 92.0,                        # 92.9, детерминировано
    "покрытие": 90.5,                       # 91.4, детерминировано
    "негативы": 95.0,                       # 95.8, детерминировано
    "круг": 84.0,                           # 84.7-85.1
    "согласованность": 97.0,                # 97.6-97.9
    "сравнение (строго)": 58.0,             # 60.0-62.0 на ста случаях
    "косвенное": 98.0,                      # 98.7-99.2
    "ПД из инструмента": 98.0,              # 98.6
    "область: связать в разговоре": 78.0,   # 79.8-81.3
    "область: не связывать через границу": 60.0,   # 70.0-90.0 на ДЕСЯТИ парах
}

# A per-type rate whose denominator is below this prints as a COUNT.
# `schema.type_denominators` states the rule and the measurement behind it: on
# v1's corpus a ten-case draw genuinely held fewer than five instances of seven
# of the nine types, and «полнота 99%» over two CARD instances is a lie by
# omission.
SUPPRESS_BELOW = 5

# Axes downstream of the substitute draw. Marked in the verdict so a reader does
# not take a half-point move between two runs for a change in the product.
DRAW_DEPENDENT: frozenset[str] = frozenset({
    "круг", "согласованность", "сравнение (строго)", "косвенное",
    "ПД из инструмента", "область: связать в разговоре",
    "область: не связывать через границу",
})

# Types whose identity IS the string or the number, so two mentions are the same
# thing exactly when `schema.same_value` says so. Everything else — a name, a
# place — is written differently every time it is said, and gets the containment
# test below.
_LITERAL_TYPES: frozenset[str] = frozenset({
    "PHONE", "EMAIL", "INN", "SNILS", "CARD", "PASSPORT", "DATE", "PLATE",
})

# Russian address and document boilerplate, folded out before two masked surfaces
# are compared. NOT a detection vocabulary and never consulted by the engine: the
# question here is what a READER concludes from two strings, and «улица» stands
# in both of any two addresses, so leaving it in makes every pair look partly
# alike. Kept deliberately tiny — a longer list would start deciding which words
# carry identity, and that is the corpus's job, not the scorer's.
_MARKERS: frozenset[str] = frozenset({
    "г", "гор", "город", "ул", "улица", "улицы", "улице", "улицу",
    "д", "дом", "дома", "кв", "квартира", "квартиру", "квартире",
    "пр", "просп", "проспект", "проспекта", "проспекте", "пер", "переулок",
    "ш", "шоссе", "наб", "набережная", "бульвар", "проезд", "стр", "строение",
    "к", "корп", "корпус",
})


# --- comparing two masked surfaces ------------------------------------------

def _words(value: str) -> list[str]:
    """Identity-carrying tokens: alphanumeric runs, folded, boilerplate dropped."""
    runs = "".join(ch if ch.isalnum() else " " for ch in value).split()
    return [word for word in (run.casefold().replace("ё", "е") for run in runs)
            if word and word not in _MARKERS]


def _same_word(left: str, right: str) -> bool:
    """One word written two ways.

    RUSSIAN INFLECTS, AND THE SUBSTITUTE INFLECTS WITH IT. `_token_for_text` puts
    the fake into the case the sentence needs, so one person appears as «Осипова
    Стелла» in one turn and «Осипову Стеллу» in the next — one substitute, two
    surfaces. A byte comparison would report every declined mention as a second
    person and the consistency axis would be noise.

    A shared prefix within two characters of the shorter word is the test, and
    the four-character floor is what stops «Иван» matching «Игорь» through a
    two-letter stem. Lemmatising instead was rejected: it would put pymorphy3 —
    the engine's own morphology — inside the scorer, and a benchmark that shares
    a component with the thing it grades cannot report that component broken.
    """
    if left == right:
        return True
    shorter = min(len(left), len(right))
    common = 0
    while common < shorter and left[common] == right[common]:
        common += 1
    return common >= max(4, shorter - 2)


def _covers(small: list[str], large: list[str]) -> bool:
    return all(any(_same_word(word, other) for other in large) for word in small)


def _reads_as_one(left: str, right: str, entity_type: str) -> bool:
    """Whether a reader takes two masked surfaces for ONE value.

    Not byte equality, and that is the whole difficulty. A conversation that says
    «Иванов Пётр Сергеевич» once and «Петру» later named one person twice, and a
    correct gateway answers with one substitute written two ways — a one-word
    mention still gets one word back. So the test is CONTAINMENT of identity
    tokens: «Устинов Глеб Петрович» and «Глеб» are one person, while two
    independently drawn people sharing a patronymic are not, because neither
    covers the other.

    A literal type skips all of that. A phone written «+7…» and «8…» is one
    subscriber and `schema.same_value` already owns that rule; running the word
    test on an address's house number instead would make «улица Речная 73, кв.
    219» and «улица Речная 73» two different places.
    """
    if entity_type in _LITERAL_TYPES:
        return same_value(left, right)
    small, large = _words(left), _words(right)
    if not small or not large:
        return False
    if len(small) > len(large):
        small, large = large, small
    return _covers(small, large)


# --- masking one case, on the production path -------------------------------

@dataclass(frozen=True)
class Mention:
    """One gold item as masking actually left it.

    `surface` is what the model read at that position; `protected` says whether
    the real value survived there anyway; `spans` counts how many detected spans
    the item was cut into — the split v1's consistency axis could not see,
    because it never looked at detection at all.
    """

    item: PiiItem
    surface: str
    protected: bool
    detected: bool
    spans: int


class _MemoDetector:
    """`Detector` with per-text memoisation, and it is not a speed trick.

    Detection is a pure function of the text, and this run needs it twice for
    every message — once inside `mask_one` and once for the detection axis. One
    shared result guarantees the two are scoring the SAME spans: a scorer whose
    recall number and whose masking disagree about what was found is measuring
    two different gateways and reporting one number.

    Neither caller mutates the list — `mask_one` filters into a new one and
    `mask_text` only reads — so handing out the same object is safe.
    """

    def __init__(self, inner: Detector) -> None:
        self._inner = inner
        self._cache: dict[str, list[object]] = {}

    def detect(self, text: str) -> list[object]:
        hit = self._cache.get(text)
        if hit is None:
            hit = self._inner.detect(text)
            self._cache[text] = hit
        return hit


def _surface(text: str, item: PiiItem, spans: list[object], vault: Vault) -> Mention:
    """What the model read where this item stood.

    Masking is replayed over ONLY the spans touching this item, so the untouched
    prefix and suffix pin the region exactly: `mask_text` rewrites nothing outside
    [min span start, max span end], and slicing the output by the input's tail
    length recovers the region byte for byte however much the substitutes changed
    its length. Any other route means tracking splice deltas, and a benchmark that
    reimplements the splice ends up measuring its own arithmetic.

    The region is the UNION of the item and the spans, not the item alone: a span
    wider than the gold value is what the model copies, and a span narrower than
    it leaves real characters inside the region — which is exactly the partial
    leak ПОКРЫТИЕ reports.
    """
    touching = [span for span in spans
                if span.start < item.end and span.end > item.start]
    if not touching:
        return Mention(item=item, surface=text[item.start:item.end],
                       protected=False, detected=False, spans=0)
    low = min([item.start] + [span.start for span in touching])
    high = max([item.end] + [span.end for span in touching])
    masked = mask_text(text, vault, touching)
    surface = masked[low:len(masked) - (len(text) - high)]
    return Mention(item=item, surface=surface,
                   protected=item.value not in surface,
                   detected=True, spans=len(touching))


def _mask_case(case: Case, detector: _MemoDetector, vault: Vault, audit: AuditLog,
               cache: MaskCache) -> tuple[dict[str, Mention], list[list[object]], Vault]:
    """Run the whole case through masking, then read back what it produced.

    `skip_template` is FALSE — the public leg, where the customer writes the
    system message and it must be masked. `schema.validate` refuses a gold item in
    a system message, so the choice cannot move a score; it is simply the stricter
    of the two legs, and a leak out of a system prompt would count here.

    The conversation is the case's own, or DERIVED from its transcript when it
    names none. Both paths exist in production and they are different code —
    `conversation_key` hashes the first two messages — and a run that used only
    one would leave the commoner of the two untested.
    """
    conversation = case.conversation_id or conversation_key(case.messages)
    view = vault.for_conversation(conversation)
    context = MaskContext(detector=detector, vault=view, audit=audit, cache=cache,
                          org_id="bench", agent_id="bench",
                          conversation_id=conversation)
    # Masked as ONE list, in order, because that is what a request carries: the
    # substitute a later message gets depends on what the earlier ones put in the
    # vault, and masking message by message would be a different product.
    mask_messages([dict(message) for message in case.messages], context, False)

    per_message = [detector.detect(message_text(case, index))
                   for index in range(len(case.messages))]
    mentions = {item.id: _surface(message_text(case, item.msg), item,
                                  per_message[item.msg], view)
                for item in case.pii}
    return mentions, per_message, view


def _round_trip(case: Case, mentions: dict[str, Mention], vault: Vault,
                item: PiiItem) -> tuple[str | None, str]:
    """Send the substitute to the tool the way the model would, and read it back.

    THE PRODUCTION PATH IS `unmask_arguments`, not a flat detokenise. Arguments
    are JSON and a real value is arbitrary text: «ООО "Заря"» spliced into a JSON
    string by plain replacement injects two bare quotes and the call stops
    parsing. The sidecar ships a separate endpoint for exactly this, so scoring
    through `unmask_text` would grade a leg the product does not offer for tool
    calls — and would silently pass the escaping defect that endpoint exists for.

    The WHOLE call is rebuilt, not the one parameter: an argument object carries
    an order number beside the name, and a detokeniser that walks JSON leaves has
    to be given leaves to walk. Where no expected call consumes the item — 551 of
    the corpus's 1852 `tool_param` items — a one-key object stands in, which is
    the same wire shape with one field.

    Returns (what arrived, one of `schema.BREAK_KINDS`).
    """
    call = next((one for one in case.calls if item.id in one.pii_items), None)
    if call is None:
        arguments: dict[str, object] = {item.tool_param: mentions[item.id].surface}
    else:
        arguments = dict(call.arguments)
        for consumed in call.pii_items:
            other = next(one for one in case.pii if one.id == consumed)
            if other.tool_param and consumed in mentions:
                arguments[other.tool_param] = mentions[consumed].surface
    restored = unmask_arguments(json.dumps(arguments, ensure_ascii=False), vault)
    try:
        parsed = json.loads(restored)
    except json.JSONDecodeError:
        # A detokeniser that broke its own JSON is the failure `unmask_arguments`
        # exists to prevent, and it has to be visible as itself rather than as a
        # value that went missing.
        return None, "residual"
    produced = parsed.get(item.tool_param)
    produced = produced if isinstance(produced, str) else None

    # RESIDUAL IS CHECKED BEFORE THE STRING COMPARISON. A minted token still
    # standing in the argument means a FAKE reached the customer's tool with a
    # 200 and an empty counter — the outcome `residual_tokens` was added to the
    # product for — and it can coexist with text that compares equal, so a string
    # test on its own would report it as `ok`.
    if produced is not None and residual_tokens(produced, vault):
        return produced, "residual"
    others = frozenset(other.canonical for other in case.pii
                       if other.identity != item.identity and other.type == item.type)
    return produced, classify_break(item.canonical, produced, others)


# --- accumulators -----------------------------------------------------------

@dataclass
class Tally:
    hit: int = 0
    total: int = 0

    def add(self, ok: bool) -> None:
        self.total += 1
        self.hit += 1 if ok else 0

    def rate(self) -> float:
        return self.hit / self.total * 100 if self.total else 0.0


@dataclass
class Results:
    """Every number this run produces. One object, so the report reads it rather
    than reaching into the scoring function's frame — a scorer that hands its
    locals to its printer cannot be given a second printer or a test."""

    gold: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    found: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    covered: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    recall_register: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    cover_register: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    recall_family: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    optional_touched: Tally = field(default_factory=Tally)
    negatives: Tally = field(default_factory=Tally)
    unclaimed_fires: int = 0
    claim_free_chars: int = 0

    trip: Tally = field(default_factory=Tally)
    trip_skipped: int = 0
    breaks: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    swallowed: int = 0

    consistency: Tally = field(default_factory=Tally)
    one_span: Tally = field(default_factory=Tally)
    collisions: list[tuple[str, str, str]] = field(default_factory=list)

    strict: Tally = field(default_factory=Tally)
    lenient: Tally = field(default_factory=Tally)
    comparison_kinds: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    indirect: Tally = field(default_factory=Tally)
    indirect_unprotected: int = 0
    inbound: Tally = field(default_factory=Tally)

    scope: dict[tuple[str, str], Tally] = field(default_factory=lambda: defaultdict(Tally))
    unjudged: int = 0
    broken_pairs: int = 0

    misses: list[str] = field(default_factory=list)
    partials: list[str] = field(default_factory=list)
    false_masks: list[str] = field(default_factory=list)
    trip_broken: list[str] = field(default_factory=list)
    inconsistent: list[str] = field(default_factory=list)
    comparison_wrong: list[str] = field(default_factory=list)
    scope_wrong: list[str] = field(default_factory=list)
    unclaimed: list[str] = field(default_factory=list)


IN_SCOPE = "в разговоре"
ACROSS = "через границу"
_KEEP = 500   # how many examples of each defect class are retained for the dump


def _vault_groups(cases: list[Case]) -> list[list[Case]]:
    """Cases that must share ONE tenant vault, in file order.

    `preceded_by` is the schema's way of saying «this case was scored after that
    one, against the same tenant». The `scope` family's ACROSS claim cannot be
    stated any other way: «these two must NOT be linked» is empty if the second
    conversation starts from a fresh vault, because nothing was there to link to
    and every gateway alive passes it.

    A case whose lead was filtered out of this run leads its own group. Scoring a
    follow against an empty vault would quietly turn its claim into a tautology,
    so the caller counts the pair as broken instead.
    """
    groups: list[list[Case]] = []
    where: dict[str, int] = {}
    for case in cases:
        position = where.get(case.preceded_by)
        if case.preceded_by and position is not None:
            groups[position].append(case)
            where[case.id] = position
        else:
            where[case.id] = len(groups)
            groups.append([case])
    return groups


# --- the axes ---------------------------------------------------------------

def _score_detection(case: Case, mentions: dict[str, Mention],
                     per_message: list[list[object]], out: Results) -> None:
    for item in case.pii:
        spans = per_message[item.msg]
        typed = [span for span in spans if span.entity_type == item.type
                 and span.start < item.end and span.end > item.start]
        positions: set[int] = set()
        for span in typed:
            positions.update(range(max(span.start, item.start),
                                   min(span.end, item.end)))
        whole = len(positions) == item.end - item.start
        if item.duty == "optional":
            # NEVER FOLDED INTO RECALL. `optional` is a legal category and not an
            # uncertainty: masking it is not an error and missing it is not a
            # leak, so it gets a column of its own and no share of the headline.
            out.optional_touched.add(any(span.start < item.end
                                         and span.end > item.start for span in spans))
            continue
        out.gold[item.type] += 1
        out.recall_register[case.register].add(bool(typed))
        out.recall_family[case.family].add(bool(typed))
        out.cover_register[case.register].add(whole)
        if typed:
            out.found[item.type] += 1
        elif len(out.misses) < _KEEP:
            out.misses.append(
                f"{item.type:<9} {item.value!r:36} в "
                f"{message_text(case, item.msg)[:80]!r}")
        if whole:
            out.covered[item.type] += 1
        elif typed and len(out.partials) < _KEEP:
            out.partials.append(f"{item.type:<9} {item.value!r:36} -> "
                                f"{mentions[item.id].surface!r}")


def _score_negatives(case: Case, per_message: list[list[object]],
                     out: Results) -> list[tuple[int, int, int]]:
    """Negatives, and the claim map the over-masking count needs afterwards."""
    claimed = [(item.msg, item.start, item.end) for item in case.pii]
    for negative in case.negatives:
        text = message_text(case, negative.msg)
        spans = per_message[negative.msg]
        masked = False
        start = text.find(negative.value)
        while start >= 0:
            end = start + len(negative.value)
            claimed.append((negative.msg, start, end))
            # EVERY occurrence, not the first. A negative said twice and masked
            # the second time is a false mask, and stopping at the first match is
            # how a scorer misses the half of a dialogue where a value is
            # referred back to — which is the half that is hard.
            if not masked and any(span.start < end and span.end > start
                                  for span in spans):
                masked = True
            start = text.find(negative.value, start + 1)
        out.negatives.add(not masked)
        if masked and len(out.false_masks) < _KEEP:
            out.false_masks.append(f"{negative.value!r:24} — {negative.why}")
    return claimed


def _score_overmasking(case: Case, per_message: list[list[object]],
                       claimed: list[tuple[int, int, int]], out: Results) -> None:
    """Detector fires the corpus claims nothing about. REPORTED, NEVER SCORED.

    `schema.audit_unlabelled` guarantees no PII-SHAPED string is unclaimed, so
    anything here is a name- or place-shaped guess in ordinary prose. The corpus
    does not assert that its filler contains nothing maskable, so scoring these
    would grade the gateway against a claim nobody made. The volume is the useful
    number: it is what a customer feels as noise.
    """
    for index, spans in enumerate(per_message):
        if not any(msg == index for msg, _start, _end in claimed):
            out.claim_free_chars += len(message_text(case, index))
        for span in spans:
            if any(msg == index and span.start < end and span.end > start
                   for msg, start, end in claimed):
                continue
            out.unclaimed_fires += 1
            if len(out.unclaimed) < _KEEP:
                out.unclaimed.append(f"{span.entity_type:<9} {span.value!r}")


def _score_round_trip(case: Case, mentions: dict[str, Mention], vault: Vault,
                      out: Results) -> None:
    for item in case.pii:
        if not item.tool_param or item.duty != "required":
            continue
        if not mentions[item.id].detected:
            out.trip_skipped += 1
            continue
        produced, kind = _round_trip(case, mentions, vault, item)
        out.trip.add(kind == "ok")
        out.breaks[kind] += 1
        # `inflected` IS `classify_break`'s RESIDUAL BUCKET and on this corpus it
        # holds two unrelated defects: a real value handed back in an oblique
        # case («Морозову Екатерину» into a CRM name field), and a real value
        # handed back with a neighbouring word the span swallowed («доставка
        # ленинский проспект 51»). The second is a detection defect arriving on
        # the round trip, and telling them apart is one substring test. Counted
        # and printed, NEVER given a break kind of its own: the taxonomy belongs
        # to `schema.BREAK_KINDS`, and a scorer that forks it stops being
        # comparable to the format it claims to implement.
        if kind == "inflected" and produced is not None:
            if item.canonical.casefold() in produced.casefold():
                out.swallowed += 1
        if kind != "ok" and len(out.trip_broken) < _KEEP:
            out.trip_broken.append(
                f"{item.type:<9} [{kind}] ждали {item.canonical!r:28} "
                f"получили {produced!r}")


def _score_consistency(case: Case, mentions: dict[str, Mention], out: Results) -> None:
    """One identity, one substitute — measured on what masking produced.

    v1 tokenised the corpus's own ground-truth strings here, which bypassed
    detection completely: a person cut in two by a split span received two
    substitutes for one mention and the axis reported 100%. Reading the surfaces
    back means a split shows up as itself, and `one_span` prints how often it
    happened at all.
    """
    surfaces: dict[str, list[str]] = defaultdict(list)
    types: dict[str, str] = {}
    for item in case.pii:
        if not item.identity or item.duty != "required":
            continue
        mention = mentions[item.id]
        if not mention.detected:
            continue
        out.one_span.add(mention.spans == 1)
        surfaces[item.identity].append(mention.surface)
        types[item.identity] = item.type
    for identity, produced in surfaces.items():
        ordered = sorted(set(produced), key=lambda value: -len(value))
        one = all(_reads_as_one(ordered[0], other, types[identity])
                  for other in ordered[1:])
        out.consistency.add(one)
        if not one and len(out.inconsistent) < _KEEP:
            out.inconsistent.append(f"{identity:<14} -> {ordered}")
    minted = sorted((identity, sorted(values)[0]) for identity, values
                    in surfaces.items())
    for left in range(len(minted)):
        for right in range(left + 1, len(minted)):
            if minted[left][1] == minted[right][1]:
                out.collisions.append((case.id, minted[left][0], minted[right][0]))


def _score_inbound(case: Case, mentions: dict[str, Mention], vault: Vault,
                   out: Results) -> None:
    """Axes 5 and 6, which share a precondition and split on one question.

    AXIS 6 asks whether data arriving FROM a tool was masked before the model saw
    it. AXIS 5 asks the harder half: for the subset the customer never wrote down
    anywhere, did the REAL value nonetheless reach the next tool call. That is the
    only path in the product where a value is minted inbound and consumed
    outbound without a human ever typing it, and it shares no code with the
    user-to-model-to-tool one but a vault.

    Protection is a PRECONDITION of axis 5, not a component of it: a gateway that
    failed to mask the CRM record would hand the model the real value and «pass»
    the round trip by doing nothing. Those are counted apart, as `не защищено`.
    """
    said_by_user = " ".join(
        message_text(case, index) for index, message in enumerate(case.messages)
        if message.get("role") == "user")
    for item in case.pii:
        if item.duty != "required" or case.messages[item.msg].get("role") != "tool":
            continue
        out.inbound.add(mentions[item.id].protected)
        if not item.tool_param or item.value in said_by_user:
            continue
        if not mentions[item.id].protected:
            out.indirect_unprotected += 1
            continue
        _produced, kind = _round_trip(case, mentions, vault, item)
        out.indirect.add(kind == "ok")


def _score_links(case: Case, scored: dict[str, dict[str, Mention]],
                 conversations: dict[str, str], out: Results) -> None:
    """Axis 7. Every judged link in the corpus, in four cells.

    THE BOUNDARY IS THE CONVERSATION, NOT THE CASE, and getting that wrong is
    easy: the `scope` family states BOTH of its claims across a `preceded_by`
    pair, so a cell keyed on «is this link cross-case» puts the WITHIN arm — the
    one that must link — in the ACROSS column and reports the engine failing a
    demand nobody made of it. The two arms differ only in whether the follow
    carries the lead's `conversation_id`, which is precisely the field the vault
    scopes on, and a derived id (`conversation_key`) counts the same way.

    `same` and `different` are both claims and both can be violated. The ACROSS
    cells are the ones v1 could not express at all: the SAME partial mention, a
    different conversation, and linking it hands one customer's address to
    another customer's dialogue. `unjudged` is counted and never scored — in
    `split_name_bare` the dialogue named no full form, so demanding a link would
    grade the gateway on information the conversation never carried.

    The `compare` family's links are counted here AND answered on axis 4. The two
    are not independent and are not meant to be: axis 7 asks what the gateway
    did, axis 4 asks what the model would then conclude, and a gateway can fail
    the second while passing the first — a pair linked into one vault row can
    still read as two places to a model that only ever sees the text.
    """
    mentions = scored[case.id]
    for link in case.links:
        if link.kind == "unjudged":
            out.unjudged += 1
            continue
        left = mentions.get(link.left)
        right = (scored.get(link.case, {}).get(link.right) if link.case
                 else mentions.get(link.right))
        if left is None or right is None:
            out.broken_pairs += 1
            continue
        other = conversations.get(link.case or case.id, "")
        where = IN_SCOPE if other == conversations[case.id] else ACROSS
        one = _reads_as_one(left.surface, right.surface, left.item.type)
        ok = one if link.kind == "same" else not one
        out.scope[(where, link.kind)].add(ok)
        if not ok and len(out.scope_wrong) < _KEEP:
            out.scope_wrong.append(
                f"{where} / {link.kind}: {left.item.value!r} -> {left.surface!r}"
                f"  |  {right.item.value!r} -> {right.surface!r}")


def _score_comparison(case: Case, mentions: dict[str, Mention], out: Results) -> None:
    """Axis 4. What a perfect model would answer, given only the masked text.

    THE QUESTION IS CLOSED — «это тот же адрес?» has two answers — so the scorer
    derives one from the surfaces instead of testing whether a reply contains a
    reference string. WebArena's `must_include` accepts a reply carrying the
    reference plus anything else, and ABC measured that leniency at 1.4-5.2%
    inflation; a substring test is the leniency this benchmark refuses.

    THREE OUTCOMES, AND THE THIRD IS WHY THERE ARE TWO NUMBERS.

      correct       both mentions protected, and the surfaces entail
                    `expected_answer`.
      wrong         both protected, and the surfaces entail the OTHER answer.
                    The gateway did not merely fail to help — it manufactured a
                    confident wrong answer out of its own substitutes.
      unanswerable  at least one judged mention reached the model in the clear.
                    The model is holding a real value against a substitute, so
                    whatever it says is an accident of which side leaked. A
                    careful model asks instead, and THAT is the refusal the
                    lenient number forgives.

    Strict = correct. Lenient = correct + unanswerable. The leak itself is not
    forgiven anywhere — axis 1 counts it, and counting it here as well would make
    one defect move two numbers.

    A LEAKED PAIR MAY NOT COUNT AS CORRECT, however right the answer looks. Two
    unmasked values compare perfectly, so a gateway that masks nothing would score
    100% on this axis — tau-bench's exact trap, where an agent that does nothing
    passes 38% of the airline subset because the ground truth demands nothing.
    """
    judged = [link for link in case.links if link.kind != "unjudged"]
    if len(judged) != 1:
        # The family's contract is one question per case. More than one judged
        # pair means the corpus and the scorer disagree about what is being
        # asked, which is a corpus defect and must not be averaged away.
        out.broken_pairs += 1
        return
    left, right = mentions[judged[0].left], mentions[judged[0].right]
    if not left.protected or not right.protected:
        out.comparison_kinds["не на чем отвечать (значение утекло)"] += 1
        out.strict.add(False)
        out.lenient.add(True)
        return
    answer = "да" if _reads_as_one(left.surface, right.surface,
                                   left.item.type) else "нет"
    ok = answer == case.expected_answer
    out.strict.add(ok)
    out.lenient.add(ok)
    out.comparison_kinds["верно" if ok else f"неверно, ответил бы «{answer}»"] += 1
    if not ok and len(out.comparison_wrong) < _KEEP:
        out.comparison_wrong.append(
            f"ждали «{case.expected_answer}»  {left.item.value!r} -> "
            f"{left.surface!r}  |  {right.item.value!r} -> {right.surface!r}")


def score(cases: list[Case], detector: _MemoDetector) -> Results:
    out = Results()
    present = {case.id for case in cases}
    scored: dict[str, dict[str, Mention]] = {}
    conversations: dict[str, str] = {}
    order: list[Case] = []

    for group in _vault_groups(cases):
        vault = Vault(":memory:", "bench")
        audit = AuditLog(":memory:")
        cache = MaskCache(512)
        for case in group:
            if case.preceded_by and case.preceded_by not in present:
                out.broken_pairs += 1
            mentions, per_message, view = _mask_case(case, detector, vault,
                                                     audit, cache)
            scored[case.id] = mentions
            conversations[case.id] = (case.conversation_id
                                      or conversation_key(case.messages))
            order.append(case)
            _score_detection(case, mentions, per_message, out)
            claimed = _score_negatives(case, per_message, out)
            _score_overmasking(case, per_message, claimed, out)
            # `view` for masking, the BASE vault for detokenising: production
            # unmasks through `_vault(org_id)` with no conversation on it, and a
            # scorer that scoped the read leg would be grading an endpoint the
            # sidecar does not expose.
            _score_round_trip(case, mentions, vault, out)
            _score_consistency(case, mentions, out)
            _score_inbound(case, mentions, vault, out)

    # Links and comparisons run AFTER every case is masked: a cross-case link
    # names the other half by id, and the other half must already have a surface.
    for case in order:
        _score_links(case, scored, conversations, out)
        if case.family == "compare" and case.expected_answer:
            _score_comparison(case, scored[case.id], out)
    return out


# --- the report -------------------------------------------------------------

def _headline(out: Results) -> dict[str, float]:
    total_gold = sum(out.gold.values()) or 1
    return {
        "полнота": sum(out.found.values()) / total_gold * 100,
        "покрытие": sum(out.covered.values()) / total_gold * 100,
        "негативы": out.negatives.rate(),
        "круг": out.trip.rate(),
        "согласованность": out.consistency.rate(),
        "сравнение (строго)": out.strict.rate(),
        "косвенное": out.indirect.rate(),
        "ПД из инструмента": out.inbound.rate(),
        "область: связать в разговоре": out.scope[(IN_SCOPE, "same")].rate(),
        "область: не связывать через границу": out.scope[(ACROSS, "different")].rate(),
    }


def _denominator(out: Results, axis: str) -> int:
    """How many observations an axis had. Zero means «not measured», which is
    neither a pass nor a failure — a filtered run holding no `compare` case must
    not report its floor as met, and must not go red either."""
    total_gold = sum(out.gold.values())
    return {
        "полнота": total_gold, "покрытие": total_gold,
        "негативы": out.negatives.total, "круг": out.trip.total,
        "согласованность": out.consistency.total,
        "сравнение (строго)": out.strict.total,
        "косвенное": out.indirect.total,
        "ПД из инструмента": out.inbound.total,
        "область: связать в разговоре": out.scope[(IN_SCOPE, "same")].total,
        "область: не связывать через границу": out.scope[(ACROSS, "different")].total,
    }[axis]


def report(out: Results, cases: list[Case], args: argparse.Namespace,
           whole_corpus: bool) -> int:
    """Print every axis, then a verdict. Nothing merged, nothing hidden.

    TWO TOTALS FOR EVERY REGISTER-SENSITIVE NUMBER, ALWAYS. The corpus is built
    with UNIFORM register cells so a per-register rate is estimable with equal
    precision; support traffic is not one fifth `clean`. The unweighted number is
    a statement about this corpus, the weighted one is a statement about traffic,
    and one number claiming to be both is exactly what `REGISTER_WEIGHTS` and this
    rule exist to prevent.
    """
    total_gold = sum(out.gold.values())
    print(f"AgentPII-RU v2 · случаев {len(cases)}"
          + (f" · срез {args.tier}" if args.tier else "")
          + (f" · регистр {args.register}" if args.register else "")
          + (f" · семейство {args.family}" if args.family else ""))
    if args.tier in TIER_ZERO_FAILURE_BOUND:
        print(f"  СРЕЗ «{args.tier}» — средство разработки, не основание для "
              f"релиза: даже при НУЛЕ ошибок верхняя граница 95% на долю "
              f"ошибок остаётся {TIER_ZERO_FAILURE_BOUND[args.tier] * 100:.1f}%.")
    print()

    print("--- 1. ДЕТЕКЦИЯ ---")
    print(f"{'ТИП':<10}{'ЭТАЛОН':>8}{'НАЙДЕНО':>9}{'ПОЛНОТА':>9}"
          f"{'ЦЕЛИКОМ':>9}{'ПОКРЫТИЕ':>10}")
    print("-" * 55)
    for kind in sorted(out.gold):
        if out.gold[kind] < SUPPRESS_BELOW:
            print(f"{kind:<10}{out.gold[kind]:>8}{out.found[kind]:>9}{'(мало)':>9}"
                  f"{out.covered[kind]:>9}{'(мало)':>10}")
            continue
        print(f"{kind:<10}{out.gold[kind]:>8}{out.found[kind]:>9}"
              f"{out.found[kind] / out.gold[kind] * 100:>8.1f}%"
              f"{out.covered[kind]:>9}"
              f"{out.covered[kind] / out.gold[kind] * 100:>9.1f}%")
    print("-" * 55)
    print(f"{'ВСЕГО':<10}{total_gold:>8}{sum(out.found.values()):>9}"
          f"{sum(out.found.values()) / total_gold * 100:>8.1f}%"
          f"{sum(out.covered.values()):>9}"
          f"{sum(out.covered.values()) / total_gold * 100:>9.1f}%")
    print("   ПОКРЫТИЕ — спан найден ЦЕЛИКОМ. Разница с полнотой — это хвосты, "
          "ушедшие к модели открытыми,")
    print("   а не округление: пересечения хватает детектору, клиенту нужно "
          "покрытие.")

    print(f"\n{'РЕГИСТР':<12}{'ЭТАЛОН':>8}{'ПОЛНОТА':>9}{'ПОКРЫТИЕ':>10}")
    print("-" * 39)
    for register in REGISTERS:
        recall, cover = out.recall_register[register], out.cover_register[register]
        if recall.total:
            print(f"{register:<12}{recall.total:>8}{recall.rate():>8.1f}%"
                  f"{cover.rate():>9.1f}%")
    weighted_recall = register_weighted(
        {name: (t.hit, t.total) for name, t in out.recall_register.items()}) * 100
    weighted_cover = register_weighted(
        {name: (t.hit, t.total) for name, t in out.cover_register.items()}) * 100
    print(f"{'по трафику':<12}{'':>8}{weighted_recall:>8.1f}%{weighted_cover:>9.1f}%"
          "   веса REGISTER_WEIGHTS, они ПРЕДВАРИТЕЛЬНЫЕ")

    print(f"\n{'СЕМЕЙСТВО':<12}{'ЭТАЛОН':>8}{'ПОЛНОТА':>9}")
    print("-" * 29)
    for family in sorted(out.recall_family):
        tally = out.recall_family[family]
        print(f"{family:<12}{tally.total:>8}{tally.rate():>8.1f}%")

    print(f"\nНЕГАТИВЫ (не ПД, маскировать нельзя): {out.negatives.hit}/"
          f"{out.negatives.total} = {out.negatives.rate():.2f}% чистых")
    print(f"OPTIONAL (маскировать можно, пропустить — не утечка): затронуто "
          f"{out.optional_touched.hit}/{out.optional_touched.total}, "
          f"в полноту НЕ входит")
    print(f"СРАБАТЫВАНИЯ ВНЕ РАЗМЕТКИ: {out.unclaimed_fires} шт.; "
          f"{out.claim_free_chars} символов сообщений без единой заявки — "
          f"это объём перемаскировки, он не штрафуется")

    print("\n--- 2. КРУГ (настоящее значение дошло до инструмента) ---")
    print(f"{out.trip.hit}/{out.trip.total} = {out.trip.rate():.1f}%   "
          f"пропущено как ненайденное детекцией: {out.trip_skipped}")
    if out.breaks:
        print("   " + ", ".join(f"{name} {count}" for name, count in
                                sorted(out.breaks.items(), key=lambda p: -p[1])))
    if out.swallowed:
        print(f"   из `inflected` — {out.swallowed} это НЕ склонение: эталон "
              f"пришёл целиком, но со словом,")
        print(f"   которое спан захватил рядом («доставка ленинский проспект 51»). "
              f"Дефект детекции, приехавший на круг.")
    print("   `model_absent` здесь не встречается по построению: модели нет, "
          "вызов строит эталон.")

    print("\n--- 3. СОГЛАСОВАННОСТЬ ---")
    print(f"один человек — одна подмена:  {out.consistency.hit}/"
          f"{out.consistency.total} = {out.consistency.rate():.1f}%")
    print(f"одно упоминание — один спан:  {out.one_span.hit}/{out.one_span.total} "
          f"= {out.one_span.rate():.1f}%   расколотый спан — это две подмены на "
          f"одно упоминание,")
    print(f"                              и v1 его не видел, потому что чеканил "
          f"токены из строк корпуса")
    print(f"разные люди с одной подменой: {len(out.collisions)}")

    print("\n--- 4. СРАВНЕНИЕ (контракт спрашивает про РАВЕНСТВО) ---")
    print(f"строго (проходит только верный ответ): {out.strict.hit}/"
          f"{out.strict.total} = {out.strict.rate():.1f}%   ← заголовок")
    print(f"мягко  (отказ отвечать тоже проходит): {out.lenient.hit}/"
          f"{out.lenient.total} = {out.lenient.rate():.1f}%")
    for name, count in sorted(out.comparison_kinds.items(), key=lambda p: -p[1]):
        print(f"   {name}: {count}")

    print("\n--- 5. КОСВЕННАЯ ССЫЛКА (клиент значения не называл) ---")
    print(f"настоящее значение дошло до инструмента: {out.indirect.hit}/"
          f"{out.indirect.total} = {out.indirect.rate():.1f}%")
    print(f"не защищено на входе, поэтому в счёт не идёт: "
          f"{out.indirect_unprotected}")
    print("   Это НАЗВАННОЕ ПОДМНОЖЕСТВО оси 2, а не отдельный счёт: те же "
          "значения входят и туда.")
    print("   Отдельная строка нужна потому, что путь инструмент -> модель -> "
          "инструмент не делит с")
    print("   пользовательским ни строчки кода, кроме волта, и общая цифра "
          "круга его прячет.")

    print("\n--- 6. ПД ИЗ ИНСТРУМЕНТА (замаскировано ДО того, как увидела модель) ---")
    print(f"{out.inbound.hit}/{out.inbound.total} = {out.inbound.rate():.1f}%   "
          f"значение не пережило маскирование ответа инструмента")

    print("\n--- 7. ОБЛАСТЬ РАЗГОВОРА ---")
    print(f"{'ГДЕ':<16}{'ТРЕБОВАНИЕ':<16}{'ПАР':>6}{'ВЕРНО':>9}")
    print("-" * 48)
    for where in (IN_SCOPE, ACROSS):
        for kind in ("same", "different"):
            tally = out.scope[(where, kind)]
            demand = "связать" if kind == "same" else "не связывать"
            print(f"{where:<16}{demand:<16}{tally.total:>6}{tally.rate():>8.1f}%")
    print(f"не судится (unjudged): {out.unjudged};  "
          f"пар без второй половины: {out.broken_pairs}")
    print("   «через границу / связать» — контрольное плечо: канонизация телефона "
          "общая для тенанта,")
    print("   поэтому шлюз, переставший связывать вообще, проходит остальные "
          "требования across и валит это.")

    for title, rows in (
            ("ПРОПУЩЕНО", out.misses),
            ("НАЙДЕНО ЧАСТИЧНО, ОСТАЛЬНОЕ УТЕКЛО", out.partials),
            ("ЗАМАСКИРОВАНО ЗРЯ", out.false_masks),
            ("КРУГ РАЗОРВАН", out.trip_broken),
            ("ОДИН ЧЕЛОВЕК, РАЗНЫЕ ПОДМЕНЫ", out.inconsistent),
            ("СРАВНЕНИЕ ОТВЕЧЕНО НЕВЕРНО", out.comparison_wrong),
            ("ОБЛАСТЬ НАРУШЕНА", out.scope_wrong),
            ("СРАБОТАЛО ВНЕ РАЗМЕТКИ", out.unclaimed),
    ):
        if not rows:
            continue
        print(f"\n--- {title} ({len(rows)}{'+' if len(rows) >= _KEEP else ''}) ---")
        for row in rows[:args.dump]:
            print(f"  {row}")

    measured = _headline(out)
    print("\n--- ВЕРДИКТ ---")
    print(f"{'ОСЬ':<38}{'N':>7}{'ИЗМЕРЕНО':>10}{'ПОРОГ':>8}")
    print("-" * 70)
    failed: list[str] = []
    for name, floor in FLOORS.items():
        # N IS PART OF THE VERDICT, not decoration. Two of these axes rest on
        # fewer than twenty observations, where one flipped case is five to ten
        # points; a table of bare percentages invites reading that as a trend.
        size = _denominator(out, name)
        if not size:
            print(f"{name:<38}{0:>7}{'—':>10}{floor:>7.1f}%  не мерилось")
            continue
        mark = "ok" if measured[name] >= floor else "НИЖЕ ПОРОГА"
        if mark != "ok":
            failed.append(name)
        draw = "~" if name in DRAW_DEPENDENT else " "
        print(f"{name:<38}{size:>7}{measured[name]:>9.1f}%{floor:>7.1f}% {draw}{mark}")
    print("~ — ось зависит от того, КАКАЯ подмена выпала: `secrets` не "
          "сеются, и это свойство продукта, а не шум")
    print("    измерения. По пяти полным прогонам: круг ±0,2, согласованность "
          "±0,2, сравнение ±1,0,")
    print("    «не связывать через границу» 70-90 — там десять пар, и одна пара "
          "стоит десять пунктов.")
    # A PARTIAL RUN PRINTS THE COMPARISON AND DOES NOT GATE ON IT. The floors
    # describe the whole corpus; `сравнение` over the ten compare cases in the
    # `small` tier is one flipped case per ten points, and a red build there
    # would be the exact failure `TIER_SIZES` warns about — somebody gating a
    # release on 19/20. So the marks stay (they are what makes the slice useful
    # while iterating) and the exit code does not.
    if not whole_corpus:
        print("\nПрогон отфильтрован: пороги описывают ПОЛНЫЙ корпус, здесь они "
              "справочные и НЕ решают код возврата.")
        if failed:
            print(f"ниже полнокорпусного порога: {', '.join(failed)}")
        return 0
    if failed:
        print(f"\nВЕРДИКТ: ниже порога {len(failed)} — {', '.join(failed)}")
        return 1
    print("\nВЕРДИКТ: все измеренные оси на пороге или выше")
    return 0


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?", default=str(here / "corpus.json"))
    parser.add_argument("--ladder", default=str(here / "ladder.json"))
    parser.add_argument("--tier", default="",
                        help="nano|small|medium|large|max — a FROZEN prefix, never a sample")
    parser.add_argument("--register", default="", help="score only this register")
    parser.add_argument("--family", default="", help="score only this family")
    parser.add_argument("--limit", type=int, default=0,
                        help="first N cases; for iteration, never for a number")
    parser.add_argument("--dump", type=int, default=10,
                        help="how many examples of each defect class to print")
    args = parser.parse_args()

    try:
        everything = build.hydrated(build.load(Path(args.corpus)))
        cases = everything
    except (OSError, ValueError, KeyError, TypeError) as error:
        # REFUSE, do not score. A corpus whose licensed text no longer hashes to
        # what the offsets were written against keeps producing numbers, and the
        # numbers still look like numbers.
        print(f"корпус не читается: {error}", file=sys.stderr)
        return 2

    if args.tier:
        payload = json.loads(Path(args.ladder).read_text(encoding="utf-8"))
        ladder = Ladder(version=int(payload["version"]), seed=int(payload["seed"]),
                        corpus_sha256=str(payload["corpus_sha256"]),
                        order=[str(name) for name in payload["order"]])
        try:
            cases = tier(cases, ladder, args.tier)
        except ValueError as error:
            print(f"лестница отказала: {error}", file=sys.stderr)
            return 2
    if args.register:
        cases = [case for case in cases if case.register == args.register]
    if args.family:
        cases = [case for case in cases if case.family == args.family]
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        print("после фильтров не осталось ни одного случая", file=sys.stderr)
        return 2

    load_dev_bundle()
    # Whether the floors apply is decided by WHAT WAS SCORED, not by which flags
    # were typed: `--tier max` is the whole corpus and must gate, while a
    # `--register` slice of the same size would not be.
    whole = len(cases) == len(everything)
    return report(score(cases, _MemoDetector(Detector())), cases, args, whole)


if __name__ == "__main__":
    raise SystemExit(main())
