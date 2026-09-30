"""Ж.2 — прокидывание leaf_notation во все точки вызова OUT-плеча.

Движок готов: `redact.unmask_arguments(raw, vault, leaf_notation={key: notation})`
рендерит СНИЛС как «XXX-XXX-XXX YY» при `target=="snils"` и в форме агента без
объявления. Этот тест закрепляет ДВЕ вещи, которых движку мало:

  1. сам шов — `leaf_notation` проходит в `unmask_arguments` и применяется по
     ключу листа, не всему вызову, а пустая карта и чужие ключи ничего не ломают;
  2. вызывающие ДЕЙСТВИТЕЛЬНО его передают — `bench.agentpii4.gateway` вычисляет
     карту из тул-схемы (`bench.agentpii5.tools.LEAF_NOTATION`) и кладёт её в
     `unmask_arguments`, что проверяется на ЖИВОМ `RealGateway`, а не на стабе.

Self-contained: без LLM и сети, грузит bundle из исходников, гоняет НАСТОЯЩИЙ
`Vault`/`Detector`/`RealGateway`.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_zh2_gateway_wiring.py
"""

import json
import re
import sys
import tempfile

import testkit

testkit.load_dev_bundle()

from pseudex.audit import AuditLog                            # noqa: E402
from pseudex.detect_all import Detector                       # noqa: E402
from pseudex.maskcache import MaskCache                       # noqa: E402
from pseudex.redact import mask_text, unmask_arguments        # noqa: E402
from pseudex.vault import Vault                               # noqa: E402

from bench.agentpii4.gateway import RealGateway, leaf_notation_for  # noqa: E402
from bench.agentpii4.schema import Case, Expectation, Message, Provenance  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _minimal_case() -> Case:
    """A Case with the bare fields `RealGateway.__init__` reads. `conversation_id`
    is set, so `messages` is never iterated for a derived key."""
    return Case(
        id="wiring", kind="validate", register="clean",
        provenance=Provenance(kind="template", corpus="authored", key="", shape="",
                              selection="authored", weight=1.0, licence="cc-by-4.0"),
        cluster="SNILS:wiring", conversation_id="conv", now="2026-09-10",
        messages=(), tools=("snils_verify",),
        seed_records=(), pii=(), plain=(), negatives=(),
        expects=Expectation(reachable_tools=("snils_verify",), primary_identity="",
                            must_contain=(), must_not_contain=(), validate_types=()),
        trace=(), note="wiring",
    )


def _substitute_of(masked: str, source: str, pattern: str) -> str:
    match = re.search(pattern, masked)
    assert match is not None, (source, masked, pattern)
    return match.group(1)


def main() -> int:
    detector = Detector()

    with tempfile.TemporaryDirectory() as td:
        vault = Vault(f"{td}/v.db", "zh2")
        real = "760-451-105 71"
        fake = vault.tokenize(real, "SNILS")
        reformatted = fake.replace("-", "").replace(" ", "")

        # --- 1. сам шов: объявлено — нотация схемы, не объявлено — форма агента
        args = json.dumps({"snils": reformatted})
        with_target = json.loads(unmask_arguments(args, vault, leaf_notation={"snils": "snils"}))["snils"]
        check(with_target == real, "Ж.2 leaf_notation={'snils':'snils'} -> XXX-XXX-XXX YY", repr(with_target))

        without_target = json.loads(unmask_arguments(args, vault))["snils"]
        check(without_target == "76045110571", "Ж.2 без объявления нотацию держит агент", repr(without_target))

        # --- 2. нотация применяется по ключу листа, а не всему вызову
        args2 = json.dumps({"snils": reformatted, "note": reformatted})
        out2 = json.loads(unmask_arguments(args2, vault, leaf_notation={"snils": "snils"}))
        check(out2["snils"] == real and out2["note"] == "76045110571",
              "Ж.2 нотация по ключу листа, соседний лист не трогается", repr(out2))

        # --- 3. пустая карта = нет изменений (форма агента)
        empty = json.loads(unmask_arguments(args, vault, leaf_notation={}))
        check(empty == {"snils": "76045110571"}, "Ж.2 пустая карта = форма агента", repr(empty))

        # --- 4. чужие ключи (series/number) не ломают паспорт
        source = "паспорт 4509 123456"
        pvault = Vault(f"{td}/pv.db", "zh2").for_conversation("c1")
        masked = mask_text(source, pvault, detector.detect(source))
        passport = re.sub(r"\D", "", _substitute_of(masked, source, r"паспорт ([\d ]{10,11})"))
        praw = json.dumps({"series": passport[:4], "number": passport[4:]}, ensure_ascii=False)
        pout = json.loads(unmask_arguments(
            praw, pvault, leaf_notation={"series": "snils", "number": "snils"}))
        check(pout == {"series": "4509", "number": "123456"},
              "Ж.2 чужой leaf_notation (series/number) не ломает паспорт", repr(pout))

        # --- 5. вычисление карты из тул-схемы ---------------------------------
        check(leaf_notation_for("snils_verify", {"snils": "x"}) == {"snils": "snils"},
              "gateway: snils_verify.snils объявлен как 'snils'",
              repr(leaf_notation_for("snils_verify", {"snils": "x"})))
        check(leaf_notation_for("patient_find", {"snils": "x", "phone": "x"}) ==
              {"snils": "snils", "phone": "e164"},
              "gateway: patient_find.snils/phone объявлены",
              repr(leaf_notation_for("patient_find", {"snils": "x", "phone": "x"})))
        check(leaf_notation_for("snils_verify", {"note": "x"}) == {},
              "gateway: необъявленный лист отсутствует, не угадывается",
              repr(leaf_notation_for("snils_verify", {"note": "x"})))
        check(leaf_notation_for("snils_verify", {"snils": "x", "note": "x"}) == {"snils": "snils"},
              "gateway: объявленный лист рядом с необъявленным", repr(leaf_notation_for("snils_verify", {"snils": "x", "note": "x"})))

        # --- 6. живой RealGateway передаёт leaf_notation в unmask_arguments ----
        gvault = Vault(f"{td}/gv.db", "zh2")
        gfake = gvault.tokenize(real, "SNILS")
        greformatted = gfake.replace("-", "").replace(" ", "")
        audit = AuditLog(f"{td}/audit.db")
        gateway = RealGateway(_minimal_case(), detector, gvault, audit, MaskCache(16))
        restored, residual = gateway.restore_arguments({"snils": greformatted}, name="snils_verify")
        check(restored["snils"] == real,
              "gateway: restore_arguments(name='snils_verify') рендерит в нотации схемы",
              repr(restored["snils"]))

        # Та же точка без объявления нотации (другой tool) — форма агента.
        restored_no, _ = gateway.restore_arguments({"snils": greformatted}, name="crm_upsert_contact")
        check(restored_no["snils"] == "76045110571",
              "gateway: без объявленной нотации форма агента",
              repr(restored_no["snils"]))

    failed = [name for ok, name, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} проверок зелёные")
    for name in failed:
        print(f"  RED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
