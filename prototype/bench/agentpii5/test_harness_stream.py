"""Стриминговое плечо: клиент читает КУСКИ, и оцениваем мы то, что он прочитал.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_harness_stream

ONE OF THE TWO TESTS OF THIS PACKAGE THAT TOUCH THE ENGINE (the other,
`test_call_scoped_name_consistency`, pins the masking leg), and it does so
entirely in process: `testkit.load_dev_bundle()` for the detection assets, an
in-memory `Vault` for the substitutes, no network, no key, no model. The replies are not
asked of a model — they are WRITTEN out of the substitutes the vault just
minted, because the question here is about the restoration leg and a live model
would only make the input less controlled.

AND IT IS SHOWN TO FAIL, TWICE. A chunked feed that starts a fresh
`StreamDetokenizer` for every chunk restores the WRONG values («Иванова
Елизавета» for «Иванова Елена») rather than failing loudly — which is why
`stream_mismatch` is a field of the record and not a `try`. And the second
half runs over the CORPUS's own streaming cases, because the first half's
hand-written sentence agreed with itself on every restoration and so could not
see the defect F3.1 closes: the run used to score the whole-text restoration,
a text the streaming customer never receives, and on the corpus the two
restorations disagree on a few percent of replies. Both texts are KEPT (R-54,
`ArmRunV5.reply_whole`): `stream_fidelity` says THAT they disagreed, and the
reader who then asks WHICH text the customer lost had nothing on disk to look
at while the whole-text leg was restored for a `len()` and thrown away.
"""
import asyncio
import json
import tempfile
from collections.abc import Callable
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from bench.agentpii3 import score
from bench.agentpii3.live import judge as v3_judge
from bench.agentpii4 import harness as v4_harness
from bench.agentpii4.compare import ArmRun, substitutes_for
from bench.agentpii4.schema import Case, Expectation, Message, Provenance, SeedRecord, message_text
from bench.agentpii5 import harness as h
from bench.agentpii5 import records, runinfo
from bench.agentpii5.actual_hops import actual_events
from bench.agentpii5.connectors import Conversation, DialogueHooks, ToolSpec
from bench.agentpii5.contracts import ArmRunV5, CaseV5
from bench.agentpii5.fixtures import _in_message, _in_seed, _item, _hop
from bench.agentpii5.harness import (
    STREAM_CHUNK, GatewayHooks, GatewayV5, answer_leg, restore_stream, restored_turn_replies,
    stream_verdict, turn_restorer)
from bench.agentpii5.mock import seed_backend_v5
from bench.agentpii5.schema import case_v5_from_json
from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.maskcache import MaskCache
from pseudex.redact import StreamDetokenizer, unmask_arguments, unmask_text
from pseudex.vault import Vault
from testkit import load_dev_bundle

TEXT: str = "Иванова Елена, +7 916 402-11-87, Ижевск, улица Клубная, 85"
# The sentences an agent writes around the values it was given. Five shapes,
# not one: the disagreement between the two restorations depends on what stands
# BEFORE the value (the whole-text leg swallowed the generic word «улицу»), so a
# single template measures one neighbourhood and calls it the streaming leg.
TEMPLATES: tuple[str, ...] = (
    "Передам {0} на {1}.",
    "Готово: {0}, адрес {1}, спасибо!",
    "Записал. {0} — {1}. Подтвердите, пожалуйста.",
    "Клиент {0}, контакт {1}, доставка оформлена.",
    "{0}\n{1}\nвсё верно?")
CORPUS: str = "corpus.v5.json"
# How many corpus cases `test_restoration_runs_on_the_conversation_view` masks.
# Enough that its negative cannot miss: over the whole corpus the base vault and
# the conversation view disagree about 43.5 % of minted substitutes, so sixty
# cases is dozens of chances to see it — and the check refuses to pass on none.
SCOPE_CASES: int = 60


def _minted(text: str, detector: Detector, vault: Vault) -> tuple[str, ...]:
    """The substitutes the production masking path minted for one message."""
    masked = score._mask_message(text, detector, vault)
    return tuple(piece.substitute for piece in masked.pieces if piece.substitute.strip())


def _broken_stream(text: str, vault: Vault, chunk: int) -> str:
    """The feed without a carry: a fresh detokenizer per chunk. The negative
    fixture — a substitute cut by a boundary is resolved half at a time."""
    out: list[str] = []
    for at in range(0, len(text), chunk):
        stream = StreamDetokenizer(vault)
        out.append(stream.feed(text[at:at + chunk]))
        out.append(stream.flush())
    return "".join(out)


