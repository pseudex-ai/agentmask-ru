"""Записывает ручные метки. Ключ — слово плюс реплика, никогда не номер строки."""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sheet import CLASSES, LABELS, key, load, sample


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stratum", choices=("masked", "missed"), required=True)
    parser.add_argument("--size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260831)
    parser.add_argument("--set", required=True,
                        help="i=class,i=class,... либо i-j=class для диапазона")
    args = parser.parse_args()

    occ = load()
    want = [r for r in occ if r["masked"] == (args.stratum == "masked")]
    rows = sample(want, args.size, args.seed)
    labels = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.exists() else {}

    added = 0
    for chunk in args.set.split(","):
        span, _, cls = chunk.partition("=")
        if cls not in CLASSES:
            raise SystemExit(f"неизвестный класс {cls!r}; есть {sorted(CLASSES)}")
        lo, _, hi = span.partition("-")
        for i in range(int(lo), int(hi or lo) + 1):
            labels[key(rows[i])] = cls
            added += 1

    LABELS.write_text(json.dumps(labels, ensure_ascii=False, indent=0,
                                 sort_keys=True), encoding="utf-8")
    print(f"записано {added}, всего меток {len(labels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
