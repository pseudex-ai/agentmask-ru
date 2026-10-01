"""AgentPII-RU v5 — THE CONTRACTS. Normative for every component; interfaces only.

Six component agents build in parallel against this file: `tools`, `comparator`,
`metrics`, `generator_a`, `generator_b`, `judge` (see `briefs/`). Nothing here
is an implementation. A dataclass is a shape, a `Protocol` is a signature, a
tuple of strings is a closed vocabulary, and a docstring says what the value
MEANS and which alternative was rejected. When two components disagree about a
shape, this file wins; when this file is silent, `docs/tz-agentpii5.md` wins;
when the spec is silent, the interpretation that keeps the instrument ABLE TO
FAIL wins (`CLAUDE.md`, «an instrument that cannot fail is not an instrument»).

WHAT IS REUSED FROM v4, BY IMPORT, NEVER BY COPY. `Case`, `PiiItem`, `Locus`,
`SeedRecord`, `Expectation`, `ToolSpec`, `FieldSpec`, `Refusal`, `REGISTRY`,
`ArmRun`, `ObservedCall`, `LevelVerdict`, the six paired `LEVELS`, `DELTA`,
`clopper_pearson`, `zero_failure_floor`, `TIER_SIZES`. Two definitions that had
to stay equal would be one definition and a drift waiting to happen — the rule
v4 learned from v3. `bench/agentpii4/` is NOT modified: it is the baseline the
mandatory v4-vs-v5 comparison (§7 of this file) runs against, and a baseline
that moved with the treatment measures nothing.

WHAT MAY IMPORT `pseudex`. Only the live glue (`bench/agentpii5/harness.py`,
owned by the judge component) — it must, because the gateway arm IS the
production path. `contracts.py`, `form.py`, `metrics.py`, `observe.py`,
`fixtures.py`, `report.py`, `tools.py`, `mock.py`, `schema.py`, every scenario
and every fixture: NEVER. An instrument that imports the engine cannot fail the
engine; `test_contracts.py` asserts it for this file, and each component's
own test asserts it for its files (`FORBIDDEN_IMPORT_PREFIX`).

Sections follow the task order: §1 hops, §2 case, §3 tools, §4 form
comparator, §5 metrics, §6 judge, §7 comparison with v4, §8 run layout.
"""
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from bench.agentpii4 import report as v4_report
from bench.agentpii4 import schema as v4
from bench.agentpii4.compare import (  # noqa: F401 - re-exported on purpose
    ArmRun, LevelVerdict, ObservedCall, PairVerdict, Triple)
from bench.agentpii4.schema import (  # noqa: F401 - re-exported on purpose
    Case, Expectation, Locus, Message, Negative, PiiItem, PlainValue, Provenance,
    SeedRecord, TraceRow)
from bench.agentpii4.stats import clopper_pearson, zero_failure_floor
from bench.agentpii4.tools import REGISTRY, FieldSpec, Refusal, ToolSpec  # noqa: F401

from bench.agentpii5 import contracts_v6
from bench.agentpii5 import pii_types

# --- §0 package rules ------------------------------------------------------------

V4_PACKAGE: str = "bench.agentpii4"
V5_PACKAGE: str = "bench.agentpii5"
# The prefix no pure module of this package may import, at any depth, lazily or
# not. `test_contracts.py` checks `sys.modules` after importing this file; each
# component's test does the same for its own modules.
FORBIDDEN_IMPORT_PREFIX: str = "pseudex"
# The two modules allowed to import the engine: `harness` runs the gateway arm
# on the production path, and `regress_print` prints the SAME path offline
# (bundle + GatewayV5 + mock, no model) for G4/L9. Everything each learns is
# written to the run files (§8) or printed, so every other module reads records,
# never the engine.
PSEUDEX_ALLOWED_MODULES: tuple[str, ...] = ("bench.agentpii5.harness",
                                            "bench.agentpii5.regress_print")
# Never published. The public harness lives in `public/agentmask-ru/`; this
# package shares no file with it and writes nothing under `public/`.
PUBLISHED: bool = False

TYPES: tuple[str, ...] = v4.TYPES + pii_types.NEW_ITEM_TYPES
# Re-exported so `schema.R02` and the orchestrator's `reg_types` read the same
# set from the one home (pii_types), never a copy.
NEW_ITEM_TYPES: tuple[str, ...] = pii_types.NEW_ITEM_TYPES
# The v6 tables, re-exported from their home (contracts_v6) — one definition,
# never a copy. `INDUSTRIES`/`V6_AXES`/`V6_PROVENANCE_KINDS`/`V6_DIR` are the
# axis vocabulary, `CaseV6Meta`/`ProcedureRecord` the shapes a v6 case carries.
INDUSTRIES: tuple[str, ...] = contracts_v6.INDUSTRIES
V6_AXES: tuple[str, ...] = contracts_v6.V6_AXES
V6_PROVENANCE_KINDS: tuple[str, ...] = contracts_v6.V6_PROVENANCE_KINDS
V6_DIR: str = contracts_v6.V6_DIR
CaseV6Meta = contracts_v6.CaseV6Meta
ProcedureRecord = contracts_v6.ProcedureRecord
# The v6 negative families (§1.6 of tz-agentpii6-registry.md). R02 admits a
# v4.validate «negative family … unknown» line for exactly these; the list
# lives in `contracts_v6.py`.
V6_NEGATIVE_FAMILIES: tuple[str, ...] = contracts_v6.V6_NEGATIVE_FAMILIES
REGISTERS: tuple[str, ...] = v4.REGISTERS
SPEECH_REGISTERS: tuple[str, ...] = v4.SPEECH_REGISTERS
V4_SCENARIO_KINDS: tuple[str, ...] = v4.SCENARIO_KINDS
TIER_SIZES: dict[str, int] = v4.TIER_SIZES
HOLDOUT_SHARE: float = v4.HOLDOUT_SHARE
MIN_CLUSTER_MULTI: int = v4.MIN_CLUSTER_MULTI
MIN_TYPE_DENOMINATOR: int = v4.MIN_TYPE_DENOMINATOR
V4_LEVELS: tuple[tuple[str, str], ...] = v4_report.LEVELS
DELTA: float = v4_report.DELTA


# --- §1 the hop model (spec §1) ----------------------------------------------------

HOP_KINDS: tuple[str, ...] = ("IN", "OUT")
# Sources whose FORM the substitute must mirror on the way in.
IN_OWNERS: tuple[str, ...] = ("user", "tool", "document", "memory")
# Consumers whose FORM — the agent's, read off its own output — the real value
# must take on the way out.
OUT_OWNERS: tuple[str, ...] = ("tool_arg", "answer", "template", "summary")
HOP_OWNERS: tuple[str, ...] = IN_OWNERS + OUT_OWNERS
# The OUT owners that are an ACT of the agent on a tool — what «B» means in an
# A→B chain. The answer is an OUT hop too, and it is not a tool: 3 870 of the
# corpus's 6 880 declared `source_hop` transitions end in the answer, so a
# chain line that accepted them would be 56% a line about prose. Declared here
# rather than in `schema.py` because BOTH the corpus rules and `metrics.
# _transitions` decide by it, and two copies of one tuple is one drift away
# from the corpus and the metric disagreeing about what a chain is.
ACTING_OUT_OWNERS: tuple[str, ...] = ("tool_arg", "template", "summary")
# The minimal loop every case with a tool result carries, in this order. A case
# that declares fewer hops than this and claims a result is invalid
# (`V5_CASE_RULES`). Chains and multi-call turns LENGTHEN it, never shorten it.
MINIMAL_LOOP: tuple[tuple[str, str], ...] = (
    ("IN", "user"), ("OUT", "tool_arg"), ("IN", "tool"), ("OUT", "answer"))
MIN_HOPS_WITH_RESULT: int = len(MINIMAL_LOOP)
# A value carried by SEVERAL leaves of one argument object (street / house /
# flat as separate fields) is one hop; the observer joins the leaves with this
# separator, in the tool's field order, so the comparator can read `by_fields`
# off the string. U+001F never occurs in a customer's text or a mock's result;
# a comma would, and would collide with the `commas` feature.
FIELD_SEP: str = "\x1f"
# Which OUT owner a tool-argument leaf belongs to. A leaf of a template tool is
# a TEMPLATE hop (the agent fills a slot of a message a human will read); a
# free-text leaf of a handover tool is a SUMMARY hop (the agent retells the
# dialogue to another agent or person); every other leaf is a plain tool
# argument. The owner decides which `form_hOUT` line the hop counts in, so the
# table is closed and lives here, not in the observer.
TEMPLATE_FIELDS: tuple[tuple[str, str], ...] = (
    ("send_template", "variables.*"), ("send_template", "text"),
    ("notify_sms", "text"), ("email_send", "body"), ("email_send", "subject"),
    # The office suite's two leaves a PERSON reads. `mail_send.body` is the
    # letter the customer opens and `reminder_set.text` is the notification that
    # reaches their phone; neither is compared for equality, both are judged for
    # form and for leaks, which is what `template` means here.
    ("mail_send", "subject"), ("mail_send", "body"), ("reminder_set", "text"))
SUMMARY_FIELDS: tuple[tuple[str, str], ...] = (
    ("escalate_to_human", "summary"), ("crm_add_note", "text"),
    ("ticket_create", "text"), ("ticket_create", "subject"),
    # The office suite's free-text leaves the agent writes IN ITS OWN WORDS for
    # another worker to read: an issue's summary and description, a card's note,
    # the paragraph appended to a document, the fact put into long-term memory,
    # the agenda of an invitation. A `summary` hop is retelling, not transport,
    # so the value inside it is judged for form and never for equality — which
    # is exactly what the client's «описание, несущее ПД» is.
    ("tracker_issue_create", "summary"), ("tracker_issue_create", "description"),
    ("crm_upsert_card", "deal.note"), ("doc_append", "text"),
    ("memory_save", "fact"), ("calendar_invite", "description"))


@dataclass(frozen=True)
class Hop:
    """One crossing of one personal datum through the gateway, as the case
    DECLARES it. The harness observes crossings (`HopObservation`); the
    comparator judges each; the metrics count them per owner and per type.

    `item_id` is the `PiiItem.id` of the datum. A hop carries ONE datum: a
    tool result with three values is three IN hops with the same `tool_name`
    and `call_ordinal`. Aggregating them would hide which type broke.

    `turn` is the index of the USER message (in `Case.messages`) that opens
    the turn the hop happens in — the harness has no other clock a live agent
    respects. `call_ordinal` is the 0-based ordinal of that tool's calls
    inside the turn: a retry is ordinal 1 of the same tool, a parallel fan-out
    is ordinals 0..N-1 of one or several tools sharing a `parallel_group`.

    `source_hop` is the chain link: the `hop_index` of the IN hop whose value
    this OUT hop carries forward («result of A → argument of B»). -1 for a
    value the user gave. `path` is the dotted leaf inside the tool result
    (IN/tool, from `ToolSpec.result_pii`) or the argument (OUT/tool_arg, from
    `FieldSpec.path`); "" for user, memory, answer.

    `optional` is True only for a hop the agent MAY legitimately skip (a
    retry it did not need because its first attempt was accepted, or a leaf the
    TOOL SCHEMA does not require). An optional hop that did not happen is not
    observed and counts nowhere; a required hop that did not happen is `absent`
    and counts as a miss in `multi_all_out` / `chain_value`. Defaulting
    everything to optional would let an agent that calls nothing pass every form
    line — the v4 D3 defect («did the arm act at all») in a new coat.

    «DID NOT HAPPEN» IS A FACT ABOUT THE LEAF, NOT ABOUT THE CALL (SPIKE-Е,
    Е-2). The observer read `optional` only when the CALL was missing, so a
    declared optional hop whose call WAS made with an empty slot went into every
    denominator — the promise on this field, broken by the branch one file away
    that did not read it (`_out_answer` already obeyed it). A hop is skipped
    when its leaf was left empty, whether or not a call was made.

    AND THE CORPUS'S OWN BUILDERS READ THE ROLE. `scenarios5.common.arg_hop`
    and `revise._arguments` set `optional = (not spec.required) or spec.role in
    GENERIC_PIECE_ROLES`: `courier_book.address.locality` and
    `delivery_create_order.to_location.city` are `required=True, role='city'`,
    and the engine keeps the settlement real by product decision — a REQUIRED
    hop there is a promise no correct gateway can keep.
    """

    kind: str            # HOP_KINDS
    owner: str           # IN → IN_OWNERS, OUT → OUT_OWNERS
    item_id: str         # PiiItem.id
    hop_index: int       # 0-based, strictly increasing inside one case
    turn: int            # index of the opening user message
    tool_name: str       # "" unless owner in ("tool", "tool_arg", "template", "summary", "document")
    call_ordinal: int    # 0-based within the turn; -1 when no tool is involved
    parallel_group: str  # "" or a label shared by OUT hops the agent must emit in ONE assistant turn
    source_hop: int      # hop_index of the IN hop this value comes from; -1 when the user said it
    path: str            # dotted leaf; "" for user / memory / answer
    optional: bool


# --- §2 the case, v5 = v4 Case + behaviour + hops + specs (spec §3, §8.2) ----------

# The taxonomy of agent behaviour a case is built to provoke (spec §3.1–3.5).
BEHAVIOURS: tuple[str, ...] = (
    "single",                  # the base: one call, four hops
    "retry_same_tool",         # an error result with the real value in its text → a second attempt
    "same_tool_other_target",  # find(A), find(B): two identities, no cross-contamination
    "sequential_chain",        # result of A → argument of B (→ C); the answer covers all
    "parallel",                # N calls in ONE assistant turn; N OUT at once
    "fanout_pick",             # a list comes back; the agent matches BY VALUE and acts on one
    "branching",               # found → update / not found → create
    "user_in_loop",            # find → show → the user confirms → act on the confirmed value
    "memory_anaphora",         # a value from turn 1 used at turn 7; «ему», «на тот адрес»
    "rag",                     # query with PII → k chunks with PII, some of OTHER people
    "document",                # the agent reads a file (CSV / form / free text / scan) and extracts
)

# The v4 `Case.kind` a v5 family stamps on `base`: v4's `validate` refuses any
# kind outside `v4.SCENARIO_KINDS`, so a behaviour name in `kind` fails R02 on
# every case. The id and the random stream still carry the behaviour. Normative
# here (ruling 2026-09-22); `scenarios5/common.py` imports it.
V4_KIND_FOR_BEHAVIOUR: dict[str, str] = {
    "single": "result_feed",                 # a result feeds the answer: the base loop
    "retry_same_tool": "normalize",          # the service refuses the form, the agent rewrites it
    "same_tool_other_target": "compare",     # two real records, told apart
    "sequential_chain": "chain",             # lookup -> result -> next call
    "parallel": "analytics",                 # several people addressed in one move
    "fanout_pick": "lookup_list",            # a list of other people's records, one chosen
    "branching": "prompt_rule",              # a rule in the prompt decides the call
    "user_in_loop": "long_clinic",           # find, show, confirm, act
    "memory_anaphora": "long_support",       # a long dialogue retold at the end
    "rag": "search_rank",                    # top-k from a directory
    "document": "container",                 # personal data inside a file payload
}
GENERATOR_A_BEHAVIOURS: tuple[str, ...] = (
    "single", "retry_same_tool", "same_tool_other_target", "sequential_chain", "parallel",
    "fanout_pick", "branching")
GENERATOR_B_BEHAVIOURS: tuple[str, ...] = ("user_in_loop", "memory_anaphora", "rag", "document")
# `single` IS generated anew (R-50), and the constant says so now. The revised
# v4 corpus supplies the family's COUNT — §8.2's row «одиночный вызов» = 180
# and v4 carries far more one-call cases than that — but not its SHAPE: 379 of
# its 463 revised cases are v4's two-hop lookup, with no seeded record to read
# back, so the four-hop base loop is authored a hundred times in
# `scenarios5/single.py` and `build.py --check` prints authored / revised /
# two-hop apart so the share is read for what it is.
# What a v4 family becomes when revised (spec §3.6, §8.2 «остальные — ревизию»).
# The revision keeps the case's messages and items byte-identical and ADDS the
# behaviour and the hops; generator_b may refine one case's behaviour by hand
# when the messages make another one obvious, and must keep the default
# otherwise — a mapping applied by taste would make the behaviour shares a
# choice instead of a measurement.
V4_KIND_TO_BEHAVIOUR: dict[str, str] = {
    "chain": "sequential_chain", "result_feed": "sequential_chain", "correction": "single",
    "validate": "single", "compare": "fanout_pick", "summary": "single", "container": "single",
    "derive": "single", "decompose": "single", "lookup_list": "fanout_pick", "crm_note": "single",
    "send_template": "single", "receipt": "single", "analytics": "single",
    "long_order": "sequential_chain", "search_rank": "fanout_pick", "prompt_rule": "branching",
    "tool_chain": "sequential_chain", "normalize": "sequential_chain",
    "long_clinic": "user_in_loop", "long_bank": "sequential_chain", "long_support": "sequential_chain",
}
DOCUMENT_FORMATS: tuple[str, ...] = ("csv", "free_text", "form", "scan")
ANAPHORA_KINDS: tuple[str, ...] = ("none", "pronoun", "same_address", "same_phone", "same_person")

