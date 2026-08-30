"""Разметка голосового набора: адрес, не адрес, неоднозначно.

ОТКУДА. 122 уникальные реплики из OpenSTT `asr_calls_2_val` — настоящие русские
телефонные звонки, расшифрованные человеком, — отобранные по наличию адресной
лексики. Разметка сделана вручную и глазами; автоматической её сделать нельзя,
потому что весь смысл набора в том, что адресная лексика и адрес — разные вещи.

ТРИ КЛАССА, А НЕ ДВА. «квартира шестьдесят семь» в разговоре диспетчера почти
наверняка часть адреса, а в этой реплике, вырванной из звонка, опознать этого
нельзя. Такие уходят в `неоднозначно` и НЕ участвуют ни в полноте, ни в
точности. Загонять их в один из двух классов значило бы мерить не детектор, а
нашу готовность угадывать.

ЧТО ДЕЛАЕТ ЭТОТ НАБОР ЦЕННЫМ. Негативы здесь настоящие, из той же речи:
«на территории улицы лермонтова понимаете о чем мы» называет улицу и не является
адресом. Ни один генератор такого не построит, потому что для этого надо не
знать заранее, где адрес.

Лицензия исходника — CC BY-NC 4.0: мерить можно, отгружать нельзя. Поэтому здесь
лежат только НОМЕРА строк и метки, а тексты берутся из
~/.cache/pseudex-bench/speech_calls.jsonl, который в репозиторий не попадает.
"""
import json
import sys
from pathlib import Path

# Номер в списке уникальных кандидатов -> метка.
ADDRESS = {7, 11, 13, 18, 20, 23, 29, 31, 32, 34, 42, 46, 47, 58, 60, 62, 64,
           65, 69, 71, 72, 77, 85, 89, 95, 103, 106, 107, 108, 109, 110, 117}
UNCLEAR = {2, 4, 28, 59, 67, 75, 78, 82, 90, 92, 97, 109}
# всё остальное — адресная лексика без адреса

CACHE = Path.home() / ".cache" / "pseudex-bench"


def candidates() -> list[str]:
    import re
    rows = [json.loads(line)["text"]
            for line in (CACHE / "speech_calls.jsonl").open(encoding="utf-8")]
    st = re.compile(r"\b(улиц\w*|проспект\w*|переул\w*|бульвар\w*|шоссе|набережн\w*"
                    r"|площад\w*|проезд\w*|микрорайон\w*|мкр|тупик\w*|аллея|квартал\w*)\b",
                    re.IGNORECASE)
    house = re.compile(r"\b(дом|корпус|квартир\w*|подъезд\w*|этаж\w*|строени\w*)\b",
                       re.IGNORECASE)
    seen, out = set(), []
    for row in rows:
        if (st.search(row) or house.search(row)) and row not in seen:
            seen.add(row)
            out.append(row)
    return out


def build() -> list[dict]:
    out = []
    for number, text in enumerate(candidates(), 1):
        if number in UNCLEAR:
            label = "неоднозначно"
        elif number in ADDRESS:
            label = "адрес"
        else:
            label = "не адрес"
        out.append({"n": number, "label": label, "text": text})
    return out


if __name__ == "__main__":
    data = build()
    counts = {}
    for row in data:
        counts[row["label"]] = counts.get(row["label"], 0) + 1
    path = CACHE / "voice_addresses.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(data)} реплик -> {path}")
    for label, count in sorted(counts.items()):
        print(f"   {label:<14} {count}")
