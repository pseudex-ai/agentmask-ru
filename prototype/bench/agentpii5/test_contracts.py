"""The contracts are pinned to the spec, mechanically.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_contracts

Three claims, each one the six component agents build on and none of which a
docstring can hold on its own:

  1. every feature name of spec §8.4 is registered for its type, and nothing
     else is — the spec table is COPIED here, so a rename in `contracts.py`
     that drifts from the spec goes red instead of silently re-labelling the
     comparator's output;
  2. every metric name of spec §4 and §8.3 is declared with hits/total
     wording, again against a literal copy;
  3. importing `contracts` loads no `pseudex` module — the instrument must be
     able to fail the engine, and an import is the first way it stops being
     able to.

No pytest here, as everywhere in `prototype/`: `main()` prints PASS/FAIL and
returns the exit code.
"""
import sys


def _spec_features() -> dict[str, tuple[str, ...]]:
    """docs/tz-agentpii5.md §8.4, copied by hand. Do not import it from
    contracts — the point is that the two are written twice."""
    return {
        "NAME": ("case_class", "gram_case", "order", "parts", "initials", "script", "hyphen_particle"),
        "PHONE": ("prefix", "grouping", "separators", "parens"),
        "LOC": ("case_class", "generic", "generic_position", "house_marker", "flat_marker", "commas",
                "city_present", "city_position", "by_fields", "building_entrance_markers"),
        "DOB": ("notation", "separator", "padding", "year_len", "month_form"),
        "DATE": ("notation", "separator", "padding", "year_len", "month_form"),
        "EMAIL": ("case_class",),
        "CARD": ("grouping", "separator"),
        "SNILS": ("separators",),
        "INN": ("length", "separators"),
        "PASSPORT": ("series_number_split",),
        "PLATE": ("case_class", "spaces", "region_sep"),
    }


def _spec_metrics() -> tuple[str, ...]:
    """§4.1 levels, §4.2 public, §4.3/§8.3 new — copied by hand."""
    return (
        "action", "tools", "keys", "state", "values", "verbatim",
        "leak", "coverage", "typed", "round_trip", "round_trip_repaired", "end_to_end",
        "overmask", "consistency", "stability", "rewrite_ratio", "shared_block",
        "form_hIN", "form_hOUT", "toolresult_masked", "answer_real", "chain_value", "chain_form",
        "multi_all_out", "multi_consistency", "retry_form", "memory_consistency", "memory_stability",
        "rag_masked", "rag_identity_kept", "doc_masked", "doc_extracted", "residual",
    )


