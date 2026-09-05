"""AgentPII-RU v4 — the case format, and every rule a scorer needs. NORMATIVE.

THERE IS NO EXPECTED CALL. v3 scored the agent against an argument dict a human
wrote, and a human's notion of the right string («Гусева, 81, кв. 117») is a
convention, not a truth — the effect on the customer's system is the truth. v4
carries what the generator BUILT (items with typed parts and writer-derived
offsets), the backend's seed, and which tools are offered; the reference is the
CONTROL ARM, run by the harness, never written here.

Reused from v3 (imported, not copied): `Message`, `Provenance`, `Source`,
`Negative`, the register gate `_register_problems`, `audit_unlabelled`,
`same_value` / `_address_parts` / `classify_break`, `span_verdict`, `Ladder`,
`tier`, `corpus_digest`, `TERMINATIONS`. Two rule sets that had to stay equal
would be one rule set and a drift waiting to happen.
"""
import random
import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

from bench.agentpii3 import schema as v3
from bench.agentpii3.schema import (  # noqa: F401 - re-exported on purpose
    EXCLUDED_TERMINATIONS, LICENCES, SHIPPABLE_LICENCES, TERMINATIONS,
    Message, Negative, Provenance, Source, message_text)
from bench.agentpii4.tools import REGISTRY

REGISTERS: tuple[str, ...] = v3.REGISTERS
SPEECH_REGISTERS: tuple[str, ...] = tuple(v3.SPEECH_REGISTERS)
TYPES: tuple[str, ...] = v3.TYPES
MAX_CLEAN_SHARE: float = v3.MAX_CLEAN_SHARE
MIN_SPEECH_SHARE: float = v3.MIN_SPEECH_SHARE

SCENARIO_KINDS: tuple[str, ...] = (
    "chain",        # lookup by PII -> result with PII -> decomposition -> free text
    "result_feed",  # PII from a tool RESULT feeds a later call; derive from it
    "correction",   # the customer corrects a value; the second one is current
    "validate",     # the system prompt demands a checksum before calling
    "compare",      # three real records come back; the agent chooses one
    "summary",      # the final reply must carry real values
    "container",    # PII inside a URL / CSV string argument
    "derive",       # age, gender, initials, translit, postcode, timezone
    "decompose",    # series/number, last/first/middle, street/house/flat
    # Added 05.09 from research/2026-09-05-agent-scenario-coverage.md. The nine
    # above share one axis — what the agent does to a VALUE — and it is nearly
    # exhausted. What follows asks where the value COMES FROM and where it GOES.
    "lookup_list",  # a search returns OTHER people's records; one is chosen
    "crm_note",     # the model WRITES the PII itself, in prose, into a CRM field
    "send_template",  # PII goes into a template VARIABLE; the placeholder must survive
    "receipt",      # the contact is a CONDITION of the sale, not an accuracy question
)
ARMS: tuple[str, ...] = ("C", "I", "C2")          # control, intervention, second control
INV_LEVELS: tuple[str, ...] = ("tools", "keys", "state")
DUTIES: tuple[str, ...] = ("required", "optional")
# 05.09: raised from 420 with the flow axis (research/2026-09-05-agent-scenario-
# coverage.md). The band is a sanity check on authoring effort, not a statistical
# constraint — the tiers are what bound the money, and `small` is still the pilot.
CORPUS_SIZE_BAND: tuple[int, int] = (330, 520)
TIER_SIZES: dict[str, int] = {"nano": 30, "small": 120, "medium": 0}
MIN_CLUSTER_MULTI: int = 8         # clusters of size >= 3, so ICC is measured, not assumed
MIN_FIND_DISTINCT_CASES: int = 12  # cases where text.find(value) != start — see validate.py
MIN_TYPE_DENOMINATOR: int = v3.MIN_TYPE_DENOMINATOR
TIER_ZERO_FAILURE_BOUND = v3.TIER_ZERO_FAILURE_BOUND


class InvalidCase(ValueError):
    pass


class InvalidCorpus(ValueError):
    pass


@dataclass(frozen=True)
class Locus:
    """Where a value lives: in a message, or in a seed record of the backend."""

    kind: str          # "message" | "seed"
    msg: int           # message index; -1 for a seed
    start: int
    end: int
    record: str        # seed record id when kind == "seed"
    path: str          # field path inside the seed record


