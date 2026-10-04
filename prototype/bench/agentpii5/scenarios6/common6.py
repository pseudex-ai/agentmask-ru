"""What every v6 family shares: the builder that assembles a `CaseV5` whose
`v6` field names its industry and provenance, the v6 value mint (`gen_v6`),
the starter skeleton registry, and the widening of v4's tool registry so R02
admits the v6 tool names.

v6 MIRRORS v5, IT DOES NOT REPLACE IT. `CaseBuilderV6` HOLDS a v5
`CaseBuilderV5` (`self.v5`) instead of extending it, exactly as v5 holds v4's
`CaseBuilder`: the v5 declarations (hops, returns, behaviour specs) and the
v5 baseline stay one definition in `scenarios5/common.py`, and a subclass
would sooner or later write a v6 field into a v5 path and move the baseline
with the treatment. The v6 builder adds ONE axis — the `CaseV6Meta` carried on
`CaseV5.v6` — and ONE source of values, `gen_v6.generate`, never a search of a
finished string (R6-26's "derive from the seed" discipline, the same rule v5's
`RecordDraft` applies one layer down).

THE THREE LAYERS ARE KEPT APART ON PURPOSE (tz-agentpii6 §3.1). The SKELETON
(language, exchange flow, operator stamps, cue typos, register) lives in
`v6/skeletons.json`, paraphrased as placeholder patterns — never a literal
value, never a verbatim quote. The PROCEDURE (the ordered steps from a norm or
an API) lives in `PROCEDURES` below as `ProcedureRecord`s with a `doc_ref` and
`steps`. The VALUE is minted here by `gen_v6.generate(type_id, seed)` and never
recovered from the finished message or record text.

THE ONE DOCUMENTED SIDE EFFECT ON v4's MODULE OBJECT. `tools.py` widens v4's
`REGISTRY` with the 24 v5 new tools (ruling R-24) so `v4.validate` — which R02
calls on `CaseV5.base` — accepts their names. The v6 tools live in `tools_v6.py`
and are NOT widened there, so this module does the same for `TOOLS_V6`: without
it no v6 case could offer a v6 tool at all, because `v4.validate` refuses any
`case.tools` name outside v4's `REGISTRY`. The names are checked to collide
with nothing, so the widening ADDS names and replaces none.

NOTHING HERE IMPORTS `pseudex` OR `licensing`, AND NOTHING HERE SEARCHES A
FINISHED STRING.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from bench.agentpii4 import pools
from bench.agentpii4.pools import Rendered
from bench.agentpii4.schema import InvalidCase
from bench.agentpii4.tools import REGISTRY as V4_REGISTRY
from bench.agentpii5 import gen_v6
from bench.agentpii5 import pii_types
from bench.agentpii5.contracts import (INDUSTRIES, V6_PROVENANCE_KINDS, CaseV5, CaseV6Meta,
                                       ProcedureRecord, ReturnExpectation)
from bench.agentpii5.scenarios5 import common as v5common
from bench.agentpii5.scenarios5.common import (CaseBuilderV5, answer_hop, arg_hop, new_builder,
                                               opener, seeded, told, tool_hop, user_hop)
from bench.agentpii5.tools import REGISTRY_V5
from bench.agentpii5.tools_v6 import TOOLS_V6

# --- the widening (see the module docstring) --------------------------------------
# TWO registries must learn the v6 tools, and they learn DIFFERENT shapes:
#
# * v4's `REGISTRY` maps tool name -> v4 `ToolSpec`. `v4.validate` (which R02
#   calls on `CaseV5.base`) reads `.fields` / `.mutating` / `.result_pii` off
#   its values, and `v4tools.spec_for` (the argument-leaf lookup behind
#   `arg_hop`) does the same — so register each v6 `ToolSpecV5.base`, the v4
#   object the wrapper COMPOSES, not the wrapper itself.
# * `REGISTRY_V5` maps tool name -> `ToolSpecV5`. R19 (`schema._declared_return_
#   forms`) reads `spec.return_forms` off its values to check a `ReturnExpectation`,
#   so the v5 registry must carry the v6 WRAPPER, not its base.
#
# Both dicts are the SAME module objects `schema.py` and `tools.py` already hold
# names for (`from ... import REGISTRY` / `REGISTRY_V5`), so mutating them here is
# the one widening every consumer sees — the same move `tools.py` itself made for
# the 24 v5 new tools (ruling R-24). A name is checked to collide with nothing, so
# the widening ADDS and replaces none.
_V6_NAMES: frozenset[str] = frozenset(spec.base.name for spec in TOOLS_V6)
_V6_COLLISIONS: tuple[str, ...] = tuple(sorted(_V6_NAMES & set(REGISTRY_V5)))
if _V6_COLLISIONS:
    # A collision would REPLACE a v4/v5 spec with a v6 one and silently score
    # every old case against a different API. Refused at import, like tools.py's
    # `_COLLIDING_TOOL_NAMES`.
    raise RuntimeError(f"v6 tool names collide with the v5 registry: {_V6_COLLISIONS}")
V4_REGISTRY.update({spec.base.name: spec.base for spec in TOOLS_V6})
REGISTRY_V5.update({spec.base.name: spec for spec in TOOLS_V6})


# --- the starter procedures registry ----------------------------------------------
# A `documented-procedure` case cites `procedure_ref` into here (R6-24 resolves
# the reference, then checks the case's declared calls carry `steps` in order).
# Each `doc_ref` is the primary source the steps were read from — never a URL
# invented to look documented. STARTER: the four flows the starter skeletons
# below cover, to be expanded alongside the skeleton registry.
PROCEDURES: dict[str, ProcedureRecord] = {
    # 115-ФЗ customer identification: read the requisites by key, write them back.
    "requisites-115fz": ProcedureRecord(
        doc_ref="https://apidocs.bitrix24.ru/api-reference/crm/requisites/universal/"
                "crm-requisite-fields.html",
        steps=("crm_requisite_get", "crm_requisite_set")),
    # ФНС «Проверка статуса плательщика НПД»: identify by ИНН, then check status.
    "npd-status": ProcedureRecord(
        doc_ref="https://npd.nalog.ru/html/sites/www.npd.nalog.ru/api_statusnpd_nalog_ru.pdf",
        steps=("crm_requisite_get", "npd_status_check")),
    # Mindbox loyalty lookup: resolve a card to a customer, then act on the card.
    "retail-loyalty": ProcedureRecord(
        doc_ref="https://developers.mindbox.ru/",
        steps=("loyalty_customer_get", "loyalty_card_bind")),
    # МИС / СФР: resolve the ОМС policy, then read the ЭЛН record off it.
    "medicine-oms-eln": ProcedureRecord(
        doc_ref="https://lk.sfr.gov.ru/eln/Спецификация_ЭЛН_МО_v_2.1.docx",
        steps=("oms_policy_find", "eln_get")),
}


def procedure_records() -> dict[str, ProcedureRecord]:
    """The procedure registry a `documented-procedure` case resolves against."""
    return dict(PROCEDURES)


# --- the starter skeleton registry -------------------------------------------------

SKELETONS_FILE: Path = Path(__file__).resolve().parent.parent / "v6" / "skeletons.json"


def load_skeletons(path: str | Path | None = None) -> dict:
    """The starter skeleton registry, parsed from `v6/skeletons.json`.

    The file holds `{"skeletons": [{"id", "source", "register", "industry",
    "skeleton"}]}`. A skeleton is a paraphrased PATTERN with placeholders
    `<NAME> <NUMBER> <PHONE> <ADDR> <DATE>`; it never carries a literal
    personal-data value nor a verbatim quote (tz-agentpii6 §3.1).
    """
    target = Path(path) if path is not None else SKELETONS_FILE
    return json.loads(target.read_text(encoding="utf-8"))


def skeleton_ids(path: str | Path | None = None) -> frozenset[str]:
    """The ids a `live-register` case may cite in `skeleton_ref`."""
    return frozenset(entry.get("id", "") for entry in load_skeletons(path)["skeletons"])


# --- the v6 value mint --------------------------------------------------------------

def _type_spec(type_id: str) -> pii_types.TypeSpec:
    for spec in pii_types.TYPE_REGISTRY:
        if spec.id == type_id:
            return spec
    raise ValueError(f"common6: {type_id!r} is not a registered pii type")


def _v6_seed(seed: int, index: int, ordinal: int) -> int:
    """A deterministic int seed for `gen_v6.generate` from the case's own
    (seed, index) and the mint ordinal.

    NOT Python's `hash()` — its string hashing is salted per process and would
    make the corpus differ between builds. hashlib.sha256 is stable, and the
    (seed, index) pair is exactly what the case id (`kind-index`) already
    carries, so R6-26's "re-derive from the seed" stays within reach when the
    scrub gate lands.
    """
    raw = f"v6:{seed}:{index}:{ordinal}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def v6_parts(type_id: str, canonical: str) -> dict[str, str]:
    """The `parts` a v6 item carries, from its `identifying_roles`.

    The comparator's `expected_leaf_value` reads `item.parts.get(role)`, so a
    digit role needs the digit run present. For a digit-notation type the
    canonical IS the digit run (gen_v6 drops every non-digit), and for the one
    squeezed-with-digits type (CADASTRAL_NUMBER) the squeezed form is also all
    digits, so `canonical` is the right value in both cases. A free-form or
    glyph-fold type has no identifying role, so its parts are empty — its whole
    value is its identity.
    """
    spec = _type_spec(type_id)
    if "digits" in spec.identifying_roles:
        return {"digits": canonical}
    return {}


def v6_rendered(type_id: str, seed: int) -> Rendered:
    """One v6 value minted by `gen_v6.generate`, wrapped as a `Rendered` with
    the parts the comparator reads. The surface is the value's natural written
    form, the canonical is the vault key, never a search of a finished string."""
    value, canonical = gen_v6.generate(type_id, seed)
    return Rendered(surface=value, canonical=canonical, spoken=False,
                    parts=v6_parts(type_id, canonical))


# --- the builder ---------------------------------------------------------------------

@dataclass
class CaseBuilderV6:
    """The v6 case kit: v5's builder plus the v6 meta and the v6 value mint.

    Composition over subclassing, the same move v5 made over v4: every v5
    declaration (`declare_hop`, `expect_return`, the behaviour specs) and every
    v4 move (`user`, `seed`) is re-exposed from `self.v5`, so a v6 scenario
    declares its hops and specs exactly as a v5 one does, and only the value
    source and the `v6` meta are new. `build(behaviour)` runs v5's own
    validation (R01-R21) and then checks the v6 meta, so no invalid case and no
    ill-formed `CaseV6Meta` can reach the corpus.
    """

    v5: CaseBuilderV5
    industry: str
    provenance: str
    skeleton_ref: str = ""
    procedure_ref: str = ""
    procedures: dict[str, ProcedureRecord] = field(default_factory=dict)
    _mint_ordinal: int = 0

    # --- the v4/v5 moves, re-exposed -------------------------------------------

    @property
    def ctx(self):
        return self.v5.ctx

    def draft(self):
        return self.v5.draft()

    def user(self, draft, typed) -> int:
        return self.v5.user(draft, typed)

    def seed(self, record_id: str, table: str, fields: dict[str, object],
             typed_paths: dict[str, tuple[str, str, Rendered]]) -> None:
        self.v5.seed(record_id, table, fields, typed_paths)

    def seed_spans(self, record_id: str, table: str, fields: dict[str, object],
                   typed_paths: dict[str, tuple[str, str, Rendered]],
                   spans: dict[str, tuple[int, int]]) -> None:
        self.v5.seed_spans(record_id, table, fields, typed_paths, spans)

    # --- the v5 declarations, re-exposed ---------------------------------------

    def declare_hop(self, hop) -> None:
        self.v5.declare_hop(hop)

    def next_hop_index(self) -> int:
        return self.v5.next_hop_index()

    def expect_return(self, expectation: ReturnExpectation) -> None:
        self.v5.expect_return(expectation)

    def force_error(self, forced) -> None:
        self.v5.force_error(forced)

    def remember(self, memory) -> None:
        self.v5.remember(memory)

    def set_pick(self, pick) -> None:
        self.v5.set_pick(pick)

    def set_branch(self, branch) -> None:
        self.v5.set_branch(branch)

    def set_loop(self, loop) -> None:
        self.v5.set_loop(loop)

    def set_rag(self, rag) -> None:
        self.v5.set_rag(rag)

    def set_document(self, document) -> None:
        self.v5.set_document(document)

    def set_streaming(self, streaming: bool) -> None:
        self.v5.set_streaming(streaming)

    # --- the v6 moves ----------------------------------------------------------

    def mint(self, type_id: str) -> Rendered:
        """Mint ONE v6 value and return its `Rendered`, ready for a message
        (`draft.value` + `told`) or a seed (`seeded`).

        The seed is this case's own `(ctx.seed, ctx.index, mint ordinal)`, so
        the same case always mints the same value and a different case never
        does. The `Rendered` carries no identity — the caller names the person
        when it attaches the value to a locus, exactly as v5 does. Nothing here
        searches a finished string.
        """
        seed = _v6_seed(self.ctx.seed, self.ctx.index, self._mint_ordinal)
        self._mint_ordinal += 1
        return v6_rendered(type_id, seed)

    def build(self, behaviour: str) -> CaseV5:
        """The v5 case, plus the v6 meta, or every problem raised by name.

        v5's `build` already runs `validate_v5` (R01-R21) and raises; the only
        thing added here is the well-formedness of `CaseV6Meta`, which R01-R21
        do not inspect because they predate it. The refs are RESOLVED here, not
        just shaped: a live-register case must name a skeleton in
        `skeletons.json`, a documented-procedure one a procedure in `procedures`
        — R6-24's promise, held at the point of writing rather than three
        thousand cases later in `build_v6 --check`.
        """
        case = self.v5.build(behaviour)
        meta = CaseV6Meta(industry=self.industry, provenance=self.provenance,
                          skeleton_ref=self.skeleton_ref, procedure_ref=self.procedure_ref)
        problems = _meta_problems(case.base.id, meta, self.procedures)
        if problems:
            raise InvalidCase(f"{case.base.id} ({behaviour}):\n  " + "\n  ".join(problems))
        return replace(case, v6=meta)


def _meta_problems(case_id: str, meta: CaseV6Meta,
                   procedures: dict[str, ProcedureRecord]) -> list[str]:
    """The v6 meta's own rules, each a separate line so a reviewer maps a line
    to a field without reading this file. The refs are resolved here."""
    problems: list[str] = []
    if meta.industry not in INDUSTRIES:
        problems.append(f"{case_id}: industry {meta.industry!r} not in INDUSTRIES")
    if meta.provenance not in V6_PROVENANCE_KINDS:
        problems.append(f"{case_id}: provenance {meta.provenance!r} not in "
                        f"V6_PROVENANCE_KINDS")
    # R6-24's halves: the ref is carried iff its provenance tag requires it.
    if (meta.skeleton_ref != "") != (meta.provenance == "live-register"):
        problems.append(f"{case_id}: skeleton_ref is {meta.skeleton_ref!r} but provenance "
                        f"is {meta.provenance!r}; live-register iff skeleton_ref set")
    if (meta.procedure_ref != "") != (meta.provenance == "documented-procedure"):
        problems.append(f"{case_id}: procedure_ref is {meta.procedure_ref!r} but provenance "
                        f"is {meta.provenance!r}; documented-procedure iff procedure_ref set")
    if meta.provenance == "live-register" and meta.skeleton_ref not in skeleton_ids():
        problems.append(f"{case_id}: skeleton_ref {meta.skeleton_ref!r} is not in "
                        f"v6/skeletons.json")
    if meta.provenance == "documented-procedure" and meta.procedure_ref not in procedures:
        problems.append(f"{case_id}: procedure_ref {meta.procedure_ref!r} is not a "
                        f"declared ProcedureRecord")
    return problems


def new_builder_v6(ctx, role: str, tools: tuple[str, ...], reachable: tuple[str, ...],
                   industry: str, provenance: str, primary_identity: str = "",
                   cluster: str = "", note: str = "", extras: tuple[str, ...] = (),
                   skeleton_ref: str = "", procedure_ref: str = "",
                   procedures: dict[str, ProcedureRecord] | None = None) -> CaseBuilderV6:
    """A v6 builder over a fresh v5 one, with the v6 meta and value mint in
    place. Mirrors `new_builder`: the v5 half (role, tools, reachable, the
    system prompt) is v5's own, and the v6 half is the industry/provenance axis
    plus the refs and the procedure registry it resolves against.

    `procedures` defaults to the module `PROCEDURES` (a COPY, so a scenario that
    extends it does not edit the shared starter set behind other cases' backs).
    """
    inner = new_builder(ctx, role, tools, reachable, primary_identity, cluster, note, extras)
    return CaseBuilderV6(
        v5=inner, industry=industry, provenance=provenance, skeleton_ref=skeleton_ref,
        procedure_ref=procedure_ref,
        procedures=dict(procedures) if procedures is not None else dict(PROCEDURES))


# --- worked examples: the two behaviours that MUST build ----------------------------
# A v6 scenario author declares hops and specs exactly as a v5 one does; these
# three are the minimal proof that `sequential_chain` and `memory_anaphora` (and
# the base `single` loop) assemble a valid v6 case. They exist so `test_scenarios6`
# can assert the builder, not a reimplementation of it.

def single_case(ctx, industry: str = "retail", provenance: str = "documented-procedure",
                skeleton_ref: str = "", procedure_ref: str = "requisites-115fz",
                procedures: dict[str, ProcedureRecord] | None = None) -> CaseV5:
    """The base loop through ONE v6 tool: the customer says an ОГРНИП, the CRM
    reads the requisites back, the answer repeats it. The value is `OGRNIP`
    (a v6 type, mod-13 checksum) minted by `gen_v6`; the tool is
    `crm_requisite_get` (a v6 tool, retail)."""
    identity = "p0"
    tool = "crm_requisite_get"
    # Offer the reader plus two the vertical really has, so «which tool» stays a
    # question the arm can get wrong rather than a one-tool elimination.
    tools = (tool, "crm_requisite_set", "phone_clean")
    builder = new_builder_v6(ctx, "crm", tools, (tool,), industry, provenance,
                             primary_identity=identity, cluster=f"OGRNIP:{ctx.index}",
                             note="v6 base loop: ОГРНИП -> реквизиты -> ответ",
                             skeleton_ref=skeleton_ref, procedure_ref=procedure_ref,
                             procedures=procedures)
    rendered = builder.mint("OGRNIP")
    row = seeded(builder.v5, "req-1", "crm_requisites",
                 {"rq_ogrnip": rendered.surface},
                 {"rq_ogrnip": ("OGRNIP", identity, rendered)})

    draft = builder.draft()
    draft.say(opener(ctx)).say("проверьте реквизиты по огрнип")
    draft.value("ogrnip", rendered)
    draft.say("скажите чей он")
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"ogrnip": ("OGRNIP", identity, "required", False)})

    builder.declare_hop(user_hop(said["ogrnip"], 0, turn))
    builder.declare_hop(arg_hop(said["ogrnip"], 1, turn, tool, 0, "ogrnip", 0, ""))
    builder.declare_hop(tool_hop(row["rq_ogrnip"], 2, turn, tool, 0, "requisite.rq_ogrnip"))
    builder.declare_hop(answer_hop(row["rq_ogrnip"], 3, turn, 2, False))
    builder.expect_return(ReturnExpectation(tool, 0, "single", (row["rq_ogrnip"],)))
    return builder.build("single")


def sequential_chain_case(ctx, industry: str = "banks_mfo_collectors",
                          provenance: str = "documented-procedure",
                          skeleton_ref: str = "", procedure_ref: str = "npd-status",
                          procedures: dict[str, ProcedureRecord] | None = None) -> CaseV5:
    """A chain across TWO tools: the ОГРНИП names the requisites, the ИНН read
    back feeds the ФНС status check. The OUT/tool_arg hop on `npd_status_check`
    sources the IN/tool hop of `crm_requisite_get` — R12's "fed by the result of
    ANOTHER tool". The ОГРНИП is v6 (`gen_v6`); the ИНН is a v5 type drawn from
    v5's pools, as a v5 value always is."""
    identity = "p0"
    get_tool = "crm_requisite_get"
    check_tool = "npd_status_check"
    tools = (get_tool, check_tool, "crm_requisite_set")
    builder = new_builder_v6(ctx, "bank", tools, (get_tool, check_tool), industry, provenance,
                             primary_identity=identity, cluster=f"OGRNIP:{ctx.index}",
                             note="v6 chain: ОГРНИП -> ИНН -> статус НПД",
                             skeleton_ref=skeleton_ref, procedure_ref=procedure_ref,
                             procedures=procedures)
    ogrnip = builder.mint("OGRNIP")
    inn_digits = pools.inn12_digits(ctx.rng)
    inn = Rendered(inn_digits, inn_digits, False, {"digits": inn_digits})
    row = seeded(builder.v5, "req-1", "crm_requisites",
                 {"rq_ogrnip": ogrnip.surface, "rq_inn": inn_digits},
                 {"rq_ogrnip": ("OGRNIP", identity, ogrnip),
                  "rq_inn": ("INN", identity, inn)})

    draft = builder.draft()
    draft.say(opener(ctx)).say("проверьте реквизиты по огрнип")
    draft.value("ogrnip", ogrnip)
    draft.say("и статус плательщика нпд")
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"ogrnip": ("OGRNIP", identity, "required", False)})

    builder.declare_hop(user_hop(said["ogrnip"], 0, turn))
    builder.declare_hop(arg_hop(said["ogrnip"], 1, turn, get_tool, 0, "ogrnip", 0, ""))
    builder.declare_hop(tool_hop(row["rq_inn"], 2, turn, get_tool, 0, "requisite.rq_inn"))
    # THE CHAIN: the ИНН read back from tool A is the argument of tool B.
    builder.declare_hop(arg_hop(row["rq_inn"], 3, turn, check_tool, 0, "inn", 2, ""))
    builder.declare_hop(answer_hop(row["rq_inn"], 4, turn, 2, False))
    builder.expect_return(ReturnExpectation(get_tool, 0, "single",
                                            (row["rq_ogrnip"], row["rq_inn"])))
    return builder.build("sequential_chain")


