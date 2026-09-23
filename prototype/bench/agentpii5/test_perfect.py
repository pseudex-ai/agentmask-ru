"""THE ACCEPTANCE TEST OF THE INSTRUMENT ITSELF.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_perfect              # tier medium, ~30 s
    python3 -m bench.agentpii5.test_perfect --tier max   # the WHOLE corpus, ~3 min

Two halves, and neither is worth anything alone:

  * a RIGHT gateway (`perfect.simulate`) must clear a declared bound on EVERY
    line — the claim «these numbers are earnable» made checkable;
  * SIX WRONG gateways must FAIL the same bounds — because an acceptance test
    a wrong gateway can also pass is not an acceptance test, it is a printout.

And a third thing the round-4 proof taught: the three corrections that made the
probe honest are themselves rules, so each is REVERTED here and the run must go
red. A correction nobody can knock down is a correction nobody can trust.

WHY `medium` (300 cases) IS THE DEFAULT, AND WHY THE OLD REASON IS GONE. It used
to be «the smallest tier on which all three corrections bite»: reverting
correction 1 moved nothing on `nano` or `small`, measured. That was a property of
a ladder whose every debug tier was ONE register — 30, 120 and 300 `voice_raw`
cases. On the recut ladder all three corrections bite on all three tiers
(measured: nano 5 / 4 / 2 breaches, small 4 / 5 / 1, medium 4 / 5 / 1), so the
default no longer rests on that. It rests on the DENOMINATORS: on `nano`,
`consistency` is 3/3 and `answer_real` 10/10, and a line of three observations
certifies almost nothing whichever way it lands. `medium` is the smallest tier
whose every line has a denominator worth reading, and the whole file is thirteen
passes, ~30 s.

AND WHY THE DEFAULT IS NOT THE WHOLE STORY. Every number this benchmark
publishes comes from `max` — all 1736 cases — and for five rounds nothing in
the repository checked the floors there: `answer_real` printed whole on `medium`
and 636/637 on `max`, and only a scratch script ever saw the second number. A
bound that is only ever tested on a slice of the corpus it is a claim about is
a bound with a blind spot, so `--tier max` runs the SAME checks over the
whole corpus: all of them, not a weakened subset — the three corrections and the
six wrong gateways were measured to bite there too. It is slow (~3 min) and it is
the run to make before any number is quoted; `medium` stays the default so the
file remains cheap enough for every change.

WHICH CORPUS AND WHICH LADDER THE NUMBERS COME FROM, AND WHY BOTH. Every
per-tier number a right gateway prints lives in `RECORDED` and is CHECKED
against the probe on every run; every illustrative number in a docstring here is
measured with `--tier max`, which moves only when the CORPUS moves and not when
the ladder is recut. The two together are the lesson of the recut: the file used
to quote «medium 2808/2808» and «medium 0.8139», measured on a `medium` of 300
`voice_raw` cases, while the ladder on disk had been redrawn the same day — the
paragraph named the corpus and not the tier, so the one thing that had changed
was the one thing it did not pin. Corpus `b80300397179` (`corpus_digest_v5`;
stamp `9d5b624572fa`), 1 736 cases, 2026-09-23.

OFFLINE BY CONSTRUCTION: no model, no network, no keys, no engine — the corpus,
the tool registry and arithmetic.
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, replace

from bench.agentpii4.schema import PiiItem
from bench.agentpii4.tools import flatten
from bench.agentpii5 import contracts, metrics, observe, perfect
from bench.agentpii5.contracts import ArmRunV5, CaseV5, Line
from bench.agentpii5.observe import fold, value_needles

# The tier the file runs on when `--tier` says nothing. See the module docstring
# for why it is not `small` (correction 1 is invisible below 300 cases) and why
# `max` is a mode rather than the default (it is the corpus every published
# number comes from, and it costs three minutes).
ACCEPTANCE_TIER: str = "medium"
TIERS: tuple[str, ...] = ("nano", "small", "medium", "large", "holdout", "max")


@dataclass(frozen=True)
class Bound:
    """What a RIGHT gateway must print on one line.

    `floor` is the rate it must reach, `ceiling` the rate it must not exceed,
    and BOTH `None` means the line makes no claim about the gateway — which is
    a statement, not an omission, so `why` is mandatory either way. Every
    measured number quoted below is from this probe: the `medium` figure is
    what this file asserts against, the corpus figure is the round-4 proof over
    all 1736 cases.
    """

    floor: float | None
    ceiling: float | None
    why: str


_EARNED: str = "a right gateway earns it whole: medium 1.0000, corpus 1.0000"

# THE TABLE IS THE CLAIM. A metric with no row here is a red test, not a line
# that quietly goes unchecked — that is precisely how v4 shipped four metrics
# nothing could fail.
BOUNDS: dict[str, Bound] = {
    # --- the value lines: masked going in, real coming out, one fake per identity
    "leak": Bound(1.0, None, _EARNED),
    "coverage": Bound(1.0, None, _EARNED),
    "typed": Bound(1.0, None, _EARNED),
    "round_trip": Bound(1.0, None, _EARNED),
    "round_trip_repaired": Bound(1.0, None, "the repaired twin of `round_trip`; a right "
                                            "gateway needs no repair, so the two are equal"),
    "end_to_end": Bound(1.0, None, _EARNED),
    "overmask": Bound(1.0, None, "a right gateway touches no negative; the counts per "
                                 "tier are in `RECORDED`"),
    "consistency": Bound(1.0, None, _EARNED),
    "stability": Bound(1.0, None, _EARNED),
    "toolresult_masked": Bound(1.0, None, _EARNED),
    "answer_real": Bound(1.0, None, "NO residue on any tier (`RECORDED`; `max` 637/637). "
                                    "The «one answer whose required datum the probe's own "
                                    "prose cannot carry» this row used to name was never the "
                                    "prose: the observer derived the restored window from the "
                                    "RAW side's offsets and lost a pure insertion sitting on "
                                    "its boundary, so the comparator was handed «+79037654» "
                                    "for a phone the gateway had restored whole "
                                    "(`observe._restored_window`, round 6)"),
    "chain_value": Bound(1.0, None, _EARNED),
    "chain_form": Bound(1.0, None, _EARNED),
    "multi_all_out": Bound(1.0, None, _EARNED),
    "multi_consistency": Bound(1.0, None, _EARNED),
    "retry_form": Bound(1.0, None, _EARNED),
    "memory_consistency": Bound(1.0, None, _EARNED),
    "rag_masked": Bound(1.0, None, _EARNED),
    "rag_identity_kept": Bound(1.0, None, _EARNED),
    "doc_masked": Bound(1.0, None, _EARNED),
    "doc_extracted": Bound(1.0, None, _EARNED),
    "residual": Bound(1.0, None, _EARNED),
    "stream_fidelity": Bound(1.0, None, _EARNED),

    # --- the form lines: the two that a right gateway cannot print whole
    "form_hOUT": Bound(0.99, None,
                       "EVERY TIER EARNS IT WHOLE — the counts are in `RECORDED` and are "
                       "checked, not quoted. THE FLOOR STAYS UNDER 1.0000, and not out of "
                       "caution: the answer half of the denominator rides on an ALIGNMENT of "
                       "two strings, so a substitute of a different length can leave an "
                       "OPTIONAL answer hop with no region to compare, and "
                       "`observe._out_answer` drops such a hop by design — 17 of 15 758 left "
                       "the denominator when the NAME pool arrived. A bound of 1.0000 would "
                       "go red for that arithmetic rather than for a gateway. One percentage "
                       "point is far under every gateway aimed at this line: on `max`, "
                       "0.7254 for one that upper-cases, 0.8723 for one that answers a case "
                       "of its own, 0.8440 for one that answers its own notation — and "
                       "`test_wrong_gateways_are_caught` proves all three every run, so the "
                       "distance is a check and these three figures are only its size"),
    "form_hIN": Bound(0.80, None,
                      "THE WHOLE RESIDUE IS DICTATED VALUES AGAINST WRITTEN SUBSTITUTES "
                      "(docs/known-issues.md Б27, an ENGINE finding, not an instrument one: "
                      "on `max`, written hops 10909/10909, dictated 253/923). The per-tier "
                      "counts are in `RECORDED`. THE FLOOR IS NOT MOVED NOW THAT THE TIERS "
                      "LOOK BETTER, and that is the point of a floor: the recut took every "
                      "tier into 0.9368–0.9577 (`max` 0.9434), because the old «medium "
                      "0.8139» was not a measurement of this line but of a tier made of 300 "
                      "`voice_raw` cases — one register, the dictated one. The share of "
                      "dictated hops is a property of a tier's register mix, and a future "
                      "recut may move it again; raising the floor to today's band would be "
                      "granting this line a promise decided after the numbers were seen. The "
                      "line that catches a masking failure is `leak`, never this one"),

    # --- the lines that make no claim about the gateway
    "out_absent": Bound(None, 0.0,
                        "a CEILING, not a floor: it counts declared OUT hops the agent never "
                        "wrote. A right agent writes them all (`RECORDED`, zero on every "
                        "tier) and an agent that drops its last call prints about a quarter "
                        "— `wrong_absent_call`, proved every run by "
                        "`test_wrong_gateways_are_caught`"),
    "rewrite_ratio_v5": Bound(None, None,
                              "it compares the gateway arm's reply with the CONTROL arm's, and "
                              "this probe writes both — so it measures the probe's prose, not "
                              "the gateway. Bounding it would certify a tautology"),
    "shared_block_answer": Bound(None, None,
                                 "a diagnostic: answer spans the alignment could not assign to "
                                 "ONE item. It is a property of the sentence the agent wrote, "
                                 "and the probe writes its own sentences"),
    "answer_optional_only": Bound(None, None,
                                  "a diagnostic about the CORPUS — answers whose case obliges "
                                  "no datum — i.e. what `answer_real`'s denominator leaves out. "
                                  "No gateway can move it"),
}


@dataclass(frozen=True)
class Probe:
    """The corpus slice and what the right gateway prints on it, computed once.

    `tier` rides along so every message names the corpus it is about: a failure
    that says «0/0 on tier medium» and one that says «0/0 on tier max» send a
    reader to different places."""

    tier: str
    cases: tuple[CaseV5, ...]
    perfect: dict[str, Line]


def measure(cases: Sequence[CaseV5], simulate: Callable[[CaseV5], ArmRunV5]) -> dict[str, Line]:
    """Every single-arm line over the runs `simulate` leaves on `cases`."""
    seen = tuple(observe.observe(case, simulate(case), None, None) for case in cases)
    return {name: metrics.METRIC_FUNCTIONS[name](seen) for name in perfect.SINGLE_ARM_METRICS}


def build_probe(tier: str) -> Probe:
    cases = perfect.cases_of_tier(perfect.load_cases(perfect.CORPUS_PATH),
                                  perfect.load_ladder(perfect.LADDER_PATH), tier)
    return Probe(tier=tier, cases=tuple(cases), perfect=measure(cases, perfect.simulate))


# --- what a right gateway ACTUALLY prints, tier by tier ------------------------------

# Every single-arm line a right gateway (`perfect.simulate`) prints on every tier
# of the RECORDED ladder, as (hits, total). Measured 23.09.2026 on corpus
# `b80300397179` (`corpus_digest_v5`, stamp `9d5b624572fa`) and ladder tiers
# nano `aabd26cb17de` · small `7aeb7b42af9e` · medium `745a0cb63e3e` · large
# `73b832fa5ac2` · holdout `47fe55f7ad51` · max `f0f6dd85c768`.
#
# WHY A TABLE AND NOT A SENTENCE. The numbers used to live in the `why` of each
# bound, as prose, and prose is not checked: two tracks of one session moved the
# ladder and probed it, and the file shipped «medium 2808/2808» and «medium
# 0.8139» for a `medium` that no longer existed — the same disease the docstring
# above declares closed, reproduced in the same file on the same day. A number
# nothing reads is a number nothing can keep true.
#
# WHY A REFUSAL AND NOT A WARNING. The point of re-measuring is that somebody
# LOOKS: a recut of the ladder is exactly the moment to ask whether a bound still
# describes what it claims to. A printed drift would be read by the same nobody
# who read the stale sentence.
#
# A ROW IS NOT A BOUND. `BOUNDS` says what a right gateway MUST clear and never
# moves with the corpus; this says what it DOES print and moves with every recut.
# Merging them would turn every bound into «whatever we measured last», which is
# a floor that cannot fail.
RECORDED: dict[str, dict[str, tuple[int, int]]] = {
    "nano": {
        "answer_optional_only": (12, 22),
        "answer_real": (10, 10),
        "chain_form": (12, 12),
        "chain_value": (12, 12),
        "consistency": (3, 3),
        "coverage": (192, 192),
        "doc_extracted": (7, 7),
        "doc_masked": (2, 2),
        "end_to_end": (109, 109),
        "form_hIN": (182, 192),
        "form_hOUT": (218, 218),
        "leak": (192, 192),
        "memory_consistency": (11, 11),
        "multi_all_out": (17, 17),
        "multi_consistency": (17, 17),
        "out_absent": (0, 184),
        "overmask": (30, 30),
        "rag_identity_kept": (6, 6),
        "rag_masked": (6, 6),
        "residual": (248, 248),
        "retry_form": (2, 2),
        "rewrite_ratio_v5": (0, 30),
        "round_trip": (88, 88),
        "round_trip_repaired": (88, 88),
        "shared_block_answer": (30, 62),
        "stability": (3, 3),
        "stream_fidelity": (0, 0),
        "toolresult_masked": (31, 31),
        "typed": (107, 107),
    },
    "small": {
        "answer_optional_only": (51, 94),
        "answer_real": (43, 43),
        "chain_form": (61, 61),
        "chain_value": (61, 61),
        "consistency": (32, 32),
        "coverage": (807, 807),
        "doc_extracted": (30, 30),
        "doc_masked": (7, 7),
        "end_to_end": (508, 508),
        "form_hIN": (756, 807),
        "form_hOUT": (1050, 1050),
        "leak": (807, 807),
        "memory_consistency": (41, 41),
        "multi_all_out": (64, 64),
        "multi_consistency": (78, 78),
        "out_absent": (0, 835),
        "overmask": (120, 120),
        "rag_identity_kept": (25, 25),
        "rag_masked": (27, 27),
        "residual": (1170, 1170),
        "retry_form": (9, 9),
        "rewrite_ratio_v5": (0, 120),
        "round_trip": (410, 410),
        "round_trip_repaired": (410, 410),
        "shared_block_answer": (154, 275),
        "stability": (32, 32),
        "stream_fidelity": (3, 3),
        "toolresult_masked": (133, 133),
        "typed": (473, 473),
    },
    "medium": {
        "answer_optional_only": (128, 236),
        "answer_real": (108, 108),
        "chain_form": (162, 162),
        "chain_value": (162, 162),
        "consistency": (74, 74),
        "coverage": (2059, 2059),
        "doc_extracted": (68, 68),
        "doc_masked": (18, 18),
        "end_to_end": (1327, 1327),
        "form_hIN": (1934, 2059),
        "form_hOUT": (2716, 2716),
        "leak": (2059, 2059),
        "memory_consistency": (107, 107),
        "multi_all_out": (166, 166),
        "multi_consistency": (197, 197),
        "out_absent": (0, 2153),
        "overmask": (300, 300),
        "rag_identity_kept": (51, 51),
        "rag_masked": (58, 58),
        "residual": (3016, 3016),
        "retry_form": (22, 22),
        "rewrite_ratio_v5": (0, 300),
        "round_trip": (1073, 1073),
        "round_trip_repaired": (1073, 1073),
        "shared_block_answer": (390, 710),
        "stability": (74, 74),
        "stream_fidelity": (12, 12),
        "toolresult_masked": (332, 332),
        "typed": (1217, 1217),
    },
    "large": {
        "answer_optional_only": (257, 470),
        "answer_real": (213, 213),
        "chain_form": (322, 322),
        "chain_value": (322, 322),
        "consistency": (136, 136),
        "coverage": (4088, 4088),
        "doc_extracted": (119, 119),
        "doc_masked": (35, 35),
        "end_to_end": (2682, 2682),
        "form_hIN": (3839, 4088),
        "form_hOUT": (5489, 5489),
        "leak": (4088, 4088),
        "memory_consistency": (210, 210),
        "multi_all_out": (318, 318),
        "multi_consistency": (387, 387),
        "out_absent": (0, 4324),
        "overmask": (600, 600),
        "rag_identity_kept": (96, 96),
        "rag_masked": (112, 112),
        "residual": (6089, 6089),
        "retry_form": (44, 44),
        "rewrite_ratio_v5": (0, 600),
        "round_trip": (2211, 2211),
        "round_trip_repaired": (2211, 2211),
        "shared_block_answer": (780, 1403),
        "stability": (136, 136),
        "stream_fidelity": (23, 23),
        "toolresult_masked": (658, 658),
        "typed": (2402, 2402),
    },
    "holdout": {
        "answer_optional_only": (130, 267),
        "answer_real": (137, 137),
        "chain_form": (169, 169),
        "chain_value": (169, 169),
        "consistency": (75, 75),
        "coverage": (2338, 2338),
        "doc_extracted": (58, 58),
        "doc_masked": (19, 19),
        "end_to_end": (1502, 1502),
        "form_hIN": (2239, 2338),
        "form_hOUT": (2937, 2937),
        "leak": (2338, 2338),
        "memory_consistency": (130, 130),
        "multi_all_out": (174, 174),
        "multi_consistency": (218, 218),
        "out_absent": (0, 2404),
        "overmask": (347, 347),
        "rag_identity_kept": (83, 83),
        "rag_masked": (97, 97),
        "residual": (3284, 3284),
        "retry_form": (25, 25),
        "rewrite_ratio_v5": (0, 347),
        "round_trip": (1243, 1243),
        "round_trip_repaired": (1243, 1243),
        "shared_block_answer": (424, 790),
        "stability": (75, 75),
        "stream_fidelity": (18, 18),
        "toolresult_masked": (379, 379),
        "typed": (1359, 1359),
    },
    "max": {
        "answer_optional_only": (720, 1357),
        "answer_real": (637, 637),
        "chain_form": (928, 928),
        "chain_value": (928, 928),
        "consistency": (369, 369),
        "coverage": (11832, 11832),
        "doc_extracted": (325, 325),
        "doc_masked": (100, 100),
        "end_to_end": (7747, 7747),
        "form_hIN": (11162, 11832),
        "form_hOUT": (15741, 15741),
        "leak": (11832, 11832),
        "memory_consistency": (619, 619),
        "multi_all_out": (909, 909),
        "multi_consistency": (1106, 1106),
        "out_absent": (0, 12491),
        "overmask": (1736, 1736),
        "rag_identity_kept": (310, 310),
        "rag_masked": (360, 360),
        "residual": (17477, 17477),
        "retry_form": (126, 126),
        "rewrite_ratio_v5": (0, 1736),
        "round_trip": (6404, 6404),
        "round_trip_repaired": (6404, 6404),
        "shared_block_answer": (2254, 4063),
        "stability": (369, 369),
        "stream_fidelity": (84, 84),
        "toolresult_masked": (1908, 1908),
        "typed": (6938, 6938),
    },
}


def test_the_recorded_numbers_are_still_the_numbers(probe: Probe) -> list[str]:
    """Every line prints on this tier exactly what `RECORDED` says it prints.

    THIS IS THE CHECK THE STALE SENTENCES NEEDED AND DID NOT HAVE. It goes red on
    a recut of the ladder, on a rebuilt corpus and on a changed probe alike — and
    that is the whole intent: each of the three is a reason to re-read what the
    bounds claim, and none of them used to leave a mark.
    """
    row = RECORDED.get(probe.tier)
    if row is None:
        return [f"tier {probe.tier} has no row in RECORDED — measure it and write it down, "
                f"or the acceptance run on it certifies numbers nobody wrote"]
    problems = [f"{name}: RECORDED says {row[name][0]}/{row[name][1]}, the probe prints "
                f"{line.hits}/{line.total} on tier {probe.tier} — re-measure, and re-read "
                f"every bound whose reason rests on the old number"
                for name, line in sorted(probe.perfect.items())
                if name in row and (line.hits, line.total) != row[name]]
    problems += [f"{name}: RECORDED holds a row for a line the probe no longer prints"
                 for name in sorted(row) if name not in probe.perfect]
    problems += [f"{name}: the probe prints a line RECORDED does not hold"
                 for name in sorted(probe.perfect) if name not in row]
    return problems


def test_every_tier_of_the_ladder_is_recorded(probe: Probe) -> list[str]:
    """`RECORDED` holds a row for every tier the ladder names, and for no other.

    A tier added to the ladder and not measured here would be a tier on which
    `--tier` runs the acceptance against nothing; a row for a tier that is gone
    is a number describing a corpus slice that does not exist. Read off the
    LADDER FILE, not off `TIERS`, because the file is what a run reads.
    """
    named = set(perfect.load_ladder(perfect.LADDER_PATH).tiers)
    problems = [f"tier {name} is in the ladder and not in RECORDED"
                for name in sorted(named - set(RECORDED))]
    problems += [f"tier {name} is in RECORDED and not in the ladder"
                 for name in sorted(set(RECORDED) - named)]
    return problems


# --- the bounds a right gateway must clear ------------------------------------------


def test_every_metric_has_a_bound(probe: Probe) -> list[str]:
    """No line goes unchecked, and no bound names a line that is gone.

    A metric added later without a row here is what this catches: v4 shipped
    `FieldSpec.required` read by no scorer and a level with nothing to compare,
    and both were invisible because nobody had to say what a right arm prints.
    """
    problems = [f"{name}: a metric with no bound — say what a right gateway prints on it"
                for name in perfect.SINGLE_ARM_METRICS if name not in BOUNDS]
    problems += [f"{name}: a bound for a line that is not a single-arm metric"
                 for name in BOUNDS if name not in perfect.SINGLE_ARM_METRICS]
    problems += [f"{name}: a bound with no reason" for name, bound in BOUNDS.items()
                 if not bound.why]
    return problems


def test_no_line_is_empty(probe: Probe) -> list[str]:
    """Every line has something to measure on this tier.

    THE v4 DISEASE, GUARDED HERE: a line with an empty denominator prints a
    rate of 0 and certifies nothing, and `all([])` is True — a triple with
    nothing to compare passed all five v4 levels. An empty line on a tier of
    300 cases is a defect wherever it comes from, so it is a failure and never
    a skip. It is also what catches correction 3: numbering the results of one
    turn as one request empties `stability` outright.
    """
    return [f"{name}: 0/0 on tier {probe.tier} — nothing to measure, nothing certified"
            for name, line in probe.perfect.items() if line.total == 0]


def _breaches(lines: dict[str, Line]) -> list[str]:
    """Every bound the run fails, named with its number."""
    out: list[str] = []
    for name, line in sorted(lines.items()):
        bound = BOUNDS.get(name)
        if bound is None or line.total == 0:
            continue
        if bound.floor is not None and line.rate < bound.floor:
            out.append(f"{name}: {line.rate:.4f} ({line.hits}/{line.total}) "
                       f"below its floor {bound.floor:.4f}")
        if bound.ceiling is not None and line.rate > bound.ceiling:
            out.append(f"{name}: {line.rate:.4f} ({line.hits}/{line.total}) "
                       f"above its ceiling {bound.ceiling:.4f}")
    return out


def test_perfect_gateway_clears_every_bound(probe: Probe) -> list[str]:
    """THE CLAIM. A gateway that does what the product promises earns every
    line it is asked for, on the corpus we are about to pay a live run on."""
    return _breaches(probe.perfect)


# --- the three corrections, each taken away --------------------------------------------


@contextlib.contextmanager
def _reverted(name: str, wrong: Callable[..., object]) -> Iterator[None]:
    """Put the WRONG version of one correction back for the length of a block.

    A rule of a simulation cannot be shown load-bearing any other way: there is
    no input that exercises it, only a probe that has it and a probe that does
    not. The attribute is restored in `finally`, so a failing check inside the
    block cannot leave the module broken for the next one.
    """
    right = getattr(perfect, name)
    setattr(perfect, name, wrong)
    try:
        yield
    finally:
        setattr(perfect, name, right)


def test_correction_one_is_load_bearing(probe: Probe) -> list[str]:
    """ONE MINT PER ITEM, WORN IN THE SURFACE'S FORM.

    Reverted, the probe mints twice — once from the surface, once from the
    canonical — and `_keep_tail` puts «пётр» and «петра» in different length
    classes, so the model reads a fake that shares no stem with the fake in the
    argument. Measured on `max`, which is the only tier a recut cannot move:
    `round_trip` 6305/6404, `end_to_end` 7648/7747, `multi_all_out` 810/909,
    `form_hOUT` 15642/15741 — ninety-nine leaves and ninety-nine turns.
    """
    with _reverted("worn_like", lambda fake, real, surface, gender: ""):
        fell = _breaches(measure(probe.cases, perfect.simulate))
    return [] if fell else ["correction 1 (`worn_like`) reverted and every bound still held — "
                            "either the rule is dead or the tier is too small to see it"]


def test_correction_two_is_load_bearing(probe: Probe) -> list[str]:
    """ONE SENTENCE PER FREE LEAF, CARRYING EVERY HOP IT DECLARES.

    Reverted — one value per leaf path, the last hop winning — the other hops
    of a shared free leaf read as values the gateway dropped: `chain_value`
    892/928 on `max`, and that is the round-4 caveat's whole 36-miss story.
    """
    with _reverted("compose_free_leaf", lambda values: (values[-1] if values else "")):
        fell = _breaches(measure(probe.cases, perfect.simulate))
    return [] if fell else ["correction 2 (`compose_free_leaf`) reverted and every bound "
                            "still held — the free-leaf rule no longer decides anything"]


def test_correction_three_is_load_bearing(probe: Probe) -> list[str]:
    """`request_index` COUNTED PER PUSH.

    Reverted — the results of one turn numbered as ONE request, which is what
    keying on the turn amounts to: every one of the 306 items in `stability`'s
    corpus denominator is mentioned by TWO results of the SAME turn (measured),
    so a turn-keyed number is one number. `stability` then prints 0/0, and a
    line that cannot fire certifies nothing — which `test_no_line_is_empty`
    refuses.
    """
    with _reverted("request_of_result", lambda message_count, seq: message_count + 1):
        lines = measure(probe.cases, perfect.simulate)
    fell = _breaches(lines) + [name for name, line in lines.items() if line.total == 0]
    return [] if fell else ["correction 3 (`request_of_result`) reverted and every bound "
                            "still held — `stability` no longer depends on the push count"]


# --- the other half: four wrong gateways --------------------------------------------


def _map_calls(run: ArmRunV5,
               fn: Callable[[dict[str, str], dict[str, str]],
                            tuple[dict[str, str], dict[str, str]]]) -> ArmRunV5:
    calls = []
    for call in run.base.calls:
        written, restored = fn(dict(flatten(call.written)), dict(flatten(call.restored)))
        calls.append(replace(call, written=perfect.unflatten(written),
                             restored=perfect.unflatten(restored)))
    return replace(run, base=replace(run.base, calls=tuple(calls)))


def wrong_passthrough(case: CaseV5) -> ArmRunV5:
    """MASKS NOTHING: the model reads the customer's own values, and the tool
    gets them back because they were never replaced."""
    run = _map_calls(perfect.simulate(case), lambda written, restored: (dict(restored),
                                                                       dict(restored)))
    return replace(run, base=replace(run.base, substitutes={},
                                     masked_spans={key: () for key in run.base.masked_spans}),
                   tool_results=tuple(replace(record, text_masked=record.text_real, pieces=())
                                      for record in run.tool_results),
                   reply_raw=run.base.reply, mentions=())


def wrong_normalised_form(case: CaseV5) -> ArmRunV5:
    """RESTORES THE RIGHT VALUE IN THE WRONG FORM: upper-cased, a canonical of
    the gateway's choosing instead of the form the agent wrote."""
    return _map_calls(perfect.simulate(case),
                      lambda written, restored: (written, {path: value.upper()
                                                           for path, value in restored.items()}))


