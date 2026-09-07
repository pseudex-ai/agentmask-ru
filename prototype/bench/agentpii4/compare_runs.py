"""Two live runs side by side: the headline levels and the autopsy causes.

    python3 bench/agentpii4/compare_runs.py bench/runs/2026-09-02/v4-live-small bench/runs/2026-09-03/v4-live-small

Each run is replayed from its own `arms.jsonl` against its own corpus
snapshot, so a corpus rebuilt between the runs changes nothing here.
"""
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from bench.agentpii4 import report, stats  # noqa: E402
from bench.agentpii4.autopsy import _cause, _load_run  # noqa: E402
from bench.agentpii4.compare import compare_triple  # noqa: E402


def _summary(run_dir: Path) -> dict[str, object]:
    corpus, triples, excluded = _load_run(run_dir)
    scored = report.score_triples(corpus, triples)
    out: dict[str, object] = {"triples": len(scored), "excluded": len(excluded)}
    # EVERY level, not three. Iterating a subset made the run-over-run tool
    # blind to exactly the two axes the product promises — values and
    # verbatimness — so a change could move them either way unseen.
    for level, _label in report.LEVELS:
        effects = report.case_effects(corpus, scored, level)
        out[level] = (stats.agreement(effects, "ic"), stats.agreement(effects, "cc"),
                      stats.cluster_bootstrap(effects, reps=1000),
                      len(report.comparable_triples(scored, level)))
    kinds: Counter[str] = Counter()
    for one in scored:
        for field in one.ic.fields:
            kinds[field.kind] += 1
    out["kinds"] = kinds
    causes: Counter[str] = Counter()
    for triple in triples:
        case = corpus[triple.case_id]
        ic, _ = compare_triple(case, triple)
        if not ic.levels.state:
            causes[_cause(case, triple, list(ic.fields))] += 1
    out["causes"] = causes
    by_type: dict[str, list[int]] = {}
    for one in scored:
        for field in one.ic.fields:
            by_type.setdefault(field.pii_type or "—", [0, 0])
            by_type[field.pii_type or "—"][1] += 1
            if field.kind == "agree":
                by_type[field.pii_type or "—"][0] += 1
    out["by_type"] = by_type
    return out


def main() -> int:
    before, after = Path(sys.argv[1]), Path(sys.argv[2])
    a, b = _summary(before), _summary(after)
    print(f"{'':18} {'до':>22} {'после':>22}")
    print(f"{'троек':18} {a['triples']:>22} {b['triples']:>22}")
    for level, label in report.LEVELS:
        (ia, ca, ba, na), (ib, cb, bb, nb) = a[level], b[level]  # type: ignore[misc]
        print(f"{label:18} {100*ia:5.1f}% / пол {100*ca:5.1f}% (n={na}) {100*ib:6.1f}% / пол {100*cb:5.1f}% (n={nb})"
              f"   эффект {100*ba.point:+.1f} -> {100*bb.point:+.1f}pp")
    kinds = sorted(set(a["kinds"]) | set(b["kinds"]), key=lambda k: -(a["kinds"].get(k, 0) + b["kinds"].get(k, 0)))  # type: ignore[union-attr]
    print("\nклассы полей (I−C):")
    for kind in kinds:
        print(f"  {kind:18} {a['kinds'].get(kind, 0):>6} {b['kinds'].get(kind, 0):>8}")  # type: ignore[union-attr]
    causes = sorted(set(a["causes"]) | set(b["causes"]), key=lambda k: -(a["causes"].get(k, 0) + b["causes"].get(k, 0)))  # type: ignore[union-attr]
    print("\nпричины расхождений на L3:")
    for cause in causes:
        print(f"  {cause:18} {a['causes'].get(cause, 0):>6} {b['causes'].get(cause, 0):>8}")  # type: ignore[union-attr]
    print("\nпо типам (agree/всего):")
    for kind in sorted(set(a["by_type"]) | set(b["by_type"])):  # type: ignore[arg-type]
        pa = a["by_type"].get(kind, [0, 0]); pb = b["by_type"].get(kind, [0, 0])  # type: ignore[union-attr]
        print(f"  {kind:10} {pa[0]:>4}/{pa[1]:<4} {pb[0]:>8}/{pb[1]:<4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
