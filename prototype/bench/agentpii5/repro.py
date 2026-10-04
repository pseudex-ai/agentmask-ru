"""AgentPII-RU v5 — ONE command that repeats a run, and an honest list of what
is no longer available (ТЗ `docs/tz-bench-harness.md` §7.3, item 22).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.repro 6f3a91c2
    python3 -m bench.agentpii5.repro --run bench/runs/2026-09-23/v5-live-medium

WHAT THIS IS FOR. Three times in one day of work the question was «чем именно
это гонялось» and the answer took a folder, a git log and a guess. A run is
repeatable only if six things are on the record — the corpus and its digest, the
tier, the seeds, the models WITH their ids, the engine and where it was, and the
NAMES of the environment variables — and this command prints them as one line
plus the list of the ones that have moved since.

IT NEVER PRINTS A VALUE OF AN ENVIRONMENT VARIABLE, only names. A repro command
that carried a key would make every terminal scrollback a credential store, and
the person repeating the run has their own key anyway.

WHAT HAS MOVED IS PART OF THE ANSWER, NOT A WARNING BESIDE IT. A corpus whose
digest no longer matches, a ladder that was redrawn, an engine at another
version, a model the price table no longer knows — each is printed as «было X,
сейчас Y», because the honest repetition of a run whose corpus moved is a
DIFFERENT run, and saying so is the difference between a repeat and a
comparison nobody can interpret.

NO MODEL, NO NETWORK, NO KEY: everything here is read off the run's files, the
registry and the working tree.
"""
import argparse
import json
import os
import shlex
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from bench.agentpii5.provider import (
    ADMIN_TOKEN_ENV,
    GATEWAY_TOKEN_ENV,
    ProviderError,
    credential_names,
    resolve_model,
    resolve_provider,
)
from bench.agentpii5.report import meta_of, run_id_of
from bench.agentpii5.runinfo import RunInfoError, RunRecord, find_run, read_runs
from bench.agentpii5.runinfo import RUNS_PATH

# THE THREE SHAPES THE REGISTRY'S `worktree` FIELD ACTUALLY CARRIES, written
# by `build.worktree_line` and by nothing else: «чисто <sha> (<branch>)»,
# «грязно <sha> (<branch>): N файлов — к коммиту не привязан», «неизвестно».
# This module used to test the field for a `"commit "` prefix NO writer emits,
# so every run in the registry — a clean one above all — was told «числа этого
# прогона не привязаны к коммиту». The discipline of §6.1 exists to make that
# sentence rare; the repro printed it always, which is the same as printing it
# never.
WORKTREE_CLEAN: str = "чисто "
WORKTREE_DIRTY: str = "грязно "

HERE: Path = Path(__file__).resolve().parent
PROTOTYPE: Path = HERE.parent.parent
CORPUS_FILE: Path = HERE / "corpus.v5.json"
LADDER_FILE: Path = HERE / "ladder.json"
VERSION_FILE: Path = PROTOTYPE / "version.txt"
UNKNOWN: str = "неизвестно"


class ReproError(ValueError):
    """A run this command cannot describe. Refusals about the REGISTRY —
    an id nobody wrote, an ambiguous prefix — are `runinfo.RunInfoError` and
    are raised by `runinfo.find_run`: naming a run is that module's job, and a
    second matcher here would be a second answer to «который из них»."""


def digest_of(path: Path) -> str:
    """The `digest` a corpus snapshot carries. "" when the file is not there —
    the caller prints «неизвестно», which is not «совпадает»."""
    if not path.exists():
        return ""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return str(raw.get("digest", "")) if isinstance(raw, dict) else ""


def ladder_digest_of(path: Path) -> str:
    """The ladder's `corpus_sha256` — the stamp R-57 refreshes in place when
    every tier's membership is provably unchanged. A repro that compared the
    ladder FILE byte for byte would call a refresh a redraw."""
    if not path.exists():
        return ""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return str(raw.get("corpus_sha256", "")) if isinstance(raw, dict) else ""