def wrong_unstable_substitute(case: CaseV5) -> ArmRunV5:
    """LOSES THE SUBSTITUTE ACROSS TURNS: a new fake on every other mention, so
    one person becomes two as far as the model can tell."""
    run = perfect.simulate(case)
    return replace(run, mentions=tuple(
        replace(mention, substitute=mention.substitute + "ский") if index % 2 else mention
        for index, mention in enumerate(run.mentions)))


def wrong_absent_call(case: CaseV5) -> ArmRunV5:
    """NEVER MAKES THE LAST CALL: the arm that does less work, which every
    survival-based line would otherwise reward."""
    run = perfect.simulate(case)
    if not run.base.calls:
        return run
    return replace(run, base=replace(run.base, calls=run.base.calls[:-1]),
                   call_turns=run.call_turns[:-1])


def _leaf_pair_with(fix: Callable[[str, str], str]) -> Callable[..., tuple[str, str]]:
    """`perfect._leaf_pair` with `fix` laid over what the gateway RESTORED.

    The seam is `_leaf_pair` and not the flat leaf map `_map_calls` reaches,
    because both mutants below are about ONE type — a name's case, a phone's
    notation — and `_leaf_pair` is the last place that still knows which item a
    leaf holds. A mutant guessing the type from the string would inflect a
    street that happens to parse as a surname, and stop being the defect it
    names.
    """
    right = perfect._leaf_pair

    def leaf(item: PiiItem, substitute: perfect.Substitute, tool: str,
             path: str) -> tuple[str, str]:
        written, restored = right(item, substitute, tool, path)
        return written, fix(item.type, restored)

    return leaf


