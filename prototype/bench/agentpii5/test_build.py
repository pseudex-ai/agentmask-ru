"""The assembled corpus, its two files, and the holdout that must not move.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_build

WHAT THIS PINS THAT NOTHING ELSE DOES. `validate_v5` answers for a case and
`validate_corpus_v5` for a list of cases; neither can see a FILE. Three claims
live only here: the v4 view on disk is readable by v4's own reader, the v5 file
round-trips to the same digest, and the holdout tier is frozen — a second build
without `--regenerate-ladder` leaves `ladder.json` byte for byte as it was.

THE HOLDOUT IS THE ONE THAT MATTERS (K12). Its whole value is that it was drawn
before anyone looked; a build that redrew it whenever the corpus grew would hand
back twenty per cent of the corpus that had seen every debugging run of the
week, and no number computed on it would mean what it says.

EVERYTHING IS WRITTEN INTO A TEMPORARY DIRECTORY. A test that wrote
`corpus.v5.json` beside the real one would make running the tests a way to
change the corpus.

NOTHING HERE IMPORTS `pseudex`, AND NO CHECK HERE CALLS A MODEL.
"""
import ast
import json
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from bench.agentpii4.build import build_ladder, ladder_problems
from bench.agentpii4.schema import case_from_json
from bench.agentpii5 import build as b
from bench.agentpii5 import contracts as c
from bench.agentpii5 import mock
from bench.agentpii5 import revise as revise_module
from bench.agentpii5.contracts import CaseV5, Hop
from bench.agentpii5.metrics import leaf_value_ok, returned_as_item
from bench.agentpii5.schema import case_v5_from_json, corpus_digest_v5, validate_corpus_v5
from bench.agentpii5.scenarios5 import common
from bench.agentpii5.test_perfect import ACCEPTANCE_TIER
from bench.agentpii5.tools import REGISTRY_V5, spec_v5_for

SEED: int = b.SEED
# The sentence an agent writes around a value it was handed. Any prose does;
# what matters is that the value is INSIDE something else, which is the whole
# difference between the free branch and byte equality.
PROSE: str = "Здравствуйте, {value}! Ваш заказ принят, курьер приедет завтра."
# Another person's value per type, two candidates each so one can be rejected
# for sharing a word with the right answer. «ленина» is a street of half the
# corpus, and a fixed decoy that collides with the case's own value reports a
# vacuous transition where there is none.
DECOYS: dict[str, tuple[str, str]] = {
    "NAME": ("Шестаков Аркадий Феофанович", "Юрганова Ядвига Эдуардовна"),
    "LOC": ("щербаковская", "тюфелева"),
    "PHONE": ("+7 (901) 222-33-44", "+7 (902) 555-66-77"),
    "EMAIL": ("zzz@example.org", "qqq@example.net"),
    "DOB": ("1901-02-03", "1902-03-04"),
    "INN": ("520832613767", "771234567890"),
    "CARD": ("2200233420297500", "4276380012345678"),
    "SNILS": ("168-408-927 05", "112-233-445 95"),
    "PLATE": ("Х501УН36", "А997ММ63"),
    "PASSPORT": ("6942 551133", "4510 123456")}
# Built once, THROUGH THE REPORTING PATH. The corpus is 1 736 cases and the whole
# assembly takes a second; doing it in six checks would make the suite slow
# enough to stop being run. `build_reporting` is the same build plus the
# downgrades counted by reason — what `chain_table` prints — so taking it here
# costs nothing and lets the printed table be checked against the real counter
# rather than against one made up for the test.
CASES, DOWNGRADES, _DROPPED = b.build_reporting(SEED, False)


def test_corpus_size_and_plan() -> list[str]:
    """Every planned family contributes its count, and the total is the three
    halves added up — not a number that happens to be in the band."""
    problems: list[str] = []
    revised = sum(1 for case in CASES if case.revised_from_v4)
    planned = sum(count for _module, count in b.PLAN)
    if revised != c.V4_CORPUS_SIZE:
        problems.append(f"{revised} revised cases, v4 has {c.V4_CORPUS_SIZE}")
    if len(CASES) != revised + planned:
        problems.append(f"{len(CASES)} cases, expected {revised} + {planned}")
    low, high = c.CORPUS_SIZE_BAND_V5
    if not low <= len(CASES) <= high:
        problems.append(f"{len(CASES)} cases, band {c.CORPUS_SIZE_BAND_V5}")
    return problems


def test_corpus_rules() -> list[str]:
    """Every corpus rule, reported in full rather than as a count. K03 is
    enforced here with the other fourteen: it was red at 73.1 % until ruling
    R-23 converted the authored no-result cases (1203 / 1594 = 75.5 %), and the
    tripwire that printed that arithmetic retired the day it went green."""
    return validate_corpus_v5(CASES, tuple(REGISTRY_V5))


def test_v4_view_loads() -> list[str]:
    """v4's own reader opens every entry of the v4 view, and the digest in the
    file is the one v4 computes over it."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        b.write_corpus(CASES, out)
        stored = json.loads((out / "corpus.json").read_text(encoding="utf-8"))
        if len(stored["corpus"]) != len(CASES):
            problems.append(f"the v4 view holds {len(stored['corpus'])} of {len(CASES)}")
        for row in stored["corpus"]:
            case_from_json(row)
        identifiers = [row["id"] for row in stored["corpus"]]
        if identifiers != [case.base.id for case in CASES]:
            problems.append("the v4 view is not in corpus order")
    return problems


def test_v5_round_trip() -> list[str]:
    """The v5 file reads back to the same digest — and a doctored file does not.

    A corpus that cannot be read back is a corpus nobody can run, and the digest
    is what the ladder is pinned to, so «reads back» has to mean «reads back
    identically» rather than «parses».
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        digest = b.write_corpus(CASES, out)
        stored = json.loads((out / "corpus.v5.json").read_text(encoding="utf-8"))
        reread = [case_v5_from_json(row) for row in stored["corpus"]]
        if corpus_digest_v5(reread) != digest:
            problems.append("the written corpus reads back to another digest")
        if stored["digest"] != digest:
            problems.append("the file's own digest is not the corpus's")
        doctored = list(stored["corpus"])
        doctored[0] = dict(doctored[0])
        doctored[0]["streaming"] = not doctored[0]["streaming"]
        if corpus_digest_v5([case_v5_from_json(row) for row in doctored]) == digest:
            problems.append("flipping one case's streaming flag left the digest equal")
    return problems


def test_holdout_frozen() -> list[str]:
    """K12: a second build without the flag leaves `ladder.json` byte-identical,
    and `--regenerate-ladder` is the only thing that may touch it."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        ladder, _lines, broken = b.write_ladder(CASES, SEED, out, True, False)
        if ladder is None or broken:
            return [f"the first build wrote no ladder: {broken}"]
        first = (out / "ladder.json").read_bytes()
        again, lines, broken = b.write_ladder(CASES, SEED, out, False, False)
        if again is not None:
            problems.append("a second build rebuilt the ladder without the flag")
        if broken:
            problems.append(f"an unchanged corpus was refused its own ladder: {broken}")
        if (out / "ladder.json").read_bytes() != first:
            problems.append("a second build changed ladder.json")
        if not any("--regenerate-ladder" in line for line in lines):
            problems.append("the second build did not say how to redraw the ladder")
        # …and the flag is not a way PAST the freeze either: a corpus that lost
        # half its cases would redraw the holdout of the survivors, so the
        # regeneration is refused and the file stays exactly as it was. The
        # freeze above would otherwise be the freeze of a function that never
        # writes, and this is the write it declines to make.
        shrunk = CASES[: len(CASES) // 2]
        _ladder, _lines, broken = b.write_ladder(shrunk, SEED, out, True, False)
        if not broken:
            problems.append("--regenerate-ladder on half the corpus moved the holdout "
                            "without saying so")
        if (out / "ladder.json").read_bytes() != first:
            problems.append("a refused regeneration wrote the file anyway")
    return problems


def test_a_changed_corpus_refuses_the_kept_ladder() -> list[str]:
    """THE DIRECTION K12 IS ACTUALLY ABOUT, and the one nothing watched.

    The freeze above only ever saw a corpus that had not changed. Rebuilding
    with another seed into a directory holding today's ladder printed «лестница
    оставлена как есть» and exited 0 while 162 of 319 holdout ids named a
    DIFFERENT case — a holdout frozen against nothing. The refusal names the
    movement, and `--regenerate-ladder` is refused in turn if it would move a
    case that still exists between tiers.

    UNDER R-57 THE REFUSAL IS ABOUT MEMBERSHIP, NOT ABOUT THE HASH. A corpus
    that changed only in bytes — a surface repaired, a column renamed — leaves
    every tier holding the same case ids, and `build` refreshes the stamp and
    prints the proof; a corpus whose draw would move even one id is refused and
    the file is left alone.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        b.write_ladder(CASES, SEED, out, True, False)
        before = (out / "ladder.json").read_bytes()
        # A corpus that lost two hundred cases: the draw moves ids between tiers,
        # which is the movement the freeze exists for.
        shrunk = CASES[: len(CASES) - 200]
        kept, _lines, broken = b.write_ladder(shrunk, SEED, out, False, False)
        if kept is not None:
            problems.append("a changed corpus rebuilt the ladder by itself")
        if not broken:
            problems.append("a corpus whose tiers moved kept the ladder silently")
        elif "СДВИНУЛСЯ" not in broken[0]:
            problems.append(f"the refusal does not name the movement: {broken[0]}")
        if (out / "ladder.json").read_bytes() != before:
            problems.append("a refused refresh wrote the file anyway")
        # …and the refusal is about the MOVEMENT, not about any change: the same
        # cases are accepted again.
        _kept, _lines, still = b.write_ladder(CASES, SEED, out, False, False)
        if still:
            problems.append(f"the unchanged corpus was refused too: {still}")
    return problems


