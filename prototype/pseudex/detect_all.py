"""Integrated detector: regex + checksum IDs + ML NER (Natasha), with
priority-based overlap resolution (checksum-validated IDs beat weak regex).
"""

from pseudex import _morph_compat  # noqa: F401  (pymorphy2->pymorphy3 BEFORE natasha import)
from natasha import Doc, NewsEmbedding, NewsNERTagger, Segmenter

import re

from pseudex.address import detect_address
from pseudex.assets import ASSETS
from pseudex.context import location_is_pii, suppress
from pseudex import morph_names
from pseudex.detect import NameSpan, Span, detect_pii
from pseudex.names import (gazetteer_names, keep_location, keep_person,
                           trim_document_words, trim_person_span)
from pseudex.normalize import normalize
from pseudex import metrics as runtime_metrics
from pseudex.profiling import stage
from pseudex.quasi import detect_quasi
from pseudex.ru_pii import detect_plates, detect_structured, detect_vehicle_ids
from pseudex.spoken import (detect_spoken_email, detect_spoken_ids,
                            detect_spoken_plate)
from pseudex.credentials import detect_credentials
from pseudex.structured import detect_structured_kv

# The priority table is LEASED (pseudex/assets.py). It is the arbiter of every
# overlap — which recognizer wins when two of them claim the same characters —
# and it was tuned on real mistyping incidents, so it belongs with the assets
# rather than in the shipped engine.


# A CHECKSUM COUNTED ON A SUB-RUN DOES NOT DECIDE HOW LONG THE SUPER-SPAN IS.
#
# `+79628863588` is a phone that PASSES the СНИЛС mod-101 — about one random
# eleven-digit number in a hundred does — and `_SNILS_NODASH_RE` (`\b\d{11}\b`)
# runs from index 1, five characters shorter than the span libphonenumber reads.
# PRIORITY puts SNILS (6) above PHONE (5), and `_resolve` sorts by priority with
# LENGTH only as a tiebreak, so the checksum of the SUB-RUN rewrote the BOUNDARY
# of the super-span: the substitute stood on eleven digits, the «+» stayed a
# literal, and the leaf received a value in the СНИЛС notation instead of a
# phone (g07 `rag-008`, `form OUT/tool_arg 0/1`).
#
# THE PRIORITY TABLE IS NOT TOUCHED, and its comment stays true where it was
# written: at EQUAL boundaries a valid INN/СНИЛС/card still outranks a bare
# phone. The rule is only about a STRICT containment whose BOUNDARY CHARACTER —
# the one character of the wider span standing just outside the sub-run — is not
# a digit: a «+», an international prefix, a separator. That character is
# evidence about where the value ENDS, and a checksum computed on a shorter run
# has no business overruling it. A digit there means the sub-run is a piece of a
# longer NUMBER, and there the checksum keeps its say.
_CHECKSUM_TYPES = frozenset({"SNILS", "INN", "CARD", "VIN", "OGRN", "OGRNIP"})


def _boundary_beats_checksum(spans: list[Span], text: str) -> list[Span]:
    """Drop a checksum span that is a strict, non-digit-bounded sub-run of one
    wider span of another type. See the block comment above."""
    out: list[Span] = []
    for span in spans:
        if span.entity_type not in _CHECKSUM_TYPES:
            out.append(span)
            continue
        swallowed = False
        for other in spans:
            if (other is span or other.entity_type == span.entity_type
                    or not (other.start <= span.start and span.end <= other.end)
                    or (other.start == span.start and other.end == span.end)):
                continue
            if ((other.start < span.start and text[span.start - 1].isdigit())
                    or (span.end < other.end and text[span.end].isdigit())):
                continue
            swallowed = True
            break
        if not swallowed:
            out.append(span)
    return out