def _dative(pii_type: str, text: str) -> str:
    """A NAME in the dative, word by word, capitalisation kept — so the ONLY
    feature that can move is `gram_case`. Lower-casing it instead would be
    caught by `case_class`, and the check would prove nothing about the case."""
    if pii_type != "NAME":
        return text
    out: list[str] = []
    for token in perfect._WORD.findall(text):
        lexeme = perfect._lexeme_parse(token) if token.isalpha() else None
        worn = None if lexeme is None else lexeme.inflect({"datv"})
        out.append(token if worn is None else perfect._worn_case(worn.word, token))
    return "".join(out)


def wrong_case_form(case: CaseV5) -> ArmRunV5:
    """RESTORES THE RIGHT NAME IN A CASE OF ITS OWN CHOOSING: the agent wrote
    «Иванов» and the tool receives «Иванову».

    `docs/known-issues.md` Б24 from the side this corpus can show. The defect
    there is «the nominative for the tool», and the nominative is what the
    corpus's own tool leaves already carry — a gateway whose canonical IS the
    nominative would be right about them by accident, and a mutant that is
    accidentally right proves nothing. So this one answers the dative: not the
    case the agent wrote, whichever case that was.

    ONE FEATURE CATCHES IT, `NAME.gram_case`, and that feature had no voice
    until the substitute became a word (`perfect` §1bis).
    `test_readable_fakes_are_load_bearing` takes the pool away and shows this
    gateway walking past `form_hOUT` untouched.
    """
    with _reverted("_leaf_pair", _leaf_pair_with(_dative)):
        return perfect.simulate(case)


