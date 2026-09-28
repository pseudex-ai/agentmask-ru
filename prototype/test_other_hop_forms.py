"""C01 — exact value+form checks on the current hop for every type but PHONE.

THE CONTRACT IS `docs/tz-hop-form-adaptation.md` §1: content comes from the real
entity, form comes from the CURRENT SENDER. On IN the sender is the user, so each
mention's substitute keeps THAT mention's form (separators, notation, letter case,
alphabet) and, when the same value is written again in another form, the second
mention keeps its own form while the canonical content stays one. On OUT the
sender is the agent: the tool argument and the prose answer both take the form the
agent actually wrote. This file asserts the contract, NOT what the engine happens
to do — a mismatch is a RED to report, never a new expectation.

Refusals stay REFUSALS. A two-digit fragment, an unnamed middle group, a
below-the-floor prefix and a local part with no domain have no supported role; the checks
below pin that they stay fake and are documented as limitations, not upgraded into
pattern support.

SEAMS. `mask_text` receives LITERAL `Span` objects (no `Detector`), a real
ephemeral `Vault`, the real dev bundle, and both restore consumers
(`unmask_arguments`, `unmask_text`). Substitutes are pinned at the mint boundary
(`_fake_snils` / `_fake_inn` / `_fake_card`, and `secrets.choice`/`randbelow` for
the mints inlined into `_render_token`). No expectation is computed by an engine
function; content comparisons use a local character fold.

DOB has one open interpretation question (day-first reading of an ambiguous
`dd.mm`); no new date semantics are asserted here. Run from `prototype/`:

    PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python test_other_hop_forms.py
"""

from __future__ import annotations

import json
import string
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from unittest.mock import patch

import testkit

from pseudex.detect import Span
from pseudex.detect_all import Detector
from pseudex.redact import mask_text, unmask_arguments, unmask_text
from pseudex.ru_pii import validate_inn, validate_luhn, validate_snils
from pseudex.vault import Vault

# Pinned substitutes: valid where applicable, leading zeros deliberate, and the
# letter/case variants are the whole point of the EMAIL/PLATE rows.
_FAKE_SNILS = "085-387-569 19"
_FAKE_INN = "001234567887"
_FAKE_CARD = "0123 4567 8901 2347"
_FAKE_PASSPORT = "0002 345678"
_FAKE_DOB = "11 июля 1975"
_FAKE_EMAIL = "abcdefgh@example.ru"
_FAKE_EMAIL_UPPER = "ABCDEFGH@EXAMPLE.RU"
_FAKE_PLATE = "М456ТУ789"
_FAKE_PLATE_LATIN = "M456TY789"
_FAKE_PLATE_LOWER = "м456ту789"

# (entity, writing A, writing B, substitute A, substitute B)
_IN_CASES: tuple[tuple[str, str, str, str, str], ...] = (
    ("SNILS", "112-233-445 95", "11223344595", _FAKE_SNILS, "08538756919"),
    ("INN", "500100732259", "50 01 007322 59", _FAKE_INN, "00 12 345678 87"),
    ("CARD", "4276 1600 1234 5675", "4276-1600-1234-5675",
     _FAKE_CARD, "0123-4567-8901-2347"),
    ("PASSPORT", "4509 123456", "45 09 123456", _FAKE_PASSPORT, "00 02 345678"),
    ("DOB", "2 июня 1975", "02.06.1975", _FAKE_DOB, "11.07.1975"),
    ("EMAIL", "ivan.petrov@mail.ru", "IVAN.PETROV@MAIL.RU",
     _FAKE_EMAIL, _FAKE_EMAIL_UPPER),
    ("PLATE", "А123ВС777", "A123BC777", _FAKE_PLATE, _FAKE_PLATE_LATIN),
)

_CHECKS: list[tuple[str, str, str, object, object]] = []
_QUESTIONS: list[str] = []

_PLATE_LATIN_TO_CYR = str.maketrans("ABEKMHOPCTYX", "АВЕКМНОРСТУХ")


