"""S2 semantic-PII observation probe — READ-ONLY on the pinned engine.

Purpose: turn the S2 gap inventory from a reading exercise into measured facts
about the UNCHANGED engine at pinned revision 0bfda236 (research only; this
probe is not a RED for a patch and changes no engine file).

For every synthetic episode in EPISODES.jsonl it records:
  * what the current pipeline detects (type + surface),
  * the masked text the model would see,
  * the round-trip mask->unmask result,
  * whether the numeric value of a semantic attribute (salary/debt) survived
    in the clear,
  * whether the substitute is a FAITHFUL value/marker for the attribute.

Environment: prototype/.venv/bin/python, cwd=prototype, PYTHONDONTWRITEBYTECODE=1.
Ephemeral in-memory vault only; no provider, no network, no writes outside S2.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
S2 = os.path.dirname(HERE)
PROTO = "/Users/igor/Projects/Obscura-hop-audit/prototype"

for path in (PROTO, S2):
    if path not in sys.path:
        sys.path.insert(0, path)

from testkit import load_dev_bundle  # noqa: E402

load_dev_bundle()  # without it every detect() raises BundleNotLeased by design

from pseudex.detect_all import Detector  # noqa: E402
from pseudex.redact import mask_text, unmask_text  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

EPISODES = os.path.join(S2, "EPISODES.jsonl")


def load_episodes() -> list[dict]:
    rows = []
    with open(EPISODES, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def digits_of(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def run() -> dict:
    detector = Detector()
    results = []
    for episode in load_episodes():
        text = episode["text"]
        spans = detector.detect(text)
        span_rows = [
            {"type": s.entity_type, "surface": text[s.start:s.end],
             "start": s.start, "end": s.end}
            for s in spans
        ]
        vault = Vault(":memory:", "s2-synthetic").for_conversation(episode["id"])
        masked = mask_text(text, vault, spans)
        restored = unmask_text(masked, vault)
        value_digits = digits_of(text)
        value_survives = bool(value_digits) and value_digits in digits_of(masked)
        results.append({
            "id": episode["id"],
            "dimension": episode["dimension"],
            "pair_role": episode["pair_role"],
            "form": episode["form"],
            "subject_present": episode["subject_present"],
            "text": text,
            "spans": span_rows,
            "types": sorted({s.entity_type for s in spans}),
            "span_count": len(span_rows),
            "masked": masked,
            "masked_changed": masked != text,
            "restored": restored,
            "roundtrip_identical": restored == text,
            "attribute_digits_present": bool(value_digits),
            "attribute_digits_survive_masked": value_survives,
            "redaction_marker_visible": "REDACTED" in masked,
        })
    return {
        "engine_revision_expected": "0bfda2363ef1a1d552e2ac093129b1026a86ad68",
        "harness": "work/S2/probes/semantic_probe.py",
        "fixture": "work/S2/EPISODES.jsonl",
        "episodes": results,
        "counts": {
            "episodes": len(results),
            "any_span": sum(1 for r in results if r["span_count"]),
            "no_span": sum(1 for r in results if not r["span_count"]),
            "masked_changed": sum(1 for r in results if r["masked_changed"]),
            "roundtrip_identical": sum(1 for r in results if r["roundtrip_identical"]),
            "redaction_marker_visible": sum(1 for r in results if r["redaction_marker_visible"]),
        },
    }


if __name__ == "__main__":
    payload = run()
    out = os.path.join(HERE, "semantic_probe.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    for row in payload["episodes"]:
        spans = ", ".join(f'{s["type"]}={s["surface"]!r}' for s in row["spans"]) or "-"
        print(f'[{row["id"]}] {row["text"]}')
        print(f'    spans: {spans}')
        print(f'    masked->{row["masked"]!r}')
        print(f'    roundtrip_identical={row["roundtrip_identical"]} '
              f'digits_survive={row["attribute_digits_survive_masked"]} '
              f'marker={row["redaction_marker_visible"]}')
    print("COUNTS " + json.dumps(payload["counts"], sort_keys=True))
    print(f"WROTE {out}")
