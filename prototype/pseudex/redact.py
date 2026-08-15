"""The swap layer: tokenize text on the way to the model, detokenize on the way back.

Detection is decoupled — the caller passes the spans (from any detector), so the
proxy can use the full ensemble (regex + checksum + NER) and tests can use a
lighter one. Reverse uses longest-token-first to avoid prefix collisions.
"""

import re

from pseudex.detect import Span
from pseudex import morph_names
from pseudex.profiling import stage
from pseudex.vault import TOKEN_RE, Vault, name_key

# A number-like run (digits + phone separators), >=7 digits — a candidate for
# digit-core detokenization when the model reformatted a numeric token.
_NUM_RUN = re.compile(r"(?<![\d])[+(]?\d[\d\s().\-]{5,}\d(?!\d)")


def _splice(text: str, spans: list[tuple[int, int, str]]) -> str:
    """Apply replacements right-to-left so the offsets of the not-yet-applied
    spans stay valid."""
    result = text
    for start, end, value in sorted(spans, key=lambda span: span[0], reverse=True):
        result = result[:start] + value + result[end:]
    return result


def mask_text(text: str, vault: Vault, spans: list[Span]) -> str:
    """Replace detected PII with consistent tokens. Pure w.r.t. text; mutates vault.

    A span whose value is ALREADY a token we issued is left untouched. This is
    load-bearing, not defensive: a fake NAME or LOC is by construction a
    well-formed name or place, so when the model echoes one back inside a new
    message, detection finds it again. Masking it a second time would mint a
    fresh token, which (a) makes the person's identity change every turn, (b)
    breaks the provider's prefix cache because the prefix is no longer stable,
    and (c) — worst — makes detokenization return the intermediate TOKEN instead
    of the real value, so the tool executes on a plausible but WRONG person.

    The content cache hides this from the obvious test: re-masking the same RAW
    text is a cache hit. The failure only appears when the token comes back
    inside different surrounding text, which is exactly what a multi-turn agent
    does.

    KNOWN LIMIT: a real person whose name exactly equals a minted fake name would
    be passed through unmasked. That needs a fake-name pool far larger than the
    current seed list (see names.py) — the same production swap already planned."""
    return _splice(text, [
        (span.start, span.end, _token_for_text(span, vault))
        for span in spans
        if not vault.is_minted_token(span.value)
    ])


def _token_for_text(span: Span, vault: Vault) -> str:
    """The token as it should READ in this sentence.

    The vault stores one nominative token per person; the text needs it in the
    case the original was written in, or the sentence says «Позвоните Руслан
    Хвостов» and the model repairs the disagreement. A repaired token does not
    match the vault, and then the customer's tool executes on a person who does
    not exist — silently, which is the worst way for this to fail.

    Only NAME is inflected. Numbers and documents have no case, and LOC is
    generated as a whole phrase whose internal agreement is the generator's job.
    """
    token = vault.tokenize(span.value, span.entity_type)
    if span.entity_type != "NAME":
        return token
    case = morph_names.detect_case(span.value)
    if case is None or case == "nomn":
        return token
    # Gender comes from the REAL person, not from re-reading the token. The two
    # agree by construction — the token was minted for this gender — and asking
    # the token again can only lose: a fake first name the dictionary happens
    # not to know (София) makes the whole span read as the wrong gender, and
    # then the surname is inflected as a man's.
    return morph_names.inflect_person(
        token, case, morph_names.detect_gender(span.value))


def unmask_text(text: str, vault: Vault) -> str:
    """Replace tokens with their real values, then catch numeric tokens the model
    REFORMATTED via a digit-signature match.

    Candidates are found by SHAPE (`Vault.TOKEN_RE`) and resolved in batched
    indexed lookups, so the cost tracks the length of the answer rather than the
    size of the vault. The previous approach loaded every token the org had ever
    minted and substring-scanned the text once per token, which made an org with
    100k tokens pay 100k scans on every single response."""
    with stage("unmask.total"):
        restored = _restore_reformatted(_restore_tokens(text, vault), vault)
        return _restore_inflected(restored, vault)


def _restore_tokens(text: str, vault: Vault) -> str:
    matches = list(TOKEN_RE.finditer(text))
    if not matches:
        return text
    values = vault.detokenize_many({match.group() for match in matches})
    return _splice(text, [
        (match.start(), match.end(), values[match.group()])
        for match in matches if match.group() in values
    ])


def _restore_reformatted(text: str, vault: Vault) -> str:
    """Numeric tokens the model rewrote (+7… -> 8…, separators stripped) no longer
    match their minted shape, so they are resolved by digit signature instead."""
    runs = [(match, re.sub(r"\D", "", match.group())) for match in _NUM_RUN.finditer(text)]
    if not runs:
        return text
    candidates: set[str] = set()
    for _, digits in runs:
        candidates.add(digits)
        if len(digits) >= 10:
            candidates.add(digits[-10:])
    resolved = vault.resolve_digit_signatures(candidates)
    if not resolved:
        return text
    spans: list[tuple[int, int, str]] = []
    for match, digits in runs:
        # Full signature wins over the phone last-10 fallback.
        value = resolved.get(digits) or (resolved.get(digits[-10:]) if len(digits) >= 10 else None)
        if value is not None:
            spans.append((match.start(), match.end(), value))
    return _splice(text, spans)