def main() -> int:
    before = {name for name in sys.modules if name.startswith("pseudex")}
    from bench.agentpii5 import contracts as c
    failures: list[str] = []

    loaded = {name for name in sys.modules if name.startswith(c.FORBIDDEN_IMPORT_PREFIX)} - before
    if loaded:
        failures.append(f"importing contracts loaded {sorted(loaded)}")

    # 1. features, per type, exactly
    spec = _spec_features()
    if set(c.FORM_FEATURES) != set(spec):
        failures.append(f"form types {sorted(c.FORM_FEATURES)} != spec {sorted(spec)}")
    for kind, features in spec.items():
        if tuple(c.FORM_FEATURES.get(kind, ())) != features:
            failures.append(f"{kind}: contracts {c.FORM_FEATURES.get(kind)} != spec {features}")
    pairs = c.feature_pairs()
    if set(c.FEATURE_LABELS) != set(pairs):
        failures.append(f"FEATURE_LABELS keys differ from feature pairs: "
                        f"{sorted(set(c.FEATURE_LABELS) ^ set(pairs))}")
    for pair, labels in c.FEATURE_LABELS.items():
        if len(labels) < 2:
            failures.append(f"{pair}: a feature with one label cannot differ")
        if len(set(labels)) != len(labels):
            failures.append(f"{pair}: duplicate labels")
    for kind in spec:
        if kind != "DATE" and kind not in c.TYPES:
            failures.append(f"form type {kind} is not a v4 TYPE")

    # 2. metrics, by name, exactly once
    names = c.METRIC_NAMES
    if len(set(names)) != len(names):
        failures.append("duplicate metric names")
    missing = [name for name in _spec_metrics() if name not in names]
    extra = [name for name in names if name not in _spec_metrics()]
    if missing:
        failures.append(f"spec metrics not declared: {missing}")
    if extra:
        failures.append(f"metrics declared beyond the spec: {extra}")
    for spec_ in c.METRICS:
        if spec_.scope not in c.SCOPES or spec_.family not in c.METRIC_FAMILIES:
            failures.append(f"{spec_.name}: scope/family outside the closed sets")
        if not spec_.hits or not spec_.total:
            failures.append(f"{spec_.name}: hits/total wording missing")
    if "round_trip_repaired" not in c.DIAGNOSTIC_METRIC_NAMES:
        failures.append("round_trip_repaired must be diagnostic (spec §8.3)")
    if set(c.V4_LEVEL_NAMES) != {"action", "tools", "keys", "state", "values", "verbatim"}:
        failures.append(f"v4 levels drifted: {c.V4_LEVEL_NAMES}")

    # 3. the closed vocabularies agree with each other
    if set(c.BEHAVIOUR_SHARES) != set(c.BEHAVIOURS):
        failures.append("BEHAVIOUR_SHARES keys != BEHAVIOURS")
    if set(c.BEHAVIOUR_FLOORS) != set(c.BEHAVIOURS):
        failures.append("BEHAVIOUR_FLOORS keys != BEHAVIOURS")
    if c.V4_CORPUS_SIZE + sum(c.BEHAVIOUR_FLOORS.values()) - c.BEHAVIOUR_FLOORS["single"] \
            - c.BEHAVIOUR_FLOORS["sequential_chain"] - c.BEHAVIOUR_FLOORS["fanout_pick"] > c.CORPUS_SIZE_BAND_V5[1]:
        failures.append("the floors the revised corpus does not already meet cannot fit the size band")
    if abs(sum(c.BEHAVIOUR_SHARES.values()) - 1.0) > 1e-9:
        failures.append(f"behaviour shares sum to {sum(c.BEHAVIOUR_SHARES.values())}")
    if set(c.GENERATOR_A_BEHAVIOURS) | set(c.GENERATOR_B_BEHAVIOURS) | {"single"} != set(c.BEHAVIOURS):
        failures.append("generator split does not cover BEHAVIOURS")
    if set(c.GENERATOR_A_BEHAVIOURS) & set(c.GENERATOR_B_BEHAVIOURS):
        failures.append("a behaviour is owned by both generators")
    # Spec §8.2 writes 45/25/15/10 — 95%; the five points are deliberately
    # unassigned and absorbed by SHARE_TOLERANCE, so the check is a band.
    if not 0.95 - 1e-9 <= sum(c.REGISTER_SHARES.values()) <= 1.0 + 1e-9:
        failures.append("register shares outside [0.95, 1.0]")
    if set(c.V4_KIND_TO_BEHAVIOUR) != set(c.V4_SCENARIO_KINDS):
        failures.append("V4_KIND_TO_BEHAVIOUR does not cover v4's kinds exactly")
    if any(value not in c.BEHAVIOURS for value in c.V4_KIND_TO_BEHAVIOUR.values()):
        failures.append("V4_KIND_TO_BEHAVIOUR maps to an unknown behaviour")
    for kind, owner in c.MINIMAL_LOOP:
        if kind not in c.HOP_KINDS or owner not in c.HOP_OWNERS:
            failures.append(f"MINIMAL_LOOP names {kind}/{owner}")
        if (kind == "IN") != (owner in c.IN_OWNERS):
            failures.append(f"MINIMAL_LOOP: {owner} is not an owner of {kind}")
    if set(c.IN_OWNERS) & set(c.OUT_OWNERS):
        failures.append("an owner is both IN and OUT")

    # 4. tools: 31 kept + 12 new, every one in exactly one vertical
    if len(c.V4_TOOL_NAMES) != 31:
        failures.append(f"v4 registry has {len(c.V4_TOOL_NAMES)} tools, expected 31")
    if len(c.NEW_TOOL_NAMES) != 12 or len(set(c.NEW_TOOL_NAMES)) != 12:
        failures.append("12 distinct new tools expected")
    if set(c.NEW_TOOL_NAMES) & set(c.V4_TOOL_NAMES):
        failures.append("a new tool name collides with v4")
    if set(c.TOOL_VERTICAL) != set(c.V4_TOOL_NAMES) | set(c.NEW_TOOL_NAMES):
        failures.append(f"TOOL_VERTICAL keys mismatch: {sorted(set(c.TOOL_VERTICAL) ^ (set(c.V4_TOOL_NAMES) | set(c.NEW_TOOL_NAMES)))}")
    if any(vertical not in c.VERTICALS for vertical in c.TOOL_VERTICAL.values()):
        failures.append("TOOL_VERTICAL names an unknown vertical")
    if set(c.TOOL_VERTICAL.values()) != set(c.VERTICALS):
        failures.append(f"verticals without a tool: {sorted(set(c.VERTICALS) - set(c.TOOL_VERTICAL.values()))}")
    if len(c.VERTICALS) != 11:
        failures.append("spec §8.1 names 11 verticals")
    if set(c.NEW_TOOL_RETURN_FORMS) != set(c.NEW_TOOL_NAMES) or set(c.NEW_TOOL_RESULT_TYPES) != set(c.NEW_TOOL_NAMES):
        failures.append("every new tool needs declared return forms and result types")
    for name, forms in c.NEW_TOOL_RETURN_FORMS.items():
        if any(form not in c.RETURN_FORMS for form in forms):
            failures.append(f"{name}: unknown return form")
    for name, kinds in c.NEW_TOOL_RESULT_TYPES.items():
        if any(kind not in c.FORM_FEATURES for kind in kinds):
            failures.append(f"{name}: result type without form features")
    if len(c.RETURN_FORMS) != 8:
        failures.append("spec §8.1 names 8 return forms")

    # 5. the leaf-owner table
    if c.hop_owner_of_leaf("send_template", "variables.name") != "template":
        failures.append("send_template.variables.name should be a template hop")
    if c.hop_owner_of_leaf("escalate_to_human", "summary") != "summary":
        failures.append("escalate_to_human.summary should be a summary hop")
    if c.hop_owner_of_leaf("delivery_create_order", "recipient.phones[0].number") != "tool_arg":
        failures.append("an ordinary leaf should be a tool_arg hop")
    if c.hop_owner_of_leaf("notify_sms", "number") != "tool_arg":
        failures.append("notify_sms.number is an argument, not the template text")

    # 6. Line is the public one
    line = c.Line("x", 3, 3)
    if line.rate != 1.0 or line.certified is None or not (0.0 < line.certified < 1.0):
        failures.append("Line.certified must be the zero-failure floor when x == n")
    if c.Line("y", 0, 0).rate != 0.0 or c.Line("y", 0, 0).interval != (0.0, 1.0):
        failures.append("an empty Line is 0 with the trivial interval")
    if c.Line("z", 1, 4).certified is not None:
        failures.append("a line with a miss certifies nothing")

    # 7. calibration thresholds are the spec's numbers
    cal = c.CALIBRATION
    if (cal.sample_size, cal.per_stratum_min, cal.raw_agreement_min, cal.kappa_min, cal.repeats,
            cal.repeat_sample, cal.max_repeat_disagreement) != (300, 20, 0.85, 0.70, 3, 50, 0.10):
        failures.append("CALIBRATION drifted from spec §8.5")
    if set(c.JUDGE_LABELS) != {"верно", "частично", "неверно", "выдумал"}:
        failures.append("judge labels drifted from spec §8.5")

    # 8. every rule string is unique and numbered
    for rules, prefix in ((c.V5_CASE_RULES, "R"), (c.V5_CORPUS_RULES, "K"), (c.VERTICAL_RULES, "V")):
        ids = [rule.split()[0] for rule in rules]
        if len(set(ids)) != len(ids) or any(not one.startswith(prefix) for one in ids):
            failures.append(f"rules {prefix}: ids not unique or not prefixed")

    print("contracts: PASS" if not failures else "contracts: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
