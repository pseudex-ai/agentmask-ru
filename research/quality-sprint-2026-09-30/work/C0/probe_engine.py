"""C0 — engine-facing RED probe against the PINNED UNCHANGED build.

WHAT THIS IS
------------
A read-only executable probe that (a) re-derives the typed-KV / SECRET / priority
facts at the pinned source hashes, and (b) runs the REAL detector (development
bundle loaded in-process, `testkit.load_dev_bundle()`) over the synthetic
fixtures from `gen_fixtures.py`, and reports each EXPECTED PROPERTY separately.

HOW TO READ THE RESULT
----------------------
This is a DESIGN/RED wave against a build that has no temporary-secret class at
all. The REDs below are INTENTIONAL, expected failing properties, not a broken
test suite and not an engine regression. `suite_verdict` therefore reads
`NOT_A_SUITE_PASS`; a RED here is the reproduced property the future patch must
turn GREEN (G4), and it must never be reported as "suite PASS".

NO WRITES OUTSIDE THIS DIRECTORY. No mint, no vault, no store, no network, no
lease server, no provider call. `load_dev_bundle()` builds the bundle in memory.

Run:
    cd prototype
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
      ../research/quality-sprint-2026-09-30/work/C0/probe_engine.py --out <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("/Users/igor/Projects/Obscura-hop-audit")
PROTOTYPE = REPO / "prototype"
sys.path.insert(0, str(PROTOTYPE))

# The bundle MUST be loaded before anything detects: without it the detector
# raises BundleNotLeased by design (CLAUDE.md, "Commands").
from testkit import load_dev_bundle  # noqa: E402

load_dev_bundle()

from pseudex.detect_all import Detector                      # noqa: E402
from pseudex.structured import _FORM_KV, _JSON_KV, _key_type  # noqa: E402
from pseudex.vault import _card_length, _render_token        # noqa: E402
from pseudex.assets import CompositeType, StructuredAssets    # noqa: E402
import licensing.assets_source as A                          # noqa: E402

FIXTURES = json.loads((HERE / "FIXTURES.json").read_text(encoding="utf-8"))["fixtures"]


def build_structured() -> StructuredAssets:
    """Exactly what `licensing/pack.py` ships and `assets._build_structured`
    rebuilds: key_type as an ORDERED list of pairs (a tuple of stems, because
    `_key_type` walks it in order), composites as the role map."""
    key_stems = tuple((str(k), str(v)) for k, v in A.KEY_TYPE.items())
    composites: dict[str, CompositeType] = {}
    for entity_type, spec in A.COMPOSITE_TYPES.items():
        roles = {word: role for role, words in spec["roles"].items() for word in words}
        composites[str(entity_type)] = CompositeType(
            roles=roles,
            order=tuple(str(r) for r in spec["order"]),
            lengths={str(r): int(n) for r, n in spec["lengths"].items()},
            required=tuple(str(r) for r in spec["required"]),
        )
    return StructuredAssets(key_type=dict(key_stems), key_stems=key_stems,
                            composites=composites)


def spans_of(det: Detector, text: str) -> list[dict]:
    return [{"type": s.entity_type, "start": s.start, "end": s.end,
             "surface": text[s.start:s.end]}
            for s in det.detect(text)]


def prop(pid: str, statement: str, observed: str, holds_now: bool,
         kind: str, fixtures: list[str], engine_change_required: bool) -> dict:
    """kind: 'RED_intentional' | 'CONTROL_must_hold'."""
    return {
        "property_id": pid,
        "statement": statement,
        "observed": observed,
        "holds_on_this_build": bool(holds_now),
        "kind": kind,
        "status": ("GREEN_as_expected" if holds_now else
                   ("RED_CONFIRMED" if kind == "RED_intentional" else "CONTROL_VIOLATED")),
        "fixtures": fixtures,
        "engine_change_required_to_close": engine_change_required,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "PROBE-FACTS.json"))
    args = ap.parse_args()

    structured = build_structured()
    det = Detector()
    report: dict = {
        "probe": "C0/probe_engine.py",
        "engine_read_only": True,
        "bundle": "development bundle built in memory via testkit.load_dev_bundle(); no file written",
        "note": "Values synthetic. REDs are EXPECTED failing properties on a build with no "
                "temporary-secret class; this is not a suite PASS.",
    }

    # --- Section 1: mechanism facts (re-derived at the pinned hashes) --------
    report["mechanism_facts"] = {
        "KEY_TYPE_entries": len(A.KEY_TYPE),
        "CTX_TYPES_entries": len(A.CTX_TYPES),
        "card_verification_keys_present_in_leased_map": [
            k for k in A.KEY_TYPE
            if any(s in str(k).lower() for s in ("cvc", "cvv", "cid", "otp", "защитн"))
        ],
        "generic_secret_keys_in_leased_map": {
            k: A.KEY_TYPE[k] for k in ("password", "passwd", "secret", "секрет", "пароль")
            if k in A.KEY_TYPE
        },
        "key_type_card_cvc": _key_type("card_cvc", structured),
        "key_type_cardcvc": _key_type("cardcvc", structured),
        "key_type_cardholder_name": _key_type("cardholder_name", structured),
        "key_type_cvc": _key_type("cvc", structured),
        "key_type_otp": _key_type("otp", structured),
        "priority_table": A.PRIORITY,
        "secret_is_top_priority": A.PRIORITY.get("SECRET") == max(A.PRIORITY.values()),
        "kv_regex_matches": {
            "json_quoted_cvc": [list(m.groups()) for m in _JSON_KV.finditer('{"cvc": "314"}')],
            "json_unquoted_cvc": [list(m.groups()) for m in _JSON_KV.finditer('{"cvc": 314}')],
            "form_cvv": [list(m.groups()) for m in _FORM_KV.finditer("CVV: 314")],
        },
        "render_fallbacks": {t: _render_token(t, original="314")
                             for t in ("CVC", "OTP", "SECRET", "OPAQUE_NOT_A_TYPE")},
        "card_renderer_for_3_digits": {
            "card_length_of_3_digits": _card_length("314"),
            "render_CARD_for_314": _render_token("CARD", original="314"),
            "note": "the CARD renderer is CSPRNG-random by design, so the sample differs on every run; "
                    "the load-bearing fact is that a 3-digit value receives a 16-digit card-shaped substitute",
        },
    }

    # --- Section 2: detection over the fixture set ---------------------------
    per_fixture = []
    for fx in FIXTURES:
        hits = spans_of(det, fx["text"])
        tgt = fx["target_value"]
        target_hits = [h for h in hits if tgt and tgt == h["surface"]] if tgt else []
        target_open = (tgt is None) or (len(target_hits) == 0)
        per_fixture.append({
            "fixture_id": fx["fixture_id"], "family": fx["family"], "kind": fx["kind"],
            "medium": fx["medium"], "text": fx["text"], "target_value": tgt,
            "spans": hits, "target_protected": bool(target_hits),
            "target_open": target_open, "red_probe_id": fx["red_probe_id"],
        })
    report["per_fixture"] = per_fixture

    def opened(fid: str) -> bool:
        return next(f["target_open"] for f in per_fixture if f["fixture_id"] == fid)

    def protected(fid: str) -> bool:
        return next(f["target_protected"] for f in per_fixture if f["fixture_id"] == fid)

    # --- Section 3: explicit expected properties ----------------------------
    cvc_props = ["POS-CVC-001", "POS-CVC-002", "POS-CVC-003", "POS-CVC-004",
                 "POS-CVC-007"]
    otp_props = ["POS-OTP-001", "POS-OTP-002", "POS-OTP-003", "POS-OTP-004"]
    negs = ["NEG-JSON-1", "NEG-JSON-2", "NEG-JSON-3", "NEG-FORM-1", "NEG-PROSE-1",
            "NEG-PROSE-2", "NEG-OTP-1", "NEG-OTP-2", "NEG-OTP-3"]

    props = [
        prop("RED-1",
             "a value under an authoritative card-verification field name/alias "
             "(cvc/cvv2/cid) is protected",
             f"{sum(protected(f) for f in cvc_props)}/{len(cvc_props)} fielded CVC positives protected",
             all(protected(f) for f in cvc_props), "RED_intentional", cvc_props, True),
        prop("RED-2",
             "a prose/form card-code field label with a colon (CVV: 314) is protected",
             f"POS-CVC-005 protected={protected('POS-CVC-005')}",
             protected("POS-CVC-005"), "RED_intentional", ["POS-CVC-005"], True),
        prop("RED-3",
             "the JSON KV regex matches the unquoted numeric form {\"cvc\": 314}",
             f"_JSON_KV matches on '{{\"cvc\": 314}}' = "
             f"{report['mechanism_facts']['kv_regex_matches']['json_unquoted_cvc']} "
             f"(quoted form does match: {report['mechanism_facts']['kv_regex_matches']['json_quoted_cvc']})",
             bool(report["mechanism_facts"]["kv_regex_matches"]["json_unquoted_cvc"]),
             "RED_intentional", ["MAL-CVC-003"], True),
        prop("RED-4",
             "a dynamic issuer one-time code (ISSUER_OTP: 3DS/SMS/one-time wording, "
             "otp field) is protected as its own class",
             f"{sum(protected(f) for f in otp_props)}/{len(otp_props)} OTP positives protected",
             all(protected(f) for f in otp_props), "RED_intentional", otp_props, True),
        prop("RED-5",
             "a malformed value under an authoritative card-code field is masked, "
             "not passed (existing OPAQUE demotion precedent)",
             f"MAL-CVC-001 open={opened('MAL-CVC-001')}, MAL-CVC-002 open={opened('MAL-CVC-002')}",
             (not opened("MAL-CVC-001")) and (not opened("MAL-CVC-002")),
             "RED_intentional", ["MAL-CVC-001", "MAL-CVC-002"], True),
        prop("RED-6",
             "one card code and one issuer OTP in one utterance are each protected "
             "with DIFFERENT classes",
             f"AMB-001 spans={next(f['spans'] for f in per_fixture if f['fixture_id'] == 'AMB-001')}",
             False, "RED_intentional", ["AMB-001"], True),
        prop("RED-7",
             "in a payload with two card objects each code is protected and bound "
             "to its own object",
             f"POS-CVC-008 spans={next(f['spans'] for f in per_fixture if f['fixture_id'] == 'POS-CVC-008')}",
             False, "RED_intentional", ["POS-CVC-008", "AMB-002"], True),
        prop("RED-8",
             "an entity type named for a card code renders a card-code-shaped "
             "substitute, never a REDACTED marker inside a numeric field",
             f"_render_token('CVC', original='314') = "
             f"{report['mechanism_facts']['render_fallbacks']['CVC']!r}",
             not str(report["mechanism_facts"]["render_fallbacks"]["CVC"]).startswith("REDACTED"),
             "RED_intentional", ["POS-CVC-001"], True),
        prop("RED-9",
             "a compound authoritative key resolves to the most specific class: "
             "the substitute never has a different LENGTH than the value it replaced",
             f"card_cvc -> {report['mechanism_facts']['key_type_card_cvc']}; "
             f"card_length('314') -> {report['mechanism_facts']['card_renderer_for_3_digits']['card_length_of_3_digits']}; "
             f"render CARD for '314' -> "
             f"{report['mechanism_facts']['card_renderer_for_3_digits']['render_CARD_for_314']!r}",
             report["mechanism_facts"]["key_type_card_cvc"] != "CARD",
             "RED_intentional", [], True),
        prop("NEG-1",
             "business/status/order numbers of the same glyph shape stay OPEN",
             f"{sum(opened(f) for f in negs)}/{len(negs)} hard negatives open",
             all(opened(f) for f in negs), "CONTROL_must_hold", negs, False),
        prop("NEG-2",
             "a bare 'код' does not license a card code",
             f"NEG-PROSE-3 open={opened('NEG-PROSE-3')}",
             opened("NEG-PROSE-3"), "CONTROL_must_hold", ["NEG-PROSE-3"], False),
    ]

    # existing-class controls: the typed-KV mechanism and the CARD class are LIVE
    ctrl_texts = {
        "CTRL-1_keyed_SECRET": '{"password": "hunter2"}',
        "CTRL-2_keyed_CARD": '{"card": "4111111111111111"}',
        "CTRL-3_bare_PAN": "4111 1111 1111 1111",
    }
    ctrl = {k: spans_of(det, v) for k, v in ctrl_texts.items()}
    report["existing_class_controls"] = ctrl
    props.append(prop("CTRL-1", "an existing keyed SECRET still types its value",
                      f"{ctrl['CTRL-1_keyed_SECRET']}",
                      any(h["type"] == "SECRET" for h in ctrl["CTRL-1_keyed_SECRET"]),
                      "CONTROL_must_hold", [], False))
    props.append(prop("CTRL-2", "the existing CARD class still types a card-shaped value",
                      f"{ctrl['CTRL-2_keyed_CARD']}",
                      any(h["type"] == "CARD" for h in ctrl["CTRL-2_keyed_CARD"]),
                      "CONTROL_must_hold", [], False))

    report["properties"] = props
    report["counts"] = {
        "fixtures_probed": len(per_fixture),
        "positive_fixtures_protected": sum(1 for f in per_fixture if f["kind"] == "positive" and f["target_protected"]),
        "positive_fixtures_total": sum(1 for f in per_fixture if f["kind"] == "positive"),
        "hard_negatives_open": sum(1 for f in per_fixture if f["kind"] == "hard_negative" and f["target_open"]),
        "hard_negatives_total": sum(1 for f in per_fixture if f["kind"] == "hard_negative"),
        "red_confirmed": sum(1 for p in props if p["status"] == "RED_CONFIRMED"),
        "red_total": sum(1 for p in props if p["kind"] == "RED_intentional"),
        "controls_held": sum(1 for p in props if p["kind"] == "CONTROL_must_hold" and p["holds_on_this_build"]),
        "controls_total": sum(1 for p in props if p["kind"] == "CONTROL_must_hold"),
    }
    report["suite_verdict"] = (
        "NOT_A_SUITE_PASS — intentional RED on a pinned unchanged build; "
        "no engine change was made by this task")
    report["not_a_defect_claim"] = (
        "The 0 detected CVC/OTP spans are expected: no recognizer claims these classes. "
        "This is a capability gap reproduced as RED, not a regression.")

    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "suite_verdict": report["suite_verdict"],
                      "properties": [{k: p[k] for k in ("property_id", "status", "observed")}
                                     for p in props]},
                     ensure_ascii=False, indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
