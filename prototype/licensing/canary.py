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
import logging
import os
import struct
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, Optional

_log = logging.getLogger(__name__)

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


def enabled() -> bool:
    """Whether per-org attribution (canaries + fingerprint — one shared secret) is
    active. A cheap presence check for deciding to build a per-org bundle, without
    synthesizing the canaries just to test them (server._leased_bundle)."""
    return bool(_secret())


@lru_cache(maxsize=1)
def _real_surnames() -> frozenset:
    """The real surname dictionary (lowercased), to guarantee every canary is
    genuinely novel — a canary equal to a real name would prove nothing."""
    path = _DATA / "surnames.txt"
    if not path.exists():
        return frozenset()
    return frozenset(w.lower() for w in path.read_text(encoding="utf-8").split())


@lru_cache(maxsize=1)
def _real_streets() -> frozenset:
    """The real ГАР street vocabulary (lowercased), so a street canary is novel
    too. Lazy import to avoid a top-level cycle (pack imports canary)."""
    try:
        from licensing.pack import load_street_vocabulary  # lazy: pack imports canary
        return frozenset(s.lower() for s in load_street_vocabulary())
    except ImportError:
        # The documented cycle-avoidance case only: pack half-imported. No vocabulary
        # yet — the caller (a per-org bundle build) does not run during that window.
        return frozenset()
    except (OSError, ValueError) as exc:
        # Vocabulary present but unreadable/corrupt. DEGRADE (surname canaries and the
        # fingerprint still attribute) but do NOT hide the cause: an unfiltered street
        # canary could coincide with a real ГАР street and then prove nothing.
        _log.warning("canary: ГАР street vocabulary unavailable (%r) — street canaries "
                     "not filtered against real streets this build", exc)
        return frozenset()


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
    # LOWERCASE, to match the leased gazetteers (`_load_dictionary` /
    # load_street_vocabulary store surnames and streets lowercased). A Capitalised
    # mark stood out as an anomaly in an all-lowercase dictionary AND was stripped by
    # a one-line `.lower()` of the stolen gazetteer — a normal rebuild step — which
    # set accuse/identify to None at zero product cost (pentest WS-7 IP-thief2). A
    # lowercase mark is indistinguishable from a real entry and survives case
    # normalization; accuse/identify also casefold, so `.upper()`/`.capitalize()`
    # cannot strip it either. Removing a mark now requires KNOWING it — the secret.
    syllables = 2 + next(stream) % 2  # 2-3 syllables
    word = ""
    for _ in range(syllables):
        word += _CONS[next(stream) % len(_CONS)] + _VOW[next(stream) % len(_VOW)]
    word += endings[next(stream) % len(endings)]
    return word


def _generate(org_id: str, kind: str, endings: tuple, avoid: frozenset) -> list:
    if not _secret():
        return []
    stream = _stream(org_id, kind)
    out: list = []
    seen: set = set()
    while len(out) < _N:
        word = _synth(stream, endings)
        # `avoid` is lowercased; compare case-insensitively so a canary never
        # coincides with a real name/street regardless of case.
        if word in seen or word.lower() in avoid:
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
    """`_N` plausible-but-invented street names unique to this org, or []. Filtered
    against the real ГАР vocabulary so each is novel — a canary equal to a real
    street proves nothing (every engine masks real streets)."""
    return _generate(org_id, "street", _STREET_END, _real_streets())


def identify(observed: Iterable, orgs: Iterable) -> Optional[str]:
    """Which of `orgs` a recovered gazetteer belongs to, by canary overlap. Returns
    the org whose canaries are most present, requiring a majority so noise cannot
    misattribute; else None."""
    if not _secret():
        return None
    # Casefold both sides so a stolen gazetteer normalized to any case still matches
    # its marks (WS-7 IP-thief2): the marks are lowercase like the gazetteer, and an
    # attacker's `.lower()`/`.upper()`/`.capitalize()` cannot shift them out of the set.
    seen = {o.casefold() for o in observed}
    best: Optional[str] = None
    best_hits = 0
    for org in orgs:
        # Both canary sets count: a recovered gazetteer (surnames and/or streets)
        # is matched against this org's whole canary set, so street canaries carry
        # attribution weight too (they are injected into every marked bundle).
        marks = {m.casefold() for m in set(canary_surnames(org)) | set(canary_streets(org))}
        hits = len(marks & seen)
        if hits > best_hits:
            best, best_hits = org, hits
    return best if best_hits >= max(3, _N // 2) else None
