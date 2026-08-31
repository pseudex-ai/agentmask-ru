"""AgentPII-RU v2 — the case format. This file IS the specification.

The benchmark is publishable only if a third party can regenerate the corpus and
re-score a COMPETING gateway without reading our engine. Nothing here imports
from `pseudex/`; every rule a scorer needs — how a value is compared, how a
broken round trip is named, what a case must contain before it is allowed to
count — is stated here rather than left to the scorer that happens to run first.

WHAT V1 COULD NOT EXPRESS, measured on its own corpus (1056 cases):

  * max 3 messages, max 2 user turns, max **159 characters**. No long context
    anywhere, so nothing tested whether a substitute still resolves after thirty
    intervening messages — which is the shape of every real support dialogue.
  * `conversation_id=""` in the scorer, so the engine's conversation-scoped
    linking path — the thing that makes a partial mention resolvable at all —
    was never exercised, in either direction.
  * **no tool results.** The multi-turn story was user-text-only, so the third
    leg of the contract (PII arriving FROM the customer's CRM and being masked
    on its way TO the model) had no case at all.
  * the consistency axis tokenised the corpus's own ground-truth strings, so a
    one-person-two-tokens caused by a SPLIT SPAN was invisible to it.
  * a latent crash: `_same_value(None, ...)` raised, which made the "token not
    found" branch unreachable — the branch that names the worst outcome.

FOUR THINGS ARE NEW IN THE FORMAT, and each exists because a defect class had
nowhere to live:

  1. `PiiItem.msg` indexes ALL messages, not the user turns. A tool result is a
     message and it carries personal data.
  2. `PiiItem.duty` separates data that MUST be masked from data that MAY be.
     TAB (Pilan et al., Computational Linguistics 48(4), 2022) separates DIRECT
     from QUASI identifiers and scores them apart; nobody has applied that split
     WITHIN a type, and the address is the one type where the boundary between
     identifying and not is a house number away.
  3. `LinkExpectation` states, per pair of mentions, whether the gateway MUST
     give them one substitute, MUST NOT, or is not being judged. v1 expressed
     only the first, by omission — «no identity» and «an identity we deliberately
     do not demand» looked identical in the JSON.
  4. `relation` names what the tool contract asks the model to compute over
     protected values. `equality` is solvable and the product solves it; every
     other relation is structurally incompatible with reversible
     pseudonymisation, and the corpus exists to give that a number, not a fix.

INDEPENDENCE RULE, inherited from v1 and from `make_stress.py`: cases are
authored from the DOMAIN — what a Russian support conversation contains — never
from a list of what our detector currently finds. `audit_unlabelled()` below
enforces the mechanical half of that: it scans for PII SHAPES with plain regex,
knowing nothing about our recognizers, and refuses a case whose text contains a
shape that neither the gold nor the negatives claim.
"""

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

# The OpenAI function-calling schema is the PROVIDER's contract, not ours. It is
# typed loosely on purpose: narrowing it would make the corpus un-replayable
# against a provider that adds a field, and the corpus's whole claim is that it
# can be run against anyone's model with no translation layer.
ToolSchema = dict[str, Any]


# --- registers ------------------------------------------------------------
#
# How the SAME datum is written by different channels. FIVE, not v1's four, and
# the extra one is a split rather than an addition.
#
# v1 had one `voice` register built on the sentence «modern ASR normalises
# digits». That was belief, not measurement, and it was wrong in the direction
# that hides leaks: seven verbatim addresses from real calls were not detected
# at all. Measured here on OpenSTT `asr_calls_2_val` — 12 950 human transcripts
# of real Russian phone calls — **zero utterances contain a digit** and 9.1%
# carry a number written out in words. (Golos, read speech rather than
# spontaneous, reports 21%; the phone-call figure is the one this product meets,
# so 9.1% is the design number and 21% is noted as the read-speech ceiling.)
#
# But commercial ASR ships inverse text normalisation and does emit «+7 916…».
# Both shapes are real and they FAIL DIFFERENTLY: a phone with digits is caught
# by libphonenumber's checksum, a phone spelled out in words is caught by
# nothing we have. One number averaged over the two describes neither — the same
# mistake `bench/voice` already documented when 71% turned out to be 94% on one
# legal class and 47% on the other. So the register splits and the two halves
# are reported apart, for ever.
REGISTERS: tuple[str, ...] = (
    "clean",      # a web form or a copy-paste from a document
    "chat",       # a messenger: lower case, no patronymic, no separators
    "sloppy",     # writing errors, drawn from RuSpellGold's measured distribution
    "voice_itn",  # ASR with inverse text normalisation on — v1's `voice`, demoted
    "voice_raw",  # ASR verbatim: numbers in words, no digits, no punctuation
)

# WHY THE CELLS ARE EQUAL AND THE HEADLINE IS NOT.
#
# Support traffic is not one fifth `clean`. But equal cells are what make a
# PER-REGISTER rate estimable with equal precision, and a mixture that changes
# between corpus versions makes two headline numbers incomparable for reasons
# that have nothing to do with the gateway. MMLU-Redux solves exactly this by
# sampling UNIFORMLY per subject and then reporting the aggregate as an
# explicitly re-weighted estimate; the same move is taken here.
#
# So: build uniform, and publish TWO totals — the unweighted one (which is a
# statement about this corpus) and the traffic-weighted one (which is a
# statement about traffic). Never one number claiming to be both.
#
# THESE WEIGHTS ARE PROVISIONAL AND SAY SO. Nothing has measured the register
# mix of live traffic. What would settle it: classify the 993 real production
# dialogues already in `bench/agentrun/` by register and publish the counts. A
# deployment with its own mix should override them; the rule that both numbers
# are printed does not move.
REGISTER_WEIGHTS: dict[str, float] = {
    "clean": 0.05,
    "chat": 0.55,
    "sloppy": 0.20,
    "voice_itn": 0.10,
    "voice_raw": 0.10,
}

