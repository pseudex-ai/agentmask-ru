"""Detection-only sweep, HONEST + COMPLETE: the ACTUAL engine over the corpus's
gold PII, scored the way the G7 question is actually asked.

FREE (no model, no network): loads the dev bundle, runs `Detector.detect` on every
message, and scores gold PII. Three things separate this from the first version,
each one a measurement that was lying or absent before:

(a) HONEST RECALL. The first version demanded `pred.entity_type == gold.type`, so
    a value the engine DID mask under its own label scored 0 — EPTS_NUMBER under
    `EPTS`, OGRNIP under `OGRN`, OMS_ENP under `OMS`, STS/PTS_NUMBER under
    `VEHICLE_DOC` (the registry's `engine_labels`, `pii_types.py`). Three numbers
    are printed per type, never merged:
      * `exact`  — pred label == gold id (the old, label-strict number);
      * `typed`  — pred label is the gold id OR one of the gold id's declared
                   `engine_labels` (typed-correct, honest about the desync);
      * `honest` — the value is masked under ANY label at all (the masking
                   question: did the real value reach the model?).
    Separators are normalised before comparing (`.:,/` and spaces stripped, case
    folded), so MAC `fc:f3:c2:cf:a5:ac` matches `FCF3C2CFA5AC` and FSSP
    `842899/97/...` matches its squeezed form. Without this the sweep measured
    its own formatting, not the detector.

(b) GENERATED HOPS. The first version scored only `where.kind == "message"`.
    Every other gold item (`kind == "seed"`, the record field the generator put
    into the case) was unscored. This version runs the detector over the case's
    DECLARED hop content — the non-user/non-system `base.messages`, and every
    string leaf of `hops` / `expects` / `forced` and of the other declaration
    fields (`document`/`rag`/`pick`/`memory`/`loop`/`branch`/`returns`, so the
    claim covers the whole frame) — and scores every `kind != "message"` gold
    item that appears there. A gold item with no message/hop presence falls back
    to the FIRST user turn only. WHAT THE HOPS ACTUALLY CARRY IS PRINTED,
    because in this corpus they carry no message text: `hops` is item ids and
    JSON paths, `expects` is null everywhere, `forced` carries a `{value}`
    placeholder template, and `base.messages` has no assistant/tool/answer turn.
    The section reports the buckets (hop-present, fallback-first-turn,
    later-turn-only, absent-from-every-scanned-text) so a reader can see exactly
    what the fallback bought.

(c) FORM + CONSISTENCY, per FOUND item, as two separate lines:
      * form — the substitute's form preserves the source's, via
        `bench/agentpii5/form.py::form_match(engine_type, token, source)`, where
        `source` is the LITERAL text the substitute replaced (the span's
        offsets, not the gold item, which can be a part of a longer span);
      * consistency — the SAME gold value (same `identity`) across the case yields
        ONE token (the vault is per-case via `for_conversation`), plus a
        mask-the-same-thing-twice idempotence check.

Run (from prototype/):
    .venv/bin/python bench/agentpii5/detect_sweep.py [corpus.v5.json ...]
    .venv/bin/python bench/agentpii5/detect_sweep.py --out-dir <dir>   # sweep.out + GATE.json
    .venv/bin/python bench/agentpii5/detect_sweep.py --limit 20        # smoke

This file is the measurement; it touches NO engine file.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

DEFAULT_PATHS = ["bench/agentpii5/corpus.v5.json",
                 "bench/agentpii5/v6/corpus.v5.json"]

# The separators the sweep normalises away, exactly the set the spec names
# (`.` `:` `,` `/` and whitespace). Case is folded too: the registry's own
# notation section prints MAC lowercase and the engine emits uppercase, and a
# comparison that cannot tell one identity from the other is measuring case.
_SEP_RE = re.compile(r"[.:,/\s\u00a0]+")


def norm(value: str) -> str:
    """Separator-stripped, case-folded comparison key."""
    return _SEP_RE.sub("", value or "").lower()


def val_match(gold: str, pred: str) -> bool:
    """The value-level match. Equality after normalisation, or containment in
    either direction — a gold value inside a longer detected span (and vice
    versa) is the same identity seen at different granularity. Kept identical in
    direction to the first version's `gval in pval or pval in gval`, only with
    the normalising fold added; an empty side never matches."""
    ng, np_ = norm(gold), norm(pred)
    if not ng or not np_:
        return False
    return ng == np_ or ng in np_ or np_ in ng


def covers(gold: str, pred: str) -> bool:
    """The STRICT masking question: the detected span covers the whole gold
    value (equality after normalisation, or the gold inside the span). The
    other direction — a gold value longer than the span — is a PARTIAL mask
    (OSAGO «НИЩ 8821179648» found only as the PHONE «8821179648») and is
    reported as `honest` but never as `full`."""
    ng, np_ = norm(gold), norm(pred)
    if not ng or not np_:
        return False
    return ng == np_ or ng in np_


def load_frame(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    return d["corpus"] if isinstance(d, dict) and "corpus" in d else d


def _string_leaves(obj, prefix=""):
    """Every string leaf of a JSON-ish object, with a readable path."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _string_leaves(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _string_leaves(v, f"{prefix}[{i}]")
    elif isinstance(obj, str):
        yield prefix, obj


