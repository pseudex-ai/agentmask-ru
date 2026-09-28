"""`<run>.report.json` and its public substring, on a REAL run directory.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_reportjson

ТЗ `docs/tz-bench-harness.md` §5.1 and §5.3, items 15 and 17. The run is the one
`test_report.build_run` writes with the real writers, so the document is built by
the code path a GO run uses — `report.read_parts`, `report.assemble`, the real
metric registry.

Each check goes red on a revert:

  * every printed line is in the JSON with hits, total, rate and the exact
    interval (item 15) — drop a field from `line_json` and `document_carries_
    every_printed_line` names it;
  * the document says WHY it is incomplete — make `incomplete_reasons` return ()
    and `incomplete_is_explained` goes red beside a `SideBySide` that says it is;
  * the public file is an ALLOWLIST (item 17) — rewrite `public` as «copy and
    pop» and `public_is_an_allowlist` finds the planted field;
  * no value of the corpus reaches the public file — the fixture's real name and
    phone are searched for in its bytes;
  * the cost in the JSON is the cost the text prints — they share the three
    atoms, and `cost_matches_the_run` pins the sum against the run's own meta.
"""
import json
import re
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii5 import contracts, payload_canaries as pc, records
from bench.agentpii5.contracts import Line, Metric
from bench.agentpii5.fixtures import FAKE_NAME, REAL_NAME, REAL_PHONE
from bench.agentpii5.metrics import METRIC_FUNCTIONS
from bench.agentpii5.report import (
    MODEL_NOT_RECORDED, assemble, meta_of, read_parts, report_lines, run_id_of)
from bench.agentpii5.reportjson import (
    PUBLIC_JSON_NAME,
    REPORT_JSON_NAME,
    PUBLIC_LINE_FIELDS,
    PUBLIC_LINES,
    PUBLIC_TOP_LEVEL,
    REPORT_JSON_VERSION,
    ReportError,
    build,
    public,
    read,
    summary_lines,
    write,
)
from bench.agentpii5.test_report import CEILING_USD, RUN_ID, build_run

BROKEN = "toolresult_masked"


def _built(root: Path) -> tuple[Path, Path]:
    return build_run(root, RUN_ID, True), build_run(root, "baseline01", False)


def _write_capture_fixture(run_dir: Path, manifest: pc.CanaryManifest,
                           delivered: tuple[pc.CapturedPayload, ...]) -> None:
    """Persist explicit test bytes for every I arm the fixture's triple writer made."""
    (run_dir / pc.MANIFEST_ARTIFACT).write_text(
        json.dumps(pc.manifest_to_json(manifest), ensure_ascii=False), encoding="utf-8")
    run_id = run_id_of(run_dir)
    triples = records.read_rows(records.run_file(run_dir, run_id, "<run>.triples.jsonl"))
    for triple in triples:
        arms = triple.get("arms")
        if isinstance(arms, dict) and "I" in arms:
            pc.append_capture(run_dir, run_id, pc.RunCapture(
                case_id=str(triple["case_id"]), repeat=int(triple["repeat"]), arm="I",
                manifest=manifest, delivered=delivered))


def _fixture_payloads() -> tuple[pc.CapturedPayload, ...]:
    """Known bytes at each boundary; no detector or saved mention constructs them."""
    return tuple(pc.CapturedPayload(name, f"VISIBLE payload at {name}")
                 for name in pc.BOUNDARIES)


def _plant_measured_manifest(run_dir: Path) -> None:
    """A measurable capture with one hidden canary and no leak."""
    manifest = pc.CanaryManifest(canaries=(pc.CanarySpec(
        "hidden", "PHONE", "model_input",
        (pc.PlantedSurface("CANARY-NEVER-WRITTEN-ANYWHERE", pc.SURFACE_FULL),),
        "", "message"),), source="s02-reportjson-test")
    _write_capture_fixture(run_dir, manifest, _fixture_payloads())


# A model id no constant of the package carries: the fixture's own `meta.json`
# names `contracts.AGENT_MODEL`, so a run written with it cannot tell «читает
# запись прогона» apart from «печатает константу».
FIXTURE_MODEL = "claude-haiku-fixture-4-5-20260101"


