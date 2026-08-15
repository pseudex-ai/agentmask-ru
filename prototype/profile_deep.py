"""Find the masking bottleneck — three levels of zoom.

  python3 profile_deep.py --mode stage     which STAGE   (always available)
  python3 profile_deep.py --mode function  which FUNCTION (needs yappi)
  python3 profile_deep.py --mode line      which LINE     (needs line_profiler)

Escalate in that order: stage tells you where to point the function profiler,
function tells you which body to hand to the line profiler. Going straight to
line-level over the whole pipeline just buries you in output.

yappi rather than cProfile because production masking runs in a threadpool and
cProfile only ever sees the thread it was started on. `--threads N` reproduces
that: with 1 thread you measure raw cost, with N you also see lock contention on
the shared SQLite connections.

Workload: a representative dirty-RU mix by default, or `--dataset holdout.json`
to profile the real benchmark corpus (generate it first with make_holdout.py).

Run against a scratch DB dir so a profiling pass never touches real vault state.
"""

import argparse
import json
import os
import statistics
import sys
import tempfile
import threading
import time

os.environ.setdefault("PSEUDEX_PROFILE", "1")
os.environ.setdefault("PSEUDEX_DB_DIR", tempfile.mkdtemp(prefix="pseudex_profile_"))

from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_messages  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402
from pseudex.profiling import ENABLED, STAGES  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

# A deliberately mixed workload: dense PII, free-form address, structured KV,
# hard negatives, and plain text. Profiling only the easy case lies to you.
_WORKLOAD = [
    "Здравствуйте, меня зовут Иван Петров, телефон +7 999 123-45-67, "
    "доставьте на улицу Ленина 5, кв 12, подъезд 3.",
    "Оформите доставку: г. Новосибирск, ул. Красный проспект, д. 17 к2, кв. 45. "
    "Получатель Анна Смирнова, моб 8-924-450-56-12.",
    '{"имя": "Мария Кузнецова", "телефон": "89991112233", "снилс": "112-233-445 95", '
    '"адрес": "Миклухо-Маклая 6", "email": "m.kuz@example.ru"}',
    "Проверьте контрагента по ИНН 7707083893 и оплатите с карты 4276 3800 1234 5678.",
    "Заказ 9676123456 по треку 77012345678901, артикул 4512 — когда приедет?",
    "Спасибо, всё устраивает, оформляйте как договорились.",
    "Паспорт 45 09 123456, дата рождения 12.03.1985, полис ОМС нужен?",
    "thanks, that works for me, please proceed with the plan as discussed above",
]


def _load_workload(dataset: str | None) -> list[str]:
    if dataset is None:
        return _WORKLOAD
    with open(dataset, encoding="utf-8") as handle:
        cases = json.load(handle)
    texts = [case["text"] for case in cases if isinstance(case.get("text"), str)]
    if not texts:
        raise ValueError(f"{dataset} contains no usable 'text' fields")
    return texts


def _context(detector: Detector, db_dir: str) -> MaskContext:
    return MaskContext(
        detector=detector,
        vault=Vault(os.path.join(db_dir, "vault.db"), "profile"),
        audit=AuditLog(os.path.join(db_dir, "audit.db")),
        # Capacity 1 keeps the cache from hiding the very work we came to measure:
        # with a warm cache every repeat is an O(1) hit and the profile is empty.
        cache=MaskCache(1),
        org_id="profile",
        agent_id="prof",
    )


def _run(texts: list[str], context: MaskContext, rounds: int, threads: int) -> float:
    """Mask the workload `rounds` times across `threads` workers; return wall ms."""
    def worker(slice_texts: list[str]) -> None:
        for _ in range(rounds):
            for text in slice_texts:
                mask_messages([{"role": "user", "content": text}], context, False)

    start = time.perf_counter()
    if threads == 1:
        worker(texts)
    else:
        workers = [threading.Thread(target=worker, args=(texts,)) for _ in range(threads)]
        for thread in workers:
            thread.start()
        for thread in workers:
            thread.join()
    return (time.perf_counter() - start) * 1000


