"""S02 — INDEPENDENT PAYLOAD CANARIES, from a construction-time manifest.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_payload_canaries      # ~1 s

THE REDESIGN. Ground truth is a `CanaryManifest` the FIXTURE built: per canary
it names the boundary, the full original, and ONLY the fragments the fixture
deliberately planted. The scanner matches exactly those surfaces, boundary-aware;
it infers no prefix, cuts no substring and reads no saved corpus value. A leak
exists iff a declared surface is in the delivered bytes — detector/span/KV/result
evidence may CLASSIFY a leak the manifest already found and may never decide one.
A run without a manifest is NOT_MEASURED, never a synthesised clean reading.
"""
from __future__ import annotations

import json
import pathlib
from collections.abc import Callable

from bench.agentpii5 import contracts, payload_canaries as pc

NO_ENGINE: str = contracts.FORBIDDEN_IMPORT_PREFIX


def test_no_pseudex() -> list[str]:
    import sys
    bad = [name for name in sys.modules if name.split(".")[0] == NO_ENGINE]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_manifest_names_every_boundary_and_surface() -> list[str]:
    """Every boundary carries a canary, every canary declares a FULL surface,
    and every neighbour is an explicit construction-time literal."""
    fixture = pc.make_canary_fixture()
    manifest = fixture.manifest
    problems: list[str] = []
    for name in pc.BOUNDARIES:
        if name not in manifest.boundaries():
            problems.append(f"{name}: the manifest declares nothing there")
    for spec in manifest.canaries:
        if not spec.surfaces:
            problems.append(f"{spec.id}: declares no surface")
        if not any(one.kind == pc.SURFACE_FULL for one in spec.surfaces):
            problems.append(f"{spec.id}: no FULL surface declared")
        for one in spec.surfaces:
            if one.kind not in (pc.SURFACE_FULL, pc.SURFACE_FRAGMENT):
                problems.append(f"{spec.id}: surface kind {one.kind!r} is not declared")
    for name in pc.BOUNDARIES:
        if not any(one.boundary == name for one in manifest.neighbours):
            problems.append(f"{name}: names no neighbouring ordinary literal")
    if manifest.version != pc.MANIFEST_VERSION:
        problems.append(f"the fixture manifest is version {manifest.version}")
    return problems


def test_a_right_run_is_clean() -> list[str]:
    """Every declared surface hidden, every neighbour intact, all boundaries reached."""
    fixture = pc.make_canary_fixture()
    report = pc.scan(fixture.manifest, fixture.delivered)
    problems = [f"{one.canary_id} leaked on {one.boundary} [{one.miss_class}]"
                for one in report.leaks]
    problems += [f"ordinary text masked or lost: {one}" for one in report.neighbour_damage]
    problems += [f"a declared boundary was never delivered: {one}" for one in report.unreached]
    if report.status != pc.STATUS_MEASURED:
        problems.append(f"the constructed run reported {report.status}")
    if not report.ok:
        problems.append(f"a right run is not ok: {report}")
    return problems


def test_a_full_planted_leak_reds_only_its_own_boundary() -> list[str]:
    """Put the real value back at ONE boundary and exactly that boundary reds."""
    fixture = pc.make_canary_fixture()
    problems: list[str] = []
    for name in pc.BOUNDARIES:
        mutant = pc.mutant_capture(fixture.delivered, name)
        report = pc.scan(fixture.manifest, mutant)
        reds = {one.boundary for one in report.leaks}
        if name not in reds:
            problems.append(f"{name}: the real value went unreported")
        stray = reds - {name}
        if stray:
            problems.append(f"{name}: reddened {sorted(stray)} as well — a scan that cannot "
                            f"localise the leak cannot direct a fix")
    return problems


