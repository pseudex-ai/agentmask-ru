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
from bench.agentpii5.metrics import NEG_TAG_PREFIX

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
                  streaming=False, revised_from_v4=False, v6=None)


def _run(case_id: str) -> ArmRunV5:
    """An empty gateway-arm record. The `_with_*` helpers below add exactly the
    half a fixture is about, so an unrelated field can never be the reason a
    fixture passes."""
    base = ArmRun(case_id=case_id, arm="I", repeat=0, calls=(), state=(), reply="",
                  termination="done", cost_usd=0.0, substitutes={}, masked_spans={})
    return ArmRunV5(base=base, reply_raw="", control_reply="", tool_results=(), mentions=(),
                    turn_replies=(), call_turns=(), request_count=1, stream_mismatch=False,
                    reply_whole="", turn_residual=0, model_trace=None)


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


def _with_turn_residual(run: ArmRunV5, turns: int) -> ArmRunV5:
    """How many of the agent's EARLIER turns still held a substitute when the
    judge prompt was built. A helper of its own because the number belongs to
    the run and not to any hop: the customer read those turns, and no hop
    observation records what stood in them."""
    return replace(run, turn_residual=turns)


def _with_results(run: ArmRunV5, results: tuple[ToolResultRecord, ...]) -> ArmRunV5:
    return replace(run, tool_results=results)


def _with_masked(run: ArmRunV5, spans: dict[int, tuple[tuple[int, int], ...]]) -> ArmRunV5:
    return replace(run, base=replace(run.base, masked_spans=spans))


def _with_message_pieces(run: ArmRunV5,
                         pieces: tuple[tuple[int, int, int, str], ...]) -> ArmRunV5:
    """The OD-76 message-piece record: (msg, start, end, engine_type) entries a
    v6 run writes for the IN/user leg (`ArmRunV5.message_pieces`). The v5 path
    never sets it, so an old-corpus replay stays byte-identical."""
    return replace(run, message_pieces=pieces)


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
# The SECOND ROW of a two-record document, as an item of the case. `record_count`
# counts people (R-30), so a CSV with two rows declares two of them — and
# `doc_extracted`'s trap only bites when the wrong value belongs to one.
ROW_TWO_ITEM = _item("p8", "NAME", OTHER_NAME, OTHER_NAME, "i2", _in_seed("s1", "manager"))