def _expect(entity: str, kind: str, name: str, got: object, want: object) -> None:
    _CHECKS.append((entity, kind, name, got, want))


def _question(entity: str, text: str) -> None:
    _QUESTIONS.append(f"[{entity}] {text}")


def _content(entity: str, shown: str) -> str:
    """Canonical CONTENT of one substitute, folded here — never by an engine call."""
    if entity in ("SNILS", "INN", "CARD", "PASSPORT"):
        return "".join(ch for ch in shown if ch.isdigit())
    if entity == "EMAIL":
        return shown.lower()
    if entity == "PLATE":
        return shown.translate(_PLATE_LATIN_TO_CYR).upper()
    return shown  # DOB: one row is the canonical-content proof; notation is not folded.


def _pinned_rng(*, letters: str, digits: str, year_offset: int,
                month: int, day: int) -> AbstractContextManager[None]:
    letters_q: list[str] = list(letters)
    digits_q: list[str] = list(digits)

    def choice(population: str) -> str:
        if population in ("АВЕКМНОРСТУХ", string.ascii_lowercase):
            return letters_q.pop(0)
        if population == string.digits:
            return digits_q.pop(0)
        raise AssertionError(f"unexpected choice population: {population!r}")

    def randbelow(n: int) -> int:
        if year_offset:
            return year_offset
        return (month - 1) if n == 12 else (day - 1)

    @contextmanager
    def _ctx() -> Iterator[None]:
        with patch("pseudex.vault.secrets.choice", side_effect=choice), \
                patch("pseudex.vault.secrets.randbelow", side_effect=randbelow):
            yield

    return _ctx()


def _mint(entity: str) -> AbstractContextManager[None]:
    if entity == "SNILS":
        return patch("pseudex.vault._fake_snils", return_value=_FAKE_SNILS)
    if entity == "INN":
        return patch("pseudex.vault._fake_inn", return_value=_FAKE_INN)
    if entity == "CARD":
        return patch("pseudex.vault._fake_card", return_value=_FAKE_CARD)
    if entity == "PASSPORT":
        return _pinned_rng(letters="", digits="345678", year_offset=5, month=0, day=0)
    if entity == "DOB":
        return _pinned_rng(letters="", digits="", year_offset=0, month=7, day=11)
    if entity == "EMAIL":
        return _pinned_rng(letters="abcdefgh", digits="", year_offset=0, month=0, day=0)
    if entity == "PLATE":
        return _pinned_rng(letters="МТУ", digits="456789", year_offset=0, month=0, day=0)
    raise AssertionError(f"no pinned mint for {entity!r}")


def _vault(customer: str, conversation: str) -> Vault:
    return Vault(":memory:", customer).for_conversation(conversation)


def _mask(text: str, value: str, entity: str, vault: Vault) -> str:
    start = text.index(value)
    span = Span(start, start + len(value), entity, value)
    return mask_text(text, vault, [span])[1:-1]


def _masked(entity: str, writing: str, vault: Vault) -> str:
    with _mint(entity):
        return _mask(f"«{writing}»", writing, entity, vault)


def _tool(written: str, vault: Vault) -> str:
    raw = json.dumps({"field": written}, ensure_ascii=False)
    restored: object = json.loads(unmask_arguments(raw, vault))
    if not isinstance(restored, dict) or not isinstance(restored.get("field"), str):
        raise AssertionError("tool restoration changed the JSON field type")
    return restored["field"]


def _prose(written: str, vault: Vault) -> str:
    return unmask_text(f"до {written} после", vault)


def _in_forms() -> None:
    """IN: the substitute keeps the form of THIS mention, in a fresh vault each."""
    for entity, writing_a, writing_b, sub_a, sub_b in _IN_CASES:
        _expect(entity, "in-form", f"A {writing_a!r}", _masked(entity, writing_a, _vault("acme", "c1")), sub_a)
        _expect(entity, "in-form", f"B {writing_b!r}", _masked(entity, writing_b, _vault("acme", "c1")), sub_b)
    # PLATE carries three independent forms; the lower-case one is not a rewrite
    # of the two above, so it gets its own mention.
    _expect("PLATE", "in-form", "lower case stays lower",
            _masked("PLATE", "а123вс777", _vault("acme", "c1")), _FAKE_PLATE_LOWER)


