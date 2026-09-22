"""generator_a's plan: the six (module, count) pairs of the multi-call half.

WHAT IS HERE AND WHY SO LITTLE OF IT. `PLAN_A` is what `build.py` imports. The
moves the six families repeat — the four hop constructors and the three
bookkeeping helpers — USED to live here; ruling R-25 moved them to
`scenarios5/common.py`, where both halves of the corpus reach them without one
plan importing the other. They are re-exported below under exactly the names
the six modules already import, so the move cost those modules nothing; the
re-export is for one release, after which each family imports them from
`common` and the line goes.

THE FAMILY IMPORTS ARE AT THE TOP, like every other file in this repository —
the bottom-of-file exception this module used to carry is gone with the
helpers. THEIR ORDER IS LOAD-BEARING, though: `PLAN_A` must name the modules
and the modules import their helpers BY NAME from here, so the re-export has
to be bound before the first family module executes. Python resolves it in
both directions — a family imported first finds `plan_a` fresh, `plan_a`
imported first offers a module whose names are already bound.
`test_generator_a.test_import_orders` pins both orders.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.

WHY THE SEED ROWS ARE WRITTEN BY THE FAMILIES AND NOT TAKEN FROM `common.py`'s
seeders. The backend row shapes `mock.BackendV5` READS and the ones
`scenarios5.common`'s seed helpers WRITE do not agree for four tables
(`bank_clients`, `vehicles`, `calendar`, and every prose row); a case seeded
through those helpers returns a result with the PII fields empty and no tag on
any item, which would score the gateway on hops that never happened. Until that
is reconciled these families seed through `common.seeded` in the shape the mock
reads, and `test_generator_a.test_backend_returns_the_declared_items` runs the
real mock over a sample of every family to prove it.
"""
# The helpers first, the families second: the order of these two statements is
# what lets a family import its helpers from here while `PLAN_A` names it.
from bench.agentpii5.scenarios5.common import (  # noqa: F401 - re-exported for the families
    answer_hop, arg_hop, full_name, grouped_card, iso_date, minted, seeded, spaced_snils,
    told, tool_hop, user_hop)
from bench.agentpii5.scenarios5 import (  # noqa: I001 - see the docstring on the order
    branching, fanout_pick, parallel, retry_same_tool, same_tool_other_target,
    sequential_chain, single)

# How many cases each family of this half builds. The §8.2 floors minus what the
# revised v4 corpus already supplies: `sequential_chain` (149 revised after
# R-49), `fanout_pick` (117), `branching` (35) and `single` are topped up, the
# other three come only from here.
#
# THREE COUNTS MOVED IN ROUND 2 AND EACH ONE IS A RULING, NOT A PREFERENCE.
# `CHAIN_COUNT` grew because R-49 took 85 revised cases out of the chain family
# (an update's argument is the value the customer just stated, never the lookup's
# stale one), and a family at 189 of a floor of 180 has no margin to lose the
# next honest case to; 70 puts it above the floor by more than a fifth with every
# transition proven by the mock at build.
# `SINGLE_COUNT` is R-50: the revised corpus supplies the COUNT of the base loop
# and not its SHAPE — 379 of its 463 cases are v4's two-hop lookup — so the
# four-hop loop is authored here.
# `RETRY_COUNT` and `MEMORY_COUNT` (in `plan_b`) grew by six each because K02's
# share arm is RELATIVE: the two families sat exactly on their floor of 120, the
# corpus grew by 142 authored cases under the two rulings above, and 120/1736 is
# 6.9% against a floor of 7%. §8.2's table is a floor and not a ceiling, so the
# honest move is to keep the two families at their share rather than to keep the
# corpus small enough for a number that was written before the rulings.
RETRY_COUNT: int = 126
OTHER_TARGET_COUNT: int = 50
CHAIN_COUNT: int = 70
PARALLEL_COUNT: int = 100
FANOUT_COUNT: int = 40
BRANCHING_COUNT: int = 50
SINGLE_COUNT: int = 100

PLAN_A: tuple[tuple[object, int], ...] = (
    (retry_same_tool, RETRY_COUNT),
    (same_tool_other_target, OTHER_TARGET_COUNT),
    (sequential_chain, CHAIN_COUNT),
    (parallel, PARALLEL_COUNT),
    (fanout_pick, FANOUT_COUNT),
    (branching, BRANCHING_COUNT),
    (single, SINGLE_COUNT),
)