def test_regeneration_keeps_the_holdout() -> list[str]:
    """`--regenerate-ladder` may distribute NEW cases and may not move an
    existing one: a holdout that changed tier is a holdout that has seen the
    debugging it was drawn to avoid."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        b.write_ladder(CASES, SEED, out, True, False)
        first = json.loads((out / "ladder.json").read_text(encoding="utf-8"))
        _ladder, _lines, broken = b.write_ladder(CASES, SEED, out, True, False)
        if broken:
            problems.append(f"an identical corpus moved its own holdout: {broken}")
        # The negative: a ladder whose holdout was drawn from ANOTHER corpus must
        # be refused, and `_holdout_moved` is what says so.
        foreign = dict(first)
        tiers = {name: list(ids) for name, ids in first["tiers"].items()}
        tiers["holdout"] = [identifier for identifier in tiers["holdout"]][:-1]
        moved_out = first["tiers"]["holdout"][-1]
        foreign["tiers"] = tiers
        (out / "ladder.json").write_text(json.dumps(foreign, ensure_ascii=False),
                                         encoding="utf-8")
        _ladder, _lines, broken = b.write_ladder(CASES, SEED, out, True, False)
        if not broken:
            problems.append(f"a holdout missing {moved_out} was accepted as frozen")
        # …AND THE ONE TIME IT MAY MOVE (R-52). The assertion that no live run
        # has read this ladder yet is the only thing that lets the same movement
        # through, and it has to SAY how many cases changed tier — a redraw that
        # moved a fifth of the corpus quietly is the failure the refusal above
        # exists for.
        _ladder, lines, broken = b.write_ladder(CASES, SEED, out, True, True)
        if broken:
            problems.append(f"the assertion did not let the one allowed redraw through: "
                            f"{broken}")
        if not any("сменили ярус" in line for line in lines):
            problems.append("the allowed redraw did not report the movement it made")
    return problems


def test_holdout_is_disjoint() -> list[str]:
    """The holdout is a fifth of the corpus and appears in no debug tier."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        ladder, _lines, _broken = b.write_ladder(CASES, SEED, out, True, False)
        if ladder is None:
            return ["no ladder was written"]
        held = set(ladder.tiers["holdout"])
        for name in ("nano", "small", "medium", "large"):
            overlap = held & set(ladder.tiers[name])
            if overlap:
                problems.append(f"{len(overlap)} holdout cases leaked into {name}")
        share = len(held) / len(CASES)
        if abs(share - c.HOLDOUT_SHARE) > 0.03:
            problems.append(f"holdout is {share:.1%} of the corpus, want "
                            f"{c.HOLDOUT_SHARE:.0%}")
        if set(ladder.tiers["max"]) != {case.base.id for case in CASES}:
            problems.append("the max tier is not the corpus")
    return problems


def test_check_prints_shares() -> list[str]:
    """The tables a reader needs are actually printed: behaviours, both register
    views, the result share, the two new types, the owners, and an MDE line per
    family."""
    problems: list[str] = []
    lines = (b.coverage_table(CASES) + b.mde_table(CASES) + b.form_disagreements(CASES)
             + b.loop_table(CASES) + b.chain_table(CASES, DOWNGRADES)
             + b.downgrade_lines(DOWNGRADES))
    text = "\n".join(lines)
    for needed in ("поведение:", "регистр (весь корпус):", "регистр (написано в v5):",
                   "с результатом инструмента:", "потоковых:", "владельцы переходов:",
                   "явный conversation_id:", "формы ответа (проверены на реальном моке):",
                   "одиночные:", "цепочки:", "написано в v5", "ушло по R-49",
                   "MDE по семьям"):
        if needed not in text:
            problems.append(f"--check prints no {needed!r}")
    for behaviour in c.BEHAVIOURS:
        if not any(line.strip().startswith(behaviour) and "MDE" in line for line in lines):
            problems.append(f"no MDE line for {behaviour!r}")
    for kind in c.MIN_CASES_BY_TYPE:
        if f"{kind}: несут" not in text:
            problems.append(f"no case count for type {kind}")
    return problems


def test_the_authored_and_the_revised_halves_are_counted_apart() -> list[str]:
    """R-50 and R-49 in the printed tables: `single` and `sequential_chain` are
    each a family the revised corpus supplies part of, and one number for either
    would be read as a claim about a shape most of it does not have.

    THE NUMBERS ARE CHECKED AGAINST THE CORPUS, not against a literal. A table
    that printed «написано в v5 100» while the plan built ninety would be a table
    nobody could use, and a literal here would have to be edited every time the
    plan does.
    """
    problems: list[str] = []
    text = "\n".join(b.loop_table(CASES) + b.chain_table(CASES, DOWNGRADES))
    for behaviour in ("single", "sequential_chain"):
        authored = sum(1 for case in CASES
                       if case.behaviour == behaviour and not case.revised_from_v4)
        revised = sum(1 for case in CASES
                      if case.behaviour == behaviour and case.revised_from_v4)
        if f"написано в v5 {authored}" not in text:
            problems.append(f"{behaviour}: the table does not print «написано в v5 "
                            f"{authored}»")
        if f"ревизия v4 {revised}" not in text:
            problems.append(f"{behaviour}: the table does not print «ревизия v4 {revised}»")
    left = sum(count for label, count in DOWNGRADES.items()
               if label.endswith(revise_module.MUTATING_REASON))
    if not left:
        problems.append("no case left sequential_chain under R-49; either the rule is gone "
                        "or the v4 corpus stopped carrying an update fed by a lookup")
    if f"ушло по R-49 (аргумент мутирующего вызова — сказанное клиентом) {left}" not in text:
        problems.append(f"the chain table does not print the R-49 departures ({left})")
    # THE NEGATIVE: with no downgrades reported the line must not claim any.
    if "клиентом) 0" not in "\n".join(b.chain_table(CASES, Counter())):
        problems.append("an empty downgrade counter still printed R-49 departures")
    return problems


def test_regenerating_the_ladder_needs_the_assertion() -> list[str]:
    """R-52: the holdout may be redrawn only while nobody has run against it, and
    the caller has to SAY so — `--regenerate-ladder` is what to do, not what is
    true.

    BOTH ANSWERS, because a refusal that has only ever been watched refusing
    could be a function that returns a string unconditionally.
    """
    problems: list[str] = []
    refusal = b.ladder_refusal(True, False)
    if "--unfrozen-before-first-run" not in refusal:
        problems.append(f"redrawing without the assertion was not refused by name: "
                        f"{refusal!r}")
    if b.ladder_refusal(True, True):
        problems.append("the assertion did not let the redraw through")
    if b.ladder_refusal(False, False):
        problems.append("an ordinary build was refused a ladder it does not redraw")
    return problems


def test_no_search_in_any_generator() -> list[str]:
    """The dynamic proof, widened to `scenarios5/`. v4's own watch list does not
    include it, so an unwidened run would prove the property of the half that no
    longer needs proving."""
    _cases, hits = b.prove_no_search_v5(SEED)
    return [f"search in a generator: {hit}" for hit in hits]


def test_static_proof_sees_containment() -> list[str]:
    """The `in` operator and a hand-rolled scan, which the dynamic watch cannot
    see at all.

    THE REPRODUCTION THIS PINS (corpus-lens/proof_nosearch.py): `str.find`
    inside a watched directory was caught, `x in y` and a slice scan were not,
    and `revise.py` — which builds 834 of the 1 594 cases and did ask
    `item.value in case.messages[turn].content` — was outside the watched set
    entirely.
    """
    problems: list[str] = []
    if b.static_search_hits():
        problems.append(f"a builder searches a finished string: {b.static_search_hits()[0]}")
    watched = {Path(one).name for one in b.WATCHED_V5}
    for needed in ("revise.py", "build.py", "scenarios5"):
        if needed not in watched:
            problems.append(f"{needed} is not watched")
    # THE NEGATIVE: each forbidden shape, read off its own AST.
    for source, why in (("item.value in case.messages[turn].content", "the `in` operator"),
                        ("case.messages[t].content.find(value)", "str.find"),
                        ("log.result_text.startswith(value)", "startswith"),
                        ("re.search(pattern, rendered)", "re.search"),
                        ("body.index(value)", "str.index")):
        node = ast.parse(source, mode="eval").body
        if not any(b._searched_surface(one) for one in ast.walk(node)):   # noqa: SLF001
            problems.append(f"the static proof does not see {why}")
    # …and it does not fire on what a builder legitimately does.
    for source in ("writer.put(text, tag)", "x in values", "text.replace(old, new)"):
        node = ast.parse(source, mode="eval").body
        if any(b._searched_surface(one) for one in ast.walk(node)):       # noqa: SLF001
            problems.append(f"the static proof fires on {source!r}")
    return problems


def test_every_case_proves_its_declaration() -> list[str]:
    """`build` refuses a corpus whose declarations the real backend does not
    produce (T1, T4, T5): a phantom result item, a return form the tool does not
    answer in, an IN hop with no rendered span."""
    problems: list[str] = []
    if b.proof_problems(CASES):
        problems.append(f"the built corpus does not prove itself: "
                        f"{b.proof_problems(CASES)[0]}")
    with_return = next(case for case in CASES if case.returns)
    phantom = replace(with_return, returns=(replace(
        with_return.returns[0],
        result_item_ids=with_return.returns[0].result_item_ids + ("ghost",)),))
    if not b.proof_problems([phantom]):
        problems.append("a declared result item the backend never renders passed the build")
    forms = {one.form for one in REGISTRY_V5[with_return.returns[0].tool_name].return_forms}
    other = sorted(forms - {with_return.returns[0].return_form})
    if not other:
        problems.append(f"{with_return.returns[0].tool_name} declares one form only; "
                        f"pick another case for the form negative")
    elif not b.proof_problems([replace(with_return, returns=(
            replace(with_return.returns[0], return_form=other[0]),))]):
        problems.append("a wrong return_form passed the build")
    return problems


def test_no_value_is_beyond_both_ways_of_scoring_it() -> list[str]:
    """V06 (R-58): a value below the identifying floor that no result tags can
    be scored by neither a span nor a needle, so it would sit in a denominator
    nothing can move.

    THE CORPUS CARRIES NO SUCH VALUE — and that is why the negative is BUILT
    rather than found. The one class it had, the filled form's house number,
    was removed from the declaration in the same round («19» names nobody and
    stood inside «1977-01-07», which cost `doc_masked` eight cases of a perfect
    gateway); a rule with nothing left to refuse in the corpus is exactly the
    rule that has to be shown refusing something, or the next family to seed a
    house number nobody reads brings the defect back in silence."""
    problems: list[str] = []
    if b.proof_problems(CASES):
        problems.append(f"the built corpus does not prove itself: {b.proof_problems(CASES)[0]}")
    if any(not mock.identifies_on_its_own(item.value)
           for case in CASES for item in case.base.pii):
        problems.append("a value below the identifying floor reached the corpus; V06 lets it "
                        "through only while some result tags it, and that is a trap to look at")
    case = next(one for one in CASES if any(item.where.kind == "seed" for item in one.base.pii))
    seed = next(item for item in case.base.pii if item.where.kind == "seed")
    # THE NEGATIVE, IN TWO INDEPENDENT HALVES. Short AND untagged is refused;
    # each half alone is not, so the rule cannot be passing by accident of
    # either condition.
    for value, tagged, want in (("19", False, True), ("19", True, False),
                                (seed.value, False, False)):
        items = tuple(replace(item, value=value) if item.id == seed.id else item
                      for item in case.base.pii)
        records = case.base.seed_records if tagged else tuple(
            replace(record, pii_ids=tuple(one for one in record.pii_ids if one != seed.id))
            if record.id == seed.where.record else record
            for record in case.base.seed_records)
        doctored = replace(case, base=replace(case.base, pii=items, seed_records=records))
        fired = [line for line in b.proof_problems([doctored]) if line.startswith("V06")]
        if bool(fired) != want:
            problems.append(f"V06 on value={value!r} tagged={tagged}: "
                            f"{'fired' if fired else 'silent'}, expected "
                            f"{'a refusal' if want else 'silence'}")
    return problems


