"""Per-customer canaries woven into the leased gazetteers, for attribution.

A leaked or cloned detector — built from a stolen tuning dump — carries the
canaries of exactly the org whose lease it came from. Each org's leased gazetteer
is seeded with a handful of unique, plausible-but-invented surnames and streets
that exist in no real dictionary and in no other org's bundle. If a cloned engine
masks one of these canaries, it is attributable to that org (the cartographer's
trap-street / dictionary-Mountweazel trick).

Canaries are DETERMINISTIC per org — `HMAC-SHA256(secret, kind:org_id)` — so a
dump maps to one org and renewals do not churn attribution; the secret lives only
on the licensing server (`PSEUDEX_CANARY_SECRET`), never in the customer's image.
They are novel by construction (filtered against the real dictionary) so a clone
masking one proves copying — a real name would prove nothing.

Honest scope: attribution + deterrence, not prevention. Indistinguishable from
real entries without the secret; a Phase-1 step entangles some into the detection
logic so removal degrades the product.
"""
import hashlib
import hmac
import os
import struct
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, Optional

_DATA = Path(__file__).resolve().parent / "data"
_N = 24  # canaries per gazetteer per org — statistically decisive, few enough to hide

# Cyrillic building blocks for plausible-but-invented Russian surnames / streets.
_CONS = "бвгдзклмнпрстфх"
_VOW = "аеиоуяю"
_SURN_END = ("ов", "ев", "ин", "ын", "ский", "цкий", "ко", "ук", "ак", "ич")
_STREET_END = ("ская", "ный", "ная", "овская", "инский", "ов", "ина", "ный")


@lru_cache(maxsize=1)
def _secret() -> bytes:
    """Server-side canary secret. Empty when unset — canaries off, never a crash."""
    return os.environ.get("PSEUDEX_CANARY_SECRET", "").encode("utf-8")


@lru_cache(maxsize=1)
def _real_surnames() -> frozenset:
    """The real surname dictionary, to guarantee every canary is genuinely novel."""
    path = _DATA / "surnames.txt"
    if not path.exists():
        return frozenset()
    return frozenset(path.read_text(encoding="utf-8").split())


def _stream(org_id: str, kind: str) -> Iterator[int]:
    """A deterministic, unbounded byte stream from HMAC(secret, kind:org_id)."""
    seed = hmac.new(_secret(), f"{kind}:{org_id}".encode("utf-8"), hashlib.sha256).digest()
    counter = 0
    while True:
        block = hashlib.sha256(seed + struct.pack(">I", counter)).digest()
        counter += 1
        for byte in block:
            yield byte


def _synth(stream: Iterator[int], endings: tuple) -> str:
    syllables = 2 + next(stream) % 2  # 2-3 syllables
    word = ""
    for _ in range(syllables):
        word += _CONS[next(stream) % len(_CONS)] + _VOW[next(stream) % len(_VOW)]
    word += endings[next(stream) % len(endings)]
    return word.capitalize()


def _generate(org_id: str, kind: str, endings: tuple, avoid: frozenset) -> list:
    if not _secret():
        return []
    stream = _stream(org_id, kind)
    out: list = []
    seen: set = set()
    while len(out) < _N:
        word = _synth(stream, endings)
        if word in seen or word in avoid:
            continue
        seen.add(word)
        out.append(word)
    return out


def canary_surnames(org_id: str) -> list:
    """`_N` plausible-but-invented surnames unique to this org, or [] when no
    secret. Each is filtered against the real dictionary, so it is genuinely novel
    and a clone masking it proves copying. Not cached — the generation is cheap and
    a cached result would go stale if the secret changed; the 197k-surname load it
    filters against is cached in `_real_surnames`."""
    return _generate(org_id, "surname", _SURN_END, _real_surnames())


def canary_streets(org_id: str) -> list:
    """`_N` plausible-but-invented street names unique to this org, or []."""
    return _generate(org_id, "street", _STREET_END, frozenset())


def identify(observed: Iterable, orgs: Iterable) -> Optional[str]:
    """Which of `orgs` a recovered gazetteer belongs to, by canary overlap. Returns
    the org whose canaries are most present, requiring a majority so noise cannot
    misattribute; else None."""
    if not _secret():
        return None
    seen = set(observed)
    best: Optional[str] = None
    best_hits = 0
    for org in orgs:
        hits = len(set(canary_surnames(org)) & seen)
        if hits > best_hits:
            best, best_hits = org, hits
    return best if best_hits >= max(3, _N // 2) else None