def _canonical_phone(pii_type: str, text: str) -> str:
    """A PHONE in ONE notation of the gateway's own: «+7» and ten digits."""
    digits = "".join(char for char in text if char.isdigit())
    return "+7" + digits[-10:] if pii_type == "PHONE" and digits else text


def wrong_normalised_number(case: CaseV5) -> ArmRunV5:
    """RETURNS THE RIGHT NUMBER IN THE WRONG NOTATION: the agent wrote the ten
    bare digits the leaf asks for and the gateway answers «+7…», its canonical.

    THE FIFTH CLASS, AND THE ONE THE PRODUCT IS ACTUALLY MEASURED AGAINST.
    `pseudex/vault.py` canonicalises on the way back — «detokenization returns
    the CANONICAL form» — so a phone restored into a leaf the agent wrote bare
    comes back with a country code the agent did not write. Four wrong gateways
    stood here and none of them was this one.

    It is also the cleanest statement of what `form_hOUT` exists for: the value
    is right to the last digit, and only the notation was decided by the wrong
    party. `test_number_mutant_moves_only_form_lines` holds it to exactly that.
    """
    with _reverted("_leaf_pair", _leaf_pair_with(_canonical_phone)):
        return perfect.simulate(case)


# Each wrong gateway names the ONE line that must catch it — the line whose
# words are its defect. Others move too, and that is fine; what a test cannot
# accept is «something somewhere changed».
WRONG_GATEWAYS: tuple[tuple[str, Callable[[CaseV5], ArmRunV5], str], ...] = (
    ("passthrough (masks nothing)", wrong_passthrough, "leak"),
    ("normalises the agent's form", wrong_normalised_form, "form_hOUT"),
    ("loses the substitute across turns", wrong_unstable_substitute, "stability"),
    ("never makes the last call", wrong_absent_call, "out_absent"),
    ("answers a case of its own", wrong_case_form, "form_hOUT"),
    ("returns the number in its own notation", wrong_normalised_number, "form_hOUT"),
)