@dataclass(frozen=True)
class PiiItem:
    """One personal datum as BUILT: surface, canonical, typed parts, and where."""

    id: str
    type: str
    identity: str       # one identity is one substitute
    value: str          # surface as written or said
    canonical: str      # what a CRM stores: +7…, dd.mm.yyyy, «series number» — for a
                        # SPOKEN identifier too, because that is what the engine restores
                        # on the tool leg and what the control arm writes. Names and
                        # addresses keep v3's rule: canonical of WHAT WAS WRITTEN.
    parts: dict[str, str]
    where: Locus
    duty: str           # "required" | "optional"
    spoken: bool
    stale: bool         # the superseded value in a `correction` case


@dataclass(frozen=True)
class PlainValue:
    """Not personal data, must reach the tool byte-identical (order no, БИК, code)."""

    value: str
    where: Locus
    family: str
    why: str


@dataclass(frozen=True)
class SeedRecord:
    id: str
    table: str                       # "contacts" | "addresses"
    fields: dict[str, object]
    pii_ids: tuple[str, ...]


@dataclass(frozen=True)
class Expectation:
    """NOT an expected call. Only what the scenario makes reachable."""

    reachable_tools: tuple[str, ...]
    primary_identity: str
    must_contain: tuple[str, ...]      # `summary` only
    must_not_contain: tuple[str, ...]  # values of OTHER identities
    validate_types: tuple[str, ...]    # `validate` only


@dataclass(frozen=True)
class TraceRow:
    msg: int
    key: str
    start: int
    end: int
    origin: str


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    register: str
    provenance: Provenance
    cluster: str                    # "<TYPE>:<canonical key>" of the primary item
    conversation_id: str            # "" = the harness derives it
    now: str                        # ISO date the system prompt fixes as today
    messages: tuple[Message, ...]   # system + user turns ONLY
    tools: tuple[str, ...]          # names into tools.REGISTRY
    seed_records: tuple[SeedRecord, ...]
    pii: tuple[PiiItem, ...]
    plain: tuple[PlainValue, ...]
    negatives: tuple[Negative, ...]
    expects: Expectation
    trace: tuple[TraceRow, ...]
    note: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


# --- validation -------------------------------------------------------------