def test_explicitly_planted_cut_fragments_red() -> list[str]:
    """An EXPLICITLY planted cut-by-1/2/3/5 fragment is a leak of kind `fragment`.

    The fragment is declared in the manifest because the fixture wrote it. The
    whole literal is nowhere in the payload, so a whole-literal scan would call
    it clean — which is the S01 shape."""
    problems: list[str] = []
    for cut in (1, 2, 3, 5):
        base = pc.make_number_fixture("", salt=f"cut{cut}")
        full = base.full_literal
        fragment = full[:len(full) - cut]
        if pc.surface_in(fragment, full):
            problems.append(f"cut-by-{cut}: the fragment still contains the full literal")
            continue
        fixture = pc.make_number_fixture(fragment, fragments=(fragment,), salt=f"cut{cut}")
        report = pc.scan(fixture.manifest, fixture.delivered)
        found = [one for one in report.leaks if one.canary_id == "num"]
        if not found:
            problems.append(f"cut-by-{cut}: the planted fragment {fragment!r} went unreported")
        elif found[0].surface_kind != pc.SURFACE_FRAGMENT or found[0].surface != fragment:
            problems.append(f"cut-by-{cut}: reported {found[0].surface!r} "
                            f"({found[0].surface_kind}), expected the declared fragment")
    return problems


def test_undeclared_prefix_stays_negative() -> list[str]:
    """A cut the fixture did NOT declare is not a leak, however identifying it looks."""
    problems: list[str] = []
    base = pc.make_number_fixture("", salt="undeclared")
    full = base.full_literal
    fragment = full[:len(full) - 3]
    fixture = pc.make_number_fixture(fragment, fragments=(), salt="undeclared")
    report = pc.scan(fixture.manifest, fixture.delivered)
    if report.leaks:
        problems.append(f"an undeclared prefix was called a leak: "
                        f"{[(one.surface, one.surface_kind) for one in report.leaks]}")
    short = full[:4]
    fixture = pc.make_number_fixture(short, fragments=(), salt="undeclared")
    if pc.scan(fixture.manifest, fixture.delivered).leaks:
        problems.append(f"the {len(short)}-character prefix {short!r} was called a leak")
    return problems


def test_longer_number_stays_negative() -> list[str]:
    """A LONGER number that merely starts with the declared digits is another number."""
    problems: list[str] = []
    base = pc.make_number_fixture("", salt="longer")
    full = base.full_literal
    fragment = full[:len(full) - 3]
    longer = "+" + pc._digits_of(full) + "000"
    fixture = pc.make_number_fixture(longer, fragments=(fragment,), salt="longer")
    report = pc.scan(fixture.manifest, fixture.delivered)
    if report.leaks:
        problems.append(f"a longer digit run was called a leak: "
                        f"{[(one.surface, one.surface_kind) for one in report.leaks]}")
    return problems


def test_ordinary_neighbours_are_preserved_and_damage_reds() -> list[str]:
    """OVER-MASKING IS A DEFECT TOO, and the axis is the manifest's own literals."""
    fixture = pc.make_canary_fixture()
    problems: list[str] = []
    if pc.scan(fixture.manifest, fixture.delivered).neighbour_damage:
        problems.append("the right run already reports neighbour damage")
    for neighbour in fixture.manifest.neighbours:
        hurt = pc.replace_delivery(fixture, neighbour.boundary,
                                   fixture.boundary(neighbour.boundary).text.replace(
                                       neighbour.text, "***"))
        report = pc.scan(fixture.manifest, hurt.delivered)
        if not any(neighbour.text[:12] in one for one in report.neighbour_damage):
            problems.append(f"masking {neighbour.text!r} on {neighbour.boundary} "
                            f"went unreported: {list(report.neighbour_damage)}")
        if report.leaks:
            problems.append(f"damaging {neighbour.text!r} invented a leak: {report.leaks}")
    return problems


def test_an_unreached_boundary_is_not_reported_clean() -> list[str]:
    """AN ERROR BOUNDARY NOBODY DELIVERED IS UNMEASURED, not clean.

    S01 lived in an error payload, so a report that silently drops the row for a
    boundary the run never reached is the report that missed it."""
    fixture = pc.make_canary_fixture()
    without_error = tuple(one for one in fixture.delivered if one.name != "tool_error")
    report = pc.scan(fixture.manifest, without_error)
    problems: list[str] = []
    if "tool_error" not in report.unreached:
        problems.append(f"an undelivered error boundary was not flagged: {report.unreached}")
    if report.ok:
        problems.append("a run whose error boundary was never delivered reads as clean")
    rows = report.by_boundary()
    if "tool_error" not in rows:
        problems.append("the error boundary has no row at all")
    return problems


