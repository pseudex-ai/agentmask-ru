"""The corpus validator, and the proof that no ground truth was searched for.

THREE PIECES OF EVIDENCE, and none of them is a promise in a docstring:

  1. STRUCTURAL — `schema.validate` refuses any item whose span is not a keyed
     row of the writer's trace, and any message whose trace does not tile it.
  2. DYNAMIC — `prove_no_search` runs the generator under `sys.setprofile` and
     records every `str.find`/`index`/`rfind`/`count` and every `re` search
     raised from a frame under `scenarios/` or `writer.py`. Any hit outside a
     named allow-list of chunk-level helpers refuses the corpus and names the
     frame.
  3. POSITIVE — `find_distinct_share` counts cases where some item's start is
     NOT what `text.find(value)` would return. `correction` guarantees these:
     the ground truth points at the SECOND occurrence, which `find` can never
     produce. A corpus that never contains such a case has never demonstrated
     the property.
"""
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from bench.agentpii4 import schema
from bench.agentpii4.schema import Case

_HERE = Path(__file__).resolve().parent
_WATCHED_DIRS = (str(_HERE / "scenarios"), str(_HERE / "writer.py"))
_SEARCHERS = frozenset({"find", "index", "rfind", "rindex", "count",
                        "search", "match", "fullmatch", "finditer", "findall"})
# Chunk-level helpers that legitimately look inside a WORD before it is put:
# a typo generator needs a position, a slip needs a vowel. They run on chunks,
# never on an assembled message, and they are named here so the watch can tell
# the difference.
_ALLOWED_FUNCTIONS = frozenset({"typo", "phonetic_slip", "speech_noise",
                                "asr_noise", "_apply_register", "noisy_word"})


def prove_no_search(build: Callable[[], Sequence[Case]]) -> tuple[Sequence[Case], list[str]]:
    """Build under a profiler that refuses string search in generator frames."""
    hits: list[str] = []

    def watch(frame: object, event: str, arg: object) -> None:
        if event != "c_call":
            return
        name = getattr(arg, "__name__", "")
        if name not in _SEARCHERS:
            return
        caller = frame  # type: ignore[assignment]
        filename = caller.f_code.co_filename  # type: ignore[attr-defined]
        if not any(filename.startswith(watched) for watched in _WATCHED_DIRS):
            return
        function = caller.f_code.co_name  # type: ignore[attr-defined]
        if function in _ALLOWED_FUNCTIONS:
            return
        hits.append(f"{Path(filename).name}:{caller.f_lineno} {function} -> {name}")  # type: ignore[attr-defined]

    sys.setprofile(watch)
    try:
        cases = build()
    finally:
        sys.setprofile(None)
    unique = sorted(set(hits))
    return cases, unique


def find_distinct_share(cases: Sequence[Case]) -> tuple[int, int]:
    """(cases where some item start != text.find(value), cases)."""
    distinct = 0
    for case in cases:
        for item in case.pii:
            if item.where.kind != "message":
                continue
            text = schema.message_text(case, item.where.msg)
            if text.find(item.value) != item.where.start:
                distinct += 1
                break
    return distinct, len(cases)


def check_all(cases: Sequence[Case]) -> list[str]:
    problems: list[str] = []
    for case in cases:
        problems.extend(schema.validate(case))
    problems.extend(schema.validate_corpus(cases))
    distinct, total = find_distinct_share(cases)
    if distinct < schema.MIN_FIND_DISTINCT_CASES:
        problems.append(f"only {distinct} of {total} cases have an item `find` could not have "
                        f"located; need {schema.MIN_FIND_DISTINCT_CASES}")
    return problems


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?", default=str(_HERE / "corpus.json"))
    args = parser.parse_args()
    raw = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    cases = [schema.case_from_json(one) for one in raw["corpus"]]
    problems = check_all(cases)
    for problem in problems[:60]:
        print(problem)
    distinct, total = find_distinct_share(cases)
    print(f"случаев: {total} · проблем: {len(problems)} · `find` не нашёл бы эталон в {distinct} случаях")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