# --- difficulty -----------------------------------------------------------
#
# Crossed ONLY inside the `transfer` family. Elsewhere the family IS the
# difficulty, and crossing it everywhere would exhaust a cross-product instead
# of covering the sources of variation — the failure Perlitz et al. name
# directly ("maximize the coverage of each source, rather than exhausting all
# cross-product combinations of a few").
DIFFICULTIES: tuple[str, ...] = (
    "easy",         # one entity, unambiguous, cued
    "hard",         # several entities, non-PII numbers adjacent, inflected forms
    "adversarial",  # built to produce a false positive or to hide a true one
)

# --- families -------------------------------------------------------------
#
# A family is a QUESTION, not a topic. Two families are justified only when a
# defect can pass one and fail the other. The rejected ones — and why — are in
# `docs/tz-agentpii2.md`; the rule that produced the cut is that a family which
# duplicates another's coverage is cost without signal.
FAMILIES: tuple[str, ...] = (
    "transfer",   # v1's scenarios: PII stated by the user, consumed by one call
    "length",     # the datum is named early and referenced late
    "compare",    # the tool contract asks whether two protected values are EQUAL
    "indirect",   # the customer never states the datum; it comes back from a tool
    "result",     # the datum ARRIVES in a tool result and must be masked inbound
    "rank",       # the contract asks for a relation OTHER than equality
    "scope",      # the conversation boundary, in both directions
    "speech",     # real call transcripts, hand-annotated
    "dispatch",   # real taxi-dispatch speech, hand-labelled, two strata
)

# --- duty -----------------------------------------------------------------
#
# TAB's DIRECT / QUASI split, applied WITHIN a type — which the literature has
# not done. «улица Пушкина» identifies nobody: hundreds of buildings stand on
# it, exactly one step more specific than the city we already decided does not
# identify anyone (152-ФЗ ст. 3 п. 1). «улица Пушкина, 14» identifies a
# building. Scored as one number those two averaged 71% while the real figures
# were 94% and 47%.
#
# `optional` is NOT «we are unsure». It is a legal category: masking it is not
# an error and missing it is not a leak, so it is counted in its own column and
# never folded into recall. A datum that is only uncertain belongs in neither
# class and must not be in the corpus at all — the `speech` set drops eleven
# such utterances for that reason.
#
# WARNING, from TAB's own numbers: the direct/quasi decision was the LEAST
# reliable annotation they had (Fleiss kappa 0.46 against 0.67 for entity type).
# Any case whose `duty` is not mechanically derivable must be double-annotated
# with a third-annotator tiebreak, and `Case.annotators` records whether it was.
DUTIES: tuple[str, ...] = ("required", "optional")

# --- link expectations ----------------------------------------------------
#
# `same` and `different` are both claims and both can be violated. `unjudged`
# is the third state and it is the one v1 could not write down: in
# `split_name_bare` the conversation named no full form, so demanding a link
# would score the gateway on information the dialogue never carried — while
# silently accepting either answer would let a real merge hide there.
LINKS: tuple[str, ...] = ("same", "different", "unjudged")

# --- relations ------------------------------------------------------------
#
# WHAT THE TOOL CONTRACT ASKS THE MODEL TO COMPUTE OVER PROTECTED VALUES. This
# is one axis, not two families' worth of coincidence:
#
#   equality    solvable, and the product solves it (`_linked_place`,
#               `_linked_token`): «вы на Ленина 14?» against a fuller mention
#               earlier in the same conversation.
#   similarity  «какой из этих адресов ближе к курьеру» — a substitute is drawn
#               independently, so the distances the model sees are noise.
#   ordering    «кто из клиентов старше» over dates of birth.
#   prefix      «который из ИНН московский» — the region code is the first two
#               digits and the substitute does not preserve it.
#   frequency   «какой телефон встречается в большинстве заказов» — derived from
#               EQUALITY alone, so a correct gateway preserves it. This is the
#               family's control arm: if `rank` scores zero across the board the
#               instrument is broken, and `frequency` is what says so.
#
# A tool is incompatible with reversible pseudonymisation when its contract
# requires a relation other than equality. Everything but `equality` and
# `frequency` is therefore declared incompatible BY THE CORPUS, and the family
# exists to give that a number — not to be fixed.
RELATIONS: tuple[str, ...] = (
    "equality", "frequency", "similarity", "ordering", "prefix",
)
COMPATIBLE_RELATIONS: frozenset[str] = frozenset({"equality", "frequency"})

# --- context length -------------------------------------------------------
#
# Rungs, with the band each must land in, measured over the WHOLE case in
# characters. v1's entire corpus fits in `short` and its longest case was 159
# characters.
#
# `long` is ~16 000 characters ≈ 4-5k tokens, chosen because that is where a
# real support transcript sits after a working session AND where the repo's own
# `bench_masking.py` shows the O(n^2) re-masking cost becoming visible. It is
# also the only rung where the mask cache and `content_key`'s conversation
# component are load-bearing rather than decorative.
LENGTH_RUNGS: dict[str, tuple[int, int]] = {
    "short": (0, 400),
    "medium": (1_200, 4_000),
    "long": (12_000, 24_000),
}