def _in_identity() -> None:
    """IN reuse: one canonical row, but each mention keeps its own form."""
    for entity, writing_a, writing_b, sub_a, sub_b in _IN_CASES:
        shared = _vault("acme", "c1")
        with _mint(entity):
            token_a = _mask(f"«{writing_a}»", writing_a, entity, shared)
            token_b = _mask(f"«{writing_b}»", writing_b, entity, shared)
        _expect(entity, "in-identity", "second mention keeps ITS form, one row",
                (token_a, token_b, len(shared.minted_tokens()), token_a != token_b),
                (sub_a, sub_b, 1, True))
        if entity != "DOB":
            _expect(entity, "in-identity", "canonical content is shared",
                    _content(entity, token_a), _content(entity, token_b))


def _out_tool() -> None:
    """OUT to the tool: the real value takes the agent's form."""
    vault = _vault("acme", "c1")
    with _mint("SNILS"):
        _mask("«112-233-445 95»", "112-233-445 95", "SNILS", vault)
    _expect("SNILS", "out-tool", "agent's own grouping",
            _tool("085 387 569 19", vault), "112 233 445 95")
    _expect("SNILS", "out-tool", "agent's bare digits",
            _tool("08538756919", vault), "11223344595")

    vault = _vault("acme", "c1")
    with _mint("INN"):
        _mask("«500100732259»", "500100732259", "INN", vault)
    _expect("INN", "out-tool", "agent's own grouping",
            _tool("0012 3456 7887", vault), "5001 0073 2259")

    vault = _vault("acme", "c1")
    with _mint("CARD"):
        _mask("«4276 1600 1234 5675»", "4276 1600 1234 5675", "CARD", vault)
    _expect("CARD", "out-tool", "agent writes dashes",
            _tool("0123-4567-8901-2347", vault), "4276-1600-1234-5675")
    _expect("CARD", "out-tool", "agent writes bare digits",
            _tool("0123456789012347", vault), "4276160012345675")

    vault = _vault("acme", "c1")
    with _mint("PASSPORT"):
        _mask("«4509 123456»", "4509 123456", "PASSPORT", vault)
    _expect("PASSPORT", "out-tool", "agent writes bare digits",
            _tool("0002345678", vault), "4509123456")

    vault = _vault("acme", "c1")
    with _mint("DOB"):
        _mask("«2 июня 1975»", "2 июня 1975", "DOB", vault)
    _expect("DOB", "out-tool", "agent writes ISO", _tool("1975-07-11", vault), "1975-06-02")
    _expect("DOB", "out-tool", "agent writes dotted", _tool("11.07.1975", vault), "02.06.1975")

    vault = _vault("acme", "c1")
    with _mint("EMAIL"):
        _mask("«ivan.petrov@mail.ru»", "ivan.petrov@mail.ru", "EMAIL", vault)
    _expect("EMAIL", "out-tool", "agent upper-cases",
            _tool(_FAKE_EMAIL_UPPER, vault), "IVAN.PETROV@MAIL.RU")

    vault = _vault("acme", "c1")
    with _mint("PLATE"):
        _mask("«А123ВС777»", "А123ВС777", "PLATE", vault)
    _expect("PLATE", "out-tool", "agent writes Latin look-alikes",
            _tool(_FAKE_PLATE_LATIN, vault), "A123BC777")
    _expect("PLATE", "out-tool", "agent lower-cases",
            _tool(_FAKE_PLATE_LOWER, vault), "а123вс777")


