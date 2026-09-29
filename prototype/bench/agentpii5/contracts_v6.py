# contracts_v6.py — the v6 tables that are NOT about PII types (those live in
# `pii_types.py`). The axis vocabulary, the provenance tag, the case meta that
# `CaseV5.v6` carries, the corpus directory and the v6 negative families.
#
# Like `pii_types.py`, this module is PURE and self-contained: it imports nothing
# from `contracts`, `pseudex` or `licensing`. `contracts.py` imports IT (one
# direction), so `contracts -> contracts_v6` and never the reverse. The tool
# registry `tools_v6.py` and the corpus rules `schema_v6.py` arrive in later
# phases and consume these tables; here only the vocabulary and the shapes live.
#
# Spec: docs/tz-agentpii6.md §2.1 (INDUSTRIES), §3.2 (provenance), §6.5
# (V6_AXES), §8.4 (V6_DIR), §14.2 (how the axes are read).

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass


# --- the industry axis (spec §2.1) ----------------------------------------------
# One per case, declared, never derived from a tool: `notify_sms` serves any
# industry. A case must touch >= 1 tool of ITS OWN industry (R6-25).
INDUSTRIES: tuple[str, ...] = (
    "retail",
    "logistics",
    "banks_mfo_collectors",
    "medicine",
    "insurance",
    "auto",
    "telecom",
    "real_estate",
    "hospitality",
    "hr",
    "legal",
    "government_services",
    "education",
    "internal_bi",
    "marketing_cdp",
)

# --- the provenance tag (spec §3.2) ---------------------------------------------
# One tag per case, about the SKELETON (language and flow), never about the
# values — the values are synthetic always.
V6_PROVENANCE_KINDS: tuple[str, ...] = ("live-register", "documented-procedure", "synthetic")


@dataclass(frozen=True)
class ProcedureRecord:
    """A documented procedure a `documented-procedure` case cites: the doc URL
    and the ordered steps (tool names or behaviour markers). R6-24 resolves the
    reference and checks the case's declared calls contain the steps in order."""

    doc_ref: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class CaseV6Meta:
    """The v6 metadata a case carries, read by the `industry` and `provenance`
    axes and by the provenance table. `skeleton_ref` is set for a
    `live-register` case, `procedure_ref` for a `documented-procedure` one; both
    are "" otherwise. Frozen, no defaults — the project forbids them, so every
    constructor site names all four fields."""

    industry: str                    # one of INDUSTRIES
    provenance: str                  # one of V6_PROVENANCE_KINDS
    skeleton_ref: str                # a skeleton-registry id, or ""
    procedure_ref: str               # a ProcedureRecord id, or ""


# --- the v6 report axes (spec §6.5) ---------------------------------------------
# Printed only on runs with a v6 case; `contracts.AXES` is untouched.
V6_AXES: tuple[str, ...] = ("industry", "provenance", "type_class")


# --- the corpus directory (spec §8.4) -------------------------------------------
# The v6 corpus and ladder live HERE, never in the pinned `corpus.v5.json` /
# `corpus.json` / `ladder.json`. `build_v6` refuses `out == HERE`'s parent.
V6_DIR: str = "bench/agentpii5/v6"


# --- the v6 negative families (spec §1.6 of the registry) -----------------------
# The 28 lookalike families a v6 case declares: business identifiers a right
# gateway must NOT mask. R02 admits a v4.validate «negative family … unknown»
# line for exactly these; `contracts.py` re-exports this tuple as
# `V6_NEGATIVE_FAMILIES`. Every id is a stable, closed vocabulary — `schema_v6`
# K6-05 requires each to appear >= its occurrence floor in a full corpus, and
# `metrics.overmask_result` reads the `neg:`-tagged result slots these families
# feed (§6.3, CQ-11).
V6_NEGATIVE_FAMILIES: tuple[str, ...] = (
    # financial / banking lookalikes (A-07, A-08, A-11)
    "BIK",              # 9 digits — the bank identifier, and the key to the account check
    "KPP",              # 9 signs NNNN PP XXX (P may be a letter)
    "INN_LEGAL",        # 10 digits — ИНН юридического лица
    "OGRN_LEGAL",       # 13 digits, С=1/5, mod 11 — ОГРН юрлица
    "GRN_RECORD",       # 15 digits «4…» — ГРН записи ЕГРИП
    "CORR_ACCOUNT",     # 20 digits «30101810…» — корр. счёт банка в ЦБ
    "LEGAL_ACCOUNT",    # 20 digits «40701/40702/40703…» — счёт юрлица
    "TREASURY_ACCOUNT", # 20 digits «03100643…» / «40102810…» — казначейские счета
    "KBK",              # 20 digits — код бюджетной классификации
    "OKTMO",            # 8 digits — территория
    "SWIFT_ISIN",       # 8/11 letters (SWIFT BIC) or 12 signs (ISIN)
    # documents / identifiers
    "PASSPORT_DEPT_CODE",  # NNN-NNN — код подразделения паспорта
    "CADASTRAL_QUARTER",   # «NN:NN:NNNNNN» — кадастровый квартал (территория)
    "FIAS_GUID",           # UUID объекта ФИАС/ГАР
    "ORG_OID",             # oid организации ЕСИА «rs/orgs/{oid}»
    "VIN_MASK",            # маска VIN «XTA21099*******» / WMI
    "COURT_INDEX",         # индекс суда «А40», «09АП», код ФССП
    "LAW_ARTICLE",         # ссылка на статью «ч. 2 ст. 12.9 КоАП»
    "DOC_NUMBER",          # деловой документ «№ 2-15/2025»
    "GOST_STANDARD",       # публичный стандарт «ГОСТ 33990-2016»
    # business order / goods
    "ORDER_NUMBER",     # номер заказа/накладной
    "TRACK_S10",        # почтовый трек UPU S10
    "TRACK_RU14",       # трек Почты России, 14 цифр
    "SKU_17",           # 17-значный артикул/SKU/код заказа
    "GTIN",             # товарный штрихкод EAN-13/14
    "CONTRACT_B2B",     # договор поставки между юрлицами
    "ICCID_M2M",        # ICCID корпоративной M2M-сим (актив юрлица)
    "METRICA_COUNTER",  # счётчик Метрики / OAuth client_id приложения
)