def test_chunked_answer() -> list[str]:
    failures: list[str] = []
    load_dev_bundle()
    detector = Detector()
    vault = Vault(":memory:", "agentpii5-stream-test")
    subs = _minted(TEXT, detector, vault)
    if len(subs) < 2:
        return [f"движок отчеканил {len(subs)} подмен на {TEXT!r} — тест не о чем"]
    raw = (f"Передам {subs[0]}, позвоню на {subs[1]}, адрес "
           f"{subs[-1]} подтверждён.")
    whole = unmask_text(raw, vault)
    if whole == raw:
        failures.append("целое восстановление ничего не изменило — подмены не в хранилище")
    chunked = restore_stream(raw, vault, STREAM_CHUNK)
    if chunked != whole:
        failures.append(f"поток разошёлся с целым:\n   целое  {whole!r}\n   куски  {chunked!r}")
    read, kept, mismatch = stream_verdict(raw, vault)
    if read != chunked:
        failures.append("stream_verdict вернул первым не то, что читает клиент")
    if kept != whole:
        failures.append("stream_verdict вернул вторым не то, что даёт unmask_text")
    if mismatch:
        failures.append("на чистом случае stream_mismatch выставлен — прибор кричит без повода")
    # R-54: the whole-text restoration is KEPT beside the scored one, so a
    # reader whom `stream_fidelity` told «две реставрации разошлись» has the
    # other text to look at. It used to be computed here and dropped.
    leg = answer_leg(raw, True, vault, _never)
    if leg.reply_whole != whole:
        failures.append(f"плечо ответа не сохранило целое восстановление: {leg.reply_whole!r}")
    # A substitute MUST straddle a boundary, or the carry was never exercised
    # and «совпало» would mean «нечего было переносить».
    if not any(at < len(subs[0]) + raw.index(subs[0]) and raw.index(subs[0]) < at
               for at in range(0, len(raw), STREAM_CHUNK)):
        failures.append(f"ни одна граница куска ({STREAM_CHUNK}) не режет первую подмену — "
                        f"перенос между кусками не проверен")
    # THE NEGATIVE: a feed with no carry restores the wrong values, and the
    # instrument must see it.
    # A random mint may happen to fit the production-size chunk boundaries,
    # or each fragment may now restore correctly on its own. The negative
    # must exercise a missing carry, not depend on that coincidence. A valid
    # one-character SSE split cuts every multi-character substitute; compare
    # the correct and broken readers on exactly that same split.
    if restore_stream(raw, vault, 1) != whole:
        failures.append("поток с переносом на односимвольных кусках разошёлся с целым")
    broken = _broken_stream(raw, vault, 1)
    if broken == whole:
        failures.append("поток без переноса совпал с целым — прибор не может покраснеть")
    return failures


def _never(text: str) -> str:
    """The whole-text restorer a STREAMING case must never call. Passed instead
    of `unmask_text` so «the chunked leg was taken» is proven by the absence of
    a call and not only by comparing two strings."""
    raise AssertionError(f"стриминговый случай позвал целое восстановление на {text[:40]!r}")


def test_corpus_answer_is_what_the_client_read() -> list[str]:
    """F3.1 over the corpus's OWN streaming cases: where the two restorations
    disagree, the scored answer is the chunked one.

    The reviewers' `f1c_fuzz.py`, turned into the test that pins the fix. The
    hand-written sentence above cannot see this: it agrees with itself on every
    restoration, while on the corpus's streaming cases the whole-text leg
    swallows the generic word («улицу подлесная …» vs «подлесная …») on a few
    percent of replies — and those were the replies the run used to score.
    """
    load_dev_bundle()
    detector = Detector()
    here = Path(__file__).resolve().parent
    raw = json.loads((here / CORPUS).read_text(encoding="utf-8"))
    cases = [case_v5_from_json(one) for one in raw["corpus"] if one.get("streaming")]
    failures: list[str] = []
    if not cases:
        return [f"в {CORPUS} нет ни одного стримингового случая — K11 сломан"]
    checked = 0
    disagreed = 0
    for case in cases:
        vault = Vault(":memory:", "agentpii5")
        subs: list[str] = []
        for message in case.base.messages:
            if message.role == "user":
                subs += list(_minted(message.content, detector, vault))
        if len(subs) < 2:
            continue
        for template in TEMPLATES:
            reply = template.format(subs[0], subs[-1])
            checked += 1
            read, kept, mismatch = stream_verdict(reply, vault)
            leg = answer_leg(reply, True, vault, _never)
            scored, flagged = leg.reply, leg.mismatch
            if scored != read or flagged != mismatch:
                failures.append(f"{case.base.id}: плечо ответа вернуло не вердикт потока")
            if leg.reply_whole != kept:
                failures.append(f"{case.base.id}: в записи не то целое восстановление")
            if (leg.reply != leg.reply_whole) != mismatch:
                failures.append(f"{case.base.id}: два текста записи расходятся не тогда, "
                                f"когда об этом говорит stream_mismatch")
            if mismatch != (read != kept):
                failures.append(f"{case.base.id}: stream_mismatch не равен «куски != целое»")
            if not mismatch:
                continue
            disagreed += 1
            # THE CLAIM: what is scored is what the customer read.
            if scored != restore_stream(reply, vault, STREAM_CHUNK):
                failures.append(f"{case.base.id}: оценивается не то, что клиент прочитал")
            if scored == unmask_text(reply, vault):
                failures.append(f"{case.base.id}: оценивается целое восстановление")
            # …and EVERY turn of the record says the same, the final one and
            # the intermediate ones alike: the streaming customer reads the
            # first turn in chunks too, and the whole-text restoration of an
            # earlier turn is a text nobody was served — the judge's context
            # and `turn_residual` both read it.
            restore = turn_restorer(case, _StreamOnly(vault))
            turns = restored_turn_replies(("Секунду, ищу.", reply), restore)
            if turns[-1] != scored:
                failures.append(f"{case.base.id}: в реплики хода уехало целое восстановление")
            if turns[0] != restore_stream("Секунду, ищу.", vault, STREAM_CHUNK):
                failures.append(f"{case.base.id}: промежуточный ход восстановлен не потоком")
    print(f"    расхождений потока и целого: {disagreed} из {checked} "
          f"({100 * disagreed / max(1, checked):.1f}%)")
    if disagreed == 0:
        # NOT a pass: with no disagreement anywhere this check asserts nothing
        # about which restoration is scored, and an instrument that cannot see
        # the defect it was built for is not an instrument. If the engine's
        # streaming leg ever agrees everywhere, widen the templates (the
        # neighbourhood of the value is what drives it) before deleting this.
        failures.append(f"на {checked} ответах корпуса куски и целое ни разу не разошлись — "
                        f"проверка F3.1 ничего не увидела")
    return failures


