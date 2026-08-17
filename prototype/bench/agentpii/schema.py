"""The case format. This file IS the specification — the benchmark is publishable
only if someone else can regenerate and re-score it without reading our engine.

WHY A NEW BENCHMARK EXISTS AT ALL. Three families of evaluation are established
and none of them measures what a PII gateway in front of a tool-calling agent
actually has to get right:

  * NER corpora (NEREL, Collection3, WikiANN-ru) — real Russian, but news prose,
    no tools, and their labels answer "is this an entity", not "is this personal
    data belonging to somebody in this conversation".
  * PII-masking corpora (ai4privacy pii-masking-300k/400k) — the right task, but
    verified directly: no Russian, and no tool calls.
  * Tool-calling benchmarks (BFCL, tau-bench) — the right shape, but English and
    with no personal data in them at all.

So the intersection — Russian conversational personal data flowing through tool
schemas that CONSUME it — has no benchmark. That intersection is the whole
product category, which is why the numbers everyone quotes (recall on a NER set)
do not predict whether a masking gateway breaks an agent.

THREE AXES, AND THE POINT IS THAT THEY COME APART. A system can score perfectly
on any one while failing another, and only measuring all three catches it:

  1. DETECTION — precision and recall per type over the user's message.
  2. ROUND TRIP — did the REAL value arrive at the tool. This is the axis with no
     prior art, and it is not implied by axis 1: a name can be detected perfectly,
     masked into a grammatically disagreeing substitute, silently repaired by the
     model, and then fail to resolve back. We shipped exactly that bug and it was
     invisible to every detection metric we had.
  3. TRANSPARENCY — did the model still produce the right call. A substitute that
     is detected and reversible can still be implausible enough to change the
     model's behaviour (`[PHONE_1]` where a phone was expected).

WHAT MAKES A CASE HARD IS THE REGISTER, NOT THE ENTITY. Support traffic is not
document prose. The same phone number arrives as «+7 916 214-88-03» in a form and
as «89162148803» or «восемь девятьсот шестнадцать...» in a chat message, and a
detector tuned on the first shape quietly misses the rest. Registers are a first
class dimension here for that reason.

INDEPENDENCE RULE, inherited from `make_stress.py`: cases are authored from the
DOMAIN — what a Russian support conversation contains — and never from a list of
what our detector currently finds. A corpus tuned against the detector measures
self-consistency and nothing else.
"""

from dataclasses import dataclass, field, asdict
from typing import Any

# --- registers ------------------------------------------------------------
#
# How the SAME personal datum is written by different people in different tools.
# Ordered by how far they sit from the tidy form a document generator produces —
# which is the form every synthetic PII corpus is implicitly made of.
REGISTERS: tuple[str, ...] = (
    "clean",   # as typed into a form: «Иванов Пётр Сергеевич, +7 916 214-88-03»
    "chat",    # as typed into a messenger: lower case, no punctuation, run-on
    "sloppy",  # typos, mixed keyboard layouts, missing separators
    "voice",   # speech-to-text: numbers spelled out, no punctuation at all
)

# --- difficulty -----------------------------------------------------------
DIFFICULTIES: tuple[str, ...] = (
    "easy",         # one entity, unambiguous, cued
    "hard",         # several entities, non-PII numbers adjacent, inflected forms
    "adversarial",  # built to produce a false positive or hide a true one
)


@dataclass(frozen=True)
class PiiItem:
    """One personal datum in the user's text, with where it is and where it goes.

    `tool_param` is what makes this benchmark different from a NER corpus. A
    labelled span says "this is a phone". This says "this phone is the argument
    the agent must pass to `create_order.phone`, and the value that arrives there
    must be the real one".
    """

    type: str
    value: str          # the surface form AS WRITTEN in the message
    start: int
    end: int
    canonical: str      # the form a CRM would store: nominative name, +7 phone
    tool_param: str | None = None   # None = present but no tool consumes it
    # WHICH MESSAGE it sits in. Offsets index that message, not a concatenation:
    # a dialogue is a list of turns and a span that indexes the wrong one still
    # scores, wrongly.
    turn: int = 0
    # WHO this datum belongs to. Two items sharing an identity are the same
    # person or the same address and MUST receive the same substitute; two
    # different identities must receive different ones. Nothing else in the
    # benchmark tests that, and it is the product's own claim — «один человек,
    # один токен и завтра, и в соседнем диалоге».
    identity: str = ""


@dataclass(frozen=True)
class Negative:
    """Something that looks like personal data and is not.

    Scored as hard as recall. A gateway that masks the order number the customer
    just asked about has broken the conversation as surely as one that leaks.
    """

    value: str
    why: str


@dataclass(frozen=True)
class Case:
    id: str
    scenario: str
    register: str
    difficulty: str
    messages: list[dict[str, str]]
    tools: list[dict[str, Any]]
    pii: list[PiiItem]
    negatives: list[Negative] = field(default_factory=list)
    expected_call: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def user_turns(case: Case) -> list[str]:
    """The user messages, in order. PII offsets index into `turn`-th of these.

    Deliberately derived rather than duplicated next to the messages: a corpus
    that carries the text twice grows two versions of itself, and the offsets
    then point silently at the wrong one.
    """
    return [m["content"] for m in case.messages if m["role"] == "user"]


def user_text(case: Case) -> str:
    """The first user message. Kept for single-turn cases."""
    turns = user_turns(case)
    if not turns:
        raise ValueError(f"case {case.id} has no user message")
    return turns[0]


def validate(case: Case) -> list[str]:
    """Structural problems that would make a case unscoreable.

    Run at build time, not at score time. A benchmark whose ground truth does not
    line up with its own text produces numbers that look fine and mean nothing —
    and offsets are the part that rots first, because every register transform
    rewrites the string.
    """
    problems: list[str] = []
    turns = user_turns(case)
    text = turns[0] if turns else ""
    if case.register not in REGISTERS:
        problems.append(f"{case.id}: unknown register {case.register!r}")
    if case.difficulty not in DIFFICULTIES:
        problems.append(f"{case.id}: unknown difficulty {case.difficulty!r}")
    for item in case.pii:
        if item.turn >= len(turns):
            problems.append(f"{case.id}: item points at turn {item.turn}, "
                            f"the dialogue has {len(turns)} user turns")
            continue
        turn_text = turns[item.turn]
        if turn_text[item.start:item.end] != item.value:
            problems.append(
                f"{case.id}: turn {item.turn} span {item.start}:{item.end} holds "
                f"{turn_text[item.start:item.end]!r}, ground truth says {item.value!r}")
    for negative in case.negatives:
        if not any(negative.value in turn for turn in turns):
            problems.append(f"{case.id}: negative {negative.value!r} not in text")
    if case.expected_call is not None:
        names = {tool["function"]["name"] for tool in case.tools}
        if case.expected_call["name"] not in names:
            problems.append(
                f"{case.id}: expected call {case.expected_call['name']!r} "
                f"is not among the offered tools")
        # Every parameter the ground truth passes by value must be traceable to a
        # PII item, or the round-trip axis has nothing to check it against.
        consumed = {item.tool_param for item in case.pii if item.tool_param}
        for param in case.expected_call.get("pii_params", []):
            if param not in consumed:
                problems.append(
                    f"{case.id}: expected_call consumes {param!r} but no pii item "
                    f"claims it")
    return problems