def validate(case: Case) -> list[str]:
    """Every problem, never the first one only."""
    problems: list[str] = []
    tag = case.id
    if case.kind not in SCENARIO_KINDS:
        problems.append(f"{tag}: unknown kind {case.kind!r}")
    if case.register not in REGISTERS:
        problems.append(f"{tag}: unknown register {case.register!r}")
    if not case.cluster or not case.note:
        problems.append(f"{tag}: cluster and note are required")
    if not case.messages or case.messages[0].role != "system":
        problems.append(f"{tag}: first message must be the system prompt")
    if any(message.role not in ("system", "user") for message in case.messages):
        problems.append(f"{tag}: only system and user messages may be scripted; "
                        f"assistant and tool turns are produced by the run")
    for name in case.tools:
        if name not in REGISTRY:
            problems.append(f"{tag}: tool {name!r} is not in the registry")
    for name in case.expects.reachable_tools:
        if name not in case.tools:
            problems.append(f"{tag}: reachable tool {name!r} is not offered")
    if not case.expects.reachable_tools:
        problems.append(f"{tag}: a case must make at least one tool reachable")

    seen_spans: dict[int, list[tuple[int, int, str]]] = {}
    seeds = {record.id: record for record in case.seed_records}
    identities: dict[str, set[str]] = {}
    for item in case.pii:
        if item.type not in TYPES:
            problems.append(f"{tag}: item {item.id} has unknown type {item.type!r}")
        if item.duty not in DUTIES:
            problems.append(f"{tag}: item {item.id} has unknown duty {item.duty!r}")
        identities.setdefault(item.identity, set()).add(item.type)
        if item.where.kind == "message":
            index = item.where.msg
            if not 0 <= index < len(case.messages):
                problems.append(f"{tag}: item {item.id} points at message {index}")
                continue
            text = message_text(case, index)
            if text[item.where.start:item.where.end] != item.value:
                problems.append(
                    f"{tag}: item {item.id} offsets [{item.where.start}:{item.where.end}] "
                    f"read {text[item.where.start:item.where.end]!r}, not {item.value!r}")
            if case.messages[index].role == "system":
                problems.append(f"{tag}: item {item.id} sits in the system prompt")
            for start, end, other in seen_spans.get(index, []):
                if start < item.where.end and item.where.start < end:
                    problems.append(f"{tag}: items {item.id} and {other} overlap")
            seen_spans.setdefault(index, []).append((item.where.start, item.where.end, item.id))
        elif item.where.kind == "seed":
            record = seeds.get(item.where.record)
            if record is None:
                problems.append(f"{tag}: item {item.id} points at seed {item.where.record!r}")
            else:
                stored = _seed_field(record.fields, item.where.path)
                if str(stored) != item.value:
                    problems.append(f"{tag}: item {item.id} seed field {item.where.path} "
                                    f"holds {stored!r}, not {item.value!r}")
        else:
            problems.append(f"{tag}: item {item.id} has unknown locus {item.where.kind!r}")
        if item.spoken and any(ch.isdigit() for ch in item.value):
            problems.append(f"{tag}: item {item.id} is spoken yet carries a digit")
        if not item.parts:
            problems.append(f"{tag}: item {item.id} carries no parts — ground truth must be built, not searched")

    stale = [item for item in case.pii if item.stale]
    if case.kind == "correction":
        current = [item for item in case.pii if not item.stale
                   and any(s.identity == item.identity for s in stale)]
        if not stale or not current:
            problems.append(f"{tag}: a correction case needs a stale and a current item of one identity")
        for old in stale:
            newer = [c for c in current if c.identity == old.identity]
            if newer and old.where.kind == "message" and newer[0].where.kind == "message":
                if (newer[0].where.msg, newer[0].where.start) <= (old.where.msg, old.where.start):
                    problems.append(f"{tag}: the current value must come after the stale one")
    elif stale:
        problems.append(f"{tag}: stale items outside a correction case")

    for plain in case.plain:
        if plain.where.kind == "message":
            text = message_text(case, plain.where.msg)
            if text[plain.where.start:plain.where.end] != plain.value:
                problems.append(f"{tag}: plain value {plain.value!r} offsets do not index it")
    for negative in case.negatives:
        if not 0 <= negative.msg < len(case.messages):
            problems.append(f"{tag}: negative points at message {negative.msg}")
            continue
        text = message_text(case, negative.msg)
        if text[negative.start:negative.end] != negative.value:
            problems.append(f"{tag}: negative {negative.value!r} offsets do not index it")
        if negative.family not in v3.NEGATIVE_FAMILIES:
            problems.append(f"{tag}: negative family {negative.family!r} unknown")

    # THE TRACE IS THE PROOF THE MESSAGE WAS BUILT, NOT SEARCHED. Every message
    # must be reproducible from its trace rows, and every claimed span must be
    # one of them.
    by_msg: dict[int, list[TraceRow]] = {}
    for row in case.trace:
        by_msg.setdefault(row.msg, []).append(row)
    for index, message in enumerate(case.messages):
        if message.role != "user":
            continue
        rows = sorted(by_msg.get(index, []), key=lambda row: row.start)
        text = message_text(case, index)
        cursor = 0
        for row in rows:
            if row.start != cursor:
                problems.append(f"{tag}: message {index} trace has a gap at {cursor}")
                break
            cursor = row.end
        if rows and cursor != len(text):
            problems.append(f"{tag}: message {index} trace ends at {cursor}, text is {len(text)}")
        if not rows:
            problems.append(f"{tag}: message {index} has no trace")
    keyed = {(row.msg, row.start, row.end) for row in case.trace if row.key}
    for item in case.pii:
        if item.where.kind == "message" and (item.where.msg, item.where.start, item.where.end) not in keyed:
            problems.append(f"{tag}: item {item.id} span is not a keyed trace row")
    for plain in case.plain:
        if plain.where.kind == "message" and (plain.where.msg, plain.where.start, plain.where.end) not in keyed:
            problems.append(f"{tag}: plain value {plain.value!r} span is not a keyed trace row")

    # Every DERIVED field of an offered tool needs a source the case carries.
    present_types = {item.type for item in case.pii}
    for name in case.expects.reachable_tools:
        for spec in REGISTRY.get(name, REGISTRY["notify_sms"]).fields:
            if spec.kind == "derived" and spec.source_type not in present_types:
                problems.append(f"{tag}: {name}.{spec.path} derives from {spec.source_type}, "
                                f"which the case does not carry")
    for kind_ in case.expects.validate_types:
        if kind_ not in present_types:
            problems.append(f"{tag}: validate_types names {kind_}, absent from the case")
    if case.kind == "summary" and not case.expects.must_contain:
        problems.append(f"{tag}: a summary case must name what the reply carries")
    primary_values = {item.value for item in case.pii if item.identity == case.expects.primary_identity}
    if set(case.expects.must_not_contain) & primary_values:
        problems.append(f"{tag}: must_not_contain names the primary identity's own value")
    if not any(item.duty == "required" for item in case.pii) and not case.negatives and not case.plain:
        problems.append(f"{tag}: a null agent passes this case")

    view = v3_view(case)
    problems.extend(v3._register_problems(view))  # type: ignore[arg-type]
    problems.extend(v3.audit_unlabelled(view))     # type: ignore[arg-type]
    return problems


