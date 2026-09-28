"""E04/E05 — LOC on the current hop: content from the real entity, form from the
CURRENT SENDER (`docs/tz-hop-form-adaptation.md` §1), and never a hybrid
«подставная улица + реальный дом» (§4.2).

Two RED classes are pinned here, both reproduced through the PUBLIC mask/restore
path with a real ephemeral `Vault` and the real dev bundle — no LLM, no network.

E04 HYBRID. A structured address card shows ONE LOC entity as SEPARATE leaves
(`street`, `house`, `flat`). An agent that reassembles the shown leaves into one
written address gets the REAL house and flat back but keeps the FAKE street —
`ул. Барбарисовая, д. 7, кв. 31`. Reproduced from `tool_chain-017`
(`delivery_create_order`, residual `барбарисовая`).

E05 MARKER/PROSE. The same written string reaches two consumers and they
disagree about the marker: `unmask_arguments` lays the real value into the
agent's own generic, while `unmask_text` hands back the stored vault form — the
real generic in place of the agent's, and the agent's settlement marker
duplicated (`г г Казань, проезд …`). §1 says the form belongs to the current
sender and §4 says the core is shared by arguments and text.

WHAT THIS FILE IS NOT. It asserts the contract, not the engine; a mismatch is a
RED to report, never a new expectation. Every `want` is written literally from
§1/§4.2 and from the real value the vault was shown — never computed by an engine
call. The fake is read at the mint boundary (the `mask_text` output), so no mint
is pinned: nothing here recomputes it.

Run from `prototype/`:

    PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python test_location_hop_form.py
"""

from __future__ import annotations

import json
import re

import testkit

testkit.load_dev_bundle()

from pseudex.detect import Span  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.redact import (mask_text, surviving_substitutes, unmask_arguments,  # noqa: E402
                            unmask_text)
from pseudex.vault import Vault  # noqa: E402

_CHECKS: list[tuple[str, str, object, object]] = []


def _expect(kind: str, name: str, got: object, want: object) -> None:
    _CHECKS.append((kind, name, got, want))


def _vault(customer: str, convo: str) -> Vault:
    return Vault(":memory:", customer).for_conversation(convo)


def _span(text: str, value: str, entity: str = "LOC") -> Span:
    start = text.index(value)
    return Span(start, start + len(value), entity, value)


def _tool(written: str, vault: Vault, key: str = "address") -> str:
    raw = json.dumps({key: written}, ensure_ascii=False)
    restored = json.loads(unmask_arguments(raw, vault))
    if not isinstance(restored, dict) or not isinstance(restored.get(key), str):
        raise AssertionError("LOC tool restoration changed the JSON field type")
    return restored[key]


def _prose(written: str, vault: Vault) -> str:
    return unmask_text(written, vault)


# The real address the vault is shown in every case below. §1 wants this content
# back on both legs; only the FORM may differ, and only the current sender's.
_REAL_FULL = "г Казань, ул Зацепская, д 7, кв 31"
_REAL_PROEZD = "г Казань, проезд Зацепская, д 7, кв 31"

# The structured card of `tool_chain-017` (contacts[].address), kept verbatim:
# one real address, shown to the model as separate leaves.
_CARD = ('{"contacts":[{"address":{"city":"казань","street":"зацепская",'
         '"house":"7","flat":"31"}}]}')


def _success_verbatim() -> None:
    """The control: an agent that COPIES the fake gets the real address whole."""
    vault = _vault("loc-success", "c1")
    text = "адрес: " + _REAL_FULL
    masked = mask_text(text, vault, [_span(text, _REAL_FULL)])
    shown = masked.split(": ", 1)[1]
    _expect("E04/success", "copied fake -> tool gets the real address",
            _tool(shown, vault), _REAL_FULL)
    _expect("E04/success", "copied fake -> prose gets the real address",
            _prose(shown, vault), _REAL_FULL)


def _hybrid_card() -> None:
    """E04 RED: reassembled street+house+flat must not mix fake and real.

    The agent writes `ул. <fake street>, д. <fake house>, кв. <fake flat>` — the
    three leaves it was shown, in one field. The engine restores the two numeric
    leaves (they have their own digit signatures) and leaves the alphabetic
    street fake. §4.2 forbids exactly this hybrid; the whole selected set must
    resolve to one owner.
    """
    spans = Detector().detect(_CARD)
    vault = _vault("loc-hybrid", "c1")
    masked = mask_text(_CARD, vault, spans)
    leaves = json.loads(masked)["contacts"][0]["address"]
    written = f"ул. {leaves['street'].capitalize()}, д. {leaves['house']}, кв. {leaves['flat']}"
    want = "ул. Зацепская, д. 7, кв. 31"  # real content, the agent's markers/order
    _expect("E04/hybrid", "tool: real street, not the fake one (§4.2)",
            _tool(written, vault), want)
    _expect("E04/hybrid", "prose: real street, not the fake one (§4.2)",
            _prose(written, vault), want)
    restored = _tool(written, vault)
    _expect("E04/hybrid", "the real house and flat DO restore (a hybrid, not a no-op)",
            ("7" in restored, "31" in restored), (True, True))
    _expect("E04/hybrid", "no fake part is left as a residual",
            surviving_substitutes(written, restored, vault, True), [])


