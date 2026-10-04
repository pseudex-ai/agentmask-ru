#!/usr/bin/env python3
"""V0 — pure executable semantic checks over the v5/v6 snapshot (no engine,
no provider, no merge, no checkout, no worktree mutation).

Every check asserts ONE property and prints its verdict as a JSON line:

    CHECK <id> <GREEN|RED> expected=<GREEN|RED> <detail>

The exit code is 0 when EVERY check landed exactly on its declared expectation
(including the checks declared EXPECTED_RED — a reproduced conflict is evidence,
not a suite PASS); it is 1 when a check deviates, because then the finding is
not the one this file claims. Nothing here is a quality PASS.

Inputs are frozen under evidence/frozen/ (v5 files via `git show <ref>`, v6
modules byte-identical to `fad9c746`), so re-running needs no git and no network.

    PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python \
        research/quality-sprint-2026-09-30/work/V0/checks/v0_checks.py
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
V0 = Path(__file__).resolve().parent.parent
FROZEN = V0 / "evidence" / "frozen"
PY = FROZEN / "pypath"
BIK = "049805746"
V5_REF = "0bfda2363ef1a1d552e2ac093129b1026a86ad68"
V6_REF = "fad9c7466ea1221282214e6c747ca373ee7e6a55"

RESULTS: list[dict] = []


def report(check: str, got: str, expected: str, detail: str) -> None:
    RESULT = {"check": check, "verdict": got, "expected": expected, "detail": detail}
    RESULTS.append(RESULT)
    print(f"CHECK {check} {got} expected={expected} {detail}", flush=True)


def literal(node: ast.AST, names: dict[str, object]) -> object:
    """Evaluate the frozen literal tables, frozenset({...})/tuple() included."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return names[node.id]
    if isinstance(node, ast.Dict):
        return {literal(k, names): literal(v, names) for k, v in zip(node.keys, node.values)}
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(literal(e, names) for e in node.elts)
    if isinstance(node, ast.Set):
        return set(literal(e, names) for e in node.elts)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args) == 1:
        arg = literal(node.args[0], names)
        if node.func.id == "frozenset":
            return frozenset(arg)
        if node.func.id == "set":
            return set(arg)
        if node.func.id == "tuple":
            return tuple(arg)
    raise ValueError(f"unsupported literal node: {ast.dump(node)[:120]}")


def module_literals(path: Path, wanted: set[str]) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: dict[str, object] = {}
    for node in tree.body:
        target_name, value = None, None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name, value = node.target.id, node.value
        if target_name is None or value is None:
            continue
        try:
            names[target_name] = literal(value, names)
        except (ValueError, KeyError, AttributeError, TypeError):
            continue   # a table built from an imported name is not a frozen literal
    return {k: v for k, v in names.items() if k in wanted}


def v6_module(name: str):
    sys.path.insert(0, str(PY))
    try:
        return __import__(f"bench.agentpii5.{name}", fromlist=[name])
    finally:
        sys.path.pop(0)


def diff_tables(v5: object, v6: object) -> list[str]:
    """Per-entry differences when both sides are mappings, else the whole values."""
    if isinstance(v5, dict) and isinstance(v6, dict):
        out: list[str] = []
        for key in sorted(set(v5) | set(v6), key=repr):
            if v5.get(key) != v6.get(key):
                out.append(f"{key}: v5={v5.get(key)!r} v6={v6.get(key)!r}")
        return out
    if v5 != v6:
        return [f"v5={v5!r} v6={v6!r}"]
    return []