def v3_view(case: Case) -> object:
    """A v3-shaped read-only view: v3's register gate and unlabelled-shape audit
    read `item.msg/start/end`, and a PLAIN value (an order number in digits) is
    PII-shaped and must count as claimed, or the audit reports the corpus's own
    negatives as leaks."""
    from types import SimpleNamespace
    claimed = [SimpleNamespace(msg=item.where.msg, start=item.where.start, end=item.where.end)
               for item in case.pii if item.where.kind == "message"]
    claimed += [SimpleNamespace(msg=plain.where.msg, start=plain.where.start, end=plain.where.end)
                for plain in case.plain if plain.where.kind == "message"]
    return SimpleNamespace(id=case.id, register=case.register, messages=case.messages,
                           pii=claimed, negatives=case.negatives)


def _seed_field(fields: dict[str, object], path: str) -> object:
    node: object = fields
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def validate_corpus(cases: Sequence[Case]) -> list[str]:
    problems: list[str] = []
    ids = [case.id for case in cases]
    if len(set(ids)) != len(ids):
        problems.append("duplicate case ids")
    low, high = CORPUS_SIZE_BAND
    if not low <= len(cases) <= high:
        problems.append(f"corpus has {len(cases)} cases, band is {CORPUS_SIZE_BAND}")
    total = max(1, len(cases))
    speech = sum(1 for case in cases if case.register in SPEECH_REGISTERS) / total
    clean = sum(1 for case in cases if case.register == "clean") / total
    if speech < MIN_SPEECH_SHARE:
        problems.append(f"speech share {speech:.0%} below {MIN_SPEECH_SHARE:.0%}")
    if clean > MAX_CLEAN_SHARE + 1e-9:
        problems.append(f"clean share {clean:.0%} above {MAX_CLEAN_SHARE:.0%}")
    for kind in SCENARIO_KINDS:
        if not any(case.kind == kind for case in cases):
            problems.append(f"kind {kind!r} absent")
    tool_use: dict[str, int] = {}
    for case in cases:
        for name in case.expects.reachable_tools:
            tool_use[name] = tool_use.get(name, 0) + 1
    for name in REGISTRY:
        if tool_use.get(name, 0) < MIN_TYPE_DENOMINATOR:
            problems.append(f"tool {name!r} reachable in {tool_use.get(name, 0)} cases, "
                            f"below {MIN_TYPE_DENOMINATOR}")
    clusters: dict[str, int] = {}
    for case in cases:
        clusters[case.cluster] = clusters.get(case.cluster, 0) + 1
    multi = sum(1 for size in clusters.values() if size >= 3)
    if multi < MIN_CLUSTER_MULTI:
        problems.append(f"{multi} clusters of size >= 3, need {MIN_CLUSTER_MULTI} to measure ICC")
    explicit = sum(1 for case in cases if case.conversation_id)
    if explicit == 0 or explicit == len(cases):
        problems.append("both explicit and derived conversation ids must occur")
    return problems


# --- serialisation -----------------------------------------------------------

