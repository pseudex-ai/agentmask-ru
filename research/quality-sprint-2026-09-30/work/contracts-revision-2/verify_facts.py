#!/usr/bin/env python3
"""Independent re-derivation of the load-bearing counts behind REVIEW.md.

Read-only. No engine import, no bundle, no network, no git mutation.
Every number below is computed here from pinned files whose sha256 is recorded
in the output; nothing is copied from a child report.

Run:
  PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python \
    research/quality-sprint-2026-09-30/work/contracts-revision-2/verify_facts.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # repo root
OUT = Path(__file__).resolve().parent

FROZEN_V5_CONTRACTS = ROOT / "prototype/bench/agentpii5/contracts.py"
FROZEN_V6_CONTRACTS = ROOT / "research/quality-sprint-2026-09-30/work/V0/evidence/frozen/v6/contracts.py"
SNAPSHOT_PII_TYPES = ROOT / "research/hop-format-audit/next-sprint-review/v6-snapshot/pii_types.py"
FROZEN_V6_CHECKSUM = ROOT / "research/quality-sprint-2026-09-30/work/V0/evidence/frozen/v6/checksum_v6.py"
STRUCTURED = ROOT / "prototype/pseudex/structured.py"

inputs: list[dict] = []
commands: list[dict] = []


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pin(p: Path) -> Path:
    inputs.append({"path": str(p.relative_to(ROOT)), "sha256": sha256(p)})
    return p


def literal(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def module_literal(path: Path, name: str):
    """Literal value of a module-level assignment.

    Also unwraps frozenset({...}) / set([...]) / tuple([...]) calls, because a
    membership table in this codebase is written as frozenset({...}) — treating
    that as "not a literal" is how the V0 check lost `unmasked` from its v5 set.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        value = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = node.value
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                value = node.value
        if value is None:
            continue
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            if value.func.id in {"frozenset", "set", "tuple", "list"}:
                inner = value.args[0] if value.args else None
                if isinstance(inner, (ast.Set, ast.List, ast.Tuple)):
                    return [literal(e) for e in inner.elts]
        return literal(value)
    return None


# ---------------------------------------------------------------- A) V0 status funnels
v5_statuses = module_literal(pin(FROZEN_V5_CONTRACTS), "HOP_STATUSES")
v6_statuses = module_literal(pin(FROZEN_V6_CONTRACTS), "HOP_STATUSES")
v5_written = module_literal(pin(FROZEN_V5_CONTRACTS), "OUT_HOP_WRITTEN_STATUSES")

funnel = {
    "v5_HOP_STATUSES": list(v5_statuses or ()),
    "v6_HOP_STATUSES": list(v6_statuses or ()),
    "v5_OUT_HOP_WRITTEN_STATUSES": list(v5_written or ()),
    "v6_subset_of_v5_HOP_STATUSES": set(v6_statuses or ()) <= set(v5_statuses or ()),
    "v6_strict_subset": set(v6_statuses or ()) < set(v5_statuses or ()),
    "v5_only_statuses": sorted(set(v5_statuses or ()) - set(v6_statuses or ())),
    # the child check compared the v6 read-vocabulary with a WRITE-population:
    "v0_check_used_v5_set": sorted(set(v5_written or ()) | {"absent", "leaked"}),
}

