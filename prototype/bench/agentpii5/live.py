"""Real-time metrics dashboard for a RUNNING v5 run.

    python -m bench.agentpii5 live <run_dir>        # refresh every INTERVAL seconds
    python -m bench.agentpii5 live --latest         # newest run under bench/runs/
    python -m bench.agentpii5 live --once <run_dir> # one snapshot, no loop

No provider, engine, or judge is touched. This reads the run's files and
recomputes the SAME pure metrics the offline `hop-report` prints, on whatever
triples are on disk RIGHT NOW. It is a watch face, not a second estimator: the
numbers here converge to `hop-report`'s numbers as triples finish, and a
number that disagrees with the offline report at the end is a bug in this
module, not a new measurement.

WHY IT CAN READ A HALF-WRITTEN RUN. `drive_v5` writes every triple's rows
before the next one starts (`append_row` flushes each line). So at any instant
the on-disk `*.arms.jsonl`, `*.arms.v5.jsonl` and `*.hops.jsonl` hold exactly
the finished triples, and `report.observations_of` rebuilds the observations
from them without requiring the run's final `meta.json` or ledger.

Engine-free, like `compare`/`hop-report`: it imports `report` (file reader),
`metrics` (pure functions of observations), `actual_hops` and `causal_hops`
(pure), never `pseudex`/`licensing`.
"""

import argparse
import json
import os
import threading
import time
from dataclasses import asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bench.agentpii5 import causal_hops, metrics, report
from bench.agentpii5.actual_hops import ActualAggregate, actual_events, aggregate
from bench.agentpii5.causal_hops import CausalAggregate, causal_events
from bench.agentpii5.hop_report import HISTORICAL_METRICS

# The four transitions the product cares about, in the order the owner reads
# them. `hop_owner` buckets are `IN/user`, `OUT/tool_arg`, `IN/tool`,
# `OUT/answer` plus the rarer `IN/document`, `OUT/summary`, `OUT/template` …
# which we still print — every bucket, never a hand-picked subset.
TRANSITION_ORDER: tuple[str, ...] = (
    "IN/user", "OUT/tool_arg", "IN/tool", "OUT/answer",
)


def _run_id_of(run_dir: Path) -> str:
    """The run id off ANY run file, so it works before the first triple writes
    `*.arms.jsonl`. `report.run_id_of` only globs arms; here the earliest file
    wins, so the watch face starts rendering from the very first second."""
    for suffix in (".spend.tsv", ".meta.json", ".arms.v5.jsonl", ".hops.jsonl", ".arms.jsonl"):
        found = sorted(run_dir.glob(f"*{suffix}"))
        if found:
            return found[0].name[: -len(suffix)]
    raise report.ReportError(f"{run_dir}: no run file yet — not a run directory")


def _rate(hits: int, total: int) -> str:
    if not total:
        return "н/п"
    return f"{hits}/{total} ({100 * hits / total:.2f}%)"