def test_no_manifest_is_not_measured() -> list[str]:
    """A SAVED RUN WITHOUT A MANIFEST IS NOT_MEASURED — never a synthesised clean.

    The old reader derived provenance from the run's spans and neighbours from
    whatever tokens the payload held. Both were guesses; with no versioned
    `canary_manifest.json` the honest answer is that nothing was measured."""
    import tempfile
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp)
        report = pc.check_run(run_dir)
        if report.status != pc.STATUS_NOT_MEASURED:
            problems.append(f"a run with no manifest reported {report.status!r}")
        if report.ok:
            problems.append("a run with no manifest reads as clean")
        if not report.reason:
            problems.append("NOT_MEASURED carries no reason")
        (run_dir / pc.MANIFEST_ARTIFACT).write_text(
            '{"version": 999, "manifest": {"canaries": []}}', encoding="utf-8")
        again = pc.check_run(run_dir)
        if again.status != pc.STATUS_NOT_MEASURED:
            problems.append(f"an unknown manifest version was accepted: {again.status!r}")
        # A FUTURE FORMAT AND A MISSING FILE ARE NOT THE SAME SENTENCE. The file
        # was there with a version this reader does not know; an operator reading
        # «no canary_manifest.json in the run» would go looking for a file that is
        # present. The reason must tell the two apart.
        if again.reason == report.reason:
            problems.append("an unsupported manifest version carries the same reason as an "
                            f"absent artifact: {again.reason!r}")
        # A manifest that is present but not readable is unmeasured too, and never
        # a crash: a reader that raises on a stranger's file is a reader a run can
        # stop with.
        (run_dir / pc.MANIFEST_ARTIFACT).write_text("{not json", encoding="utf-8")
        broken = pc.check_run(run_dir)
        if broken.status != pc.STATUS_NOT_MEASURED or broken.ok:
            problems.append(f"a corrupt manifest reported {broken.status!r} ok={broken.ok}")
        if not broken.reason:
            problems.append("a corrupt manifest carries no reason")
    return problems


def test_empty_manifest_is_not_measured() -> list[str]:
    """S02 C2 — A KNOWN VERSION DECLARING ZERO CANARIES IS NOT A MEASUREMENT.

    THE COUNTEREXAMPLE THIS PINS. `{"version":1,"manifest":{"canaries":[]}}` was
    accepted as `MEASURED` with `ok=True` and `by_boundary()=={}`, and the §1bis
    of that run printed only its status line — the exact «heading with no rows»
    the redesign removed for the NOT_MEASURED case, restored one layer up. `ok`
    is the green verdict, so a run that planted nothing reported clean on zero
    evidence. A manifest with no denominator must be unmeasurable, not green,
    and it must be so through EVERY entry point — `check_run` and `scan` alike,
    or the guard is one caller away from being bypassed.
    """
    import tempfile
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp)
        (run_dir / pc.MANIFEST_ARTIFACT).write_text(json.dumps(
            {"version": pc.MANIFEST_VERSION, "manifest": {"canaries": [], "neighbours": []}},
            ensure_ascii=False), encoding="utf-8")
        report = pc.check_run(run_dir)
        if report.status != pc.STATUS_NOT_MEASURED:
            problems.append(f"a zero-canary manifest reported {report.status!r}")
        if report.ok:
            problems.append("a manifest that declares nothing reads as clean")
        if report.by_boundary():
            problems.append(f"a zero-canary manifest produced rows: {report.by_boundary()!r}")
        if not report.reason:
            problems.append("NOT_MEASURED for an empty manifest carries no reason")
        direct = pc.scan(pc.CanaryManifest(canaries=()),
                         (pc.CapturedPayload("model_input", "любые байты"),))
        if direct.status != pc.STATUS_NOT_MEASURED or direct.ok:
            problems.append(f"scan accepted an empty manifest: {direct.status!r} ok={direct.ok}")
    return problems