def _out_prose() -> None:
    """OUT to the human: the answer's own mention owns the form too."""
    vault = _vault("acme", "c1")
    with _mint("SNILS"):
        _mask("«112-233-445 95»", "112-233-445 95", "SNILS", vault)
    _expect("SNILS", "out-prose", "agent's bare digits, not the customer's dashes",
            _prose("08538756919", vault), "до 11223344595 после")
    _expect("SNILS", "out-prose", "agent's own grouping",
            _prose("085 387 569 19", vault), "до 112 233 445 95 после")

    vault = _vault("acme", "c1")
    with _mint("INN"):
        _mask("«500100732259»", "500100732259", "INN", vault)
    _expect("INN", "out-prose", "agent's own grouping",
            _prose("0012 3456 7887", vault), "до 5001 0073 2259 после")

    vault = _vault("acme", "c1")
    with _mint("CARD"):
        _mask("«4276 1600 1234 5675»", "4276 1600 1234 5675", "CARD", vault)
    _expect("CARD", "out-prose", "agent writes dashes, not the customer's spaces",
            _prose("0123-4567-8901-2347", vault), "до 4276-1600-1234-5675 после")

    vault = _vault("acme", "c1")
    with _mint("PASSPORT"):
        _mask("«4509 123456»", "4509 123456", "PASSPORT", vault)
    _expect("PASSPORT", "out-prose", "agent writes bare digits",
            _prose("0002345678", vault), "до 4509123456 после")

    vault = _vault("acme", "c1")
    with _mint("DOB"):
        _mask("«2 июня 1975»", "2 июня 1975", "DOB", vault)
    _expect("DOB", "out-prose", "agent writes ISO",
            _prose("1975-07-11", vault), "до 1975-06-02 после")
    _expect("DOB", "out-prose", "agent writes dotted",
            _prose("11.07.1975", vault), "до 02.06.1975 после")

    vault = _vault("acme", "c1")
    with _mint("EMAIL"):
        _mask("«ivan.petrov@mail.ru»", "ivan.petrov@mail.ru", "EMAIL", vault)
    _expect("EMAIL", "out-prose", "agent's upper case",
            _prose(_FAKE_EMAIL_UPPER, vault), "до IVAN.PETROV@MAIL.RU после")

    vault = _vault("acme", "c1")
    with _mint("PLATE"):
        _mask("«А123ВС777»", "А123ВС777", "PLATE", vault)
    _expect("PLATE", "out-prose", "agent's lower case",
            _prose(_FAKE_PLATE_LOWER, vault), "до а123вс777 после")
    _expect("PLATE", "out-prose", "agent's Latin script",
            _prose(_FAKE_PLATE_LATIN, vault), "до A123BC777 после")


def _parts() -> None:
    """Selected roles resolve; unsupported roles stay fake (documented limits)."""
    vault = _vault("acme", "c1")
    with _mint("SNILS"):
        _mask("«112-233-445 95»", "112-233-445 95", "SNILS", vault)
    _expect("SNILS", "part", "first group is an edge", _tool("085", vault), "112")
    _expect("SNILS", "part", "last four resolve", _tool("6919", vault), "4595")
    _expect("SNILS", "part", "LIMIT: two-digit control stays fake", _tool("19", vault), "19")
    _expect("SNILS", "part", "LIMIT: unnamed middle stays fake", _tool("387", vault), "387")

    vault = _vault("acme", "c1")
    with _mint("INN"):
        _mask("«500100732259»", "500100732259", "INN", vault)
    _expect("INN", "part", "last four resolve", _tool("7887", vault), "2259")
    _expect("INN", "part", "LIMIT: two-digit prefix stays fake", _tool("00", vault), "00")

    vault = _vault("acme", "c1")
    with _mint("CARD"):
        _mask("«4276 1600 1234 5675»", "4276 1600 1234 5675", "CARD", vault)
    _expect("CARD", "part", "last four resolve", _tool("2347", vault), "5675")

    vault = _vault("acme", "c1")
    with _mint("PASSPORT"):
        _mask("«4509 123456»", "4509 123456", "PASSPORT", vault)
    _expect("PASSPORT", "part", "series resolve", _tool("0002", vault), "4509")

    vault = _vault("acme", "c1")
    with _mint("EMAIL"):
        _mask("«ivan.petrov@mail.ru»", "ivan.petrov@mail.ru", "EMAIL", vault)
    _expect("EMAIL", "part", "LIMIT: a local part without a domain stays fake",
            _tool("abcdefgh", vault), "abcdefgh")


