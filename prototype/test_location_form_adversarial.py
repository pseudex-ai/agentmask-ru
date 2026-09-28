"""LOC hop form — INDEPENDENT adversarial review of the current candidate.

This file is an attack, not a restatement. It exercises the invariants the LOC
candidate claims to hold — content from the real entity, form from the CURRENT
SENDER (`docs/tz-hop-form-adaptation.md` §1), never a hybrid of a fake street
and a real house/flat (§4.2), and the same core on the argument and the prose
leg (§4) — through the PUBLIC `mask_text` / `unmask_text` / `unmask_arguments`
with a real ephemeral `Vault` and the real dev bundle. No LLM, no network.

Every `want` is written LITERALLY from the real value the vault was shown and
from §1/§4.2; none is computed by an engine call. The mint is random, so the
fake is READ at the mint boundary (`mask_text` / `Vault.tokenize` output) and
never pinned.

The one non-textual fixture is the short/full link of `test_product.py`
(`Vault.tokenize`), reproduced here because that is the public path the shipped
test uses; the assertions still go through `unmask_text` / `unmask_arguments`.

A mismatch is a RED to report, never a new expectation: do not weaken an
assertion to make the engine green.

Run from `prototype/`:

    PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python test_location_form_adversarial.py
"""

from __future__ import annotations

import json
import re

import testkit

testkit.load_dev_bundle()

from pseudex import morph_places  # noqa: E402
from pseudex.detect import Span  # noqa: E402
from pseudex.redact import (mask_text, surviving_substitutes, unmask_arguments,  # noqa: E402
                            unmask_text)
from pseudex.vault import Vault  # noqa: E402

_CHECKS: list[tuple[str, str, object, object]] = []


def _expect(kind: str, name: str, got: object, want: object) -> None:
    _CHECKS.append((kind, name, got, want))


def _vault(customer: str, convo: str = "c1") -> Vault:
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


def _bare(street: str) -> str:
    """The street role without the leading generic word («улица Зацепская» -> «Зацепская»)."""
    words = street.split()
    while words and morph_places.is_generic_word(words[0]):
        words.pop(0)
    return " ".join(words)


def _fake(real: str, vault: Vault, prefix: str = "адрес: ") -> str:
    """The substitute the model is shown for `real`, read at the mint boundary."""
    text = prefix + real
    return mask_text(text, vault, [_span(text, real)]).split(prefix, 1)[1]


def _roles(real: str, vault: Vault) -> tuple[str, dict[str, str]]:
    fake = _fake(real, vault)
    return fake, morph_places.split_roles(fake)


# The real address behind the marker/case/hybrid cases below. Its street marker
# is the FULL word «улица»: the same-kind abbreviation controls intentionally do
# NOT touch «улица» vs «проезд» — whether the kind of a street is content or
# form is an unresolved semantic policy, so this file does not encode either
# reading. Only ulitsa/ul. (one kind, two spellings) is asserted.
_REAL = "г Казань, улица Зацепская, д 7, кв 31"


# --------------------------------------------------------------------------- #
# R0 — the shipped `test_product.py::test_short_address_resolves_to_the_full_one`
#      regression. The customer wrote «Ленина 14»; the FULL address elsewhere in
#      the conversation had a type word, so the link's substitute carries one.
#      §1 says the short mention restores as WRITTEN, so no «ул.» may be added.
# --------------------------------------------------------------------------- #
_REAL_LENINA = "г. Москва, ул. Ленина, д. 14"
_WANT_SHORT_PROSE = "адрес Ленина 14"
_WANT_SHORT_TOOL = "Ленина 14"


def _short_link(full_via: str) -> None:
    talk = Vault(":memory:", "loc-short-" + full_via).for_conversation("dialog-1")
    if full_via == "mask":
        mask_text(_REAL_LENINA, talk, [_span(_REAL_LENINA, _REAL_LENINA)])
    else:
        talk.tokenize(_REAL_LENINA, "LOC")
    short = talk.tokenize("Ленина 14", "LOC")
    _expect("R0/link", f"precondition ({full_via}): the link mirrors the full fake's marker",
            bool(re.search(r"(?i)(ул\.|улица|ул\b)", short)), True)
    _expect("R0/link", f"prose restores exactly what the short mention wrote ({full_via} mint)",
            _prose(f"адрес {short}", talk), _WANT_SHORT_PROSE)
    _expect("R0/link", f"tool restores exactly what the short mention wrote ({full_via} mint)",
            _tool(short, talk), _WANT_SHORT_TOOL)


