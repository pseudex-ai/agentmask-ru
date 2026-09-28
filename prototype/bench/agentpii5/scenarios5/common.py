"""What every v5 family shares: the builder that declares hops, the v5 register
mix, the plate renderer v4 never needed, and the backend rows the new tools read.

THREE MOVES, AS IN v4, PLUS ONE. A v4 scenario draws, writes and finishes; a v5
scenario draws, writes, **declares what crosses the gateway**, and finishes.
The fourth move is the whole of v5: `CaseBuilderV5` collects `Hop`s,
`ReturnExpectation`s and the behaviour spec, and `build(behaviour)` refuses to
hand back a case that `schema.validate_v5` has anything to say about — so no
invalid case can reach `corpus.v5.json` in the first place.

COMPOSITION OVER SUBCLASSING, EVERYWHERE. `CaseBuilderV5` HOLDS a v4
`CaseBuilder` (`self.v4`) instead of extending it. v4's builder writes the v4
`Case` that the v4 baseline is run on, and a subclass would sooner or later put
a v5 field into `Case.to_json()` — then the baseline moves with the treatment
and the comparison measures nothing.

NOTHING HERE SEARCHES A FINISHED STRING. Message text comes from
`MessageDraft`, and a free-text BACKEND field (a RAG chunk, a ticket history, a
scanned document) comes from `RecordDraft`, which is the same discipline one
layer down: the chunk's slot offsets are laid as the chunk is written, never
recovered from it. `bench.agentpii4.validate.prove_no_search` watches this
directory.

NOTHING HERE IMPORTS `pseudex`.
"""
import random
from dataclasses import dataclass, field, replace

from bench.agentpii4 import pools
from bench.agentpii4.pools import Person, Rendered
from bench.agentpii4.scenarios import common as v4common
from bench.agentpii4.scenarios.common import (  # noqa: F401 - re-exported on purpose
    NOW, Ctx, Drawn, MessageDraft, address, address_seed_fields, card, contact_seed,
    ctx_for, dob, draw, email, full_name_canonical, inn, is_rare_stratum, name,
    noisy_word, opener, order_number, passport, phone, snils, time_of_day)
from bench.agentpii4.schema import InvalidCase, Locus, Message, PiiItem
from bench.agentpii5.contracts import (BranchSpec, CaseV5, DocumentSpec, ForcedError, Hop,
                                       LoopSpec, MemorySpec, PickSpec, RagSpec,
                                       ReturnExpectation, hop_owner_of_leaf)
from bench.agentpii5.contracts import (
    V4_KIND_FOR_BEHAVIOUR as contracts_v4_kind_for_behaviour)
from bench.agentpii5.schema import has_result, validate_v5
from bench.agentpii5.tools import csv_row_path, field_at, spec_v5_for

# The date the whole corpus calls today. NOT a v5 constant of its own: v4's
# `CaseBuilder.build()` stamps `Case.now` from v4's `NOW`, so a v5 system
# prompt fixing another date would put two dates in one case and the agent
# would be told one while the record says the other.
NOW_V5: str = NOW
# THE v4 KIND EVERY v5 BEHAVIOUR WEARS is `contracts.V4_KIND_FOR_BEHAVIOUR`,
# normative there since the 2026-09-22 ruling (R-10) and re-exported here under
# the name every family already imports. Rule R02 runs v4's own validator on
# `CaseV5.base`, and that validator refuses any `kind` outside
# `v4.SCENARIO_KINDS` — so a family whose `ctx.kind` is «parallel» would fail
# R02 on every case it writes. The case id and the random stream still carry the
# BEHAVIOUR (`ctx.kind`); only `Case.kind` is stamped from the table.
V4_KIND_FOR_BEHAVIOUR: dict[str, str] = dict(contracts_v4_kind_for_behaviour)

# The roles `system_prompt_v5` can open with. Read off v4's table rather than
# copied: a copy is a second list that has to stay equal to the first.
ROLES: tuple[str, ...] = tuple(v4common._ROLE_PROMPTS)  # noqa: SLF001 - read, never written

# --- the v5 register mix (spec §8.2) ------------------------------------------

# voice 45% (0.28 + 0.17), chat 30%, sloppy 15%, clean 10% — `contracts.
# REGISTER_SHARES` with voice split between the two speech registers. It SUMS TO
# 1.00 (ruling R-16): the earlier 0.95 left five points unassigned, and K04 reads
# the shares as four two-sided bands with nowhere for a remainder to land. The
# five points went to `chat`, the register a live support dialogue defaults to.
REGISTER_MIX_V5: tuple[tuple[str, float], ...] = (
    ("voice_raw", 0.28), ("voice_itn", 0.17), ("chat", 0.30), ("sloppy", 0.15), ("clean", 0.10))


def registers_for(count: int, rng: random.Random) -> list[str]:
    """A register per case, apportioned then shuffled.

    APPORTIONMENT, NOT `rng.sample` AND NOT `round(count * share)`. v5 puts
    `clean` at 10% and families as small as forty cases; `round(40 * 0.10)` is
    4, but `round(5 * 0.10)` is 0 and the register vanishes from a family
    exactly where the corpus most needs it present. The rule below is
    Sainte-Laguë (Webster): each case goes to the register whose next case is
    most overdue, `share / (2·delivered + 1)`. It is the unbiased divisor
    method — every register gets its first case before any gets its third — so
    a family of five carries all five registers and a family of five hundred
    carries the shares to a fraction of a point.

    Ties break towards the register that has delivered least, so the rarest
    share wins the last seat rather than the largest one.
    """
    if count <= 0:
        raise pools.BuildError(f"a family of {count} cases has no registers to hand out")
    targets: dict[str, float] = dict(REGISTER_MIX_V5)
    if abs(sum(targets.values()) - 1.0) > 1e-9:
        raise pools.BuildError(f"the v5 register mix adds to {sum(targets.values())}, not 1.00")
    delivered: dict[str, int] = {register: 0 for register in targets}
    out: list[str] = []
    for _ in range(count):
        overdue = min(sorted(targets),
                      key=lambda register: (-targets[register] / (2 * delivered[register] + 1),
                                            delivered[register], register))
        delivered[overdue] += 1
        out.append(overdue)
    rng.shuffle(out)
    return out


