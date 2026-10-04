"""В — REDACTED-маркер как подмена: `_render_token` не имеет права выпускать
случайный hex.

Симптом: `{"cardholder": "Котов"}` → `structured.detect_structured_kv` типизирует
лист по ключу (`cardholder` префиксно совпадает с `card` → CARD), значение без
цифр понижается до OPAQUE, у OPAQUE нет рендерера, и `_render_token` выдавал
`REDACTED<secrets.token_hex(3)>` — СЛУЧАЙНЫЙ маркер, который (а) не идемпотентен
даже сам с собой, (б) сам становится «значением» под числовым ключом. Правило:
неизобразимый тип получает ДЕТЕРМИНИРОВАННУЮ нейтральную форму (digest от
значения), а не случайный hex.

Self-contained: без LLM и сети, грузит bundle из исходников, гоняет НАСТОЯЩИЙ
`redact.mask_text`.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_v_redacted_deterministic.py
"""

import sys
import tempfile

import testkit

testkit.load_dev_bundle()

from pseudex import redact                                     # noqa: E402
from pseudex.detect_all import Detector                        # noqa: E402
from pseudex.vault import REDACTION_MARKER, Vault, _render_token  # noqa: E402

DET = Detector()
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def main() -> int:
    # ДЕТЕРМИНИРОВАННОСТЬ: одно значение → один маркер, всегда.
    a = _render_token("OPAQUE", original="Котов")
    b = _render_token("OPAQUE", original="Котов")
    c = _render_token("OPAQUE", original="Юдин")
    check(a == b, "В один и тот же OPAQUE → один и тот же маркер", f"{a!r}")
    check(a != c, "В разное значение → разный маркер (но оба детерминированы)",
          f"{a!r} vs {c!r}")
    check(bool(REDACTION_MARKER.fullmatch(a)),
          "В маркер узнаётся как редакция (fixed point)", f"{a!r}")

    # ПРОДАКШЕН-ПУТЬ: cardholder маскируется ДВАЖДЫ в один и тот же вывод.
    with tempfile.TemporaryDirectory() as td:
        vault = Vault(f"{td}/v.db", "v1").for_conversation("conv")
        payload = '{"cardholder": "Котов"}'
        first = redact.mask_text(payload, vault, DET.detect(payload))
        second = redact.mask_text(payload, vault, DET.detect(payload))
        check(first == second, "В cardholder маскируется идемпотентно",
              f"{first!r} vs {second!r}")
        check("Котов" not in first, "В настоящее значение не ушло в модель", first)
        check(REDACTION_MARKER.search(first) is not None,
              "В вывод — детерминированный маркер, не фальшивая карта", first)

    failed = [name for ok, name, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} проверок зелёные")
    for name in failed:
        print(f"  RED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
