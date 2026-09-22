"""Three can-fail fixtures per metric, hand-built, never produced by an agent.

THE RULE THIS FILE EXISTS FOR (spec §4.4, `e2e/audit_gates.py`): an instrument
that cannot fail is not an instrument. Every metric ships one input on which it
MUST print 0/n, one on which it MUST print n/n, and one built to fool it. A
metric that does not SEPARATE its own zero from its own one is not printed at
all, and a report holding a refused non-diagnostic metric carries «НЕПОЛНЫЙ»
in its header (`report.gate_all`).

THE ADVERSARIAL FIXTURE IS THE ONE THAT MATTERS, AND ITS DOCSTRING SAYS WHAT A
WRONG METRIC WOULD PRINT. Four of v4's defects were found by reading the code
and every one of them worked in the gateway's favour: a triple with nothing to
compare passed five levels, `FieldSpec.required` was read by no scorer, no
level asked whether the arm acted at all, and over-masking was declared and
never called. Each of those would have been caught by an adversarial fixture
asking «what does this print when the answer is obvious and the code is
wrong?».

NOTHING HERE RUNS AN AGENT, THE ENGINE OR THE NETWORK. A fixture built by
running the thing under test agrees with it by construction; these are records
written by hand, and the verdicts are computed by the real `form_match`, so a
fixture is a statement about the METRIC and never about the comparator.

Run the test: cd prototype && source .venv/bin/activate
                && python3 -m bench.agentpii5.test_fixtures
"""
from dataclasses import replace

from bench.agentpii3.schema import Negative
from bench.agentpii4.compare import ArmRun, ObservedCall
from bench.agentpii4.parts import parts_of
from bench.agentpii4.schema import (
    Case,
    Expectation,
    Locus,
    Message,
    PiiItem,
    Provenance,
    SeedRecord,
)
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import (
    ArmRunV5,
    CaseV5,
    DocumentSpec,
    Fixture,
    ForcedError,
    Hop,
    HopObservation,
    MemorySpec,
    MentionRecord,
    RagSpec,
    ReturnExpectation,
    RunObservation,
    ToolResultRecord,
)
from bench.agentpii5.form import form_match

# One person, one substitute, one other person. Written out here so every
# fixture reads as a sentence and a reader can check the expected fraction
# against the values instead of against a builder's defaults.
REAL_NAME = "Иванова Елена"
FAKE_NAME = "Пахомова Ольга"
OTHER_NAME = "Смирнова Анна"
REAL_PHONE = "+79164021187"
AGENT_PHONE = "8 916 402-11-87"
# A MASCULINE pair for the form fixtures, and the reason is pymorphy3, not
# taste: «Кузнецова» is both the nominative of a woman and the genitive of a
# man, the analyser votes `gent` for both spellings, and a «grammatical case
# failure» built on it is no failure at all. «Орлов»/«Орлову» is unambiguous,
# so the zero fixture really is red.
FAKE_MALE = "Орлов Иван"
DECLINED_MALE = "Орлову Ивану"
# The SAME substitute as `FAKE_NAME`, in the dative — what a model writes into
# a free-text note. `multi_consistency` must read the two as one mint.
DECLINED_FAKE = "Пахомовой Ольге"


# --- builders --------------------------------------------------------------------------

def _message(text: str) -> Message:
    return Message(role="user", content=text, source=None, name="")


def _item(item_id: str, pii_type: str, value: str, canonical: str, identity: str,
          where: Locus) -> PiiItem:
    """A corpus item carries the PARTS it was built from, and so does a fixture
    one: every value metric now asks a role'd leaf for `item.parts[role]`
    (`metrics.leaf_value_ok`), and an item with `parts={}` would make every
    such leaf an unsatisfiable hop — the fixtures would pin the corpus defect
    instead of the metric. Split from the canonical with the ONE splitter the
    comparator uses, so a fixture cannot disagree with the corpus about what
    the surname of a name is."""
    return PiiItem(id=item_id, type=pii_type, identity=identity, value=value,
                   canonical=canonical, parts=parts_of(pii_type, canonical), where=where,
                   duty="required", spoken=False, stale=False)


def _in_message(msg: int, start: int, end: int) -> Locus:
    return Locus(kind="message", msg=msg, start=start, end=end, record="", path="")


def _in_seed(record: str, path: str) -> Locus:
    return Locus(kind="seed", msg=-1, start=-1, end=-1, record=record, path=path)


def _case(case_id: str, behaviour: str, texts: tuple[str, ...], items: tuple[PiiItem, ...],
          hops: tuple[Hop, ...]) -> CaseV5:
    """The smallest v5 case a metric can read: messages, items, declared hops.
    Everything a particular fixture needs beyond that (negatives, a `RagSpec`, a
    `MemorySpec`) is added with `dataclasses.replace`, so the common shape is
    written once and a fixture's extra declaration is visible on its own line."""
    base = Case(
        id=case_id, kind="chain", register="chat",
        provenance=Provenance(kind="authored", corpus="authored", key="", shape="",
                              selection="census", weight=1.0, licence="authored"),
        cluster=f"NAME:{REAL_NAME.casefold()}", conversation_id=case_id, now="2026-09-01",
        messages=tuple(_message(text) for text in texts), tools=(),
        seed_records=(SeedRecord(id="s1", table="contacts", fields={}, pii_ids=()),),
        pii=items, plain=(), negatives=(),
        expects=Expectation(reachable_tools=(), primary_identity="i1", must_contain=(),
                            must_not_contain=(), validate_types=()),
        trace=(), note="фикстура метрики")
    return CaseV5(base=base, behaviour=behaviour, hops=hops, returns=(), forced=(), memory=(),
                  pick=None, branch=None, loop=None, rag=None, document=None,
                  has_result=any(hop.kind == "IN" and hop.owner == "tool" for hop in hops),
                  streaming=False, revised_from_v4=False)


def _run(case_id: str) -> ArmRunV5:
    """An empty gateway-arm record. The `_with_*` helpers below add exactly the
    half a fixture is about, so an unrelated field can never be the reason a
    fixture passes."""
    base = ArmRun(case_id=case_id, arm="I", repeat=0, calls=(), state=(), reply="",
                  termination="done", cost_usd=0.0, substitutes={}, masked_spans={})
    return ArmRunV5(base=base, reply_raw="", control_reply="", tool_results=(), mentions=(),
                    turn_replies=(), call_turns=(), request_count=1, stream_mismatch=False)


def _with_subs(run: ArmRunV5, subs: dict[str, str]) -> ArmRunV5:
    return replace(run, base=replace(run.base, substitutes={
        item_id: (surface, {}) for item_id, surface in subs.items()}))


def _with_replies(run: ArmRunV5, raw: str, restored: str, control: str) -> ArmRunV5:
    """The three replies a one-turn run holds, and its `turn_replies`.

    Every fixture here is a SINGLE-TURN run, so «the agent's restored reply at
    the end of every turn» is exactly `(restored,)` — set here rather than by a
    fourth `_with_*` helper nobody would remember to call, which is how
    `control_reply` came to be Line(0, 0) on every run before ruling R-40's
    sibling. An empty restoration stays an empty tuple: a turn the agent never
    spoke is not a turn with an empty reply, and `judge.dialogue_context`
    reads the difference."""
    turn_replies = (restored,) if restored else ()
    return replace(run, reply_raw=raw, control_reply=control, turn_replies=turn_replies,
                   base=replace(run.base, reply=restored))


def _with_calls(run: ArmRunV5, calls: tuple[ObservedCall, ...], turns: tuple[int, ...]) -> ArmRunV5:
    return replace(run, base=replace(run.base, calls=calls), call_turns=turns)


def _with_mentions(run: ArmRunV5, mentions: tuple[MentionRecord, ...]) -> ArmRunV5:
    return replace(run, mentions=mentions)


def _with_results(run: ArmRunV5, results: tuple[ToolResultRecord, ...]) -> ArmRunV5:
    return replace(run, tool_results=results)


def _with_masked(run: ArmRunV5, spans: dict[int, tuple[tuple[int, int], ...]]) -> ArmRunV5:
    return replace(run, base=replace(run.base, masked_spans=spans))


def _hop(kind: str, owner: str, item_id: str, index: int, turn: int, tool: str,
         ordinal: int, source: int, path: str) -> Hop:
    return Hop(kind=kind, owner=owner, item_id=item_id, hop_index=index, turn=turn,
               tool_name=tool, call_ordinal=ordinal, parallel_group="", source_hop=source,
               path=path, optional=False)


def _seen(case: CaseV5, hop: Hop, pii_type: str, produced: str, reference: str) -> HopObservation:
    """An `observed` crossing, with the REAL comparator's verdict on it: a
    fixture that asserted its own verdict would test nothing but itself."""
    return HopObservation(case_id=case.base.id, repeat=0, hop=hop, declared=True,
                          pii_type=pii_type, produced=produced, reference=reference,
                          status="observed", verdict=form_match(pii_type, produced, reference))


def _unseen(case: CaseV5, hop: Hop, pii_type: str, produced: str, reference: str,
            status: str) -> HopObservation:
    return HopObservation(case_id=case.base.id, repeat=0, hop=hop, declared=True,
                          pii_type=pii_type, produced=produced, reference=reference,
                          status=status, verdict=None)


