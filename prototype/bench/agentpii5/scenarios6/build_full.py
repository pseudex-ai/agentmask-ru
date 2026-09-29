"""AgentPII-RU v6 — build the full 500-case corpus from `plan_v6`.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.scenarios6.build_full

WHAT THIS FILE DOES. It instantiates every `plan_v6.PlanRow` into a `CaseV5`
through `new_builder_v6`/`CaseBuilderV6`, minting values with `gen_v6`, seeding
the v6 mock's records, declaring the hops, and reusing the v5 behaviour moves
(sequential_chain, memory_anaphora, retry_same_tool, same_tool_other_target,
parallel, fanout_pick, branching, user_in_loop, rag, document). Every case
carries `v6.industry`/`v6.provenance`; `main()` builds, validates, writes
`v6/corpus.v5.json` + `v6/ladder.json`, and exits 0 iff the verdict is clean.

THE RECIPES. Each of the 14 admitted types has a `_recipe`: the reading tool, its
lookup argument and result leaf, the writing tool and argument leaf, the seed
record fields (in the mock's OWN notation) and the cue words. The base loop is
«user says the value (cued) -> argument -> tool result -> answer», which is what
`_single` builds; the other behaviours wrap the same recipe.

WHY FOUR TYPES WILL SHOW A K6-16 LINE. A [K] type must never be a BARE positive
(no cue, no key). The bare check keys a seed item on `where.path in field_keys`.
For OGRNIP / OSAGO_POLICY / INTL_PASSPORT / DIPLOMA_NUMBER the mock's reading
field («rq_ogrnip», «series»/«number», «document_number») is NOT one of the
registry's `field_keys`, so the seed item is bare and `validate_corpus_v6`
reports K6-16 on exactly those four. That is a DATA mismatch (mock field name vs
registry key), not a generator lie, and it is left red so the owner fixes the
registry or renames the mock fields — the generator must not pretend a value it
cannot honestly key is keyed.

NOTHING HERE IMPORTS `pseudex` OR `licensing`, AND NOTHING HERE SEARCHES A
FINISHED STRING.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, replace

from bench.agentpii4 import pools
from bench.agentpii4.pools import Rendered
from bench.agentpii4.scenarios.common import ctx_for
from bench.agentpii5 import build_v6, gen_v6, pii_types, schema_v6
from bench.agentpii5.contracts import (CaseV5, ForcedError, Hop, ReturnExpectation)
from bench.agentpii5.scenarios5 import common as v5
from bench.agentpii5.scenarios5.common import (answer_hop, arg_hop, opener, seeded, told,
                                               tool_hop, user_hop)
from bench.agentpii5.scenarios6 import plan_v6
from bench.agentpii5.scenarios6.common6 import (new_builder_v6, procedure_records,
                                                skeleton_ids)
from bench.agentpii5.tools_v6 import TOOLS_V6, V6_META

SEED: int = 6
PROVENANCE: str = "documented-procedure"


@dataclass(frozen=True)
class Recipe:
    """Everything a behaviour needs to cross one v6 type through the mock.

    `read_tool` is the tool whose result carries the type back (IN/tool); `lookup`
    is the argument leaf the agent fills to ask for it (OUT/tool_arg); `result`
    is the result leaf the value comes back on; `field` is the seed record field
    the mock tags (the item's `where.path`). `cues` are the message cue words the
    [K] rule reads for non-bare MESSAGE items. `register` is the v4 system-prompt
    role. `extra_args` are additional plain columns a strict parse demands."""
    type_id: str
    role: str
    read_tool: str
    lookup: str
    result: str
    field: str
    return_form: str
    cues: tuple[str, ...]
    note: str


def _digits_parts(type_id: str, canonical: str) -> dict[str, str]:
    return {"digits": canonical} if "digits" in _spec(type_id).identifying_roles else {}


def _spec(type_id: str) -> pii_types.TypeSpec:
    for spec in pii_types.TYPE_REGISTRY:
        if spec.id == type_id:
            return spec
    raise ValueError(f"{type_id!r} is not a registered type")


# The 14 admitted types' recipes, read off tools_v6's FieldSpecs and mock_v6's
# stored field names. `field` is the seed record column the mock tags by.
RECIPES: dict[str, Recipe] = {
    "OGRNIP": Recipe("OGRNIP", "crm", "crm_requisite_get", "ogrnip",
                     "requisite.rq_ogrnip", "ogrnip", "single",
                     ("ОГРНИП", "огрнип", "рег. номер ИП"),
                     "ОГРНИП -> реквизиты -> ответ"),
    "BANK_ACCOUNT": Recipe("BANK_ACCOUNT", "bank", "bank_accounts_list", "client_id",
                           "Data.Account[].AccountDetails[].identification", "account", "list",
                           ("счёт", "счет", "расчётный счёт"),
                           "лицевой счёт из реестра счетов"),
    "CADASTRAL_NUMBER": Recipe("CADASTRAL_NUMBER", "gov", "egrn_extract_get",
                               "cadastral_number", "object.cadastral_number",
                               "cadastral_number", "nested", ("кадастровый номер", "КН", "кадастр"),
                               "кадастровый номер -> выписка"),
    "DIPLOMA_NUMBER": Recipe("DIPLOMA_NUMBER", "gov", "diploma_registry_check",
                             "blank_number", "document.number", "diploma_number", "single",
                             ("диплом", "серия и номер диплома", "документ об образовании"),
                             "диплом -> реестр"),
    "EMPLOYEE_TAB_NUMBER": Recipe("EMPLOYEE_TAB_NUMBER", "crm", "hr_employee_get",
                                  "tab_number", "value[].ТабельныйНомер", "tab_number", "single",
                                  ("табельный номер", "таб. №", "табельный"),
                                  "табельный номер -> карточка сотрудника"),
    "EPTS_NUMBER": Recipe("EPTS_NUMBER", "gov", "epts_status_get", "epts_number",
                          "epts", "epts", "single", ("ЭПТС", "электронный ПТС", "электронный паспорт"),
                          "ЭПТС -> статус"),
    "GIS_ZHKH_ELS": Recipe("GIS_ZHKH_ELS", "gov", "gis_gkh_account_get", "els",
                           "account.els", "els", "single", ("ЕЛС", "единый лицевой счёт", "ИЖКУ"),
                           "ЕЛС -> лицевой счёт ЖКУ"),
    "ICCID": Recipe("ICCID", "crm", "sim_replace_request", "new_iccid", "iccid",
                    "iccid", "single", ("ICCID", "номер сим-карты", "номер SIM"),
                    "ICCID -> замена сим-карты"),
    "INTL_PASSPORT": Recipe("INTL_PASSPORT", "gov", "flight_order_get",
                            "flight_order_id", "data.travelers[].documents[].number",
                            "passport_number", "nested", ("загранпаспорт", "загран", "паспорт для выезда"),
                            "загранпаспорт из брони"),
    "LOAN_CONTRACT_NUMBER": Recipe("LOAN_CONTRACT_NUMBER", "bank", "debtor_card_get",
                                   "contract_number", "loan.contract", "contract_number", "nested",
                                   ("кредитный договор", "договор займа", "номер договора"),
                                   "договор -> карточка должника"),
    "LOYALTY_CARD_NUMBER": Recipe("LOYALTY_CARD_NUMBER", "crm", "loyalty_card_bind",
                                  "card_number", "discountCard.ids.number", "card_number", "single",
                                  ("карта лояльности", "бонусная карта", "дисконтная карта"),
                                  "карта лояльности -> привязка"),
    "OMS_ENP": Recipe("OMS_ENP", "clinic", "oms_policy_find", "enp", "person.enp",
                      "enp", "single", ("полис", "полис ОМС", "ЕНП"), "ЕНП -> полис ОМС"),
    "OSAGO_POLICY": Recipe("OSAGO_POLICY", "gov", "osago_policy_check", "policy",
                           "policy.number", "osago_number", "single", ("ОСАГО", "полис ОСАГО", "автогражданка"),
                           "полис ОСАГО -> проверка"),
    "VIN": Recipe("VIN", "gov", "osago_policy_check", "vin", "vehicle.vin", "vin", "single",
                  ("VIN", "ВИН", "вин-код"), "VIN -> проверка ОСАГО"),
}

# The chain pairs: a READ tool whose ONE result carries two admitted types, so a
# `sequential_chain` row spends one case on two type-slots. `second_result` is
# the partner's leaf on the READER; `write_tool`/`write_path` is the DIFFERENT
# tool the partner value feeds (R12: an OUT hop sourced by another tool's IN).
CHAIN_SPECS: dict[tuple[str, str], dict[str, str]] = {
    ("OSAGO_POLICY", "VIN"): {"second_result": "vehicle.vin",
                              "write_tool": "insurance_claim_create", "write_path": "vehicle.vin"},
    ("EPTS_NUMBER", "VIN"): {"second_result": "vin",
                             "write_tool": "insurance_claim_create", "write_path": "vehicle.vin"},
}


def _mint(builder, type_id: str) -> Rendered:
    """Mint a value with `gen_v6` and guarantee non-empty `parts`.

    v4's validator refuses an item with empty `parts` (ground truth must be
    built, not searched), but `common6.v6_parts` leaves a whole-value type
    (LOAN_CONTRACT_NUMBER, OSAGO_POLICY, VIN, GIS_ZHKH_ELS — no digit
    identifying role) with empty parts. The comparator reads those by their
    WHOLE canonical (their field role is ""), so a single `whole` part keeps the
    ground truth complete without inventing a digit run the value does not have.
    """
    rendered = builder.mint(type_id)
    # THE SURFACE IS THE CANONICAL, NOT THE PRINTED FORM. A v6 identifier's
    # printed form may carry a «:» (CADASTRAL_NUMBER), a space (OSAGO) or a «-»
    # (GIS_ZHKH_ELS); the `voice_itn` register forbids sentence punctuation
    # `[.,;:!?]` and the canonical (squeezed / glyph-folded) is punctuation-free,
    # so dictating the canonical keeps every register buildable. The mock matches
    # by digit signature, so the same value is still found and tagged.
    surface = rendered.canonical or rendered.surface
    if rendered.parts:
        return Rendered(surface, rendered.canonical, rendered.spoken, dict(rendered.parts))
    return Rendered(surface, rendered.canonical, rendered.spoken, {"whole": rendered.canonical})


def _register_for(ctx) -> str:
    return ctx.register


def _seeded_item(builder, record_id: str, recipe: Recipe, rendered: Rendered,
                 identity: str) -> str:
    """Seed the mock record and return the item id the IN/tool hop names."""
    fields = {recipe.field: rendered.surface}
    typed = {recipe.field: (recipe.type_id, identity, rendered)}
    row = seeded(builder.v5, record_id, "v6_record", fields, typed)
    return row[recipe.field]


def _base_case(ctx, recipe: Recipe, industry: str, behaviour: str,
               chain_partner: str = "") -> CaseV5:
    """The base loop: user says the value, the agent asks the reader, the value
    comes back, the answer repeats it. `chain_partner` names a second type the
    same reader returns (for `sequential_chain`)."""
    identity = "p0"
    tools, reachable = _offer(industry, recipe)
    proc = "requisites-115fz"
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity=identity, cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note, procedure_ref=proc,
                             procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, identity)

    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("val", rendered)
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, identity, "required", False)})

    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(answer_hop(item, 3, turn, 2, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    return builder.build(behaviour)


def _chain_case(ctx, first: Recipe, second: Recipe, industry: str) -> CaseV5:
    """A two-type chain: the reader returns both types; the partner feeds a
    DIFFERENT tool (R12's «result of A -> argument of B»). The first type's value
    is the lookup; the partner is written back to its own write tool."""
    identity = "p0"
    spec = CHAIN_SPECS[(first.type_id, second.type_id)]
    write_tool, write_path = spec["write_tool"], spec["write_path"]
    second_result = spec["second_result"]
    tools, reachable = _offer(industry, first)
    tools = tuple(sorted(set(tools) | {write_tool}))
    builder = new_builder_v6(ctx, first.role, tools, tools, industry, PROVENANCE,
                             primary_identity=identity, cluster=f"{first.type_id}:{ctx.index}",
                             note=f"цепочка {first.type_id}->{second.type_id}",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    a = _mint(builder, first.type_id)
    b = _mint(builder, second.type_id)
    fields = {first.field: a.surface, second.field: b.surface}
    typed = {first.field: (first.type_id, identity, a),
             second.field: (second.type_id, identity, b)}
    row = seeded(builder.v5, f"rec-{ctx.index}", "v6_record", fields, typed)

    draft = builder.draft()
    draft.say(opener(ctx)).say(first.cues[0].lower())
    draft.value("val", a)
    draft.say("и").say(second.cues[0].lower())
    draft.value("b", b)
    draft.punct(".")
    turn, said = told(builder.v5, draft,
                      {"val": (first.type_id, identity, "required", False),
                       "b": (second.type_id, identity, "required", False)})

    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, first.read_tool, 0, first.lookup, 0, ""))
    builder.declare_hop(tool_hop(row[first.field], 2, turn, first.read_tool, 0, first.result))
    builder.declare_hop(tool_hop(row[second.field], 3, turn, first.read_tool, 0, second_result))
    builder.declare_hop(arg_hop(row[second.field], 4, turn, write_tool, 0, write_path, 3, ""))
    builder.declare_hop(answer_hop(row[second.field], 5, turn, 3, False))
    builder.expect_return(ReturnExpectation(first.read_tool, 0, first.return_form,
                                            (row[first.field], row[second.field])))
    return builder.build("sequential_chain")


def _retry_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    """A scripted refusal of the form, then a second call — retry_same_tool."""
    identity = "p0"
    tools, reachable = _offer(industry, recipe)
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity=identity, cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — отказ по форме, повтор",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, identity)
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("val", rendered)
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, identity, "required", False)})
    builder.force_error(ForcedError(recipe.read_tool, 0, "format",
                                    item, f"значение {{value}} не прошло проверку формата"))

    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, "error.subject"))
    builder.declare_hop(arg_hop(said["val"], 3, turn, recipe.read_tool, 1, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 4, turn, recipe.read_tool, 1, recipe.result))
    builder.declare_hop(answer_hop(item, 5, turn, 4, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 1, recipe.return_form, (item,)))
    return builder.build("retry_same_tool")


def _memory_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    """The value said at turn 1 is used at turn 2 without being re-said."""
    identity = "p0"
    tools, reachable = _offer(industry, recipe)
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, "synthetic",
                             primary_identity=identity, cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — анафора")
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, identity)

    d1 = builder.draft()
    d1.say(opener(ctx)).say("мой").say(recipe.cues[0].lower())
    d1.value("val", rendered)
    d1.punct(".")
    turn1, said = told(builder.v5, d1, {"val": (recipe.type_id, identity, "required", False)})
    d2 = builder.draft()
    d2.say("проверьте по нему и скажите что получилось")
    d2.punct(".")
    turn2, _ = told(builder.v5, d2, {})

    builder.declare_hop(user_hop(said["val"], 0, turn1))
    builder.declare_hop(arg_hop(said["val"], 1, turn2, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn2, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(answer_hop(item, 3, turn2, 2, False))
    from bench.agentpii5.scenarios5.common import MemorySpec
    builder.remember(MemorySpec(item_id=said["val"], first_turn=turn1, recall_turn=turn2,
                                anaphora="pronoun"))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    return builder.build("memory_anaphora")


def _parallel_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    """Two OUT hops in ONE assistant turn (a parallel_group)."""
    identity = "p0"
    tools, reachable = _offer(industry, recipe)
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity=identity, cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — параллельный вызов",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, identity)
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("val", rendered)
    draft.say("и проверь дважды")
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, identity, "required", False)})
    # TWO OUT hops, same turn, same group — the parallel contract (R09).
    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, "g1"))
    builder.declare_hop(arg_hop(said["val"], 2, turn, recipe.read_tool, 1, recipe.lookup, 0, "g1"))
    builder.declare_hop(tool_hop(item, 3, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(answer_hop(item, 4, turn, 3, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    return builder.build("parallel")


def _industry_tools(industry: str) -> tuple[str, ...]:
    """The v6 tools V6_META files under one industry, sorted and unique."""
    names = sorted({spec.base.name for spec in TOOLS_V6
                    if V6_META[spec.base.name].industry == industry})
    return tuple(names)


def _offer(industry: str, recipe: Recipe) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The tools a case offers: the reader plus every tool of the case's industry.

    Offering the whole industry keeps K6-14 honest: every v6 tool is reachable in
    >= 5 cases because its own industry carries >= 20. The reader is added too,
    because a type may be read by a tool filed under another industry (a bank
    reading a CADASTRAL_NUMBER through egrn_extract_get).
    """
    names = sorted(set(_industry_tools(industry)) | {recipe.read_tool})
    return names, names


def _same_tool_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    """Two identities, one tool — R11's «find(A), find(B)»."""
    tools, reachable = _offer(industry, recipe)
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — два лица, один инструмент",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    a = _mint(builder, recipe.type_id)
    b = _mint(builder, recipe.type_id)
    ra = _seeded_item(builder, f"rec-{ctx.index}-a", recipe, a, "p0")
    rb = _seeded_item(builder, f"rec-{ctx.index}-b", recipe, b, "p1")
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("a", a)
    draft.say("и ещё")
    draft.value("b", b)
    draft.punct(".")
    turn, said = told(builder.v5, draft,
                      {"a": (recipe.type_id, "p0", "required", False),
                       "b": (recipe.type_id, "p1", "required", False)})
    builder.declare_hop(user_hop(said["a"], 0, turn))
    builder.declare_hop(user_hop(said["b"], 1, turn))
    builder.declare_hop(arg_hop(said["a"], 2, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(ra, 3, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(arg_hop(said["b"], 4, turn, recipe.read_tool, 1, recipe.lookup, 1, ""))
    builder.declare_hop(tool_hop(rb, 5, turn, recipe.read_tool, 1, recipe.result))
    builder.declare_hop(answer_hop(ra, 6, turn, 3, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (ra,)))
    return builder.build("same_tool_other_target")


def _fanout_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    """A list of two candidates of the same type, pick one by value (R13)."""
    from bench.agentpii5.contracts import PickSpec
    tools, reachable = _offer(industry, recipe)
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — список, выбор по значению",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    a = _mint(builder, recipe.type_id)
    b = _mint(builder, recipe.type_id)
    ra = _seeded_item(builder, f"rec-{ctx.index}-a", recipe, a, "p0")
    rb = _seeded_item(builder, f"rec-{ctx.index}-b", recipe, b, "p1")
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("a", a)
    draft.say("найди и выбери первого")
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"a": (recipe.type_id, "p0", "required", False)})
    builder.declare_hop(user_hop(said["a"], 0, turn))
    builder.declare_hop(arg_hop(said["a"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(ra, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(arg_hop(ra, 3, turn, recipe.read_tool, 0, recipe.lookup, 2, ""))
    builder.declare_hop(answer_hop(ra, 4, turn, 2, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (ra, rb)))
    builder.set_pick(PickSpec(list_tool=recipe.read_tool, candidate_identities=("p0", "p1"),
                              target_identity="p0", act_tool=recipe.read_tool))
    return builder.build("fanout_pick")


def _branch_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    """found -> update, not-found -> create (R14)."""
    from bench.agentpii5.contracts import BranchSpec
    tools, reachable = _offer(industry, recipe)
    else_tool = next((t for t in tools if t != recipe.read_tool), recipe.read_tool)
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — ветвление",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, "p0")
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("val", rendered)
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, "p0", "required", False)})
    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(answer_hop(item, 3, turn, 2, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    builder.set_branch(BranchSpec(probe_tool=recipe.read_tool, seed_present=True,
                                  then_tool=recipe.read_tool, else_tool=else_tool))
    return builder.build("branching")


def _loop_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    """find -> show -> confirm -> act (R15)."""
    from bench.agentpii5.contracts import LoopSpec
    tools, reachable = _offer(industry, recipe)
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — человек в цикле",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, "p0")
    d1 = builder.draft()
    d1.say(opener(ctx)).say(recipe.cues[0].lower())
    d1.value("val", rendered)
    d1.say("покажите что нашли")
    d1.punct(".")
    turn1, said = told(builder.v5, d1, {"val": (recipe.type_id, "p0", "required", False)})
    d2 = builder.draft()
    d2.say("да это оно действуйте")
    d2.punct(".")
    turn2, _ = told(builder.v5, d2, {})
    builder.declare_hop(user_hop(said["val"], 0, turn1))
    builder.declare_hop(arg_hop(said["val"], 1, turn1, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn1, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(answer_hop(item, 3, turn1, 2, False))
    builder.declare_hop(arg_hop(item, 4, turn2, recipe.read_tool, 0, recipe.lookup, 2, ""))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    builder.set_loop(LoopSpec(find_tool=recipe.read_tool, show_turn=turn1, confirm_turn=turn2,
                              confirm_phrase="да это оно действуйте", act_tool=recipe.read_tool))
    return builder.build("user_in_loop")


def _rag_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    """A retrieval over chunks that hold another person (R17), with the v6 type
    still crossed through the reader."""
    from bench.agentpii5.contracts import RagSpec
    tools, reachable = _offer(industry, recipe)
    tools = tuple(sorted(set(tools) | {"kb_search"}))
    builder = new_builder_v6(ctx, recipe.role, tools, tools, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — поиск по базе",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, "p0")
    # A chunk with a FOREIGN identity (R17: >= 1 foreign identity). The foreign
    # item is keyed by the type's FIRST field key, never «id»: a seed at «id» is
    # not a `field_keys` entry, so `_bare_problems` would read the foreign value
    # as a bare positive (K6-16) and refuse a value that is honestly keyed.
    foreign = _mint(builder, recipe.type_id)
    foreign_key = _spec(recipe.type_id).field_keys[0]
    chunk = seeded(builder.v5, f"chunk-{ctx.index}", "kb_chunks",
                   {"template": f"клиент {{who}} с идентификатором {{{foreign_key}}}",
                    "who": "другой человек", foreign_key: foreign.surface},
                   {foreign_key: (recipe.type_id, "p1", foreign)})
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("val", rendered)
    draft.say("найди в базе")
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, "p0", "required", False)})
    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(arg_hop(said["val"], 3, turn, "kb_search", 0, "query", 0, ""))
    builder.declare_hop(tool_hop(chunk[foreign_key], 4, turn, "kb_search", 0, "hits[].text"))
    builder.declare_hop(answer_hop(item, 5, turn, 2, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    builder.expect_return(ReturnExpectation("kb_search", 0, "chunks", (chunk[foreign_key],)))
    builder.set_rag(RagSpec(tool_name="kb_search", k=1, chunk_ids=(f"chunk-{ctx.index}",),
                            foreign_identities=("p1",), query_item_ids=(said["val"],)))
    return builder.build("rag")


def _document_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    """A value read out of a file and written back (R18), with the v6 type."""
    from bench.agentpii5.contracts import DocumentSpec
    tools, reachable = _offer(industry, recipe)
    tools = tuple(sorted(set(tools) | {"file_read"}))
    builder = new_builder_v6(ctx, recipe.role, tools, tools, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — документ",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, "p0")
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower()).say("прочитай файл и проверь")
    draft.value("val", rendered)
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, "p0", "required", False)})
    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(arg_hop(item, 3, turn, recipe.read_tool, 0, recipe.lookup, 2, ""))
    builder.declare_hop(answer_hop(item, 4, turn, 2, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    builder.set_document(DocumentSpec(doc_id=f"doc-{ctx.index}", read_tool="file_read",
                                      format="free_text", record_count=1,
                                      record_ids=(f"rec-{ctx.index}",),
                                      extract_to_tool=recipe.read_tool,
                                      extracted_item_ids=(item,)))
    return builder.build("document")


# --- vertical coverage (K6-15): delivery / directory / files ---------------------
# The 14 recipes read through crm/bank/gov/clinic tools; the three reading
# verticals delivery/directory/files are offered but never crossed, so K6-15's
# K16 half flags them. One case per vertical reads a v5 NAME/PHONE back through
# a TOOLS_V6 tool of that vertical — coverage of any PII type, which is what the
# check counts. The plan leaves `plan_v6.VERTICAL_READER_CASES` slots for these.

_VERTICAL_READS: tuple[dict[str, str], ...] = (
    # tool, industry, role, lookup leaf, result leaf, return form, value, seed field, key, ask
    {"tool": "cdek_order_info", "industry": "logistics", "role": "delivery",
     "lookup": "cdek_number", "result": "entity.recipient.name", "form": "nested",
     "value": "NAME", "field": "name", "key": "PHONE", "ask": "заказ"},
    {"tool": "phone_clean", "industry": "retail", "role": "crm",
     "lookup": "source", "result": "items[].phone", "form": "canon",
     "value": "PHONE", "field": "source", "key": "PHONE", "ask": "нормализуйте телефон"},
    {"tool": "dwh_sql_query", "industry": "internal_bi", "role": "bank",
     "lookup": "sql", "result": "data[].client_fio", "form": "list",
     "value": "NAME", "field": "client_fio", "key": "NAME", "ask": "найдите клиента"},
)


def _vertical_case(ctx, vspec: dict[str, str]) -> CaseV5:
    """One reading hop through a TOOLS_V6 tool of a vertical the recipes never
    cross. The value read back is a v5 NAME or PHONE seeded into the tool's own
    record, in a notation the user's register does not write — the same IN/tool
    crossing that makes any other vertical «read»."""
    tool = vspec["tool"]
    identity = "p0"
    builder = new_builder_v6(ctx, vspec["role"], (tool,), (tool,), vspec["industry"],
                             "synthetic", primary_identity=identity,
                             cluster=f"{vspec['value']}:{ctx.index}",
                             note=f"вертикаль {vspec['value']} через {tool}")
    drawn = v5.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    name_r = v5.stored_name(drawn, ctx)
    phone_r = v5.stored_phone(drawn)
    if vspec["value"] == "NAME":
        stored, value_type = name_r, "NAME"
    else:
        stored, value_type = phone_r, "PHONE"
    # The record the tool reads: its lookup key plus the seeded value it returns.
    fields = {vspec["field"]: stored.surface, vspec["lookup"]: phone_r.surface}
    typed = {vspec["field"]: (value_type, identity, stored)}
    row = seeded(builder.v5, f"vc-{ctx.index}", "v6_record", fields, typed)
    item_id = row[vspec["field"]]

    draft = builder.draft()
    draft.say(opener(ctx)).say(vspec["ask"])
    if vspec["key"] == "PHONE":
        draft.value("key", v5.phone(ctx, drawn.phone))
    else:
        draft.value("key", v5.name(ctx, drawn.person, ("surname", "given")))
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"key": (vspec["key"], identity, "required", False)})

    builder.declare_hop(user_hop(said["key"], 0, turn))
    builder.declare_hop(arg_hop(said["key"], 1, turn, tool, 0, vspec["lookup"], 0, ""))
    builder.declare_hop(tool_hop(item_id, 2, turn, tool, 0, vspec["result"]))
    builder.declare_hop(answer_hop(item_id, 3, turn, 2, False))
    builder.expect_return(ReturnExpectation(tool, 0, vspec["form"], (item_id,)))
    return builder.build("single")


def _build_one(ctx, row: plan_v6.PlanRow) -> CaseV5:
    recipe = RECIPES[row.type_id]
    partner = ""
    if row.form.startswith(plan_v6.CHAIN_FORM_PREFIX):
        partner = row.form[len(plan_v6.CHAIN_FORM_PREFIX):]
    if row.behaviour == "sequential_chain" and partner:
        return _chain_case(ctx, recipe, RECIPES[partner], row.industry)
    if row.behaviour == "retry_same_tool":
        return _retry_case(ctx, recipe, row.industry)
    if row.behaviour == "memory_anaphora":
        return _memory_case(ctx, recipe, row.industry)
    if row.behaviour == "parallel":
        return _parallel_case(ctx, recipe, row.industry)
    if row.behaviour == "same_tool_other_target":
        return _same_tool_case(ctx, recipe, row.industry)
    if row.behaviour == "fanout_pick":
        return _fanout_case(ctx, recipe, row.industry)
    if row.behaviour == "branching":
        return _branch_case(ctx, recipe, row.industry)
    if row.behaviour == "user_in_loop":
        return _loop_case(ctx, recipe, row.industry)
    if row.behaviour == "rag":
        return _rag_case(ctx, recipe, row.industry)
    if row.behaviour == "document":
        return _document_case(ctx, recipe, row.industry)
    return _single(ctx, recipe, row.industry)


def _single(ctx, recipe: Recipe, industry: str) -> CaseV5:
    return _base_case(ctx, recipe, industry, "single")


def build_full(seed: int = SEED) -> list[CaseV5]:
    """Instantiate every plan row into a v6 case, in plan order."""
    cases: list[CaseV5] = []
    registers = _registers(seed)
    position = 0
    for row in plan_v6.PLAN_V6:
        for _ in range(row.count):
            register = registers[position % len(registers)]
            ctx = ctx_for(row.type_id, seed, position, register)
            case = _build_one(ctx, row)
            # K6-11: a streaming case rides the voice register (R20). Every 5th
            # voice_itn case is marked streaming — ≥ 30 of them, above the floor.
            if register == "voice_itn" and position % 5 == 0:
                case = replace(case, streaming=True)
            cases.append(case)
            position += 1
    # The three reading verticals the recipes never cross (K6-15): one case per
    # vertical seeds a v5 NAME/PHONE the tool returns. The plan leaves exactly
    # `plan_v6.VERTICAL_READER_CASES` slots for them, so the corpus sums to 500.
    for vspec in _VERTICAL_READS:
        register = registers[position % len(registers)]
        ctx = ctx_for(vspec["tool"], seed, position, register)
        case = _vertical_case(ctx, vspec)
        if register == "voice_itn" and position % 5 == 0:
            case = replace(case, streaming=True)
        cases.append(case)
        position += 1
    return cases


def _registers(seed: int) -> list[str]:
    """The register mix OD-07: chat 0.40 / voice 0.30 / sloppy 0.20 / clean 0.10,
    apportioned by Sainte-Laguë. «voice» is served by `voice_itn` (digits are
    written, not spoken) because a v6 identifier is a digit run that the
    `voice_raw` register refuses — 0 of 53 324 measured utterances carry one.

    NOT v5's `registers_for`: v6's shares differ (chat 0.40, not 0.30) and the
    voice bucket must be `voice_itn` alone, never `voice_raw`.
    """
    targets = {"chat": 0.40, "voice_itn": 0.30, "sloppy": 0.20, "clean": 0.10}
    delivered = {name: 0 for name in targets}
    out: list[str] = []
    for _ in range(500):
        name = min(targets, key=lambda n: (-targets[n] / (2 * delivered[n] + 1),
                                           delivered[n], n))
        delivered[name] += 1
        out.append(name)
    import random
    random.Random(f"v6-register:{seed}").shuffle(out)
    return out


def main() -> int:
    started = time.monotonic()
    cases = build_full()
    problems = schema_v6.validate_corpus_v6(cases, "full", 500)
    print(f"build_full: {len(cases)} случаев, {time.monotonic() - started:.1f}s")
    for line in schema_v6.type_floor_table(cases, "full"):
        print(line)
    for line in problems:
        print(f"RED {line}")
    if problems:
        print("build_full: FAIL")
        return 1
    digest = build_v6.write_corpus(cases, build_v6.V6_OUT)
    build_v6.write_ladder_v6(cases, build_v6.V6_OUT)
    print(f"build_full: PASS (corpus {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
