"""The swap layer: tokenize text on the way to the model, detokenize on the way back.

Detection is decoupled — the caller passes the spans (from any detector), so the
proxy can use the full ensemble (regex + checksum + NER) and tests can use a
lighter one. Reverse uses longest-token-first to avoid prefix collisions.
"""

import re

from obscura.detect import Span
from obscura.vault import Vault

# A number-like run (digits + phone separators), >=7 digits — a candidate for
# digit-core detokenization when the model reformatted a numeric token.
_NUM_RUN = re.compile(r"(?<![\d])[+(]?\d[\d\s().\-]{5,}\d(?!\d)")


def mask_text(text: str, vault: Vault, spans: list[Span]) -> str:
    """Replace detected PII with consistent tokens. Pure w.r.t. text; mutates vault."""
    result = text
    for span in sorted(spans, key=lambda s: s.start, reverse=True):
        token = vault.tokenize(span.value, span.entity_type)
        result = result[: span.start] + token + result[span.end :]
    return result


def unmask_text(text: str, vault: Vault) -> str:
    """Replace known tokens with their real values (longest token first), then
    catch numeric tokens the model REFORMATTED via a digit-signature match."""
    result = text
    for token in sorted(vault.known_tokens(), key=len, reverse=True):
        if token in result:
            value = vault.detokenize(token)
            if value is not None:
                result = result.replace(token, value)
    index = vault.numeric_index()
    if not index:
        return result

    def _restore(match: re.Match) -> str:
        run = match.group(0)
        digits = re.sub(r"\D", "", run)
        for key in (digits, digits[-10:] if len(digits) >= 10 else ""):
            if key and key in index:
                return index[key]
        return run

    return _NUM_RUN.sub(_restore, result)


# Longest token across our format-preserving tokens is well under this.
_STREAM_KEEP = 64


class StreamDetokenizer:
    """Detokenizes a streamed response. Carries a tail buffer so a token split
    across SSE chunks is still replaced. Privacy note: streaming only affects the
    RESPONSE leg (fake tokens -> real for the user); the model already received a
    fully-masked request, so a rare split is cosmetic, never a real-PII leak."""

    def __init__(self, vault: Vault) -> None:
        self._vault = vault
        self._raw = ""

    def feed(self, chunk: str) -> str:
        self._raw += chunk
        if len(self._raw) <= _STREAM_KEEP:
            return ""
        head, self._raw = self._raw[:-_STREAM_KEEP], self._raw[-_STREAM_KEEP:]
        return unmask_text(head, self._vault)

    def flush(self) -> str:
        out = unmask_text(self._raw, self._vault)
        self._raw = ""
        return out
