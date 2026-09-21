"""The case format. This file is the specification; `schema/case.schema.json`
is its machine-checkable shadow and the two must agree (gate G1 runs the JSON
schema, gate G2 runs the checks below that a JSON schema cannot express).

WHAT A CASE IS. One short Russian support conversation in which the customer
states personal data, plus the tool the agent is expected to call with that
data. A masking gateway sits between the conversation and the model; the
benchmark asks three things of it that no NER score answers:

  * did the personal data reach the model at all (LEAK, COVERAGE),
  * did the REAL value reach the tool after the gateway restored the agent's
    call (ROUND TRIP),
  * did the gateway leave alone the order numbers, amounts and dates that
    look like personal data and are not (OVERMASK).

GROUND TRUTH IS THE CANONICAL FORM OF WHAT WAS WRITTEN. A chat message with
no patronymic must not demand one back; a phone typed as «89071234567» is
owed back as those digits, not as «+7 (907) …». Offsets are computed while
the message is assembled (`assemble.py`), never by searching the finished
string — a search finds the FIRST occurrence, and a message that mentions the
same phone twice would then point at the wrong one.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

VERSION = "0.1"

TYPES: tuple[str, ...] = (
    "NAME", "PHONE", "EMAIL", "ADDRESS", "SNILS", "INN", "PASSPORT", "CARD", "DOB",
)

REGISTERS: tuple[str, ...] = (
    "clean",   # as typed into a form: «Петров Иван Сергеевич, +7 907 123-45-67»
    "chat",    # as typed into a messenger: lower case, no separators, no patronymic
    "sloppy",  # one generic slip: swapped letters, a dropped letter, a Latin twin, a lost separator
)

FAMILIES: tuple[str, ...] = (
    "create_order", "check_status", "verify_identity", "refund", "send_sms", "second_mention",
    "decompose",
)

# How the second mention of a person is written in `second_mention` cases.
SUBCASES: tuple[str, ...] = ("lower", "declined", "reformatted")

# Where a name came from. The benchmark's author sells a masker with a large
# name gazetteer; so does every serious competitor. A corpus of common names
# cannot fail against any of them, so the report prints the tiers apart.
NAME_TIERS: tuple[str, ...] = ("common", "tail", "diminutive", "foreign")

NEGATIVE_KINDS: tuple[str, ...] = (
    "order_no", "track_no", "invoice", "amount", "doc_date", "city",
)

# The canary rides in every case file and must be quoted wherever a case is
# quoted. It does not stop a model from training on the corpus; it lets a
# reader ASK a model whether it has seen it.
CANARY = "AGENTMASK-RU-CANARY-7c1e4b2a-6f3d-4a8e-9b1c-2d5e8f0a3b7c"
DATA_LICENSE = "CC-BY-4.0"


@dataclass(frozen=True)
class PiiItem:
    """One personal datum: where it is in the conversation and where it goes.

    `tool_param` is what makes this a benchmark of gateways rather than a NER
    corpus: this phone is the argument the agent must pass to `create_order`,
    and the value that arrives there must be the real one. `identity` ties two
    mentions of one person together for the consistency line.
    """

    id: str
    type: str
    value: str          # the surface form AS WRITTEN in the message
    canonical: str      # what the tool is owed; equals `value` unless a register says otherwise
    turn: int           # index into `messages`; always a user message
    start: int
    end: int
    tool_param: str | None
    cue: bool           # a cue word stands right before the value («телефон:»)
    tier: str | None    # NAME_TIERS for names, None otherwise
    identity: str       # persons sharing a value across turns share this
    # THE VALUE IN PARTS, where the tool wants them apart: `last_name` /
    # `first_name` / `middle_name` for a name, `street` / `house` / `flat`
    # for an address — each part as the customer WROTE it, cut by the same
    # rule the scripted agent cuts the substitute with (`parts.py`). A
    # placeholder cannot be cut: that is the whole point of the family.
    parts: dict[str, str] | None = None


@dataclass(frozen=True)
class Negative:
    """A value that looks like personal data and is not. Masking it breaks
    the agent as surely as leaking a real one breaks the law."""

    value: str
    kind: str
    turn: int
    start: int
    end: int


@dataclass(frozen=True)
class ExpectedCall:
    name: str
    pii_params: tuple[str, ...]          # the parameters that carry personal data
    plain_params: dict[str, str]         # the parameters that carry negatives, verbatim


@dataclass(frozen=True)
class Source:
    generator: str
    version: str
    seed: int | None


@dataclass(frozen=True)
class Case:
    id: str
    version: str
    family: str
    register: str
    subcase: str | None
    messages: tuple[dict[str, str], ...]
    tools: tuple[dict[str, object], ...]
    expected_call: ExpectedCall
    pii: tuple[PiiItem, ...]
    negatives: tuple[Negative, ...]
    hard: dict[str, str] | None          # {"why": ...} when a naive regex is EXPECTED to miss
    created_at: str
    source: Source
    canary: str
    license: str


# --- (de)serialisation -----------------------------------------------------

def to_dict(case: Case) -> dict[str, object]:
    raw = asdict(case)
    raw["messages"] = list(case.messages)
    raw["tools"] = list(case.tools)
    # `parts` is written only where it exists, so the six families that
    # predate it stay byte-identical on disk.
    raw["pii"] = [{k: v for k, v in asdict(p).items() if not (k == "parts" and v is None)} for p in case.pii]
    raw["negatives"] = [asdict(n) for n in case.negatives]
    raw["expected_call"] = {
        "name": case.expected_call.name,
        "pii_params": list(case.expected_call.pii_params),
        "plain_params": dict(case.expected_call.plain_params),
    }
    return raw


def from_dict(raw: dict[str, object]) -> Case:
    call = raw["expected_call"]
    assert isinstance(call, dict)
    source = raw["source"]
    assert isinstance(source, dict)
    pii = raw["pii"]
    negatives = raw["negatives"]
    assert isinstance(pii, list) and isinstance(negatives, list)
    return Case(
        id=str(raw["id"]),
        version=str(raw["version"]),
        family=str(raw["family"]),
        register=str(raw["register"]),
        subcase=None if raw.get("subcase") is None else str(raw["subcase"]),
        messages=tuple(dict(m) for m in raw["messages"]),  # type: ignore[union-attr]
        tools=tuple(dict(t) for t in raw["tools"]),  # type: ignore[union-attr]
        expected_call=ExpectedCall(
            name=str(call["name"]),
            pii_params=tuple(str(p) for p in call["pii_params"]),
            plain_params={str(k): str(v) for k, v in dict(call["plain_params"]).items()},
        ),
        pii=tuple(PiiItem(**p) for p in pii),
        negatives=tuple(Negative(**n) for n in negatives),
        hard=None if raw.get("hard") is None else {str(k): str(v) for k, v in dict(raw["hard"]).items()},  # type: ignore[arg-type]
        created_at=str(raw["created_at"]),
        source=Source(generator=str(source["generator"]), version=str(source["version"]),
                      seed=None if source.get("seed") is None else int(source["seed"])),  # type: ignore[arg-type]
        canary=str(raw["canary"]),
        license=str(raw["license"]),
    )


def dump(case: Case, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(case), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def load(path: Path) -> Case:
    return from_dict(json.loads(path.read_text(encoding="utf-8")))


def load_dir(root: Path) -> list[Case]:
    """Every case under `root`, sorted by path so two runs see one order."""
    return [load(p) for p in sorted(root.rglob("*.json"))]


# --- validation that a JSON schema cannot express --------------------------

def validate(case: Case) -> list[str]:
    """Return the list of defects; empty means the case is sound.

    Every check here is one that let a wrong corpus score once: an offset
    that drifted after post-processing, a negative that was never there, an
    expected parameter no item feeds.
    """
    problems: list[str] = []
    user_turns = {i for i, m in enumerate(case.messages) if m.get("role") == "user"}
    for item in case.pii:
        if item.turn not in user_turns:
            problems.append(f"{item.id}: turn {item.turn} is not a user message")
            continue
        text = case.messages[item.turn]["content"]
        if text[item.start:item.end] != item.value:
            problems.append(f"{item.id}: offsets [{item.start}:{item.end}] give {text[item.start:item.end]!r}, not {item.value!r}")
        if item.type not in TYPES:
            problems.append(f"{item.id}: unknown type {item.type}")
        if item.type == "NAME" and item.tier not in NAME_TIERS:
            problems.append(f"{item.id}: NAME without a tier")
        if item.type != "NAME" and item.tier is not None:
            problems.append(f"{item.id}: tier on a non-name")
    for neg in case.negatives:
        if neg.turn not in user_turns:
            problems.append(f"negative {neg.value!r}: turn {neg.turn} is not a user message")
            continue
        text = case.messages[neg.turn]["content"]
        if text[neg.start:neg.end] != neg.value:
            problems.append(f"negative {neg.value!r}: offsets do not match")
        if neg.kind not in NEGATIVE_KINDS:
            problems.append(f"negative {neg.value!r}: unknown kind {neg.kind}")
    if not case.negatives:
        problems.append("no negatives — over-masking would be unmeasurable")
    spans = [(p.turn, p.start, p.end, p.id) for p in case.pii] + [(n.turn, n.start, n.end, n.value) for n in case.negatives]
    spans.sort()
    for (t1, s1, e1, a), (t2, s2, e2, b) in zip(spans, spans[1:]):
        if t1 == t2 and s2 < e1:
            problems.append(f"spans overlap: {a!r} and {b!r}")
    tool_names = {str(t["function"]["name"]) for t in case.tools if isinstance(t.get("function"), dict)}  # type: ignore[index]
    if case.expected_call.name not in tool_names:
        problems.append(f"expected tool {case.expected_call.name} is not offered")
    fed = {p.tool_param for p in case.pii if p.tool_param}
    for p in case.pii:
        if p.parts:
            fed |= set(p.parts)
    for param in case.expected_call.pii_params:
        if param not in fed:
            problems.append(f"pii_param {param} is fed by no item")
    if case.family not in FAMILIES:
        problems.append(f"unknown family {case.family}")
    if case.register not in REGISTERS:
        problems.append(f"unknown register {case.register}")
    if case.subcase is not None and case.subcase not in SUBCASES:
        problems.append(f"unknown subcase {case.subcase}")
    if case.canary != CANARY:
        problems.append("canary missing or altered")
    if case.license != DATA_LICENSE:
        problems.append(f"license is {case.license}, not {DATA_LICENSE}")
    return problems
