#!/usr/bin/env python3
"""D0 — comparable detector-mechanism experiment (isolated research harness).

WHAT THIS IS
    A reproducible, output-local harness that runs *several* detection mechanisms
    over the *same* explicit gold examples and reports, per arm and per gold type:
    exact / whole-same-type / partial-same-type / wrong-type / miss, character
    coverage, and false positives split by what they landed on (declared hard
    negative, hand-labelled "other", "place", "public", or nothing gold).

WHAT THIS IS NOT
    * It does NOT choose an architecture, rank mechanisms, or adopt anything.
      O-DETECT is an owner checkpoint (SPRINT-PLAN §7, GOAL-BRIEF §9).
    * Every arm except FULL is an ABLATION. An ablation shows what one component
      contributes to *this* gold set; it is NOT a causal claim about production
      quality, and RAW_NER is NOT proposed as a product replacement (D0 brief).
    * It does NOT touch holdout data, the paid run directory, the engine, the
      scorer, the benchmark, git, licensing, or any other work folder. It writes
      only under work/D0/out/ (or the --out you pass).
    * It reads the development bundle in memory via testkit.load_dev_bundle() —
      the documented development path. No container, no lease server, no network.

ARMS
    FULL          product path, unmodified: Detector().detect() — rules + gates +
                  Natasha news NER + address + KV + quasi, priority-resolved.
    RAW_NER       bare Natasha NewsNERTagger (PER/LOC/ORG), no engine gates,
                  no trimming, no address layer. ABLATION.
    RAW_NER_REGEX bare Natasha + the naive phone/email/long-number regexes of
                  prototype/bench/_baseline_independent.py. ABLATION.
    RULES_ONLY    product path with the Natasha layer disabled (Detector subclass
                  overriding _ner_spans). ABLATION.
    HYBRID_UNION  FULL ∪ RAW_NER — the ceiling of "just add raw NER tags".
                  ABLATION; union of two arms is not a mechanism.

GOLD (all known-diagnostic, no holdout)
    golden   prototype/dataset.json          generated golden set (make_dataset.py)
    dirty    prototype/dirty.json            dirty set + hard negatives (make_dirty.py)
    gatectx  ~/.cache/pseudex-bench/gate_candidates.json × prototype/bench/gate/labels.json
             600 hand-labelled occurrences in real speech, label classes
             person/address (must mask) vs other/place/public (must not).

USAGE
    cd prototype
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
        ../research/quality-sprint-2026-09-30/work/D0/d0_arm_compare.py \
        --out ../research/quality-sprint-2026-09-30/work/D0/out

Exits: 0 = harness ran and instrument controls passed; 2 = positive control
failed (harness could not see the detector — results are void); 3 = negative
control failed (empty text produced spans). A non-zero exit is a harness defect
report, not an engine verdict.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.metadata as md
import json
import os
import pathlib
import platform
import sys
import time

ROOT = pathlib.Path("/Users/igor/Projects/Obscura-hop-audit")
PROTO = ROOT / "prototype"
SPRINT = ROOT / "research" / "quality-sprint-2026-09-30"
B0 = SPRINT / "work" / "B0"
CACHE = pathlib.Path.home() / ".cache" / "pseudex-bench"
SITE = PROTO / ".venv" / "lib" / "python3.12" / "site-packages"

# ---------------------------------------------------------------- hashing ----

def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record_file(path: pathlib.Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False}
    return {"path": str(path), "exists": True,
            "bytes": path.stat().st_size, "sha256": sha256_file(path)}


# ------------------------------------------------------------- gold slices ---

def occurrences(text: str, value: str) -> list[tuple[int, int]]:
    """Every non-overlapping literal occurrence of a gold value in its text."""
    out, i = [], text.find(value)
    while i != -1:
        out.append((i, i + len(value)))
        i = text.find(value, i + len(value))
    return out


def load_value_slice(path: pathlib.Path, name: str) -> tuple[list[dict], dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    cases, unresolved = [], 0
    for i, row in enumerate(rows):
        text = row["text"]
        gold, negs = [], []
        for ent in row.get("entities", []):
            hits = occurrences(text, ent["value"])
            if not hits:
                unresolved += 1
                continue
            for s, e in hits:
                gold.append({"start": s, "end": e, "type": ent["type"],
                             "value": ent["value"]})
        for val in row.get("negatives", []) or []:
            for s, e in occurrences(text, val):
                negs.append({"start": s, "end": e, "value": val, "label": "declared"})
        cases.append({"id": f"{name}:{i}", "text": text, "gold": gold,
                      "negatives": negs})
    meta = {"slice": name, "file": record_file(path), "cases": len(cases),
            "unresolved_gold_values": unresolved}
    return cases, meta


def gate_key(row: dict) -> str:
    """The occurrence identity used by prototype/bench/gate/sheet.py:101."""
    raw = f"{row['word']}\t{row['start']}\t{row['text']}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# Hand-labelled occurrence classes -> what this harness counts them as.
GATE_MUST_MASK = {"person": "NAME", "address": "LOC"}
GATE_MUST_NOT = ("other", "place", "public")


def load_gate_slice(cache: pathlib.Path, labels: pathlib.Path) -> tuple[list[dict], dict]:
    occ = json.loads(cache.read_text(encoding="utf-8"))["occurrences"]
    lab = json.loads(labels.read_text(encoding="utf-8"))
    cases, unlabelled, duplicates, seen = [], 0, 0, collections.Counter()
    used_keys: set[str] = set()
    for row in occ:
        k = gate_key(row)
        label = lab.get(k)
        if not label:
            unlabelled += 1
            continue
        if k in used_keys:      # 634 labelled rows, 587 unique keys — dedupe
            duplicates += 1
            continue
        used_keys.add(k)
        span = {"start": row["start"], "end": row["end"], "value": row["word"]}
        gold, negs = [], []
        if label in GATE_MUST_MASK:
            gold = [dict(span, type=GATE_MUST_MASK[label])]
        elif label in GATE_MUST_NOT:
            negs = [dict(span, label=label)]
        else:                        # unknown label class: fail loud, never guess
            raise SystemExit(f"unknown gate label {label!r}")
        seen[label] += 1
        cases.append({"id": f"gatectx:{k}", "text": row["text"],
                      "gold": gold, "negatives": negs, "gate_label": label})
    meta = {"slice": "gatectx", "file": record_file(cache),
            "labels_file": record_file(labels), "occurrences_total": len(occ),
            "labelled_used": len(cases), "unlabelled_skipped": unlabelled,
            "duplicate_rows_skipped": duplicates,
            "label_counts": dict(seen)}
    return cases, meta


# ------------------------------------------------------------------- arms ----

def _raw_natasha(text: str, seg, ner, out: list[dict]) -> None:
    from natasha import Doc
    doc = Doc(text)
    doc.segment(seg)
    doc.tag_ner(ner)
    for sp in doc.spans:
        kind = {"PER": "NAME", "LOC": "LOC", "ORG": "ORG"}.get(sp.type)
        if kind:
            out.append({"start": sp.start, "end": sp.stop, "type": kind})


def make_arms(detector):
    """Return {arm_name: fn(text) -> [{'start','end','type'}]}."""
    from pseudex import _morph_compat  # noqa: F401  (before natasha import)
    from natasha import NewsEmbedding, NewsNERTagger, Segmenter
    import re

    seg, ner = Segmenter(), NewsNERTagger(NewsEmbedding())
    phone = re.compile(r"(?:\+7|8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}")
    email = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b")
    longnum = re.compile(r"\b\d{10,20}\b")

    def full(text):
        return [{"start": s.start, "end": s.end, "type": s.entity_type}
                for s in detector.detect(text)]

    def raw_ner(text):
        out = []
        _raw_natasha(text, seg, ner, out)
        return out

    def raw_ner_regex(text):
        out = []
        _raw_natasha(text, seg, ner, out)
        for rx, kind in ((phone, "PHONE"), (email, "EMAIL"), (longnum, "NUM")):
            for m in rx.finditer(text):
                out.append({"start": m.start(), "end": m.end(), "type": kind})
        return out

    class RulesOnly(type(detector)):
        def _ner_spans(self, text):       # explicit ablation, documented above
            return []

    rules_only_det = RulesOnly()

    def rules_only(text):
        return [{"start": s.start, "end": s.end, "type": s.entity_type}
                for s in rules_only_det.detect(text)]

    def hybrid_union(text):
        merged = full(text)[:]
        for sp in raw_ner(text):
            if not any(sp["start"] < m["end"] and m["start"] < sp["end"]
                       for m in merged):
                merged.append(sp)
        return merged

    return {"FULL": full, "RAW_NER": raw_ner, "RAW_NER_REGEX": raw_ner_regex,
            "RULES_ONLY": rules_only, "HYBRID_UNION": hybrid_union}


ABLATION_ARMS = ("RAW_NER", "RAW_NER_REGEX", "RULES_ONLY", "HYBRID_UNION")


# -------------------------------------------------------------- evaluation ---

def overlaps(a: dict, b: dict) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def contains(outer: dict, inner: dict) -> bool:
    return outer["start"] <= inner["start"] and inner["end"] <= outer["end"]


def evaluate(cases, arm_fn, memo) -> dict:
    """Outcome taxonomy per gold item + prediction FP taxonomy per arm.

    UNIT OF COUNTING. Gold items are counted once per (span, type): the gate
    instrument stores the same occurrence row twice under one label key
    (634 labelled rows, 587 unique keys), and counting rows would inflate the
    denominator. Predictions are counted ONCE PER UNIQUE TEXT: a text carries
    several labelled occurrences, and a prediction that misses one occurrence's
    gold must not be re-counted as a fresh false positive for every sibling
    occurrence in the same utterance.
    """
    grouped: "collections.OrderedDict[str, dict]" = collections.OrderedDict()
    for case in cases:
        g = grouped.setdefault(case["text"], {"gold": {}, "negatives": {}})
        for item in case["gold"]:
            g["gold"][(item["start"], item["end"], item["type"])] = item
        for n in case["negatives"]:
            g["negatives"][(n["start"], n["end"], n["label"])] = n

    per_type = collections.defaultdict(collections.Counter)
    total = collections.Counter()
    pred_types = collections.Counter()
    pred_types_matched = collections.Counter()
    started = time.perf_counter()
    n_texts = 0

    for text, grp in grouped.items():
        if text not in memo:
            memo[text] = arm_fn(text)
            n_texts += 1
        preds = memo[text]
        golds, negs = list(grp["gold"].values()), list(grp["negatives"].values())

        # --- per gold item -------------------------------------------------
        for g in golds:
            same = [p for p in preds if p["type"] == g["type"] and overlaps(p, g)]
            any_ = [p for p in preds if overlaps(p, g)]
            c = per_type[g["type"]]
            c["gold"] += 1
            total["gold"] += 1
            if any(p["type"] == g["type"] and p["start"] == g["start"]
                   and p["end"] == g["end"] for p in preds):
                outcome = "exact"
            elif any(contains(p, g) for p in same):
                outcome = "whole_same_type"
            elif same:
                outcome = "partial_same_type"
            elif any(contains(p, g) or overlaps(p, g) for p in any_):
                outcome = "wrong_type"
            else:
                outcome = "miss"
            c[outcome] += 1
            total[outcome] += 1
            if outcome == "wrong_type":
                # WHICH type the engine used instead — a typed miss is not a leak
                # but it changes substitute shape and tool semantics.
                for t in sorted({p["type"] for p in preds if overlaps(p, g)}):
                    c[f"wrongtype:{g['type']}->{t}"] += 1
                    total[f"wrongtype:{g['type']}->{t}"] += 1
            # character coverage by SAME-TYPE spans only (leaked tails matter)
            covered = set()
            for p in same:
                covered.update(range(max(p["start"], g["start"]),
                                     min(p["end"], g["end"])))
            c["gold_chars"] += g["end"] - g["start"]
            c["covered_chars"] += len(covered)
            total["gold_chars"] += g["end"] - g["start"]
            total["covered_chars"] += len(covered)

        # --- per prediction ------------------------------------------------
        for p in preds:
            pred_types[p["type"]] += 1
            total["pred"] += 1
            hit_same = any(g["type"] == p["type"] and overlaps(p, g) for g in golds)
            hit_any = any(overlaps(p, g) for g in golds)
            if hit_same:
                total["pred_typed_tp"] += 1
                pred_types_matched[p["type"]] += 1
            elif hit_any:
                total["pred_wrong_type_tp"] += 1
                pred_types_matched[p["type"]] += 1
            else:
                neg = next((n for n in negs if overlaps(p, n)), None)
                if neg is not None:
                    total[f"fp_{neg['label']}"] += 1
                else:
                    total["fp_other"] += 1
                    total[f"fp_other_type:{p['type']}"] += 1

        # --- negatives that stayed clear / got masked ----------------------
        for n in negs:
            total["negatives"] += 1
            if any(overlaps(p, n) for p in preds):
                total["negatives_masked"] += 1

    elapsed = time.perf_counter() - started
    return {"per_type": {k: dict(v) for k, v in sorted(per_type.items())},
            "totals": dict(total), "pred_type_hist": dict(pred_types),
            "pred_type_matched": dict(pred_types_matched),
            "seconds": round(elapsed, 3), "new_texts_detected": n_texts}


# ------------------------------------------------------------------- main ----

ZERO_CONTROL = ""
POSITIVE_CONTROL = "Позвоните Иванову Ивану по телефону +79261234567"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(SPRINT / "work" / "D0" / "out"))
    ap.add_argument("--max-cases", type=int, default=0,
                    help="cap per slice (0 = all); use only for quick checks")
    ap.add_argument("--arms", default=",".join(
        ("FULL", "RAW_NER", "RAW_NER_REGEX", "RULES_ONLY", "HYBRID_UNION")))
    args = ap.parse_args()
    outdir = pathlib.Path(args.out)
    if SPRINT not in outdir.resolve().parents and "D0" not in outdir.resolve().parts:
        raise SystemExit("refusing to write outside work/D0: " + str(outdir))
    outdir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(PROTO))
    from testkit import load_dev_bundle
    load_dev_bundle()                     # BEFORE any detect()
    from pseudex.detect_all import Detector
    detector = Detector()
    arms = make_arms(detector)
    wanted = [a.strip() for a in args.arms.split(",") if a.strip()]
    for a in wanted:
        if a not in arms:
            raise SystemExit(f"unknown arm {a}")

    # -------- inputs and identity ------------------------------------------
    # ALL shipped engine modules + all licensing modules (hash-pinned), plus the
    # harness-relevant dev/test/bench files. Verified against B0's 198 pins below.
    source_paths = sorted(
        str(p.relative_to(ROOT)) for p in
        list((PROTO / "pseudex").glob("*.py")) + list((PROTO / "licensing").glob("*.py")))
    source_paths += [
        "prototype/testkit.py",
        "prototype/make_dataset.py", "prototype/make_dirty.py",
        "prototype/bench/_baseline_independent.py", "prototype/bench/gate/extract.py",
        "prototype/bench/gate/sheet.py",
    ]
    sources = [record_file(ROOT / p) for p in source_paths]
    model_paths = sorted(str(p.relative_to(ROOT)) for p in [
        SITE / "natasha" / "data" / "emb" / "navec_news_v1_1B_250K_300d_100q.tar",
        SITE / "natasha" / "data" / "model" / "slovnet_ner_news_v1.tar",
        SITE / "natasha" / "data" / "model" / "slovnet_morph_news_v1.tar",
    ])
    models = [record_file(ROOT / p) for p in model_paths] + \
             [dict(record_file(p), path=str(p)) for p in [
                 SITE / "natasha" / "data" / "dict" / "first.txt",
                 SITE / "natasha" / "data" / "dict" / "last.txt"]]
    dictionary_files = [
        "prototype/licensing/data/first_names.txt",
        "prototype/licensing/data/gar_streets.tsv",
        "prototype/licensing/data/gar_types.json",
        "prototype/licensing/data/surnames.txt",
    ]
    dictionaries = [record_file(ROOT / p) for p in dictionary_files]

    from licensing.pack import build_payload, build_plaintext
    payload = build_payload()
    plaintext = build_plaintext()
    bundle = {"version": payload["version"], "bytes": len(plaintext),
              "sha256": hashlib.sha256(plaintext).hexdigest(),
              "written_to_disk": False, "org_id": "", "watermark": ""}
    b0_runtime = json.loads((B0 / "RUNTIME.json").read_text(encoding="utf-8"))
    bundle["vs_B0_RUNTIME"] = {
        "version_match": bundle["version"] == b0_runtime["bundle_version"],
        "sha256_match": bundle["sha256"] == b0_runtime["bundle_sha256"],
        "bytes_match": bundle["bytes"] == b0_runtime["bundle_bytes"]}

    b0_inputs = json.loads((B0 / "INPUTS.json").read_text(encoding="utf-8"))
    pins = {row["path"]: row["sha256"] for row in b0_inputs["sources"]}
    pin_check = {"compared": 0, "match": 0, "drift": [], "not_in_B0": []}
    for row in sources:
        rel = str(pathlib.Path(row["path"]).relative_to(ROOT))
        if rel not in pins:
            pin_check["not_in_B0"].append(rel)
            continue
        pin_check["compared"] += 1
        if row.get("sha256") == pins[rel]:
            pin_check["match"] += 1
        else:
            pin_check["drift"].append(rel)

    env = {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "PYTHONDONTWRITEBYTECODE": os.environ.get("PYTHONDONTWRITEBYTECODE"),
        "libraries": {name: _ver(name) for name in
                      ("natasha", "navec", "slovnet", "pymorphy3", "phonenumbers",
                       "numpy", "razdel", "yargy", "ipymarkup", "sqlcipher3")},
        "installed_ner_capable": _installed_ner_names(),
    }

    # -------- gold ---------------------------------------------------------
    slices = {}
    slice_meta = []
    cases, meta = load_value_slice(PROTO / "dataset.json", "golden")
    slices["golden"], _ = cases, slice_meta.append(meta)
    cases, meta = load_value_slice(PROTO / "dirty.json", "dirty")
    slices["dirty"] = cases
    slice_meta.append(meta)
    cases, meta = load_gate_slice(CACHE / "gate_candidates.json",
                                  PROTO / "bench" / "gate" / "labels.json")
    slices["gatectx"] = cases
    slice_meta.append(meta)
    if args.max_cases:
        slices = {k: v[:args.max_cases] for k, v in slices.items()}

    # -------- instrument controls -----------------------------------------
    # Warm-up FIRST: address/NER layers load lazily, and a 100 ms first call
    # would otherwise be reported as this arm's per-text cost. Timings are
    # exploratory either way (shared host, single run) — see report["limits"].
    warmup_text = "Прогрев: Иванов Иван, Тверская улица 5, +79261234567"
    warmup = {arm: len(fn(warmup_text)) for arm, fn in arms.items()}
    memo_ctl: dict = {}
    pos_spans = arms["FULL"](POSITIVE_CONTROL)
    pos_ok = len(pos_spans) >= 2
    neg_ok = all(len(arm(ZERO_CONTROL)) == 0 for arm in arms.values())
    controls = {"positive": {"text": POSITIVE_CONTROL, "spans": pos_spans,
                             "required": ">=2", "pass": pos_ok},
                "negative": {"text": "<empty>", "required": "0 spans in every arm",
                             "pass": neg_ok}}

    # -------- run ----------------------------------------------------------
    results = {"arms": {}, "instrument_controls": controls,
               "warmup_spans_per_arm": warmup}
    for arm in wanted:
        memo: dict = {}
        results["arms"][arm] = {
            "per_slice": {name: evaluate(cs, arms[arm], memo)
                          for name, cs in slices.items()},
            "is_ablation": arm in ABLATION_ARMS,
            "unique_texts": len(memo),
        }
        secs = sum(v["seconds"] for v in results["arms"][arm]["per_slice"].values())
        results["arms"][arm]["seconds_total"] = round(secs, 3)
        results["arms"][arm]["seconds_per_text"] = round(
            secs / max(1, len(memo)), 6)
        # positive control per FULL on golden, for the record
    golden_full = results["arms"].get("FULL", {}).get("per_slice", {}).get("golden")
    if golden_full:
        g = golden_full["totals"]
        controls["positive"]["golden_full_whole_recall"] = round(
            (g.get("exact", 0) + g.get("whole_same_type", 0)) / max(1, g["gold"]), 4)

    report = {
        "task": "D0",
        "harness": str(pathlib.Path(__file__).resolve()),
        "harness_sha256": sha256_file(pathlib.Path(__file__).resolve()),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope_note": ("isolated research harness; arms other than FULL are "
                       "ablations; no architecture choice, no causality claim"),
        "environment": env,
        "bundle": bundle,
        "source_pin_check_vs_B0": pin_check,
        "sources": sources,
        "models": models,
        "dictionaries": dictionaries,
        "gold_slices": slice_meta,
        "gold_files_hashed": [
            record_file(PROTO / "dataset.json"), record_file(PROTO / "dirty.json"),
            record_file(PROTO / "bench" / "gate" / "labels.json"),
            record_file(CACHE / "gate_candidates.json")],
        "holdout": {"file_present": (PROTO / "holdout.json").exists(),
                    "used": False,
                    "note": "known-diagnostic slices only; no holdout read"},
        "arms_run": wanted,
        "results": results,
        "limits": [
            "single host, possibly shared with other sprint tasks: timings are "
            "exploratory, NOT a p50/p95/RSS admission budget",
            "golden/dirty are our own generated sets; gatectx labels are ours; "
            "none of them measures real-traffic precision",
            "RAW_NER/HYBRID_UNION/RULES_ONLY are ablations on this gold, not "
            "candidate mechanisms and not evidence of a causal effect",
            "no production artifact, container, lease server or provider call",
        ],
    }

    (outdir / "arm-results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    _write_tsv(outdir / "arm-summary.tsv", report)
    (outdir / "source-hashes.json").write_text(json.dumps(
        {"sources": sources, "models": models, "dictionaries": dictionaries,
         "pin_check": pin_check, "bundle": bundle}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    _print_summary(report)
    if not controls["positive"]["pass"]:
        print("INSTRUMENT FAILURE: positive control — harness cannot see the detector")
        return 2
    if not controls["negative"]["pass"]:
        print("INSTRUMENT FAILURE: negative control — empty text produced spans")
        return 3
    return 0


def _ver(name: str) -> str:
    try:
        return md.version(name)
    except Exception:
        return "NOT_INSTALLED"


def _installed_ner_names() -> dict:
    """Which NER-capable libraries are importable HERE. Presence is not quality."""
    found = {}
    for mod, dist in (("natasha", "natasha"), ("slovnet", "slovnet"),
                      ("razdel", "razdel"), ("yargy", "yargy"),
                      ("spacy", "spacy"), ("transformers", "transformers"),
                      ("torch", "torch"), ("deeppavlov", "deeppavlov"),
                      ("stanza", "stanza"), ("flair", "flair")):
        found[mod] = {"installed": _ver(dist) != "NOT_INSTALLED"}
    return found


def _ratios(c: dict) -> dict:
    n = max(1, c.get("gold", 0))
    chars = max(1, c.get("gold_chars", 0))
    preds = max(1, c.get("pred", 0))
    whole = c.get("exact", 0) + c.get("whole_same_type", 0)
    return {
        "exact": c.get("exact", 0) / n,
        "whole_same_type": whole / n,
        "overlap_any_same_type": (whole + c.get("partial_same_type", 0)) / n,
        "wrong_type": c.get("wrong_type", 0) / n,
        "miss": c.get("miss", 0) / n,
        "char_coverage_same_type": c.get("covered_chars", 0) / chars,
        "pred_typed_ppv": c.get("pred_typed_tp", 0) / preds,
        "fp_other": c.get("fp_other", 0),
        "fp_declared": c.get("fp_declared", 0),
        "fp_place": c.get("fp_place", 0),
        "fp_public": c.get("fp_public", 0),
    }


def _write_tsv(path: pathlib.Path, report: dict) -> None:
    cols = ["arm", "slice", "type", "gold", "exact", "whole_same_type",
            "partial_same_type", "wrong_type", "miss", "char_coverage_same_type",
            "pred", "pred_typed_tp", "fp_declared", "fp_other", "fp_place",
            "fp_public", "negatives", "negatives_masked"]
    lines = ["\t".join(cols)]
    for arm, data in report["results"]["arms"].items():
        for sl, res in data["per_slice"].items():
            rows = [("ALL", res["totals"])] + sorted(res["per_type"].items())
            for typ, c in rows:
                r = _ratios(c)
                lines.append("\t".join(str(x) for x in [
                    arm, sl, typ, c.get("gold", 0), c.get("exact", 0),
                    c.get("whole_same_type", 0), c.get("partial_same_type", 0),
                    c.get("wrong_type", 0), c.get("miss", 0),
                    f"{r['char_coverage_same_type']:.4f}",
                    c.get("pred", 0), c.get("pred_typed_tp", 0),
                    c.get("fp_declared", 0), c.get("fp_other", 0),
                    c.get("fp_place", 0), c.get("fp_public", 0),
                    c.get("negatives", 0), c.get("negatives_masked", 0)]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_summary(report: dict) -> None:
    env = report["environment"]
    print(f"python          {env['python'].split()[0]}")
    print(f"bundle          {report['bundle']['version']} "
          f"{report['bundle']['bytes']}B {report['bundle']['sha256'][:16]}…")
    print(f"bundle vs B0    {report['bundle']['vs_B0_RUNTIME']}")
    pc = report["source_pin_check_vs_B0"]
    print(f"source pins     {pc['match']}/{pc['compared']} match B0, "
          f"drift={pc['drift']}")
    print(f"holdout read    {report['holdout']['used']} "
          f"(file present: {report['holdout']['file_present']})")
    print(f"controls        {report['results']['instrument_controls']}")
    for arm, data in report["results"]["arms"].items():
        tag = "ABLATION" if data["is_ablation"] else "PRODUCT"
        print(f"\n== {arm} ({tag}) {data['seconds_per_text']*1000:.2f} ms/text "
              f"over {data['unique_texts']} unique texts ==")
        for sl, res in data["per_slice"].items():
            t = res["totals"]
            n = max(1, t.get("gold", 0))
            whole = (t.get("exact", 0) + t.get("whole_same_type", 0)) / n
            ov = (t.get("exact", 0) + t.get("whole_same_type", 0)
                  + t.get("partial_same_type", 0)) / n
            print(f"  {sl:<8} gold={t.get('gold',0):>5} overlap={ov:6.3f} "
                  f"whole={whole:6.3f} wrong_type={t.get('wrong_type',0)/n:6.3f} "
                  f"miss={t.get('miss',0)/n:6.3f} pred={t.get('pred',0):>5} "
                  f"fp(other/decl/place/public)={t.get('fp_other',0)}/"
                  f"{t.get('fp_declared',0)}/{t.get('fp_place',0)}/"
                  f"{t.get('fp_public',0)}")


if __name__ == "__main__":
    raise SystemExit(main())