def live_snapshot(run_dir: Path) -> dict[str, object]:
    """One snapshot of the run as it stands right now.

    Returns a JSON-safe dict. `state` is one of ``starting`` (no triple has
    finished), ``no_corpus`` (directory not a run yet) or ``live`` (at least
    one observation is readable)."""
    run_dir = run_dir.resolve()
    base: dict[str, object] = {"run_dir": str(run_dir), "ts": datetime.now().isoformat(timespec="seconds")}

    if not run_dir.is_dir():
        return {**base, "state": "missing"}
    if not (run_dir / "corpus.v5.json").exists():
        return {**base, "state": "no_corpus"}

    try:
        cases = report.v5_cases(run_dir)
    except report.ReportError as error:
        return {**base, "state": "no_corpus", "error": str(error)}

    try:
        half = report.observations_of(run_dir, (), cases)
    except report.ReportError:
        # No `*.arms.jsonl` yet: zero finished triples, still a valid state.
        return {**base, "state": "starting", "done": 0, "corpus": len(cases)}

    observations = half.observations
    historical: dict[str, dict[str, int]] = {}
    for name in HISTORICAL_METRICS:
        line = metrics.METRIC_FUNCTIONS[name](observations)
        historical[name] = {"hits": line.hits, "total": line.total}

    actual: ActualAggregate = aggregate(
        tuple(actual_events(one.case, one.run) for one in observations))
    causal: CausalAggregate = causal_hops.aggregate(
        tuple(causal_events(one.case, one.run) for one in observations))
    # Render the causal table HERE, where the real dataclasses exist; the JSON
    # snapshot only carries the rendered lines (and the numeric `asdict`) so the
    # viewer never rebuilds nested `CausalLine`s from a dict.
    causal_render: list[str] = list(causal_hops.render(causal))

    # The hop-owner breakdown = the four transitions, plus every rarer bucket.
    owners: dict[str, dict[str, dict[str, int]]] = {}
    buckets = metrics.by_axis(observations, "hop_owner")
    for owner in sorted(buckets):
        rows = buckets[owner]
        owners[owner] = {
            name: {"hits": metrics.METRIC_FUNCTIONS[name](rows).hits,
                   "total": metrics.METRIC_FUNCTIONS[name](rows).total}
            for name in metrics.HOP_SLICEABLE
        }

    return {
        **base,
        "state": "live",
        "done": len(observations),
        "hopless": len(half.hopless),
        "stopped": len(half.stopped),
        "corpus": len(cases),
        # The case ids FINISHED so far: the side-by-side against a saved run is
        # only fair on the same cases, so the viewer aggregates the saved run
        # over exactly these ids and never over its whole population.
        "case_ids": [one.case.base.id for one in observations],
        "historical": historical,
        "owners": owners,
        "actual": asdict(actual),
        "causal": asdict(causal),
        "causal_render": causal_render,
    }


def _historical_table(snapshot: dict[str, object]) -> list[str]:
    rows = ["## Historical (completed-only, все 13 метрик спринта)", "",
            "| Metric | Hits/total |", "|---|---:|"]
    hist = snapshot["historical"]
    assert isinstance(hist, dict)
    for name in HISTORICAL_METRICS:
        line = hist[name]
        assert isinstance(line, dict)
        rows.append(f"| {name} | {_rate(int(line['hits']), int(line['total']))} |")
    return rows


def _owners_table(snapshot: dict[str, object]) -> list[str]:
    owners = snapshot.get("owners") or {}
    assert isinstance(owners, dict)
    if not owners:
        return []
    columns = tuple(metrics.HOP_SLICEABLE)
    header = ["## Переходы (по hop_owner)", "",
              "| owner | " + " | ".join(columns) + " |",
              "|---|" + "---:|" * len(columns)]
    rows = list(header)
    order = tuple(o for o in TRANSITION_ORDER if o in owners) + tuple(
        o for o in sorted(owners) if o not in TRANSITION_ORDER)
    for owner in order:
        cells = [_rate(int(owners[owner][c]["hits"]), int(owners[owner][c]["total"]))
                 for c in columns]
        rows.append(f"| {owner} | " + " | ".join(cells) + " |")
    return rows


def _actual_table(snapshot: dict[str, object]) -> list[str]:
    actual = snapshot.get("actual")
    if not actual:
        return []
    assert isinstance(actual, dict)
    overall = actual.get("overall") or {}
    by_type = actual.get("by_type") or []
    rows = ["", "## Actual OUT (листовые события, M0 estimator)", "",
            f"Листовых событий: {actual.get('events_total')}; "
            f"не применимо: {actual.get('not_applicable')}; "
            f"прогонов: {actual.get('runs')}.",
            "",
            "| Type | Cand. | Attr. | Value | Form | Form∅ | Residual | Joint |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for item in (overall, *by_type):
        count = int(item.get("candidates") or 0)
        rows.append(
            f"| {item.get('pii_type') or 'untyped'} | {count} | "
            + " | ".join(_rate(int(item.get(k) or 0), count) for k in
                         ("attributed", "value_ok", "form_ok", "form_unmeasured",
                          "residual", "joint_ok"))
            + " |")
    return rows


def render(snapshot: dict[str, object]) -> str:
    state = snapshot.get("state")
    if state != "live":
        head = snapshot.get("run_dir") or "?"
        return "\n".join([
            "=== pseudex v5 LIVE ===",
            f"run_dir: {head}",
            f"state: {state}" + (f" ({snapshot.get('error')})" if snapshot.get("error") else ""),
            "ждём завершения первой тройки / создания каталога прогона…",
        ])

    blocks: list[str] = []
    blocks.append("=== pseudex v5 LIVE ===")
    blocks.append(
        f"готово: {snapshot.get('done')} · корпус: {snapshot.get('corpus')} · "
        f"hopless: {snapshot.get('hopless')} · stopped: {snapshot.get('stopped')} · "
        f"обновлено {snapshot.get('ts')}")
    blocks.append("")
    blocks.extend(_historical_table(snapshot))
    blocks.extend(_owners_table(snapshot))
    blocks.extend(_actual_table(snapshot))

    causal_render = snapshot.get("causal_render")
    if causal_render:
        blocks.extend(["", "## Actual causal (recorded chronology, M03 estimator)", ""])
        blocks.extend(str(line) for line in causal_render)
    return "\n".join(blocks)


def _newest_run(runs_root: Path) -> Path | None:
    if not runs_root.is_dir():
        return None
    candidates = [p for p in runs_root.rglob("corpus.v5.json")]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime).parent