def _print_stages(total_ms: float, calls: int) -> None:
    snapshot = STAGES.snapshot()
    if not snapshot:
        raise RuntimeError("no stages recorded — is PSEUDEX_PROFILE=1 set?")
    total_stage = snapshot.get("mask.one", {}).get("total_ms", 0.0) or total_ms
    print(f"\n{'STAGE':<26}{'CALLS':>8}{'TOTAL ms':>11}{'%':>7}{'MEAN':>9}{'p95':>9}{'MAX':>9}")
    print("-" * 79)
    for name, stats in snapshot.items():
        share = stats["total_ms"] / total_stage * 100 if total_stage else 0
        print(f"{name:<26}{stats['count']:>8}{stats['total_ms']:>11.1f}{share:>6.1f}%"
              f"{stats['mean_ms']:>9.3f}{stats['p95_ms']:>9.3f}{stats['max_ms']:>9.3f}")
    print("-" * 79)
    print(f"wall {total_ms:.0f} ms for {calls} masked messages "
          f"({total_ms / calls:.2f} ms/message)")
    print("\n% is share of mask.one. Nested stages overlap — detect.* sum to "
          "detect.total, which is itself inside mask.one.")


def _mode_stage(args: argparse.Namespace) -> None:
    texts = _load_workload(args.dataset)
    detector = Detector()
    detector.detect("прогрев словарей")  # exclude dictionary load from the numbers
    STAGES.reset()
    context = _context(detector, os.environ["PSEUDEX_DB_DIR"])
    total = _run(texts, context, args.rounds, args.threads)
    _print_stages(total, len(texts) * args.rounds * args.threads)


def _mode_function(args: argparse.Namespace) -> None:
    try:
        import yappi
    except ImportError as error:
        raise SystemExit(
            "yappi is required for --mode function: pip install yappi\n"
            "(yappi, not cProfile: masking runs in a threadpool and cProfile "
            "only profiles the thread it was started on)"
        ) from error
    texts = _load_workload(args.dataset)
    detector = Detector()
    detector.detect("прогрев словарей")
    context = _context(detector, os.environ["PSEUDEX_DB_DIR"])
    yappi.set_clock_type("wall")
    yappi.start()
    _run(texts, context, args.rounds, args.threads)
    yappi.stop()
    stats = yappi.get_func_stats().sort("ttot")
    print(f"\nTop {args.top} functions by total wall time (own code first):\n")
    stats.print_all(columns={0: ("name", 72), 1: ("ncall", 9), 2: ("ttot", 9),
                             3: ("tsub", 9), 4: ("tavg", 9)})


def _mode_line(args: argparse.Namespace) -> None:
    try:
        from line_profiler import LineProfiler
    except ImportError as error:
        raise SystemExit(
            "line_profiler is required for --mode line: pip install line_profiler"
        ) from error
    from pseudex import address, detect, names, normalize, quasi, ru_pii, structured
    from pseudex import detect_all as detect_all_module

    texts = _load_workload(args.dataset)
    detector = Detector()
    detector.detect("прогрев словарей")
    context = _context(detector, os.environ["PSEUDEX_DB_DIR"])

    profiler = LineProfiler()
    for function in (
        Detector.detect, Detector._ner_spans, detect_all_module._resolve,
        address.detect_address, address._regex_candidates, address._merge,
        detect.detect_pii, names.gazetteer_names, names._lemma,
        normalize.normalize, quasi.detect_quasi,
        ru_pii.detect_structured, structured.detect_structured_kv,
    ):
        profiler.add_function(function)
    profiler.runcall(_run, texts, context, args.rounds, 1)
    profiler.print_stats(output_unit=1e-6)
    print("Times are microseconds per line. --threads is forced to 1 here: "
          "line_profiler does not aggregate across threads.")


def main() -> None:
    load_dev_bundle()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("stage", "function", "line"), default="stage")
    parser.add_argument("--rounds", type=int, default=20, help="passes over the workload")
    parser.add_argument("--threads", type=int, default=1, help="concurrent maskers")
    parser.add_argument("--dataset", default=None, help="JSON file of {text: ...} cases")
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    if not ENABLED and args.mode == "stage":
        raise SystemExit("set PSEUDEX_PROFILE=1 (this script sets it by default — "
                         "did something override it?)")
    print(f"mode={args.mode} rounds={args.rounds} threads={args.threads} "
          f"db={os.environ['PSEUDEX_DB_DIR']}", file=sys.stderr)
    {"stage": _mode_stage, "function": _mode_function, "line": _mode_line}[args.mode](args)


if __name__ == "__main__":
    main()