IN_USER = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
OUT_ARG = _hop("OUT", "tool_arg", "p1", 1, 0, "crm_upsert_contact", 0, -1, "contact.name")
IN_TOOL = _hop("IN", "tool", "p1", 2, 0, "crm_find_contact", 0, -1, "contacts[].name")
OUT_ANSWER = _hop("OUT", "answer", "p1", 3, 0, "", -1, -1, "")
# An answer hop the case does NOT oblige the agent to make. `_hop` builds every
# hop required, so the optional one is written once here: J1.1's fixtures turn
# on the difference and a second `replace(..., optional=True)` in two places
# would be two declarations of one fact.
OPTIONAL_ANSWER = replace(OUT_ANSWER, optional=True)


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
    #   5. a leaf the gateway never masked: the agent wrote the REAL value, so
    #      the tool DID receive it — and it is a MISS, because the model read
    #      it too. The docstring of this line used to promise the opposite
    #      («a passthrough scores 100% here»), which is the reading F1.3 made
    #      false and the one `report --selftest`'s
    #      `end_to_end_unmasked_is_a_hit` mutant takes: with no such leaf in any
    #      fixture the gate could not tell that mutant from the shipped line.
    #      The status is `not_masked` (class Е split `unmasked` in three).
    unmasked_leaf = _hop("OUT", "tool_arg", "p1", 5, 0, "crm_upsert_contact", 2, -1,
                         "contact.name")
    both = _case("fx-e2e-2", "parallel", ("…",), (NAME_ITEM, PHONE_ITEM),
                 (OUT_ARG, second, surname, patronymic, unmasked_leaf))
    mixed = _obs(both, _run("fx-e2e-2"),
                 (_seen(both, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME),
                  _unseen(both, second, "PHONE", "", "", "absent"),
                  _seen(both, surname, "NAME", "Смирнова", "Пахомова"),
                  _seen(both, patronymic, "NAME", "Сергеевна", "Олеговна"),
                  _unseen(both, unmasked_leaf, "NAME", REAL_NAME, REAL_NAME, "not_masked")))
    return (_fx("end_to_end", "zero", "", (missing,), 0, 1),
            _fx("end_to_end", "one", "", (arrived,), 1, 1),
            _fx("end_to_end", "adversarial",
                "absent stays in the denominator; a wrong part, an unsatisfiable role and a "
                "leaf the gateway never masked are misses — a metric counting such a leaf "
                "(`not_masked`) as a hit prints 2/5",
                (mixed,), 1, 5))


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
    # SECOND CLAUSE: the phone printed in TWO DIFFERENT TOOL RESULTS under two
    # different substitutes. Every result mention carries `msg == -1`
    # (`harness.push_call`), so a population keyed on `msg` alone folds both
    # results into ONE place, leaves the item out and prints 1/1 — and, because
    # no corpus item is both said in a message and echoed by a tool, that
    # reading left `consistency` with an EMPTY population on all 1 736 cases: a
    # public line that could print nothing but «н/п». A result is a place
    # (contracts §4bis is the neighbouring lesson: one definition, stated), so
    # the item is in the population and it is a MISS. `report.MUTANTS` carries
    # the `msg`-only reading and this fixture is what refuses it.
    single = one + (MentionRecord("p2", 0, -1, "+79990001122", 0),)
    result_only = one + (MentionRecord("p2", -1, 0, "+79990001122", 0),
                         MentionRecord("p2", -1, 1, "+79990009988", 0))
    return (_fx("consistency", "zero", "",
                (_obs(case, _with_mentions(_run("fx-cons"), two), ()),), 0, 1),
            _fx("consistency", "one", "",
                (_obs(case, _with_mentions(_run("fx-cons"), one), ()),), 1, 1),
            _fx("consistency", "adversarial",
                "one mention is not a population; and two tool results under two substitutes are "
                "two places — a metric keyed on `msg` alone folds them into one and prints 2/2",
                (_obs(case, _with_mentions(_run("fx-cons"), single), ()),
                 _obs(case, _with_mentions(_run("fx-cons"), result_only), ())), 2, 3))


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
    # SECOND CLAUSE: an IN hop that LEAKED. There is no substitute, so there is
    # no form to compare and the hop is OUTSIDE this line's population
    # (`contracts.METRICS`: «IN hops observed (not leaked)»); `leak` and
    # `coverage` are where a leak is counted. Nothing in the package carried a
    # leaked IN hop, so the mutant that puts leaked hops into the denominator
    # AS HITS printed 1/2 where the shipped line prints 0/1 and the gate could
    # not tell them apart («form_hIN_leaked_is_a_hit», `report --selftest`).
    leaked = _obs(case, run, (_seen(case, IN_USER, "NAME", FAKE_MALE.upper(), FAKE_MALE),
                              _unseen(case, IN_USER, "NAME", "", REAL_NAME, "leaked")))
    zero, one = _form_pair("form_hIN", IN_USER)
    return (zero, one,
            _fx("form_hIN", "adversarial",
                "same letters, other case class; and a LEAKED hop, which is in no population "
                "here — a metric counting a leaked hop as a form hit prints 1/2",
                (leaked,), 0, 1))


def _form_out_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    case = _plain_case("fx-form_hOUT", (OUT_ARG,))
    run = _run("fx-form_hOUT")
    # ADVERSARIAL, TWO CLAUSES. The first hop shouts the substitute back in
    # another letter case — the C-153 trap. The second is a leaf the gateway
    # never masked: the agent wrote the REAL value, nothing was restored, and
    # `produced == reference` made `form_match` say «same». A gateway that
    # masked NOTHING printed 100% on this line, so the fact is a MISS and stays
    # in the denominator; dropping it instead would let a passthrough score
    # «н/п» and look untested rather than broken. The status is `not_masked` —
    # what the class Е split renamed `unmasked` to on this leg, the leaf
    # already holding the real value with no substitute ever minted for it.
    trap = _obs(case, run, (_seen(case, OUT_ARG, "NAME", FAKE_MALE.upper(), FAKE_MALE),
                            _unseen(case, OUT_ARG, "NAME", REAL_NAME, REAL_NAME, "not_masked")))
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
    # SECOND CLAUSE: a declared but OPTIONAL hop the agent DID write. It is a
    # declared OUT hop, so it belongs in the denominator — `Hop.optional` says
    # the agent MAY skip it, not that the benchmark stops counting it. Nothing
    # in the package carried `optional=True` before this line, so the mutant
    # that drops optional hops from the total («out_absent_optional_dropped»,
    # `report --selftest`) printed the same number as the shipped metric.
    retry = replace(_hop("OUT", "tool_arg", "p1", 2, 0, "crm_upsert_contact", 1, -1,
                         "contact.name"), optional=True)
    with_optional = _case("fx-oa-2", "retry_same_tool", ("…",), (NAME_ITEM, PHONE_ITEM),
                          (OUT_ARG, retry))
    extra = _extra_seen(case, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME)
    mixed = _obs(case, run, (_unseen(case, OUT_ARG, "NAME", "", "", "absent"), extra))
    optional = _obs(with_optional, _run("fx-oa-2"),
                    (_unseen(with_optional, OUT_ARG, "NAME", "", "", "absent"),
                     _seen(with_optional, retry, "NAME", REAL_NAME, FAKE_NAME)))
    return (_fx("out_absent", "zero", "", (wrote,), 0, 1),
            _fx("out_absent", "one", "", (skipped,), 1, 1),
            _fx("out_absent", "adversarial",
                "an undeclared crossing is not a skipped one; a declared OPTIONAL hop the agent "
                "DID write stays in the denominator — a metric dropping optional hops prints 2/2",
                (mixed, optional), 2, 3))


