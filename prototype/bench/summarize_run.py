"""Сводка одного прогона: заголовочные числа из каждого файла в один документ.

ЗАЧЕМ. `bench/runs/<дата>/` — это два десятка текстовых выводов, и чтобы
сравнить два замера, человеку приходится открывать сорок файлов. Здесь из
каждого достаётся ровно та строка, ради которой шаг и запускался, — а сырой
вывод остаётся на месте, потому что заголовочное число никогда не объясняет,
почему оно такое.

ВЫТАСКИВАЕТСЯ ПО ЯВНОМУ ПРАВИЛУ НА ШАГ, а не общей регуляркой. Одна регулярка
на все файлы молча подхватывает не ту строку при первом же изменении формата
вывода, и сводка начинает врать тише, чем ошибаться.

    python3 bench/summarize_run.py bench/runs/2026-09-01
"""
import json
import pathlib
import re
import sys

# шаг -> сколько строк вокруг совпадения показать
PATTERNS: dict[str, tuple[str, int]] = {
    "10-golden": (r"^OVERALL", 0),
    "11-dirty": (r"^OVERALL|type-aware miss|TRUE-LEAK", 0),
    "12-stress": (r"^OVERALL|false masks", 0),
    "13-addr-fresh-seed": (r"^OVERALL|ПОРОГ|type-aware miss|TRUE-LEAK", 0),
    "14-overmasking": (r"наблюдаемая точность|СЕРТИФИЦИРУЕТ|ошибок", 0),
    "20-nerel-recall": (r"^PERSON |Cyrillic-only", 0),
    "21-nerel-precision": (r"ТОЧНОСТЬ|спанов выдано", 0),
    "22-massive-ru": (r"^person|^email_address|^place_name", 0),
    "23-pii-bench": (r"^ВСЕГО", 0),
    "24-voice": (r"полнота|ПОКРЫТИЕ|точность ", 0),
    "25-gate": (r"ЗАМАСКИРОВАНО|ПРОПУЩЕНО|ОБЯЗАНЫ|СДВИГ", 0),
    "26-prose-volume": (r"предложений|срабатываний|^ТИП|^[A-Z]+\s+\d", 0),
    "30-noise-ladder": (r"^\s*\d|СТУПЕНЬ", 0),
    "31-noise-by-type": (r"^[A-Z]", 0),
    "32-metamorphic": (r"инвариант|устойч|всего|%", 0),
    "33-gar-cut": (r"^\s*\d+\s+\d|порог|STREET_MIN", 0),
    "34-fuzz-registers": (r"вариантов|подмен", 0),
    "40-v3-offline": (r"^ВСЕГО|^взвешенно|ЭТАЛОННЫЙ ВЫЗОВ|настоящее значение|"
                      r"разные люди|один человек|^  clean|^  value_missing|^  unjudged", 0),
    "54-collisions": (r"OK|потолок", 0),
}


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    out = [f"# Замер {manifest['date']}", "",
           f"git `{manifest['git_head'][:12]}`"
           f"{' + незакоммиченные правки' if manifest['git_dirty'] else ''}"
           f" · python {manifest['python']}", ""]

    status = {r["step"]: r for r in manifest["steps"]}
    for step, record in status.items():
        if record["status"] == "SKIP":
            out += [f"## {step} — ПРОПУЩЕН", "",
                    f"нет данных: `{record['missing'][0]}`", ""]
            continue
        path = root / f"{step}.txt"
        if not path.exists():
            continue
        pattern = PATTERNS.get(step)
        mark = "" if record["status"] == "OK" else "  ⚠ ненулевой код возврата"
        out += [f"## {step}{mark}", "", f"_{record['why']}_  ·  {record['seconds']} с", ""]
        if pattern:
            lines = [line.rstrip() for line in
                     path.read_text(encoding="utf-8").splitlines()
                     if re.search(pattern[0], line)]
            out += ["```", *lines[:24], "```", ""]
        else:
            out += [f"полный вывод: `{step}.txt`", ""]

    (root / "SUMMARY.md").write_text("\n".join(out), encoding="utf-8")
    print(f"сводка -> {root / 'SUMMARY.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