def _clear() -> None:
    if os.environ.get("TERM") and os.environ.get("TERM") != "dumb" and not os.environ.get("NO_COLOR"):
        print("\033[2J\033[H", end="")


# --- the saved run this viewer compares against ------------------------------

# The owner's earlier 450, whose per-case lines live in the audit's evidence
# tree. Read-only; a missing file simply turns the comparison column off.
BASELINE_INDEX: Path = (Path(__file__).resolve().parents[3]
                        / "research" / "hop-format-audit" / "evidence" / "case-index.json")
_BASELINE_CACHE: list[dict[str, object]] | None = None


def _baseline_rows() -> list[dict[str, object]]:
    """The saved run's per-case metric lines, parsed once and cached — the watch
    face refreshes every 2 s and re-parsing 450 rows each tick would be waste."""
    global _BASELINE_CACHE
    if _BASELINE_CACHE is None:
        try:
            _BASELINE_CACHE = list(json.loads(BASELINE_INDEX.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            _BASELINE_CACHE = []
    return _BASELINE_CACHE


def baseline_counts(case_ids: frozenset[str]) -> dict[str, dict[str, int]]:
    """The saved run aggregated over EXACTLY `case_ids`.

    THE COMPARISON MUST COVER THE SAME CASES. Summing the whole saved population
    against a live prefix flatters whichever side has the easier cases, so the
    saved run is filtered to the ids the live run has actually finished. This is
    also why `live_snapshot` carries `case_ids` at all."""
    sums: dict[str, dict[str, int]] = {}
    for row in _baseline_rows():
        if str(row.get("case_id")) not in case_ids:
            continue
        for name, line in (row.get("metrics") or {}).items():
            slot = sums.setdefault(str(name), {"hits": 0, "total": 0})
            slot["hits"] += int((line or {}).get("hits") or 0)
            slot["total"] += int((line or {}).get("total") or 0)
    return sums


# The saved run's PER-OWNER form lines live in the audit summary beside the
# per-case index; there is no per-case owner split, so this leg is the whole
# saved population and the caption says so.
BASELINE_AUDIT: Path = BASELINE_INDEX.parent / "audit.json"
_BASELINE_FORMS_CACHE: dict[str, dict[str, int]] | None = None


def baseline_forms() -> dict[str, dict[str, int]]:
    """The saved run's form rate per `hop_owner`, parsed once."""
    global _BASELINE_FORMS_CACHE
    if _BASELINE_FORMS_CACHE is None:
        try:
            data = json.loads(BASELINE_AUDIT.read_text(encoding="utf-8"))
            forms = data.get("forms") or {}
            _BASELINE_FORMS_CACHE = {
                str(key): {"hits": int(one.get("hits") or 0),
                           "total": int(one.get("total") or 0)}
                for key, one in forms.items()}
        except (OSError, ValueError, AttributeError):
            _BASELINE_FORMS_CACHE = {}
    return _BASELINE_FORMS_CACHE


def _pct(cell: dict[str, object] | None) -> str:
    """One line as `57.3% 12/21`, or a dash when nothing was measured."""
    if not cell:
        return '<span class="mut">—</span>'
    hits, total = int(cell.get("hits") or 0), int(cell.get("total") or 0)
    if not total:
        return '<span class="mut">—</span>'
    return (f'<span class="rate">{100 * hits / total:.1f}%</span>'
            f'<span class="frac">{hits}/{total}</span>')


def _movement(base: dict[str, object] | None, cur: dict[str, object] | None) -> str:
    """The shift in percentage points, green up / red down. `=` inside a tenth
    of a point, because a moving number that has not moved is noise."""
    if not base or not cur:
        return '<td class="mut">—</td>'
    bt, ct = int(base.get("total") or 0), int(cur.get("total") or 0)
    if not bt or not ct:
        return '<td class="mut">·</td>'
    shift = 100.0 * int(cur.get("hits") or 0) / ct - 100.0 * int(base.get("hits") or 0) / bt
    if abs(shift) < 0.1:
        return '<td class="mut">=</td>'
    return f'<td class="{"up" if shift > 0 else "dn"}">{shift:+.1f}</td>'


def _render_main(snapshot: dict[str, object]) -> str:
    """The `<main>` fragment: clean tables, the saved run BESIDE the live one.

    Server-rendered on purpose — the numbers are ours, the layout is ours, and a
    page that builds its own tables in JS is a page that can be broken by a
    single stray quote in a metric name."""
    state = snapshot.get("state")
    if state != "live":
        note = f' · <span class="mut">{snapshot.get("error")}</span>' if snapshot.get("error") else ""
        return (f'<div class="wait">состояние: <b>{state}</b>{note}'
                '<br>ждём завершения первой тройки / создания каталога прогона…</div>')

    ids = frozenset(str(one) for one in (snapshot.get("case_ids") or ()))
    base = baseline_counts(ids)
    hist = snapshot.get("historical") or {}
    assert isinstance(hist, dict)

    out: list[str] = []
    out.append('<section><h2>Метрики спринта'
               '<span class="sub">слева — прошлый прогон на ТЕХ ЖЕ кейсах, справа — идущий;'
               ' Δ в п.п.</span></h2>')
    out.append('<table class="grid"><thead><tr><th>Метрика</th>'
               '<th>Прошлый прогон</th><th class="hl">Сейчас</th><th>Δ</th></tr></thead><tbody>')
    for name in HISTORICAL_METRICS:
        cur_cell = hist.get(name) if isinstance(hist.get(name), dict) else None
        out.append(f'<tr><td class="name">{name}</td>'
                   f'<td>{_pct(base.get(name))}</td>'
                   f'<td class="hl">{_pct(cur_cell)}</td>'
                   f'{_movement(base.get(name), cur_cell)}</tr>')
    out.append('</tbody></table></section>')

    owners = snapshot.get("owners") or {}
    assert isinstance(owners, dict)
    if owners:
        base_forms = baseline_forms()
        details = ("coverage", "end_to_end", "typed", "leak", "out_absent")
        order = tuple(o for o in TRANSITION_ORDER if o in owners) + tuple(
            o for o in sorted(owners) if o not in TRANSITION_ORDER)
        out.append('<section><h2>Переходы<span class="sub">форма на самом хопе: прошлый '
                   'прогон (весь, 450) против идущего на тех же переходах; прочие колонки — '
                   'только текущий</span></h2>')
        out.append('<table class="grid"><thead><tr><th>Переход</th>'
                   '<th>Форма: прошлый</th><th class="hl">Форма: сейчас</th><th>Δ</th>'
                   + "".join(f"<th>{col}</th>" for col in details) + '</tr></thead><tbody>')
        for owner in order:
            # ONE form line per owner: the side that carries it is IN for the
            # inbound hops and OUT for the outbound ones, so form_hIN/form_hOUT
            # are two names for the same question.
            form_key = "form_hIN" if owner.startswith("IN/") else "form_hOUT"
            cur_form = owners[owner].get(form_key) or {}
            base_form = base_forms.get(owner)
            cls = ' class="name hl"' if owner in TRANSITION_ORDER else ' class="name"'
            cells = "".join(
                f'<td>{_pct(owners[owner].get(col) or {})}</td>' for col in details)
            out.append(f'<tr><td{cls}>{owner}</td>'
                       f'<td>{_pct(base_form)}</td><td class="hl">{_pct(cur_form)}</td>'
                       f'{_movement(base_form, cur_form)}{cells}</tr>')
        out.append('</tbody></table></section>')

    actual = snapshot.get("actual") or {}
    assert isinstance(actual, dict)
    rows = [actual.get("overall") or {}, *(actual.get("by_type") or [])]
    if actual.get("events_total"):
        out.append('<section><h2>Actual OUT<span class="sub">листовые события, M0 estimator · '
                   f'событий {actual.get("events_total")}, не применимо {actual.get("not_applicable")}, '
                   f'прогонов {actual.get("runs")} · прошлый прогон не хранит actual-OUT по типам'
                   '</span></h2>')
        keys = ("attributed", "value_ok", "form_ok", "form_unmeasured", "residual", "joint_ok")
        out.append('<table class="grid"><thead><tr><th>Тип</th><th>Cand.</th>'
                   + "".join(f"<th>{k}</th>" for k in keys) + '</tr></thead><tbody>')
        for item in rows:
            cand = int(item.get("candidates") or 0)
            cells = "".join(
                f'<td>{_pct({"hits": int(item.get(k) or 0), "total": cand})}</td>' for k in keys)
            name = item.get("pii_type") or "untyped"
            out.append(f'<tr><td class="name">{name}</td><td class="num">{cand}</td>{cells}</tr>')
        out.append('</tbody></table></section>')

    causal = snapshot.get("causal_render") or []
    if causal:
        out.append('<section><h2>Actual causal<span class="sub">записанная хронология, M03</span></h2>')
        out.append('<pre class="causal">' + "\n".join(str(one) for one in causal) + '</pre></section>')
    return "\n".join(out)


WEB_SHELL: str = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>pseudex v5 LIVE</title>
<style>
  :root{color-scheme:dark;--bg:#0d1117;--panel:#161b22;--line:#30363d;--ink:#e6edf3;
        --mut:#8b949e;--acc:#58a6ff;--up:#3fb950;--dn:#f85149}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif}
  .bar{position:sticky;top:0;z-index:9;display:flex;gap:14px;align-items:baseline;
       justify-content:space-between;flex-wrap:wrap;padding:10px 18px;
       background:var(--panel);border-bottom:1px solid var(--line)}
  .brand{font-weight:700;color:var(--acc);letter-spacing:.02em}
  .prog{color:var(--ink)} .prog b{font-variant-numeric:tabular-nums}
  .ts{color:var(--mut);font-variant-numeric:tabular-nums}
  main{padding:16px 18px 40px;max-width:1500px}
  section{margin:0 0 22px}
  h2{font-size:14px;font-weight:600;margin:0 0 8px;display:flex;gap:10px;
     align-items:baseline;flex-wrap:wrap}
  h2 .sub{font-weight:400;color:var(--mut);font-size:12px}
  table.grid{border-collapse:separate;border-spacing:0;width:100%;background:var(--panel);
             border:1px solid var(--line);border-radius:8px;overflow:hidden}
  table.grid th,table.grid td{padding:5px 10px;border-bottom:1px solid var(--line);
             text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
  table.grid th{background:#1c2230;color:var(--mut);font-weight:600;font-size:11px;
             text-transform:uppercase;letter-spacing:.04em}
  table.grid td.name,table.grid th:first-child{text-align:left;
             font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  table.grid tr:last-child td{border-bottom:0}
  table.grid tbody tr:hover{background:#1b2230}
  td.hl,th.hl{background:rgba(88,166,255,.08)}
  td.name{color:var(--ink)}
  td.name.hl{color:var(--acc);font-weight:600}
  .rate{font-weight:600} .frac{color:var(--mut);margin-left:6px;font-size:11px}
  .mut{color:var(--mut)} .up{color:var(--up);font-weight:600} .dn{color:var(--dn);font-weight:600}
  .num{font-variant-numeric:tabular-nums}
  .wait{padding:40px 0;color:var(--mut)}
  pre.causal{background:var(--panel);border:1px solid var(--line);border-radius:8px;
             padding:12px 14px;overflow:auto;font:11.5px/1.45 ui-monospace,Menlo,monospace;
             color:#c9d1d9}
</style></head><body>
<div class="bar"><span class="brand">pseudex v5 LIVE</span>
<span class="prog" id="prog">—</span>
<span class="ts"><span id="ts">—</span> · обновление 2 с</span></div>
<main id="app">загрузка…</main>
<script>
const app=document.getElementById('app'),ts=document.getElementById('ts'),prog=document.getElementById('prog');
async function tick(){
  try{
    const [f,s]=await Promise.all([
      fetch('/fragment',{cache:'no-store'}),fetch('/snapshot.json',{cache:'no-store'})]);
    app.innerHTML=await f.text();
    const snap=await s.json();
    prog.innerHTML=snap.state==='live'
      ? `готово <b>${snap.done}</b> / ${snap.corpus} · исключено <b>${snap.stopped}</b>`
      : `состояние: ${snap.state}`;
    ts.textContent=new Date().toLocaleTimeString();
  }catch(e){ts.textContent='нет связи';}
}
tick();setInterval(tick,2000);
</script></body></html>
"""



_SNAPSHOT_LOCK = threading.Lock()
_SNAPSHOT_CACHE: dict[str, tuple[float, dict[str, object]]] = {}
# `live_snapshot` walks EVERY finished triple through the actual and causal
# estimators; on a long run that is seconds, not milliseconds (measured 3.3 s at
# 119 triples). A browser asking every 2 s would pile requests up until it gave
# up — the page just said «загрузка…» forever. One computation is shared, and a
# request that arrives while it runs waits for it rather than starting its own.
SNAPSHOT_TTL: float = 2.5


def cached_snapshot(run_dir: Path) -> dict[str, object]:
    """The snapshot, recomputed at most once per `SNAPSHOT_TTL`."""
    key = str(run_dir)
    with _SNAPSHOT_LOCK:
        entry = _SNAPSHOT_CACHE.get(key)
        if entry is not None and time.monotonic() - entry[0] < SNAPSHOT_TTL:
            return entry[1]
        snapshot = live_snapshot(run_dir)
        _SNAPSHOT_CACHE[key] = (time.monotonic(), snapshot)
        return snapshot


def _serve_web(run_dir: Path, host: str, port: int) -> None:
    """A tiny read-only HTTP face: `/` is the auto-refreshing page, `/snapshot.txt`
    is the rendered metrics text, `/snapshot.json` is the raw snapshot. No
    engine, no writes, no secrets — it only READS the run directory."""
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self._send(200, WEB_SHELL.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/fragment":
                html = _render_main(cached_snapshot(run_dir))
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/snapshot.txt":
                text = render(cached_snapshot(run_dir))
                self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8")
            elif self.path == "/snapshot.json":
                payload = json.dumps(cached_snapshot(run_dir), ensure_ascii=False)
                self._send(200, payload.encode("utf-8"), "application/json; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain; charset=utf-8")

        def log_message(self, *_args) -> None:
            pass  # a watch face has nothing to log

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"live web UI: http://{host}:{server.server_port}/  (Ctrl-C чтобы остановить)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", nargs="?", type=Path,
                        help="каталог прогона (тот, что печатает `run`)")
    parser.add_argument("--latest", action="store_true",
                        help="самый свежий прогон под bench/runs/")
    parser.add_argument("--once", action="store_true",
                        help="один снимок, без цикла")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="секунды между обновлениями (по умолчанию 2)")
    parser.add_argument("--web", action="store_true",
                        help="HTTP-страница со ссылкой (браузер) вместо терминала")
    parser.add_argument("--host", default="127.0.0.1",
                        help="адрес для --web (по умолчанию 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787,
                        help="порт для --web (по умолчанию 8787)")
    args = parser.parse_args()

    run_dir: Path
    if args.latest:
        here = Path(__file__).resolve().parent
        newest = _newest_run(here.parent / "runs")
        if newest is None:
            print("нет ни одного каталога прогона под bench/runs/", file=__import__("sys").stderr)
            return 2
        run_dir = newest
    elif args.run_dir is not None:
        run_dir = args.run_dir
    else:
        parser.error("нужен <run_dir> или --latest")

    if args.once:
        print(render(live_snapshot(run_dir)))
        return 0

    if args.web:
        _serve_web(run_dir, args.host, args.port)
        return 0

    interval = max(0.5, args.interval)
    last: str = ""
    while True:
        snapshot = live_snapshot(run_dir)
        text = render(snapshot)
        if text != last:
            _clear()
            print(text, flush=True)
            last = text
        time.sleep(interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
