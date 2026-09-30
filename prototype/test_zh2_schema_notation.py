"""Ж.2 — тул-схема как живой маркер нотации на OUT-плече.

Владелец (`DECISIONS-SPRINT.md` §Класс Ж): тул-схема из запроса — авторитетный
маркер; «схема говорит SNILS: XXX-XXX-XXX YY — рендерим в этой нотации», и
ничего сверх схемы не угадываем. Раньше `notation.render_like(target=...)` не
передавал ни один вызов: настоящий СНИЛС восстанавливался в форме агента
(разделители агента), а не в форме, которую объявляет схема листа. Теперь
`unmask_arguments` принимает `leaf_notation` (ключ листа → нотация), а
`unmask_text` — `target`; «snils» форсирует «XXX-XXX-XXX YY», пустая строка —
«не объявлено, не угадываем».

Self-contained: без LLM и сети, грузит bundle из исходников, гоняет НАСТОЯЩИЙ
`Vault`/`redact.unmask_arguments`.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_zh2_schema_notation.py
"""

import json
import sys
import tempfile

import testkit

testkit.load_dev_bundle()

from pseudex import redact                                     # noqa: E402
from pseudex.vault import Vault                                # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        vault = Vault(f"{td}/v.db", "zh2").for_conversation("conv")
        real = "760-451-105 71"
        fake = vault.tokenize(real, "SNILS")
        print(f"        настоящий {real!r} -> подмена {fake!r}")

        # Агент переписал подмену без дефисов (его форма), а схема листа требует
        # «XXX-XXX-XXX YY». С объявленной нотацией восстанавливаем в нотации
        # схемы; без объявления — в форме агента, ничего не угадывая.
        reformatted = fake.replace("-", "").replace(" ", "")
        args = json.dumps({"snils": reformatted})

        with_target = json.loads(redact.unmask_arguments(
            args, vault, leaf_notation={"snils": "snils"}))["snils"]
        check(with_target == "760-451-105 71",
              "Ж.2 схема «snils» рендерит СНИЛС в XXX-XXX-XXX YY",
              repr(with_target))

        without_target = json.loads(redact.unmask_arguments(args, vault))["snils"]
        check(without_target == "76045110571",
              "Ж.2 без объявления нотацию держит агент (дефисов не угадываем)",
              repr(without_target))

        # ДРУГОЙ ЛИСТ ТОГО ЖЕ ВЫЗОВА без объявления не трогается: нотация
        # применяется по ключу листа, а не всему вызову.
        args2 = json.dumps({"snils": reformatted, "note": reformatted})
        out2 = json.loads(redact.unmask_arguments(
            args2, vault, leaf_notation={"snils": "snils"}))
        check(out2["snils"] == "760-451-105 71" and out2["note"] == "76045110571",
              "Ж.2 нотация применяется по ключу листа, а не всему вызову",
              repr(out2))

        # ПРЯМОЙ ШОВ: `render_like(target=...)` — то же решение, что и в аргументе.
        from pseudex import notation
        rendered = notation.render_like(real, reformatted, "SNILS", for_tool=True,
                                        target="snils")
        check(rendered == "760-451-105 71",
              "Ж.2 render_like(target='snils') -> XXX-XXX-XXX YY", repr(rendered))
        rendered_no = notation.render_like(real, reformatted, "SNILS", for_tool=True)
        check(rendered_no == "76045110571",
              "Ж.2 render_like без target не угадывает форму", repr(rendered_no))

    failed = [name for ok, name, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} проверок зелёные")
    for name in failed:
        print(f"  RED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
