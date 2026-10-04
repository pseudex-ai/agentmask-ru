#!/usr/bin/env python3
"""R1 — seed20 (D1-N F1) + street-adjacency veto (D1-N F4) on the leased NAME path.

WHAT THIS IS
    The RED->GREEN instrument for the Tier-0 NAME fix ordered by
    `work/P1/name-model/PLAN.md` §4 R1:

      F1  twenty short lower-case diminutives become SEED-LIST entries in the
          leased asset (`licensing/assets_source.py`, read through
          `names.name_set`), NOT by lowering `_LOWER_DICT_MIN` and NOT by
          relaxing the "every reading" loop in `_lowercase_dictionary_ok`.
      F4  a street word adjacent to the token vetoes the lower-case NAME branch
          (`names.py::gazetteer_names`), so `улицы лермонтова` is a place and not
          a person named Валерий. `ADDR (4) > NAME (3)` still types the real
          address; `«счёт на Гагарина»` must stay masked.

    It runs the REAL detector (`testkit.load_dev_bundle()` -> `Detector`), on
    two frozen frames and two case lists, and prints one machine JSON per run.
    RED is the pristine build; GREEN is the same run after the edit. The
    `--compare` mode reads the two JSONs and prints the delta, so no number in
    the report is copied by hand.

THE TWO DENOMINATORS, FIXED HERE AND NOT CHOSEN AFTER THE FACT
    §1 of PLAN.md records that F1 was once reported as "+27 FP" and once as
    "4 new FP", both true, because the denominators differ. Both are printed on
    every run:

      HAND-LABEL FP   one row per hand-labelled gate occurrence whose label is
                      `other`/`place`/`public` (the three "must NOT mask"
                      labels of `bench/gate`) and which the engine now masks.
                      This is the denominator FIX-PLAN.md §2 uses for "4 new
                      false masks", fp/close 0.15.
      DETECTOR-SPAN FP one row per NAME span the engine emits on a frame text
                      that it did NOT emit before, excluding the spans that
                      close a labelled `person`/`address` occurrence. This is
                      the denominator F1-FINDING.md uses for "+27", fp/close 1.0.
                      It counts every span, several per utterance, including
                      words the gate never labelled.

    A number without its denominator has already cost this repository one
    rollback; both are therefore in the JSON, in the log and in DELTA.json.

FRAMES
    primary   D1-N: 587 unique hand-labelled occurrences of `bench/gate`
              (`~/.cache/pseudex-bench/gate_candidates.json` x
              `bench/gate/labels.json`). person 271 / address 24 / public 57 /
              place 26 / other 209. This is the frame the R1 target
              (219/271 -> 246/271) is stated on.
    cross    P1: the 600-row reconstruction in `work/P1/name-model/gate-frame.json`
              (person 273 / address 25 / public 57 / place 29 / other 216) — a
              second extraction of the same instrument, printed as a
              cross-calibration, never substituted for the primary.

WHAT IT DOES NOT DO
    no engine write, no scorer write, no gold edit, no git, no downloads. The
    only file it writes is `--out/r1-<tag>.json` (and DELTA.json in --compare).

USAGE
    cd prototype
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_r1_seed20_f4.py --tag RED \\
        --out ../research/quality-sprint-2026-09-30/work/P1/r1
    # ... apply the seed20 edit ...
    ... --tag GREEN --out ...
    ... --compare --out ...
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
CACHE = pathlib.Path.home() / ".cache" / "pseudex-bench"
GATE_LABELS = HERE / "bench" / "gate" / "labels.json"
P1_FRAME = (REPO / "research" / "quality-sprint-2026-09-30" / "work" / "P1"
            / "name-model" / "gate-frame.json")
RED_CASES = (REPO / "research" / "quality-sprint-2026-09-30" / "work" / "D1"
             / "N" / "RED-cases.jsonl")
DEFAULT_OUT = (REPO / "research" / "quality-sprint-2026-09-30" / "work" / "P1"
               / "r1")

# The R1 class. Twenty short lower-case diminutives whose surface IS already in
# the leased bulk dictionaries with a Name/Surn reading and is refused by the
# lower-case branch: 28 of the frame's person occurrences carry these surfaces,
# 27 of them unprotected (the 28th is found by the name-pair rule).
SEED20: tuple[str, ...] = (
    "лера", "гуля", "ника", "варя", "илик", "шура", "алсу", "боб", "ирка",
    "мия", "тони", "лех", "азиз", "алик", "лекс", "жора", "тоня", "кац",
    "жан", "ежи",
)

# F4 case list. `label` is the gate label of the occurrence the case is about;
# `expect` is what the engine must do with it. `place`/`other` = the occurrence
# must stay OUT of every span (that is what the gate label means). `address` =
# a LOC span must cover it (ADDR is remapped to LOC after `_resolve`).
# `person` = a NAME span must cover it.
F4_CASES: tuple[tuple[str, str, str, int, str, str], ...] = (
    # --- the three F4 RED place false masks (FIX-PLAN.md §5) ----------------
    ("F4-015", "нет у нас на территории улицы лермонтова понимаете о чем мы с вами разговариваем",
     "лермонтова", 30, "place", "unmasked"),
    ("F4-105", "лермонтова улица лермонтова", "лермонтова", 17, "place", "unmasked"),
    ("F4-151", "крем заказ сто пятьдесят девять минут пять опоздание ленина стоит в дикая пробка",
     "ленина", 53, "place", "unmasked"),
    # --- the three address occurrences the frame labels `address` -----------
    ("F4-221", "здравствуйте ленина сто сорок два со стороны церкви",
     "ленина", 13, "address", "loc"),
    ("F4-215", "деревня иксанова район кунашакский улица центральная дом сорок п",
     "иксанова", 8, "address", "loc"),
    ("F4-147", "первомайская ленина двенадцать тридцать восемь проездная петрова",
     "петрова", 57, "address", "loc"),
    # --- F4 must-not-regress ------------------------------------------------
    ("KEEP-001", "перезвоните ленину пожалуйста", "ленину", 12, "person", "name"),
    ("KEEP-002", "передайте петровой документы", "петровой", 9, "person", "name"),
    # THE load-bearing case named in the R1 order: the capital letter and the
    # naming cue are stronger evidence than the street word, so the address
    # guard must not reach past them.
    ("KEEP-003", "счёт на Гагарина пришёл", "Гагарина", 6, "person", "name"),
    ("KEEP-004", "позвоните морозову сегодня", "морозову", 9, "person", "name"),
    ("KEEP-005", "живу на улице ленина дом пять", "ленина", 16, "address", "loc"),
    ("KEEP-006", "улица лермонтова дом семь", "лермонтова", 7, "address", "loc"),
    ("KEEP-007", "на ленина торговый центр кит", "ленина", 3, "place", "unmasked"),
    # the guard must not reach across a clause boundary: «улица» from the second
    # mention is not evidence about the first
    ("CTRL-001", "гуля, улица лермонтова", "гуля", 0, "person", "name"),
    ("CTRL-002", "перезвоните лере. улица лермонтова", "лере", 12, "person", "name"),
    # a name that IS a street name stays a person when nothing names a street
    ("CTRL-003", "перезвоните гагариной", "гагариной", 12, "person", "name"),
    ("CTRL-004", "позвони митиной", "митиной", 7, "person", "name"),
    # the ADDR arm still owns a real address (its priority is higher)
    ("CTRL-005", "переулок лермонтова 34 квартира 9", "лермонтова", 9, "address", "loc"),
    # adjacency for the other street words of the order (проспект, переулок)
    ("CTRL-006", "проспект ленина закрыт на ремонт", "ленина", 9, "place", "unmasked"),
    ("CTRL-007", "переулок ленина дом три", "ленина", 9, "address", "loc"),
)

ENGINE_FILES = (
    "pseudex/names.py",
    "pseudex/detect_all.py",
    "pseudex/address.py",
    "pseudex/morph_names.py",
    "pseudex/assets.py",
    "licensing/assets_source.py",
)

# Independent corpora (NOT written by this repository) used for the per-word
# false-mask question the F1 caveat names: "seed-list membership is context-free,
# so these words become names everywhere. гуля (pigeon), ежи (hedgehogs), боб
# (bean), кац are the risky ones."
MASSIVE_CACHE = CACHE
NEREL_DIR = CACHE / "nerel" / "NEREL-v1.1"

# ----------------------------------------------------------------- helpers --


def sha256_file(path: pathlib.Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gate_key(row: dict) -> str:
    raw = f"{row['word']}\t{row['start']}\t{row['text']}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def overlaps(a: dict, b: dict) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def covers(outer: dict, inner: dict) -> bool:
    return outer["start"] <= inner["start"] and inner["end"] <= outer["end"]


# ------------------------------------------------------------------ frames --


def load_primary_frame() -> list[dict]:
    """D1-N frame: 587 unique labelled occurrences, one row each.

    Deduplicated by the gate key, exactly as `work/D1/N/d1_name_probe.py` does —
    the raw candidate file repeats a row for every sentence of an utterance.
    """
    occ = json.loads((CACHE / "gate_candidates.json").read_text(encoding="utf-8"))
    lab = json.loads(GATE_LABELS.read_text(encoding="utf-8"))
    rows: list[dict] = []
    seen: set[str] = set()
    for row in occ["occurrences"]:
        key = gate_key(row)
        if key in seen or key not in lab:
            continue
        seen.add(key)
        rows.append({"key": key, "word": row["word"], "start": row["start"],
                     "end": row["end"], "text": row["text"], "label": lab[key],
                     "corpus": row.get("corpus"),
                     "masked_in_snapshot": row["masked"]})
    return rows


def load_all_occurrences() -> list[dict]:
    """Every candidate occurrence (labelled or not) — needed to attribute a new
    span that lands on an occurrence the gate never labelled (the honest
    detector-span denominator)."""
    occ = json.loads((CACHE / "gate_candidates.json").read_text(encoding="utf-8"))
    lab = json.loads(GATE_LABELS.read_text(encoding="utf-8"))
    rows, seen = [], set()
    for row in occ["occurrences"]:
        key = gate_key(row)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"key": key, "word": row["word"], "start": row["start"],
                     "end": row["end"], "text": row["text"],
                     "label": lab.get(key), "corpus": row.get("corpus")})
    return rows


def load_p1_frame() -> list[dict]:
    rows = json.loads(P1_FRAME.read_text(encoding="utf-8"))
    return [{"word": r["word"], "start": r["start"], "end": r["end"],
             "text": r["text"], "label": r["label"], "stratum": r["stratum"]}
            for r in rows]


def frame_texts(rows: list[dict]) -> list[str]:
    return sorted({r["text"] for r in rows})


# ------------------------------------------------------------- measurement --


def detect_map(det, texts) -> dict[str, list[dict]]:
    out = {}
    for text in texts:
        out[text] = [{"start": s.start, "end": s.end, "type": s.entity_type,
                      "value": s.value} for s in det.detect(text)]
    return out


def recall_block(rows: list[dict], preds: dict[str, list[dict]]) -> dict:
    """Occurrence-level recall + coverage for the `person` label, and the
    occurrence-level precision split of every label the engine protects.

    The D1-N taxonomy is reproduced exactly: `exact` (same boundaries), `whole`
    (a NAME span contains the occurrence), `partial` (NAME overlaps it), `miss`.
    Recall is exact+whole, as in `work/D1/N/NAME-BASELINE.md` and `F1-FINDING.md`.
    Char coverage is counted over MUST-MASK occurrences only (person+address),
    because those are the occurrences the frame declares gold — summing the
    209 `other` occurrences into the denominator is what makes a coverage number
    that can never be compared with the archive's.
    """
    by_word: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    c = collections.Counter()
    misses = []
    for r in rows:
        spans = preds[r["text"]]
        name = [s for s in spans if s["type"] == "NAME" and overlaps(s, r)]
        any_ = [s for s in spans if overlaps(s, r)]
        masked = bool(any_)
        by_word[r["word"].lower()][r["label"]] += 1
        by_word[r["word"].lower()]["masked"] += 1 if masked else 0
        by_word[r["word"].lower()]["protected_name"] += 1 if name else 0
        if r["label"] in ("person", "address"):
            c["must_mask"] += 1
            covered = set()
            for s in name:
                covered.update(range(max(s["start"], r["start"]),
                                     min(s["end"], r["end"])))
            c["gold_chars"] += r["end"] - r["start"]
            c["covered_chars"] += len(covered)
        if r["label"] == "person":
            c["person"] += 1
            pcovered = set()
            for s in name:
                pcovered.update(range(max(s["start"], r["start"]),
                                      min(s["end"], r["end"])))
            c["person_gold_chars"] += r["end"] - r["start"]
            c["person_covered_chars"] += len(pcovered)
            if any(s["start"] == r["start"] and s["end"] == r["end"] for s in name):
                c["person_exact"] += 1
            elif any(covers(s, r) for s in name):
                c["person_whole"] += 1
            elif name:
                c["person_partial"] += 1
            elif any_:
                c["person_wrong_type"] += 1
            else:
                c["person_miss"] += 1
            if name:
                c["person_protected"] += 1
            else:
                misses.append(r)
        elif r["label"] == "address":
            c["address_n"] += 1
            if any_:
                c["address_protected"] += 1
            else:
                c["address_miss"] += 1
        elif r["label"] in ("place", "other", "public"):
            c[f"{r['label']}_n"] += 1
            if masked:
                c[f"false_mask_{r['label']}"] += 1
                if name:
                    c[f"false_mask_{r['label']}_name"] += 1
    person = max(1, c["person"])
    must = max(1, c["must_mask"])
    hand_fp = c["false_mask_other"] + c["false_mask_place"] + c["false_mask_public"]
    return {
        "rows": len(rows),
        "label_counts": dict(collections.Counter(r["label"] for r in rows)),
        "person": c["person"], "person_protected": c["person_protected"],
        "person_exact": c["person_exact"], "person_whole": c["person_whole"],
        "person_partial": c["person_partial"],
        "person_wrong_type": c["person_wrong_type"],
        "person_recall_whole": round((c["person_exact"] + c["person_whole"]) / person, 4),
        "person_miss": c["person_miss"],
        "person_recall": round(c["person_protected"] / person, 4),
        "address": c["address_n"],
        "address_protected": c["address_protected"], "address_miss": c["address_miss"],
        "must_mask": c["must_mask"],
        "must_mask_protected": c["person_protected"] + c["address_protected"],
        "must_mask_recall": round((c["person_protected"] + c["address_protected"]) / must, 4),
        "char_coverage": round(c["person_covered_chars"] / max(1, c["person_gold_chars"]), 4),
        "char_coverage_person": round(c["person_covered_chars"] / max(1, c["person_gold_chars"]), 4),
        "char_coverage_must_mask": round(c["covered_chars"] / max(1, c["gold_chars"]), 4),
        "gold_chars": c["person_gold_chars"], "covered_chars": c["person_covered_chars"],
        "false_mask_occurrences": hand_fp,
        "false_mask_by_label": {
            "other": c["false_mask_other"], "place": c["false_mask_place"],
            "public": c["false_mask_public"]},
        "false_mask_other_or_place": c["false_mask_other"] + c["false_mask_place"],
        "misses": misses,
    }


def span_taxonomy(rows: list[dict], preds: dict[str, list[dict]],
                  all_occ: list[dict]) -> dict:
    """Every NAME span the engine emits on a frame text, classified by what it
    lands on. This is the DETECTOR-SPAN denominator: one row per span, several
    per utterance, including words the gate never labelled."""
    per_text_occ: dict[str, list[dict]] = collections.defaultdict(list)
    for o in all_occ:
        per_text_occ[o["text"]].append(o)
    texts = {r["text"] for r in rows}
    c = collections.Counter()
    spans: list[dict] = []
    for text in texts:
        for s in preds[text]:
            if s["type"] != "NAME":
                continue
            c["name_spans"] += 1
            hits = [o for o in per_text_occ.get(text, []) if overlaps(s, o)]
            if not hits:
                cls = "unlabelled_none"
            else:
                labels = sorted({o["label"] or "UNLABELLED" for o in hits})
                cls = "+".join(labels)
            c[f"on_{cls}"] += 1
            spans.append({"text": text, "span": s, "class": cls,
                          "occurrences": [o["word"] for o in hits]})
    return {"counters": dict(c), "spans": spans}


def span_delta(pre: dict, post: dict) -> dict:
    """New NAME spans = spans GREEN emits that RED did not. A span counts as a
    close when it lands on a labelled `person`/`address` occurrence that RED did
    not protect; everything else is a false mask on the detector-span
    denominator, split by what it landed on."""
    def index(d):
        out = {}
        for row in d["spans"]:
            key = (row["text"], row["span"]["start"], row["span"]["end"])
            out[key] = row
        return out
    a, b = index(pre), index(post)
    new_rows = [b[k] for k in b if k not in a]
    closes, fp = [], []
    for row in new_rows:
        cls = row["class"]
        if cls in ("person", "address"):
            closes.append(row)
        else:
            fp.append(row)
    by_class = collections.Counter(r["class"] for r in fp)
    return {
        "name_spans_red": pre["counters"].get("name_spans", 0),
        "name_spans_green": post["counters"].get("name_spans", 0),
        "new_name_spans": len(new_rows),
        "closed_occurrences": len(closes),
        "new_fp_detector_spans": len(fp),
        "new_fp_by_class": dict(by_class),
        "new_fp_words": collections.Counter(
            w for r in fp for w in r["occurrences"]).most_common(30),
        "examples": [{"text": r["text"], "span": r["span"], "class": r["class"],
                      "occurrences": r["occurrences"]} for r in fp[:15]],
    }


def f4_block(det) -> list[dict]:
    out = []
    for cid, text, value, off, label, expect in F4_CASES:
        spans = [{"start": s.start, "end": s.end, "type": s.entity_type,
                  "value": s.value} for s in det.detect(text)]
        on = [s for s in spans if s["start"] <= off < s["end"]
              or s["start"] < off + len(value) <= s["end"]
              or (off <= s["start"] and s["end"] <= off + len(value))]
        any_hit = bool(on)
        name_hit = any(s["type"] == "NAME" for s in on)
        loc_hit = any(s["type"] == "LOC" for s in on)
        if expect == "unmasked":
            ok = not any_hit
        elif expect == "loc":
            ok = loc_hit
        else:
            ok = name_hit
        out.append({"id": cid, "text": text, "value": value, "offset": off,
                    "gate_label": label, "expect": expect,
                    "verdict": "PASS" if ok else "FAIL",
                    "name_vetoed": not name_hit,
                    "spans": spans, "spans_on_occurrence": on})
    return out


def seed20_block(det, rows: list[dict], preds: dict[str, list[dict]],
                 names, all_occ: list[dict]) -> dict:
    """Per-word evidence for the class: frame occurrences, what the engine does,
    and whether the word is currently reachable at all."""
    from pseudex.morph import MORPH
    target = set(SEED20)
    per_word: dict[str, dict] = {}
    for word in SEED20:
        wr = [r for r in rows if r["word"].lower() == word]
        occ_all = [o for o in all_occ if o["word"].lower() == word]
        protected = 0
        for r in wr:
            spans = preds[r["text"]]
            if r["label"] != "person":
                continue
            if any(s["type"] == "NAME" and overlaps(s, r) for s in spans):
                protected += 1
        parses = MORPH.parse(word)
        name_tags = sorted({t for p in parses for t in
                            {"Name", "Surn", "Patr"} & set(p.tag.grammemes)})
        per_word[word] = {
            "labelled_occurrences": collections.Counter(r["label"] for r in wr),
            "labelled_person_protected_now": protected,
            "labelled_person_total": sum(1 for r in wr if r["label"] == "person"),
            "all_occurrences_in_frame": len(occ_all),
            "in_name_set": word in names.name_set,
            "in_ambiguous_cue_gated": word in names.ambiguous,
            "in_dict_first": word in names.dict_first,
            "in_dict_surnames": word in names.dict_surnames,
            "len": len(word),
            "morph_name_tags": name_tags,
            "morph_known": bool(parses) and any(p.is_known for p in parses),
        }
    return per_word


def red_cases_block(det) -> dict:
    """The D1-N RED case list, re-run live: which of the recorded NAME misses
    the engine still misses, split by the recorded class."""
    if not RED_CASES.exists():
        return {"available": False}
    rows, classes = [], collections.Counter()
    for line in RED_CASES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        exp = case.get("expected") or {}
        if case.get("kind") != "MISS" or exp.get("type") != "NAME":
            continue
        text = case["text"]
        s, e = exp["span"]
        spans = [{"start": sp.start, "end": sp.end, "type": sp.entity_type}
                 for sp in det.detect(text)]
        protected = any(sp["type"] == "NAME" and sp["start"] <= s and e <= sp["end"]
                        for sp in spans)
        cls = case.get("class", "")
        classes[cls] += 1
        rows.append({"id": case.get("id"), "word": case.get("target"),
                     "class": cls, "still_missed": not protected,
                     "text": text[:120]})
    return {"available": True, "n": len(rows), "classes": dict(classes),
            "still_missed": sum(1 for r in rows if r["still_missed"]),
            "rows": rows}


# -------------------------------------------------------------------- main --


def strip_seed20_assets() -> None:
    """Remove the twenty words from the LEASED payload and reload.

    This exists so the two arms of R1 can be measured inside ONE process, on
    byte-identical engine sources. Two reasons it is the right instrument here
    and not a shortcut:

      * `prototype/pseudex/address.py` is being edited by another workstream in
        the same working tree; a RED run and a GREEN run ten minutes apart can
        straddle that edit, and the delta would then be LOC + NAME.
      * PLAN.md §7 records that the seed20 arm was first measured by
        CAPITALISING the word — a different code path from seed membership.
        Loading the stripped payload exercises the real one (`_name_set_hit`).

    The strip is at the PAYLOAD level, so `assets._build_names` derives
    `name_set`/`ambiguous` exactly as production does; nothing is patched on the
    runtime struct after the fact.
    """
    import hashlib as _hashlib
    from licensing.pack import build_payload
    from pseudex import bundle
    from pseudex.assets import ASSETS

    payload = build_payload()
    names = payload["names"]
    for key in ("seed_first_names", "diminutives"):
        names[key] = [w for w in names[key] if w not in set(SEED20)]
    payload["version"] = _hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    ASSETS.load(bundle.frame_payload(payload))


def measure(tag: str, det, names, primary, all_occ, p1) -> dict:
    started = time.perf_counter()
    preds = detect_map(det, frame_texts(primary))
    preds_p1 = detect_map(det, frame_texts(p1))

    rec = recall_block(primary, preds)
    tax = span_taxonomy(primary, preds, all_occ)
    rec_p1 = recall_block(p1, preds_p1)

    return {
        "tag": tag,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine_sha256": {f: sha256_file(HERE / f) for f in ENGINE_FILES},
        "seed20": list(SEED20),
        "primary_frame": "D1-N 587 hand-labelled occurrences (gate_candidates x bench/gate/labels.json)",
        "frame": {k: v for k, v in rec.items() if k != "misses"},
        "frame_misses": [{"word": r["word"], "label": r["label"],
                          "text": r["text"][:120]} for r in rec["misses"]],
        "span_taxonomy": tax["counters"],
        "span_rows": tax["spans"],
        "p1_frame": {k: v for k, v in rec_p1.items() if k != "misses"},
        "f4_cases": f4_block(det),
        "seed20_words": seed20_block(det, primary, preds, names, all_occ),
        "red_cases": red_cases_block(det),
        "elapsed_s": round(time.perf_counter() - started, 2),
    }


def run(tag: str, out_dir: pathlib.Path) -> int:
    sys.path.insert(0, str(HERE))
    from testkit import load_dev_bundle
    load_dev_bundle()
    from pseudex.detect_all import Detector
    from pseudex.names import ASSETS

    det = Detector()
    names = ASSETS.get().names

    primary = load_primary_frame()
    all_occ = load_all_occurrences()
    p1 = load_p1_frame()

    report = measure(tag, det, names, primary, all_occ, p1)
    rec = report["frame"]
    rec_p1 = report["p1_frame"]
    tax = {"counters": report["span_taxonomy"]}

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"r1-{tag}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                    encoding="utf-8")

    # ------------------------------------------------------------- the log --
    print(f"=== R1 {tag} === {report['generated_utc']}")
    print("engine sha256:")
    for f, h in report["engine_sha256"].items():
        print(f"  {f:<34} {h}")
    print()
    print(f"PRIMARY FRAME (D1-N 587): labels {report['frame']['label_counts']}")
    print(f"  person        {rec['person_protected']}/{rec['person']} protected"
          f"   whole recall {rec['person_exact'] + rec['person_whole']}/{rec['person']}"
          f" = {rec['person_recall_whole']:.4f}   miss {rec['person_miss']}"
          f"   char_coverage {rec['char_coverage']:.4f}")
    print(f"  must-mask     {rec['must_mask_protected']}/{rec['must_mask']} = {rec['must_mask_recall']:.4f}"
          f"   (person+address)")
    print(f"  hand-label FP occurrences: {rec['false_mask_occurrences']} "
          f"{rec['false_mask_by_label']}")
    print(f"  detector-span NAME spans: {tax['counters'].get('name_spans', 0)}")
    for cls in sorted(k for k in tax["counters"] if k.startswith("on_")):
        print(f"    {cls:<28} {tax['counters'][cls]}")
    print()
    print(f"P1 CROSS FRAME (600): person {rec_p1['person_protected']}/{rec_p1['person']} "
          f"= {rec_p1['person_recall']:.4f}  miss {rec_p1['person_miss']}  "
          f"FP occ {rec_p1['false_mask_occurrences']} {rec_p1['false_mask_by_label']}")
    print()
    print("F4 CASES:")
    for row in report["f4_cases"]:
        spans = ", ".join(f"{s['type']}:{s['value']!r}" for s in row["spans_on_occurrence"]) or "-"
        print(f"  {row['verdict']:<4} {row['id']:<9} [{row['gate_label']:>7}] "
              f"expect {row['expect']:<8} on-span: {spans}")
    print()
    print("SEED20 WORDS (frame occurrences / protected / reachability):")
    for word in SEED20:
        w = report["seed20_words"][word]
        print(f"  {word:<6} person {w['labelled_person_protected_now']}/{w['labelled_person_total']}"
              f"  labels {dict(w['labelled_occurrences'])}"
              f"  in_name_set={w['in_name_set']} cue_gated={w['in_ambiguous_cue_gated']}"
              f"  len={w['len']} tags={w['morph_name_tags']}")
    print()
    rc = report["red_cases"]
    if rc.get("available"):
        print(f"RED-CASES (D1-N recorded NAME misses): {rc['still_missed']}/{rc['n']} still missed"
              f"  classes {rc['classes']}")
    print()
    print(f"elapsed {report['elapsed_s']}s -> {path}")
    return 0


def _corpus_texts() -> list[dict]:
    """Independent corpora, with whatever gold this repository already trusts.

    MASSIVE ru-RU (third-party slots) and NEREL v1.1 dev+test (third-party
    PERSON annotations). Both are read here only to answer ONE question that the
    pinned gate frame cannot: do the twenty seed words start masking ordinary
    words in prose nobody tuned against?
    """
    rows: list[dict] = []
    try:
        import pandas as pd
    except ImportError:  # venv has pyarrow, the bench's pandas is not shipped
        shim = pathlib.Path(os.environ.get("R1_PANDAS_SHIM", "/tmp/r1-shim"))
        if not (shim / "pandas.py").exists():
            raise
        sys.path.insert(0, str(shim))
        import pandas as pd  # type: ignore  (pyarrow-backed, see GATE.json)
    files = [MASSIVE_CACHE / f"massive_ru_{p}.parquet"
             for p in ("train", "validation", "test")]
    # The corpus is OPTIONAL: skip it when no shard is downloaded, fail closed
    # when a present shard will not read — never swallow a read error as «absent».
    present = [f for f in files if f.exists()]
    if present:
        frame = pd.concat([pd.read_parquet(f) for f in present])
        slot = __import__("re").compile(r"\[([a-z_]+)\s*:\s*([^\]]+)\]")
        for utt, annot in zip(frame["utt"], frame["annot_utt"]):
            text = str(utt)
            persons = [v.strip() for k, v in slot.findall(str(annot))
                       if k == "person"]
            rows.append({"corpus": "MASSIVE", "text": text, "gold_person": persons,
                         "gold_spans": []})
    if NEREL_DIR.exists():
        ann_re = __import__("re").compile(r"^T\d+\t(\w+) (\d+) (\d+)\t(.*)$")
        for split in ("dev", "test"):
            for txt in sorted((NEREL_DIR / split).glob("*.txt")):
                ann = txt.with_suffix(".ann")
                if not ann.exists():
                    continue
                spans = []
                for line in ann.read_text(encoding="utf-8").splitlines():
                    m = ann_re.match(line)
                    if m and m.group(1) == "PERSON":
                        spans.append((int(m.group(2)), int(m.group(3)),
                                      m.group(4), m.group(1)))
                rows.append({"corpus": f"NEREL/{split}",
                             "text": txt.read_text(encoding="utf-8"),
                             "gold_person": [s[2] for s in spans],
                             "gold_spans": spans})
    return rows


def independent(out_dir: pathlib.Path) -> int:
    """Per-word false-mask check on the two independent corpora.

    A token is a CANDIDATE when its lemma (or its lowercase surface) is one of
    the twenty — the same test `_name_set_hit` makes, because inflected forms
    («гулей», «гуль») are exactly how the risk shows up. Only texts carrying a
    candidate are detected, so the cost is the candidates, not the corpus.

    An arm is MASKED when a NAME span of the engine covers the token. Gold is
    used only to say whether the newly masked word was a person to the corpus's
    annotator; a new mask on a non-person is a measured false mask in prose we
    did not write.
    """
    sys.path.insert(0, str(HERE))
    from testkit import load_dev_bundle
    load_dev_bundle()
    from pseudex.detect_all import Detector
    from pseudex.names import _lemmas
    from pseudex.morph import MORPH  # noqa: F401  (warms the analyzer)

    det = Detector()
    rows = _corpus_texts()
    target = set(SEED20)

    def candidates(text: str) -> list[tuple[int, int, str, str]]:
        out = []
        for m in __import__("re").finditer(r"[а-яёА-ЯЁ]+", text):
            word = m.group()
            low = word.lower()
            lemmas = _lemmas(low)
            hit = low if low in target else next(
                (lm for lm in lemmas if lm in target), None)
            if hit:
                out.append((m.start(), m.end(), word, hit))
        return out

    cand_rows = [(r, candidates(r["text"])) for r in rows]
    cand_rows = [(r, c) for r, c in cand_rows if c]
    print(f"independent corpora: {len(rows)} documents, {len(cand_rows)} carry a seed20 candidate")

    def arm(_det) -> dict[tuple[str, int, int], bool]:
        masked: dict[tuple[str, int, int], bool] = {}
        for r, cands in cand_rows:
            spans = [s for s in _det.detect(r["text"]) if s.entity_type == "NAME"]
            for start, end, _word, _hit in cands:
                masked[(r["corpus"], start, end)] = any(
                    s.start < end and start < s.end for s in spans)
        return masked

    after = arm(det)
    strip_seed20_assets()
    before = arm(det)

    per_word: dict[str, dict] = {w: {"candidates": 0, "new_masked": 0,
                                     "new_masked_person": 0,
                                     "new_masked_non_person": 0,
                                     "examples": []} for w in SEED20}
    total = collections.Counter()
    for r, cands in cand_rows:
        for start, end, word, hit in cands:
            key = (r["corpus"], start, end)
            was, now = before.get(key, False), after.get(key, False)
            # a token counts as person-gold when it sits INSIDE a gold span, or
            # when the utterance's person slot literally contains it
            inside = any(gs <= start and end <= ge for gs, ge, _v, _t in r["gold_spans"]) \
                or any(v.lower().strip() == word.lower() for v in r["gold_person"])
            d = per_word[hit]
            d["candidates"] += 1
            total["candidates"] += 1
            if now and not was:
                d["new_masked"] += 1
                total["new_masked"] += 1
                if inside:
                    d["new_masked_person"] += 1
                    total["new_masked_person"] += 1
                else:
                    d["new_masked_non_person"] += 1
                    total["new_masked_non_person"] += 1
                    if len(d["examples"]) < 4:
                        d["examples"].append({"corpus": r["corpus"], "word": word,
                                              "text": r["text"][:160]})
            if was != now:
                total["changed"] += 1

    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "engine_sha256": {f: sha256_file(HERE / f) for f in ENGINE_FILES},
           "corpora": {c: sum(1 for r in rows if r["corpus"] == c)
                       for c in sorted({r["corpus"] for r in rows})},
           "documents_with_candidate": len(cand_rows),
           "totals": dict(total),
           "per_word": per_word}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "INDEPENDENT.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{'word':<8}{'cand':>6}{'new_mask':>10}{'person':>8}{'NON-person':>12}")
    for w in SEED20:
        d = per_word[w]
        print(f"{w:<8}{d['candidates']:>6}{d['new_masked']:>10}"
              f"{d['new_masked_person']:>8}{d['new_masked_non_person']:>12}")
    print(f"{'TOTAL':<8}{total['candidates']:>6}{total['new_masked']:>10}"
          f"{total['new_masked_person']:>8}{total['new_masked_non_person']:>12}")
    print("\nnew masks on non-person occurrences (independent prose):")
    for w in SEED20:
        for ex in per_word[w]["examples"]:
            print(f"  {w:<6} [{ex['corpus']}] {ex['text']!r}")
    print(f"\nwrote {out_dir / 'INDEPENDENT.json'}")
    return 0


def compare(out_dir: pathlib.Path) -> int:
    red = json.loads((out_dir / "r1-RED.json").read_text(encoding="utf-8"))
    green = json.loads((out_dir / "r1-GREEN.json").read_text(encoding="utf-8"))
    compare_reports(red, green, out_dir, "DELTA.json")
    return 0


def paired(out_dir: pathlib.Path) -> int:
    """Both arms in ONE process, on byte-identical engine sources.

    The live RED/GREEN pair can straddle another workstream's edit of
    `pseudex/address.py` (it did: the file changed under this run). This mode
    removes the seed words from the LEASED payload and reloads, so the only
    difference between the two arms is the seed list — the same guarantee a
    frozen build gives, without copying the tree.
    """
    sys.path.insert(0, str(HERE))
    from testkit import load_dev_bundle
    load_dev_bundle()
    from pseudex.detect_all import Detector
    from pseudex.names import ASSETS

    det = Detector()
    primary = load_primary_frame()
    all_occ = load_all_occurrences()
    p1 = load_p1_frame()

    after = measure("PAIRED-WITH-SEED20", det, ASSETS.get().names, primary, all_occ, p1)
    strip_seed20_assets()
    before = measure("PAIRED-WITHOUT-SEED20", det, ASSETS.get().names, primary, all_occ, p1)

    out_dir.mkdir(parents=True, exist_ok=True)
    for tag, rep in (("PAIRED-RED", before), ("PAIRED-GREEN", after)):
        (out_dir / f"r1-{tag}.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    compare_reports(before, after, out_dir, "DELTA-PAIRED.json")
    return 0


def compare_reports(red: dict, green: dict, out_dir: pathlib.Path,
                    out_name: str) -> dict:

    # the pair is only a measurement if nothing else moved
    moved = {f: (red["engine_sha256"][f], green["engine_sha256"][f])
             for f in red["engine_sha256"]
             if red["engine_sha256"][f] != green["engine_sha256"][f]}
    allowed = {"pseudex/names.py", "licensing/assets_source.py"}
    unexpected = {f: v for f, v in moved.items() if f not in allowed}

    pre_tax = {"counters": red["span_taxonomy"], "spans": red["span_rows"]}
    post_tax = {"counters": green["span_taxonomy"], "spans": green["span_rows"]}
    delta = span_delta(pre_tax, post_tax)
    rf, gf = red["frame"], green["frame"]
    closes = gf["person_protected"] - rf["person_protected"]
    hand_new = gf["false_mask_by_label"]["other"] - rf["false_mask_by_label"]["other"] \
        + gf["false_mask_by_label"]["place"] - rf["false_mask_by_label"]["place"] \
        + gf["false_mask_by_label"]["public"] - rf["false_mask_by_label"]["public"]
    det_new = delta["new_fp_detector_spans"]

    out = {
        "task": "P1/R1 — seed20 (D1-N F1) + street-adjacency veto (D1-N F4)",
        "model": "deepseek-official/deepseek-flash (explicit routing)",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine_sha256": green["engine_sha256"],
        "moved_files": moved,
        "unexpected_moved_files": unexpected,
        "primary_frame": {
            "person_before": f"{rf['person_protected']}/{rf['person']}",
            "person_after": f"{gf['person_protected']}/{gf['person']}",
            "person_recall_before": rf["person_recall_whole"],
            "person_recall_after": gf["person_recall_whole"],
            "person_protected_before": rf["person_protected"],
            "person_protected_after": gf["person_protected"],
            "person_closed": closes,
            "char_coverage_before": rf["char_coverage"],
            "char_coverage_after": gf["char_coverage"],
            "must_mask_before": f"{rf['must_mask_protected']}/{rf['must_mask']}",
            "must_mask_after": f"{gf['must_mask_protected']}/{gf['must_mask']}",
            "hand_label_fp_before": rf["false_mask_by_label"],
            "hand_label_fp_after": gf["false_mask_by_label"],
            "hand_label_new_fp": hand_new,
            "hand_label_fp_per_close": round(hand_new / closes, 3) if closes else None,
            "detector_span_new_fp": det_new,
            "detector_span_new_fp_per_close": round(det_new / closes, 3) if closes else None,
        },
        "detector_span_detail": delta,
        "p1_frame": {
            "person_before": f"{red['p1_frame']['person_protected']}/{red['p1_frame']['person']}",
            "person_after": f"{green['p1_frame']['person_protected']}/{green['p1_frame']['person']}",
            "person_recall_before": red['p1_frame']['person_recall_whole'],
            "person_recall_after": green['p1_frame']['person_recall_whole'],
            "hand_label_fp_before": red["p1_frame"]["false_mask_by_label"],
            "hand_label_fp_after": green["p1_frame"]["false_mask_by_label"],
        },
        "f4_cases": [{"id": g["id"], "red": r["verdict"], "green": g["verdict"],
                      "gate_label": g["gate_label"], "expect": g["expect"],
                      "green_spans": g["spans_on_occurrence"]}
                     for r, g in zip(red["f4_cases"], green["f4_cases"])],
        "seed20_words": {w: {"person_before": red["seed20_words"][w]["labelled_person_protected_now"],
                             "person_after": green["seed20_words"][w]["labelled_person_protected_now"],
                             "person_total": green["seed20_words"][w]["labelled_person_total"],
                             "all_occurrences": green["seed20_words"][w]["all_occurrences_in_frame"],
                             "after_in_name_set": green["seed20_words"][w]["in_name_set"],
                             "after_cue_gated": green["seed20_words"][w]["in_ambiguous_cue_gated"]}
                         for w in green["seed20"]},
        "red_cases": {"before": red["red_cases"], "after": green["red_cases"]},
    }
    # keep the per-word before/after counters JSON-safe (Counters are dicts already)
    (out_dir / out_name).write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"=== R1 DELTA ({out_name}) RED -> GREEN ===")
    print(f"files moved: {moved}")
    if unexpected:
        print(f"!!! UNEXPECTED files moved outside this task's write scope: {unexpected}")
    pf = out["primary_frame"]
    print(f"PRIMARY (D1-N 587) person {pf['person_before']} -> {pf['person_after']}"
          f" = {pf['person_recall_after']:.4f}  closed {pf['person_closed']}")
    print(f"  char coverage {pf['char_coverage_before']} -> {pf['char_coverage_after']}")
    print(f"  must-mask {pf['must_mask_before']} -> {pf['must_mask_after']}")
    print(f"  HAND-LABEL new FP {pf['hand_label_new_fp']}"
          f"  fp/close {pf['hand_label_fp_per_close']}   {pf['hand_label_fp_after']}")
    print(f"  DETECTOR-SPAN new FP {pf['detector_span_new_fp']}"
          f"  fp/close {pf['detector_span_new_fp_per_close']}")
    print(f"    by class {delta['new_fp_by_class']}")
    print(f"    by word  {delta['new_fp_words']}")
    print(f"P1 CROSS: {out['p1_frame']['person_before']} -> {out['p1_frame']['person_after']}"
          f"  FP {out['p1_frame']['hand_label_fp_before']} -> {out['p1_frame']['hand_label_fp_after']}")
    print()
    print("F4 cases red->green:")
    for row in out["f4_cases"]:
        print(f"  {row['red']:>4} -> {row['green']:<4} {row['id']:<9} [{row['gate_label']}]")
    print()
    print("per-word person closes / new occurrences masked:")
    for w, d in out["seed20_words"].items():
        print(f"  {w:<6} {d['person_before']}->{d['person_after']}/{d['person_total']}"
              f"  frame_occurrences {d['all_occurrences']}"
              f"  name_set {d['after_in_name_set']} cue_gated {d['after_cue_gated']}")
    print(f"\nwrote {out_dir / out_name}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="RED")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--paired", action="store_true",
                    help="both arms in one process via payload strip (drift-proof)")
    ap.add_argument("--independent", action="store_true",
                    help="per-word new false masks on MASSIVE + NEREL")
    args = ap.parse_args()
    out_dir = pathlib.Path(args.out)
    if args.independent:
        return independent(out_dir)
    if args.paired:
        return paired(out_dir)
    if args.compare:
        return compare(out_dir)
    return run(args.tag, out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
