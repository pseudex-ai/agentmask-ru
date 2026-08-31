"""AgentPII-RU v3 — the case format. This file IS the specification.

The benchmark is publishable only if a third party can regenerate the corpus and
re-score a COMPETING gateway without reading our engine. Nothing here imports
from `pseudex/`; every rule a scorer needs — how a value is compared, how a
broken round trip is named, what a case must contain before it is allowed to
count — is stated here rather than left to whichever scorer runs first.

WHAT V2 GOT WRONG, measured on its own corpus (1334 cases):

  * **The register was inverted.** 16% of cases were literary — capitals,
    commas, «адрес доставки: Краснодар, проспект Мира, д. 5, кв. 100». Measured
    over 53 324 distinct human transcripts of Russian phone and dispatch speech:
    ZERO carry a digit, ZERO carry sentence punctuation, 0.028% start with a
    capital. The register v2 spent a sixth of its mass on does not occur in the
    traffic this product meets.
  * **Only 264 of 1334 cases (20%) carried a form taken from real speech.** The
    rest was template generation where «улица Чехова, дом 29, квартира 66» and
    «улица Чехова, дом 43, квартира 46» differ by a counter. A corpus of
    counter-variants measures one shape many times and calls it coverage.
  * **The tier ladder was a prefix**, so only `large` closed every dimension.
    A nano run reported on whatever the first twenty ids happened to be.
  * Two engine defects were invisible to it BY CONSTRUCTION, because both live
    where written text cannot go: an address whose house number is a word
    («школьная пятьдесят девять»), and an identifier dictated aloud (133 spoken
    phones in the v2 corpus, of which the engine found 0 — libphonenumber and
    every checksum wait for digits).

WHAT V3 CHANGES, and each change is a field or a corpus-level refusal:

  1. `Provenance` — every case says which real utterance its FORM came from, and
     `PiiItem.value_source` says separately where its VALUE came from. Real form
     with pooled values is the majority shape; `validate_corpus` refuses a corpus
     below MIN_REAL_FORM_SHARE.
  2. The literary register is capped at MAX_CLEAN_SHARE and gated per case: a
     `clean` case with no capital and no full stop is not literary, it is a
     `chat` case spending the literary budget.
  3. `Ladder.tiers` holds a FROZEN ID LIST PER TIER, nested, and `check_ladder`
     refuses a ladder whose nano does not exercise every family, register,
     provenance, context rung, duty and type. A prefix cannot promise that.
  4. `Provenance.selection` and `.weight` carry the sampling design forward, so
     the marker-filtered stratum — the one selected by the same words the
     detector looks at — can never be silently averaged with the random one.
  5. Expected calls are matched UNORDERED. Every published benchmark that looked
     at this concluded order is a property of the model, not of correctness
     (BFCL's own `method_invoke_order_checker` is committed COMMENTED OUT), and
     the owner has ruled model behaviour out of scope.

THREE AXES, AND ONLY THREE. `detect` (per type: found, found WHOLE, nothing
extra), `roundtrip` (did the reference call arrive with the reference
arguments), `answer` (did personal data leak into the final reply, and was a
substitute passed off as real). The arm-against-arm "transparency" axis v2
carried is deleted, not renamed: the owner ruled that measuring how the model
uses its tools is not this benchmark's job.

INDEPENDENCE RULE, inherited from v1/v2 and from `make_stress.py`: cases are
authored from the DOMAIN — what real Russian speech contains — never from a list
of what our detector currently finds. The first voice set admitted an utterance
only if it held «улица» or «дом», which is exactly what the engine looks at; it
reported 100% where the truth was 38.6%. `Provenance.selection` is that lesson
turned into a field, and `audit_unlabelled()` is its mechanical half.
"""

import hashlib
import json
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# `probes` is the mining-side numeral definition and it is imported here rather
# than copied, because the copy is what went wrong: the reference distribution
# was measured with `probes` and the corpus with a word list, and the audit
# printed the two side by side as though they were one measurement. It carries no
# dependency of its own and consults nothing in `pseudex/`.
if __package__ in (None, ""):                       # `python3 schema.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import probes                                   # type: ignore[import-not-found]
else:
    from bench.agentpii3 import probes

# The OpenAI function-calling schema is the PROVIDER's contract, not ours. Typed
# loosely on purpose: narrowing it would make the corpus un-replayable against a
# provider that adds a field, and the corpus's whole claim is that it runs
# against anyone's model with no translation layer.
ToolSchema = dict[str, Any]


class InvalidCase(ValueError):
    """A case that cannot be scored. Raised, never logged and stepped over."""


class InvalidCorpus(ValueError):
    """A corpus-level claim that does not hold. Same rule: refuse."""


# --- types ----------------------------------------------------------------
#
# The vocabulary a scorer compares against. An adapter for a competing gateway
# maps ITS names into these; the mapping belongs in the adapter, and this module
# refuses a type it does not know rather than accepting an unmapped name and
# scoring it as a miss for ever.
#
# `DOB` and not `DATE`, deliberately. A bare date is not personal data — it
# becomes personal by association with a birth cue or an identifier — so a
# corpus with a `DATE` type would invite cases demanding that «счёт от
# 15.05.2025» be masked, which is the over-masking defect, not the target.
TYPES: tuple[str, ...] = (
    "NAME", "LOC", "PHONE", "EMAIL", "DOB",
    "SNILS", "INN", "CARD", "PASSPORT", "PLATE",
)

# Types that neither speech corpus carries in usable quantity, measured in
# `mined/reference_distribution.json`: email and inn occur ZERO times, and
# phone/dob/snils/card/passport/plate occur too thinly to measure on. Their
# VALUES must be generated; their SENTENCES must still be drawn from the mined
# shapes, or the corpus tests the type in a register the type never appears in.
TEMPLATE_VALUE_TYPES: frozenset[str] = frozenset({
    "PHONE", "EMAIL", "DOB", "SNILS", "INN", "CARD", "PASSPORT", "PLATE",
})

# Compared by digits after separators are stripped. PLATE is NOT here: «А123ВС
# 77» is letters and digits and a digit-only comparison would call two different
# plates equal.
DIGIT_TYPES: frozenset[str] = frozenset({
    "PHONE", "DOB", "SNILS", "INN", "CARD", "PASSPORT",
})


# --- registers ------------------------------------------------------------
#
# How the SAME datum reaches the gateway. FIVE, and the split is measured rather
# than imagined — `mined/reference_distribution.json`, over 53 324 distinct
# utterances from OpenSTT `asr_calls_2_val` and SOVA RuDevices:
#
#     digits in text            0.0
#     sentence punctuation      0.0
#     starts with a capital     0.00028
#     numeral run present       0.1045
#     words, median             6
#
# `voice_raw` is therefore the BASE register of this product, not an exotic one.
# `clean` is the register v2 spent a sixth of its mass on and it is capped here
# at a twentieth, kept only to prove we did not break on it.
REGISTERS: tuple[str, ...] = (
    "voice_raw",   # ASR verbatim: numbers in words, no digits, no punctuation
    "voice_itn",   # ASR with inverse text normalisation on: digits, still no punctuation
    "chat",        # a messenger: lower case, digits, few separators
    "sloppy",      # chat plus writing errors — keyboard-shaped, not phonetic
    "clean",       # a web form or a document: capitals, commas, full stops
)

SPEECH_REGISTERS: frozenset[str] = frozenset({"voice_raw", "voice_itn"})

# v2 published a traffic-weighted total beside the unweighted one, using weights
# nothing had measured. v3 does not ship weights at all: the corpus mix is
# authored AGAINST a measured reference distribution, so the unweighted total is
# the estimate, and the per-register breakdown is printed beside it always. A
# deployment with its own mix calls `reweight()` with its own numbers — which is
# the honest version of what v2's constant pretended to be.


# --- provenance -----------------------------------------------------------
#
# WHERE THE FORM CAME FROM. This is the axis v2 did not have, and its absence is
# why 80% of that corpus was counter-variants of four sentences.
#
#   verbatim    the text IS a real utterance, unchanged. Ground truth is the
#               hand annotation. Ships only if the licence allows.
#   recombined  the SENTENCE SHAPE is a mined one (`Provenance.shape` names it)
#               and the values are drawn from pools. This is the majority and it
#               is what makes «form from real speech» compatible with a
#               generator that knows its own ground truth.
#   template    neither form nor values come from a corpus. Permitted ONLY for a
#               case carrying a type no speech corpus holds, and reported apart.
PROVENANCES: tuple[str, ...] = ("verbatim", "recombined", "template")

# WHERE THE VALUE CAME FROM, which is a different question and was conflated
# with the one above until it cost a whole family. A spoken phone is a TEMPLATE
# VALUE inside a RECOMBINED FORM: the digits are ours, the sentence around them
# is a real dispatcher's.
VALUE_SOURCES: tuple[str, ...] = ("corpus", "pool", "template")

# HOW THE UTTERANCE ENTERED THE SET. The first voice set is the reason this is a
# field and not a footnote: it admitted a reply only when «улица» or «дом» was
# present, which is what the engine looks at, so the set could only ever show
# what we already found. Measured on the hand labels afterwards, the marker probe
# recalls 97.2% inside the stratum it selects and 0.0% outside it.
#
#   census   the whole stratum was read. Weight 1.0.
#   random   a fixed-seed random sample of a larger stratum. `weight` is the
#            inverse sampling fraction (19.22 for RuDevices' number layer) and
#            EVERY share over such cases must carry it.
#   marker   selected by a surface cue the detector also uses. BIASED UPWARD by
#            construction. Allowed, declared, and never the only source of a type.
#   authored the case was written, not sampled.
SELECTIONS: tuple[str, ...] = ("census", "random", "marker", "authored")

# Fail closed on an unknown licence: a corpus whose licence we cannot name is a
# corpus we cannot decide whether to ship.
LICENCES: frozenset[str] = frozenset({"CC BY 4.0", "CC BY-NC 4.0", "authored"})
SHIPPABLE_LICENCES: frozenset[str] = frozenset({"CC BY 4.0", "authored"})


# --- families -------------------------------------------------------------
#
# A family is a QUESTION, not a topic. Two families are justified only when a
# defect can pass one and fail the other; `docs/tz-agentpii3.md` §4 carries the
# argument for each and the list of the ones that were rejected.
#
# `length` is NOT here and that is deliberate. The owner named it, and as a
# family it would have measured only itself — context depth has to CROSS the
# others (the case he described, «ПД названы двадцать реплик назад и упоминаются
# косвенно», is `indirect` at `context="long"`). It is `Case.context` instead.
#
# `rank` from v2 is deleted, not moved. It asked the model to order or compare
# protected values, which is model reasoning over substitutes — ruled out of
# scope. `compare` survives because equality is decided by the GATEWAY's linking
# (one identity, one substitute), not by the model's judgement.
FAMILIES: tuple[str, ...] = (
    "transfer",   # PII stated by the customer, consumed by one call
    "compare",    # «а вы на Ленина 14?» / «тебя Игорь зовут?» — equality across mentions
    "indirect",   # the datum is never stated; the agent must fetch it with a tool
    "result",     # the datum ARRIVES in a tool result and must be masked inbound
    "crowd",      # several people in one dialogue — whose address is whose
    "spoken_id",  # an identifier dictated aloud: no digits anywhere
    "wordnum",    # an address whose house number is a word
    "repair",     # the value is said twice with a correction between
    "negative",   # nothing here may be masked
    "scope",      # the conversation boundary, in both directions
)


