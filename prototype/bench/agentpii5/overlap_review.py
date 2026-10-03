# overlap_review.py — S7/G8: the 24 overlap review records, ONE PER PATH, and
# the frozen evidence the merge was resolved against.
#
#     cd prototype && source .venv/bin/activate
#     python3 -m bench.agentpii5.overlap_review            # verify + print
#     python3 -m bench.agentpii5.overlap_review --write     # + the JSON artifact
#
# WHY THIS MODULE EXISTS (V1 SPEC §2, §6 S7). The integration resolved 24 paths
# that BOTH branches touched, by four different mechanisms (`HAND_MERGE_ADDITIVE`,
# `HAND_MERGE_KEEP_V5_SEMANTICS`, `ADOPT_V6`, `GATED_ADOPT_V6`, `KEEP_V5`). A
# decision that exists only in a plan document is not a review record: S7's RED
# clause is that all 24 have a record IN THE INTEGRATION TREE, each naming the
# path, the decision, what was kept, what was adopted, who it was covered by and
# how it is re-checked. `RECORDS` is the transcribed decision table from
# `V1-INTEGRATION-PLAN.json` (`path_decisions`); everything below it is read from
# the LIVE tree, so a record whose path is missing, whose re-check names a module
# that does not exist, or whose decision is outside the closed vocabulary is RED
# here instead of being discovered by a reader.
#
# TWO OF THE 24 HAD NO RESOLUTION RECORD BEFORE S7 (C17 `test_form.py`, C21
# `test_spec_form.py`). Both are `HAND_MERGE_KEEP_V5_SEMANTICS` and both were
# resolved by S3, which did not write a row for them; S7 records them with the
# evidence it does have (the live blob hash and the module's own test, run and
# green in `s7/RED.log` + `s7/GREEN.log`) rather than inventing an S3 hunk
# ledger.
#
# THE FROZEN EVIDENCE. S7 also owns «no old corpus was regenerated over the
# frozen evidence». `FROZEN_INPUTS` pins the five corpus/ladder files by
# sha256, two of them to pins recorded OUTSIDE this branch by earlier stages
# (`work/A1/INVENTORY.json` for the v5 corpora, `work/B0/INPUTS.json`
# `ladder_file_sha256` for the ladder), so the check is «unchanged since a
# witness this task did not write» rather than «unchanged since I looked».
#
# PURE, ENGINE-FREE, deterministic: hashes of files, never a run.
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE: Path = Path(__file__).resolve().parent
GENERATED_BY: str = "bench.agentpii5.overlap_review"
OUT_PATH: Path = HERE / "review" / "overlap-24.json"

# The closed decision vocabulary. A record carrying a sixth name is RED: the
# mechanisms are a small, argued set, and silently adding one would be how a
# third merge strategy enters without anybody deciding it.
DECISIONS: tuple[str, ...] = (
    "HAND_MERGE_ADDITIVE",
    "HAND_MERGE_KEEP_V5_SEMANTICS",
    "ADOPT_V6",
    "GATED_ADOPT_V6",
    "KEEP_V5",
)

# The re-check commands in `red_acceptance` that name a module this package does
# NOT hold, with the reason. Named rather than tolerated: an unlisted miss is a
# RED, and this list is the one place the gap is visible.
KNOWN_ABSENT_TARGETS: dict[str, str] = {
    "bench.agentpii5.test_scenarios5":
        "no such module in this package; the scenarios5 family is driven by "
        "test_build / test_calibration / test_report_gate (each exit 0 in the "
        "S7 sweep), and the plan's C13 row named a module that was never added",
}


@dataclass(frozen=True)
class OverlapRecord:
    """One of the 24 paths both branches touched, transcribed from the plan."""

    id: str
    path: str
    decision: str
    keep_v5: tuple[str, ...]
    adopt_v6: tuple[str, ...]
    owner_covered: tuple[str, ...]
    red_acceptance: tuple[str, ...]


