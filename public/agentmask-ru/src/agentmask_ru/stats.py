"""The three statistics this benchmark is allowed to print. Standard library
only, so a reader can check them without installing anything.

A RATE WITHOUT AN INTERVAL IS A RUMOUR. Of 445 benchmarks surveyed at
NeurIPS 2025, 16% used any statistical test; this one prints an exact
Clopper–Pearson interval beside every rate, and when a system makes zero
mistakes it prints what that actually certifies — 0 errors on 100 items
certify 97.0%, not 100%.

Comparisons between two systems are PAIRED: both ran the same cases, so the
question is about the cases where they disagree, and McNemar's exact test is
the one that asks it.
"""

from math import comb, exp, lgamma, log, log1p


def clopper_pearson(hits: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact binomial interval by bisection on the CDF, computed in logs so
    a thousand items do not overflow."""
    if total == 0:
        return 0.0, 1.0

    def log_pmf(p: float, i: int) -> float:
        return (lgamma(total + 1) - lgamma(i + 1) - lgamma(total - i + 1)
                + i * log(p) + (total - i) * log1p(-p))

    def at_least(p: float, k: int) -> float:
        return sum(exp(log_pmf(p, i)) for i in range(k, total + 1))

    def at_most(p: float, k: int) -> float:
        return sum(exp(log_pmf(p, i)) for i in range(0, k + 1))

    low = 0.0
    if hits:
        a, b = 0.0, 1.0
        for _ in range(80):
            mid = (a + b) / 2
            a, b = (mid, b) if at_least(mid, hits) < alpha / 2 else (a, mid)
        low = (a + b) / 2
    high = 1.0
    if hits < total:
        a, b = 0.0, 1.0
        for _ in range(80):
            mid = (a + b) / 2
            a, b = (a, mid) if at_most(mid, hits) < alpha / 2 else (mid, b)
        high = (a + b) / 2
    return low, high


def zero_failure_floor(total: int, alpha: float = 0.05) -> float:
    """What «no mistakes on n items» certifies, one-sided: alpha ** (1/n).
    272 flawless cases certify 98.9%; 99.4% would need 498."""
    return alpha ** (1.0 / total) if total > 0 else 0.0


def items_for(target: float, alpha: float = 0.05) -> int:
    """How many flawless items are needed to certify `target`."""
    if not 0.0 < target < 1.0:
        raise ValueError("target must be a probability")
    from math import ceil
    return ceil(log(alpha) / log(target))


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact binomial on the discordant pairs of a paired
    comparison: `b` cases where A passed and B failed, `c` the reverse."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)