def test_evidence_classifies_but_never_decides() -> list[str]:
    """Evidence labels a leak the manifest already found; it cannot create one.

    A value the evidence claims was recognised and covered is still clean when
    the bytes do not carry it, and a value with no substitute on the record is a
    `detector` miss once the bytes DO carry it."""
    fixture = pc.make_canary_fixture()
    problems: list[str] = []
    right = pc.scan(fixture.manifest, fixture.delivered, pc.ProvenanceEvidence(
        substitutes={spec.id: "x" for spec in fixture.manifest.canaries},
        span_missed=frozenset(spec.id for spec in fixture.manifest.canaries)))
    if right.leaks:
        problems.append(f"evidence invented leaks on a clean run: {right.leaks}")
    mutant = pc.mutant_capture(fixture.delivered, "model_input")
    blind = pc.scan(fixture.manifest, mutant, pc.ProvenanceEvidence())
    classes = {one.miss_class for one in blind.leaks if one.boundary == "model_input"}
    if classes != {"detector"}:
        problems.append(f"a value with no minted substitute was classified {sorted(classes)}, "
                        f"expected detector")
    covered = pc.scan(fixture.manifest, mutant, pc.ProvenanceEvidence(
        substitutes={spec.id: "x" for spec in fixture.manifest.canaries}))
    if {one.miss_class for one in covered.leaks if one.boundary == "model_input"} != {"oracle"}:
        problems.append("a value the record claims was covered was not classified oracle")
    unlabelled = pc.scan(fixture.manifest, mutant)
    if not unlabelled.unclassified:
        problems.append("a leak with no evidence at all was not reported unclassified")
    return problems


def test_a_manifest_without_delivered_bytes_is_not_measured() -> list[str]:
    """S02 CAPTURE — A PLANTED MANIFEST IS NOT A MEASUREMENT.

    THE DEFECT THIS PINS. `check_run` paired a manifest with bytes it
    RECONSTRUCTED out of the run's own `mentions` (detector-derived substitute
    records) and the corpus messages, and it never built the composed
    `model_request` at all — so a manifest dropped into any saved run measured
    the reconstruction under test, not what the model was sent. A run that
    carries no `canary_capture` artifact must stay NOT_MEASURED no matter what
    manifest stands beside it; the bytes are a separate, versioned artifact and
    are never derived from detector records."""
    import tempfile
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp)
        fixture = pc.make_canary_fixture()
        (run_dir / pc.MANIFEST_ARTIFACT).write_text(
            json.dumps(pc.manifest_to_json(fixture.manifest), ensure_ascii=False),
            encoding="utf-8")
        report = pc.check_run(run_dir)
        if report.status != pc.STATUS_NOT_MEASURED:
            problems.append(f"a manifest with no delivered bytes measured as {report.status!r}")
        if report.ok:
            problems.append("a run with no persisted bytes reads as clean")
        if not report.reason or pc.CAPTURE_SUFFIX not in report.reason:
            problems.append(f"the reason does not name the missing capture artifact: "
                            f"{report.reason!r}")
    return problems