def _card_lengths() -> None:
    """A card keeps the length and the separators it was WRITTEN with.

    C02 fixed the length rule for everything the engine can meet — a card read
    aloud in eighteen or nineteen digits was answered with a sixteen-digit
    substitute, a shape the customer's own validator refuses — and the written
    path is where the same rule shows up in the IN form: the substitute must
    carry the sender's own grouping, not the register's.

    The generator is the REAL one here. A pinned substitute would make the
    length assertion vacuous, and the length IS the assertion.

    The span is LITERAL, as everywhere in this file, so this pins the VAULT's
    form rule and not detection. Detection of the same lengths from a card cue
    is pinned where detection lives, `test_hard_cases.py`
    (`test_a_cued_card_is_typed_whole`); `ru_pii._CARD_CUE_RE` now captures the
    whole 13..19-digit run, so the detector and this form rule agree.
    """
    for writing in ("0123 4567 8901 2347",
                    "0123 4567 8901 2345 02",
                    "0123-4567-8901-2345-02",
                    "0123 4567 8901 2345 002"):
        vault = _vault("acme", "c1")
        masked = _mask(f"«{writing}»", writing, "CARD", vault)
        digits = "".join(ch for ch in writing if ch.isdigit())
        _expect("CARD", "in-form", f"digit count kept for {writing!r}",
                str(len([ch for ch in masked if ch.isdigit()])), str(len(digits)))
        _expect("CARD", "in-form", f"sender's separators kept for {writing!r}",
                "".join(ch for ch in masked if not ch.isdigit()),
                "".join(ch for ch in writing if not ch.isdigit()))
        _expect("CARD", "out-tool", f"tool gets the card back for {writing!r}",
                _tool(masked, vault), writing)
        _expect("CARD", "out-prose", f"prose gets the card back for {writing!r}",
                _prose(masked, vault), f"до {writing} после")


def _negatives() -> None:
    vault = _vault("acme", "c1")
    with _mint("INN"):
        masked = _mask("«500100732259»", "500100732259", "INN", vault)
    _expect("CONTROL", "negative", "quantities are not identifiers",
            json.loads(unmask_arguments(json.dumps({"count": "12", "qty": "5"},
                                                   ensure_ascii=False), vault)),
            {"count": "12", "qty": "5"})
    _expect("CONTROL", "negative", "numbers in a sentence stay",
            unmask_text("Заказ 42; скидка 10%; осталось 3 места", vault),
            "Заказ 42; скидка 10%; осталось 3 места")
    _expect("CONTROL", "negative", "non-PII neighbours in JSON are untouched",
            json.loads(unmask_arguments(json.dumps(
                {"order": "A-1234", "note": "позвонить после 18:00", "field": masked},
                ensure_ascii=False), vault)),
            {"order": "A-1234", "note": "позвонить после 18:00", "field": "500100732259"})
    _expect("CONTROL", "negative", "non-PII prose neighbours are untouched",
            unmask_text(f"заказ A-1234, потом {masked}, скидка 10%", vault),
            "заказ A-1234, потом 500100732259, скидка 10%")


def _json_escaping() -> None:
    vault = _vault("acme", "c1")
    with _mint("PLATE"):
        masked = _mask("«А123ВС777»", "А123ВС777", "PLATE", vault)
    raw = ('{"note": "он сказал \\"привет\\" и ушёл\\\\", '
           f'"field": "{masked}", "n": 7}}')
    restored = json.loads(unmask_arguments(raw, vault))
    _expect("CONTROL", "json", "escaped neighbour survives a masked field", restored,
            {"note": 'он сказал "привет" и ушёл\\', "field": "А123ВС777", "n": 7})
    reparsed = json.loads(unmask_arguments(json.dumps(restored, ensure_ascii=False), vault))
    _expect("CONTROL", "json", "the restored document re-parses", reparsed, restored)