def test_wrong_gateways_are_caught(probe: Probe) -> list[str]:
    """THE HALF THAT MAKES THE OTHER HALF MEAN ANYTHING."""
    problems: list[str] = []
    for label, gateway, named in WRONG_GATEWAYS:
        lines = measure(probe.cases, gateway)
        if lines == probe.perfect:
            problems.append(f"{label}: changed nothing at all — a mutant with no bite "
                            f"proves nothing about the line it is aimed at")
            continue
        breaches = _breaches(lines)
        empty = [name for name, line in lines.items() if line.total == 0]
        if not breaches and not empty:
            problems.append(f"{label}: every bound still held — a wrong gateway earns the "
                            f"same report as a right one")
            continue
        if not any(one.startswith(f"{named}:") for one in breaches) and named not in empty:
            problems.append(f"{label}: caught, but not by `{named}`, which is the line that "
                            f"names its defect; caught by {breaches or empty}")
    return problems


# The lines whose hit condition READS a `FormVerdict`. Every other line asks
# about the VALUE, and a gateway that returns the right number in the wrong
# notation must leave all of them exactly where it found them.
FORM_READING_LINES: frozenset[str] = frozenset({
    "form_hIN", "form_hOUT", "chain_form", "retry_form", "multi_all_out"})


def test_readable_fakes_are_load_bearing(probe: Probe) -> list[str]:
    """THE POOL IS WHAT GIVES `NAME.gram_case` A VOICE.

    Reverted — `pool_pick` refuses every word, so every name is minted by
    letter substitution as it was before `perfect` §1bis — pymorphy3 knows none
    of the substitutes, `form._word_readings` refuses a prediction made from an
    ending, and `name_gram_case_same` abstains on the REFERENCE side of every
    name hop. `wrong_case_form` then answers a case nobody wrote and
    `form_hOUT` does not move: measured on the corpus, 6 200 of 6 200 NAME
    substitutes silent against 93 of 6 200 real values.

    The value lines still catch it, and that is not the point: the defect is a
    FORM, `gram_case` is the feature whose words describe it, and a line that
    cannot see the defect it names is the v4 disease this whole file exists to
    keep out.
    """
    with _reverted("pool_pick", lambda word, gender, role, taken: ("", "")):
        blind = measure(probe.cases, wrong_case_form)
    caught = [one for one in _breaches(blind) if one.startswith("form_hOUT:")]
    return [f"with the pool reverted `form_hOUT` still caught the case mutant ({caught}) — "
            f"either the letter-mangled fakes were already readable, or the mutant moves "
            f"some other feature and proves nothing about `gram_case`"] if caught else []


