"""Detection-only sweep: run the ACTUAL engine over the corpus's message-level PII.

FREE (no model, no network): loads the dev bundle, runs `Detector.detect` on every
message, and scores the message-level gold PII (base.pii where.kind == "message").
Prints per-type recall/coverage/precision with x/n. This is the G7 detection sweep
on the corpus, NOT the agent 3-arm run.

Run (from prototype/):  .venv/bin/python bench/agentpii5/detect_sweep.py [corpus.v5.json ...]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def load_frame(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    corpus = d["corpus"] if isinstance(d, dict) and "corpus" in d else d
    return corpus


def match(gtype, gval, ptype, pval):
    if gtype != ptype:
        return False
    return gval == pval or gval in pval or pval in gval


def sweep(corpus, detector, label):
    # per type: gt, found (recall), whole (coverage), typed_correct, typed_total
    gt = defaultdict(int)
    found = defaultdict(int)
    whole = defaultdict(int)
    typed_correct = defaultdict(int)
    typed_total = defaultdict(int)
    for c in corpus:
        msgs = c["base"].get("messages", [])
        preds_cache = {}
        for e in c["base"].get("pii", []):
            w = e.get("where", {})
            if w.get("kind") != "message":
                continue
            mi = w.get("msg", -1)
            if not (0 <= mi < len(msgs)):
                continue
            gtype = e["type"]; gval = e["value"]
            gt[gtype] += 1
            if mi not in preds_cache:
                preds_cache[mi] = [(s.entity_type, s.value) for s in detector.detect(msgs[mi]["content"])]
            preds = preds_cache[mi]
            # recall: any same-type pred overlaps the gold value
            hit = any(match(gtype, gval, p, v) for p, v in preds)
            if hit:
                found[gtype] += 1
                whole[gtype] += 1
            else:
                # coverage: any pred (any type) overlaps
                anyhit = any(gval in v or v in gval for _, v in preds)
                if anyhit:
                    whole[gtype] += 1
        # precision: typed preds vs gold
        for mi, preds in preds_cache.items():
            txt = msgs[mi]["content"]
            for p, v in preds:
                if p not in gt:
                    continue
                typed_total[p] += 1
                if any(match(p, v, e["type"], e["value"])
                       for e in c["base"].get("pii", [])
                       if e.get("where", {}).get("msg") == mi):
                    typed_correct[p] += 1
    print(f"\n=== {label} ===")
    print(f"{'TYPE':<14}{'GT':>5}{'recall':>10}{'whole':>10}{'prec':>10}")
    for t in sorted(gt):
        r = found[t] / gt[t] if gt[t] else 0
        wh = whole[t] / gt[t] if gt[t] else 0
        pr = typed_correct[t] / typed_total[t] if typed_total[t] else 0
        print(f"{t:<14}{gt[t]:>5}{r:>9.1%}{wh:>9.1%}{pr:>9.1%}  ({found[t]}/{gt[t]} r, {typed_correct[t]}/{typed_total[t]} p)")
    tot_gt = sum(gt.values()); tot_f = sum(found.values()); tot_w = sum(whole.values())
    tot_tc = sum(typed_correct.values()); tot_tt = sum(typed_total.values())
    print(f"{'OVERALL':<14}{tot_gt:>5}{tot_f/tot_gt:>9.1%}{tot_w/tot_gt:>9.1%}{tot_tc/tot_tt:>9.1%}  ({tot_f}/{tot_gt} r, {tot_tc}/{tot_tt} p)")
    return tot_gt, tot_f, tot_w


def main():
    from testkit import load_dev_bundle
    load_dev_bundle()
    from pseudex.detect_all import Detector
    d = Detector()
    paths = sys.argv[1:] or ["bench/agentpii5/corpus.v5.json",
                            "bench/agentpii5/v6/corpus.v5.json"]
    for p in paths:
        path = Path(p)
        if not path.exists():
            print(f"skip (missing): {path}")
            continue
        corpus = load_frame(path)
        print(f"\n{'='*60}\n{path}: {len(corpus)} cases")
        sweep(corpus, d, path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
