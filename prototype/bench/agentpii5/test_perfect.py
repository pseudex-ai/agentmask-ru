"""THE ACCEPTANCE TEST OF THE INSTRUMENT ITSELF.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_perfect              # tier medium, ~30 s
    python3 -m bench.agentpii5.test_perfect --tier max   # the WHOLE corpus, ~2 min 15 s

Two halves, and neither is worth anything alone:

  * a RIGHT gateway (`perfect.simulate`) must clear a declared bound on EVERY
    line — the claim «these numbers are earnable» made checkable;
  * four WRONG gateways must FAIL the same bounds — because an acceptance test
    a wrong gateway can also pass is not an acceptance test, it is a printout.

And a third thing the round-4 proof taught: the three corrections that made the
probe honest are themselves rules, so each is REVERTED here and the run must go
red. A correction nobody can knock down is a correction nobody can trust.

WHY `medium` (300 cases) IS THE DEFAULT AND NOT `small`. Runtime is not the
constraint — one pass over the tier is under two seconds — the corrections are:
reverting correction 1 moves NOTHING on `nano` or on `small` (measured), so a
test on those tiers would certify a rule it cannot see. `medium` is the
smallest tier on which all three corrections bite; the whole file is eight
passes, ~30 s.

AND WHY THE DEFAULT IS NOT THE WHOLE STORY. Every number this benchmark
publishes comes from `max` — all 1736 cases — and for five rounds nothing in
the repository checked the floors there: `answer_real` was 101/101 on `medium`
and 636/637 on `max`, and only a scratch script ever saw the second number. A
bound that is only ever tested on a slice of the corpus it is a claim about is
a bound with a blind spot, so `--tier max` runs the SAME eight checks over the
whole corpus: all eight, not a weakened subset — the three corrections and the
four wrong gateways were measured to bite there too. It is slow (~2 min 15 s,
eight passes of ~13 s plus the corpus load) and it is the run to make before
any number is quoted; `medium` stays the default so the file remains cheap
enough for every change.

OFFLINE BY CONSTRUCTION: no model, no network, no keys, no engine — the corpus,
the tool registry and arithmetic.
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, replace

from bench.agentpii4.tools import flatten
from bench.agentpii5 import contracts, metrics, observe, perfect
from bench.agentpii5.contracts import ArmRunV5, CaseV5, Line

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
    "overmask": Bound(1.0, None, "a right gateway touches no negative: medium 1.0000"),
    "consistency": Bound(1.0, None, _EARNED),
    "stability": Bound(1.0, None, _EARNED),
    "toolresult_masked": Bound(1.0, None, _EARNED),
    "answer_real": Bound(1.0, None, "medium 1.0000, corpus 1.0000 (637/637) — NO residue. "
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
                       "medium 0.9986 (2807/2811), corpus 0.9988 (15734/15753). ALL 19 corpus "
                       "misses are ANSWER hops on a region the agent wrote as ONE phrase for "
                       "2–10 data, which `answer_pair` then narrows per item (C-200): the raw "
                       "side by the substitute's needles, the restored side by the real "
                       "value's, and on a multi-part address or name the two needle sets do "
                       "not land on the same parts — «Ауков, ул Фоеочая» against «Псковская "
                       "область, г Псков, ул Рабочая». Measured: the UN-narrowed window "
                       "compares `same` on all 19, so this is the narrowing's own cost and "
                       "not a gateway defect. The floor sits below every tier (small 0.9974 "
                       "is the weakest) so a real regression still shows — a gateway that "
                       "normalises the form prints 0.72 here"),
    "form_hIN": Bound(0.80, None,
                      "medium 0.8121, small 0.8141, corpus 0.9431 — and the whole residue is "
                      "DICTATED values against WRITTEN substitutes (docs/known-issues.md Б27, "
                      "an ENGINE finding, not an instrument one: written items 10812/10812). "
                      "The share of dictated hops differs by tier, which is why the floor sits "
                      "under the weakest tier and why the line that catches a masking failure "
                      "is `leak`, never this one"),

    # --- the lines that make no claim about the gateway
    "out_absent": Bound(None, 0.0,
                        "a CEILING, not a floor: it counts declared OUT hops the agent never "
                        "wrote. A right agent writes them all — medium 0/2174 — and an agent "
                        "that drops its last call prints 0.24 (`wrong_absent_call`)"),
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
    argument. Measured on this tier: `round_trip` 1132/1135, `end_to_end`
    1359/1362, `multi_all_out` 154/157; over the whole corpus, twelve leaves
    and twelve turns.
    """
    with _reverted("worn_like", lambda fake, real, surface: ""):
        fell = _breaches(measure(probe.cases, perfect.simulate))
    return [] if fell else ["correction 1 (`worn_like`) reverted and every bound still held — "
                            "either the rule is dead or the tier is too small to see it"]


def test_correction_two_is_load_bearing(probe: Probe) -> list[str]:
    """ONE SENTENCE PER FREE LEAF, CARRYING EVERY HOP IT DECLARES.

    Reverted — one value per leaf path, the last hop winning — the other hops
    of a shared free leaf read as values the gateway dropped: `chain_value`
    160/166 here, 892/928 over the corpus, and that is the round-4 caveat's
    whole 36-miss story.
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


# Each wrong gateway names the ONE line that must catch it — the line whose
# words are its defect. Others move too, and that is fine; what a test cannot
# accept is «something somewhere changed».
WRONG_GATEWAYS: tuple[tuple[str, Callable[[CaseV5], ArmRunV5], str], ...] = (
    ("passthrough (masks nothing)", wrong_passthrough, "leak"),
    ("normalises the agent's form", wrong_normalised_form, "form_hOUT"),
    ("loses the substitute across turns", wrong_unstable_substitute, "stability"),
    ("never makes the last call", wrong_absent_call, "out_absent"),
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
        ("no_line_is_empty", test_no_line_is_empty),
        ("perfect_gateway_clears_every_bound", test_perfect_gateway_clears_every_bound),
        ("correction_one_is_load_bearing", test_correction_one_is_load_bearing),
        ("correction_two_is_load_bearing", test_correction_two_is_load_bearing),
        ("correction_three_is_load_bearing", test_correction_three_is_load_bearing),
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