# --- break taxonomy -------------------------------------------------------
#
# AgentBench publishes five FINISH REASONS and is the only agent benchmark in
# the field that separates «the agent's format was wrong» from «the agent chose
# wrongly». PAAC publishes a seven-way alignment error taxonomy for
# Desanitize(Sanitize(q)) != q. Neither is about a VALUE's integrity inside a
# tool argument, which is what this taxonomy names.
#
# The reason to keep them apart rather than report one rate: v1 reported one
# number and a footnote (`broken_kinds`), and a reader could not tell a
# normalisation repair from a declined name written into a customer's CRM. Those
# have the same SHAPE and opposite meanings.
#
# `model_absent` is the AgentBench move: a model that never made the call is a
# model failure, and it must never move the gateway's number in either
# direction.
BREAK_KINDS: tuple[str, ...] = (
    "ok",                  # the real value arrived
    "not_resolved",        # no vault row: the substitute resolved to nothing
    "residual",            # a minted token still stands in the argument
    "other_person",        # resolved to a REAL value belonging to someone else
    "inflected",           # resolved, but declined or otherwise re-formed
    "truncated",           # a prefix came back; the tail leaked or was lost
    "space_repaired",      # differs only in whitespace
    "lookalike_repaired",  # differs only by a Latin/Cyrillic twin
    "model_absent",        # the model never made the call — not the gateway
)

# --- tiers ----------------------------------------------------------------
#
# NESTED PREFIXES OF ONE FROZEN ORDERING, never a runtime sampler. Every named
# subset in the field is a frozen id list — SWE-bench Lite is 300 named
# instances, Verified is 500, BIG-bench Lite is 24 named tasks. Measured on v1's
# corpus, re-running a balanced sampler after growing the corpus by 10% kept
# only 3-4 of 10 nano cases: the better a sampler balances, the more violently
# it re-draws, because balance is a global property. Freezing is what makes last
# month's number comparable to this month's.
#
# The sizes are multiples of 8 families and 5 registers so a floor of one case
# per family is reachable at every rung. What each rung can DECIDE is in the
# design doc; the short version is that nano and small decide nothing and must
# be labelled as development conveniences in the output, or somebody will gate a
# release on 19/20.
TIER_SIZES: dict[str, int] = {
    "nano": 20,
    "small": 80,
    "medium": 240,
    "large": 560,
    "max": 0,   # 0 means "every case in the corpus"
}

# Exact one-sided 95% Clopper-Pearson upper bound on the true failure rate given
# ZERO observed failures, 1 - 0.05**(1/n). Printed instead of a confidence
# interval at the small rungs, because ruling things out is the only thing a
# small n can do — and because the Wald interval at a perfect score has width
# zero, which is maximally wrong exactly where these suites land.
TIER_ZERO_FAILURE_BOUND: dict[str, float] = {
    "nano": 0.139, "small": 0.037, "medium": 0.012, "large": 0.0053,
}


