"""Credentials: found when stamped by a vendor, untouched when merely random.

The negatives matter more than the positives here. An entropy detector would
pass every positive in this file and also destroy every negative — git SHAs,
UUIDs, content hashes and base64 payloads are exactly what an agent needs intact.
That is the regression this suite exists to prevent.

    python3 test_credentials.py
"""

import sys

import testkit
from pseudex.detect_all import Detector
from pseudex.vault import Vault

# (text, must the span be found)
POSITIVE: tuple[tuple[str, str], ...] = (
    ("ключ sk-ant-api03-" + "aB3" * 30 + "xy", "Anthropic"),
    ("OPENAI_API_KEY=sk-proj-" + "Xy7" * 20, "OpenAI project"),
    ("возьми sk-or-v1-" + "a1b2c3d4" * 8 + " для роутера", "OpenRouter"),
    ("токен ghp_" + "A1b2C3d4" * 4 + "abcd", "GitHub"),
    ("export AWS_ACCESS_KEY_ID=AKIA4MZJK2QW7TVBH3RS", "AWS"),
    ("google AIzaSyD-1234567890abcdefghijklmnopqrstu", "Google API"),
    ("slack xoxb-123456789012-abcdefghijklmnopqrst", "Slack"),
    ("stripe sk_live_" + "4eC39H" * 5, "Stripe (секретный)"),
    ("hf_" + "aBcDeFgHiJ" * 3 + "abcd", "HuggingFace"),
    ("glpat-" + "aZ3xK9mQ2wLp7nR4tY6u"[:20], "GitLab"),
    ("npm_" + "abcdefgh" * 4 + "abcd", "npm"),
    ("бот 123456789:AA" + "Fx9k2mQ" * 4 + "abcde", "Telegram"),
    ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk", "JWT"),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAx7Zk\nQmNvZGVoZXJl\n-----END RSA PRIVATE KEY-----", "PEM"),
    ("y0_AgAAAABxyz1234567890abcdefghij", "Яндекс OAuth"),
)

# These must survive UNTOUCHED. Every one is high-entropy; an entropy-based
# detector masks them all and breaks the agent that needed them.
NEGATIVE: tuple[tuple[str, str], ...] = (
    ("коммит a94a8fe5ccb19ba61c4c0873d391e987982fbbd3 сломал сборку", "git SHA"),
    ("id 550e8400-e29b-41d4-a716-446655440000", "UUID"),
    ("хеш файла 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "SHA-256"),
    ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk", "base64 картинка"),
    ("заказ A-4471 от 14.03.2025", "номер заказа"),
    ("ветка feature/sk-integration готова", "ветка со sk-"),
    ("skip this line", "слово, начинающееся на sk"),
    ("пакет AIzaSy — так назывался проект", "короткий обрывок"),
    ("Иванов Пётр, +7 916 214-88-03", "обычные ПД, не секрет"),
    ("SELECT * FROM users WHERE token IS NULL", "SQL"),
    # Vendor-published examples and templates. Both are shaped like credentials
    # and neither is one: AWS prints AKIAIOSFODNN7EXAMPLE in its own docs, and
    # Stripe documents pk_ as safe for client-side code.
    ("export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE", "пример из доки AWS"),
    ("публичный ключ pk_live_51H8xKfL2eZvKYlo2C0abcdef", "публикуемый Stripe"),
    ("в конфиге sk-ant-api03-${ANTHROPIC_API_KEY}", "шаблон переменной"),
    ("пример ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "заглушка из xxxx"),
)


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    vault = Vault(":memory:", "acme")
    failures = 0

    print("НАХОДИМ (должен быть SECRET)")
    for text, label in POSITIVE:
        types = {s.entity_type for s in detector.detect(text)}
        ok = "SECRET" in types
        failures += 0 if ok else 1
        print(f"  {'OK ' if ok else 'FAIL'} {label:16} {sorted(types) or 'ничего'}")

    print("\nНЕ ТРОГАЕМ (SECRET быть НЕ должно)")
    for text, label in NEGATIVE:
        types = {s.entity_type for s in detector.detect(text)}
        ok = "SECRET" not in types
        failures += 0 if ok else 1
        print(f"  {'OK ' if ok else 'FAIL'} {label:22} {sorted(types) or 'чисто'}")

    print("\nКРУГ: подмена и восстановление")
    real = "sk-ant-api03-" + "aB3" * 30 + "xy"
    token = vault.tokenize(real, "SECRET")
    back = vault.detokenize(token)
    checks = (
        ("токен не равен оригиналу", token != real),
        ("префикс сохранён", token.startswith("sk-ant-api03-")),
        ("длина сохранена", len(token) == len(real)),
        ("восстановление точное", back == real),
    )
    for label, ok in checks:
        failures += 0 if ok else 1
        print(f"  {'OK ' if ok else 'FAIL'} {label}")
    print(f"       оригинал: {real[:34]}…")
    print(f"       модель:   {token[:34]}…")

    print(f"\n{'ВСЁ ЧИСТО' if not failures else f'ПРОВАЛОВ: {failures}'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