class _StreamOnly:
    """A stand-in gateway whose WHOLE-TEXT restorer raises.

    `turn_restorer` chooses the leg once per case, and a streaming case must
    never take the whole-text one — for an INTERMEDIATE turn either. Proven by
    the absence of a call rather than by comparing two strings: the two
    restorations agree on most replies, so an equality check would pass on a
    harness that restored every earlier turn whole.
    """

    def __init__(self, vault: Vault) -> None:
        self.vault = vault

    def restore_text(self, text: str) -> str:
        raise AssertionError(f"стриминговый случай позвал целое восстановление на {text[:40]!r}")


def test_restoration_runs_on_the_conversation_view() -> list[str]:
    """G3.1: the gateway masks through the conversation VIEW and must restore
    through the SAME object.

    `RealGateway` masks with `MaskContext(vault=self._view)` — the conversation
    scope — and v4 restored through `self._base`, the unscoped vault. Production
    restores through the view too (`service._scoped` →
    `vault.for_conversation(conversation_id)`), and a LINKED row is written
    under a CONVERSATION-scoped canonical, so the base vault cannot resolve it:
    458 of 1 260 substitutes minted over this corpus came back STANDING. Every
    value metric of the gateway arm was then scoring a restoration the product
    never performs — a fake reaching the tool, and an answer the residual
    pre-gate calls «неверно».

    THE NEGATIVE IS THE OLD OBJECT ITSELF: the base vault handed to the
    constructor is still there, and the check refuses to pass unless it can be
    shown leaving a substitute standing on at least one case.
    """
    load_dev_bundle()
    detector = Detector()
    here = Path(__file__).resolve().parent
    raw = json.loads((here / CORPUS).read_text(encoding="utf-8"))
    cases = [case_v5_from_json(one) for one in raw["corpus"][:SCOPE_CASES]]
    failures: list[str] = []
    masked_messages = 0
    base_lost = 0
    tool_lost = 0
    for case in cases:
        base = Vault(":memory:", "agentpii5")
        gateway = GatewayV5(case, detector, base, AuditLog(":memory:"), MaskCache(256))
        gateway.push_system(case.base.messages[0].content)
        gateway.tools()
        if gateway.vault is base:
            # RETURNED, not `break`: with the wrong object every counter below
            # says «нечего проверять», and three lines of noise under the one
            # real cause is how a reader learns to skim a failure list.
            return [f"{case.base.id}: gateway.vault — это базовое хранилище, "
                    f"а маскировали видом разговора"]
        for index, message in enumerate(case.base.messages):
            if message.role != "user":
                continue
            served = gateway.push_user(index)
            original = message_text(case.base, index)
            if served == original:
                continue
            masked_messages += 1
            if gateway.restore_text(served) != original:
                failures.append(f"{case.base.id}: сообщение не восстановилось тем же видом:\n"
                                f"   было  {original!r}\n   стало {gateway.restore_text(served)!r}")
            if unmask_text(served, base) != original:
                base_lost += 1
        written = [surface for surface in gateway.substitutes() if surface.strip()]
        if not written:
            continue
        # THE TOOL LEG, where a surviving substitute is the product's headline
        # defect: the agent writes back what it read.
        arguments = {"name": written[0], "note": " ".join(written)}
        restored, residual = gateway.restore_arguments(arguments)
        if residual:
            failures.append(f"{case.base.id}: в аргумент инструмента уехала подмена: {residual}")
        through_base = json.loads(unmask_arguments(json.dumps(arguments, ensure_ascii=False), base))
        if through_base != restored:
            tool_lost += 1
    if masked_messages == 0:
        failures.append(f"на {len(cases)} случаях корпуса движок ничего не замаскировал — "
                        f"проверка ни о чём")
    if base_lost == 0:
        failures.append(f"базовое хранилище восстановило ВСЁ на {masked_messages} сообщениях — "
                        f"негатив не сработал, и «восстановили видом» ничего не доказывает")
    if tool_lost == 0:
        failures.append("аргументы инструмента через базовое хранилище вышли теми же — "
                        "негатив ни о чём")
    print(f"    сообщений замаскировано: {masked_messages} · базовое хранилище потеряло "
          f"{base_lost} · аргументов разошлось: {tool_lost}")
    return failures