# Corpus targets (spec §8.2). Shares are of the WHOLE corpus; `SHARE_TOLERANCE`
# is the band `validate_corpus_v5` accepts around each — the spec writes «≈»,
# and a band of zero would refuse every real build while a band of ten points
# would let a family vanish. Three points is where a 120-case family can still
# be missed by at most a third of its MDE budget.
# Spec §8.2 says «≈ 1 200–1 500»; the kept 834 revised cases plus the table's
# per-family floors (BEHAVIOUR_FLOORS below) add to ≥ 1 514, and R-51 widens the
# upper end to 1 800 so the authored `single` family and the provable
# `sequential_chain` top-up fit without trimming a family: K01 is a sanity bound
# on the corpus, never a target families are cut to. The floors and MDEs are
# what bound the claim.
CORPUS_SIZE_BAND_V5: tuple[int, int] = (1200, 1800)
# ±10pp per family needs 120 (TIER_SIZES["small"]); the §8.2 table gives some
# families fewer (same_tool_other_target 50). The FLOORS are the table's own
# counts, no ceiling — `single` and `sequential_chain` exceed theirs because
# the revised v4 corpus supplies them — and the report prints every family's
# MDE (`stats.mde_paired`) so a family under 120 shows its wider interval
# instead of being refused.
MIN_CASES_FOR_10PP: int = 120
BEHAVIOUR_FLOORS: dict[str, int] = {
    "single": 180, "retry_same_tool": 120, "sequential_chain": 180, "parallel": 100,
    "fanout_pick": 100, "branching": 85, "user_in_loop": 85, "memory_anaphora": 120,
    "rag": 100, "document": 100, "same_tool_other_target": 50,
}
MIN_SHARE_WITH_RESULT: float = 0.75      # cases whose loop reaches IN/tool + OUT/answer
BEHAVIOUR_SHARES: dict[str, float] = {
    "single": 0.15, "retry_same_tool": 0.10, "sequential_chain": 0.15, "parallel": 0.08,
    "fanout_pick": 0.08, "branching": 0.07, "user_in_loop": 0.07, "memory_anaphora": 0.10,
    "rag": 0.08, "document": 0.08, "same_tool_other_target": 0.04,
}
SHARE_TOLERANCE: float = 0.03
# Registers: voice is voice_raw + voice_itn together (both are SPEECH_REGISTERS).
# Sums to 1.00 (ruling 2026-09-22: the former 0.95 left 5% unassigned, and K04
# read as four two-sided bands had no place for it; the remainder goes to chat).
# K04 is a claim about what v5 AUTHORS: the 834 revised cases keep the registers
# v4 measured (voice_raw 276, voice_itn 183, chat 250, sloppy 119, clean 6) and
# no mix of new cases can move that block; the report prints the corpus-wide
# register table beside it so nobody mistakes the authored share for the whole.
REGISTER_SHARES: dict[str, float] = {"voice": 0.45, "chat": 0.30, "sloppy": 0.15, "clean": 0.10}
# v4's validate_corpus caps clean at 5% (MAX_CLEAN_SHARE) and bands the corpus
# at (330, 900); both are v4's numbers and v5 does NOT call v4's corpus-level
# validator — it calls v4's per-CASE `validate` on `.base` and re-checks the
# corpus with the constants above.
MIN_CASES_BY_TYPE: dict[str, int] = {"INN": 60, "PLATE": 60}
# «остальные — не ниже v4»: item counts of the 834-case v4 corpus, by type,
# from `wiki/BENCHMARK.md` §2. A v5 corpus with fewer items of a type than v4
# has lost coverage the baseline had.
V4_TYPE_ITEM_COUNTS: dict[str, int] = {
    "NAME": 2204, "LOC": 1767, "PHONE": 1275, "DOB": 547, "EMAIL": 472,
    "CARD": 77, "SNILS": 50, "PASSPORT": 50, "INN": 0, "PLATE": 0}
V4_CORPUS_SIZE: int = 834
V4_CASES_WITH_RESULT: int = 455


@dataclass(frozen=True)
class ReturnExpectation:
    """What ONE call of a tool returns in this case, so the IN/tool hops can be
    declared and the mock knows which return form to render. `result_item_ids`
    are the `PiiItem`s (seed locus) the result carries; the mock renders exactly
    those, in `return_form`. NOTHING AT RUN TIME ASSERTS THAT: `build` proves it
    (`mock.render_problems` — V02 on the form, V03 on the items, V04 on the
    IN/tool hop that reads them) and `toolresult_masked` scores it, whose
    denominator is this declaration. The docstring used to promise an assertion
    in the harness that no line of the harness made, and 42 % of the revised
    half's IN/tool hops were crossings the mock never rendered — each one a hop
    that would have scored as a gateway miss for ever."""

    tool_name: str
    call_ordinal: int
    return_form: str                 # RETURN_FORMS (§3)
    result_item_ids: tuple[str, ...]


@dataclass(frozen=True)
class ForcedError:
    """The mock's scripted refusal that makes `retry_same_tool` deterministic
    with a LIVE agent: on `call_ordinal` of `tool_name` the mock answers an
    `error_with_value` body that echoes `PiiItem.canonical` of `echo_item_id`
    — what the tool's parser accepted, never the spoken surface of a dictated
    number — (as the real API echoes the offending field), whatever the
    arguments. `build` proves the echo renders (`mock.render_problems` V04 on
    the IN hop `retry_same_tool` puts on `error.message`) and the IN-hop lines
    (`leak`, `form_hIN`) score it; `retry_form` asks the OTHER question —
    whether every attempt of the retry wore the agent's own form — and compares
    no canonical, which is what this docstring used to promise. The
    next call of that tool is parsed normally. `code` is the documented rule
    name the message carries. Without this the retry depends on the agent
    making a mistake, and a case whose provocation is a coin toss has an
    unmeasured denominator."""

    tool_name: str
    call_ordinal: int
    code: str
    echo_item_id: str
    message_template: str            # "…{value}…" — exactly one `{value}` slot


@dataclass(frozen=True)
class MemorySpec:
    """A value mentioned at `first_turn` and needed again at `recall_turn`
    (spec §3.3). `anaphora` names how the recall is phrased: `none` repeats the
    value, the others refer to it without saying it («ему», «на тот адрес»,
    «тот же телефон», the person by role). `memory_consistency` counts the
    item — and it is the ONLY line over this population, because an anaphoric
    recall spells no value: the substitute is read in one message and one
    request, which is what left `memory_stability` 0/0 and got it removed
    (J1.2, the removal comment in `METRICS`)."""

    item_id: str
    first_turn: int
    recall_turn: int
    anaphora: str                    # ANAPHORA_KINDS


@dataclass(frozen=True)
class RagSpec:
    """`kb_search(query, k)` returns `k` chunks; `chunk_ids` are the seed
    record ids rendered as chunks, in rank order; `foreign_identities` are the
    identities in those chunks that are NOT the customer's — the ones
    `rag_identity_kept` must see kept apart. `query_item_ids` are the items the
    agent must put into the query (OUT/tool_arg on `kb_search`)."""

    tool_name: str                   # "kb_search" | "doc_retrieve"
    k: int
    chunk_ids: tuple[str, ...]
    foreign_identities: tuple[str, ...]
    query_item_ids: tuple[str, ...]


# A CHUNK SEED IS A `template` COLUMN PLUS ONE FLAT COLUMN PER `{slot}`, and the
# item's `Locus.path` is the BARE COLUMN NAME. Ruling R-28 supersedes R-12,
# which described `{"text": …, "slots": {…}}` with `Locus.path == "slots.<key>"`:
# the landed `mock.py` renders the template shape, and a seed written in the
# other one comes back as a result with empty fields and no tags — a case that
# measures nothing and reads as a gateway miss.
#
# `mock._template_pieces` splits the template on `{[a-z_]+}`, looks each slot up
# in the row's OWN columns, renders it in that field's prose notation
# (`mock.PROSE_NOTATION` writes a phone as «+7 (916) …», a СНИЛС with the ПФР
# separators, a card in four groups) and tags the piece with
# `_tag_of(record, field)`. So the offsets inside the rendered chunk are laid
# down by the writer as it composes; nothing is searched for in a finished
# string, which is the v1 defect this shape exists to prevent. The column keeps
# the value the case declared and the prose may write it in another notation —
# that disagreement IS the IN hop the family measures.
#
# A SLOT NAME IS `[a-z_]+`, and that is a rule of the corpus rather than a
# detail of the splitter: a digit in it («{who2}») is not a slot
# `mock._template_pieces` sees, so the template keeps it as literal text, the
# column it names is never rendered, and every hop declared on it is a crossing
# that never happened. A builder that wants two people in one chunk names them
# `{who_a}` / `{who_b}`.


@dataclass(frozen=True)
class DocumentSpec:
    """A document the agent reads through a tool (`file_read`, `doc_retrieve`,
    `form_parse`) and extracts values from into `extract_to_tool`. `format`
    decides the rendering (`csv` rows, a `form` as nested fields, `free_text`,
    `scan` = free text with OCR-shaped noise).

    `record_count` COUNTS PEOPLE, `record_ids` COUNTS ROWS, AND THEY ARE NOT
    THE SAME NUMBER (ruling R-30). A CSV is ONE `documents` row that holds
    three people, so `len(record_ids)` may be well below `record_count`; the
    equality R-11 first asked for would have refused the commonest document in
    the corpus. `record_ids` names the seed records this document is rendered
    from, and it exists so R18 can check «items of THOSE records» instead of
    the weaker «some seed item», which passed a document claiming to extract a
    value that lives in another record entirely.

    `extracted_item_ids` are the items the agent is expected to move into
    `extract_to_tool` — the OUT hops `doc_extracted` counts — and every one of
    them must be an item of a record in `record_ids`."""

    doc_id: str
    read_tool: str
    format: str                      # DOCUMENT_FORMATS
    record_count: int                # PEOPLE in the payload
    record_ids: tuple[str, ...]      # the seed records rendered; ROWS, not people
    extract_to_tool: str
    extracted_item_ids: tuple[str, ...]


@dataclass(frozen=True)
class PickSpec:
    """`fanout_pick`: `list_tool` returns `candidate_identities` (≥ 2, all with
    a value of the same type as the customer's), the agent must pick
    `target_identity` BY VALUE and call `act_tool` on it. A placeholder masker
    cannot do this — that is the point of the family."""

    list_tool: str
    candidate_identities: tuple[str, ...]
    target_identity: str
    act_tool: str


@dataclass(frozen=True)
class BranchSpec:
    """`branching`: `probe_tool` answers found / not found (decided by whether
    the seed exists — `seed_present`), and the agent must take `then_tool`
    when found, `else_tool` when not. The v4 levels already score whether the
    agent's logic on substitutes equals the control's; the spec adds nothing
    per hop, so the case only declares which branch is the right one."""

    probe_tool: str
    seed_present: bool
    then_tool: str
    else_tool: str


@dataclass(frozen=True)
class LoopSpec:
    """`user_in_loop`: the agent shows what it found at `show_turn` (an
    OUT/answer hop), the user confirms at `confirm_turn`, and the act happens
    after it (an OUT/tool_arg hop with `source_hop` pointing at the IN/tool
    hop of the find). `confirm_phrase` is what the user says — never the
    value itself, or the case would not test memory."""

    find_tool: str
    show_turn: int
    confirm_turn: int
    confirm_phrase: str
    act_tool: str


@dataclass(frozen=True)
class CaseV5:
    """v5 = v4 `Case` + behaviour + declared hops + return expectations + the
    behaviour-specific spec. COMPOSITION, NOT SUBCLASSING: every v4 function
    (`validate`, `case_from_json`, `sample`, `tier`, the harness, the
    comparator) receives `.base` unchanged, so the v4 baseline is run on the
    same bytes it was built for. A subclass would make v4's `to_json` emit v5
    fields into a v4 corpus file and the baseline would drift with the treatment.

    Exactly one of `pick`, `branch`, `loop`, `rag`, `document` is set, and
    only for its behaviour; `memory` may accompany any behaviour; `forced`
    is non-empty only for `retry_same_tool`. `streaming` marks a case whose
    answer leg the harness must run through the sidecar's chunk contract
    (spec §3.7); the corpus needs ≥ `MIN_STREAMING_CASES` of them.

    `has_result` is DERIVED and stored: True iff `hops` contains an IN/tool
    hop AND an OUT/answer hop. Stored because the ≥75% rule (`MIN_SHARE_WITH_
    RESULT`) is a corpus-level count and recomputing it from hops in every
    reader is where readers diverge.
    """

    base: Case
    behaviour: str
    hops: tuple[Hop, ...]
    returns: tuple[ReturnExpectation, ...]
    forced: tuple[ForcedError, ...]
    memory: tuple[MemorySpec, ...]
    pick: PickSpec | None
    branch: BranchSpec | None
    loop: LoopSpec | None
    rag: RagSpec | None
    document: DocumentSpec | None
    has_result: bool
    streaming: bool
    revised_from_v4: bool            # True for the 834; False for a case a v5 generator built
    # v6 industry + provenance; None for every v5-authored case.
    #
    # DEFAULTED, and the default is what keeps the KEEP_V5 row working (S2
    # `scenarios5/common.py`, decision C13: `checkout_v5`, v6's `v6=None` line
    # deliberately dropped because it sits next to the `optional` fix that keeps
    # a required hop off a settlement). That file builds `CaseV5` with no `v6`
    # keyword and `test_schema` drives it: with no default the constructor raises
    # `TypeError: missing 1 required positional argument: 'v6'` — a red that is
    # not about the contract but about a builder that never heard of v6.
    # `schema.py` (corpus JSON) and `fixtures.py`/`revise.py`/`test_judge.py`
    # (the S2 rows) pass it explicitly either way, so the default changes no
    # reading and only admits the v5-only construction path.
    v6: CaseV6Meta | None = None


MIN_STREAMING_CASES: int = 60

# The rules `validate_v5(case) -> list[str]` (generator_b, `schema.py`) must
# enforce, each a separate message so a reviewer can map a rule to a line.
# Every problem is reported, never the first one only (v4's discipline).
V5_CASE_RULES: tuple[str, ...] = (
    "R01 behaviour in BEHAVIOURS",
    "R02 v4.validate(base) reports nothing",
    "R03 hop_index values are 0..n-1 in order; kinds/owners in HOP_KINDS/HOP_OWNERS; IN owner in IN_OWNERS, OUT owner in OUT_OWNERS",
    "R04 every hop.item_id names an item of base.pii; every hop.turn indexes a user message of base.messages",
    "R05 an IN/user hop's item has a message locus; an IN/tool or IN/document hop's item has a seed locus and its tool_name appears in `returns`",
    "R06 every OUT hop with source_hop != -1 points at an earlier IN hop of the SAME item or of an item of the same identity",
    "R07 has_result == (any IN/tool hop and any OUT/answer hop); a case with has_result carries at least MIN_HOPS_WITH_RESULT hops",
    "R08 tool_name of every tool-bearing hop is in base.tools; call_ordinal >= 0 iff tool_name != ''",
    "R09 hops sharing a parallel_group are all OUT, all in one turn, and ≥ 2; behaviour == 'parallel' iff any parallel_group",
    "R10 behaviour == 'retry_same_tool' iff forced is non-empty; each ForcedError names a tool in base.tools, an item of base.pii, and has exactly one {value} slot; a hop with call_ordinal == forced.call_ordinal + 1 exists for that tool",
    "R11 behaviour == 'same_tool_other_target' → ≥ 2 identities each with an OUT/tool_arg hop on the same tool_name",
    "R12 behaviour == 'sequential_chain' → ≥ 1 OUT hop with source_hop pointing at an IN/tool hop of a DIFFERENT tool_name",
    "R13 behaviour == 'fanout_pick' iff pick is set; pick.list_tool returns ≥ 2 candidate identities; target_identity in candidates; every candidate has a seed item of the same type as the target's matched value",
    "R14 behaviour == 'branching' iff branch is set; then_tool and else_tool both in base.tools and differ",
    "R15 behaviour == 'user_in_loop' iff loop is set; show_turn < confirm_turn; confirm_phrase contains no item value; an OUT/answer hop at show_turn and an OUT hop with owner in ('tool_arg', 'template', 'summary') at or after confirm_turn exist (a handover — escalate_to_human, crm_add_note — acts through summary leaves and must count; Hop.turn is the user message that OPENS a turn, and the act that follows «да, это я» happens inside the turn that message opened)",
    "R16 behaviour == 'memory_anaphora' → memory non-empty; every MemorySpec has first_turn < recall_turn, anaphora in ANAPHORA_KINDS, and the item is NOT written again at recall_turn when anaphora != 'none'",
    "R17 behaviour == 'rag' iff rag is set; rag.k == len(chunk_ids); every chunk_id is a seed record; foreign_identities are identities of those seeds other than expects.primary_identity, ≥ 1 of them",
    "R18 behaviour == 'document' iff document is set; format in DOCUMENT_FORMATS; record_count ≥ 1 (≥ 2 for csv — it counts PEOPLE); every id in record_ids is a seed record of the case; extracted_item_ids are seed items OF THOSE RECORDS (ruling R-30: a CSV is one row holding several people, so len(record_ids) is not len(record_count)); extract_to_tool in base.tools",
    "R19 every ReturnExpectation names a tool in base.tools, a return_form in RETURN_FORMS declared by that tool's ToolSpecV5 (a tool declares EVERY form it can return — a state-decided one like address_suggest canon/list is declared as both — and the case's return_form says which one THIS seeded state yields; the observer compares the mock's actual form with it), and result_item_ids that are seed items",
    "R20 streaming cases are register voice_raw or voice_itn",
    "R21 the items of every OUT hop with owner in ('template','summary') are named by TEMPLATE_FIELDS / SUMMARY_FIELDS of its tool",
    "R22 the OUT hops of one (turn, item, semantic leaf) declare ONE (tool, path): two DIFFERENT leaves of one class on one transition would let one written leaf satisfy both, and one crossing would read two `observed`",
    "R23 a REQUIRED OUT hop must not name an item superseded by a LATER message item of the same (type, identity, message) with a DIFFERENT value: the correct agent writes the corrected value, so the hop on the cancelled one can never become `observed`",
)
V5_CORPUS_RULES: tuple[str, ...] = (
    "K01 size in CORPUS_SIZE_BAND_V5 and every case id unique (two cases under one id are one case counted twice in every share below)",
    "K02 every behaviour in BEHAVIOURS has ≥ BEHAVIOUR_FLOORS[behaviour] cases and a share ≥ BEHAVIOUR_SHARES[behaviour] - SHARE_TOLERANCE (a floor, no ceiling); build.py prints each family's MDE",
    "K03 share of has_result cases ≥ MIN_SHARE_WITH_RESULT",
    "K04 register shares of the v5-AUTHORED cases (revised_from_v4 == False) within SHARE_TOLERANCE of REGISTER_SHARES (voice = voice_raw + voice_itn); the revised 834 are reported beside, never mixed in",
    "K05 for each type in MIN_CASES_BY_TYPE: ≥ that many cases carry an item of the type (any locus)",
    "K06 for each type: item count ≥ V4_TYPE_ITEM_COUNTS[type]",
    "K07 every tool of REGISTRY_V5 is reachable in ≥ MIN_TYPE_DENOMINATOR cases",
    "K08 ≥ MIN_CLUSTER_MULTI clusters of size ≥ 3",
    "K09 both explicit and derived conversation ids occur",
    "K10 exactly V4_CORPUS_SIZE cases have revised_from_v4, and V4_CASES_WITH_RESULT of them have has_result",
    "K11 ≥ MIN_STREAMING_CASES streaming cases",
    "K12 holdout tier = HOLDOUT_SHARE of the corpus, frozen in the ladder before any debug run (enforced by build.py and test_build.test_holdout_frozen — validate_corpus_v5 sees a list of cases, not a ladder, and says so in its docstring)",
    "K13 every owner in HOP_OWNERS is declared by ≥ MIN_TYPE_DENOMINATOR cases; every IN owner other than 'user' and every OUT owner other than 'tool_arg' also by ≥ MIN_TYPE_DENOMINATOR cases of ≥ 2 behaviours",
    "K14 every DOCUMENT_FORMATS value occurs in ≥ MIN_TYPE_DENOMINATOR document cases; every ANAPHORA_KINDS value other than 'none' in ≥ MIN_TYPE_DENOMINATOR memory cases; ≥ MIN_TYPE_DENOMINATOR memory cases carry ≥ 3 MemorySpecs and ≥ 2 identities across ≥ 5 user turns",
    "K15 ≥ MIN_TYPE_DENOMINATOR cases declare a ReturnExpectation whose result_item_ids hold ≥ 2 items of ONE identity (many records of one person)",
    "K17 every IN/tool hop's path (array indexes erased) is one of its tool's declared result_pii paths — the other half of V06: a declaration a hop crosses can no longer be deleted in silence, and a hop can no longer cross a leaf the registry never claimed carries personal data (126 hops crossed `error.message` while four tools declared only `error.subject`)",
    "K16 every vertical whose READING tool (non-mutating, result_pii non-empty) the corpus OFFERS carries ≥ MIN_TYPE_DENOMINATOR IN/tool hops — a vertical whose result notation nothing reads back prints «н/п» in every form slice while its OUT hops make it look covered (clinic: 584 hops, zero IN/tool). A vertical whose tools are all mutating is exempt and named: it has no result to read, by the API's design, not by ours",
)


