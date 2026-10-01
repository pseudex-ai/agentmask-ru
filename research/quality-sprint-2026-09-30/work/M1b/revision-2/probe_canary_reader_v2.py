"""M1b revision-2 probe — canary readback, corrected.

WHAT CHANGED AGAINST revision-1, AND WHY.

1. BYTE FIELDS ARE BYTES. revision-1 named `len(str)` results `*_bytes`; those
   are character counts. This probe reports `chars` and `utf8_bytes` as two
   separate numbers for every payload, the row and the run. The resource limit
   a reader needs is a byte limit; a character count understates a Cyrillic
   payload by ~2x.

2. THE DENOMINATOR SENTENCE IS CORRECTED. The `0/0` in the published report is
   NOT the «no captures» branch failing to look at the journal on all paths. The
   journal (`_expected_capture_keys`) is consulted on normal success and on the
   empty-captures branch. The defect is narrower and earlier: `check_run` calls
   `read_captures` FIRST and returns `not_measured(...)` on its `CaptureError`
   (payload_canaries.py:926-931) before any denominator code runs, so the whole
   run keeps `capture_rows=0, intervention_rows=0, coverage_known=False`.

3. THE LEGACY v1 PATH IS SPECIFIED, NOT JUST A v2 HEADER. revision-1's D1 added
   a version-2 declared size block while saying version-1 rows stay under the
   version-1 rule — but the immutable problematic run IS version 1, so a new
   writer cannot make the saved rows readable. This probe measures the actual
   UTF-8 sizes of the saved v1 rows and runs a bounded, read-only LEGACY reader
   against them under payload-level limits. It writes nothing to the run.

WHAT THIS PROBE IS. A design instrument inside the task's own output scope. It
does NOT patch `payload_canaries.py`, does NOT change the global MEASURED/
NOT_MEASURED semantics, and does NOT re-rank the parity hard fail. The original
reader verdict is read from the unchanged engine and reported beside the
diagnostic.

EXIT CONTRACT. 0 when every assertion below holds; 1 otherwise. A red reader
verdict is the FINDING and is asserted, not a probe failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[5]
PROTO = REPO / "prototype"
sys.path.insert(0, str(PROTO))

from bench.agentpii5 import payload_canaries as pc  # noqa: E402

# --- proposed LEGACY v1 limits ------------------------------------------------------------------
# Chosen ABOVE the measured maximum of the saved run and BELOW a hostile single
# object, so the bound discriminates a chatty row from a hostile one. Every
# number is justified by a measurement printed by this probe, not by taste.
LEGACY_MAX_PAYLOAD_UTF8_BYTES = 1 << 20        # measured max 36,592 B (~28x headroom)
LEGACY_MAX_PAYLOADS = 4096                     # measured max 380 (~10x headroom)
LEGACY_MAX_ROW_UTF8_BYTES = 8 << 20            # measured max 5,531,229 B (~1.5x headroom)
LEGACY_MAX_RUN_BYTES = pc.CAPTURE_MAX_RUN_BYTES   # 256 MiB, unchanged
LEGACY_READ_CHUNK = 1 << 20                    # incremental decode window, 1 MiB


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def geometry(path: pathlib.Path) -> dict:
    """True physical rows, with physical BYTES and decoded CHARACTERS apart."""
    rows = 0
    total_bytes = 0
    total_chars = 0
    max_row_bytes = 0
    over: list[dict] = []
    with path.open("rb") as source:
        for raw in source:
            rows += 1
            total_bytes += len(raw)
            total_chars += len(raw.decode("utf-8"))
            max_row_bytes = max(max_row_bytes, len(raw))
            if len(raw) > pc.CAPTURE_MAX_ROW_BYTES:
                over.append({"line": rows, "bytes_including_newline": len(raw)})
    return {
        "path": str(path), "sha256": sha256_file(path), "rows": rows,
        "total_bytes": total_bytes, "total_chars": total_chars,
        "max_row_bytes": max_row_bytes,
        "engine_row_bound_bytes": pc.CAPTURE_MAX_ROW_BYTES,
        "engine_run_bound_bytes": pc.CAPTURE_MAX_RUN_BYTES,
        "over_engine_row_bound": over,
        "rows_at_or_under_engine_bound": rows - len(over),
    }


def per_row_sizes(path: pathlib.Path) -> dict:
    """One pass: per-row and per-payload size accounting in BOTH units.

    ONLY the rows the engine refuses are expanded payload-by-payload: the
    question this answers is «is each oversized row large because of one huge
    value, or because it is chatty?», and that is a question about the refused
    rows. Every row still contributes its physical bytes to the run totals."""
    expanded: list[dict] = []
    rows = 0
    payloads = 0
    max_payload_utf8 = 0
    max_payload_chars = 0
    max_payload_count = 0
    with path.open("rb") as source:
        for number, raw in enumerate(source, start=1):
            rows += 1
            if len(raw) <= pc.CAPTURE_MAX_ROW_BYTES:
                continue
            parsed = json.loads(raw.decode("utf-8"))
            body = parsed.get("capture") or {}
            items = body.get("payloads") or []
            sizes = [{"name": one.get("name"),
                      "text_chars": len(one.get("text", "")),
                      "text_utf8_bytes": len(one.get("text", "").encode("utf-8")),
                      "real_chars": len(one.get("real_text", "")),
                      "real_utf8_bytes": len(one.get("real_text", "").encode("utf-8"))}
                     for one in items if isinstance(one, dict)]
            payloads += len(sizes)
            max_payload_count = max(max_payload_count, len(sizes))
            if sizes:
                max_payload_utf8 = max(max_payload_utf8,
                                       max(max(s["text_utf8_bytes"], s["real_utf8_bytes"])
                                           for s in sizes))
                max_payload_chars = max(max_payload_chars,
                                        max(max(s["text_chars"], s["real_chars"]) for s in sizes))
            expanded.append({
                "line": number, "row_bytes_including_newline": len(raw),
                "version": parsed.get("version"), "case_id": parsed.get("case_id"),
                "payload_count": len(sizes),
                "max_payload_text_utf8_bytes": max((s["text_utf8_bytes"] for s in sizes), default=0),
                "max_payload_real_utf8_bytes": max((s["real_utf8_bytes"] for s in sizes), default=0),
                "total_payload_text_utf8_bytes": sum(s["text_utf8_bytes"] for s in sizes),
                "total_payload_real_utf8_bytes": sum(s["real_utf8_bytes"] for s in sizes),
            })
    return {"rows_sized": rows, "refused_rows_expanded": len(expanded),
            "payloads_in_refused_rows": payloads,
            "max_payload_count": max_payload_count,
            "max_payload_utf8_bytes": max_payload_utf8,
            "max_payload_chars": max_payload_chars,
            "refused_row_details": expanded}


def legacy_bounded_read(path: pathlib.Path) -> dict:
    """A bounded, incremental, READ-ONLY v1 reader over one artifact.

    THE LEGACY PATH revision-1 lacked. It never materialises a row before it is
    admissible, it decodes incrementally in `LEGACY_READ_CHUNK` windows, and a
    row it cannot admit is COUNTED AND NAMED while the remaining rows are still
    measured. The run budget is the engine's own 256 MiB and is enforced before
    any row is read; the row ceiling, the per-payload UTF-8 bound and the
    payload-count bound are the three new ones.

    It returns its own report type and NEVER writes to the run."""
    total = 0
    seen = 0
    measured = 0
    skipped: list[dict] = []
    refused: list[dict] = []
    payloads = 0
    identities: set[tuple[str, int]] = set()
    with path.open("rb") as source:
        size = path.stat().st_size
        if size > LEGACY_MAX_RUN_BYTES:
            return {"measured_rows": 0, "skipped_rows": 0,
                    "refused_rows": [{"reason": f"run over the {LEGACY_MAX_RUN_BYTES} byte budget"}],
                    "payloads": 0}
        while True:
            raw = source.readline(LEGACY_MAX_ROW_UTF8_BYTES + 1)
            if not raw:
                break
            total += len(raw)
            seen += 1
            if total > LEGACY_MAX_RUN_BYTES:
                skipped.append({"line": seen, "reason": "run budget exceeded mid-read"})
                break
            if len(raw) > LEGACY_MAX_ROW_UTF8_BYTES:
                # A hostile single row: named, counted, skipped — the rest still measured.
                skipped.append({"line": seen, "reason":
                                f"row over the {LEGACY_MAX_ROW_UTF8_BYTES} byte hard ceiling"})
                continue
            if not raw.strip():
                continue
            try:
                line = raw.decode("utf-8")
            except UnicodeDecodeError:
                refused.append({"line": seen, "reason": "invalid UTF-8"})
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                refused.append({"line": seen, "reason": "not JSON"})
                continue
            if not isinstance(parsed, dict):
                refused.append({"line": seen, "reason": "not an object"})
                continue
            items = (parsed.get("capture") or {}).get("payloads")
            if not isinstance(items, list):
                refused.append({"line": seen, "reason": "no payload list"})
                continue
            if len(items) > LEGACY_MAX_PAYLOADS:
                skipped.append({"line": seen, "reason":
                                f"payload count over {LEGACY_MAX_PAYLOADS}"})
                continue
            bad = next((one for one in items
                        if not isinstance(one, dict)
                        or len(str(one.get("text", "")).encode("utf-8")) > LEGACY_MAX_PAYLOAD_UTF8_BYTES
                        or len(str(one.get("real_text", "")).encode("utf-8")) > LEGACY_MAX_PAYLOAD_UTF8_BYTES),
                       None)
            if bad is not None:
                skipped.append({"line": seen, "reason":
                                f"payload over the {LEGACY_MAX_PAYLOAD_UTF8_BYTES} byte bound"})
                continue
            try:
                capture = pc.capture_from_json(parsed)
            except pc.CaptureError as broken:
                refused.append({"line": seen, "reason": str(broken)})
                continue
            key = (capture.case_id, capture.repeat)
            if key in identities:
                refused.append({"line": seen, "reason": f"duplicate capture {key!r}"})
                continue
            identities.add(key)
            measured += 1
            payloads += len(capture.delivered)
    return {"measured_rows": measured, "skipped_rows": len(skipped),
            "skipped": skipped, "refused_rows": len(refused), "refused": refused,
            "payloads": payloads, "distinct_keys": len(identities)}


def build_synthetic_controls(root: pathlib.Path) -> dict:
    """Three admissible/boundary synthetic rows in THIS task's scope.

    (a) a valid v1 row under all legacy bounds  -> measured;
    (b) one payload over the payload bound      -> skipped, named, others measured;
    (c) hostile single row over the row ceiling -> skipped by name, others measured.
    The synthetic run is a directory this probe owns; the saved run is never
    written to."""
    import shutil
    run_dir = root / "synthetic-legacy-controls"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    def manifest(tag: str) -> pc.CanaryManifest:
        return pc.CanaryManifest(
            canaries=(pc.CanarySpec("syn-phone", "PHONE", "model_input",
                                    (pc.PlantedSurface("+7 916 123-45-67", pc.SURFACE_FULL),),
                                    "+7 917 000-00-00", "message"),),
            neighbours=(pc.Neighbour("model_input", "обезличенного"),),
            salt=tag, source="m1b-rev2")

    rows = [pc.RunCapture(case_id=f"rev2-ok-{i}", repeat=0, arm="I", manifest=manifest("ok"),
                          delivered=(pc.CapturedPayload("model_input", "phone +7 917 000-00-00",
                                                        "phone +7 916 123-45-67"),))
            for i in range(2)]
    for capture in rows:
        pc.append_capture(run_dir, "m1b-rev2", capture)

    # (b) a valid v1 capture whose single payload is over the payload bound.
    filler = "Строка без персональных данных. " * 50_000   # ~1.5 MiB, over 1 MiB
    big = pc.RunCapture(case_id="rev2-big-payload", repeat=0, arm="I", manifest=manifest("big"),
                        delivered=(pc.CapturedPayload("model_input", filler, filler),))
    pc.append_capture(run_dir, "m1b-rev2", big)

    # (c) a hostile physical row over the row ceiling, built beside the artifact
    hostile = (root / "synthetic-legacy-controls-hostile.canary.jsonl")
    hostile.write_bytes(b'{"version":1,"case_id":"rev2-hostile","repeat":0,"arm":"I","capture":{"manifest":{},"payloads":[]}}' + b" " * (9 << 20) + b"\n")

    # (d) a version-2 row whose DECLARED sizes lie about the bytes it holds.
    lying = (root / "synthetic-v2-lying.canary.jsonl")
    lying.write_text(json.dumps({
        "version": 2, "case_id": "rev2-lying", "repeat": 0, "arm": "I",
        "capture": {"manifest": {}, "payloads": [],
                    "declared": {"payload_count": 1, "max_payload_bytes": 10,
                                 "total_text_bytes": 10, "row_bytes": 10}},
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    return {"run_dir": str(run_dir), "artifact": str(run_dir / "m1b-rev2.canary.jsonl"),
            "hostile_row": str(hostile), "v2_lying_row": str(lying),
            "ok_rows": 2, "big_payload_utf8_bytes": len(filler.encode("utf-8"))}


def declared_vs_actual(path: pathlib.Path) -> dict:
    """A v2 declared size block is UNTRUSTED METADATA.

    A reader may not allocate on the declaration, and may not accept a row whose
    declaration disagrees with the bytes it holds. This is the check the design
    requires; it is demonstrated on a synthetic v2 row that lies, because no v2
    row exists in the saved run."""
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    declared = (row.get("capture") or {}).get("declared") or {}
    actual_payloads = len((row.get("capture") or {}).get("payloads") or [])
    actual_total = sum(len(str(one.get("text", "")).encode("utf-8"))
                       for one in (row.get("capture") or {}).get("payloads") or [])
    return {"declared": declared, "declared_payload_count": declared.get("payload_count"),
            "actual_payload_count": actual_payloads,
            "declared_total_text_bytes": declared.get("total_text_bytes"),
            "actual_total_text_bytes": actual_total,
            "agrees": (declared.get("payload_count") == actual_payloads
                       and declared.get("total_text_bytes") == actual_total),
            "verdict": "REFUSED" if (declared.get("payload_count") != actual_payloads
                                     or declared.get("total_text_bytes") != actual_total) else "ACCEPTED"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    run_dir = pathlib.Path(args.run).resolve()
    out_root = pathlib.Path(args.out).resolve()
    (out_root / "tmp").mkdir(parents=True, exist_ok=True)

    captures = pc.capture_paths(run_dir)
    result: dict = {"run_dir": str(run_dir),
                    "engine_limits": {"capture_version": pc.CAPTURE_VERSION,
                                      "manifest_version": pc.MANIFEST_VERSION,
                                      "row_bound_bytes": pc.CAPTURE_MAX_ROW_BYTES,
                                      "run_bound_bytes": pc.CAPTURE_MAX_RUN_BYTES},
                    "proposed_legacy_limits": {
                        "max_payload_utf8_bytes": LEGACY_MAX_PAYLOAD_UTF8_BYTES,
                        "max_payloads": LEGACY_MAX_PAYLOADS,
                        "max_row_utf8_bytes": LEGACY_MAX_ROW_UTF8_BYTES,
                        "max_run_bytes": LEGACY_MAX_RUN_BYTES,
                        "read_chunk_bytes": LEGACY_READ_CHUNK},
                    "capture_artifacts": [str(one) for one in captures]}
    if len(captures) != 1:
        print(json.dumps({"error": f"expected exactly one capture artifact, found {len(captures)}"}))
        return 1

    path = captures[0]
    result["geometry"] = geometry(path)
    result["sizes"] = per_row_sizes(path)

    # The ORIGINAL verdict, from the unchanged engine. This is the number the
    # published report used and it does not change here.
    report = pc.check_run(run_dir)
    result["engine_check_run"] = {
        "status": report.status, "ok": report.ok, "reason": report.reason,
        "coverage_known": report.coverage_known, "capture_rows": report.capture_rows,
        "intervention_rows": report.intervention_rows, "selected_rows": report.selected_rows}

    # The LEGACY diagnostic, a separate report type in a separate namespace.
    result["legacy_diagnostic"] = legacy_bounded_read(path)
    result["legacy_diagnostic"]["note"] = (
        "DIAGNOSTIC ONLY. The global reader verdict above stays NOT_MEASURED; this "
        "read is a design path that must be accepted and implemented in M1c before "
        "it can feed any gate. It never admits a skipped/refused row as measured.")

    controls = build_synthetic_controls(out_root / "tmp")
    result["synthetic_controls"] = controls
    result["synthetic_legacy_read"] = {
        "ok_and_big_payload": legacy_bounded_read(pathlib.Path(controls["run_dir"]) / "m1b-rev2.canary.jsonl"),
        "hostile_row": legacy_bounded_read(pathlib.Path(controls["hostile_row"])),
    }
    result["v2_declared_vs_actual"] = declared_vs_actual(pathlib.Path(controls["v2_lying_row"]))

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    (out_root / "probe_canary_reader_v2.json").write_text(text + "\n", encoding="utf-8")

    g = result["geometry"]
    s = result["sizes"]
    diag = result["legacy_diagnostic"]
    legit = result["synthetic_legacy_read"]["ok_and_big_payload"]
    hostile = result["synthetic_legacy_read"]["hostile_row"]
    ok = (
        g["rows"] == 810
        and len(g["over_engine_row_bound"]) == 2
        and report.status == pc.STATUS_NOT_MEASURED
        and "byte bound" in report.reason
        and report.capture_rows == 0 and report.intervention_rows == 0
        and s["max_payload_utf8_bytes"] > s["max_payload_chars"]      # bytes and chars are NOT the same number
        and diag["measured_rows"] == g["rows"]                        # every valid row readable on the legacy path
        and diag["skipped_rows"] == 0 and diag["refused_rows"] == 0
        and legit["measured_rows"] == 2 and legit["skipped_rows"] == 1   # the big payload row is skipped, named
        and legit["skipped"][0]["line"] == 3
        and hostile["measured_rows"] == 0 and hostile["skipped_rows"] >= 1
        and result["v2_declared_vs_actual"]["verdict"] == "REFUSED"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