# --- §1.4 обрыв провайдера НА НАСТОЯЩЕМ ПУТИ --------------------------------------------

# Сколько обрывов подряд имитирует скрипт транспорта. Считаются ВЫЗОВЫ
# `receive_response`, а первым плечом тройки идёт контрольное, так что два
# обрыва — это две попытки тройки, снятые на первом же её плече.
_BREAKS_LEFT: dict[str, int] = {"left": 0, "forever": 0}


class _ScriptedTransport:
    """Клиент SDK, которого подменили скриптом: рвётся, потом отвечает.

    ЭТО ЕДИНСТВЕННЫЙ СПОСОБ проверить §1.4 на живом пути, не позвав модель.
    Повтор написан вокруг ТРОЙКИ, а рвётся ПЛЕЧО — и между ними стоят стражи
    (`_guarded_control`, `_guarded_arm_v5`) и `run_triple_v5` с его `finally`
    по леджеру. Проверка на подменённом `run_arm_v5` (`test_harness`) не видит
    ни стражей в связке, ни того, что тройка по дороге ничего не глотает;
    проверка отсюда видит весь путь от `drive_v5` до `ClaudeSDKClient`.
    """

    def __init__(self, options: object = None, **kwargs: object) -> None:
        self._options = options
        self._pending: list[str] = []

    async def __aenter__(self) -> "_ScriptedTransport":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def query(self, text: str) -> None:
        self._pending.append(text)

    async def receive_response(self):          # type: ignore[no-untyped-def]
        if _BREAKS_LEFT["forever"]:
            raise ConnectionError("провайдер оборвал связь (скрипт, навсегда)")
        if _BREAKS_LEFT["left"] > 0:
            _BREAKS_LEFT["left"] -= 1
            raise ConnectionError("провайдер оборвал связь (скрипт)")
        yield AssistantMessage(content=[TextBlock(text="Готово.")], model="scripted-model")
        yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False,
                            num_turns=1, session_id="scripted", total_cost_usd=0.001,
                            model_usage={"scripted-model": {"costUSD": 0.001}})


def _drive(case: CaseV5, run_dir: Path, run_id: str) -> object:
    """Одна тройка КОРПУСНОГО случая через `drive_v5` → `run_triple_v5` →
    настоящие стражи → скриптованный транспорт. Судья выключен: он спрашивает
    модель, а здесь её нет."""
    load_dev_bundle()
    detector = Detector()
    ledger = v3_judge.SpendLedger(run_dir / f"{run_id}.spend.tsv", 10.0)
    runner = h.triple_runner(detector, ledger, None, "scripted-model", run_id, h.ClaudeArms())
    h.write_corpus(run_dir, [case], "deadbeef")
    policy = h.DrivePolicy(attempts=3, base_s=runinfo.RETRY_BASE_S, pause=_no_pause,
                           jitter=lambda: 1.0, expected_per_case_usd=0.0)
    return asyncio.run(h.drive_v5([case], 1, runner, run_dir, run_id, 1, frozenset(), policy))


async def _no_pause(seconds: float) -> None:
    """Отступ без ожидания: кривая отступа проверяется в `test_runinfo`, а
    честные 2 + 4 секунды здесь — это шесть секунд к батарее и выключенная
    через неделю проверка."""
    return None