def _resolve(spans: list[Span], priority: dict[str, int],
             text: str = "", keyed: list[Span] | None = None) -> list[Span]:
    """Разрешение пересечений: по приоритету, потом по длине, без наложений.

    КЛЮЧ ПОБЕЖДАЕТ ФОРМУ, и это выше любого приоритета в таблице. `{"passport":
    "34 50 213278"}` уходило к модели как ТЕЛЕФОН: десять цифр, разбитые 2-2-6,
    libphonenumber читает уверенно, а PHONE в таблице старше PASSPORT. Ключ при
    этом буквально называет тип — сильнее свидетельства не бывает, и таблица
    приоритетов про догадки по форме, а не про то, что написано прямым текстом.
    22 паспорта и один ИНН на AgentPII v3 ровно так и терялись.

    НО ТОЛЬКО ПРОТИВ ДРУГОГО ТИПА. Ключ отвечает на вопрос «что это», а не «где
    это кончается»: «адрес: Москве, проспекте Мира» разбирается ключом как LOC
    «Москве» — и, победив, обрезал адрес до города, а улица уходила к модели
    открытым текстом. Поэтому спан по ключу отбрасывается, если спан ТОГО ЖЕ
    типа содержит его целиком: там нечего решать, а длина решается ниже.

    Осторожность та же, что у самого `KEY_TYPE`: ключ типизирует ВЕСЬ значение
    без проверки формы, поэтому в карте ключей стоят только однозначные слова.
    Здесь это правило только доводится до конца.
    """
    def _crosses(other: Span, span: Span) -> bool:
        """Спан ПЕРЕСЕКАЕТ ключевой, не будучи целиком внутри него."""
        return (other is not span
                and other.start < span.end and span.start < other.end
                and not (span.start <= other.start and other.end <= span.end))

    # БУСТ СНИМАЕТСЯ ПРИ ЛЮБОМ ПЕРЕСЕЧЕНИИ, А НЕ ТОЛЬКО ПРИ ВЛОЖЕНИИ ТОГО ЖЕ
    # ТИПА. Проверка на вложение закрывала ровно одну форму и оставляла
    # открытой утечку: `_FORM_KV` обрезает значение на 60 символах, поэтому
    # длинная строка «Клиент: …» даёт ОБРЕЗАННЫЙ ключевой спан, который по
    # бусту побеждает нормально найденный телефон — и телефон выбрасывается
    # ЦЕЛИКОМ, вместе с хвостом за границей обрезки. «имя: <58 букв>
    # +79991234567» отдавало модели весь номер открытым текстом.
    #
    # Случай, ради которого буст писался, сохраняется: в `{"passport": "34 50
    # 213278"}` спан PHONE совпадает с ключевым по границам, то есть вложен, и
    # ключ по-прежнему побеждает форму.
    boosted = [span for span in (keyed or ())
               if not any(_crosses(other, span) for other in spans)]
    keyed_ids = {id(span) for span in boosted}
    ordered = sorted(
        spans,
        key=lambda s: (id(s) in keyed_ids,
                       priority.get(s.entity_type, 1), s.end - s.start),
        reverse=True,
    )
    kept: list[Span] = []
    for span in ordered:
        if all(span.end <= k.start or span.start >= k.end for k in kept):
            kept.append(span)
    return _merge_places(sorted(kept, key=lambda s: s.start), text)


# What may sit between two halves of one address: a comma, a space, and the
# abbreviations that introduce the next part.
_ADDRESS_JOIN = re.compile(r"(?i)^[\s,]*(?:г\.?|город|ул\.?|улица|д\.?|дом|"
                           r"пр-?т|проспект|пер\.?|переулок|наб\.?|б-?р|мкр\.?)?[\s,]*$")


def _merge_places(spans: list[Span], text: str = "") -> list[Span]:
    """Join `Москва` + `Ленинский проспект 42` into ONE address span.

    They arrive separately because a city and a street are separate entities,
    and separately they get two unrelated substitutes — the customer's single
    address becomes a city in one region and a street in another, which is worse
    than either half being wrong. One span, one substitute, one place.

    Only adjacent LOC spans are merged, and only across a gap that is punctuation
    or an address abbreviation, so two places mentioned in one sentence
    («доставка из Москвы в Казань») stay two.
    """
    if not text:
        return spans
    merged: list[Span] = []
    for span in spans:
        # ADDR, not just LOC: the remap to LOC happens AFTER resolution, so a
        # street still carries its internal type here.
        places = {"LOC", "ADDR"}
        if (merged and merged[-1].entity_type in places and span.entity_type in places
                and span.start - merged[-1].end <= 12
                and _ADDRESS_JOIN.match(text[merged[-1].end:span.start])):
            previous = merged.pop()
            merged.append(Span(previous.start, span.end, previous.entity_type,
                               text[previous.start:span.end]))
            continue
        merged.append(span)
    return merged