RECORDS: tuple[OverlapRecord, ...] = (
# id, path, decision, keep_v5, adopt_v6, owner_covered, red_acceptance
    OverlapRecord(
        id='C01',
        path='CLAUDE.md',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('the v5 statements about live code', 'the embedded MAP block, byte-equal to wiki/MAP.md'),
        adopt_v6=('the v6 §4.1.1 block describing the agentpii5 v6 modules',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 wiki/check.py', 'python3 wiki/check.py --sync is a no-op after the MAP edit'),
    ),
    OverlapRecord(
        id='C02',
        path='prototype/bench/agentpii5/contracts.py',
        decision='HAND_MERGE_KEEP_V5_SEMANTICS',
        keep_v5=('FORM_FEATURES/FEATURE_LABELS/FORM_ABSTAIN carrying the script(alphabet) vs translit(romanization) SPLIT', 'LEAF_EQUIVALENCE / semantic_leaf / is_canonical_leaf / equivalent_leaves / equivalence_problems', 'VALUE_READINGS / VALUE_NORMALISERS as the ONE reading of «same value»', 'OUT_HOP_WRITTEN_STATUSES / OUT_HOP_RESTORABLE_STATUSES and the eight status-split metric rows', 'V5_CASE_RULES R22/R23', 'ModelResponse / ModelTrace'),
        adopt_v6=('TYPES = v4.TYPES + pii_types.NEW_ITEM_TYPES', 'the INDUSTRIES / V6_AXES / V6_PROVENANCE_KINDS / V6_DIR / CaseV6Meta / ProcedureRecord / V6_NEGATIVE_FAMILIES / V5_TOOL_NAMES re-exports', 'CaseV5.v6', 'ArmRunV5.message_pieces'),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_contracts', 'python3 -m bench.agentpii5.test_spec_form', 'python3 -m bench.agentpii5.test_pii_types', 'the live-file table equality check (stage S4) must read the LIVE contracts.py, never a hand copy'),
    ),
    OverlapRecord(
        id='C03',
        path='prototype/bench/agentpii5/fixtures.py',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('the closed v5 FIXTURES surface (zero/one/adversarial per v5 metric)', 'the v5 *_written fixture families and their name constants'),
        adopt_v6=('V6_FIXTURES kept deliberately OUTSIDE FIXTURES', '_with_message_pieces', 'v6=None in _case'),
        owner_covered=('COV-CHECKSUM-INHERIT', 'MUTANT-LINE-REDEFINE'),
        red_acceptance=('python3 -m bench.agentpii5.test_fixtures', 'python3 -m bench.agentpii5.test_metrics_v6'),
    ),
    OverlapRecord(
        id='C04',
        path='prototype/bench/agentpii5/form.py',
        decision='GATED_ADOPT_V6',
        keep_v5=('name_translit (the romanization extractor the v5 split added)', "its registration FEATURE_EXTRACTORS[('NAME','translit')]"),
        adopt_v6=("the NAME row re-read from the registry's form features",),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_form', 'python3 -m bench.agentpii5.test_spec_form'),
    ),
    OverlapRecord(
        id='C05',
        path='prototype/bench/agentpii5/harness.py',
        decision='ADOPT_V6',
        keep_v5=('the v5 connector/gateway-hook machinery', 'delivery-manifest capture', 'scaled timeouts'),
        adopt_v6=('main() wiring for the v6 corpus', 'contracts.PSEUDEX_ALLOWED_MODULES admitting bench.agentpii5.regress_print'),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_cli', 'old-corpus replay byte comparison (F7)'),
    ),
    OverlapRecord(
        id='C06',
        path='prototype/bench/agentpii5/judge.py',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('ConnectedJudgeConfig / _ask_connector', "the v5 hunted_types contract ((*NEEDLE_TYPES,'PLATE') when a plate shape is present)"),
        adopt_v6=('the v6 hunt-shape gate: hunted_types additionally returns registry types whose hunt is always/covered AND whose grammar fullmatches the folded surface',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_judge', 'python3 -m bench.agentpii5.test_judge_v6'),
    ),
    OverlapRecord(
        id='C07',
        path='prototype/bench/agentpii5/metrics.py',
        decision='HAND_MERGE_KEEP_V5_SEMANTICS',
        keep_v5=('the closed METRIC_FUNCTIONS / contracts.METRICS surface', 'the status-split metrics (out_written, out_no_mint, out_engine_kept, out_not_masked, out_leaf_foreign, end_to_end_written, chain_*_written, multi_all_out_written)', 'v5 value_matches / role_matches behaviour for the eleven v5 types'),
        adopt_v6=('V6_METRIC_FUNCTIONS (typed_user / fake_checksum_invalid / overmask_result) kept OUTSIDE the v5 dict', 'v6 value comparison by value_notation', 'NEG_TAG_PREFIX', 'the type_class axis'),
        owner_covered=('COV-CHECKSUM-INHERIT', 'MUTANT-LINE-REDEFINE', 'COV-INTEGRATION-KEEP-V5'),
        red_acceptance=('python3 -m bench.agentpii5.test_metrics', 'python3 -m bench.agentpii5.test_metrics_v6', 'old-corpus replay byte comparison (F7)'),
    ),
    OverlapRecord(
        id='C08',
        path='prototype/bench/agentpii5/observe.py',
        decision='HAND_MERGE_KEEP_V5_SEMANTICS',
        keep_v5=('VALUE_READINGS as the ONE reading of «same value» (_leaf_value_ok, _phone_equal, _name_equal, _place_equal, equivalent_out_leaf, call_ordinal_of)', 'the v5 hop statuses engine_kept / not_masked / leaf_foreign in place of the single `unmasked`'),
        adopt_v6=('the three new needle kinds (glyph, octets, ipv6)', 'glyph_fold', 'the IPv4/IPv6 span finders'),
        owner_covered=('COV-INTEGRATION-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_observe', 'python3 -m bench.agentpii5.test_observe_v6', 'the frozen old-corpus status-count replay (stage S3)'),
    ),
    OverlapRecord(
        id='C09',
        path='prototype/bench/agentpii5/perfect.py',
        decision='HAND_MERGE_KEEP_V5_SEMANTICS',
        keep_v5=("the v5 perfect-arm semantics: a checksum-type substitute keeps the source's validity (INVARIANTS.md#structured-ids, COV-CHECKSUM-INHERIT)", 'reverse_action_order'),
        adopt_v6=('mint_v6 (class-preserving alphanumeric shift with a digits-only fallback)',),
        owner_covered=('COV-CHECKSUM-INHERIT', 'MUTANT-LINE-REDEFINE'),
        red_acceptance=('python3 -m bench.agentpii5.test_perfect', 'python3 -m bench.agentpii5.test_perfect_v6', 'the redefined mutant separation test (valid->invalid, invalid->valid, wrong form, unsafe identity/collision)'),
    ),
    OverlapRecord(
        id='C10',
        path='prototype/bench/agentpii5/records.py',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('byte-identical old-corpus run rows (the v5 _v5_block keys)', 'the model-trace record added on this branch'),
        adopt_v6=('message_pieces written ONLY when non-empty',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_observe', 'old-corpus replay byte comparison (F7)'),
    ),
    OverlapRecord(
        id='C11',
        path='prototype/bench/agentpii5/report.py',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('beside_of / FrozenParts / axis_cells', 'every v5 printed line, including the eight status-split diagnostic rows'),
        adopt_v6=('has_v6_case', 'v6_axis_rows', 'v6_type_slice_lines', 'v6_new_row_lines', '_calibration_new_types'),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_report', 'python3 -m bench.agentpii5.test_report_v6', 'G2 meter gate on an unchanged old corpus'),
    ),
    OverlapRecord(
        id='C12',
        path='prototype/bench/agentpii5/revise.py',
        decision='ADOPT_V6',
        keep_v5=('_dedup_equivalent_leaves', 'the v5 `optional` reading (a hop on a generic role is optional)'),
        adopt_v6=('the two v6-changed lines',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_revise',),
    ),
    OverlapRecord(
        id='C13',
        path='prototype/bench/agentpii5/scenarios5/common.py',
        decision='KEEP_V5',
        keep_v5=('arg_hop setting optional = (not spec.required) or spec.role in GENERIC_PIECE_ROLES, so a REQUIRED hop on a settlement is never declared',),
        adopt_v6=(),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_scenarios5',),
    ),
    OverlapRecord(
        id='C14',
        path='prototype/bench/agentpii5/schema.py',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('_superseded_ids', 'R23 (a required OUT hop must not name a superseded item)'),
        adopt_v6=('_r02_suppressed — v6 negatives admitted as a known «negative family» line in R02',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_schema',),
    ),
    OverlapRecord(
        id='C15',
        path='prototype/bench/agentpii5/test_cli.py',
        decision='ADOPT_V6',
        keep_v5=('the v5 CLI test',),
        adopt_v6=('six added lines',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_cli',),
    ),
    OverlapRecord(
        id='C16',
        path='prototype/bench/agentpii5/test_contracts.py',
        decision='HAND_MERGE_KEEP_V5_SEMANTICS',
        keep_v5=('the v5 contract tests (leaf equivalence, value readings, R22/R23)',),
        adopt_v6=('the nine added / five removed lines',),
        owner_covered=('COV-KEEP-V5', 'INSTRUMENT-FIX-LEAF-READINGS'),
        red_acceptance=('python3 -m bench.agentpii5.test_contracts',),
    ),
    OverlapRecord(
        id='C17',
        path='prototype/bench/agentpii5/test_form.py',
        decision='HAND_MERGE_KEEP_V5_SEMANTICS',
        keep_v5=('the v5 form tests',),
        adopt_v6=('the seven added / five removed lines',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_form',),
    ),
    OverlapRecord(
        id='C18',
        path='prototype/bench/agentpii5/test_judge.py',
        decision='ADOPT_V6',
        keep_v5=('the v5 judge test',),
        adopt_v6=('one line',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_judge',),
    ),
    OverlapRecord(
        id='C19',
        path='prototype/bench/agentpii5/test_observe.py',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('test_second_declared_hop_on_a_claimed_leaf_is_absent (the v5 R22 watcher)',),
        adopt_v6=('_registry_values', 'the twenty-two added lines'),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_observe',),
    ),
    OverlapRecord(
        id='C20',
        path='prototype/bench/agentpii5/test_schema.py',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('test_r22', 'test_r23', '_address_case', '_correction_case'),
        adopt_v6=('one line',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_schema',),
    ),
    OverlapRecord(
        id='C21',
        path='prototype/bench/agentpii5/test_spec_form.py',
        decision='HAND_MERGE_KEEP_V5_SEMANTICS',
        keep_v5=('the v5 spec/form tests',),
        adopt_v6=('V5_TYPES', 'the fifteen added lines'),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 -m bench.agentpii5.test_spec_form',),
    ),
    OverlapRecord(
        id='C22',
        path='wiki/INDEX.md',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('the v5 rows for the hop-format audit and the v5 model-connector docs',),
        adopt_v6=('two added lines',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 wiki/check.py',),
    ),
    OverlapRecord(
        id='C23',
        path='wiki/MAP.md',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('the v5 module rows (connectors, live runner, payload canaries, vault helpers)',),
        adopt_v6=('the §4.1.1 v6 module block (193 added lines)',),
        owner_covered=('COV-KEEP-V5',),
        red_acceptance=('python3 wiki/check.py', 'python3 wiki/check.py --sync must be a no-op after the merge'),
    ),
    OverlapRecord(
        id='C24',
        path='wiki/STATE.md',
        decision='HAND_MERGE_ADDITIVE',
        keep_v5=('D-070 … D-076 as the v5 branch defines them (current-hop PHONE form, vault identity, classes А/Б/Г/Д)',),
        adopt_v6=('the v6 decision records for pilot types, pilot tools and the full corpus',),
        owner_covered=('D-ID-RENUMBER', 'COV-KEEP-V5'),
        red_acceptance=('every D-NNN cross-reference in wiki/ resolves to exactly one heading', "count of '^### D-' headings == count of distinct ids"),
    ),
)


# Which stage produced the resolution record. S2 resolved sixteen additive /
# verifiable rows, S3 the six semantic-core rows, and S7 the two the plan named
# but neither stage wrote (C17, C21).
RESOLVED_IN: dict[str, str] = {
    **{rid: "S2" for rid in ("C01", "C03", "C05", "C06", "C10", "C11", "C12",
                             "C13", "C14", "C15", "C18", "C19", "C20", "C22",
                             "C23", "C24")},
    **{rid: "S3" for rid in ("C02", "C04", "C07", "C08", "C09", "C16")},
    "C17": "S7",
    "C21": "S7",
}

# The frozen evidence, pinned OUTSIDE this branch where a witness exists:
#   * corpus.v5.json / corpus.json — sha256 recorded in
#     work/A1/INVENTORY.json and work/D1/A/GAPS.json before the merge;
#   * ladder.json — work/B0/INPUTS.json `ladder_file_sha256`;
#   * the v6 pair — recorded in the v6 report's `regress.pinned_v5` and
#     unchanged by every stage of this integration.
#
# THE v6 LADDER WAS RE-STAMPED ONCE, DELIBERATELY, AFTER THE INTEGRATION: it
# carried the v5 corpus digest (`build_ladder_v6` stamped `corpus_digest_v5`)
# while its only consumer, `bench.agentpii4.schema.tier`, recomputes v4's digest
# of the bases — so every v6 dry-run refused it. `v6/corpus.v5.json` did not move
# (76b5bf…, the same bytes), the tiers and the holdout did not move; only the
# digest field did, and the pin below is that one-line regeneration. The v5
# ladder, which was always stamped with the v4 digest, is untouched.
FROZEN_INPUTS: dict[str, tuple[str, str]] = {
    "prototype/bench/agentpii5/corpus.json": (
        "6bc58c5b8d6a3957b604bb67a7ea9a78992882f2c028c837186f57ad11e6e4ec",
        "work/A1/INVENTORY.json"),
    "prototype/bench/agentpii5/corpus.v5.json": (
        "3ba227908d40911bd6578418b2da9d3b7925a1ffefe88ebbf5cead5ce5115118",
        "work/A1/INVENTORY.json · work/D1/A/GAPS.json"),
    "prototype/bench/agentpii5/ladder.json": (
        "3e088f66334309feedd32f8d860a34d215e3ca94561b2a8d55425c01317708d9",
        "work/B0/INPUTS.json ladder_file_sha256"),
    "prototype/bench/agentpii5/v6/corpus.v5.json": (
        "76b5bffe5a00bf7858212d0280b8d69bf8dfeeaf3c63372fbfd616745da23ad7",
        "review/v6-integration.json regress.pinned_v5"),
    "prototype/bench/agentpii5/v6/ladder.json": (
        "b7f1d05a9f63d7a327ffbdbc1a35d0bb51b160e4309aacddc810d935e7541600",
        "review/v6-integration.json regress.pinned_v5"),
}
# The v6 corpus pair is a v6 artifact, not the frozen v5 evidence: freshness
# there is not a claim this record makes.
FROZEN_V5 = tuple(k for k in FROZEN_INPUTS if "/v6/" not in k)


def repo_root() -> Path:
    """The repository root: `prototype/bench/agentpii5/` -> three levels up."""
    return HERE.parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record_ids() -> tuple[str, ...]:
    return tuple(record.id for record in RECORDS)


def by_path(path: str) -> OverlapRecord:
    for record in RECORDS:
        if record.path == path:
            return record
    raise KeyError(path)


def command_targets(record: OverlapRecord) -> tuple[str, ...]:
    """Every module/script a `python3 …` line in `red_acceptance` names."""
    out: list[str] = []
    for entry in record.red_acceptance:
        match = re.match(r"python3 -m (bench\.agentpii5\.[\w.]+)", entry)
        if match:
            out.append(match.group(1))
        elif entry.startswith("python3 wiki/check.py"):
            out.append("wiki/check.py")
    return tuple(out)


def target_exists(target: str) -> bool:
    if target.startswith("bench."):
        return (repo_root() / "prototype" / (target.replace(".", "/") + ".py")).exists()
    return (repo_root() / target).exists()


def _problems_for(records: tuple[OverlapRecord, ...],
                  resolved_in: dict[str, str]) -> list[str]:
    """Every clause S7's RED acceptance puts on a record set, over an INJECTED
    set so the negative controls below can drive a broken one through it."""
    problems: list[str] = []
    if len(records) != 24:
        problems.append(f"{len(records)} records, the plan declares 24 overlap paths")
    if len({record.id for record in records}) != len(records):
        problems.append("duplicate record ids")
    if len({record.path for record in records}) != len(records):
        problems.append("two records for one path")
    root = repo_root()
    for record in records:
        where = f"{record.id} {record.path}"
        if record.decision not in DECISIONS:
            problems.append(f"{where}: decision {record.decision!r} is not declared")
        if not record.keep_v5:
            problems.append(f"{where}: nothing recorded as kept")
        if not record.adopt_v6 and record.decision != "KEEP_V5":
            # A whole-file KEEP_V5 adopts nothing by definition; every other
            # mechanism must say what came across, or the record is a label.
            problems.append(f"{where}: nothing recorded as adopted")
        if not record.owner_covered:
            problems.append(f"{where}: no owner decision recorded")
        if not record.red_acceptance:
            problems.append(f"{where}: no re-check recorded")
        if record.id not in resolved_in:
            problems.append(f"{where}: no resolving stage recorded")
        if not (root / record.path).is_file():
            problems.append(f"{where}: the path does not exist in the tree")
        for target in command_targets(record):
            if target_exists(target):
                continue
            if target in KNOWN_ABSENT_TARGETS:
                continue
            problems.append(f"{where}: re-check names {target!r}, which does not exist")
    return problems


def record_problems() -> list[str]:
    """The live record set, plus the negative controls that prove each clause
    above can actually fail."""
    problems = _problems_for(RECORDS, RESOLVED_IN)
    # The two rows the plan declared and no earlier stage wrote.
    for rid in ("C17", "C21"):
        if RESOLVED_IN.get(rid) != "S7":
            problems.append(f"{rid}: not recorded as resolved by S7")
    controls: tuple[tuple[str, tuple[OverlapRecord, ...], str], ...] = (
        ("a duplicated path", RECORDS + (RECORDS[0],), "two records for one path"),
        ("an unknown decision",
         (dataclasses.replace(RECORDS[0], decision="OURS"),) + RECORDS[1:],
         "is not declared"),
        ("a missing path",
         (dataclasses.replace(RECORDS[0],
                              path="prototype/bench/agentpii5/no_such.py"),)
         + RECORDS[1:],
         "does not exist in the tree"),
    )
    for label, mutated, needle in controls:
        if not any(needle in problem for problem in _problems_for(mutated, RESOLVED_IN)):
            problems.append(f"negative control: {label} was NOT caught")
    return problems


def frozen_problems() -> list[str]:
    """«No old corpus was regenerated over the frozen evidence.»"""
    problems: list[str] = []
    root = repo_root()
    for rel, (expected, source) in FROZEN_INPUTS.items():
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel}: missing (pinned by {source})")
            continue
        got = _sha256(path)
        if got != expected:
            problems.append(f"{rel}: {got} != {expected} pinned by {source}")
    return problems


def record_json(record: OverlapRecord) -> dict[str, object]:
    root = repo_root()
    path = root / record.path
    return {
        "id": record.id,
        "path": record.path,
        "decision": record.decision,
        "resolved_in": RESOLVED_IN.get(record.id, ""),
        "keep_v5": list(record.keep_v5),
        "adopt_v6": list(record.adopt_v6),
        "owner_covered": list(record.owner_covered),
        "red_acceptance": list(record.red_acceptance),
        "red_acceptance_targets": [
            {"target": target, "exists": target_exists(target),
             "reason_if_absent": KNOWN_ABSENT_TARGETS.get(target, "")}
            for target in command_targets(record)
        ],
        "sha256": _sha256(path) if path.is_file() else "",
    }


def report() -> dict[str, object]:
    return {
        "generated_by": GENERATED_BY,
        "overlap_paths": len(RECORDS),
        "decision_vocabulary": list(DECISIONS),
        "decisions": {name: sum(1 for record in RECORDS if record.decision == name)
                      for name in DECISIONS},
        "resolved_in": {stage: sum(1 for record in RECORDS
                                   if RESOLVED_IN.get(record.id) == stage)
                        for stage in ("S2", "S3", "S7")},
        "frozen_inputs": {rel: {"sha256": pin[0], "pinned_by": pin[1]}
                          for rel, pin in FROZEN_INPUTS.items()},
        "records": [record_json(record) for record in RECORDS],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true",
                        help=f"write {OUT_PATH.name} as well as printing")
    args = parser.parse_args(sys.argv[1:])
    problems = record_problems() + frozen_problems()
    doc = report()
    print(f"overlap_review: {doc['overlap_paths']} records · "
          f"decisions {doc['decisions']} · resolved_in {doc['resolved_in']} · "
          f"problems={len(problems)}")
    for problem in problems:
        print(f"  PROBLEM {problem}")
    if args.write:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
        print(f"wrote {OUT_PATH}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