def _with_model(run_dir: Path, model: str | None) -> None:
    """Rewrite the run's own `meta.json` with (or without) an agent model.

    Over the file the fixture wrote, so everything else in it stays exactly
    what a run writes — the report must read a REAL record, not one this test
    invented from scratch."""
    run_id = run_id_of(run_dir)
    path = records.run_file(run_dir, run_id, "<run>.meta.json")
    meta = dict(meta_of(run_dir, run_id))
    if model is None:
        meta.pop("model", None)
    else:
        meta["model"] = model
    path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def test_both_files_name_the_model_the_run_recorded() -> list[str]:
    """ONE run, ONE answer to «какая модель отвечала».

    `assemble` stamped `contracts.AGENT_MODEL` — the model the harness would
    choose TODAY — into the markdown header while this document read the run's
    own `meta.json`. A run made by any other model was then described by two
    files that disagreed, and the one a reader believes is whichever they
    opened first. Both now read the RUN RECORD, and a run that recorded no
    model says so instead of being credited with today's constant.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        _with_model(v5_dir, FIXTURE_MODEL)
        parts = read_parts(v5_dir, v4_dir)
        side = assemble(parts, METRIC_FUNCTIONS)
        text = "\n".join(report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS))
        document = build(parts, side)
        agent = document["models"]["agent"]  # type: ignore[index]
        if agent != FIXTURE_MODEL:
            problems.append(f"the JSON does not name the model the run recorded: {agent!r}")
        if FIXTURE_MODEL not in text:
            problems.append("the markdown header does not name the model the run recorded")
        if contracts.AGENT_MODEL in text:
            problems.append("the markdown names the constant instead of the run's own model")
        if agent not in text:
            problems.append(f"report.txt and report.json disagree about the model: "
                            f"{agent!r} is not in the markdown")
        # The other half: a run that recorded NO model is not credited with
        # one. «Не записано» and «claude-haiku-4-5» are not the same fact.
        _with_model(v5_dir, None)
        blind_parts = read_parts(v5_dir, v4_dir)
        blind = build(blind_parts, assemble(blind_parts, METRIC_FUNCTIONS))
        blind_text = "\n".join(report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS))
        if blind["models"]["agent"] is not None:  # type: ignore[index]
            problems.append(f"a run with no recorded model got one: "
                            f"{blind['models']['agent']!r}")  # type: ignore[index]
        if MODEL_NOT_RECORDED not in blind_text:
            problems.append("the markdown does not say the model was not recorded")
        if contracts.AGENT_MODEL in blind_text:
            problems.append("a run with no recorded model is credited with today's constant")
    return problems


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_document_carries_every_printed_line() -> list[str]:
    """Item 15: «каждая строка метрики (hits, total, rate, интервал)». A JSON
    that held a rate alone could not be re-aggregated, and one that held fewer
    lines than the text would make the trend disagree with the report beside
    it."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        parts = read_parts(v5_dir, v4_dir)
        side = assemble(parts, METRIC_FUNCTIONS)
        document = build(parts, side)
        if document["schema"] != REPORT_JSON_VERSION:
            problems.append("the document is not versioned")
        lines = document["lines"]
        if not isinstance(lines, dict):
            problems.append("lines is not an object")
            return problems
        if set(lines) != set(side.v5_lines):
            problems.append(f"the JSON and the report print different lines: "
                            f"{sorted(set(lines) ^ set(side.v5_lines))}")
        for name, row in lines.items():
            line: Line = side.v5_lines[name]
            low, high = line.interval
            for field, wanted in (("hits", line.hits), ("total", line.total),
                                  ("rate", line.rate), ("ci_low", low), ("ci_high", high),
                                  ("certified", line.certified)):
                if row.get(field) != wanted:
                    problems.append(f"{name}.{field}: {row.get(field)!r} != {wanted!r}")
            if row.get("family") is None or row.get("scope") is None:
                problems.append(f"{name}: the declaration (family, scope) did not travel")
        # The slices too, or §4.2's «срезы» exist only in the text.
        slices = document["slices"]
        if not isinstance(slices, dict) or set(slices) != set(side.v5_by_axis):
            problems.append("the axis slices are not in the document")
        # v4's own levels, or the mandatory comparison is unreadable by machine.
        levels = document["v4_levels"]
        if not isinstance(levels, list) or len(levels) != len(side.v4_levels):
            problems.append(f"the v4 levels did not travel: {levels}")
        elif levels and "tost_verdict" not in levels[0]:
            problems.append("a v4 level row without its TOST verdict")
    return problems