def _extra_seen(case: CaseV5, hop: Hop, pii_type: str, produced: str,
                reference: str) -> HopObservation:
    """A crossing the agent made that the case did NOT declare (`observe.
    _extra_call_hops`): it counts in the form lines and in no denominator the
    case owns, and `hop_index` is -1 so no `source_hop` can point at it."""
    return HopObservation(case_id=case.base.id, repeat=0, hop=replace(hop, hop_index=-1),
                          declared=False, pii_type=pii_type, produced=produced,
                          reference=reference, status="observed",
                          verdict=form_match(pii_type, produced, reference))


def _obs(case: CaseV5, run: ArmRunV5, hops: tuple[HopObservation, ...]) -> RunObservation:
    return RunObservation(case=case, repeat=0, hops=hops, run=run, ic=None, cc=None)


# What a WRONG metric would print on each adversarial fixture, by fixture name.
# `contracts.Fixture` has no field for it, and a note that lived only in a
# comment could not be checked — `test_fixtures.test_adversarial_notes` demands
# one for every trap, so «adversarial» can never become a third ordinary case.
NOTES: dict[str, str] = {}


def _fx(metric: str, kind: str, note: str, rows: tuple[RunObservation, ...],
        hits: int, total: int) -> Fixture:
    fixture = Fixture(metric=metric, name=f"fx_{metric}_{kind}", kind=kind, input=rows,
                      expected_hits=hits, expected_total=total)
    NOTES[fixture.name] = note
    return fixture


# --- reusable pieces -------------------------------------------------------------------

NAME_ITEM = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 0, len(REAL_NAME)))
PHONE_ITEM = _item("p2", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_message(0, 20, 32))
DOB_ITEM = _item("p3", "DOB", "14.03.1987", "14.03.1987", "i1", _in_message(0, 0, 10))
LOC_ITEM = _item("p4", "LOC", "Ижевск, улица Клубная, 85", "Ижевск, улица Клубная, 85", "i1",
                 _in_seed("s1", "address"))
OTHER_ITEM = _item("p9", "NAME", OTHER_NAME, OTHER_NAME, "i2", _in_seed("s2", "name"))

IN_USER = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
OUT_ARG = _hop("OUT", "tool_arg", "p1", 1, 0, "crm_upsert_contact", 0, -1, "contact.name")
IN_TOOL = _hop("IN", "tool", "p1", 2, 0, "crm_find_contact", 0, -1, "contacts[].name")
OUT_ANSWER = _hop("OUT", "answer", "p1", 3, 0, "", -1, -1, "")


def _plain_case(case_id: str, hops: tuple[Hop, ...]) -> CaseV5:
    return _case(case_id, "single", (f"{REAL_NAME}, {REAL_PHONE}",), (NAME_ITEM, PHONE_ITEM), hops)


def _result(tool: str, turn: int, ordinal: int, form: str, real: str, masked: str,
            spans: dict[str, tuple[int, int]],
            pieces: tuple[tuple[int, int, str, str], ...], forced: bool) -> ToolResultRecord:
    return ToolResultRecord(tool_name=tool, seq=ordinal, call_ordinal=ordinal, turn=turn,
                            return_form=form, text_real=real, text_masked=masked,
                            spans_real=spans, pieces=pieces, forced=forced)


def _masked_text(real: str, pieces: tuple[tuple[int, int, str, str], ...]) -> str:
    """What the model reads: the real text with every replaced piece put in.

    Written out rather than passed by hand, because the `*_masked` lines now
    ask whether a piece of the value SURVIVES anywhere in the masked text —
    and a fixture that handed the real text as the masked one would fail a
    correct metric for a reason that has nothing to do with the case it
    describes. Right to left, so an earlier replacement cannot move a later
    span."""
    out = real
    for start, end, substitute, _engine_type in sorted(pieces, reverse=True):
        out = out[:start] + substitute + out[end:]
    return out


def _call(name: str, written: dict[str, object], restored: dict[str, object],
          residual: dict[str, tuple[str, ...]], refusal: str, seq: int) -> ObservedCall:
    return ObservedCall(name=name, written=written, restored=restored, residual=residual,
                        refusal_path="", refusal_rule=refusal, parsed=None, seq=seq)


# --- §4.2 public metrics ---------------------------------------------------------------

def _leak_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-leak", (IN_USER,))
    run = _run("fx-leak")
    leaked = _obs(case, run, (_unseen(case, IN_USER, "NAME", "", REAL_NAME, "leaked"),))
    altered = _obs(case, run, (_seen(case, IN_USER, "NAME", FAKE_NAME, REAL_NAME),))
    # ADVERSARIAL. The ONE value the model was shown LEAKED, and the two tool
    # calls the case declares never happened. `absent` is not «protected»:
    # nothing crossed there at all. Counting it as a hit printed 2/3 — «the
    # gateway altered two thirds of what the model saw» — while 100% of what
    # the model actually saw had leaked, and an agent that skipped a step
    # RAISED the headline number.
    absent = _obs(case, run, (_unseen(case, IN_USER, "NAME", "", REAL_NAME, "leaked"),
                              _unseen(case, IN_TOOL, "NAME", "", "", "absent"),
                              _unseen(case, IN_TOOL, "NAME", "", "", "absent")))
    return (_fx("leak", "zero", "", (leaked,), 0, 1),
            _fx("leak", "one", "", (altered,), 1, 1),
            _fx("leak", "adversarial", "absent is not shown, so it is not protection",
                (absent,), 0, 1))


def _coverage_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-cov", (IN_TOOL,))
    real = "Кузнецов Дмитрий"
    leaky = _with_results(_run("fx-cov"), (_result(
        "crm_find_contact", 0, 0, "single", real, "Кузнецов Игорь", {"p1": (0, len(real))},
        ((0, len(real), "Пахомов Игорь", "NAME"),), False),))
    clean = _with_results(_run("fx-cov"), (_result(
        "crm_find_contact", 0, 0, "single", real, "Пахомов Игорь", {"p1": (0, len(real))},
        ((0, len(real), "Пахомов Игорь", "NAME"),), False),))
    # ADVERSARIAL. The masked text still says «Ижевск». A city is a place
    # reference every Russian town shares and the corpus declares it NOT
    # personal data; a metric that counted every `parts_of` role as a piece
    # would print 0/1 and demand the engine mask the country too.
    address = LOC_ITEM.value
    city = _with_results(_run("fx-cov"), (_result(
        "crm_find_contact", 0, 0, "single", address, "Ижевск, улица Луговая, 10",
        {"p4": (0, len(address))}, ((0, len(address), "Самара, улица Луговая, 10", "LOC"),),
        False),))
    loc_hop = _hop("IN", "tool", "p4", 0, 0, "crm_find_contact", 0, -1, "contacts[].address")
    loc_case = _case("fx-cov-loc", "single", ("адрес",), (LOC_ITEM,), (loc_hop,))
    return (_fx("coverage", "zero", "", (_obs(case, leaky, (
                _seen(case, IN_TOOL, "NAME", "Пахомов Игорь", real),)),), 0, 1),
            _fx("coverage", "one", "", (_obs(case, clean, (
                _seen(case, IN_TOOL, "NAME", "Пахомов Игорь", real),)),), 1, 1),
            _fx("coverage", "adversarial", "a surviving city is not a surviving piece",
                (_obs(loc_case, city, (_seen(loc_case, loc_hop, "LOC",
                                             "Самара, улица Луговая, 10", address),)),), 1, 1))


def _typed_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-typed", (IN_TOOL,))

    def one(engine_type: str, real: str, sub: str) -> ArmRunV5:
        return _with_results(_run("fx-typed"), (_result(
            "crm_find_contact", 0, 0, "single", real, sub, {"p1": (0, len(real))},
            ((0, len(real), sub, engine_type),), False),))

    wrong = _obs(case, one("LOC", REAL_NAME, FAKE_NAME),
                 (_seen(case, IN_TOOL, "NAME", FAKE_NAME, REAL_NAME),))
    right = _obs(case, one("NAME", REAL_NAME, FAKE_NAME),
                 (_seen(case, IN_TOOL, "NAME", FAKE_NAME, REAL_NAME),))
    # ADVERSARIAL. The engine typed a birth date `DATE`. It is the same
    # judgement — a birth date IS a date — and a metric comparing the two
    # strings would print 0/1 and send somebody to fix a correct detector.
    dob_hop = _hop("IN", "tool", "p3", 0, 0, "crm_find_contact", 0, -1, "contacts[].birth_date")
    dob_case = _case("fx-typed-dob", "single", ("др",), (DOB_ITEM,), (dob_hop,))
    dated = _with_results(_run("fx-typed-dob"), (_result(
        "crm_find_contact", 0, 0, "single", "14.03.1987", "02.11.1979", {"p3": (0, 10)},
        ((0, 10, "02.11.1979", "DATE"),), False),))
    return (_fx("typed", "zero", "", (wrong,), 0, 1),
            _fx("typed", "one", "", (right,), 1, 1),
            _fx("typed", "adversarial", "DOB and DATE are one judgement",
                (_obs(dob_case, dated, (_seen(dob_case, dob_hop, "DOB", "02.11.1979", "14.03.1987"),)),),
                1, 1))