def engine_version_of(path: Path) -> str:
    """`prototype/version.txt` — the ONE source of the engine version (D-053).
    READ AS A FILE, never imported: this package may not import `pseudex`, and
    the number is a fact about the tree either way."""
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


@dataclass(frozen=True)
class ReproPlan:
    """What `repro` prints: the command, the variable NAMES it needs, and what
    has moved since the run."""

    run_id: str
    command: str
    environment: tuple[str, ...]
    moved: tuple[str, ...]
    notes: tuple[str, ...]


def _gateway_of(meta: Mapping[str, object]) -> tuple[str, str]:
    """(the engine's address as the run recorded it, the version it reported).

    From `meta.json`'s `gateway` block (item 13). A run that predates the block
    ran the gateway IN PROCESS, from the source tree, and that is stated rather
    than inferred as «наверное, из дерева»."""
    block = meta.get("gateway")
    if not isinstance(block, dict):
        return ("в процессе, из исходного дерева (прогон старше записи о шлюзе)", "")
    mode = str(block.get("mode") or UNKNOWN)
    if mode != "http":
        return ("в процессе, из исходного дерева", str(block.get("engine_version") or ""))
    where = str(block.get("base_url") or UNKNOWN)
    digest = str(block.get("image_digest") or "")
    return (f"{where}" + (f" · образ {digest}" if digest else " · образ неизвестен"),
            str(block.get("engine_version") or ""))