# --- class Е: the split of the OUT funnel and the honest share --------------------------
#
# THE SIX STATUSES ARE SET BY HAND HERE, and that is the rule of this file: a
# fixture built by running the thing under test agrees with it by construction.
# A metric of the funnel reads `HopObservation.status` and the leaf's own value,
# so the record has to state both — and `observed` gets the value the leaf ASKS
# FOR (`tools.expected_leaf_value`), because a fixture that wrote the whole name
# into `contact.last_name` would be a miss of the value predicate and would pin
# that miss instead of the line under test.

def _leaf_value(item: PiiItem, tool: str, path: str) -> str:
    """The value a correct gateway leaves in this leaf: its part for the leaf's
    role, the whole canonical for a leaf that names no role."""
    from bench.agentpii5.tools import expected_leaf_value, spec_v5_for

    spec = spec_v5_for(tool, path)
    return item.canonical if spec is None else expected_leaf_value(item, spec)


def _leaves(case_id: str, *statuses: str, tool: str = "crm_upsert_contact",
            paths: tuple[str, ...] | None = None) -> RunObservation:
    """One handwritten observation whose declared OUT/tool_arg leaves carry
    `statuses`, in order. The paths default to the name parts of `NAME_ITEM`,
    so «observed» and «the real value» are the same thing in every fixture."""
    item = NAME_ITEM
    chosen = paths or ("contact.last_name",) * len(statuses)
    hops = [_hop("OUT", "tool_arg", item.id, index, 0, tool, index, -1, path)
            for index, path in enumerate(chosen)]
    case = _case(case_id, "single", (item.value,), (item,), tuple(hops))
    rows: list[HopObservation] = []
    for hop, status in zip(hops, statuses):
        real = _leaf_value(item, tool, hop.path)
        if status == "observed":
            rows.append(_seen(case, hop, item.type, real, FAKE_NAME))
        elif status == "residual":
            rows.append(_unseen(case, hop, item.type, FAKE_NAME, FAKE_NAME, status))
        elif status == "leaf_foreign":
            rows.append(_unseen(case, hop, item.type, OTHER_SURNAME, FAKE_NAME, status))
        else:                       # engine_kept / not_masked / absent
            rows.append(_unseen(case, hop, item.type, real, real, status))
    return _obs(case, _run(case_id), tuple(rows))


OTHER_SURNAME = "Сидорова"
# The substitute SPLIT into the parts a decomposed leaf asks for. A leaf named
# for ONE role must be compared with the ONE-role spelling of the fake: handing
# `contact.last_name` the whole «Пахомова Ольга» makes the form comparator read
# two words against one and any turn holding such a leaf a miss of the FORM —
# which is a fixture bug, not a finding.
FAKE_SURNAME, FAKE_GIVEN = FAKE_NAME.split(" ")


def _end_to_end_written_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """The honest share. The traps are the two populations it is NOT: every
    declared leaf (the strict line) and every leaf the engine never touched."""
    return (_fx("end_to_end_written", "zero", "",
                (_leaves("fx-e2ew-0", "residual"),), 0, 1),
            _fx("end_to_end_written", "one", "",
                (_leaves("fx-e2ew-1", "observed"),), 1, 1),
            _fx("end_to_end_written", "adversarial",
                "an `absent` slot and the two halves of «nothing to restore» are OUTSIDE the "
                "honest denominator: a metric keeping the corpus timetable prints 1/4, one "
                "crediting the engine-kept city for free prints 3/4",
                (_leaves("fx-e2ew-2", "absent", "engine_kept", "not_masked", "observed"),), 1, 1))


def _out_written_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """`form_hOUT`'s population, printed."""
    case = _plain_case("fx-ow-extra", (OUT_ARG,))
    extra = _extra_seen(case, OUT_ARG, "NAME", REAL_NAME, FAKE_NAME)
    skipped = _obs(case, _run("fx-ow-extra"),
                   (_unseen(case, OUT_ARG, "NAME", "", "", "absent"), extra))
    return (_fx("out_written", "zero", "", (_leaves("fx-ow-0", "absent", "absent"),), 0, 2),
            _fx("out_written", "one", "",
                (_leaves("fx-ow-1", "observed", "not_masked"),), 2, 2),
            _fx("out_written", "adversarial",
                "a crossing the case never DECLARED is not a leaf the agent owed — a metric "
                "counting every OUT hop prints 1/2",
                (skipped,), 0, 1))