def case_from_json(raw: dict[str, object]) -> Case:
    messages = tuple(Message(role=str(m["role"]), content=str(m["content"]),
                             source=(Source(**m["source"]) if m.get("source") else None),
                             name=str(m.get("name", "")))
                     for m in raw["messages"])  # type: ignore[index]
    pii = tuple(PiiItem(id=str(p["id"]), type=str(p["type"]), identity=str(p["identity"]),
                        value=str(p["value"]), canonical=str(p["canonical"]),
                        parts=dict(p["parts"]), where=Locus(**p["where"]),
                        duty=str(p["duty"]), spoken=bool(p["spoken"]), stale=bool(p["stale"]))
                for p in raw["pii"])  # type: ignore[index]
    plain = tuple(PlainValue(value=str(p["value"]), where=Locus(**p["where"]),
                             family=str(p["family"]), why=str(p["why"]))
                  for p in raw["plain"])  # type: ignore[index]
    negatives = tuple(Negative(**n) for n in raw["negatives"])  # type: ignore[index]
    seeds = tuple(SeedRecord(id=str(s["id"]), table=str(s["table"]), fields=dict(s["fields"]),
                             pii_ids=tuple(s["pii_ids"]))
                  for s in raw["seed_records"])  # type: ignore[index]
    expects = raw["expects"]  # type: ignore[index]
    return Case(
        id=str(raw["id"]), kind=str(raw["kind"]), register=str(raw["register"]),
        provenance=Provenance(**raw["provenance"]),  # type: ignore[arg-type]
        cluster=str(raw["cluster"]), conversation_id=str(raw["conversation_id"]),
        now=str(raw["now"]), messages=messages, tools=tuple(raw["tools"]),  # type: ignore[arg-type]
        seed_records=seeds, pii=pii, plain=plain, negatives=negatives,
        expects=Expectation(reachable_tools=tuple(expects["reachable_tools"]),  # type: ignore[index]
                            primary_identity=str(expects["primary_identity"]),  # type: ignore[index]
                            must_contain=tuple(expects["must_contain"]),  # type: ignore[index]
                            must_not_contain=tuple(expects["must_not_contain"]),  # type: ignore[index]
                            validate_types=tuple(expects["validate_types"])),  # type: ignore[index]
        trace=tuple(TraceRow(**t) for t in raw["trace"]),  # type: ignore[index]
        note=str(raw["note"]))


def corpus_digest(cases: Sequence[Case]) -> str:
    """Order- and claim-sensitive; message text included (nothing here is
    carried by reference — v4 cases are authored)."""
    digest = hashlib.sha256()
    for case in cases:
        digest.update(json.dumps(case.to_json(), ensure_ascii=False, sort_keys=True).encode())
        digest.update(b"\x00")
    return digest.hexdigest()


@dataclass(frozen=True)
class Ladder:
    version: int
    seed: int
    corpus_sha256: str
    tiers: dict[str, tuple[str, ...]] = field(default_factory=dict)


def sample(cases: Sequence[Case], count: int, seed: int) -> list[Case]:
    """A seeded random sample of the corpus, STRATIFIED by family.

    The ladder's tiers are frozen lists, and a frozen list is what gets
    debugged case by case: every fix of this week was read off `small`, so
    `small` can no longer tell whether the engine improved or the fixes did.
    A sample drawn from a seed nobody has looked at is the answer, and it is
    stratified so a 60-case draw still carries every family — a uniform draw
    of that size drops `container` (30 of 360) one time in five.

    Reproducible by (corpus digest, count, seed); the ids ride in the run's
    meta so a replay never has to redraw.
    """
    if count <= 0 or count > len(cases):
        raise InvalidCorpus(f"sample of {count} from a corpus of {len(cases)}")
    rng = random.Random(f"v4-sample:{corpus_digest(cases)}:{count}:{seed}")
    by_kind: dict[str, list[Case]] = {}
    for case in cases:
        by_kind.setdefault(case.kind, []).append(case)
    # Largest-remainder apportionment, so the shares add up to `count` exactly.
    shares = {kind: count * len(group) / len(cases) for kind, group in by_kind.items()}
    quota = {kind: int(share) for kind, share in shares.items()}
    for kind in sorted(shares, key=lambda k: shares[k] - quota[k], reverse=True)[: count - sum(quota.values())]:
        quota[kind] += 1
    chosen: list[Case] = []
    for kind in sorted(by_kind):
        chosen.extend(rng.sample(by_kind[kind], quota[kind]))
    return sorted(chosen, key=lambda case: case.id)


def tier(cases: Sequence[Case], ladder: Ladder, name: str) -> list[Case]:
    if name not in TIER_SIZES:
        raise InvalidCorpus(f"unknown tier {name!r}")
    actual = corpus_digest(cases)
    if actual != ladder.corpus_sha256:
        raise InvalidCorpus(
            f"ladder v{ladder.version} was frozen against corpus {ladder.corpus_sha256[:12]}, "
            f"this corpus is {actual[:12]}; regenerate the ladder deliberately")
    if name not in ladder.tiers:
        raise InvalidCorpus(f"ladder has no tier {name!r}")
    by_id = {case.id: case for case in cases}
    return [by_id[case_id] for case_id in ladder.tiers[name]]