# --- system prompts -----------------------------------------------------------

# The clauses a v5 family adds to v4's role prompt. They are HERE and not in the
# families because each one is a business rule the substitute can break, and a
# rule written twice is two rules that drift. A clause passes through the
# gateway with the rest of the prompt, so a clause the masking rewrote is a
# clause the agent never received — which is itself part of what v5 measures.
VALIDATE_CLAUSE: str = v4common.VALIDATE_CLAUSE
PARALLEL_CLAUSE: str = ("Если в реплике несколько независимых поручений, вызови инструменты "
                        "для них ОДНИМ ходом, а не по очереди.")
BRANCH_CLAUSE: str = ("Сначала проверь, есть ли карточка клиента: если есть — обнови её, "
                      "если нет — заведи новую.")
DOCUMENT_CLAUSE: str = ("Данные бери из приложенного файла: сначала прочитай его инструментом, "
                        "потом заполняй поля значениями оттуда, ничего не придумывая.")
CONFIRM_CLAUSE: str = ("Найдя карточку, покажи клиенту, что именно нашёл, и действуй только "
                       "после его подтверждения.")
RAG_CLAUSE: str = ("Отвечай только по найденным фрагментам базы знаний. Данные других клиентов "
                   "в ответ не переноси.")
MEMORY_CLAUSE: str = ("Клиент может ссылаться на сказанное раньше («ему», «на тот адрес», "
                      "«тот же телефон») — восстанавливай значение из разговора, не переспрашивай.")
RETRY_CLAUSE: str = ("Если инструмент отказал из-за формата поля, исправь формат и вызови его "
                     "ещё раз; данные клиента при этом не меняй.")


def system_prompt_v5(role: str, now: str, extras: tuple[str, ...]) -> str:
    """v4's role prompt plus the clauses this family needs, in the given order.

    `role` is one of `ROLES` — v5 adds no role: the new verticals reuse v4's
    (`bank` for bank_client_find / account_statement, `gov` for vehicle_check /
    snils_verify, `crm` for file_read / form_parse / kb_search, `callcenter`
    for ticket_history / calendar_free). A new role would be a new prompt
    against which the v4 baseline was never run.

    The checksum clause is passed IN `extras` (`VALIDATE_CLAUSE`) rather than
    derived from `validate_types`, so the prompt a family sends is the prompt
    its module names, with nothing added behind its back.
    """
    if role not in ROLES:
        raise pools.BuildError(f"unknown role {role!r}; v5 adds none, the roles are {ROLES}")
    text = v4common.system_prompt(role, now, (), "")
    for clause in extras:
        if not clause:
            raise pools.BuildError(f"empty clause in the prompt of role {role!r}")
        text = f"{text} {clause}"
    return text


# --- the plate, the type v4 never carried -------------------------------------

PLATE_CANONICAL_WIDTHS: tuple[int, int] = (8, 9)   # А123ВС77 and А123ВС777


def plate_text(rng: random.Random) -> str:
    """A canonical Russian plate, drawn from v4's pool: «А123ВС77».

    Built here rather than in the caller because the canonical form is the
    VAULT KEY of this type, and four callers assembling it by hand is four
    chances to put a space where the key has none.
    """
    series, digits, letters, region = pools.draw_plate(rng)
    return f"{series}{digits}{letters}{region}"


def plate(ctx: Ctx, text: str) -> Rendered:
    """A plate in the register's notation, with the parts it was built from.

    WHY NOT `pools.render_plate`. v4's renderer sets `canonical` to the SPOKEN
    words for `voice_raw` — which is right for a corpus that never stored a
    plate in a backend, and wrong for v5, where `vehicle_check` returns the
    plate from a record and the canonical is the key both arms must agree on.
    Here the canonical is «А123ВС77» in every register, and v4's `parts` names
    (`letter` / `pair`) become the spec's (`series` / `letters`).

    EVERY SPOKEN FORM PARSES BACK TO ITS DIGITS. A dictated value the corpus
    cannot decode is a ground truth nobody can check — the rule v4 applies to
    every spoken identifier, applied here to the two numeral runs of a plate.
    """
    series, digits, letters, region = _plate_parts(text)
    parts: dict[str, str] = {"series": series, "digits": digits,
                             "letters": letters, "region": region}
    canonical = f"{series}{digits}{letters}{region}"
    if ctx.register == "voice_raw":
        words: list[str] = [pools.PLATE_SPOKEN[series]]
        words.extend(_spoken_digits(digits))
        words.extend(pools.PLATE_SPOKEN[letter] for letter in letters)
        words.extend(_spoken_digits(region))
        return Rendered(surface=" ".join(words), canonical=canonical, spoken=True, parts=parts)
    if ctx.register == "voice_itn":
        # What an ITN pass writes back: the letters as the caller said them
        # (lower case), the numeral runs as digits, one space per run.
        surface = f"{series.lower()} {digits} {letters.lower()} {region}"
    elif ctx.register == "chat":
        surface = f"{series}{digits}{letters} {region}".lower()
    elif ctx.register == "sloppy":
        surface = canonical
    else:
        # `clean`: the region is a separate field on the plate itself, and a
        # literate writer copies that space.
        surface = f"{series}{digits}{letters} {region}"
    return Rendered(surface=surface, canonical=canonical, spoken=False, parts=parts)


def _plate_parts(text: str) -> tuple[str, str, str, str]:
    """Split a canonical plate by POSITION — the format is fixed-width, so no
    pattern is searched for and no offset is recovered. Anything else raises:
    a plate the corpus cannot decompose is ground truth nobody can score."""
    if len(text) not in PLATE_CANONICAL_WIDTHS:
        raise pools.BuildError(f"{text!r} is not a canonical plate (width "
                               f"{PLATE_CANONICAL_WIDTHS})")
    series, digits, letters, region = text[0], text[1:4], text[4:6], text[6:]
    for letter in (series, *letters):
        if letter not in pools.PLATE_LETTERS:
            raise pools.BuildError(f"{text!r} carries letter {letter!r}, outside "
                                   f"{pools.PLATE_LETTERS}")
    for run in (digits, region):
        if not run.isdigit():
            raise pools.BuildError(f"{text!r} carries a non-digit run {run!r}")
    return series, digits, letters, region


