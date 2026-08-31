"""The transparency verdict: did masking change what the agent did.

THE REFERENCE IS THE PLAIN ARM, NOT THE CORPUS, and that is the whole design.
`expected_call` says what a correct agent would do; it cannot say what THIS model
would have done, and the difference between those two is where every honest
transparency number lives. A masked run that misses the corpus's expected call
proves nothing on its own — the plain run may have missed it too, for reasons
that have nothing to do with masking. Only A against B separates «the gateway
broke it» from «the model decided that itself».

WHAT A/B STILL CANNOT SEPARATE, stated up front: the model is not deterministic,
so an A/B difference may be the model disagreeing with itself. That is measured,
not assumed away — `run.py --self-control` runs the plain arm TWICE and scores
A1 against A2 through this same comparator, which puts a floor under the number.
A transparency rate reported without that floor beside it is a rate a reader will
mistake for the gateway's contribution.

THE DIVERGENCE TAXONOMY IS `schema.BREAK_KINDS`, NOT A NEW ONE. When an argument
differs, `schema.classify_break` names how — `other_person`, `inflected`,
`truncated`, `not_resolved` — because the round-trip axis already paid for those
names and a second taxonomy for the same phenomenon would let two numbers in one
repository disagree about what happened. Only the shapes that axis cannot see get
new names here, and there are three: a different tool was chosen, an argument
appeared or vanished, and one arm made no call at all.

ATTRIBUTION IS DELIBERATELY SPARSE. Exactly one divergence class is charged to
the gateway with no argument: `residual`, a minted substitute still standing in
an argument the tool executed on. Everything else is `неотнесено` and the
self-control arm is what a reader must use to interpret it. Guessing per case
would produce a confident split that the run has no evidence for.
"""

from dataclasses import dataclass, field

from bench.agentpii2.live.agent import ArmResult, ObservedCall, strip_prefix
from bench.agentpii2.schema import Case, classify_break, same_value

# Divergences this file names because no other axis can. Everything else reuses
# `schema.BREAK_KINDS`.
STRUCTURAL: tuple[str, ...] = (
    "tool_choice",       # a different function, or a different order
    "argument_missing",  # the masked arm dropped an argument the plain arm sent
    "argument_extra",    # the masked arm invented one the plain arm did not send
    "masked_absent",     # the plain arm called, the masked arm did not
    "plain_absent",      # the masked arm called, the plain arm did not
    "answer",            # the closed answer the `compare` family demands differs
)


@dataclass(frozen=True)
class Divergence:
    kind: str
    position: int
    tool: str
    key: str
    plain: str
    masked: str
    attribution: str    # "шлюз" only where it is not a guess; else "неотнесено"


def pii_params(case: Case) -> frozenset[str]:
    """The arguments the CORPUS says carry a personal value.

    The first live run is why this exists. On
    `transfer-split_name_bare-voice_raw-hard-00` the masked text differed from
    the plain one in two names and NOTHING else — and the arms still disagreed,
    because the case is `voice_raw` and both models had to hear an order number
    out of «заявка восемь три семь семь две позиции». One read 8377, the other
    83772. That is the model transcribing, not the gateway masking, and a
    benchmark that charges it to the gateway is measuring ASR ambiguity.

    On `length-long` the same shape appeared in a `summary` the model composes in
    its own words: «не звонить ночью» against «не звонить в ночное время». No
    gateway can make two runs phrase that identically and none should try.

    So a SECOND number is reported beside the strict one, over the arguments the
    corpus itself declared as carrying personal data — never instead of it, and
    never merged. Strict answers «did anything change»; this one answers «did a
    PERSON'S VALUE change», and only the second is the product's business. The
    set comes from `PiiItem.tool_param`, which is corpus metadata written before
    any of this ran, so the scorer is not choosing which divergences to forgive.
    """
    return frozenset(item.tool_param for item in case.pii if item.tool_param)