_STREET_WORD = re.compile(
    r"\b(ул|улиц\w*|пр-?кт|проспект\w*|пер|переул\w*|б-р|бульвар\w*|ш|шоссе|мкр|"
    r"микрорайон\w*|д|дом|кв|квартир\w*|корп|стр|влад|пос|посёл\w*|посел\w*|"
    r"дер|деревн\w*|село|г|город\w*)\b", re.IGNORECASE)


def _guess_inside_person(span: Span, ner: list[Span], text: str) -> bool:
    """A marker-less address guess sitting inside a name NER actually found."""
    surface = text[span.start:span.end]
    if _STREET_WORD.search(surface) or any(c.isdigit() for c in surface):
        return False
    return any(other.entity_type == "NAME"
               and other.start <= span.start and span.end <= other.end
               for other in ner)


def _drop_address_inside_multipart_name(spans: list[Span], text: str) -> list[Span]:
    """Drop an ADDR guess that sits inside a MULTI-PART NAME (S1 defect B).

    A marker-less street guess typed «битюкова» (ADDR) outranks the full person
    «битюкова зинаида» (NAME) and left the given name «зинаида» in the clear.
    `_guess_inside_person` only drops an ADDR inside a name the NER found; the
    gazetteer name below is produced later and the NER misses the lower-case
    full name, so the ADDR won on priority. A single-word street («Пушкина»
    without a given) stays ADDR — the NAME here has at least two parts, so the
    whole person outranks the partial street guess.
    """
    full_names = [s for s in spans
                  if s.entity_type == "NAME"
                  and len(text[s.start:s.end].split()) >= 2]
    if not full_names:
        return spans
    return [s for s in spans
            if not (s.entity_type == "ADDR"
                    and any(n.start <= s.start and s.end <= n.end
                            and not (n.start == s.start and n.end == s.end)
                            for n in full_names))]


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
                # `text` (the RAW text) is passed through, and it is KEPT by the
                # Lead's integration review: it is the only reading of a HEX value
                # behind a cue (a UUID's `B`, a ЕЛС series' `В`), and the raw
                # reading supersedes the folded one inside `detect_structured`.
                # Reverting this one argument degrades the telecom and utility
                # families to the NORMALIZED reading — a wrong value restored to
                # the customer's tool, never a leak — which is why it is kept;
                # `detect_structured(text, raw="")` stays callable without it.
                spans += detect_structured(norm, text)
                # DICTATED ALOUD, so no digit exists for the arms above to find.
                # Measured on a corpus built from real transcripts: 281
                # identifiers spoken as words, and every recognizer here missed
                # all of them. The spoken arm only turns words into a digit
                # string; the SAME checksums decide whether it is an identifier.
                spans += detect_spoken_ids(norm)
                # Почта и госномер вслух — у них не отбор кандидатов подводит,
                # а отсутствие шаблона: «воронина собака яндекс точка ру» не
                # похожа ни на что, что ищут ветки выше.
                spans += detect_spoken_email(norm)
                spans += detect_spoken_plate(norm)
                # RAW text: a credential is ASCII and self-anchored, so the
                # look-alike fold can only hurt it. Offsets are 1:1 either way.
                spans += detect_credentials(text)
                spans += detect_vehicle_ids(text)
                # RAW text on purpose — see detect_plates.
                spans += detect_plates(text)
            with stage("detect.ner"):
                ner = self._ner_spans(norm)
                spans += ner
            # EVIDENCE BEATS A GUESS. ADDR outranks NAME so that a street named
            # after a person is masked as a street — but a marker-less street is
            # a GUESS: «adjective + type» with no «улица» in sight. Natasha
            # typed «Мкртчян Ашот» a person, the guess claimed «Мкртчян», and
            # ADDR's higher priority handed the customer a place where a person
            # stood. Foreign surnames take the whole loss, because those are the
            # ones the street vocabulary has no opinion about.
            #
            # Narrow on purpose: only a span with NO street-type word and NO
            # digits, sitting inside a span NER called a person, is dropped.
            # «улица Тверская» and «Ленинский проспект 42» keep every word.
            address = [span for span in address
                       if not _guess_inside_person(span, ner, norm)]
            spans += address
            with stage("detect.gazetteer"):
                # НАЗВАНИЕ ДОКУМЕНТА СНИМАЕТСЯ И С ГАЗЕТИРНЫХ СПАНОВ: «ашот инн»,
                # «кукушкин инн» уезжали в аргумент `customer_name` вместе со
                # словом «ИНН». Полная обрезка здесь тоже пробовалась и даёт
                # +0.5 имени ценой -0.4 адресу и -0.2 полноте на MASSIVE —
                # размен нулевой, а риск живой. Узкое правило не может стоить
                # ничего: «ИНН» именем не бывает.
                for span in gazetteer_names(norm):
                    # ПЕРЕСОБИРАТЬ СПАН МОЖНО, ТОЛЬКО ЕСЛИ ЕГО ЗНАЧЕНИЕ И ЕСТЬ
                    # СРЕЗ ТЕКСТА. `_possessive_names` отдаёт «Женя» на месте
                    # слова «женин» — базовое имя, а не написанное, — и подсчёт
                    # конца по длине сдвигал границу на чужие символы. Измерено:
                    # полнота имён на MASSIVE падала на 1.6 пункта, и это было
                    # не свойство обрезки, а эта арифметика.
                    if norm[span.start:span.end] != span.value:
                        spans.append(span)
                        continue
                    lead, trimmed = trim_document_words(span.value)
                    if not trimmed:
                        continue
                    start = span.start + lead
                    spans.append(Span(start, start + len(trimmed),
                                      span.entity_type, trimmed))
            with stage("detect.structured_kv"):   # Layer 1: JSON/forms
                # KEPT ASIDE: a KV span carries its own evidence. The KEY typed
                # the value — that is stronger than any word standing near it —
                # so re-checking it against the cue lists can only lose.
                #
                # It did: `{"passport": "4509123456"}` was typed correctly by the
                # key and then thrown away, because the passport cue list holds
                # «паспорт» and not the Latin «passport». A customer's JSON field
                # went to the model in the clear while the same number after the
                # Russian word was masked. Extending the cue list would have
                # fixed one key and left the next one to be discovered the same
                # way; the provenance is the real answer.
                #
                # `text` (the RAW text) is the second argument, and it is what the
                # KEY path reads a VALUE from: `normalize()` folds digit
                # look-alikes inside any run of five or more real digits, so a
                # UUID behind its field key arrived as `…AE58…` and the round trip
                # gave the customer's tool a value they never wrote. Offsets are
                # shared because the fold is 1:1; the masks are unchanged.
                kv_spans = detect_structured_kv(norm, text)
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
                candidates = _drop_address_inside_multipart_name(spans, text)
                kept = suppress(text, candidates)
                # THE OVER-MASKING GUARD IS COUNTED HERE, and this is the ONLY
                # point where it can be. A denied span mints no token and writes
                # no audit row, so `/stats` cannot derive it from the journal the
                # way `by_type` is derived — `context.py` owns the decision, the
                # detector owns the tally, and `metrics.TypeCounter` is where the
                # two meet. The UI renders it beside the masked counts as
                # «suppressed».
                #
                # POSITION-KEYED, NOT IDENTITY-KEYED, because `suppress` RETYPES
                # a personal date DATE -> DOB and hands back a fresh `Span`: a
                # retype is still a mask, and an identity diff would report it as
                # a denial. A span is denied exactly when no kept span covers its
                # offsets.
                #
                # AFTER `suppress`, deliberately: if the wider span is denied by
                # context the checksum sub-run stays, so the value is masked
                # either way. Dropping it earlier could leave the text with
                # nothing at all — a leak bought for a notation.
                kept_positions = {(s.start, s.end) for s in kept}
                denied = [s.entity_type for s in candidates
                          if (s.start, s.end) not in kept_positions]
                if denied:
                    runtime_metrics.SUPPRESSED.add_many(denied)
                resolved = _resolve(
                    _boundary_beats_checksum(kept, text) + kv_spans,
                    ASSETS.get().priority, text, keyed=kv_spans)
            # A NAME LEAVES WITH THE CASES ITS SENTENCE ALLOWS (`NameSpan`): the
            # vault reads the phrase alone, and «на имя марину» alone is a man.
            return [Span(s.start, s.end, "LOC", s.value) if s.entity_type == "ADDR"
                    else NameSpan(s.start, s.end, "NAME", s.value,
                                  morph_names.governing_cases(text, s.start, s.value))
                    if s.entity_type == "NAME" and not isinstance(s, NameSpan) else s
                    for s in resolved]