def test_document_is_written_beside_the_markdown() -> list[str]:
    """§5.1 «рядом с markdown». The file is next to `<run>.report.txt`, named the
    same way, and reads back as the same document."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        written = write(v5_dir, v4_dir, METRIC_FUNCTIONS)
        run_id = run_id_of(v5_dir)
        if written.report.name != f"{run_id}.report.json":
            problems.append(f"the file is not named after the run: {written.report.name}")
        if not (v5_dir / f"{run_id}.report.txt").exists():
            problems.append("the markdown it is supposed to sit beside is missing")
        back = read(v5_dir)
        if back["lines"] != written.document["lines"]:
            problems.append("what was written is not what reads back")
        # A run with no document must SAY so rather than read as an empty one.
        empty = Path(tmp) / "nowhere"
        empty.mkdir()
        try:
            read(empty)
            problems.append("a directory with no run was read as a report")
        except (ReportError, ValueError):
            pass
    return problems


def test_incomplete_is_explained() -> list[str]:
    """A machine reader must be able to branch on WHY, not only on whether. The
    text report prints the three causes in three sections; a consumer that had
    to tell them apart was reading three places and guessing.

    THE COMPLETE HALF CARRIES A MEASURED CANARY MANIFEST. Since S02 an unmeasured
    S02 half is itself a cause (C1), so «a healthy run is not marked» can only be
    asserted of a run that really was measured — the fixture plants a version-1
    manifest with one hidden canary rather than leaving the S02 half empty.
    """
    problems: list[str] = []

    def always_one(_observations: object) -> Line:
        return Line(BROKEN, 1, 1)

    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        _plant_measured_manifest(v5_dir)
        broken: dict[str, Metric] = {**METRIC_FUNCTIONS, BROKEN: always_one}
        parts = read_parts(v5_dir, v4_dir)
        side = assemble(parts, broken)
        document = build(parts, side)
        if not document["incomplete"]:
            problems.append("a refused non-diagnostic metric did not mark the document")
        reasons = document["incomplete_reasons"]
        if not isinstance(reasons, list) or not any(BROKEN in str(one) for one in reasons):
            problems.append(f"the reasons do not name the refused metric: {reasons}")
        if BROKEN in dict(document["refused"]) and BROKEN in dict(document["lines"]):  # type: ignore[arg-type]
            problems.append("a refused metric was printed as a line anyway")
        # The other side, or «it says incomplete» would pass on a document that
        # can never be complete.
        healthy = build(parts, assemble(parts, METRIC_FUNCTIONS))
        if healthy["incomplete"] or healthy["incomplete_reasons"]:
            problems.append(f"a healthy run was marked incomplete: {healthy['incomplete_reasons']}")
    return problems


def test_public_is_an_allowlist() -> list[str]:
    """Item 17: «состав определяется явным списком в контракте, не «всё кроме»».

    The check that separates the two spellings: a field the private document
    grows tomorrow must be ABSENT from the public one. Under «copy and pop» it
    would be published, and nobody would notice until it was in an article."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        parts = read_parts(v5_dir, v4_dir)
        document = build(parts, assemble(parts, METRIC_FUNCTIONS))
        document["внутреннее_поле"] = "тайна прогона"
        shown = public(document)
        if "внутреннее_поле" in shown:
            problems.append("a field nobody allowlisted was published")
        extra = set(shown) - set(PUBLIC_TOP_LEVEL) - {"lines_withheld"}
        if extra:
            problems.append(f"the public file carries keys outside the allowlist: {sorted(extra)}")
        lines = shown["lines"]
        if not isinstance(lines, dict):
            problems.append("the public file carries no lines")
            return problems
        outside = sorted(set(lines) - set(PUBLIC_LINES))
        if outside:
            problems.append(f"private lines reached the public file: {outside}")
        if not lines:
            problems.append("the public file has no line at all — the allowlist is dead")
        for name, row in lines.items():
            beyond = sorted(set(row) - set(PUBLIC_LINE_FIELDS))
            if beyond:
                problems.append(f"{name}: fields outside the line allowlist: {beyond}")
        # The two diagnostics of the `public` family must NOT be published: their
        # own declarations say they are not the public quantities of that name.
        for name in ("rewrite_ratio_v5", "shared_block_answer"):
            if name in lines:
                problems.append(f"{name} was published although it is not the public quantity")
        if shown.get("lines_withheld", 0) <= 0:
            problems.append("the public file does not say that it is a substring")
    return problems