def test_a_provider_blip_is_retried_on_the_real_path() -> list[str]:
    """§1.4 на настоящем пути: два обрыва подряд — третья попытка доезжает;
    обрыв навсегда — случай снят, прогон доходит до конца.

    ДО ПОЧИНКИ ЭТА ПРОВЕРКА КРАСНАЯ И НА ТОЙ, И НА ДРУГОЙ ПОЛОВИНЕ: страж
    плеча ловил `ConnectionError` (это `OSError`) и возвращал снятое плечо, так
    что `run_with_retries` не видел ни одной попытки повторить, а тройка
    записывалась как `excluded` по вердикту плеча — не как снятая обрывом.
    Разница читателю видна только по причине в строке, и «плечо не доиграло»
    он спишет на модель.
    """
    failures: list[str] = []
    here = Path(__file__).resolve().parent
    raw = json.loads((here / CORPUS).read_text(encoding="utf-8"))
    case = case_v5_from_json(raw["corpus"][0])
    original_v5, original_v4 = h.ClaudeSDKClient, v4_harness.ClaudeSDKClient
    with tempfile.TemporaryDirectory() as tmp:
        try:
            h.ClaudeSDKClient = _ScriptedTransport
            v4_harness.ClaudeSDKClient = _ScriptedTransport
            _BREAKS_LEFT.update(left=2, forever=0)
            good_dir = Path(tmp) / "good"
            good_dir.mkdir()
            outcome = _drive(case, good_dir, "run-good")
            if _BREAKS_LEFT["left"] != 0:
                failures.append(f"скрипт оборвал связь не дважды: осталось "
                                f"{_BREAKS_LEFT['left']}")
            if outcome.transport_terminated:
                failures.append(f"случай снят обрывом, хотя третья попытка обязана была "
                                f"доехать: {outcome.transport_terminated}")
            rows = records.read_rows(records.run_file(good_dir, "run-good",
                                                      "<run>.triples.jsonl"))
            if len(rows) != 1 or str(rows[0].get("status")) != "complete":
                failures.append(f"тройка после двух обрывов записана как "
                                f"{[row.get('status') for row in rows]}, ожидался complete")
            _BREAKS_LEFT.update(left=0, forever=1)
            bad_dir = Path(tmp) / "bad"
            bad_dir.mkdir()
            gone = _drive(case, bad_dir, "run-bad")
            if gone.transport_terminated != 1:
                failures.append(f"снятых обрывом {gone.transport_terminated}, ожидался один — "
                                f"прогон обязан идти дальше, а не падать")
            rows = records.read_rows(records.run_file(bad_dir, "run-bad",
                                                      "<run>.triples.jsonl"))
            if len(rows) != 1:
                failures.append(f"строк троек {len(rows)}: случай, о котором не написано "
                                f"ничего, читается как случай, который не выбирали")
            elif runinfo.TRANSPORT_TERMINATED not in str(rows[0].get("reason")):
                failures.append(f"снятый случай не назван обрывом: {rows[0].get('reason')!r}")
        finally:
            h.ClaudeSDKClient, v4_harness.ClaudeSDKClient = original_v5, original_v4
            _BREAKS_LEFT.update(left=0, forever=0)
    return failures


# --- E07: chains, repeats, corrections, memory, several entities --------------------------

# Two customers' phones, one per identity. The chain carries the first; the
# second is the same TYPE that must never be confused with it.
CHAIN_PHONE_ONE: str = "+79164021187"
CHAIN_PHONE_TWO: str = "+79261234567"
CHAIN_TOOLS: tuple[str, ...] = ("crm_find_contact", "notify_sms")


def _chain_case() -> CaseV5:
    """The SMALL case E07 pins: one A→B chain, two entities of one type.

    The user says both phones in one message; the agent looks each up, sends an
    SMS to each, repeats the first, corrects a wrong number, and — a turn later
    — acts on the first phone again from memory. The declared hops carry the
    chain link (`source_hop` on the OUT/tool_arg `notify_sms.number` pointing at
    the IN/tool `crm_find_contact` `contacts[].phone` hop), so a reader can flip
    it and see the test go red.
    """
    text = f"мой номер {CHAIN_PHONE_ONE}, коллеге {CHAIN_PHONE_TWO}"
    one_at = text.index(CHAIN_PHONE_ONE)
    two_at = text.index(CHAIN_PHONE_TWO)
    p_msg1 = _item("p_msg1", "PHONE", CHAIN_PHONE_ONE, CHAIN_PHONE_ONE, "i1",
                   _in_message(1, one_at, one_at + len(CHAIN_PHONE_ONE)))
    p_msg2 = _item("p_msg2", "PHONE", CHAIN_PHONE_TWO, CHAIN_PHONE_TWO, "i2",
                   _in_message(1, two_at, two_at + len(CHAIN_PHONE_TWO)))
    p1s = _item("p1s", "PHONE", CHAIN_PHONE_ONE, CHAIN_PHONE_ONE, "i1", _in_seed("c-1", "phone"))
    p2s = _item("p2s", "PHONE", CHAIN_PHONE_TWO, CHAIN_PHONE_TWO, "i2", _in_seed("c-2", "phone"))
    base = Case(
        id="e07-chain", kind="chain", register="chat",
        provenance=Provenance(kind="authored", corpus="authored", key="", shape="",
                              selection="census", weight=1.0, licence="authored"),
        cluster=f"PHONE:{CHAIN_PHONE_ONE}", conversation_id="e07-chain", now="2026-09-01",
        messages=(Message(role="system", content="Ты оператор.", source=None, name=""),
                  Message(role="user", content=text, source=None, name=""),
                  Message(role="user", content="позвоните ещё раз на мой номер",
                          source=None, name="")),
        tools=CHAIN_TOOLS,
        seed_records=(
            SeedRecord(id="c-1", table="contacts",
                       fields={"last_name": "Иванова", "first_name": "Елена",
                               "phone": CHAIN_PHONE_ONE},
                       pii_ids=("p1s",)),
            SeedRecord(id="c-2", table="contacts",
                       fields={"last_name": "Смирнова", "first_name": "Анна",
                               "phone": CHAIN_PHONE_TWO},
                       pii_ids=("p2s",)),
        ),
        pii=(p_msg1, p_msg2, p1s, p2s), plain=(), negatives=(),
        expects=Expectation(reachable_tools=CHAIN_TOOLS, primary_identity="i1",
                            must_contain=(), must_not_contain=(), validate_types=()),
        trace=(), note="E07: цепь/повтор/исправление/память/две сущности")
    find_in = _hop("IN", "tool", "p1s", 3, 1, "crm_find_contact", 0, -1, "contacts[].phone")
    hops = (
        _hop("IN", "user", "p_msg1", 0, 1, "", -1, -1, ""),
        _hop("IN", "user", "p_msg2", 1, 1, "", -1, -1, ""),
        _hop("OUT", "tool_arg", "p_msg1", 2, 1, "crm_find_contact", 0, 0, "query.phone"),
        find_in,
        # THE CHAIN HOP: B consumes the value A returned. `source_hop == 3` is
        # the IN/tool hop above; flipping it is what a reader breaks to see red.
        _hop("OUT", "tool_arg", "p1s", 4, 1, "notify_sms", 0, 3, "number"),
        _hop("OUT", "tool_arg", "p_msg2", 5, 1, "crm_find_contact", 0, 1, "query.phone"),
        _hop("IN", "tool", "p2s", 6, 1, "crm_find_contact", 0, -1, "contacts[].phone"),
        _hop("OUT", "tool_arg", "p2s", 7, 1, "notify_sms", 0, 6, "number"),
    )
    return CaseV5(base=base, behaviour="sequential_chain", hops=hops, returns=(), forced=(),
                  memory=(), pick=None, branch=None, loop=None, rag=None, document=None,
                  has_result=True, streaming=False, revised_from_v4=False)


