"""THE RIGHT GATEWAY, simulated — the instrument's own acceptance probe.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.perfect              # the acceptance tier, ~2 s
    python3 -m bench.agentpii5.perfect --tier max   # the whole corpus, ~20 s

Every metric line of this benchmark answers «did the gateway do what the
product promises». A line that a RIGHT gateway cannot earn is a broken line,
and until round 5 the evidence that our lines can be earned lived in a scratch
file under `/tmp` that needed THREE corrections to become honest — two of them
probe bugs worth twelve points of `round_trip` / `end_to_end` /
`multi_all_out`. Nobody could re-check the claim, which is the one thing a
private benchmark cannot afford. So the probe moved here, beside the code it
certifies.

WHAT THIS IS. For every `CaseV5` of the corpus it builds the `ArmRunV5` that a
gateway doing exactly the right thing — and an agent obeying the case — would
leave behind: every declared hop performed, every value masked on the way in,
every value restored on the way out in the agent's own form, one substitute per
identity for the whole conversation. Then it runs the package's OWN
`observe.observe` and `metrics.METRIC_FUNCTIONS` over those records.

WHAT THIS IS NOT. Nothing here computes a verdict. The simulation only writes
records; every number comes from the package's own code, so a probe that
flattered the gateway could not also move a metric. It calls no model, opens no
socket and never imports the engine — it is the corpus, the tool registry and
arithmetic.

THE THREE CORRECTIONS ARE THE SPECIFICATION (§2). Each is a statement about
what a right gateway does, each is labelled with what the probe printed while
it was wrong, and each has a test that falls when it is reverted
(`test_perfect.py`). Read them before changing anything here: they are the
places where a plausible simulation charges the gateway for the probe's own
bookkeeping.

THE OTHER HALF lives in `test_perfect.py`: four wrong gateways must FAIL the
same bounds this one clears. An acceptance test a wrong gateway can also pass
is not an acceptance test.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from bench.agentpii4.compare import ArmRun, ObservedCall
from bench.agentpii4.schema import Ladder, PiiItem, tier
from bench.agentpii5 import contracts, metrics, observe
from bench.agentpii5.contracts import (ArmRunV5, CaseV5, Line, MentionRecord, RunObservation,
                                       ToolResultRecord)
from bench.agentpii5.metrics import parts_of
from bench.agentpii5.schema import case_v5_from_json
from bench.agentpii5.tools import REGISTRY_V5, expected_leaf_value, spec_v5_for

HERE = pathlib.Path(__file__).resolve().parent
CORPUS_PATH = HERE / "corpus.v5.json"
LADDER_PATH = HERE / "ladder.json"

# The six v4 level lines (`action` … `verbatim`) compare the gateway arm with a
# CONTROL arm and need two `PairVerdict`s, so a single-arm probe cannot measure
# them at all and they carry no metric function here. This tuple is what
# `test_perfect.py` demands a bound for — all of it, and nothing outside it.
SINGLE_ARM_METRICS: tuple[str, ...] = tuple(
    name for name in contracts.METRIC_NAMES if name in metrics.METRIC_FUNCTIONS)


# --- §1 the substitute a right gateway mints ---------------------------------------
#
# Same shape, same notation, same part count, a different lexeme. This is not a
# copy of `pseudex/vault.py` — it is the PROMISE that code makes, written out
# offline, and each rule below exists because breaking it made the simulation
# invent a gateway defect that only belonged to the simulation.

_CYR_MAP = str.maketrans(
    "абвгдежзийклмнопрстуфхцчшщъыьэюя",
    "оевзыджлнпрбткмафухчцшщъисьэюягд")
_LAT_MAP = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ovezydjlnpbrtkmafuhcwsxqig")

# The generic vocabulary an address wears. `pseudex` replaces the street NAME
# and leaves «улица», «кв», «переулок» standing, and `observe.GENERIC_ROLES`
# exempts them from the needles; a mint that mangled them would hand the
# splitter a string with no markers and invent a miss.
_GENERIC_TOKENS = frozenset((
    "улица", "ул", "проспект", "пр", "пркт", "переулок", "пер", "шоссе", "ш",
    "бульвар", "б", "бул", "проезд", "площадь", "пл", "набережная", "наб",
    "тупик", "аллея", "линия", "квартал", "микрорайон", "мкр", "дом", "д",
    "корпус", "корп", "к", "строение", "стр", "квартира", "кв", "офис", "оф",
    "подъезд", "этаж", "литера", "лит", "город", "г", "гор", "село", "с",
    "посёлок", "поселок", "пос", "п", "деревня", "дер", "область", "обл",
    "район", "р", "рн", "край", "республика", "респ"))

_DIGIT_TYPES: tuple[str, ...] = ("PHONE", "CARD", "SNILS", "INN", "PASSPORT", "OGRN", "PLATE")
_DATE_TYPES: tuple[str, ...] = ("DOB", "DATE")
# The address roles, in the order a written Russian address states them.
_ROLE_ORDER: tuple[str, ...] = ("city", "street_type", "street", "house", "flat")
_NAME_ROLES: tuple[str, ...] = ("surname", "given", "patronymic")
# The roles whose disappearance from a minted surface means the substitute can
# no longer be SPLIT the way the real value is — and then every role-aware
# needle stops finding it, for reasons that belong to this file.
_SPLIT_ROLES: tuple[str, ...] = ("street", "surname", "given", "patronymic")
_WORD = re.compile(r"[^\W\d_]+|\d+|\W+|_", re.UNICODE)


def _keep_tail(word: str) -> int:
    """How many trailing characters a fake KEEPS.

    A Russian role is read off the suffix — «-ович» a patronymic, «-ова» a
    surname, «-ой» the dative — and `metrics.parts_of` and the grammatical-case
    reading both work from it. A fake that mangles the ending is not a fake of
    the same shape: it is a word of no shape at all.
    """
    if len(word) >= 7:
        return 4
    if len(word) >= 5:
        return 3
    return 0


def _fake_word(word: str) -> str:
    """Same length, same script, same case class, different letters."""
    out: list[str] = []
    for char in word:
        if not char.isalpha():
            out.append(char)
            continue
        low = char.lower()
        if "а" <= low <= "я" or low == "ё":
            new = low.translate(_CYR_MAP)
        elif "a" <= low <= "z":
            new = low.translate(_LAT_MAP)
        else:
            new = low
        out.append(new.upper() if char.isupper() else new)
    return "".join(out)


def _fake_stem(word: str) -> str:
    """A different lexeme wearing the SAME ending."""
    tail = _keep_tail(word)
    return _fake_word(word) if not tail else _fake_word(word[:-tail]) + word[-tail:]


def _shift_digits(text: str, by: int) -> str:
    return "".join(str((int(c) + by) % 10) if c.isdigit() else c for c in text)


def _fake_digits(text: str, pii_type: str) -> str:
    """Shift every digit, keep the separators — and keep the COUNTRY digit of
    an eleven-digit phone, so the substitute's canonical, its surface and its
    `digits` part all carry ONE digit signature. Minting them independently is
    how a simulation invents a gateway defect that is only its own bookkeeping.
    """
    positions = [i for i, char in enumerate(text) if char.isdigit()]
    keep = set()
    if pii_type == "PHONE" and len(positions) == 11 and text[positions[0]] in "78":
        keep.add(positions[0])
    return "".join(char if (not char.isdigit() or i in keep) else str((int(char) + 3) % 10)
                   for i, char in enumerate(text))


def _fake_date(text: str) -> str:
    """Shift the DAY by +1 inside 1..28 and the YEAR by +1: a fake date that is
    still a date, so every notation of it folds the way the real one does."""
    def day(match: re.Match[str]) -> str:
        return f"{(int(match.group(0)) % 28) + 1:0{len(match.group(0))}d}"

    def year(match: re.Match[str]) -> str:
        return str(int(match.group(0)) + 1)

    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text.strip())
    if iso:
        return f"{int(iso.group(1)) + 1:04d}-{iso.group(2)}-{(int(iso.group(3)) % 28) + 1:02d}"
    return re.sub(r"^\s*\d{1,2}(?=[.\-/ ])", day,
                  re.sub(r"\b(19|20)\d{2}\b", year, text))


def _fake_words(text: str) -> str:
    """NAME, LOC and anything else: word for word, digits shifted, generic
    words left standing."""
    out: list[str] = []
    for token in _WORD.findall(text):
        if token.isalpha():
            out.append(token if token.casefold() in _GENERIC_TOKENS else _fake_stem(token))
        elif token.isdigit():
            out.append(_shift_digits(token, 3))
        else:
            out.append(token)
    return "".join(out)


def mint(pii_type: str, surface: str, canonical: str, parts: dict[str, str]
         ) -> tuple[str, str, dict[str, str]]:
    """(substitute surface, substitute canonical, substitute parts)."""
    if pii_type in _DATE_TYPES:
        return (_fake_date(surface), _fake_date(canonical),
                {role: _fake_date(value) for role, value in parts.items()})
    if pii_type in _DIGIT_TYPES:
        return (_fake_digits(surface, pii_type), _fake_digits(canonical, pii_type),
                {role: (_fake_digits(value, pii_type) if any(c.isdigit() for c in value)
                        else _fake_word(value))
                 for role, value in parts.items()})
    if pii_type == "EMAIL":
        # WHAT THE PRODUCT ACTUALLY MINTS (`pseudex/vault.py`): eight letters at
        # `example.ru`. Keeping the customer's domain would leave «yandex.ru»
        # standing in the masked text, and `pieces_of` counts a domain as a
        # piece of the value — a simulation that kept it would report a leak
        # the gateway does not commit.
        local = "".join(_fake_word(char) for char in (canonical.partition("@")[0] + "abcdefgh")[:8])
        return local + "@example.ru", local + "@example.ru", {"local": local,
                                                              "domain": "example.ru"}
    return (_fake_words(surface), _fake_words(canonical),
            {role: _fake_words(value) for role, value in parts.items()})


@dataclass(frozen=True)
class Substitute:
    """The minted fake, shaped like a `PiiItem` so that `expected_leaf_value`
    reads its parts the way it reads the real one. One per identity, for the
    whole conversation — which is what `consistency` and `stability` ask."""

    id: str
    type: str
    identity: str
    value: str
    canonical: str
    parts: dict[str, str] = field(default_factory=dict)


# --- §2 the three corrections that ARE the specification ----------------------------


def _fold(word: str) -> str:
    return word.lower().replace("ё", "е")


def worn_like(fake_canonical: str, real_canonical: str, real_surface: str) -> str:
    """CORRECTION 1 — ONE MINT PER ITEM, WORN IN THE SURFACE'S GRAMMATICAL FORM.

    A right gateway mints ONE substitute per identity and INFLECTS it; the
    model reads «аёхфу» where the customer wrote «петру», and the SAME lexeme
    «аёхф» comes back in the argument.

    WHAT IT COST WHEN IT WAS WRONG. Minting twice — once from the surface, once
    from the canonical — looks harmless and is not: `_keep_tail` reads the
    ending off the word's LENGTH, so «пётр» (4) and «петра» (5) fall in
    different classes and come back as two UNRELATED fakes — «аёхф» and
    «адтра», which this file still prints if you ask it. The fake the model
    read then shares no stem with the fake in the argument, `carries_any` says
    the leaf holds no substitute, and the hop reads `unmasked`: the probe
    charging the gateway for its own bookkeeping. MEASURED, with this reverted:
    twelve leaves off `round_trip` and off `end_to_end`, twelve turns off
    `multi_all_out` over the whole corpus (three of each on the acceptance
    tier — `test_perfect.test_correction_one_is_load_bearing`).

    So: take the ONE minted canonical, and wear the surface's ending — keep the
    prefix the real canonical and the real surface share, and take the rest of
    the ending from the surface itself. Word counts must line up; when they do
    not the caller keeps the plain mint ("" is returned).
    """
    fakes = _WORD.findall(fake_canonical)
    reals = _WORD.findall(real_canonical)
    surfaces = _WORD.findall(real_surface)
    if not len(fakes) == len(reals) == len(surfaces):
        return ""
    out: list[str] = []
    for fake, real, surface in zip(fakes, reals, surfaces):
        if not fake.isalpha():
            out.append(surface)
            continue
        common = 0
        for left, right in zip(_fold(real), _fold(surface)):
            if left != right:
                break
            common += 1
        out.append(fake[:common] + surface[common:])
    return "".join(out)


def compose_free_leaf(values: Sequence[str]) -> str:
    """CORRECTION 2 — ONE SENTENCE PER FREE-TEXT LEAF, CARRYING EVERY HOP THAT
    LEAF DECLARES.

    `escalate_to_human.summary` is handed a NAME, a PHONE and a LOC. A free
    leaf is prose: a right agent writes all three into it, and a right gateway
    restores all three.

    WHAT IT COST WHEN IT WAS WRONG. Writing ONE value per leaf path kept only
    the LAST hop of such a leaf, and the other hops read as values the gateway
    dropped. 135 of the corpus's 928 chain transitions land on a shared free
    leaf (`notify_sms.text` 75, `escalate_to_human.summary` 36,
    `ticket_create.text` 24) and that is exactly where `chain_value`'s 36
    misses came from over the whole corpus — a probe artifact that would have
    sent us fixing a gateway that is not broken. FIX-4's per-transition
    measurement composed the prose properly and found 0 of 210 free-leaf
    transitions unhittable. (`test_perfect.test_correction_two_is_load_bearing`)
    """
    kept = [value for value in values if value]
    if not kept:
        return ""
    if len(kept) == 1:
        return kept[0]
    return "Клиент " + ", ".join(kept) + "."


def request_of_message(index: int) -> int:
    """CORRECTION 3 — `request_index` IS COUNTED PER PUSH, as `GatewayV5._push`
    counts it: one per message the gateway hands the model, system prompt
    excluded.

    WHAT IT COST WHEN IT WAS WRONG. A message and the tool result of the same
    TURN are two model requests. Numbering both by the turn collapses them, and
    then `stability` — «the substitute did not change BETWEEN requests» — sees
    one request per item, drops every item out of its denominator and prints
    0/0. A line that cannot fire certifies nothing.
    (`test_perfect.test_correction_three_is_load_bearing`)
    """
    return index + 1


def request_of_result(message_count: int, seq: int) -> int:
    """The other half of correction 3: a result is pushed AFTER the turn's
    message, so it rides a LATER request than the message that provoked it."""
    return message_count + seq + 1


# --- §3 the run a right gateway and a right agent leave behind ----------------------


def unflatten(flat: dict[str, str]) -> dict[str, object]:
    """Dotted leaf paths back into the nested argument object a tool receives."""
    out: dict[str, object] = {}
    for path, value in flat.items():
        node = out
        parts = path.split(".")
        for key in parts[:-1]:
            node = node.setdefault(key, {})       # type: ignore[assignment]
        node[parts[-1]] = value
    return out


def _leaf_pair(item: PiiItem, substitute: Substitute, tool: str, path: str) -> tuple[str, str]:
    """(what the agent WROTE — the substitute in the leaf's own notation,
    what the gateway RESTORED — the real value in the same notation)."""
    spec = spec_v5_for(tool, path) if tool in REGISTRY_V5 else None
    if spec is None:
        return substitute.canonical or substitute.value, item.canonical or item.value
    return expected_leaf_value(substitute, spec), expected_leaf_value(item, spec)


def _lost_roles(item: PiiItem, surface: str) -> bool:
    """Does the minted surface still SPLIT into the roles the item declares?"""
    got = parts_of(item.type, surface)
    return any(item.parts.get(role) and role not in got for role in _SPLIT_ROLES)


def _address_from_parts(parts: dict[str, str]) -> str:
    bits: list[str] = []
    for role in _ROLE_ORDER:
        value = parts.get(role)
        if value:
            bits.append("кв " + value if role == "flat" else value)
    return " ".join(bits)


def _substitute_for(item: PiiItem) -> Substitute:
    """The one fake this item wears everywhere it is mentioned."""
    # A DICTATED value is replaced by a WRITTEN fake. `pseudex.vault` mints
    # `_fake_phone()` / `_fake_snils()` whatever the surface was; `looks_dictated`
    # decides only what is RESTORED to the tool, never what the model is shown.
    # Minting a spoken-shaped substitute here would simulate a product that
    # does not exist — and it is why `form_hIN` cannot be 100 % for a right
    # gateway (docs/known-issues.md Б27).
    written = item.canonical if item.spoken else item.value
    surface, canonical, parts = mint(item.type, written, item.canonical, dict(item.parts))
    if item.type in ("NAME", "LOC") and not item.spoken and written != item.canonical:
        worn = worn_like(canonical, item.canonical, written)
        if worn:
            surface = worn
    # A DICTATED ADDRESS is replaced by a WRITTEN one. «садовая сорок шесть
    # квартира семьдесят девять» is the item's canonical, and mangling it word
    # by word leaves a string `metrics.parts_of` cannot split — so the
    # substitute would carry no street needle for reasons belonging to this
    # simulation. The engine mints a written fake; so does this.
    if item.type == "LOC" and _lost_roles(item, surface):
        surface = canonical = _address_from_parts(parts)
    if item.type == "NAME" and _lost_roles(item, surface):
        surface = canonical = " ".join(parts[role] for role in _NAME_ROLES if parts.get(role))
    return Substitute(id=item.id, type=item.type, identity=item.identity,
                      value=surface, canonical=canonical, parts=parts)


def _masked_messages(case: CaseV5, subs: dict[str, Substitute]
                     ) -> tuple[dict[int, tuple[tuple[int, int], ...]], list[MentionRecord]]:
    """Every message the conversation pushed: the spans the gateway replaced,
    and what the model read in each of them."""
    masked: dict[int, tuple[tuple[int, int], ...]] = {}
    mentions: list[MentionRecord] = []
    for index, _message in enumerate(case.base.messages):
        spans: list[tuple[int, int]] = []
        for item in case.base.pii:
            if item.where.kind == "message" and item.where.msg == index:
                spans.append((item.where.start, item.where.end))
                mentions.append(MentionRecord(item_id=item.id, msg=index, result_seq=-1,
                                              substitute=subs[item.id].value,
                                              request_index=request_of_message(index)))
        masked[index] = tuple(sorted(spans))
    return masked, mentions


def _tool_results(case: CaseV5, items: dict[str, PiiItem], subs: dict[str, Substitute]
                  ) -> tuple[list[ToolResultRecord], list[MentionRecord]]:
    """The tool results the case declares, rendered real and masked.

    `ToolResultRecord.pieces` are the gateway's replaced spans in `text_real`
    coordinates (`observe.covering_piece` compares them with `spans_real`),
    each with the substitute that slot got and the type the gateway assigned.
    """
    by_result: dict[tuple[int, str, int], list[str]] = {}
    for hop in case.hops:
        if hop.kind == "IN" and hop.owner in ("tool", "document"):
            by_result.setdefault((hop.turn, hop.tool_name, hop.call_ordinal), []).append(hop.item_id)
    declared = {(ret.tool_name, ret.call_ordinal): ret for ret in case.returns}
    records: list[ToolResultRecord] = []
    mentions: list[MentionRecord] = []
    for seq, ((turn, tool, ordinal), read_ids) in enumerate(sorted(by_result.items())):
        # EVERY DECLARED item of this result, even one no hop reads: a value the
        # result renders and nobody consumes still reaches the model.
        ret = declared.get((tool, ordinal))
        ids = list(dict.fromkeys(read_ids + list(ret.result_item_ids if ret else ())))
        real_parts: list[str] = []
        masked_parts: list[str] = []
        spans_real: dict[str, tuple[int, int]] = {}
        pieces: list[tuple[int, int, str, str]] = []
        for item_id in ids:
            item = items.get(item_id)
            if item is None:
                continue
            fake = subs[item_id]
            prefix = f"{item_id}: " if real_parts else ""
            start_real = sum(len(part) for part in real_parts) + len(prefix)
            real_parts.append(prefix + item.canonical + "\n")
            masked_parts.append(prefix + fake.canonical + "\n")
            spans_real[item_id] = (start_real, start_real + len(item.canonical))
            pieces.append((start_real, start_real + len(item.canonical), fake.canonical, item.type))
        records.append(ToolResultRecord(
            tool_name=tool, seq=seq, call_ordinal=ordinal, turn=turn,
            return_form=(ret.return_form if ret else "flat_json"),
            text_real="".join(real_parts), text_masked="".join(masked_parts),
            spans_real=spans_real, pieces=tuple(pieces), forced=False))
        for item_id in spans_real:
            mentions.append(MentionRecord(
                item_id=item_id, msg=-1, result_seq=seq, substitute=subs[item_id].canonical,
                request_index=request_of_result(len(case.base.messages), seq)))
    return records, mentions


def _calls(case: CaseV5, items: dict[str, PiiItem], subs: dict[str, Substitute]
           ) -> tuple[list[ObservedCall], list[int]]:
    """The tool calls the case declares, each leaf holding what the agent wrote
    and what the gateway restored."""
    by_call: dict[tuple[int, str, int], list[contracts.Hop]] = {}
    for hop in case.hops:
        if hop.kind == "OUT" and hop.owner in contracts.ACTING_OUT_OWNERS and hop.tool_name:
            by_call.setdefault((hop.turn, hop.tool_name, hop.call_ordinal), []).append(hop)
    calls: list[ObservedCall] = []
    turns: list[int] = []
    for (turn, tool, ordinal), hops in sorted(by_call.items()):
        written: dict[str, str] = {}
        restored: dict[str, str] = {}
        by_path: dict[str, list[contracts.Hop]] = {}
        for hop in hops:
            by_path.setdefault(hop.path, []).append(hop)
        for path, path_hops in by_path.items():
            pairs = [_leaf_pair(items[hop.item_id], subs[hop.item_id], tool, hop.path)
                     for hop in path_hops if hop.item_id in items]
            if not pairs:
                continue
            spec = spec_v5_for(tool, path) if tool in REGISTRY_V5 else None
            if len(pairs) > 1 and spec is not None and spec.kind == "free":
                written[path] = compose_free_leaf([one for one, _other in pairs])
                restored[path] = compose_free_leaf([other for _one, other in pairs])
            else:
                # A single hop, or a NON-free leaf carrying two: the second is a
                # corpus shape no agent can honour — one slot, one value — and
                # the last hop wins, as it does in the record of a live run.
                written[path], restored[path] = pairs[-1]
        calls.append(ObservedCall(name=tool, written=unflatten(written),
                                  restored=unflatten(restored), residual={},
                                  refusal_path="", refusal_rule="", parsed=None, seq=len(calls)))
        turns.append(turn)
    return calls, turns


def _answer(case: CaseV5, items: dict[str, PiiItem], subs: dict[str, Substitute]
            ) -> tuple[str, str]:
    """(the reply as the model wrote it — substitutes still in it,
    the reply as the customer reads it — real values restored).

    EACH DATUM IN ITS OWN SENTENCE, with unchanged words around it. Two values
    written side by side («Готово. X. Y.») align as ONE `replace` run, land in
    ONE `AttributedSpan`, and `answer_pair` then narrows the region by
    occurrences — which is how a whole phone once came back as «+79037654».
    That was the probe's prose, not the gateway's work.
    """
    raw = ["Готово."]
    real = ["Готово."]
    for number, hop in enumerate(
            [hop for hop in case.hops if hop.kind == "OUT" and hop.owner == "answer"], start=1):
        item = items.get(hop.item_id)
        if item is None:
            continue
        raw.append(f" Пункт {number}: {subs[hop.item_id].value} — записано.")
        real.append(f" Пункт {number}: {item.value} — записано.")
    return "".join(raw), "".join(real)


def simulate(case: CaseV5) -> ArmRunV5:
    """The `ArmRunV5` a right gateway and a right agent leave behind on `case`."""
    items = {item.id: item for item in case.base.pii}
    subs = {item.id: _substitute_for(item) for item in case.base.pii}
    masked_spans, message_mentions = _masked_messages(case, subs)
    results, result_mentions = _tool_results(case, items, subs)
    calls, call_turns = _calls(case, items, subs)
    reply_raw, reply = _answer(case, items, subs)
    base = ArmRun(case_id=case.base.id, arm="I", repeat=0, calls=tuple(calls), state=(),
                  reply=reply, termination="done", cost_usd=0.0,
                  substitutes={item_id: (fake.value, dict(fake.parts))
                               for item_id, fake in subs.items()},
                  masked_spans=masked_spans)
    return ArmRunV5(
        base=base, reply_raw=reply_raw,
        # The control arm writes the same answer; a right gateway does not
        # rewrite the agent's prose, which is what `rewrite_ratio_v5` asks.
        control_reply=reply + " ",
        tool_results=tuple(results), mentions=tuple(message_mentions + result_mentions),
        turn_replies=(reply,), call_turns=tuple(call_turns),
        # Correction 3 again, at the level of the whole run: one request per
        # push, messages and results alike.
        request_count=max(len(case.base.messages) + len(results), 1),
        stream_mismatch=False, reply_whole=reply if case.streaming else "", turn_residual=0)


# --- §4 running it ------------------------------------------------------------------


def load_cases(path: pathlib.Path) -> list[CaseV5]:
    return [case_v5_from_json(row)
            for row in json.loads(path.read_text(encoding="utf-8"))["corpus"]]


def load_ladder(path: pathlib.Path) -> Ladder:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Ladder(version=int(raw["version"]), seed=int(raw["seed"]),
                  corpus_sha256=str(raw["corpus_sha256"]),
                  tiers={name: tuple(ids) for name, ids in dict(raw["tiers"]).items()})


def cases_of_tier(cases: Sequence[CaseV5], ladder: Ladder, name: str) -> list[CaseV5]:
    """The tier's cases, in corpus order. `max` is every case, so the ladder is
    not consulted and a probe over the whole corpus needs no frozen list."""
    if name == "max":
        return list(cases)
    picked = {one.id for one in tier([case.base for case in cases], ladder, name)}
    return [case for case in cases if case.base.id in picked]


def observations(cases: Sequence[CaseV5]) -> tuple[RunObservation, ...]:
    """One observation per case, through the package's OWN observer.

    No `except` here on purpose: an observer that raises on a record a right
    gateway would leave is a finding, not a case to skip. A probe that skipped
    it would report the metrics of the cases that happened to work.
    """
    return tuple(observe.observe(case, simulate(case), None, None) for case in cases)


def measure(cases: Sequence[CaseV5]) -> dict[str, Line]:
    """Every single-arm metric line over the simulated run."""
    seen = observations(cases)
    return {name: metrics.METRIC_FUNCTIONS[name](seen) for name in SINGLE_ARM_METRICS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", default=str(CORPUS_PATH))
    parser.add_argument("--ladder", default=str(LADDER_PATH))
    parser.add_argument("--tier", default="medium",
                        choices=("nano", "small", "medium", "large", "holdout", "max"))
    args = parser.parse_args()
    cases = cases_of_tier(load_cases(pathlib.Path(args.corpus)),
                          load_ladder(pathlib.Path(args.ladder)), args.tier)
    lines = measure(cases)
    print(f"perfect gateway · tier {args.tier} · {len(cases)} cases\n")
    print(f"{'metric':26s} {'hits':>7s}/{'total':<7s} rate")
    for name in SINGLE_ARM_METRICS:
        line = lines[name]
        print(f"{name:26s} {line.hits:7d}/{line.total:<7d} "
              f"{(line.rate if line.total else 0):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
