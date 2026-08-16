"""Integrated detector: regex + checksum IDs + ML NER (Natasha), with
priority-based overlap resolution (checksum-validated IDs beat weak regex).
"""

from pseudex import _morph_compat  # noqa: F401  (pymorphy2->pymorphy3 BEFORE natasha import)
from natasha import Doc, NewsEmbedding, NewsNERTagger, Segmenter

from pseudex.address import detect_address
from pseudex.assets import ASSETS
from pseudex.context import location_is_pii, suppress
from pseudex.detect import Span, detect_pii
from pseudex.names import gazetteer_names, keep_location, keep_person, trim_person_span
from pseudex.normalize import normalize
from pseudex.profiling import stage
from pseudex.quasi import detect_quasi
from pseudex.ru_pii import detect_plates, detect_structured
from pseudex.structured import detect_structured_kv

# The priority table is LEASED (pseudex/assets.py). It is the arbiter of every
# overlap — which recognizer wins when two of them claim the same characters —
# and it was tuned on real mistyping incidents, so it belongs with the assets
# rather than in the shipped engine.


def _resolve(spans: list[Span], priority: dict[str, int]) -> list[Span]:
    ordered = sorted(
        spans,
        key=lambda s: (priority.get(s.entity_type, 1), s.end - s.start),
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
                    # NER swallows a capitalised word that follows a surname
                    # (it looks like a patronymic). Because masking is
                    # reversible, that extra word comes back attached to the
                    # value and the tool acts on the wrong person — so the span
                    # is trimmed to the actual name before it is minted.
                    lead, trimmed = trim_person_span(value)
                    start = span.start + lead
                    spans.append(Span(start, start + len(trimmed), "NAME", trimmed))
            elif span.type == "LOC":
                value = text[span.start:span.stop]
                # Drop verb over-tags AND non-PII place references (city as a
                # landmark). Street+house addresses come from detect_address and
                # bypass this gate (always masked).
                if keep_location(value) and location_is_pii(text, span.start, span.stop, value):
                    spans.append(Span(span.start, span.stop, "LOC", value))
        return spans

    def detect(self, text: str) -> list[Span]:
        # Every layer is timed separately: detection is the whole CPU cost of the
        # product, and "masking is slow" is only actionable once you know WHICH
        # recognizer owns the time. Zero overhead unless PSEUDEX_PROFILE=1.
        with stage("detect.total"):
            # Layer 0: offset-safe normalization (1:1) so spans map back to original.
            with stage("detect.normalize"):
                norm = normalize(text)
            # Address spans are typed ADDR (priority 4) so they outrank a NAME
            # sitting inside the street; remapped back to LOC after resolution.
            with stage("detect.address"):
                address = [Span(s.start, s.end, "ADDR", s.value) for s in detect_address(norm)]
            with stage("detect.regex"):
                spans = detect_pii(norm)
            with stage("detect.structured_id"):
                spans += detect_structured(norm)
                # RAW text on purpose — see detect_plates.
                spans += detect_plates(text)
            with stage("detect.ner"):
                spans += self._ner_spans(norm)
            spans += address
            with stage("detect.gazetteer"):
                spans += gazetteer_names(norm)
            with stage("detect.structured_kv"):   # Layer 1: JSON/forms
                spans += detect_structured_kv(norm)
            with stage("detect.quasi"):           # quasi: DOB/age/medical
                spans += detect_quasi(norm)
            # Suppress denied phones BEFORE resolving, else a phone that wins the
            # overlap (priority) and is then suppressed leaves the real entity
            # (e.g. a passport it overlapped) undetected.
            #
            # Suppression reads the ORIGINAL text, not the normalised one, and
            # that is load-bearing. Layer 0 folds digit look-alikes inside
            # digit-dense runs, and a cue word touching a number loses its last
            # letter to that fold: `заказ 9056174833` normalises to `зака3
            # 9056174833`, so the deny word no longer matches itself and the
            # order number was masked as a phone. Offsets are 1:1 by invariant,
            # so the same spans index into either text.
            with stage("detect.resolve"):
                resolved = _resolve(suppress(text, spans), ASSETS.get().priority)
            return [Span(s.start, s.end, "LOC", s.value) if s.entity_type == "ADDR" else s
                    for s in resolved]
