"""Real taxi-dispatch speech: addresses dictated aloud, and the numbers that are not.

SOVA RuDevices (`bond005/sova_rudevices`), 41 342 unique human transcriptions,
CC BY 4.0. The licence is why this family exists in the shape it does: unlike
OpenSTT, which `speech` draws from, these texts MAY be redistributed, so the
utterances live in `corpus.json` as plain content. No content-hash tables, no
hydration step, no pinned selection digest guarding a filter — roughly a third
of `speech.py` is licence compliance and none of it is needed here.

WHY A SECOND SPEECH FAMILY RATHER THAN A WIDER `speech`. `speech` selects its
utterances with a filter built from street-type words and house markers — the
same signals the detector leans on — so it measures the engine on the population
the engine was shaped for and flatters it. That defect cannot be retrofitted
away, because the filter IS the family's selection. Here selection comes from a
hand label and nothing else: a human read 650 utterances with the detector
switched off and wrote down what carried an address. Nothing in this file
consults a street vocabulary, morphology, or any other engine component to
decide what goes in.

TWO STRATA, AND COUNTING THEM ALIKE IS THE TRAP THIS FAMILY EXISTS TO AVOID.

    marker         400 utterances — a CENSUS of the stratum holding a street-type
                   word or a house marker. Complete, and biased by exactly the
                   signals above: it is the `bench/voice` filter, read in full.
    number-sample  250 utterances — a RANDOM SAMPLE (seed 20260830) of the 4805
                   remaining utterances that hold a numeral or a digit. Unbiased
                   by construction, so an interval over it is honest.

The sample found 13 addresses in 250 utterances, so the number-only stratum
holds on the order of 250 address values against the marker stratum's 156. THE
CENSUS OF THE MARKER STRATUM IS NOT A CENSUS OF THE CORPUS, and a family built
on the 400 alone would inherit precisely the skew that makes `speech` flatter.

The correction is a weight, not a redraw. Cases carry their stratum in
`scenario` and `STRATUM_WEIGHTS` states what one case of each is worth; a rate
computed without it gives the sampled stratum a nineteenth of its true weight.
This mirrors `REGISTER_WEIGHTS`: cells stay uniform so each stratum keeps its
own error bars, and the traffic weighting lives one layer out, in the scorer.

TWO ROW CLASSES ARE DELIBERATELY NOT USED.

  * `неоднозначно` (10 rows) — the annotator looked and declined to decide.
    Scoring them either way would resolve, on our own authority, a judgement the
    only person who read them refused to make.
  * `улица без номера` (14 rows, 16 values) — kept, and `optional`. A bare
    street is NOT personal data: «улица Пушкина» identifies nobody, one step
    more specific than the city that already identifies nobody. The engine
    refuses one deliberately unless a house number or an intent word stands with
    it, and in dispatch speech neither does — «на бульваре героев», «в газовом
    переулке». SO THIS COLUMN READS 0/16 AND THAT IS THE CORRECT ANSWER, not a
    hole: it is «не ПД, не обязаны», and a reader who sees 0% as a failure will
    go and break the veto that produces it. The contrast is the OpenSTT set in
    `speech`, where the same class scores 7/15 because those utterances wrap the
    street in a sentence that does carry address context.

    The boundaries came from the annotator reading the utterances, not from
    searching the finished string for something matching a pattern — the v1
    defect this corpus was rebuilt to remove.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bench.agentpii2 import tools  # noqa: E402
from bench.agentpii2.schema import (  # noqa: E402
    Case, ExpectedCall, Negative, PiiItem, ToolSchema,
)

LABELS = Path.home() / ".cache" / "pseudex-bench" / "rudevices_addresses.json"

# THE LABEL FILE IS PINNED. A re-labelling changes what the corpus claims, and
# a corpus whose ground truth moved while its digest stayed still is not
# comparable to its own previous run. Raising here forces the maintainer to
# re-pin deliberately, which is the same guard `speech` puts on its selection.
LABELS_DIGEST: str = "5ce7bcfa7a60"

# One case of `number-sample` speaks for 4805/250 utterances of the stratum it
# was drawn from; one case of `marker` speaks for itself, the stratum being read
# in full. A scorer that reports a single dispatch number MUST apply these, and
# one that reports the strata apart must still never add them up unweighted.
STRATUM_WEIGHTS: dict[str, float] = {
    "dispatch_marker": 1.0,
    "dispatch_marker_street": 1.0,
    "dispatch_sample": 4805.0 / 250.0,
    "dispatch_sample_street": 4805.0 / 250.0,
}

_SCENARIO: dict[str, str] = {
    "marker": "dispatch_marker",
    "number-sample": "dispatch_sample",
}

_ADDRESS = "адрес с номером"
_STREET = "улица без номера"
_PLAIN = "не адрес"

# Numerals as ASR writes them: words, never digits. Used ONLY to draw the
# boundary of a negative — never to decide whether a row is an address, which
# is what the hand label is for.
_NUM = (r"(?:нол\w+|один\w*|одна|одну|два|две|три|четыре|пять|шесть|семь"
        r"|восем\w*|девят\w+|десят\w+|одиннадцат\w+|двенадцат\w+|тринадцат\w+"
        r"|четырнадцат\w+|пятнадцат\w+|шестнадцат\w+|семнадцат\w+"
        r"|восемнадцат\w+|девятнадцат\w+|двадцат\w+|тридцат\w+|сорок\w*"
        r"|пятьдесят|шестьдесят|семьдесят|восемьдесят|девяност\w+|сто|сот\w+"
        r"|двест\w+|трист\w+|четырест\w+|пятьсот|шестьсот|семьсот|восемьсот"
        r"|девятьсот|тысяч\w*|перв\w+|втор\w+|трет\w+|четверт\w+|пят\w+"
        r"|шест\w+|седьм\w+|восьм\w+|девят\w+|десят\w+|\d+)")
_RUN = re.compile(rf"\b{_NUM}(?:\s+{_NUM})*\b", re.IGNORECASE)
_LEXICON = re.compile(
    r"\b(?:улиц\w*|проспект\w*|переул\w*|бульвар\w*|шоссе|набережн\w*"
    r"|проезд\w*|площад\w*|микрорайон\w*|дом|дома|корпус\w*|строени\w*"
    r"|квартир\w*|подъезд\w*|этаж\w*|литер\w*)\b", re.IGNORECASE)

_PLAIN_WHY = ("числовой или адресный оборот в реплике, размеченной человеком "
              "как «не адрес»")

_SYSTEM: str = ("Ты диспетчер такси. Если клиент называет адрес подачи, вызови "
                "register_address и передай адрес дословно, как он прозвучал.")

# The dispatcher turn between the two utterances. It exists for the wire format
# and carries no claim: some providers refuse two consecutive user messages and
# others merge them, and a merge would move every offset in the second one.
_OPERATOR_TURN: str = "Принял, слушаю."

# The family is one register throughout, because the source is. Every utterance
# is ASR output: numbers in words, no punctuation, no capitals.
_REGISTER: str = "voice_raw"

# Difficulty is not a dimension here for the same reason it is not one in
# `speech`: the field has no «not applicable» member, and spreading values over
# rows would draw a gradient the annotation never drew.
_DIFFICULTY: str = "hard"


def _rows() -> list[dict[str, object]]:
    """The hand labelling, verified against its pin."""
    if not LABELS.exists():
        raise FileNotFoundError(
            f"the RuDevices labelling is missing at {LABELS}. It is not in the "
            f"repository — see rudevices_addresses.README.md beside it")
    rows = json.loads(LABELS.read_text(encoding="utf-8"))
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    digest = hashlib.blake2b(canonical, digest_size=6).hexdigest()
    if digest != LABELS_DIGEST:
        raise ValueError(
            f"the labelling changed: {LABELS} now hashes to {digest}, the "
            f"family is pinned to {LABELS_DIGEST}. Re-pin deliberately and "
            f"rebuild, so the corpus digest moves with the ground truth")
    return rows


def _locate(text: str, span: str, cursor: int, key: str) -> tuple[int, int]:
    """Where this span sits, searching forward from the previous one.

    Progressive rather than absolute: «ферганская один у нас находится миронова
    пятьдесят восемь» is two flats in one utterance, and two spans that happened
    to share a surface form would otherwise both resolve to the first.
    """
    start = text.find(span, cursor)
    if start < 0:
        raise ValueError(f"utterance {key}: annotated span {span!r} does not "
                         f"occur in the text at or after {cursor}")
    return start, start + len(span)


def _negatives(row: dict[str, object], message: int) -> list[Negative]:
    """The address-shaped fragments of an utterance a human read as no address.

    THE CLAIM IS THE FRAGMENT, NOT THE UTTERANCE, and here that is a correctness
    requirement rather than the licence constraint it is in `speech`. These texts
    may ship whole, so claiming the whole utterance is available — and it would
    be wrong: `Negative` carries no type, this register is full of people saying
    their own names («павлова тамара владимировна» is a RuDevices utterance), and
    a whole-utterance claim would charge the gateway for masking a real person
    correctly. What the annotator judged is narrower and exactly right: this
    number, this address word, is not an address.

    Numerals and address vocabulary are merged when they touch, so «шестнадцатый
    кабинет» is one claim rather than two halves a maximal span could satisfy
    while covering neither.
    """
    text = str(row["text"])
    key = str(row["key"])
    spans = sorted(
        [match.span() for match in _RUN.finditer(text)]
        + [match.span() for match in _LEXICON.finditer(text)])
    if not spans:
        raise ValueError(f"utterance {key} carries neither a numeral nor an "
                         f"address word, yet one of those is what selected it "
                         f"into the labelled set: {text!r}")
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    out: list[Negative] = []
    seen: set[str] = set()
    for start, end in merged:
        value = text[start:end]
        if value in seen:
            continue
        seen.add(value)
        out.append(Negative(value=value, why=_PLAIN_WHY, msg=message))
    return out


def _claimable(row: dict[str, object]) -> bool:
    """Whether this utterance carries a fragment a negative can point at.

    58 of the 471 do not, and they are dropped from the companion pool rather
    than forced into one. The selection filter that built the strata knows more
    address words than this file does — «тупик» and «квартал» are ГАР street
    types and both appear — and widening `_LEXICON` until it matched would mean
    reconstructing that filter by guesswork, which is how a corpus quietly
    starts selecting on the detector's own signals again. A companion that
    claims nothing simply is not one; it costs a row from a pool of hundreds.
    """
    text = str(row["text"])
    return bool(_RUN.search(text) or _LEXICON.search(text))


def _tool() -> ToolSchema:
    """A fresh dict per case: the schemas travel into a JSON corpus and into a
    provider call, and one shared mutable object would let a scorer's edit reach
    every case in the family."""
    return tools.schema_for("register_address")


def _address_case(row: dict[str, object], companion: dict[str, object],
                  index: int) -> Case:
    """A dictated address, paired with a real utterance that holds none.

    `canonical` IS the surface form. A CRM would store «улица Гусева, 7», but no
    leg of this product converts «семь» into a digit, and demanding it back would
    score the gateway on a normalisation it never performs — v1's lesson, that
    the ground truth is the canonical form of WHAT WAS SAID.
    """
    text = str(row["text"])
    key = str(row["key"])
    spans = [str(span) for span in row["spans"]]
    if not spans:
        raise ValueError(f"utterance {key} is labelled {_ADDRESS!r} and the "
                         f"annotation draws no boundary for it")
    items: list[PiiItem] = []
    cursor = 0
    for position, span in enumerate(spans):
        start, end = _locate(text, span, cursor, key)
        cursor = end
        # ONE ITEM PER ANNOTATED ADDRESS, each with its OWN identity. Two
        # addresses in one utterance are two places, and a shared identity would
        # demand one substitute for both — the merge this corpus exists to
        # catch, manufactured by us instead of by the gateway.
        items.append(PiiItem(
            id=f"addr{position}",
            type="LOC",
            value=span,
            start=start,
            end=end,
            canonical=span,
            msg=1,
            identity=f"place{position}",
            duty="required",
            tool_param="address",
        ))
    scenario = _SCENARIO[str(row["filter"])]
    return Case(
        id=f"dispatch_{scenario.split('_')[1]}_{index:03d}",
        family="dispatch",
        scenario=scenario,
        register=_REGISTER,
        difficulty=_DIFFICULTY,
        length_rung="short",
        conversation_id="",
        relation="equality",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
            {"role": "assistant", "content": _OPERATOR_TURN},
            {"role": "user", "content": str(companion["text"])},
        ],
        tools=[_tool()],
        pii=items,
        preceded_by="",
        annotators=1,
        adjudicated=False,
        # A NEGATIVE NEVER SHARES A MESSAGE WITH A PII ITEM. An utterance naming
        # a street and a house would otherwise claim both that the street may be
        # masked and that the number beside it may not, and a gateway taking the
        # natural maximal span would be right and wrong at once.
        negatives=_negatives(companion, 3),
        # ONE CALL PER ADDRESS. `register_address` takes one address, so an
        # utterance naming two demands two calls — not one argument holding both,
        # which would let a gateway that lost either half still compare equal.
        calls=[ExpectedCall(
            name="register_address",
            after_msg=1,
            arguments={"address": entry.value},
            pii_items=[entry.id],
        ) for entry in items],
    )


def _street_case(row: dict[str, object], companion: dict[str, object],
                 index: int) -> Case:
    """A bare street, `optional`, travelling with a real negative utterance.

    The companion is what makes the case falsifiable: the street itself can fail
    nothing, so alone the case would be unmeasurable in either direction.
    """
    text = str(row["text"])
    key = str(row["key"])
    spans = [str(span) for span in row["spans"]]
    if not spans:
        raise ValueError(f"utterance {key} is labelled {_STREET!r} and the "
                         f"annotation draws no boundary for it")
    items: list[PiiItem] = []
    cursor = 0
    for position, span in enumerate(spans):
        start, end = _locate(text, span, cursor, key)
        cursor = end
        items.append(PiiItem(
            id=f"street{position}",
            type="LOC",
            value=span,
            start=start,
            end=end,
            canonical=span,
            msg=0,
            identity=f"place{position}",
            duty="optional",
            tool_param=None,
        ))
    scenario = _SCENARIO[str(row["filter"])] + "_street"
    return Case(
        id=f"dispatch_street_{index:03d}",
        family="dispatch",
        scenario=scenario,
        register=_REGISTER,
        difficulty=_DIFFICULTY,
        length_rung="short",
        conversation_id="",
        relation="equality",
        messages=[
            {"role": "user", "content": text},
            {"role": "assistant", "content": _OPERATOR_TURN},
            {"role": "user", "content": str(companion["text"])},
        ],
        tools=[],
        pii=items,
        preceded_by="",
        annotators=1,
        adjudicated=False,
        negatives=_negatives(companion, 2),
    )


def _long_words(text: str) -> set[str]:
    return {word for word in re.findall(r"[а-яё]+", text.lower())
            if len(word) >= 6}


def _pair(rng: random.Random, addresses: list[dict[str, object]],
          plains: list[dict[str, object]]) -> list[tuple[dict, dict]]:
    """Give each address utterance a companion that shares no long word with it.

    Two mentions of one street inside a single conversation are exactly what the
    engine's conversation scope is built to LINK, so a companion drawn carelessly
    could put «гусева» in both turns and manufacture a link — and the false mask
    that follows would be charged to the gateway rather than to our pairing.
    """
    pool = list(plains)
    rng.shuffle(pool)
    pairs: list[tuple[dict, dict]] = []
    for row in addresses:
        words = _long_words(str(row["text"]))
        choice = next((candidate for candidate in pool
                       if not (words & _long_words(str(candidate["text"])))),
                      None)
        if choice is None:
            raise ValueError(
                f"no companion utterance is disjoint from {row['key']}; the "
                f"pool of {len(plains)} has been exhausted, which is a floor to "
                f"raise deliberately rather than a pairing to loosen")
        pool.remove(choice)
        pairs.append((row, choice))
    return pairs


def build(rng: random.Random, count: int) -> list[Case]:
    """Every labelled address, both strata, in a fixed order.

    THE FAMILY IS A CENSUS OF WHAT WAS LABELLED and `count` is asserted rather
    than honoured: subsampling would quietly shrink the stratum whose whole
    purpose is to carry an unbiased interval, and 13 sampled addresses do not
    survive being cut. A changed labelling should move this number in `PLAN`
    where a reader can see it, not inside a generator.
    """
    rows = _rows()
    by_stratum: dict[str, list[dict[str, object]]] = {}
    streets: dict[str, list[dict[str, object]]] = {}
    plains: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        stratum = str(row["filter"])
        if stratum not in _SCENARIO:
            raise ValueError(f"unknown stratum {stratum!r} in the labelling; "
                             f"a new one needs a weight in STRATUM_WEIGHTS "
                             f"before any case may be built from it")
        if row["label"] == _ADDRESS:
            by_stratum.setdefault(stratum, []).append(row)
        elif row["label"] == _STREET:
            streets.setdefault(stratum, []).append(row)
        elif row["label"] == _PLAIN and _claimable(row):
            plains.setdefault(stratum, []).append(row)
    total = (sum(len(group) for group in by_stratum.values())
             + sum(len(group) for group in streets.values()))
    if count != total:
        detail = ", ".join(
            f"{name} {len(by_stratum.get(name, ()))}+{len(streets.get(name, ()))}"
            for name in sorted(set(by_stratum) | set(streets)))
        raise ValueError(
            f"dispatch is a census: the labelling holds {total} utterances "
            f"carrying a street ({detail}, address+bare) and PLAN asks for "
            f"{count}. Update PLAN, do not subsample")
    cases: list[Case] = []
    index = 0
    # Strata in a fixed order so the corpus digest does not depend on dict
    # iteration; companions drawn from the SAME stratum, so a case never mixes
    # two sampling frames and a scorer can weight it whole. Both classes draw
    # from ONE companion pool per stratum, so no utterance is a companion twice.
    for stratum in sorted(set(by_stratum) | set(streets)):
        pool = plains.get(stratum, [])
        pairs = _pair(rng, by_stratum.get(stratum, []) + streets.get(stratum, []),
                      pool)
        for row, companion in pairs:
            if row["label"] == _ADDRESS:
                cases.append(_address_case(row, companion, index))
            else:
                cases.append(_street_case(row, companion, index))
            index += 1
    return cases


def main() -> int:
    cases = build(random.Random("dispatch"), 168)
    spans = sum(len(case.pii) for case in cases)
    negatives = sum(len(case.negatives) for case in cases)
    required = sum(1 for case in cases for item in case.pii
                   if item.duty == "required")
    optional = spans - required
    print(f"dispatch: {len(cases)} cases, {required} обязательных значений, "
          f"{optional} optional (голая улица — НЕ ПД, 0% здесь корректен), "
          f"{negatives} негативов")
    for scenario, weight in sorted(STRATUM_WEIGHTS.items()):
        group = [case for case in cases if case.scenario == scenario]
        print(f"   {scenario:<17} {len(group):>3} кейсов   вес {weight:5.2f}   "
              f"{sum(len(case.pii) for case in group):>3} значений")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