class CaseKit(Protocol):
    """The builder generator_b ships in `scenarios5/common.py` and generator_a
    codes against. It wraps v4's `CaseBuilder` (messages, items, seeds,
    negatives, trace) and ADDS the v5 declarations; `build()` runs
    `validate_v5` and raises on any problem, so no invalid case can be written.
    Method order in a scenario: v4 moves first (user / seed), then the
    declarations, then build."""

    def declare_hop(self, hop: Hop) -> None: ...
    def expect_return(self, expectation: ReturnExpectation) -> None: ...
    def force_error(self, forced: ForcedError) -> None: ...
    def remember(self, memory: MemorySpec) -> None: ...
    def set_pick(self, pick: PickSpec) -> None: ...
    def set_branch(self, branch: BranchSpec) -> None: ...
    def set_loop(self, loop: LoopSpec) -> None: ...
    def set_rag(self, rag: RagSpec) -> None: ...
    def set_document(self, document: DocumentSpec) -> None: ...
    def set_streaming(self, streaming: bool) -> None: ...
    def build(self, behaviour: str) -> CaseV5: ...


# --- §3 tools: verticals and return forms (spec §2, §8.1) ---------------------------

RETURN_FORMS: tuple[str, ...] = (
    "single",            # one record
    "list",              # several records; the agent must choose / match
    "nested",            # an object with typed sub-fields (address by fields, recipient{name, phone})
    "error_with_value",  # an error body that echoes the real value in its text; a documented parse REFUSAL whose message names the offending argument is recorded as this form too (Refusal.as_error) — the model reads the value either way
    "empty",             # not found / no rows — a 200 with nothing
    "canon",             # a normaliser's canonical form («г Самара, ул Луговая, д 10», «+7 (916) …»)
    "free_text",         # prose carrying values (ticket history, a document)
    "chunks",            # k retrieval chunks, each free text, possibly other people's
)
# Eleven verticals (spec §2 table; §8.1 «11 вертикалей»). Telephony is a
# REGISTER (voice) plus streaming, not a vertical of tools; CRM is where v4's
# 31 mostly sit and remains a vertical of its own.
VERTICALS: tuple[str, ...] = (
    "delivery", "directory", "clinic", "bank", "support", "calendar",
    "messaging", "government", "search", "files", "crm")
V4_TOOL_NAMES: tuple[str, ...] = tuple(REGISTRY)          # 31, kept whole
# A SUITE IS A SLICE ACROSS VERTICALS, NEVER A TWELFTH VERTICAL. An office
# assistant's tools land in five different verticals — mail is `messaging`, an
# invitation is `calendar`, a tracker is `support`, a card is `crm`, a sheet and
# a document are `files` — so `--slice vertical=…` cannot isolate them and a new
# vertical would both break the closed list of eleven and file a spreadsheet
# under something other than «files», where it belongs by its return form.
#
# THE AXIS IS GENERAL, THE VALUE IS NOT. `office` is the first customer's shape
# of work; the next customer gets their own suite name and the same machinery.
# A tool belongs to at most one suite, and a tool named by no suite is filed
# under "" — the great majority, and the reason this is a lookup with a default
# rather than a required field on every spec.
SUITES: tuple[str, ...] = ("office",)
NO_SUITE: str = ""
NEW_TOOL_NAMES: tuple[str, ...] = (
    "kb_search", "doc_retrieve", "file_read", "form_parse", "bank_client_find",
    "account_statement", "vehicle_check", "snils_verify", "calendar_free",
    "email_send", "ticket_history", "courier_status", "patient_find",
    # --- the office suite (the first enterprise customer's own shapes) -------
    # Named by SHAPE, never by product. The corpus outlives any one deal and is
    # reused for the next customer; «форма → реальный продукт» is a separate
    # note kept outside it. `mail_read` and `mail_search` are the leg the corpus
    # had nowhere: of 708 IN/tool → OUT/tool_arg transitions not ONE starts in a
    # `free_text` result, and a letter read and then written into a card is
    # exactly where a placeholder gateway scores zero.
    "mail_read", "mail_search", "mail_send", "calendar_invite",
    "tracker_find_user", "tracker_issue_create", "crm_upsert_card",
    "sheet_append_row", "doc_append", "memory_save", "reminder_set")
# The 55 tool names v5 shipped, PINNED so the old-corpus checks keep reading
# them after v6 tools land (F17/F13). `REGISTRY_V5` grows to 55 + v6; this tuple
# never does, and `test_tools` pins the count at 55.
V5_TOOL_NAMES: tuple[str, ...] = (*V4_TOOL_NAMES, *NEW_TOOL_NAMES)
# The suite a tool belongs to. Lookup, not a column: 44 of the 55 belong to none.
TOOL_SUITE: dict[str, str] = {
    "mail_read": "office", "mail_search": "office", "mail_send": "office",
    "calendar_invite": "office", "tracker_find_user": "office",
    "tracker_issue_create": "office", "crm_upsert_card": "office",
    "sheet_append_row": "office", "doc_append": "office", "memory_save": "office",
    "reminder_set": "office"}
# The vertical of every v4 tool (a revision, spec §8.1) and of every new one
# (spec §8.1 table). Closed here so two components cannot file one tool under
# two verticals.
TOOL_VERTICAL: dict[str, str] = {
    "delivery_create_order": "delivery", "courier_book": "delivery", "order_status": "delivery",
    "order_cancel": "delivery", "order_reschedule": "delivery", "delivery_quote": "delivery",
    "pickup_points_near": "delivery", "courier_status": "delivery",
    "address_suggest": "directory", "normalize_contact": "directory",
    "clinic_book": "clinic", "clinic_slots": "clinic", "appointment_cancel": "clinic",
    "appointment_reschedule": "clinic", "referral_create": "clinic",
    "patient_find": "clinic",
    "payment_create": "bank", "payment_status": "bank", "payment_refund": "bank",
    "receipt_fetch": "bank", "bank_client_find": "bank", "account_statement": "bank",
    "ticket_create": "support", "ticket_find": "support", "escalate_to_human": "support",
    "ticket_history": "support",
    "callback_schedule": "calendar", "calendar_free": "calendar",
    "notify_sms": "messaging", "send_template": "messaging", "email_send": "messaging",
    "passport_verify": "government", "vehicle_check": "government", "snils_verify": "government",
    "kb_search": "search", "doc_retrieve": "search",
    "crm_import_csv": "files", "file_read": "files", "form_parse": "files",
    "crm_find_contact": "crm", "crm_upsert_contact": "crm", "crm_add_note": "crm",
    "crm_segment_report": "crm", "crm_merge_contacts": "crm",
    # --- the office suite, filed by RETURN FORM rather than by product family --
    # A letter is messaging; an invitation and a reminder are calendar work; a
    # tracker is the support desk under another name; a two-dimensional sheet and
    # a document are files, which is the vertical whose forms they wear; a card
    # and a fact about a person saved for later are CRM. Nothing here asks for a
    # twelfth vertical, and `test_contracts` pins that at eleven.
    "mail_read": "messaging", "mail_search": "messaging", "mail_send": "messaging",
    "calendar_invite": "calendar", "reminder_set": "calendar",
    "tracker_find_user": "support", "tracker_issue_create": "support",
    "crm_upsert_card": "crm", "memory_save": "crm",
    "sheet_append_row": "files", "doc_append": "files",
}
# The return forms each NEW tool must declare (spec §8.1 table), and the PII
# types its results carry. The tools component may add forms, never remove.
NEW_TOOL_RETURN_FORMS: dict[str, tuple[str, ...]] = {
    "kb_search": ("chunks", "empty"),
    "doc_retrieve": ("free_text", "empty"),
    "file_read": ("free_text", "list", "empty"),
    "form_parse": ("nested", "error_with_value"),
    "bank_client_find": ("single", "list", "empty", "error_with_value"),
    "account_statement": ("list", "empty"),
    "vehicle_check": ("single", "error_with_value"),
    "snils_verify": ("single", "empty", "error_with_value"),
    "calendar_free": ("list", "empty"),
    "email_send": ("single", "error_with_value"),
    "ticket_history": ("free_text", "empty"),
    "courier_status": ("nested", "error_with_value"),
    # THE ONLY READING TOOL OF THE CLINIC, and it exists because the vertical
    # had none: five booking/cancelling tools, 584 declared hops and not one
    # IN/tool — so «ДР ISO, СНИЛС с разделителями» (spec §2) was the one return
    # notation no run could check. `empty` rather than `error_with_value`: a МИС
    # answers an unknown insured person with an empty match set, not a fault,
    # and inventing a fault the API does not raise would measure our fiction.
    "patient_find": ("single", "empty"),
    # --- the office suite ----------------------------------------------------
    # `free_text` ON A READING TOOL IS THE WHOLE POINT. The corpus carries 708
    # IN/tool → OUT/tool_arg transitions and not one of them starts in prose:
    # the only free text that reaches an argument today comes from a DOCUMENT
    # (413 hops, `file_read`/`form_parse`/`doc_retrieve`). A letter is the
    # customer's commonest source of prose, messaging had ZERO reading tools —
    # the vertical is exempt from K16 with the reason «only writes» — and the
    # exemption goes the moment `mail_read` lands.
    "mail_read": ("nested", "free_text", "empty"),
    "mail_search": ("list", "empty", "error_with_value"),
    "mail_send": ("single", "error_with_value"),
    "calendar_invite": ("single", "error_with_value"),
    # NO `error_with_value`: Jira's user search has no DOMAIN failure — an
    # unknown person is an empty match set, not a fault — and the only error it
    # answers is the documented refusal of a malformed query, which the package
    # already records as that form through `Refusal.as_error`. Declaring it here
    # too would ask the mock to render a body the API never writes.
    "tracker_find_user": ("list", "empty"),
    "tracker_issue_create": ("single", "error_with_value"),
    "crm_upsert_card": ("nested", "error_with_value"),
    "sheet_append_row": ("list", "error_with_value"),
    "doc_append": ("single", "error_with_value"),
    "memory_save": ("single", "error_with_value"),
    "reminder_set": ("single", "error_with_value"),
}
NEW_TOOL_RESULT_TYPES: dict[str, tuple[str, ...]] = {
    "kb_search": ("NAME", "PHONE", "LOC"), "doc_retrieve": ("NAME", "PHONE", "LOC", "DOB", "EMAIL"),
    "file_read": ("NAME", "PHONE", "EMAIL", "DOB", "LOC"), "form_parse": ("NAME", "DOB", "PASSPORT", "SNILS", "LOC"),
    "bank_client_find": ("INN", "CARD", "NAME"), "account_statement": ("NAME", "CARD"),
    "vehicle_check": ("PLATE", "NAME"), "snils_verify": ("SNILS", "NAME", "DOB"),
    # `DATE` is not a v4 item type (a slot date is not personal data); the
    # calendar's personal datum is the patient's DOB beside the name. DATE
    # features exist for spans the ENGINE typed DATE (undeclared IN hops).
    "calendar_free": ("NAME", "DOB"), "email_send": ("EMAIL",),
    "ticket_history": ("NAME", "PHONE", "LOC", "EMAIL"), "courier_status": ("NAME", "PHONE", "LOC"),
    # The clinic's own three notations, and the reason the tool is here: the
    # birth date in ISO, the СНИЛС with the ПФР separators, the phone in E.164
    # — three forms no speech register writes.
    "patient_find": ("NAME", "DOB", "SNILS", "PHONE"),
    # --- the office suite ----------------------------------------------------
    # EMAIL leads the mail tools because that is the gap the measurement found:
    # EMAIL crosses the gateway as an IN/user hop 14 times in 1 736 cases while
    # the corpus declares 1 196 EMAIL items — the type is DECLARED everywhere
    # and CROSSED almost nowhere, and a mailbox is where it actually travels.
    "mail_read": ("NAME", "EMAIL", "PHONE", "LOC"),
    "mail_search": ("EMAIL", "NAME", "PHONE"),
    "mail_send": ("EMAIL",),
    "calendar_invite": ("EMAIL", "NAME"),
    "tracker_find_user": ("NAME", "EMAIL"),
    "tracker_issue_create": ("NAME",),
    "crm_upsert_card": ("NAME", "PHONE", "EMAIL", "LOC"),
    # A spreadsheet cell holds a WHOLE value, never a part of one: one column is
    # the name, the next the phone, the next the address. That is why the sheet
    # names four types and why its argument leaf declares no `role`.
    "sheet_append_row": ("NAME", "PHONE", "EMAIL", "LOC"),
    "doc_append": ("NAME", "PHONE", "LOC"),
    # ONLY the subject: `memory.fact` is the agent's own sentence and the mock
    # cannot tag a value inside a string it did not build (see `tools.py`).
    "memory_save": ("NAME",),
    "reminder_set": ("NAME", "PHONE"),
}
# Per-vertical coverage every registry must satisfy (spec §8.1 «Итого»).
VERTICAL_RULES: tuple[str, ...] = (
    "V01 every vertical has ≥ 1 tool declaring return form 'list'",
    "V02 every vertical has ≥ 1 tool declaring 'error_with_value' or 'empty'",
    "V03 every vertical has ≥ 1 tool with differs_from_user_form",
    "V04 every tool declares ≥ 1 return form and ≥ 1 result path carrying PII (result_pii non-empty) — a tool whose result carries nothing has no IN/tool hop to measure",
    "V05 every tool has a non-empty source and a strict parse that refuses a malformed argument with a documented rule name",
    "V06 every result_pii path is named by at least one declared ReturnForm.pii_paths — V04 checks the containment one way only (a form may not name a path result_pii does not), so a path declared in the union and in no form was measurable by nothing and deleting it broke nothing: five of the 142 lived that way",
    "V07 every tool's suite is SUITES or NO_SUITE, and it is the one TOOL_SUITE names — the suite is the axis a customer's own shapes are read on, and two components filing one tool under two suites would make `--slice suite=office` mean two different sets",
)


@dataclass(frozen=True)
class ReturnForm:
    """One return form of a tool: the form, an EXAMPLE the mock's rendering
    must match in shape (same keys, same nesting, same separators — the
    example is data, checked by `test_tools`), and the result paths carrying
    PII in THIS form. `result_pii` on the v4 `ToolSpec` is the union; here it
    is per form because `list` and `error_with_value` carry values at
    different paths."""

    form: str
    example: str
    pii_paths: tuple[str, ...]


@dataclass(frozen=True)
class ToolSpecV5:
    """v4 `ToolSpec` (schema, fields, strict parse, mutating, result_pii) plus
    the vertical and the declared return forms. Composition again: the mock
    and the comparator keep calling `base.parse` / reading `base.fields`.

    `differs_from_user_form` is True when at least one result form renders
    a PII type in a notation the user register never produces (a canon, ISO
    dates, «+7 (916) 123-45-67», СНИЛС with separators) — the tools whose
    IN/tool hop actually tests adaptation (spec §8.1 «форма, ОТЛИЧНАЯ от той,
    что дал юзер»)."""

    base: ToolSpec
    vertical: str                    # VERTICALS
    return_forms: tuple[ReturnForm, ...]
    differs_from_user_form: bool
    # SUITES or NO_SUITE. A SECOND, CROSS-CUTTING AXIS, and it exists because
    # the vertical could not answer the question a customer asks: «what do YOUR
    # numbers say about MY tools». An office assistant's eleven shapes fall into
    # five verticals, so `--slice vertical=messaging` measures a third of them
    # and dilutes that third with SMS; `--slice suite=office` is exactly them.
    # Default "" so the 44 that belong to no suite need no edit, and so a future
    # customer's suite is one dict entry rather than a migration.
    suite: str = NO_SUITE