def _tenant_isolation() -> None:
    vault = _vault("acme", "c1")
    with _mint("PASSPORT"):
        masked = _mask("«4509 123456»", "4509 123456", "PASSPORT", vault)
    other = _vault("other-tenant", "c1")
    _expect("CONTROL", "isolation", "a tool argument in another tenant",
            _tool(masked, other), masked)
    _expect("CONTROL", "isolation", "prose in another tenant",
            _prose(masked, other), f"до {masked} после")


def _cross_type(detector: Detector) -> None:
    """CROSS-TYPE: a value ambiguous between two owners, where the right one wins.

    The numeric arms pin the RESTORE leg: the minted fake has a digit shape that
    overlaps a DIFFERENT type (a leading-`8` eleven-digit СНИЛС looks like a
    phone; a ten-digit ИНН and a bare passport are phone/ИНН length; a sixteen-
    digit card is a long numeric run), and `_digits_in_form_of`/the digit-signature
    reindex must still answer with the real value of the TYPE it was minted as —
    never a phone splice. The PLATE arm pins the DETECT leg through the real
    detector: «счёт 1234 от 15.05.2025» is the invoice phrase `ru_pii.
    _PLATE_DENY_LOWER` exists to keep whole (its lower-case «от» is prose, not a
    motorcycle plate).
    """
    # SNILS-vs-PHONE: a fake beginning with `8` must not take the phone prefix rule.
    vault = _vault("acme", "c1")
    with patch("pseudex.vault._fake_snils", return_value="805-387-569 27"):
        vault.tokenize("112-233-445 22", "SNILS")
    typed = vault.resolve_digit_signatures_typed({"80538756927"}, True)
    _expect("SNILS", "cross-type", "leading-8 signature keeps its SNILS type",
            typed["80538756927"][0], "SNILS")
    _expect("SNILS", "cross-type", "leading-8 fake is not phone-spliced (tool)",
            _tool("80538756927", vault), "11223344522")
    _expect("SNILS", "cross-type", "leading-8 fake restores as SNILS (prose)",
            _prose("805-387-569 27", vault), "до 112-233-445 22 после")

    # INN-10-vs-PHONE: ten digits overlap a local phone's length.
    vault = _vault("acme", "c1")
    with patch("pseudex.vault._fake_inn", return_value="0012345673"):
        vault.tokenize("7707083893", "INN")
    _expect("INN", "cross-type", "ten-digit INN fake is not read as phone (tool)",
            _tool("0012345673", vault), "7707083893")
    _expect("INN", "cross-type", "ten-digit INN fake groups as ИНН (prose)",
            _prose("00 12 345673", vault), "до 77 07 083893 после")

    # CARD-vs-INN: a sixteen-digit card is a longer run than any ИНН.
    vault = _vault("acme", "c1")
    with patch("pseudex.vault._fake_card", return_value="0123 4567 8901 2347"):
        vault.tokenize("4276 1600 1234 5675", "CARD")
    _expect("CARD", "cross-type", "sixteen-digit card fake is not read as ИНН (tool)",
            _tool("0123456789012347", vault), "4276160012345675")
    _expect("CARD", "cross-type", "sixteen-digit card fake groups as card (prose)",
            _prose("0123-4567-8901-2347", vault), "до 4276-1600-1234-5675 после")

    # PASSPORT-vs-INN/PHONE: series+number is ten digits, the same as an ИНН-10.
    vault = _vault("acme", "c1")
    with _mint("PASSPORT"):
        vault.tokenize("4509 123456", "PASSPORT")
    _expect("PASSPORT", "cross-type", "ten-digit passport fake is not read as ИНН/phone (tool)",
            _tool("0002345678", vault), "4509123456")
    _expect("PASSPORT", "cross-type", "passport fake groups as passport (prose)",
            _prose("0002 345678", vault), "до 4509 123456 после")

    # PLATE-vs-prose «от»: the lower-case word is prose, not a plate's letters.
    vault = _vault("acme", "c1")
    invoice = "счёт 1234 от 15.05.2025"
    _expect("PLATE", "cross-type", "lower-case 'от' before a plate shape stays prose",
            mask_text(invoice, vault, detector.detect(invoice)), invoice)


