"""Offline report round-trip and refusal to overwrite an existing artifact.

The causal section is pinned beside the historical and actual ones: three
estimators in one file, each labelled, and the historical lines still read as
SCHEDULED hops rather than being silently absorbed by the new estimator.
"""

import json
import sys
import tempfile
from pathlib import Path

from bench.agentpii5.causal_hops import ESTIMATOR_VERSION as CAUSAL_VERSION
from bench.agentpii5.cohort import SourceSpec
from bench.agentpii5.hop_report import REPORT_VERSION, source_spec, write_report
from bench.agentpii5.test_cohort import CASES_A, PROVIDER_12000, SOURCE_A, _cases, _write_source


def main() -> int:
    assert not any(name == "pseudex" or name.startswith("pseudex.") for name in sys.modules)
    with tempfile.TemporaryDirectory() as directory:
        root: Path = Path(directory)
        source: Path = _write_source(root, SOURCE_A, _cases(CASES_A), PROVIDER_12000, 5.0)
        output: Path = root / "report"
        spec: SourceSpec = source_spec(f"A={source}")
        report = write_report((spec,), output)
        assert not any(name == "pseudex" or name.startswith("pseudex.") for name in sys.modules), \
            "The offline report imported the engine it is supposed to measure independently"
        assert report.runs == 2
        payload = json.loads((output / "report.json").read_text())
        assert payload["report_version"] == REPORT_VERSION
        assert payload["actual"]["estimator"] == report.estimator
        assert len(payload["historical"]) == 13
        assert "actual_hops.py" in payload["scorer_sha256"]
        # THE CAUSAL BLOCK IS SERIALIZED, SEPARATE AND VERSIONED.
        causal = payload["causal"]
        assert causal["estimator"] == CAUSAL_VERSION
        assert causal["runs"] == report.runs
        # Every event is a candidate: `not_applicable` is an emission that was
        # never made, so it can never silently enlarge a denominator.
        assert causal["overall"]["candidates"] == causal["events_total"]
        assert {"overall", "by_surface", "by_owner"} <= set(causal)
        assert {"attributed", "ambiguous", "unattributed", "not_identifiable", "user_provided"} \
            <= {name for name, _count in causal["overall"]["statuses"]}
        for line in causal["by_surface"]:
            assert line["tool_causal"] <= line["candidates"]
            assert line["joint_ok"] <= line["attributed"] <= line["tool_causal"] + line["user_provided"]
        assert "causal_hops.py" in payload["scorer_sha256"]
        manifest = json.loads((output / "manifest.json").read_text())
        assert manifest
        events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
        assert len(events) == report.events_total
        assert len({(event["case_id"], event["repeat"], event["event_id"]) for event in events}) == len(events)
        summary = (output / "summary.md").read_text()
        assert "NOT an engine improvement" in summary
        # THE HISTORICAL LINES KEEP THEIR OWN LABEL BESIDE THE CAUSAL ONES.
        assert "Historical estimator (SCHEDULED hops" in summary
        assert "Actual causal hops (recorded chronology" in summary
        assert f"causal: `{CAUSAL_VERSION}`" in summary
        assert "not_identifiable" in summary
        before: bytes = (output / "report.json").read_bytes()
        try:
            write_report((spec,), output)
        except FileExistsError:
            pass
        else:
            raise AssertionError("An existing report was silently overwritten")
        assert (output / "report.json").read_bytes() == before
    print("hop_report: PASS (offline, manifest, events, historical + causal lines, "
          "immutable output)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