class ResultRenderer(Protocol):
    """How the mock (tools component, `mock.py`) renders a result for one
    call: the typed data, the `writer.Slot` tree whose serialisation carries
    the offsets of every PII value (v4's `mock.CallLog.result_spans`), and the
    form actually used. `form` is chosen by the mock from the tool's declared
    forms by the state it is in (found → single/list, absent → empty, a
    ForcedError → error_with_value); the harness records it on the
    `ToolResultRecord` so `toolresult_masked` can slice by form."""

    def __call__(self, tool_name: str, parsed: dict[str, object],
                 forced: ForcedError | None) -> tuple[dict[str, object], object, str]: ...


# --- §4 the form comparator (spec §1.1, §8.4) ----------------------------------------

# THE v6 HALF OF EVERY FORM TABLE, READ FROM ITS ONE HOME. The eleven v5 rows
# below stay LITERALS — they are the home `pii_types` transcribes, and the
# script/translit SPLIT lives in them — while the 55 v6 records are added from
# `pii_types.TYPE_REGISTRY`, the one home the approved `contracts → pii_types`
# edge points at (SPEC §3.2 O-V6-4). Neither half replaces the other: a bare
# `pii_types.form_features(TYPE_REGISTRY)` would transcribe the registry's NAME
# record, which still predates the split (alphabet and romanization collapsed
# into one `script`, `translit` absent), and taking it makes
# `form.FEATURE_EXTRACTORS[('NAME','translit')]` unreachable — the romanization
# question would stop being asked SILENTLY instead of failing loudly (SPEC §2.1
# C04 adopt_gate, §5.1). S4 migrates the NAME record itself, after which the
# three tables below are one plain registry read and the v5 literals are the
# transcription test's business — not before.
_V6_RECORDS: tuple[pii_types.TypeSpec, ...] = tuple(
    record for record in pii_types.TYPE_REGISTRY if record.origin == pii_types.ORIGIN_V6)

# EXACTLY the feature names of spec §8.4, per type. `DATE` is a non-birth date
# the engine substituted (an appointment slot, a document date): same features
# as DOB, listed separately because the spec lists «DOB/DATE» and a metric
# slice by type must not fold the two.
FORM_FEATURES: dict[str, tuple[str, ...]] = {
    # `script` IS THE ALPHABET AND `translit` IS THE ROMANIZATION (SPIKE-Ж, Ж-5).
    # One feature used to answer both: `form.name_script` returned
    # `latin:gost|icao|bgn|unknown`, so two LATIN strings whose letters no
    # published table spells differently — `unknown`, which is the extractor
    # saying «no opinion» — were charged a `script` difference. That is 50 of
    # the 62 `form OUT/answer` misses of g07 (17 cases), and it punishes the
    # instrument's own resolution limit, exactly as `order` → `other` already
    # abstains next door. The alphabet is a real question and stays (3
    # Cyrillic-versus-Latin hops in the archives, 202 in g06, are class Г and
    # MUST remain a difference); the romanization system is a separate one and
    # abstains when no table speaks.
    "NAME": ("case_class", "gram_case", "order", "parts", "initials", "script", "translit",
             "hyphen_particle"),
    "PHONE": ("prefix", "grouping", "separators", "parens"),
    "LOC": ("case_class", "generic", "generic_position", "house_marker", "flat_marker", "commas",
            "city_present", "city_position", "by_fields", "building_entrance_markers"),
    "DOB": ("notation", "separator", "padding", "year_len", "month_form"),
    "DATE": ("notation", "separator", "padding", "year_len", "month_form"),
    "EMAIL": ("case_class",),
    "CARD": ("grouping", "separator"),
    "SNILS": ("separators",),
    "INN": ("length", "separators"),
    "PASSPORT": ("series_number_split",),
    "PLATE": ("case_class", "spaces", "region_sep"),
}
# THE 55 v6 ROWS ARE ADDED, NEVER SUBSTITUTED FOR THE v5 ONES (SPEC §2.1 C02:
# keep_v5 + adopt_v6). The split above survives because `NAME` is a v5 record and
# `_V6_RECORDS` does not carry it; the v6 additions survive because nothing here
# filters them out. `test_form.test_extractor_keys_equal_contract` is the pin:
# `form.FEATURE_EXTRACTORS` is built from `form_v6`'s v6 half as well, so a
# v5-only `FORM_FEATURES` would leave those extractors unreachable and RED.
FORM_FEATURES.update(pii_types.form_features(_V6_RECORDS))
FORM_TYPES: tuple[str, ...] = tuple(FORM_FEATURES)
# The closed label set each feature extractor returns. Two strings with the
# same label agree on the feature; anything else is a difference named by the
# feature. A label written `prefix:*` is an open family whose members are
# distinguished by the text after the colon (the generic word itself, the
# marker set) — the comparator compares the whole label. Closed here so the
# adversarial fixtures of `form_hIN`/`form_hOUT` can name the label they
# expect, and so two extractors written by two people cannot disagree about
# what «title case» means.
FEATURE_LABELS: dict[tuple[str, str], tuple[str, ...]] = {
    ("NAME", "case_class"): ("lower", "title", "upper", "mixed", "none"),
    ("NAME", "gram_case"): ("nomn", "gent", "datv", "accs", "ablt", "loct", "unknown"),
    ("NAME", "order"): ("F-I-O", "I-F", "I-O-F", "single", "other"),
    ("NAME", "parts"): ("1", "2", "3", "4+"),
    ("NAME", "initials"): ("none", "given", "given_patronymic"),
    ("NAME", "script"): ("cyrillic", "latin", "mixed", "none"),
    ("NAME", "translit"): ("latin:gost", "latin:icao", "latin:bgn", "latin:unknown"),
    ("NAME", "hyphen_particle"): ("none", "hyphen", "particle", "both"),
    ("PHONE", "prefix"): ("plus7", "eight", "seven", "bare", "other"),
    ("PHONE", "grouping"): ("3-3-2-2", "3-3-4", "solid", "other"),
    ("PHONE", "separators"): ("none", "space", "hyphen", "dot", "mixed"),
    ("PHONE", "parens"): ("yes", "no"),
    ("LOC", "case_class"): ("lower", "title", "upper", "mixed", "none"),
    ("LOC", "generic"): ("none", "full:*", "abbr:*"),
    ("LOC", "generic_position"): ("before", "after", "none"),
    ("LOC", "house_marker"): ("none", "d_dot_space", "d_dot_nospace", "d_nodot", "dom", "other"),
    ("LOC", "flat_marker"): ("none", "kv_dot_space", "kv_dot_nospace", "kv_nodot", "kvartira", "other"),
    ("LOC", "commas"): ("yes", "no"),
    ("LOC", "city_present"): ("yes", "no"),
    ("LOC", "city_position"): ("first", "last", "middle", "none"),
    ("LOC", "by_fields"): ("fields", "string"),
    ("LOC", "building_entrance_markers"): ("none", "markers:*"),
    ("DOB", "notation"): ("dmy_dots", "dmy_slashes", "iso", "words", "solid", "other"),
    ("DOB", "separator"): ("dot", "slash", "hyphen", "space", "none"),
    ("DOB", "padding"): ("padded", "unpadded"),
    ("DOB", "year_len"): ("2", "4", "none"),
    ("DOB", "month_form"): ("number", "word_nominative", "word_genitive"),
    ("DATE", "notation"): ("dmy_dots", "dmy_slashes", "iso", "words", "solid", "other"),
    ("DATE", "separator"): ("dot", "slash", "hyphen", "space", "none"),
    ("DATE", "padding"): ("padded", "unpadded"),
    ("DATE", "year_len"): ("2", "4", "none"),
    ("DATE", "month_form"): ("number", "word_nominative", "word_genitive"),
    ("EMAIL", "case_class"): ("lower", "upper", "mixed", "none"),
    ("CARD", "grouping"): ("4x4", "solid", "other"),
    ("CARD", "separator"): ("space", "hyphen", "none", "other"),
    ("SNILS", "separators"): ("canonical", "solid", "other"),
    ("INN", "length"): ("10", "12", "other"),
    ("INN", "separators"): ("none", "space", "other"),
    ("PASSPORT", "series_number_split"): ("2-2-6", "4-6", "solid", "other"),
    ("PLATE", "case_class"): ("lower", "upper", "mixed", "none"),
    ("PLATE", "spaces"): ("yes", "no"),
    ("PLATE", "region_sep"): ("space", "none", "other"),
}
# THE v6 LABELS ARE ADDED, AND `NAME`'s TWO ROMANIZATION-ADJACENT ROWS ABOVE ARE
# NOT TOUCHED: the registry's NAME record still declares the seven-label pre-split
# `script` and no `translit` at all, so reading it would (a) drop the abstention
# `("NAME","translit") → latin:unknown`, (b) re-open the 50-of-62 g07 form misses
# the split removed, and (c) leave `contracts.FORM_ABSTAIN` with a key no label
# set declares — `test_form.test_abstain_is_closed_and_one_sided` reads exactly
# that (SPEC §2.1 C04 adopt_gate, §5.1).
FEATURE_LABELS.update(pii_types.feature_labels(_V6_RECORDS))

# ABSTAIN (ruling 2026-09-22 on the comparator's question): `form_match` adds a
# feature to `differs` iff a != b AND neither side carries the feature's abstain
# label. The brief's own acceptance pairs demand it — («Ivanov Petr», «Иванов
# Пётр») must differ in {script} only, and a Latin rendering has no Russian
# case; («Ленина 14», «ул. Ленина 14») in {generic} only, and an address without
# a generic word has no position for it. A string with no letters has no case
# class and no script either: the label is «none» and the feature abstains,
# rather than two letterless strings «agreeing» on a claim neither supports.
# PHONE.prefix and CARD.separator gained «other» so a string matching none of
# the named shapes is a label, not a silent fall-through to the last branch.
# LOC.city_present CANNOT be isolated from city_position (an absent city is
# also a position): the per-feature isolation check accepts {city_present,
# city_position} for either one.
# `order` = «other» joined the list in round 3 for the same reason `script` =
# «none» is in it: `name_order` returns `other` when the suffix shapes do not
# spell one of the four readings, which is the extractor saying «I cannot read
# the roles of these words», not «the roles are unusual». 47 of 346 NAME
# canonicals in the corpus read `other` — every given name in -ин/-ий/-ая/-ой
# (Ирина, Марина, Дмитрий, Аркадий) is surname-shaped — so comparing `other`
# as a reading made a PERFECT restoration a form MISS whenever the real value
# and the minted substitute fell on opposite sides of the guess.
FORM_ABSTAIN: dict[tuple[str, str], str] = {
    ("NAME", "gram_case"): "unknown",
    ("LOC", "generic_position"): "none",
    ("NAME", "case_class"): "none",
    ("LOC", "case_class"): "none",
    ("EMAIL", "case_class"): "none",
    ("PLATE", "case_class"): "none",
    ("NAME", "script"): "none",
    # THE ROMANIZATION SYSTEM ABSTAINS WHEN THERE IS NO OPINION, and the label
    # `latin:unknown` IS that opinion's absence — the extractor's own words in
    # `form_tables.TRANSLIT_SIGNATURES` («nothing discriminating»). Comparing it
    # as though it were a CONVENTION is what made `DMITRIY KUZNETSOV` against
    # `EGOR BOBROV` differ. The same shape as `order` → `other` below,
    # and `test_form` pins the two abstentions together.
    ("NAME", "translit"): "latin:unknown",
    ("NAME", "order"): "other",
}
# THE v6 ABSTENTIONS ARE ADDED ON TOP (SPEC §2.1 C02: keep v5 PLUS any v6 rows) —
# never instead of them. The v5 rows above are all v5 records and every one of
# them is also a key `FEATURE_LABELS` declares and `form.FEATURE_EXTRACTORS`
# answers; the v6 rows arrive together with their labels and their extractors, so
# `test_form.test_abstain_is_closed_and_one_sided` stays a live check on all of
# them. The registry's NAME abstentions are a strict subset of the v5 rows here
# (gram_case / case_class / script / order), which is why the split's `translit`
# row has to be kept literally: the registry does not declare it.
FORM_ABSTAIN.update(pii_types.form_abstain(_V6_RECORDS))
# LEXEME-DEPENDENT FEATURES, and why a label is not enough for them.
#
# `form_match` is handed two DIFFERENT LEXEMES on the OUT leg — `observe.
# _out_call` passes produced = the real value and reference = the substitute
# the agent wrote — so a feature whose label is a reading of the WORDS rather
# than of the WRITING cannot be compared label to label: the two strings may
# wear the same form and still read differently, and a perfect gateway is
# scored a miss for a difference it cannot remove. Measured: a perfect gateway
# over 200 corpus cases printed form_hOUT 76.3% (NAME.gram_case 96 misses,
# NAME.order 57), and the answer line 74.3%.
#
# Each key here names a feature whose COMPARISON is a function rather than
# label equality; `form.FEATURE_COMPARATORS` holds exactly these keys and
# `test_form` pins the two sets equal, so a comparator can never be added
# without the reason being written down, nor a reason without a comparator.
# The value is that reason, printed by nothing and read by whoever asks why a
# feature stopped being compared the ordinary way.
FORM_LEXEME_READINGS: dict[tuple[str, str], str] = {
    ("NAME", "gram_case"): (
        "pymorphy3 gives «Соколова» {nomn, gent, accs} and «Ткачук» all six, and the TOP parse "
        "among equally scored readings is arbitrary — «Громова» reads gent, «Титова» accs, "
        "«Марина» nomn, from one and the same set. Two strings therefore wear the same case "
        "whenever their possible-case sets INTERSECT, and differ only when no reading puts them "
        "in one case; «Иванов Пётр» {nomn} against «Иванову Петру» {accs, datv} is still a "
        "difference, which is the defect the feature exists for (known-issues Б24)."),
    ("NAME", "order"): (
        "the roles are guessed from suffixes, so two names written in the same order can read "
        "differently; `other` abstains through FORM_ABSTAIN, and a pair whose part COUNTS differ "
        "abstains here — «Иванов Пётр» against «Пахомова» is a difference `parts` already names, "
        "and counting it twice would make one violation two."),
    ("NAME", "initials"): (
        "«П.О.» is one part and «Иванова Елена» is two: whether initials were squeezed is not "
        "comparable across two strings of different part counts, and `parts` names that "
        "difference once."),
}
# The transliteration tables `script` must tell apart; written from their
# published standards, never from `pseudex/translit.py` (the engine's own
# table deciding whether the engine's rendering is «GOST» is the instrument
# judging itself).
TRANSLIT_TABLES: tuple[str, ...] = ("gost", "icao", "bgn")


@dataclass(frozen=True)
class FormVerdict:
    """`same` iff `differs` is empty. `differs` is a subset of
    `FORM_FEATURES[type]`: the report prints the SET («падеж и регистр»),
    never a bare «нет». A verdict with `same=True` and a non-empty `differs`,
    or the reverse, is a bug the comparator's own test refuses."""

    same: bool
    differs: frozenset[str]


class FormMatcher(Protocol):
    """`form_match(type, produced, reference)`. `type` is a key of
    FORM_FEATURES. `produced` and `reference` are strings of the SAME datum:
    IN hop — produced = the substitute the model read, reference = the
    source's surface; OUT hop — produced = the real value the consumer
    received, reference = the substitute exactly as the agent wrote it. A
    multi-field value arrives joined by `FIELD_SEP`. Pure, deterministic,
    no I/O, no `pseudex`; pymorphy3 IS allowed for `gram_case` (spec §8.4
    «по pymorphy3 голосованием») because it is a third-party dictionary, not
    the engine. Raises `ValueError` on a type without features."""

    def __call__(self, type: str, produced: str, reference: str) -> FormVerdict: ...


class FeatureExtractor(Protocol):
    """One feature of one string → one label of `FEATURE_LABELS[(type,
    feature)]`. The comparator registers one per (type, feature) in
    `FEATURE_EXTRACTORS: dict[tuple[str, str], FeatureExtractor]`, and its
    test asserts the dict's keys equal the pairs `FORM_FEATURES` enumerates."""

    def __call__(self, text: str) -> str: ...


class FeatureComparator(Protocol):
    """Do these two strings wear the same value of ONE lexeme-dependent
    feature. Registered in `form.FEATURE_COMPARATORS` for exactly the keys of
    `FORM_LEXEME_READINGS`, and consulted by `form_match` INSTEAD of comparing
    the two labels — never beside it, because two rules for one feature is how
    a difference comes to be counted twice. The extractor stays: the report's
    histogram still prints one label per string."""

    def __call__(self, produced: str, reference: str) -> bool: ...