def test_number_mutant_moves_only_form_lines(probe: Probe) -> list[str]:
    """A NOTATION IS NOT A VALUE, and the line that says so must be alone.

    `wrong_normalised_number` returns the customer's phone to the last digit
    and writes it in the gateway's own notation. Every value line must print
    what a right gateway prints; only the lines that read a form verdict may
    move. Without this, «caught by form_hOUT» would be satisfied by a mutant
    that quietly corrupted the number as well, and the row would stop being
    evidence about the form.
    """
    lines = measure(probe.cases, wrong_normalised_number)
    moved = [name for name, line in lines.items() if line != probe.perfect[name]]
    problems = [f"{name}: {probe.perfect[name].hits}/{probe.perfect[name].total} -> "
                f"{lines[name].hits}/{lines[name].total} under a gateway that changed a "
                f"notation and no value — this line does not read a form verdict"
                for name in moved if name not in FORM_READING_LINES]
    if not any(name in FORM_READING_LINES for name in moved):
        problems.append("the notation mutant moved no form line at all — it is not a mutant")
    return problems


def _corpus_reading(cases: Sequence[CaseV5]) -> tuple[frozenset[str], str]:
    """(every NAME stem needle the corpus carries, every value of it in one
    folded blob). The blob is joined on a newline so a match can never straddle
    two values."""
    stems: set[str] = set()
    values: set[str] = set()
    for case in cases:
        for item in case.base.pii:
            for surface in {item.value, item.canonical, *item.parts.values()}:
                values.add(fold(surface))
                if item.type != "NAME":
                    continue
                stems |= {needle.text for needle in value_needles("NAME", surface)
                          if needle.kind == "stem"}
    return frozenset(stems), "\n".join(sorted(values))