def _scripted_chain_run():
    """The E07 case through the REAL gateway path, the agent's actions scripted.

    `GatewayHooks` is the same seam `ConnectedArms._run` drives with a live
    connector; here the connector is replaced by a fixed script, so the mask →
    restore → mock → record path is the production one and no model is asked
    for anything. The script writes back the SUBSTITUTES the gateway just
    minted (a real agent reads masked values and echoes them), so the restored
    value is the assertion and the mint itself is not.
    """
    case = _chain_case()
    detector = Detector()
    vault = Vault(":memory:", "agentpii5-chain")
    gateway = GatewayV5(case, detector, vault, AuditLog(":memory:"), MaskCache(256))
    backend = seed_backend_v5(case)
    hooks = GatewayHooks(case, gateway, backend)
    gateway.push_system(case.base.messages[0].content)

    def substitute(item_id: str) -> str:
        for mention in reversed(gateway.mentions()):
            if mention.item_id == item_id and mention.substitute:
                return mention.substitute
        raise AssertionError(f"нет подмены для {item_id}")

    hooks.user(1)
    sub_one = substitute("p_msg1")
    sub_two = substitute("p_msg2")
    # (a) A→B chain: A returns the stored phone, B sends to it.
    hooks.response("найду первого")
    hooks.tool("crm_find_contact", {"query": {"phone": sub_one}})
    stored_one = substitute("p1s")
    hooks.response("отправлю смс")
    hooks.tool("notify_sms", {"number": stored_one, "text": "Готово", "sign": "SMS Aero"})
    # (e) the second entity, the same type, kept apart.
    hooks.response("найду второго")
    hooks.tool("crm_find_contact", {"query": {"phone": sub_two}})
    stored_two = substitute("p2s")
    hooks.response("отправлю второму")
    hooks.tool("notify_sms", {"number": stored_two, "text": "Готово", "sign": "SMS Aero"})
    # (b) a repeat: the same call again is a SECOND crossing, never merged.
    hooks.response("повторю первому")
    hooks.tool("notify_sms", {"number": stored_one, "text": "Готово", "sign": "SMS Aero"})
    # (c) a correction: the wrong number first, the right one re-issued after.
    hooks.response("исправлю")
    hooks.tool("notify_sms", {"number": stored_two, "text": "Готово", "sign": "SMS Aero"})
    hooks.response("исправил")
    hooks.tool("notify_sms", {"number": stored_one, "text": "Готово", "sign": "SMS Aero"})
    # (d) memory: the NEXT turn acts on a value obtained in this one.
    hooks.user(2)
    hooks.response("ещё раз")
    hooks.tool("notify_sms", {"number": stored_one, "text": "Готово", "sign": "SMS Aero"})

    raw = "Готово, отправил."
    base_run = ArmRun(case_id=case.base.id, arm="I", repeat=0, calls=tuple(hooks.calls),
                      state=backend.snapshot(), reply=raw, termination="done", cost_usd=0.0,
                      substitutes=substitutes_for(case.base, gateway.substitutes_seen()),
                      masked_spans=gateway.masked_spans())
    run = ArmRunV5(base=base_run, reply_raw=raw, control_reply="",
                   tool_results=gateway.tool_records(), mentions=gateway.mentions(),
                   turn_replies=(raw,), call_turns=tuple(hooks.turns),
                   request_count=gateway.request_index, stream_mismatch=False,
                   reply_whole=raw, turn_residual=0, model_trace=hooks.model_trace())
    return case, run, actual_events(case, run)