# --- the per-family value grammar (spec §1.6) -------------------------------------
# A deterministic, plausible value per family, driven by a LOCAL RNG seeded from
# `(family, seed)` so the same pair always yields the same value and a different
# seed yields a different one. The grammar is the card's own shape (§1.6 table);
# a digit run of length 11/12/13/15/16 is BY CONSTRUCTION not a valid v5 contract
# checksum (СНИЛС/ИНН/ОГРН/ОГРНИП/Лун) — the K6-21 guard `schema_v6` runs on
# negatives — and lengths 13/15 (ОГРН юрлица, ГРН) are minted with a deliberately
# WRONG check digit, never by a search-and-reject loop.

_DIGITS = "0123456789"
_HEX = "0123456789abcdef"
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(_DIGITS) for _ in range(n))


def _neg_seed(family: str, seed: int) -> int:
    """A deterministic int seed for one negative, stable across processes (never
    Python's salted `hash()`)."""
    raw = f"neg:{family}:{seed}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _gen_bik(rng: random.Random) -> str:
    return _digits(rng, 9)


def _gen_kpp(rng: random.Random) -> str:
    return _digits(rng, 4) + _digits(rng, 2) + _digits(rng, 3)


def _gen_inn_legal(rng: random.Random) -> str:
    return _digits(rng, 10)


def _gen_ogrn_legal(rng: random.Random) -> str:
    # ОГРН юрлица: 12-digit body (С=1/5) + a WRONG mod-11 check digit — never a
    # valid ОГРН, so the v5 contract mask cannot swallow it (K6-21).
    body = rng.choice("15") + _digits(rng, 11)
    return body + str((int(body) % 11 % 10 + 1) % 10)


def _gen_grn_record(rng: random.Random) -> str:
    # ГРН записи ЕГРИП: 14-digit body (С=4) + a WRONG mod-13 check digit.
    body = "4" + _digits(rng, 13)
    return body + str((int(body) % 13 % 10 + 1) % 10)


def _gen_corr_account(rng: random.Random) -> str:
    return "30101810" + _digits(rng, 12)


def _gen_legal_account(rng: random.Random) -> str:
    return "4070" + rng.choice("123") + _digits(rng, 15)


def _gen_treasury_account(rng: random.Random) -> str:
    return rng.choice(("03100643", "40102810")) + _digits(rng, 12)


def _gen_kbk(rng: random.Random) -> str:
    return _digits(rng, 20)


def _gen_oktmo(rng: random.Random) -> str:
    return _digits(rng, 8)


def _gen_swift_isin(rng: random.Random) -> str:
    return "".join(rng.choice(_LETTERS) for _ in range(11))


def _gen_passport_dept_code(rng: random.Random) -> str:
    return f"{_digits(rng, 3)}-{_digits(rng, 3)}"


def _gen_cadastral_quarter(rng: random.Random) -> str:
    # Dash-separated, not colon-separated: «:» is sentence punctuation the
    # voice_itn register forbids, and the quarter is a territory, not the full
    # cadastral number. Digit run is 10 — never a v5 contract length (K6-21).
    return f"{_digits(rng, 2)}-{_digits(rng, 2)}-{_digits(rng, 6)}"


def _gen_fias_guid(rng: random.Random) -> str:
    # A UUID whose tail is fixed letters, so the digit run is at most 8 — never a
    # v5 contract length (K6-21).
    head = "".join(rng.choice(_HEX) for _ in range(8))
    return f"{head}-ffff-ffff-ffff-ffffffffffff"


def _gen_org_oid(rng: random.Random) -> str:
    return f"rs/orgs/{_digits(rng, 8)}"