def test_every_extracted_item_has_a_hop() -> list[str]:
    """H4.1 over the BUILT corpus, not over a fixture: `doc_extracted`'s
    denominator is `extracted_item_ids` and its numerator needs an OUT hop into
    `extract_to_tool`, so an item with no such hop is a case the line cannot
    ever credit. Fifty of 375 were exactly that — the ceiling was 86.7% and
    nothing printed it. The table is checked against the corpus rather than
    against a literal, so a family that grows cannot make the row stale."""
    problems: list[str] = []
    declared = 0
    for case in CASES:
        document = case.document
        if document is None:
            continue
        declared += len(document.extracted_item_ids)
        for item_id in document.extracted_item_ids:
            if not any(hop.kind == "OUT" and hop.item_id == item_id
                       and hop.tool_name == document.extract_to_tool for hop in case.hops):
                problems.append(f"{case.base.id}: extracted {item_id} has no OUT hop into "
                                f"{document.extract_to_tool}")
    if not declared:
        problems.append("no case extracts anything; the check measures nothing")
    text = "\n".join(b.document_table(CASES))
    if f"извлечения из документов: {declared} (переходов под них {declared})" not in text:
        problems.append(f"the document table does not print {declared} extractions "
                        f"with {declared} hops: {text!r}")
    return problems


def test_stamp_refreshes_only_when_membership_holds() -> list[str]:
    """R-57: the freeze protects MEMBERSHIP, not a hash.

    A repair that moves a case's bytes moves `corpus_sha256` and moves nobody
    between tiers; pinning the ladder to the byte hash made every such repair a
    choice between a stale stamp and reaching for the redraw flag, whose name
    («no live run has read this ladder») is an assertion a repair has no
    business making. So the stamp is refreshed in place with the proof printed
    per tier; the half that makes the refresh mean anything — a corpus whose
    membership DOES move is refused and the file left alone — is
    `test_a_changed_corpus_refuses_the_kept_ladder`."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        ladder, _lines, broken = b.write_ladder(CASES, SEED, out, True, True)
        if ladder is None or broken:
            return [f"the first build wrote no ladder: {broken}"]
        first = json.loads((out / "ladder.json").read_text(encoding="utf-8"))
        if "tier_sha256" not in first:
            problems.append("the written ladder carries no per-tier membership hash")
        # The SAME cases with one byte moved: every id stays, the digest does not.
        repaired = [replace(case, base=replace(case.base, note=case.base.note + " "))
                    for case in CASES]
        _again, lines, broken = b.write_ladder(repaired, SEED, out, False, False)
        refreshed = json.loads((out / "ladder.json").read_text(encoding="utf-8"))
        if broken:
            problems.append(f"a byte-only change was refused its own ladder: {broken}")
        if refreshed["corpus_sha256"] != b.v4.corpus_digest([case.base for case in repaired]):
            problems.append("the refreshed stamp is not the new corpus digest")
        if refreshed["tiers"] != first["tiers"]:
            problems.append("the refresh moved a tier")
        if refreshed.get("tier_sha256") != first.get("tier_sha256"):
            problems.append("the refresh changed a membership hash while keeping the ids")
        holdout = len(first["tiers"]["holdout"])
        if not any(f"холдаут не сдвинулся: 0 из {holdout}" in line for line in lines):
            problems.append(f"the refresh printed no proof per tier: {lines}")
        for tier in sorted(first["tiers"]):
            if tier == "holdout":
                continue
            if not any(line.strip().startswith(f"{tier} не сдвинулся: 0") for line in lines):
                problems.append(f"no proof line for tier {tier}")
        if refreshed.get("tier_sha256", {}).get("holdout") != b.tier_sha256(
                first["tiers"]["holdout"]):
            problems.append("the id-set hash is not the hash of the ids beside it")
        # AND THE SECOND REFRESH IS A NO-OP: the stamp now matches the corpus,
        # so the ordinary «оставлена как есть» branch runs and writes nothing.
        _kept, again, still = b.write_ladder(repaired, SEED, out, False, False)
        if still or not any("оставлена как есть" in line for line in again):
            problems.append(f"the refreshed ladder was not simply kept: {again} {still}")
    return problems


def _is_free_leaf(hop: Hop) -> bool:
    """Does this OUT hop land in a field the agent writes PROSE into."""
    spec = spec_v5_for(hop.tool_name, hop.path) if hop.tool_name and hop.path else None
    return spec is not None and not spec.role and spec.kind == "free"


def _decoy(pii_type: str, reference: str) -> str:
    """Another person's value of the same type, sharing no word with this one."""
    candidates = DECOYS.get(pii_type)
    if candidates is None:
        raise KeyError(f"no decoy declared for {pii_type!r}; a type the corpus carries "
                       f"and this check cannot falsify is a check that passes by absence")
    for candidate in candidates:
        words = [word for word in candidate.lower().split() if len(word) > 3]
        if not any(word[:4] in reference.lower() for word in words):
            return candidate
    raise ValueError(f"every {pii_type} decoy shares a word with {reference!r}")


def test_free_text_transitions_can_be_won_and_lost() -> list[str]:
    """H4.2: every hand-over that lands in PROSE is earnable by a gateway that
    does the right thing AND failable by one that does not.

    210 of the 938 declared transitions (22.4 %) put the value into a field the
    agent composes a sentence around, and `leaf_value_ok` compared the whole
    prose field byte for byte with the canonical — False by construction, so
    `chain_value` charged the gateway for 22 % of its own denominator. The rule
    is now containment, and a containment rule can fail the other way: a leaf
    so permissive that another person's value also passes measures nothing. So
    both halves are asserted per transition, and a transition that failed
    either would be a corpus defect to drop — none does.

    THE DECOY IS A VALUE OF THE SAME TYPE THAT SHARES NO WORD WITH THE RIGHT
    ONE, checked rather than assumed: the first decoy list collided with the
    corpus's own “ленина” and the check reported four vacuous transitions that
    were nothing of the kind."""
    problems: list[str] = []
    seen = 0
    for case in CASES:
        pairs = [(hop, source) for hop, source in b.transitions_of(case)
                 if _is_free_leaf(hop)]
        if not pairs:
            continue
        rendered = {(call.tool_name, call.call_ordinal): dict(call.rendered)
                    for call in mock.drive_returns(case)}
        items = {item.id: item for item in case.base.pii}
        for hop, source in pairs:
            reference = rendered.get((source.tool_name, source.call_ordinal), {}).get(
                source.item_id)
            if reference is None:
                problems.append(f"{case.base.id}: hop {hop.hop_index} sources a result that "
                                f"renders nothing — V04's job, and it did not fire")
                continue
            seen += 1
            target = returned_as_item(items[source.item_id], reference)
            item = items[hop.item_id]
            right = PROSE.format(value=reference)
            wrong = PROSE.format(value=_decoy(item.type, reference))
            if not leaf_value_ok(target, hop.tool_name, hop.path, right):
                problems.append(f"{case.base.id}: {hop.tool_name}.{hop.path} cannot be won — "
                                f"prose carrying {reference!r} scored a miss")
            if leaf_value_ok(target, hop.tool_name, hop.path, wrong):
                problems.append(f"{case.base.id}: {hop.tool_name}.{hop.path} cannot be lost — "
                                f"prose carrying another person's value scored a hit")
    if not seen:
        problems.append("no transition lands in a free-text leaf; the check measures nothing")
    text = "\n".join(b.chain_leaf_table(CASES))
    if f"в свободный текст {seen}" not in text:
        problems.append(f"the chain-leaf table does not print {seen} free-text transitions: "
                        f"{text!r}")
    return problems


def test_no_item_carries_a_placeholder_surface() -> list[str]:
    """Over the BUILT corpus: not one item's written surface is «None», «null»
    or empty. 310 were «None» — and the surface is what the needle layer
    indexes, so the stem «none» sat in every document case's own-stem
    exemption and matched the literal word anywhere in a reply."""
    bad = [f"{case.base.id}/{item.id} ({item.type}) = {item.value!r}"
           for case in CASES for item in case.base.pii
           if item.value.strip().lower() in common.PLACEHOLDER_SURFACES]
    return [f"{len(bad)} items carry a placeholder surface: {bad[:4]}"] if bad else []


def test_widened_watch_is_restored() -> list[str]:
    """The watch list is put back. A module-level tuple left extended would make
    every later v4 run watch a directory v4 does not own."""
    from bench.agentpii4 import validate as v4validate
    before = v4validate._WATCHED_DIRS                    # noqa: SLF001
    b.prove_no_search_v5(SEED)
    after = v4validate._WATCHED_DIRS                     # noqa: SLF001
    return [] if before == after else [f"watch list left as {after}"]


# --- «положил файл — попал в ярус» (пункт 9) -----------------------------------------

def _dropped_family(template: CaseV5) -> SimpleNamespace:
    """A scenario family written the way §3.1 says to write one: a module with
    `build(seed, count)` and nothing else.

    BUILT FROM A REAL CASE rather than from a stub, because the claim under test
    is that a family added to the plan reaches the corpus — and a stub that
    `validate_v5` would refuse could reach it and prove nothing.
    """
    def build(seed: int, wanted: int) -> list[CaseV5]:
        del seed
        return [replace(template, base=replace(template.base, id=f"dropin-{index:03d}"))
                for index in range(wanted)]
    return SimpleNamespace(__name__="bench.agentpii5.scenarios5.dropin", build=build)


def test_a_family_dropped_into_the_plan_is_built_and_printed() -> list[str]:
    """PUNKT 9: a file in `scenarios5/` and a line in the plan, with no edit to
    the harness.

    THE PLAN IS CONSUMED IN ONE PLACE AND IT TAKES THE PLAN AS AN ARGUMENT, so
    this check hands `build_planned` its own two-line plan and watches the same
    function the real build runs. Reading `PLAN` from the module global was the
    alternative and it makes the property uncheckable: a check would have to
    ASSIGN to `build.PLAN`, and a test that edits a module global leaves every
    later check running against its edit.
    """
    problems: list[str] = []
    template = next(case for case in CASES if not case.revised_from_v4)
    family = _dropped_family(template)
    plan = ((family, 3),)
    built = b.build_planned(SEED, plan)
    if [case.base.id for case in built] != ["dropin-000", "dropin-001", "dropin-002"]:
        problems.append(f"the plan built {[case.base.id for case in built]}")
    text = "\n".join(b.plan_table(built, plan))
    if "dropin" not in text:
        problems.append(f"the plan table does not name the family that landed: {text!r}")
    if "заказано 3" not in text:
        problems.append(f"the plan table does not print what was asked for: {text!r}")
    # A family that builds fewer cases than it is asked for moves every share
    # below it, and the totals add up either way — so the disagreement is a line.
    short = "\n".join(b.plan_table(built[:2], plan))
    if "!" not in short:
        problems.append(f"a family that built 2 of 3 was not flagged: {short!r}")
    # …and the real plan's own table names every family of the real corpus.
    real = "\n".join(b.plan_table(CASES, b.PLAN))
    for module, _count in b.PLAN:
        if b._plan_name(module) not in real:                 # noqa: SLF001 - the name is the test
            problems.append(f"the plan table leaves out {b._plan_name(module)}")  # noqa: SLF001
    return problems