def _out_no_mint_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """The population `end_to_end_written` subtracts, in one count."""
    return (_fx("out_no_mint", "zero", "",
                (_leaves("fx-onm-0", "observed", "absent"),), 0, 2),
            _fx("out_no_mint", "one", "",
                (_leaves("fx-onm-1", "engine_kept", "not_masked"),), 2, 2),
            _fx("out_no_mint", "adversarial",
                "a THIRD value in the leaf is not «nothing to restore»: a metric lumping every "
                "non-observed status prints 3/3",
                (_leaves("fx-onm-2", "engine_kept", "not_masked", "leaf_foreign"),), 2, 3))


def _out_engine_kept_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """The deliberate exception, which the two halves must not be merged into."""
    return (_fx("out_engine_kept", "zero", "",
                (_leaves("fx-oek-0", "not_masked"),), 0, 1),
            _fx("out_engine_kept", "one", "",
                (_leaves("fx-oek-1", "engine_kept"),), 1, 1),
            _fx("out_engine_kept", "adversarial",
                "a passthrough and a leftover fake are not decisions of the engine: a metric "
                "counting «the engine did not mask it» prints 3/3",
                (_leaves("fx-oek-2", "engine_kept", "not_masked", "residual"),), 1, 3))


def _out_not_masked_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """The passthrough, which is a failure of the IN leg and no decision."""
    return (_fx("out_not_masked", "zero", "",
                (_leaves("fx-onk-0", "engine_kept"),), 0, 1),
            _fx("out_not_masked", "one", "",
                (_leaves("fx-onk-1", "not_masked"),), 1, 1),
            _fx("out_not_masked", "adversarial",
                "«the leaf already held the real value» is neither a third value nor an empty "
                "slot: a metric counting every miss prints 3/3",
                (_leaves("fx-onk-2", "not_masked", "leaf_foreign", "absent"),), 1, 3))


def _out_leaf_foreign_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """The third value, which `form_match` cannot see at all."""
    return (_fx("out_leaf_foreign", "zero", "",
                (_leaves("fx-olf-0", "not_masked"),), 0, 1),
            _fx("out_leaf_foreign", "one", "",
                (_leaves("fx-olf-1", "leaf_foreign"),), 1, 1),
            _fx("out_leaf_foreign", "adversarial",
                "a leftover fake and an empty slot are not third values: a metric counting every "
                "status that is not `observed` prints 3/3",
                (_leaves("fx-olf-2", "leaf_foreign", "residual", "absent"),), 1, 3))


def _two_leaf_case(case_id: str) -> tuple[CaseV5, Hop, Hop]:
    """One turn, two declared non-optional OUT leaves — `_multi_turns`'
    population, the one g02's 56 turns are counted over."""
    first = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    second = _hop("OUT", "tool_arg", "p1", 1, 0, "crm_upsert_contact", 1, -1, "contact.first_name")
    return _case(case_id, "parallel", (REAL_NAME,), (NAME_ITEM,), (first, second)), first, second


def _multi_all_out_written_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """The honest twin of `multi_all_out`: 55 of g02's 56 turns had neither
    leaf written and the strict line read 0/56 — a fact about the scene."""
    case, first, second = _two_leaf_case("fx-maow")
    broke = _obs(case, _run("fx-maow"),
                 (_unseen(case, first, "NAME", OTHER_SURNAME, FAKE_SURNAME, "leaf_foreign"),
                  _unseen(case, second, "NAME", "", "", "absent")))
    whole = _obs(case, _run("fx-maow"),
                 (_seen(case, first, "NAME", "Иванова", FAKE_SURNAME),
                  _seen(case, second, "NAME", "Елена", FAKE_GIVEN)))
    # ADVERSARIAL. The turn where the agent wrote ONE of the two leaves and got
    # it right is OUTSIDE `multi_all_out`'s «every argument» reading and INSIDE
    # this one (1/1); a metric that demanded every declared leaf would print
    # 0/1 and score the agent down for a scene that never offered the second.
    # SECOND CLAUSE: both values right, one in the tool's CANON form — the value
    # half passes and the form half fails, as `multi_all_out`'s own ruling says.
    half_case, half_first, half_second = _two_leaf_case("fx-maow-2")
    half = _obs(half_case, _run("fx-maow-2"),
                (_unseen(half_case, half_first, "NAME", "Иванова", FAKE_SURNAME, "not_masked"),
                 _seen(half_case, half_second, "NAME", "Елена", FAKE_GIVEN)))
    form_case, form_first, form_second = _two_leaf_case("fx-maow-3")
    formless = _obs(form_case, _run("fx-maow-3"),
                    (_seen(form_case, form_first, "NAME", "Иванова", FAKE_SURNAME),
                     _seen(form_case, form_second, "NAME", "Елена", "ЕЛЕНА")))
    return (_fx("multi_all_out_written", "zero", "", (broke,), 0, 1),
            _fx("multi_all_out_written", "one", "", (whole,), 1, 1),
            _fx("multi_all_out_written", "adversarial",
                "one written leaf of a two-leaf turn is judged on what was written; and the "
                "right value in the tool's canon form still fails — a metric checking the value "
                "alone prints 2/2",
                (half, formless), 1, 2))


