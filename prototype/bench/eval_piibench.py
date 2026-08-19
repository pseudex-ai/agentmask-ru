"""PII-Bench (hivetrace, Apache-2.0) — чужой русский корпус в ЧАТОВОМ регистре.

ЗАЧЕМ ЕЩЁ ОДИН ВНЕШНИЙ ПРИБОР. Внешних измерений у нас три, и все они
новостные: NEREL — Wikinews, и оба замера по нему меряют текст, который
customer support не пишет. AgentPII-RU написан здесь, то есть меряет нас нашим
же представлением о клиенте. PII-Bench закрывает ровно тот зазор: 1810
примеров неформального русского со сленгом и обсценной лексикой, размеченных
СИМВОЛЬНЫМИ СПАНАМИ именно персональных данных, с типами, которые почти
совпадают с нашими, — и написан он не нами.

ДВА ЧИСЛА, А НЕ ОДНО, И ЭТО НЕ УКЛОНЕНИЕ ОТ ОТВЕТА.

Корпус размечает КПП и ОГРН как персональные данные. Они таковыми не являются:
это идентификаторы ЮРИДИЧЕСКОГО лица, а GDPR Recital 14 прямо выводит данные
юрлиц из-под регламента «включая название, форму и контактные данные», и 152-ФЗ
приходит туда же через определение субъекта как физического лица. Маскировать
ОГРН — значит ломать клиенту его собственный документооборот ради того, что
законом не защищено.

ОГРНИП — другое дело: индивидуальный предприниматель это физлицо, и его
регистрационный номер к нему и относится.

Поэтому печатаются обе колонки. СТРОГО — как размечено в корпусе, чтобы число
было сравнимо с чужими публикациями по нему. ПО ЗАКОНУ — без идентификаторов
юрлица, потому что это и есть наша позиция, и продукт, маскирующий ОГРН, был бы
неправ независимо от того, что показывает метрика.

ДВЕ ОСИ, КАК ВЕЗДЕ. Полнота — спан пересёкся. Покрытие — спан найден ЦЕЛИКОМ.
Разница между ними это утёкший хвост: «Кзнецов Дмитрий», опознанный как
«Дмитрий», считается полнотой, пока фамилия уходит в модель открытым текстом.

    python3 bench/eval_piibench.py ~/.cache/pseudex-bench/pii-bench
"""

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyarrow.parquet as pq  # noqa: E402

from pseudex.detect_all import Detector  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

# Их тип -> наш. ADDRESS ложится на LOC, TOKEN на SECRET.
_MAP: dict[str, tuple[str, ...]] = {
    "NAME": ("NAME",),
    "PHONE_NUMBER": ("PHONE",),
    "EMAIL": ("EMAIL",),
    "ADDRESS": ("LOC", "ADDR"),
    "BANK_CARD_NUMBER": ("CARD",),
    "INN": ("INN",),
    "SNILS": ("SNILS",),
    "PASSPORT_NUMBER": ("PASSPORT",),
    "TOKEN": ("SECRET",),
    # CVC отдельного типа у нас нет. Три цифры без контекста неотличимы от
    # любого другого трёхзначного числа, поэтому ловится он только рядом с
    # картой — засчитываем любое перекрытие, но НЕ требуем своего типа.
    "CVC": (),
    "KPP": (),
    "OGRN": (),
    "OGRNIP": ("INN", "OGRN"),
}

# ТИПЫ, ГДЕ КОРПУС ВРЁТ, И ПРИБОР ОБЯЗАН ЭТО ГОВОРИТЬ.
#
# Корпус синтетический, и его генератор выдумывал номера по ФОРМЕ, не считая
# контрольную сумму: из 92 карт Луна проходят ЧЕТЫРЕ. Мы находим ровно эти
# четыре — то есть 4.3% здесь означает «детектор прав на 100% валидных и верно
# отверг 88 невалидных», а выглядит как провал. Число без этой строки — ложное
# обвинение собственному коду, и первый, кто его прочтёт, начнёт чинить
# работающее.
#
# TOKEN — не ошибка корпуса, а РАЗНОГЛАСИЕ по определению. Их TOKEN это любая
# строка высокой энтропии; наши учётные данные привязаны к опубликованным
# префиксам, а не к энтропии, потому что git SHA, UUID, хеш и base64-картинка
# тоже высокоэнтропийны и ни один из них не секрет. Низкое число здесь —
# записанное решение, а не недоделка.
_CORPUS_DEFECT = {
    "BANK_CARD_NUMBER": "88 из 92 номеров не проходят Луна — выдуманы генератором",
    "TOKEN": "их TOKEN = энтропия; наш SECRET = опубликованный префикс (по решению)",
    "CVC": "своего типа нет: три цифры без карты рядом неотличимы от любого числа",
}

# Идентификаторы ЮРЛИЦА. Не персональные данные ни по Recital 14, ни по 152-ФЗ —
# см. докстринг. ОГРНИП сюда НЕ входит: ИП это физлицо.
_LEGAL_PERSON = frozenset({"KPP", "OGRN"})


