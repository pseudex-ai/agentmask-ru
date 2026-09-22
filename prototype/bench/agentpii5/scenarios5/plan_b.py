"""generator_b's plan, and the moves its four families share.

WHAT IS HERE. `PLAN_B` is what `build.py` imports: the four (module, count)
pairs of the conversational half of the corpus — the user in the loop, memory
and anaphora, retrieval, and documents. Above it sit the moves those four
families repeat: the hop constructors they do not share with generator_a
(`memory_hop`, `document_hop`), and `caller_card`, which opens a case the way
all four open it.

THE IMPORTS OF THE FOUR MODULES SIT AT THE BOTTOM, and this is now the only
file in the package that does it: `PLAN_B` must name the modules, and the four
modules import `caller_card`, `find_the_caller`, `city_for`, `stored_street` and
`plain_column` BY NAME from here — helpers that are still this half's alone. One
of the two edges has to close after the other. `plan_a` lost its copy of the
exception when its helpers moved to `common` (R-25); these will follow when a
second consumer for them exists, and not before, because moving a helper with
one caller into a shared module buys nothing.

`stored_name` AND `stored_phone` HAVE MOVED (R-25's rule, on their second
caller). generator_a's `single` family needed the same «as a backend holds it»
notation, and a second copy would be a second opinion about how a backend spells
a name — the two halves of the corpus would then disagree about what an IN/tool
hop measures. They live in `common` and are re-exported here, so the two family
modules that call them did not move with them.

WHY THE HOP CONSTRUCTORS COME FROM `common`. `user_hop`, `tool_hop`, `arg_hop`
and `answer_hop` are the same four moves in both halves of the corpus, and a
second copy of `arg_hop` would be a second opinion about which `form_hOUT` line
a leaf counts in. They used to be imported from `plan_a`; ruling R-25 moved
them to `common`, so neither plan imports the other any more — this half is
built even when generator_a's six modules are not loaded at all. They are
re-exported under the same names, as is `extra_people` (ruling R-32 put it in
`common` beside the `draw` it warns about), so the four family modules did not
move with them.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4 import pools
from bench.agentpii4.pools import BuildError
from bench.agentpii5.contracts import Hop, ReturnExpectation
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.common import CaseBuilderV5
from bench.agentpii5.scenarios5.common import (  # noqa: F401 - re-exported for the families
    answer_hop, arg_hop, extra_people, minted, stored_name, stored_phone, told, tool_hop,
    user_hop)

# How many cases each family of this half builds — the §8.2 floors minus what
# the revised v4 corpus already supplies. `user_in_loop` is the only one topped
# up: v4's `long_clinic` (45 cases) revises into it, and 45 + 40 is its floor of
# 85 exactly. The other three are families v4 never had, so their whole count is
# authored here.
LOOP_COUNT: int = 40
# SIX MORE THAN THE FLOOR, and the six are K02's share arm rather than a wish:
# the family sat exactly on 120, round 2 added 142 authored cases to the corpus
# (R-49's chain top-up and R-50's `single` family), and 120 of 1 736 is 6.9%
# against a floor of 7%. The §8.2 table is a floor with no ceiling, so the family
# keeps its share instead of the corpus being kept small for a number written
# before the two rulings. `plan_a.RETRY_COUNT` moved for the same reason.
MEMORY_COUNT: int = 126
RAG_COUNT: int = 100
DOCUMENT_COUNT: int = 100


# --- the two hops the other half never declares -------------------------------------

def memory_hop(item_id: str, index: int, turn: int, source_hop: int) -> Hop:
    """A value entering this turn FROM THE CONVERSATION, not from a message of
    it and not from a tool result.

    THE OWNER EXISTS BECAUSE THE FORM COMES FROM SOMEWHERE. Every IN owner names
    a source whose FORM the substitute must mirror; for a value the customer
    said six turns ago the source is the transcript the model is re-reading, and
    that is neither `user` (no message of THIS turn carries it) nor `tool` (no
    call returned it). Without the owner an anaphoric recall would have to be
    declared as an IN/user hop on a turn whose text does not contain the value,
    which R05 refuses — correctly.

    `source_hop` points back at the IN hop where the value first entered. It is
    carried even though R06 only constrains OUT hops: the chain is what
    `memory_stability` compares the two crossings of one substitute over, and a
    recall with no first mention to compare against measures nothing.
    """
    if source_hop < 0:
        raise BuildError(f"memory hop {index} has no first mention to recall; "
                         f"a value remembered from nowhere is not a memory")
    return Hop(kind="IN", owner="memory", item_id=item_id, hop_index=index, turn=turn,
               tool_name="", call_ordinal=-1, parallel_group="", source_hop=source_hop,
               path="", optional=False)


def document_hop(item_id: str, index: int, turn: int, tool: str, ordinal: int,
                 path: str) -> Hop:
    """A value arriving inside a FILE the agent read, at `path` in the payload.

    Told apart from IN/tool on purpose: a CSV cell, a scanned form field and an
    OCR-damaged line are a different notation problem from a JSON result, and
    merging them would hide which of the two the gateway mangles. `source_hop`
    stays -1 for the same reason it does on IN/tool — the chain link belongs to
    the OUT hop that carries the value onward.
    """
    return Hop(kind="IN", owner="document", item_id=item_id, hop_index=index, turn=turn,
               tool_name=tool, call_ordinal=ordinal, parallel_group="", source_hop=-1,
               path=path, optional=False)


# --- the move all four families open with -----------------------------------------

# The tool that turns a phone into a card, and the two leaves of its result this
# half reads back. One place, because four families quoting the same two paths
# is four chances to quote a third one that the registry does not carry.
FIND_TOOL: str = "crm_find_contact"
FIND_LEAVES: tuple[tuple[str, str], ...] = (
    ("last_name", "contacts[].last_name"), ("birth_date", "contacts[].birth_date"))


def caller_card(builder: CaseBuilderV5, ctx: c.Ctx, drawn: c.Drawn, city: str,
                identity: str) -> dict[str, str]:
    """The caller's own CRM row, seeded so the find has something to return.

    THE CALLER IS NEVER THE PERSON IN THE PAYLOAD. A document row, a knowledge
    base chunk or a second client in the same case carries a DIFFERENT person,
    because the mock indexes a seeded value by the value itself and drops any
    string two items share — a name in both the caller's card and the file would
    be tagged on neither, and every hop on it would score as a gateway miss that
    no gateway could avoid.
    """
    before = len(builder.v4.pii)
    c.contact_seed("c-caller", drawn, city, ctx, builder, identity)
    return {item.where.path: item.id for item in minted(builder, before)}


def find_the_caller(builder: CaseBuilderV5, card: dict[str, str], phone_item: str,
                    turn: int, phone_hop: int) -> tuple[int, int]:
    """Look the caller up by the phone they just gave, and read the card back.

    Returns `(the IN/tool hop on the surname, the next free hop index)`. The
    ReturnExpectation is declared here too: it names five items of ONE identity
    in one call, which is what K15 («many records of one person in one result»)
    is counted on, and declaring it beside the hops keeps the two from drifting.
    """
    index = builder.next_hop_index()
    builder.declare_hop(arg_hop(phone_item, index, turn, FIND_TOOL, 0, "query.phone",
                                phone_hop, ""))
    surname_hop = index + 1
    for offset, (field, path) in enumerate(FIND_LEAVES):
        builder.declare_hop(tool_hop(card[field], index + 1 + offset, turn, FIND_TOOL, 0, path))
    builder.expect_return(ReturnExpectation(
        FIND_TOOL, 0, "list",
        (card["last_name"], card["first_name"], card["phone"], card["birth_date"],
         card["address.street"])))
    return surname_hop, index + 1 + len(FIND_LEAVES)


def conversation_id(behaviour: str, index: int) -> str:
    """An explicit conversation id on every fifth case, derived on the rest.

    K09 wants both kinds to occur, and the two are not interchangeable: a
    derived id is `envelope.conversation_key` reading the first two messages,
    which a long dialogue changes under it. Every fifth case is the same rule
    generator_a applies, so the two halves do not disagree about the share.
    """
    return f"conv-{behaviour}-{index}" if index % 5 == 0 else ""


def city_for(ctx: c.Ctx) -> str:
    return ctx.rng.choice(list(pools.CORPUS_CITIES))


def stored_street(drawn: c.Drawn) -> pools.Rendered:
    """A street as a backend column holds it: the bare name, no generic word."""
    street = drawn.address.street
    return pools.Rendered(street, street, False, {"street": street})


def plain_column(text: str) -> pools.Rendered:
    """A template slot that is NOT personal data — a topic, a case number. It
    still goes through `Rendered` where a caller needs one, so there is no
    second path for «just a string» that could put the column and the template
    out of step."""
    return pools.Rendered(text, text, False, {})


# The four families, imported LAST — see the module docstring for why.
from bench.agentpii5.scenarios5 import (  # noqa: E402 - the cycle closes here on purpose
    document, memory_anaphora, rag, user_in_loop)

PLAN_B: tuple[tuple[object, int], ...] = (
    (user_in_loop, LOOP_COUNT),
    (memory_anaphora, MEMORY_COUNT),
    (rag, RAG_COUNT),
    (document, DOCUMENT_COUNT),
)