def _per_type_negatives(detector: Detector) -> None:
    """NEGATIVE per type, through the REAL Detector + mask_text path.

    A bare look-alike with no cue word must be refused by the CHECksum gate (a
    СНИЛС shape whose mod-101 fails; a sixteen-digit run that fails Luhn) or by
    the plate deny gate (a lower-case «от» in the two-letter slot), so nothing is
    masked. A cue word would type the value regardless of checksum — see the
    `_SNILS_CUE_RE` arm — so these stay cue-less on purpose: the checksum is the
    only thing that can refuse them.
    """
    for entity, text in (
            ("SNILS", "112-233-445 00"),
            ("CARD", "1234 5678 9012 3456"),
            ("PLATE", "1234 от 77")):
        vault = _vault("acme", "c1")
        _expect(entity, "negative", f"{text!r} stays unmasked",
                mask_text(text, vault, detector.detect(text)), text)


def _fake_checksums() -> None:
    """The minted substitute PASSES its own validator, on purpose.

    A substitute must never be a real person's ID. The engine guarantees that
    structurally — an ИНН under region «00», a card under MII «0», a СНИЛС above
    the exempt range — so the fake is checksum-VALID (it parses as a well-formed
    identifier) yet impossible for a person to hold
    (research/2026-09-03-checksum-valid-substitutes.md). Asserting the fake PASSES
    `validate_*` pins that the form-adaptation path did not corrupt the checksum
    it was minted with; a revert to checksum-INVALID mints goes red here.
    """
    _expect("SNILS", "fake-checksum", "minted SNILS fake passes validate_snils",
            validate_snils(_FAKE_SNILS), True)
    _expect("INN", "fake-checksum", "minted INN fake passes validate_inn",
            validate_inn(_FAKE_INN), True)
    _expect("CARD", "fake-checksum", "minted CARD fake passes validate_luhn",
            validate_luhn(_FAKE_CARD), True)


def _open_questions() -> None:
    _question("DOB", "AMBIGUOUS DATE: '05.06.2025' is read day-first by "
              "`_date_canonical`; no rule distinguishes dd.mm from mm.dd when both "
              "are <= 12. C01 pins the unambiguous notations and asserts no reading.")
    _question("PLATE", "REGION WIDTH: a 2-digit region ('А123ВС77') normally mints a "
              "3-digit one; 'region width' is not part of the current-sender form "
              "contract in §1 and needs an explicit decision.")


def _tally() -> None:
    entities: dict[str, int] = {}
    kinds: dict[str, int] = {}
    for entity, kind, _name, _got, _want in _CHECKS:
        entities[entity] = entities.get(entity, 0) + 1
        kinds[kind] = kinds.get(kind, 0) + 1
    print("checks by type: " + ", ".join(f"{e} {n}" for e, n in sorted(entities.items())))
    print("checks by kind: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())))


def main() -> int:
    testkit.load_dev_bundle()
    _in_forms()
    _in_identity()
    _out_tool()
    _out_prose()
    _parts()
    _card_lengths()
    _negatives()
    _json_escaping()
    _tenant_isolation()
    detector = Detector()
    _cross_type(detector)
    _per_type_negatives(detector)
    _fake_checksums()
    _open_questions()

    failures = [c for c in _CHECKS if c[3] != c[4]]
    for entity, kind, name, got, want in failures:
        print(f"RED [{entity}/{kind}] {name}\n    got  {got!r}\n    want {want!r}")
    print()
    _tally()
    print(f"other_hop_forms: {len(_CHECKS) - len(failures)}/{len(_CHECKS)} contract checks passed")
    if _QUESTIONS:
        print(f"\nQUESTIONS (domain choices, neither pass nor fail): {len(_QUESTIONS)}")
        for question in _QUESTIONS:
            print(f"  ? {question}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