def test_the_capture_artifact_round_trips_exact_bytes() -> list[str]:
    """S02 CAPTURE — THE ARTIFACT CARRIES THE BYTES, AND THE READER READS THEM.

    Built through the WRITERS this module owns (`run_capture_row` →
    `append_row`), so the reader is checked against the file the harness writes
    and not against a hand-written dictionary. A mutation of one boundary's
    delivered bytes must move that boundary's row and no other: an instrument
    that cannot localise the change cannot direct a fix."""
    import tempfile
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp)
        fixture = pc.make_canary_fixture()
        spec = next(one for one in fixture.manifest.canaries
                    if one.boundary == "model_input")
        # The composed model-bound boundary is the one a hand-written fixture
        # cannot have and the real harness appends; the artifact must carry it
        # like any other, so it is added here explicitly.
        composed = pc.CapturedPayload(
            "model_request", fixture.delivered[0].text,
            fixture.delivered[0].real_text)
        delivered = fixture.delivered + (composed,)
        run = pc.RunCapture(case_id="c-0001", repeat=0, arm="I", manifest=fixture.manifest,
                            delivered=delivered)
        pc.append_capture(run_dir, "abc123", run)
        reads = pc.read_captures(run_dir)
        if len(reads) != 1 or reads[0] != run:
            return [f"the artifact did not round-trip: {reads!r}"]
        report = pc.check_run(run_dir)
        if report.status != pc.STATUS_MEASURED:
            problems.append(f"a written capture did not measure: {report.reason!r}")
        rows = report.by_boundary()
        # A row is present for every boundary the MANIFEST names — the fixture's
        # five; `model_request` is carried by the artifact and scanned by the
        # real-run test, which is where a manifest declaring it exists.
        for name in fixture.manifest.boundaries():
            if name not in rows:
                problems.append(f"{name}: no row after a read-back")
        if not any(one.name == "model_request" for one in pc.read_captures(run_dir)[0].delivered):
            problems.append("the composed model_request boundary did not survive the artifact")
        if rows.get("model_input", {}).get("hidden", 0) <= 0:
            problems.append(f"the round-tripped bytes hid nothing: {rows.get('model_input')!r}")
        # THE MUTATION: the real value put back at ONE boundary.
        leaked = pc.RunCapture(case_id=run.case_id, repeat=run.repeat, arm=run.arm,
                               manifest=run.manifest,
                               delivered=pc.mutant_capture(run.delivered, "model_input"))
        (run_dir / pc.capture_name("abc123")).unlink()
        pc.append_capture(run_dir, "abc123", leaked)
        mutated = pc.check_run(run_dir)
        reds = {one.boundary for one in mutated.leaks}
        if reds != {"model_input"}:
            problems.append(f"the mutation reddened {sorted(reds)}, expected only model_input")
        if spec.id not in {one.canary_id for one in mutated.leaks}:
            problems.append(f"{spec.id} was not the reported leak: "
                            f"{[one.canary_id for one in mutated.leaks]}")
    return problems


def test_a_broken_or_out_of_scope_capture_is_not_a_crash() -> list[str]:
    """S02 CAPTURE — A STRANGER'S FILE IS UNMEASURED, NOT AN EXCEPTION.

    Three shapes, one verdict each: a capture of unknown version, a capture
    whose JSON does not parse, and a capture naming a boundary outside
    `CAPTURE_BOUNDARIES`. The last one is the SCOPE boundary: a file that can
    invent a boundary name would put a leak in a row no reader has a column
    for. All three must report NOT_MEASURED with a reason — a reader that
    raises is a reader a run can stop with — and a run with NO capture must
    answer `read_captures` with an empty result, never with a fabricated one."""
    import tempfile
    problems: list[str] = []
    fixture = pc.make_canary_fixture()
    run = pc.RunCapture(case_id="c-0001", repeat=0, arm="I", manifest=fixture.manifest,
                        delivered=fixture.delivered)
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp)
        if pc.read_captures(run_dir) != ():
            problems.append("a run with no capture artifact produced bytes")
        path = run_dir / pc.capture_name("abc123")
        path.write_text('{"version": 999, "case_id": "c-0001", "repeat": 0, "arm": "I"}',
                        encoding="utf-8")
        unknown = pc.check_run(run_dir)
        if unknown.status != pc.STATUS_NOT_MEASURED or not unknown.reason:
            problems.append(f"a future capture version reported {unknown.status!r} "
                            f"reason={unknown.reason!r}")
        path.write_text("{not json", encoding="utf-8")
        broken = pc.check_run(run_dir)
        if broken.status != pc.STATUS_NOT_MEASURED or not broken.reason:
            problems.append(f"a corrupt capture reported {broken.status!r}")
        row = pc.capture_row(run)
        payloads = row["capture"]["payloads"]  # type: ignore[index]
        payloads[0]["name"] = "not_a_boundary"  # type: ignore[index]
        (run_dir / pc.MANIFEST_ARTIFACT).write_text(
            json.dumps(pc.manifest_to_json(fixture.manifest), ensure_ascii=False),
            encoding="utf-8")
        path.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
        outside = pc.check_run(run_dir)
        if outside.status != pc.STATUS_NOT_MEASURED or "not_a_boundary" not in outside.reason:
            problems.append(f"a capture naming an unknown boundary reported "
                            f"{outside.status!r} reason={outside.reason!r}")
    return problems