# --- §4bis THE NEEDLE LAYER: one definition of «does this value survive in
#     this text» (round 4, H1.1) --------------------------------------------------------
#
# WHY THIS SECTION EXISTS AT ALL. Six of the lines below — `coverage`,
# `toolresult_masked`, `rag_masked`, `doc_masked`, `residual` and, through the
# OUT status, every form and value line — rest on ONE question: is this value,
# or an identifying piece of it, still standing in this text? Until round 4
# that question had THREE answers living in two files, and the WEAKEST of the
# three guarded the leak lines:
#
#   * `observe.needles_of` — notation-aware (digit signatures, date folds, word
#     stems, transliteration, initials);
#   * `observe.pieces_of` + `metrics._surviving_piece` — a plain folded
#     SUBSTRING test over parts that `parts_of` had already NORMALISED, so it
#     asked for a string that does not occur in the value itself;
#   * a per-caller guess at which part of a value a tool leaf holds.
#
# Each was measured, and each failed in the gateway's favour: `_surviving_piece`
# could not find a value in a text that IS the value for 12.7 % of the corpus's
# written surfaces (every PLATE, 88.6 % of SNILS, 84.6 % of CARD, 29.5 % of
# LOC); a LOC's only word needle was the four-character prefix of an
# ALPHABETICALLY SORTED blob, so 22.6 % of addresses carried a needle for the
# CITY and none for the street; and a substitute standing in a leaf the tool
# schema DECOMPOSES («address.building» = «79») matched no needle of the whole
# value, so that leaf read `unmasked` for ever — un-earnable by a right gateway
# and un-failable by a wrong one at once.
#
# THE SIX RULES, each pinned by a test of `test_observe.py`:
#
#   N1. A TEXT THAT IS THE VALUE CONTAINS IT. `survives(type, v, v)` is true
#       for every type. This is what a substring test over normalised parts
#       could not do, and it is the cheapest possible tripwire on the layer.
#   N2. A VALUE INSIDE A LONGER TEXT IS FOUND, in the shapes a MODEL writes it:
#       verbatim, declined (a word stem), renotated (a digit signature),
#       refolded (a date), transliterated, squeezed to initials, respaced.
#   N3. A PIECE IS TYPED, NEVER SPLIT BY A RULE WRITTEN FOR ANOTHER TYPE.
#       `IDENTIFYING_ROLES` says, per type, which roles of the value are
#       evidence it stood somewhere; `PIECE_MIN_CHARS` / `PIECE_MIN_DIGITS` say
#       how much of one is enough to identify rather than to coincide.
#   N4. A GENERIC WORD IS NOT AN IDENTIFYING PIECE. The settlement, the generic
#       street word, the mail domain, the grammatical gender belong to
#       everybody (`GENERIC_PIECE_ROLES`), and so does the address vocabulary
#       and every month name (`form_tables.GENERIC_WORDS`). A surviving
#       «улица», «дом» or «марта» is grammar, not a leak.
#   N5. THE CUSTOMER'S OWN RENDERINGS ARE EXEMPT THROUGH ONE PATH. Exactly one
#       parameter — `exempt` — carries them, and both readings pass their own
#       set through it: the residual side passes the stems of the customer's
#       real values, the leak side passes nothing (its needles are built from
#       the REAL value and every generic role is already gone by N4).
#   N6. A DECOMPOSED LEAF IS JUDGED BY ITS OWN ROLE. When a tool schema splits
#       a value across fields, the question asked of one leaf is about the part
#       that leaf holds (`PartSurvival`), never about needles of the whole
#       value — no needle of a whole address can live in «79».

# The shapes a value survives being rewritten in. Closed, because a metric
# that could not name the shape it matched on could not be argued with.
#   whole     — the surface itself, case- and ё-folded
#   stem      — the first `PIECE_MIN_CHARS` letters of one role, at a word start
#   digits    — the type's digit signature, inside one number run whatever its
#               separators
#   date      — the ISO fold of a date, whatever notation wrote it
#   initials  — «П.О.», the squeeze a model writes a name to
#   squeezed  — the surface with every separator dropped, for the one type
#               whose notation carries no other robust needle (see
#               SQUEEZED_TYPES)
NEEDLE_KINDS: tuple[str, ...] = pii_types.NEEDLE_KINDS

# WHAT A PIECE OF A VALUE IS, BY TYPE. The roles named here are the ones whose
# survival in free text is evidence that THIS value stood there; a role not
# named is either generic (N4) or too short to identify (a house number, a
# passport series — every street has a 79 and the leaf that holds one is judged
# by N6 instead).
IDENTIFYING_ROLES: dict[str, tuple[str, ...]] = pii_types.identifying_roles(pii_types.TYPE_REGISTRY)
# A plate carries no identifying role: every part `parts_of` reads off it is one
# to three characters — a letter, three digits, a letter pair, a region — so a
# plate has no piece that identifies on its own and the whole is matched instead,
# respacing included (SQUEEZED_TYPES). Leaving the tuple empty and saying why is
# the point: a silent absence read as «no needles» is how the fake plate came to
# be invisible to `residual` for three rounds.
# Roles that belong to EVERYBODY, so a needle built from one proves nothing
# about which value stood in a string: the settlement (a place reference every
# Russian city shares), the grammatical gender, the mail domain, the street's
# generic word. ONE list, where there used to be two that disagreed —
# `observe.EXEMPT_ROLES` (what is not a LEAK) left `domain` in while the
# comment beside it said a surviving «yandex.ru» is not a leak.
#
# IT DECIDES TWO THINGS AND THEY ARE THE SAME FACT READ TWICE. N4 says such a
# piece is not a leak; the OUT funnel says the engine LEFT IT TRUE on purpose
# (`pseudex/vault.py::_settlement_of`, «what the law does not protect stays
# true»), so a leaf whose role is here is `engine_kept` rather than `not_masked`
# when the mint record proves the engine was awake for that entity. And the
# corpus's own builders must not demand a hop there
# (`scenarios5.common.arg_hop`): a city inside an address cannot become
# `observed` by any correct gateway, and a REQUIRED hop on it is a promise no
# product can keep (g07, g01, g03, g04, g14).
GENERIC_PIECE_ROLES: frozenset[str] = frozenset({"city", "gender", "domain", "street_type"})

# --- the authorial leaf equivalence (SPIKE-Е, Е-6) ------------------------------------
#
# THE SAME DATUM UNDER TWO TOOL SCHEMAS IS ONE LEAF SEMANTICALLY, and the
# instrument used to miss it because it looked for the corpus's TOOL NAME. The
# corpus declares `courier_book.address.locality` and the agent writes
# `crm_upsert_contact.contact.address.city` in the same turn: the settlement
# crossed once and came back once, and the hop read `absent` (g08: 25 of the 30
# `absent` of the group). The reading was about the corpus's spelling of the
# leaf, not about the crossing.
#
# IT IS A TABLE AND NOT A MATCHER, deliberately. `actual_hops.py` warns that
# matching events by TOOL NAME «can tie a re-search, a second delivery, or data
# the agent had not been given to the wrong event»; the same warning applies to
# a guess off a path's spelling. Every class below is AUTHORED, closed, and
# grounded in the registry's own `FieldSpec.pii_type` / `.role` — the class key
# IS the role the members declare, so a member of another role is refused (see
# `equivalence_problems`). A class of one leaf folds nothing and is refused too.
#
# WHAT IS NOT HERE, AND WHY. `delivery_create_order.to_location.address` (the
# whole address) and `courier_book.address` (the container) are not folded into
# the parts: a whole is not a part, and counting a city leaf for an address leaf
# would credit a value the agent never carried. `crm_find_contact.query.phone`
# is not folded into `crm_upsert_contact.contact.phone`: both hold E.164 digits,
# but a LOOKUP and a WRITE are different acts, and the spike's own warning is
# about exactly that reading.
LEAF_EQUIVALENCE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("city", ("courier_book.address.locality",
              "crm_upsert_contact.contact.address.city",
              "crm_upsert_card.contact.address.city",
              "delivery_create_order.to_location.city")),
    ("street", ("courier_book.address.street",
                "crm_upsert_contact.contact.address.street",
                "crm_upsert_card.contact.address.street")),
    ("house", ("courier_book.address.building",
               "crm_upsert_contact.contact.address.house",
               "crm_upsert_card.contact.address.house")),
    ("flat", ("courier_book.address.sflat",
              "crm_upsert_contact.contact.address.flat",
              "crm_upsert_card.contact.address.flat")),
)
# `"tool.path"` → the class that folds it. A leaf in no class is equivalent to
# no other leaf and the observer reads it exactly as it always has.
LEAF_SEMANTICS: dict[str, str] = {leaf: name for name, leaves in LEAF_EQUIVALENCE
                                  for leaf in leaves}
# The FIRST leaf of each class — the canonical spelling the corpus keeps when a
# family reaches the same semantic leaf through two tool schemas (R22 forbids
# declaring both, so the builder must know which one to KEEP). The first member
# is `courier_book.address.*` in every landed class, and that order is the
# decision, not an accident of authoring: `courier_book` is the class's own
# READ tool, the others are WRITES into another CRM's spelling.
LEAF_CANONICAL: dict[str, str] = {name: leaves[0] for name, leaves in LEAF_EQUIVALENCE}


def semantic_leaf(tool: str, path: str) -> str:
    """The semantic leaf `(tool, path)` carries, or "" when it is in no class.

    "" and not the path itself on purpose: a caller that treated «no class» as
    a class of its own would fold every unknown leaf into one."""
    return LEAF_SEMANTICS.get(f"{tool}.{path}", "")


def is_canonical_leaf(tool: str, path: str) -> bool:
    """Whether `(tool, path)` is the FIRST leaf its class folds — the one the
    corpus KEEPS when a family reaches the same semantic leaf twice (R22). A
    leaf in no class is canonical of nothing and answers False."""
    name = semantic_leaf(tool, path)
    return name != "" and LEAF_CANONICAL[name] == f"{tool}.{path}"


def equivalent_leaves(tool: str, path: str) -> tuple[tuple[str, str], ...]:
    """Every OTHER `(tool, path)` that carries the same semantic leaf, in the
    table's own order. Empty for a leaf in no class — including the declared
    leaf itself, which the caller already holds and must not be handed back as
    its own alternative."""
    name = semantic_leaf(tool, path)
    if not name:
        return ()
    own = f"{tool}.{path}"
    out: list[tuple[str, str]] = []
    for group, leaves in LEAF_EQUIVALENCE:
        if group != name:
            continue
        for leaf in leaves:
            if leaf == own:
                continue
            other_tool, other_path = leaf.split(".", 1)
            out.append((other_tool, other_path))
    return tuple(out)


def equivalence_problems(spec_for: "Callable[[str, str], FieldSpec | None]",
                         table: Sequence[tuple[str, tuple[str, ...]]] | None = None) -> list[str]:
    """Every violation of the leaf-equivalence table, never the first one only.

    THE LOOKUP IS A PARAMETER, the shape `tools.registry_problems` uses and for
    the same reason: `tools` imports THIS module, so a checker that read
    `REGISTRY_V5` itself would close the cycle — and a rule that cannot be shown
    to fail is not a rule. `table` defaults to the landed one so the test can
    hand a deliberately broken copy and demand a red.

    WHAT IS CHECKED, and each clause is a way the table could lie: every member
    names a leaf the registry knows; a member appears in exactly one class (a
    leaf in two classes would make equivalence intransitive); every member
    declares the class's own role; every member of a class declares ONE pii_type
    (folding a LOC and a NAME leaf would let one value answer for another); and
    no class folds fewer than two leaves (a class of one proves nothing and
    would make `semantic_leaf` a lookup with no partner)."""
    problems: list[str] = []
    rows = LEAF_EQUIVALENCE if table is None else table
    seen: dict[str, str] = {}
    for name, leaves in rows:
        if len(leaves) < 2:
            problems.append(f"class {name!r} folds {len(leaves)} leaf — a class of one "
                            f"folds nothing")
        types: set[str] = set()
        for leaf in leaves:
            if "." not in leaf:
                problems.append(f"class {name!r}: {leaf!r} is not a «tool.path» pair")
                continue
            if leaf in seen:
                problems.append(f"class {name!r}: {leaf} is already in class {seen[leaf]!r}; "
                                f"equivalence would not be transitive")
                continue
            seen[leaf] = name
            tool, path = leaf.split(".", 1)
            try:
                spec = spec_for(tool, path)
            except Exception as error:  # noqa: BLE001 - the exception IS the verdict
                # A lookup that RAISES on an unknown tool (v4's `spec_for` indexes
                # its registry) says the same thing a None does: the table names
                # a leaf no tool carries, which is a typo in the table.
                problems.append(f"class {name!r}: {leaf} resolves to nothing ({error!r})")
                continue
            if spec is None:
                problems.append(f"class {name!r}: {leaf} is no argument leaf of {tool!r}")
                continue
            if spec.role != name:
                problems.append(f"class {name!r}: {leaf} declares role {spec.role!r}")
            types.add(spec.pii_type)
        if len(types) > 1:
            problems.append(f"class {name!r}: members carry several types {sorted(types)}")
    return problems
# A piece of a value short enough to stand inside an unrelated word is not
# evidence that the value was there. Four characters is v4's own floor in
# `residual` detection and the public harness's; a shorter one matched «Лев»
# inside «Лебедева» and attributed one person's answer span to another.
PIECE_MIN_CHARS: int = 4
# ...AND A RUSSIAN ENDING TAKES ONE OF THEM. A stem is a prefix that must
# survive declension, so for a word of exactly `PIECE_MIN_CHARS` letters the
# four-character prefix is the WHOLE word and «Анну» stops matching «Анна» — a
# four-letter given name written in another case read `unmasked`, and
# `residual` was blind to a fake standing in a tool argument for no reason but
# the length of the name. Three characters is the floor for those, and the
# floor on the WORD stays four: a three-letter word is too common to identify
# anybody, while the third letter of a four-letter one still does.
STEM_MIN_CHARS: int = 3
# The same floor for a digit signature: three digits occur in every order
# number in the corpus.
PIECE_MIN_DIGITS: int = 4
# Two letters is the shortest squeezed initials a needle may carry: one letter
# («П.») stands in front of a third of the Russian alphabet's worth of names.
MIN_INITIALS: int = 2
# «+7 999…» and «8 999…» are one number said twice, so the signature is the
# last ten digits — `pseudex.vault`'s own canonicalisation rule, arrived at
# here independently (this package never imports the engine).
PHONE_SIGNATURE_DIGITS: int = 10
# Types whose identity is a DIGIT SIGNATURE and never a spelling: the model
# reformats «+79990001122» as «8 999 000-11-22» and a letters-and-stems test
# finds nothing at all.
DIGIT_PIECE_TYPES: frozenset[str] = pii_types.digit_piece_types(pii_types.TYPE_REGISTRY)
# A date is neither: «14.03.1987» and «1987-03-14» share no substring at all.
DATE_PIECE_TYPES: frozenset[str] = pii_types.date_piece_types(pii_types.TYPE_REGISTRY)
# Types whose value a model rewrites in another ALPHABET or squeezes to
# initials. NAME only, and deliberately: `FORM_FEATURES` declares `script` and
# `initials` for NAME alone, and a transliterated STREET needle would fire on
# ordinary Latin text in an address field with no derived form present.
DERIVED_PIECE_TYPES: frozenset[str] = pii_types.derived_piece_types(pii_types.TYPE_REGISTRY)
# The one type matched with every separator dropped. A plate is a letter, three
# digits, a letter pair and a region: the four groups cannot form by accident
# across a word boundary, which is why the squeeze is safe HERE and is not
# offered to types whose squeeze would weld two neighbouring words into a
# needle. Without it a gateway that left the fake plate in the tool argument
# RESPACED was invisible to all 29 lines while the same fake written verbatim
# was caught — the critical-defect line defeated by inserting spaces.
SQUEEZED_TYPES: frozenset[str] = pii_types.squeezed_types(pii_types.TYPE_REGISTRY)

# --- THE ONE READING OF «IS THIS THE SAME VALUE» (SPIKE-Ж, Ж-1) ----------------
#
# ONE TABLE, AND EVERY QUESTION ABOUT A VALUE'S IDENTITY READS IT. The spike
# measured the same question answered by THREE copies — `metrics.value_matches`
# (byte equality with a LOC exception), `observe.part_matches` (digits / ISO /
# squeeze), `revise._same_value` (a third fold) — and which copy a hop got was
# decided by whether its `FieldSpec.role` was empty: `calendar_free.person`
# (NAME), `vehicle_check.plate` (PLATE) and `snils_verify.snils` (SNILS) all
# declare `role=''` and took the strict one. 24 PLATE and 9 NAME hops then read
# as the GATEWAY's miss on values the tool's own parser had ACCEPTED
# (`tools._vehicle_check_parse` strips spaces and upper-cases; the
# `_calendar_free_parse` takes one to three words in any order). Two copies are
# one drift away, and the third had already left.
#
# THE QUESTION IS NOTATION-TOLERANT ON PURPOSE. `observe.part_matches`'s own
# docstring states the doctrine — «the spacing is `form_hOUT`'s question, and
# charging the value line for it would make one defect two» — and the owner
# ruling for class Ж is the same doctrine one level up: the value line is
# notation-BLIND (it mirrors the agent's form and does not judge the tool's
# schema), while the field's declared notation stays an authoritative marker for
# the substitution on the OUT leg (`tools.LEAF_NOTATION`). So separators,
# spaces, case class, word order and the dotted notation the tool happens to
# want are NOT this table's business: only what makes two spellings ONE VALUE.
#
# A NAMED READING, NOT A LAMBDA, because a closed vocabulary is what a test can
# hold: `test_contracts` pins every value here to a reading the implementation
# declares and every type of `TYPES` to a row, and `test_spike_zh` pins that the
# three former copies answer alike on a shared pair set.
#
# WHY `PHONE` IS NOT THE NEEDLE RULE, and why «just call `part_matches`» would
# be wrong: the needle layer asks IDENTIFICATION — «did this value survive being
# rewritten», where the last ten digits are the signature that the rewrite left
# the number intact. A LEAF asks EQUALITY, and there `+1 916…` and `+7 916…`
# share those ten digits while being two different numbers. Hence a reading that
# carries the PREFIX CLASS beside them. This is the one place where the value
# line deliberately does NOT reduce to the needle layer, and the reason is
# written here rather than rediscovered (SPIKE-Ж, risk 3).
VALUE_READINGS: tuple[str, ...] = (
    "fold",         # case- and ё-folded text — the default
    "squeeze",      # every separator dropped (PLATE)
    "digits",       # the type IS its digits (SNILS / INN / CARD / PASSPORT)
    "phone",        # the last ten digits AND the prefix class (+7 ≡ 8 ≢ +1)
    "iso",          # the ISO fold of a date, whatever notation wrote it
    "name_parts",   # the parts as a MULTISET: «Евгений Вольнов» ≡ «вольнов евгений»
    "place_roles",  # the roles street / house / flat; the settlement is excluded
)
VALUE_NORMALISERS: dict[str, str] = {
    "NAME": "name_parts",
    "LOC": "place_roles",
    "PHONE": "phone",
    "EMAIL": "fold",
    "DOB": "iso",
    "DATE": "iso",
    "CARD": "digits",
    "SNILS": "digits",
    "INN": "digits",
    "PASSPORT": "digits",
    "PLATE": "squeeze",
}