# ------------------------------------------------- B) v6 registry item counts
# The 11 v5 records are inline in pii_types.py; the 55 v6 records live in the
# group files it folds in (pii_types_a/b/c.py). All four are read.
GROUP_FILES = [SNAPSHOT_PII_TYPES] + [
    SNAPSHOT_PII_TYPES.with_name(f"pii_types_{g}.py") for g in ("a", "b", "c")
]
records = []
for path in GROUP_FILES:
    tree = ast.parse(pin(path).read_text(encoding="utf-8"))
    # module constants: resolve `origin=ORIGIN_V6` to the string it names.
    # The group files IMPORT these constants rather than defining them, so the
    # two origin names are seeded from the pin: ORIGIN_V5 = "v5", ORIGIN_V6 = "v6".
    consts: dict[str, object] = {"ORIGIN_V5": "v5", "ORIGIN_V6": "v6"}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = literal(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            consts[node.target.id] = literal(node.value)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "TypeSpec":
            kw = {k.arg: k.value for k in node.keywords if k.arg}

            def val(name):
                if name not in kw:
                    return None
                node_v = kw[name]
                if isinstance(node_v, ast.Name):
                    return consts.get(node_v.id)
                return literal(node_v)

            records.append({
                "source_file": path.name,
                "id": val("id"),
                "origin": val("origin"),
                "item_type": val("item_type"),
                "generated_checksum": val("generated_checksum"),
                "sample": val("sample"),
                "bare_typed": val("bare_typed"),
            })

registry = {
    "records_total": len(records),
    "by_origin": {
        "v5": sum(1 for r in records if r["origin"] == "v5"),
        "v6": sum(1 for r in records if r["origin"] == "v6"),
    },
    "item_types_true": sum(1 for r in records if r["item_type"] is True),
    "non_item_types": [r["id"] for r in records if r["item_type"] is False],
    "v5_non_item": [r["id"] for r in records if r["origin"] == "v5" and r["item_type"] is False],
    "bare_typed_true": sum(1 for r in records if r["bare_typed"] is True),
    "per_source_file": {p.name: sum(1 for r in records if r["source_file"] == p.name) for p in GROUP_FILES},
    # generated_checksum is a STRING naming the rule ("" == none), not a bool
    "generated_checksum_nonempty": sorted(r["id"] for r in records if r["generated_checksum"]),
}
records_total = len(records)

# --------------------------------------- C) checksum validity of the pinned samples
sys.path.insert(0, str(FROZEN_V6_CHECKSUM.parent))
import checksum_v6  # type: ignore  # noqa: E402
pin(FROZEN_V6_CHECKSUM)

BIK = "044525225"
validity = []
for r in records:
    if not r["generated_checksum"] or not isinstance(r["sample"], str):
        continue
    try:
        ok = checksum_v6.validate_account(r["sample"], BIK) if r["id"] == "BANK_ACCOUNT" else checksum_v6.validate(r["id"], r["sample"])
    except Exception as exc:  # a type the validator cannot read is reported, not guessed
        ok = f"ERROR:{type(exc).__name__}"
    validity.append({"id": r["id"], "sample": r["sample"], "rule": r["generated_checksum"], "valid": ok})

n_cs = len(validity)
n_valid = sum(1 for v in validity if v["valid"] is True)
checksum = {
    "generated_checksum_types": n_cs,
    "samples_valid": n_valid,
    "all_samples_valid": n_valid == n_cs,
    "rows": validity,
    # v6 §6.3 line semantics reproduced in V0/checks/v0_checks.py: a HIT == substitute FAILS
    "v0_q2_hit_line": n_cs - n_valid,
    "v0_m8_hit_line": n_cs - n_valid,
    "q2_equals_m8_in_that_formula": True,
}

# ------------------------------------------- D) numeric demotion guard is digits-only
src = pin(STRUCTURED).read_text(encoding="utf-8")
guard_line = [ln.strip() for ln in src.splitlines()
              if "_NUMERIC_KEY_TYPES and not any(c.isdigit()" in ln]
demotion = {
    "guard_source_line": guard_line,
    "guard_is_no_digits_only": bool(guard_line) and "not any(c.isdigit()" in guard_line[0],
    "note": "a value that CONTAINS a digit but is malformed is not covered by this guard",
}

# ------------------------------------------------------- E) in-memory vault exists
test_loop = pin(ROOT / "prototype/test_loop.py").read_text(encoding="utf-8")
sqlite_setup = pin(ROOT / "prototype/pseudex/sqlite_setup.py").read_text(encoding="utf-8")
vault_py = pin(ROOT / "prototype/pseudex/vault.py").read_text(encoding="utf-8")
in_memory = {
    "test_loop_uses_memory_vault": 'Vault(":memory:"' in test_loop,
    "sqlite_setup_handles_memory": '":memory:"' in sqlite_setup,
    "opaque_is_deterministic_redaction": "NO RENDERER — DETERMINISTIC REDACTION" in vault_py,
    "opaque_original_stored_in_tokens_table": '"original, first_seen, name_key' in vault_py,
}

# ------------------------------------------------------------ F) NEREL version reads
a1_inv = ROOT / "research/quality-sprint-2026-09-30/work/A1/inventory_sources.py"
inv_src = pin(a1_inv).read_text(encoding="utf-8")
nerel_reads = sorted({ln.strip() for ln in inv_src.splitlines()
                      if "nerel" in ln.lower() and ("v1.0" in ln or "v1.1" in ln)})

# ------------------------------------------------------ G) budget arithmetic re-check
prop = json.loads((ROOT / "research/quality-sprint-2026-09-30/work/A1/ACCEPTANCE-PROPOSAL.json").read_text(encoding="utf-8"))
pin(ROOT / "research/quality-sprint-2026-09-30/work/A1/ACCEPTANCE-PROPOSAL.json")
pi = prop["cost_estimate_human_review_items"]["planning_inputs"]["unit_counts"]
native_only = pi["native_positive_units"] + pi["ppv_spans"] + pi["specificity_negatives"]
full = native_only + pi["v6_new_type_occurrences_est"] + pi["temp_secret_fixture_units_est"]
budget = {
    "native_only_recomputed": native_only,
    "native_only_declared": prop["cost_estimate_human_review_items"]["planning_result"]["units_native_only"],
    "full_scope_recomputed": full,
    "full_scope_declared": prop["cost_estimate_human_review_items"]["planning_result"]["units_full_scope"],
    "labeler_items_full_recomputed": 2 * full,
    # the support floor the budget does NOT cover: 55 new types x 300 independent units
    "support_floor_55x300": 55 * 300,
    "budget_covers_support_floor": full >= 55 * 300,
    "note": "17.8-18.6k review items is a staged estimate; it is below the 16 500 positive units the 300/type floor implies before registers, PPV, negatives and cluster de-duplication",
}

facts = {
    "script": "verify_facts.py",
    "scope": "independent read-only re-derivation; no detector call, no engine import, no network",
    "python": sys.version.split()[0],
    "funnel_v0": funnel,
    "v6_registry": registry,
    "checksum": checksum,
    "c0_demotion_guard": demotion,
    "c0_in_memory_and_opaque": in_memory,
    "a1_nerel_version_refs_in_inventory": nerel_reads,
    "a1_budget_arithmetic": budget,
    "inputs": inputs,
    "commands": commands,
    "exit": 0,
}

(OUT / "FACTS.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in facts.items() if k not in ("inputs",)}, ensure_ascii=False, indent=2))
print("OUTPUT_SHA256", hashlib.sha256((OUT / "FACTS.json").read_bytes()).hexdigest())