def test_a_case_outside_every_tier_is_named_by_the_check() -> list[str]:
    """PUNKT 9, step 5: a case in the corpus and in no tier is taken by no run,
    and `--check` has to say so — with a different answer on the two sides of
    the first live run (пункт 10)."""
    problems: list[str] = []
    template = next(case for case in CASES if not case.revised_from_v4)
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        ladder, _lines, broken = b.write_ladder(CASES, SEED, out, True, False)
        if ladder is None or broken:
            return [f"the ladder was not written: {broken}"]
        path = out / "ladder.json"
        settled = "\n".join(b.ladder_coverage(CASES, path))
        if "новых случаев нет" not in settled:
            problems.append(f"a corpus every tier holds was not called settled: {settled!r}")
        grown = list(CASES) + b.build_planned(SEED, ((_dropped_family(template), 2),))
        text = "\n".join(b.ladder_coverage(grown, path))
        if "новых случаев вне ярусов: 2" not in text:
            problems.append(f"the two new cases were not named as tierless: {text!r}")
        if "--unfrozen-before-first-run" not in text:
            problems.append(f"the check does not say how to place them: {text!r}")
        lost = "\n".join(b.ladder_coverage(CASES[:-3], path))
        if "лестница называет 3 случаев, которых в корпусе нет" not in lost:
            problems.append(f"three cases the corpus lost were not named: {lost!r}")
        # AFTER THE FIRST LIVE RUN THE ANSWER IS ANOTHER ONE, and printing the
        # redraw flag there would be telling a reader to assert a falsehood.
        b.stamp_holdout_touched(path, "run-ladder-coverage", "2026-09-23T10:00:00+00:00")
        after = "\n".join(b.ladder_coverage(grown, path))
        if "--unfrozen-before-first-run" in after or "решение владельца" not in after:
            problems.append(f"a touched ladder still advertises the redraw: {after!r}")
        missing = "\n".join(b.ladder_coverage(CASES, out / "no-such-ladder.json"))
        if "ещё не нарисована" not in missing:
            problems.append(f"a missing ladder was not reported as missing: {missing!r}")
    return problems


# --- мёртвый груз и дубли по составу (пункт 11) --------------------------------------

def test_dead_weight_and_content_duplicates_are_counted() -> list[str]:
    """PUNKT 11: a case no metric line can count, and a case that duplicates
    another by family and values.

    BOTH HALVES OF EACH. A `dead_weight` that only ever returns () could be a
    function that returns () — so a case declaring NOTHING is built and must be
    named — and every predicate of the table must fire on the real corpus, or it
    is a line in the table that counts nothing and lets dead weight through.
    """
    problems: list[str] = []
    template = CASES[0]
    mute = replace(template, hops=(), returns=(), memory=(), forced=(), pick=None,
                   branch=None, loop=None, rag=None, document=None, has_result=False,
                   streaming=False,
                   base=replace(template.base, id="mute-000", pii=(), negatives=()))
    if b.denominator_lines(mute):
        problems.append(f"a case declaring nothing feeds {b.denominator_lines(mute)}")
    if "mute-000" not in b.dead_weight([template, mute]):
        problems.append("the case no line counts was not named as dead weight")
    if b.dead_weight([template]):
        problems.append(f"a real corpus case was called dead weight: {b.dead_weight([template])}")
    for label, licensed in b.DENOMINATORS:
        if not any(licensed(case) for case in CASES):
            problems.append(f"no case of the corpus licenses {label!r}: the predicate "
                            f"counts nothing and lets dead weight through")
    for name in b.DEAD_WEIGHT_EXEMPT:
        if name in {label for label, _licensed in b.DENOMINATORS}:
            problems.append(f"{name} counts every observation and is in the table: "
                            f"dead weight would be a class with no members")
    twin = replace(template, base=replace(template.base, id="twin-000"))
    other = next(case for case in CASES
                 if case.behaviour == template.behaviour
                 and b.content_key(case) != b.content_key(template))
    groups = b.content_duplicates([template, twin, other])
    if groups != ((template.base.id, "twin-000"),) and groups != (("twin-000", template.base.id),):
        problems.append(f"the content duplicate was not found alone: {groups}")
    if b.content_duplicates([template, other]):
        problems.append("two cases carrying different values were called duplicates")
    # A family is part of the identity: the same people in another family is a
    # different measurement and duplicates nothing.
    elsewhere = replace(twin, behaviour="rag" if template.behaviour != "rag" else "document")
    if b.content_duplicates([template, elsewhere]):
        problems.append("the same values in another family were called a duplicate")
    if b.duplicate_ids([template, twin]):
        problems.append("two distinct ids were reported as duplicated")
    if b.duplicate_ids([template, template]) != (template.base.id,):
        problems.append("one id carried by two cases was not reported")
    # …and the printed table carries what the corpus really holds today.
    text = "\n".join(b.waste_table(CASES))
    groups = b.content_duplicates(CASES)
    if f"дубли по составу (семья и значения): {len(groups)} групп" not in text:
        problems.append(f"the waste table does not print the corpus's own groups: {text!r}")
    if f"мёртвый груз (ни одна строка метрик не считает): {len(b.dead_weight(CASES))}" not in text:
        problems.append(f"the waste table does not print the dead weight: {text!r}")
    # A PRINTED KEY MUST NOT BE A PRINTED VALUE: the table names ids and hashes,
    # never the people a case carries.
    for item in template.base.pii:
        if item.value and item.value in text:
            problems.append(f"the waste table prints a corpus value ({item.type})")
    return problems


# --- холдаут, тронутый живым прогоном (пункт 10) -------------------------------------

def test_the_first_live_run_stamps_the_holdout() -> list[str]:
    """PUNKT 10: the first live run that reads the holdout writes the date and
    its own id into `ladder.json`, and the FIRST stamp is the one that stays."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        ladder, _lines, broken = b.write_ladder(CASES, SEED, out, True, False)
        if ladder is None or broken:
            return [f"the ladder was not written: {broken}"]
        path = out / "ladder.json"
        if b.holdout_touch(path) is not None:
            problems.append("a freshly drawn ladder claims a live run has read it")
        if b.holdout_touch(out / "no-such-ladder.json") is not None:
            problems.append("a ladder that does not exist claims a touch")
        held = list(ladder.tiers["holdout"])
        debugged = [one for one in ladder.tiers["nano"] if one not in set(held)]
        if not b.touches_holdout(path, held[:1]):
            problems.append("a run over a holdout case was not seen as touching it")
        if b.touches_holdout(path, debugged[:1]):
            problems.append("a run over a debug case was read as touching the holdout")
        if not b.touches_holdout(path, [case.base.id for case in CASES]):
            problems.append("--tier max does not count as touching the holdout")
        stamp = b.stamp_holdout_touched(path, "run-first", "2026-09-23T10:00:00+00:00")
        if stamp != b.HoldoutTouch("2026-09-23T10:00:00+00:00", "run-first"):
            problems.append(f"the stamp returned {stamp}")
        if b.holdout_touch(path) != stamp:
            problems.append("the stamp was not written into the file")
        again = b.stamp_holdout_touched(path, "run-second", "2026-09-24T10:00:00+00:00")
        if again != stamp:
            problems.append(f"a second run overwrote the first touch: {again}")
        kept = json.loads(path.read_text(encoding="utf-8"))
        if kept.get(b.HOLDOUT_TOUCHED_BY) != "run-first":
            problems.append("the file remembers the second run, not the first")
        if "tier_sha256" not in kept or set(kept["tiers"]) != set(ladder.tiers):
            problems.append("stamping the ladder dropped what was in it")
    return problems


def test_a_touched_ladder_refuses_every_redraw() -> list[str]:
    """PUNKT 10: from the first touch on, a change of holdout membership is a
    REFUSAL — `--unfrozen-before-first-run` asserts something the file itself
    contradicts.

    BOTH SIDES, because a refusal that has only been watched refusing could be a
    function that refuses always: the same redraw goes through on an untouched
    ladder (R-52, which stands until the stamp appears).
    """
    problems: list[str] = []
    shrunk = CASES[: len(CASES) - 200]
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        b.write_ladder(CASES, SEED, out, True, False)
        path = out / "ladder.json"
        if b.touched_refusal(path, True):
            problems.append("an untouched ladder refused the one allowed redraw")
        _ladder, lines, broken = b.write_ladder(shrunk, SEED, out, True, True)
        if broken or not any("сменили ярус" in line for line in lines):
            problems.append(f"R-52's redraw was refused before any touch: {broken}")
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        b.write_ladder(CASES, SEED, out, True, False)
        path = out / "ladder.json"
        b.stamp_holdout_touched(path, "run-first", "2026-09-23T10:00:00+00:00")
        before = path.read_bytes()
        refusal = b.touched_refusal(path, True)
        if "run-first" not in refusal or "ОТКАЗ" not in refusal:
            problems.append(f"the redraw was not refused by name: {refusal!r}")
        if b.touched_refusal(path, False):
            problems.append("an ordinary build was refused because of the stamp")
        _ladder, _lines, broken = b.write_ladder(shrunk, SEED, out, True, True)
        if not broken:
            problems.append("the assertion moved a holdout a live run had already read")
        elif "живой прогон" not in broken[0]:
            problems.append(f"the refusal does not name the run: {broken[0]}")
        if path.read_bytes() != before:
            problems.append("a refused redraw wrote the file anyway")
    return problems


def test_a_stamp_refresh_keeps_the_touch() -> list[str]:
    """PUNKT 10 against R-57: a repair that moves bytes and no case ids refreshes
    the stamp — and must carry the touch through, or the freeze quietly goes back
    to being a human's word one honest repair later."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        b.write_ladder(CASES, SEED, out, True, False)
        path = out / "ladder.json"
        touch = b.stamp_holdout_touched(path, "run-first", "2026-09-23T10:00:00+00:00")
        repaired = [replace(case, base=replace(case.base, note=case.base.note + " "))
                    for case in CASES]
        _again, lines, broken = b.write_ladder(repaired, SEED, out, False, False)
        if broken:
            problems.append(f"a byte-only change was refused after the touch: {broken}")
        if not any("штамп лестницы обновлён" in line for line in lines):
            problems.append(f"the stamp was not refreshed: {lines}")
        if b.holdout_touch(path) != touch:
            problems.append(f"the refresh dropped the touch: {b.holdout_touch(path)}")
        # …and a redraw that MOVES nobody is allowed even after the touch, and
        # keeps the stamp too: the refusal is about movement, not about writing.
        _ladder, _lines, broken = b.write_ladder(repaired, SEED, out, True, True)
        if broken:
            problems.append(f"a redraw that moves nobody was refused: {broken}")
        if b.holdout_touch(path) != touch:
            problems.append("a redraw that moved nobody dropped the touch")
    return problems