def test_chain_repeat_correction_memory_two_entities() -> list[str]:
    """E07: the measurement follows the ACTUAL events, not the declared turns.

    The historical observer scores the case's timetable; `actual_events` scores
    every written leaf of every actual call. Five properties, each broken
    separately to see red:

      * (a) chain: B's OUT hop names A's IN/tool result in `source_hop`, and the
        crossing B actually made carries A's real value;
      * (b) repeat: two calls of one tool are two events, never one;
      * (c) correction: the value re-issued in a later call is the one measured;
      * (d) memory: a value obtained in turn 1 and acted on in turn 2 restores
        again in turn 2;
      * (e) two entities of one type stay their own: each leaf restores to the
        real value of the item it is attributed to, and the two never swap.
    """
    # Standalone load, like every other check in this file: the E07 check is
    # callable directly (not only through `main()`) and must lease the detection
    # bundle itself — `Detector()`/`GatewayV5` raise `BundleNotLeased` without it.
    load_dev_bundle()
    case, run, observation = _scripted_chain_run()
    failures: list[str] = []
    events = observation.events
    numbers = [event for event in events
               if event.tool_name == "notify_sms" and event.path == "number"]

    # (a) THE DECLARED CHAIN LINK. `source_hop` on the OUT/tool_arg notify_sms
    # hop names the IN/tool hop of `crm_find_contact` whose value B carries.
    chain_hop = next((hop for hop in case.hops
                      if hop.owner == "tool_arg" and hop.tool_name == "notify_sms"
                      and hop.call_ordinal == 0), None)
    if chain_hop is None or chain_hop.source_hop < 0:
        failures.append("нет OUT/tool_arg notify_sms hop с source_hop")
    else:
        source = case.hops[chain_hop.source_hop]
        if not (source.kind == "IN" and source.owner == "tool"
                and source.tool_name == "crm_find_contact" and source.item_id == "p1s"):
            failures.append(f"source_hop {chain_hop.source_hop} ведёт не на IN/tool "
                            f"crm_find_contact.p1s, а на {source}")

    # (a) THE CHAIN AS IT ACTUALLY RAN: the FIRST SMS is the one A's result fed,
    # and it carries the real phone the find returned — restored in the tool's
    # own notation, in the form the leaf asked for. Pointing B at the wrong
    # entity moves this first crossing to p2s and the check goes red.
    chain_event = min(numbers, key=lambda event: event.call_seq, default=None)
    if chain_event is None or chain_event.item_id != "p1s":
        failures.append("первый notify_sms.number ушёл не на сущность цепи (p1s), "
                        f"а на {chain_event.item_id if chain_event else None}")
    else:
        if chain_event.restored != CHAIN_PHONE_ONE:
            failures.append(f"цепь донесла до B не настоящий номер: "
                            f"{chain_event.restored!r}")
        if not (chain_event.value_ok and chain_event.form_ok):
            failures.append(f"цепь: value_ok/form_ok = {chain_event.value_ok}/"
                            f"{chain_event.form_ok} на {chain_event.restored!r}")

    # (b) REPEAT is itself present AND does not merge. The repeat is the SECOND
    # p1s crossing in turn 1; the chain, the repeat and the correction together
    # write p1s three times, so the count of p1s crossings in turn 1 is the
    # unique fingerprint of the repeat — delete the repeat and it drops to two.
    # This is what makes the check a PIN rather than a tautology: counting
    # `len(numbers) == notify_calls` alone stayed green with the repeat deleted.
    p1s_turn1 = [event for event in numbers
                 if event.item_id == "p1s" and event.call_turn == 1]
    if len(p1s_turn1) != 3:
        failures.append(f"повтор не различим: {len(p1s_turn1)} пересечений p1s на "
                        f"ходе 1 вместо 3 (цепь+повтор+исправление)")
    # Every actual `notify_sms` call is ONE `number` crossing, so a call made
    # twice is two events and never folded into one.
    notify_calls = sum(1 for call in run.base.calls if call.name == "notify_sms")
    if len(numbers) != notify_calls:
        failures.append(f"повтор слился: {notify_calls} вызовов notify_sms, "
                        f"а событий number {len(numbers)}")
    elif len({event.call_seq for event in numbers}) != len(numbers):
        failures.append("два повтора поделили один call_seq — события не различимы")

    # (c) CORRECTION: the wrong number was re-issued as the right one, and the
    # RIGHT one is the value the later call measured. The correction-wrong is the
    # SECOND p2s crossing in turn 1 (the first belongs to the second entity), so
    # it exists only because the correction wrote it; the correction-right is the
    # LAST p1s crossing, after it. The old check read any p2s as «wrong» and any
    # later p1s as «right», so the second entity plus the repeat satisfied it with
    # the correction deleted — now each half is uniquely required.
    wrong = [event for event in numbers
             if event.item_id == "p2s" and event.call_turn == 1]
    right = [event for event in numbers
             if event.item_id == "p1s" and event.call_turn == 1
             and event.restored == CHAIN_PHONE_ONE]
    if len(wrong) < 2:
        failures.append("исправлению не предшествовал отдельный неверный номер (p2s)")
    elif max(event.call_seq for event in right) <= max(event.call_seq for event in wrong):
        failures.append("исправленный номер не стал ПОЗЖЕ неверного — правка не измерена")

    # (d) MEMORY: turn 2 acts on the value obtained in turn 1 and it restores.
    remembered = [event for event in numbers
                  if event.item_id == "p1s" and event.call_turn == 2]
    if not remembered:
        failures.append("значение с хода 1 не дошло до хода 2 — память не измерена")
    elif any(event.restored != CHAIN_PHONE_ONE for event in remembered):
        failures.append("память восстановила на ходе 2 не тот номер")

    # (e) TWO ENTITIES stay distinct: every attributed number restores to the
    # real value of the item it names, and both identities crossed at least once.
    restored_by_identity: dict[str, set[str]] = {}
    for event in numbers:
        if event.item_id in ("p1s", "p2s"):
            restored_by_identity.setdefault(event.identity, set()).add(event.restored)
    if restored_by_identity.get("i1") != {CHAIN_PHONE_ONE}:
        failures.append(f"сущность i1 восстановилась не в свой номер: "
                        f"{restored_by_identity.get('i1')}")
    if restored_by_identity.get("i2") != {CHAIN_PHONE_TWO}:
        failures.append(f"сущность i2 восстановилась не в свой номер: "
                        f"{restored_by_identity.get('i2')}")
    if "i1" not in restored_by_identity or "i2" not in restored_by_identity:
        failures.append("обе сущности должны пересечь шлюз, а пересекла одна")

    # THE TOOL NEVER RECEIVED A SUBSTITUTE: every restored number is a real one
    # and no residual leaked past the gateway into the call.
    for call in run.base.calls:
        if call.name != "notify_sms":
            continue
        number = call.restored.get("number")
        if number not in (CHAIN_PHONE_ONE, CHAIN_PHONE_TWO):
            failures.append(f"в инструмент ушёл не номер: {number!r}")
        if call.residual.get("number"):
            failures.append(f"в номер уехала подмена: {call.residual.get('number')}")
    return failures