def test_capture_bounds_apply_per_row_and_to_the_whole_run() -> list[str]:
    """A 450-row archive may exceed one row's limit without losing measurement."""
    import tempfile
    fixture = pc.make_canary_fixture()
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp)
        payload = pc.CapturedPayload("model_input", "ordinary " * 1400)
        for number in range(450):
            pc.append_capture(run_dir, "many", pc.RunCapture(
                case_id=f"case-{number:03d}", repeat=0, arm="I",
                manifest=fixture.manifest, delivered=(payload,)))
        path = run_dir / pc.capture_name("many")
        if path.stat().st_size <= pc.CAPTURE_MAX_ROW_BYTES:
            return ["the 450-row fixture never crossed the per-row limit"]
        try:
            rows = pc.read_captures(run_dir)
        except pc.CaptureError as error:
            problems.append(f"a bounded 450-row archive was refused: {error}")
        else:
            if len(rows) != 450:
                problems.append(f"the 450-row archive read back {len(rows)} rows")
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp)
        pc.append_capture(run_dir, "oversize", pc.RunCapture(
            case_id="huge", repeat=0, arm="I", manifest=fixture.manifest,
            delivered=(pc.CapturedPayload("model_input", "x" * pc.CAPTURE_MAX_ROW_BYTES),)))
        try:
            pc.read_captures(run_dir)
            problems.append("one oversized capture row was accepted")
        except pc.CaptureError as error:
            if ":1:" not in str(error):
                problems.append(f"oversized row lacks a line number: {error}")
    return problems


def test_duplicate_capture_cannot_double_count() -> list[str]:
    """Resume append cannot count the same case and repeat twice."""
    import tempfile
    fixture = pc.make_canary_fixture()
    run = pc.RunCapture(case_id="same", repeat=0, arm="I",
                        manifest=fixture.manifest, delivered=fixture.delivered)
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp)
        pc.append_capture(run_dir, "duplicate", run)
        pc.append_capture(run_dir, "duplicate", run)
        try:
            pc.read_captures(run_dir)
        except pc.CaptureError as error:
            return [] if "duplicate" in str(error).lower() else [str(error)]
        return ["duplicate case/repeat rows were counted twice"]


def test_capture_rows_cover_every_executed_intervention() -> list[str]:
    """One missing capture cannot shrink a real run's measured denominator."""
    import tempfile
    fixture = pc.make_canary_fixture()
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp)
        triples = run_dir / "coverage.triples.jsonl"
        rows = (
            {"case_id": "first", "repeat": 0, "status": "complete", "arms": {"I": {}}},
            {"case_id": "second", "repeat": 0, "status": "complete", "arms": {"I": {}}},
            {"case_id": "refused", "repeat": 0, "status": "refused", "arms": {}},
        )
        triples.write_text("".join(json.dumps(one) + "\n" for one in rows), encoding="utf-8")
        for case_id in ("first", "second"):
            if case_id == "second":
                missing = pc.check_run(run_dir)
                if missing.status != pc.STATUS_NOT_MEASURED or "second" not in missing.reason:
                    problems.append(f"a missing intervention capture was hidden: "
                                    f"{missing.status!r} {missing.reason!r}")
            pc.append_capture(run_dir, "coverage", pc.RunCapture(
                case_id=case_id, repeat=0, arm="I", manifest=fixture.manifest,
                delivered=fixture.delivered))
        complete = pc.check_run(run_dir)
        if complete.status != pc.STATUS_MEASURED:
            problems.append(f"the refused no-I triple blocked two measured I arms: "
                            f"{complete.status!r} {complete.reason!r}")
        if (not complete.coverage_known or complete.capture_rows != 2
                or complete.intervention_rows != 2 or complete.selected_rows != 3):
            problems.append("the report lost capture/I/selected denominators: "
                            f"{complete.capture_rows}/{complete.intervention_rows}/"
                            f"{complete.selected_rows}")
    return problems


