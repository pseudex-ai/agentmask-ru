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

from bench.agentpii4.schema import case_from_json
from bench.agentpii5 import build as b
from bench.agentpii5 import contracts as c
from bench.agentpii5 import mock
from bench.agentpii5 import revise as revise_module
from bench.agentpii5.contracts import CaseV5, Hop
from bench.agentpii5.metrics import leaf_value_ok, returned_as_item
from bench.agentpii5.schema import case_v5_from_json, corpus_digest_v5, validate_corpus_v5
from bench.agentpii5.scenarios5 import common
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
    test_widened_watch_is_restored)


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