def _round_trip_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-rt", (IN_USER, OUT_ARG))
    run = _run("fx-rt")
    wrong = _obs(case, run, (_seen(case, IN_USER, "NAME", FAKE_NAME, REAL_NAME),
                             _seen(case, OUT_ARG, "NAME", "Иванова Лена", FAKE_NAME)))
    right = _obs(case, run, (_seen(case, IN_USER, "NAME", FAKE_NAME, REAL_NAME),
                             _seen(case, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME)))
    return (_fx("round_trip", "zero", "", (wrong,), 0, 1),
            _fx("round_trip", "one", "", (right,), 1, 1),
            _fx("round_trip", "adversarial", "a repaired value is not a round trip",
                (_repaired_name("fx-rt-2"),), 0, 1))


def _repaired_name(case_id: str) -> RunObservation:
    """The REAL name, DECLINED, into a leaf that takes the whole name.

    The pair `round_trip` / `round_trip_repaired` exists to price
    normalisation, so the two must disagree on exactly one input and this is
    it: «Ивановой Елене» is the customer's own name and it is not what the
    CRM field was promised. The example used to be a DOB written in ISO where
    the customer said «14.03.1987» — but `patient.birth_date` DECLARES the
    role `iso`, so ISO is the value that leaf asks for and the comparison is
    now made against the item's ISO part: a right answer, and no longer a
    trap. A leaf with no role keeps the verbatim promise."""
    whole = _hop("OUT", "tool_arg", "p1", 1, 0, "delivery_create_order", 0, -1, "recipient.name")
    case = _case(case_id, "single", (REAL_NAME,), (NAME_ITEM,), (IN_USER, whole))
    return _obs(case, _run(case_id), (_seen(case, IN_USER, "NAME", FAKE_NAME, REAL_NAME),
                                      _seen(case, whole, "NAME", "Ивановой Елене", FAKE_NAME)))


def _round_trip_repaired_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-rtr", (IN_USER, OUT_ARG))
    run = _run("fx-rtr")
    wrong = _obs(case, run, (_seen(case, IN_USER, "NAME", FAKE_NAME, REAL_NAME),
                             _seen(case, OUT_ARG, "NAME", OTHER_NAME, FAKE_NAME)))
    right = _obs(case, run, (_seen(case, IN_USER, "NAME", FAKE_NAME, REAL_NAME),
                             _seen(case, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME)))
    # ADVERSARIAL. The very case `round_trip` refuses. A diagnostic that
    # printed 0/1 here would be a copy of the line it exists to explain, and
    # the two would never differ by the cost of normalisation.
    return (_fx("round_trip_repaired", "zero", "", (wrong,), 0, 1),
            _fx("round_trip_repaired", "one", "", (right,), 1, 1),
            _fx("round_trip_repaired", "adversarial", "the declined real name IS repaired",
                (_repaired_name("fx-rtr-2"),), 1, 1))