def _r0_short_address() -> None:
    _short_link("mask")
    _short_link("tokenize")


# --------------------------------------------------------------------------- #
# R1 — dropped street marker + prose. The agent wrote the whole address but
#      without the type word. The WRITTEN form is bare, so content must come
#      back bare; the real house and flat must not be mixed with the fake street
#      and fake house. `_restore_inflected_spans` resolves the composite span
#      correctly; `_unmask` discards it (the `place_owner` guard in the reorder)
#      and the prose-only cued-number pass then splices a REAL flat under the
#      FAKE street — the §4.2 hybrid.
# --------------------------------------------------------------------------- #
def _r1_dropped_marker() -> None:
    vault = _vault("loc-r1")
    fake, roles = _roles(_REAL, vault)
    written = f"г {roles['city']}, {_bare(roles['street'])}, д {roles['house']}, кв {roles['flat']}"
    want = "г Казань, Зацепская, д 7, кв 31"
    _expect("R1/priority", "tool: real street, house and flat in the agent's bare form",
            _tool(written, vault), want)
    _expect("R1/priority", "prose: real street, house and flat — no fake street over a real flat",
            _prose(written, vault), want)
    _expect("R1/priority", "argument and prose agree on the whole address",
            _tool(written, vault), _prose(written, vault))
    _expect("R1/priority", "no fake part stands in the restored tool value",
            surviving_substitutes(written, _tool(written, vault), vault, True), [])


# --------------------------------------------------------------------------- #
# R2 — lower-case street. The same seam, reached by the agent's case alone:
#      the resolver resolves the whole composite, the cued-number pass steals
#      the flat first, and the prose leg keeps the fake street and fake house.
# --------------------------------------------------------------------------- #
def _r2_lower_case() -> None:
    vault = _vault("loc-r2")
    fake, roles = _roles(_REAL, vault)
    name = _bare(roles["street"])
    written = (f"г {roles['city'].lower()}, улица {name.lower()}, "
               f"д {roles['house']}, кв {roles['flat']}")
    want = "г казань, улица зацепская, д 7, кв 31"
    _expect("R2/case", "tool: the real address in the agent's letter case",
            _tool(written, vault), want)
    _expect("R2/case", "prose: the real address in the agent's letter case",
            _prose(written, vault), want)
    _expect("R2/case", "argument and prose agree on the whole address",
            _tool(written, vault), _prose(written, vault))


# --------------------------------------------------------------------------- #
# R3 — upper-case street. Here the resolver itself loses CONTENT: the real city
#      is dropped and the real street is spliced into the city slot, because
#      `role_spans` does not read an all-caps settlement as a city. §4.2 forbids
#      taking a part from another role; §1 forbids losing the real city.
# --------------------------------------------------------------------------- #
def _r3_upper_case() -> None:
    vault = _vault("loc-r3")
    fake, roles = _roles(_REAL, vault)
    name = _bare(roles["street"])
    written = (f"г {roles['city'].upper()}, улица {name.upper()}, "
               f"д {roles['house']}, кв {roles['flat']}")
    want = "г КАЗАНЬ, улица ЗАЦЕПСКАЯ, д 7, кв 31"
    _expect("R3/case", "tool: the real CITY survives an all-caps mention",
            _tool(written, vault), want)
    _expect("R3/case", "prose: the real CITY survives an all-caps mention",
            _prose(written, vault), want)


# --------------------------------------------------------------------------- #
# R4 — a street-less fragment. §4.2: a role the agent did not write is not
#      added; a role it did write is filled with the real part. The tool leg
#      hands back the WHOLE real address for a lone flat, and appends it whole
#      after a house+flat fragment — the opposite of both halves of the rule.
# --------------------------------------------------------------------------- #
def _r4_streetless_fragment() -> None:
    vault = _vault("loc-r4")
    fake, roles = _roles(_REAL, vault)
    flat_only = f"кв {roles['flat']}"
    _expect("R4/fragment", "tool: a lone flat restores as a flat, not the whole address",
            _tool(flat_only, vault), "кв 31")
    _expect("R4/fragment", "prose: a lone flat restores as a flat",
            _prose(flat_only, vault), "кв 31")
    _expect("R4/fragment", "argument and prose agree on a lone flat",
            _tool(flat_only, vault), _prose(flat_only, vault))

    house_flat = f"д {roles['house']}, кв {roles['flat']}"
    _expect("R4/fragment", "tool: house+flat restores both parts and adds neither city nor street",
            _tool(house_flat, vault), "д 7, кв 31")
    _expect("R4/fragment", "prose: house+flat restores both parts",
            _prose(house_flat, vault), "д 7, кв 31")
    _expect("R4/fragment", "argument and prose agree on house+flat",
            _tool(house_flat, vault), _prose(house_flat, vault))


