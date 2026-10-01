#!/usr/bin/env python3
"""V0 — build COMPATIBILITY24.json, TYPE55.json and INPUTS.json from the frozen
snapshot. Read-only with respect to the repository: writes only under work/V0/.

    PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python \
        research/quality-sprint-2026-09-30/work/V0/checks/build_artifacts.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
V0 = Path(__file__).resolve().parent.parent
ROOT = V0.parents[3]
FROZEN = V0 / "evidence/frozen"
PY = FROZEN / "pypath"
V5_REF = "0bfda2363ef1a1d552e2ac093129b1026a86ad68"
V6_REF = "fad9c7466ea1221282214e6c747ca373ee7e6a55"
BASE = "3be526a2bfb8a9b9e86a9b14b3e11758f723f3a8"
EVIDENCE_COMMIT = "890c50849a326f882eac336ba4e38c91171de473"

# path -> (current_must_preserve, v6_addition, risk, test_acceptance)
ROWS: dict[str, tuple[str, str, str, str]] = {
    "CLAUDE.md": (
        "The v5 statements about live code and the embedded MAP copy; `wiki/check.py --sync` "
        "requires the embedded block to equal `wiki/MAP.md` byte-for-byte.",
        "A new §4.1.1 describing the v6 modules in `bench/agentpii5/`.",
        "Doc drift: the v6 section can be merged while a v5 paragraph it touches becomes false, "
        "and the embedded-map invariant only catches the copy, not the prose.",
        "`python3 wiki/check.py` (embedded copy == MAP.md; every named path exists)"),
    "prototype/bench/agentpii5/contracts.py": (
        "The v5 semantic tables edited on this branch: `FORM_FEATURES`/`FEATURE_LABELS`/`FORM_ABSTAIN` "
        "carry the `script` (alphabet) vs `translit` (romanization) SPLIT; `LEAF_EQUIVALENCE` + "
        "`semantic_leaf`/`is_canonical_leaf`/`equivalent_leaves`/`equivalence_problems`; `VALUE_READINGS`/"
        "`VALUE_NORMALISERS`; `OUT_HOP_WRITTEN_STATUSES`/`OUT_HOP_RESTORABLE_STATUSES` and the eight "
        "status-split metric rows; `V5_CASE_RULES` R22/R23; `ModelResponse`/`ModelTrace`.",
        "`TYPES = v4.TYPES + pii_types.NEW_ITEM_TYPES`; re-exports of `INDUSTRIES`, `V6_AXES`, "
        "`V6_PROVENANCE_KINDS`, `V6_DIR`, `CaseV6Meta`, `ProcedureRecord`, `V6_NEGATIVE_FAMILIES`, "
        "`V5_TOOL_NAMES`; `CaseV5.v6`; `ArmRunV5.message_pieces`; and the DERIVATION of the nine "
        "literal tables from `pii_types.TYPE_REGISTRY`.",
        "THE HIGHEST-RISK ROW. v6 replaces the same literal blocks v5 edited with a registry whose "
        "hand-transcribed NAME record predates the `script`/`translit` split, so the v6 direction of "
        "the edge silently rolls back the v5 decision (CHK-3/CHK-7).",
        "`python3 -m bench.agentpii5.test_contracts`, `...test_spec_form`, `...test_pii_types`, "
        "and V0 CHK-3/CHK-4/CHK-5/CHK-7/CHK-8/CHK-9 in `checks/v0_checks.py`"),
    "prototype/bench/agentpii5/fixtures.py": (
        "The closed v5 `FIXTURES` surface (every v5 metric has zero/one/adversarial), plus the v5 "
        "`*_written` fixture families and their name constants.",
        "`V6_FIXTURES` for the three OD-54 rows, deliberately OUTSIDE `FIXTURES`; `_with_message_pieces`; "
        "`v6=None` in `_case`.",
        "Two writers of one table: a merge that folds `V6_FIXTURES` into `FIXTURES` turns the v5 gate "
        "red; the `fake_checksum_invalid` fixtures encode «a Luhn-valid substitute is a MISS», which is "
        "the owner-Q2 conflict in fixture form.",
        "`python3 -m bench.agentpii5.test_fixtures`, `...test_metrics_v6` (V6_FIXTURES names)"),
    "prototype/bench/agentpii5/form.py": (
        "`name_translit` (the romanization extractor the v5 split added) and its registration in "
        "`FEATURE_EXTRACTORS`.",
        "The NAME row of `FEATURE_EXTRACTORS` is re-read from `pii_types` form features.",
        "v6's derived NAME feature tuple has no `translit`, so the extractor becomes unreachable; the "
        "form line silently stops asking the romanization question instead of failing loudly.",
        "`python3 -m bench.agentpii5.test_form`, `...test_spec_form`"),
    "prototype/bench/agentpii5/harness.py": (
        "The v5 connector/gateway-hook machinery, delivery manifest capture and scaled timeouts.",
        "Only `main()` wiring for the v6 corpus plus `contracts.PSEUDEX_ALLOWED_MODULES` admitting "
        "`bench.agentpii5.regress_print`.",
        "Low textual overlap, high semantic: the v6 corpus must run through the SAME v5 production path, "
        "or a v6 number is not comparable to a v5 number.",
        "`python3 -m bench.agentpii5.test_cli`, run-file byte comparison of an old-corpus replay (F7)"),
    "prototype/bench/agentpii5/judge.py": (
        "`ConnectedJudgeConfig`/`_ask_connector` and the v5 `hunted_types` contract "
        "(`(*NEEDLE_TYPES, 'PLATE')` when a plate shape is present).",
        "A v6 hunt-shape gate: `hunted_types` additionally returns registry types whose `hunt` is "
        "`always`/`covered` AND whose grammar regex fullmatches the folded surface.",
        "`hunted_types` is consumed by privacy scanning; widening it changes the denominator of every "
        "judge reading, and the v5 PLATE path must keep its exact output.",
        "`python3 -m bench.agentpii5.test_judge`, `...test_judge_v6`"),
    "prototype/bench/agentpii5/metrics.py": (
        "The closed v5 `METRIC_FUNCTIONS`/`contracts.METRICS` surface, the status-split metrics "
        "(`out_written`, `out_no_mint`, `out_engine_kept`, `out_not_masked`, `out_leaf_foreign`, "
        "`end_to_end_written`, `chain_*_written`, `multi_all_out_written`) and the v5 `value_matches`/"
        "`role_matches` behaviour for the eleven v5 types.",
        "v6 value comparison by `value_notation`, `NEG_TAG_PREFIX`, `V6_METRIC_FUNCTIONS` "
        "(`typed_user`/`fake_checksum_invalid`/`overmask_result`) kept outside the v5 dict, and the "
        "`type_class` axis.",
        "`fake_checksum_invalid` redefines the correct arm: under owner Q2 a valid source mints a VALID "
        "substitute, which this line scores 0 (CHK-6); `_record_clean` skipping `neg:` tags also changes "
        "the v5 `toolresult_masked` reading wherever a negative is present.",
        "`python3 -m bench.agentpii5.test_metrics`, `...test_metrics_v6`, V0 CHK-6"),
    "prototype/bench/agentpii5/observe.py": (
        "`VALUE_READINGS` as the ONE reading of «same value» (`_leaf_value_ok`, `_phone_equal`, "
        "`_name_equal`, `_place_equal`, `equivalent_out_leaf`, `call_ordinal_of`) and the v5 hoр statuses "
        "`engine_kept`/`not_masked`/`leaf_foreign` in place of the single `unmasked`.",
        "Three new needle kinds (`glyph`, `octets`, `ipv6`), `glyph_fold`, and the IPv4/IPv6 span "
        "finders.",
        "v6's `contracts.HOP_STATUSES` still names `unmasked` and omits the three split statuses, so the "
        "status funnel the v5 branch built has no reader on the v6 side (CHK-5).",
        "`python3 -m bench.agentpii5.test_observe`, `...test_observe_v6`, V0 CHK-5"),
    "prototype/bench/agentpii5/perfect.py": (
        "The v5 perfect-arm semantics: a substitute keeps the source's validity for a checksum type "
        "(product invariant #structured-ids) and `reverse_action_order`.",
        "`mint_v6` — a class-preserving alphanumeric shift that RE-MINTS until a `generated_checksum` "
        "type FAILS its own checksum (R6-39), with a digits-only fallback for structural identifiers.",
        "DECISIVE CONFLICT: R6-39 requires invalid fakes, owner Q2 requires validity inherited from the "
        "source, and the engine invariant requires checksum-VALID fakes from impossible ranges. Three "
        "contracts, one line (CHK-6).",
        "`python3 -m bench.agentpii5.test_perfect`, `...test_perfect_v6`, V0 CHK-6"),
    "prototype/bench/agentpii5/records.py": (
        "Byte-identical old-corpus run rows: the v5 `_v5_block` keys and the model-trace record added "
        "on this branch.",
        "`message_pieces` is written ONLY when non-empty, so a v5 arm record stays byte-for-byte the row "
        "it was.",
        "Both branches add optional fields to one JSON row; a merge that always writes them (or reorders "
        "keys) breaks the frozen-counter comparison the whole sprint leans on.",
        "`python3 -m bench.agentpii5.test_observe`, old-corpus replay byte comparison (F7)"),
    "prototype/bench/agentpii5/report.py": (
        "`beside_of`/`FrozenParts`/`axis_cells` and every v5 printed line, including the eight "
        "status-split diagnostic rows.",
        "`has_v6_case`, `v6_axis_rows`, `v6_type_slice_lines`, `v6_new_row_lines`, "
        "`_calibration_new_types` — the v6 sections print only when a v6 case is present.",
        "A report that gates new rows on `has_v6_case` is safe; a merge that prints v6 rows "
        "unconditionally turns every old-corpus report red and can hide a v5 line.",
        "`python3 -m bench.agentpii5.test_report`, `...test_report_v6`, G2 meter gate"),
    "prototype/bench/agentpii5/revise.py": (
        "`_dedup_equivalent_leaves` and the v5 `optional` reading (a hop on a generic role is optional).",
        "Two changed lines only.",
        "Low overlap; the `optional` docstring/fact is edited on the v5 side and read by the v6 builder.",
        "`python3 -m bench.agentpii5.test_revise`"),
    "prototype/bench/agentpii5/scenarios5/common.py": (
        "`arg_hop` setting `optional = (not spec.required) or spec.role in GENERIC_PIECE_ROLES`, so a "
        "REQUIRED hop on a settlement is never declared.",
        "One changed line.",
        "A v6 builder that declares a required city hop reintroduces a promise no correct gateway can "
        "keep — the v5 fix that removed it is one line away from the v6 edit.",
        "`python3 -m bench.agentpii5.test_scenarios5`"),
    "prototype/bench/agentpii5/schema.py": (
        "`_superseded_ids` and R23 (a required OUT hop must not name a superseded item).",
        "`_r02_suppressed` — v6 negatives admitted as a known «negative family» line in R02.",
        "Both branches add a suppression clause to the same rule checker; a merge can drop one and the "
        "corpus stays silently invalid.",
        "`python3 -m bench.agentpii5.test_schema` (v5 added `test_r22`/`test_r23`)"),
    "prototype/bench/agentpii5/test_cli.py": ("The v5 CLI test.", "Six added lines.",
        "Small.", "`python3 -m bench.agentpii5.test_cli`"),
    "prototype/bench/agentpii5/test_contracts.py": (
        "The v5 contract tests (leaf equivalence, value readings, R22/R23).",
        "Nine added / five removed lines.", "Small, but this is the file that must pin the split.",
        "`python3 -m bench.agentpii5.test_contracts`"),
    "prototype/bench/agentpii5/test_form.py": ("The v5 form tests.", "Seven added / five removed.",
        "Small.", "`python3 -m bench.agentpii5.test_form`"),
    "prototype/bench/agentpii5/test_judge.py": ("The v5 judge test.", "One line.",
        "Small.", "`python3 -m bench.agentpii5.test_judge`"),
    "prototype/bench/agentpii5/test_observe.py": (
        "`test_second_declared_hop_on_a_claimed_leaf_is_absent` (the v5 R22 watcher).",
        "`_registry_values`, twenty-two added lines.", "Small.",
        "`python3 -m bench.agentpii5.test_observe`"),
    "prototype/bench/agentpii5/test_schema.py": (
        "`test_r22`, `test_r23`, `_address_case`, `_correction_case`.",
        "One line.", "Small, but the only executable pin on R22/R23.",
        "`python3 -m bench.agentpii5.test_schema`"),
    "prototype/bench/agentpii5/test_spec_form.py": (
        "The v5 spec/form tests.", "`V5_TYPES` and fifteen added lines.",
        "The v6 test pins the v5 type list separately — a second copy of `TYPES`.",
        "`python3 -m bench.agentpii5.test_spec_form`"),
    "wiki/INDEX.md": ("The v5 rows for the hop-format audit and the v5 model-connector docs.",
        "Two added lines.", "Cheap to merge, but `wiki/check.py` demands every named path exist.",
        "`python3 wiki/check.py`"),
    "wiki/MAP.md": ("The v5 module rows (connectors, live runner, payload canaries, vault helpers).",
        "The §4.1.1 v6 module block, 193 added lines.",
        "Both branches add rows for the SAME directory; a merge can keep one side's row and lose the "
        "other's, and the embedded copy in CLAUDE.md must follow.",
        "`python3 wiki/check.py`; `python3 wiki/check.py --sync` must be a no-op after the merge"),
    "wiki/STATE.md": (
        "D-070 … D-076 as the v5 branch defines them (current-hop PHONE form, vault identity, classes "
        "А/Б/Г/Д).",
        "D-068/D-069/D-070 re-stated for v6 (pilot types, pilot tools, full corpus).",
        "HARD ID COLLISION: both branches use D-068, D-069 and D-070 with different dates and different "
        "decisions. A merge either duplicates an id or silently keeps one meaning; no owner decision "
        "covers it (O-V6-3).",
        "`python3 wiki/check.py` (it does not validate id uniqueness — no instrument catches this)"),
}


CONFLICT_CHECKS: dict[str, list[str]] = {
    "prototype/bench/agentpii5/contracts.py": [
        "v5-tables-reproduced", "v6-test-literal-copy", "script-translit",
        "v5-leaf-and-readings", "v5-corpus-rules", "status-funnel"],
    "prototype/bench/agentpii5/metrics.py": ["checksum-policy", "status-funnel"],
    "prototype/bench/agentpii5/observe.py": ["status-funnel"],
    "prototype/bench/agentpii5/perfect.py": ["checksum-policy"],
    "prototype/bench/agentpii5/fixtures.py": ["checksum-policy"],
    "prototype/bench/agentpii5/form.py": ["script-translit"],
    "prototype/bench/agentpii5/judge.py": [],
    "wiki/STATE.md": ["no-executable-check: D-068/D-069/D-070 carry different decisions on the "
                      "two branches; wiki/check.py does not validate id uniqueness"],
}


def git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} -> {proc.returncode}: {proc.stderr[:300]}")
    return proc.stdout


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blob_sha(path: str) -> str:
    return git("rev-parse", f"{V5_REF}:{path}").strip()


def main() -> int:
    raw = json.loads((V0 / "evidence/compat_raw.json").read_text(encoding="utf-8"))
    rows = []
    for index, row in enumerate(raw["rows"], start=1):
        path = row["path"]
        preserve, addition, risk, accept = ROWS[path]
        rows.append({
            "id": f"C{index:02d}",
            "path": path,
            "v5_added_lines_removed": row["v5_stat"],
            "v6_added_lines_removed": row["v6_stat"],
            "v5_changed_symbols": row["v5_added_symbols"],
            "v6_changed_symbols": row["v6_added_symbols"],
            "current_must_preserve": preserve,
            "v6_addition": addition,
            "risk": risk,
            "test_acceptance": accept,
            "conflict_checks": CONFLICT_CHECKS.get(path, []),
        })
    compat = {
        "task": "V0",
        "v5_ref": V5_REF,
        "v6_ref": V6_REF,
        "base_ref": BASE,
        "evidence_commit": EVIDENCE_COMMIT,
        "overlap_count_recomputed": len(rows),
        "overlap_count_declared": 24,
        "reproduced_exactly": len(rows) == 24,
        "product_source_unchanged_between_v5_and_evidence_commit": True,
        "no_merge_performed": True,
        "rows": rows,
    }
    (V0 / "COMPATIBILITY24.json").write_text(
        json.dumps(compat, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- TYPE55.json ---------------------------------------------------------------
    sys.path.insert(0, str(PY))
    from bench.agentpii5 import pii_types  # noqa: E402
    inventory = json.loads((V0.parents[3] / "research/hop-format-audit/next-sprint-review/"
                            "v6-snapshot/registry-inventory.json").read_text(encoding="utf-8"))
    by_id = {row["type"]: row for row in inventory}
    types = []
    for spec in pii_types.TYPE_REGISTRY:
        if spec.origin != pii_types.ORIGIN_V6:
            continue
        inv = by_id.get(spec.id, {})
        types.append({
            "type": spec.id,
            "type_class": spec.type_class,
            "grammar_status": spec.grammar_status,
            "grammar_uncertain": spec.grammar_status != "ГОТОВ",
            "industries": list(spec.industries),
            "industries_registry_md": inv.get("industries", []),
            "generated_checksum": spec.generated_checksum,
            "value_notation": spec.value_notation,
            "engine_labels": list(spec.engine_labels),
            "mint": spec.mint,
            "hunt": spec.hunt,
            "source_pointer": "research/hop-format-audit/next-sprint-review/v6-snapshot/"
                              "tz-agentpii6-registry.md + pii_types.py (blob "
                              "ee0544665b8aeab4f421eb8fadf62697306f3a4a)",
        })
    type55 = {
        "task": "V0",
        "v6_ref": V6_REF,
        "count_recomputed": len(types),
        "count_declared": 55,
        "grammar_uncertain_recomputed": sorted(t["type"] for t in types if t["grammar_uncertain"]),
        "grammar_uncertain_declared": 9,
        "v5_item_types": sorted(s.id for s in pii_types.TYPE_REGISTRY
                                if s.origin == pii_types.ORIGIN_V5),
        "claim_boundary": "These are REGISTRY records, not engine support. No type here is claimed "
                          "detected, substituted or restored by the product; native support is proven "
                          "per type after V1/N1.",
        "types": types,
    }
    (V0 / "TYPE55.json").write_text(json.dumps(type55, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- INPUTS.json ----------------------------------------------------------------
    snapshot_dir = ROOT / "research/hop-format-audit/next-sprint-review/v6-snapshot"
    snapshot_files = {
        "pii_types.py": "prototype/bench/agentpii5/pii_types.py",
        "pii_types_a.py": "prototype/bench/agentpii5/pii_types_a.py",
        "pii_types_b.py": "prototype/bench/agentpii5/pii_types_b.py",
        "pii_types_c.py": "prototype/bench/agentpii5/pii_types_c.py",
        "contracts_v6.py": "prototype/bench/agentpii5/contracts_v6.py",
        "tz-agentpii6.md": "docs/tz-agentpii6.md",
        "tz-agentpii6-registry.md": "docs/tz-agentpii6-registry.md",
        "v6-evidence-matrix.md": "prototype/bench/agentpii5/review/v6-evidence-matrix.md",
        "v6-tools-gap-study.md": "prototype/bench/agentpii5/review/v6-tools-gap-study.md",
        "registry-inventory.json": None,
        "branch-comparison.json": None,
    }
    frozen_files = sorted(p for p in FROZEN.rglob("*") if p.is_file())
    inputs = {
        "task": "V0",
        "purpose": "read-only v5/v6 semantic compatibility evidence; no merge, no product patch",
        "refs": {
            "v5": V5_REF, "v6": V6_REF, "base": BASE,
            "evidence_commit": EVIDENCE_COMMIT,
            "evidence_commit_touches_prototype": False,
            "branch": git("branch", "--show-current").strip(),
        },
        "snapshot_dir": str(snapshot_dir),
        "snapshot_sources": {
            name: {"sha256": sha256_file(snapshot_dir / name),
                   "v6_blob": git("rev-parse", f"{V6_REF}:{repo_path}").strip()
                   if repo_path else None,
                   "v6_repo_path": repo_path,
                   "byte_identical_to_v6_ref": (git("hash-object", str(snapshot_dir / name)).strip()
                                                == git("rev-parse", f"{V6_REF}:{repo_path}").strip())
                   if repo_path else None}
            for name, repo_path in snapshot_files.items()},
        "frozen_sources": {str(p.relative_to(FROZEN)): sha256_file(p) for p in frozen_files},
        "frozen_v5_sources_from_ref": {
            f"prototype/bench/agentpii5/{p.name}": blob_sha(f"prototype/bench/agentpii5/{p.name}")
            for p in sorted((FROZEN / "v5/bench/agentpii5").glob("*.py"))},
        "runtime": {"python": sys.version.split()[0],
                    "interpreter": sys.executable,
                    "PYTHONDONTWRITEBYTECODE": "1"},
        "commands": [
            {"cmd": "prototype/.venv/bin/python work/V0/checks/extract_compat.py", "exit": 0,
             "writes": ["evidence/compat_raw.json", "evidence/extract_compat.log"]},
            {"cmd": "prototype/.venv/bin/python work/V0/checks/v0_checks.py", "exit": 0,
             "note": "9 checks, 7 declared RED reproduced, 0 unexpected",
             "writes": ["checks/v0_checks.result.json"]},
            {"cmd": "prototype/.venv/bin/python work/V0/checks/probe_checksum_samples.py", "exit": 0,
             "note": "11/11 registry samples are checksum-valid"},
            {"cmd": "prototype/.venv/bin/python work/V0/checks/build_artifacts.py", "exit": 0},
        ],
        "boundaries": {
            "wrote_only": ["research/quality-sprint-2026-09-30/work/V0/"],
            "no_merge": True, "no_checkout": True, "no_worktree": True, "no_stash": True,
            "no_engine_or_provider": True, "no_installs": True, "no_source_patch": True,
            "read_only_refs": ["prototype/", "licensing/", "wiki/", "old run directories"],
        },
    }
    (V0 / "INPUTS.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote COMPATIBILITY24.json rows={len(rows)}")
    print(f"wrote TYPE55.json types={len(types)} uncertain={len(type55['grammar_uncertain_recomputed'])}")
    print(f"wrote INPUTS.json frozen_files={len(frozen_files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
