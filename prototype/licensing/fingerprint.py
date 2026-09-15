"""Collusion-resistant fingerprint (Tardos) woven into the leased gazetteers.

The single-leaker canary (`licensing/canary.py`) gives each org UNIQUE marks, which
TWO colluding orgs strip by intersecting their bundles — the intersection keeps only
entries common to both, and per-org-unique canaries are common to none. This closes
that gap: all orgs draw from ONE shared universe of novel fake entries, and each org
receives the SUBSET selected by its Tardos codeword. A pirate bundle fused from
several orgs — by union OR intersection — still scores its true contributors above
any innocent, by the Tardos tracing bound (Tardos, STOC 2003; symmetric score
Škorić et al., Designs Codes Crypt. 2008). The solo leaker is the trivial case (its
bundle IS its codeword) and is always traced.

MARKING ASSUMPTION holds because the marks are novel fakes indistinguishable from
real gazetteer entries without the secret: a coalition cannot tell which entries are
fingerprint positions, so it can only take whole-bundle set operations, and a
position where all colluders agree is preserved (they dare not drop random entries —
that degrades their own detector and still cannot target the marks).

HONEST TRADE, stated because it is load-bearing: coalition strength scales with the
number of marks M (Tardos needs ~t² positions for coalition size t), and every mark
is one more novel word the detector will mask — so M trades coalition-resistance
against over-masking. The marks are gibberish-shaped nonwords filtered novel against
the real dictionary, so real traffic almost never contains one; still, the default M
is conservative and `PSEUDEX_FINGERPRINT_BITS` raises it for higher-assurance
deployments (measure `test_overmasking` when raising it).

Secret: PSEUDEX_CANARY_SECRET (one attribution secret, shared with the canary). Empty
-> off, never a crash. Server-side only, never in the customer's image.
"""
import hashlib
import hmac
import math
import os
from functools import lru_cache
from typing import Iterable, Optional

from licensing import canary

# Per-kind universe size. Tardos needs ~t^2 marks for coalitions of size t; 512 traces
# coalitions of up to three orgs with a wide margin under the conservative 4*sqrt(M)
# threshold (measured: t=3 union scores 74-128 vs innocent <=11), while the marks stay
# gibberish-rare in real traffic. Tunable up for larger coalitions (over-masking cost).
_BITS = max(16, int(os.environ.get("PSEUDEX_FINGERPRINT_BITS", "512")))
# Tardos cut-off: p_j in [sin^2(THETA0), cos^2(THETA0)]. Bounds the score magnitude so
# one position cannot dominate; 1/300 is Tardos's own regime for realistic n.
_THETA0 = math.asin(math.sqrt(1.0 / 300.0))
_ENDS = {"surname": canary._SURN_END, "street": canary._STREET_END}


@lru_cache(maxsize=1)
def _secret() -> bytes:
    return os.environ.get("PSEUDEX_CANARY_SECRET", "").encode("utf-8")


def _uniform(label: str) -> float:
    """A deterministic float in [0, 1) from HMAC(secret, label)."""
    digest = hmac.new(_secret(), label.encode("utf-8"), hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big") / 2.0 ** 64


def _prob(kind: str, j: int) -> float:
    """Position j's Tardos bias p_j, drawn as sin^2(theta) with theta uniform in
    [THETA0, pi/2 - THETA0] — the Tardos distribution, deterministic from the secret."""
    theta = _THETA0 + _uniform(f"fp-prob:{kind}:{j}") * (math.pi / 2.0 - 2.0 * _THETA0)
    return math.sin(theta) ** 2


@lru_cache(maxsize=4)
def _universe(kind: str) -> tuple:
    """The SHARED pool of `_BITS` novel fake entries, one per code position, the same
    for every org. Novel by construction (filtered against the real dictionary), so a
    clone masking one proves copying and none coincides with a real name/street."""
    if not _secret():
        return ()
    avoid = canary._real_surnames() if kind == "surname" else canary._real_streets()
    stream = canary._stream("", f"fp-universe:{kind}")  # org-independent shared stream
    out: list = []
    seen: set = set()
    while len(out) < _BITS:
        word = canary._synth(stream, _ENDS[kind])
        if word in seen or word.lower() in avoid:
            continue
        seen.add(word)
        out.append(word)
    return tuple(out)


def _bit(kind: str, org_id: str, j: int, p_j: float) -> bool:
    """Org's codeword bit X_ij ~ Bernoulli(p_j), deterministic from the secret."""
    return _uniform(f"fp-bit:{kind}:{org_id}:{j}") < p_j


def fingerprint_entries(org_id: str, kind: str) -> list:
    """The org's fingerprint marks for this gazetteer: the universe entries where its
    Tardos bit is 1, or [] when no secret. Woven into the leased gazetteer by pack."""
    universe = _universe(kind)
    if not universe:
        return []
    return [universe[j] for j in range(len(universe))
            if _bit(kind, org_id, j, _prob(kind, j))]


def _g(x: int, y: int, p: float) -> float:
    """Symmetric Tardos per-position score for codeword bit x against pirate bit y."""
    a = math.sqrt((1.0 - p) / p)   # weight when the org matches a present mark
    b = math.sqrt(p / (1.0 - p))   # weight when it matches an absent one
    if y == 1:
        return a if x == 1 else -b
    return -a if x == 1 else b


def accuse(observed: Iterable, orgs: Iterable, kind: str) -> Optional[str]:
    """The org the pirate gazetteer is traced to, or None. `observed` is the set of
    (surname|street) entries recovered from a leaked/cloned bundle; the pirate bit
    y_j is 1 iff universe[j] is present. Each org is scored by the symmetric Tardos
    statistic; the top scorer is accused iff it clears the threshold Z = 4*sqrt(M),
    which bounds the innocent false-accusation rate to ~3e-5 per org."""
    universe = _universe(kind)
    if not universe:
        return None
    present = set(observed)
    y = [1 if universe[j] in present else 0 for j in range(len(universe))]
    p = [_prob(kind, j) for j in range(len(universe))]
    threshold = 4.0 * math.sqrt(len(universe))
    best: Optional[str] = None
    best_score = threshold
    for org in orgs:
        score = 0.0
        for j in range(len(universe)):
            x = 1 if _bit(kind, org, j, p[j]) else 0
            score += _g(x, y[j], p[j])
        if score > best_score:
            best, best_score = org, score
    return best