@dataclass
class Verdict:
    tools_same: bool = False
    arguments_same: bool = False
    pii_arguments_same: bool = False
    answer_same: bool | None = None
    residual: list[str] = field(default_factory=list)
    divergences: list[Divergence] = field(default_factory=list)
    plain_called: bool = False
    masked_called: bool = False
    control_matches_corpus: bool | None = None

    @property
    def transparent(self) -> bool:
        """Both arms did the same thing AND no fake reached a tool.

        A residual can coexist with arguments that compare equal — the token
        resolved to a string that happens to match — so it is checked apart and
        vetoes the verdict on its own.

        THE CLOSED ANSWER COUNTS TOO, and the first live run is why. On
        `cmp0070-same-place-clean` the tool call round-tripped perfectly — the
        real address arrived — and the model told the customer the two addresses
        were DIFFERENT, because the same place got two substitutes. A headline
        reading 100% beside that would be describing the tool call and calling it
        the agent's behaviour. The three components stay printed apart; only the
        headline conjoins them.
        """
        return (self.tools_same and self.arguments_same and not self.residual
                and self.answer_same is not False
                and not (self.plain_called ^ self.masked_called))

    @property
    def transparent_on_pii(self) -> bool:
        """The same verdict restricted to arguments the corpus says carry a
        person. Printed BESIDE `transparent`, never instead of it."""
        return (self.tools_same and self.pii_arguments_same and not self.residual
                and self.answer_same is not False
                and not (self.plain_called ^ self.masked_called))