def _spoken_digits(digits: str) -> tuple[str, ...]:
    """One numeral run as a caller says it, proved decodable before it is used."""
    words = pools.spell_groups(digits, (len(digits),))
    if pools.parse_numerals(words) != digits:
        raise pools.BuildError(f"spoken run {' '.join(words)!r} does not decode to {digits!r}")
    return words


# --- the builder ---------------------------------------------------------------

@dataclass
class CaseBuilderV5:
    """The concrete `contracts.CaseKit`: v4's builder plus the v5 declarations.

    The accumulator fields carry `field(default_factory=...)` because a builder
    without them is unusable, which is v4's own idiom in this package; every
    value a SCENARIO decides is passed explicitly through `new_builder`.

    `build` validates and RAISES. A scenario that wrote an invalid case must
    hear about it where the case was written, not three thousand cases later in
    `build.py --check` — and `InvalidCase` carries every problem, so one run
    fixes the family instead of one rule.
    """

    v4: v4common.CaseBuilder
    hops: list[Hop] = field(default_factory=list)
    returns: list[ReturnExpectation] = field(default_factory=list)
    forced: list[ForcedError] = field(default_factory=list)
    memory: list[MemorySpec] = field(default_factory=list)
    pick: PickSpec | None = None
    branch: BranchSpec | None = None
    loop: LoopSpec | None = None
    rag: RagSpec | None = None
    document: DocumentSpec | None = None
    streaming: bool = False

    # --- the v4 moves, re-exposed -------------------------------------------

    @property
    def ctx(self) -> Ctx:
        return self.v4.ctx

    def draft(self) -> MessageDraft:
        """A message of this case's register, ready to be written into."""
        return MessageDraft(self.v4.ctx)

    def user(self, draft: MessageDraft,
             typed: dict[str, tuple[str, str, str, bool]]) -> int:
        """v4's: append a user message, turn its keyed chunks into items,
        return the message index — which is the `turn` of every hop of it."""
        return self.v4.user(draft, typed)

    def seed(self, record_id: str, table: str, fields: dict[str, object],
             typed_paths: dict[str, tuple[str, str, Rendered]]) -> None:
        """v4's: a backend row that exists before the run."""
        self.v4.seed(record_id, table, fields, typed_paths)

    def seed_spans(self, record_id: str, table: str, fields: dict[str, object],
                   typed_paths: dict[str, tuple[str, str, Rendered]],
                   spans: dict[str, tuple[int, int]]) -> None:
        """A seed row whose PII fields also know WHERE they sit in a free-text
        field of the same row.

        v4's `seed` writes `Locus(start=0, end=0)` because a v4 seed is a typed
        column and a column has no offsets. A v5 chunk is one free-text column
        holding several people, and the mock must know which stretch of it each
        item occupies. The items are created by v4's `seed` (so the id counter
        stays v4's, one allocator) and then their locus is replaced — nothing
        of v4 is edited, and the row is still a plain v4 `SeedRecord`.
        """
        before = len(self.v4.pii)
        self.seed(record_id, table, fields, typed_paths)
        for position in range(before, len(self.v4.pii)):
            item = self.v4.pii[position]
            span = spans.get(item.where.path)
            if span is None:
                continue
            start, end = span
            self.v4.pii[position] = _with_span(item, start, end)

    # --- the v5 declarations (contracts.CaseKit) ----------------------------

    def declare_hop(self, hop: Hop) -> None:
        """Append one declared crossing. The index is CHECKED, never rewritten:
        a scenario computes `source_hop` from indexes it already handed out, so
        renumbering silently would repoint somebody's chain."""
        if hop.hop_index != len(self.hops):
            raise InvalidCase(f"{self.v4.ctx.kind}: hop_index {hop.hop_index} declared at "
                              f"position {len(self.hops)}")
        self.hops.append(hop)

    def next_hop_index(self) -> int:
        """The index the next `declare_hop` expects — what a scenario stores as
        another hop's `source_hop`."""
        return len(self.hops)

    def expect_return(self, expectation: ReturnExpectation) -> None:
        self.returns.append(expectation)

    def force_error(self, forced: ForcedError) -> None:
        self.forced.append(forced)

    def remember(self, memory: MemorySpec) -> None:
        self.memory.append(memory)

    def set_pick(self, pick: PickSpec) -> None:
        self._refuse_second("pick", self.pick)
        self.pick = pick

    def set_branch(self, branch: BranchSpec) -> None:
        self._refuse_second("branch", self.branch)
        self.branch = branch

    def set_loop(self, loop: LoopSpec) -> None:
        self._refuse_second("loop", self.loop)
        self.loop = loop

    def set_rag(self, rag: RagSpec) -> None:
        self._refuse_second("rag", self.rag)
        self.rag = rag

    def set_document(self, document: DocumentSpec) -> None:
        self._refuse_second("document", self.document)
        self.document = document

    def _refuse_second(self, label: str, current: object) -> None:
        """A behaviour spec is set once. A second `set_pick` overwriting the
        first silently would lose the half of the case the scenario had already
        declared hops for."""
        if current is not None:
            raise InvalidCase(f"{self.v4.ctx.kind}: {label} is already set; "
                              f"a case carries one {label}")

    def set_streaming(self, streaming: bool) -> None:
        self.streaming = streaming

    def build(self, behaviour: str) -> CaseV5:
        """The v4 case, the v5 declarations, and every problem or nothing."""
        hops = tuple(self.hops)
        # An unknown behaviour keeps whatever kind it had: raising a KeyError
        # here would name no rule, while `validate_v5` answers R01 by name.
        kind = V4_KIND_FOR_BEHAVIOUR.get(behaviour, self.v4.ctx.kind)
        case = CaseV5(
            base=replace(self.v4.build(), kind=kind), behaviour=behaviour, hops=hops,
            returns=tuple(self.returns), forced=tuple(self.forced), memory=tuple(self.memory),
            pick=self.pick, branch=self.branch, loop=self.loop, rag=self.rag,
            document=self.document, has_result=has_result(hops), streaming=self.streaming,
            revised_from_v4=False, v6=None)
        problems = validate_v5(case)
        if problems:
            raise InvalidCase(f"{case.base.id} ({behaviour}):\n  " + "\n  ".join(problems))
        return case