@dataclass(frozen=True)
class Needle:
    """One shape of one value, and the role it is evidence for.

    `role` is "" for a needle built from the WHOLE value (`whole`, `squeezed`)
    and for `initials`, which spans the parts rather than naming one. It is the
    role's own name for `stem`, `digits` and `date`, so `Survival.pieces` can
    say WHICH piece survived and a caller can ask for one role alone (N6)."""

    kind: str                        # NEEDLE_KINDS
    role: str                        # a key of the value's parts, or ""
    text: str                        # what is looked for, folded where the kind folds


@dataclass(frozen=True)
class Survival:
    """The answer to N1–N5 for one (value, text) pair.

    `whole` — the value itself stands there. `pieces` — the roles whose
    identifying piece stands there. `spans` — where, in the text's own offsets,
    so a caller that needs positions (the answer alignment, «is another
    person's value standing where this one's is not») reads them from the same
    pass rather than running a second, different search."""

    whole: bool
    pieces: frozenset[str]
    spans: tuple[tuple[int, int], ...]

    @property
    def found(self) -> bool:
        return self.whole or bool(self.pieces)


class ValueNeedles(Protocol):
    """`needles_of(pii_type, surface, parts)` → the needles of one value.

    `parts` is the value's roles: the ones the CORPUS declared when the caller
    holds the item, the ones `parts_of` read off the surface when it holds only
    a string. The difference is not cosmetic — `parts_of` lumps every word of
    an address it cannot type into ONE alphabetically sorted `street` blob, so
    a declared «улица Клубная» in Ижевск yields the street, while the same
    address parsed from a comma-less surface yields «клубная ижевск». Both are
    split PER WORD here (N3), and the declared path additionally knows which
    word is the city and drops it (N4)."""

    def __call__(self, pii_type: str, surface: str,
                 parts: dict[str, str]) -> tuple[Needle, ...]: ...


class ValueSurvival(Protocol):
    """`survival(needles, text, exempt)` → `Survival`.

    IT TAKES THE NEEDLES, not the value, so the two readers of the layer meet
    in ONE search: the corpus's own item (whose roles are declared) and a bare
    substitute surface (whose roles are parsed) differ in how their needles are
    BUILT and in nothing else.

    `exempt` is the ONE path of N5: needle texts that prove nothing because
    another value of the same conversation already carries them. Nothing else
    filters, and no caller may pre-filter on its own — three filters is how the
    layer came to disagree with itself."""

    def __call__(self, needles: Sequence[Needle], text: str,
                 exempt: frozenset[str]) -> Survival: ...


class LeafSurvival(Protocol):
    """`leaf_holds(pii_type, surfaces, minted, real, text)` → does this
    ONE-VALUE tool leaf hold a piece of the SUBSTITUTE rather than the
    customer's own datum (N6)?

    Asked of a TOOL LEAF and never of free prose: a leaf is a short string the
    schema names for one part of one value, so «79» may be read there as a
    house number and could not be read that way in a sentence.
    `tools.expected_leaf_value` names the customer's own value for the leaf;
    this says whether what stands in it is that, the fake, or neither.
    `surfaces` are the spellings of the substitute the run recorded and
    `minted` its roles (`ArmRun.substitutes[item][1]`) — a spoken substitute
    has roles in the record that no splitter can read back off its surface."""

    def __call__(self, pii_type: str, surfaces: Sequence[str], minted: dict[str, str],
                 real: str, text: str) -> bool: ...


# --- §5 metrics (spec §4, §8.3) -------------------------------------------------------

@dataclass(frozen=True)
class Line:
    """One report line, x of n, exactly the public `score.Line`: a rate, an
    exact Clopper–Pearson interval, and — when x = n > 0 — what a flawless
    line CERTIFIES (`zero_failure_floor`), because 100% is not a number a
    finite sample can print. Rates are never stored; counters are."""

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
        if self.total and self.hits == self.total:
            return zero_failure_floor(self.total)
        return None


# What a metric counts over. `e` = one personal datum on one hop; the others
# are named as the spec's §8.3 table names them.
SCOPES: tuple[str, ...] = (
    "item", "hop", "result", "answer", "transition", "turn", "retry", "value",
    "substitute", "chunk", "identity", "document", "extracted", "leaf", "case",
    "negative", "observation", "level")
METRIC_FAMILIES: tuple[str, ...] = ("v4_level", "public", "v5_new")


@dataclass(frozen=True)
class MetricSpec:
    """The declaration of one metric: its name, what `hits` and `total` count
    (in the spec's own words, so a reviewer can diff the table against the
    code), its scope and family, whether it is DIAGNOSTIC (printed, never a
    success criterion) and whether it is a v4 paired level (printed by v4's
    report, not as a `Line`)."""

    name: str
    hits: str
    total: str
    scope: str                       # SCOPES
    family: str                      # METRIC_FAMILIES
    diagnostic: bool


# The v4 paired levels, kept as they are (spec §4.1). They are NOT Lines: each
# is I≈C beside C′≈C with a cluster-bootstrap CI, a TOST verdict at DELTA, the
# 1/n floor and `comparable`, printed by `bench.agentpii4.report.render` on
# `.base` cases. Listed so the checklist and the side-by-side can name them.
V4_LEVEL_NAMES: tuple[str, ...] = tuple(name for name, _label in V4_LEVELS)
# There is NO `V4_EXTRA_LINES` and no `SideBySide.v4_extra` (ruling R-35).
# v4 computes `v4_leak`, `v4_seed_coverage` and `v4_overmask` inside
# `bench.agentpii4.report.render` and exposes them through no function, so the
# only honest way to print them is to embed v4's own block byte for byte —
# which the v5 report does. Any second source of those three numbers would be a
# re-derivation, and two derivations that must agree are one drift away from a
# report contradicting itself on the same page.

METRICS: tuple[MetricSpec, ...] = (
    # §4.1 — the paired levels, by name only (see V4_LEVEL_NAMES)
    MetricSpec("action", "triples where I acted as C did", "comparable triples", "level", "v4_level", False),
    MetricSpec("tools", "triples with the same tool sequence", "comparable triples", "level", "v4_level", False),
    MetricSpec("keys", "triples with the same argument keys", "comparable triples", "level", "v4_level", False),
    MetricSpec("state", "triples with the same typed state", "comparable triples", "level", "v4_level", False),
    MetricSpec("values", "triples where the tool got the same VALUES", "comparable triples", "level", "v4_level", False),
    MetricSpec("verbatim", "triples where the values match byte for byte", "comparable triples", "level", "v4_level", False),
    # §4.2 — carried from the public harness. THE WORDING NAMES WHAT THE CODE
    # COUNTS, not what the public unit is: v5 counts a datum PER CROSSING (one
    # item read in a message and again in a tool result is two IN hops), while
    # the public harness counts it once per case. A spec that said «items»
    # while the code counted hops would be a denominator nobody could check.
    MetricSpec("leak", "IN hops the gateway ALTERED before the model saw them", "IN hops shown to the model (observed ∪ leaked; `absent` was shown to nobody)", "hop", "public", False),
    MetricSpec("coverage", "IN hops of which NO piece survived — by the span the gateway replaced where the value stood in a MESSAGE, by what the model read where it did not (a seed value stood in no message, so «was its span masked» is a question about nothing); city / generic word / marker are not PII", "IN hops shown to the model (observed ∪ leaked)", "hop", "public", False),
    MetricSpec("typed", "IN/tool and IN/document hops the gateway typed as the declared type (DOB and DATE are ONE answer)", "IN/tool and IN/document hops whose slot a replaced piece covers, so a type was exposed", "hop", "public", False),
    MetricSpec("round_trip", "OUT/tool_arg leaves the gateway RESTORED to the real value of THAT leaf (absolute, not paired); a leaf it never masked (`engine_kept` / `not_masked` / `leaf_foreign`) is a miss, and so is one the agent never wrote", "OUT/tool_arg leaves of items altered on the way in", "leaf", "public", False),
    MetricSpec("round_trip_repaired", "the same, counting a value that arrived REPAIRED (the same unmasked-and-`absent` misses)", "OUT/tool_arg leaves of items altered on the way in", "leaf", "public", True),
    MetricSpec("end_to_end", "declared OUT/tool_arg leaves the gateway RESTORED to the real value of THAT leaf — a leaf that carried no substitute (now `engine_kept` / `not_masked`) is a MISS, so a passthrough scores 0 here and not 100 (F1.3)", "all declared OUT/tool_arg leaves", "leaf", "public", False),
    # THE HONEST SHARE, BESIDE THE STRICT ONE AND NEVER INSTEAD OF IT (SPIKE-Е,
    # Е-3). The strict line is the protection against a passthrough and the
    # lesson of v4's D3; this one answers the question the strict denominator
    # buries — of the leaves the ENGINE had something to do on, how many came
    # back right. The two differ by the population and by NOTHING else: both
    # read `metrics.leaf_value_ok` (Е-7), so a reader may print them side by
    # side, and the strict line is printed FIRST (`report.beside_of`).
    MetricSpec("end_to_end_written", "declared OUT/tool_arg leaves of the RESTORABLE population the gateway restored to the real value of THAT leaf — the engine's honest share; the strict `end_to_end` is its headline and prints first", "declared OUT/tool_arg leaves with status observed / residual / leaf_foreign (`absent` is the agent's, `engine_kept` and `not_masked` had nothing to restore and are printed by `out_no_mint`)", "leaf", "public", False),
    MetricSpec("overmask", "negatives NOT altered", "all negatives", "negative", "public", False),
    MetricSpec("consistency", "items whose every mention carried ONE substitute", "items the model met in more than one PLACE — a distinct (`msg`, `result_seq`) pair, so a message is a place and so is EACH tool result; keying on `msg` alone made every result one place and left the population empty on the whole corpus", "item", "public", False),
    MetricSpec("stability", "items whose substitute did not change between requests", "items mentioned in more than one request", "item", "public", False),
    # NOT THE PUBLIC QUANTITIES, AND THE NAMES SAY SO (`_v5` / `_answer`).
    # `agentmask_ru.align.rewrite_ratio` is the share of characters changed
    # OUTSIDE the protected spans of the message the model reads, flagged over
    # 0.3; this line compares the gateway arm's REPLY with the control's and
    # flags a similarity below `REWRITE_RATIO_FLOOR`. The public
    # `unattributable` counts ITEMS with a tool parameter whose substitute the
    # alignment could not place; this line counts ANSWER SPANS carrying more
    # than one item. Two numbers under one name would be read as one.
    MetricSpec("rewrite_ratio_v5", "cases whose gateway-arm REPLY is a different text from the control's (not the public message-level ratio)", "cases with both replies", "case", "public", True),
    MetricSpec("shared_block_answer", "ANSWER spans the alignment could not assign to one item (not the public per-item `unattributable`)", "answer spans", "answer", "public", True),
    # §4.3 / §8.3 — new in v5
    # THE RESIDUE OF THIS LINE IS AN ENGINE FINDING AND THE SPEC SAYS SO. A
    # perfect gateway earns 10812/10812 on the values the customer WROTE and
    # 250/918 on the ones the customer DICTATED, because our engine shows a
    # WRITTEN fake for a spoken value and the IN form then cannot mirror its
    # source (`docs/known-issues.md` Б27, the voice track's work, not this
    # benchmark's). The `spoken` axis is where a reader sees that, so the
    # sub-100 figure is never read as an instrument defect.
    MetricSpec("form_hIN", "IN hops where form_match == same", "IN hops observed (not leaked); read on the `spoken` axis — the whole residue is dictated values against written substitutes (Б27), an ENGINE finding", "hop", "v5_new", False),
    MetricSpec("form_hOUT", "OUT hops where form_match == same", "OUT hops the agent WROTE (`contracts.OUT_HOP_WRITTEN_STATUSES`; `absent` is printed beside the line by `out_absent`, and the funnel's own counts by `out_written` / `out_no_mint`)", "hop", "v5_new", False),
    MetricSpec("out_absent", "declared OUT hops the agent never wrote", "all declared OUT hops", "hop", "v5_new", True),
    # THE FUNNEL PRINTED, COUNT BY COUNT. `unmasked` used to be one cell for
    # three facts and the report had no cell in which any of them was named:
    # these are the four statuses the split created plus the population they
    # were carved out of. They are DIAGNOSTIC the way `out_absent` is — a count
    # beside the line it explains, not a success criterion of its own.
    MetricSpec("out_written", "declared OUT hops the agent WROTE something in (`absent` is the only status outside) — the population `form_hOUT` counts and `out_absent` leaves out", "all declared OUT hops", "hop", "v5_new", True),
    MetricSpec("out_no_mint", "declared OUT hops the engine had NOTHING to restore on — `engine_kept` (a generic part left real on purpose, with the mint recorded) plus `not_masked` (the leaf already held the real value); what `end_to_end_written` subtracts, printed as one count", "all declared OUT hops", "hop", "v5_new", True),
    MetricSpec("out_engine_kept", "declared OUT hops where the engine DELIBERATELY left the real value: a generic role (settlement / generic word / domain / gender) and the mint record proves it was awake", "all declared OUT hops", "hop", "v5_new", True),
    MetricSpec("out_not_masked", "declared OUT hops where the leaf already held the real value and no substitute was minted for it (a passthrough, or a leaf naming no generic role)", "all declared OUT hops", "hop", "v5_new", True),
    MetricSpec("out_leaf_foreign", "declared OUT hops where a THIRD value stands: neither this datum's substitute nor its real value — invisible to `form_match` (`produced == reference`, no verdict)", "all declared OUT hops", "hop", "v5_new", True),
    MetricSpec("toolresult_masked", "declared tool results where no real value reached the model", "results the case DECLARES personal data in (`returns[].result_item_ids`) and the agent obtained", "result", "v5_new", False),
    MetricSpec("answer_real", "answers where every REQUIRED datum is the real value — any inflection of the part(s) the answer names — in the agent's form, and no substitute is left anywhere in the reply", "answers the case declares a REQUIRED OUT/answer hop for; an answer with nothing to require is outside it and counted by `answer_optional_only`", "answer", "v5_new", False),
    # THE V4 DISEASE, CAUGHT IN A NEW PLACE (J1.1). `all([])` is True, and 720
    # of the 1357 answers the corpus declares an answer hop for declare no
    # REQUIRED one — so a full passthrough scored 53.1% on the line named «the
    # answer carries the real value». An answer with nothing to require is
    # outside the denominator, and the count is PRINTED beside the line rather
    # than left implicit, because a denominator that quietly shrank is the
    # defect this pair exists to make visible. DIAGNOSTIC because no gateway
    # can move it: it counts what the CORPUS obliges, fixed before any arm
    # runs, so it is the caption of `answer_real`'s rate and never a result of
    # its own.
    MetricSpec("answer_optional_only", "answers whose case declares answer hops and obliges NONE of them — what `answer_real`'s denominator leaves out", "answers the case declares an OUT/answer hop for", "answer", "v5_new", True),
    MetricSpec("chain_value", "A→B transitions where the real value in B equals the real value from A", "all A→B transitions", "transition", "v5_new", False),
    MetricSpec("chain_form", "A→B transitions with form_match == same on OUT(B)", "all A→B transitions", "transition", "v5_new", False),
    MetricSpec("chain_value_written", "the same, over the transitions whose OUT(B) leaf is RESTORABLE — the hand-over the engine was asked to perform", "A→B transitions with a restorable OUT(B) leaf (observed / residual / leaf_foreign)", "transition", "v5_new", False),
    MetricSpec("chain_form_written", "the same, the FORM question", "A→B transitions with a restorable OUT(B) leaf", "transition", "v5_new", False),
    MetricSpec("multi_all_out", "turns where EVERY OUT argument is right in value and form", "turns with N ≥ 2 OUT hops", "turn", "v5_new", False),
    # THE SAME TURNS, THE HONEST POPULATION (SPIKE-Е witness g02: 55 of 56
    # multi-hop turns had NEITHER leaf written, and the strict line printed
    # 0/56 — a fact about the scene, read as a defect of the engine). A turn in
    # which nothing was restorable is outside this denominator; a turn with one
    # restorable leaf is judged on that leaf. The strict line still counts the
    # turn nobody wrote as a miss.
    MetricSpec("multi_all_out_written", "turns where EVERY RESTORABLE OUT argument is right in value and form (a turn with nothing restorable is outside the denominator)", "turns with N ≥ 2 declared non-optional OUT hops and ≥ 1 restorable leaf", "turn", "v5_new", False),
    MetricSpec("multi_consistency", "turns where one value → one substitute across all its calls", "turns with N ≥ 2 calls", "turn", "v5_new", False),
    MetricSpec("retry_form", "retries where OUT form matched the agent's form on EVERY attempt", "retries of one tool", "retry", "v5_new", False),
    MetricSpec("memory_consistency", "values a `MemorySpec` names, mentioned in > 1 turn with ONE substitute", "values a `MemorySpec` names", "value", "v5_new", False),
    # `memory_stability` WAS HERE AND IS REMOVED (J1.2). Its population was
    # «substitutes of `MemorySpec` values seen in > 1 request», and it is
    # EMPTY BY CONSTRUCTION, not by accident: a `MentionRecord` is written
    # once per message, when the message is first pushed (`harness.
    # GatewayV5._note_message_mentions`), and a `MemorySpec` recall is
    # anaphoric — «ему», «на тот адрес» — so the value is spelled in exactly
    # one message and read in exactly one request. Measured over the whole
    # corpus with the perfect-gateway probe: all 619 memory specs have their
    # mentions in ONE request (and in ONE place, so a `places` variant is
    # empty too), the line printed 0/0, and not one of the 23 wrong gateways
    # could move it. The two repairs available were both dead ends: a real
    # per-request record is the harness's to write and would say what
    # `stability` already says of every item; a per-PLACE population is
    # `memory_consistency` (619/619, moved by WG23) under a second name. H1.4's
    # rule decides it — «a public line that can only print «н/п» is worse than
    # no line» — so the line is gone rather than shipped unearnable.
    MetricSpec("rag_masked", "declared chunks where no real value reached the model; a declared value the chunk rendered UNTAGGED is a miss", "chunks the case DECLARES personal data in (`RagSpec.chunk_ids`) and the retriever returned", "chunk", "v5_new", False),
    MetricSpec("rag_identity_kept", "foreign identities in chunks kept apart from the customer", "foreign identities in chunks", "identity", "v5_new", False),
    MetricSpec("doc_masked", "documents where every real value was masked, UNTAGGED ones included", "documents the agent actually read (one the read never reached is outside it, the way an absent result is)", "document", "v5_new", False),
    MetricSpec("doc_extracted", "extracted items that reached the tool as the REAL value", "extracted items the case DECLARES an OUT hop into `extract_to_tool` for; an item it asks nobody to carry is outside the denominator rather than a forced miss", "extracted", "v5_new", False),
    MetricSpec("residual", "answers and argument leaves WITHOUT a substitute in them", "all answers, and every OUT leaf the agent WROTE (`absent` is neither)", "leaf", "v5_new", False),
    # THE STREAMING LEG, WHICH NOTHING READ. `ArmRunV5.stream_mismatch` was
    # written by the harness on all 84 streaming cases and consumed by no
    # metric and no report line, so the one defect the leg exists to catch —
    # the chunked restoration differing from the whole-text one — could not
    # appear anywhere. A field nobody reads is a measurement nobody made.
    MetricSpec("stream_fidelity", "streaming cases whose chunked restoration equals the whole-text one", "streaming cases", "case", "v5_new", False),
)
METRIC_NAMES: tuple[str, ...] = tuple(spec.name for spec in METRICS)
V5_NEW_METRIC_NAMES: tuple[str, ...] = tuple(spec.name for spec in METRICS if spec.family == "v5_new")
PUBLIC_METRIC_NAMES: tuple[str, ...] = tuple(spec.name for spec in METRICS if spec.family == "public")
DIAGNOSTIC_METRIC_NAMES: tuple[str, ...] = tuple(spec.name for spec in METRICS if spec.diagnostic)
# Slices the report prints for every Line (spec §4.2 «срезы», §4.3
# «агрегаты»). One axis at a time, never two crossed — the public rule, for
# the same reason (cells of eight items have intervals wider than any
# difference worth reading).
# `spoken` IS A HOP AXIS AND IT EXISTS FOR ONE READING (J1.3, Б27). A perfect
# gateway prints `form_hIN` 94.31% and every point of the residue is a value
# the customer DICTATED against the WRITTEN substitute the engine mints for it:
# written 10812/10812, spoken 250/918. Without the slice the caption reads as
# an instrument defect and somebody goes looking for the bug; with it the
# number names the engine finding it is. The bucket is `PiiItem.spoken` — what
# the corpus says about the SOURCE, never a guess off the surface.
AXES: tuple[str, ...] = (
    "register", "name_tier", "cue", "family", "behaviour", "vertical", "hop_owner", "pii_type",
    "return_form", "spoken")