# --------------------------------------------------------------------------- #
# F — two addresses in one text. They share the real street; the mint gives
#     them the SAME fake street (measured), and only house/flat tell them apart.
#     §4.2: each resolves independently, a street alone names no house, and one
#     mention's ambiguity never donates a part of the other.
# --------------------------------------------------------------------------- #
def _two_addresses() -> None:
    vault = _vault("loc-two")
    a = "казань зацепская 7 кв 31"
    b = "казань зацепская 9 кв 32"
    text = f"отправка: {a}; доставка: {b}"
    masked = mask_text(text, vault, [_span(text, a), _span(text, b)])
    fake_a = masked.split("отправка: ", 1)[1].split(";", 1)[0]
    fake_b = masked.split("доставка: ", 1)[1]
    roles_a, roles_b = morph_places.split_roles(fake_a), morph_places.split_roles(fake_b)

    _expect("CTRL/two", "A restores to its own house (tool)", _tool(fake_a, vault), a)
    _expect("CTRL/two", "B restores to its own house (tool)", _tool(fake_b, vault), b)
    _expect("CTRL/two", "A restores to its own house (prose)", _prose(fake_a, vault), a)
    _expect("CTRL/two", "B restores to its own house (prose)", _prose(fake_b, vault), b)

    bare = _bare(roles_a["street"])
    _expect("CTRL/two", "a street shared by two addresses names no house (tool)",
            bool(re.search(r"\d", _tool(bare, vault))), False)
    _expect("CTRL/two", "a street shared by two addresses names no house (prose)",
            bool(re.search(r"\d", _prose(bare, vault))), False)

    # A the street+house of A with the flat of B: the two mentions must not be
    # welded into one, and B's whole address must not appear in A's field.
    cross = f"г {roles_a['city']}, {roles_a['street']}, д {roles_a['house']}, кв {roles_b['flat']}"
    _expect("F/two", "a cross-mixed mention does not leak the OTHER address whole (tool)",
            b in _tool(cross, vault), False)
    # Contradictory owners cannot be made correct by forcing residual=0.
    # Keep the unresolved mention intact and expose it through the existing
    # residual diagnostic; neither a foreign whole nor a hybrid is acceptable.
    _expect("F/two", "conflicting parts remain unresolved as a whole (tool)",
            _tool(cross, vault), cross)
    _expect("F/two", "conflicting parts remain unresolved as a whole (prose)",
            _prose(cross, vault), cross)
    _expect("F/two", "conflicting parts are visible to the residual diagnostic",
            bool(surviving_substitutes(cross, _prose(cross, vault), vault, False)), True)


# --------------------------------------------------------------------------- #
# Controls (expected GREEN). They pin what the candidate is not allowed to
# trade away while fixing the REDs above.
# --------------------------------------------------------------------------- #
def _controls_verbatim_and_scope() -> None:
    vault = _vault("loc-ctrl-verbatim")
    fake = _fake(_REAL, vault)
    _expect("CTRL/verbatim", "a copied fake restores to the real address (tool)",
            _tool(fake, vault), _REAL)
    _expect("CTRL/verbatim", "a copied fake restores to the real address (prose)",
            _prose(fake, vault), _REAL)

    base = Vault(":memory:", "loc-ctrl-scope")
    here, elsewhere = base.for_conversation("convA"), base.for_conversation("convB")
    fake = _fake(_REAL, here)
    roles = morph_places.split_roles(fake)
    for label, written in (("bare street", _bare(roles["street"])),
                           ("street+house", f"{_bare(roles['street'])} {roles['house']}")):
        _expect("CTRL/scope", f"a {label} fragment stays fake in another conversation (tool)",
                _tool(written, elsewhere), written)
        _expect("CTRL/scope", f"a {label} fragment stays fake in another conversation (prose)",
                _prose(written, elsewhere), written)


def _controls_unknown_street() -> None:
    vault = _vault("loc-ctrl-unknown")
    # The real house is 7 and the real flat is 31. A number that is NOT ours
    # must never be replaced by one that is, however address-shaped the sentence.
    for written in ("г Казань, улица Незнакомая, д 3, кв 3",
                    "улица Незнакомая, д 31",
                    "улица Незнакомая 999"):
        want = re.sub(r"\d+", "?", written)
        _expect("CTRL/unknown", f"unknown-street value stays put (tool): {written!r}",
                re.sub(r"\d+", "?", _tool(written, vault)), want)
        _expect("CTRL/unknown", f"unknown-street value stays put (prose): {written!r}",
                re.sub(r"\d+", "?", _prose(written, vault)), want)
    _expect("CTRL/unknown", "a measured quantity is not an address (tool)",
            _tool("2 гектаров", vault), "2 гектаров")