def _pool_problems(entries: Sequence[str], stems: frozenset[str], blob: str) -> list[str]:
    """Every way one entry is unfit to be minted from — the three rules written
    out in `perfect` §1bis plus the one they all rest on, that pymorphy3 knows
    the word and can inflect it."""
    problems: list[str] = []
    for entry in entries:
        lexeme = perfect._lexeme_parse(entry)
        worn = [] if lexeme is None else [lexeme.inflect({case}) for case in _GRAM_CASES]
        forms = {entry} | {one.word for one in worn if one is not None}
        if lexeme is None or any(one is None for one in worn):
            problems.append(f"{entry}: unknown — pymorphy3 holds no name parse it can "
                            f"inflect into all six cases")
        if len(entry) < 5:
            problems.append(f"{entry}: short — under five letters the four-letter stem "
                            f"needle is the ending, and the ending moves")
        moved = sorted({perfect._stem(one) for one in forms})
        if len(moved) > 1:
            problems.append(f"{entry}: stem-moves — {moved}")
        clash = sorted({stem for stem in stems
                        for mine in [perfect._stem(entry)]
                        if stem.startswith(mine) or mine.startswith(stem)})
        if clash:
            problems.append(f"{entry}: corpus-stem — shares a needle with {clash}")
        inside = sorted({one for one in forms if fold(one) in blob})
        if inside:
            problems.append(f"{entry}: inside-corpus — {inside} stands inside a corpus value")
    return problems