def _end_to_end_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-e2e", (OUT_ARG,))
    run = _run("fx-e2e")
    missing = _obs(case, run, (_unseen(case, OUT_ARG, "NAME", "", "", "absent"),))
    arrived = _obs(case, run, (_seen(case, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME),))
    # ADVERSARIAL, AND IT CARRIES FOUR CLAUSES BECAUSE THE LINE HAS FOUR WAYS
    # TO BE WRONG.
    #   1. the whole name arrived — a hit;
    #   2. the phone call never happened: `absent` stays in the DENOMINATOR. A
    #      metric that dropped it would print 1/1 and an agent that stopped
    #      calling tools would score better than one that called them — v4's
    #      D3 defect, which took a floor of 44.5 to notice;
    #   3. `contact.last_name` asks for the SURNAME and got another person's:
    #      observed, wrong value. No fixture used to exercise that clause at
    #      all, so a metric that only checked `status == "observed"` passed;
    #   4. `contact.middle_name` asks for a PATRONYMIC the customer never said.
    #      No string can satisfy the tool and the metric at once — a corpus
    #      defect, and it is a MISS. 793 of 8 399 declared leaves were in that
    #      state before the corpus was rebuilt and none is today, which is why
    #      the verdict lives in a fixture: silently calling it a hit would be
    #      «all() over an empty list» once more, and invisible when it returns.
    second = _hop("OUT", "tool_arg", "p2", 2, 0, "crm_upsert_contact", 1, -1, "contact.phone")
    surname = _hop("OUT", "tool_arg", "p1", 3, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    patronymic = _hop("OUT", "tool_arg", "p1", 4, 0, "crm_upsert_contact", 0, -1,
                      "contact.middle_name")
    both = _case("fx-e2e-2", "parallel", ("…",), (NAME_ITEM, PHONE_ITEM),
                 (OUT_ARG, second, surname, patronymic))
    mixed = _obs(both, _run("fx-e2e-2"),
                 (_seen(both, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME),
                  _unseen(both, second, "PHONE", "", "", "absent"),
                  _seen(both, surname, "NAME", "Смирнова", "Пахомова"),
                  _seen(both, patronymic, "NAME", "Сергеевна", "Олеговна")))
    return (_fx("end_to_end", "zero", "", (missing,), 0, 1),
            _fx("end_to_end", "one", "", (arrived,), 1, 1),
            _fx("end_to_end", "adversarial",
                "absent stays in the denominator; a wrong part and an unsatisfiable role are misses",
                (mixed,), 1, 4))


def _overmask_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    negative = Negative(value="TRK-88142", start=10, end=19, msg=0, family="order_no",
                        why="трек-номер, не ПД")
    case = replace(_plain_case("fx-om", ()), base=replace(
        _plain_case("fx-om", ()).base, negatives=(negative,)))
    covered = _with_masked(_run("fx-om"), {0: ((8, 22),)})
    free = _with_masked(_run("fx-om"), {0: ((0, 5),)})
    # ADVERSARIAL. The masked span ENDS exactly where the negative begins.
    # Touching is not covering; a metric comparing with `<=` on the boundary
    # would print 0/1 and a track number beside a masked name would read as a
    # false mask for ever.
    touching = _with_masked(_run("fx-om"), {0: ((0, 10), (19, 25))})
    return (_fx("overmask", "zero", "", (_obs(case, covered, ()),), 0, 1),
            _fx("overmask", "one", "", (_obs(case, free, ()),), 1, 1),
            _fx("overmask", "adversarial", "a span that touches does not cover",
                (_obs(case, touching, ()),), 1, 1))


def _consistency_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-cons", ())
    two = (MentionRecord("p1", 0, -1, FAKE_NAME, 0), MentionRecord("p1", 2, -1, OTHER_NAME, 1))
    one = (MentionRecord("p1", 0, -1, FAKE_NAME, 0), MentionRecord("p1", 2, -1, FAKE_NAME, 1))
    # ADVERSARIAL. The phone is mentioned ONCE. There is no second mention to
    # agree with, so it is not in the population at all; a metric that counted
    # every item would print 1/2 and every case with a value said once would
    # drag the line down.
    single = one + (MentionRecord("p2", 0, -1, "+79990001122", 0),)
    return (_fx("consistency", "zero", "",
                (_obs(case, _with_mentions(_run("fx-cons"), two), ()),), 0, 1),
            _fx("consistency", "one", "",
                (_obs(case, _with_mentions(_run("fx-cons"), one), ()),), 1, 1),
            _fx("consistency", "adversarial", "one mention is not a population",
                (_obs(case, _with_mentions(_run("fx-cons"), single), ()),), 1, 1))


def _stability_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-stab", ())
    moved = (MentionRecord("p1", 0, -1, FAKE_NAME, 0), MentionRecord("p1", 0, -1, OTHER_NAME, 1))
    kept = (MentionRecord("p1", 0, -1, FAKE_NAME, 0), MentionRecord("p1", 0, -1, FAKE_NAME, 1))
    # ADVERSARIAL. The phone appears twice in ONE request (two messages of the
    # same transcript). That is `consistency`, not `stability`; a metric keyed
    # on messages rather than on `request_index` would print 1/2 and the two
    # lines would stop being two questions.
    same_request = kept + (MentionRecord("p2", 0, -1, "+79990001122", 0),
                           MentionRecord("p2", 2, -1, "+79990009988", 0))
    return (_fx("stability", "zero", "",
                (_obs(case, _with_mentions(_run("fx-stab"), moved), ()),), 0, 1),
            _fx("stability", "one", "",
                (_obs(case, _with_mentions(_run("fx-stab"), kept), ()),), 1, 1),
            _fx("stability", "adversarial", "two messages of one request are not two requests",
                (_obs(case, _with_mentions(_run("fx-stab"), same_request), ()),), 1, 1))


def _rewrite_ratio_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-rw", ())
    same = _with_replies(_run("fx-rw"), "", "Заказ оформлен, курьер приедет завтра.",
                         "Заказ оформлен, курьер приедет завтра.")
    other = _with_replies(_run("fx-rw"), "", "Не смогу помочь с этим запросом.",
                          "Заказ оформлен, курьер приедет завтра.")
    # ADVERSARIAL. The two replies differ by the NAME and nothing else — which
    # is what a working gateway produces on every single case. A metric that
    # flagged any difference would print 1/1 and the diagnostic would fire on
    # the product working as designed.
    near = _with_replies(_run("fx-rw"), "",
                         "Заказ оформлен на Иванову Елену, курьер приедет завтра до 18:00.",
                         "Заказ оформлен на Кузнецову Дарью, курьер приедет завтра до 18:00.")
    return (_fx("rewrite_ratio_v5", "zero", "", (_obs(case, same, ()),), 0, 1),
            _fx("rewrite_ratio_v5", "one", "", (_obs(case, other, ()),), 1, 1),
            _fx("rewrite_ratio_v5", "adversarial", "one restored name is not a rewrite",
                (_obs(case, near, ()),), 0, 1))


def _shared_block_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    two_people = (NAME_ITEM, OTHER_ITEM)
    case = _case("fx-sb", "single", ("…",), two_people, ())
    lone = _with_subs(_with_replies(_run("fx-sb"), "Готово: ПАХОМОВА. Спасибо.",
                                    "Готово: ИВАНОВА. Спасибо.", ""), {"p1": "ПАХОМОВА"})
    # Two items, one rewritten region: the agent wrote the pair as one phrase.
    # The substitutes share no letters with the real values on purpose — two
    # names that rhyme align into several regions, and this fixture is about
    # the metric's grouping, not about the alignment's resolution.
    shared = _with_subs(_with_replies(_run("fx-sb"), "Готово: ЩУКИН ЭЛЬБРУС. Спасибо.",
                                      "Готово: Иванова Елена. Спасибо.", ""),
                        {"p1": "ЩУКИН", "p9": "ЭЛЬБРУС"})
    # ADVERSARIAL. Two spans, one item each, and BOTH items belong to one
    # person. Nothing is shared: a metric that grouped by identity instead of
    # by span would print 1/2 and would call the commonest case in the corpus —
    # a name and a phone of the same customer — an attribution failure.
    same_identity = _item("p5", "NAME", "Иванов Пётр", "Иванов Пётр", "i1", _in_message(0, 0, 11))
    pair_case = _case("fx-sb-2", "single", ("…",), (NAME_ITEM, same_identity), ())
    apart = _with_subs(_with_replies(_run("fx-sb-2"),
                                     "Готово: ПАХОМОВА. Далее: ОРЛОВ. Спасибо.",
                                     "Готово: ИВАНОВА. Далее: ПЕТРОВ. Спасибо.", ""),
                       {"p1": "ПАХОМОВА", "p5": "ОРЛОВ"})
    return (_fx("shared_block_answer", "zero", "", (_obs(case, lone, ()),), 0, 1),
            _fx("shared_block_answer", "one", "", (_obs(case, shared, ()),), 1, 1),
            _fx("shared_block_answer", "adversarial", "one identity across two spans shares nothing",
                (_obs(pair_case, apart, ()),), 0, 2))


# --- §4.3 the v5 metrics ---------------------------------------------------------------

def _form_pair(metric: str, hop: Hop) -> tuple[Fixture, Fixture]:
    """The zero and the one of a form line: a grammatical case failure and an
    exact match. Shared, because `form_hIN` and `form_hOUT` differ only in
    which hop they count; their TRAPS differ and are written apart."""
    case = _plain_case(f"fx-{metric}", (hop,))
    run = _run(f"fx-{metric}")
    declined = _obs(case, run, (_seen(case, hop, "NAME", DECLINED_MALE, FAKE_MALE),))
    exact = _obs(case, run, (_seen(case, hop, "NAME", FAKE_MALE, FAKE_MALE),))
    return (_fx(metric, "zero", "", (declined,), 0, 1),
            _fx(metric, "one", "", (exact,), 1, 1))


def _form_in_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-form_hIN", (IN_USER,))
    run = _run("fx-form_hIN")
    # ADVERSARIAL. Identical letters, another case class. A comparator folding
    # the strings before comparing would print 1/1 — and «ПАХОМОВА ОЛЬГА» in a
    # CRM field the customer reads is precisely the failure the line exists for.
    shouted = _obs(case, run, (_seen(case, IN_USER, "NAME", FAKE_MALE.upper(), FAKE_MALE),))
    zero, one = _form_pair("form_hIN", IN_USER)
    return (zero, one,
            _fx("form_hIN", "adversarial", "same letters, other case class", (shouted,), 0, 1))


def _form_out_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-form_hOUT", (OUT_ARG,))
    run = _run("fx-form_hOUT")
    # ADVERSARIAL, TWO CLAUSES. The first hop shouts the substitute back in
    # another letter case — the C-153 trap. The second is a leaf the gateway
    # never masked: the agent wrote the REAL value, nothing was restored, and
    # `produced == reference` made `form_match` say «same». A gateway that
    # masked NOTHING printed 100% on this line, so `unmasked` is a MISS and
    # stays in the denominator; dropping it instead would let a passthrough
    # score «н/п» and look untested rather than broken.
    trap = _obs(case, run, (_seen(case, OUT_ARG, "NAME", FAKE_MALE.upper(), FAKE_MALE),
                            _unseen(case, OUT_ARG, "NAME", REAL_NAME, REAL_NAME, "unmasked")))
    zero, one = _form_pair("form_hOUT", OUT_ARG)
    return (zero, one,
            _fx("form_hOUT", "adversarial", "a letter-case change and a leaf with nothing in it",
                (trap,), 0, 2))


def _out_absent_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """The count printed BESIDE `form_hOUT`: what the agent never wrote."""
    case = _plain_case("fx-oa", (OUT_ARG,))
    run = _run("fx-oa")
    wrote = _obs(case, run, (_seen(case, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME),))
    skipped = _obs(case, run, (_unseen(case, OUT_ARG, "NAME", "", "", "absent"),))
    # ADVERSARIAL. One declared hop the agent skipped, and one crossing it made
    # that the case never declared. The undeclared one is not a hop the agent
    # «failed to write», so it is outside the denominator: a metric counting
    # every OUT hop would print 1/2 and an agent that improvised an extra call
    # would look more obedient than one that did not.
    extra = _extra_seen(case, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME)
    mixed = _obs(case, run, (_unseen(case, OUT_ARG, "NAME", "", "", "absent"), extra))
    return (_fx("out_absent", "zero", "", (wrote,), 0, 1),
            _fx("out_absent", "one", "", (skipped,), 1, 1),
            _fx("out_absent", "adversarial", "an undeclared crossing is not a skipped one",
                (mixed,), 1, 1))


def _stream_fidelity_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """The streaming leg, which the harness measured on 84 cases and nothing
    read."""
    case = replace(_plain_case("fx-sf", ()), streaming=True)
    torn = _obs(case, replace(_run("fx-sf"), stream_mismatch=True), ())
    whole = _obs(case, _run("fx-sf"), ())
    # ADVERSARIAL. A NON-streaming case, whose `stream_mismatch` is False
    # because the leg never ran. A metric counting every observation would
    # print 2/2 and certify a streaming contract on a corpus that streamed
    # once; the population is the streaming cases and a corpus without them
    # gets «н/п».
    plain = _obs(_plain_case("fx-sf-2", ()), _run("fx-sf-2"), ())
    return (_fx("stream_fidelity", "zero", "", (torn,), 0, 1),
            _fx("stream_fidelity", "one", "", (whole,), 1, 1),
            _fx("stream_fidelity", "adversarial", "a case that never streamed is not a hit",
                (whole, plain), 1, 1))


def _returns_case(case_id: str, tool: str, ordinal: int, form: str,
                  item_ids: tuple[str, ...]) -> CaseV5:
    """A case that DECLARES which result carries which datum. That declaration
    — not «whatever the mock happened to tag» — is `toolresult_masked`'s
    denominator now."""
    return replace(_plain_case(case_id, ()),
                   returns=(ReturnExpectation(tool_name=tool, call_ordinal=ordinal,
                                              return_form=form, result_item_ids=item_ids),))


def _toolresult_masked_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _returns_case("fx-trm", "crm_find_contact", 0, "single", ("p1", "p2"))
    real = f"{REAL_NAME}, {REAL_PHONE}"
    name_span, phone_span = (0, len(REAL_NAME)), (len(REAL_NAME) + 2, len(real))
    half = _with_results(_run("fx-trm"), (_result(
        "crm_find_contact", 0, 0, "single", real, "…", {"p1": name_span, "p2": phone_span},
        ((name_span[0], name_span[1], FAKE_NAME, "NAME"),), False),))
    whole = _with_results(_run("fx-trm"), (_result(
        "crm_find_contact", 0, 0, "single", real, "…", {"p1": name_span, "p2": phone_span},
        ((name_span[0], name_span[1], FAKE_NAME, "NAME"),
         (phone_span[0], phone_span[1], "+79990001122", "PHONE")), False),))
    # ADVERSARIAL, FOUR CLAUSES — the line's four blind spots, in one input.
    #   1. a scripted `error_with_value`: the API echoes the offending field,
    #      so the REAL phone is in the error body the model reads. The tag
    #      carries `ECHO_TAG_PREFIX`; a metric skipping echo tags would print
    #      it clean and the retry family would score perfect while handing the
    #      model the value it is supposed to hide;
    #   2. the holder printed on EVERY row of a statement, tagged and masked
    #      ONCE: `contracts` promises the leak check reads the whole text, and
    #      the span check alone called this clean;
    #   3. a DECLARED value the result renders with NO tag: 540 of 2 483
    #      results on the revised half were exactly that, and every one was
    #      outside the old denominator rather than a miss;
    #   4. a declared result the agent NEVER obtained: outside the denominator,
    #      the way an `absent` hop is — the agent's inaction is not a leak.
    body = f"неверный формат: {REAL_PHONE}"
    echo_case = _returns_case("fx-trm-echo", "crm_upsert_contact", 0, "error_with_value", ("p2",))
    echo = _with_results(_run("fx-trm-echo"), (_result(
        "crm_upsert_contact", 0, 0, "error_with_value", body, body,
        {contracts.ECHO_TAG_PREFIX + "p2": (18, len(body))}, (), True),))
    rows = f"Владелец: {REAL_NAME}. Строка 1: {REAL_NAME} 500р"
    first = (10, 10 + len(REAL_NAME))
    twice_case = _returns_case("fx-trm-rows", "account_statement", 0, "list", ("p1",))
    twice = _with_results(_run("fx-trm-rows"), (_result(
        "account_statement", 0, 0, "list", rows,
        rows.replace(REAL_NAME, FAKE_NAME, 1), {"p1": first},
        ((first[0], first[1], FAKE_NAME, "NAME"),), False),))
    untagged_case = _returns_case("fx-trm-untag", "crm_find_contact", 0, "single", ("p1", "p2"))
    untagged = _with_results(_run("fx-trm-untag"), (_result(
        "crm_find_contact", 0, 0, "single", real, f"{FAKE_NAME}, {REAL_PHONE}",
        {"p1": name_span}, ((name_span[0], name_span[1], FAKE_NAME, "NAME"),), False),))
    never_case = _returns_case("fx-trm-none", "crm_find_contact", 0, "single", ("p1",))
    return (_fx("toolresult_masked", "zero", "", (_obs(case, half, ()),), 0, 1),
            _fx("toolresult_masked", "one", "", (_obs(case, whole, ()),), 1, 1),
            _fx("toolresult_masked", "adversarial",
                "the echo, the second rendering, the untagged declared value, the call never made",
                (_obs(echo_case, echo, ()), _obs(twice_case, twice, ()),
                 _obs(untagged_case, untagged, ()), _obs(never_case, _run("fx-trm-none"), ())),
                0, 3))


def _answer_real_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-ar", (OUT_ANSWER,))
    run = _run("fx-ar")
    left = _obs(case, run, (_unseen(case, OUT_ANSWER, "NAME", "", "", "residual"),))
    good = _obs(case, run, (_seen(case, OUT_ANSWER, "NAME", REAL_NAME, REAL_NAME),))
    # ADVERSARIAL. The REAL phone, in the engine's canonical, where the agent
    # wrote «8 916 402-11-87». The value is right and the customer reads a
    # number in a notation nobody in the dialogue used; a metric that asked
    # only «is it the real value» would print 1/1 and the answer leg would
    # never be measured at all (spec §1, «OUT-ответ ✗»).
    answer_phone = _hop("OUT", "answer", "p2", 0, 0, "", -1, -1, "")
    phone_case = _case("fx-ar-phone", "single", (AGENT_PHONE,), (PHONE_ITEM,), (answer_phone,))
    canon = _obs(phone_case, _run("fx-ar-phone"),
                 (_seen(phone_case, answer_phone, "PHONE", REAL_PHONE, AGENT_PHONE),))
    # ADVERSARIAL, SECOND CLAUSE. Perfect form, ANOTHER PERSON's name. For 713
    # cases this line could only be failed by a `residual` status, so a wrong
    # value in the answer was invisible and an answer naming nobody scored a
    # hit — v4's «all() over an empty list», on the leg the customer reads.
    other_case = _plain_case("fx-ar-2", (OUT_ANSWER,))
    wrong_person = _obs(other_case, _run("fx-ar-2"),
                        (_seen(other_case, OUT_ANSWER, "NAME", OTHER_NAME, OTHER_NAME),))
    return (_fx("answer_real", "zero", "", (left,), 0, 1),
            _fx("answer_real", "one", "", (good,), 1, 1),
            _fx("answer_real", "adversarial",
                "the real value in a foreign form, and another person's in the right one",
                (canon, wrong_person), 0, 2))


def _chain_case(case_id: str, out_item: str, items: tuple[PiiItem, ...]) -> tuple[CaseV5, Hop, Hop]:
    source = _hop("IN", "tool", "p1", 0, 0, "crm_find_contact", 0, -1, "contacts[].name")
    target = Hop(kind="OUT", owner="tool_arg", item_id=out_item, hop_index=1, turn=0,
                 tool_name="delivery_create_order", call_ordinal=0, parallel_group="",
                 source_hop=0, path="recipient.name", optional=False)
    return _case(case_id, "sequential_chain", ("…",), items, (source, target)), source, target


def _chain_value_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case, source, target = _chain_case("fx-cv", "p1", (NAME_ITEM,))
    run = _run("fx-cv")
    lost = _obs(case, run, (_seen(case, source, "NAME", FAKE_NAME, REAL_NAME),
                            _seen(case, target, "NAME", "Иванова Л.", FAKE_NAME)))
    kept = _obs(case, run, (_seen(case, source, "NAME", FAKE_NAME, REAL_NAME),
                            _seen(case, target, "NAME", REAL_NAME, FAKE_NAME)))
    # ADVERSARIAL. The string that arrived at B is exactly the string A
    # returned — for ANOTHER PERSON. The hop belongs to `p9` (identity i2) and
    # the chain it claims to continue belongs to `p1` (identity i1). A metric
    # comparing only the two strings would print 1/1 while the gateway wrote
    # one customer's data into another customer's order: the `other_person`
    # class v4 already flags as a product defect.
    other_case, other_source, other_target = _chain_case("fx-cv-2", "p9", (NAME_ITEM, OTHER_ITEM))
    crossed = _obs(other_case, _run("fx-cv-2"),
                   (_seen(other_case, other_source, "NAME", FAKE_NAME, REAL_NAME),
                    _seen(other_case, other_target, "NAME", REAL_NAME, FAKE_NAME)))
    return (_fx("chain_value", "zero", "", (lost,), 0, 1),
            _fx("chain_value", "one", "", (kept,), 1, 1),
            _fx("chain_value", "adversarial",
                "the right string for the wrong person; and B is a TOOL, never the answer",
                (crossed, _answer_link("fx-cv-3")), 0, 1))


def _answer_link(case_id: str) -> RunObservation:
    """«The agent told the customer what the tool said» — an OUT/answer hop
    carrying a `source_hop`. The corpus declares 3 870 of them and they are
    NOT A→B transitions: B is an act on a tool
    (`contracts.ACTING_OUT_OWNERS`). A metric that accepted them counted 56%
    of its own denominator as chain links that no tool ever received, and this
    one would be a HIT — the value is right — so the line would read better
    for containing a thing it should not contain."""
    source = _hop("IN", "tool", "p1", 0, 0, "crm_find_contact", 0, -1, "contacts[].name")
    told = Hop(kind="OUT", owner="answer", item_id="p1", hop_index=1, turn=0, tool_name="",
               call_ordinal=-1, parallel_group="", source_hop=0, path="", optional=False)
    case = _case(case_id, "sequential_chain", ("…",), (NAME_ITEM,), (source, told))
    return _obs(case, _run(case_id), (_seen(case, source, "NAME", FAKE_NAME, REAL_NAME),
                                      _seen(case, told, "NAME", REAL_NAME, FAKE_NAME)))


def _chain_form_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case, source, target = _chain_case("fx-cf", "p1", (NAME_ITEM,))
    run = _run("fx-cf")
    canon = _obs(case, run, (_seen(case, source, "NAME", FAKE_NAME, REAL_NAME),
                             _seen(case, target, "NAME", "ИВАНОВА ЕЛЕНА", FAKE_NAME)))
    agent = _obs(case, run, (_seen(case, source, "NAME", FAKE_NAME, REAL_NAME),
                             _seen(case, target, "NAME", REAL_NAME, FAKE_NAME)))
    # ADVERSARIAL. A value carried by two FIELDS, the street in the agent's
    # spelling and the generic word from the tool's canon. A metric that
    # compared the joined string as one blob would print 1/1; the comparator
    # names `generic` and the transition is a miss.
    loc_source = _hop("IN", "tool", "p4", 0, 0, "address_suggest", 0, -1, "suggestions[].value")
    loc_target = Hop(kind="OUT", owner="tool_arg", item_id="p4", hop_index=1, turn=0,
                     tool_name="courier_book", call_ordinal=0, parallel_group="",
                     source_hop=0, path="address", optional=False)
    loc_case = _case("fx-cf-loc", "sequential_chain", ("…",), (LOC_ITEM,), (loc_source, loc_target))
    sep = contracts.FIELD_SEP
    mixed = _obs(loc_case, _run("fx-cf-loc"),
                 (_seen(loc_case, loc_source, "LOC", f"Луговая{sep}10", f"Клубная{sep}85"),
                  _seen(loc_case, loc_target, "LOC", f"ул. Клубная{sep}85", f"Луговая{sep}10")))
    return (_fx("chain_form", "zero", "", (canon,), 0, 1),
            _fx("chain_form", "one", "", (agent,), 1, 1),
            _fx("chain_form", "adversarial",
                "one field in each form; and the answer is not a B",
                (mixed, _answer_link("fx-cf-2")), 0, 1))


def _multi_all_out_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    first = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.name")
    second = _hop("OUT", "tool_arg", "p2", 1, 0, "crm_upsert_contact", 1, -1, "contact.phone")
    case = _case("fx-mao", "parallel", ("…",), (NAME_ITEM, PHONE_ITEM), (first, second))
    run = _run("fx-mao")
    broken = _obs(case, run, (_seen(case, first, "NAME", REAL_NAME, REAL_NAME),
                              _seen(case, second, "PHONE", "+79990001122", REAL_PHONE)))
    whole = _obs(case, run, (_seen(case, first, "NAME", REAL_NAME, REAL_NAME),
                             _seen(case, second, "PHONE", REAL_PHONE, REAL_PHONE)))
    # ADVERSARIAL. Both arguments are right and the agent emitted them in the
    # other order — `call_ordinal` 1 for the hop the case declared first. Order
    # is the model's taste; a metric that required the declaration order would
    # print 0/1 and would score the gateway down for a decision it never made.
    swapped = _obs(case, run, (
        _seen(case, replace(first, call_ordinal=1), "NAME", REAL_NAME, REAL_NAME),
        _seen(case, replace(second, call_ordinal=0), "PHONE", REAL_PHONE, REAL_PHONE)))
    # ADVERSARIAL, SECOND CLAUSE. Both values are RIGHT and one of them wears
    # the tool's canon instead of the agent's «8 916 402-11-87». The turn is a
    # MISS: «все OUT верны (значение И форма)». No fixture exercised the form
    # half, so a metric that checked the value alone passed the gate.
    formless = _case("fx-mao-2", "parallel", ("…",), (NAME_ITEM, PHONE_ITEM), (first, second))
    canon = _obs(formless, _run("fx-mao-2"),
                 (_seen(formless, first, "NAME", REAL_NAME, FAKE_NAME),
                  _seen(formless, second, "PHONE", REAL_PHONE, AGENT_PHONE)))
    return (_fx("multi_all_out", "zero", "", (broken,), 0, 1),
            _fx("multi_all_out", "one", "", (whole,), 1, 1),
            _fx("multi_all_out", "adversarial",
                "order is not a condition; the right value in the wrong form still fails",
                (swapped, canon), 1, 2))


def _multi_consistency_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-mc", ())

    def turn(first_sub: str, second_sub: str, refusal: str) -> ArmRunV5:
        run = _with_calls(_run("fx-mc"), (
            _call("crm_upsert_contact", {"contact": {"name": first_sub}},
                  {"contact": {"name": REAL_NAME}}, {}, refusal, 0),
            _call("crm_upsert_contact", {"contact": {"name": second_sub}},
                  {"contact": {"name": REAL_NAME}}, {}, "", 1)), (0, 0))
        return _with_mentions(run, (MentionRecord("p1", 0, -1, first_sub, 0),
                                    MentionRecord("p1", 0, -1, second_sub, 0)))

    two = turn(FAKE_NAME, OTHER_NAME, "")
    one = turn(FAKE_NAME, FAKE_NAME, "")
    # ADVERSARIAL. The first call was REFUSED and the agent tried again with
    # the same substitute. Two calls, one substitute — the gateway did exactly
    # what it promises. A metric counting attempts instead of distinct
    # substitutes would print 0/1 and every retry case would read as a re-mint.
    retry = turn(FAKE_NAME, FAKE_NAME, "phone_not_e164")
    # ADVERSARIAL, SECOND CLAUSE. ONE substitute, TWO inflections: the agent
    # put the nominative into the name field and the dative into a free-text
    # note of the SAME turn. That is ordinary Russian and exactly what the
    # gateway promises to allow. `substitute_surfaces` returns every spelling
    # the model READ of one mint, so a metric counting distinct spellings
    # called this a re-mint and failed the turn — the line fired on the
    # product working.
    declined = _with_mentions(_with_subs(_with_calls(_run("fx-mc-2"), (
        _call("crm_upsert_contact", {"contact": {"name": FAKE_NAME}},
              {"contact": {"name": REAL_NAME}}, {}, "", 0),
        _call("crm_add_note", {"text": f"перезвонить {DECLINED_FAKE}"},
              {"text": f"перезвонить {REAL_NAME}"}, {}, "", 1)), (0, 0)), {"p1": FAKE_NAME}),
        (MentionRecord("p1", 0, -1, FAKE_NAME, 0), MentionRecord("p1", 2, -1, DECLINED_FAKE, 1)))
    return (_fx("multi_consistency", "zero", "", (_obs(case, two, ()),), 0, 1),
            _fx("multi_consistency", "one", "", (_obs(case, one, ()),), 1, 1),
            _fx("multi_consistency", "adversarial",
                "a retry is not a second value, and neither is a second case ending",
                (_obs(case, retry, ()), _obs(_plain_case("fx-mc-2", ()), declined, ())), 2, 2))


def _retry_fixture(case_id: str, first_ref: str, second_ref: str,
                   first_out: str, second_out: str) -> RunObservation:
    first = _hop("OUT", "tool_arg", "p2", 0, 0, "crm_upsert_contact", 0, -1, "contact.phone")
    second = _hop("OUT", "tool_arg", "p2", 1, 0, "crm_upsert_contact", 1, -1, "contact.phone")
    case = _case(case_id, "retry_same_tool", ("…",), (PHONE_ITEM,), (first, second))
    case = replace(case, forced=(ForcedError("crm_upsert_contact", 0, "phone_not_e164", "p2",
                                             "неверный формат: {value}"),))
    run = _with_calls(_run(case_id), (
        _call("crm_upsert_contact", {"contact": {"phone": first_ref}},
              {"contact": {"phone": first_out}}, {}, "phone_not_e164", 0),
        _call("crm_upsert_contact", {"contact": {"phone": second_ref}},
              {"contact": {"phone": second_out}}, {}, "", 1)), (0, 0))
    return _obs(case, run, (_seen(case, first, "PHONE", first_out, first_ref),
                            _seen(case, second, "PHONE", second_out, second_ref)))


def _retry_form_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    # ADVERSARIAL. The agent gave up on «+7…» after the refusal and wrote
    # «8 916…» on the second attempt; the gateway restored each attempt in the
    # form of THAT attempt. A metric that judged attempt 2 against attempt 1's
    # form — the tempting way to say «consistent» — would print 0/1 and would
    # punish the gateway for listening to the agent, which is the whole rule.
    return (_fx("retry_form", "zero", "",
                (_retry_fixture("fx-rf-0", "+7 916 402-11-87", "8 916 402-11-87",
                                "+7 916 402-11-87", "+79164021187"),), 0, 1),
            _fx("retry_form", "one", "",
                (_retry_fixture("fx-rf-1", "+7 916 402-11-87", "+7 916 402-11-87",
                                "+7 916 402-11-87", "+7 916 402-11-87"),), 1, 1),
            # SECOND CLAUSE: attempt ONE was restored in the wrong form and
            # attempt two was right. «В КАЖДОЙ попытке» — a metric judging the
            # last attempt only would print 1/1 and a gateway that learnt the
            # form after being refused would score the same as one that had it
            # from the start.
            _fx("retry_form", "adversarial",
                "the agent changed form and we followed; a wrong FIRST attempt still fails",
                (_retry_fixture("fx-rf-2", "+7 916 402-11-87", "8 916 402-11-87",
                                "+7 916 402-11-87", "8 916 402-11-87"),
                 _retry_fixture("fx-rf-3", "+7 916 402-11-87", "+7 916 402-11-87",
                                "+79164021187", "+7 916 402-11-87")), 1, 2))


def _memory_consistency_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    spec = MemorySpec(item_id="p1", first_turn=0, recall_turn=6, anaphora="none")
    case = replace(_plain_case("fx-mem", ()), memory=(spec,))
    minted_twice = _with_mentions(_run("fx-mem"), (
        MentionRecord("p1", 0, -1, FAKE_NAME, 0), MentionRecord("p1", 6, -1, OTHER_NAME, 3)))
    minted_once = _with_mentions(_run("fx-mem"), (
        MentionRecord("p1", 0, -1, FAKE_NAME, 0), MentionRecord("p1", 6, -1, FAKE_NAME, 3)))
    # ADVERSARIAL. «Позвоните ему» — the recall turn says no value, so it
    # leaves no mention at all. The value still crossed once, with one
    # substitute. A metric that demanded a mention AT the recall turn would
    # print 0/1 and every anaphora case, the family this metric was written
    # for, would be a failure.
    pronoun = replace(case, memory=(replace(spec, anaphora="pronoun"),))
    anaphoric = _with_mentions(_run("fx-mem"), (MentionRecord("p1", 0, -1, FAKE_NAME, 0),
                                                MentionRecord("p1", 0, -1, FAKE_NAME, 3)))
    return (_fx("memory_consistency", "zero", "", (_obs(case, minted_twice, ()),), 0, 1),
            _fx("memory_consistency", "one", "", (_obs(case, minted_once, ()),), 1, 1),
            _fx("memory_consistency", "adversarial", "anaphora leaves no mention",
                (_obs(pronoun, anaphoric, ()),), 1, 1))


def _memory_stability_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """ITS OWN POPULATION — the items a `MemorySpec` names. `stability` and
    this line were one function under two names and their fixtures answered
    identically on every input in the package, so the gate could not tell them
    apart either. These cases carry a `MemorySpec`; `stability`'s carry none,
    which is what makes the two lines two measurements."""
    spec = MemorySpec(item_id="p1", first_turn=0, recall_turn=4, anaphora="none")
    case = replace(_plain_case("fx-ms", ()), memory=(spec,))
    moved = _with_mentions(_run("fx-ms"), (MentionRecord("p1", 0, -1, FAKE_NAME, 0),
                                           MentionRecord("p1", 0, -1, OTHER_NAME, 2)))
    kept = _with_mentions(_run("fx-ms"), (MentionRecord("p1", 0, -1, FAKE_NAME, 0),
                                          MentionRecord("p1", 0, -1, FAKE_NAME, 2)))
    # ADVERSARIAL. TWO conversations, each with its own stable substitute, and
    # the two substitutes differ. That is the conversation scope doing the one
    # thing that makes the single-candidate rule safe. A metric that pooled the
    # mentions across observations would print 0/2 and the report would name
    # the product's central safety property as a defect.
    other_case = replace(case, base=replace(case.base, id="fx-ms-2", conversation_id="conv-2"))
    second = _with_mentions(_run("fx-ms-2"), (MentionRecord("p1", 0, -1, OTHER_NAME, 0),
                                              MentionRecord("p1", 0, -1, OTHER_NAME, 2)))
    # SECOND CLAUSE: an item the case does NOT ask the agent to remember, read
    # in two requests with two substitutes. `stability` counts it and fails;
    # this line does not, because its population is the `MemorySpec` items —
    # the difference that makes it a second measurement rather than a second
    # printing of the first.
    plain = _obs(_plain_case("fx-ms-3", ()),
                 _with_mentions(_run("fx-ms-3"), (MentionRecord("p1", 0, -1, FAKE_NAME, 0),
                                                  MentionRecord("p1", 0, -1, OTHER_NAME, 2))), ())
    return (_fx("memory_stability", "zero", "", (_obs(case, moved, ()),), 0, 1),
            _fx("memory_stability", "one", "", (_obs(case, kept, ()),), 1, 1),
            _fx("memory_stability", "adversarial",
                "a new conversation is a new substitute, and an item nobody must remember is not counted",
                (_obs(case, kept, ()), _obs(other_case, second, ()), plain), 2, 2))


def _rag_case(case_id: str, items: tuple[PiiItem, ...], chunks: tuple[str, ...],
              foreign: tuple[str, ...]) -> CaseV5:
    case = _case(case_id, "rag", ("…",), items, ())
    return replace(case, rag=RagSpec(tool_name="kb_search", k=len(chunks), chunk_ids=chunks,
                                     foreign_identities=foreign, query_item_ids=("p1",)))


def _rag_masked_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    mine = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_seed("s1", "name"))
    theirs = _item("p9", "NAME", OTHER_NAME, OTHER_NAME, "i2", _in_seed("s2", "name"))
    one_chunk = _rag_case("fx-rag", (mine,), ("s1",), ("i2",))
    text = f"Клиент: {REAL_NAME}."
    span = (8, 8 + len(REAL_NAME))
    leaky = _with_results(_run("fx-rag"), (_result(
        "kb_search", 0, 0, "chunks", text, text, {"p1": span}, (), False),))
    clean_pieces = ((span[0], span[1], FAKE_NAME, "NAME"),)
    clean = _with_results(_run("fx-rag"), (_result(
        "kb_search", 0, 0, "chunks", text, _masked_text(text, clean_pieces), {"p1": span},
        clean_pieces, False),))
    # ADVERSARIAL. ONE chunk carrying two people; ours is masked and the other
    # person's is not. A chunk is the unit, so this is 0/1 — a metric averaging
    # over the values inside would print 1/2 and would let the half of a
    # retrieval result that belongs to a stranger be paid for by our own half.
    two_people = _rag_case("fx-rag-2", (mine, theirs), ("s1",), ("i2",))
    mixed_text = f"Клиент: {REAL_NAME}. Менеджер: {OTHER_NAME}."
    mine_span = (8, 8 + len(REAL_NAME))
    theirs_span = (mixed_text.index(OTHER_NAME), mixed_text.index(OTHER_NAME) + len(OTHER_NAME))
    both = _item("p9", "NAME", OTHER_NAME, OTHER_NAME, "i2", _in_seed("s1", "manager"))
    two_people = replace(two_people, base=replace(two_people.base, pii=(mine, both)))
    mixed_pieces = ((mine_span[0], mine_span[1], FAKE_NAME, "NAME"),)
    mixed = _with_results(_run("fx-rag-2"), (_result(
        "kb_search", 0, 0, "chunks", mixed_text, _masked_text(mixed_text, mixed_pieces),
        {"p1": mine_span, "p9": theirs_span}, mixed_pieces, False),))
    # SECOND CLAUSE: ONE identity, masked at its tagged slot and printed again
    # a few words later with no tag. `contracts` promises the leak check reads
    # the whole chunk; the span check alone called this clean.
    twice_text = f"Клиент: {REAL_NAME}. Ответственный: {REAL_NAME}."
    twice_span = (8, 8 + len(REAL_NAME))
    twice = _with_results(_run("fx-rag-3"), (_result(
        "kb_search", 0, 0, "chunks", twice_text,
        twice_text.replace(REAL_NAME, FAKE_NAME, 1), {"p1": twice_span},
        ((twice_span[0], twice_span[1], FAKE_NAME, "NAME"),), False),))
    repeated = _rag_case("fx-rag-3", (mine,), ("s1",), ("i2",))
    return (_fx("rag_masked", "zero", "", (_obs(one_chunk, leaky, ()),), 0, 1),
            _fx("rag_masked", "one", "", (_obs(one_chunk, clean, ()),), 1, 1),
            _fx("rag_masked", "adversarial",
                "two identities in one chunk, one masked; and a second, untagged rendering",
                (_obs(two_people, mixed, ()), _obs(repeated, twice, ())), 0, 2))


