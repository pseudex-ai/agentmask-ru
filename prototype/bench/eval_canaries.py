"""Известные ПД, подсаженные в НАСТОЯЩИЕ сообщения.

WHY THIS EXISTS. Production dialogues have no labels, so recall on them cannot
be measured directly — and our own detector cannot be its own ground truth. A
canary sidesteps both: we KNOW what was planted and where, and everything around
it is text a real customer actually wrote.

That surrounding text is the whole point. A value in a sentence we composed is a
value in a sentence built to contain it; the same value dropped into somebody
else's message meets real punctuation, real abbreviations, a real neighbouring
order number, and a real missing space. Recall measured there is the number that
predicts production.

The canaries are chosen from the shapes that have HURT us — the colloquial
register, an oblique case, a missed space, a lower-case surname — not from the
shapes we already pass, because a canary that always survives measures nothing.

    python3 bench/eval_canaries.py <dialogues.jsonl> [--per 60]
"""

import argparse
import collections
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pseudex.detect_all import Detector  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

# (тип, значение, как это обычно вводят в текст)
CANARIES: tuple[tuple[str, str, str], ...] = (
    ("NAME", "Гончарова Анна Дмитриевна", "{}"),
    ("NAME", "гончарова анна", "{}"),
    ("NAME", "Гончаровой Анне", "передайте {}"),
    ("NAME", "ГончароваАнна", "{}"),
    ("NAME", "серёга", "запиши {}"),
    ("NAME", "виталик", "перезвони {}"),
    ("NAME", "Мамедова Лейла", "{}"),
    ("NAME", "Ким Виктор", "{}"),
    ("NAME", "Petr Ivanov", "{}"),
    ("PHONE", "+7 916 214-88-03", "тел {}"),
    ("PHONE", "89162148803", "{}"),
    ("PHONE", "8 (916) 214 88 03", "{}"),
    ("EMAIL", "i.petrov@example.ru", "{}"),
    ("LOC", "Москва, Ленинский проспект, д. 42, кв. 118", "{}"),
    ("LOC", "ленинский проспект 42", "адрес {}"),
    ("LOC", "улица Строителей, дом 53", "{}"),
    ("SNILS", "112-233-445 95", "СНИЛС {}"),
    ("SNILS", "112 233 445 95", "СНИЛС {}"),
    ("INN", "7707083893", "ИНН {}"),
    ("CARD", "4276 3800 1234 5679", "карта {}"),
    ("PASSPORT", "4509 123456", "паспорт {}"),
    ("PLATE", "А123ВС777", "госномер {}"),
    ("PLATE", "а123вс777", "номер машины {}"),
)


def carriers(path: str, limit: int) -> list[str]:
    """Real messages long enough to hide a canary inside, PII-free ones first.

    A carrier that already holds personal data would let a neighbouring span
    rescue the canary, and the number would flatter us.
    """
    out: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        for session in record.get("sessions", []):
            for message in session.get("messages", []):
                text = (message.get("text") or "").strip()
                if 40 <= len(text) <= 300 and "\n" not in text:
                    out.append(text)
        if len(out) > limit * 6:
            break
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument("--per", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260818)
    parser.add_argument("--dump", type=int, default=12)
    args = parser.parse_args()

    load_dev_bundle()
    detector = Detector()
    rng = random.Random(args.seed)

    pool = carriers(args.corpus, args.per)
    clean = [text for text in pool if not detector.detect(text)]
    print(f"сообщений-носителей: {len(clean)} (из {len(pool)}, отобраны без своих ПД)\n")

    found: collections.Counter[tuple[str, str]] = collections.Counter()
    total: collections.Counter[tuple[str, str]] = collections.Counter()
    misses: list[tuple[str, str, str]] = []

    for kind, value, frame in CANARIES:
        for _ in range(args.per):
            carrier = rng.choice(clean)
            planted = frame.format(value)
            # В середину, между предложениями — так его пишет человек.
            cut = carrier.find(" ", len(carrier) // 2)
            cut = cut if cut > 0 else len(carrier)
            text = f"{carrier[:cut]}, {planted}{carrier[cut:]}"
            at = text.index(value)
            key = (kind, value)
            total[key] += 1
            hit = any(s.entity_type == kind and s.start < at + len(value) and s.end > at
                      for s in detector.detect(text))
            if hit:
                found[key] += 1
            elif len(misses) < 400:
                misses.append((kind, value, text))

    print(f"{'ТИП':<10}{'КАНАРЕЙКА':<44}{'НАЙДЕНО':>9}")
    print("-" * 64)
    worst: list[tuple[float, str, str]] = []
    for key in total:
        rate = found[key] / total[key] * 100
        worst.append((rate, key[0], key[1]))
    for rate, kind, value in sorted(worst):
        flag = "  <<<" if rate < 100 else ""
        print(f"{kind:<10}{value[:42]:<44}{rate:>8.0f}%{flag}")
    overall = sum(found.values()) / sum(total.values()) * 100
    print("-" * 64)
    print(f"{'ВСЕГО':<54}{overall:>8.1f}%")

    if misses:
        print(f"\n--- ПРОПУЩЕНО В НАСТОЯЩЕМ ОКРУЖЕНИИ ({len(misses)}) ---")
        for kind, value, text in misses[:args.dump]:
            print(f"  {kind:<8} {value[:28]!r:30} … {text[:96]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