class PartialThenErrorAgent:
    """A connector double that executes two tool calls, then fails the engine.

    The RuntimeError is NOT a transient blip, so `arm_verdict` classifies the I
    arm as `gateway_5xx` — exactly the long_order-012 shape where three accepted
    orders once vanished behind an empty record."""

    async def converse(self, system: str, tools: tuple[ToolSpec, ...],
                       user_indices: tuple[int, ...], hooks: DialogueHooks,
                       timeout_s: float, max_calls: int) -> Conversation:
        for index in user_indices:
            hooks.user(index)
        hooks.response("lookup")
        hooks.tool("crm_find_contact", {"query": {"phone": CHAIN_PHONE_ONE}})
        hooks.response("send")
        hooks.tool("notify_sms", {"number": CHAIN_PHONE_ONE, "text": "ok", "sign": "SMS Aero"})
        raise RuntimeError("engine failed closed after two calls")


def test_partial_history_preserved_on_error() -> list[str]:
    """An error AFTER executed calls must keep those calls and the mock state."""
    failures: list[str] = []
    case = _chain_case()
    gateway = GatewayV5(case, Detector(), Vault(":memory:", "partial-history"),
                        AuditLog(":memory:"), MaskCache(256))
    backend = seed_backend_v5(case)
    outcome = asyncio.run(h.ConnectedArms(PartialThenErrorAgent(), max_calls=100).intervention(
        case, 0, gateway, backend, "fixture", 0.15, "fixture-run"))
    run = outcome.run
    if outcome.base.run.termination != "gateway_5xx":
        failures.append(f"termination={outcome.base.run.termination}, want gateway_5xx")
    if len(run.base.calls) != 2:
        failures.append(f"calls={len(run.base.calls)}, want 2")
    if not run.base.state:
        failures.append("state empty despite two executed calls")
    if len(run.tool_results) != 2:
        failures.append(f"tool_results={len(run.tool_results)}, want 2")
    if tuple(run.call_turns) != (2, 2):
        failures.append(f"call_turns={run.call_turns}, want (2, 2)")
    if run.model_trace is None:
        failures.append("model_trace lost although responses were reported")
    return failures


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("chunked_answer", test_chunked_answer),
        ("corpus_answer_is_what_the_client_read", test_corpus_answer_is_what_the_client_read),
        ("restoration_runs_on_the_conversation_view",
         test_restoration_runs_on_the_conversation_view),
        ("a_provider_blip_is_retried_on_the_real_path",
         test_a_provider_blip_is_retried_on_the_real_path),
        ("chain_repeat_correction_memory_two_entities",
         test_chain_repeat_correction_memory_two_entities),
        ("partial_history_preserved_on_error", test_partial_history_preserved_on_error),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("harness_stream: PASS" if not failures
          else "harness_stream: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
