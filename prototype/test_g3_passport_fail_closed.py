"""Г-3 — passport.* fail-closed: родительский ключ типизирует детей, и лист,
который не читается как часть, закрывается ЦЕЛОЙ подменой, а не остаётся
открытым.

Свидетель: g09 `document-027…-048` — 24 утечки, клетка `form:OUT/tool_arg
PASSPORT 0/22`. `{"passport": {"series": "4608"}}` (только серия, без номера)
уходил модели в открытую: 4 цифры без контрольной суммы не берёт ни один
shape-рекогнайзер, `_JSON_KV` не видит родительский ключ, а `_composite_leaves`
возвращал {} при отсутствии обязательной роли — и лист падал сквозь.

Self-contained: без LLM и сети, грузит bundle из исходников и гоняет НАСТОЯЩИЙ
`detect_structured_kv`/`redact.mask_text`.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_g3_passport_fail_closed.py
"""

import json
import sys
import tempfile

import testkit

testkit.load_dev_bundle()

from pseudex import redact                                     # noqa: E402
from pseudex.detect_all import Detector                        # noqa: E402
from pseudex.structured import detect_structured_kv            # noqa: E402
from pseudex.vault import Vault                                # noqa: E402

DET = Detector()
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _kv(text: str) -> list[tuple[int, int, str, str]]:
    return [(s.start, s.end, s.entity_type, s.value) for s in detect_structured_kv(text)]


def _covered_leaf(payload: str, leaf: str) -> bool:
    """Is this literal leaf closed by SOME span in the payload?"""
    return any(payload[s.start:s.end] == leaf for s in DET.detect(payload))


def main() -> int:
    # НЕПОЛНАЯ ЧАСТЬ: серия без номера, номер без серии — лист обязан закрыться
    # ЦЕЛОЙ подменой PASSPORT, а не уйти в открытую.
    partials = (
        '{"passport": {"series": "4608"}}',
        '{"passport": {"number": "246256"}}',
        '{"passport": {"series": "4608", "issued": "2015"}}',
    )
    for payload in partials:
        kv = _kv(payload)
        leaks = [v for v in ("4608", "246256", "2015") if v in payload
                 and not any(k[3] == v for k in kv)]
        check(not leaks, f"3a частичный лист закрыт: {payload!r}",
              f"открыты: {leaks}; kv={kv}")

    # ОПЕЧАТКА РОЛИ: seria/nomer не в карте ролей — лист всё равно закрыт целым.
    typos = (
        '{"passport": {"seria": "4608", "nomer": "246256"}}',
        '{"паспорт": {"серия": "4608"}}',
        '{"паспорт": {"серия": "4608", "номер": "246256"}}',
    )
    for payload in typos:
        leaks = [v for v in ("4608", "246256") if v in payload
                 and not any(k[3] == v for k in _kv(payload))]
        check(not leaks, f"3b опечатка/частичный русский лист закрыт: {payload!r}",
              f"открыты: {leaks}; kv={_kv(payload)}")

    # РЕГРЕССИЯ: полный passport.{series,number} — по-прежнему ДВЕ части ОДНОГО
    # документа, а не два целых.
    full = ('{"last_name": "громова", "passport": {"series": "4608", "number": "246256"}, '
            '"address": {"city": "уфа", "street": "сиреневая", "house": "72", "flat": "33"}}')
    kv = _kv(full)
    passport = [k for k in kv if k[2] == "PASSPORT"]
    whole_spans = [s for s in detect_structured_kv(full) if s.entity_type == "PASSPORT"]
    wholes = {getattr(s, "whole", "") for s in whole_spans}
    check(len(passport) == 2 and len(wholes) == 1 and all(w for w in wholes),
          "3c полный passport — две части ОДНОГО документа", str(kv))
    address_leaves = ("уфа", "сиреневая", "72", "33")
    open_address = [leaf for leaf in address_leaves if not _covered_leaf(full, leaf)]
    check(not open_address, "3d контроль: address закрыт целиком", str(open_address))

    # ЦЕЛАЯ ПОДМЕНА ДОЕЗЖАЕТ ДО МАСКИ: настоящее значение не остаётся в выводе.
    with tempfile.TemporaryDirectory() as td:
        vault = Vault(f"{td}/v.db", "g3").for_conversation("conv")
        payload = '{"passport": {"series": "4608"}}'
        masked = redact.mask_text(payload, vault, DET.detect(payload))
        check("4608" not in masked, "3e настоящее значение не ушло в модель", masked)
        doc = json.loads(masked)
        series = doc["passport"]["series"]
        check(series != "4608" and any(ch.isdigit() for ch in series),
              "3f лист получил ЦЕЛУЮ подмену (цифровую), а не открыт", repr(series))

    failed = [name for ok, name, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} проверок зелёные")
    for name in failed:
        print(f"  RED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
