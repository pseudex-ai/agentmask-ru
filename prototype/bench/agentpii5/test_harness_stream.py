"""Стриминговое плечо: восстановление по кускам обязано совпасть с целым.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_harness_stream

THE ONLY TEST OF THIS PACKAGE THAT TOUCHES THE ENGINE, and it does so entirely
in process: `testkit.load_dev_bundle()` for the detection assets, an in-memory
`Vault` for the substitutes, no network, no key, no model. The reply is not
asked of a model — it is WRITTEN out of the substitutes the vault just minted,
because the question here is about the restoration leg and a live model would
only make the input less controlled.

AND IT IS SHOWN TO FAIL. A chunked feed that starts a fresh `StreamDetokenizer`
for every chunk is exactly the bug the carry exists to prevent, and it restores
the WRONG values («Иванова Елизавета» for «Иванова Елена») rather than failing
loudly — which is why `stream_mismatch` is a field of the record and not a
`try`.
"""
from collections.abc import Callable

from bench.agentpii3 import score
from bench.agentpii5.harness import STREAM_CHUNK, restore_stream, stream_verdict
from pseudex.detect_all import Detector
from pseudex.redact import StreamDetokenizer, unmask_text
from pseudex.vault import Vault
from testkit import load_dev_bundle

TEXT: str = "Иванова Елена, +7 916 402-11-87, Ижевск, улица Клубная, 85"


def _minted(detector: Detector, vault: Vault) -> tuple[str, ...]:
    """The substitutes the production masking path minted for one message."""
    masked = score._mask_message(TEXT, detector, vault)
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
    subs = _minted(detector, vault)
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
    restored, mismatch = stream_verdict(raw, vault)
    if restored != whole:
        failures.append("stream_verdict вернул не то, что unmask_text")
    if mismatch:
        failures.append("на чистом случае stream_mismatch выставлен — прибор кричит без повода")
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


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("chunked_answer", test_chunked_answer),
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