# --- the REFUSE-TO-REPORT gate (spec §4.4, §8.3) --------------------------------------
# The discipline of `e2e/audit_gates.py`: a check that cannot go red is
# decorative. Every metric ships THREE fixtures — one on which it MUST be 0/n
# (`zero`), one on which it MUST be n/n (`one`), and one built to fool it
# (`adversarial`, with the exact hits/total it must print). A metric missing a
# kind, or whose fixture prints another fraction than the one it declares, is
# NOT PRINTED — its name goes to `refused` with the reason — and a report with
# any refused non-diagnostic metric carries the word «НЕПОЛНЫЙ» in its header.
# Not printing is the only sanction that survives a deadline.
#
# THERE IS NO SEPARATION CONSTANT (R-55). It read «rate(one) − rate(zero) ≥
# 1.0» after `Fixture.expected_hits`/`expected_total` had already pinned the
# two rates at exactly 0/n and n/n, so the comparison could not fire on its
# own; and the 0/0 pair it was kept for is refused one check earlier by
# `test_fixtures.test_kind_invariants` («zero is 0 of n > 0»). A check that
# cannot go red is decoration in the one place of v5 that decides whether
# numbers are printed at all.
FIXTURE_KINDS: tuple[str, ...] = ("zero", "one", "adversarial")
INCOMPLETE_REPORT_MARK: str = "НЕПОЛНЫЙ"


@dataclass(frozen=True)
class Fixture:
    """One can-fail fixture of one metric. `input` is a tuple of
    `RunObservation` built by hand in `fixtures.py` (never by running an
    agent); `expected_hits`/`expected_total` are what the metric MUST return
    on it. For `zero`: expected_hits == 0 < expected_total; for `one`:
    expected_hits == expected_total > 0; for `adversarial`: whatever the
    trap yields when the metric is right, and the fixture's docstring says
    what a wrong metric would print instead."""

    metric: str
    name: str
    kind: str                        # FIXTURE_KINDS
    input: tuple["RunObservation", ...]
    expected_hits: int
    expected_total: int


@dataclass(frozen=True)
class GateVerdict:
    """The gate's answer for one metric. `printable` iff all three kinds exist,
    each prints its expected fraction, and zero/one separate. `why` is empty
    when printable and names the failing fixture otherwise."""

    metric: str
    printable: bool
    why: str


class Metric(Protocol):
    """Every metric is a pure function from observations to ONE Line named as
    its `MetricSpec.name`. It must not read the engine, the corpus file or the
    network; everything it needs is on the observations."""

    def __call__(self, observations: Sequence["RunObservation"]) -> Line: ...


class MetricGate(Protocol):
    """`gate(metric_fn, fixtures) -> GateVerdict`. Runs each fixture through
    the metric and compares; never raises on a wrong metric — a wrong metric
    is the finding."""

    def __call__(self, metric: Metric, fixtures: Sequence[Fixture]) -> GateVerdict: ...


# --- what the metrics READ: observations the harness records ----------------------------

@dataclass(frozen=True)
class MentionRecord:
    """Every time the model read a substitute for an item: which message (or
    which tool result, by `result_seq`) and what it read. `memory_consistency`
    and `multi_consistency` count DISTINCT substitutes per item from these."""

    item_id: str
    msg: int                         # message index; -1 for a tool result
    result_seq: int                  # CallLog.seq of the result; -1 for a message
    substitute: str
    request_index: int               # the model request that carried it (for stability)


# THE SLOT-TAG CONVENTION. v4's mock tags result slots with private names
# («r_name», «c0_phone») that nothing outside the mock can map to an item. A
# v5 mock (`BackendV5`) tags every slot that renders a SEED item's value with
# that item's id, and the echoed value of a `ForcedError` with
# `ECHO_TAG_PREFIX + item id`; a slot that renders a value the case does not
# label (a slot time, an order id) carries no tag. The observer resolves an
# IN/tool hop by `spans_real[item_id]` and nothing else. ONE tag per item per
# result — the FIRST rendering (an account statement prints the holder on every
# row); leak checks (`toolresult_masked`) read the whole text, so a second
# rendering can never hide a leak, and no metric counts occurrences.
ECHO_TAG_PREFIX: str = "echo:"


@dataclass(frozen=True)
class ToolResultRecord:
    """One tool result as the mock produced it and as the model read it. v4's
    `ArmRun` does not carry these (the gateway kept them as `score.Masked` and
    the record dropped them), which is exactly why v4 could not score the
    IN/tool hop. `spans_real` are the mock's slot offsets (`CallLog.result_
    spans`, tag → span in `text_real`); `pieces` are the gateway's replaced
    spans in `text_real` with the substitute each got. `forced` marks a
    scripted `error_with_value`."""

    tool_name: str
    seq: int
    call_ordinal: int
    turn: int
    return_form: str
    text_real: str
    text_masked: str
    spans_real: dict[str, tuple[int, int]]           # item id (or ECHO_TAG_PREFIX + item id) → span in text_real
    pieces: tuple[tuple[int, int, str, str], ...]   # (start, end, substitute, engine_type)
    forced: bool


@dataclass(frozen=True)
class AnswerSpan:
    """One replaced span of the final reply: where the substitute stood in
    the reply AS THE MODEL WROTE IT (`raw`) and where the real value stands in
    the reply AS THE CUSTOMER READS IT (`restored`). Derived by the observer
    from `reply_raw` vs `reply` with a pure sequence alignment (difflib
    opcodes), never by the engine: an OUT/answer hop exists for every raw
    span that contains a substitute the run minted. NOT persisted in the arms
    file — the observer derives it on every read; a stored copy would be a
    second value that could drift from `reply_raw` (ruling 2026-09-22)."""

    item_id: str
    raw_start: int
    raw_end: int
    restored_start: int
    restored_end: int


# THE MODEL'S OWN CHRONOLOGY (Codex contract, 2026-09-27). `request_count` is
# «how many pushes the connector made» and it stays exactly that — a historical
# number is never reinterpreted by a later reader. `ModelTrace` is the ADDITIVE
# record of what the PROVIDER actually returned: one `ModelResponse` per
# completed provider response, in order, each carrying the request ordinal the
# arm saw, the user turn it answered, how many tool results were ALREADY
# available to it, the raw text it wrote and that text restored through the
# gateway's current state. `call_requests` maps each ACCEPTED tool call, in call
# order, to the `request` of the response that emitted it — the fact
# `request_index` cannot express, because two tool calls of ONE response execute
# sequentially while the second's result was NOT visible to the response that
# asked for both.
#
# None means «this connector never called the `response` hook» (Claude, the
# legacy paths, a perfect simulation), NEVER «no model was asked». A connector
# that does not call `response` gets None rather than a manufactured per-call
# model request: a guess would put a chronology in the record that nobody
# observed, which is the defect class this instrument exists to avoid.
MODEL_TRACE_FORMAT: int = 1


@dataclass(frozen=True)
class ModelResponse:
    """One COMPLETED provider response of the model loop.

    `available_results` is the count of accepted tool calls BEFORE this
    response's OWN function calls are processed, so two calls of one response
    both read 0 and the NEXT response reads 2. `raw`/`restored` are the
    response's text as the provider wrote it and as the gateway's CURRENT state
    restores it; an empty `raw` is a real observation (a pure tool-call turn),
    which is why the hook fires even when the text is empty.
    """

    request: int
    turn: int
    available_results: int
    raw: str
    restored: str


@dataclass(frozen=True)
class ModelTrace:
    """The provider chronology of one arm. `len(call_requests) == len(calls)`:
    every accepted call is mapped to the response that emitted it, in order."""

    responses: tuple[ModelResponse, ...]
    call_requests: tuple[int, ...]


@dataclass(frozen=True)
class ArmRunV5:
    """v4 `ArmRun` + what the IN/tool, OUT/answer, memory and RAG questions
    need. Written by `harness.py` for the I arm only (C and C′ carry the v4
    record and nothing else — a control has no substitutes to observe).
    `reply_raw` is the reply with substitutes still in it; `calls` on `base`
    already carry `written` (substitutes) and `restored` (real) per leaf."""

    base: ArmRun
    reply_raw: str
    # The C arm's final reply of the SAME triple, copied here by the harness
    # (it runs all three arms and is the only place that holds both). Without
    # it `rewrite_ratio` would print Line(0, 0) on every run — a diagnostic
    # that can never fire is decorative, and the gate would refuse it anyway.
    control_reply: str
    tool_results: tuple[ToolResultRecord, ...]
    mentions: tuple[MentionRecord, ...]
    # THE JUDGE SEES THE AGENT'S OWN EARLIER WORDS (ruling R-40). One RESTORED
    # reply per turn, in turn order, as the harness collected them; `""` for a
    # turn the agent answered with no text, and a tuple shorter than the
    # dialogue for an arm that died mid-run. `judge.dialogue_context` emits
    # them as `role="assistant"` turns, so question 4 («учёл ли контекст») on
    # `memory_anaphora` / `user_in_loop` is judged against what the agent
    # actually said rather than against the user's messages alone — the judge
    # was otherwise asked whether a reply used context it was never shown.
    # RESTORED, never raw: the judge must not see a substitute (spec §5), and a
    # raw turn would put one in front of it. The LAST non-empty entry is the
    # final answer, which the judge gets as EVIDENCE in its own section; the
    # dialogue leaves it out so the answer is not quoted to the judge twice.
    turn_replies: tuple[str, ...]
    call_turns: tuple[int, ...]      # the turn each call in base.calls happened in, same order
    request_count: int               # model requests the arm made (for `stability`)
    # `streaming` cases only: the reply restored chunk by chunk through the
    # sidecar's stream contract differed from the whole-text restoration — a
    # product defect of the streaming leg, counted apart, never folded into
    # the form lines (spec §3.7). False for non-streaming cases.
    stream_mismatch: bool
    # THE OTHER HALF OF `stream_mismatch` (R-47). The run is SCORED on the
    # chunked restoration — the text the streaming customer actually reads —
    # and this is the whole-text restoration of the same reply, kept beside it
    # so `stream_fidelity` names a disagreement a reader can then look at. ""
    # on a non-streaming case: there the two restorations are one string, and
    # storing it twice would invite a reader to compare a field with itself.
    reply_whole: str
    # How many of the agent's EARLIER turns still carried a minted substitute
    # when the judge's prompt was built (`harness.masked_dialogue`) — the
    # defect `residual` counts in the answer, one turn sooner. It lived on the
    # triple row alone, where no metric could read it, so a substitute the
    # customer saw in turn 2 and not in the final answer was counted nowhere;
    # `residual` now takes `> 0` as a miss of the observation.
    turn_residual: int
    # THE MODEL'S CHRONOLOGY, additive and explicit (see `ModelTrace`). It has
    # NO default: every constructor states whether it observed the provider, so
    # a path that forgot the field fails at construction instead of silently
    # writing `None` and looking like «the connector has no chronology».
    model_trace: ModelTrace | None
    # OD-76 / TZ §14.3: the MESSAGE-span replacements with the engine's type
    # label — the IN/user analogue of `ToolResultRecord.pieces`, which carry
    # the same four fields for a TOOL RESULT's spans. Written ONLY on a run with
    # a v6 case; empty (and omitted from the record) otherwise, so the
    # old-corpus replay stays byte-identical and `typed_user` prints «н/п»
    # (0/0) rather than a fabricated zero. Each entry is
    # (msg index, start, end, engine_type) in the ORIGINAL message's offsets.
    #
    # BOTH FIELDS STAY (SPEC §2.1 C02 keep_v5 + adopt_v6, and the S2 rows' own
    # cross-row dependency): `model_trace` is v5's field with NO default — S2's
    # `test_judge` calls `ArmRunV5(..., model_trace=None)` and would raise
    # TypeError without it — and `message_pieces` is v6's, defaulted so the 834
    # old-corpus constructors that never heard of it keep building the same
    # record. `message_pieces` is last on purpose: a defaulted field may not
    # precede an undefaulted one in a dataclass.
    message_pieces: tuple[tuple[int, int, int, str], ...] = ()


@dataclass(frozen=True)
class HopObservation:
    """One declared (or extra) hop as the run performed it. `declared` is
    False for a crossing the agent made that the case did not declare — an
    extra call; it is observed (it is a real crossing of real data) but
    counts in `form_h*` only, never in `chain_*` / `multi_*` whose
    denominators are declared hops.

    `status` IS ONE FACT, NEVER THREE. The OUT leaf funnel of
    `observe._out_status` answers a single question at a time and the ORDER of
    its branches is the contract:

    * `observed` — the leaf carried the substitute and the engine restored the
      real value of THAT leaf (the compared, earnable state).
    * `residual` — the leaf carried the substitute and the substitute is still
      there: a fake reached the consumer (counted by `residual`).
    * `engine_kept` — the leaf does NOT carry the substitute, it carries the
      CORRECT real value, its role is generic (`GENERIC_PIECE_ROLES`) and the
      run's mint record proves the engine was awake for this entity: the
      settlement inside an address, the generic street word, the mail domain,
      the gender. `pseudex/vault.py::_settlement_of` leaves those real BY
      PRODUCT DECISION — «what the law does not protect stays true» — so this
      is the engine working, and it is a MISS nowhere.
    * `not_masked` — the same shape WITHOUT that proof: the agent wrote the
      real value because the gateway never minted a substitute (a passthrough),
      or the leaf names no generic role. There was nothing to restore.
    * `leaf_foreign` — a THIRD value stands in the leaf: neither this datum's
      substitute nor its real value. `form_match` cannot see it (`verdict` is
      None, `produced == reference`), so before the split it was invisible.
    * `absent` — the agent wrote NOTHING at the leaf: a required hop inside a
      made call whose slot is empty, or a call the case declared and the agent
      never made. A fact about the AGENT, counted by `out_absent`.
    * `leaked`, `unmasked` — IN hops and the ANSWER leg, unchanged. `unmasked`
      is still EMITTED by `_out_answer` (the reply held the real value because
      the gateway never minted) and is still READ off every artifact on disk:
      `records.py` checks this vocabulary on READ, so removing it would take a
      saved replay down three weeks after the run that cost the money.

    `verdict` is set iff status == "observed".

    WHY `not_masked` IS NOT `observed`. When the gateway missed the value on
    the way IN, the agent writes the REAL value, the engine restores nothing,
    and `produced == reference` — so `form_match` said «same» and a gateway that
    masked NOTHING printed 100% on `form_hOUT`, `chain_form`, `chain_value` and
    `multi_all_out`. The hop happened; there was simply no substitute in it, and
    a comparison of a string with itself is not evidence about the product."""

    case_id: str
    repeat: int
    hop: Hop
    declared: bool
    pii_type: str
    produced: str
    reference: str
    status: str                      # HOP_STATUSES
    verdict: FormVerdict | None