def test_public_carries_no_value_of_the_corpus() -> list[str]:
    """§5.3: «публичный не содержит ни одного значения из корпуса». The fixture's
    real name, its phone and the substitute minted for it are searched for in the
    public file's own bytes — and found in the private one, or the search would
    prove nothing."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        written = write(v5_dir, v4_dir, METRIC_FUNCTIONS)
        shown = written.public.read_text(encoding="utf-8")
        for value in (REAL_NAME, REAL_PHONE, FAKE_NAME, RUN_ID):
            if value in shown:
                problems.append(f"the public file carries {value!r}")
        # A case id is not personal data, and it is still out: a public file that
        # named cases would let a reader of the article ask for them.
        for case_id in ("c-0001", "c-0002"):
            if case_id in shown:
                problems.append(f"the public file names case {case_id}")
        # The other side: the private document DOES name the run, or the search
        # above is a search of an empty file.
        if RUN_ID not in written.report.read_text(encoding="utf-8"):
            problems.append("the private document does not name the run — the check is vacuous")
    return problems


def test_cost_matches_the_run() -> list[str]:
    """The cost block is built from the atoms the text lines are built from, so
    the two cannot disagree about a number. Pinned against the run's own
    `meta.json` — the ceiling a cost line without it could not name."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        parts = read_parts(v5_dir, v4_dir)
        document = build(parts, assemble(parts, METRIC_FUNCTIONS))
        cost = document["cost"]
        if not isinstance(cost, dict):
            problems.append("there is no cost block")
            return problems
        if cost.get("ceiling_usd") != CEILING_USD:
            problems.append(f"the ceiling is not the run's: {cost.get('ceiling_usd')}")
        if abs(float(cost.get("triples_usd") or 0.0) - 0.24) > 1e-9:
            problems.append(f"the triples' cost is not 2 × $0.12: {cost.get('triples_usd')}")
        if abs(float(cost.get("judge_usd") or 0.0) - 0.02) > 1e-9:
            problems.append(f"the judge's share is not 2 × $0.01: {cost.get('judge_usd')}")
        if abs(float(cost.get("ledger_usd") or 0.0) - 0.24) > 1e-9:
            problems.append(f"the ledger total did not travel: {cost.get('ledger_usd')}")
        counts = cost.get("triples")
        if not isinstance(counts, dict) or counts.get("complete") != 2:
            problems.append(f"the triple counts are wrong: {counts}")
        # A missing triples file is «неизвестно», never «$0.00».
        records_path = v5_dir / f"{run_id_of(v5_dir)}.triples.jsonl"
        kept = records_path.read_text(encoding="utf-8")
        records_path.unlink()
        blind = build(read_parts(v5_dir, v4_dir), assemble(read_parts(v5_dir, v4_dir),
                                                           METRIC_FUNCTIONS))["cost"]
        records_path.write_text(kept, encoding="utf-8")
        if not isinstance(blind, dict) or blind.get("triples_usd") is not None:
            problems.append(f"a run with no triples file was costed anyway: {blind}")
        if isinstance(blind, dict) and not blind.get("missing"):
            problems.append("the document does not say which file is missing")
    return problems


def test_summary_lines_read_the_document() -> list[str]:
    """What `trend` prints per run comes off the document, not off the text — a
    trend that parsed the report's spacing broke the day the spacing moved."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        parts = read_parts(v5_dir, v4_dir)
        document = build(parts, assemble(parts, METRIC_FUNCTIONS))
        rows = summary_lines(document, ["leak", "нет_такой_метрики"])
        if not rows or "/" not in rows[0]:
            problems.append(f"a printed line did not summarise: {rows}")
        if len(rows) != 2 or "н/д" not in rows[1]:
            problems.append(f"a metric the run does not carry must read «н/д»: {rows}")
    return problems


def test_public_refuses_a_document_missing_an_allowlisted_field() -> list[str]:
    """The allowlist is a CONTRACT with the private document, in both
    directions: a field on the list that the document stopped carrying is a
    refusal naming it, not a public file that is quietly shorter."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        parts = read_parts(v5_dir, v4_dir)
        document = build(parts, assemble(parts, METRIC_FUNCTIONS))
        short = {key: value for key, value in document.items() if key != "tier"}
        try:
            public(short)
            problems.append("a document missing an allowlisted field was published anyway")
        except ReportError as refused:
            if "tier" not in str(refused):
                problems.append(f"the refusal does not name the field: {refused}")
    return problems


def test_the_two_names_are_run_files_of_the_contract() -> list[str]:
    """Both files are ROWS of `contracts.RUN_FILES`, so `records.run_file`
    builds them and a name outside the contract is refused there.

    This replaced a local path helper. The helper was right while the rows did
    not exist; keeping it afterwards would have been a second way to spell a run
    file, and the failure that shape produces is a reader looking for a file no
    run writes."""
    problems: list[str] = []
    for name in (REPORT_JSON_NAME, PUBLIC_JSON_NAME):
        if name not in contracts.RUN_FILES:
            problems.append(f"{name} is not in RUN_FILES — the contract does not know the file "
                            f"every consumer of §5.1 reads")
    try:
        records.run_file(Path("/tmp"), "id", "<run>.invented.json")
        problems.append("a run file outside RUN_FILES was built")
    except records.RecordError:
        pass
    if records.run_file(Path("/tmp"), "id", REPORT_JSON_NAME).name != "id.report.json":
        problems.append("the run id is not substituted into the name")
    if records.run_file(Path("/tmp"), "id", PUBLIC_JSON_NAME).name != "id.public.json":
        problems.append("the public file is not named after the run either")
    return problems