def _with_span(item: PiiItem, start: int, end: int) -> PiiItem:
    """The same seed item, knowing where it sits inside its record's text."""
    locus = item.where
    return replace(item, where=Locus(kind=locus.kind, msg=locus.msg, start=start, end=end,
                                     record=locus.record, path=locus.path))


def new_builder(ctx: Ctx, role: str, tools: tuple[str, ...], reachable: tuple[str, ...],
                primary_identity: str, cluster: str, note: str,
                extras: tuple[str, ...]) -> CaseBuilderV5:
    """A v5 builder over a fresh v4 one, with the v5 system prompt in place.

    The system prompt is REPLACED rather than parameterised: v4's
    `CaseBuilder.__post_init__` writes message 0 from v4's `system_prompt`, and
    v5's extra clauses are v5's. Everything else a scenario may need
    (`conversation_id`, `validate_types`, `rule`, `must_contain`,
    `must_not_contain`) is a mutable field of `builder.v4`, set before `build`;
    they are not arguments here because a factory with twelve parameters is a
    factory whose call sites are read by counting commas.
    """
    inner = v4common.CaseBuilder(ctx=ctx, role=role, tools=tools, reachable=reachable,
                                 primary_identity=primary_identity, cluster=cluster, note=note)
    inner.messages[0] = Message(role="system", content=system_prompt_v5(role, NOW_V5, extras),
                                source=None, name="")
    return CaseBuilderV5(v4=inner)


# --- the hops every family declares ---------------------------------------------
#
# THE FOUR CONSTRUCTORS LIVE HERE, NOT IN `plan_a.py` (ruling R-25). They were
# written there because generator_a's six families needed them first; both
# halves of the corpus need them, and a second copy of `arg_hop` would be a
# second opinion about which `form_hOUT` line a leaf counts in. `plan_a` and
# `plan_b` re-export them under the same names, so the ten family modules did
# not have to move with them.

def user_hop(item_id: str, index: int, turn: int) -> Hop:
    """The customer said it: no tool, no source, never optional.

    An IN/user hop is never optional because the value IS in the message — an
    optional hop that did not happen counts nowhere, and a datum the customer
    dictated that the gateway did not carry is the one failure this benchmark
    exists to see."""
    return Hop(kind="IN", owner="user", item_id=item_id, hop_index=index, turn=turn,
               tool_name="", call_ordinal=-1, parallel_group="", source_hop=-1,
               path="", optional=False)


def tool_hop(item_id: str, index: int, turn: int, tool: str, ordinal: int, path: str) -> Hop:
    """A value coming BACK from a tool result, at `path` inside that result.

    `source_hop` is -1 and stays -1: the chain link is a property of the OUT hop
    that carries a value forward, and an IN hop that pointed back at the
    argument it was looked up by would make `metrics.chain_value` count one
    transition twice."""
    return Hop(kind="IN", owner="tool", item_id=item_id, hop_index=index, turn=turn,
               tool_name=tool, call_ordinal=ordinal, parallel_group="", source_hop=-1,
               path=path, optional=False)


def arg_hop(item_id: str, index: int, turn: int, tool: str, ordinal: int, path: str,
            source_hop: int, group: str) -> Hop:
    """A value going OUT into one argument leaf of one call.

    THE OWNER AND THE OPTIONALITY ARE READ, NOT DECIDED. `hop_owner_of_leaf`
    answers whether the leaf is a plain argument, a template slot a human will
    read, or a summary the agent writes for another agent — the owner decides
    which `form_hOUT` line the hop counts in, and a family that chose it by hand
    would move hops between lines case by case. `optional` is `not
    FieldSpec.required` for the same reason: the tool's own schema already says
    whether a call can legitimately omit the leaf, and a second opinion here
    would be a second definition of the same fact.

    A path the registry does not know RAISES rather than defaulting to
    `tool_arg`: it is a typo in a family, and a hop on a leaf no call can carry
    is a miss the agent can never avoid.
    """
    spec = spec_v5_for(tool, path)
    if spec is None:
        raise pools.BuildError(f"{tool} has no argument leaf {path!r}; a hop on it can "
                               f"never happen")
    return Hop(kind="OUT", owner=hop_owner_of_leaf(tool, path), item_id=item_id,
               hop_index=index, turn=turn, tool_name=tool, call_ordinal=ordinal,
               parallel_group=group, source_hop=source_hop, path=path,
               optional=not spec.required)


def answer_hop(item_id: str, index: int, turn: int, source_hop: int, optional: bool) -> Hop:
    """A value the reply to the customer carries. `optional` is False only where
    the customer ASKED for this datum by name — then the case also puts its
    canonical into `must_contain`, so the judge and the hop agree about what the
    answer owed."""
    return Hop(kind="OUT", owner="answer", item_id=item_id, hop_index=index, turn=turn,
               tool_name="", call_ordinal=-1, parallel_group="", source_hop=source_hop,
               path="", optional=optional)


# --- recovering the ids the v4 builder minted ------------------------------------

def minted(builder: CaseBuilderV5, before: int) -> tuple[PiiItem, ...]:
    """The items the last `seed` / `user` call added, in the order it added them.

    v4's builder allocates ids and appends; it returns none of them. Reading the
    tail of `builder.v4.pii` is how `test_schema._valid_case` does it and the
    only way that does not restate v4's id counter in a second place.
    """
    if before > len(builder.v4.pii):
        raise pools.BuildError(f"{before} items were never minted; the case holds "
                               f"{len(builder.v4.pii)}")
    return tuple(builder.v4.pii[before:])


# What a written surface may never be. A column that resolved to nothing used to
# reach the corpus as the string «None», and it is not an odd-looking value: it
# is a NEEDLE. `needles_of('NAME', 'None')` yields the stem «none», which every
# `own_stems` exemption then honours and which `occurrences_of` finds in the
# literal word «None» anywhere in a reply — so an answer that mentioned it read
# as «the agent wrote the real value».
PLACEHOLDER_SURFACES: tuple[str, ...] = ("", "none", "null")