# EVERY STATUS THE OBSERVER MAY EMIT, and the closed vocabulary a saved row is
# READ against. The OUT funnel no longer emits `unmasked` (the three facts it
# hid are `engine_kept` / `not_masked` / `leaf_foreign` now); the answer leg
# still does, and so does every artifact written before this round.
HOP_STATUSES: tuple[str, ...] = ("observed", "leaked", "residual", "unmasked", "absent",
                                 "engine_kept", "not_masked", "leaf_foreign")
# THE LEAVES THE AGENT WROTE SOMETHING IN: what `form_hOUT` counts, and what
# `absent` is not. `residual` belongs here and used to be left out of that line
# only because the old funnel spelled the pair from the other end («observed ∪
# unmasked»); a leaf holding a fake the agent wrote IS written, and leaving it
# out let the one state where a fake reached the customer's tool be the one
# state the form line did not judge.
OUT_HOP_WRITTEN_STATUSES: frozenset[str] = frozenset({
    "observed", "residual", "engine_kept", "not_masked", "leaf_foreign"})
# THE LEAVES THE ENGINE HAD SOMETHING TO DO ON — the honest denominator of
# `end_to_end_written` and its siblings. `observed`/`residual` put a substitute
# in the agent's hand, so the restoration was the engine's to perform;
# `leaf_foreign` says a third value arrived where a datum was at stake, which is
# a failure the strict line counts and a denominator that dropped it would hide.
# `engine_kept` (nothing to restore) and `not_masked` (the leaf already held the
# real value) are OUT: counting either would let a gateway that protected
# nothing earn a share of the round trip, and both are printed beside the line
# as counts (`out_engine_kept`, `out_not_masked`, `out_no_mint`).
OUT_HOP_RESTORABLE_STATUSES: frozenset[str] = frozenset({
    "observed", "residual", "leaf_foreign"})


@dataclass(frozen=True)
class RunObservation:
    """Everything the metrics read about ONE (case, repeat) of the gateway
    arm, built by `observe.py` from a `CaseV5` and an `ArmRunV5` — and by
    hand in `fixtures.py`. The v4 paired verdicts ride beside it so the
    side-by-side needs one object per triple."""

    case: CaseV5
    repeat: int
    hops: tuple[HopObservation, ...]
    run: ArmRunV5
    ic: PairVerdict | None           # None on fixtures and on excluded triples
    cc: PairVerdict | None


class Observer(Protocol):
    """`observe(case, run) -> RunObservation` (metrics component,
    `observe.py`). Pure: reads the case's declared hops and the run's
    records, decides each hop's status and calls `form_match`. The alignment
    rules it must follow are on the dataclasses above and in
    `briefs/metrics.md`."""

    def __call__(self, case: CaseV5, run: ArmRunV5, ic: PairVerdict | None,
                 cc: PairVerdict | None) -> RunObservation: ...


# --- §6 the judge (spec §5, §8.5) ----------------------------------------------------

JUDGE_LABELS: tuple[str, ...] = ("верно", "частично", "неверно", "выдумал")
# Owner's decision: Sonnet judges, Haiku holds the dialogue. The ids are what
# the harness passes to the SDK; a run prints both in its header.
JUDGE_MODEL: str = "claude-sonnet-5"   # Claude 5 ids carry no date; this IS the canonical id
# Haiku 4.5's dated id is the canonical one the SDK resolves; the bare alias moved
# under our feet once already (bench/agentpii3/live/judge.py pins a sonnet-4-6
# id nobody meant to keep).
AGENT_MODEL: str = "claude-haiku-4-5-20251001"
JUDGED_BY: tuple[str, ...] = ("residual_gate", "model", "none")


@dataclass(frozen=True)
class DialogueTurn:
    """One turn of the dialogue AS THE CUSTOMER WOULD SEE IT: user text as
    written, tool results RESTORED (real values), assistant text RESTORED.
    The judge never sees a substitute (spec §5 «не видит подмен»)."""

    role: str                        # "user" | "assistant" | "tool"
    text: str


@dataclass(frozen=True)
class JudgeInput:
    """What the judge reads (spec §8.5 «Что судья видит»): the RESTORED
    answer, the real oracle literals, the dialogue context — and nothing
    about form, which is `form_hOUT` on the answer owner. `oracle_literals`
    are the real values the answer is expected to be about (the customer's
    own values + the tool result's values), so the judge can tell «matched
    the right record» from «invented one»."""

    case_id: str
    restored_answer: str
    oracle_literals: tuple[str, ...]
    dialogue_context: tuple[DialogueTurn, ...]
    customer_question: str


@dataclass(frozen=True)
class JudgeVerdict:
    """One of JUDGE_LABELS with a reason that QUOTES the answer (v3's rule: a
    verdict without a quote that stands in the text is discarded, not
    counted). `judged_by == "residual_gate"` marks a `неверно` decided before
    the model was asked. `judged_by == "none"` ⇔ `label == ""`: no quote stood
    in the text, the answer is NOT counted, and a reader refuses any other
    combination (a non-empty label beside «none» would be a verdict that
    counts and does not count at once)."""

    label: str                       # JUDGE_LABELS, or "" iff judged_by == "none"
    reason: str
    judged_by: str                   # JUDGED_BY
    cost_usd: float


@dataclass(frozen=True)
class JudgeRow:
    """One line of `<run>.judge.jsonl`: the verdict plus WHAT it judged. The
    protocol returns a verdict and nothing else; the file needs the answer the
    verdict is about, and `input_sha256` (of the JudgeInput as `build_prompt`
    fed it) is what makes a re-judged run comparable to the previous one — the
    same answer judged under a different prompt is a different measurement,
    and the hash is the only evidence of that on disk. Normative here (ruling
    2026-09-22); `records.py` reads and writes it."""

    case_id: str
    repeat: int
    input_sha256: str
    verdict: JudgeVerdict


class ResidualPregate(Protocol):
    """`residual_pregate(restored_answer, substitutes_minted) -> JudgeVerdict
    | None`: if any minted substitute still stands in the restored answer, the
    answer is `неверно` with `judged_by="residual_gate"` and the judge is NOT
    asked (spec §5, §8.5). None means «ask the judge».

    «STANDS» IS THE NEEDLE LAYER OF §4bis AND NOTHING ELSE — the same rule
    `residual` counts, asked through `observe.survival`, so the two halves of
    one question cannot disagree. A gate with a reading of its own (whole
    surfaces plus whole words of them) let a declined name, a renotated phone
    and a respaced card reach the judge while `residual` called each a
    critical defect, and a judge reading our fake is not the blind judge §8.5
    promises."""

    def __call__(self, restored_answer: str, substitutes_minted: tuple[str, ...]) -> JudgeVerdict | None: ...


class Judge(Protocol):
    """The model call. Blind to substitutes by construction (JudgeInput has no
    field for them); budgeted by the v4 `SpendLedger` at `QUERY_CAP_USD` per
    query; retried `RETRIES` times; a verdict whose quote does not stand in
    `restored_answer` is retried once with a stricter instruction and then
    recorded as `judged_by="none"`."""

    async def __call__(self, request: JudgeInput) -> JudgeVerdict: ...


QUERY_CAP_USD: float = 0.20
RETRIES: int = 2


@dataclass(frozen=True)
class CalibrationRecord:
    """One row of the calibration file (spec §8.5): a judged answer beside a
    human label. `repeat_index` is 0..K-1 for the stability sub-sample and 0
    otherwise. `prompt_sha256` pins the prompt the verdict came from, so a
    prompt edit invalidates the calibration mechanically."""

    sample_id: str
    case_id: str
    pii_types: tuple[str, ...]
    family: str
    register: str
    holdout: bool
    human_label: str                 # JUDGE_LABELS
    judge_label: str                 # JUDGE_LABELS | "none"
    judge_reason: str
    repeat_index: int
    judge_model: str
    prompt_sha256: str


@dataclass(frozen=True)
class CalibrationThresholds:
    sample_size: int
    per_stratum_min: int
    holdout_share: float
    raw_agreement_min: float
    kappa_min: float
    per_type_min_examples: int
    repeats: int
    repeat_sample: int
    max_repeat_disagreement: float
    recalibrate_on_corpus_change: float


CALIBRATION: CalibrationThresholds = CalibrationThresholds(
    sample_size=300, per_stratum_min=20, holdout_share=0.20, raw_agreement_min=0.85,
    kappa_min=0.70, per_type_min_examples=20, repeats=3, repeat_sample=50,
    max_repeat_disagreement=0.10, recalibrate_on_corpus_change=0.20)


@dataclass(frozen=True)
class CalibrationStamp:
    """What a report prints about the judge it used. `calibrated` is False
    until every threshold in CALIBRATION holds on the calibration file for
    THIS prompt hash and model; a report with an uncalibrated judge prints
    the judge lines under the INCOMPLETE mark and is not circulated internally
    (spec §8.5 «отчёт с некалиброванным судьёй не публикуется внутри»)."""

    judge_model: str
    prompt_sha256: str
    n: int
    raw_agreement: float
    kappa: float
    per_type_kappa: dict[str, float]
    repeat_disagreement: float
    calibrated: bool


# --- §7 the comparison with v4 (mandatory, every GO run) --------------------------------

@dataclass(frozen=True)
class LevelRow:
    """One row of v4's block, as `bench.agentpii4.report.render` prints it —
    the same numbers, parsed into fields so the side-by-side can print them
    beside the v5 lines. The v4 block is produced by v4's `render` on the
    `.base` cases and the v4-shaped `arms.jsonl`, so `compare_runs.py` of v4
    reads a v5 run directory unchanged."""

    level: str
    label: str
    comparable: int
    triples: int
    agree_ic: float
    agree_cc: float
    effect: float
    ci_low: float
    ci_high: float
    tost_verdict: str
    tost_low: float
    tost_high: float
    mcnemar_p: float
    discordant_b: int
    discordant_c: int
    icc_case: float
    icc_value: float
    deff: float


@dataclass(frozen=True)
class SideBySide:
    """What the final report of a v5 run prints, side by side with the v4
    baseline run it is compared to. Both halves come from run FILES (§8),
    never from re-running a model. `v5_refused` lists every metric the gate
    refused with its reason; `incomplete` is True when any non-diagnostic one
    is refused or the judge is not calibrated, and the header then carries
    INCOMPLETE_REPORT_MARK."""

    v5_run: str                      # run directory
    v4_run: str                      # baseline run directory (a v4 run, or the v4 block of an earlier v5 run)
    corpus_digest_v5: str
    corpus_digest_v4: str
    agent_model: str
    judge: CalibrationStamp
    v4_levels: tuple[LevelRow, ...]  # exactly V4_LEVEL_NAMES, in order
    v5_lines: dict[str, Line]        # printable metrics, by name
    v5_by_axis: dict[str, dict[str, dict[str, Line]]]   # metric → axis → bucket → Line
    v5_refused: dict[str, str]
    judge_labels: dict[str, int]     # JUDGE_LABELS → count over answers with PII
    # Verdicts the DETERMINISTIC pre-gate produced (`judged_by ==
    # "residual_gate"`), counted apart from `judge_labels`: folding them in
    # credits the model with verdicts it never gave and measures the gate's
    # agreement with itself. Printed on the judge line of the header.
    judge_pregate: int
    # Every (case, repeat) the v5 population LOST, as "case_id|repeat
    # (reason)". Two reasons and they are not the same fact: a HOLE
    # (`EXCLUDED_NO_HOPS` — the case declares hops, the arm finished, and no
    # hop row is on disk) makes `incomplete` True, because `residual` once
    # printed 1/1 over ten observations whose hops it had never read; an arm
    # that stopped carries its own termination and does not, because v4's own
    # block already prints it under «исключено». The report reads them HERE
    # rather than from the half it assembled from, so a `SideBySide` that has
    # been written to a file still names its own holes.
    excluded_observations: tuple[str, ...]
    incomplete: bool


# The reason word an `excluded_observations` row carries when the observation
# is a HOLE rather than an arm that stopped. A constant, so the writer and any
# reader cannot disagree about which half of the list makes a report НЕПОЛНЫЙ.
EXCLUDED_NO_HOPS: str = "нет хопов"


# --- §8 run layout: what a v5 run directory holds ---------------------------------------

# v4 readers (`autopsy._load_run`, `compare_runs`, `harness --report`) take a
# directory and read `corpus.json` (v4 shape, key "corpus") and `*.arms.jsonl`
# (v4 records). A v5 run writes those two EXACTLY as v4 does, from `.base`, and
# adds its own files beside them. Then the baseline comparison is v4's own
# tool run on two directories, and nothing in v5 can flatter itself.
# The benchmark's own name, in ONE place. It is written into every registry row
# (`runinfo.RunRecord.benchmark`) and into `<run>.report.json`, and those two
# files are read side by side by `trend`; two spellings of it would be two
# benchmarks in one table, discovered by a reader of the trend.
BENCHMARK: str = "agentpii5"

RUN_FILES: dict[str, str] = {
    "corpus.json": "the v4-shaped corpus snapshot: {\"corpus\": [case.base.to_json() …], \"digest\": …}",
    "corpus.v5.json": "the v5 corpus snapshot: {\"corpus\": [case_v5_to_json(case) …], \"digest\": …}",
    "<run>.arms.jsonl": "one v4 `arm_record` per arm, unchanged shape",
    "<run>.arms.v5.jsonl": "one `ArmRunV5` record per I arm (key = case_id|I|repeat)",
    "<run>.triples.jsonl": "v4's per-triple status/cost/judge rows",
    "<run>.hops.jsonl": "one HopObservation per hop per (case, repeat), as `observe` produced it",
    "<run>.judge.jsonl": "row 0 is the CalibrationStamp (calibration_stamp_to_json — a row carrying `calibrated`), then one JudgeRow per answer with the JudgeInput's sha256 (ruling 2026-09-22: the report marks itself НЕПОЛНЫЙ without the stamp, so the stamp travels with the verdicts it certifies)",
    "<run>.spend.tsv": "the SpendLedger file (agent + judge), v4 format",
    "<run>.report.txt": "the side-by-side (SideBySide rendered), header first",
    "<run>.gate.json": "GateVerdict per metric — the proof the report was allowed to print",
    "<run>.meta.json": "what the run itself was: {run_id, benchmark, model, judge_model, tier, repeats, digest, ceiling_usd, spent_usd, prompt_sha256, started, finished, wall_s, label, note, worktree, provenance, provider, gateway} — written by `harness.main`. `label`/`note` are the run's own words (ТЗ §1.3) and `started`/`wall_s` are what the NEXT run's time estimate is built from; `worktree` is the one-line state of the tree (§6.1) the registry row copies verbatim, `provenance` the commit and digests behind it, `provider` and `gateway` what answered and what was masked against (§4.1, §4.2). The report needs two of them and can get them nowhere else: the CEILING the run was given (a cost line without it says «spent $12 of an unknown ceiling») and the `prompt_sha256` a calibration stamp must match, because a calibration of another prompt certifies another instrument. A run that wrote no meta file is read as a run whose ceiling and prompt are unknown — never as a free run under the right prompt",
    "<run>.report.json": "the same report as DATA (ТЗ §5.1): one versioned schema with every metric line as {hits, total, rate, interval}, the slices, the v4 levels, the cost, the digests and the models — written by `reportjson.write` beside the text, so a trend, an article or a diff of two runs never re-parses `<run>.report.txt` (a line whose spacing changed took the trend with it)",
    "<run>.public.json": "the substring of the above that may be shown outside (ТЗ §5.3), built by an ALLOWLIST (`reportjson.PUBLIC_TOP_LEVEL` / `PUBLIC_LINES`) and never by deletion: a field added to the private report is absent here until somebody names it. Carries no case id and no value from the corpus",
}
CALIBRATION_FILE: str = "bench/agentpii5/calibration/<judge_model>.<prompt_sha256[:12]>.jsonl"


# --- helpers every component may call (pure, tiny, and therefore here) ------------------

def feature_pairs() -> tuple[tuple[str, str], ...]:
    """Every (type, feature) the comparator must register — the flattening
    of FORM_FEATURES, in its order."""
    return tuple((kind, feature) for kind, features in FORM_FEATURES.items() for feature in features)


def hop_owner_of_leaf(tool_name: str, path: str) -> str:
    """Which OUT owner an argument leaf counts under, from the closed tables.
    `variables.*` matches any leaf under `variables`; array indexes are
    erased before matching so `phones[0].number` and `phones[].number` are
    one path."""
    generic = _erase_indexes(path)
    for tool, pattern in TEMPLATE_FIELDS:
        if tool == tool_name and _path_matches(pattern, generic):
            return "template"
    for tool, pattern in SUMMARY_FIELDS:
        if tool == tool_name and _path_matches(pattern, generic):
            return "summary"
    return "tool_arg"


def _erase_indexes(path: str) -> str:
    out: list[str] = []
    depth = 0
    for char in path:
        if char == "[":
            depth += 1
            out.append("[")
        elif char == "]":
            depth -= 1
            out.append("]")
        elif depth == 0:
            out.append(char)
    return "".join(out)


def _path_matches(pattern: str, path: str) -> bool:
    if pattern.endswith(".*"):
        return path == pattern[:-2] or path.startswith(pattern[:-2] + ".")
    return path == pattern


MetricRegistry = dict[str, Callable[[Sequence[RunObservation]], Line]]