def test_zero_capture_archive_keeps_its_denominator() -> list[str]:
    """An old saved run (triples journal, no capture artifact) is NOT_MEASURED
    with its OWN denominator — 0 captures against the journal's I arms — never a
    bare 0/0 that reads like an empty run with nothing to measure."""
    import tempfile
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp)
        triples = run_dir / "old.triples.jsonl"
        rows = (
            {"case_id": "first", "repeat": 0, "status": "complete", "arms": {"I": {}}},
            {"case_id": "second", "repeat": 0, "status": "complete", "arms": {"I": {}}},
        )
        triples.write_text("".join(json.dumps(one) + "\n" for one in rows), encoding="utf-8")
        report = pc.check_run(run_dir)
        if report.status != pc.STATUS_NOT_MEASURED:
            problems.append(f"a zero-capture archive was not NOT_MEASURED: {report.status!r}")
        if (not report.coverage_known or report.capture_rows != 0
                or report.intervention_rows != 2 or report.selected_rows != 2):
            problems.append("the zero-capture report dropped its denominator: "
                            f"known={report.coverage_known} "
                            f"{report.capture_rows}/{report.intervention_rows}/"
                            f"{report.selected_rows}")
    return problems


def test_scanner_names_no_fixture_literal() -> list[str]:
    """The scan never names a literal: the fixture's own literals must not appear
    in its source, so it cannot be tuned against one fixture."""
    module = pathlib.Path(pc.__file__).read_text(encoding="utf-8")
    start = module.index("# --- the scan:")
    end = module.index("# --- classification:")
    scanner = module[start:end]
    problems: list[str] = []
    for literal in (spec.surfaces[0].text for spec in pc.make_canary_fixture().manifest.canaries):
        if literal in scanner:
            problems.append(f"the scanner names the fixture literal {literal!r}")
    return problems


CHECKS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("no_pseudex", test_no_pseudex),
    ("manifest_names_every_boundary_and_surface", test_manifest_names_every_boundary_and_surface),
    ("a_right_run_is_clean", test_a_right_run_is_clean),
    ("a_full_planted_leak_reds_only_its_own_boundary",
     test_a_full_planted_leak_reds_only_its_own_boundary),
    ("explicitly_planted_cut_fragments_red", test_explicitly_planted_cut_fragments_red),
    ("undeclared_prefix_stays_negative", test_undeclared_prefix_stays_negative),
    ("longer_number_stays_negative", test_longer_number_stays_negative),
    ("ordinary_neighbours_are_preserved_and_damage_reds",
     test_ordinary_neighbours_are_preserved_and_damage_reds),
    ("an_unreached_boundary_is_not_reported_clean",
     test_an_unreached_boundary_is_not_reported_clean),
    ("no_manifest_is_not_measured", test_no_manifest_is_not_measured),
    ("empty_manifest_is_not_measured", test_empty_manifest_is_not_measured),
    ("evidence_classifies_but_never_decides", test_evidence_classifies_but_never_decides),
    ("a_manifest_without_delivered_bytes_is_not_measured",
     test_a_manifest_without_delivered_bytes_is_not_measured),
    ("the_capture_artifact_round_trips_exact_bytes",
     test_the_capture_artifact_round_trips_exact_bytes),
    ("a_broken_or_out_of_scope_capture_is_not_a_crash",
     test_a_broken_or_out_of_scope_capture_is_not_a_crash),
    ("capture_bounds_apply_per_row_and_to_the_whole_run",
     test_capture_bounds_apply_per_row_and_to_the_whole_run),
    ("duplicate_capture_cannot_double_count", test_duplicate_capture_cannot_double_count),
    ("capture_rows_cover_every_executed_intervention",
     test_capture_rows_cover_every_executed_intervention),
    ("zero_capture_archive_keeps_its_denominator",
      test_zero_capture_archive_keeps_its_denominator),
    ("scanner_names_no_fixture_literal", test_scanner_names_no_fixture_literal),
)


def main() -> int:
    failures: list[str] = []
    for name, check in CHECKS:
        try:
            problems = check()
        except Exception as error:  # noqa: BLE001 — a raised check is a red check
            problems = [f"raised {type(error).__name__}: {error}"]
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print(f"payload_canaries: PASS ({len(pc.BOUNDARIES)} границ, "
          f"{len(pc.MISS_CLASSES)} классов)" if not failures
          else "payload_canaries: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
