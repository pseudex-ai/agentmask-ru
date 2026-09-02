"""Every diverging triple of a run, one row each, with a root cause.

    python3 bench/agentpii4/autopsy.py bench/runs/<date>/v4-live-small [--out autopsy.md]

The report aggregates; this does the opposite. For each triple where the
gateway arm's typed state differs from the control's, print what the model
WROTE, what the gateway RETURNED, what the mock said, and assign the cause —
by rules that read the recorded data, never by re-running a model. The cause
labels are the known-issues numbers (Б8, Б9, Б10, Б11 …) plus the classes the
engine cannot fix by construction, so the table is a work list, not a score.

Cause rules, first match wins, all on recorded facts:
  control_erred    a field where the gateway restored the corpus canonical and the control did not
  Б8-echo          a lookup tool (address_suggest / crm_find_contact) answered, and the gateway
                   arm stopped there, chose another record, or joined two substitutes
  Б9-span          the gateway arm made no call and the substitute it read has more words than
                   the real name, or its reply asks which words are the name
  Б10-city         the gateway arm asked for the city and the substitute carries none
  validate-refuse  kind == validate and the gateway arm refused to call
  derived-only     every diverging field is `derived`
  residual         a substitute reached the tool
  asks             the gateway arm made no call and none of the above explains it
  other            everything else — read it by hand
"""
import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from bench.agentpii4.compare import Triple, compare_triple, pair_runs  # noqa: E402
from bench.agentpii4.records import arm_from_record  # noqa: E402
from bench.agentpii4.schema import Case, case_from_json  # noqa: E402

LOOKUPS = ("address_suggest", "crm_find_contact")


def _load_run(run_dir: Path) -> tuple[dict[str, Case], list[Triple], list[str]]:
    corpus_path = run_dir / "corpus.json"
    if not corpus_path.exists():
        corpus_path = _HERE.parent / "corpus.json"
    corpus = {c["id"]: case_from_json(c) for c in json.loads(corpus_path.read_text(encoding="utf-8"))["corpus"]}
    arms_file = sorted(glob.glob(str(run_dir / "*.arms.jsonl")))[-1]
    arms = [arm_from_record(json.loads(line)) for line in Path(arms_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    triples, excluded = pair_runs(arms)
    return corpus, triples, excluded


def _cause(case: Case, triple: Triple, fields: list) -> str:
    kinds = Counter(f.kind for f in fields if f.kind != "agree")
    i_tools = [c.name for c in triple.I.calls]
    c_tools = [c.name for c in triple.C.calls]
    reply = triple.I.reply.casefold()
    if kinds and set(kinds) <= {"control_erred"}:
        return "control_erred"
    if kinds.get("residual"):
        return "residual"
    if any(f.kind == "other_person" and ".sugg" in f.sub for f in fields):
        return "Б8-echo"
    if c_tools and i_tools and i_tools[-1] in LOOKUPS and len(i_tools) < len(c_tools):
        return "Б8-echo"
    if case.kind in ("compare", "result_feed") and c_tools and not any(t not in LOOKUPS for t in i_tools):
        return "Б8-echo"
    if not i_tools and c_tools:
        if case.kind == "validate":
            return "validate-refuse"
        if "город" in reply or "населённ" in reply:
            return "Б10-city"
        subs = [s for s, _ in triple.I.substitutes.values()]
        longest = max((len(s.split()) for s in subs), default=0)
        real_longest = max((len(item.value.split()) for item in case.pii if item.type == "NAME"), default=0)
        if "фио" in reply or "слов" in reply or longest > max(real_longest, 3):
            return "Б9-span"
        return "asks"
    if kinds and set(kinds) <= {"derived", "extra", "absent"} and kinds.get("derived"):
        return "derived-only"
    return "other"


def _one_example(fields: list) -> str:
    for f in fields:
        if f.kind not in ("agree", "derived"):
            return f"{f.tool}.{f.path}: агент `{_short(f.obs)}` / контроль `{_short(f.ref)}` [{f.kind}{('/' + f.sub) if f.sub else ''}]"
    for f in fields:
        if f.kind == "derived":
            return f"{f.tool}.{f.path}: `{_short(f.obs)}` / `{_short(f.ref)}` [derived]"
    return ""


def _short(text: str, n: int = 38) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 1] + "…"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir")
    parser.add_argument("--out", default="autopsy.md")
    parser.add_argument("--level", default="state", choices=("tools", "keys", "state"))
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    corpus, triples, excluded = _load_run(run_dir)
    rows: list[tuple] = []
    causes: Counter[str] = Counter()
    by_kind: dict[str, Counter[str]] = {}
    for triple in triples:
        case = corpus[triple.case_id]
        ic, cc = compare_triple(case, triple)
        ok = {"tools": ic.levels.tools, "keys": ic.levels.keys, "state": ic.levels.state}[args.level]
        if ok:
            continue
        fields = list(ic.fields)
        cause = _cause(case, triple, fields)
        causes[cause] += 1
        by_kind.setdefault(case.kind, Counter())[cause] += 1
        kinds = Counter(f.kind for f in fields if f.kind != "agree")
        rows.append((f"{triple.case_id}|{triple.repeat}", case.kind, case.register,
                     ",".join(c.name.replace("crm_", "").replace("_contact", "")[:12] for c in triple.C.calls) or "—",
                     ",".join(c.name.replace("crm_", "").replace("_contact", "")[:12] for c in triple.I.calls) or "—",
                     "да" if cc.levels.state else "нет",
                     " ".join(f"{k}:{v}" for k, v in kinds.most_common(4)) or "—",
                     cause, _one_example(fields)))
    lines = [f"# Разбор расхождений I≠C на уровне {args.level} — {run_dir.name}", "",
             f"троек с расхождением: {len(rows)} из {len(triples)} · исключено {len(excluded)}", "",
             "## Причины", "", "| причина | троек |", "|---|---|"]
    lines += [f"| {cause} | {count} |" for cause, count in causes.most_common()]
    lines += ["", "## По видам", "", "| вид | " + " | ".join(c for c, _ in causes.most_common()) + " |",
              "|---|" + "---|" * len(causes)]
    for kind in sorted(by_kind):
        lines.append(f"| {kind} | " + " | ".join(str(by_kind[kind].get(c, 0)) for c, _ in causes.most_common()) + " |")
    lines += ["", "## Тройки", "",
              "| тройка | вид | регистр | C вызвал | I вызвал | C′≈C | классы полей | причина | пример: агент / контроль |",
              "|---|---|---|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join(str(v).replace("|", "\\|") if i != 0 else str(v) for i, v in enumerate(row)) + " |" for row in rows]
    out = run_dir / args.out
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:6 + len(causes) + 4 + len(by_kind)]))
    print(f"\nзаписано {out} · строк {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
