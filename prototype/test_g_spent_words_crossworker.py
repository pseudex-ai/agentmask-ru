"""Г — `_spent_real_words` многоваркерный снимок: два Vault на одной БД видят
имена друг друга.

`_spent_real_words` кэшировал ведра основ настоящих значений на ПРОЦЕСС (экземпляр
Vault), а файл волта общий на N воркеров. Вставка строки NAME другим процессом
кэш не сбрасывала, поэтому второй воркер мог отчеканить подмену, несущую целое
слово настоящего значения, которое первый воркер записал в ту же БД. Правило:
кэш сверяется с БД точечным запросом (`MAX(rowid)`), как `_shares_a_stem_in_conversation`
уже спрашивает индекс точечно, а не верит снимку.

Self-contained: без LLM и сети, грузит bundle из исходников, гоняет НАСТОЯЩИЙ
`Vault` на двух экземплярах над одним файлом.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_g_spent_words_crossworker.py
"""

import sys
import tempfile

import testkit

testkit.load_dev_bundle()

from pseudex.vault import Vault                                   # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        db = f"{td}/v.db"
        w1 = Vault(db, "cust").for_conversation("conv")
        w2 = Vault(db, "cust").for_conversation("conv")

        # w2 СНАЧАЛА кэширует свои (пустые) ведра — до того, как w1 что-то чеканит.
        check(w2._spent_real_words() == {}, "Г w2 кэш изначально пуст", "")

        # w1 отчеканивает имя (вставка строки NAME в общую БД).
        real = "Лебедева Екатерина Петровна"
        fake = w1.tokenize(real, "NAME")
        check("лебедев" not in fake.casefold(), "Г w1 подмена не несёт своей фамилии", fake)

        # w2 со СВОИМ протухшим кэшем обязан увидеть слово, отчеканенное w1.
        check(w2._shares_a_spent_word("Лебедев Иван"),
              "Г w2 видит имя, отчеканенное w1 (инвалидация по внешней вставке)",
              f"w2 spent={sorted(w2._spent_real_words())}")
        check(w2._is_free_token("Лебедев Иван", "NAME", "", "") is False,
              "Г сторож w2 отвергает подмену с чужим настоящим словом", "")

        # И ОБРАТНОЕ НАПРАВЛЕНИЕ: w1 тоже видит то, что w2 отчеканит позже.
        w2.tokenize("Мещеряков Валерий Ярославович", "NAME")
        check(w1._shares_a_spent_word("Мещеряков Пётр"),
              "Г w1 видит имя, отчеканенное w2", f"w1 spent={sorted(w1._spent_real_words())}")

    failed = [name for ok, name, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} проверок зелёные")
    for name in failed:
        print(f"  RED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
