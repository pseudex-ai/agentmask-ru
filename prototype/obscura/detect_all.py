"""Integrated detector: regex + checksum IDs + ML NER (Natasha), with
priority-based overlap resolution (checksum-validated IDs beat weak regex).
"""

from obscura import _morph_compat  # noqa: F401  (pymorphy2->pymorphy3 BEFORE natasha import)
from natasha import Doc, NewsEmbedding, NewsNERTagger, Segmenter

from obscura.address import detect_address
from obscura.context import location_is_pii, suppress
from obscura.detect import Span, detect_pii
from obscura.names import gazetteer_names, keep_location, keep_person
from obscura.normalize import normalize
from obscura.quasi import detect_quasi
from obscura.ru_pii import detect_structured
from obscura.structured import detect_structured_kv

# Higher = more trusted; wins overlaps. Checksum-validated IDs outrank phone so
# a valid INN/СНИЛС/card is never mislabeled as a bare phone.
# A marker/house-anchored ADDR span is high-confidence and must beat a NAME that
# sits inside it (the street name), so the whole address — incl. the house number
# — is masked, not just the surname. Bare NER-city LOC stays low (a coincidental
# city should lose to a real name).
_PRIORITY: dict[str, int] = {
    "SNILS": 6, "INN": 6, "CARD": 6,
    "PHONE": 5, "EMAIL": 5, "ADDR": 4,
    "NAME": 3, "DATE": 2, "PASSPORT": 2, "LOC": 2,
}


def _resolve(spans: list[Span]) -> list[Span]:
    ordered = sorted(
        spans,
        key=lambda s: (_PRIORITY.get(s.entity_type, 1), s.end - s.start),
        reverse=True,
    )
    kept: list[Span] = []
    for span in ordered:
        if all(span.end <= k.start or span.start >= k.end for k in kept):
            kept.append(span)
    return sorted(kept, key=lambda s: s.start)


class Detector:
    """Holds the Natasha NER model (external model -> class is appropriate)."""

    def __init__(self) -> None:
        self._segmenter = Segmenter()
        self._ner = NewsNERTagger(NewsEmbedding())

    def _ner_spans(self, text: str) -> list[Span]:
        doc = Doc(text)
        doc.segment(self._segmenter)
        doc.tag_ner(self._ner)
        spans: list[Span] = []
        for span in doc.spans:
            if span.type == "PER":
                value = text[span.start:span.stop]
                if keep_person(value):  # drop verb over-tags ("Оформите", "Не")
                    spans.append(Span(span.start, span.stop, "NAME", value))
            elif span.type == "LOC":
                value = text[span.start:span.stop]
                # Drop verb over-tags AND non-PII place references (city as a
                # landmark). Street+house addresses come from detect_address and
                # bypass this gate (always masked).
                if keep_location(value) and location_is_pii(text, span.start, span.stop, value):
                    spans.append(Span(span.start, span.stop, "LOC", value))
        return spans

    def detect(self, text: str) -> list[Span]:
        # Layer 0: offset-safe normalization (1:1) so spans map back to original.
        norm = normalize(text)
        # Address spans are typed ADDR (priority 4) so they outrank a NAME sitting
        # inside the street; remapped back to LOC after overlap resolution.
        address = [Span(s.start, s.end, "ADDR", s.value) for s in detect_address(norm)]
        spans = (
            detect_pii(norm)
            + detect_structured(norm)
            + self._ner_spans(norm)
            + address
            + gazetteer_names(norm)
            + detect_structured_kv(norm)   # Layer 1: JSON/forms (key types the value)
            + detect_quasi(norm)           # quasi: DOB/age/medical
        )
        # Suppress denied phones BEFORE resolving, else a phone that wins the
        # overlap (priority) and is then suppressed leaves the real entity
        # (e.g. a passport it overlapped) undetected.
        resolved = _resolve(suppress(norm, spans))
        return [Span(s.start, s.end, "LOC", s.value) if s.entity_type == "ADDR" else s
                for s in resolved]