def _gen_vin_mask(rng: random.Random) -> str:
    return f"{rng.choice(('XTA', 'XUF', 'XTH'))}{_digits(rng, 7)}*******"


def _gen_court_index(rng: random.Random) -> str:
    return rng.choice(("А40", "09АП", "77001", "77003", "А41"))


def _gen_law_article(rng: random.Random) -> str:
    # Space-separated, never «ч. 2 ст. 12.9»: the periods are sentence
    # punctuation the voice_itn register forbids, and the reference is a norm,
    # not a person. Digit run stays short — never a v5 contract length (K6-21).
    return f"ч {rng.randint(1, 5)} ст {rng.randint(1, 300)} КоАП"


def _gen_doc_number(rng: random.Random) -> str:
    return f"№ {rng.randint(1, 20)}-{rng.randint(1, 300)}/{rng.choice(('2023', '2024', '2025', '2026'))}"


def _gen_gost_standard(rng: random.Random) -> str:
    return f"ГОСТ {_digits(rng, 5)}-{rng.choice(('2016', '2017', '2020', '2021', '2023'))}"


def _gen_order_number(rng: random.Random) -> str:
    return _digits(rng, rng.randint(6, 9))


def _gen_track_s10(rng: random.Random) -> str:
    return "".join(rng.choice(_LETTERS) for _ in range(2)) + _digits(rng, 9) \
        + rng.choice(("RU", "CN", "DE"))


def _gen_track_ru14(rng: random.Random) -> str:
    return _digits(rng, 14)


def _gen_sku_17(rng: random.Random) -> str:
    return _digits(rng, 17)


def _gen_gtin(rng: random.Random) -> str:
    return _digits(rng, 14)


def _gen_contract_b2b(rng: random.Random) -> str:
    return f"Д-{rng.choice(('2024', '2025', '2026'))}/{_digits(rng, 5)}"


def _gen_iccid_m2m(rng: random.Random) -> str:
    return "89" + _digits(rng, 17)


def _gen_metrica_counter(rng: random.Random) -> str:
    return _digits(rng, 8)


_NEG_GENERATORS: dict[str, object] = {
    "BIK": _gen_bik,
    "KPP": _gen_kpp,
    "INN_LEGAL": _gen_inn_legal,
    "OGRN_LEGAL": _gen_ogrn_legal,
    "GRN_RECORD": _gen_grn_record,
    "CORR_ACCOUNT": _gen_corr_account,
    "LEGAL_ACCOUNT": _gen_legal_account,
    "TREASURY_ACCOUNT": _gen_treasury_account,
    "KBK": _gen_kbk,
    "OKTMO": _gen_oktmo,
    "SWIFT_ISIN": _gen_swift_isin,
    "PASSPORT_DEPT_CODE": _gen_passport_dept_code,
    "CADASTRAL_QUARTER": _gen_cadastral_quarter,
    "FIAS_GUID": _gen_fias_guid,
    "ORG_OID": _gen_org_oid,
    "VIN_MASK": _gen_vin_mask,
    "COURT_INDEX": _gen_court_index,
    "LAW_ARTICLE": _gen_law_article,
    "DOC_NUMBER": _gen_doc_number,
    "GOST_STANDARD": _gen_gost_standard,
    "ORDER_NUMBER": _gen_order_number,
    "TRACK_S10": _gen_track_s10,
    "TRACK_RU14": _gen_track_ru14,
    "SKU_17": _gen_sku_17,
    "GTIN": _gen_gtin,
    "CONTRACT_B2B": _gen_contract_b2b,
    "ICCID_M2M": _gen_iccid_m2m,
    "METRICA_COUNTER": _gen_metrica_counter,
}


def neg_value(family: str, seed: int) -> str:
    """A deterministic, plausible negative value for one family (§1.6 grammar).

    `seed` drives a LOCAL `random.Random`, so the same `(family, seed)` yields the
    same value across processes and calls. Unknown `family` raises. The value is
    the identifier alone — never a cue word, never an «от <дата>» tail — and a
    digit run of length 11/12/13/15/16 is never a valid v5 contract checksum.
    """
    if family not in V6_NEGATIVE_FAMILIES:
        raise ValueError(f"contracts_v6: unknown negative family {family!r}")
    rng = random.Random(_neg_seed(family, seed))
    return _NEG_GENERATORS[family](rng)  # type: ignore[operator]


# A module-load proof the generator table covers exactly the families — no family
# silently missing a grammar, mirroring gen_v6's guard.
if set(_NEG_GENERATORS) != set(V6_NEGATIVE_FAMILIES):
    _missing = sorted(set(V6_NEGATIVE_FAMILIES) - set(_NEG_GENERATORS))
    _extra = sorted(set(_NEG_GENERATORS) - set(V6_NEGATIVE_FAMILIES))
    raise RuntimeError(
        f"contracts_v6 negative generator table does not match V6_NEGATIVE_FAMILIES: "
        f"missing={_missing}, extra={_extra}")
