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

from agentmask_ru.results import corpus_digest, read, rescored
from agentmask_ru.schema import load_dir
from agentmask_ru.stats import mcnemar_exact

_POLICY_ORDER: tuple[str, ...] = ("copier", "rewriter", "reformat")
_POLICY_TITLES: dict[str, str] = {
    "copier": "копирует дословно",
    "rewriter": "пишет в своём формате",
    "reformat": "переписывает телефон",
}
_POLICY_NOTES: dict[str, str] = {
    "copier": ("Скриптовая модель копирует подмену в вызов инструмента слово в слово — "
               "и режет её на части, где инструмент хочет части (`decompose`)."),
    "rewriter": ("Скриптовая модель пишет каждое значение в своей нотации: имя — с заглавных в именительном, "
                 "телефон — `+7…`, дату — ISO, карту — цифрами подряд. Плейсхолдеру переписывать нечего — "
                 "он проходит как есть, поэтому шлюз на плейсхолдерах здесь равен себе под копирующим агентом, "
                 "а шлюз с подменами, сохраняющими формат, измеряется на том, умеет ли он вернуть значение "
                 "в форме АГЕНТА. Инструменту здесь причитается значение в нотации этого агента "
                 "(`rewrite` над оригиналом) — то, что он передал бы и без шлюза."),
}

_COLUMNS: tuple[tuple[str, str], ...] = (
    ("leak", "скрыто"),
    ("coverage", "скрыто целиком"),
    ("round_trip", "круг (из скрытых)"),
    ("round_trip_repaired", "круг с починкой"),
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
    out.append("Что стоит знать, читая цифры, — в разделе «Оговорки» ниже; конфигурация каждого")
    out.append("прогона лежит в `results/<система>/` в поле `manifest`. Строки таблицы пересчитаны из")
    out.append("записанных наблюдений текущим судьёй харнесса — один и тот же для всех систем.")
    out.append("")
    # ONE TABLE PER AGENT. `copier` copies the substitute verbatim into the
    # tool call; `rewriter` writes every value in its own notation (Title-case
    # nominative, +7…, ISO, bare digits). A gateway that only mirrors is good
    # under the first and falls under the second; a placeholder gateway is
    # the same under both, because a placeholder carries no form to rewrite.
    # Read the two tables together, never one.
    policies = sorted({str(p["manifest"].get("policy", "copier")) for p in current},  # type: ignore[union-attr]
                      key=lambda name: _POLICY_ORDER.index(name) if name in _POLICY_ORDER else 99)
    for policy in policies:
        rows = [p for p in current if str(p["manifest"].get("policy", "copier")) == policy]  # type: ignore[union-attr]
        if len(policies) > 1:
            out.append(f"## Агент «{_POLICY_TITLES.get(policy, policy)}»")
            out.append("")
            out.append(_POLICY_NOTES.get(policy, ""))
            out.append("")
        header = "| система | " + " | ".join(title for _, title in _COLUMNS) + " | ошибок |"
        out.append(header)
        out.append("|" + "---|" * (len(_COLUMNS) + 2))
        for payload in rows:
            lines = payload["lines"]
            assert isinstance(lines, dict)
            run = payload["run"]
            assert isinstance(run, dict)
            name = str(payload["manifest"]["system"])  # type: ignore[index]
            cells = " | ".join(_cell(lines, key) for key, _ in _COLUMNS)
            out.append(f"| {name} | {cells} | {run['errors']} |")
        out.append("")

    copier_rows = [p for p in current if str(p["manifest"].get("policy", "copier")) == "copier"]  # type: ignore[union-attr]
    pairs = [(a, b) for i, a in enumerate(copier_rows) for b in copier_rows[i + 1:]]
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

    out.append("## Оговорки")
    out.append("")
    out.append("Каждая строка здесь — факт о конфигурации, без которого число читается неверно.")
    out.append("")
    for payload in current:
        meta = payload["manifest"]
        assert isinstance(meta, dict)
        config = meta.get("adapter_config", {})
        caveat = config.get("caveat") if isinstance(config, dict) else None
        notes = str(meta.get("notes", "")).strip()
        if caveat:
            out.append(f"- **{meta['system']}** — {caveat}")
        elif notes:
            out.append(f"- **{meta['system']}** — {notes}")
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


def _utf8_stdout() -> None:
    """Печатать по-русски в консоль Windows.

    Windows отдаёт стандартному выводу кодировку страницы (cp1251/cp437), и
    первая же русская строка роняет процесс с UnicodeEncodeError — что и
    случилось в первом же прогоне CI. Матрица ubuntu+windows стоит в CI
    ровно ради таких находок, и чинить это надо не переменной окружения в
    workflow, а здесь: читатель статьи запустит бенчмарк у себя, и у него
    тоже Windows.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", default="results")
    parser.add_argument("--cases", default="cases")
    parser.add_argument("--out", default="leaderboard.md")
    args = parser.parse_args(argv)
    cases = load_dir(Path(args.cases))
    if not cases:
        print("нет случаев", file=sys.stderr)
        return 1
    payloads = [read(path) for path in sorted(Path(args.results).rglob("*.json"))
                if "_archive" not in path.parts]
    if not payloads:
        print("нет прогонов в results/", file=sys.stderr)
        return 1
    # One run per system: the latest, so a re-run replaces rather than duplicates.
    latest: dict[tuple[str, str], dict[str, object]] = {}
    for payload in payloads:
        meta = payload["manifest"]
        assert isinstance(meta, dict)
        key = (str(meta["system"]), str(meta.get("policy", "copier")))
        run_at = str(meta["run_at"])
        if key not in latest or run_at > str(latest[key]["manifest"]["run_at"]):  # type: ignore[index]
            latest[key] = payload
    # EVERY RUN IS READ BY THE CURRENT JUDGE. The lines a run file carries are
    # the ones computed on its day; the table re-derives them from the stored
    # observations so that seven systems are compared under one rule.
    text = render([rescored(p, cases) for p in latest.values()], corpus_digest(cases), len(cases))
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