def _canary_section(text: str) -> str:
    """The §1bis block of a rendered report, heading to the next section."""
    start = text.find("1bis.")
    if start == -1:
        return ""
    end = text.find("\n2.", start)
    return text[start:end if end != -1 else len(text)]


def test_unmeasured_canaries_are_never_printed_as_zero_leaks() -> list[str]:
    """S02 — AN UNMEASURED RUN MUST NOT READ AS A CLEAN ONE, in all three
    finished surfaces.

    THE DEFECT THIS PINS. A saved run with no `canary_manifest.json` is
    `NOT_MEASURED` at the source, and that is correct — but the finish line
    dropped the status: §1bis iterated `by_boundary()`, which is `{}` when the
    report has no boundaries, so the section rendered as a heading with no rows
    (indistinguishable from «measured, zero leaks»); the oracle sidecar wrote
    `"canaries": {}` with no status; and the versioned machine report carried no
    canary field at all. A reader of the finished report could not tell a run
    that measured nothing from a run that leaked nothing.

    THE CHECK IS NOT VACUOUS. It first demands the SOURCE be `NOT_MEASURED` with
    a reason (the fixture writes no manifest), then reads the three produced
    surfaces back. The other side is exercised too: a manifest is planted with
    one hidden and one leaked surface per delivered boundary, and the same three
    surfaces must then say `MEASURED`, keep the per-boundary counts and still
    name the leak — so a hard-coded «NOT_MEASURED» could not pass.

    NO PROVIDER, NO NETWORK, NO ENGINE: the fixture is `test_report.build_run`,
    and the planted surfaces are read off the run's own saved delivered bytes,
    never off a detector span.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        v5_dir, v4_dir = _built(root)
        run_id = run_id_of(v5_dir)
        source = pc.check_run(v5_dir)
        if source.status != pc.STATUS_NOT_MEASURED:
            return [f"the fixture carries a manifest (status {source.status!r}) — "
                    f"the unmeasured half is vacuous"]
        if not source.reason:
            problems.append("the source report is NOT_MEASURED with no reason")
        # --- surface 1: the human report, and surface 2: the oracle sidecar ----
        report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        text = (v5_dir / f"{run_id}.report.txt").read_text(encoding="utf-8")
        section = _canary_section(text)
        if not section:
            problems.append("§1bis is absent from the finished report")
        if pc.STATUS_NOT_MEASURED not in section:
            problems.append("§1bis does not say NOT_MEASURED — an unmeasured run reads as a "
                            "measured one")
        if source.reason not in section:
            problems.append("§1bis names the status but not the reason")
        if "скрыто" in section:
            problems.append("§1bis printed per-boundary count rows for an unmeasured run — "
                            "absence reads as zero leaks")
        oracle = json.loads((v5_dir / f"{run_id}.oracle.json").read_text(encoding="utf-8"))
        if oracle.get("canary_status") != pc.STATUS_NOT_MEASURED:
            problems.append(f"the oracle sidecar does not carry the status: "
                            f"{oracle.get('canary_status')!r}")
        if not oracle.get("canary_reason"):
            problems.append("the oracle sidecar does not carry the reason")
        if oracle.get("canaries"):
            problems.append(f"the oracle sidecar wrote boundary counts for an unmeasured run: "
                            f"{oracle.get('canaries')!r}")
        # --- surface 3: the versioned machine report --------------------------
        document = json.loads(write(v5_dir, v4_dir, METRIC_FUNCTIONS)
                              .report.read_text(encoding="utf-8"))
        if document.get("canary_status") != pc.STATUS_NOT_MEASURED:
            problems.append(f"the machine report omits the canary status: "
                            f"{document.get('canary_status')!r}")
        if not document.get("canary_reason"):
            problems.append("the machine report omits the canary reason")
        if document.get("canary_by_boundary"):
            problems.append(f"the machine report carries boundary counts for an unmeasured run: "
                            f"{document.get('canary_by_boundary')!r}")

        # --- the other side: a MEASURED run keeps its counts and its leak ------
        delivered = _fixture_payloads()
        specs: list[pc.CanarySpec] = []
        seen_names: list[str] = []
        for payload in delivered:
            if payload.name in seen_names:
                continue
            seen_names.append(payload.name)
            specs.append(pc.CanarySpec(
                f"absent@{payload.name}", "PHONE", payload.name,
                (pc.PlantedSurface(f"CANARY-NOT-IN-BYTES-{payload.name}", pc.SURFACE_FULL),),
                "", "message"))
            visible = next((word for word in re.findall(r"[^\W\d_]{4,}", payload.text)
                            if pc.surface_in(payload.text, word)), "")
            if not visible:
                return problems + [f"no whole-word canary stands in {payload.name!r}"]
            specs.append(pc.CanarySpec(
                f"leak@{payload.name}", "NAME", payload.name,
                (pc.PlantedSurface(visible, pc.SURFACE_FULL),), "", "message"))
        _write_capture_fixture(v5_dir, pc.CanaryManifest(
            canaries=tuple(specs), source="s02-report-surface-test"), delivered)
        report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        text = (v5_dir / f"{run_id}.report.txt").read_text(encoding="utf-8")
        section = _canary_section(text)
        if pc.STATUS_MEASURED not in section:
            problems.append("a measured run does not say MEASURED in §1bis")
        if "скрыто" not in section:
            problems.append("a measured run printed no per-boundary counts")
        oracle = json.loads((v5_dir / f"{run_id}.oracle.json").read_text(encoding="utf-8"))
        if oracle.get("canary_status") != pc.STATUS_MEASURED:
            problems.append(f"the oracle sidecar did not report the measured run: "
                            f"{oracle.get('canary_status')!r}")
        counts = oracle.get("canaries")
        if not isinstance(counts, dict) or not counts:
            problems.append(f"the measured run's per-boundary counts did not travel: {counts!r}")
        else:
            if not any(one.get("leaked", 0) >= 1 for one in counts.values()):
                problems.append(f"a planted leak was not counted: {counts!r}")
            if not any(one.get("hidden", 0) >= 1 for one in counts.values()):
                problems.append(f"a hidden canary was not counted: {counts!r}")
        document = json.loads(write(v5_dir, v4_dir, METRIC_FUNCTIONS)
                              .report.read_text(encoding="utf-8"))
        if document.get("canary_status") != pc.STATUS_MEASURED:
            problems.append(f"the machine report did not report the measured run: "
                            f"{document.get('canary_status')!r}")
        coverage = document.get("canary_capture")
        if coverage != {"known": True, "captured": 2, "intervention": 2,
                        "selected": 2}:
            problems.append(f"the machine report has no capture denominator: {coverage!r}")
        machine = document.get("canary_by_boundary")
        if not isinstance(machine, dict) or not any(
                one.get("leaked", 0) >= 1 for one in machine.values()):
            problems.append(f"the machine report lost the measured counts: {machine!r}")
    return problems


def test_unmeasured_canaries_make_the_public_file_incomplete() -> list[str]:
    """S02 C1 — THE OUTWARD FILE MUST NOT BE THE ONE SURFACE THAT SAYS «ПОЛНЫЙ».

    THE COUNTEREXAMPLE THIS PINS. A saved run with no `canary_manifest.json`
    published `<run>.public.json` with `incomplete: false`,
    `incomplete_reasons: []` and no canary key at all, because canary status fed
    neither the flag nor the reason list. That is not silence: the public file
    AFFIRMATIVELY claimed completeness while omitting the fact that invalidates
    it, and the public file is the one whose readers by construction cannot
    consult §1bis. The reason travels in `incomplete_reasons` and, as status and
    reason only — never a corpus value — in the canary fields themselves.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        run_id = run_id_of(v5_dir)
        from bench.agentpii5.report import report_lines as render_report
        render_report(v5_dir, v4_dir, METRIC_FUNCTIONS)
        written = write(v5_dir, v4_dir, METRIC_FUNCTIONS)
        shown = json.loads(written.public.read_text(encoding="utf-8"))
        if not shown.get("incomplete"):
            problems.append(f"the public file calls an unmeasured run complete: "
                            f"incomplete={shown.get('incomplete')!r}")
        reasons = shown.get("incomplete_reasons")
        if not isinstance(reasons, list) or not any("канаре" in str(one).lower() for one in reasons):
            problems.append(f"the public file does not name the canary reason: {reasons!r}")
        if shown.get("canary_status") != pc.STATUS_NOT_MEASURED:
            problems.append(f"the public file omits the canary status: "
                            f"{shown.get('canary_status')!r}")
        if not shown.get("canary_reason"):
            problems.append("the public file omits the canary reason")
        # The two surfaces that already said it must keep saying it.
        private = json.loads(written.report.read_text(encoding="utf-8"))
        if (private.get("canary_status") != pc.STATUS_NOT_MEASURED
                or not private.get("canary_reason")):
            problems.append("the private report lost the canary status or reason")
        section = _canary_section((v5_dir / f"{run_id}.report.txt").read_text(encoding="utf-8"))
        if pc.STATUS_NOT_MEASURED not in section or str(private["canary_reason"]) not in section:
            problems.append("§1bis lost the status or the reason")
        # Status and reason only: no value of the corpus rides along with them.
        for value in (REAL_NAME, REAL_PHONE, FAKE_NAME):
            if value in written.public.read_text(encoding="utf-8"):
                problems.append(f"the public file now carries {value!r}")
    return problems


