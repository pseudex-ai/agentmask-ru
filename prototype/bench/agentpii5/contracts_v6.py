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
# Empty until the first v6 case registers one. R02 admits a v4.validate
# «negative family … unknown» line for exactly these; `contracts.py` re-exports
# this tuple as `V6_NEGATIVE_FAMILIES`.
V6_NEGATIVE_FAMILIES: tuple[str, ...] = ()