def _accepted_labels():
    """gold type -> the set of engine labels that count as TYPED-CORRECT.

    The registry is the single home of the mapping (`engine_labels`), never a
    literal here. Direction: a gold id is typed-correct under its own label and
    under any label the registry declares as the engine's label for it. A v5
    record declares no labels, so its set is `{id}` and old behaviour holds."""
    from bench.agentpii5.pii_types import TYPE_REGISTRY
    accepted = {}
    for spec in TYPE_REGISTRY:
        accepted[spec.id] = frozenset({spec.id}) | frozenset(spec.engine_labels)
    return accepted


def _gold_universe(corpus):
    out = set()
    for c in corpus:
        for e in c["base"].get("pii", []):
            out.add(e["type"])
    return out


class HopScan:
    """What the declared hop content is, measured once per corpus."""

    def __init__(self):
        self.cases_with_hop_text = 0
        self.hop_leaves = 0
        self.hop_leaves_textlike = 0
        self.non_user_non_system_messages = 0
        self.forced_cases = 0
        self.expects_cases = 0
        self.hop_present = 0          # gold value literally found in hop content
        self.fallback_first_user = 0  # no hop presence -> scored on first user turn
        self.absent = 0               # not even on the first user turn
        self.later_user_only = 0      # present on a LATER user turn, not the first
        self.hop_samples = []         # the text-like leaves, so the reader sees them

    def as_dict(self):
        return dict(self.__dict__)


def _hop_sources(case):
    """The declared hop content carrying TEXT: non-user/non-system messages plus
    every string leaf of the case's declaration fields. Values are returned raw;
    whether a leaf is 'message text' is decided by whether it carries a gold
    value, never by a guess about which field 'looks like' content.

    `hops`/`expects`/`forced` are what the spec names. The other declaration
    fields (`document`, `rag`, `pick`, `memory`, `loop`, `branch`, `returns`)
    are scanned too, so the «the hops carry no text» claim is a property of the
    WHOLE frame and not of the three fields someone remembered to look at."""
    out = []
    msgs = case["base"].get("messages", [])
    for i, m in enumerate(msgs):
        role = m.get("role")
        if role in ("user", "system"):
            continue
        content = m.get("content")
        if isinstance(content, str) and content.strip():
            out.append((f"msg[{i}]:{role}", content))
    for field in ("hops", "expects", "forced", "document", "rag", "pick",
                  "memory", "loop", "branch", "returns"):
        for path, s in _string_leaves(case.get(field)):
            if s.strip():
                label = f"{field}{path}" if path.startswith("[") else f"{field}.{path}"
                out.append((label, s))
    return out


def _hop_leaf_count(case):
    """Non-message string leaves of the declaration fields — the 'declared hop
    content' proper, as opposed to any assistant/tool turn."""
    n = 0
    for field in ("hops", "expects", "forced", "document", "rag", "pick",
                  "memory", "loop", "branch", "returns"):
        n += sum(1 for _, s in _string_leaves(case.get(field)) if s.strip())
    return n


def _hop_message_count(case):
    return sum(1 for m in case["base"].get("messages", [])
               if m.get("role") not in ("user", "system")
               and isinstance(m.get("content"), str) and m["content"].strip())


_WORD = r"0-9a-z\u0430-\u044f\u0451"


def _present_in(value: str, text: str) -> bool:
    """Does this gold value appear in this text?

    Normalised containment alone is not enough: «кирилл» sits inside
    «кириллицей», and the first version's plain substring test scored that as
    the seed NAME being present in a `forced` message_template. So containment
    must be a WHOLE TOKEN — unless the gold itself carries separators the text
    may spell differently (MAC `fc:f3:…` vs `FCF3…`, FSSP `842899/97/…`), in
    which case the normalised form decides. This is the same distinction the
    recall comparison makes, applied to «is it here at all»."""
    ng = norm(value)
    if not ng or ng not in norm(text):
        return False
    if _SEP_RE.search(value):
        return True
    return re.search(rf"(?<![{_WORD}]){re.escape(value)}(?![{_WORD}])",
                     text, re.IGNORECASE) is not None


