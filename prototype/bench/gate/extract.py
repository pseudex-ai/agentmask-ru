"""Вытаскивает КАНДИДАТОВ, которых гейт отверг, ВМЕСТЕ С КОНТЕКСТОМ.

Кандидат — слово из арендуемого словаря имён (28 412 личных + 196 799 фамилий).
Отвергнут — не попал внутрь ни одного спана NAME/LOC.

СЛОВО БЕЗ КОНТЕКСТА РАЗМЕТИТЬ НЕЛЬЗЯ, и это не оговорка, а суть задачи. «ленина»
— улица в одной реплике и человек в другой; «алиса» — голосовой помощник в
девяти случаях из десяти и живой человек в десятом. Прибор, который разметил бы
СЛОВО, ответил бы на вопрос, которого никто не задавал: гейт решает про
ВХОЖДЕНИЕ, и потолок гейта считается по вхождениям.

ЗАПИСЫВАЮТСЯ ОБЕ СТОРОНЫ, а не только отвергнутая. Гейт — решение с двумя
исходами, и после снятия требования заглавной буквы интереснее стала вторая:
«капец» лежит в словаре фамилий и теперь маскируется как человек шестьдесят раз.
Прибор, читающий только промахи, показал бы, что чинить нечего.
"""
import collections
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1].parent))
from testkit import load_dev_bundle

load_dev_bundle()

from pseudex.detect_all import Detector

ROOT = pathlib.Path(__file__).resolve().parents[1].parent
DATA = ROOT / "licensing" / "data"
CACHE = pathlib.Path.home() / ".cache" / "pseudex-bench"
OUT = CACHE / "gate_candidates.json"

WORD = re.compile(r"[а-яё]+")
# Источники различимы полем `corpus`: у них разные лицензии и разный регистр
# речи — диспетчерские звонки против бытовых команд, — и складывать их в одно
# число можно только осознанно.
CORPORA = (("calls", "speech_calls.jsonl"), ("rudevices", "speech_rudevices.jsonl"))


def vocabulary() -> set[str]:
    words: set[str] = set()
    for name in ("first_names.txt", "surnames.txt"):
        for line in (DATA / name).read_text(encoding="utf-8").split():
            words.add(line.strip().lower())
    return words


def main() -> int:
    voc = vocabulary()
    detector = Detector()
    rows: list[dict] = []
    counts: collections.Counter = collections.Counter()
    accepted: collections.Counter = collections.Counter()
    seen = 0
    started = time.perf_counter()

    for corpus, filename in CORPORA:
        path = CACHE / filename
        if not path.exists():
            print(f"нет {path} — соберите: python3 bench/fetch_ru_speech.py", file=sys.stderr)
            return 1
        for line in path.open(encoding="utf-8"):
            text = json.loads(line)["text"]
            seen += 1
            hits = [m for m in WORD.finditer(text) if m.group() in voc]
            if not hits:
                continue
            spans = [s for s in detector.detect(text)
                     if s.entity_type in ("NAME", "LOC")]
            for hit in hits:
                inside = any(s.start <= hit.start() and hit.end() <= s.end
                             for s in spans)
                (accepted if inside else counts)[hit.group()] += 1
                rows.append({
                    "corpus": corpus,
                    "word": hit.group(),
                    "start": hit.start(),
                    "end": hit.end(),
                    "text": text,
                    "masked": inside,
                })

    OUT.write_text(json.dumps({
        "utterances": seen,
        "accepted": dict(accepted),
        "occurrences": rows,
    }, ensure_ascii=False), encoding="utf-8")

    total = sum(counts.values())
    print(f"реплик прочитано {seen:,} за {time.perf_counter() - started:.0f} с")
    print(f"кандидатов принято гейтом {sum(accepted.values()):,} "
          f"· различных слов {len(accepted):,}")
    print(f"кандидатов ОТВЕРГНУТО {total:,} · различных слов {len(counts):,}")
    covered = 0
    for rank, (_, n) in enumerate(counts.most_common(), 1):
        covered += n
        if covered * 2 >= total:
            print(f"половину вхождений покрывают {rank} слов")
            break
    print(f"записано {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