# --- shapes the audit knows about -----------------------------------------
#
# DELIBERATELY NOT OUR RECOGNIZERS. This is a mechanical shape scan whose only
# job is to catch a case whose text contains something PII-shaped that the
# ground truth forgot to claim — filler prose in a `long` case is where that
# happens, and an unclaimed value there is scored as a false mask against a
# gateway that was right.
#
# Capitalised bigrams (a name shape) are NOT scanned: sentence starts make that
# rule fire on ordinary prose, and a noisy gate gets disabled. The three shapes
# below are unambiguous, and between them they cover every filler defect the v1
# templates actually produced.
_SHAPE_DIGITS = re.compile(r"\d{6,}")
_SHAPE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SHAPE_PHONE = re.compile(r"(?:\+7|\b8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
_ANY_DIGITS = re.compile(r"\d{2,}")

# The seven Latin letters with a Cyrillic twin, lower case only because the
# comparison casefolds first. No duplicates: a repeated key silently changes the
# mapping and the table stops meaning what it says.
_LOOKALIKE = str.maketrans("acepoxy", "асероху")


@dataclass(frozen=True)
class Source:
    """Where a message's text comes from when the corpus may not carry it.

    The 122 hand-annotated utterances in the `speech` family come from OpenSTT
    `asr_calls_2_val`, licensed **CC BY-NC 4.0**: measuring with it is allowed,
    shipping it is not. So the corpus stores a REFERENCE and the text is
    hydrated from `~/.cache/pseudex-bench/` at score time.

    `sha256` is not bookkeeping. A re-downloaded corpus whose lines shifted by
    one would silently move every offset in the family, and the benchmark would
    keep printing numbers. Hydration compares the digest and refuses.
    """

    corpus: str      # e.g. "speech_calls"
    line: int        # 1-based line number in that corpus
    sha256: str      # digest of the expected text, utf-8
    licence: str     # e.g. "CC BY-NC 4.0"


@dataclass(frozen=True)
class PiiItem:
    """One personal datum, with where it sits and where it must arrive.

    `tool_param` is what separates this from a NER corpus. A labelled span says
    «this is a phone». This says «this phone is the argument the agent must pass
    to `create_order.phone`, and the value that arrives there must be the real
    one».

    `id` is new in v2 and it is load-bearing. v1 joined `expected_call` to the
    ground truth by PARAM NAME, which stops being unique the moment a case
    expects two calls — and the `indirect` family expects exactly that: a lookup
    and then an update carrying the value the lookup returned.
    """

    id: str             # case-local, stable, referenced by calls and links
    type: str
    value: str          # the surface form AS WRITTEN in the message
    start: int
    end: int
    canonical: str      # the form a CRM would store: nominative name, +7 phone
    # WHICH MESSAGE it sits in, indexing `Case.messages` — every message, not
    # only the user turns. v1 indexed user turns, which had no way to address a
    # tool result, and a tool result is where the customer's own CRM hands the
    # model an address that appeared in no user turn.
    msg: int
    # WHO it belongs to. Two items sharing an identity are the same person or
    # the same place and must receive the SAME substitute; two identities must
    # not collide. Items sharing an identity must share a type — a person's name
    # and their phone are one person and two identities here, because they get
    # two substitutes.
    identity: str
    # `required` = masking it is the law. `optional` = it identifies nobody on
    # its own; counted in its own column, never folded into recall.
    duty: str
    # None = present, but no tool consumes it. An `optional` item may never name
    # one: demanding a real value in an argument for a datum we also declared
    # safe to leave alone is a contradiction the scorer cannot resolve.
    tool_param: str | None


@dataclass(frozen=True)
class Negative:
    """Something PII-shaped that is not personal data.

    Scored as hard as recall. A gateway that masks the order number the customer
    just asked about has broken the conversation as surely as one that leaks.
    """

    value: str
    why: str
    msg: int


@dataclass(frozen=True)
class LinkExpectation:
    """Whether two mentions must reach the model as ONE value.

    This is the axis v1 could not write down, and the engine's whole
    conversation scope exists to serve it. `left` and `right` are item ids;
    `case` names the OTHER case when the pair spans a `preceded_by` chain, which
    is how the `scope` family states its negative claim — the same partial
    mention, a different `conversation_id`, and linking it would hand one
    customer's address to another customer's dialogue.
    """

    left: str
    right: str
    kind: str          # one of LINKS
    case: str          # "" = both items are in this case
    why: str


@dataclass(frozen=True)
class ExpectedCall:
    """One call a correct agent makes, with the REAL values in it.

    An ordered LIST of these replaces v1's single `expected_call`, because the
    `indirect` family cannot be stated otherwise: you cannot update an address
    before you have looked it up, and the value that goes into the update never
    appeared in a user turn.

    MATCHED IN ORDER, AS A SUBSEQUENCE. Extra calls do not fail the round trip —
    a model is allowed to look something up twice — but they are counted and
    reported on the transparency axis. BFCL's response checker accepts an
    unordered subset and calls a different trajectory correct; that leniency is
    right for «did the task get done» and wrong here, where the order is the
    contract.
    """

    name: str
    after_msg: int                        # expected once this message is in scope
    arguments: dict[str, str | int | float]
    pii_items: list[str]                  # item ids whose real value must arrive


@dataclass(frozen=True)
class Case:
    id: str
    family: str
    scenario: str
    register: str
    difficulty: str
    length_rung: str
    # "" means the harness must DERIVE the conversation identity from the
    # transcript, which is a different code path from being handed one and is
    # what a customer gateway with no conversation field actually triggers. Both
    # forms must occur in the corpus; `validate_corpus` refuses one that has
    # only one of them.
    conversation_id: str
    # The tool contract's demand over protected values. `equality` for almost
    # everything; anything else marks the case as measuring an incompatibility.
    relation: str
    messages: list[dict[str, object]]
    tools: list[ToolSchema]
    pii: list[PiiItem]
    # An id the scorer must have scored FIRST, sharing one tenant vault with
    # this case. The `scope` family is a pair of conversations and there is no
    # honest way to state «these must NOT be linked» inside a single case.
    preceded_by: str
    # How many people labelled this case, and whether disagreements were
    # adjudicated. 0 = generated. TAB's kappa 0.46 on the direct/quasi decision
    # is the warning: `duty` on a hand-labelled case needs two annotators and a
    # tiebreak, and this field is what lets a human ceiling be computed later
    # instead of asserted.
    annotators: int
    adjudicated: bool
    negatives: list[Negative] = field(default_factory=list)
    links: list[LinkExpectation] = field(default_factory=list)
    calls: list[ExpectedCall] = field(default_factory=list)
    # Which item a correct ranking picks. Required when `relation` is
    # incompatible: without it the family can report «the model chose» and not
    # «the model chose the right one», and the difference is whether a real —
    # but wrong — person's data reached the tool.
    expected_choice: str = ""
    # A closed answer the assistant's final text must assert, for `compare`.
    # An ENUM and never a substring test: WebArena's `must_include` accepts a
    # reply containing the reference plus anything else, and ABC measured that
    # leniency at 1.4-5.2% inflation. A yes/no question has two answers, so the
    # scorer parses to one of them or records `model_absent`.
    expected_answer: str = ""
    # Declares that this `voice_itn` / `voice_raw` case deliberately carries
    # digits. Default False, which is what makes the register gate below bite.
    asr_digits: bool = False

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Ladder:
    """The frozen tier ordering. Data, never a sampler.

    `corpus_sha256` is checked before the ladder is used. On a mismatch the
    runner must REFUSE and print which ids no longer exist — it must not
    silently re-sample, because a re-sampled nano is a different measurement
    wearing last month's name.
    """

    version: int
    seed: int
    corpus_sha256: str
    order: list[str]


# --- accessors ------------------------------------------------------------

def message_text(case: Case, index: int) -> str:
    """The text of one message. Offsets index THIS string.

    A tool result carrying JSON is stored as the SERIALISED string, because that
    is exactly what a gateway sees on the wire — the envelope's `content` is a
    string and masking runs over it as flat text. Storing the object and
    serialising at score time would let the scorer's separator choices move
    every offset in the family.
    """
    content = case.messages[index].get("content")
    if not isinstance(content, str):
        raise TypeError(f"{case.id}: message {index} has non-string content; "
                        f"the corpus stores wire form, not objects")
    return content


def case_characters(case: Case) -> int:
    """Total characters across all messages — the unit `length_rung` bands."""
    return sum(len(message_text(case, i)) for i in range(len(case.messages)))


def hydrate(case: Case, resolve: Callable[[str, int], str]) -> Case:
    """Fill in text the corpus is not licensed to carry.

    `resolve(corpus, line)` returns the text; the digest is checked against
    `Source.sha256` and a mismatch RAISES. A benchmark that keeps scoring after
    its source has shifted underneath it is worse than one that stops: the
    numbers still look like numbers.
    """
    messages: list[dict[str, object]] = []
    for message in case.messages:
        source = message.get("source")
        if not isinstance(source, dict):
            messages.append(dict(message))
            continue
        text = resolve(str(source["corpus"]), int(source["line"]))
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(
                f"{case.id}: {source['corpus']} line {source['line']} hashes to "
                f"{digest[:12]}, the corpus expects {str(source['sha256'])[:12]} — "
                f"the source shifted and every offset in this case is now wrong")
        filled = dict(message)
        filled["content"] = text
        messages.append(filled)
    return Case(**{**asdict(case), "messages": messages})  # type: ignore[arg-type]


# --- the comparison rule, stated here so a scorer cannot invent its own ----

def digits_of(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def same_value(produced: str | None, expected: str) -> bool:
    """Whether the tool received the right thing.

    `produced is None` means the substitute resolved to NOTHING, and it is
    False, explicitly. v1 fell through to `.strip()` on None and raised, which
    made the «token not found» branch — the branch naming the worst outcome —
    unreachable for the life of the corpus.

    Numeric identifiers are compared by digits: a phone may legitimately come
    back as +7… where it went in as 8…, and both name the same subscriber. Text
    is compared case-insensitively, because case is not identity.

    NOTHING ELSE IS FORGIVEN. Not whitespace, not a Latin twin, not a prefix.
    Those get their own break kinds and are printed beside the rate. A scorer
    that normalises a shape away stops seeing the real defect wearing it:
    «позвоните Игорю» coming back as «Игорю» has the same shape as a repair and
    is a declined name written into a customer's CRM.
    """
    if produced is None:
        return False
    expected_digits = digits_of(expected)
    if len(expected_digits) >= 6:
        produced_digits = digits_of(produced)
        if not produced_digits:
            return False
        return (produced_digits.endswith(expected_digits[-10:])
                or expected_digits.endswith(produced_digits[-10:]))
    return produced.strip().casefold() == expected.strip().casefold()


def classify_break(expected: str, restored: str | None,
                   other_identities: frozenset[str]) -> str:
    """Name a broken round trip. One of BREAK_KINDS.

    `residual` and `model_absent` are decided by the CALLER before this runs —
    the first needs the vault (a surviving minted token), the second needs to
    know the call was never made. Neither is a string comparison and pretending
    otherwise here would let a scorer guess at them.

    `other_identities` holds the canonical values of every OTHER person or place
    in the case. A restored value that matches one of them is the worst outcome
    the product has: the tool executed, returned 200, and acted on a real human
    being who is not the one the conversation was about. v1 had no name for it
    and reported it as «форма изменена».
    """
    if restored is None:
        return "not_resolved"
    if same_value(restored, expected):
        return "ok"
    if any(same_value(restored, other) for other in other_identities):
        return "other_person"
    if restored.replace(" ", "") == expected.replace(" ", ""):
        return "space_repaired"
    if (restored.lower().translate(_LOOKALIKE)
            == expected.lower().translate(_LOOKALIKE)):
        return "lookalike_repaired"
    if expected.startswith(restored) or restored.startswith(expected):
        return "truncated"
    return "inflected"


def register_weighted(per_register: dict[str, tuple[int, int]]) -> float:
    """A traffic-weighted rate from per-register (hit, total) counts.

    Printed BESIDE the unweighted total, never instead of it. A register with no
    cases contributes nothing and its weight is redistributed, so a tier that
    happens to miss a register does not silently score it at zero.
    """
    live = {name: counts for name, counts in per_register.items() if counts[1]}
    mass = sum(REGISTER_WEIGHTS[name] for name in live)
    if not mass:
        return 0.0
    return sum(REGISTER_WEIGHTS[name] * counts[0] / counts[1]
               for name, counts in live.items()) / mass


# --- validation -----------------------------------------------------------

def audit_unlabelled(case: Case) -> list[str]:
    """PII-shaped strings that neither the gold nor the negatives claim.

    THE ABC OUTCOME-VALIDITY GATE, made mechanical. tau-bench passes any task
    whose ground truth writes nothing — an agent that does nothing scores 1.0 on
    38% of its airline subset — and our exact analogue is a case whose filler
    quietly contains a phone number nobody labelled. The gateway masks it, the
    scorer counts a false mask, and the corpus was wrong.

    Shapes only, no recognizers: this must stay true when our detector changes,
    or the independence rule is decoration.
    """
    problems: list[str] = []
    claimed: list[tuple[int, int, int]] = [
        (item.msg, item.start, item.end) for item in case.pii]
    for index in range(len(case.messages)):
        text = message_text(case, index)
        for negative in case.negatives:
            if negative.msg != index:
                continue
            start = text.find(negative.value)
            while start >= 0:
                claimed.append((index, start, start + len(negative.value)))
                start = text.find(negative.value, start + 1)
        for pattern in (_SHAPE_PHONE, _SHAPE_EMAIL, _SHAPE_DIGITS):
            for match in pattern.finditer(text):
                if any(msg == index and start < match.end() and end > match.start()
                       for msg, start, end in claimed):
                    continue
                problems.append(
                    f"{case.id}: message {index} holds {match.group()!r}, which "
                    f"is PII-shaped and claimed by neither pii nor negatives")
    return problems


def validate(case: Case) -> list[str]:
    """Structural problems that would make a case unscoreable.

    Run at BUILD time, not at score time. A benchmark whose ground truth has
    drifted from its own text keeps producing numbers, and offsets are the part
    that rots first because every register transform rewrites the string.
    """
    problems: list[str] = []
    if case.family not in FAMILIES:
        problems.append(f"{case.id}: unknown family {case.family!r}")
    if case.register not in REGISTERS:
        problems.append(f"{case.id}: unknown register {case.register!r}")
    if case.difficulty not in DIFFICULTIES:
        problems.append(f"{case.id}: unknown difficulty {case.difficulty!r}")
    if case.relation not in RELATIONS:
        problems.append(f"{case.id}: unknown relation {case.relation!r}")
    if case.length_rung not in LENGTH_RUNGS:
        problems.append(f"{case.id}: unknown length rung {case.length_rung!r}")
        return problems

    # A case is not allowed to be silently empty. tau-bench's trap: a task whose
    # ground truth demands nothing is passed by an agent that does nothing, and
    # here that is a gateway that masks nothing at all.
    if not any(item.duty == "required" for item in case.pii) and not case.negatives:
        problems.append(
            f"{case.id}: no required pii and no negatives — a gateway that does "
            f"nothing passes this case")

    unsourced = [i for i, m in enumerate(case.messages)
                 if not isinstance(m.get("content"), str)]
    if unsourced:
        problems.append(f"{case.id}: messages {unsourced} carry no wire-form "
                        f"content; hydrate before validating")
        return problems

    low, high = LENGTH_RUNGS[case.length_rung]
    size = case_characters(case)
    if not low <= size <= high:
        problems.append(f"{case.id}: {size} characters is outside the "
                        f"{case.length_rung} band {low}-{high}")

    # A message that declares a licensed source must ship EMPTY. Checked here so
    # an accidental commit of CC BY-NC text is a build failure rather than a
    # licence violation discovered by somebody else.
    for index, message in enumerate(case.messages):
        if isinstance(message.get("source"), dict) and message.get("content"):
            problems.append(f"{case.id}: message {index} names a licensed source "
                            f"AND carries its text; the corpus may not ship it")

    seen_ids: set[str] = set()
    spans_by_msg: dict[int, list[tuple[int, int, str]]] = {}
    by_identity: dict[str, set[str]] = {}
    for item in case.pii:
        if item.id in seen_ids:
            problems.append(f"{case.id}: duplicate item id {item.id!r}")
        seen_ids.add(item.id)
        if item.duty not in DUTIES:
            problems.append(f"{case.id}: item {item.id} has unknown duty "
                            f"{item.duty!r}")
        if item.duty == "optional" and item.tool_param:
            problems.append(
                f"{case.id}: item {item.id} is optional to mask AND claims tool "
                f"param {item.tool_param!r} — a value the round trip demands "
                f"back cannot also be one we do not require masked")
        if not 0 <= item.msg < len(case.messages):
            problems.append(f"{case.id}: item {item.id} points at message "
                            f"{item.msg}, the case has {len(case.messages)}")
            continue
        if case.messages[item.msg].get("role") == "system":
            problems.append(
                f"{case.id}: item {item.id} sits in a system message; whether a "
                f"system prompt is masked depends on the deployment leg "
                f"(`skip_template`), so the corpus does not test it")
        text = message_text(case, item.msg)
        if text[item.start:item.end] != item.value:
            problems.append(
                f"{case.id}: message {item.msg} span {item.start}:{item.end} "
                f"holds {text[item.start:item.end]!r}, ground truth says "
                f"{item.value!r}")
        for start, end, other in spans_by_msg.setdefault(item.msg, []):
            if item.start < end and item.end > start:
                problems.append(f"{case.id}: items {other} and {item.id} overlap "
                                f"in message {item.msg}")
        spans_by_msg[item.msg].append((item.start, item.end, item.id))
        if item.identity:
            by_identity.setdefault(item.identity, set()).add(item.type)

    # One identity, one type. A person's name and their phone are one human and
    # TWO identities here, because they receive two substitutes and the
    # consistency axis compares substitutes. v1 did not check this and a corpus
    # bug of that shape reports as a gateway failure.
    for identity, types in by_identity.items():
        if len(types) > 1:
            problems.append(f"{case.id}: identity {identity!r} spans types "
                            f"{sorted(types)}; one identity is one substitute")

    for negative in case.negatives:
        if not 0 <= negative.msg < len(case.messages):
            problems.append(f"{case.id}: negative {negative.value!r} points at "
                            f"message {negative.msg}")
        elif negative.value not in message_text(case, negative.msg):
            problems.append(f"{case.id}: negative {negative.value!r} is not in "
                            f"message {negative.msg}")

    tool_names = {tool["function"]["name"] for tool in case.tools}
    by_name = {tool["function"]["name"]: tool for tool in case.tools}
    previous = -1
    for call in case.calls:
        if call.name not in tool_names:
            problems.append(f"{case.id}: expected call {call.name!r} is not "
                            f"among the offered tools")
            continue
        if call.after_msg < previous:
            problems.append(f"{case.id}: expected calls are out of order at "
                            f"{call.name!r}")
        previous = call.after_msg
        params = set(by_name[call.name]["function"]["parameters"]["properties"])
        for item_id in call.pii_items:
            item = next((i for i in case.pii if i.id == item_id), None)
            if item is None:
                problems.append(f"{case.id}: call {call.name!r} consumes unknown "
                                f"item {item_id!r}")
                continue
            if not item.tool_param:
                problems.append(f"{case.id}: call {call.name!r} consumes item "
                                f"{item_id!r}, which claims no tool param")
            elif item.tool_param not in params:
                problems.append(
                    f"{case.id}: item {item_id!r} claims param "
                    f"{item.tool_param!r}, absent from {call.name!r}")

    for link in case.links:
        if link.kind not in LINKS:
            problems.append(f"{case.id}: link {link.left}/{link.right} has "
                            f"unknown kind {link.kind!r}")
        if link.left not in seen_ids:
            problems.append(f"{case.id}: link names unknown item {link.left!r}")
        if not link.case and link.right not in seen_ids:
            problems.append(f"{case.id}: link names unknown item {link.right!r}")
        if link.case and link.case != case.preceded_by:
            problems.append(
                f"{case.id}: link reaches into {link.case!r}, which is not the "
                f"case this one is preceded by ({case.preceded_by!r}) — only a "
                f"case in the same vault group is in scope")

    if case.relation not in COMPATIBLE_RELATIONS:
        if case.family != "rank":
            problems.append(f"{case.id}: relation {case.relation!r} is "
                            f"incompatible with pseudonymisation and belongs in "
                            f"the `rank` family")
        if not case.expected_choice:
            problems.append(
                f"{case.id}: an incompatible relation needs `expected_choice`, "
                f"or the family can only report that the model chose and never "
                f"whether it chose the right one")
        elif case.expected_choice not in seen_ids:
            problems.append(f"{case.id}: expected_choice {case.expected_choice!r} "
                            f"is not an item of this case")
    if case.expected_answer and case.expected_answer not in ("да", "нет"):
        problems.append(f"{case.id}: expected_answer {case.expected_answer!r} is "
                        f"not a closed answer; free text invites a substring "
                        f"test and a substring test is the leniency we refuse")

    # THE REGISTER GATE, and it is the one v1 needed and did not have. Measured
    # on 12 950 human transcripts of real Russian phone calls: ZERO carry a
    # digit. A `voice_raw` case with digits in it is not verbatim speech, and a
    # `voice_itn` case without them is indistinguishable from `chat`, which
    # would make the split decorative.
    if case.register in ("voice_raw", "voice_itn"):
        speech = " ".join(message_text(case, i)
                          for i, m in enumerate(case.messages)
                          if m.get("role") in ("user", "tool"))
        has_digits = bool(_ANY_DIGITS.search(speech))
        if case.register == "voice_raw" and has_digits and not case.asr_digits:
            problems.append(
                f"{case.id}: voice_raw case carries digits without declaring "
                f"`asr_digits`; real call transcripts carry none (0 of 12 950 "
                f"measured on asr_calls_2_val)")
        if case.register == "voice_itn" and not has_digits:
            problems.append(
                f"{case.id}: voice_itn is defined by inverse text normalisation "
                f"being ON; with no digits it is a `chat` case in disguise")

    problems.extend(audit_unlabelled(case))
    return problems


def validate_corpus(cases: list[Case]) -> list[str]:
    """Properties no single case can carry, and each one is a past defect.

    A per-case validator cannot see that the corpus never exercises the derived
    conversation id, or that a `preceded_by` points forward, or that a tier
    would report a per-type rate from two instances. Those are corpus-level
    claims and they belong here.
    """
    problems: list[str] = []
    positions = {case.id: index for index, case in enumerate(cases)}
    if len(positions) != len(cases):
        problems.append("duplicate case ids in the corpus")

    for index, case in enumerate(cases):
        if not case.preceded_by:
            continue
        if case.preceded_by not in positions:
            problems.append(f"{case.id}: preceded_by names a case that does not "
                            f"exist ({case.preceded_by!r})")
        elif positions[case.preceded_by] >= index:
            problems.append(
                f"{case.id}: preceded_by {case.preceded_by!r} comes later in the "
                f"file; a vault group is scored in file order and a forward "
                f"reference would be scored against an empty vault")

    families = {case.family for case in cases}
    missing = [name for name in FAMILIES if name not in families]
    if missing:
        problems.append(f"families with no cases: {missing} — a tier drawn from "
                        f"this corpus cannot hold a floor of one per family")

    registers = {case.register for case in cases}
    if registers != set(REGISTERS):
        problems.append(f"registers present: {sorted(registers)}; the weighted "
                        f"total is only defined over all five")

    # BOTH SCOPE FORMS. Being handed a conversation id and deriving one from the
    # transcript are different code paths, and the derived one is what a
    # customer gateway with no conversation field actually triggers. v1
    # exercised neither: it passed `conversation_id=""` and had no linking case.
    given = any(case.conversation_id for case in cases)
    derived = any(not case.conversation_id for case in cases)
    if not (given and derived):
        problems.append("the corpus must contain cases with an explicit "
                        "conversation_id AND cases with none, or one of the two "
                        "scope paths is never scored")

    if not any(case.length_rung == "long" for case in cases):
        problems.append("no `long` case: v1's entire corpus fit in 159 "
                        "characters and the defect this dimension exists for "
                        "cannot appear below a few thousand")

    # A NEGATIVE-ONLY CASE IS PASSED BY A GATEWAY THAT DOES NOTHING, and the
    # per-case gate above cannot say so — «do not mask this» is a real demand and
    # a null gateway satisfies it. They are still the most valuable cases in the
    # corpus (the 79 real utterances that name a street and are not an address
    # were said by living people and no generator would build them), so the rule
    # is a declared bound, not a ban: they may not become the corpus, and a tier
    # made only of them measures nothing at all.
    negative_only = [case for case in cases
                     if not any(item.duty == "required" for item in case.pii)]
    if len(negative_only) > len(cases) // 10:
        problems.append(
            f"{len(negative_only)} of {len(cases)} cases demand only that "
            f"nothing be masked; a gateway that does nothing passes all of them, "
            f"so they may not exceed a tenth of the corpus")

    if not any(link.kind == "different" for case in cases for link in case.links):
        problems.append("no `different` link expectation: without one the corpus "
                        "only ever asks whether the gateway links, never whether "
                        "it refuses to")

    return problems


def type_denominators(cases: list[Case]) -> dict[str, int]:
    """Gold items per type, for the suppression rule.

    THE RULE, enforced in the scorer and stated here so it is not a convention:
    a per-type rate with a denominator below five is printed as a COUNT, never
    as a percentage. Measured on v1's corpus, a 10-case draw genuinely holds
    fewer than five instances of seven of the nine types, and «полнота 99%» over
    two CARD instances is a lie by omission.
    """
    counts: dict[str, int] = {}
    for case in cases:
        for item in case.pii:
            if item.duty == "required":
                counts[item.type] = counts.get(item.type, 0) + 1
    return counts


def corpus_digest(cases: list[Case]) -> str:
    """The digest a `Ladder` is pinned to. Order- AND claim-sensitive.

    Order, because a reordered corpus is a different corpus to a prefix-based
    tier ladder. Claims, because this hashed ids ALONE until a re-labelling of
    `dispatch`'s source showed what that costs: the ground truth moved, every
    id stayed, and the pin stayed green. A pin that can only see names is the
    same shape of defect as a benchmark whose filter cannot express its own
    failure — it reports agreement about something it never looked at. A
    shifted offset, a corrected span, a changed expected call are each a
    different measurement wearing the same tier name.

    MESSAGE TEXT IS DELIBERATELY NOT HASHED. `speech` carries its utterances by
    reference until `hydrated()` fills them in, so hashing content would make
    the digest depend on whether the caller hydrated first, and `tier()` would
    refuse a legitimately hydrated corpus. The claims are hydration-invariant,
    and they are what a ladder is actually pinning.
    """
    digest = hashlib.sha256()
    for case in cases:
        digest.update(case.id.encode("utf-8"))
        digest.update(b"\x00")
        claims = (
            [(item.id, item.type, item.value, item.start, item.end,
              item.canonical, item.msg, item.identity, item.duty,
              item.tool_param) for item in case.pii],
            [(neg.value, neg.why, neg.msg) for neg in case.negatives],
            [(call.name, call.after_msg, sorted(call.arguments.items()),
              call.pii_items) for call in case.calls],
            [(link.left, link.right, link.kind, link.case, link.why)
             for link in case.links],
        )
        digest.update(json.dumps(claims, ensure_ascii=False, sort_keys=True,
                                 default=str).encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


def tier(cases: list[Case], ladder: Ladder, name: str) -> list[Case]:
    """The nested prefix for a tier. Reads the ladder, never samples.

    Refuses on a digest mismatch and names the ids that vanished. Re-sampling
    instead would produce a set that answers a different question under the same
    label, and the whole point of freezing was that last month's nano number and
    this month's are about the same twenty cases.
    """
    if name not in TIER_SIZES:
        raise ValueError(f"unknown tier {name!r}")
    actual = corpus_digest(cases)
    if actual != ladder.corpus_sha256:
        known = {case.id for case in cases}
        gone = [case_id for case_id in ladder.order if case_id not in known]
        raise ValueError(
            f"ladder v{ladder.version} was frozen against corpus "
            f"{ladder.corpus_sha256[:12]}, this corpus is {actual[:12]}; "
            f"{len(gone)} ladder ids no longer exist: {gone[:8]}. Regenerate the "
            f"ladder deliberately (--regenerate, bump version) — do not sample.")
    by_id = {case.id: case for case in cases}
    size = TIER_SIZES[name] or len(ladder.order)
    return [by_id[case_id] for case_id in ladder.order[:size]]