# Five entries, one broken rule each, and the check must name all five. A
# checker that cannot fail is the thing this file exists to refuse, and a pool
# check is the easiest one to write so that it never does.
_UNFIT_POOL: tuple[str, ...] = ("зоя", "павел", "тарас", "панов", "укщыхьв")
_GRAM_CASES: tuple[str, ...] = ("nomn", "gent", "datv", "accs", "ablt", "loct")
_UNFIT_LABELS: tuple[str, ...] = ("short", "stem-moves", "corpus-stem", "inside-corpus",
                                  "unknown")


def test_pool_is_fit_to_mint_from(probe: Probe) -> list[str]:
    """EVERY POOL ENTRY OBEYS THE THREE RULES, ENTRY BY ENTRY.

    The bounds above already go red when an entry is unfit — a shared stem
    prints as `coverage 0.9975` — and that is a number, not an instruction.
    This names the word and the rule, which is what a reader needs when a
    rebuilt corpus brings in a name the pool has held for months.

    The second half poisons the pool with one entry per rule and demands a
    complaint for each: «Зоя» too short, «Павел» whose vowel is fleeting,
    «Тарас» sharing the needle of «Тарасова», «Панов» sitting inside
    «стеПАНОВич», and a string no dictionary holds.
    """
    stems, blob = _corpus_reading(probe.cases)
    entries = sorted({one for pool in perfect._POOL.values() for one in pool})
    problems = _pool_problems(entries, stems, blob)
    caught = _pool_problems(_UNFIT_POOL, stems, blob)
    problems += [f"the pool check missed `{label}` on its own unfit pool — it cannot fail"
                 for label in _UNFIT_LABELS
                 if not any(f": {label}" in one for one in caught)]
    return problems


def test_no_engine_imported(probe: Probe) -> list[str]:
    """The probe is records and arithmetic. An engine import here would mean the
    acceptance numbers depend on the thing being accepted."""
    bad = [name for name in sys.modules
           if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tier", default=ACCEPTANCE_TIER, choices=TIERS,
                        help="the corpus slice every check runs on; `max` is the whole "
                             "corpus, which is where every published number comes from")
    args = parser.parse_args(argv)
    probe = build_probe(args.tier)
    checks: tuple[tuple[str, Callable[[Probe], list[str]]], ...] = (
        ("no_engine_imported", test_no_engine_imported),
        ("every_metric_has_a_bound", test_every_metric_has_a_bound),
        ("every_tier_of_the_ladder_is_recorded", test_every_tier_of_the_ladder_is_recorded),
        ("the_recorded_numbers_are_still_the_numbers",
         test_the_recorded_numbers_are_still_the_numbers),
        ("no_line_is_empty", test_no_line_is_empty),
        ("perfect_gateway_clears_every_bound", test_perfect_gateway_clears_every_bound),
        ("correction_one_is_load_bearing", test_correction_one_is_load_bearing),
        ("correction_two_is_load_bearing", test_correction_two_is_load_bearing),
        ("correction_three_is_load_bearing", test_correction_three_is_load_bearing),
        ("pool_is_fit_to_mint_from", test_pool_is_fit_to_mint_from),
        ("readable_fakes_are_load_bearing", test_readable_fakes_are_load_bearing),
        ("number_mutant_moves_only_form_lines", test_number_mutant_moves_only_form_lines),
        ("wrong_gateways_are_caught", test_wrong_gateways_are_caught),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check(probe)
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    bounded = sum(1 for bound in BOUNDS.values() if bound.floor is not None or bound.ceiling)
    print(f"perfect: PASS ({len(probe.cases)} cases of tier {probe.tier}, "
          f"{bounded} bounded lines, {len(WRONG_GATEWAYS)} wrong gateways caught)"
          if not failures else f"perfect: FAIL on tier {probe.tier}\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