def seeded(builder: CaseBuilderV5, record_id: str, table: str, fields: dict[str, object],
           typed_paths: dict[str, tuple[str, str, Rendered]]) -> dict[str, str]:
    """One backend row, and the {field path: item id} map its consumers need.

    The map is keyed by PATH because that is what a `ReturnExpectation`, an
    IN/tool hop and `seed_backend_v5`'s tag binding are all written against.

    THE WRITTEN SURFACE IS RE-READ THROUGH `field_at` (round 4). v4's `seed`
    stores `str(_seed_field(fields, path))`, which is the same string for every
    flat column and the string «None» for an indexed one; re-reading is
    therefore a no-op everywhere except where v4 could not walk, and it is done
    for EVERY item rather than for the ones that look wrong, because a rule
    that only repairs what it recognises is a rule that stops recognising.
    """
    before = len(builder.v4.pii)
    builder.seed(record_id, table, fields, typed_paths)
    for position in range(before, len(builder.v4.pii)):
        item = builder.v4.pii[position]
        surface = str(field_at(fields, item.where.path))
        if surface.strip().lower() in PLACEHOLDER_SURFACES:
            raise pools.BuildError(f"seed {table}/{record_id} column {item.where.path!r} "
                                   f"holds {surface!r}; a written surface is what the record "
                                   f"says, never a placeholder")
        builder.v4.pii[position] = replace(item, value=surface)
    return {item.where.path: item.id for item in minted(builder, before)}


def told(builder: CaseBuilderV5, draft: MessageDraft,
         typed: dict[str, tuple[str, str, str, bool]]) -> tuple[int, dict[str, str]]:
    """One user message, its turn index, and the {draft key: item id} map.

    `draft.values` is an insertion-ordered dict and v4's `user` walks it in that
    order, so zipping its keys with the tail of the item list recovers the ids
    without any of them being looked up by value — the rule this corpus is built
    on, applied to its own bookkeeping.
    """
    before = len(builder.v4.pii)
    turn = builder.user(draft, typed)
    items = minted(builder, before)
    keys = tuple(draft.values)
    if len(keys) != len(items):
        raise pools.BuildError(f"message {turn} wrote {len(keys)} values and minted "
                               f"{len(items)} items")
    return turn, {key: item.id for key, item in zip(keys, items)}


# --- more people for one case ----------------------------------------------------

def extra_people(ctx: Ctx, city: str, apart_from: Drawn, count: int) -> tuple[Drawn, ...]:
    """`count` more people for this case, distinct from `apart_from` AND from
    each other in every field the mock indexes by value.

    NOT `draw` A SECOND TIME, and the reason is a trap that cost a whole family
    (ruling R-32; the note lives here because v4's own docstring is not ours to
    edit). v4's `draw` overrides its own result on two index rules: every fifth
    case gets one of the EIGHT SHARED people (the clusters the bootstrap
    resamples) and one in seven gets a rare-stratum person from a stream seeded
    by the index alone. Both are deterministic in the index, so a second call
    inside one case returns the SAME person — a loop asking for a distinct one
    never terminates.

    ITS OWN RANDOM STREAM, for v4's reason: drawing from `ctx.rng` would shift
    every later draw of the scenario, and adding a second person to a family
    would silently be a new corpus rather than the same corpus with a second
    person. The stream is seeded by kind, seed, index and ordinal, so the draw
    is reproducible and every extra person of one case is a different one.

    DISTINCTNESS IS PAIRWISE, not «against the first». The mock drops a by-value
    tag that two items share, so two strangers with one surname would make both
    their payloads unobservable and every hop on them would read as a gateway
    miss no gateway could avoid.
    """
    if count < 1:
        raise pools.BuildError(f"asked for {count} extra people; the caller wants none")
    drawn: list[Drawn] = []
    ordinal = 0
    while len(drawn) < count:
        ordinal += 1
        if ordinal > count * 60:
            raise pools.BuildError(f"{ordinal} draws in {city!r} produced no person distinct "
                                   f"from {apart_from.person.surname[0]!r} and "
                                   f"{len(drawn)} others")
        candidate = _draw_apart(ctx, city, ordinal)
        if not _distinct(candidate, apart_from):
            continue
        if any(not _distinct(candidate, earlier) for earlier in drawn):
            continue
        drawn.append(candidate)
    return tuple(drawn)


def _draw_apart(ctx: Ctx, city: str, ordinal: int) -> Drawn:
    """One person off a stream of this case's own, with none of `draw`'s
    index-driven overrides."""
    stream = random.Random(f"v5:other:{ctx.kind}:{ctx.seed}:{ctx.index}:{ordinal}")
    person = stream.choice(pools.MALE + pools.FEMALE)
    return Drawn(
        person=person,
        phone=pools.mobile_digits(stream),
        address=pools.draw_address(stream, city, True, False, True),
        dob=pools.draw_dob(stream),
        email_local=pools.mail_translit(person.surname[0]) + str(stream.randrange(70, 99)),
        email_domain=stream.choice(pools.EMAIL_DOMAINS))


def _distinct(one: Drawn, other: Drawn) -> bool:
    return (one.person.surname[0] != other.person.surname[0]
            and one.person.given[0] != other.person.given[0]
            and one.phone != other.phone
            and one.address.street != other.address.street
            and one.email_local != other.email_local
            and one.dob != other.dob)


# --- backend rows the new tools read -------------------------------------------

def _person_fields(person: Person) -> dict[str, object]:
    """The three name columns every table in this mock spells the same way."""
    return {"last_name": person.surname[0], "first_name": person.given[0],
            "middle_name": person.patronymic[0]}


def _person_typed(person: Person, identity: str) -> dict[str, tuple[str, str, Rendered]]:
    """…and their typed items. The `parts` carry the gender because the name
    comparator's `gram_case` vote needs it and cannot infer it from one word."""
    return {
        "last_name": ("NAME", identity, Rendered(person.surname[0], person.surname[0], False,
                                                 {"surname": person.surname[0],
                                                  "gender": person.gender})),
        "first_name": ("NAME", identity, Rendered(person.given[0], person.given[0], False,
                                                  {"given": person.given[0],
                                                   "gender": person.gender})),
        "middle_name": ("NAME", identity, Rendered(person.patronymic[0], person.patronymic[0],
                                                   False, {"patronymic": person.patronymic[0],
                                                           "gender": person.gender})),
    }


