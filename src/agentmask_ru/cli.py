"""The one entry point: build, validate, gates, run, leaderboard.

    agentmask build --seed 20260920
    agentmask gates
    agentmask run --adapter placeholder_regex --out results/
    agentmask run --adapter openai_proxy --name cloudru --base-url http://localhost:8080/v1 \
        --upstream-bind 0.0.0.0:8099 --out results/
    agentmask leaderboard
"""

import argparse
import sys
from pathlib import Path

from agentmask_ru import build as build_module
from agentmask_ru import gates as gates_module
from agentmask_ru import leaderboard as leaderboard_module
from agentmask_ru.harness import run as run_harness
from agentmask_ru.policy import POLICIES
from agentmask_ru.registry import ADAPTERS, build as build_masker
from agentmask_ru.report import render
from agentmask_ru.results import manifest, to_payload, write
from agentmask_ru.schema import load_dir, validate
from agentmask_ru.score import score


def _cmd_run(args: argparse.Namespace) -> int:
    cases = load_dir(Path(args.cases))
    if not cases:
        print(f"в {args.cases} нет случаев", file=sys.stderr)
        return 1
    if args.limit:
        cases = cases[: args.limit]
    masker, upstream = build_masker(args)
    try:
        observations = run_harness(masker, cases, args.policy, args.seed)
    finally:
        if upstream is not None:
            upstream.stop()
    scores = score(observations)
    print(render(masker.name, scores, observations))
    if args.out:
        meta = manifest(masker.name, masker.config, args.policy, args.seed, cases, args.submitted_by, args.notes)
        path = Path(args.out) / masker.name / f"{meta.run_at.replace(':', '').replace('-', '')}.json"
        write(path, to_payload(meta, scores, observations))
        print(f"\nзапись прогона: {path}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    cases = load_dir(Path(args.cases))
    problems = [(case.id, problem) for case in cases for problem in validate(case)]
    for case_id, problem in problems:
        print(f"{case_id}: {problem}", file=sys.stderr)
    print(f"{len(cases)} случаев, дефектов: {len(problems)}")
    return 1 if problems else 0


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
    parser = argparse.ArgumentParser(prog="agentmask", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="сгенерировать корпус")
    p_build.add_argument("--seed", type=int, required=True)
    p_build.add_argument("--out", default="cases")
    p_build.add_argument("--created", default=None)
    p_build.add_argument("--check", action="store_true")

    p_validate = sub.add_parser("validate", help="проверить случаи")
    p_validate.add_argument("--cases", default="cases")

    p_gates = sub.add_parser("gates", help="проверки корпуса и репозитория")
    p_gates.add_argument("--cases", default="cases")
    p_gates.add_argument("--root", default=".")

    p_run = sub.add_parser("run", help="прогнать маскировщик по корпусу")
    p_run.add_argument("--adapter", required=True, choices=ADAPTERS)
    p_run.add_argument("--name", default=None, help="как система называется в таблице")
    p_run.add_argument("--cases", default="cases")
    p_run.add_argument("--policy", default="copier", choices=POLICIES)
    p_run.add_argument("--seed", type=int, default=20260920)
    p_run.add_argument("--limit", type=int, default=0)
    p_run.add_argument("--out", default=None, help="каталог для записи прогона")
    p_run.add_argument("--base-url", default=None)
    p_run.add_argument("--api-key", default="unused")
    p_run.add_argument("--model", default="agentmask-fake")
    p_run.add_argument("--org-id", default="agentmask")
    p_run.add_argument("--language", default="ru")
    p_run.add_argument("--timeout", type=float, default=60.0)
    p_run.add_argument("--upstream-bind", default="127.0.0.1:0",
                       help="где слушает фальшивый провайдер; 0.0.0.0:8099 для контейнеров")
    p_run.add_argument("--submitted-by", default="", help="кто прислал прогон")
    p_run.add_argument("--notes", default="", help="что важно знать о конфигурации")

    p_board = sub.add_parser("leaderboard", help="собрать таблицу из results/")
    p_board.add_argument("--results", default="results")
    p_board.add_argument("--cases", default="cases")
    p_board.add_argument("--out", default="leaderboard.md")

    args = parser.parse_args(argv)
    if args.command == "build":
        argv_build = ["--seed", str(args.seed), "--out", args.out]
        if args.created:
            argv_build += ["--created", args.created]
        if args.check:
            argv_build.append("--check")
        sys.argv = ["build"] + argv_build
        return build_module.main()
    if args.command == "validate":
        return _cmd_validate(args)
    if args.command == "gates":
        return gates_module.main(["--cases", args.cases, "--root", args.root])
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "leaderboard":
        return leaderboard_module.main(["--results", args.results, "--cases", args.cases, "--out", args.out])
    raise SystemExit(f"unknown command {args.command}")


if __name__ == "__main__":
    sys.exit(main())