def _model_notes(meta: Mapping[str, object], record: RunRecord,
                 env: Mapping[str, str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What the run's models are today: still priced, or a line to add.

    The provider is read off `meta.json` when the run recorded one (item 12) and
    is the Anthropic path otherwise — which is what every run before the
    provider layer used, and saying so is not a guess about the future."""
    block = meta.get("provider")
    if isinstance(block, dict) and isinstance(block.get('connectors'), dict):
        connectors = block['connectors']
        names: list[str] = []
        notes: list[str] = []
        if connectors.get('agent') == 'deepseek':
            names.append('DEEPSEEK_API_KEY')
        if connectors.get('judge') == 'codex' and record.judge_model:
            names.append('AGENTPII5_CODEX_HOME')
            notes.append('Codex judge uses ChatGPT sign-in and subscription quota; '
                         'not API billing.')
        return tuple(names), tuple(notes)
    name = str(block.get("provider")) if isinstance(block, dict) else ""
    try:
        provider = resolve_provider(name, env)
    except ProviderError as broken:
        return ((), (f"провайдер прогона не читается: {broken}",))
    environment = list(credential_names(provider))
    moved: list[str] = []
    for role, model in (("agent", record.model), ("judge", record.judge_model)):
        if not model:
            continue
        choice = resolve_model(provider, role, model)
        if choice.price is None:
            moved.append(f"{role}: {choice.unpriced_reason}")
    return (tuple(environment), tuple(moved))


def worktree_verdict(worktree: str) -> tuple[str, str]:
    """What the run's tree says: (the line for the notes, the line for «что
    изменилось» — empty when nothing did).

    THREE STATES, THREE DIFFERENT ANSWERS, and only one of them is a warning.
    A CLEAN tree is the state §6.1 is written to produce: the numbers ARE tied
    to that commit, and the repeat can start by checking it out. A DIRTY tree
    is the state `--dirty-ok` buys: the numbers belong to no commit, and a
    repeat cannot restore what was in the working copy. An UNRECORDED tree —
    `неизвестно`, or a run older than the field — is neither: nothing is known,
    which is not «грязно» and is certainly not «чисто».
    """
    line = worktree.strip()
    if line.startswith(WORKTREE_CLEAN):
        return (f"дерево: {line} — числа привязаны к этому коммиту", "")
    if line.startswith(WORKTREE_DIRTY):
        return (f"дерево: {line}",
                f"рабочее дерево прогона было грязным: {line} — числа этого прогона не "
                f"привязаны к коммиту (§6.1), и повтор пойдёт на другом его состоянии")
    return (f"дерево: {line or UNKNOWN}",
            f"состояние рабочего дерева прогона: {line or UNKNOWN} — привязать его числа "
            f"к коммиту нечем (§6.1)")


def plan(record: RunRecord, corpus: Path, ladder: Path, version_file: Path,
         env: Mapping[str, str]) -> ReproPlan:
    """The whole answer for one run, from files only.

    `corpus`, `ladder` and `version_file` are parameters rather than the module
    constants so the test can drive this against a small tree — a repro command
    that could only be exercised against the real 28 MB corpus is a command
    nobody would exercise."""
    if not record.run_dir.strip():
        raise ReproError(f"строка реестра {record.run_id} не называет каталога прогона: "
                         f"повторить можно, но сверять не с чем — ни меты, ни снимка корпуса")
    run_dir = Path(record.run_dir)
    meta = meta_of(run_dir, run_id_of(run_dir)) if run_dir.exists() else {}
    where, reported = _gateway_of(meta)
    environment, unpriced = _model_notes(meta, record, env)
    moved: list[str] = list(unpriced)
    if not run_dir.exists():
        # NOT a refusal: the tier, the models and the ceiling are in the
        # registry, so the run CAN be repeated — what is lost is the snapshot to
        # compare against and the gateway the run measured, and that is exactly
        # what this list is for.
        moved.append(f"каталога прогона {run_dir} нет: снимок корпуса и мета недоступны, "
                     f"повтор пойдёт на корпусе из дерева")

    tree_corpus = digest_of(corpus)
    if not tree_corpus:
        moved.append(f"корпуса {corpus} нет — пересоберите его (build) до повтора")
    elif record.corpus_digest and tree_corpus != record.corpus_digest:
        moved.append(f"корпус: прогон шёл на {record.corpus_digest[:12]}, в дереве "
                     f"{tree_corpus[:12]} — это ДРУГОЙ прогон; возьмите снимок из "
                     f"{run_dir / 'corpus.v5.json'}")
    tree_ladder = ladder_digest_of(ladder)
    if record.ladder_digest and tree_ladder and tree_ladder != record.ladder_digest:
        moved.append(f"лестница: прогон шёл на {record.ladder_digest[:12]}, в дереве "
                     f"{tree_ladder[:12]} — состав яруса мог измениться (R-52, R-57)")
    tree_version = engine_version_of(version_file)
    if reported and tree_version and reported != tree_version:
        moved.append(f"движок: прогон мерил {reported}, в дереве {tree_version}")
    if not reported:
        moved.append(f"версия движка прогона {UNKNOWN} — сверить не с чем")
    tree_note, tree_moved = worktree_verdict(record.worktree)
    if tree_moved:
        moved.append(tree_moved)

    # The corpus a repeat should use: the run's OWN snapshot when the tree has
    # moved, the tree's otherwise. `write_corpus` put it there before the first
    # dollar precisely so a replay does not depend on the tree.
    snapshot = run_dir / "corpus.v5.json"
    use_corpus = snapshot if (record.corpus_digest and tree_corpus != record.corpus_digest
                              and snapshot.exists()) else corpus
    parts = ["python3", "-m", "bench.agentpii5.harness", str(use_corpus),
             "--ladder", str(ladder), "--tier", record.tier,
             "--repeats", str(record.repeats),
             "--ceiling", f"{record.ceiling_usd:.2f}",
             "--model", record.model,
             "--judge-model", record.judge_model,
             "--label", f"повтор {record.run_id[:8]}"]
    provider_block = meta.get('provider')
    if isinstance(provider_block, dict) and isinstance(provider_block.get('connectors'), dict):
        connectors = provider_block['connectors']
        for key in ('agent', 'judge'):
            parts += [f'--{key}-connector', str(connectors[key]),
                      f'--{key}-effort', str(connectors[f'{key}_effort'])]
        parts += ['--connector-max-tokens', str(connectors['max_tokens']),
                  '--agent-turn-limit', str(connectors['agent_turn_limit']),
                  '--judge-request-limit', str(connectors['judge_request_limit'])]
        if 'max_calls' in connectors:
            parts += ['--max-calls', str(connectors['max_calls'])]
        if connectors.get('agent') == 'deepseek':
            parts += ['--provider', 'deepseek']
        if not record.judge_model:
            parts += ['--no-judge']
        if record.tier not in ('nano', 'small', 'medium', 'large', 'holdout', 'max'):
            if not snapshot.exists():
                raise ReproError('connector selection requires the recorded corpus snapshot')
            saved = json.loads(snapshot.read_text(encoding='utf-8'))
            ids = [str(row['base']['id']) for row in saved['corpus']]
            at = parts.index('--tier')
            parts[at:at + 2] = ['--ids', ','.join(ids)]
    gateway = meta.get("gateway")
    if isinstance(gateway, dict) and gateway.get("mode") == "http" and gateway.get("base_url"):
        parts += ["--gateway", str(gateway["base_url"])]
        environment = tuple(list(environment) + [GATEWAY_TOKEN_ENV, ADMIN_TOKEN_ENV])
    notes = (
        f"прогон {record.run_id} · {record.started} · ярус {record.tier} · "
        f"случаев {record.cases} · метка «{record.label or '—'}»",
        f"заметка: {record.note or '—'}",
        f"движок: {where} · версия {reported or UNKNOWN} (в дереве "
        f"{tree_version or UNKNOWN})",
        tree_note,
        f"сиды: лестница {record.ladder_digest[:12] or UNKNOWN}, корпус "
        f"{record.corpus_digest[:12] or UNKNOWN} — v5 не принимает --seed, "
        f"выборку задаёт лестница",
        f"стоило ${record.spent_usd:.2f} из ${record.ceiling_usd:.2f} · вердикт "
        f"{record.verdict}")
    return ReproPlan(run_id=record.run_id, command=" ".join(shlex.quote(one) for one in parts),
                     environment=tuple(dict.fromkeys(environment)), moved=tuple(moved),
                     notes=notes)


def render(one: ReproPlan) -> list[str]:
    """The printed answer: the notes, the one command, the names to export, and
    what has moved."""
    out = [f"# повтор прогона {one.run_id}"]
    out += [f"#   {line}" for line in one.notes]
    out += ["", "# экспортируйте (ИМЕНА, значения ваши):"]
    out += [f"#   export {name}=…" for name in one.environment] or ["#   (переменных нет)"]
    out += ["", one.command, ""]
    out.append("# что изменилось с тех пор:")
    out += [f"#   {line}" for line in one.moved] or ["#   ничего: повтор — это повтор"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id", nargs="?", default="", help="id прогона или его начало")
    parser.add_argument("--runs", default=str(RUNS_PATH))
    parser.add_argument("--corpus", default=str(CORPUS_FILE))
    parser.add_argument("--ladder", default=str(LADDER_FILE))
    parser.add_argument("--version-file", default=str(VERSION_FILE))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.run_id:
        parser.error("нужен id прогона (или его начало)")
    registry_path = Path(args.runs)
    if not registry_path.exists():
        print(f"{registry_path} нет: реестр создаёт первый прогон (ТЗ §1.2)", file=sys.stderr)
        return 2
    try:
        record = find_run(read_runs(registry_path), args.run_id)
    except RunInfoError as broken:
        print(broken, file=sys.stderr)
        return 2
    built = plan(record, Path(args.corpus), Path(args.ladder), Path(args.version_file),
                 dict(os.environ))
    if args.json:
        print(json.dumps({"run_id": built.run_id, "command": built.command,
                          "environment": list(built.environment),
                          "moved": list(built.moved), "notes": list(built.notes)},
                         ensure_ascii=False, indent=2))
        return 0
    for line in render(built):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