# --- context depth --------------------------------------------------------
#
# Banded by MESSAGE COUNT, not characters, because the owner's unit is «двадцать
# реплик назад» and because a character band means four different things across
# five registers: the median utterance is 35 characters in speech and several
# hundred in a support email. `deep` carries a character floor as well, so that
# thirty two-word replies cannot pass for a long context.
CONTEXT_RUNGS: dict[str, tuple[int, int]] = {
    "solo": (1, 2),      # the utterance, at most a system message beside it
    "short": (3, 8),
    "long": (9, 30),
    "deep": (31, 200),
}
MIN_DEEP_CHARS: int = 4_000


# --- duty -----------------------------------------------------------------
#
# TAB's DIRECT / QUASI split (Pilan et al., Computational Linguistics 48(4),
# 2022) applied WITHIN a type, which the literature does not do. «улица
# Пушкина» identifies nobody — hundreds of buildings stand on it, one step more
# specific than the city that already identifies nobody under 152-ФЗ ст. 3 п. 1.
# «улица Пушкина, 14» identifies a building. Scored as one number those two
# averaged 71% while the real figures were 94% and 47%.
#
# `optional` is NOT «we are unsure». It is a legal category: masking it is not an
# error, missing it is not a leak, it is counted in its own column and never
# folded into recall. Something merely ambiguous belongs in no column and must
# not be in the corpus — the hand annotation drops fifteen «неоднозначно»
# utterances for exactly this reason.
#
# WARNING from TAB's own numbers: direct/quasi was the LEAST reliable annotation
# they had, Fleiss kappa 0.46 against 0.67 for entity type. A hand-labelled duty
# needs two annotators and a third to break ties; `Case.annotators` and
# `Case.adjudicated` record whether it got them.
DUTIES: tuple[str, ...] = ("required", "optional")

# The other half of the precision measurement, and it is NOT the same thing as
# `optional`. An `optional` item may be masked without penalty. A negative may
# not be masked at all: «на улице погода хорошая», «три четырнадцатый кабинет»,
# «к девяти ноль ноль». In the call corpus a number standing beside «кабинет» or
# «отделение» occurs 528 times — the single largest false-positive source in this
# register — so these families are named rather than left to a generator's taste.
NEGATIVE_FAMILIES: tuple[str, ...] = (
    "street_no_name",      # «улица» with no name: the yard, the weather, a walk
    "flat_as_home",        # «квартира» with no number: buying, renting, cleaning
    "entrance_no_street",  # «шестой подъезд» standing alone
    "room_number",         # «три четырнадцатый кабинет», «второго отделения»
    "time_of_day",         # «к девяти ноль ноль» — zeros spoken as words
    "order_number",        # a dictated order number; the defect that shipped once
    "quantity",            # «за сто к пять штук», «двенадцать филиалов»
    "fare",                # «проезд» as the fare, not a street type
    "city_reference",      # a city used as a place, not as anyone's address
    "measure",             # «территория завода пять гектаров»
)


# --- link expectations ----------------------------------------------------
#
# `same` and `different` are both claims and both can be violated. `unjudged` is
# the third state: where the dialogue never carried the fuller form, demanding a
# link would score the gateway on information the conversation did not have,
# while silently accepting either answer would let a real merge hide there.
LINKS: tuple[str, ...] = ("same", "different", "unjudged")


# --- outcomes -------------------------------------------------------------
#
# AgentBench publishes a good taxonomy of finish reasons and then throws it away
# — its dbbench handler writes reward 0 for a harness exception, so a broken rig
# is recorded as a model failure. tau2-bench does the other thing: it EXCLUDES
# INFRASTRUCTURE_ERROR rows from the metrics («simulations that never ran») and
# prints the excluded count beside them.
#
# The line here is tau2's, with one addition the product forces. `gateway_5xx`
# is NOT excluded: masking that fails must propagate as a 5xx and the caller
# treats that as a block, so a refused request is a real product outcome and has
# to be visible in the rate. `provider_error` and `harness_error` are excluded,
# because a run that never reached the gateway says nothing about it.
TERMINATIONS: tuple[str, ...] = (
    "done",            # the agent finished
    "max_steps",       # it ran out of turns — a model failure, counted
    "gateway_5xx",     # our gateway refused — a product failure, counted
    "provider_error",  # the model provider failed — excluded, counted apart
    "harness_error",   # the rig failed — excluded, counted apart
    "timeout",         # excluded, counted apart
)
EXCLUDED_TERMINATIONS: frozenset[str] = frozenset({
    "provider_error", "harness_error", "timeout",
})


# --- break taxonomy -------------------------------------------------------
#
# What happened to a value between the customer's mouth and the tool's argument.
# Kept apart rather than summed, because v2's single rate plus a footnote could
# not distinguish a whitespace repair from a declined name written into a
# customer's CRM, and those have the same shape and opposite meanings.
BREAK_KINDS: tuple[str, ...] = (
    "ok",                  # the real value arrived
    "not_resolved",        # no vault row: the substitute resolved to nothing
    "residual",            # a minted token still stands in the argument
    "other_person",        # resolved to a REAL value belonging to someone else
    "renumbered",          # went in spelled out, came back in digits (or back)
    "inflected",           # resolved, but declined or otherwise re-formed
    "truncated",           # a prefix came back; the tail leaked or was lost
    "space_repaired",      # differs only in whitespace
    "lookalike_repaired",  # differs only by a Latin/Cyrillic twin
    "call_absent",         # the model never made the call — not the gateway
)

# What the final reply to the user did. `substitute_shown` is the failure the
# owner named: the agent hands the customer a fake and presents it as their own
# datum. It is worse than `token_shown`, which is visible garbage a human
# notices; a plausible fake address is not noticed by anybody.
ANSWER_VERDICTS: tuple[str, ...] = (
    "clean",
    "substitute_shown",   # a minted fake, presented as the customer's real value
    "token_shown",        # a raw token survived detokenisation
    "third_party",        # real data of somebody this case forbids disclosing
    "value_missing",      # a value the reply had to carry did not come back
    "answer_wrong",       # the closed answer is the other one
    "answer_absent",      # the agent never answered — not the gateway
)

# The three zones a case can be judged in. Derived from CONTENT, never declared:
# tau2-bench lets a task list a zone in `reward_basis` while the zone's criteria
# are null — 72 of 114 retail tasks do — and the evaluator then returns 1.0 for
# it with a note nobody reads. A zone that exists because its content exists
# cannot drift from its content.
AXES: tuple[str, ...] = ("detect", "roundtrip", "answer")


# --- tiers ----------------------------------------------------------------
#
# The sizes are the owner's. What is new is that a tier is a STRATIFIED FROZEN
# SET, not a prefix: v2's ladder was `order[:n]`, so only `large` closed every
# dimension and a nano run reported on whichever ids happened to sort first.
#
# Frozen, because a balanced sampler re-draws violently — measured on v1, growing
# the corpus 10% and re-running the sampler kept 3 of 10 nano cases. Freezing is
# what makes last month's number comparable to this month's. Nested, because
# otherwise `small` and `nano` answer different questions and their difference
# is not a signal about anything.
TIER_SIZES: dict[str, int] = {
    "nano": 30,
    "small": 120,
    "medium": 400,
    "large": 800,
    "max": 0,   # 0 means "every case in the corpus"
}

# Exact one-sided 95% Clopper-Pearson upper bound on the true failure rate given
# ZERO observed failures: 1 - 0.05**(1/n). Printed instead of a confidence
# interval at the small rungs, because ruling things out is all a small n can do
# — and because a Wald interval at a perfect score has width zero, which is
# maximally wrong exactly where these suites land.
TIER_ZERO_FAILURE_BOUND: dict[str, float] = {
    "nano": 0.09503, "small": 0.02466, "medium": 0.00746, "large": 0.00374,
}

# A per-type rate whose denominator is below this prints as a COUNT, never as a
# percentage. «полнота 99%» over two CARD instances is a lie by omission, and at
# nano every type is below it — which is the honest reading of a 30-case suite.
MIN_TYPE_DENOMINATOR: int = 5


# --- corpus-level bounds --------------------------------------------------
#
# Every one of these is a decision, not a preference, and each is enforced by
# `validate_corpus` rather than described in a README that nothing reads.
CORPUS_SIZE_BAND: tuple[int, int] = (1_500, 2_000)
MAX_CLEAN_SHARE: float = 0.05           # the literary register, capped
MIN_SPEECH_SHARE: float = 0.50          # voice_raw + voice_itn
MIN_REAL_FORM_SHARE: float = 0.70       # verbatim + recombined
MAX_NEGATIVE_ONLY_SHARE: float = 0.10   # a null gateway passes these