def _rag_identity_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    mine = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_seed("s1", "name"))
    theirs = _item("p9", "NAME", OTHER_NAME, OTHER_NAME, "i2", _in_seed("s2", "name"))
    case = _rag_case("fx-rik", (mine, theirs), ("s1", "s2"), ("i2",))
    out = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.name")
    case = replace(case, hops=(out,))
    run = _run("fx-rik")
    bled = _obs(case, run, (_seen(case, out, "NAME", OTHER_NAME, FAKE_NAME),))
    apart = _obs(case, run, (_seen(case, out, "NAME", REAL_NAME, FAKE_NAME),))
    # ADVERSARIAL. Nothing bled into the arguments — and the chunk shows the
    # CUSTOMER's substitute where the OTHER person's name stood, so the model
    # was told two people are one. A metric that only inspected the OUT
    # arguments (the obvious half) would print 1/1 and the confusion would
    # surface later, as the customer's own record updated with a stranger's data.
    text = f"Менеджер: {OTHER_NAME}."
    span = (10, 10 + len(OTHER_NAME))
    merged_run = _with_subs(_with_results(run, (_result(
        "kb_search", 0, 0, "chunks", text, text, {"p9": span},
        ((span[0], span[1], FAKE_NAME, "NAME"),), False),)), {"p1": FAKE_NAME})
    merged = _obs(case, merged_run, (_seen(case, out, "NAME", REAL_NAME, FAKE_NAME),))
    # SECOND CLAUSE (C-164): ONE VALUE, TWO OWNERS. The customer and the
    # stranger in the retrieved chunk share a phone — a shared household line,
    # the commonest way two identities collide in real data — and the agent
    # writes it into the customer's own argument. The gateway cannot tell the
    # two apart by the string, and the metric must still say the identities
    # were not kept apart; nothing in the package exercised that path.
    shared_case = _rag_case("fx-rik-2", (), (), ())
    hers = _item("p1", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_seed("s1", "phone"))
    theirs_phone = _item("p9", "PHONE", REAL_PHONE, REAL_PHONE, "i2", _in_seed("s2", "phone"))
    shared_out = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.phone")
    shared_case = replace(shared_case, base=replace(shared_case.base, pii=(hers, theirs_phone)),
                          hops=(shared_out,),
                          rag=RagSpec(tool_name="kb_search", k=2, chunk_ids=("s1", "s2"),
                                      foreign_identities=("i2",), query_item_ids=("p1",)))
    shared = _obs(shared_case, _run("fx-rik-2"),
                  (_seen(shared_case, shared_out, "PHONE", REAL_PHONE, "+79990001122"),))
    return (_fx("rag_identity_kept", "zero", "", (bled,), 0, 1),
            _fx("rag_identity_kept", "one", "", (apart,), 1, 1),
            _fx("rag_identity_kept", "adversarial",
                "one substitute for two people; and one value with two owners",
                (merged, shared), 0, 2))


