"""Detection eval on the DIRTY dataset — per-type recall/precision/F2, plus a
dump of the actual false positives and false negatives so fixes are data-driven,
not guesswork. Also the hard-negative false-mask rate.
"""

import json
import re
import sys

from pseudex.detect_all import Detector
from pseudex.normalize import normalize
from testkit import load_dev_bundle

_NUMERIC = {"PHONE", "SNILS", "INN", "CARD", "PASSPORT", "DATE"}


def _norm(entity_type: str, value: str) -> str:
    value = normalize(value)  # compare semantically (homoglyph «О»->0)
    if entity_type in _NUMERIC:
        return re.sub(r"\D", "", value)
    return value.strip().lower()


def _match(a_type: str, a_val: str, b_type: str, b_val: str) -> bool:
    if a_type != b_type:
        return False
    a, b = _norm(a_type, a_val), _norm(b_type, b_val)
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def _val_match(a: str, b: str) -> bool:
    """Type-agnostic value match — was this PII value masked by ANY entity type?"""
    na = re.sub(r"[^0-9a-zа-яё]", "", normalize(a).lower())
    nb = re.sub(r"[^0-9a-zа-яё]", "", normalize(b).lower())
    return len(na) >= 2 and len(nb) >= 2 and (na in nb or nb in na)


def _f2(recall: float, precision: float) -> float:
    if recall == 0 and precision == 0:
        return 0.0
    return 5 * precision * recall / (4 * precision + recall)


def main() -> None:
    load_dev_bundle()
    path = sys.argv[1] if len(sys.argv) > 1 else "dirty.json"
    print(f"dataset: {path}")
    with open(path, encoding="utf-8") as handle:
        cases = json.load(handle)

    detector = Detector()
    types = ["NAME", "PHONE", "EMAIL", "SNILS", "INN", "CARD", "PASSPORT", "DATE", "LOC"]
    gt = {t: 0 for t in types}
    found = {t: 0 for t in types}
    det = {t: 0 for t in types}
    cor = {t: 0 for t in types}
    false_pos: list[str] = []
    true_leaks: list[str] = []
    neg_total = 0
    neg_fp = 0
    quasi_total = 0
    quasi_cov = 0

    for case in cases:
        gold = [(e["type"], e["value"]) for e in case["entities"]]
        preds = [(s.entity_type, s.value) for s in detector.detect(case["text"])]
        pred_vals = [p_val for _, p_val in preds]
        for g_type, g_val in gold:
            gt[g_type] = gt.get(g_type, 0) + 1
            if any(_match(g_type, g_val, p_type, p_val) for p_type, p_val in preds):
                found[g_type] += 1
            if not any(_val_match(g_val, pv) for pv in pred_vals):  # value-level (real leak)
                true_leaks.append(f"{g_type}: {g_val!r}  in: {case['text'][:55]!r}")
        for quasi in case.get("quasi", []):
            quasi_total += 1
            if any(_val_match(quasi["value"], pv) for pv in pred_vals):
                quasi_cov += 1
        for p_type, p_val in preds:
            if p_type in det:
                det[p_type] += 1
                if any(_match(p_type, p_val, g_type, g_val) for g_type, g_val in gold):
                    cor[p_type] += 1
                else:
                    false_pos.append(f"{p_type}: {p_val!r}  in: {case['text'][:60]!r}")
        for neg in case["negatives"]:
            neg_total += 1
            neg_norm = re.sub(r"\D", "", neg) or neg.lower()
            for _, p_val in preds:
                pv = re.sub(r"\D", "", p_val) or p_val.lower()
                if neg_norm and (neg_norm in pv or pv in neg_norm):
                    neg_fp += 1
                    break

    print(f"{'TYPE':<10}{'GT':>5}{'RECALL':>8}{'PREC':>7}{'F2':>7}")
    tgt = tfound = tdet = tcor = 0
    for t in types:
        if gt[t] == 0 and det[t] == 0:
            continue
        rec = found[t] / gt[t] if gt[t] else 0.0
        pre = cor[t] / det[t] if det[t] else 0.0
        print(f"{t:<10}{gt[t]:>5}{rec:>7.0%}{pre:>7.0%}{_f2(rec, pre):>7.0%}")
        tgt += gt[t]; tfound += found[t]; tdet += det[t]; tcor += cor[t]
    rec = tfound / tgt; pre = tcor / tdet if tdet else 0
    print("-" * 37)
    print(f"{'OVERALL':<10}{tgt:>5}{rec:>7.0%}{pre:>7.0%}{_f2(rec, pre):>7.0%}")
    print(f"type-aware miss: {tgt - tfound}/{tgt} | HARD-NEG false-mask: {neg_fp}/{neg_total}")
    print(f"TRUE-LEAK (value not masked by ANY type): {len(true_leaks)}/{tgt}")
    if quasi_total:
        print(f"QUASI-IDENTIFIERS caught: {quasi_cov}/{quasi_total}  (known gap)")

    print("\n--- TRUE LEAKS (PII value actually reached the model) ---")
    for line in true_leaks[:20]:
        print(" ", line)
    print("\n--- FALSE POSITIVES (over-masked) ---")
    for line in false_pos[:12]:
        print(" ", line)
    return rec, pre, len(true_leaks), neg_fp


# SEEDED AT 13, so these 150 values and 12 hard negatives are the same set
# everywhere. Three floors rather than one, because they fail differently: a
# true leak is a value that reached the model, a false mask on a hard negative
# is data we invented, and recall/precision are the summary that hides both.
_FLOOR = 1.0


def gate() -> int:
    recall, precision, leaks, false_masks = main()
    problems = []
    if recall < _FLOOR or precision < _FLOOR:
        problems.append(f"полнота {recall:.1%}, точность {precision:.1%}, нужно {_FLOOR:.0%}")
    if leaks:
        problems.append(f"{leaks} значений дошли до модели открытым текстом")
    if false_masks:
        problems.append(f"{false_masks} ложных масок на жёстких негативах")
    if problems:
        print("\nПОРОГ НЕ ВЗЯТ: " + "; ".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(gate())
