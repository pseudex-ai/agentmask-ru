"""Statistics for a paired, clustered, repeated three-arm design.

WHAT THE NUMBERS MEAN AND WHY THEY ARE COMPUTED THIS WAY:

  * agreement per case is a pass^k-style count (τ-bench's estimator,
    C(c,k)/C(n,k)), because a case that agrees on some repeats and not on
    others is a fragile case, not half a case;
  * the effect is a PAIRED difference — agreement(I,C) minus agreement(C,C′)
    on the same case — because paired differences are «a "free" reduction in
    estimator variance» (Miller 2024) and because the model's own noise is
    the thing being subtracted;
  * the interval is a CLUSTER bootstrap over distinct PII values (Field &
    Welsh 2007): one shared phone in three cases is one draw, not three;
  * McNemar's exact test runs on the discordant pairs and is LABELLED as
    ignoring clusters — the bootstrap interval is the one to quote;
  * ICC and the design effect (Kish: 1 + (m̄−1)·ICC) are printed so the next
    run's n and K are chosen from a measurement, not from an assumed 0.2;
  * the Clopper–Pearson floor is printed beside every zero: 0 divergences on
    400 pairs certifies ≥ 99.25%, never 100%.

`clopper_pearson` is lifted verbatim from `bench/voice/score.py`. No
`pseudex` import; no dependency on the corpus.
"""
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import comb, exp, lgamma, log, log1p


@dataclass(frozen=True)
class CaseEffect:
    case_id: str
    cluster: str
    ic: int      # repeats where I agreed with C
    cc: int      # repeats where C′ agreed with C
    n: int       # complete triples


@dataclass(frozen=True)
class Interval:
    point: float
    low: float
    high: float
    method: str
    n: int


def pass_k(agree: int, n: int, k: int) -> float:
    """C(agree, k) / C(n, k): the chance k i.i.d. repeats all agree."""
    if n < k or k <= 0:
        return 0.0
    return comb(agree, k) / comb(n, k)


def effect(cases: Sequence[CaseEffect]) -> float:
    """Mean over cases of (ic/n − cc/n)."""
    if not cases:
        return 0.0
    return sum((one.ic - one.cc) / one.n for one in cases if one.n) / len(cases)


def agreement(cases: Sequence[CaseEffect], side: str) -> float:
    if not cases:
        return 0.0
    return sum((one.ic if side == "ic" else one.cc) / one.n for one in cases if one.n) / len(cases)


def cluster_bootstrap(cases: Sequence[CaseEffect], reps: int = 4000, seed: int = 0,
                      alpha: float = 0.05) -> Interval:
    """Percentile CI of the effect, resampling CLUSTERS with replacement."""
    if not cases:
        return Interval(0.0, 0.0, 0.0, "cluster-bootstrap", 0)
    by_cluster: dict[str, list[CaseEffect]] = {}
    for one in cases:
        by_cluster.setdefault(one.cluster, []).append(one)
    clusters = list(by_cluster.values())
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(reps):
        sample: list[CaseEffect] = []
        for _ in range(len(clusters)):
            sample.extend(rng.choice(clusters))
        draws.append(effect(sample))
    draws.sort()
    low = draws[int(alpha / 2 * reps)]
    high = draws[min(reps - 1, int((1 - alpha / 2) * reps))]
    return Interval(effect(cases), low, high, "cluster-bootstrap", len(cases))


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact binomial on discordant pairs. Ignores clusters."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def icc_binary(groups: Mapping[str, Sequence[int]]) -> float:
    """One-way ANOVA ICC(1) on 0/1 outcomes. Groups of size 1 add nothing."""
    sizes = [len(values) for values in groups.values() if values]
    if not sizes or sum(sizes) <= len(sizes):
        return 0.0
    total = sum(sizes)
    grand = sum(sum(values) for values in groups.values()) / total
    between = sum(len(values) * (sum(values) / len(values) - grand) ** 2
                  for values in groups.values() if values)
    within = sum((value - sum(values) / len(values)) ** 2
                 for values in groups.values() for value in values)
    k = len(sizes)
    if k <= 1 or total - k == 0:
        return 0.0
    ms_between = between / (k - 1)
    ms_within = within / (total - k)
    n0 = (total - sum(size * size for size in sizes) / total) / (k - 1)
    if n0 <= 0 or ms_between + (n0 - 1) * ms_within == 0:
        return 0.0
    return max(0.0, (ms_between - ms_within) / (ms_between + (n0 - 1) * ms_within))


