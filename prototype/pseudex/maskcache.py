"""Content-keyed masking cache — the O(n^2) killer.

A multi-step agent turn re-sends the GROWING transcript on every LLM call, so a
naive `/mask` re-runs full morphology over every message every time -> O(n^2) CPU
per conversation. The content cache removes that cost WITHOUT changing what gets
masked:

  CONTENT CACHE (`MaskCache`): masking is deterministic (the Vault returns the
  same token for the same value+type, and tokens are checksum-invalid so they
  never re-trigger detection AS the same entity), therefore masking a given RAW
  input always yields the same masked output. We cache
  `(org_id, sha256(raw_content)) -> masked_content` in a bounded LRU. On a hit we
  return the stored masked output and do NOT re-run morphology and do NOT
  re-record the audit (de-dup, see below). CRITICAL: we key on the RAW input and
  never feed masked output back through detection — masked tokens LOOK like PII
  (a fake phone is a valid phone shape), so `mask(mask(x))` differs from
  `mask(x)`; "skip already-masked messages" would be wrong, and this cache
  deliberately avoids that trap.

NO PII PRE-FILTER. An earlier version had a `maybe_contains_pii` gate that
skipped detection for text with "no PII signal". It was NOT a true superset of
the recognizers (single Latin names and Latin-keyed KV like {"name":"john"}
passed the gate yet detection would mask them), so it leaked raw PII to the
model. In a fail-closed PII gateway a pre-filter must be a PERFECT, permanent
superset of EVERY recognizer's trigger — an unmaintainable invariant — so it was
removed. The cache alone delivers the O(n^2) win; detection always runs.

Audit semantics on a cache hit: the audit trail answers "what PII did this org
protect". The same value re-sent N times in a growing transcript is ONE protected
value, not N. The previous code recorded it N times (inflated counts). We record
on the FIRST masking of a given (org, content) only — a cache hit skips the
record. This both de-duplicates the inflated counts and removes the cost. The
Vault token map is unaffected (tokens are deterministic regardless of audit).
"""

import hashlib
import threading
from collections import OrderedDict
from typing import Callable, TypeVar

from pseudex.inspection import MaskedText

_Cached = TypeVar("_Cached", str, MaskedText)


def content_key(org_id: str, conversation_id: str, content: str) -> str:
    """Stable cache key per (org, conversation, exact raw content).

    org_id is part of the key because tokens are per-org: the same value masks
    to different tokens for different orgs, so two orgs must never share an
    entry.

    conversation_id is part of it for a sharper reason. Masking a partial
    mention («Ленина 14») may resolve it against a fuller one said EARLIER IN
    THE SAME CONVERSATION, and that decision is true only there. Keyed on
    content alone, the first conversation's answer would be served to every
    later one — a courier sent to the address of whoever spoke first. The scope
    that makes the link safe has to reach the cache, or the cache undoes it.

    Hit rate is unaffected where it matters: the O(n^2) growing-transcript case
    resends the same text WITHIN one conversation, so the id is constant across
    exactly the resends the cache exists for."""
    h = hashlib.sha256()
    h.update(org_id.encode("utf-8"))
    h.update(b"\x00")
    h.update(conversation_id.encode("utf-8"))
    h.update(b"\x00")
    h.update(content.encode("utf-8"))
    return h.hexdigest()


class MaskCache:
    """Thread-safe bounded LRU mapping content-key -> masked content.

    Bounded so a long-lived process can't grow without limit. Thread-safe because
    masking now runs in a threadpool (multiple worker threads may hit the cache
    concurrently). The cache stores masked OUTPUT and immutable splice receipts
    (shown surfaces and coordinates only). No raw values, JSON Pointers or request
    identity are retained. Text and metadata are one atomic first-writer snapshot."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("MaskCache capacity must be >= 1")
        self._capacity = capacity
        self._lock = threading.Lock()
        self._store: "OrderedDict[str, str | MaskedText]" = OrderedDict()

    def get_or_compute(self, key: str, compute: Callable[[], _Cached]) -> tuple[_Cached, bool]:
        """Return (masked_content, was_hit). On a miss, `compute()` is called
        (which masks + records audit) and the result is stored. `compute` runs
        OUTSIDE the lock so a slow morphology pass never serializes other orgs'
        cache lookups; a benign duplicate compute under a race is harmless because
        masking is deterministic (identical output, idempotent audit-once intent
        is preserved by the first writer winning)."""
        with self._lock:
            cached = self._store.get(key)
            if cached is not None:
                self._store.move_to_end(key)
                return cached, True
        masked = compute()
        with self._lock:
            existing = self._store.get(key)
            if existing is not None:
                self._store.move_to_end(key)
                return existing, True
            self._store[key] = masked
            self._store.move_to_end(key)
            while len(self._store) > self._capacity:
                self._store.popitem(last=False)
            return masked, False

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