def _classify_non_message(case, scan, hop_sources):
    """Bucket the non-message items of ONE case and return, per item id, the
    (label, text) it must be scored against — the hop leaf that carries it, else
    the first user turn, else None (absent from every scanned text)."""
    msgs = case["base"].get("messages", [])
    user_idx = [i for i, m in enumerate(msgs)
                if m.get("role") == "user" and isinstance(m.get("content"), str)]
    first_idx = user_idx[0] if user_idx else None
    first_text = msgs[first_idx]["content"] if first_idx is not None else ""
    later = [msgs[i]["content"] for i in user_idx[1:]]
    hop_norm = [(lab, text, norm(text)) for lab, text in hop_sources]
    if hop_sources:
        scan.cases_with_hop_text += 1
    out = {}
    for e in case["base"].get("pii", []):
        if e.get("where", {}).get("kind") == "message":
            continue
        gv = e["value"]
        ng = norm(gv)
        if not ng:
            out[e["id"]] = None
            continue
        where = None
        for lab, text, nt in hop_norm:
            if nt and ng in nt and _present_in(gv, text):
                where = (lab, text)
                scan.hop_present += 1
                break
        if where is None:
            if _present_in(gv, first_text):
                where = (f"first_user[{first_idx}]", first_text)
                scan.fallback_first_user += 1
            else:
                where = None
                if any(_present_in(gv, t) for t in later):
                    scan.later_user_only += 1
                scan.absent += 1
        out[e["id"]] = where
    return first_idx, out


def _score(gtype, gval, preds, accepted):
    """Return (exact, typed, honest, best_span). `best_span` is the span whose
    token and form are judged in (c), and it is only ever a span that COVERS the
    whole gold value — judging the form of a partial mask against the full source
    would blame the engine for the sweep's own overlap semantics."""
    exact = typed = honest = False
    best = None
    best_rank = -1
    for span in preds:
        if not val_match(gval, span.value):
            continue
        honest = True
        lab = span.entity_type
        is_typed = lab in accepted.get(gtype, frozenset({gtype}))
        if is_typed:
            typed = True
        if lab == gtype:
            exact = True
        if not covers(gval, span.value):
            continue
        rank = 2 if is_typed else 1
        if rank > best_rank:
            best, best_rank = span, rank
    if not honest:
        return False, False, False, None
    return exact, typed, True, best


