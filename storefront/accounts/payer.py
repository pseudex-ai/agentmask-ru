"""Who the customer is, as THEY state it — the one fact nobody else can supply.

`Organization.kind` used to be set by nobody: the default was «юрлицо», the
cabinet had no form, and the счёт page said «напишите нам, и мы добавим». Every
customer was therefore a company on paper, including the developer paying with
a personal card, and the closing documents were written by hand by us. The
form this module validates is the customer's own declaration; it is checked
here rather than in the view so the rules can be read and tested without a
request.

The ИНН checksum is the same arithmetic the engine uses in `pseudex/ru_pii.py`
and is deliberately COPIED, not imported: the storefront must not depend on
the engine package (it does not ship with it and must not pull it in).
"""
from __future__ import annotations

import re

from accounts.models import Organization

_DIGITS = re.compile(r"\D+")

_INN_WEIGHTS_10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN_WEIGHTS_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN_WEIGHTS_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


class PayerError(ValueError):
    """A field the customer typed cannot be what they say it is."""


def inn_is_valid(inn: str) -> bool:
    """Checksum of a Russian ИНН: 10 digits for a company, 12 for a person or ИП.

    A typo in an ИНН is not a cosmetic problem — it goes onto a счёт and an акт
    that the buyer's accountant files with the tax office, and a document with
    the wrong ИНН is a document that was never issued to that buyer.
    """
    digits = _DIGITS.sub("", inn)
    if len(digits) == 10:
        control = sum(int(digits[i]) * _INN_WEIGHTS_10[i] for i in range(9)) % 11 % 10
        return control == int(digits[9])
    if len(digits) == 12:
        control_11 = sum(int(digits[i]) * _INN_WEIGHTS_11[i] for i in range(10)) % 11 % 10
        control_12 = sum(int(digits[i]) * _INN_WEIGHTS_12[i] for i in range(11)) % 11 % 10
        return control_11 == int(digits[10]) and control_12 == int(digits[11])
    return False


def payer_fields(kind: str, legal_name: str, inn: str, kpp: str,
                 legal_address: str) -> dict[str, str]:
    """Validate the payer form and return the fields to store, normalised.

    Raises `PayerError` with a message written for the customer. The rules are
    the document rules, not the database's: a company or an ИП is billed by
    счёт and closed by акт, and both need a name and an ИНН; an individual is
    billed by card and receipt only, so for them everything but the kind is
    optional — but an ИНН, if given, still has to be one.
    """
    kinds = {code for code, _title in Organization.KINDS}
    if kind not in kinds:
        raise PayerError("Выберите, кто плательщик: юридическое лицо, ИП или физическое лицо.")
    name = " ".join(legal_name.split())[:300]
    inn_digits = _DIGITS.sub("", inn)
    kpp_digits = _DIGITS.sub("", kpp)
    address = " ".join(legal_address.split())[:1000]

    if kind != Organization.KIND_PERSON and not name:
        raise PayerError("Для счёта нужно наименование — как в ЕГРЮЛ или ЕГРИП.")
    if kind != Organization.KIND_PERSON and not inn_digits:
        raise PayerError("Для счёта нужен ИНН.")
    if inn_digits:
        expected = 10 if kind == Organization.KIND_COMPANY else 12
        if len(inn_digits) != expected:
            raise PayerError(f"ИНН {'юридического лица' if expected == 10 else 'ИП и физического лица'} "
                             f"— это {expected} цифр, у вас {len(inn_digits)}.")
        if not inn_is_valid(inn_digits):
            raise PayerError("ИНН не проходит контрольную сумму — проверьте цифры.")
    if kpp_digits and kind != Organization.KIND_COMPANY:
        raise PayerError("КПП есть только у юридических лиц.")
    if kpp_digits and len(kpp_digits) != 9:
        raise PayerError(f"КПП — это 9 цифр, у вас {len(kpp_digits)}.")

    return {
        "kind": kind,
        "legal_name": name,
        "inn": inn_digits,
        "kpp": kpp_digits,
        "legal_address": address,
    }