# --- грязное дерево и чужой корпус (пункт 18) ----------------------------------------

def _provenance(dirty: tuple[str, ...], dirty_ok: bool, ladder_digest: str) -> b.RunProvenance:
    """A provenance with everything but the two facts under test held fixed.

    The selection here IS its tier («nano» with the frozen hash), so the third
    refusal stays silent and the two under test are the only ones that speak.
    """
    return b.RunProvenance(
        commit="0123456789abcdef0123456789abcdef01234567", branch="main", dirty=dirty,
        dirty_ok=dirty_ok, tier="nano", cases=3, corpus_cases=30, corpus_sha256="aaaa",
        corpus_v5_sha256="bbbb", selection_sha256="dddd",
        ladder_corpus_sha256=ladder_digest,
        ladder_tier_sha256=(("holdout", "cccc"), ("nano", "dddd")),
        ladder_tier_names=("holdout", "nano"),
        holdout_touched_at="", holdout_touched_by="")


def test_a_live_run_refuses_a_dirty_tree_and_a_foreign_corpus() -> list[str]:
    """PUNKT 18: the two refusals, and the ONE of them a flag may clear.

    A dirty tree makes the numbers untieable to a commit — sometimes worth it,
    so `--dirty-ok` exists and says so in the record. A corpus that disagrees
    with the ladder makes them untieable to anything: the tier names ids drawn
    from another corpus, so the run measures a selection nobody chose.
    """
    problems: list[str] = []
    clean = _provenance((), False, "aaaa")
    if b.start_refusals(clean):
        problems.append(f"a clean tree on its own corpus was refused: {b.start_refusals(clean)}")
    dirty = _provenance((" M prototype/pseudex/vault.py", "?? prototype/x.py"), False, "aaaa")
    refusals = b.start_refusals(dirty)
    if len(refusals) != 1 or "грязное" not in refusals[0]:
        problems.append(f"a dirty tree was not refused: {refusals}")
    elif "2 файлов" not in refusals[0] or "(2 под prototype/)" not in refusals[0]:
        problems.append(f"the refusal does not count the dirt: {refusals[0]}")
    allowed = _provenance((" M prototype/pseudex/vault.py",), True, "aaaa")
    if b.start_refusals(allowed):
        problems.append(f"--dirty-ok did not let the run start: {b.start_refusals(allowed)}")
    foreign = _provenance((), True, "zzzz")
    refusals = b.start_refusals(foreign)
    if len(refusals) != 1 or "лестниц" not in refusals[0]:
        problems.append(f"a corpus the ladder was not drawn from was accepted: {refusals}")
    elif "--dirty-ok этого не снимает" not in refusals[0]:
        problems.append(f"the refusal does not say the flag will not clear it: {refusals[0]}")
    both = _provenance((" M x",), False, "zzzz")
    if len(b.start_refusals(both)) != 2:
        problems.append(f"two problems were reported as {len(b.start_refusals(both))}")
    # WHAT THE RECORD SAYS: the run either can be tied to a commit or cannot,
    # decided once here rather than inferred by each reader.
    record = b.provenance_json(allowed)
    if record["tied_to_commit"] is not False or record["dirty_ok"] is not True:
        problems.append(f"a run on a dirty tree is recorded as tied to a commit: {record}")
    if record["dirty"] != 1 or record["dirty_paths"] != [" M prototype/pseudex/vault.py"]:
        problems.append(f"the record does not carry the dirt: {record}")
    if b.provenance_json(clean)["tied_to_commit"] is not True:
        problems.append("a clean run is not recorded as tied to its commit")
    for key in ("commit", "branch", "corpus_sha256", "corpus_v5_sha256",
                "ladder_corpus_sha256", b.HOLDOUT_TOUCHED_AT):
        if key not in record:
            problems.append(f"the record carries no {key}")
    # И ТА ЖЕ ОДНА СТРОКА, которую колонкой печатает реестр и шапка отчёта. Она
    # считается ЗДЕСЬ, из того же объекта: реестр и отчёт, пришедшие к «привязан
    # к коммиту» каждый своей дорогой, однажды разойдутся — и спорить будут два
    # файла об одном прогоне.
    line = b.worktree_line(allowed)
    if "0123456789ab" not in line or "к коммиту не привязан" not in line:
        problems.append(f"строка о грязном дереве не называет ни коммит, ни вывод: {line!r}")
    if "чисто" not in b.worktree_line(clean):
        problems.append(f"чистое дерево описано как {b.worktree_line(clean)!r}")
    if b.worktree_line(replace(clean, commit="")) != "неизвестно":
        problems.append("дерево, о котором git промолчал, описано словом, а не «неизвестно»")
    return problems


def test_the_provenance_is_read_off_the_real_tree() -> list[str]:
    """PUNKT 18: the commit, the branch and the corpus digest come from git and
    from the cases — not from a header a file writes about itself.

    THE ONE THING THIS ALSO PROVES: the corpus this build assembles is the one
    the committed ladder was drawn from. A disagreement here is exactly the
    refusal a live run would hit, found at test time instead of at spend time.
    """
    problems: list[str] = []
    commit, branch, _dirty = b.worktree_state(b.REPO)
    if len(commit) != 40 or not branch:
        problems.append(f"git answered commit={commit!r} branch={branch!r}")
    provenance = b.run_provenance(CASES, CASES, "max", b.HERE / "ladder.json", b.REPO, True)
    if provenance.corpus_sha256 != provenance.ladder_corpus_sha256:
        problems.append(f"the built corpus {provenance.corpus_sha256[:12]} is not the one "
                        f"ladder.json was drawn from ({provenance.ladder_corpus_sha256[:12]})")
    if provenance.cases != len(CASES) or not provenance.ladder_tier_sha256:
        problems.append(f"the provenance does not describe the corpus: {provenance.cases}")
    v4_digest, v5_digest = b.corpus_stamp(CASES)
    if (v4_digest, v5_digest) != (provenance.corpus_sha256, provenance.corpus_v5_sha256):
        problems.append("the provenance's digests are not the corpus's own")
    # A tree git cannot answer for is named, never read as «no provenance»: the
    # two would be one blank field in the run record.
    with tempfile.TemporaryDirectory() as folder:
        try:
            b.worktree_state(Path(folder))
            problems.append("a directory that is not a checkout answered as one")
        except b.WorktreeUnreadable as error:
            if folder not in str(error):
                problems.append(f"the error does not name the directory: {error}")
    return problems


# --- пороги приёмки в CI (пункт 19) --------------------------------------------------

def test_every_tier_starts_and_a_foreign_selection_does_not() -> list[str]:
    """PUNKT 18, the half that was inverted: a TIER is checked against the
    membership the ladder froze for THAT TIER, and the corpus against the corpus.

    THE BLOCKER THIS PINS. `run_provenance` used to be handed the tier selection
    alone and digest it as «the corpus», so `start_refusals` compared the digest
    of thirty cases with the digest of 1 736 — and refused every live run but
    `--tier max`, with the words «корпус не тот», which was not what was wrong.
    The first paid run would have died on it. Every tier of the real committed
    ladder is walked here, because the defect was invisible on the one tier
    (`max`) where the two digests coincide.
    """
    problems: list[str] = []
    ladder_path = b.HERE / "ladder.json"
    ladder = json.loads(ladder_path.read_text(encoding="utf-8"))
    by_id = {case.base.id: case for case in CASES}
    for name, identifiers in sorted(dict(ladder["tiers"]).items()):
        selection = [by_id[one] for one in identifiers if one in by_id]
        if len(selection) != len(identifiers):
            problems.append(f"ярус {name}: лестница называет случаи, которых в корпусе нет")
            continue
        provenance = b.run_provenance(CASES, selection, name, ladder_path, b.REPO, True)
        refusals = b.start_refusals(provenance)
        if refusals:
            problems.append(f"ярус {name} ({len(selection)} случаев) не стартует: {refusals[0]}")
        if b.selection_is_the_tier(provenance) is not True:
            problems.append(f"ярус {name} не признан своим замороженным составом")
        if provenance.cases != len(selection) or provenance.corpus_cases != len(CASES):
            problems.append(f"ярус {name}: выборка {provenance.cases} и корпус "
                            f"{provenance.corpus_cases} записаны неверно")
        if provenance.corpus_sha256 != provenance.ladder_corpus_sha256:
            problems.append(f"ярус {name}: дайджест корпуса считается по выборке")
    # …А ВЫБОРКА, КОТОРАЯ ЯРУСОМ НЕ ЯВЛЯЕТСЯ, ОТКАЗАНА — иначе проверка выше
    # зеленела бы и на коде, который не проверяет ничего.
    smallest = min(dict(ladder["tiers"]).items(), key=lambda pair: len(pair[1]))
    trimmed = [by_id[one] for one in smallest[1][:-1]]
    provenance = b.run_provenance(CASES, trimmed, smallest[0], ladder_path, b.REPO, True)
    refusals = b.start_refusals(provenance)
    if not refusals or "выборка яруса" not in refusals[0]:
        problems.append(f"ярус без одного случая не отказан: {refusals}")
    elif smallest[0] not in refusals[0]:
        problems.append(f"отказ не называет ярус: {refusals[0]}")
    if b.selection_is_the_tier(provenance) is not False:
        problems.append("подменённый состав яруса признан замороженным")
    # …и `--ids` — ТРЕТИЙ ответ, а не «нет»: замороженного состава, с которым
    # сравнивать названные руками случаи, не существует.
    named = b.run_provenance(CASES, trimmed, b.IDS_SELECTION, ladder_path, b.REPO, True)
    if b.selection_is_the_tier(named) is not None:
        problems.append("прогон по названным руками случаям сравнён с ярусом, которого у него нет")
    if b.start_refusals(named):
        problems.append(f"--ids отказан: {b.start_refusals(named)}")
    record = b.provenance_json(named)
    for key in ("tier", "cases", "corpus_cases", "selection_sha256", "selection_is_the_tier"):
        if key not in record:
            problems.append(f"запись прогона не несёт {key}")
    if record.get("selection_is_the_tier") is not None:
        problems.append(f"запись назвала выборку --ids ярусом: "
                        f"{record.get('selection_is_the_tier')}")
    return problems


