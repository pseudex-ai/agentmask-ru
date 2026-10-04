"""Б — литера дома без пунктуации: «34 в кв 9» — дом 34в, квартира 9, а не
«34» и предлог «в».

Свидетель g06 P4 / search_rank-008: `address_key("толстого 34 в")` и
`address_key("толстого 34")` сливались в один ключ, потому что список предлогов
съедал «в» (и «с», «к», «о» — ровно те буквы, которыми пишут литеру). Первое
лечение склеивало литеру только В КОНЦЕ строки или перед пунктуацией
(`_SPACED_LITERA_RE`); перед маркером («34 в кв 9») литера по-прежнему падала в
предлоги. Правило владельца: литера после числа (одна буква после пробела, не
предлог) склеивается ДО выкидывания предлогов, в ЛЮБОЙ позиции.

Self-contained: без LLM и сети, грузит bundle из исходников, гоняет НАСТОЯЩИЙ
`morph_places.address_key`.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_b_litera_composition.py
"""

import sys

import testkit

testkit.load_dev_bundle()

from pseudex.morph_places import address_key, street_house_key       # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def main() -> int:
    # ДВА РАЗНЫХ ДОМА: «34 в кв 9» (дом 34в) ≠ «34 кв 9» (дом 34).
    a, b = address_key("толстого 34 в кв 9"), address_key("толстого 34 кв 9")
    check(a != b, "Б литера перед маркером: «34 в кв 9» ≠ «34 кв 9»", f"{a!r} vs {b!r}")

    # ЛИТЕРА СКЛЕИВАЕТСЯ ОДИНАКОВО ВО ВСЕХ ТРЁХ ЗАПИСЯХ.
    glued = address_key("толстого 34в")
    spaced_end = address_key("толстого 34 в")
    spaced_marker = address_key("толстого 34 в кв 9")
    check(glued == spaced_end, "Б литера: «34в» == «34 в»", f"{glued!r} vs {spaced_end!r}")
    check(spaced_marker.startswith(glued + " "),
          "Б литера: «34 в кв 9» несёт ту же литеру «34в»", f"{spaced_marker!r} / {glued!r}")

    # ЛИТЕРА ПЕРЕД ДРУГИМИ МАРКЕРАМИ И С ТОЧКОЙ.
    check(address_key("толстого 34 в корп 2") != address_key("толстого 34 корп 2"),
          "Б литера перед «корп» тоже склеивается",
          f"{address_key('толстого 34 в корп 2')!r}")
    check(address_key("толстого 34 в кв. 9") == address_key("толстого 34 в кв 9"),
          "Б точка после маркера не мешает склейке",
          f"{address_key('толстого 34 в кв. 9')!r}")

    # СТРОЕНИЕ/КОРПУС — НЕ ЛИТЕРА: «65 с 2» остаётся «строение 2», а не «65с».
    check(address_key("толстого 65 с 2").endswith("65 стр 2"),
          "Б контроль: «с» между числами — строение, а не литера",
          f"{address_key('толстого 65 с 2')!r}")

    # СВЯЗЫВАЮЩИЙ КЛЮЧ ОСТАЁТСЯ ТЕРПИМЫМ: короткое «34 в» по-прежнему находит
    # «34» — литера срезается только в тождестве, не в связывании.
    check(street_house_key("толстого 34 в") == street_house_key("толстого 34"),
          "Б linking: tolerant-ключ по-прежнему связывает «34 в» с «34»",
          f"{street_house_key('толстого 34 в')!r}")

    failed = [name for ok, name, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} проверок зелёные")
    for name in failed:
        print(f"  RED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