def load(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in ("domain", "entity"):
        path = root / "data" / f"{name}-00000-of-00001.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"нет {path}. Файлы под git-lfs; если `git lfs` не стоит, качать так:\n"
                f"  curl -L -o {path} https://huggingface.co/datasets/"
                f"hivetrace/pii-bench/resolve/main/data/{name}-00000-of-00001.parquet")
        rows.extend(pq.read_table(path).to_pylist())
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?",
                        default=str(Path.home() / ".cache/pseudex-bench/pii-bench"))
    parser.add_argument("--dump", type=int, default=15)
    args = parser.parse_args()

    load_dev_bundle()
    detector = Detector()
    rows = load(Path(args.root))

    hit: collections.Counter[str] = collections.Counter()
    whole: collections.Counter[str] = collections.Counter()
    typed: collections.Counter[str] = collections.Counter()
    total: collections.Counter[str] = collections.Counter()
    by_domain_hit: collections.Counter[str] = collections.Counter()
    by_domain_total: collections.Counter[str] = collections.Counter()
    misses: list[tuple[str, str, str]] = []
    partials: list[tuple[str, str, int]] = []

    for row in rows:
        text = str(row["text"])
        found = [(span.start, span.end, span.entity_type) for span in detector.detect(text)]
        for entity in row["entities"] or []:
            kind = str(entity["type"])
            start, end = int(entity["start"]), int(entity["end"])
            total[kind] += 1
            by_domain_total[str(row["domain"])] += 1
            overlap = [f for f in found if f[0] < end and start < f[1]]
            if overlap:
                hit[kind] += 1
                by_domain_hit[str(row["domain"])] += 1
                # ПОКРЫТИЕ: каждый символ эталона накрыт хоть одним спаном.
                # Складывать длины нельзя — два спана могут перекрываться, и
                # сумма тогда объявит покрытым то, что покрыто наполовину.
                covered = set()
                for f_start, f_end, _ in overlap:
                    covered |= set(range(max(start, f_start), min(end, f_end)))
                if len(covered) == end - start:
                    whole[kind] += 1
                elif len(partials) < args.dump:
                    partials.append((kind, text[start:end], end - start - len(covered)))
                if any(f[2] in _MAP.get(kind, ()) for f in overlap) or not _MAP.get(kind):
                    typed[kind] += 1
            elif len(misses) < args.dump:
                misses.append((kind, text[start:end], text[:70]))

    print(f"примеров: {len(rows)}   значений: {sum(total.values())}\n")
    print(f"{'ТИП':<20}{'ЭТАЛОН':>8}{'ПОЛНОТА':>10}{'ПОКРЫТИЕ':>11}{'СВОЙ ТИП':>11}")
    print("-" * 60)
    for kind in sorted(total):
        mark = "  (юрлицо)" if kind in _LEGAL_PERSON else ""
        if kind in _CORPUS_DEFECT:
            mark = "  !"
        print(f"{kind:<20}{total[kind]:>8}{hit[kind] / total[kind] * 100:>9.1f}%"
              f"{whole[kind] / total[kind] * 100:>10.1f}%"
              f"{typed[kind] / total[kind] * 100:>10.1f}%{mark}")

    def summary(label: str, kinds: list[str]) -> None:
        got = sum(hit[k] for k in kinds)
        cov = sum(whole[k] for k in kinds)
        num = sum(total[k] for k in kinds)
        print(f"{label:<20}{num:>8}{got / num * 100:>9.1f}%{cov / num * 100:>10.1f}%")

    print("-" * 60)
    summary("ВСЕГО (строго)", sorted(total))
    summary("ВСЕГО (по закону)", [k for k in sorted(total) if k not in _LEGAL_PERSON])
    print("           «по закону» = без КПП/ОГРН: идентификаторы юрлица не ПД")
    print("\n--- ! ЧИТАТЬ ПЕРЕД ТЕМ, КАК ЧИНИТЬ ---")
    for kind, why in _CORPUS_DEFECT.items():
        print(f"  {kind:<20}{why}")

    print(f"\n{'СЦЕНАРИЙ':<20}{'ЭТАЛОН':>8}{'ПОЛНОТА':>10}")
    for domain in sorted(by_domain_total):
        print(f"{domain:<20}{by_domain_total[domain]:>8}"
              f"{by_domain_hit[domain] / by_domain_total[domain] * 100:>9.1f}%")

    if misses:
        print("\n--- НЕ НАЙДЕНО (утечка) ---")
        for kind, value, context in misses:
            print(f"  [{kind}] {value!r}   … {context!r}")
    if partials:
        print("\n--- НАЙДЕНО ЧАСТИЧНО (хвост утёк) ---")
        for kind, value, left in partials:
            print(f"  [{kind}] {value!r}   не покрыто символов: {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