def _marker_prose() -> None:
    """E05 RED: the prose leg must take its marker from the current sender.

    The agent rewrites the fake's generic (`проезд` -> `улица`) in its own
    sentence. The tool leg honours that; the prose leg returns the STORED form,
    re-inserting `проезд` and duplicating the settlement marker.
    """
    vault = _vault("loc-marker", "c1")
    text = "адрес: " + _REAL_PROEZD
    shown = mask_text(text, vault, [_span(text, _REAL_PROEZD)]).split(": ", 1)[1]
    written = shown.replace("проезд", "улица", 1)  # the agent's own generic word
    want = "г Казань, улица Зацепская, д 7, кв 31"
    _expect("E05/marker", "tool keeps the agent's generic word",
            _tool(written, vault), want)
    _expect("E05/marker", "prose keeps the agent's generic word (§1)",
            _prose(written, vault), want)
    _expect("E05/marker", "the agent's settlement marker is not duplicated",
            _prose(written, vault).count("Казань"), 1)


def _two_addresses() -> None:
    """§4.2 control: two addresses are resolved INDEPENDENTLY.

    Both name the same street but different houses. Each full fake must restore
    its own house; the street alone must claim neither.
    """
    vault = _vault("loc-two", "c1")
    address_a = "казань зацепская 7 кв 31"
    address_b = "казань зацепская 9 кв 32"
    text = f"отправка: {address_a}; доставка: {address_b}"
    masked = mask_text(text, vault, [_span(text, address_a), _span(text, address_b)])
    fake_a = masked.split("отправка: ", 1)[1].split(";", 1)[0]
    fake_b = masked.split("доставка: ", 1)[1]
    _expect("CTRL/two-address", "A resolves to its own house",
            _tool(fake_a, vault), address_a)
    _expect("CTRL/two-address", "B resolves to its own house",
            _tool(fake_b, vault), address_b)
    bare_street = re.sub(r"\s*\d+.*$", "", fake_a).strip()
    _expect("CTRL/two-address", "a street shared by two addresses names no house",
            bool(re.search(r"\d", _tool(bare_street, vault))), False)


def _negatives() -> None:
    """A number that is not an address, and prose around a masked field, stay."""
    vault = _vault("loc-neg", "c1")
    _expect("CTRL/negative", "a measured quantity is not an address",
            _tool("2 гектаров", vault), "2 гектаров")
    _expect("CTRL/negative", "numbers in a sentence stay",
            _prose("Заказ 42; скидка 10%; осталось 3 места", vault),
            "Заказ 42; скидка 10%; осталось 3 места")


def _declension() -> None:
    """E05 RED: a non-dictionary adjectival street must still decline.

    «Зацепская» is absent from OpenCorpora, so the street came back nominative
    while the agent's generic word was already locative — «на улице Зацепская»
    is broken Russian. The real street must agree with the declined generic.
    """
    from unittest.mock import patch
    vault = _vault("loc-decl", "c1")
    text = "адрес: " + _REAL_FULL
    with patch("pseudex.vault._fake_place",
               return_value="г Казань, улица Кедровая, д 2, кв 5"):
        mask_text(text, vault, [_span(text, _REAL_FULL)])
    written = "Живу на улице Кедровой, д 2"   # the agent declined the fake street
    want = "Живу на улице Зацепской, д 7"     # the real street agrees
    _expect("E05/declension", "prose: the real street agrees with the declined generic",
            _prose(written, vault), want)
    _expect("E05/declension", "tool: the real street agrees with the declined generic",
            _tool("на улице Кедровой, д 2", vault), "на улице Зацепской, д 7")


def main() -> int:
    testkit.load_dev_bundle()
    _success_verbatim()
    _hybrid_card()
    _marker_prose()
    _two_addresses()
    _negatives()
    _declension()

    failures = [check for check in _CHECKS if check[2] != check[3]]
    for kind, name, got, want in failures:
        print(f"RED [{kind}] {name}\n    got  {got!r}\n    want {want!r}")
    print()
    print(f"location_hop_form: {len(_CHECKS) - len(failures)}/{len(_CHECKS)} "
          f"contract checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
