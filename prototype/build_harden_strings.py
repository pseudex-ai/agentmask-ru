"""Спрятать строки-маяки лицензионного тракта из скомпилированного образа.

ЗАЧЕМ. Замерено на собранном бинарнике: Nuitka кладёт строковые литералы в
constants-блоб ОТКРЫТЫМ ТЕКСТОМ, и блоб переживает `strip` (это данные, а не
таблица символов ELF). `grep license_expired pseudex-serve` находит строку, а
рядом с ней — ветку лестницы деградации. Это первый ход любителя с LLM: строка
как карта до места, которое надо пропатчить.

ЧТО ДЕЛАЕТ. Каждый ЗАРАНЕЕ НАЗВАННЫЙ строковый литерал заменяется на выражение,
дающее ТО ЖЕ значение в рантайме (`bytes.fromhex(...).decode()`), но не
содержащее исходной строки. Контракт на проводе, сравнения и ключи словарей не
меняются — значение идентично. Меняется только то, что `grep` по говорящему
слову больше ничего не находит.

ЧЕГО НЕ ДЕЛАЕТ, СКАЗАНО ПРЯМО. Это security-by-obscurity против ЛЮБИТЕЛЯ, а не
против профи: тот запустит декодер и получит строку. Планка поднимается с
«grep за вечер» до «читать поток управления», не превращаясь в невозможность —
для on-prem-with-root её и не бывает (research 2026-09-01, docs/tz-license-
packaging.md §3.4). Энтропию не поднимает (не триггерит EDR клиента) и номера
строк сохраняет (трейсбеки поддержки живут) — тем и отличается от упаковщиков,
которые здесь отвергнуты.

ПРИМЕНЯЕТСЯ ТОЛЬКО К СТРОКАМ ИЗ СПИСКА. Слепая обфускация всех строк ловила бы
имена переменных окружения, ключи, форматные шаблоны — список делает трансформ
предсказуемым и проверяемым.

usage: python3 build_harden_strings.py <dir-or-file> [more...]
"""

import ast
import sys
from pathlib import Path

# СТРОКИ-МАЯКИ ДВИЖКА. Только те, что видны в бинарнике и ведут к лицензионной
# ветке: коды ответа, операторский текст REMEDIES, сообщения лестницы. НЕ
# трогаем имена переменных окружения и форматные шаблоны — они либо нужны
# читаемыми, либо f-строки (их пасс и так пропускает).
_SENSITIVE: frozenset[str] = frozenset({
    "license_missing", "license_invalid", "license_expired", "license_revoked",
    "bundle_unavailable", "bundle_corrupt", "capacity_exhausted",
    "instance_limit", "release_budget",
    "no valid detection lease", "no detection lease was ever obtained",
    "detection assets unloaded — /mask now returns 503",
})


def _encoded(value: str) -> str:
    """Выражение, дающее `value` в рантайме, но не несущее его текстом.

    `bytes.fromhex(...).decode()` — вызов, а не константная операция, поэтому
    Nuitka не сворачивает его обратно в литерал (проверяется грепом собранного
    образа в гейте). Однострочно: не двигает номера строк."""
    return f'bytes.fromhex("{value.encode("utf-8").hex()}").decode()'


class _Marker(ast.NodeVisitor):
    """Собирает точные позиции строковых литералов из списка."""

    def __init__(self) -> None:
        self.hits: list[tuple[int, int, int, int, str]] = []

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and node.value in _SENSITIVE:
            # end_lineno == lineno: многострочные не трогаем, чтобы не двигать
            # нумерацию; наши маяки все однострочные.
            if node.lineno == node.end_lineno:
                self.hits.append((node.lineno, node.col_offset,
                                  node.end_lineno, node.end_col_offset,
                                  node.value))
        self.generic_visit(node)


def harden(path: Path) -> int:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    marker = _Marker()
    marker.visit(tree)
    if not marker.hits:
        return 0
    # Плоские смещения по всему файлу: line-join терял один \n на граничных
    # строках. Смещение = позиция начала строки + столбец. Заменяем СПРАВА
    # НАЛЕВО, чтобы более ранние смещения не съезжали. Всё в пределах одной
    # строки, поэтому номера строк не двигаются.
    # В БАЙТАХ, А НЕ В СИМВОЛАХ. `ast` отдаёт `col_offset` в UTF-8 БАЙТАХ, и на
    # строке с многобайтовым символом (em-dash «—» — 3 байта) индексирование по
    # символам съезжало и съедало соседний перевод строки. `_encoded` выдаёт
    # только ASCII, поэтому работа в байтах безопасна.
    raw = source.encode("utf-8")
    starts = [0]
    for i, byte in enumerate(raw):
        if byte == 0x0A:
            starts.append(i + 1)
    spans = []
    for lineno, col, _end_line, end_col, value in marker.hits:
        spans.append((starts[lineno - 1] + col, starts[lineno - 1] + end_col, value))
    for begin, finish, value in sorted(spans, reverse=True):
        raw = raw[:begin] + _encoded(value).encode("ascii") + raw[finish:]
    path.write_bytes(raw)
    return len(marker.hits)


def main() -> int:
    targets = [Path(arg) for arg in sys.argv[1:]]
    files: list[Path] = []
    for target in targets:
        files.extend([target] if target.is_file() else target.rglob("*.py"))
    total = 0
    for path in files:
        if path.name in ("build_harden_strings.py", "build_strip_docstrings.py"):
            continue
        n = harden(path)
        if n:
            print(f"  hardened {n} strings in {path}")
            total += n
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