def test_an_empty_manifest_cannot_render_clean() -> list[str]:
    """S02 C2 — a known-version manifest with ZERO canaries must not render
    `MEASURED`/«чисто» on ANY finished surface.

    The source guard lives in `check_run` (and `scan`); this check is the
    consequence: §1bis says NOT_MEASURED with a reason instead of printing a
    status line and nothing else, and both JSON documents mark the run
    incomplete. A run that planted nothing has no denominator, so «no leaks»
    about it is not a fact.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        run_id = run_id_of(v5_dir)
        (v5_dir / pc.MANIFEST_ARTIFACT).write_text(json.dumps(
            {"version": pc.MANIFEST_VERSION,
             "manifest": {"canaries": [], "neighbours": []}}, ensure_ascii=False),
            encoding="utf-8")
        source = pc.check_run(v5_dir)
        if source.status != pc.STATUS_NOT_MEASURED or source.ok:
            problems.append(f"the empty manifest measured as {source.status!r} ok={source.ok}")
        from bench.agentpii5.report import report_lines as render_report
        render_report(v5_dir, v4_dir, METRIC_FUNCTIONS)
        section = _canary_section((v5_dir / f"{run_id}.report.txt").read_text(encoding="utf-8"))
        if pc.STATUS_NOT_MEASURED not in section:
            problems.append("§1bis calls an empty manifest MEASURED")
        if source.reason not in section:
            problems.append("§1bis does not print the reason the empty manifest is unmeasured")
        if "скрыто" in section:
            problems.append("§1bis printed per-boundary rows for a run that declared no canary")
        written = write(v5_dir, v4_dir, METRIC_FUNCTIONS)
        document = json.loads(written.report.read_text(encoding="utf-8"))
        if document.get("canary_status") != pc.STATUS_NOT_MEASURED:
            problems.append(f"the machine report calls an empty manifest "
                            f"{document.get('canary_status')!r}")
        if document.get("canary_by_boundary"):
            problems.append(f"the machine report wrote rows for a zero-canary manifest: "
                            f"{document.get('canary_by_boundary')!r}")
        shown = json.loads(written.public.read_text(encoding="utf-8"))
        if not shown.get("incomplete"):
            problems.append("the public file calls a zero-canary run complete")
        if not any("канаре" in str(one).lower()
                   for one in shown.get("incomplete_reasons", [])):
            problems.append(f"the public file does not name the canary reason: "
                            f"{shown.get('incomplete_reasons')!r}")
    return problems


def test_measured_canaries_keep_their_counts_and_stay_complete() -> list[str]:
    """THE GENUINE MEASUREMENT IS NOT COLLATERAL. A real version-1 manifest keeps
    its hidden/leaked counts, its neighbour damage and its unreached boundary on
    the machine report and §1bis, and is NOT dragged into «НЕПОЛНЫЙ» by the
    canary term C1 adds — otherwise the fix for the empty case would mark every
    honest run and the word would stop meaning anything.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        delivered = _fixture_payloads()
        run_id = run_id_of(v5_dir)
        target = delivered[0]
        # A surface that really stands in the delivered bytes, found by the
        # scanner's OWN matcher: a whole letter token of the payload, so the
        # leak half is not vacuous. This is a fixture literal, never a corpus
        # value the instrument picked out of saved text.
        visible = next((one for one in re.findall(r"[^\W\d_]{4,}", target.text)
                        if pc.surface_in(target.text, one)), "")
        if not visible:
            return problems + [f"no declared surface stands in {target.name!r} — "
                               f"the leak half is vacuous"]
        specs = (
            pc.CanarySpec("hidden", "PHONE", target.name,
                          (pc.PlantedSurface("CANARY-NEVER-WRITTEN-ANYWHERE", pc.SURFACE_FULL),),
                          "", "message"),
            pc.CanarySpec("leaked", "NAME", target.name,
                          (pc.PlantedSurface(visible, pc.SURFACE_FULL),),
                          "", "message"),
            pc.CanarySpec("unreached", "PHONE", "model_request",
                          (pc.PlantedSurface("CANARY-NEVER-DELIVERED", pc.SURFACE_FULL),),
                          "", "message"),
        )
        _write_capture_fixture(v5_dir, pc.CanaryManifest(
            canaries=specs, neighbours=(
                pc.Neighbour(target.name, "NEIGHBOUR-TEXT-NOT-PRESENT"),),
            source="s02-measured-test"), delivered)
        source = pc.check_run(v5_dir)
        if source.status != pc.STATUS_MEASURED:
            problems.append(f"the measured fixture did not measure: {source.status!r}")
        if source.ok:
            problems.append("a leaking, neighbour-damaging, unreached manifest reads as clean")
        if not source.leaks or not source.neighbour_damage or not source.unreached:
            problems.append(f"the measured fixture lost a fact: leaks={source.leaks} "
                            f"damage={source.neighbour_damage} unreached={source.unreached}")
        from bench.agentpii5.report import report_lines as render_report
        render_report(v5_dir, v4_dir, METRIC_FUNCTIONS)
        section = _canary_section((v5_dir / f"{run_id}.report.txt").read_text(encoding="utf-8"))
        for wanted in ("скрыто", "СОСЕДИ ЗАТРОНУТЫ", "ГРАНИЦЫ НЕ ДОСТИГНУТЫ"):
            if wanted not in section:
                problems.append(f"§1bis lost {wanted!r} on a measured run")
        if "ЗАХВАТЫ: 2/2" not in section:
            problems.append("§1bis omitted the measured I-arm denominator")
        written = write(v5_dir, v4_dir, METRIC_FUNCTIONS)
        document = json.loads(written.report.read_text(encoding="utf-8"))
        if document.get("canary_capture") != {
                "known": True, "captured": 2, "intervention": 2, "selected": 2}:
            problems.append(f"the machine report lost capture counts: "
                            f"{document.get('canary_capture')!r}")
        if document.get("incomplete"):
            problems.append("a genuinely measured run was marked incomplete")
        counts = document.get("canary_by_boundary")
        if not isinstance(counts, dict) or not any(
                one.get("leaked", 0) >= 1 for one in counts.values()):
            problems.append(f"the measured counts did not travel: {counts!r}")
        if not document.get("canary_neighbour_damage") or not document.get("canary_unreached"):
            problems.append("the machine report lost the neighbour damage or the unreached boundary")
        shown = json.loads(written.public.read_text(encoding="utf-8"))
        if shown.get("canary_capture") != document.get("canary_capture"):
            problems.append("the public report lost the safe capture denominator")
        if shown.get("incomplete"):
            problems.append("a genuinely measured run reads as incomplete in public")
        if shown.get("canary_status") != pc.STATUS_MEASURED:
            problems.append(f"the public file did not carry the measured status: "
                            f"{shown.get('canary_status')!r}")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("both_files_name_the_model_the_run_recorded",
         test_both_files_name_the_model_the_run_recorded),
        ("document_carries_every_printed_line", test_document_carries_every_printed_line),
        ("document_is_written_beside_the_markdown", test_document_is_written_beside_the_markdown),
        ("incomplete_is_explained", test_incomplete_is_explained),
        ("public_is_an_allowlist", test_public_is_an_allowlist),
        ("public_carries_no_value_of_the_corpus", test_public_carries_no_value_of_the_corpus),
        ("cost_matches_the_run", test_cost_matches_the_run),
        ("summary_lines_read_the_document", test_summary_lines_read_the_document),
        ("public_refuses_a_document_missing_an_allowlisted_field",
         test_public_refuses_a_document_missing_an_allowlisted_field),
        ("the_two_names_are_run_files_of_the_contract",
         test_the_two_names_are_run_files_of_the_contract),
        ("unmeasured_canaries_are_never_printed_as_zero_leaks",
         test_unmeasured_canaries_are_never_printed_as_zero_leaks),
        ("unmeasured_canaries_make_the_public_file_incomplete",
         test_unmeasured_canaries_make_the_public_file_incomplete),
        ("an_empty_manifest_cannot_render_clean", test_an_empty_manifest_cannot_render_clean),
        ("measured_canaries_keep_their_counts_and_stay_complete",
         test_measured_canaries_keep_their_counts_and_stay_complete),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("reportjson: PASS" if not failures
          else "reportjson: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