def _chain_written_pair(case_id: str, out_status: str, produced: str) -> RunObservation:
    """An A→B transition whose OUT(B) leaf carries `out_status`."""
    case, source, target = _chain_case(case_id, "p1", (NAME_ITEM,))
    written = (_seen(case, source, "NAME", FAKE_NAME, REAL_NAME),
               _seen(case, target, "NAME", produced, FAKE_NAME) if out_status == "observed"
               else _unseen(case, target, "NAME", produced, FAKE_NAME, out_status))
    return _obs(case, _run(case_id), written)


def _chain_value_written_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """`chain_value` over the hand-overs the engine was asked to perform."""
    other = _item("p9", "NAME", OTHER_NAME, OTHER_NAME, "i2", _in_seed("s2", "name"))
    cross_case, cross_source, cross_target = _chain_case("fx-cvw-3", "p9", (NAME_ITEM, other))
    crossed = _obs(cross_case, _run("fx-cvw-3"),
                   (_seen(cross_case, cross_source, "NAME", FAKE_NAME, REAL_NAME),
                    _seen(cross_case, cross_target, "NAME", REAL_NAME, FAKE_NAME)))
    absent_case, absent_source, absent_target = _chain_case("fx-cvw-4", "p1", (NAME_ITEM,))
    silent = _obs(absent_case, _run("fx-cvw-4"),
                  (_seen(absent_case, absent_source, "NAME", FAKE_NAME, REAL_NAME),
                   _unseen(absent_case, absent_target, "NAME", "", "", "absent")))
    return (_fx("chain_value_written", "zero", "",
                (_chain_written_pair("fx-cvw-0", "leaf_foreign", OTHER_SURNAME),), 0, 1),
            _fx("chain_value_written", "one", "",
                (_chain_written_pair("fx-cvw-1", "observed", REAL_NAME),), 1, 1),
            _fx("chain_value_written", "adversarial",
                "the right string for ANOTHER person is a miss; and an A→B whose B the agent "
                "never wrote is outside this denominator (a metric over every scheduled "
                "transition prints 0/2)",
                (crossed, silent), 0, 1))


def _chain_form_written_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """The same population, the form question."""
    return (_fx("chain_form_written", "zero", "",
                (_chain_written_pair("fx-cfw-0", "observed", "ИВАНОВА ЕЛЕНА"),), 0, 1),
            _fx("chain_form_written", "one", "",
                (_chain_written_pair("fx-cfw-1", "observed", REAL_NAME),), 1, 1),
            _fx("chain_form_written", "adversarial",
                "a substitute still standing (`residual`) is in the population and has no form to "
                "compare, while a leaf the engine never masked is outside it — a metric over "
                "every written leaf prints 0/2",
                (_chain_written_pair("fx-cfw-2", "residual", OTHER_SURNAME),
                 _chain_written_pair("fx-cfw-3", "not_masked", REAL_NAME)), 0, 1))


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
    # ADVERSARIAL, THIRD CLAUSE — THE V4 DISEASE ON THIS LEG (J1.1). The case
    # declares ONE answer hop and obliges none of it; the gateway masked
    # nothing, so the hop is `unmasked`, nothing is residual and there is no
    # substitute in the reply. `required` is empty, `all([])` is True, and the
    # pre-J1.1 body counted this a HIT — which is how a full passthrough
    # printed 53.1% over the real corpus (720 of 1357 answers declare no
    # required hop). Outside the denominator, so the fixture's total stays 2
    # and a metric that keeps the old reading prints 1/3.
    optional_case = _plain_case("fx-ar-3", (OPTIONAL_ANSWER,))
    passthrough = _obs(optional_case, _run("fx-ar-3"),
                       (_unseen(optional_case, OPTIONAL_ANSWER, "NAME",
                                REAL_NAME, REAL_NAME, "unmasked"),))
    return (_fx("answer_real", "zero", "", (left,), 0, 1),
            _fx("answer_real", "one", "", (good,), 1, 1),
            _fx("answer_real", "adversarial",
                "the real value in a foreign form, another person's in the right one, and a "
                "PASSTHROUGH on a case that obliges nothing — the old body printed 1/3",
                (canon, wrong_person, passthrough), 0, 2))