def _doc_case(case_id: str, doc_format: str, extracted: tuple[str, ...],
              hops: tuple[Hop, ...]) -> CaseV5:
    case = _case(case_id, "document", ("…",), (NAME_ITEM, PHONE_ITEM), hops)
    return replace(case, document=DocumentSpec(
        doc_id="d1", read_tool="file_read", format=doc_format, record_count=2,
        record_ids=("s1",), extract_to_tool="crm_upsert_contact",
        extracted_item_ids=extracted))


def _doc_masked_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _doc_case("fx-dm", "csv", (), ())
    text = f"{REAL_NAME};{REAL_PHONE}"
    name_span, phone_span = (0, len(REAL_NAME)), (len(REAL_NAME) + 1, len(text))
    leak_pieces = ((phone_span[0], phone_span[1], "+79990001122", "PHONE"),)
    row_leak = _with_results(_run("fx-dm"), (_result(
        "file_read", 0, 0, "list", text, _masked_text(text, leak_pieces),
        {"p1": name_span, "p2": phone_span}, leak_pieces, False),))
    whole_pieces = ((name_span[0], name_span[1], FAKE_NAME, "NAME"),
                    (phone_span[0], phone_span[1], "+79990001122", "PHONE"))
    whole = _with_results(_run("fx-dm"), (_result(
        "file_read", 0, 0, "list", text, _masked_text(text, whole_pieces),
        {"p1": name_span, "p2": phone_span}, whole_pieces, False),))
    # ADVERSARIAL. A SCAN: the OCR wrote a Latin «e» inside the surname, the
    # detector did not fold it, and the span is left uncovered while every
    # other value in the document is masked. A metric that scored the document
    # by the SHARE of covered spans would print 1/1 — and scan noise is the
    # commonest way a document leaks, which is why the unit is the document.
    scan = _doc_case("fx-dm-2", "scan", (), ())
    noisy = f"Иванoва Елена;{REAL_PHONE}"
    noisy_name, noisy_phone = (0, 13), (14, len(noisy))
    scan_pieces = ((noisy_phone[0], noisy_phone[1], "+79990001122", "PHONE"),)
    bypassed = _with_results(_run("fx-dm-2"), (_result(
        "file_read", 0, 0, "free_text", noisy, _masked_text(noisy, scan_pieces),
        {"p1": noisy_name, "p2": noisy_phone}, scan_pieces, False),))
    # SECOND CLAUSE: the piece covers the slot except its LAST CHARACTER —
    # «Иванова Елен» replaced, «а» left standing. Coverage is not overlap
    # (`observe.covering_piece`), and a document is the unit: a metric using
    # `<` anywhere on that boundary would call the row masked.
    short = _doc_case("fx-dm-3", "csv", (), ())
    clip_pieces = ((name_span[0], name_span[1] - 1, FAKE_NAME, "NAME"),
                   (phone_span[0], phone_span[1], "+79990001122", "PHONE"))
    clipped = _with_results(_run("fx-dm-3"), (_result(
        "file_read", 0, 0, "list", text, _masked_text(text, clip_pieces),
        {"p1": name_span, "p2": phone_span}, clip_pieces, False),))
    return (_fx("doc_masked", "zero", "", (_obs(case, row_leak, ()),), 0, 1),
            _fx("doc_masked", "one", "", (_obs(case, whole, ()),), 1, 1),
            _fx("doc_masked", "adversarial",
                "scan noise walked past the mask; and a piece one character short covers nothing",
                (_obs(scan, bypassed, ()), _obs(short, clipped, ())), 0, 2))


