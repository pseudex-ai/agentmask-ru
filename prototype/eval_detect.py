"""Statistical eval: run the integrated detector over the golden set and report
per-entity-type recall and precision against ground truth.
"""

import json
import re

from pseudex.detect_all import Detector
from testkit import load_dev_bundle

_NUMERIC = {"PHONE", "SNILS", "INN", "CARD", "PASSPORT", "DATE"}


def _norm(entity_type: str, value: str) -> str:
    if entity_type in _NUMERIC:
        return re.sub(r"\D", "", value)
    return value.strip().lower()


def _match(a_type: str, a_val: str, b_type: str, b_val: str) -> bool:
    if a_type != b_type:
        return False
    a, b = _norm(a_type, a_val), _norm(b_type, b_val)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def main() -> None:
    load_dev_bundle()
    with open("dataset.json", encoding="utf-8") as handle:
        cases = json.load(handle)

    detector = Detector()
    types = ["NAME", "PHONE", "EMAIL", "SNILS", "INN", "CARD", "PASSPORT", "DATE", "LOC"]
    gt_total = {t: 0 for t in types}
    found = {t: 0 for t in types}
    detected = {t: 0 for t in types}
    correct = {t: 0 for t in types}

    for case in cases:
        gold = [(e["type"], e["value"]) for e in case["entities"]]
        preds = [(s.entity_type, s.value) for s in detector.detect(case["text"])]
        for g_type, g_val in gold:
            gt_total[g_type] = gt_total.get(g_type, 0) + 1
            if any(_match(g_type, g_val, p_type, p_val) for p_type, p_val in preds):
                found[g_type] += 1
        for p_type, p_val in preds:
            if p_type not in detected:
                continue
            detected[p_type] += 1
            if any(_match(p_type, p_val, g_type, g_val) for g_type, g_val in gold):
                correct[p_type] += 1

    print(f"{'TYPE':<10}{'GT':>5}{'RECALL':>9}{'PREC':>9}")
    tot_gt = tot_found = tot_det = tot_corr = 0
    for t in types:
        if gt_total[t] == 0 and detected[t] == 0:
            continue
        recall = found[t] / gt_total[t] if gt_total[t] else 0.0
        prec = correct[t] / detected[t] if detected[t] else 0.0
        print(f"{t:<10}{gt_total[t]:>5}{recall:>8.0%}{prec:>9.0%}")
        tot_gt += gt_total[t]; tot_found += found[t]
        tot_det += detected[t]; tot_corr += correct[t]
    print("-" * 33)
    print(f"{'OVERALL':<10}{tot_gt:>5}{tot_found / tot_gt:>8.0%}{tot_corr / tot_det:>9.0%}")
    print(f"\nRecall is the privacy metric: {tot_gt - tot_found} of {tot_gt} PII items were MISSED (would leak).")


if __name__ == "__main__":
    main()