def _answer_optional_only_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    """The count `answer_real` leaves out of its denominator, as its own line.

    `out_absent` is the precedent and the reason: a denominator that shrinks
    without saying so is exactly how «all() over an empty list» survived v4,
    and a reader cannot tell 637 judged answers from 1357 unless the 720 are
    printed."""
    required_case = _plain_case("fx-aoo-req", (OUT_ANSWER,))
    required = _obs(required_case, _run("fx-aoo-req"),
                    (_seen(required_case, OUT_ANSWER, "NAME", REAL_NAME, REAL_NAME),))
    optional_case = _plain_case("fx-aoo-opt", (OPTIONAL_ANSWER,))
    optional = _obs(optional_case, _run("fx-aoo-opt"),
                    (_seen(optional_case, OPTIONAL_ANSWER, "NAME", REAL_NAME, REAL_NAME),))
    # ADVERSARIAL, TWO CLAUSES. (1) a case with NO answer hop at all: it is in
    # neither population — the corpus asks the agent to name nothing, so there
    # is no answer to judge and none to exclude — and a metric counting «no
    # required hop» over every observation would print 2/3. (2) a case with one
    # optional AND one required hop: `answer_real` judges it, so it is not an
    # exclusion, and a metric asking «is any hop optional» would print 3/3.
    silent = _obs(_plain_case("fx-aoo-none", ()), _run("fx-aoo-none"), ())
    mixed_hop = _hop("OUT", "answer", "p2", 4, 0, "", -1, -1, "")
    mixed_case = _plain_case("fx-aoo-mix", (OPTIONAL_ANSWER, mixed_hop))
    mixed = _obs(mixed_case, _run("fx-aoo-mix"),
                 (_seen(mixed_case, OPTIONAL_ANSWER, "NAME", REAL_NAME, REAL_NAME),
                  _seen(mixed_case, mixed_hop, "PHONE", REAL_PHONE, REAL_PHONE)))
    return (_fx("answer_optional_only", "zero", "", (required,), 0, 1),
            _fx("answer_optional_only", "one", "", (optional,), 1, 1),
            _fx("answer_optional_only", "adversarial",
                "an answer nobody declared is in neither population (a wrong metric prints 2/3), "
                "and one optional hop beside a required one is not an exclusion (3/3)",
                (optional, silent, mixed), 1, 2))


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


