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
import ast
import pathlib
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


def _v3_judge_constant(name: str) -> float:
    """A number read off v3's judge SOURCE, never by importing it.

    Spec §8.5 says the judge's budget is «как в v4», and v4's harness takes
    that number from `bench.agentpii3.live.judge` — which reaches
    `bench.agentpii3.score`, which imports the engine at module level, while
    `contracts.PSEUDEX_ALLOWED_MODULES` names only `harness`. So the file is
    parsed instead of imported: «as in v4» becomes a check rather than a
    sentence, and a silent change of the per-query ceiling — the number that
    decides whether an expensive run is cut off — goes red here.
    """
    source = (pathlib.Path(__file__).resolve().parents[1] / "agentpii3" / "live" / "judge.py")
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        target = (node.target if isinstance(node, ast.AnnAssign)
                  else node.targets[0] if isinstance(node, ast.Assign) and node.targets else None)
        if isinstance(target, ast.Name) and target.id == name and node.value is not None:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is no longer declared in {source} — «как в v4» names nothing")


def _spec_metrics() -> tuple[str, ...]:
    """§4.1 levels, §4.2 public, §4.3/§8.3 new — copied by hand.

    SIX NAMES DIFFER FROM THE SPEC'S TABLE, AND EACH DIFFERENCE IS A DECISION.
    `rewrite_ratio_v5` / `shared_block_answer` carry the version because they
    are NOT the public quantities of those names (a message-level change ratio
    and a per-item attribution failure); printing two different numbers under
    one name is how a reader comes to believe a v5 line was validated by the
    public harness. `out_absent` is the count `form_hOUT`'s denominator leaves
    out, and `stream_fidelity` is the one reader of `stream_mismatch`, which
    the harness wrote on every streaming case and nothing consumed.

    ROUND 5 MOVED TWO MORE. `answer_optional_only` is `out_absent`'s twin — the
    answers `answer_real` stopped judging when J1.1 took «all() over an empty
    list» out of its denominator, printed so the shrink is visible. And
    `memory_stability` is GONE: its population is empty by construction on any
    corpus whose memory recall is anaphoric, so the line could only ever print
    «н/п» (J1.2, the removal comment in `contracts.METRICS`).
    """
    return (
        "action", "tools", "keys", "state", "values", "verbatim",
        "leak", "coverage", "typed", "round_trip", "round_trip_repaired", "end_to_end",
        "overmask", "consistency", "stability", "rewrite_ratio_v5", "shared_block_answer",
        "form_hIN", "form_hOUT", "out_absent",
        "toolresult_masked", "answer_real", "answer_optional_only", "chain_value", "chain_form",
        "multi_all_out", "multi_consistency", "retry_form", "memory_consistency",
        "rag_masked", "rag_identity_kept", "doc_masked", "doc_extracted", "residual",
        "stream_fidelity",
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
    # R-09/R-16: the five points §8.2 left unassigned went to `chat` (0.30) and
    # the mix sums to 1.00 exactly. A band would accept the superseded reading
    # as readily as the ruled one, which is no check at all.
    if abs(sum(c.REGISTER_SHARES.values()) - 1.0) > 1e-9:
        failures.append(f"R-16: register shares sum to {sum(c.REGISTER_SHARES.values())}, not 1.00")
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

    # 4. tools: 31 kept + 24 new, every one in exactly one vertical. Thirteen of
    # the 24 are §8.1's — `patient_find` among them, the clinic's reading tool,
    # ordered by §2 («book, slots, patient_find») and missing from §8.1's table,
    # whose absence is why the vertical returned no personal data at all — and
    # ELEVEN are the office suite (§8.1bis).
    if len(c.V4_TOOL_NAMES) != 31:
        failures.append(f"v4 registry has {len(c.V4_TOOL_NAMES)} tools, expected 31")
    if len(c.NEW_TOOL_NAMES) != 24 or len(set(c.NEW_TOOL_NAMES)) != 24:
        failures.append(f"24 distinct new tools expected, got {len(set(c.NEW_TOOL_NAMES))}")
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

    # 4bis. the SUITE axis. A suite is a slice ACROSS verticals — the customer's
    # own shapes — and the checks below are what stop it turning into a twelfth
    # vertical or into a second, disagreeing list of the same tools.
    if not c.SUITES or len(set(c.SUITES)) != len(c.SUITES):
        failures.append("SUITES must be a non-empty tuple of distinct names")
    if c.NO_SUITE in c.SUITES:
        failures.append("NO_SUITE is the absence of a suite and may not be one")
    unknown = sorted({one for one in c.TOOL_SUITE.values()} - set(c.SUITES))
    if unknown:
        failures.append(f"TOOL_SUITE names suites that are not in SUITES: {unknown}")
    outside = sorted(set(c.TOOL_SUITE) - (set(c.V4_TOOL_NAMES) | set(c.NEW_TOOL_NAMES)))
    if outside:
        failures.append(f"TOOL_SUITE names tools no registry holds: {outside}")
    for suite in c.SUITES:
        members = [name for name, one in c.TOOL_SUITE.items() if one == suite]
        if not members:
            failures.append(f"suite {suite!r} holds no tool")
            continue
        # THE WHOLE POINT OF THE AXIS: if a suite sat inside one vertical,
        # `--slice vertical=…` would already answer it and this would be
        # decoration. The office suite spans five.
        if len({c.TOOL_VERTICAL[name] for name in members}) < 2:
            failures.append(f"suite {suite!r} fits inside one vertical — "
                            f"the vertical axis already isolates it")

    # 5. the leaf-owner table
    if c.hop_owner_of_leaf("send_template", "variables.name") != "template":
        failures.append("send_template.variables.name should be a template hop")
    if c.hop_owner_of_leaf("escalate_to_human", "summary") != "summary":
        failures.append("escalate_to_human.summary should be a summary hop")
    if c.hop_owner_of_leaf("delivery_create_order", "recipient.phones[0].number") != "tool_arg":
        failures.append("an ordinary leaf should be a tool_arg hop")
    if c.hop_owner_of_leaf("notify_sms", "number") != "tool_arg":
        failures.append("notify_sms.number is an argument, not the template text")
    # The office suite's own leaves: what a PERSON reads is a template hop, what
    # the agent RETELLS for a colleague is a summary hop, and the identity leaf
    # beside them stays an ordinary argument.
    if c.hop_owner_of_leaf("mail_send", "body") != "template":
        failures.append("mail_send.body is read by a person — a template hop")
    if c.hop_owner_of_leaf("reminder_set", "text") != "template":
        failures.append("reminder_set.text reaches a person — a template hop")
    if c.hop_owner_of_leaf("tracker_issue_create", "description") != "summary":
        failures.append("tracker_issue_create.description is a retelling — a summary hop")
    if c.hop_owner_of_leaf("crm_upsert_card", "deal.note") != "summary":
        failures.append("crm_upsert_card.deal.note is a retelling — a summary hop")
    if c.hop_owner_of_leaf("mail_send", "to[0]") != "tool_arg":
        failures.append("mail_send.to[] is an address, not the letter a person reads")
    if c.hop_owner_of_leaf("sheet_append_row", "values[0][2]") != "tool_arg":
        failures.append("a spreadsheet cell is an ordinary argument leaf")

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
    # §8.5 names no number for the budget and says «как в v4», so v4's own
    # source is what the claim is checked against.
    for name, value in (("QUERY_CAP_USD", c.QUERY_CAP_USD), ("RETRIES", c.RETRIES)):
        theirs = _v3_judge_constant(name)
        if value != theirs:
            failures.append(f"§8.5 «как в v4»: {name} is {value}, v4 spends {theirs}")

    # 8. the Phase-3 rulings that changed a SHAPE, pinned so a revert is red
    doc_fields = tuple(c.DocumentSpec.__dataclass_fields__)
    if "record_ids" not in doc_fields:
        failures.append("R-30: DocumentSpec must carry record_ids (the seed rows it renders)")
    if "turn_replies" not in c.ArmRunV5.__dataclass_fields__:
        failures.append("R-40: ArmRunV5 must carry turn_replies (the judge reads them)")
    # R-35: v4 computes these three inside its own `render` and exposes them
    # through no function, so a v5 field for them could only be a re-derivation.
    if hasattr(c, "V4_EXTRA_LINES"):
        failures.append("R-35: V4_EXTRA_LINES is dropped; v4's block prints those three")
    if "v4_extra" in c.SideBySide.__dataclass_fields__:
        failures.append("R-35: SideBySide.v4_extra is dropped")
    # R-31: a handover acts through a summary leaf, so R15's text must name the
    # three acting owners rather than tool_arg alone.
    r15 = next(rule for rule in c.V5_CASE_RULES if rule.startswith("R15"))
    for owner in ("tool_arg", "template", "summary"):
        if owner not in r15:
            failures.append(f"R-31: R15 does not name the acting owner {owner!r}")
    r18 = next(rule for rule in c.V5_CASE_RULES if rule.startswith("R18"))
    if "record_ids" not in r18:
        failures.append("R-30: R18 does not read record_ids")

    # 8bis. the round-2 rulings that changed a SHAPE (R-51, R-54, F1.22)
    if c.CORPUS_SIZE_BAND_V5 != (1200, 1800):
        failures.append(f"R-51: the corpus band is {c.CORPUS_SIZE_BAND_V5}, ruled (1200, 1800)")
    # The two fields are read by DIFFERENT readers (`stream_fidelity` and
    # `residual`), so the TYPE is pinned beside the name: a `turn_residual`
    # written as text would count as a miss on «0» just as loudly as on «3».
    arm_fields = c.ArmRunV5.__dataclass_fields__
    for field_name, want in (("reply_whole", str), ("turn_residual", int)):
        if field_name not in arm_fields:
            failures.append(f"R-54: ArmRunV5 must carry {field_name}")
        elif arm_fields[field_name].type is not want:
            failures.append(f"R-54: ArmRunV5.{field_name} is {arm_fields[field_name].type}, "
                            f"and {want.__name__} is what its reader counts")
    if "<run>.meta.json" not in c.RUN_FILES:
        failures.append("F1.22: <run>.meta.json is a run file, not a name report.py invents")
    side_fields = c.SideBySide.__dataclass_fields__
    for field_name in ("judge_pregate", "excluded_observations"):
        if field_name not in side_fields:
            failures.append(f"F1.22: SideBySide must carry {field_name} — the report reads its "
                            f"own holes off the object, not off the half it was built from")
    if not c.EXCLUDED_NO_HOPS:
        failures.append("F1.22: the hole marker of excluded_observations must be a word")

    # 9. every rule string is unique and numbered
    for rules, prefix in ((c.V5_CASE_RULES, "R"), (c.V5_CORPUS_RULES, "K"), (c.VERTICAL_RULES, "V")):
        ids = [rule.split()[0] for rule in rules]
        if len(set(ids)) != len(ids) or any(not one.startswith(prefix) for one in ids):
            failures.append(f"rules {prefix}: ids not unique or not prefixed")

    print("contracts: PASS" if not failures else "contracts: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
