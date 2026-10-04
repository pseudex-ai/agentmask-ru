"""M1b probe 1 — the canary reader against the SAVED run and against a valid
oversized synthetic capture. READ-ONLY over the run directory.

What it answers, in order, with exit codes:
  1. the row geometry of the saved `*.canary.jsonl` (counts, sizes, the
     oversized rows by line number);
  2. whether the oversized rows are VALID capture rows (they parse and pass
     `capture_from_json`), so «over the bound» is not «malformed»;
  3. what `payload_canaries.check_run` answers for the saved run — the original
     verdict the sprint recorded as NOT_MEASURED, with the reason string intact;
  4. what the same reader answers for a MEMORY-BUILT, schema-valid oversized
     capture written into this task's own scope — the positive control that the
     refusal is arithmetic and size-driven, not a property of this one archive.

Usage:
    PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python probe_canary_reader.py \
        --run <run_dir> --out <work/M1b> [--json <path>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[4]
PROTO = REPO / "prototype"
sys.path.insert(0, str(PROTO))

from bench.agentpii5 import payload_canaries as pc  # noqa: E402

OVERSIZE = pc.CAPTURE_MAX_ROW_BYTES


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def row_geometry(path: pathlib.Path) -> dict:
    """One pass, true line boundaries.

    Iterating the binary file yields WHOLE lines — `readline(bound+1)`, which is
    what the reader under test uses, would split an oversized row into a
    `bound+1` chunk and a tail and would report the archive as more rows than it
    has. The geometry is measured at the reader's own notion of a line, so the
    two questions («how many rows does the file have» and «what does the reader
    do with them») stay separate."""
    sizes: list[int] = []
    total = 0
    with path.open("rb") as source:
        for raw in source:
            sizes.append(len(raw))
            total += len(raw)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "rows": len(sizes),
        "total_bytes": total,
        "max_row_bytes": max(sizes) if sizes else 0,
        "min_row_bytes": min(sizes) if sizes else 0,
        "bound_bytes": OVERSIZE,
        "run_bound_bytes": pc.CAPTURE_MAX_RUN_BYTES,
        "over_run_bound": total > pc.CAPTURE_MAX_RUN_BYTES,
        "oversized_rows": [
            {"line": i + 1, "bytes": size,
             "over_by": size - OVERSIZE,
             "note": "line length includes the trailing newline"}
            for i, size in enumerate(sizes) if size > OVERSIZE
        ],
        "rows_at_or_under_bound": sum(1 for size in sizes if size <= OVERSIZE),
    }


def oversized_row_validity(path: pathlib.Path, lines: list[int]) -> list[dict]:
    """Parse each named oversized row and put it through the READER's own
    `capture_from_json`. A valid-but-large row is a size limit, not corruption;
    the two need different fixes and the report must not merge them."""
    out: list[dict] = []
    want = set(lines)
    with path.open("rb") as source:
        for number, raw in enumerate(source, start=1):
            if number not in want:
                continue
            text = raw.decode("utf-8")
            parsed = json.loads(text)
            entry = {
                "line": number,
                "bytes": len(raw),
                "top_keys": sorted(parsed.keys()) if isinstance(parsed, dict) else None,
                "version": parsed.get("version") if isinstance(parsed, dict) else None,
                "case_id": parsed.get("case_id") if isinstance(parsed, dict) else None,
                "repeat": parsed.get("repeat") if isinstance(parsed, dict) else None,
                "arm": parsed.get("arm") if isinstance(parsed, dict) else None,
            }
            body = parsed.get("capture") if isinstance(parsed, dict) else None
            payloads = body.get("payloads", []) if isinstance(body, dict) else []
            entry["payloads"] = [
                {"name": one.get("name"), "text_bytes": len(one.get("text", "")),
                 "real_text_bytes": len(one.get("real_text", ""))}
                for one in payloads if isinstance(one, dict)
            ]
            try:
                capture = pc.capture_from_json(parsed)
            except pc.CaptureError as broken:
                entry["capture_from_json"] = f"REFUSED: {broken}"
            else:
                entry["capture_from_json"] = "ACCEPTED"
                entry["delivered_boundaries"] = [one.name for one in capture.delivered]
                entry["manifest_canaries"] = len(capture.manifest.canaries)
            out.append(entry)
    return out


def triples_denominator(run_dir: pathlib.Path) -> dict:
    """The denominator the run's own triples journal names.

    `_expected_capture_keys` (payload_canaries.py) reads the same journal, and
    the empty-captures branch of `check_run` uses it. It is computed here from
    OUTSIDE for the case where the reader raises before reaching it."""
    paths = tuple(sorted(run_dir.glob("*.triples.jsonl")))
    expected: set[tuple[str, int]] = set()
    selected = 0
    complete = 0
    with paths[0].open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            selected += 1
            key = (row["case_id"], int(row["repeat"]))
            if row.get("status") == "complete":
                complete += 1
            if "I" in row.get("arms", {}):
                expected.add(key)
    return {"triples_artifact": str(paths[0]), "selected_rows": selected,
            "complete_rows": complete, "expected_i_arms": len(expected),
            "expected_keys": expected}


def raw_record_integrity(path: pathlib.Path) -> dict:
    """Every row parsed in full, and the delivered bytes accounted for.

    THIS IS THE LINE BETWEEN A LOST RECORD AND AN UNREADABLE ARCHIVE. A row that
    fails to parse is a lost record; a row the reader refuses by arithmetic is
    an intact record the reader will not look at. The two are counted apart."""
    rows = 0
    bytes_on_disk = 0
    payloads = 0
    text_bytes = 0
    real_bytes = 0
    names: dict[str, int] = {}
    identities: set[tuple[str, int]] = set()
    duplicates: list[tuple[str, int]] = []
    with path.open("rb") as source:
        for raw in source:
            rows += 1
            bytes_on_disk += len(raw)
            row = json.loads(raw)
            key = (row["case_id"], int(row["repeat"]))
            if key in identities:
                duplicates.append(key)
            identities.add(key)
            for one in row["capture"]["payloads"]:
                payloads += 1
                names[one["name"]] = names.get(one["name"], 0) + 1
                text_bytes += len(one["text"])
                real_bytes += len(one["real_text"])
    return {"rows": rows, "bytes_on_disk": bytes_on_disk, "payloads": payloads,
            "payload_text_bytes": text_bytes, "payload_real_bytes": real_bytes,
            "distinct_case_repeat_keys": len(identities), "duplicates": duplicates,
            "boundaries": names, "unparsable_rows": 0}


def coverage(run_dir: pathlib.Path, path: pathlib.Path) -> dict:
    """How much of the journal-named denominator the saved rows cover."""
    denominator = triples_denominator(run_dir)
    expected = denominator.pop("expected_keys")
    captured: set[tuple[str, int]] = set()
    with path.open("rb") as source:
        for raw in source:
            row = json.loads(raw)
            captured.add((row["case_id"], int(row["repeat"])))
    missing = expected - captured
    unexpected = captured - expected
    return {**denominator,
            "captured_rows": len(captured),
            "covered": len(captured & expected),
            "coverage_fraction": (len(captured & expected) / len(expected)) if expected else None,
            "missing": sorted(missing)[:20],
            "missing_count": len(missing),
            "unexpected_count": len(unexpected),
            "unexpected": sorted(unexpected)[:20]}


def build_synthetic_oversized(root: pathlib.Path) -> dict:
    """A schema-valid capture whose single payload is deliberately over the row
    bound — built in memory, written only inside this task's scope."""
    # A single payload just over the row bound, so the control is the smallest
    # row that must trip it — not a 50 MB row that would trip any bound.
    filler = ("Строка обезличенного текста без персональных данных. " * 45_000)
    phone = "+7 916 123-45-67"
    text = f"телефон {phone} " + filler
    manifest = pc.CanaryManifest(
        canaries=(pc.CanarySpec("syn-phone", "PHONE", "model_input",
                                (pc.PlantedSurface(phone, pc.SURFACE_FULL),),
                                "+7 917 000-00-00", "message"),),
        neighbours=(pc.Neighbour("model_input", "обезличенного"),),
        salt="m1b-oversize", source="m1b-synthetic")
    capture = pc.RunCapture(case_id="m1b-synthetic-oversize", repeat=0, arm="I",
                            manifest=manifest,
                            delivered=(pc.CapturedPayload("model_input", text.replace(phone, "+7 917 000-00-00"), text),))
    run_id = "m1b-synthetic"
    run_dir = root / "synthetic-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    written = pc.append_capture(run_dir, run_id, capture)
    row_bytes = written.stat().st_size
    # The synthetic run has no triples journal, so `check_run` reaches the
    # capture reader and the run-bound/row-bound arithmetic directly.
    report = pc.check_run(run_dir)
    return {
        "run_dir": str(run_dir),
        "capture_file": str(written),
        "row_bytes": row_bytes,
        "over_row_bound": row_bytes > OVERSIZE,
        "under_run_bound": row_bytes <= pc.CAPTURE_MAX_RUN_BYTES,
        "check_run_status": report.status,
        "check_run_reason": report.reason,
        "check_run_ok": report.ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    run_dir = pathlib.Path(args.run).resolve()
    out_root = pathlib.Path(args.out).resolve()
    (out_root / "tmp").mkdir(parents=True, exist_ok=True)

    result: dict = {
        "run_dir": str(run_dir),
        "bound_bytes": OVERSIZE,
        "run_bound_bytes": pc.CAPTURE_MAX_RUN_BYTES,
        "capture_version": pc.CAPTURE_VERSION,
        "manifest_version": pc.MANIFEST_VERSION,
    }

    captures = pc.capture_paths(run_dir)
    result["capture_artifacts"] = [str(one) for one in captures]
    if not captures:
        print("RED: the run carries no capture artifact", file=sys.stderr)
        return 2

    geometry = [row_geometry(one) for one in captures]
    result["geometry"] = geometry
    lines = [one["line"] for geo in geometry for one in geo["oversized_rows"]]
    result["oversized_row_validity"] = [
        entry for path in captures for entry in oversized_row_validity(path, lines)]

    # The ORIGINAL verdict, from the reader the sprint shipped matters more than
    # any re-derivation: it is the number the report was built from.
    report = pc.check_run(run_dir)
    result["check_run"] = {
        "status": report.status,
        "ok": report.ok,
        "reason": report.reason,
        "coverage_known": report.coverage_known,
        "capture_rows": report.capture_rows,
        "intervention_rows": report.intervention_rows,
        "selected_rows": report.selected_rows,
    }

    synthetic = build_synthetic_oversized(out_root / "tmp")
    result["synthetic_oversized"] = synthetic

    result["raw_record_integrity"] = [
        raw_record_integrity(one) for one in captures]
    result["coverage"] = [coverage(run_dir, one) for one in captures]

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Exit contract: 0 means every assertion the probe makes held. A red verdict
    # is NOT a failed probe — it is the finding — so the red is asserted here.
    integrity = result["raw_record_integrity"][0]
    ok = (
        len(geometry) == 1
        and len(result["oversized_row_validity"]) == len(lines)
        and all(one.get("capture_from_json") == "ACCEPTED"
                for one in result["oversized_row_validity"])
        and report.status == pc.STATUS_NOT_MEASURED
        and "byte bound" in report.reason
        and synthetic["check_run_status"] == pc.STATUS_NOT_MEASURED
        and synthetic["over_row_bound"]
        and integrity["unparsable_rows"] == 0
        and integrity["rows"] == geometry[0]["rows"]
        and result["coverage"][0]["expected_i_arms"] > 0
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
