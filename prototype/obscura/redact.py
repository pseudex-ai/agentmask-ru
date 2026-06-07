"""The swap layer: tokenize text on the way to the model, detokenize on the way back.

Detection is decoupled — the caller passes the spans (from any detector), so the
proxy can use the full ensemble (regex + checksum + NER) and tests can use a
lighter one. Reverse uses longest-token-first to avoid prefix collisions.
"""

from obscura.detect import Span
from obscura.vault import Vault


def mask_text(text: str, vault: Vault, spans: list[Span]) -> str:
    """Replace detected PII with consistent tokens. Pure w.r.t. text; mutates vault."""
    result = text
    for span in sorted(spans, key=lambda s: s.start, reverse=True):
        token = vault.tokenize(span.value, span.entity_type)
        result = result[: span.start] + token + result[span.end :]
    return result


def unmask_text(text: str, vault: Vault) -> str:
    """Replace known tokens with their real values (longest token first)."""
    result = text
    for token in sorted(vault.known_tokens(), key=len, reverse=True):
        if token in result:
            value = vault.detokenize(token)
            if value is not None:
                result = result.replace(token, value)
    return result