def design_effect(mean_cluster_size: float, icc: float) -> float:
    return 1.0 + (mean_cluster_size - 1.0) * icc


def effective_n(n: int, deff: float) -> float:
    return n / deff if deff > 0 else float(n)


def clopper_pearson(hits: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact binomial interval, bisection on the CDF, in logs (no overflow)."""
    if total == 0:
        return 0.0, 1.0

    def _pmf_log(p: float, i: int) -> float:
        return (lgamma(total + 1) - lgamma(i + 1) - lgamma(total - i + 1)
                + i * log(p) + (total - i) * log1p(-p))

    def ge(p: float, k: int) -> float:
        return sum(exp(_pmf_log(p, i)) for i in range(k, total + 1))

    def le(p: float, k: int) -> float:
        return sum(exp(_pmf_log(p, i)) for i in range(0, k + 1))

    low = 0.0
    if hits:
        a, b = 0.0, 1.0
        for _ in range(80):
            mid = (a + b) / 2
            a, b = (mid, b) if ge(mid, hits) < alpha / 2 else (a, mid)
        low = (a + b) / 2
    high = 1.0
    if hits < total:
        a, b = 0.0, 1.0
        for _ in range(80):
            mid = (a + b) / 2
            a, b = (a, mid) if le(mid, hits) < alpha / 2 else (mid, b)
        high = (a + b) / 2
    return low, high


def zero_failure_floor(n: int, alpha: float = 0.05) -> float:
    """0 failures on n pairs certifies an agreement rate of at least this
    (one-sided): alpha^(1/n). 400 clean pairs certify 99.25%, never 100%."""
    return alpha ** (1.0 / n) if n > 0 else 0.0


def n_for_halfwidth(rate: float, halfwidth: float, deff: float = 1.0) -> int:
    """Wald n for ±halfwidth at 95%, inflated by the design effect."""
    if halfwidth <= 0:
        return 0
    base = 1.96 ** 2 * rate * (1 - rate) / halfwidth ** 2
    return int(base * deff + 0.999)


def main() -> int:
    failures = 0
    if abs(mcnemar_exact(3, 10) - 0.0923) > 0.001:
        failures += 1
        print(f"FAIL mcnemar {mcnemar_exact(3, 10)}")
    low, high = clopper_pearson(0, 400)
    if abs(high - 0.00918) > 0.0002 or low != 0.0:     # two-sided 95%
        failures += 1
        print(f"FAIL clopper {low} {high}")
    if abs(zero_failure_floor(400) - 0.99254) > 0.0002:  # one-sided 95%
        failures += 1
        print(f"FAIL floor {zero_failure_floor(400)}")
    if icc_binary({"a": [1, 1, 1], "b": [0, 0, 0]}) < 0.99:
        failures += 1
        print(f"FAIL icc identical groups {icc_binary({'a': [1, 1, 1], 'b': [0, 0, 0]})}")
    if icc_binary({"a": [1, 0], "b": [0, 1], "c": [1, 0]}) > 0.05:
        failures += 1
        print("FAIL icc independent groups")
    singles = [CaseEffect(f"c{i}", f"k{i}", 2 if i % 3 else 3, 3, 3) for i in range(60)]
    interval = cluster_bootstrap(singles, reps=500)
    if not (interval.low <= interval.point <= interval.high) or interval.point > 0:
        failures += 1
        print(f"FAIL bootstrap {interval}")
    if pass_k(2, 3, 3) != 0.0 or pass_k(3, 3, 3) != 1.0 or abs(pass_k(2, 3, 1) - 2 / 3) > 1e-9:
        failures += 1
        print("FAIL pass_k")
    if not 440 <= n_for_halfwidth(0.95, 0.02) <= 460:
        failures += 1
        print(f"FAIL n_for_halfwidth {n_for_halfwidth(0.95, 0.02)}")
    print("stats: PASS" if not failures else f"stats: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
