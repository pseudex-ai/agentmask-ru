# PROTOCOL — how to keep this wiki true

The wiki is only worth relying on if it stays equal to the code. This file is the
contract for that. It is short on purpose.

## The files

| file | holds | changes when |
|---|---|---|
| [`MAP.md`](MAP.md) | where everything lives, who calls it, which test pins it | a module, test, benchmark, doc, deploy file or CI workflow is added, renamed or removed |
| [`FLOWS.md`](FLOWS.md) | how a request / lease / store / build moves, with real function names | a step of one of those flows changes, or a named function is renamed |
| [`INVARIANTS.md`](INVARIANTS.md) | the rules a change must not break, each with its pinning test | a rule is learned, retired, or its test changes |
| [`STATE.md`](STATE.md) | every decision, the rejected alternative, the price (`D-NNN`) | a fork is decided or reversed |
| [`INDEX.md`](INDEX.md) | what each `docs/` and `research/` file answers, and its status | a doc or research file is added or its status changes |
| [`check.py`](check.py) | the checker that proves the four above against the code | the shape of any wiki file changes |

`MAP.md` is copied verbatim into `CLAUDE.md` between `<!-- wiki:MAP:begin -->`
and `<!-- wiki:MAP:end -->`, so an agent that only reads `CLAUDE.md` still has
the map. That copy is machine-maintained — never edit it by hand.

## The rule for an agent making a change

When your change adds or moves a module, a test, a benchmark, a doc, a deploy
file, a CI workflow, a rule or a decision, **update the wiki in the same
change**, then:

```bash
python3 wiki/check.py --sync   # rewrites the MAP block inside CLAUDE.md from MAP.md
python3 wiki/check.py          # must print "0 finding(s)"
```

`--sync` is the only correct way to update the copy in `CLAUDE.md`. If you edited
`check.py` itself, also run `python3 wiki/check.py --selftest` — it breaks the
wiki in known ways and refuses to pass unless it catches every break, so a
checker that has stopped checking cannot go green.

## What the checker proves (and what it cannot)

`check.py` proves, mechanically:

- **map** — every path the wiki names exists; every `pseudex/` module has an
  entry whose `Uses` / `Used by` / `API` equal the real import graph and public
  names; every "direct test" the map names really imports that module; every
  test, bench script, e2e gate, deploy file and workflow in the tree is on the
  map.
- **flows** — every `module.function` and `Class.method` FLOWS.md names is a real
  definition.
- **invariants** — every rule names a test that exists (or is marked `UNPINNED`);
  every `INVARIANTS.md#anchor` referenced from MAP or STATE resolves.
- **state** — decision ids are unique; every path a decision cites exists.
- **index** — every `docs/` and `research/` file has a row; every path exists.
- **claude** — the embedded map equals `MAP.md` byte for byte.

It **cannot** prove that prose is true — that a description matches behaviour,
that a status is current, that a decision still holds. Those are the parts a
human keeps honest. The checker guarantees the skeleton (paths, imports, tests,
symbols, cross-references); you guarantee the flesh.

## The one habit that matters

When you touch the code and the wiki disagrees with what you did, the wiki is
wrong — fix it, do not work around it. A single stale row teaches the next agent
to distrust the whole map, and then the map is worth nothing. `CLAUDE.md` earned
that distrust once (16 tests and 4 directories missing, invisible because prose
reads the same whether a file is there or not); `check.py` exists so it cannot
happen silently again, but only the habit keeps the prose worth reading.

## CI

`wiki/check.py --selftest` runs on every push as the `wiki` job in
`.github/workflows/checks.yml`. A map that has drifted from the code fails the
build — that is what makes "always rely on the map" a fact rather than a hope.