def full_name(person: Person) -> str:
    """The one string a bank, a calendar and a ticket system store a person
    under. Three name columns is the CRM's shape and nobody else's."""
    return " ".join(part for part in (person.surname[0], person.given[0],
                                      person.patronymic[0]) if part)


def stored_name(drawn: Drawn, ctx: Ctx) -> Rendered:
    """A name as a BACKEND holds it: nominative, clean, undamaged.

    NOT `common.name`, which renders in the CASE's register. A knowledge-base
    note and a scanned form are written by the customer's own systems, not
    dictated by the caller — a chunk carrying «иванов пётр» because the call was
    `voice_raw` would measure the register twice and the backend never.

    HERE RATHER THAN IN `plan_b` (R-25's rule, applied on its second caller).
    Generator_b wrote it first; the `single` family of generator_a needs the same
    notation, and a second copy would be a second opinion about how a backend
    spells a name — the two halves of the corpus would then disagree about what
    an IN/tool hop is measuring.
    """
    return pools.render_name(drawn.person, ("surname", "given"), "nom", "clean", "none",
                             ctx.rng)


def stored_phone(drawn: Drawn) -> Rendered:
    """A phone as a backend COLUMN holds it: «+79164021187». The prose renders
    it through `mock.PROSE_NOTATION` as «+7 (916) 402-11-87», and that
    disagreement between the column and the page is the IN hop."""
    value = f"+7{drawn.phone}"
    return Rendered(value, value, False, {"digits": drawn.phone})


def grouped_card(digits: str) -> str:
    """A card as a bank's own screen prints it: four groups of four — the
    notation the RESULT carries and no caller register produces."""
    if len(digits) != 16:
        raise pools.BuildError(f"{digits!r} is not a 16-digit card")
    return " ".join(digits[start:start + 4] for start in range(0, 16, 4))


def spaced_snils(digits: str) -> str:
    """«XXX-XXX-XXX YY» — the ПФР's own separators."""
    if len(digits) != 11:
        raise pools.BuildError(f"{digits!r} is not an 11-digit СНИЛС")
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"


def iso_date(value: tuple[int, int, int]) -> str:
    day, month, year = value
    return f"{year:04d}-{month:02d}-{day:02d}"


def bank_client_seed(record_id: str, inn_digits: str, card_digits: str, drawn: Drawn,
                     builder: CaseBuilderV5, identity: str,
                     statement_rows: tuple[dict[str, str], ...]) -> dict[str, str]:
    """A row of `bank_clients`, in the shape `mock.BackendV5` READS it.

    ONE `name` COLUMN, NOT THREE. The first version of this helper wrote the
    CRM's `last_name`/`first_name`/`middle_name`; `mock._bank_row` reads a single
    `name`, so every seeded client came back with an empty name and no tag on any
    item — a case that scores the gateway on a hop the backend never produced.
    The row shapes the mock reads are the contract, and this file follows them.

    The card is stored in FOUR GROUPS because a bank's screen prints it that way,
    and a result in a notation the caller's register never writes is exactly the
    IN/tool hop `differs_from_user_form` exists to create. `statement_rows` are
    the ledger lines `account_statement` filters — not personal data, so they
    carry no items, but the holder repeats on every one of them, which is what
    K15 («many records of one person in one result») is counted on.
    """
    person = full_name(drawn.person)
    # `grouped` rather than `card`: `card` is the re-exported v4 renderer, and a
    # local of that name inside this module hides it from every later line here.
    grouped = grouped_card(card_digits)
    fields: dict[str, object] = {
        "name": person, "inn": inn_digits, "card": grouped, "phone": f"+7{drawn.phone}",
        "status": "active", "rows": [dict(row) for row in statement_rows]}
    return seeded(builder, record_id, "bank_clients", fields, {
        "name": ("NAME", identity, Rendered(person, person, False,
                                            {"surname": drawn.person.surname[0],
                                             "given": drawn.person.given[0],
                                             "gender": drawn.person.gender})),
        "inn": ("INN", identity, Rendered(inn_digits, inn_digits, False,
                                          {"digits": inn_digits})),
        "card": ("CARD", identity, Rendered(grouped, grouped, False,
                                            {"digits": card_digits})),
    })


def vehicle_seed(record_id: str, plate_canonical: str, drawn: Drawn,
                 builder: CaseBuilderV5, identity: str) -> dict[str, str]:
    """A row of `vehicles`: the plate in its canonical form and a NESTED owner.

    `mock._vehicle_check` reads `owner.last_name` / `owner.first_name`; a flat
    pair of columns beside the plate is read by nothing and tags nothing.
    """
    series, digits, letters, region = _plate_parts(plate_canonical)
    fields: dict[str, object] = {
        "plate": plate_canonical, "model": "Lada Vesta", "year": "2019",
        "owner": {"last_name": drawn.person.surname[0], "first_name": drawn.person.given[0]}}
    return seeded(builder, record_id, "vehicles", fields, {
        "plate": ("PLATE", identity, Rendered(plate_canonical, plate_canonical, False,
                                              {"series": series, "digits": digits,
                                               "letters": letters, "region": region})),
        "owner.last_name": ("NAME", identity,
                            Rendered(drawn.person.surname[0], drawn.person.surname[0], False,
                                     {"surname": drawn.person.surname[0],
                                      "gender": drawn.person.gender})),
        "owner.first_name": ("NAME", identity,
                             Rendered(drawn.person.given[0], drawn.person.given[0], False,
                                      {"given": drawn.person.given[0],
                                       "gender": drawn.person.gender})),
    })