# `_memory_stability_fixtures` STOOD HERE AND IS REMOVED WITH ITS METRIC
# (J1.2). The fixtures were sound — a `MemorySpec` item read in two requests
# with two substitutes, a second conversation that is not a failure, an item
# nobody must remember — and that is precisely what made them misleading: they
# built by hand the only population the line could ever have. On the real
# corpus all 619 memory specs have their mentions in ONE request, so the line
# printed 0/0 there and no wrong gateway could move it. A fixture population
# the corpus cannot produce is a gate that only ever tests the fixture.


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
    # THIRD CLAUSE (F1.7). The chunk the case DECLARES came back rendered RAW,
    # tagged by nothing. `if not spans: continue` dropped it from the
    # denominator, so a retrieval leg that put the customer's name into the
    # model's context printed «н/п» — «the chunk never came back» and «the
    # chunk came back unmasked» were one state.
    untagged_case = _rag_case("fx-rag-4", (mine,), ("s1",), ("i2",))
    untagged = _with_results(_run("fx-rag-4"), (_result(
        "kb_search", 0, 0, "chunks", text, text, {}, (), False),))
    return (_fx("rag_masked", "zero", "", (_obs(one_chunk, leaky, ()),), 0, 1),
            _fx("rag_masked", "one", "", (_obs(one_chunk, clean, ()),), 1, 1),
            _fx("rag_masked", "adversarial",
                "two identities in one chunk, one masked; a second, untagged rendering; "
                "and a DECLARED chunk returned with no tag at all — a metric keyed on what "
                "the mock tagged prints 0/2 and calls the third «not applicable»",
                (_obs(two_people, mixed, ()), _obs(repeated, twice, ()),
                 _obs(untagged_case, untagged, ())), 0, 3))


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
    # THIRD CLAUSE (F1.7). The document came back rendered RAW, tagged by
    # nothing: `all(_record_clean(...))` iterated an empty `spans_real` and
    # printed a perfect hit for a document whose every real value reached the
    # model — v4's «all() over an empty list», on the document family.
    raw_case = _doc_case("fx-dm-4", "csv", (), ())
    untagged = _with_results(_run("fx-dm-4"), (_result(
        "file_read", 0, 0, "list", text, text, {}, (), False),))
    return (_fx("doc_masked", "zero", "", (_obs(case, row_leak, ()),), 0, 1),
            _fx("doc_masked", "one", "", (_obs(case, whole, ()),), 1, 1),
            _fx("doc_masked", "adversarial",
                "scan noise walked past the mask; a piece one character short covers nothing; "
                "and a document returned with NO tags at all — a metric verdicting over "
                "`spans_real` alone prints 1/3 and certifies the untagged one as clean",
                (_obs(scan, bypassed, ()), _obs(short, clipped, ()),
                 _obs(raw_case, untagged, ())), 0, 3))


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
    #
    # ROW TWO'S PERSON IS A DECLARED ITEM OF THE CASE, and that is the whole
    # trap. While `OTHER_NAME` was carried by no item, the two readings the
    # note distinguishes — «did A value of the case arrive» and «did THIS
    # item's value arrive» — printed the same 0/1, so the loosest of them
    # passed the gate (`report --selftest` mutant `doc_extracted_any_real`).
    # A document declaring `record_count=2` has an item per row, which is
    # exactly the shuffled-CSV failure the note describes.
    two_rows = replace(case, base=replace(case.base, pii=(NAME_ITEM, PHONE_ITEM, ROW_TWO_ITEM)))
    wrong_row = _obs(two_rows, run, (_seen(two_rows, extract, "NAME", OTHER_NAME, FAKE_NAME),))
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
    # FOURTH CLAUSE (R-54): the FINAL answer is clean and an EARLIER turn was
    # not — the customer read «Пахомова Ольга» in turn 2 and a correct name in
    # turn 3. `turn_residual` counted it on the triple row, where no metric
    # could reach it, and this line printed 1/1: the critical-defect metric
    # certifying a run in which a fake reached a human.
    earlier_case = _plain_case("fx-res-5", (IN_USER,))
    earlier = _obs(earlier_case,
                   _with_turn_residual(_with_replies(_run("fx-res-5"), "", REAL_NAME, ""), 1),
                   (_seen(earlier_case, IN_USER, "NAME", FAKE_NAME, REAL_NAME),))
    return (_fx("residual", "zero", "", (leaked,), 0, 2),
            _fx("residual", "one", "", (clean,), 2, 2),
            _fx("residual", "adversarial",
                "a substitute in the answer; an absent leaf is not a clean one; an undeclared "
                "item still leaks; a clean answer after a turn that was not",
                (echoed, idle, stray, earlier), 2, 6))


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
    "end_to_end_written": _end_to_end_written_fixtures(),
    "out_written": _out_written_fixtures(),
    "out_no_mint": _out_no_mint_fixtures(),
    "out_engine_kept": _out_engine_kept_fixtures(),
    "out_not_masked": _out_not_masked_fixtures(),
    "out_leaf_foreign": _out_leaf_foreign_fixtures(),
    "multi_all_out_written": _multi_all_out_written_fixtures(),
    "chain_value_written": _chain_value_written_fixtures(),
    "chain_form_written": _chain_form_written_fixtures(),
    "stream_fidelity": _stream_fidelity_fixtures(),
    "toolresult_masked": _toolresult_masked_fixtures(),
    "answer_real": _answer_real_fixtures(),
    "answer_optional_only": _answer_optional_only_fixtures(),
    "chain_value": _chain_value_fixtures(),
    "chain_form": _chain_form_fixtures(),
    "multi_all_out": _multi_all_out_fixtures(),
    "multi_consistency": _multi_consistency_fixtures(),
    "retry_form": _retry_form_fixtures(),
    "memory_consistency": _memory_consistency_fixtures(),
    "rag_masked": _rag_masked_fixtures(),
    "rag_identity_kept": _rag_identity_fixtures(),
    "doc_masked": _doc_masked_fixtures(),
    "doc_extracted": _doc_extracted_fixtures(),
    "residual": _residual_fixtures(),
}


# --- §6.3 the three v6 rows (OD-54) ---------------------------------------------------
#
# Each ships its own zero / one / adversarial, exactly like a v5 metric, but in a
# SEPARATE table: `FIXTURES` is the closed v5 surface `test_fixtures` pins, and a
# v6 row registered there would turn the v5 gate red without a v6 case anywhere.
# The report gates these rows on a v6 case and runs them against this table.


def _enp_item(item_id: str, value: str, start: int, end: int) -> PiiItem:
    """An OMS_ENP item: a Luhn checksum type with `engine_labels` = («OMS»,)."""
    return _item(item_id, "OMS_ENP", value, value, "i1", _in_message(0, start, end))