def test_the_acceptance_test_runs_on_every_push() -> list[str]:
    """PUNKT 19: `test_perfect` on the acceptance tier is a step of the engine
    job in `.github/workflows/checks.yml`.

    A THRESHOLD NOBODY RUNS IS A THRESHOLD NOBODY HAS. The instrument's own
    acceptance — a right gateway clears every bound, four wrong ones fail them —
    lived in a file people ran by hand, which is exactly the state the golden and
    dirty sets were in when work landed unguarded for weeks. The check reads the
    workflow's ENGINE job rather than the whole file: a step in the storefront
    job would run in a virtualenv that has no corpus and no `bench` package, and
    grepping the file as a whole would call that green.
    """
    problems: list[str] = []
    path = b.REPO / ".github" / "workflows" / "checks.yml"
    if not path.exists():
        return [f"{path} does not exist"]
    text = path.read_text(encoding="utf-8")
    start = text.find("\n  engine:")
    end = text.find("\n  storefront:")
    if start < 0 or end < start:
        return [f"{path} has no engine job to read"]
    # THE COMMANDS, NOT THE PROSE. The step's own comment explains why the whole
    # corpus is the nightly's and names `--tier max`; a check over the raw block
    # would read that sentence as the command it warns against.
    engine = "\n".join(line for line in text[start:end].splitlines()
                       if not line.strip().startswith("#"))
    if "bench.agentpii5.test_perfect" not in engine:
        problems.append("the engine job does not run the instrument's acceptance test")
    if "--tier max" in engine:
        problems.append("the whole corpus (~2 min) is asked for on every push; "
                        "`--tier max` belongs to the nightly run")
    if "python -m bench.agentpii5.test_perfect" not in engine:
        problems.append("the acceptance test is not run as a module from prototype/")
    # …and the tier it runs at is the one the file itself calls the acceptance
    # tier, so renaming the default cannot leave CI running another corpus slice.
    if ACCEPTANCE_TIER != "medium":
        problems.append(f"the acceptance tier moved to {ACCEPTANCE_TIER!r}; the workflow's "
                        f"comment and the nightly split say medium")
    return problems


def test_a_tier_is_a_miniature_and_the_old_draw_is_refused() -> list[str]:
    """ПЕРЕРЕЗКА 23.09: каждый ярус повторяет корпус по регистру И по поведению,
    и проверка, которая это требует, КРАСНЕЕТ на лестнице, прожившей до первого
    живого прогона.

    ПОЧЕМУ ОТРИЦАТЕЛЬНАЯ ПОЛОВИНА ЗДЕСЬ ГЛАВНАЯ. «nano = 30 голосовых сырых» не
    красило ничего: `ladder_problems` требует от яруса все СЕМЬИ и молчит о
    регистре, а `_register_round_robin(free, 1, rng)` при запросе в ОДИН случай
    возвращает первый непустой регистр из `REGISTER_ORDER` — то есть всегда
    `voice_raw`. Измерено на этом корпусе: nano 30/30, small 120/120, medium
    300/300, large 446+154 — и приёмка прибора на каждый push шла на `medium`.
    Поэтому старая жеребьёвка строится ЗДЕСЬ, из v4, и проверка обязана на ней
    покраснеть; иначе зелёное на новой лестнице не значит ничего.
    """
    problems: list[str] = []
    fresh = b.build_ladder_v5(CASES, SEED)
    if b.ladder_problems_v5(CASES, fresh):
        problems.append(f"стратифицированная лестница отказана самой себе: "
                        f"{b.ladder_problems_v5(CASES, fresh)[:2]}")
    if ladder_problems([case.base for case in CASES], fresh):
        problems.append(f"v4-проверка отказала новой лестнице: "
                        f"{ladder_problems([case.base for case in CASES], fresh)[:2]}")
    by_nano = {case.base.id: case for case in CASES}
    # ОТРИЦАТЕЛЬНАЯ ПОЛОВИНА: прежняя жеребьёвка v4 на том же корпусе.
    stale = build_ladder([case.base for case in CASES], SEED)
    said = b.ladder_problems_v5(CASES, stale)
    if not said:
        problems.append("одноголосая лестница v4 признана миниатюрой корпуса")
    if not any("nano" in line and "register" in line for line in said):
        problems.append(f"проверка не назвала nano и регистр: {said[:3]}")
    # СЕМЬЯ, КОТОРОЙ В ЯРУСЕ НЕТ, — НЕГАТИВ ПОСТРОЕННЫЙ, А НЕ ВЫПРОШЕННЫЙ У
    # ЖЕРЕБЬЁВКИ. Строка стояла на том, что в v4-шном nano нет
    # `same_tool_other_target`; корпус вырос до 1800, тот же розыгрыш накрыл все
    # одиннадцать поведений, и проверка покраснела, ничего не узнав о коде. Что
    # она обязана доказать — что ось BEHAVIOUR читается так же, как register, —
    # доказывается ярусом, из которого поведение УБРАНО, и это не зависит от
    # размера корпуса.
    gone = "same_tool_other_target"
    without = [one for one in fresh.tiers["nano"] if by_nano[one].behaviour != gone]
    filler = [case.base.id for case in CASES
              if case.base.id not in set(fresh.tiers["nano"]) | set(fresh.tiers["holdout"])
              and case.behaviour != gone][:len(fresh.tiers["nano"]) - len(without)]
    stripped = replace(fresh, tiers={**fresh.tiers, "nano": tuple(without + filler)})
    if not any(gone in line for line in b.ladder_problems_v5(CASES, stripped)):
        problems.append(f"ярус без семьи {gone!r} принят: "
                        f"{b.ladder_problems_v5(CASES, stripped)[:3]}")
    if ladder_problems([case.base for case in CASES], stale):
        problems.append("v4-проверка сама краснеет на своей же лестнице — тогда новая "
                        "проверка не доказывает, что видит больше")
    # …И ТРЕТЬЯ: ярус, у которого доли поехали НЕ ДО НУЛЯ. Покрытие такой ярус
    # проходит — все значения на месте, — и без строки о пропорции он был бы
    # зелёным, хотя чата в нём вдвое больше корпусного.
    by_id = {case.base.id: case for case in CASES}
    nano = [by_id[one] for one in fresh.tiers["nano"]]
    spare = [case for case in CASES
             if case.base.id not in set(fresh.tiers["nano"]) | set(fresh.tiers["holdout"])
             and case.base.register == "chat"]
    swapped = ([case for case in nano if case.base.register != "chat"][:-6]
               + [case for case in nano if case.base.register == "chat"]
               + spare[:6])
    tilted = replace(fresh, tiers={**fresh.tiers,
                                   "nano": tuple(sorted(case.base.id for case in swapped))})
    said = b.ladder_problems_v5(CASES, tilted)
    if not any("не миниатюра" in line and "chat" in line for line in said):
        problems.append(f"перекошенный по доле ярус принят: {said[:3]}")
    return problems


def test_the_stratified_order_is_deterministic_and_order_independent() -> list[str]:
    """Один и тот же набор случаев даёт один и тот же порядок — в любом порядке
    подачи и с любой стороны.

    ЭТО ТРЕБОВАНИЕ, А НЕ СВОЙСТВО. Срез и ярус обязаны быть повторимы: прогон
    «до» и прогон «после» по одному правилу должны сыграть ОДНИ И ТЕ ЖЕ случаи,
    иначе разница между их числами — это разница выборок. Проверяется и
    независимость от порядка входа: корпус читается из файла, и однажды он
    придёт в другом порядке.
    """
    problems: list[str] = []
    sample = CASES[:400]
    first = [case.base.id for case in b.stratified_order(sample, SEED)]
    again = [case.base.id for case in b.stratified_order(sample, SEED)]
    if first != again:
        problems.append("два вызова дали разный порядок")
    shuffled = list(reversed(sample))
    if [case.base.id for case in b.stratified_order(shuffled, SEED)] != first:
        problems.append("порядок зависит от порядка подачи")
    if sorted(first) != sorted(case.base.id for case in sample):
        problems.append("порядок потерял или размножил случаи")
    # …и другой сид даёт ДРУГОЙ порядок: иначе «детерминирован» означало бы
    # «не зависит ни от чего», и сид был бы украшением.
    if [case.base.id for case in b.stratified_order(sample, SEED + 1)] == first:
        problems.append("сид не влияет на порядок")
    return problems


def test_the_floor_fits_the_smallest_tier() -> list[str]:
    """Пол — каждое значение каждой оси хотя бы раз — укладывается в самый
    маленький ярус, и это ИЗМЕРЕНО, а не предположено.

    22 семьи, 11 поведений, 5 регистров, 11 вертикалей и 10 типов ПД — 59
    клеток, но случай закрывает несколько сразу, и жадный проход по полу берёт
    23 случая из 30. Запас в семь; корпус, у которого семей станет больше
    тридцати, обязан узнать об этом здесь, а не на первом прогоне, где ярус
    молча потеряет семью. Длина пола меряется по самому порядку — первый
    префикс, покрывший все клетки, — а не считается по формуле, которая
    разошлась бы с кодом на первой же правке.

    ПОЛ СПРАШИВАЕТСЯ ПО ОБОИМ СПИСКАМ ОСЕЙ, И ИМЕННО ЗДЕСЬ ЭТО ВИДНО. Пока он
    шёл только по `LADDER_AXES`, эта проверка зеленела на лестнице, в которой
    nano не нёс ни вертикали `calendar`, ни типа `INN` — она сверяла ярус с тем
    же коротким списком, по которому его и рисовали.
    """
    problems: list[str] = []
    fresh = b.build_ladder_v5(CASES, SEED)
    by_id = {case.base.id: case for case in CASES}
    smallest = min(b.DEBUG_TIERS, key=lambda name: len(fresh.tiers[name]))
    members = [by_id[one] for one in fresh.tiers[smallest]]
    for axis in b.LADDER_AXES:
        whole = {b.case_axis(case, axis) for case in CASES}
        here = {b.case_axis(case, axis) for case in members}
        if whole - here:
            problems.append(f"ярус {smallest} не несёт по оси {axis}: {sorted(whole - here)}")
    for axis in b.LADDER_COVERAGE_AXES:
        whole = {one for case in CASES for one in b.case_slice_values(case, axis)}
        here = {one for case in members for one in b.case_slice_values(case, axis)}
        if whole - here:
            problems.append(f"ярус {smallest} не несёт по оси {axis}: {sorted(whole - here)}")
    held = set(fresh.tiers["holdout"])
    pool = [case for case in CASES if case.base.id not in held]
    cells = {cell for case in pool for cell in b._floor_cells(case)}
    order = b.stratified_order(pool, SEED)
    seen: set[tuple[str, str]] = set()
    floor = len(order)
    for index, case in enumerate(order, start=1):
        seen.update(b._floor_cells(case))
        if seen == cells:
            floor = index
            break
    if floor > len(fresh.tiers[smallest]):
        problems.append(f"пол занимает {floor} случаев, а в {smallest} их "
                        f"{len(fresh.tiers[smallest])}: ярус нечем добрать до пропорции")
    # Отрицательная половина: ярус, из которого вынут единственный случай
    # редкого значения, обязан быть назван по оси и по значению. Спрашивается по
    # ОБОИМ спискам осей, потому что молчала проверка именно на многозначной.
    thin = min(((axis, value) for axis in (*b.LADDER_AXES, *b.LADDER_COVERAGE_AXES)
                for value in {one for case in members
                              for one in _axis_values(case, axis)}),
               key=lambda pair: sum(1 for case in members if pair[1] in _axis_values(case, pair[0])))
    stripped = [case for case in members if thin[1] not in _axis_values(case, thin[0])]
    broken = replace(fresh, tiers={**fresh.tiers,
                                   smallest: tuple(sorted(case.base.id for case in stripped))})
    said = b.ladder_problems_v5(CASES, broken)
    if not any(f"не несёт ось {thin[0]}" in line and thin[1] in line for line in said):
        problems.append(f"ярус без значения {thin[1]!r} оси {thin[0]} принят: {said[:3]}")
    return problems