def snils_seed(record_id: str, snils_digits: str, drawn: Drawn,
               builder: CaseBuilderV5, identity: str) -> dict[str, str]:
    """A row of `snils_records`, what `snils_verify` returns. The СНИЛС is
    stored with the ПФР separators and the birth date in ISO — two notations no
    speech register produces, which is the point of reading them back."""
    separated = spaced_snils(snils_digits)
    iso = iso_date(drawn.dob)
    fields: dict[str, object] = {**_person_fields(drawn.person), "status": "valid",
                                 "snils": separated, "birth_date": iso}
    return seeded(builder, record_id, "snils_records", fields, {
        "last_name": _name_column(drawn.person, "surname", identity),
        "first_name": _name_column(drawn.person, "given", identity),
        "snils": ("SNILS", identity, Rendered(separated, separated, False,
                                              {"digits": snils_digits})),
        "birth_date": ("DOB", identity, Rendered(iso, iso, False, {"iso": iso})),
    })


def patient_seed(record_id: str, snils_digits: str, drawn: Drawn,
                 builder: CaseBuilderV5, identity: str) -> dict[str, str]:
    """A row of `patients`, what `patient_find` returns: the clinic's card.

    THREE NOTATIONS NO SPEECH REGISTER WRITES, in one result — the birth date in
    ISO, the СНИЛС with the ПФР separators, the phone in E.164. That is the
    whole reason the clinic needed a READING tool: its other five write, so
    every value in their results is one the dialogue handed them a moment
    earlier and the IN/tool hop measures nothing about the vertical's own form.
    The ТЗ §2 promised «ДР ISO, СНИЛС с разделителями» as the clinic's return
    format and 584 hops of the corpus checked none of it.

    THE PHONE IS STORED AND ALSO SAID BY THE CALLER, on purpose: it is the key
    the search is made on, so the same datum crosses as IN/user, as OUT/tool_arg
    and back as IN/tool, and the card's notation can be compared with the one it
    was dictated in.
    """
    separated = spaced_snils(snils_digits)
    iso = iso_date(drawn.dob)
    phone = f"+7{drawn.phone}"
    fields: dict[str, object] = {**_person_fields(drawn.person), "birth_date": iso,
                                 "snils": separated, "phone": phone,
                                 "policy": f"ОМС {record_id}"}
    return seeded(builder, record_id, "patients", fields, {
        "last_name": _name_column(drawn.person, "surname", identity),
        "first_name": _name_column(drawn.person, "given", identity),
        "birth_date": ("DOB", identity, Rendered(iso, iso, False, {"iso": iso})),
        "snils": ("SNILS", identity, Rendered(separated, separated, False,
                                              {"digits": snils_digits})),
        "phone": ("PHONE", identity, Rendered(phone, phone, False, {"digits": drawn.phone})),
    })


def calendar_seed(record_id: str, drawn: Drawn, builder: CaseBuilderV5,
                  identity: str) -> dict[str, str]:
    """A row of `calendar`, what `calendar_free` returns: whose calendar it is.

    THE FREE SLOTS ARE NOT SEEDED AND ARE NOT PERSONAL DATA. `mock._calendar_
    slots` derives them from the record id and the asked-for date, in two
    notations out of four, so the DATE form a case can measure is the mock's
    and not a column somebody could forget to write. The table is `calendar`,
    singular — the mock names it that way and a row in `calendar_entries` is a
    row no tool reads.
    """
    iso = iso_date(drawn.dob)
    person = full_name(drawn.person)
    fields: dict[str, object] = {"person": person, "birth_date": iso}
    return seeded(builder, record_id, "calendar", fields, {
        "person": ("NAME", identity, Rendered(person, person, False,
                                              {"surname": drawn.person.surname[0],
                                               "given": drawn.person.given[0],
                                               "gender": drawn.person.gender})),
        "birth_date": ("DOB", identity, Rendered(iso, iso, False, {"iso": iso})),
    })


# --- documents ------------------------------------------------------------------

def csv_row_fields(drawn: Drawn) -> dict[str, str]:
    """One line of the CSV `file_read` hands back as its `list` form, in the
    column order `mock._file_read` reads (`CSV_HEADER`)."""
    return {"last_name": drawn.person.surname[0], "first_name": drawn.person.given[0],
            "phone": f"+7{drawn.phone}", "email": f"{drawn.email_local}@{drawn.email_domain}",
            "birth_date": iso_date(drawn.dob)}


def csv_row_typed(index: int, drawn: Drawn,
                  identity: str) -> dict[str, tuple[str, str, Rendered]]:
    """…and its items, keyed by the path the mock tags by (`csv_row_path`)."""
    row = csv_row_fields(drawn)
    return {
        csv_row_path(str(index), "last_name"): _name_column(drawn.person, "surname", identity),
        csv_row_path(str(index), "first_name"): _name_column(drawn.person, "given", identity),
        csv_row_path(str(index), "phone"): ("PHONE", identity, Rendered(
            row["phone"], row["phone"], False, {"digits": drawn.phone})),
        csv_row_path(str(index), "email"): ("EMAIL", identity, Rendered(
            row["email"], row["email"], False, {"local": drawn.email_local,
                                                "domain": drawn.email_domain})),
        csv_row_path(str(index), "birth_date"): ("DOB", identity, Rendered(
            row["birth_date"], row["birth_date"], False, {"iso": row["birth_date"]})),
    }


def form_document_fields(drawn: Drawn, city: str, series: str, number: str,
                         snils_digits: str) -> dict[str, object]:
    """The flat columns `mock._form_parse` reads out of a filled application
    form: ФИО, birth date, passport in two halves, СНИЛС, address by parts."""
    return {**_person_fields(drawn.person), "birth_date": iso_date(drawn.dob),
            "passport_series": series, "passport_number": number,
            "snils": spaced_snils(snils_digits), "city": city,
            "street": drawn.address.street, "house": f"{drawn.address.house}{drawn.address.letter}",
            "flat": str(drawn.address.flat) if drawn.address.flat else ""}


