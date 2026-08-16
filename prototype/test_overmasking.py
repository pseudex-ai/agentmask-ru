"""Ordinary business and technical Russian, containing no personal data at all.

WHY THIS FILE EXISTS. The golden and dirty sets both reported 100% precision
while «Счёт 1234 от 15.05.2025» — one of the commonest sentences in Russian
business writing — was being masked. The sets were not wrong; they simply
contained no ordinary business text, so the failure was invisible to every
metric we had. Measured here for the first time, precision on this corpus was
69.2%: eight of twenty-six clean sentences were touched.

Recall protects the customer's data. THIS protects the customer's work: an
invoice number replaced by a fake one leaves the agent reasoning about a
document that does not exist, and «Счёт 1234 от 15.05.2025» rewritten into a
plate-shaped token is not even grammatical any more.

Every sentence below must come back untouched.

    python3 test_overmasking.py
"""

import sys

import testkit
from pseudex.detect_all import Detector

CLEAN: tuple[str, ...] = (
    # Document number followed by its date — the shape that was broken.
    "Счёт 1234 от 15.05.2025 оплачен полностью.",
    "Договор 8871 от 02.09.2024 продлён на год.",
    "Отгрузка по накладной 4471 от 14.03.2025 задержана.",
    "Платёж 9900 от 01.01.2025 не прошёл.",
    "Резервная копия от 15.05.2025 восстановлена.",
    "Акт 445 от 11.11.2023 подписан обеими сторонами.",
    # Deadlines and validity — dates with nobody attached.
    "Скидка 15% действует до 31.12.2025.",
    "Версия 1.2.3, сборка 4567, релиз 12.04.2025.",
    # Identifiers that belong to things, not people.
    "Заказ №A-4471 собран, вес 4517 г, трек 812345.",
    "Артикул 2024/117, партия 445, склад Б.",
    "Модель RTX 4090, серийный 1234567890123456.",
    "Рейс SU 1234 задержан на 40 минут.",
    "Инструкция ТУ 4573-001-12345678-2020.",
    "ГОСТ Р 50577-2018 описывает типы номерных знаков.",
    "Склад 12, стеллаж 4, ячейка 445.",
    # High-entropy values an agent must keep intact.
    "Коммит a94a8fe5ccb19ba61c4c0873d391e987982fbbd3 сломал тесты.",
    "Задача 550e8400-e29b-41d4-a716-446655440000 закрыта.",
    "Хеш 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08 совпал.",
    # Ordinary operations talk.
    "SELECT * FROM orders WHERE status = 'new'",
    "Ошибка 500 на эндпоинте /api/v1/orders.",
    "Контейнер перезапущен, аптайм 14 дней.",
    "Лимит 100000 запросов в месяц исчерпан.",
    "Ставка НДС 20%, сумма 12400 рублей.",
    "Отчёт за 2024 год готов, страниц 117.",
    "Позиция 7 в накладной не сходится по количеству.",
    "Тариф 990 рублей в месяц за один контейнер.",
    # A city as a place reference, not somebody's address.
    "Офис в Екатеринбурге работает до 18:00.",
)


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    touched: list[tuple[str, list[tuple[str, str]]]] = []

    for text in CLEAN:
        spans = [(s.entity_type, s.value) for s in detector.detect(text)]
        if spans:
            touched.append((text, spans))

    precision = (len(CLEAN) - len(touched)) / len(CLEAN) * 100
    print(f"чистых фраз:  {len(CLEAN)}")
    print(f"затронуто:    {len(touched)}")
    print(f"ТОЧНОСТЬ:     {precision:.1f}%   (было 69.2% до правок 16.08)")

    if touched:
        print("\n--- ЛОЖНЫЕ СРАБАТЫВАНИЯ ---")
        for text, spans in touched:
            print(f"  {text}")
            print(f"      -> {spans}")

    return 1 if touched else 0


if __name__ == "__main__":
    sys.exit(main())