def _axis_values(case: CaseV5, axis: str) -> frozenset[str]:
    """Значения оси у случая — однозначной или многозначной, одним вызовом.

    Отрицательные половины проверок обязаны уметь вынимать значение ЛЮБОЙ оси;
    две ветки по месту вызова разошлись бы с `ladder_problems_v5` на первой же
    правке, и отрицательная половина стала бы проверять не то, что стережёт.
    """
    if axis in b.LADDER_AXES:
        return frozenset({b.case_axis(case, axis)})
    return b.case_slice_values(case, axis)


def test_the_recut_did_not_move_the_holdout() -> list[str]:
    """Перерезка трогает только отладочные ярусы: холдаут — тот же, что рисует
    v4, случай в случай.

    ЕГО ЦЕННОСТЬ В ТОМ, ЧТО ОН ОТЛОЖЕН ДО ТОГО, КАК КТО-ЛИБО ПОСМОТРЕЛ. Новый
    порядок мог бы сделать его пропорциональнее — и это был бы обмен
    единственного, за что холдаут держится, на украшение. Здесь же названа цена
    этого решения: холдаут НЕ пропорционален по регистру (`clean` 50 из 359 —
    13.9% против 5.7% в корпусе), и `tier_mix_table` печатает обе доли, чтобы
    читатель холдаутного числа это видел. Числа — после перерезки 23.09 под
    корпус 1800; перекос тот же, потому что жеребьёвка холдаута та же v4-шная.
    """
    problems: list[str] = []
    bases = [case.base for case in CASES]
    fresh = b.build_ladder_v5(CASES, SEED)
    if set(fresh.tiers["holdout"]) != set(build_ladder(bases, SEED).tiers["holdout"]):
        problems.append("перерезка сдвинула холдаут")
    if set(fresh.tiers["max"]) != {case.base.id for case in CASES}:
        problems.append("ярус max не равен корпусу")
    for smaller, bigger in zip(b.DEBUG_TIERS, b.DEBUG_TIERS[1:]):
        if not set(fresh.tiers[smaller]) <= set(fresh.tiers[bigger]):
            problems.append(f"{smaller} не вложен в {bigger}")
    # Отрицательная половина вложенности: ярус, в котором один случай подменён
    # чужим, обязан быть пойман — иначе строка выше зеленела бы на любом коде.
    outsider = next(case.base.id for case in CASES
                    if case.base.id not in set(fresh.tiers["small"])
                    and case.base.id not in set(fresh.tiers["holdout"]))
    torn = {**fresh.tiers, "nano": (*fresh.tiers["nano"][1:], outsider)}
    if set(torn["nano"]) <= set(torn["small"]):
        problems.append("подменённый nano всё ещё вложен в small — проверка вложенности "
                        "не может покраснеть")
    by_id = {case.base.id: case for case in CASES}
    held = [by_id[one] for one in fresh.tiers["holdout"]]
    if len({case.base.register for case in held}) != len({case.base.register
                                                          for case in CASES}):
        problems.append("холдаут несёт не все регистры — его пришлось бы перерисовать, "
                        "и это решение владельца, а не флага")
    printed = "\n".join(b.tier_mix_table(CASES, fresh))
    if "clean 50" not in printed:
        problems.append("таблица состава не называет перекос холдаута по clean")
    return problems


def test_a_slice_is_repeatable_and_never_reads_the_holdout() -> list[str]:
    """СРЕЗ (просьба владельца): «дай 120 случаев только чата» — одна команда,
    повторимая словом, и холдаута он не касается.

    ХОЛДАУТ ИСКЛЮЧЁН БЕЗ ФЛАГА, И ЭТО ПРОВЕРЯЕТСЯ, А НЕ ОБЕЩАЕТСЯ. Дешёвый срез
    по всему корпусу прочитал бы двадцать процентов, отложенных до того, как
    кто-либо посмотрел, и штамп `holdout_touched_at` встал бы навсегда за
    четыре доллара.
    """
    problems: list[str] = []
    ladder = json.loads((b.HERE / "ladder.json").read_text(encoding="utf-8"))
    held = ladder["tiers"]["holdout"]
    clauses = b.parse_slice("register=chat", CASES)
    first = b.slice_cases(CASES, held, clauses, 120, SEED)
    again = b.slice_cases(CASES, list(reversed(held)),
                          b.parse_slice("register=chat", CASES), 120, SEED)
    if [case.base.id for case in first] != [case.base.id for case in again]:
        problems.append("один и тот же срез дал два разных списка")
    if len(first) != 120:
        problems.append(f"срез в 120 дал {len(first)}")
    if {case.base.register for case in first} != {"chat"}:
        problems.append("срез по регистру взял чужой регистр")
    if set(case.base.id for case in first) & set(held):
        problems.append("срез прочитал холдаут")
    # Отрицательная половина: без исключения холдаут в срез ПОПАДАЕТ. Если бы
    # не попадал, строка выше зеленела бы и на коде, который ничего не отсекает.
    unguarded = b.slice_cases(CASES, (), clauses, 0, SEED)
    if not set(case.base.id for case in unguarded) & set(held):
        problems.append("холдаут не попадает в срез и без исключения — проверка "
                        "исключения не может покраснеть")
    # Срез — тоже миниатюра ТОГО, ЧТО В НЁМ ОСТАЛОСЬ: набранный первыми по
    # имени, он был бы той же болезнью в меньшем масштабе.
    lost = {case.behaviour for case in CASES
            if case.base.register == "chat" and case.base.id not in set(held)} - {
        case.behaviour for case in first}
    if lost:
        problems.append(f"срез в 120 случаев потерял поведения: {sorted(lost)}")
    # Имя КАНОНИЧЕСКОЕ: два написания одного среза — одна строка реестра.
    one_way = b.slice_name(b.parse_slice("register=chat,vertical=clinic", CASES))
    other_way = b.slice_name(b.parse_slice("vertical=clinic, register=chat", CASES))
    if one_way != other_way:
        problems.append(f"два написания одного среза дали два имени: {one_way} / {other_way}")
    if b.selection_kind(one_way) != "slice":
        problems.append(f"срез записан как {b.selection_kind(one_way)!r}")
    if b.selection_kind("nano") != "tier" or b.selection_kind(b.IDS_SELECTION) != "ids":
        problems.append("ярус или --ids записаны не своим видом выборки")
    # Отказы: ось, значение, пустота, повтор оси. Срез, который молча вернул бы
    # пустой список, отправил бы человека искать дефект корпуса вместо опечатки.
    for text, want in (("nope=1", "нет оси"), ("register=Chat", "не несёт"),
                       ("register", "одно «=»"), ("", "срез пуст"),
                       ("register=chat,register=clean", "дважды")):
        try:
            b.parse_slice(text, CASES)
            problems.append(f"срез {text!r} принят")
        except b.SliceError as refused:
            if want not in str(refused):
                problems.append(f"срез {text!r} отказан не по делу: {refused}")
    # И срез не выдаёт себя за ярус: замороженного состава у него нет.
    provenance = b.run_provenance(CASES, first, one_way, b.HERE / "ladder.json", b.REPO, True)
    if b.selection_is_the_tier(provenance) is not None:
        problems.append("срез сравнён с замороженным составом, которого у него нет")
    if b.provenance_json(provenance).get("selection_kind") != "slice":
        problems.append("запись прогона не называет срез срезом")
    return problems


def test_the_result_pii_column_says_how_much_of_it_is_measured() -> list[str]:
    """КОЛОНКА «ПД В РЕЗУЛЬТАТЕ» НАЗЫВАЕТ СВОЙ ОСТАТОК, и он заморожен поимённо.

    ТЗ писало «вторая слепота закрыта», потому что пяти названным путям
    (`courier_status.recipient.*`, `crm_upsert_contact.contact.*`) дали хопы.
    Дали — а 106 объявлений из 151 по-прежнему не пересекает ни один IN/tool-хоп,
    и ни V06 (объявление против формы возврата), ни K17 (хоп → объявление) в эту
    сторону не смотрят: удаление любого из 106 сразу из `result_pii` и из формы
    возврата не красило НИЧЕГО — тот же тест, который проходили те пятеро.

    ЗАМОРОЗКА, А НЕ НОЛЬ, и цена названа: инструмент объявляет, что его API
    МОЖЕТ вернуть, корпус решает, что он ВОЗВРАЩАЕТ. Проверка требует не нуля, а
    того, чтобы остаток был ровно тем, на который однажды посмотрели, — поэтому
    краснеет в обе стороны.
    """
    problems: list[str] = []
    lines = b.result_pii_residue(CASES)
    if any("ОТКАЗ" in line for line in lines):
        problems.append(f"остаток разошёлся с замороженным списком: {lines[1:3]}")
    # 183 И 116, НЕ 151 И 106: набор `office` добавил одиннадцать инструментов и
    # с ними 32 объявления, из которых корпус пересёк 22. Числа переписаны здесь
    # ПОСЛЕ того, как `UNCROSSED_RESULT_PII` назвал каждое из десяти новых
    # непересечённых поимённо — иначе рост остатка прошёл бы как рост корпуса.
    if "183 объявлений" not in lines[0] or "116 держатся объявлением" not in lines[0]:
        problems.append(f"строка остатка не называет обе половины: {lines[0]}")
    # Отрицательная половина первая: объявление, которое НИКТО не пересекает и
    # которого нет в списке, — отказ. Так выглядело бы новое декоративное поле.
    spare = "kb_search.records[].invented_leaf"
    watched = b.UNCROSSED_RESULT_PII
    from bench.agentpii5.tools import REGISTRY_V5
    name, leaf = spare.split(".", 1)
    spec = REGISTRY_V5[name]
    widened = replace(spec, base=replace(spec.base,
                                         result_pii=(*spec.base.result_pii, leaf)))
    REGISTRY_V5[name] = widened
    try:
        said = b.result_pii_residue(CASES)
        if not any("ОТКАЗ" in line and spare in line for line in said):
            problems.append(f"новое декоративное объявление принято молча: {said}")
    finally:
        REGISTRY_V5[name] = spec
    # Отрицательная половина вторая: замороженное объявление, которое КОРПУС
    # теперь пересекает, — тоже отказ, иначе список тихо стал бы потолком и
    # остаток «106» пережил бы любое улучшение.
    crossed_now = sorted(watched)[0]
    tool, path = crossed_now.split(".", 1)
    donor = next(case for case in CASES
                 if any(hop.kind == "IN" and hop.owner == "tool" for hop in case.hops))
    hop = next(one for one in donor.hops if one.kind == "IN" and one.owner == "tool")
    patched = replace(donor, hops=tuple(replace(one, tool_name=tool, path=path)
                                        if one is hop else one for one in donor.hops))
    said = b.result_pii_residue([one if one is not donor else patched for one in CASES])
    if not any("ОТКАЗ" in line and crossed_now in line for line in said):
        problems.append(f"пересечённое замороженное объявление принято молча: {said}")
    return problems