def sweep(corpus, detector, label, vault, form_match, tokenize_span, accepted,
          limit=None):
    cases = corpus if limit is None else corpus[:limit]
    # per type
    gt = defaultdict(int)
    exact_hits = defaultdict(int)
    typed_hits = defaultdict(int)
    honest_hits = defaultdict(int)
    full_hits = defaultdict(int)
    partial_only = defaultdict(int)
    # message-level only (the number the G7 doc compares against)
    msg_gt = 0
    msg_exact = msg_typed = msg_honest = msg_full = 0
    # precision (label-aware), message-level gold only
    typed_total = defaultdict(int)
    typed_correct = defaultdict(int)
    # (c)
    form_pass = defaultdict(int)
    form_total = defaultdict(int)
    form_na = defaultdict(int)
    form_differs = Counter()
    msg_gold_by_msg = defaultdict(list)   # mi -> [(type, value)]
    # (a2) honest hits whose engine label the registry does NOT declare for the
    # gold type: the desync the `engine_labels` mapping was supposed to cover and
    # does not. Kept because it is the difference between «typed 0%» and «typed
    # 0% for a reason we can name».
    desync = defaultdict(lambda: defaultdict(int))
    mapped_via_declared = defaultdict(int)
    # The denominator, stated: a gold item whose declared text is not in this
    # frame at all cannot be scored by any detector, and counting it as a miss
    # turns the sweep into a count of the frame's own gaps.
    unscored = defaultdict(int)
    scored = defaultdict(int)
    # The domain of types this corpus is allowed to predict: a prediction of a
    # type the corpus never labels is not this sweep's business (the first
    # version's `if p not in gt` guard, precomputed so it is complete).
    type_universe = {e["type"] for c in cases for e in c["base"].get("pii", [])}
    type_universe |= {lab for t in type_universe
                      for lab in accepted.get(t, frozenset({t}))}

    scan = HopScan()
    for c in cases:
        case = c["base"]
        msgs = case.get("messages", [])
        items = case.get("pii", [])
        cid = case.get("conversation_id") or case.get("id") or ""
        view = vault.for_conversation(str(cid))
        det_cache = {}

        def preds_for(key, text):
            if key not in det_cache:
                det_cache[key] = detector.detect(text)
            return det_cache[key]

        hop_sources = _hop_sources(c)
        scan.hop_leaves += _hop_leaf_count(c)
        scan.non_user_non_system_messages += _hop_message_count(c)
        if c.get("forced"):
            scan.forced_cases += 1
        if c.get("expects"):
            scan.expects_cases += 1
        # a declared leaf is 'text-like' if it is not just an id/path/enum token
        for lab, t in hop_sources:
            if len(t.split()) >= 2 or len(t) >= 18:
                scan.hop_leaves_textlike += 1
                if len(scan.hop_samples) < 4 and not lab.startswith("msg["):
                    scan.hop_samples.append(f"{lab} = {t[:90]!r}")

        for e in items:
            w = e.get("where", {})
            if w.get("kind") == "message":
                mi = w.get("msg", -1)
                if isinstance(mi, int) and 0 <= mi < len(msgs) \
                        and isinstance(msgs[mi].get("content"), str):
                    msg_gold_by_msg[mi].append((e["type"], e["value"]))
                continue

        # --- score every gold occurrence -------------------------------------------------
        first_idx, nonmsg_where = _classify_non_message(c, scan, hop_sources)
        occurrences = []   # (item_id, gtype, gval, preds, source_label)
        for e in items:
            w = e.get("where", {})
            kind = w.get("kind")
            gtype, gval = e["type"], e["value"]
            gt[gtype] += 1
            preds = None
            if kind == "message":
                mi = w.get("msg", -1)
                if not (isinstance(mi, int) and 0 <= mi < len(msgs)):
                    unscored[gtype] += 1
                    continue
                content = msgs[mi].get("content")
                if not isinstance(content, str):
                    unscored[gtype] += 1
                    continue
                preds = preds_for(("msg", mi), content)
                src = f"msg[{mi}]"
                src_text = content
            else:
                where = nonmsg_where.get(e["id"])
                if where is None:
                    unscored[gtype] += 1
                    continue  # no hop presence and not on the first user turn
                src, src_text = where
                preds = preds_for(("text", src), src_text)
            scored[gtype] += 1
            exact, typed, honest, best = _score(gtype, gval, preds, accepted)
            if exact:
                exact_hits[gtype] += 1
            if typed:
                typed_hits[gtype] += 1
            if honest:
                honest_hits[gtype] += 1
            is_full = any(covers(gval, s.value) for s in preds)
            if is_full:
                full_hits[gtype] += 1
            elif honest:
                partial_only[gtype] += 1
            if kind == "message":
                msg_gt += 1
                msg_exact += 1 if exact else 0
                msg_typed += 1 if typed else 0
                msg_honest += 1 if honest else 0
                msg_full += 1 if is_full else 0
            if typed and not exact:
                mapped_via_declared[gtype] += 1
            if honest and not typed and best is not None:
                desync[gtype][best.entity_type] += 1
            if best is not None:
                # The LITERAL text the substitute replaced — what form_match's
                # `reference` means. The gold item can be a PART of a longer
                # detected span (18 of 4 396 v5 mentions), and judging the whole
                # token's form against the part would blame the engine for the
                # detector's span, not for its own substitute.
                literal = src_text[best.start:best.end]
                occurrences.append((e.get("identity") or e["id"], gtype, gval,
                                    e.get("canonical") or "", best, literal, src))

        # --- precision: typed predictions on user messages vs message-level gold --------
        for mi, preds in list(det_cache.items()):
            if not (isinstance(mi, tuple) and mi[0] == "msg"):
                continue
            mi_idx = mi[1]
            if not (isinstance(mi_idx, int) and 0 <= mi_idx < len(msgs)):
                continue
            gold_here = msg_gold_by_msg.get(mi_idx, [])
            for span in preds:
                ptype = span.entity_type
                if ptype not in type_universe:
                    continue
                typed_total[ptype] += 1
                ok = any(ptype in accepted.get(gtype, frozenset({gtype}))
                         and val_match(gval, span.value)
                         for gtype, gval in gold_here)
                if ok:
                    typed_correct[ptype] += 1

        # --- (c) form + consistency, over the found occurrences of THIS case ------------
        tokens_by_identity = defaultdict(list)
        for ident, gtype, gval, canonical, span, literal, src in occurrences:
            et = span.entity_type
            tok1 = tokenize_span(span, view)
            tok2 = tokenize_span(span, view)
            consistency_mask2_total[0] += 1
            if tok1 == tok2:
                consistency_mask2_pass[0] += 1
            try:
                verdict = form_match(et, tok1, literal)
            except ValueError:
                # The engine's own label is not a registry type (EPTS, OGRN,
                # ACCOUNT, VEHICLE_DOC ...), so no form table speaks for it.
                # Counted separately, never as a failure: a line that cannot
                # fail on a type it cannot judge is not a line.
                form_na[et] += 1
            else:
                form_total[et] += 1
                if verdict.same:
                    form_pass[et] += 1
                else:
                    for feature in verdict.differs:
                        form_differs[feature] += 1
            if tok1:
                # The VALUE's own identity: the corpus's `canonical` when it has
                # one (it collapses «+7 916…», «8-916…», «8916…» to one string),
                # else the separator-normalised surface. Grouping on the raw
                # surface would call two notations of one phone two identities.
                tokens_by_identity[(ident, norm(canonical or gval))].append(tok1)

        for key, toks in tokens_by_identity.items():
            if len(toks) >= 2:
                consistency_total[0] += 1
                if len(set(toks)) == 1:
                    consistency_pass[0] += 1
            else:
                consistency_single[0] += 1

    # --- print ------------------------------------------------------------------------
    tot_gt = sum(gt.values())
    tot_exact = sum(exact_hits.values())
    tot_typed = sum(typed_hits.values())
    tot_honest = sum(honest_hits.values())
    tot_full = sum(full_hits.values())
    tot_partial = sum(partial_only.values())
    tot_scored = sum(scored.values())
    tot_unscored = sum(unscored.values())
    tot_honest_scored = sum(honest_hits[t] for t in scored)
    tot_tt = sum(typed_total.values())
    tot_tc = sum(typed_correct.values())

    print(f"\n=== {label} ===")
    print("GOLD = every item the corpus labels, scored on its declared text "
          "(message OR the (b) hop/fallback path).")
    print("exact = same label | typed = label or declared engine_labels | "
          "honest = masked under ANY label (overlap) | full = span covers the "
          "whole gold value. `scored` = items whose declared text is in frame; "
          "the percentages divide by GT, so an unscored item reads as a miss.")
    print(f"{'TYPE':<24}{'GT':>6}{'scored':>7}{'exact':>9}{'typed':>9}"
          f"{'honest':>9}{'full':>9}{'prec':>9}")
    for t in sorted(gt):
        n = gt[t]
        print(f"{t:<24}{n:>6}{scored[t]:>7}{exact_hits[t]/n:>8.1%}"
              f"{typed_hits[t]/n:>9.1%}"
              f"{honest_hits[t]/n:>9.1%}{full_hits[t]/n:>9.1%}"
              f"{(typed_correct[t]/typed_total[t] if typed_total[t] else 0):>9.1%}")
    print(f"{'OVERALL (all gold)':<24}{tot_gt:>6}{tot_scored:>7}"
          f"{tot_exact/tot_gt:>8.1%}"
          f"{tot_typed/tot_gt:>9.1%}{tot_honest/tot_gt:>9.1%}"
          f"{tot_full/tot_gt:>9.1%}"
          f"{(tot_tc/tot_tt if tot_tt else 0):>9.1%}")
    print(f"  counts: exact {tot_exact}/{tot_gt}, typed {tot_typed}/{tot_gt}, "
          f"honest {tot_honest}/{tot_gt}, full {tot_full}/{tot_gt}, "
          f"prec {tot_tc}/{tot_tt}")
    print(f"  honest-but-PARTIAL (gold masked only in part by a shorter span, "
          f"never counted as `full`, never form-judged): {tot_partial}" +
          ("  " + ", ".join(
              f"{t}:{n}" for t, n in sorted(partial_only.items(),
                                            key=lambda kv: -kv[1])[:10])
           if tot_partial else ""))
    print(f"OVERALL (message-level only, G7 doc's denominator)   "
          f"GT {msg_gt}  exact {msg_exact/msg_gt:.1%}  typed {msg_typed/msg_gt:.1%}  "
          f"honest {msg_honest/msg_gt:.1%}  full {msg_full/msg_gt:.1%}")
    print(f"SCORED DENOMINATOR: {tot_scored}/{tot_gt} gold items have their "
          f"declared text in this frame; {tot_unscored} are absent (no scanned "
          f"text carries them) and count as misses under the fallback rule.")
    print(f"HONEST RECALL over the SCORED denominator: "
          f"{tot_honest_scored}/{tot_scored} = "
          f"{(tot_honest_scored/tot_scored if tot_scored else 0):.1%}")

    via_declared_total = sum(mapped_via_declared.values())
    print(f"  typed-correct ONLY because the registry declares the engine label: "
          f"{via_declared_total}  " + ", ".join(f"{t}:{n}" for t, n in
                                sorted(mapped_via_declared.items(),
                                       key=lambda kv: -kv[1])[:10]))
    print("  label desync NOT covered by engine_labels (gold type -> emitted "
          "label: honest hits that stay typed-misses):")
    for t in sorted(desync, key=lambda t: -sum(desync[t].values())):
        pairs = ", ".join(f"{lab}:{n}" for lab, n in
                          sorted(desync[t].items(), key=lambda kv: -kv[1]))
        print(f"    {t:<24} {pairs}")

    print("\n--- (b) GENERATED HOPS ---")
    d = scan.as_dict()
    print(f"  declared string leaves scanned "
          f"(hops/expects/forced/document/rag/pick/memory/loop/branch/returns): "
          f"{d['hop_leaves']} ({d['hop_leaves_textlike']} text-like); "
          f"non-user/non-system messages carrying text: "
          f"{d['non_user_non_system_messages']}")
    print(f"  cases with declared hop content: {d['cases_with_hop_text']}; "
          f"expects non-null: {d['expects_cases']}; forced non-null: "
          f"{d['forced_cases']}")
    print(f"  non-message gold scored IN hop content: {d['hop_present']}")
    print(f"  non-message gold scored on FALLBACK first user turn: "
          f"{d['fallback_first_user']}")
    print(f"  non-message gold on a LATER user turn only (unscored by the rule): "
          f"{d['later_user_only']}")
    print(f"  non-message gold absent from every scanned text: {d['absent']}"
          f"  (of which later-turn-only: {d['later_user_only']})")
    if scan.hop_samples:
        print("  text-like DECLARED leaves seen (tool names/paths/templates — "
              "none carries a gold value):")
        for s in scan.hop_samples:
            print(f"    {s}")

    print("\n--- (c) FORM ---")
    ft = sum(form_total.values())
    fp = sum(form_pass.values())
    fna = sum(form_na.values())
    print(f"FORM PASS (substitute preserves the form of the LITERAL source it "
          f"replaced, engine type): "
          f"{fp}/{ft} = {fp/ft if ft else 0:.1%}   "
          f"(no form features declared for the engine label: {fna})")
    if ft:
        worst = sorted((t for t in form_total),
                       key=lambda t: form_pass[t] / form_total[t])[:8]
        print("  worst types: " + ", ".join(
            f"{t} {form_pass[t]}/{form_total[t]}" for t in worst))
        print("  features that differ most (count of failing occurrences): " +
              ", ".join(f"{f}:{n}" for f, n in
                        form_differs.most_common(8)))

    print("\n--- (c) CONSISTENCY ---")
    ct, cp = consistency_total[0], consistency_pass[0]
    print(f"CONSISTENCY PASS (one token per (identity, canonical value) with >=2 "
          f"found occurrences in the case): {cp}/{ct} = {cp/ct if ct else 0:.1%}"
          f"   (groups with a single occurrence: {consistency_single[0]})")
    m2_total, m2_pass = consistency_mask2_total[0], consistency_mask2_pass[0]
    print(f"CONSISTENCY MASK-TWICE (same span tokenized twice -> one token): "
          f"{m2_pass}/{m2_total} = {m2_pass/m2_total if m2_total else 0:.1%}")

    return {
        "cases": len(cases),
        "gold_all": tot_gt,
        "gold_message": msg_gt,
        "exact": {"hit": tot_exact, "total": tot_gt,
                  "rate": tot_exact / tot_gt if tot_gt else 0.0},
        "typed": {"hit": tot_typed, "total": tot_gt,
                  "rate": tot_typed / tot_gt if tot_gt else 0.0},
        "honest": {"hit": tot_honest, "total": tot_gt,
                   "rate": tot_honest / tot_gt if tot_gt else 0.0},
        "scored": {"scored": tot_scored, "unscored_absent_from_frame": tot_unscored,
                   "honest_over_scored": tot_honest_scored,
                   "honest_over_scored_rate": (tot_honest_scored / tot_scored
                                               if tot_scored else 0.0)},
        "honest_full": {"hit": tot_full, "total": tot_gt,
                        "rate": tot_full / tot_gt if tot_gt else 0.0},
        "honest_partial_only": {"hit": tot_partial, "total": tot_gt,
                                "rate": tot_partial / tot_gt if tot_gt else 0.0,
                                "by_type": {t: partial_only[t] for t in partial_only}},
        "message_only": {
            "gold": msg_gt,
            "exact": msg_exact / msg_gt if msg_gt else 0.0,
            "typed": msg_typed / msg_gt if msg_gt else 0.0,
            "honest": msg_honest / msg_gt if msg_gt else 0.0,
            "full": msg_full / msg_gt if msg_gt else 0.0},
        "typed_via_declared_engine_labels": via_declared_total,
        "label_desync": {t: dict(sorted(desync[t].items(), key=lambda kv: -kv[1]))
                         for t in sorted(desync)},
        "precision": {"correct": tot_tc, "total": tot_tt,
                      "rate": tot_tc / tot_tt if tot_tt else 0.0},
        "hops": d,
        "form": {"pass": fp, "total": ft, "no_features": fna,
                 "rate": fp / ft if ft else 0.0,
                 "features_differs": dict(form_differs.most_common()),
                 "by_type": {t: {"pass": form_pass[t], "total": form_total[t]}
                             for t in sorted(form_total)}},
        "consistency": {
            "groups_pass": cp, "groups_total": ct,
            "rate": cp / ct if ct else 0.0,
            "single_occurrence_groups": consistency_single[0],
            "mask2_pass": m2_pass, "mask2_total": m2_total,
            "mask2_rate": m2_pass / m2_total if m2_total else 0.0},
        "per_type": {t: {"gt": gt[t], "scored": scored[t], "unscored": unscored[t],
                         "exact": exact_hits[t],
                         "typed": typed_hits[t], "honest": honest_hits[t],
                         "full": full_hits[t]}
                     for t in sorted(gt)},
    }