def _doc_extracted_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    extract = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.name")
    case = _doc_case("fx-de", "form", ("p1",), (extract,))
    run = _run("fx-de")
    fake = _obs(case, run, (_seen(case, extract, "NAME", FAKE_NAME, FAKE_NAME),))
    real = _obs(case, run, (_seen(case, extract, "NAME", REAL_NAME, FAKE_NAME),))
    # ADVERSARIAL. A REAL value, correctly restored, from the WRONG record of
    # the same document — row two's customer in row one's field. A metric that
    # asked «did a real value arrive» rather than «did THIS item's value
    # arrive» would print 1/1, and a CSV import would quietly shuffle a
    # thousand customers.
    wrong_row = _obs(case, run, (_seen(case, extract, "NAME", OTHER_NAME, FAKE_NAME),))
    return (_fx("doc_extracted", "zero", "", (fake,), 0, 1),
            _fx("doc_extracted", "one", "", (real,), 1, 1),
            _fx("doc_extracted", "adversarial", "the real value of another row",
                (wrong_row,), 0, 1))


def _residual_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-res", (OUT_ANSWER,))
    run = _run("fx-res")
    leaked = _obs(case, run, (_unseen(case, OUT_ANSWER, "NAME", "", "", "residual"),))
    arg_case = _plain_case("fx-res-1", (OUT_ARG,))
    clean = _obs(arg_case, _run("fx-res-1"),
                 (_seen(arg_case, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME),))
    # ADVERSARIAL. The tool argument is clean and the ANSWER carries the
    # substitute the mock echoed in its error text. Two OUT hops and one
    # answer: 1 of 3. A metric that counted only tool arguments would print
    # 2/2, and the one place the customer actually reads — the answer — would
    # be the one place a substitute could hide.
    both = _plain_case("fx-res-2", (OUT_ARG, OUT_ANSWER))
    echoed = _obs(both, _run("fx-res-2"),
                  (_seen(both, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME),
                   _unseen(both, OUT_ANSWER, "NAME", "", "", "residual")))
    # SECOND CLAUSE: the agent called nothing. Two declared OUT leaves,
    # `absent` both, an empty reply — and the old line printed 3/3, the
    # critical-defect metric certifying a run in which nothing happened. An
    # absent leaf is not a leaf; it is in NEITHER half, and only the answer
    # term remains.
    idle_second = _hop("OUT", "tool_arg", "p2", 2, 0, "crm_upsert_contact", 0, -1, "contact.phone")
    idle_case = _plain_case("fx-res-3", (OUT_ARG, idle_second))
    idle = _obs(idle_case, _run("fx-res-3"),
                (_unseen(idle_case, OUT_ARG, "NAME", "", "", "absent"),
                 _unseen(idle_case, idle_second, "PHONE", "", "", "absent")))
    # THIRD CLAUSE: a substitute standing VERBATIM in the customer's answer for
    # an item the case declared no answer hop for. Read off the alignment's
    # `equal` regions it was invisible — the engine had rewritten elsewhere —
    # and the whole point of the line is that the customer reads this text.
    stray_case = _plain_case("fx-res-4", (IN_USER,))
    stray_reply = f"Готово: {FAKE_NAME}."
    stray = _obs(stray_case, _with_replies(_with_subs(_run("fx-res-4"), {"p1": FAKE_NAME}),
                                           stray_reply, stray_reply, ""),
                 (_seen(stray_case, IN_USER, "NAME", FAKE_NAME, REAL_NAME),))
    return (_fx("residual", "zero", "", (leaked,), 0, 2),
            _fx("residual", "one", "", (clean,), 2, 2),
            _fx("residual", "adversarial",
                "a substitute in the answer; an absent leaf is not a clean one; an undeclared item still leaks",
                (echoed, idle, stray), 2, 5))