def test_a_slice_axis_reads_the_case_and_not_the_offer() -> list[str]:
    """ОБЕ многозначные оси среза считаются по ХОПАМ: вертикаль — не по
    `base.tools`, тип ПД — не по `base.pii`.

    `tools` — это то, что агенту ПРЕДЛОЖИЛИ. Случай, которому предложили
    инструмент клиники и который туда не ходил, попал бы в срез «только
    клиника», ничего о клинике не измеряя, — и число такого прогона описывало
    бы не вертикаль, а список предложений.

    `base.pii` — ТА ЖЕ БОЛЕЗНЬ НА ДРУГОЙ ОСИ, и полгода она стояла рядом с
    закрытой. В нём лежат значения seed-записи мока, которых не произносит ни
    одно сообщение и не возвращает ни один хоп: `pii_type=EMAIL` набирал 713
    случаев, из которых 383 о почте не говорили ничего. ПРЕЖНЯЯ ПРОВЕРКА ЭТОГО
    УВИДЕТЬ НЕ МОГЛА — она сверяла `case_slice_values(case, "pii_type")` с тем
    же `base.pii`, из которого функция и читала, то есть сверяла функцию с
    собой.

    ОБЕ ПОЛОВИНЫ ЗДЕСЬ ОТРИЦАТЕЛЬНЫЕ: мало показать, что срез читает хопы, —
    нужно, чтобы чтение по объявлению давало ДРУГОЙ ответ. Иначе проверка
    зеленела бы и на корпусе, где эти два чтения совпадают, и на коде, который
    вернулся к объявлению.
    """
    problems: list[str] = []
    offered = {case.base.id for case in CASES
               if any(c.TOOL_VERTICAL.get(name) == "clinic" for name in case.base.tools)}
    walked = {case.base.id for case in CASES
              if "clinic" in b.case_slice_values(case, "vertical")}
    if not walked:
        problems.append("ни один случай не ходит в клинику — срез по вертикали не проверен")
    if walked >= offered and offered:
        problems.append("срез по вертикали читает предложенные инструменты, а не хопы")
    # Тип ПД: срез обязан быть СТРОГО уже объявления хотя бы на одном типе, и
    # каждый взятый тип обязан иметь хоп с ИМЕННО ЭТОЙ записью.
    narrowed: list[str] = []
    for kind in sorted({item.type for case in CASES for item in case.base.pii}):
        declared = {case.base.id for case in CASES
                    if any(item.type == kind for item in case.base.pii)}
        crossing = {case.base.id for case in CASES
                    if kind in b.case_slice_values(case, "pii_type")}
        if not crossing <= declared:
            problems.append(f"срез по типу {kind} берёт случаи, которые типа не несут вовсе")
        if crossing < declared:
            narrowed.append(kind)
    if not narrowed:
        problems.append("срез по типу ПД совпал с объявлением на всех типах: "
                        "либо он читает `base.pii`, либо корпус перестал нести "
                        "необойдённые записи и проверку надо переписать")
    for case in CASES:
        crossed = {hop.item_id for hop in case.hops}
        if b.case_slice_values(case, "pii_type") != {item.type for item in case.base.pii
                                                     if item.id in crossed}:
            problems.append(f"{case.base.id}: типы ПД среза не равны типам ПЕРЕСЕЧЁННЫХ записей")
            break
    return problems



def test_the_suite_axis_is_a_slice_across_verticals() -> list[str]:
    """Пятая ось среза — НАБОР, и три вещи о ней держат её честной.

    ЗАЧЕМ ОНА ВООБЩЕ. Инструменты одного клиента лежат в пяти вертикалях сразу:
    почта — messaging, приглашение — calendar, трекер — support, карточка — crm,
    таблица и документ — files. `--slice vertical=messaging` возьмёт треть из
    них и разбавит её SMS; вопрос «что ваши числа говорят о МОИХ инструментах»
    ни одна прежняя ось не задаёт. Ось общая: следующий клиент получает своё имя
    набора и ту же механику.

    ПО ХОПАМ, А НЕ ПО `base.tools`, и ОБЕ половины проверки отрицательные.
    Случай, которому инструмент набора лишь ПРЕДЛОЖИЛИ и который туда не ходил,
    попал бы в срез, ничего о наборе не измеряя, — и цифра, которую мы назовём
    клиенту, была бы разбавлена случаями, в которых его форм нет. Ровно эта
    болезнь уже ловилась на вертикали, поэтому проверка построена так, чтобы
    красить код, вернувшийся к объявлению.
    """
    problems: list[str] = []
    if "suite" not in b.SLICE_AXES:
        return ["оси suite нет в SLICE_AXES"]
    suite = next(iter(c.SUITES))
    members = [name for name, one in c.TOOL_SUITE.items() if one == suite]
    if len({c.TOOL_VERTICAL[name] for name in members}) < 2:
        problems.append(f"набор {suite!r} целиком внутри одной вертикали — "
                        f"тогда его выделяет ось vertical и эта ось декоративна")
    sample = next((case for case in CASES if case.hops), None)
    if sample is None:
        return problems + ["в корпусе нет случая с хопами — ось не на чем показать"]
    # ПРЕДЛОЖИЛИ, НО НЕ ХОДИЛИ: инструмент набора дописан в `base.tools`, и срез
    # обязан остаться пустым.
    offered = replace(sample, base=replace(sample.base,
                                           tools=(*sample.base.tools, members[0])))
    if b.case_slice_values(offered, "suite"):
        problems.append("срез по набору читает предложенные инструменты, а не хопы")
    # ХОДИЛИ: один хоп переведён на инструмент набора, и срез обязан его взять.
    walked = replace(sample, hops=(replace(sample.hops[0], tool_name=members[0]),
                                   *sample.hops[1:]))
    if b.case_slice_values(walked, "suite") != frozenset({suite}):
        problems.append(f"случай, сходивший в {members[0]}, не попал в срез "
                        f"{suite!r}: {b.case_slice_values(walked, 'suite')}")
    # Случай, не трогавший ни одного инструмента набора, не принадлежит никакому.
    if any(hop.tool_name in c.TOOL_SUITE for hop in sample.hops):
        return problems
    if b.case_slice_values(sample, "suite"):
        problems.append("случай без инструментов набора попал в набор")
    return problems


def test_an_unknown_suite_is_refused_by_name() -> list[str]:
    """Срез по набору, которого корпус не несёт, — ИМЕНОВАННЫЙ отказ.

    Пустая выборка читается как «таких случаев нет», и человек идёт искать
    дефект корпуса вместо опечатки; отказ обязан сказать, чего корпус не несёт,
    и перечислить, что несёт (`SliceError`, та же дисциплина, что у вертикали).
    """
    try:
        b.parse_slice("suite=нетакого", CASES)
    except b.SliceError as error:
        return [] if "suite" in str(error) else [f"отказ не называет ось: {error}"]
    return ["срез по несуществующему набору не отказал"]


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_the_authored_and_the_revised_halves_are_counted_apart,
    test_regenerating_the_ladder_needs_the_assertion,
    test_a_changed_corpus_refuses_the_kept_ladder, test_regeneration_keeps_the_holdout,
    test_static_proof_sees_containment, test_every_case_proves_its_declaration,
    test_corpus_size_and_plan, test_corpus_rules,
    test_v4_view_loads, test_v5_round_trip, test_holdout_frozen, test_holdout_is_disjoint,
    test_check_prints_shares, test_no_search_in_any_generator,
    test_no_value_is_beyond_both_ways_of_scoring_it,
    test_every_extracted_item_has_a_hop, test_free_text_transitions_can_be_won_and_lost,
    test_no_item_carries_a_placeholder_surface,
    test_stamp_refreshes_only_when_membership_holds,
    test_a_family_dropped_into_the_plan_is_built_and_printed,
    test_a_case_outside_every_tier_is_named_by_the_check,
    test_dead_weight_and_content_duplicates_are_counted,
    test_the_first_live_run_stamps_the_holdout,
    test_a_touched_ladder_refuses_every_redraw,
    test_a_stamp_refresh_keeps_the_touch,
    test_a_live_run_refuses_a_dirty_tree_and_a_foreign_corpus,
    test_the_provenance_is_read_off_the_real_tree,
    test_every_tier_starts_and_a_foreign_selection_does_not,
    test_the_acceptance_test_runs_on_every_push,
    test_widened_watch_is_restored,
    # Перерезка 23.09: ярус — миниатюра корпуса, и выборка прогона настраиваема.
    test_a_tier_is_a_miniature_and_the_old_draw_is_refused,
    test_the_stratified_order_is_deterministic_and_order_independent,
    test_the_floor_fits_the_smallest_tier,
    test_the_recut_did_not_move_the_holdout,
    test_a_slice_is_repeatable_and_never_reads_the_holdout,
    test_a_slice_axis_reads_the_case_and_not_the_offer,
    test_the_suite_axis_is_a_slice_across_verticals,
    test_an_unknown_suite_is_refused_by_name,
    test_the_result_pii_column_says_how_much_of_it_is_measured)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        if problems:
            failures += 1
            print(f"  {check.__name__}: {problems[0]}")
            for problem in problems[1:5]:
                print(f"    {problem}")
    print(f"build: {len(CHECKS)} проверок над {len(CASES)} случаями · "
          + ("PASS" if not failures else f"FAIL ({failures})"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