def _controls_literal_typos() -> None:
    for label, real in (
        ("typo in the type word", "г Казань, улца Зацепская, д 7, кв 31"),
        ("transposed street letters", "г Казань, улица Зацепксая, д 7, кв 31"),
        ("latin look-alike in the street", "г Казань, улица Зацепcкая, д 7, кв 31"),
        ("latin look-alike in the flat", "г Казань, улица Зацепская, д 7, кв 3l"),
    ):
        vault = _vault("loc-typo-" + label.replace(" ", "-"))
        fake = _fake(real, vault)
        _expect("CTRL/typo", f"a copied fake returns the original exactly ({label}, tool)",
                _tool(fake, vault), real)
        _expect("CTRL/typo", f"a copied fake returns the original exactly ({label}, prose)",
                _prose(fake, vault), real)


def _controls_same_kind_marker() -> None:
    # Same KIND, two spellings: the current sender's spelling wins. «улица» vs
    # «проезд» is deliberately NOT asserted — that is a semantic question.
    cases = (
        ("г Казань, улица Зацепская, д 7, кв 31", "ул.", "г Казань, ул. Зацепская, д 7, кв 31"),
        ("г Казань, ул Зацепская, д 7, кв 31", "улица", "г Казань, улица Зацепская, д 7, кв 31"),
        ("г Казань, ул. Зацепская, д 7, кв 31", "улица", "г Казань, улица Зацепская, д 7, кв 31"),
    )
    for index, (real, marker, want) in enumerate(cases):
        vault = _vault(f"loc-marker-{index}")
        fake, roles = _roles(real, vault)
        name = _bare(roles["street"])
        written = f"г {roles['city']}, {marker} {name}, д {roles['house']}, кв {roles['flat']}"
        _expect("CTRL/marker", f"the agent's abbreviation is kept ({marker!r}, tool)",
                _tool(written, vault), want)
        _expect("CTRL/marker", f"the agent's abbreviation is kept ({marker!r}, prose)",
                _prose(written, vault), want)


def _controls_copied_fragments() -> None:
    vault = _vault("loc-ctrl-frag")
    fake = _fake(_REAL, vault)
    roles = morph_places.split_roles(fake)
    name, house, flat = _bare(roles["street"]), roles["house"], roles["flat"]
    cases = (
        ("bare street", name, "Зацепская"),
        ("street+type", f"улица {name}", "улица Зацепская"),
        ("street+house", f"{name} {house}", "Зацепская 7"),
        ("city+street", f"{roles['city']}, улица {name}", "Казань, улица Зацепская"),
    )
    for label, written, want in cases:
        _expect("CTRL/fragment", f"copied {label} restores its own part (tool)",
                _tool(written, vault), want)
        _expect("CTRL/fragment", f"copied {label} restores its own part (prose)",
                _prose(written, vault), want)


def _controls_role_and_cue() -> None:
    vault = _vault("loc-role-and-cue")
    fake, roles = _roles(_REAL, vault)
    house, flat = roles["house"], roles["flat"]
    for written in (f"Иванов Д {house}", f"класс д {house}", f"группа Д {house}",
                    f"кв {house}", f"д {flat}"):
        _expect("CTRL/role", f"not a known address role (tool): {written}",
                _tool(written, vault), written)
        _expect("CTRL/role", f"not a known address role (prose): {written}",
                _prose(written, vault), written)


def main() -> int:
    testkit.load_dev_bundle()
    _controls_role_and_cue()
    _r0_short_address()
    _r1_dropped_marker()
    _r2_lower_case()
    _r3_upper_case()
    _r4_streetless_fragment()
    _two_addresses()
    _controls_verbatim_and_scope()
    _controls_unknown_street()
    _controls_literal_typos()
    _controls_same_kind_marker()
    _controls_copied_fragments()

    failures = [check for check in _CHECKS if check[2] != check[3]]
    for kind, name, got, want in failures:
        print(f"RED [{kind}] {name}\n    got  {got!r}\n    want {want!r}")
    print()
    print(f"location_form_adversarial: {len(_CHECKS) - len(failures)}/{len(_CHECKS)} "
          f"contract checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