def _stringify(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _names(calls: tuple[ObservedCall, ...]) -> list[str]:
    return [strip_prefix(call.name) for call in calls]


def _others(case: Case, value: str) -> frozenset[str]:
    """Canonical values of every OTHER identity in the case, for
    `classify_break`'s worst branch. Matched to the argument by which gold item
    the plain arm's value belongs to, so a name is compared against other people
    and never against an address."""
    owner = next((item for item in case.pii
                  if same_value(value, item.canonical) or same_value(value, item.value)),
                 None)
    if owner is None:
        return frozenset()
    return frozenset(item.canonical for item in case.pii
                     if item.identity != owner.identity and item.type == owner.type)


def _answer(text: str) -> str | None:
    """The closed answer the `compare` family demands, parsed to one of two
    values or to nothing.

    A substring test is what WebArena does and ABC measured it at 1.4-5.2%
    inflation: a reply containing «нет» inside «нет, это тот же адрес» is graded
    as «нет». So the FIRST of the two words to appear decides, and a reply
    carrying neither is `None` rather than a default — a model that answered
    something else must not be silently scored as having answered «нет».
    """
    lowered = text.casefold()
    yes = min((lowered.find(word) for word in ("да", "тот же", "совпада")
               if lowered.find(word) >= 0), default=-1)
    no = min((lowered.find(word) for word in ("нет", "не тот", "не совпада",
                                              "друг") if lowered.find(word) >= 0),
             default=-1)
    if yes < 0 and no < 0:
        return None
    if no < 0 or (yes >= 0 and yes < no):
        return "да"
    return "нет"


def compare_calls(case: Case, plain: ArmResult, masked: ArmResult,
                  restored: list[dict[str, object]], residual: list[str]) -> Verdict:
    """A against B. `restored` is the masked arm's arguments AFTER
    `unmask_arguments`, one dict per call, in the same order as `masked.calls`.

    Comparison is by POSITION, not by an unordered set. BFCL's response checker
    accepts an unordered subset and calls a different trajectory correct; that
    leniency is right for «did the task get done» and wrong here, where the
    question is whether the sequence changed at all.
    """
    verdict = Verdict()
    verdict.residual = list(residual)
    verdict.plain_called = bool(plain.calls)
    verdict.masked_called = bool(masked.calls)

    plain_names, masked_names = _names(plain.calls), _names(masked.calls)
    verdict.tools_same = plain_names == masked_names

    if verdict.plain_called and not verdict.masked_called:
        verdict.divergences.append(Divergence(
            kind="masked_absent", position=0, tool=plain_names[0], key="",
            plain=",".join(plain_names), masked="", attribution="неотнесено"))
    if verdict.masked_called and not verdict.plain_called:
        verdict.divergences.append(Divergence(
            kind="plain_absent", position=0, tool=masked_names[0], key="",
            plain="", masked=",".join(masked_names), attribution="неотнесено"))

    for position in range(min(len(plain_names), len(masked_names))):
        if plain_names[position] != masked_names[position]:
            verdict.divergences.append(Divergence(
                kind="tool_choice", position=position, tool=plain_names[position],
                key="", plain=plain_names[position], masked=masked_names[position],
                attribution="неотнесено"))

    arguments_same = True
    pii_same = True
    carriers = pii_params(case)
    for position in range(min(len(plain.calls), len(masked.calls))):
        if plain_names[position] != masked_names[position]:
            # A different function has different parameters; comparing their
            # arguments would report a second divergence for one decision.
            arguments_same = False
            pii_same = False
            continue
        left = {key: _stringify(value)
                for key, value in plain.calls[position].arguments.items()}
        right = dict(restored[position]) if position < len(restored) else {}
        right = {key: _stringify(value) for key, value in right.items()}
        for key in sorted(set(left) | set(right)):
            if key not in right:
                arguments_same = False
                pii_same = pii_same and key not in carriers
                verdict.divergences.append(Divergence(
                    kind="argument_missing", position=position,
                    tool=plain_names[position], key=key, plain=left[key],
                    masked="", attribution="неотнесено"))
            elif key not in left:
                arguments_same = False
                pii_same = pii_same and key not in carriers
                verdict.divergences.append(Divergence(
                    kind="argument_extra", position=position,
                    tool=plain_names[position], key=key, plain="",
                    masked=right[key], attribution="неотнесено"))
            elif not same_value(right[key], left[key]):
                arguments_same = False
                pii_same = pii_same and key not in carriers
                verdict.divergences.append(Divergence(
                    kind=classify_break(left[key], right[key], _others(case, left[key])),
                    position=position, tool=plain_names[position], key=key,
                    plain=left[key], masked=right[key], attribution="неотнесено"))
    verdict.arguments_same = arguments_same and verdict.tools_same
    verdict.pii_arguments_same = pii_same and verdict.tools_same

    for token in residual:
        verdict.divergences.append(Divergence(
            kind="residual", position=0, tool=masked_names[0] if masked_names else "",
            key="", plain="", masked=token, attribution="шлюз"))

    if case.family == "compare" and case.expected_answer:
        left_answer, right_answer = _answer(plain.final_text), _answer(masked.final_text)
        verdict.answer_same = left_answer == right_answer
        if not verdict.answer_same:
            verdict.divergences.append(Divergence(
                kind="answer", position=0, tool="", key="expected_answer",
                plain=left_answer or "<нет ответа>", masked=right_answer or "<нет ответа>",
                attribution="неотнесено"))
    return verdict


def control_matches(case: Case, plain: ArmResult) -> bool | None:
    """Did the PLAIN arm do what the corpus expects — the capability control.

    `None` when the case states no expected call, which is most of `result` and
    all of `scope`: those cases are still valid A/B measurements and must not be
    scored against a contract they do not carry.

    Matched as an ordered SUBSEQUENCE of names. Extra calls do not fail it — a
    model is allowed to look something up twice — and the corpus's own
    `ExpectedCall` docstring says exactly that. Arguments are not checked here:
    whether the plain arm's arguments were right is the offline round trip's
    question, and answering it twice with two different rules would give the
    repository two numbers that can disagree.
    """
    if not case.calls:
        return None
    wanted = [call.name for call in case.calls]
    seen = iter(_names(plain.calls))
    return all(any(name == want for name in seen) for want in wanted)