def form_document_typed(drawn: Drawn, ctx: Ctx, series: str, number: str,
                        snils_digits: str,
                        identity: str) -> dict[str, tuple[str, str, Rendered]]:
    """…and the items of those columns. `city` carries NO item: a bare city
    identifies nobody, the engine refuses bare cities on purpose, and an item on
    one would be a permanent miss the gateway is right to produce.

    `house` CARRIES NO ITEM EITHER, FOR THE SAME REASON (round 4). «19» on its
    own names nobody, no gateway masks it, and the ground truth loses nothing
    because the STREET item's parts already carry the house (`rendered_address`
    splits the whole address). Declared as an item it did worse than sit there:
    its two-character surface is a needle, and «19» stands inside «1977-01-07»
    and «7931», so `doc_masked` read the form's own birth date as the house
    number surviving unmasked and printed 92 of 100 for a gateway that had
    done everything right."""
    iso = iso_date(drawn.dob)
    separated = spaced_snils(snils_digits)
    rendered_address = pools.render_address(drawn.address, "clean", ctx.rng, False)
    return {
        "last_name": _name_column(drawn.person, "surname", identity),
        "first_name": _name_column(drawn.person, "given", identity),
        "middle_name": _name_column(drawn.person, "patronymic", identity),
        "birth_date": ("DOB", identity, Rendered(iso, iso, False, {"iso": iso})),
        "passport_series": ("PASSPORT", identity, Rendered(series, series, False,
                                                           {"series": series})),
        "passport_number": ("PASSPORT", identity, Rendered(number, number, False,
                                                           {"number": number})),
        "snils": ("SNILS", identity, Rendered(separated, separated, False,
                                              {"digits": snils_digits})),
        "street": ("LOC", f"{identity}.home", Rendered(
            drawn.address.street, drawn.address.street, False, dict(rendered_address.parts))),
    }


def document_seed(record_id: str, path: str, doc_format: str, title: str,
                  fields: dict[str, object], typed_paths: dict[str, tuple[str, str, Rendered]],
                  builder: CaseBuilderV5) -> dict[str, str]:
    """One row of `documents` — the table `file_read`, `doc_retrieve` and
    `form_parse` all read.

    THE FORMAT IS A COLUMN, NOT A BRANCH IN HERE. `csv` needs `rows`, `form`
    needs the flat application columns, `free_text` and `scan` need a
    `template`; each caller assembles its own with the helpers above and hands
    the result in, so this function has no branch a caller can take by accident
    and no shape it can silently write half of. `scan` is `free_text` plus the
    mock's OCR noise, seeded by the document id — the same page in every arm.
    """
    if doc_format not in ("csv", "free_text", "form", "scan"):
        raise pools.BuildError(f"unknown document format {doc_format!r}")
    row: dict[str, object] = {"path": path, "format": doc_format, "title": title, **fields}
    return seeded(builder, record_id, "documents", row, typed_paths)


# --- prose rows (a knowledge-base chunk, a ticket history) -----------------------

def prose_seed(record_id: str, table: str, template: str, values: dict[str, Rendered],
               typed: dict[str, tuple[str, str]], extra: dict[str, object],
               builder: CaseBuilderV5) -> dict[str, str]:
    """A backend row the mock renders as RUNNING PROSE from a `{field}` template.

    THE SHAPE IS THE MOCK'S, AND THE MOCK TAGS BY FIELD NAME.
    `mock._template_pieces` walks the template, looks each `{field}` up in the
    row's own columns and tags the piece with `_tag_of(record, field)` — the
    EXACT (table, id, path) map. So the item's `Locus.path` is the bare column
    name; the offsets inside the rendered chunk are laid down by the mock's own
    `Writer` as it composes, and nothing is ever searched for.

    (The 2026-09-22 ruling R-12 describes an earlier design — `{"text": …,
    "slots": {…}}` with `Locus.path == "slots.<key>"` and offsets into `text`.
    The landed `mock.py` implements the template shape instead, and a seed the
    mock does not read is a result with empty fields and no tags. The
    divergence is reported as a contract question rather than patched in a file
    this component does not own.)

    A value a column holds in one notation may be RENDERED in another:
    `mock.PROSE_NOTATION` writes a phone as «+7 (916) …», a СНИЛС with the ПФР
    separators and a card in four groups. That disagreement between the column
    and the prose is the IN hop this family exists to measure, so the item's
    value stays the column's.
    """
    missing = tuple(key for key in values if f"{{{key}}}" not in template)
    if missing:
        raise pools.BuildError(f"record {record_id!r}: template names no slot for {missing}")
    fields: dict[str, object] = {"template": template, **extra,
                                 **{key: rendered.surface for key, rendered in values.items()}}
    typed_paths: dict[str, tuple[str, str, Rendered]] = {}
    for key, rendered in values.items():
        if key not in typed:
            raise pools.BuildError(f"slot {key!r} of record {record_id!r} has no declared type")
        pii_type, identity = typed[key]
        typed_paths[key] = (pii_type, identity, rendered)
    return seeded(builder, record_id, table, fields, typed_paths)


def chunk_seed(record_id: str, template: str, values: dict[str, Rendered],
               typed: dict[str, tuple[str, str]], extra: dict[str, object],
               builder: CaseBuilderV5) -> dict[str, str]:
    """A row of `kb_chunks`: one retrieval chunk, one to three people in it.

    `extra` holds the columns the template names that are NOT personal data — a
    topic word, a case number. They are columns rather than values because every
    entry of `values` becomes a `PiiItem`, and an item of type "" is a type v4's
    validator does not know.
    """
    return prose_seed(record_id, "kb_chunks", template, values, typed, extra, builder)


def ticket_event_seed(record_id: str, issue_id: str, order: int, template: str,
                      values: dict[str, Rendered], typed: dict[str, tuple[str, str]],
                      builder: CaseBuilderV5) -> dict[str, str]:
    """A row of `ticket_events`: what `ticket_history` retells in prose, in
    `order` — the mock sorts the events of one `issue_id` by that column."""
    return prose_seed(record_id, "ticket_events", template, values, typed,
                      {"issue_id": issue_id, "order": order}, builder)


def _name_column(person: Person, part: str, identity: str) -> tuple[str, str, Rendered]:
    """One name column, typed, carrying the gender the comparator's
    grammatical-case vote cannot infer from a single word."""
    text = {"surname": person.surname[0], "given": person.given[0],
            "patronymic": person.patronymic[0]}[part]
    return ("NAME", identity, Rendered(text, text, False, {part: text, "gender": person.gender}))