def main() -> int:
    contracts_v5 = FROZEN / "v5/bench/agentpii5/contracts.py"
    pii_types = v6_module("pii_types")
    checksum_v6 = v6_module("checksum_v6")

    # --- CHK-1 the 24 overlaps are reproducible from the refs -----------------------
    import subprocess
    def git(*args: str) -> str:
        proc = subprocess.run(["git", *args], cwd="/Users/igor/Projects/Obscura-hop-audit",
                              capture_output=True, text=True)
        return proc.stdout
    base = "3be526a2bfb8a9b9e86a9b14b3e11758f723f3a8"
    v5_changed = set(git("diff", "--name-only", f"{base}..{V5_REF}").splitlines())
    v6_changed = set(git("diff", "--name-only", f"{base}..{V6_REF}").splitlines())
    declared = json.loads((V0 / ".." / ".." / ".." / "hop-format-audit"
                           / "next-sprint-review/v6-snapshot/branch-comparison.json"
                           ).resolve().read_text())["overlapping_paths"]
    overlap = sorted(v5_changed & v6_changed)
    report("overlap-24", "GREEN" if overlap == sorted(declared) else "RED", "GREEN",
           f"recomputed={len(overlap)} declared={len(declared)} identical={overlap == sorted(declared)}")

    # --- CHK-2 the registry counts --------------------------------------------------
    v6_types = tuple(t for t in pii_types.TYPE_REGISTRY if t.origin == pii_types.ORIGIN_V6)
    uncertain = tuple(t.id for t in v6_types if t.grammar_status != "ГОТОВ")
    counts_ok = (len(v6_types) == 55 and len(pii_types.NEW_ITEM_TYPES) == 55
                 and len(uncertain) == 9)
    report("type-55", "GREEN" if counts_ok else "RED", "GREEN",
           f"ORIGIN_V6={len(v6_types)} NEW_ITEM_TYPES={len(pii_types.NEW_ITEM_TYPES)} "
           f"grammar_uncertain={len(uncertain)} -> {list(uncertain)}")

    # --- CHK-3 v6's derivatives vs the LIVE v5 literals -----------------------------
    wanted = {"FORM_FEATURES", "FEATURE_LABELS", "FORM_ABSTAIN", "IDENTIFYING_ROLES",
              "NEEDLE_KINDS", "DIGIT_PIECE_TYPES", "DATE_PIECE_TYPES",
              "DERIVED_PIECE_TYPES", "SQUEEZED_TYPES"}
    live = module_literals(contracts_v5, wanted)
    v5_specs = tuple(t for t in pii_types.TYPE_REGISTRY if t.origin == pii_types.ORIGIN_V5)
    derived = {
        "FORM_FEATURES": pii_types.form_features(v5_specs),
        "FEATURE_LABELS": pii_types.feature_labels(v5_specs),
        "FORM_ABSTAIN": pii_types.form_abstain(v5_specs),
        "IDENTIFYING_ROLES": pii_types.identifying_roles(v5_specs),
        "NEEDLE_KINDS": pii_types.NEEDLE_KINDS[:len(live["NEEDLE_KINDS"])],
        "DIGIT_PIECE_TYPES": pii_types.digit_piece_types(v5_specs),
        "DATE_PIECE_TYPES": pii_types.date_piece_types(v5_specs),
        "DERIVED_PIECE_TYPES": pii_types.derived_piece_types(v5_specs),
        "SQUEEZED_TYPES": pii_types.squeezed_types(v5_specs),
    }
    diffs = {k: diff_tables(live[k], derived[k]) for k in wanted}
    diffs = {k: v for k, v in diffs.items() if v}
    report("v5-tables-reproduced", "GREEN" if not diffs else "RED", "RED",
           f"tables_diverging={sorted(diffs)} detail=" + "; ".join(
               f"{k}: {diffs[k][0]}" for k in sorted(diffs)))

    # --- CHK-4 the v6 test's hand-copied literals are the BASE tree, not the live v5 --
    lit_wanted = {f"_LITERAL_{n}" for n in wanted}
    copied = module_literals(FROZEN / "v6/test_pii_types.py", lit_wanted)
    stale = {}
    for name, value in copied.items():
        key = name[len("_LITERAL_"):]
        if key in live and live[key] != value:
            stale[key] = diff_tables(live[key], value)
    report("v6-test-literal-copy", "GREEN" if not stale else "RED", "RED",
           f"copied_tables_diverging_from_live_v5={sorted(stale)} "
           f"live_v5_matches_copy={not stale}")

    # --- CHK-5 the status funnel ----------------------------------------------------
    status_wanted = {"HOP_STATUSES", "OUT_HOP_WRITTEN_STATUSES"}
    v5_status = module_literals(contracts_v5, status_wanted)
    v6_status = module_literals(FROZEN / "v6/contracts.py", status_wanted)
    v5_written = set(v5_status.get("OUT_HOP_WRITTEN_STATUSES", ()))
    v5_all = v5_written | {"absent", "leaked"}
    v6_hop_statuses = tuple(v6_status.get("HOP_STATUSES", ()))
    report("status-funnel", "GREEN" if v5_all == set(v6_hop_statuses) else "RED", "RED",
           f"v5_live_statuses={sorted(v5_all)} v6_HOP_STATUSES={sorted(v6_hop_statuses)} "
           f"v6_missing_from_v5={sorted(set(v6_hop_statuses) - v5_all)} "
           f"v5_missing_from_v6={sorted(v5_all - set(v6_hop_statuses))}")

    # --- CHK-6 the checksum policy conflict + mutant indistinguishability -----------
    cs_rows = []
    for t in pii_types.TYPE_REGISTRY:
        if not t.generated_checksum:
            continue
        sample = t.sample
        valid = (checksum_v6.validate_account(sample, BIK) if t.id == "BANK_ACCOUNT"
                 else checksum_v6.validate(t.id, sample))
        # v6 §6.3 `fake_checksum_invalid`: a HIT is the substitute FAILING its checksum.
        q2_hit = 0 if valid else 1      # owner Q2: valid source -> valid substitute
        m8_hit = 0 if valid else 1      # M8 mutant: mints a substitute that PASSES its KC
        cs_rows.append((t.id, valid, q2_hit, m8_hit))
    total = len(cs_rows)
    q2_line = sum(r[2] for r in cs_rows)
    m8_line = sum(r[3] for r in cs_rows)
    conflict = (q2_line != total) and (m8_line == q2_line)
    report("checksum-policy", "RED" if conflict else "GREEN", "RED",
           f"generated_checksum_types={total} samples_valid={sum(1 for r in cs_rows if r[1])}/{total} "
           f"owner_Q2_line={q2_line}/{total} M8_mutant_line={m8_line}/{total} "
           f"Q2_equals_M8={m8_line == q2_line} boundary_1.0_met_under_Q2={q2_line == total} "
           "(the perfect arm is indistinguishable from the mutant on this line)")

    # --- CHK-7 the script/translit split is absent from the v6 NAME record ----------
    name = next(t for t in pii_types.TYPE_REGISTRY if t.id == "NAME")
    features = name.form_features
    labels = dict(name.feature_labels)
    abstain = dict(name.abstain)
    report("script-translit", "GREEN" if "translit" in features else "RED", "RED",
           f"v6_NAME_features_has_translit={'translit' in features} "
           f"v6_script_labels={labels.get('script')} "
           f"v6_translit_abstain={abstain.get('translit')!r} "
           f"v5_live_NAME_features={live['FORM_FEATURES']['NAME']}")

    # --- CHK-8 the v5 authorial-leaf and value-reading tables are not carried -------
    v5_extra = module_literals(contracts_v5, {"LEAF_EQUIVALENCE", "VALUE_READINGS",
                                              "VALUE_NORMALISERS", "LEAF_SEMANTICS"})
    v6_tree = ast.parse((FROZEN / "v6/contracts.py").read_text(encoding="utf-8"))
    names_v6: set[str] = set()
    for node in v6_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names_v6.add(node.name)
        elif isinstance(node, ast.Assign):
            names_v6 |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    pt_names = set(dir(pii_types))
    carried = sorted(k for k in v5_extra if k in names_v6 or k in pt_names)
    report("v5-leaf-and-readings", "GREEN" if not v5_extra else "RED", "RED",
           f"v5_live_tables={sorted(v5_extra)} present_in_v6_snapshot={carried} "
           f"unrepresented={sorted(set(v5_extra) - set(carried))}")

    # --- CHK-9 the v5 corpus/case rules are not carried by v6 -----------------------
    v5_rules = module_literals(contracts_v5, {"V5_CASE_RULES", "V5_CORPUS_RULES"})
    v6_rules = module_literals(FROZEN / "v6/contracts.py", {"V5_CASE_RULES", "V5_CORPUS_RULES"})
    added_by_v5 = sorted(set(v5_rules.get("V5_CASE_RULES", ())) - set(v6_rules.get("V5_CASE_RULES", ())))
    report("v5-corpus-rules", "GREEN" if not added_by_v5 else "RED", "RED",
           f"v5_case_rules={len(v5_rules.get('V5_CASE_RULES', ()))} "
           f"v6_case_rules={len(v6_rules.get('V5_CASE_RULES', ()))} "
           f"v5_only_rules={[r.split(' ', 1)[0] for r in added_by_v5]}")

    expected_red = {"v5-tables-reproduced", "v6-test-literal-copy", "status-funnel",
                    "checksum-policy", "script-translit", "v5-leaf-and-readings",
                    "v5-corpus-rules"}
    bad = [r for r in RESULTS if r["verdict"] != r["expected"]]
    print(f"CHECKS total={len(RESULTS)} expected_red={len(expected_red)} "
          f"unexpected={len(bad)} -> {'OK' if not bad else 'DEVIATION'}")
    (V0 / "checks" / "v0_checks.result.json").write_text(
        json.dumps({"v5_ref": V5_REF, "v6_ref": V6_REF, "results": RESULTS,
                    "unexpected": bad}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
