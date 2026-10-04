"""Г-4 — обратный порядок: подмена, выданная раньше, узнаётся по ЧАСТЯМ, а
настоящий человек, появившийся позже, маскируется.

Подмена A («Смирнова» → «Титова Вера Константиновна») несёт фамилию, которая
позже оказывается настоящей фамилией B («Титова»). Инвариант владельца
(`DECISIONS-SPRINT.md` §Класс Г): подмена не имеет права нести целое слово =
настоящее значение ДРУГОГО лица в том же разговоре. Две половины:
  * чеканка (`_spent_real_words`) — новая подмена не несёт слова уже известного
    настоящего значения (вектор 4 SPIKE-Г);
  * части (`name_rendering_is_ours`, вопрос `is_own_substitute`) — одиночная
    фамилия подмены узнаётся как своя (иначе перечеканится во вторую личность),
    а ПОЛНОЕ настоящее имя B, пришедшее позже, частью подмены A не является и
    маскируется.

Self-contained: без LLM и сети, грузит bundle из исходников, гоняет НАСТОЯЩИЙ
`Vault`/`Detector`/`redact.is_own_substitute`.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_g4_reverse_order.py
"""

import sys
import tempfile

import testkit

testkit.load_dev_bundle()

from pseudex import redact                                     # noqa: E402
from pseudex.detect_all import Detector                        # noqa: E402
from pseudex.vault import Vault                                # noqa: E402

DET = Detector()
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _name_span(text: str):
    spans = [s for s in DET.detect(text) if s.entity_type == "NAME"]
    return spans[0] if spans else None


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        vault = Vault(f"{td}/v.db", "g4").for_conversation("conv")

        # A чеканится РАНЬШЕ.
        subA = vault.tokenize("Смирнова Анна Ивановна", "NAME")
        surnameA = subA.split()[0]
        print(f"        A подмена: {subA!r}, фамилия подмены: {surnameA!r}")

        # ЧАСТЬ ПОДМЕНЫ — СВОЯ: вопрос задаёт `is_own_substitute` через
        # `name_rendering_is_ours` (один владелец, слот фамилии), а не только
        # точная строка `is_minted_token`.
        lone = _name_span(surnameA)
        check(lone is not None and redact.is_own_substitute(lone, vault),
              "Г-4 одиночная фамилия подмены узнаётся как своя (часть, не целое)",
              f"is_own_substitute({surnameA!r})={redact.is_own_substitute(lone, vault)}")
        pair = _name_span(f"{subA.split()[0]} {subA.split()[1]}")
        check(pair is not None and redact.is_own_substitute(pair, vault),
              "Г-4 часть «фамилия имя» узнаётся как своя",
              f"{subA.split()[0]} {subA.split()[1]}")

        # B — НАСТОЯЩИЙ человек с той же фамилией, появившийся ПОЗЖЕ. ПОЛНОЕ имя
        # — не часть подмены A (слова не все её) и обязано маскироваться.
        realB = f"{surnameA} Пётр Сергеевич"
        full = _name_span(realB)
        check(full is not None and not redact.is_own_substitute(full, vault),
              "Г-4 полное настоящее имя B не пропускается как «наша» подмена",
              f"{realB!r} -> is_own_substitute={redact.is_own_substitute(full, vault)}")

        # ЧЕКАНКА B: новая подмена не несёт НАСТОЯЩЕЙ фамилии B (строгий сторож
        # `_shares_a_word`), иначе подмена B несла бы слово настоящего значения
        # (та же инъективность, что у A).
        subB = vault.tokenize(realB, "NAME")
        check(subB.split()[0].casefold() != surnameA.casefold(),
              "Г-4 подмена B не несёт настоящей фамилии B", f"{subB!r}")

    failed = [name for ok, name, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} проверок зелёные")
    for name in failed:
        print(f"  RED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