def _typed_user_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    item = _enp_item("e1", "7707536455681514", 0, 16)
    hop = _hop("IN", "user", "e1", 0, 0, "", -1, -1, "")
    case = _case("fx-typed_user", "single", ("7707536455681514",), (item,), (hop,))

    def one(engine_type: str) -> RunObservation:
        run = _with_message_pieces(_run("fx-typed_user"), ((0, 0, 16, engine_type),))
        return _obs(case, run, (_seen(case, hop, "OMS_ENP", "0030869788914847", item.value),))

    # ADVERSARIAL. ONE piece covers the ENP and the customer's NAME, labelled
    # OMS: the ENP hop is a hit (OMS is its alias), the NAME hop is a miss (OMS
    # is nobody's alias for a name). Counted per HOP it is 1/2; a metric that
    # counted PIECES instead of hops prints 1/1.
    name_item = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 17, 17 + len(REAL_NAME)))
    name_hop = _hop("IN", "user", "p1", 1, 0, "", -1, -1, "")
    both_case = _case("fx-typed_user-2", "single",
                      (f"7707536455681514 {REAL_NAME}",), (item, name_item), (hop, name_hop))
    shared_run = _with_message_pieces(_run("fx-typed_user-2"),
                                      ((0, 0, 17 + len(REAL_NAME), "OMS"),))
    shared = _obs(both_case, shared_run,
                  (_seen(both_case, hop, "OMS_ENP", "0030869788914847", item.value),
                   _seen(both_case, name_hop, "NAME", FAKE_NAME, REAL_NAME)))
    return (_fx("typed_user", "zero", "", (one("CARD"),), 0, 1),
            _fx("typed_user", "one", "", (one("OMS"),), 1, 1),
            _fx("typed_user", "adversarial", "one piece covering the ENP and a name "
                "is two hops — counted per piece a wrong metric prints 1/1", (shared,), 1, 2))


def _fake_checksum_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    item = _enp_item("e1", "7707536455681514", 0, 16)
    case = _case("fx-fcs", "single", ("7707536455681514",), (item,), ())

    def one(substitute: str) -> RunObservation:
        return _obs(case, _with_subs(_run("fx-fcs"), {"e1": substitute}), ())

    # ADVERSARIAL. The substitute is GROUPED with spaces and its digit run IS
    # Luhn-valid («7707536455681514»). The correct metric folds by
    # `value_notation` and sees a valid substitute — not an invalid one — so it
    # prints 0/1; a metric that feeds the raw grouped string to the validator
    # rejects it for its spaces and prints 1/1.
    return (_fx("fake_checksum_invalid", "zero", "",
                (one("7707536455681514"),), 0, 1),
            _fx("fake_checksum_invalid", "one", "",
                (one("7707536455681515"),), 1, 1),
            _fx("fake_checksum_invalid", "adversarial",
                "a grouped substitute whose digit run IS valid — the correct metric strips "
                "the separators (0/1), a raw-string metric prints 1/1",
                (one("7707 5364 5568 1514"),), 0, 1))


def _overmask_result_fixtures() -> tuple[Fixture, Fixture, Fixture]:
    # A statement result carrying a BIK NEGATIVE tagged in `spans_real` under
    # `NEG_TAG_PREFIX`. `text_real` is the mock's output; `text_masked` is what
    # the model read after the gateway's `pieces` were laid down.
    real = "БИК 044525225, счёт 0445252259876543210987"
    bik_span = (4, 13)

    def case_with(pieces: tuple[tuple[int, int, str, str], ...], masked: str) -> RunObservation:
        case = _plain_case("fx-omr", ())
        run = _with_results(_run("fx-omr"), (_result(
            "account_statement", 0, 0, "list", real, masked,
            {NEG_TAG_PREFIX + "n1": bik_span}, pieces, False),))
        return _obs(case, run, ())

    masked = case_with(((bik_span[0], bik_span[1], "000000000", "BIK"),),
                       "БИК 000000000, счёт 0445252259876543210987")
    free = case_with((), real)
    # ADVERSARIAL. The BIK is MASKED (over-masking, the defect) while its digits
    # also OPEN the neighbouring account, which is left standing. A span-reading
    # metric sees the BIK's own slot covered and prints 0/1; a needle-reading
    # metric finds «044525225» inside the account and reports a survival (1/1).
    return (_fx("overmask_result", "zero", "", (masked,), 0, 1),
            _fx("overmask_result", "one", "", (free,), 1, 1),
            _fx("overmask_result", "adversarial",
                "the BIK is masked and its digits open the neighbouring account — a span "
                "metric prints 0/1, a needle metric finds the digits in the account and "
                "prints 1/1",
                (masked,), 0, 1))


# The OD-54 rows' fixtures. NOT in `FIXTURES` (the v5 gate); `report` runs them
# through the same `report.gate` shape only on a v6 run (TZ §6.3).
V6_FIXTURES: dict[str, tuple[Fixture, Fixture, Fixture]] = {
    "typed_user": _typed_user_fixtures(),
    "fake_checksum_invalid": _fake_checksum_fixtures(),
    "overmask_result": _overmask_result_fixtures(),
}


def main() -> int:
    from bench.agentpii5.test_fixtures import main as run_tests
    return run_tests()


if __name__ == "__main__":
    raise SystemExit(main())
