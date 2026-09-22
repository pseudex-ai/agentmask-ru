"""Стриминговое плечо: клиент читает КУСКИ, и оцениваем мы то, что он прочитал.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_harness_stream

THE ONLY TEST OF THIS PACKAGE THAT TOUCHES THE ENGINE, and it does so entirely
in process: `testkit.load_dev_bundle()` for the detection assets, an in-memory
`Vault` for the substitutes, no network, no key, no model. The replies are not
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
import json
from collections.abc import Callable
from pathlib import Path

from bench.agentpii3 import score
from bench.agentpii5.harness import (
    STREAM_CHUNK, answer_leg, restore_stream, stream_verdict, with_streamed_answer)
from bench.agentpii5.schema import case_v5_from_json
from pseudex.detect_all import Detector
from pseudex.redact import StreamDetokenizer, unmask_text
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
    broken = _broken_stream(raw, vault, STREAM_CHUNK)
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
            # …and the record's last turn says the same, or the judge's context
            # and the report's answer would be two different texts.
            turns = with_streamed_answer(("Секунду, ищу.", unmask_text(reply, vault)), scored)
            if turns[-1] != scored:
                failures.append(f"{case.base.id}: в реплики хода уехало целое восстановление")
            if turns[0] != "Секунду, ищу.":
                failures.append(f"{case.base.id}: подмена последнего хода задела промежуточный")
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
    # The tuple the record keeps is unchanged when the agent said nothing: a
    # replaced answer must not invent a turn.
    if with_streamed_answer((), "ответ") != ():
        failures.append("подмена последнего хода придумала реплику на пустом прогоне")
    return failures


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("chunked_answer", test_chunked_answer),
        ("corpus_answer_is_what_the_client_read", test_corpus_answer_is_what_the_client_read),
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
