"""Независимая линия: голая Natasha + наивные регулярки. НАШИХ словарей нет.

Смысл в том, чтобы она ошибалась ИНАЧЕ. Всё, что нашла она и не нашли мы, —
кандидат в пропуски; размечать семь тысяч сообщений не нужно, нужно посмотреть
глазами на расхождения.
"""
import re

from pseudex import _morph_compat  # noqa: F401
from natasha import Doc, NewsEmbedding, NewsMorphTagger, NewsNERTagger, Segmenter

_SEG = Segmenter()
_EMB = NewsEmbedding()
_NER = NewsNERTagger(_EMB)
_MORPH = NewsMorphTagger(_EMB)

_PHONE = re.compile(r"(?:\+7|8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b")
_LONGNUM = re.compile(r"\b\d{10,20}\b")


def spans(text: str) -> list[tuple[str, int, int, str]]:
    out: list[tuple[str, int, int, str]] = []
    doc = Doc(text)
    doc.segment(_SEG)
    doc.tag_ner(_NER)
    for span in doc.spans:
        kind = {"PER": "NAME", "LOC": "LOC", "ORG": "ORG"}.get(span.type)
        if kind:
            out.append((kind, span.start, span.stop, text[span.start:span.stop]))
    for rx, kind in ((_PHONE, "PHONE"), (_EMAIL, "EMAIL"), (_LONGNUM, "NUM")):
        for m in rx.finditer(text):
            out.append((kind, m.start(), m.end(), m.group()))
    return out