def memory_anaphora_case(ctx, industry: str = "retail", provenance: str = "synthetic",
                         skeleton_ref: str = "", procedure_ref: str = "",
                         procedures: dict[str, ProcedureRecord] | None = None) -> CaseV5:
    """A value said at turn 1 and used again at turn 2 WITHOUT being re-said
    («проверьте по нему») — R16's memory loop, with the value minted by `gen_v6`
    and carried back through the v6 tool."""
    identity = "p0"
    tool = "crm_requisite_get"
    tools = (tool, "crm_requisite_set", "phone_clean")
    builder = new_builder_v6(ctx, "crm", tools, (tool,), industry, provenance,
                             primary_identity=identity, cluster=f"OGRNIP:{ctx.index}",
                             note="v6 memory: ОГРНИП сказан в 1-й реплике, использован во 2-й",
                             skeleton_ref=skeleton_ref, procedure_ref=procedure_ref,
                             procedures=procedures)
    rendered = builder.mint("OGRNIP")
    row = seeded(builder.v5, "req-1", "crm_requisites",
                 {"rq_ogrnip": rendered.surface},
                 {"rq_ogrnip": ("OGRNIP", identity, rendered)})

    draft1 = builder.draft()
    draft1.say(opener(ctx)).say("мой огрнип")
    draft1.value("ogrnip", rendered)
    draft1.punct(".")
    turn1, said = told(builder.v5, draft1, {"ogrnip": ("OGRNIP", identity, "required", False)})

    draft2 = builder.draft()
    draft2.say("проверьте по нему реквизиты и скажите чьи они")
    draft2.punct(".")
    turn2, _ = told(builder.v5, draft2, {})

    builder.declare_hop(user_hop(said["ogrnip"], 0, turn1))
    builder.declare_hop(arg_hop(said["ogrnip"], 1, turn2, tool, 0, "ogrnip", 0, ""))
    builder.declare_hop(tool_hop(row["rq_ogrnip"], 2, turn2, tool, 0, "requisite.rq_ogrnip"))
    builder.declare_hop(answer_hop(row["rq_ogrnip"], 3, turn2, 2, False))
    builder.remember(v5common.MemorySpec(item_id=said["ogrnip"], first_turn=turn1,
                                         recall_turn=turn2, anaphora="pronoun"))
    builder.expect_return(ReturnExpectation(tool, 0, "single", (row["rq_ogrnip"],)))
    return builder.build("memory_anaphora")
