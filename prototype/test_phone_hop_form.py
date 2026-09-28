"""Current-hop PHONE form on the real mask/restore paths, without an LLM."""

import json
import re
from collections.abc import Callable
from unittest.mock import patch

import testkit
from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.envelope import MaskContext, mask_messages
from pseudex.maskcache import MaskCache
from pseudex.redact import mask_text, residual_tokens, unmask_arguments, unmask_text
from pseudex.vault import Vault, canonicalize

ORG: str = "phone-hop-envelope"
USER_PHONE: str = "8 (916) 214-88-03"
RESULT_PHONE: str = "+79162148803"
FAKE_PHONE: str = "+79795553322"


def _context(conversation: str, detector: Detector,
             cache: MaskCache | None = None) -> MaskContext:
    return MaskContext(detector=detector, vault=Vault(":memory:", ORG).for_conversation(conversation),
                       audit=AuditLog(":memory:"), cache=cache or MaskCache(256),
                       org_id=ORG, agent_id="phone-hop", conversation_id=conversation)


def _result_body(phone: str) -> str:
    return json.dumps({"error": {"message": f"phone_not_e164: {phone}"}}, ensure_ascii=False)


def _hop_transcript(leaf: str, echoed: str) -> list[dict[str, object]]:
    return [
        {"role": "user", "content": "телефон " + USER_PHONE + " звоните"},
        {"role": "assistant", "tool_calls": [
            {"id": "hop-1", "type": "function",
             "function": {"name": "find", "arguments": json.dumps({"phone": leaf},
                                                                   ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "hop-1", "content": _result_body(echoed)},
    ]


def _masked_hop(context: MaskContext, leaf: str, echoed: str) -> tuple[str, str]:
    masked = mask_messages([dict(message) for message in _hop_transcript(leaf, echoed)],
                           context, False)
    calls = masked[1]["tool_calls"]
    if not isinstance(calls, list) or not isinstance(calls[0], dict):
        raise AssertionError("the masked call lost its shape")
    visible: object = json.loads(str(calls[0]["function"]["arguments"])).get("phone")
    result: object = masked[-1]["content"]
    if not isinstance(visible, str) or not isinstance(result, str):
        raise AssertionError("a masked leaf changed its wire type")
    return visible, result


def _warm_hop(context: MaskContext, user_message: str,
              leaf: str, echoed: str) -> tuple[str, str]:
    """The production two-request read: the USER turn already minted the row, and
    the result is read on the next request with the row in the frozen snapshot."""
    masked = mask_messages([
        {"role": "user", "content": user_message},
        {"role": "assistant", "tool_calls": [
            {"id": "warm-1", "type": "function",
             "function": {"name": "find", "arguments": json.dumps({"phone": leaf},
                                                                  ensure_ascii=False)}}]},
        {"role": "tool", "tool_call_id": "warm-1", "content": _result_body(echoed)},
    ], context, False)
    calls = masked[1]["tool_calls"]
    if not isinstance(calls, list) or not isinstance(calls[0], dict):
        raise AssertionError("the masked warm call lost its shape")
    visible: object = json.loads(str(calls[0]["function"]["arguments"])).get("phone")
    result: object = masked[-1]["content"]
    if not isinstance(visible, str) or not isinstance(result, str):
        raise AssertionError("a masked warm leaf changed its wire type")
    return visible, result


WARM_8_MINT: str = "8 968 929 95 73"
WARM_7_MINT: str = "+79689299573"


def envelope_phone_hop(detector: Detector) -> int:
    """`long_order-058`: one identity, `8 …` for the user and `+7…` for the tool.

    The mask/restore helpers below read one leaf at a time; this exercises the
    SHARED envelope both entry points call (`proxy.py` and `service.py` both go
    through `envelope.mask_messages`), because the form of a result is decided
    there — the call's current rendering is applied to the ORIGINAL result span
    before the detector can answer with the mint's own notation. The assertions
    are comparisons between the model-visible call leaf and the result
    replacement, so they do not restate a substitute."""
    checks: int = 0
    stored: str = "8 (979) 555-33-22"
    lanes: tuple[tuple[str, str, str], ...] = (
        ("E.164 leaf, +7 result", FAKE_PHONE, RESULT_PHONE),
        ("domestic leaf, +7 result", stored, RESULT_PHONE),
        ("E.164 leaf, flat 8 result", FAKE_PHONE, "89162148803"),
    )
    for label, leaf, echoed in lanes:
        context: MaskContext = _context("hop-" + label, detector)
        with patch("pseudex.vault._fake_phone", return_value=FAKE_PHONE):
            visible, result = _masked_hop(context, leaf, echoed)
        rendered: str = result[result.index("phone_not_e164: ") + len("phone_not_e164: "):-3]
        assert visible == leaf, f"{label}: the model reads the call it wrote"
        assert echoed not in result, f"{label}: the real result digits leaked"
        assert "++" not in result, f"{label}: a doubled country code was written: {result!r}"
        # THE RESULT'S OWN NOTATION, not the user's earlier one and not the call
        # leaf's: `long_order-058` is the defect where a `+7…` result came back in
        # the user's `8 …` form.
        leading: str = "8" if echoed.startswith("8") else "+7"
        assert rendered.startswith(leading), (
            f"{label}: the result must keep its own notation, rendered={rendered!r}")
        assert stored not in result, f"{label}: the user's earlier form was imported: {result!r}"
        assert canonicalize("PHONE", rendered) == canonicalize("PHONE", FAKE_PHONE), (
            f"{label}: the result names a different phone: {rendered!r}")
        checks += 6
    # THE CACHE MUST NOT RETURN ANOTHER MENTION'S FORM. The same store is warmed
    # by the USER turn — whose cached rendering is the `8 (979) 555-33-22` the
    # dialogue minted — and the result body is then read on that warm cache in
    # both orders (bound call first, unbound first) and twice in a row. A cache
    # key that ignored the call's evidence, or a content key that ignored the
    # text, would serve the user's form or freeze the first reading.
    for order, bound_first in (("bound-first", True), ("plain-first", False)):
        context = _context(f"hop-cache-{order}", detector)
        with patch("pseudex.vault._fake_phone", return_value=FAKE_PHONE):
            mask_text("телефон " + USER_PHONE + " звоните", context.vault,
                      detector.detect("телефон " + USER_PHONE + " звоните"))

            def _plain() -> str:
                read = mask_messages(
                    [{"role": "tool", "name": "find", "content": _result_body(RESULT_PHONE)}],
                    context, False)[0]["content"]
                if not isinstance(read, str):
                    raise AssertionError("the unbound result changed its wire type")
                return read

            if bound_first:
                first: str = _masked_hop(context, FAKE_PHONE, RESULT_PHONE)[1]
                again: str = _masked_hop(context, FAKE_PHONE, RESULT_PHONE)[1]
                plain: str = _plain()
            else:
                plain = _plain()
                first = _masked_hop(context, FAKE_PHONE, RESULT_PHONE)[1]
                again = _masked_hop(context, FAKE_PHONE, RESULT_PHONE)[1]
        assert RESULT_PHONE not in first and RESULT_PHONE not in plain, "a real digit leaked"
        assert first == again, "a cache hit changed the result's form"
        assert stored not in first, f"the user's earlier form reached the result: {first!r}"
        assert FAKE_PHONE in first, f"the bound result lost the current form: {first!r}"
        assert stored not in plain, f"the unbound result imported the user's form: {plain!r}"
        checks += 4
    return checks


def envelope_warm_notation(detector: Detector) -> int:
    """E01 on the WARM path, where the row already exists.

    `envelope_phone_hop` above forces the substitute to E.164 and reads the whole
    transcript in ONE pass, so on every one of its lanes the frozen rendering
    snapshot is taken before the row this pass mints exists. That is the COLD
    case. `long_order-058` is the other one and the normal multi-turn one: the
    USER turn has already minted the substitute, the tool answers in its own
    notation, and the result is read on the next request. The row is then part of
    the frozen snapshot, `as_is` is true, and the echo leg returned the row's own
    string verbatim — the user's `8 …` form for a `+7…` result, and the mirror.
    Both directions are driven here with the mint's notation stated by the patch,
    and the identical read is repeated so the cache/pass-order clause is measured
    too (`first == again`)."""
    checks: int = 0
    cases: tuple[tuple[str, str, str, str, str], ...] = (
        # label, the minted identity as `_fake_phone` returns it, the USER's own
        # notation (which the row mirrors), the USER's literal, and the tool's
        # echo in ITS OWN notation
        ("8-mint, +7 result", WARM_8_MINT, "8", "8 988 999 09 49", "+7 988 999 09 49"),
        ("+7-mint, 8 result", WARM_7_MINT, "+7", "+7 988 999 09 49", "8 988 999 09 49"),
    )
    for label, mint, user_leading, user_literal, echoed in cases:
        context: MaskContext = _context("warm-" + label, detector)
        user_message: str = "телефон " + user_literal + " звоните"
        with patch("pseudex.vault._fake_phone", return_value=mint):
            mask_messages([{"role": "user", "content": user_message}], context, False)
            rows: list[tuple[str, str]] = [(shown, original) for shown, original, kind
                                           in context.vault.shown_forms() if kind == "PHONE"]
            assert rows, f"{label}: the user turn minted no PHONE row"
            minted: str = rows[-1][0]
            # The ROW mirrors the user's notation, which is the axis under test.
            assert canonicalize("PHONE", minted) == canonicalize("PHONE", mint), (
                f"{label}: the fixture minted another identity: {minted!r}")
            assert minted.startswith(user_leading), (
                f"{label}: the row did not take the user's notation: {minted!r}")
            visible, first = _warm_hop(context, user_message, minted, echoed)
            _visible_again, again = _warm_hop(context, user_message, minted, echoed)
        rendered: str = first[first.index("phone_not_e164: ") + len("phone_not_e164: "):-3]
        assert visible == minted, f"{label}: the model reads the call it wrote"
        assert "9889990949" not in re.sub(r"\D", "", first), (
            f"{label}: the real result digits leaked: {first!r}")
        assert "+8" not in first and "++" not in first, (
            f"{label}: a doubled country code was written: {first!r}")
        # THE RESULT'S OWN NOTATION, with the row already minted.
        leading: str = "8" if echoed.startswith("8") else "+7"
        assert rendered.startswith(leading), (
            f"{label}: the warm result must keep its own notation, rendered={rendered!r}")
        assert minted not in first, (
            f"{label}: the mint's own notation was returned verbatim: {first!r}")
        assert user_literal not in first, (
            f"{label}: the user's earlier form was imported: {first!r}")
        assert canonicalize("PHONE", rendered) == canonicalize("PHONE", minted), (
            f"{label}: the result names a different phone: {rendered!r}")
        assert first == again, f"{label}: a repeat of the identical read changed the form"
        checks += 8
    return checks


def international(digits: str) -> str:
    return "+7" + digits[-10:]


def domestic(digits: str) -> str:
    tail: str = digits[-10:]
    return f"8 ({tail[:3]}) {tail[3:6]}-{tail[6:8]}-{tail[8:]}"


def local(digits: str) -> str:
    return digits[-10:]


def grouped(digits: str) -> str:
    tail: str = digits[-10:]
    return f"+7 {tail[:3]} {tail[3:6]} {tail[6:8]} {tail[8:]}"


def tool_value(written: str, vault: Vault) -> str:
    restored: object = json.loads(unmask_arguments(json.dumps({"phone": written}), vault))
    if not isinstance(restored, dict) or not isinstance(restored.get("phone"), str):
        raise AssertionError("PHONE tool restoration changed the JSON field type")
    return restored["phone"]


def answer_value(written: str, vault: Vault) -> str:
    return unmask_text(written, vault)


def regression_controls(detector: Detector) -> int:
    """Protect copied spelling, typed numeric lookup and separate identities."""
    checks: int = 0
    literal: str = "8 916 214-88-О3"
    vault: Vault = Vault(":memory:", "phone-controls").for_conversation("one")
    with patch("pseudex.vault._fake_phone", return_value="+79795553322"):
        shown: str = mask_text(literal, vault, detector.detect(literal))
    assert tool_value(shown, vault) == literal, "Copied homoglyph was normalized"
    assert answer_value(shown, vault) == literal, "Copied answer lost its homoglyph"
    checks += 2

    pair_vault: Vault = Vault(":memory:", "two-phones").for_conversation("pair")
    with patch("pseudex.vault._fake_phone", side_effect=("+79795553322", "+79865554433")):
        mask_text("+79162148803", pair_vault, detector.detect("+79162148803"))
        mask_text("+79261234567", pair_vault, detector.detect("+79261234567"))
    written: str = "Первый: +79795553322; второй: 8 (986) 555-44-33."
    expected: str = "Первый: +79162148803; второй: 8 (926) 123-45-67."
    assert answer_value(written, pair_vault) == expected, "Two PHONE identities mixed"
    checks += 1

    other: Vault = Vault(":memory:", "other-tenant").for_conversation("pair")
    assert answer_value(written, other) == written, "A token resolved in an unrelated tenant"
    checks += 1

    documents: Vault = Vault(":memory:", "documents").for_conversation("one")
    with patch("pseudex.vault._fake_snils", return_value="805-387-569 27"):
        documents.tokenize("112-233-445 22", "SNILS")
    typed: dict[str, tuple[str, str]] = documents.resolve_digit_signatures_typed({"80538756927"}, True)
    assert typed["80538756927"][0] == "SNILS", "Numeric lookup lost its type"
    assert tool_value("80538756927", documents) == "11223344522", "SNILS took the phone prefix rule"
    assert answer_value("805-387-569 27", documents) == "112-233-445 22", "SNILS answer changed"
    checks += 3
    reused: Vault = Vault(":memory:", "phone-reuse").for_conversation("one")
    with patch("pseudex.vault._fake_phone", return_value="+79795553322"):
        first = "8 (916) 214-88-03"
        shown_first = mask_text(first, reused, detector.detect(first))
        assert shown_first == "8 (979) 555-33-22", shown_first
        second = "+79162148803"
        shown_second = mask_text(second, reused, detector.detect(second))
        assert shown_second == "+79795553322", "A later result inherited the user's earlier form"
        assert tool_value(shown_first, reused) == first, "Earlier presentation lost its literal"
        assert tool_value(shown_second, reused) == second, "Result copy inherited earlier notation"
    checks += 4
    return checks


def extended_phone_is_not_partially_restored(detector: Detector) -> int:
    """An extra agent digit must not splice a real prefix into a fake number.

    The digit may sit at the END (the suffix the first version caught), at the
    FRONT, or INSIDE the known fake; every position must come back unchanged on
    both legs and be flagged residual, never a real/fake hybrid.
    """
    vault: Vault = Vault(":memory:", "extended-phone").for_conversation("one")
    with patch("pseudex.vault._fake_phone", return_value=FAKE_PHONE):
        source = "+79162148803"
        assert mask_text(source, vault, detector.detect(source)) == FAKE_PHONE
    altered: tuple[str, ...] = (
        "+797955533221",          # suffix, +7 form
        "8 (979) 555-33-221",     # suffix, domestic grouped (8 + last ten + one)
        "979795553322",           # one digit BEFORE the known fake
        "879795553322",           # prefix digit after an 8 country code
        "8 797 955 533 22",       # prefix digit, grouped
        "+797955533292",          # one digit INSERTED inside the known fake
    )
    checks = 0
    for written in altered:
        for consume in (tool_value, answer_value):
            actual = consume(written, vault)
            assert actual == written, (
                f"{consume.__name__}: unsupported extra digit made a hybrid: {actual!r}")
            checks += 1
        assert residual_tokens(tool_value(written, vault), vault), (
            f"a known fake with one added digit reached the tool silently: {written!r}")
        checks += 1
    ordinary = "+791234567890"
    assert tool_value(ordinary, vault) == ordinary
    assert answer_value(ordinary, vault) == ordinary
    assert not residual_tokens(ordinary, vault)
    return checks + 3


def main() -> int:
    testkit.load_dev_bundle()
    detector: Detector = Detector()
    sources: tuple[tuple[str, str], ...] = (
        ("8 (916) 214-88-03", "79162148803"),
        ("+7 916 214 88 03", "79162148803"),
        ("восемь девятьсот пятьдесят ноль шесть сорок ноль один семь", "79500640017"),
    )
    styles: tuple[Callable[[str], str], ...] = (international, domestic, local, grouped)
    consumers: tuple[Callable[[str, Vault], str], ...] = (tool_value, answer_value)
    fake_digits: str = "79795553322"
    failed: int = 0
    checked: int = 0
    for source, real_digits in sources:
        vault: Vault = Vault(":memory:", "phone-hop").for_conversation("one")
        text: str = "Телефон " + source
        with patch("pseudex.vault._fake_phone", return_value="+" + fake_digits):
            masked: str = mask_text(text, vault, detector.detect(text))
        if source in masked or canonicalize("PHONE", masked.removeprefix("Телефон ")) != "+" + fake_digits:
            raise AssertionError(f"PHONE fixture did not cross the real mask path: {source!r}")
        for render in styles:
            written: str = render(fake_digits)
            expected: str = render(real_digits)
            for consume in consumers:
                actual: str = consume(written, vault)
                checked += 1
                if actual != expected:
                    failed += 1
                    print(f"FAIL {consume.__name__}/{render.__name__}: source={source!r} "
                          f"written={written!r} expected={expected!r} actual={actual!r}")
        if unmask_text("Заказ 42; скидка 10%; осталось 3 места", vault) != "Заказ 42; скидка 10%; осталось 3 места":
            raise AssertionError("Unrelated quantities were rewritten")
    print(f"phone_hop_form: {checked - failed}/{checked} value+form checks passed; "
          "ordinary-quantity controls passed")
    controls: int = regression_controls(detector)
    print(f"phone_hop_form: {controls}/{controls} additional regression controls passed")
    extended: int = extended_phone_is_not_partially_restored(detector)
    print(f"phone_hop_form: {extended}/{extended} extended-token controls passed")
    hops: int = envelope_phone_hop(detector)
    print(f"phone_hop_form: {hops}/{hops} shared-envelope current-form hops passed")
    warm: int = envelope_warm_notation(detector)
    print(f"phone_hop_form: {warm}/{warm} warm two-request notation hops passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
