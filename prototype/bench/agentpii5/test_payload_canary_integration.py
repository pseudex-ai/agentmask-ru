"""S02 INTEGRATION — the canaries against the REAL harness caller.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_payload_canary_integration

WHY THIS FILE IS NOT `test_payload_canaries`. That file proves the SCANNER over
payloads a test wrote. This one drives the same coroutine a paid run uses —
`harness.ConnectedArms.intervention` — with a connector double in place of the
provider, so the bytes the canaries scan are the bytes `GatewayV5` itself
delivered:

    hooks.user  → gateway._push      → model_input   and the composed model_request
    hooks.tool  → note_tool_call     → tool_args     (as the AGENT wrote them)
                → push_call          → tool_result / tool_error
    _run        → answer_leg         → final_answer  (model bytes vs customer bytes)

GROUND TRUTH IS CONSTRUCTION. The manifest lists each case item's declared value
on every boundary as a FULL surface; nothing is read from a detector span, a
delivered payload or a saved corpus, and the scan decides from manifest +
delivered bytes alone. The error boundary is DRIVEN, never assumed: a scripted
unparseable call goes through `push_call` so `tool_error` is reached, because an
unreached error boundary is the S01 shape and must not read as clean.

Removing the capture hook (`capture=False`) must unmeasure every boundary — if
the counts survived it, they came from somewhere other than the harness.

NO NETWORK, NO PROVIDER, NO MONEY. A missing `claude_agent_sdk` is REPORTED,
not skipped: an instrument that cannot run and says nothing reads exactly like
one that ran clean.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
from collections.abc import Callable

from bench.agentpii5 import payload_canaries as pc

# The boundaries a run is expected to reach when the case carries PII and a
# scripted error is driven through the gateway.
CORE: tuple[str, ...] = ("model_input", "tool_args", "model_request", "tool_error",
                         "final_answer")


def _corpus_path() -> pathlib.Path:
    return pathlib.Path(__file__).with_name("corpus.v5.json")


async def _no_pause(seconds: float) -> None:
    """The driver's retry pause, without the pause: one attempt is made and its
    curve is tested in `test_runinfo`."""
    return None


class _Double:
    """A connector double: it reads, calls one tool, and answers.

    Deliberately ignorant of benchmark objects — it talks to `GatewayHooks` the
    way an external connector does, which is what keeps this on the production
    seam instead of a test-only one."""

    async def converse(self, system: str, tools, user_indices, hooks, timeout_s: float,
                       max_calls: int):
        from bench.agentpii5.connectors import Conversation, Usage

        replies: list[str] = []
        for index in user_indices:
            hooks.user(index)
            hooks.response("")               # a provider response with no prose
            gateway = hooks.gateway
            names = [str(one["function"]["name"]) for one in gateway.tools()
                     if isinstance(one.get("function"), dict)]
            substitutes = gateway.substitutes_seen()
            if names and substitutes:
                properties = (gateway.tools()[0]["function"].get("parameters") or {}).get(
                    "properties") or {}
                key = next(iter(properties), "query")
                hooks.tool(names[0], {key: next(iter(substitutes.values()))})
            reply = "Готово: " + (next(iter(substitutes.values())) if substitutes else "ок")
            hooks.assistant(reply)
            replies.append(reply)
        return Conversation(tuple(replies), Usage(10, 0, 10, 0, 0.0, "double"),
                            len(replies), "double-session", 1)


def _drive_error(gateway, case) -> None:
    """Drive ONE unparseable call through `push_call` so `tool_error` is reached.

    The payload carries a real item value and the mock's slot tag for it, so the
    gateway MASKS it exactly as it masks a result; the manifest can then demand
    the value is hidden there. An error boundary nobody drives is the boundary
    this file exists to stop reporting clean."""
    from bench.agentpii4.mock import CallLog

    item = next((one for one in case.base.pii if one.value), None)
    if item is None:
        return
    value = str(item.value)
    text = f"Ошибка: {value} не найден"
    start = text.index(value)
    tag = "item:" + item.id
    log = CallLog(tool="canary_error", seq=9999, parsed=None, refusal=None,
                  result={"error": {"message": value}}, result_text=text,
                  result_spans={tag: (start, start + len(value))})
    gateway.push_call("canary_error", log, "error", 0, 1)


def _run(capture: bool = True):
    """One real harness intervention over the first corpus case, offline."""
    from bench.agentpii5 import harness as h
    from bench.agentpii5.mock import seed_backend_v5

    cases, _ = h._load_corpus(_corpus_path())
    case = next(one for one in cases if len(one.base.pii) > 0)
    h.load_dev_bundle()
    gateway = h.GatewayV5(case, h.Detector(), h.Vault(":memory:", "canary-integration"),
                          h.AuditLog(":memory:"), h.MaskCache(256), capture=capture)
    arms = h.ConnectedArms(_Double())
    outcome = asyncio.run(arms.intervention(case, 0, gateway, seed_backend_v5(case),
                                            "canary-double", 0.0, "canary-run"))
    _drive_error(gateway, case)
    return case, gateway, outcome


def test_the_real_run_is_clean_and_counted_per_boundary() -> list[str]:
    """Every boundary has a row, the core ones really hid something, and the
    right gateway leaks nothing."""
    problems: list[str] = []
    case, gateway, outcome = _run()
    if outcome.base.run.termination != "done":
        return [f"the double's run did not finish: {outcome.base.run.termination}"]
    report = gateway.canary_report()
    if report.status != pc.STATUS_MEASURED:
        return [f"the real run reported {report.status}: {report.reason}"]
    if not gateway.capture(0).manifest.neighbours:
        problems.append("the production manifest declares no ordinary neighbours")
    if report.neighbour_damage:
        problems.append(f"the gateway damaged ordinary neighbours: {report.neighbour_damage}")
    rows = report.by_boundary()
    for name in pc.CAPTURE_BOUNDARIES:
        if name not in rows:
            problems.append(f"{name}: no row — an unreached boundary reads as a clean one")
    for name in CORE:
        if rows.get(name, {}).get("hidden", 0) <= 0:
            problems.append(f"{name}: nothing was hidden there, so the boundary measured "
                            f"nothing ({rows.get(name)})")
    for leak in report.leaks:
        problems.append(f"{leak.canary_id} leaked on {leak.boundary} "
                        f"[{leak.miss_class}] {leak.surface!r}")
    if report.unreached:
        problems.append(f"the run never reached {list(report.unreached)}")
    return problems


def test_each_boundary_mutant_reds_only_itself() -> list[str]:
    """THE HALF THAT MAKES THE OTHER HALF MEAN ANYTHING: put the real value back
    at ONE boundary and that boundary, and only it, must red."""
    problems: list[str] = []
    case, gateway, outcome = _run()
    baseline = gateway.canary_report()
    captured = gateway.captured_payloads()
    evidence = gateway.evidence()
    for name in CORE:
        if not any(one.name == name for one in captured):
            problems.append(f"{name}: the harness delivered no such boundary, so its mutant "
                            f"would measure nothing")
            continue
        found = pc.scan(gateway._manifest, pc.mutant_capture(captured, name), evidence)
        reds = {one.boundary for one in found.leaks}
        if name not in reds:
            problems.append(f"{name}: the real value went unreported "
                            f"(reds={sorted(reds)}, baseline_hidden="
                            f"{baseline.by_boundary().get(name, {}).get('hidden')})")
        stray = reds - {name}
        if stray:
            problems.append(f"{name}: reddened {sorted(stray)} as well — a scan that cannot "
                            f"localise the leak cannot direct a fix")
    return problems


def test_removing_the_capture_hook_unmeasures_every_boundary() -> list[str]:
    """THE MUTATION THAT UNSHIPS THE HOOK.

    A file that passes with `capture=False` is measuring its own fixture, not the
    harness. This asserts the INVERSE direction: with the hook removed nothing is
    delivered, so the core boundaries must report nothing hidden — i.e. the
    check above would be red — proving the counts come from the harness."""
    case, gateway, outcome = _run(capture=False)
    report = gateway.canary_report()
    measured = [name for name in CORE
                if report.by_boundary().get(name, {}).get("hidden", 0) > 0]
    if measured:
        return [f"capture=False still measured {measured} — the counts do not come from the "
                f"harness hook, so the hook is not what the instrument reads"]
    return []


def test_the_real_runner_persists_and_reads_back_its_bytes() -> list[str]:
    """S02 CAPTURE — THE PRODUCTION RUNNER PERSISTS ITS BYTES AND A READER FINDS THEM.

    THE DEFECT THIS PINS. `run_triple_v5` built `GatewayV5(..., MaskCache(256))` —
    `capture` defaulted to `False` and no manifest was passed — so even a paid run
    wrote nothing a canary could scan, and `check_run` could only REBUILD
    `model_input` from the run's detector-derived `mentions`, never building the
    composed `model_request` at all. This test drives the real triple
    (`run_triple_v5` → `drive_v5`'s writer) with a connector double in place of
    the provider, then reads the run directory back through the public reader —
    never through `run.mentions`, which is the reconstruction that was refused.

    THREE THINGS ARE ASSERTED, and each one can fail:
      * the artifact carries the EXACT bytes per case/repeat/boundary, the composed
        `model_request` among them;
      * a mutation of ONE boundary's persisted bytes reds that boundary and no
        other — a scan that could not localise it could not direct a fix;
      * a run whose artifact is absent stays NOT_MEASURED even with a manifest
        planted beside it, and a run that carries the artifact but loses the
        manifest does too.
    """
    import tempfile

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp) / "v5-canary-capture"
        run_dir.mkdir()
        case, gateway, outcome = _run()
        capture = gateway.capture(0)
        if capture.manifest is None:
            problems.append("the gateway captures no manifest — the row cannot be measured")
        if not capture.delivered:
            problems.append("the gateway issued no capture at all")
        pc.append_capture(run_dir, "canary-capture", capture)
        if not (run_dir / pc.capture_name("canary-capture")).exists():
            return problems + ["the writer produced no artifact"]
        report = pc.check_run(run_dir)
        if report.status != pc.STATUS_MEASURED:
            return problems + [f"the persisted run did not measure: {report.reason!r}"]
        rows = report.by_boundary()
        for name in CORE:
            if name not in rows:
                problems.append(f"{name}: no row in the read-back")
            elif rows[name]["hidden"] <= 0:
                problems.append(f"{name}: nothing hidden after the read-back ({rows[name]})")
        if pc.CAPTURE_BOUNDARIES[0] in rows and "model_request" not in rows:
            problems.append("the composed model_request boundary did not survive the artifact")
        if report.leaks:
            problems.append(f"the read-back invented leaks: {report.leaks}")
        # --- the mutation: one boundary's real bytes put back -----------------
        row = pc.read_captures(run_dir)[0]
        mutated = pc.RunCapture(case_id=row.case_id, repeat=row.repeat, arm=row.arm,
                                manifest=row.manifest,
                                delivered=pc.mutant_capture(row.delivered, "model_request"))
        (run_dir / pc.capture_name("canary-capture")).unlink()
        pc.append_capture(run_dir, "canary-capture", mutated)
        reds = pc.check_run(run_dir)
        if {one.boundary for one in reds.leaks} != {"model_request"}:
            problems.append(f"a model_request mutation reddened "
                            f"{sorted({one.boundary for one in reds.leaks})}, expected only "
                            f"model_request")
        # --- the negations ----------------------------------------------------
        (run_dir / pc.capture_name("canary-capture")).unlink()
        (run_dir / pc.MANIFEST_ARTIFACT).write_text(
            json.dumps(pc.manifest_to_json(capture.manifest), ensure_ascii=False), encoding="utf-8")
        without = pc.check_run(run_dir)
        if without.status != pc.STATUS_NOT_MEASURED:
            problems.append(f"a planted manifest with no capture measured as {without.status!r}")
        if not without.reason or pc.CAPTURE_SUFFIX not in without.reason:
            problems.append(f"the refusal does not name the artifact: {without.reason!r}")
        pc.append_capture(run_dir, "canary-capture", pc.RunCapture(
            case_id=row.case_id, repeat=row.repeat, arm=row.arm,
            manifest=pc.CanaryManifest(canaries=()), delivered=row.delivered))
        (run_dir / pc.MANIFEST_ARTIFACT).write_text(
            '{"version": 999, "manifest": {"canaries": []}}', encoding="utf-8")
        future = pc.check_run(run_dir)
        if future.status != pc.STATUS_NOT_MEASURED:
            problems.append(f"a future manifest version was accepted: {future.status!r}")
    return problems


def test_the_real_runner_writes_the_capture_through_the_writer() -> list[str]:
    """S02 CAPTURE — THE LIVE PATH, NOT ONLY THE GATEWAY'S OWN METHOD.

    `test_the_real_runner_persists_and_reads_back_its_bytes` proves the reader
    over an artifact the TEST wrote. This one proves the WRITER is on the live
    path: a real `run_triple_v5` over a one-case corpus, driven by the scripted
    connector, must leave the artifact in the run directory with a row per
    (case, repeat) — the branch `drive_v5` gained when `TripleResult` grew
    `captures`. A seam that exists only in the test is the seam the reviewer
    found unshipped.

    The judge is switched OFF (`config=None`): a verdict is not what is being
    measured, and asking a model would put a provider call inside a harness test.
    """
    import asyncio
    import tempfile

    from bench.agentpii3.live import judge as v3_judge
    from bench.agentpii5 import harness as h

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp) / "v5-live-canary"
        run_dir.mkdir()
        cases, digest = h._load_corpus(_corpus_path())
        case = next((one for one in cases if len(one.base.pii) > 0), None)
        if case is None:
            return ["the corpus holds no case with PII — the writer test is vacuous"]
        h.write_corpus(run_dir, [case], digest)
        ledger = v3_judge.SpendLedger(h.r.run_file(run_dir, "canary-writer", "<run>.spend.tsv"),
                                      5.0)
        runner = h.triple_runner(h.Detector(), ledger, None, "canary-double", "canary-writer",
                                 h.ConnectedArms(_Double()))
        result = asyncio.run(h.drive_v5([case], 1, runner, run_dir, "canary-writer", 1,
                                        frozenset(),
                                        h.DrivePolicy(attempts=1, pause=_no_pause,
                                                      jitter=lambda: 1.0,
                                                      expected_per_case_usd=0.0)))
        if result.triples and result.triples[0].get("status") == "excluded":
            return [f"the scripted triple was excluded: {result.triples[0].get('reason')!r}"]
        artifact = run_dir / pc.capture_name("canary-writer")
        if not artifact.exists():
            return problems + [f"the live run wrote no {artifact.name}"]
        rows = pc.read_captures(run_dir)
        if not rows:
            return problems + ["the live run's artifact holds no capture row"]
        if not any(one.name == "model_request" for one in rows[0].delivered):
            problems.append("the live artifact carries the per-message bytes but not the "
                            "composed model_request")
        if rows[0].case_id != case.base.id or rows[0].repeat != 0:
            problems.append(f"the row is not keyed by case and repeat: "
                            f"{rows[0].case_id!r} {rows[0].repeat!r}")
        measured = pc.check_run(run_dir)
        if measured.status != pc.STATUS_MEASURED:
            problems.append(f"the live runner saved bytes but no measurable manifest: "
                            f"{measured.reason}")
        if (not measured.coverage_known or measured.capture_rows != 1
                or measured.intervention_rows != 1 or measured.selected_rows != 1):
            problems.append("the real runner has no 1/1/1 capture denominator")
        if not rows[0].manifest.neighbours:
            problems.append("the live runner saved no ordinary neighbours")
        # THE OUTWARD FILES MUST NOT CARRY THE CORPUS. The capture is not a
        # `RUN_FILES` name, so no consumer of the contract can iterate into it.
        for name in ("<run>.triples.jsonl", "<run>.arms.v5.jsonl"):
            path = h.r.run_file(run_dir, "canary-writer", name)
            if path.exists() and "canary.jsonl" in path.read_text(encoding="utf-8"):
                problems.append(f"{name} embeds the capture artifact's name")
    return problems


def test_model_request_is_snapshotted_before_later_notes() -> list[str]:
    """A note added after the last push was never in a model request."""
    _case, gateway, _outcome = _run()
    gateway.note("AFTER-PUSH-NOTE-MUST-NOT-APPEAR")
    requests = tuple(one for one in gateway.captured_payloads()
                     if one.name == "model_request")
    if not requests:
        return ["no composed model request was captured"]
    if any("AFTER-PUSH-NOTE-MUST-NOT-APPEAR" in one.text or
           "AFTER-PUSH-NOTE-MUST-NOT-APPEAR" in one.real_text for one in requests):
        return ["model_request was recomposed from the later transcript"]
    return []


CHECKS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("the_real_run_is_clean_and_counted_per_boundary",
     test_the_real_run_is_clean_and_counted_per_boundary),
    ("each_boundary_mutant_reds_only_itself", test_each_boundary_mutant_reds_only_itself),
    ("removing_the_capture_hook_unmeasures_every_boundary",
     test_removing_the_capture_hook_unmeasures_every_boundary),
    ("the_real_runner_persists_and_reads_back_its_bytes",
     test_the_real_runner_persists_and_reads_back_its_bytes),
    ("the_real_runner_writes_the_capture_through_the_writer",
     test_the_real_runner_writes_the_capture_through_the_writer),
    ("model_request_is_snapshotted_before_later_notes",
     test_model_request_is_snapshotted_before_later_notes),
)


def main() -> int:
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError as error:
        print(f"payload_canary_integration: CANNOT RUN — the harness needs claude_agent_sdk "
              f"({error}); an instrument that cannot run must not read as clean")
        return 2
    failures: list[str] = []
    for name, check in CHECKS:
        try:
            problems = check()
        except Exception as error:  # noqa: BLE001 — a raised check is a red check
            problems = [f"raised {type(error).__name__}: {error}"]
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("payload_canary_integration: PASS" if not failures
          else "payload_canary_integration: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
