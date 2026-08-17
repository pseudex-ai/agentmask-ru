"""Gate P3: the compiled image must detect EXACTLY what the source tree detects.

"It starts and answers 200" is not what packaging has to prove. Nuitka rewrites
the program; the risk is a subtly different one — a regex flag lost, a dictionary
not bundled, a docstring-dependent code path stripped by `--python-flag=
no_docstrings`. So the whole detection suite is re-run THROUGH HTTP against a
running container, and the numbers are compared to the source run digit for
digit.

Detection is read through `/spans`, which returns offsets and types but never the
matched value — so the value is recovered from the caller's own text via the
offsets. That is a real property being exercised, not a workaround: offsets are
guaranteed to index into the ORIGINAL text because normalization is 1:1, and the
UI depends on exactly that.

usage:
    python3 e2e/parity.py http://127.0.0.1:18000 --out source.json
    python3 e2e/parity.py http://127.0.0.1:18000 --out compiled.json
    python3 e2e/parity.py --compare source.json compiled.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

import httpx

from e2e.gates import gateway_headers

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from e2e import fixtures  # noqa: E402
from eval_dirty import _f2, _match, _val_match  # noqa: E402
from test_coverage_152fz import _MUST_CATCH, _MUST_NOT_MASK  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

# The SCORING helpers borrowed from eval_dirty compare values semantically, which
# means folding homoglyphs — so they call `normalize()`, which needs the leased
# look-alike table. This harness runs OUTSIDE the container, so it loads a bundle
# of its own purely to score with.
#
# It changes nothing about what is under test: every detection here comes from
# the container over HTTP. The local bundle never touches it.
load_dev_bundle()

_ORG = "parity"
_BATCH = 40
_TYPES = ["NAME", "PHONE", "EMAIL", "SNILS", "INN", "CARD", "PASSPORT", "DATE", "LOC"]


def detect_many(base_url: str, texts: list[str]) -> list[list[tuple[str, str]]]:
    """(type, value) per text, through the running container."""
    out: list[list[tuple[str, str]]] = []
    for start in range(0, len(texts), _BATCH):
        chunk = texts[start:start + _BATCH]
        response = httpx.post(f"{base_url}/spans", timeout=300,
                              headers=gateway_headers(),
                              json={"org_id": _ORG, "texts": chunk})
        response.raise_for_status()
        for text, spans in zip(chunk, response.json()["results"]):
            out.append([(span["type"], text[span["start"]:span["end"]]) for span in spans])
    return out


def coverage(base_url: str) -> dict[str, object]:
    """The 152-ФЗ checklist, both directions."""
    catch_texts = [text for text, _ in _MUST_CATCH]
    results = detect_many(base_url, catch_texts)
    missed = [
        f"{expected}: {text}"
        for (text, expected), spans in zip(_MUST_CATCH, results)
        if expected not in [entity_type for entity_type, _ in spans]
    ]
    over_results = detect_many(base_url, list(_MUST_NOT_MASK))
    over = [f"{text} -> {spans}" for text, spans in zip(_MUST_NOT_MASK, over_results) if spans]
    return {"types_checked": len(_MUST_CATCH), "missed": missed,
            "lookalikes_checked": len(_MUST_NOT_MASK), "over_masked": over}


def dirty(base_url: str, path: Path) -> dict[str, object]:
    """The dirty-set eval, computed exactly as eval_dirty.py computes it."""
    cases = json.loads(path.read_text(encoding="utf-8"))
    predictions = detect_many(base_url, [case["text"] for case in cases])

    gt = {t: 0 for t in _TYPES}
    found = {t: 0 for t in _TYPES}
    det = {t: 0 for t in _TYPES}
    cor = {t: 0 for t in _TYPES}
    true_leaks = 0
    neg_total = neg_fp = 0

    for case, preds in zip(cases, predictions):
        gold = [(entity["type"], entity["value"]) for entity in case["entities"]]
        pred_vals = [value for _, value in preds]
        for g_type, g_val in gold:
            gt[g_type] = gt.get(g_type, 0) + 1
            if any(_match(g_type, g_val, p_type, p_val) for p_type, p_val in preds):
                found[g_type] += 1
            if not any(_val_match(g_val, value) for value in pred_vals):
                true_leaks += 1
        for p_type, p_val in preds:
            if p_type in det:
                det[p_type] += 1
                if any(_match(p_type, p_val, g_type, g_val) for g_type, g_val in gold):
                    cor[p_type] += 1
        for negative in case["negatives"]:
            neg_total += 1
            neg_norm = re.sub(r"\D", "", negative) or negative.lower()
            for _, value in preds:
                normalized = re.sub(r"\D", "", value) or value.lower()
                if neg_norm and (neg_norm in normalized or normalized in neg_norm):
                    neg_fp += 1
                    break

    total_gt = sum(gt.values())
    total_found = sum(found.values())
    total_det = sum(det.values())
    total_cor = sum(cor.values())
    recall = total_found / total_gt if total_gt else 0.0
    precision = total_cor / total_det if total_det else 0.0
    return {
        "cases": len(cases),
        "gt": total_gt,
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f2": round(_f2(recall, precision), 4),
        "type_aware_miss": total_gt - total_found,
        "hard_negative_false_mask": neg_fp,
        "hard_negatives": neg_total,
        "true_leaks": true_leaks,
        "per_type": {t: {"gt": gt[t], "found": found[t], "det": det[t], "cor": cor[t]}
                     for t in _TYPES},
    }


def roundtrip(base_url: str) -> dict[str, object]:
    """The tool-call loop: what the tool receives must be the original value."""
    masked = httpx.post(f"{base_url}/mask", timeout=300,
                        headers=gateway_headers(),
                        json=fixtures.mask_body(_ORG)).json()
    content = masked["messages"][0]["content"]
    leaked = [v for v in fixtures.PII_PAYLOAD.values() if v in content]
    restored = httpx.post(f"{base_url}/unmask", timeout=120,
                          headers=gateway_headers(), json={
        "org_id": _ORG, "response": {"choices": [{"message": {"content": content}}]},
    }).json()["response"]["choices"][0]["message"]["content"]
    return {
        "leaked_to_model": leaked,
        "restored": sorted(k for k, v in fixtures.PII_PAYLOAD.items() if v in restored),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", nargs="?", default="")
    parser.add_argument("--dirty", type=Path, default=Path("dirty.json"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--compare", nargs=2, type=Path, default=None)
    args = parser.parse_args()

    if args.compare:
        left = json.loads(args.compare[0].read_text())
        right = json.loads(args.compare[1].read_text())
        same = left == right
        print(json.dumps({"identical": same}, indent=2))
        if not same:
            for key in sorted(set(left) | set(right)):
                if left.get(key) != right.get(key):
                    print(f"  DIFFERS {key}:\n    {args.compare[0].name}: {left.get(key)}\n"
                          f"    {args.compare[1].name}: {right.get(key)}")
        raise SystemExit(0 if same else 1)

    if not args.base_url:
        raise SystemExit(__doc__)
    report = {
        "coverage": coverage(args.base_url),
        "dirty": dirty(args.base_url, args.dirty) if args.dirty.exists() else {"skipped": True},
        "roundtrip": roundtrip(args.base_url),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
