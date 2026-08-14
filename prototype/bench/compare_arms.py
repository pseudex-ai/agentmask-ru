"""Paired-run comparison: what did putting Veilgate in the path actually cost?

The headline number is `task sensitivity` — the name the literature already uses
(Tau-Eval, EMNLP 2025): Δ = accuracy_control − accuracy_masked. A single scalar
hides everything interesting, so this also splits the per-entry outcome into four
buckets, because they mean different things:

  both pass      — masking was transparent
  DAMAGED        — control passed, masked failed. THE metric that matters.
  recovered      — masked passed, control failed. Not a win; it is noise, and its
                   size is the floor under which a DAMAGED count means nothing.
  both fail      — the model was not capable of the task either way; carries no
                   signal about masking at all

`recovered` is why a bare Δ is untrustworthy at small n: if 2 tasks flip each way,
Δ is 0 while 4 tasks actually changed behaviour. Report both.

Error types come from BFCL's own checker, so a DAMAGED entry says WHICH way it
broke — state mismatch vs a call that errored vs force-termination.

usage: python3 compare_arms.py <score_dir> <control_model> <masked_model> [category]
"""

import json
import sys
from pathlib import Path


def _load(score_dir: Path, model: str, category: str) -> tuple[dict[str, object], dict[str, str]]:
    """Return (summary, {failed_id: error_type}). BFCL writes a summary object on
    line 1 and one object per FAILING entry after it — so a passing entry is
    simply absent, and the pass set is derived by subtraction."""
    path = score_dir / model / "multi_turn" / f"BFCL_v4_{category}_score.json"
    if not path.exists():
        raise FileNotFoundError(f"no score file for {model}: {path}")
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    summary = lines[0]
    failures = {
        entry["id"]: entry.get("error", {}).get("error_type", "unknown")
        for entry in lines[1:] if "id" in entry
    }
    return summary, failures


def _mcnemar_verdict(damaged: int, recovered: int) -> str:
    """Is the delta real, or is it the run-to-run wobble of a stochastic model?

    Reporting Δ alone is misleading here: the arms disagree in BOTH directions,
    so a small net difference can sit on top of a large amount of flipping. Only
    the DISCORDANT pairs carry information — the tasks both arms passed or both
    failed say nothing about masking — which is exactly McNemar's test.

    Exact binomial rather than the chi-square approximation, because the counts
    are small enough for the approximation to misbehave, and this number is meant
    to be quotable to a customer."""
    discordant = damaged + recovered
    if discordant == 0:
        return "No entry changed outcome — masking was fully transparent."
    # P(|k - n/2| >= |damaged - n/2|) under a fair coin, two-sided.
    from math import comb

    extreme = abs(damaged - discordant / 2)
    tail = sum(
        comb(discordant, k)
        for k in range(discordant + 1)
        if abs(k - discordant / 2) >= extreme
    )
    p_value = tail / 2 ** discordant
    verdict = (
        "NOT significant — indistinguishable from the model's own run-to-run variance"
        if p_value > 0.05 else
        "SIGNIFICANT — masking really did change outcomes"
    )
    return (f"McNemar exact test on the {discordant} discordant pairs "
            f"({damaged} damaged vs {recovered} recovered): p = {p_value:.3f}\n"
            f"  -> {verdict}")


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    score_dir = Path(sys.argv[1])
    control_model, masked_model = sys.argv[2], sys.argv[3]
    category = sys.argv[4] if len(sys.argv) > 4 else "multi_turn_base"

    control_summary, control_failed = _load(score_dir, control_model, category)
    masked_summary, masked_failed = _load(score_dir, masked_model, category)

    total = control_summary["total_count"]
    if masked_summary["total_count"] != total:
        raise ValueError(
            f"arms cover different entry counts ({total} vs "
            f"{masked_summary['total_count']}) — they are not paired"
        )

    ids = sorted(set(control_failed) | set(masked_failed))
    damaged = [i for i in ids if i not in control_failed and i in masked_failed]
    recovered = [i for i in ids if i in control_failed and i not in masked_failed]
    both_fail = [i for i in ids if i in control_failed and i in masked_failed]

    control_accuracy = control_summary["accuracy"]
    masked_accuracy = masked_summary["accuracy"]

    print(f"category      : {category}   n={total}")
    print(f"control       : {control_accuracy:.1%}  ({control_summary['correct_count']}/{total})")
    print(f"masked        : {masked_accuracy:.1%}  ({masked_summary['correct_count']}/{total})")
    print(f"task sensitivity Δ = {control_accuracy - masked_accuracy:+.1%}"
          "   (positive = masking cost us)")
    print()
    print(f"both pass     : {total - len(ids)}")
    print(f"DAMAGED       : {len(damaged)}   {damaged}")
    print(f"recovered     : {len(recovered)}   {recovered}   <- noise floor")
    print(f"both fail     : {len(both_fail)}   (model-limited, no signal)")

    if damaged:
        print("\nhow the damaged entries broke (BFCL checker error types):")
        for entry_id in damaged:
            print(f"  {entry_id:<28}{masked_failed[entry_id]}")

    print(f"\n{_mcnemar_verdict(len(damaged), len(recovered))}")


if __name__ == "__main__":
    main()
