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
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii5 import contracts, records
from bench.agentpii5.contracts import Line, Metric
from bench.agentpii5.fixtures import FAKE_NAME, REAL_NAME, REAL_PHONE
from bench.agentpii5.metrics import METRIC_FUNCTIONS
from bench.agentpii5.report import assemble, read_parts, report_lines, run_id_of
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
    to tell them apart was reading three places and guessing."""
    problems: list[str] = []

    def always_one(_observations: object) -> Line:
        return Line(BROKEN, 1, 1)

    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
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


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
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