# --- shapes the audit knows about -----------------------------------------
#
# DELIBERATELY NOT OUR RECOGNIZERS. A mechanical shape scan whose only job is to
# catch a case whose text holds something PII-shaped that the ground truth forgot
# to claim. Filler in a `deep` case is where that happens, and an unclaimed value
# there scores as a false mask against a gateway that was right.
_SHAPE_DIGITS = re.compile(r"\d{6,}")
_SHAPE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SHAPE_PHONE = re.compile(
    r"(?:\+7|\b8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
_ANY_DIGIT = re.compile(r"\d")
_SENTENCE_PUNCT = re.compile(r"[.,;:!?]")
_WORD = re.compile(r"[а-яёa-z]+", re.IGNORECASE)

# The seven Latin letters with a Cyrillic twin, lower case only because the
# comparison casefolds first. No duplicates: a repeated key silently changes the
# mapping and the table stops meaning what it says.
_LOOKALIKE = str.maketrans("acepoxy", "асероху")

# Written-out numbers, WITH the contractions the register actually produces.
# Measured on the call corpus: 22.9% of every «-десят» form arrives contracted
# («песят», «шеесят», «шейсят»), and numerals arrive truncated mid-word («триц»,
# «девяно»). A list of only the canonical forms would make a numeral run
# invisible in exactly the utterances where it matters most.
#
# Exact forms, not stems. A stem list is shorter and wrong: «сто» prefixes
# «стоит», «три» prefixes «тритон», and a numeral scanner that fires on ordinary
# verbs turns the unlabelled-shape audit into noise, and a noisy gate gets
# switched off.
NUMERAL_WORDS: frozenset[str] = frozenset("""
ноль нуль ноля нуля нолю
один одна одно одну одного первый первая первое первого первом первую
два две двух двум второй вторая второе второго втором вторую
три трёх трех трём третий третья третье третьего третьем
четыре четырёх четырех четвёртый четвертый четвёртая четвёртого
пять пяти пятый пятая пятое пятого пятом
шесть шести шестой шестая шестое шестого шестом
семь семи седьмой седьмая седьмое седьмого седьмом
восемь восьми восьмой восьмая восьмое восьмого восьмом
девять девяти девятый девятая девятое девятого девятом
десять десяти десятый десятая десятое десятого десятом
одиннадцать двенадцать тринадцать четырнадцать пятнадцать
шестнадцать семнадцать восемнадцать девятнадцать
одиннадцатый двенадцатый тринадцатый четырнадцатый пятнадцатый
двадцать тридцать сорок пятьдесят шестьдесят семьдесят восемьдесят девяносто
двадцатый тридцатый сороковой
сто ста двести триста четыреста пятьсот шестьсот семьсот восемьсот девятьсот
тысяча тысячи тысяч
песят пеесят пяесят пейсят пясят шеесят шейсят шесят восемесят
триц тридц трис девяно семест восемест восемьст
тристо трииста шессот восем восемсь пяять четыыре
""".split())

# Street type words, from the seven the call corpus actually produced plus the
# forms the dispatch corpus adds. NOT the full 42-type ГАР list: this is a shape
# probe for the diagnostic below, not a recognizer, and importing the leased
# vocabulary here would make the benchmark depend on the bundle it is supposed
# to be able to score without.
STREET_TYPE_WORDS: frozenset[str] = frozenset("""
улица улицу улице улицы ул проспект проспекте проспекта пр
переулок переулке переулка пер шоссе бульвар бульваре площадь площади
проезд проезде набережная набережной тупик слобода тракт линия аллея
микрорайон мкр посёлок поселок квартал
""".split())

# House and flat markers, as spoken.
HOUSE_MARKERS: frozenset[str] = frozenset("""
дом дома доме д корпус корпуса к строение строения стр
квартира квартиры кв подъезд подъезде этаж этаже номер дробь литера
""".split())

# --- the filler guard, and it is ONE guard ---------------------------------
#
# Filler is a real utterance that carries no claim. Five families used to screen
# it with five private copies of the same idea and five different name lists, so
# a name added to one protected one family — «оксана» was in `direct`'s list and
# in nobody else's, and «александр», «михаил сергеевич» and «игорь» walked into
# `result` filler through a screen that had no name check at all. That is the
# defect: not the missing words, the missing SINGLE PLACE to put them.
#
# THE VOCABULARY IS THE CORPUS'S OWN, NOT A GAZETTEER. `FILLER_STOPWORDS` is a
# frozen snapshot of `attested_pii_vocabulary` — every word the corpus's own gold
# spans call a street or a person at least `ATTESTED_MIN` times. Two properties
# come from that and neither is available from an external list:
#
#   * it is not a second recognizer. The independence rule forbids screening
#     filler with the signals the DETECTOR reads; this screens it with the labels
#     WE wrote, which is a different thing and cannot flatter the detector.
#   * it is a FIXED POINT UNDER ITS OWN EFFECT, which is the property that makes
#     a snapshot usable at all. The vocabulary is a function of the GOLD values;
#     filler carries no gold; so tightening the screen cannot remove a word from
#     the list that drives it, and one pass converges. It is NOT invariant under
#     a resize — a value mentioned twice instead of three times drops out — so
#     `audit._vocabulary_drift` recomputes it from the built corpus and names
#     every word the constant lacks. Ten words appeared that way when the corpus
#     was trimmed to 2 000, and that is the mechanism working, not failing.
#
# IT IS DELIBERATELY NOT CURATED. «последний», «новая», «вера» and «труда» are
# ordinary Russian words that reach the list because «улица Последняя» and «Вера»
# are in the pools, and they stay. Rejecting them costs 2.4 per cent of 42 952
# RuDevices utterances — filler is fungible and there is a great deal of it — and
# keeping them would cost a judgement call every time the report is re-read.
ATTESTED_MIN: int = 3

# SPLIT IN TWO, and the split is load-bearing. A pure filler line may hold
# neither; a line chosen to CARRY a declared address-shaped negative («шестой
# подъезд», «улице» about the weather) has to be allowed its street vocabulary,
# or the trap pool empties and the over-masking half of the benchmark goes with
# it. What such a line may still never hold is a person — that is `unsafe_person`
# below, and it is the half that «говорит громова проедьте пожалуйста…» walked
# through.
FILLER_STREET_WORDS: frozenset[str] = frozenset("""
абазисная армейская бабушкина базисная барамзиной баранова барышникова берша
бумашевская буммашевская вишнёвая влксм вольная воровского воронеж
воронцовский восточная восточный воткинское выставочная гагарина горького
грибоедова гусева деловая депутатская деревообделочная дзержинского
добролюбова екатеринбург загородная загородный западный заречная заречное
зеленоградская ижевск казань калашникова калуга камская карла киров кирова
кирочная клубная колпино комиссарова коммунаров комсомольская комсомольский
котовского красина краснодар ленина ленинский лермонтова лесная ломоносова
луговая люхвинцева майская маркса марта машиностроителей маяковского
металлистов миронова молодёжная мончегорская наличная напойма некрасова
нижняя новая новое новосибирск объездное октябрьский октября орджоникидзе
павлова пенза пермь петрова победы подлесная полевая последний приморский
пушкина пушкинская разина ракетная репина русская рязань сабурова садовая
самара саратов северная северный семесят смольный советская совхозная
солнечная сортавала сосновый союзная старое степана строителей телегина
тельмана тимирязева толстого транспортная труда тюмень угловой удмуртская
ухтомского ферганская фруктовая фрунзе халтурина химзаводская цветочный
центральная циолковского чайковского чапаева челюскинцев челябинск четвёрьый
школьная шумайлова энгельса южное ярославль
""".split())

FILLER_NAME_WORDS: frozenset[str] = frozenset("""
абдуллаев абрамова александр александрович александровна алексеевич
алексеевна алексей алексею алексея алиса алла анастасия анатольевна андреев
андреева андреевич андреевна андрей анна антон аркадий арсентьеву артём
артёмович артёмовна аширбаева аширбаевой ашот бабаев белов белова беловой
беляев беляева бирюков битюков битюкова битюкову богданов богданова
бондаренко борис борисовна борисыч букин букина букину валентина
валентинович валентиновна валерий валерия валиахметов валиахметова василий
васильев васю вера веру виктор викторович викторовна викторыч виноградов
виноградова витальевич витальевна витька витёк владимир владимирович
владимировна владислав волков волкова вольнов вольнова воробьёв воронина
воронов вячеслав габдрахманов габдрахманова гаврилов гаврилова гаврилову
галина галину галю гилязов глеб глеба голубев голубева гончарова горбунова
горбуновой григорьев григорьевна громов громова громову гулиев гуляев
гуляеву гусев гусеву давидович дарье дарью дарья дементьев дементьева
дементьевой денис дениса денисович денисовна джонсон димыч дмитриевич
дмитриевна дмитрий дмитрию дмитрия дроздов дроздова дроздову дьяконовой
евгений евгению евгения егор егорович егоровна екатерина елена елене ерохин
ерохина ерохину жанна жанну заболотная заболотного заболотному заболотную
заболотный зайцев зайцева захаров зинаида зинаиду иван иванов иванович
ивановна иванову иваныч игоревич игоревна игорь игорю ильдар ильдару ильич
ирина ирину ирочка исаевой карен кирилл кириллович кирилловна киселёв
киселёва коваль ковалёв ковалёва коля комаров комарова коновалова
константинович константиныч копылова кочарян кочаряну ксения кудрявцева
кузнецов кузнецова кузнецовой кукушкин кукушкина кукушкину лариса ларису
лебедев лебедева леонид леонида леонидовна леонидыч лидия лыткина лыткиной
львович львовна любовь людмила майкл макаров макарова максим максима
максимович максимовна мамедова маратович маратовна марина марине марину
мария матвей мельник миллер миллера миронов миронова михаил михаила михайлов
михайлова михайлович михайловна михалыч мкртчян морозов морозова морозову
назаров назарова назарову наталье наталью наталья наташа нгуен нечаева
никита никитич никитична николаевич николаевна николаич николай николая нина
нину новиков новикова новиковой оков оксана олег олега олегович олеговна
олесь олесю олеся ольга ольге ольгу орлов орлова павел павла павлов павлова
павлович павловна павлову павлу палыч панкратов пантелеева петра петрович
петровна полина полю поляков полякова полякову попов потёмкиной птицын пётр
регина робертовна роман романа романович романовна роману рудакова рудаковой
русика руслан руслана рустам савельев саныч санька санёк саркисян светлана
светлану селезнёва семёнов семёнова сергеев сергеевич сергеевна сергееву
сергей сергею сергея серёжа серёжу симонов симонова смирнов смирнова соколов
соколова солонской сорокина станислав станкевич станкевичу степанович
степановна тагиев тамара тамару танюха тарасов тарасова татьяна татьяне
тахмина тахмине тимур тимура титова ткаченко тому ушаков фомин фёдоров
фёдорова фёдорыч хайруллин хайруллина худяков худякову цветкова цветковой
чернову шагиев шамиля шевченко шестаков шестакова широков широкова широкову
щербаков щербакову эльдар эльдара юлия юрьевна
""".split())

FILLER_STOPWORDS: frozenset[str] = FILLER_STREET_WORDS | FILLER_NAME_WORDS

# Case endings, generated rather than listed. «димон» was in a family's list and
# «димону» was not, and the reply naming him went into filler unclaimed. The junk
# this produces («оляу») matches nothing and costs nothing.
_FILLER_ENDINGS: tuple[str, ...] = (
    "", "а", "у", "е", "ы", "и", "ой", "ей", "ем", "ом", "ю", "ов", "ым", "ах")

def _forms(words: frozenset[str]) -> frozenset[str]:
    return frozenset(word + ending
                     for word in words for ending in _FILLER_ENDINGS)


_FILLER_NAME_FORMS: frozenset[str] = _forms(FILLER_NAME_WORDS)
_FILLER_STOP_FORMS: frozenset[str] = (
    _FILLER_NAME_FORMS | _forms(FILLER_STREET_WORDS))

_PATRONYMIC_IN_TEXT = re.compile(
    r"\b[а-яё]{3,}(?:ович|евич|овна|евна|ична|иныч|аныч|алыч)\b")


def attested_pii_vocabulary(
        cases: Sequence["Case"]) -> tuple[frozenset[str], frozenset[str]]:
    """Street words and name words the corpus's own gold vouches for.

    Built from CLAIMED values only, so it is the corpus judging itself. An
    external gazetteer would make this a second recognizer, and a second
    recognizer is the one thing a selection filter may never contain.

    Lives here rather than in `audit` because the filler guard and the audit that
    condemns the filler have to be reading the same list. They were two lists,
    and the audit could therefore only ever report words the guard had never been
    told about.
    """
    streets: dict[str, int] = {}
    names: dict[str, int] = {}
    skip = STREET_TYPE_WORDS | HOUSE_MARKERS | NUMERAL_WORDS
    for case in cases:
        for item in case.pii:
            if item.type == "LOC":
                for word in re.findall(r"[а-яё]{5,}", item.value.lower()):
                    if word not in skip:
                        streets[word] = streets.get(word, 0) + 1
            elif item.type == "NAME":
                for word in re.findall(r"[а-яё]{4,}", item.value.lower()):
                    names[word] = names.get(word, 0) + 1
    return (frozenset(w for w, n in streets.items() if n >= ATTESTED_MIN),
            frozenset(w for w, n in names.items() if n >= ATTESTED_MIN))


def unsafe_filler(text: str) -> str:
    """Why this utterance may not stand as unlabelled filler, or "" if it may.

    A REASON and not a boolean, because a screen that only says no is a screen
    nobody can debug, and the audit prints these strings when it explains what
    the pool refused.

    The numeral-run bound is TWO, not the four the shape audit uses. A spoken
    house number is one word to three («пять», «сто сорок шесть»), and the run
    that reached the corpus unclaimed was «тридцать девять» — length two, under
    every threshold anybody had set. The audit's threshold answers «is this a
    dictated identifier»; this one answers «could this be a number attached to a
    person», and the second question has to be asked further out.
    """
    lowered = text.lower()
    if _ANY_DIGIT.search(text):
        return "a digit"
    if _PATRONYMIC_IN_TEXT.search(lowered):
        return "patronymic"
    for word in _WORD.findall(lowered):
        if len(word) >= 4 and word in _FILLER_STOP_FORMS:
            return f"attested PII word {word!r}"
    if numeral_run(text) >= 2:
        return "a numeral run of two is a spoken house number"
    return ""


def unsafe_outside(text: str, claimed: Iterable[str]) -> str:
    """Why a hand-annotated utterance may not be used, judging only the REMAINDER.

    A hand annotation says what it claims and is silent about the rest, and the
    rest is where the holes are: `rudevices_addresses.json` annotates ADDRESSES,
    so «говорит громова проедьте пожалуйста по наличной дом сорок» carries a
    surname nobody labelled, and «восточная девять … поедем на ленина сто сорок
    шесть» carries a second address where one is claimed.

    Neither can be repaired by claiming the extra value: ground truth is what the
    generator BUILT, and searching a finished string for a value to claim is the
    derivation that cost v2 162 of 183 sloppy failures. So the row is REFUSED
    instead — 7 of 168 annotated rows, which is what a partial annotation costs
    when you decline to complete it by guessing.
    """
    remainder = text
    for span in claimed:
        remainder = remainder.replace(span, " ")
    return unsafe_filler(remainder)


def unsafe_person(text: str) -> str:
    """The person half of the screen alone, for a line chosen to carry a trap.

    A trap line is a real utterance picked BECAUSE it holds something
    address-shaped that is not an address — «шестой подъезд», «улице» about the
    weather — and the full screen would reject every one of them. It may still
    never name a person: «говорит громова проедьте пожалуйста по наличной дом
    сорок» is a trap line, and «громова» in it is a real surname no span claims.
    """
    lowered = text.lower()
    if _PATRONYMIC_IN_TEXT.search(lowered):
        return "patronymic"
    for word in _WORD.findall(lowered):
        if len(word) >= 4 and word in _FILLER_NAME_FORMS:
            return f"attested name word {word!r}"
    return ""


_PATRONYMIC_TAILS: tuple[str, ...] = (
    "ович", "евич", "ьич", "овна", "евна", "ична", "инична",
    "ыч", "ича", "ичем", "овну", "евну",
)


# --- dataclasses ----------------------------------------------------------

@dataclass(frozen=True)
class Source:
    """Where a message's text lives when the corpus may not carry it.

    OpenSTT `asr_calls_2_val` is CC BY-NC 4.0: measuring with it is allowed,
    shipping it is not. SOVA RuDevices is CC BY 4.0 and its text ships. So a
    message names its source either way, and `licence` decides whether `content`
    may be filled in the committed file.

    `sha256` is not bookkeeping. A re-downloaded corpus whose lines shifted by
    one would silently move every offset in the case, and the benchmark would go
    on printing numbers. `hydrate()` compares the digest and refuses.
    """

    corpus: str      # "speech_calls" | "speech_rudevices"
    key: str         # blake2b-6 utterance key, as used by the annotation files
    line: int        # 1-based line in that corpus, for a human to go and look
    sha256: str      # digest of the expected text, utf-8
    licence: str     # one of LICENCES


@dataclass(frozen=True)
class Provenance:
    """Where the case's FORM came from, and how it was selected.

    `shape` names an entry in `mined/calls_grammar.json` or
    `mined/dispatch_grammar.json`. It is required for `recombined`: without it
    "the form came from real speech" is an assertion nobody can check, which is
    the state v2 was in for 1070 of its 1334 cases.

    `weight` is the inverse sampling fraction. RuDevices' number layer is 250
    read out of 4805, so weight 19.22; a census layer is 1.0. A share computed
    over mixed strata without it is wrong by a factor of nineteen, and wrong in
    our favour — the marker stratum is the one the detector is good at.
    """

    kind: str            # one of PROVENANCES
    corpus: str          # "speech_calls" | "speech_rudevices" | "authored"
    key: str             # utterance key the form came from, "" when authored
    shape: str           # mined shape id, "" when authored
    selection: str       # one of SELECTIONS
    weight: float        # inverse sampling fraction; 1.0 for a census
    licence: str         # one of LICENCES


@dataclass(frozen=True)
class Message:
    """One wire message.

    `content` is the SERIALISED string, always. A tool result carrying JSON is
    stored already serialised, because that is exactly what the gateway sees —
    `content` in the envelope is a string and masking runs over it as flat text.
    Storing an object and serialising at score time would let the scorer's
    separator choices move every offset in the family.

    There are no assistant messages CARRYING TOOL CALLS in a case. The corpus
    scripts history, never the behaviour under test: a `tool` message holds the
    scripted result, offline scoring masks it like any other text, and the live
    harness serves that same string when the model calls the tool. If the model
    never calls it, that is `call_absent` — a model outcome, and the detect axis
    is scored offline regardless.
    """

    role: str                 # one of ROLES
    content: str              # "" when carried by reference; see `hydrate`
    source: Source | None
    name: str                 # tool name for role == "tool", else ""


ROLES: tuple[str, ...] = ("system", "user", "assistant", "tool")


@dataclass(frozen=True)
class PiiItem:
    """One personal datum: where it sits, and where it must arrive.

    `tool_param` is what separates this from a NER corpus. A labelled span says
    «this is a phone». This says «this phone is the argument the agent passes to
    `create_order.phone`, and the value that arrives there must be the real one».

    `value` is the surface form AS SAID. `canonical` is what a CRM would store.
    For a spoken value they differ completely — «сорок один ноль девять» against
    «+74109...» — and the round trip is judged against whichever string the
    expected call names, so the case says which one it wants instead of a scorer
    guessing. Ground truth is derived from what the generator BUILT: `value` is
    written by the generator that placed it, never by searching the finished
    string. The v2 predecessor of this field was matched by substring and every
    part a register had touched vanished from the ground truth — 162 of 183
    sloppy failures were that bug, twice.

    `value_source` is separate from `Provenance.kind` on purpose: a dictated
    phone is a TEMPLATE VALUE inside a RECOMBINED FORM, and one field cannot say
    that.
    """

    id: str              # case-local, stable, referenced by calls and links
    type: str            # one of TYPES
    value: str           # the surface form as written or said
    canonical: str       # what a CRM would store
    start: int
    end: int
    msg: int             # indexes Case.messages — every message, not user turns
    identity: str        # who it belongs to; one identity is one substitute
    duty: str            # one of DUTIES
    value_source: str    # one of VALUE_SOURCES
    spoken: bool         # the value is said in words, so it carries no digits
    tool_param: str      # "" = present, but no tool consumes it


@dataclass(frozen=True)
class Negative:
    """Something PII-shaped that is not personal data, with its span.

    Scored as hard as recall: a gateway that masks the cabinet number the caller
    just gave has broken the conversation as surely as one that leaks.

    `start`/`end` are explicit and not found by `text.find(value)`. The same
    discipline the gold spans are under, for the same reason — a searched offset
    is derived from the finished string, and the finished string is what the
    register transform already rewrote.
    """

    value: str
    start: int
    end: int
    msg: int
    family: str   # one of NEGATIVE_FAMILIES
    why: str


@dataclass(frozen=True)
class LinkExpectation:
    """Whether two mentions must reach the model as ONE value.

    `case` names the OTHER case when the pair spans a `preceded_by` chain, which
    is how `scope` states its negative claim: the same partial mention in a
    different conversation, where linking would hand one customer's address to
    another customer's dialogue.
    """

    left: str
    right: str
    kind: str     # one of LINKS
    case: str     # "" = both items are in this case
    why: str


@dataclass(frozen=True)
class ExpectedCall:
    """One call a correct agent makes, with the REAL values in it.

    MATCHED UNORDERED. Every published benchmark that examined this arrived at
    the same place: tau2-bench's ActionEvaluator searches the whole trajectory
    per expected action, BFCL's response checker is an unordered multiset with
    the comment «we don't need to enforce the order», and BFCL's own
    `method_invoke_order_checker` is committed COMMENTED OUT. Order is a property
    of the model, and the owner ruled model behaviour out of scope. v2 required
    an ordered subsequence and that was a source of false failures.

    `judged_args` is tau2-bench's `compare_args`, which exists there and is used
    37 times in 13 907 actions — for us it is the central case. It names the
    arguments that carry personal data; everything else in the call
    (`limit=10`, a page size, an idempotency key) is not this product's business
    and comparing it would fail a gateway for a model's choice.

    `after_msg` is diagnostic only. It says from which message the case's own
    instruction makes the call possible, which is what the transcript builder
    needs; it is never a veto, because a veto on position is order-checking
    wearing another name.
    """

    name: str
    arguments: dict[str, str]
    judged_args: tuple[str, ...]
    pii_items: tuple[str, ...]   # item ids whose real value must arrive
    after_msg: int


@dataclass(frozen=True)
class FinalAnswer:
    """What the reply to the customer must and must not carry.

    THE SUBSTITUTE CHECK IS NOT HERE and takes no ground truth: on every live
    case, any minted substitute surviving into the final reply is
    `substitute_shown`, and any raw token is `token_shown`. Both are gateway
    defects and the vault knows both strings exactly. That is the advantage this
    benchmark has over every LLM-judged one — ToolBench's judge cannot know
    which string was real, and we do.

    `must_not_contain` is the axis nobody has: over WebArena's 812 official
    cases `must_include` appears 639 times and `must_not` exactly zero. It holds
    REAL values whose appearance is a disclosure — another customer's row that
    came back from the CRM in a `result` or `crowd` case.

    `answer` is a CLOSED answer or empty. Never free text: WebArena's
    `must_include` accepts a reply containing the reference plus anything else,
    and a yes/no question has two answers, so the scorer parses to one of them
    or records `answer_absent`.
    """

    must_contain: tuple[str, ...]
    must_not_contain: tuple[str, ...]
    answer: str            # "да" | "нет" | ""


CLOSED_ANSWERS: frozenset[str] = frozenset({"да", "нет", ""})


@dataclass(frozen=True)
class Case:
    """One benchmark case. Every field is required — there are no defaults.

    A default would make «this case declares no negatives» and «the author
    forgot the negatives» the same JSON, and the negatives are half the precision
    measurement. Verbose construction is the price and it is the cheaper half of
    the trade.
    """

    id: str
    family: str            # one of FAMILIES
    register: str          # one of REGISTERS
    context: str           # one of CONTEXT_RUNGS
    provenance: Provenance
    # Cases derived from ONE real utterance or ONE template instance share a
    # cluster. Error bars are computed over clusters, never over cases: one
    # address said by seven callers is one value and seven occurrences, and an
    # interval over occurrences is narrower than the truth, in our favour.
    cluster: str
    # "" means the harness must DERIVE the conversation identity from the
    # transcript, which is a different code path from being handed one and is
    # what a customer gateway with no conversation field actually triggers. Both
    # forms must occur in the corpus; `validate_corpus` refuses one that has only
    # one of them.
    conversation_id: str
    messages: tuple[Message, ...]
    tools: tuple[ToolSchema, ...]
    pii: tuple[PiiItem, ...]
    negatives: tuple[Negative, ...]
    links: tuple[LinkExpectation, ...]
    calls: tuple[ExpectedCall, ...]
    final: FinalAnswer
    # An id the scorer must have run FIRST, sharing one tenant vault with this
    # case. `scope` is a pair of conversations and there is no honest way to say
    # «these two must NOT be linked» inside one case.
    preceded_by: str
    annotators: int        # 0 = generated
    adjudicated: bool
    note: str              # one line: why this case exists at all

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MaskedSpan:
    """What a gateway did, in the form the scorer compares against.

    An adapter turns whatever the gateway under test reports into these. Keeping
    the observation typed here is what lets `span_verdict` state the recall and
    the coverage rule once, for every gateway, instead of once per scorer.
    """

    msg: int
    start: int
    end: int
    type: str


@dataclass(frozen=True)
class Ladder:
    """The frozen tiers. Data, never a sampler.

    `tiers` maps a tier name to its FROZEN ID LIST. Nested and stratified, and
    `check_ladder` enforces both — v2's ladder was a prefix of one order, so a
    dimension only closed at `large` and the owner's requirement that every rung
    close every measurement was met by exactly one rung.

    `corpus_sha256` is checked before the ladder is used. On a mismatch the
    runner REFUSES and names the ids that vanished; re-sampling instead would
    produce a set answering a different question under last month's label.
    """

    version: int
    seed: int
    corpus_sha256: str
    tiers: dict[str, tuple[str, ...]]


# --- accessors ------------------------------------------------------------

def message_text(case: Case, index: int) -> str:
    """The text of one message. Offsets index THIS string."""
    message = case.messages[index]
    if message.source is not None and not message.content:
        raise InvalidCase(
            f"{case.id}: message {index} is carried by reference and has not "
            f"been hydrated; call `hydrate` before scoring or validating")
    return message.content


def case_characters(case: Case) -> int:
    """Total characters across all messages."""
    return sum(len(message_text(case, i)) for i in range(len(case.messages)))


def judged_axes(case: Case) -> tuple[str, ...]:
    """Which zones judge this case, DERIVED from what it contains.

    tau2-bench lets a task declare a zone whose criteria are null — 72 of its 114
    retail tasks do — and the evaluator returns 1.0 for the empty zone with a
    note. A declared list and a content list are two things that have to stay
    equal; deriving one from the other removes the second thing.
    """
    axes = ["detect"]
    if case.calls:
        axes.append("roundtrip")
    if case.final.must_contain or case.final.must_not_contain or case.final.answer:
        axes.append("answer")
    return tuple(axes)


def hydrate(case: Case, resolve: Callable[[str, str], str]) -> Case:
    """Fill in text the corpus is not licensed to carry.

    `resolve(corpus, key)` returns the utterance; the digest is checked against
    `Source.sha256` and a mismatch RAISES. A benchmark that keeps scoring after
    its source shifted underneath it is worse than one that stops, because the
    numbers still look like numbers.
    """
    messages: list[Message] = []
    for index, message in enumerate(case.messages):
        if message.source is None or message.content:
            messages.append(message)
            continue
        text = resolve(message.source.corpus, message.source.key)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest != message.source.sha256:
            raise InvalidCase(
                f"{case.id}: message {index}, {message.source.corpus} key "
                f"{message.source.key} hashes to {digest[:12]}, the corpus "
                f"expects {message.source.sha256[:12]} — the source shifted and "
                f"every offset in this case is now wrong")
        messages.append(Message(role=message.role, content=text,
                                source=message.source, name=message.name))
    return Case(**{**vars(case), "messages": tuple(messages)})


# --- the comparison rules, stated here so a scorer cannot invent its own ---

def digits_of(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def is_numeral_word(word: str) -> bool:
    """Whether one token is a written-out number.

    TWO TESTS, AND THE SECOND ONE IS NOT REDUNDANT. `NUMERAL_WORDS` is an exact
    list and the families depend on membership in it — a contraction table
    asserts at import that every target is in it, which a regex cannot answer.
    `probes.is_numeral` is an ANCHORED alternation over stems and endings, and it
    is what `mine_reference.py` measured the reference distribution with.

    They were used on opposite sides of one comparison. The audit printed «v3
    carries a numeral run in X% of replies, live speech in 10.45%» with X counted
    by the word list and 10.45% counted by the regex, so the two columns were
    measured with two different rulers and v3's was the shorter one. That is not
    a rounding difference: the list has «двадцать» and not «двадцати», «тысяча»
    and not «тысячу», so every oblique case broke a run in the middle.

    It is also why the filler guard could not see «хохряки ленина одинадцать».
    The list holds exact forms, the register misspells them, and the misspelling
    made the run measure ZERO. The regex reads «оди|надцать» and does not care.
    An exact list can be extended one typo at a time for ever; a stem rule is the
    shape of instrument this register needs, and the project already had one.
    """
    return word in NUMERAL_WORDS or probes.is_numeral(word)


def numeral_run(text: str) -> int:
    """Longest run of consecutive written-out numbers. The spoken-value probe.

    A written corpus cannot produce this shape at all — in text a digit is a
    digit — so a whole class of defect is structurally invisible to every
    literary set. Measured on 53 324 real utterances: 10.45% carry a run, 1.14%
    carry one of three or more, and a dictated identifier is four to eight.
    """
    best = 0
    current = 0
    for word in _WORD.findall(text.lower()):
        if is_numeral_word(word):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def same_value(produced: str | None, expected: str, kind: str) -> bool:
    """Whether the tool received the right thing.

    `produced is None` means the substitute resolved to NOTHING and it is False,
    explicitly. v1 fell through to `.strip()` on None and raised, which made the
    «token not found» branch — the branch naming the worst outcome — unreachable
    for the life of that corpus.

    TYPE-AWARE, which v2 was not. v2 compared the last ten digits of any value
    with six or more of them, so two СНИЛС differing only in their first two
    digits compared EQUAL. Only a phone may legitimately change its leading
    country code (+7 against 8), so only a phone is compared by its last ten;
    every other numeric identifier is compared on all of its digits.

    NOTHING ELSE IS FORGIVEN. Not whitespace, not a Latin twin, not a prefix,
    not a numeral spelled out. Each gets its own break kind and is printed beside
    the rate: a scorer that normalises a shape away stops seeing the real defect
    wearing it, and «позвоните Игорю» coming back as «Игорю» has the same shape
    as a repair while being a declined name in a customer's CRM.
    """
    if produced is None:
        return False
    if kind not in TYPES:
        raise InvalidCase(f"unknown type {kind!r}; the adapter must map into TYPES")
    if kind in DIGIT_TYPES:
        expected_digits = digits_of(expected)
        produced_digits = digits_of(produced)
        if not expected_digits or not produced_digits:
            # A spoken value carries no digits; fall through to text, where a
            # digit form coming back is `renumbered` rather than silently equal.
            return produced.strip().casefold() == expected.strip().casefold()
        if kind == "PHONE":
            return produced_digits[-10:] == expected_digits[-10:]
        return produced_digits == expected_digits
    return produced.strip().casefold() == expected.strip().casefold()


def classify_break(item: PiiItem, expected: str, restored: str | None,
                   other_values: Sequence[tuple[str, str]]) -> str:
    """Name a broken round trip. One of BREAK_KINDS.

    `residual` and `call_absent` are decided by the CALLER before this runs — the
    first needs the vault (a surviving minted token), the second needs to know
    the call was never made. Neither is a string comparison and pretending
    otherwise here would let a scorer guess at them.

    `other_values` holds (type, canonical) for every OTHER person or place in the
    case and its `preceded_by` chain. A restored value matching one of them is
    the worst outcome the product has: the tool executed, returned 200, and acted
    on a real human being who is not the one the conversation was about.
    """
    if restored is None:
        return "not_resolved"
    if same_value(restored, expected, item.type):
        return "ok"
    for kind, other in other_values:
        if kind == item.type and same_value(restored, other, kind):
            return "other_person"
    expected_has_digits = bool(_ANY_DIGIT.search(expected))
    restored_has_digits = bool(_ANY_DIGIT.search(restored))
    if expected_has_digits != restored_has_digits:
        return "renumbered"
    if restored.replace(" ", "") == expected.replace(" ", ""):
        return "space_repaired"
    if (restored.lower().translate(_LOOKALIKE)
            == expected.lower().translate(_LOOKALIKE)):
        return "lookalike_repaired"
    if expected.startswith(restored) or restored.startswith(expected):
        return "truncated"
    return "inflected"


def _merge(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Union of half-open intervals, so coverage is not claimed across a gap."""
    ordered = sorted(intervals)
    merged: list[tuple[int, int]] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def span_verdict(item: PiiItem, produced: Sequence[MaskedSpan]) -> str:
    """`missed` | `partial` | `covered`. THE TWO NUMBERS THAT NEVER MERGE.

    Recall counts `partial` and `covered` together — the gateway noticed
    somebody. Coverage counts `covered` alone. Their difference is the leaked
    tail: «Кзнецов Дмитрий» detected as «Дмитрий» scores as recall while the
    surname reaches the model in the clear. On AgentPII-RU v1 that difference was
    97.6% against 95.0% — sixty-nine partial leaks hidden by a single number.

    THE TYPE MUST MATCH. A counter that accepts any overlap scores a СНИЛС masked
    as a street as a found СНИЛС, and the gateway that did that would rank above
    one that found nothing while both leaked the same digits.
    """
    same_type = [span for span in produced
                 if span.msg == item.msg and span.type == item.type]
    overlapping = [(span.start, span.end) for span in same_type
                   if span.start < item.end and span.end > item.start]
    if not overlapping:
        return "missed"
    for start, end in _merge(overlapping):
        if start <= item.start and end >= item.end:
            return "covered"
    return "partial"


def false_masks(case: Case, produced: Sequence[MaskedSpan]) -> list[Negative]:
    """Negatives the gateway masked. The precision half, and it is not optional.

    Our own generated sets reported 100% precision while «Счёт 1234 от
    15.05.2025» was being masked — they were not wrong, they contained no
    ordinary business text. In this register the equivalent is «три
    четырнадцатый кабинет», and it occurs 528 times in the call corpus.
    """
    hit: list[Negative] = []
    for negative in case.negatives:
        for span in produced:
            if (span.msg == negative.msg
                    and span.start < negative.end and span.end > negative.start):
                hit.append(negative)
                break
    return hit


# --- substitute shape, a DIAGNOSTIC and never a veto ----------------------

def shape_features(kind: str, value: str) -> frozenset[str]:
    """Coarse structural features of a value, by declared rules only.

    This exists for one measured defect: the substitute for «школьная пятьдесят
    девять» is «Сортавала» — a bare settlement, no house — because the shape
    probe that picks a substitute looks for `\\d` and a spoken house number has
    none. Detection scores it as found, the round trip resolves it, and the only
    place the defect is visible is the SHAPE of the string the model was handed.

    Reported as a diagnostic and never as a veto — tau2-bench's own arrangement,
    where components outside `reward_basis` are computed and printed but do not
    multiply into the reward. The veto version of this check would fail a gateway
    for a substitute that is merely different, and different is allowed.
    """
    if kind not in TYPES:
        raise InvalidCase(f"unknown type {kind!r}")
    words = _WORD.findall(value.lower())
    features: set[str] = set()
    if kind == "LOC":
        if _ANY_DIGIT.search(value) or any(w in NUMERAL_WORDS for w in words):
            features.add("house_number")
        if any(word in STREET_TYPE_WORDS for word in words):
            features.add("street_type")
        if any(word in HOUSE_MARKERS for word in words):
            features.add("marker")
        if words and len(words[-1]) == 1 and words[-1] not in NUMERAL_WORDS:
            features.add("letter_suffix")
        named = [w for w in words
                 if w not in STREET_TYPE_WORDS and w not in HOUSE_MARKERS
                 and w not in NUMERAL_WORDS]
        if named:
            features.add("street_name")
        return frozenset(features)
    if kind == "NAME":
        features.add(f"parts_{min(len(words), 3)}")
        if any(word.endswith(_PATRONYMIC_TAILS) for word in words):
            features.add("patronymic")
        return frozenset(features)
    if kind == "EMAIL":
        if "@" in value:
            features.add("at")
        if "." in value.split("@")[-1]:
            features.add("domain")
        return frozenset(features)
    digits = digits_of(value)
    if digits:
        features.add(f"digits_{len(digits)}")
    else:
        features.add("spoken")
        if any(word in NUMERAL_WORDS for word in words):
            features.add(f"numerals_{numeral_run(value)}")
    return frozenset(features)


def shape_loss(item: PiiItem, substitute: str) -> tuple[str, ...]:
    """Features the real value carried and the substitute does not."""
    return tuple(sorted(shape_features(item.type, item.value)
                        - shape_features(item.type, substitute)))


# --- weighting and clustering ---------------------------------------------

def weighted_rate(observations: Sequence[tuple[bool, float]]) -> float:
    """A rate over strata with different sampling fractions.

    RuDevices' number layer is 250 read out of 4805 and its marker layer is a
    census of 400. Summed unweighted, the marker layer — selected by the very
    words the detector looks at, and where the marker probe recalls 97.2% — gets
    nineteen times the weight it has earned. Every share over mixed strata goes
    through here.
    """
    mass = sum(weight for _, weight in observations)
    if not mass:
        return 0.0
    return sum(weight for hit, weight in observations if hit) / mass


def distinct_values(cases: Sequence[Case]) -> dict[str, int]:
    """Distinct required values per type, printed BESIDE the occurrence count.

    One address said by seven callers is one value and seven occurrences. A
    confidence interval over occurrences is narrower than the truth and narrower
    in our favour, so the two counts are always printed together.
    """
    seen: dict[str, set[str]] = {}
    for case in cases:
        for item in case.pii:
            if item.duty != "required":
                continue
            seen.setdefault(item.type, set()).add(item.canonical.casefold())
    return {kind: len(values) for kind, values in sorted(seen.items())}


def clusters(cases: Sequence[Case]) -> dict[str, list[str]]:
    """Case ids grouped by cluster. Bootstrap resamples THESE, not cases."""
    grouped: dict[str, list[str]] = {}
    for case in cases:
        grouped.setdefault(case.cluster, []).append(case.id)
    return grouped


def reweight(per_register: dict[str, tuple[int, int]],
             weights: dict[str, float]) -> float:
    """A caller-weighted rate from per-register (hit, total) counts.

    No default weights exist in this module. v2 shipped a provisional table that
    nothing had measured and it was read as a fact for a version. A deployment
    that knows its own register mix passes it; everybody else reads the
    per-register breakdown, which is printed unconditionally.
    """
    live = {name: counts for name, counts in per_register.items() if counts[1]}
    mass = sum(weights.get(name, 0.0) for name in live)
    if not mass:
        return 0.0
    return sum(weights.get(name, 0.0) * counts[0] / counts[1]
               for name, counts in live.items()) / mass


def type_denominators(cases: Sequence[Case]) -> dict[str, int]:
    """Required gold items per type, for the suppression rule.

    THE RULE, stated here so it is not a convention a scorer may forget: a
    per-type rate whose denominator is below MIN_TYPE_DENOMINATOR prints as a
    COUNT, never as a percentage.
    """
    counts: dict[str, int] = {}
    for case in cases:
        for item in case.pii:
            if item.duty == "required":
                counts[item.type] = counts.get(item.type, 0) + 1
    return counts


# --- validation -----------------------------------------------------------

def audit_unlabelled(case: Case) -> list[str]:
    """PII-shaped strings that neither the gold nor the negatives claim.

    The outcome-validity gate, made mechanical. tau-bench passes any task whose
    ground truth writes nothing, and our analogue is a case whose filler quietly
    contains a phone number nobody labelled: the gateway masks it, the scorer
    counts a false mask, and the corpus was wrong.

    Shapes only, no recognizers — this must stay true when our detector changes,
    or the independence rule is decoration. The numeral-run scan is here because
    a regex over digits is blind in this register by construction: a dictated
    order number is four to eight numeral words and no digit-shaped pattern will
    ever see it. Threshold four, from the measured run-length histogram — three
    is «сорок один» plus a neighbour and fires on ordinary speech.
    """
    problems: list[str] = []
    claimed: list[tuple[int, int, int]] = [
        (item.msg, item.start, item.end) for item in case.pii]
    claimed += [(neg.msg, neg.start, neg.end) for neg in case.negatives]
    for index in range(len(case.messages)):
        if case.messages[index].role == "system":
            continue
        text = message_text(case, index)
        for pattern in (_SHAPE_PHONE, _SHAPE_EMAIL, _SHAPE_DIGITS):
            for match in pattern.finditer(text):
                if any(msg == index and start < match.end() and end > match.start()
                       for msg, start, end in claimed):
                    continue
                problems.append(
                    f"{case.id}: message {index} holds {match.group()!r}, which "
                    f"is PII-shaped and claimed by neither pii nor negatives")
        # Blank out every claimed character before counting, so a labelled
        # spoken address does not report itself as an unlabelled numeral run.
        characters = list(text)
        for msg, start, end in claimed:
            if msg == index:
                for position in range(max(start, 0), min(end, len(characters))):
                    characters[position] = " "
        if numeral_run("".join(characters)) >= 4:
            problems.append(
                f"{case.id}: message {index} carries a run of four or more "
                f"written-out numbers that nothing claims; in this register that "
                f"is the shape of a dictated identifier")
    return problems


def _register_problems(case: Case) -> list[str]:
    """The register gate. Every threshold is a measured number.

    Applied to `user` messages only. A tool result is machine text and carries
    digits whatever the customer's voice did; a system prompt is written by the
    integrator. Judging those by the speech gate would make every `result` case
    unrepresentable.
    """
    problems: list[str] = []
    spoken = [message_text(case, i) for i, m in enumerate(case.messages)
              if m.role == "user"]
    if not spoken:
        return problems
    joined = " ".join(spoken)
    has_digits = bool(_ANY_DIGIT.search(joined))
    has_punct = bool(_SENTENCE_PUNCT.search(joined))
    has_capital = any(text[:1].isupper() for text in spoken)

    if case.register == "voice_raw":
        # Zero of 53 324 measured utterances carry a digit, zero carry sentence
        # punctuation, 0.028% start with a capital. There is no `asr_digits`
        # escape hatch in v3: v2 had one and it existed only to let a generator
        # that had not done the work through.
        if has_digits:
            problems.append(
                f"{case.id}: voice_raw carries a digit in user text; 0 of 53 324 "
                f"measured utterances do, and a spoken number is words")
        if has_punct:
            problems.append(f"{case.id}: voice_raw carries sentence punctuation; "
                            f"the measured share is 0.0")
        if has_capital:
            problems.append(f"{case.id}: voice_raw starts a user message with a "
                            f"capital; the measured share is 0.00028")
    elif case.register == "voice_itn":
        if not has_digits:
            problems.append(
                f"{case.id}: voice_itn is defined by inverse text normalisation "
                f"being ON; with no digit it is a voice_raw case in disguise")
        if has_punct:
            problems.append(f"{case.id}: voice_itn carries sentence punctuation; "
                            f"ITN restores digits, not commas")
    elif case.register in ("chat", "sloppy"):
        # A chat case written like a document is a `clean` case that dodged the
        # cap. The cap is the whole point of the register split, so the dodge has
        # to be closed from the other side too.
        if has_capital and has_punct:
            problems.append(
                f"{case.id}: register {case.register!r} with both capitals and "
                f"sentence punctuation is a `clean` case avoiding the "
                f"{MAX_CLEAN_SHARE:.0%} literary cap")
    elif case.register == "clean":
        # The literary register has a budget of one case in twenty. A `clean`
        # case that is merely lower-case chat spends that budget on nothing.
        if not has_punct or not has_capital:
            problems.append(
                f"{case.id}: register `clean` with no capital or no sentence "
                f"punctuation is a chat case spending the literary budget")
    return problems


def validate(case: Case) -> list[str]:
    """Structural problems that make a case unscoreable.

    Run at BUILD time. A benchmark whose ground truth has drifted from its own
    text keeps producing numbers, and offsets are the part that rots first
    because every register transform rewrites the string.
    """
    problems: list[str] = []
    if case.family not in FAMILIES:
        problems.append(f"{case.id}: unknown family {case.family!r}")
    if case.register not in REGISTERS:
        problems.append(f"{case.id}: unknown register {case.register!r}")
    if case.context not in CONTEXT_RUNGS:
        problems.append(f"{case.id}: unknown context rung {case.context!r}")
        return problems
    if case.provenance.kind not in PROVENANCES:
        problems.append(f"{case.id}: unknown provenance {case.provenance.kind!r}")
    if case.provenance.selection not in SELECTIONS:
        problems.append(f"{case.id}: unknown selection "
                        f"{case.provenance.selection!r}")
    if case.provenance.licence not in LICENCES:
        problems.append(f"{case.id}: unknown licence {case.provenance.licence!r}")
    if case.provenance.weight <= 0:
        problems.append(f"{case.id}: selection weight must be positive; a census "
                        f"is 1.0 and a sample is its inverse fraction")
    if not case.cluster:
        problems.append(f"{case.id}: no cluster; error bars are computed over "
                        f"clusters and an empty one silently becomes its own")
    if case.final.answer not in CLOSED_ANSWERS:
        problems.append(f"{case.id}: expected answer {case.final.answer!r} is not "
                        f"closed; free text invites a substring test and a "
                        f"substring test is the leniency we refuse")
    if not case.note:
        problems.append(f"{case.id}: no note; a case nobody can say the purpose "
                        f"of cannot be repaired when it starts failing")

    for index, message in enumerate(case.messages):
        if message.role not in ROLES:
            problems.append(f"{case.id}: message {index} has unknown role "
                            f"{message.role!r}")
        if message.role == "tool" and not message.name:
            problems.append(f"{case.id}: tool message {index} names no tool; the "
                            f"live harness serves it by name")
        if message.source is not None:
            if message.source.licence not in LICENCES:
                problems.append(f"{case.id}: message {index} names licence "
                                f"{message.source.licence!r}, which is unknown")
            elif (message.source.licence not in SHIPPABLE_LICENCES
                  and message.content):
                problems.append(
                    f"{case.id}: message {index} carries text licensed "
                    f"{message.source.licence} — the corpus may not ship it; "
                    f"leave content empty and hydrate")
    if case.messages and case.messages[-1].role == "assistant":
        problems.append(f"{case.id}: the last message is an assistant turn; the "
                        f"assistant's turn is what the run produces, and a "
                        f"scripted one there would be the answer under test")

    unhydrated = [i for i, m in enumerate(case.messages)
                  if m.source is not None and not m.content]
    if unhydrated:
        problems.append(f"{case.id}: messages {unhydrated} are carried by "
                        f"reference; hydrate before validating")
        return problems

    low, high = CONTEXT_RUNGS[case.context]
    if not low <= len(case.messages) <= high:
        problems.append(f"{case.id}: {len(case.messages)} messages is outside the "
                        f"`{case.context}` band {low}-{high}")
    if case.context == "deep" and case_characters(case) < MIN_DEEP_CHARS:
        problems.append(
            f"{case.id}: `deep` with {case_characters(case)} characters — thirty "
            f"two-word replies are not a long context, and the defect this rung "
            f"exists for cannot appear below a few thousand characters")

    # A case is not allowed to be silently empty. tau-bench's trap: a task whose
    # ground truth demands nothing is passed by an agent that does nothing, and
    # here that is a gateway that masks nothing at all.
    if not any(item.duty == "required" for item in case.pii) and not case.negatives:
        problems.append(f"{case.id}: no required pii and no negatives — a gateway "
                        f"that does nothing passes this case")

    if case.provenance.kind == "recombined" and not case.provenance.shape:
        problems.append(
            f"{case.id}: `recombined` with no mined shape id — «the form came "
            f"from real speech» is then an assertion nobody can check, which is "
            f"the state 1070 of v2's 1334 cases were in")
    if case.provenance.kind == "verbatim":
        if not any(m.source is not None for m in case.messages):
            problems.append(f"{case.id}: `verbatim` with no message naming a "
                            f"source utterance")
        if case.provenance.selection == "authored":
            problems.append(f"{case.id}: `verbatim` cannot be `authored`")
    if case.provenance.kind == "template":
        speech_reachable = {item.type for item in case.pii
                            if item.duty == "required"} - TEMPLATE_VALUE_TYPES
        if speech_reachable:
            problems.append(
                f"{case.id}: `template` carries {sorted(speech_reachable)}, which "
                f"the speech corpora do hold — a template is permitted only where "
                f"mining cannot reach, and NAME and LOC are not that")

    seen_ids: set[str] = set()
    spans_by_msg: dict[int, list[tuple[int, int, str]]] = {}
    by_identity: dict[str, set[str]] = {}
    for item in case.pii:
        if item.id in seen_ids:
            problems.append(f"{case.id}: duplicate item id {item.id!r}")
        seen_ids.add(item.id)
        if item.type not in TYPES:
            problems.append(f"{case.id}: item {item.id} has unknown type "
                            f"{item.type!r}")
        if item.duty not in DUTIES:
            problems.append(f"{case.id}: item {item.id} has unknown duty "
                            f"{item.duty!r}")
        if item.value_source not in VALUE_SOURCES:
            problems.append(f"{case.id}: item {item.id} has unknown value source "
                            f"{item.value_source!r}")
        if item.duty == "optional" and item.tool_param:
            problems.append(
                f"{case.id}: item {item.id} is optional to mask AND claims tool "
                f"param {item.tool_param!r} — a value the round trip demands back "
                f"cannot also be one we do not require masked")
        if item.spoken and _ANY_DIGIT.search(item.value):
            problems.append(f"{case.id}: item {item.id} is marked spoken and "
                            f"carries a digit")
        if not item.spoken and item.type in DIGIT_TYPES and not digits_of(item.value):
            problems.append(f"{case.id}: item {item.id} is a {item.type} with no "
                            f"digit and is not marked spoken")
        if not 0 <= item.msg < len(case.messages):
            problems.append(f"{case.id}: item {item.id} points at message "
                            f"{item.msg}, the case has {len(case.messages)}")
            continue
        if case.messages[item.msg].role == "system":
            problems.append(
                f"{case.id}: item {item.id} sits in a system message; whether a "
                f"system prompt is masked depends on the deployment leg, so the "
                f"corpus does not test it")
        text = message_text(case, item.msg)
        if text[item.start:item.end] != item.value:
            problems.append(
                f"{case.id}: message {item.msg} span {item.start}:{item.end} "
                f"holds {text[item.start:item.end]!r}, ground truth says "
                f"{item.value!r}")
        for start, end, other in spans_by_msg.setdefault(item.msg, []):
            if item.start < end and item.end > start:
                problems.append(f"{case.id}: items {other} and {item.id} overlap "
                                f"in message {item.msg}")
        spans_by_msg[item.msg].append((item.start, item.end, item.id))
        if item.identity:
            by_identity.setdefault(item.identity, set()).add(item.type)

    # One identity, one type. A person's name and their phone are one human and
    # TWO identities here, because they receive two substitutes and the linking
    # axis compares substitutes. v2 did not check this and a corpus bug of that
    # shape reports as a gateway failure.
    for identity, kinds in by_identity.items():
        if len(kinds) > 1:
            problems.append(f"{case.id}: identity {identity!r} spans types "
                            f"{sorted(kinds)}; one identity is one substitute")

    for negative in case.negatives:
        if negative.family not in NEGATIVE_FAMILIES:
            problems.append(f"{case.id}: negative {negative.value!r} has unknown "
                            f"family {negative.family!r}")
        if not 0 <= negative.msg < len(case.messages):
            problems.append(f"{case.id}: negative {negative.value!r} points at "
                            f"message {negative.msg}")
            continue
        text = message_text(case, negative.msg)
        if text[negative.start:negative.end] != negative.value:
            problems.append(
                f"{case.id}: negative span {negative.start}:{negative.end} in "
                f"message {negative.msg} holds "
                f"{text[negative.start:negative.end]!r}, not {negative.value!r}")

    # A malformed tool schema must be a reported problem, not a KeyError out of
    # the validator: the caller asked what is wrong with this case and deserves
    # the whole list, not the first exception.
    by_name: dict[str, ToolSchema] = {}
    for position, tool in enumerate(case.tools):
        try:
            by_name[str(tool["function"]["name"])] = tool
        except (KeyError, TypeError):
            problems.append(f"{case.id}: tool {position} is not an OpenAI "
                            f"function schema: {tool!r}")
    for call in case.calls:
        if call.name not in by_name:
            problems.append(f"{case.id}: expected call {call.name!r} is not among "
                            f"the offered tools")
            continue
        try:
            params = set(by_name[call.name]["function"]["parameters"]["properties"])
        except (KeyError, TypeError):
            problems.append(f"{case.id}: tool {call.name!r} declares no parameter "
                            f"properties, so its arguments cannot be checked")
            continue
        if not call.judged_args:
            problems.append(
                f"{case.id}: call {call.name!r} judges no argument; a call whose "
                f"personal data nobody named is scored on nothing")
        for argument in call.judged_args:
            if argument not in call.arguments:
                problems.append(f"{case.id}: call {call.name!r} judges "
                                f"{argument!r}, which it does not pass")
            if argument not in params:
                problems.append(f"{case.id}: call {call.name!r} judges "
                                f"{argument!r}, absent from the tool schema")
        for item_id in call.pii_items:
            item = next((i for i in case.pii if i.id == item_id), None)
            if item is None:
                problems.append(f"{case.id}: call {call.name!r} consumes unknown "
                                f"item {item_id!r}")
                continue
            if not item.tool_param:
                problems.append(f"{case.id}: call {call.name!r} consumes item "
                                f"{item_id!r}, which claims no tool param")
                continue
            if item.tool_param not in params:
                problems.append(f"{case.id}: item {item_id!r} claims param "
                                f"{item.tool_param!r}, absent from {call.name!r}")
                continue
            if item.tool_param not in call.judged_args:
                problems.append(
                    f"{case.id}: item {item_id!r} carries personal data into "
                    f"{call.name}.{item.tool_param} and that argument is not "
                    f"judged — the round trip would pass without checking it")
                continue
            # The validity gate tau2-bench applies to its user simulator, applied
            # to ourselves: the expected argument must be derivable from what the
            # message actually said. AgentPII-RU learned this expensively — a
            # ground truth that demands a patronymic no message carried scores the
            # gateway on information the conversation never had.
            passed = call.arguments[item.tool_param]
            if passed not in (item.value, item.canonical):
                problems.append(
                    f"{case.id}: call {call.name}.{item.tool_param} expects "
                    f"{passed!r}, which is neither the form said ({item.value!r}) "
                    f"nor the canonical form ({item.canonical!r})")

    for link in case.links:
        if link.kind not in LINKS:
            problems.append(f"{case.id}: link {link.left}/{link.right} has "
                            f"unknown kind {link.kind!r}")
        if link.left not in seen_ids:
            problems.append(f"{case.id}: link names unknown item {link.left!r}")
        if not link.case and link.right not in seen_ids:
            problems.append(f"{case.id}: link names unknown item {link.right!r}")
        if link.case and link.case != case.preceded_by:
            problems.append(
                f"{case.id}: link reaches into {link.case!r}, which is not the "
                f"case this one is preceded by ({case.preceded_by!r}) — only a "
                f"case in the same vault group is in scope")

    known_values = {item.value for item in case.pii}
    known_values |= {item.canonical for item in case.pii}
    for value in case.final.must_contain:
        if value not in known_values:
            problems.append(
                f"{case.id}: the final answer must contain {value!r}, which is no "
                f"item's value — the reply would be judged on a string the "
                f"conversation never carried")
    by_value = {item.value: item for item in case.pii}
    for value in case.final.must_not_contain:
        item = by_value.get(value)
        if item is not None and item.duty != "required":
            problems.append(
                f"{case.id}: the final answer may not disclose {value!r} while "
                f"the same value is only `optional` to mask — forbidding a "
                f"disclosure we did not require prevented is a contradiction")
    if case.family == "scope" and not case.preceded_by:
        problems.append(f"{case.id}: a `scope` case is half of a pair and needs "
                        f"`preceded_by`")

    problems.extend(_register_problems(case))
    problems.extend(audit_unlabelled(case))
    return problems


def validate_corpus(cases: Sequence[Case]) -> list[str]:
    """Claims no single case can carry. Each one is a decision or a past defect."""
    problems: list[str] = []
    positions = {case.id: index for index, case in enumerate(cases)}
    if len(positions) != len(cases):
        problems.append("duplicate case ids in the corpus")
    total = len(cases)
    if not total:
        return ["the corpus is empty"]

    low, high = CORPUS_SIZE_BAND
    if not low <= total <= high:
        problems.append(f"{total} cases is outside the agreed band {low}-{high}")

    for index, case in enumerate(cases):
        if not case.preceded_by:
            continue
        if case.preceded_by not in positions:
            problems.append(f"{case.id}: preceded_by names a case that does not "
                            f"exist ({case.preceded_by!r})")
        elif positions[case.preceded_by] >= index:
            problems.append(
                f"{case.id}: preceded_by {case.preceded_by!r} comes later in the "
                f"file; a vault group is scored in file order and a forward "
                f"reference would be scored against an empty vault")

    missing_families = [name for name in FAMILIES
                        if not any(c.family == name for c in cases)]
    if missing_families:
        problems.append(f"families with no cases: {missing_families} — a tier "
                        f"drawn from this corpus cannot close on family")
    if {case.register for case in cases} != set(REGISTERS):
        problems.append(f"registers present: "
                        f"{sorted({c.register for c in cases})}; all five are "
                        f"needed or a rung cannot close on register")
    if {case.context for case in cases} != set(CONTEXT_RUNGS):
        problems.append(f"context rungs present: "
                        f"{sorted({c.context for c in cases})}; all four are "
                        f"needed, and `deep` is the one v2 had none of")

    # THE OWNER'S THREE SHARES, enforced rather than described. v2 described a
    # register mix in its design document and shipped the opposite.
    clean = sum(1 for case in cases if case.register == "clean") / total
    if clean > MAX_CLEAN_SHARE:
        problems.append(
            f"the literary register is {clean:.1%} of the corpus, over the "
            f"{MAX_CLEAN_SHARE:.0%} cap — v2 spent 16% of its mass on a register "
            f"that does not occur in 53 324 measured utterances")
    speech = sum(1 for case in cases if case.register in SPEECH_REGISTERS) / total
    if speech < MIN_SPEECH_SHARE:
        problems.append(f"the speech registers are {speech:.1%} of the corpus, "
                        f"under the {MIN_SPEECH_SHARE:.0%} floor; speech is the "
                        f"base of this benchmark, not one of its corners")
    real_form = sum(1 for case in cases
                    if case.provenance.kind in ("verbatim", "recombined")) / total
    if real_form < MIN_REAL_FORM_SHARE:
        problems.append(
            f"only {real_form:.1%} of cases carry a form taken from a real "
            f"transcript, under the {MIN_REAL_FORM_SHARE:.0%} floor; v2 was at "
            f"20% and the other 80% were counter-variants of a few templates")

    # THE SELECTION-BIAS RULE, and it is the most expensive lesson in the file.
    # A type reachable only through the marker stratum has been measured on the
    # utterances chosen by the words the detector reads. That set reported 100%
    # where the truth was 38.6%.
    by_type_selection: dict[str, set[str]] = {}
    for case in cases:
        if case.provenance.kind == "template":
            continue
        for item in case.pii:
            if item.duty == "required":
                by_type_selection.setdefault(item.type, set()).add(
                    case.provenance.selection)
    for kind, selections in sorted(by_type_selection.items()):
        if selections == {"marker"}:
            problems.append(
                f"every speech-derived {kind} comes from the `marker` stratum, "
                f"which is selected by the same surface cues the detector reads; "
                f"the set can only show what we already find")

    # A NEGATIVE-ONLY CASE IS PASSED BY A GATEWAY THAT DOES NOTHING, and the
    # per-case gate cannot say so — «do not mask this» is a real demand and a
    # null gateway satisfies it. They are still among the most valuable cases in
    # the corpus (528 real utterances put a number beside «кабинет» and no
    # generator would have written them), so the rule is a bound, not a ban.
    negative_only = [case for case in cases
                     if not any(item.duty == "required" for item in case.pii)]
    if len(negative_only) > total * MAX_NEGATIVE_ONLY_SHARE:
        problems.append(
            f"{len(negative_only)} of {total} cases demand only that nothing be "
            f"masked; a gateway that does nothing passes all of them, so they may "
            f"not exceed {MAX_NEGATIVE_ONLY_SHARE:.0%} of the corpus")

    given = any(case.conversation_id for case in cases)
    derived = any(not case.conversation_id for case in cases)
    if not (given and derived):
        problems.append("the corpus must hold cases with an explicit "
                        "conversation_id AND cases with none, or one of the two "
                        "scope paths is never exercised")
    if not any(link.kind == "different" for case in cases for link in case.links):
        problems.append("no `different` link expectation: without one the corpus "
                        "only ever asks whether the gateway links, never whether "
                        "it refuses to")
    if not any(item.spoken for case in cases for item in case.pii):
        problems.append("no spoken value anywhere: the two defects this version "
                        "exists for both live in numbers said as words")
    if not any(case.final.must_not_contain for case in cases):
        problems.append("nothing is forbidden from any final answer; the third "
                        "axis would then only ever check that a substitute did "
                        "not survive, and never that data stayed undisclosed")

    thin = {kind: count for kind, count in type_denominators(cases).items()
            if count < MIN_TYPE_DENOMINATOR}
    if thin:
        problems.append(f"types with fewer than {MIN_TYPE_DENOMINATOR} required "
                        f"items: {thin}; their rates can only be printed as "
                        f"counts, so the corpus should carry more or drop them")
    return problems


def require_valid(case: Case) -> Case:
    """Refuse an invalid case. The build path calls this, never `validate` alone."""
    problems = validate(case)
    if problems:
        raise InvalidCase("\n".join(problems))
    return case


def require_valid_corpus(cases: Sequence[Case]) -> Sequence[Case]:
    """Refuse an invalid corpus, per case and then as a whole."""
    problems: list[str] = []
    for case in cases:
        problems.extend(validate(case))
    problems.extend(validate_corpus(cases))
    if problems:
        raise InvalidCorpus("\n".join(problems))
    return cases


# --- the ladder -----------------------------------------------------------

def coverage(case: Case) -> frozenset[tuple[str, str]]:
    """The (dimension, value) pairs one case closes."""
    pairs: set[tuple[str, str]] = {
        ("family", case.family),
        ("register", case.register),
        ("context", case.context),
        ("provenance", case.provenance.kind),
        ("selection", case.provenance.selection),
    }
    for axis in judged_axes(case):
        pairs.add(("axis", axis))
    for item in case.pii:
        pairs.add(("type", item.type))
        pairs.add(("duty", item.duty))
        if item.spoken:
            pairs.add(("spoken", "yes"))
    for negative in case.negatives:
        pairs.add(("negative", negative.family))
    return frozenset(pairs)


def check_ladder(cases: Sequence[Case], ladder: Ladder) -> list[str]:
    """Nesting and closure. THE REQUIREMENT THAT V2 MET AT ONE RUNG OUT OF FIVE.

    v2's tiers were `order[:n]` of one frozen sequence, so a rung closed a
    dimension only if the sequence happened to put one of each near the front —
    and only `large` did. The owner's rule is that EVERY rung closes EVERY
    measurement, which a prefix cannot promise and a stratified frozen set can.

    Closure here is MARGINAL, and saying so is part of the honesty: thirty cases
    cannot cross ten families with five registers, and a rung that claimed to
    would be lying about what it can decide. Every value of every dimension is
    EXERCISED at nano; nothing is DECIDED there, which is why
    MIN_TYPE_DENOMINATOR and TIER_ZERO_FAILURE_BOUND are printed beside it.
    """
    problems: list[str] = []
    by_id = {case.id: case for case in cases}
    universe: set[tuple[str, str]] = set()
    for case in cases:
        universe |= coverage(case)
    # `selection` and `negative` families are properties of the SOURCE, not
    # measurements, and demanding every one of them at nano would spend the whole
    # rung on provenance bookkeeping.
    required = {pair for pair in universe
                if pair[0] in ("family", "register", "context", "provenance",
                               "axis", "type", "duty", "spoken")}

    names = [name for name in TIER_SIZES if name in ladder.tiers]
    previous: tuple[str, ...] = ()
    for name in names:
        ids = ladder.tiers[name]
        expected = TIER_SIZES[name] or len(cases)
        unknown = [case_id for case_id in ids if case_id not in by_id]
        if unknown:
            problems.append(f"tier {name}: {len(unknown)} ids are not in the "
                            f"corpus: {unknown[:8]}")
            continue
        if len(set(ids)) != len(ids):
            problems.append(f"tier {name}: repeated ids")
        if len(ids) != expected:
            problems.append(f"tier {name}: {len(ids)} cases, expected {expected}")
        if previous and not set(previous) <= set(ids):
            problems.append(
                f"tier {name} does not contain tier before it; unnested rungs "
                f"answer different questions and their difference means nothing")
        covered: set[tuple[str, str]] = set()
        for case_id in ids:
            covered |= coverage(by_id[case_id])
        missing = sorted(required - covered)
        if missing:
            problems.append(f"tier {name} does not close: {missing}")
        previous = ids
    for name in TIER_SIZES:
        if name not in ladder.tiers:
            problems.append(f"ladder has no tier {name!r}")
    return problems


def corpus_digest(cases: Sequence[Case]) -> str:
    """The digest a `Ladder` is pinned to. Order- AND claim-sensitive.

    Claims, because an earlier version hashed ids alone until a re-labelling of
    the dispatch source showed what that costs: the ground truth moved, every id
    stayed, and the pin stayed green. A shifted offset, a corrected span and a
    changed expected call are each a different measurement wearing the same name.

    MESSAGE TEXT IS DELIBERATELY NOT HASHED. Licensed utterances are carried by
    reference until `hydrate` fills them in, so hashing content would make the
    digest depend on whether the caller hydrated first, and `tier()` would refuse
    a legitimately hydrated corpus. The claims are hydration-invariant and they
    are what a ladder is actually pinning; the TEXT is pinned by `Source.sha256`,
    one message at a time, which is stricter.
    """
    digest = hashlib.sha256()
    for case in cases:
        digest.update(case.id.encode("utf-8"))
        digest.update(b"\x00")
        claims = (
            case.family, case.register, case.context, case.cluster,
            case.provenance.kind, case.provenance.shape,
            case.provenance.selection, case.provenance.weight,
            [(i.id, i.type, i.value, i.canonical, i.start, i.end, i.msg,
              i.identity, i.duty, i.value_source, i.spoken, i.tool_param)
             for i in case.pii],
            [(n.value, n.start, n.end, n.msg, n.family) for n in case.negatives],
            [(c.name, sorted(c.arguments.items()), list(c.judged_args),
              list(c.pii_items)) for c in case.calls],
            [(l.left, l.right, l.kind, l.case) for l in case.links],
            (list(case.final.must_contain), list(case.final.must_not_contain),
             case.final.answer),
        )
        digest.update(json.dumps(claims, ensure_ascii=False, sort_keys=True,
                                 default=str).encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


def tier(cases: Sequence[Case], ladder: Ladder, name: str) -> list[Case]:
    """The frozen set for a tier. Reads the ladder, never samples."""
    if name not in TIER_SIZES:
        raise InvalidCorpus(f"unknown tier {name!r}")
    if name not in ladder.tiers:
        raise InvalidCorpus(f"ladder v{ladder.version} has no tier {name!r}")
    actual = corpus_digest(cases)
    if actual != ladder.corpus_sha256:
        known = {case.id for case in cases}
        gone = [case_id for case_id in ladder.tiers[name] if case_id not in known]
        raise InvalidCorpus(
            f"ladder v{ladder.version} was frozen against corpus "
            f"{ladder.corpus_sha256[:12]}, this corpus is {actual[:12]}; "
            f"{len(gone)} ids in tier {name} no longer exist: {gone[:8]}. "
            f"Regenerate the ladder deliberately and bump its version — do not "
            f"re-sample, because a re-sampled nano is a different measurement "
            f"wearing last month's name.")
    by_id = {case.id: case for case in cases}
    return [by_id[case_id] for case_id in ladder.tiers[name]]


# --- json round trip ------------------------------------------------------
#
# `to_json` is `asdict`; the way back has to be written out, because json gives
# lists where the dataclasses hold tuples and a list field in a frozen dataclass
# is a mutable default waiting to be shared between two cases.

def _tuple_of_str(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, (list, tuple)):
        raise InvalidCase(f"expected a list of strings, got {type(raw).__name__}")
    return tuple(str(value) for value in raw)


def case_from_json(raw: dict[str, object]) -> Case:
    """Rebuild a case from its serialised form, refusing anything unexpected.

    Every failure comes back as `InvalidCase`. A `KeyError` escaping from here
    would be a corpus file the loader could not name a reason for, and «which
    field is missing from which case» is the only useful thing to say about it.
    """
    try:
        return _case_from_json(raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidCase(
            f"case {raw.get('id', '<no id>')!r} cannot be read: {exc}") from exc


def _case_from_json(raw: dict[str, object]) -> Case:
    provenance = Provenance(**raw["provenance"])           # type: ignore[arg-type]
    messages = tuple(
        Message(role=str(m["role"]), content=str(m["content"]),
                source=Source(**m["source"]) if m.get("source") else None,
                name=str(m.get("name", "")))
        for m in raw["messages"])                          # type: ignore[union-attr]
    final_raw = raw["final"]
    final = FinalAnswer(
        must_contain=_tuple_of_str(final_raw["must_contain"]),      # type: ignore[index]
        must_not_contain=_tuple_of_str(final_raw["must_not_contain"]),  # type: ignore[index]
        answer=str(final_raw["answer"]))                            # type: ignore[index]
    return Case(
        id=str(raw["id"]),
        family=str(raw["family"]),
        register=str(raw["register"]),
        context=str(raw["context"]),
        provenance=provenance,
        cluster=str(raw["cluster"]),
        conversation_id=str(raw["conversation_id"]),
        messages=messages,
        tools=tuple(raw["tools"]),                          # type: ignore[arg-type]
        pii=tuple(PiiItem(**item) for item in raw["pii"]),  # type: ignore[union-attr]
        negatives=tuple(Negative(**n) for n in raw["negatives"]),  # type: ignore[union-attr]
        links=tuple(LinkExpectation(**l) for l in raw["links"]),   # type: ignore[union-attr]
        calls=tuple(
            ExpectedCall(name=str(c["name"]),
                         arguments={str(k): str(v) for k, v in c["arguments"].items()},
                         judged_args=_tuple_of_str(c["judged_args"]),
                         pii_items=_tuple_of_str(c["pii_items"]),
                         after_msg=int(c["after_msg"]))
            for c in raw["calls"]),                         # type: ignore[union-attr]
        final=final,
        preceded_by=str(raw["preceded_by"]),
        annotators=int(raw["annotators"]),                  # type: ignore[arg-type]
        adjudicated=bool(raw["adjudicated"]),
        note=str(raw["note"]),
    )