# One to three capitalised Cyrillic words — the shape a personal name takes in
# running text. Deliberately permissive: a false positive costs one indexed
# lookup that finds nothing, a false negative costs a fake value delivered to a
# tool as if it were real.
_NAME_WORD = re.compile(r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?")


def _name_windows(text: str) -> list[tuple[int, int, str]]:
    """Every contiguous 1-3 word window of capitalised Cyrillic words.

    Windows rather than maximal runs, because a sentence-initial word is
    capitalised too: `Позвоните Ивану Щукину` is one run of three, and looking
    it up whole finds nothing while `Ивану Щукину` would have matched. Misses
    are free — an indexed point query that returns no row — so enumerating is
    cheaper than being clever about which word starts a sentence.
    """
    words = [(m.start(), m.end(), m.group()) for m in _NAME_WORD.finditer(text)]
    windows: list[tuple[int, int, str]] = []
    for i in range(len(words)):
        for size in (3, 2, 1):
            if i + size > len(words):
                continue
            start, end = words[i][0], words[i + size - 1][1]
            # Only if the words are adjacent — a window may not jump a comma or
            # a lowercase word, which would join two unrelated names.
            if re.fullmatch(r"[А-ЯЁа-яё\s-]+", text[start:end]) is None:
                continue
            windows.append((start, end, text[start:end]))
    return windows


def _restore_inflected(text: str, vault: Vault) -> str:
    """NAME tokens the model put into another case no longer match their minted
    shape, so they are resolved by case-invariant key instead.

    Exactly parallel to `_restore_reformatted` for numbers, and the reason a
    fake no longer reaches a customer's tool when the model writes `Руслану
    Хвостову` instead of the nominative it was handed. Longest window first, so
    a full name wins over its own surname and half a name is never replaced.
    """
    windows = _name_windows(text)
    if not windows:
        return text
    keys: dict[tuple[int, int], str] = {}
    for start, end, surface in windows:
        try:
            keys[(start, end)] = name_key(surface)
        except Exception:  # noqa: BLE001 - morphology must never break a response
            continue
    resolved = vault.resolve_name_keys(set(keys.values()))
    if not resolved:
        return text
    spans: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for start, end, surface in sorted(windows, key=lambda w: w[1] - w[0], reverse=True):
        value = resolved.get(keys.get((start, end), ""))
        if value is None:
            continue
        if any(a < end and start < b for a, b in taken):
            continue
        taken.append((start, end))
        spans.append((start, end, _in_case_of(value, surface)))
    return _splice(text, spans)


def _in_case_of(value: str, surface: str) -> str:
    """Put the real name into the case the token was standing in.

    Both readings of "restore" are legitimate and they disagree, so neither can
    be the only answer:

      * a TOOL ARGUMENT wants the person's name — `create_lead(name=...)` should
        receive «Иванов Пётр Сергеевич», not the dative the sentence happened to
        need;
      * TEXT SHOWN TO A HUMAN wants the sentence to still parse — «Позвоните
        Иванов Пётр Сергеевич» is what a machine translation reads like.

    Matching the case of what was replaced satisfies both without a mode flag:
    inside JSON the model writes the value in the nominative, so the nominative
    comes back; inside prose it writes the case the sentence needs, and the same
    case comes back.
    """
    case = morph_names.detect_case(surface)
    if case is None or case == "nomn":
        return value
    return morph_names.inflect_person(value, case, morph_names.detect_gender(value))


# Longest token across our format-preserving tokens is well under this.
_STREAM_KEEP = 64


def unmask_stream_chunk(delta: str, carry: str, vault: Vault, flush: bool) -> tuple[str, str]:
    """Detokenize one streamed delta, returning (emit, new_carry).

    STATELESS by design: the caller owns the carry. A host gateway (LiteLLM) runs
    many worker processes, so keeping per-stream state inside the sidecar would
    need a shared store plus TTL cleanup for streams that die mid-flight. Handing
    the carry back to the caller — which already holds the connection — removes
    that whole class of problem.

    The carry withholds the last `_STREAM_KEEP` chars from the user until more
    arrives, so a token split across two SSE chunks is still replaced. Privacy
    note: streaming only affects the RESPONSE leg (fake -> real for the user); the
    model already received a fully-masked request, so a rare split is cosmetic,
    never a real-PII leak."""
    raw = carry + delta
    if flush:
        return unmask_text(raw, vault), ""
    if len(raw) <= _STREAM_KEEP:
        return "", raw
    return unmask_text(raw[:-_STREAM_KEEP], vault), raw[-_STREAM_KEEP:]


class StreamDetokenizer:
    """Stateful wrapper over `unmask_stream_chunk` for the in-process proxy leg,
    where one object can own the carry for the life of a single stream."""

    def __init__(self, vault: Vault) -> None:
        self._vault = vault
        self._carry = ""

    def feed(self, chunk: str) -> str:
        emit, self._carry = unmask_stream_chunk(chunk, self._carry, self._vault, False)
        return emit

    def flush(self) -> str:
        emit, self._carry = unmask_stream_chunk("", self._carry, self._vault, True)
        return emit