# Process-wide counters for the (c) section (the sweep is single-threaded; these
# keep `sweep()`'s signature from growing a fourth accumulator).
consistency_total = [0]
consistency_pass = [0]
consistency_single = [0]
consistency_mask2_total = [0]
consistency_mask2_pass = [0]


def _reset_counters():
    for c in (consistency_total, consistency_pass, consistency_single,
              consistency_mask2_total, consistency_mask2_pass):
        c[0] = 0


class _Tee:
    """stdout that also lands in sweep.out, so the FILE is the whole report and
    not the few lines someone remembered to route through `emit`."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, text):
        for s in self._streams:
            s.write(text)
        return len(text)

    def flush(self):
        for s in self._streams:
            s.flush()


def _git(args):
    try:
        return subprocess.run(["git", "-C", str(Path(__file__).resolve().parents[3])] + args,
                              capture_output=True, text=True, check=False).stdout.strip()
    except Exception:
        return ""


# WHAT THE NUMBERS WERE MEASURED ON. This worktree is shared and the engine
# files may be mid-edit while the sweep runs; a recall figure without the exact
# revision (and without proof it did not move under the sweep) is not a
# measurement. The digest covers the engine plus the registry/form tables the
# scoring reads.
_DIGEST_ROOTS = ("pseudex", "licensing",
                 "bench/agentpii5/pii_types.py", "bench/agentpii5/pii_types_a.py",
                 "bench/agentpii5/pii_types_b.py", "bench/agentpii5/pii_types_c.py",
                 "bench/agentpii5/form.py", "bench/agentpii5/contracts.py")


def _digest(root: Path):
    h = hashlib.sha256()
    files = []
    for rel in _DIGEST_ROOTS:
        p = root / rel
        if p.is_dir():
            files.extend(sorted(f for f in p.rglob("*.py")))
        elif p.exists():
            files.append(p)
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(f.read_bytes())
    return h.hexdigest(), len(files)


def _revision():
    root = Path(__file__).resolve().parents[2]
    digest, n = _digest(root)
    return {"git_head": _git(["rev-parse", "HEAD"]),
            "git_branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "git_status_porcelain": _git(["status", "--porcelain"]).splitlines(),
            "engine_digest": digest,
            "engine_files_hashed": n}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", default=None)
    ap.add_argument("--out-dir", default=None,
                    help="write <dir>/sweep.out and <dir>/GATE.json")
    ap.add_argument("--limit", type=int, default=None,
                    help="score only the first N cases (smoke run)")
    args = ap.parse_args(argv)

    from testkit import load_dev_bundle
    load_dev_bundle()
    from pseudex.detect_all import Detector
    from pseudex.vault import Vault
    from pseudex.redact import tokenize_span
    from bench.agentpii5.form import form_match

    accepted = _accepted_labels()
    detector = Detector()
    vault = Vault(":memory:", "agentpii5-detect-sweep")
    paths = args.paths or DEFAULT_PATHS

    revision_before = _revision()
    report = {"tool": "prototype/bench/agentpii5/detect_sweep.py",
              "mode": "honest+complete: (a) exact/typed/honest recall, "
                      "(b) generated hops + fallback, (c) form + consistency",
              "git_head": revision_before["git_head"],
              "git_branch": revision_before["git_branch"],
              "revision_before": revision_before,
              "corpora": {}}

    out_file = None
    if args.out_dir:
        d = Path(args.out_dir)
        d.mkdir(parents=True, exist_ok=True)
        out_file = open(d / "sweep.out", "w", encoding="utf-8")
        sys.stdout = _Tee(sys.__stdout__, out_file)

    def emit(*a):
        # stdout is teed, so a plain print reaches console AND sweep.out.
        print(*a)

    emit(f"detect_sweep honest+complete  head={report['git_head'][:12]} "
         f"branch={report['git_branch']}")
    emit(f"engine digest (before) {revision_before['engine_digest'][:16]} over "
         f"{revision_before['engine_files_hashed']} files; dirty files: "
         f"{len(revision_before['git_status_porcelain'])}")
    emit("note: this file scores gold items; it changes no engine file.")

    for p in paths:
        path = Path(p)
        if not path.exists():
            emit(f"skip (missing): {path}")
            continue
        corpus = load_frame(path)
        _reset_counters()
        result = sweep(corpus, detector, path.name, vault, form_match,
                       tokenize_span, accepted, limit=args.limit)
        result["path"] = str(path)
        key = "v6" if "v6" in str(path) else "v5"
        report["corpora"][key] = result

    if args.out_dir:
        revision_after = _revision()
        report["revision_after"] = revision_after
        report["engine_stable_during_run"] = (
            revision_after["engine_digest"] == revision_before["engine_digest"]
            and revision_after["git_head"] == revision_before["git_head"])
        emit(f"engine digest (after) {revision_after['engine_digest'][:16]}; "
             f"stable during run: {report['engine_stable_during_run']}")
        # The gate verdicts, each on a NAMED denominator — a bare «PASS» over a
        # denominator nobody wrote down is how the first sweep reported 57.8%
        # and the doc read it as a detector number.
        gate = {}
        for key, r in report["corpora"].items():
            gate[key] = {
                "G7_threshold": 0.99,
                "honest_message_only": r["message_only"]["honest"],
                "honest_over_scored": r["scored"]["honest_over_scored_rate"],
                "honest_all_gold": r["honest"]["rate"],
                "exact_message_only": r["message_only"]["exact"],
                "typed_message_only": r["message_only"]["typed"],
                "form": r["form"]["rate"],
                "consistency": r["consistency"]["rate"],
                "consistency_mask2": r["consistency"]["mask2_rate"],
                "gold_message": r["message_only"]["gold"],
                "gold_all": r["gold_all"],
                "gold_scored": r["scored"]["scored"],
                "gold_unscored_absent_from_frame":
                    r["scored"]["unscored_absent_from_frame"],
                "G7_message_only": "PASS" if r["message_only"]["honest"] >= 0.99
                                   else "FAIL",
                "G7_over_scored": "PASS" if r["scored"]["honest_over_scored_rate"] >= 0.99
                                  else "FAIL",
            }
        report["gate"] = gate
        for key, g in gate.items():
            emit(f"\nGATE {key}:  G7 threshold 99.0% honest recall")
            emit(f"  message-only honest  {g['honest_message_only']:.1%}  -> "
                 f"{g['G7_message_only']}  (exact {g['exact_message_only']:.1%}, "
                 f"typed {g['typed_message_only']:.1%})")
            emit(f"  over SCORED gold     {g['honest_over_scored']:.1%}  -> "
                 f"{g['G7_over_scored']}  ({g['gold_scored']}/{g['gold_all']} "
                 f"items have text in frame)")
            emit(f"  all-gold honest      {g['honest_all_gold']:.1%}  "
                 f"(denominator includes {g['gold_unscored_absent_from_frame']} "
                 f"items no scanned text carries)")
            emit(f"  form                 {g['form']:.1%}")
            emit(f"  consistency          {g['consistency']:.1%}   "
                 f"mask-twice {g['consistency_mask2']:.1%}")
        report["caveats"] = [
            "The corpus frame carries no generated assistant/tool/answer text: "
            "base.messages is system+user only, `hops` is item ids and JSON "
            "paths, `expects` is null everywhere, `forced` carries a {value} "
            "template. Every kind!=message gold item is therefore scored on the "
            "(b) fallback, the FIRST user turn, when its value is there at all. "
            "The scan covers document/rag/pick/memory/loop/branch/returns too, "
            "so this is a property of the frame, not of three fields.",
            "`honest_all_gold` divides by items whose text the frame does not "
            "carry; read `honest_over_scored` for the detector and "
            "`unscored_absent_from_frame` for the frame's own gap.",
            "`form` is judged only on gold items the engine masked IN FULL and "
            "whose emitted label has a registry form table; the reference is the "
            "literal text the substitute replaced. Partial masks and engine-only "
            "labels are reported separately, never as failures.",
            "`consistency` covers (identity, canonical value) groups with >=2 "
            "found occurrences in one case; single occurrences cannot disagree.",
            ("engine digest STABLE during the run: the numbers describe one "
             "revision (see revision_before)." if report["engine_stable_during_run"]
             else "ENGINE MOVED DURING THE RUN (digest changed): these numbers "
                  "describe no single revision and must be re-run."),
        ]
        emit("\nCAVEATS (also GATE.json):")
        for cv in report["caveats"]:
            emit(f"  - {cv}")
        sys.stdout = sys.__stdout__
        if out_file is not None:
            out_file.close()
        gate_path = Path(args.out_dir) / "GATE.json"
        gate_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        # echo the gate path on the console (not into sweep.out)
        print(f"\nwrote {gate_path} and {Path(args.out_dir) / 'sweep.out'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
