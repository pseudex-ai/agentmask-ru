#!/usr/bin/env python3
"""A1 read-only inventory of existing dataset sources for the O-DATA acceptance manifest.

What this script does NOT do:
  * it never imports the detector, never loads a bundle, never masks anything;
  * it never reads a detector prediction, eval result, score, hop or judge artifact;
  * it never writes outside its own directory and never mutates a source file.

Everything counted here is *case definition / gold label / raw external annotation*
material that already exists on this host.  Every source is hashed before use so a
later reader can prove which revision the counts belong to.

Run (from the repository root):
    PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python \
        research/quality-sprint-2026-09-30/work/A1/inventory_sources.py
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/Users/igor/Projects/Obscura-hop-audit")
OUT_DIR = ROOT / "research/quality-sprint-2026-09-30/work/A1"
CACHE = Path.home() / ".cache" / "pseudex-bench"
VENDORED = ROOT / "research/hop-format-audit/detection-status-2026-09-30/external/dependencies"

# Parquet reader: vendored pyarrow of the B0-verified dependency snapshot.  No install.
if VENDORED.exists():
    sys.path.insert(0, str(VENDORED))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_record(path: Path, notes: str = "") -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False, "notes": notes}
    return {
        "path": str(path),
        "exists": True,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "notes": notes,
    }


def corpus_case_base(case: dict) -> dict:
    """agentpii5 v5 corpus nests the case under 'base'; the frozen run corpus is flat."""
    return case["base"] if isinstance(case.get("base"), dict) else case


def summarize_agent_corpus(path: Path, notes: str) -> dict:
    """Count gold PII units of a frozen agent-corpus file. No detector involved."""
    doc = json.loads(path.read_text())
    cases = doc["corpus"] if isinstance(doc, dict) and "corpus" in doc else doc
    per_type = collections.Counter()
    per_type_identities: dict[str, set] = collections.defaultdict(set)
    per_type_cases: dict[str, set] = collections.defaultdict(set)
    per_type_registers = collections.Counter()
    per_type_kinds = collections.Counter()
    register_type_ident: dict[str, set] = collections.defaultdict(set)
    register_type_items = collections.Counter()
    kind_type_items = collections.Counter()
    kind_type_ident: dict[str, set] = collections.defaultdict(set)
    shapes: set = set()
    registers = collections.Counter()
    kinds = collections.Counter()
    negatives = 0
    negative_types = collections.Counter()
    clusters: set = set()
    conversations: set = set()
    case_ids: set = set()
    for case in cases:
        base = corpus_case_base(case)
        cid = base.get("id")
        reg = base.get("register")
        kind = base.get("kind")
        clusters.add(base.get("cluster"))
        conversations.add(base.get("conversation_id"))
        case_ids.add(cid)
        registers[reg] += 1
        kinds[kind] += 1
        shape = (base.get("provenance") or {}).get("shape") or ""
        if shape:
            shapes.add(shape)
        for item in base.get("pii") or []:
            t = item.get("type")
            ident = item.get("identity")
            per_type[t] += 1
            per_type_identities[t].add(ident)
            per_type_cases[t].add(cid)
            per_type_registers[f"{t}|{reg}"] += 1
            per_type_kinds[f"{t}|{kind}"] += 1
            register_type_items[f"{reg}|{t}"] += 1
            register_type_ident[f"{reg}|{t}"].add(ident)
            kind_type_items[f"{kind}|{t}"] += 1
            kind_type_ident[f"{kind}|{t}"].add(ident)
        for neg in base.get("negatives") or []:
            negatives += 1
            if isinstance(neg, dict):
                negative_types[neg.get("type") or neg.get("kind") or "untyped"] += 1
            else:
                negative_types["untyped"] += 1
    return {
        "path": str(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "notes": notes,
        "cases": len(cases),
        "case_ids_unique": len(case_ids),
        "registers": dict(sorted(registers.items())),
        "kinds": dict(sorted(kinds.items())),
        "clusters_unique": len(clusters),
        "conversations_unique": len(conversations),
        "provenance_shapes_unique": len(shapes),
        "pii_items_total": sum(per_type.values()),
        "pii_identities_unique_total": len(set().union(*per_type_identities.values())) if per_type_identities else 0,
        "per_type": {
            t: {
                "items": per_type[t],
                "unique_identities": len(per_type_identities[t]),
                "cases": len(per_type_cases[t]),
            }
            for t in sorted(per_type)
        },
        "per_type_register_items": dict(sorted(per_type_registers.items())),
        "per_type_kind_items": dict(sorted(per_type_kinds.items())),
        "register_type_items": dict(sorted(register_type_items.items())),
        "register_type_unique_identities": {
            k: len(v) for k, v in sorted(register_type_ident.items())
        },
        "kind_type_items": dict(sorted(kind_type_items.items())),
        "kind_type_unique_identities": {k: len(v) for k, v in sorted(kind_type_ident.items())},
        "negatives_total": negatives,
        "negatives_by_label": dict(sorted(negative_types.items())),
    }


def summarize_legacy_set(path: Path) -> dict:
    doc = json.loads(path.read_text())
    per_type = collections.Counter()
    per_type_cases = collections.defaultdict(set)
    negative_labels = collections.Counter()
    negatives = 0
    quasi = 0
    for i, case in enumerate(doc):
        if not isinstance(case, dict):
            continue
        for ent in case.get("entities") or []:
            t = ent.get("type") if isinstance(ent, dict) else str(ent)
            per_type[t] += 1
            per_type_cases[t].add(i)
        for neg in case.get("negatives") or []:
            negatives += 1
            if isinstance(neg, dict):
                negative_labels[neg.get("type") or neg.get("label") or "untyped"] += 1
            else:
                negative_labels["untyped"] += 1
        quasi += len(case.get("quasi") or [])
    return {
        "path": str(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "cases": len(doc),
        "per_type": {t: {"items": per_type[t], "cases": len(per_type_cases[t])}
                     for t in sorted(per_type)},
        "entities_total": sum(per_type.values()),
        "negatives_total": negatives,
        "negatives_by_label": dict(sorted(negative_labels.items())),
        "quasi_items": quasi,
    }


def summarize_gate_instrument(labels_path: Path, candidates_path: Path) -> dict:
    labels = json.loads(labels_path.read_text())
    out = {
        "labels_path": str(labels_path),
        "labels_sha256": sha256(labels_path),
        "labelled_occurrences": len(labels),
        "label_distribution": dict(sorted(collections.Counter(labels.values()).items())),
        "candidates_path": str(candidates_path),
    }
    if candidates_path.exists():
        cand = json.loads(candidates_path.read_text())
        out["candidates_sha256"] = sha256(candidates_path)
        out["candidates_keys"] = sorted(cand) if isinstance(cand, dict) else None
        occ = cand.get("occurrences") if isinstance(cand, dict) else None
        if isinstance(occ, dict):
            out["candidate_occurrences"] = len(occ)
            out["candidate_occurrences_by_stratum"] = dict(
                sorted(collections.Counter(
                    (v.get("stratum") if isinstance(v, dict) else None) for v in occ.values()
                ).items(), key=lambda kv: str(kv[0]))
            )
        elif isinstance(occ, list):
            out["candidate_occurrences"] = len(occ)
        acc = cand.get("accepted") if isinstance(cand, dict) else None
        if isinstance(acc, dict):
            out["candidate_accepted"] = len(acc)
            out["candidate_accepted_by_stratum"] = dict(
                sorted(collections.Counter(
                    (v.get("stratum") if isinstance(v, dict) else None) for v in acc.values()
                ).items(), key=lambda kv: str(kv[0]))
            )
        utt = cand.get("utterances") if isinstance(cand, dict) else None
        if hasattr(utt, "__len__"):
            out["candidate_utterances"] = len(utt)
    return out


def summarize_nerel(base: Path, splits=("dev", "test")) -> dict:
    out = {}
    for split in splits:
        d = base / split
        if not d.is_dir():
            out[split] = {"exists": False}
            continue
        types = collections.Counter()
        docs = 0
        person_docs = 0
        for ann in sorted(d.glob("*.ann")):
            docs += 1
            has_person = False
            for line in ann.read_text(errors="replace").splitlines():
                if not line or line[0] not in "T":
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                tag = parts[1].split()[0]
                types[tag] += 1
                if tag.upper().startswith("PERSON"):
                    has_person = True
            person_docs += int(has_person)
        out[split] = {
            "exists": True,
            "docs": docs,
            "annotation_rows": sum(types.values()),
            "person_rows": sum(v for k, v in types.items() if k.upper().startswith("PERSON")),
            "docs_with_person": person_docs,
            "top_types": dict(types.most_common(15)),
        }
    return out


def summarize_piibench(data_dir: Path) -> dict:
    import pyarrow.parquet as pq

    out = {}
    for name in ("domain", "entity"):
        f = data_dir / f"{name}-00000-of-00001.parquet"
        if not f.exists():
            out[name] = {"exists": False}
            continue
        table = pq.read_table(f)
        types = collections.Counter()
        row_ids = set()
        rows_with_entities = 0
        for row in table.to_pylist():
            row_ids.add(row.get("id"))
            ents = row.get("entities") or []
            if ents:
                rows_with_entities += 1
            for ent in ents:
                types[ent.get("type")] += 1
        out[name] = {
            "exists": True,
            "path": str(f),
            "sha256": sha256(f),
            "rows": table.num_rows,
            "unique_ids": len(row_ids),
            "rows_with_entities": rows_with_entities,
            "entity_occurrences": sum(types.values()),
            "per_type": dict(sorted(types.items())),
        }
    return out


SLOT = re.compile(r"\[([a-z_]+)\s*:\s*([^\]]+)\]")


def summarize_massive() -> dict:
    import pyarrow.parquet as pq

    out = {}
    for part in ("train", "validation", "test"):
        f = CACHE / f"massive_ru_{part}.parquet"
        if not f.exists():
            out[part] = {"exists": False}
            continue
        table = pq.read_table(f, columns=["utt", "annot_utt"])
        kinds = collections.Counter()
        uniq: dict[str, set] = collections.defaultdict(set)
        rows_with_person = 0
        for utt, annotated in zip(table.column("utt").to_pylist(),
                                   table.column("annot_utt").to_pylist()):
            slots = [(k, v.strip()) for k, v in SLOT.findall(str(annotated))
                     if k in {"person", "place_name", "email_address"}]
            for k, v in slots:
                kinds[k] += 1
                uniq[k].add(v)
            if any(k == "person" for k, _ in slots):
                rows_with_person += 1
        out[part] = {
            "exists": True,
            "path": str(f),
            "sha256": sha256(f),
            "rows": table.num_rows,
            "slot_occurrences": dict(sorted(kinds.items())),
            "slot_unique_values": {k: len(v) for k, v in sorted(uniq.items())},
            "rows_with_person": rows_with_person,
        }
    return out


def summarize_jsonl(path: Path, notes: str = "") -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False, "notes": notes}
    n = 0
    keys: collections.Counter = collections.Counter()
    for line in path.open(errors="replace"):
        line = line.strip()
        if not line:
            continue
        n += 1
        if n <= 200:
            try:
                keys.update(json.loads(line).keys())
            except Exception:
                keys["<unparsed>"] += 1
    return {"path": str(path), "exists": True, "bytes": path.stat().st_size,
            "sha256": sha256(path), "lines_nonempty": n,
            "sample_keys": dict(keys.most_common(10)), "notes": notes}


def summarize_voice(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False}
    doc = json.loads(path.read_text())
    labels = collections.Counter(x.get("label") for x in doc)
    filters = collections.Counter(x.get("filter") for x in doc)
    return {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size,
            "records": len(doc), "label_distribution": dict(sorted(labels.items())),
            "filter_distribution": dict(sorted(filters.items()))}


def summarize_v6() -> dict:
    inv = json.loads((ROOT / "research/hop-format-audit/next-sprint-review/v6-snapshot/"
                      "registry-inventory.json").read_text())
    origins = collections.Counter(e["origin"] for e in inv)
    classes = collections.Counter(e["class"] for e in inv)
    grammar = collections.Counter(e["grammar_status"] for e in inv)
    industries: collections.Counter = collections.Counter()
    for e in inv:
        industries.update(e.get("industries") or [])
    return {
        "registry_entries": len(inv),
        "origins": dict(sorted(origins.items())),
        "classes": dict(sorted(classes.items())),
        "grammar_status": dict(sorted(grammar.items())),
        "industries": dict(sorted(industries.items())),
        "new_v6_types": [e["type"] for e in inv if e["origin"] == "ORIGIN_V6"],
        "v5_types_in_registry": [e["type"] for e in inv if e["origin"] == "ORIGIN_V5"],
        "grammar_uncertain_types": [e["type"] for e in inv if e["grammar_status"] != "ГОТОВ"],
        "generated_v6_cases_on_host": 0,
        "generated_v6_cases_note": (
            "v6 exists as registry/contracts source (branch fad9c746, snapshot copy). "
            "No generated v6 corpus file is present on this host; the 500-case/15-industry "
            "corpus is a plan in tz-agentpii6.md, not a counted population."
        ),
    }


def summarize_git() -> dict:
    def run(args):
        p = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    rc, head, _ = run(["git", "rev-parse", "HEAD"])
    rc2, status, _ = run(["git", "status", "--porcelain"])
    rc3, branch, _ = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return {
        "head": head,
        "head_exit": rc,
        "branch": branch,
        "branch_exit": rc3,
        "porcelain_lines": len(status.splitlines()) if status else 0,
        "status_exit": rc2,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    env = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git": summarize_git(),
        "cwd": os.getcwd(),
    }

    inv: dict = {"environment": env, "sources": [], "notes": []}

    v5 = ROOT / "prototype/bench/agentpii5/corpus.v5.json"
    v5_plain = ROOT / "prototype/bench/agentpii5/corpus.json"
    run_dir = ROOT / "prototype/bench/runs/2026-09-30/v5-sprint-v2-813"
    inv["v5_corpus_1800"] = summarize_agent_corpus(
        v5, "agentpii5 v5 case definitions + gold PII (base-nested). No predictions read.")
    inv["v5_corpus_1800_plain"] = summarize_agent_corpus(
        v5_plain, "agentpii5 corpus.json revision; counted for revision comparison only.")
    inv["run_2026_09_30_813"] = summarize_agent_corpus(
        run_dir / "corpus.json",
        "frozen paid run cc3a551f case definitions (flat). Run outcome artifacts were NOT read.")
    inv["run_dir_files_not_read"] = sorted(
        p.name for p in run_dir.iterdir()
        if p.name not in {"corpus.json", "corpus.v5.json"}
    )

    for name in ("dataset.json", "dirty.json", "stress.json", "stress2.json"):
        inv[f"legacy_{name.replace('.json', '')}"] = summarize_legacy_set(ROOT / "prototype" / name)

    inv["gate_instrument"] = summarize_gate_instrument(
        ROOT / "prototype/bench/gate/labels.json",
        CACHE / "gate_candidates.json",
    )
    inv["voice_addresses"] = summarize_voice(CACHE / "voice_addresses.json")
    inv["rudevices_addresses"] = summarize_voice(CACHE / "rudevices_addresses.json")
    inv["speech_calls"] = summarize_jsonl(CACHE / "speech_calls.jsonl",
                                          "unlabelled real call speech")
    inv["speech_rudevices"] = summarize_jsonl(CACHE / "speech_rudevices.jsonl",
                                              "unlabelled real speech")
    inv["ru_prose"] = file_record(CACHE / "ru_prose.jsonl",
                                  "0 bytes on host => over-masking volume corpus unavailable")
    inv["nerel"] = summarize_nerel(CACHE / "nerel/NEREL-v1.1")
    inv["piibench"] = summarize_piibench(CACHE / "pii-bench/data")
    inv["massive"] = summarize_massive()
    inv["v6_registry"] = summarize_v6()

    cvc_dir = ROOT / "research/quality-sprint-2026-09-30/followup/cvc-context-contract"
    inv["temporary_secrets_prior"] = {
        "context_matrix": file_record(cvc_dir / "CONTEXT-MATRIX.json"),
        "episodes": summarize_jsonl(cvc_dir / "EPISODES.jsonl", "4 CVC divergence episodes"),
        "primary_sources": file_record(cvc_dir / "PRIMARY-SOURCES.md"),
        "probes": sorted(p.name for p in (cvc_dir / "probes").iterdir())
        if (cvc_dir / "probes").is_dir() else [],
    }

    nameprop = ROOT / "research/quality-sprint-2026-09-30/followup/name-labels-blind-proposal"
    inv["name_label_proposal_prior"] = {
        "proposal_counts": json.loads((nameprop / "proposal-counts.json").read_text()),
        "raw_person_slots_lines": summarize_jsonl(nameprop / "person-slots-raw.jsonl"),
        "nerel_person_sample_lines": summarize_jsonl(nameprop / "nerel-person-sample.jsonl"),
        "findings": file_record(nameprop / "FINDINGS.md",
                                "prior AI proposal, explicitly NOT accepted gold"),
        "proposed_labels": file_record(nameprop / "PROPOSED-LABELS.jsonl"),
    }
    inv["name15_prior"] = {
        "findings": file_record(ROOT / "research/quality-sprint-2026-09-30/followup/"
                                "name15-verified/FINDINGS.md"),
        "verified_rows": summarize_jsonl(ROOT / "research/quality-sprint-2026-09-30/followup/"
                                         "name15-verified/VERIFIED-15.jsonl"),
        "extract_summary": file_record(ROOT / "research/quality-sprint-2026-09-30/followup/"
                                       "name15-verified/EXTRACT-SUMMARY.json"),
    }

    for rec in (v5, v5_plain, run_dir / "corpus.json",
                ROOT / "prototype/bench/gate/labels.json",
                CACHE / "gate_candidates.json"):
        inv["sources"].append(file_record(rec))

    out = OUT_DIR / "INVENTORY.json"
    out.write_text(json.dumps(inv, ensure_ascii=False, indent=2, sort_keys=False) + "\n")

    # Human-readable log
    print(f"generated_utc = {env['generated_utc']}")
    print(f"python = {env['python']} ({env['executable']})")
    print(f"git HEAD = {env['git']['head']} branch={env['git']['branch']} "
          f"porcelain_lines={env['git']['porcelain_lines']}")
    print()
    for key, val in inv.items():
        if key in {"environment", "sources", "notes"}:
            continue
        if isinstance(val, dict) and "pii_items_total" in val:
            print(f"[{key}] cases={val['cases']} pii_items={val['pii_items_total']} "
                  f"unique_identities={val['pii_identities_unique_total']} "
                  f"clusters={val['clusters_unique']} convs={val['conversations_unique']} "
                  f"negatives={val['negatives_total']}")
            for t, d in val["per_type"].items():
                print(f"    {t:10s} items={d['items']:6d} unique_identities={d['unique_identities']:6d} "
                      f"cases={d['cases']:5d}")
        elif isinstance(val, dict) and "entities_total" in val:
            print(f"[{key}] cases={val['cases']} entities={val['entities_total']} "
                  f"negatives={val['negatives_total']} quasi={val['quasi_items']} "
                  f"per_type={ {t: v['items'] for t, v in val['per_type'].items()} }")
        elif key == "gate_instrument":
            print(f"[gate] labelled={val['labelled_occurrences']} dist={val['label_distribution']} "
                  f"candidates={val.get('candidate_occurrences')} "
                  f"accepted={val.get('candidate_accepted')} utts={val.get('candidate_utterances')}")
        elif key in {"voice_addresses", "rudevices_addresses"}:
            print(f"[{key}] records={val.get('records')} labels={val.get('label_distribution')}")
        elif key.startswith("speech_") or key == "ru_prose":
            print(f"[{key}] {val.get('lines_nonempty', val.get('bytes'))} "
                  f"exists={val.get('exists')}")
        elif key == "nerel":
            for split, d in val.items():
                print(f"[nerel:{split}] docs={d.get('docs')} rows={d.get('annotation_rows')} "
                      f"person_rows={d.get('person_rows')} docs_with_person={d.get('docs_with_person')}")
        elif key == "piibench":
            for part, d in val.items():
                print(f"[piibench:{part}] rows={d.get('rows')} ids={d.get('unique_ids')} "
                      f"entities={d.get('entity_occurrences')}")
        elif key == "massive":
            for part, d in val.items():
                print(f"[massive:{part}] rows={d.get('rows')} slots={d.get('slot_occurrences')} "
                      f"unique={d.get('slot_unique_values')}")
        elif key == "v6_registry":
            print(f"[v6] entries={val['registry_entries']} origins={val['origins']} "
                  f"grammar={val['grammar_status']} industries={len(val['industries'])} "
                  f"generated_cases_on_host={val['generated_v6_cases_on_host']}")
        else:
            print(f"[{key}] keys={list(val) if isinstance(val, dict) else val}")

    print()
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
