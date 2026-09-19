"""Build `leaderboard.md` from the run files in `results/`.

THE TABLE IS GROUPED BY CORPUS DIGEST. Two systems measured on different
versions of the corpus are not comparable, and a table that puts them in one
column says they are. Runs made on an older corpus are listed under
«устаревшие» with their digest, not deleted: a withdrawn number is a number
somebody can no longer check.

NOTHING IS RANKED BY A SINGLE SCORE. There is no total here on purpose. A
gateway that masks everything wins the leak line and loses over-masking and
the round trip; the reader decides which of those they are buying.
"""

import argparse
import sys
from pathlib import Path

from agentmask_ru.results import corpus_digest, read
from agentmask_ru.schema import load_dir
from agentmask_ru.stats import mcnemar_exact

_COLUMNS: tuple[tuple[str, str], ...] = (
    ("leak", "скрыто"),
    ("coverage", "скрыто целиком"),
    ("round_trip", "круг (из скрытых)"),
    ("end_to_end", "круг (из всех)"),
    ("overmask", "не тронуто лишнего"),
    ("consistency", "одна подстановка"),
)


def _cell(lines: dict[str, object], key: str) -> str:
    line = lines.get(key)
    if not isinstance(line, dict) or not line.get("total"):
        return "—"
    rate = float(line["rate"]) * 100
    low, high = (float(v) * 100 for v in line["ci95"])  # type: ignore[union-attr]
    return f"{rate:.1f}% [{low:.0f}–{high:.0f}] {line['hits']}/{line['total']}"


def render(payloads: list[dict[str, object]], digest: str, cases: int) -> str:
    current = [p for p in payloads if p["manifest"]["corpus_digest"] == digest]  # type: ignore[index]
    stale = [p for p in payloads if p["manifest"]["corpus_digest"] != digest]  # type: ignore[index]
    current.sort(key=lambda p: str(p["manifest"]["system"]))  # type: ignore[index]

    out: list[str] = []
    out.append("# AgentMask-RU — таблица")
    out.append("")
    out.append(f"Корпус `{digest}`, {cases} случаев. В скобках — точный 95% интервал Клоппера–Пирсона.")
    out.append("Столбцы НЕ складываются в общий балл: шлюз, который маскирует всё, выигрывает первый")
    out.append("столбец и проигрывает два последних.")
    out.append("")
    header = "| система | " + " | ".join(title for _, title in _COLUMNS) + " | ошибок |"
    out.append(header)
    out.append("|" + "---|" * (len(_COLUMNS) + 2))
    for payload in current:
        lines = payload["lines"]
        assert isinstance(lines, dict)
        run = payload["run"]
        assert isinstance(run, dict)
        name = str(payload["manifest"]["system"])  # type: ignore[index]
        cells = " | ".join(_cell(lines, key) for key, _ in _COLUMNS)
        out.append(f"| {name} | {cells} | {run['errors']} |")
    out.append("")

    pairs = [(a, b) for i, a in enumerate(current) for b in current[i + 1:]]
    if pairs:
        out.append("## Парные сравнения (McNemar, точный)")
        out.append("")
        out.append("| пара | строка | b | c | p |")
        out.append("|---|---|---|---|---|")
        for a, b in pairs:
            for key in ("leak", "end_to_end"):
                counts = _discordant(a, b, key)
                if counts is None:
                    continue
                only_a, only_b = counts
                p_value = mcnemar_exact(only_a, only_b)
                left = str(a["manifest"]["system"])  # type: ignore[index]
                right = str(b["manifest"]["system"])  # type: ignore[index]
                out.append(f"| {left} ↔ {right} | {key} | {only_a} | {only_b} | {p_value:.3f} |")
        out.append("")

    if stale:
        out.append("## Устаревшие прогоны (другой корпус)")
        out.append("")
        for payload in stale:
            meta = payload["manifest"]
            assert isinstance(meta, dict)
            out.append(f"- {meta['system']} — корпус `{meta['corpus_digest']}`, прогон {meta['run_at']}")
        out.append("")
    return "\n".join(out)


def _discordant(left: dict[str, object], right: dict[str, object], key: str) -> tuple[int, int] | None:
    def outcomes(payload: dict[str, object]) -> dict[tuple[str, str], bool]:
        out: dict[tuple[str, str], bool] = {}
        observations = payload.get("observations")
        if not isinstance(observations, list):
            return out
        for observation in observations:
            for item in observation.get("items", []):
                if key == "leak":
                    out[(item["case_id"], item["item_id"])] = bool(item["altered"])
                elif key == "end_to_end" and item.get("round_trip") is not None:
                    out[(item["case_id"], item["item_id"])] = bool(item["round_trip"])
        return out

    a, b = outcomes(left), outcomes(right)
    shared = set(a) & set(b)
    if not shared:
        return None
    return (sum(1 for k in shared if a[k] and not b[k]), sum(1 for k in shared if b[k] and not a[k]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", default="results")
    parser.add_argument("--cases", default="cases")
    parser.add_argument("--out", default="leaderboard.md")
    args = parser.parse_args(argv)
    cases = load_dir(Path(args.cases))
    if not cases:
        print("нет случаев", file=sys.stderr)
        return 1
    payloads = [read(path) for path in sorted(Path(args.results).rglob("*.json"))]
    if not payloads:
        print("нет прогонов в results/", file=sys.stderr)
        return 1
    # One run per system: the latest, so a re-run replaces rather than duplicates.
    latest: dict[str, dict[str, object]] = {}
    for payload in payloads:
        system = str(payload["manifest"]["system"])  # type: ignore[index]
        run_at = str(payload["manifest"]["run_at"])  # type: ignore[index]
        if system not in latest or run_at > str(latest[system]["manifest"]["run_at"]):  # type: ignore[index]
            latest[system] = payload
    text = render(list(latest.values()), corpus_digest(cases), len(cases))
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