FIXTURES: dict[str, tuple[Fixture, Fixture, Fixture]] = {
    "leak": _leak_fixtures(),
    "coverage": _coverage_fixtures(),
    "typed": _typed_fixtures(),
    "round_trip": _round_trip_fixtures(),
    "round_trip_repaired": _round_trip_repaired_fixtures(),
    "end_to_end": _end_to_end_fixtures(),
    "overmask": _overmask_fixtures(),
    "consistency": _consistency_fixtures(),
    "stability": _stability_fixtures(),
    "rewrite_ratio_v5": _rewrite_ratio_fixtures(),
    "shared_block_answer": _shared_block_fixtures(),
    "form_hIN": _form_in_fixtures(),
    "form_hOUT": _form_out_fixtures(),
    "out_absent": _out_absent_fixtures(),
    "stream_fidelity": _stream_fidelity_fixtures(),
    "toolresult_masked": _toolresult_masked_fixtures(),
    "answer_real": _answer_real_fixtures(),
    "chain_value": _chain_value_fixtures(),
    "chain_form": _chain_form_fixtures(),
    "multi_all_out": _multi_all_out_fixtures(),
    "multi_consistency": _multi_consistency_fixtures(),
    "retry_form": _retry_form_fixtures(),
    "memory_consistency": _memory_consistency_fixtures(),
    "memory_stability": _memory_stability_fixtures(),
    "rag_masked": _rag_masked_fixtures(),
    "rag_identity_kept": _rag_identity_fixtures(),
    "doc_masked": _doc_masked_fixtures(),
    "doc_extracted": _doc_extracted_fixtures(),
    "residual": _residual_fixtures(),
}


def main() -> int:
    from bench.agentpii5.test_fixtures import main as run_tests
    return run_tests()


if __name__ == "__main__":
    raise SystemExit(main())
