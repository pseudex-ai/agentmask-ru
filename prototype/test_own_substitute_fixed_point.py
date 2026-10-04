#!/usr/bin/env python3
"""Class В — the engine's OWN substitute is a fixed point of the mask.

`research/hop-format-audit/DIAGNOSIS.md`, class В: «ответ модели (уже несущий
подмену) передетектируется и перечеканивается заново → имя меняется на каждом
ходу, "три личности" в одном диалоге, REDACTED вместо подмены». The owner's
decision (`DECISIONS-SPRINT.md`, class В): «Непрерывность личности: производная
форма СВОЕЙ подмены (одна фамилия / инициалы / падеж) пропускается как своя. Одна
персона = одна подмена.»

Self-contained: no LLM, no network, no licensing server. The development bundle is
built and loaded exactly as the rest of the suite does (`testkit.load_dev_bundle`),
and every turn is driven through the PRODUCTION path `envelope.mask_messages` with
one persistent `Vault`, one `MaskCache` and one `MaskContext` per request — the
shape both HTTP legs use.

    cd prototype && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_own_substitute_fixed_point.py

WHAT THE CHECKS ARE WRITTEN FROM. Every positive contract below comes from a
WITNESS in `research/hop-format-audit/agents/`, never from a value the engine
computed, and the substitute in each run is random — the expectations are
relative (`written` against `delivered_to_model`), so no check is pinned to a
particular fake:

  * g04 П3 (`long_order+correction`): «6501 сообщение `assistant` в доставленных
    запросах, 920 (14.2%) пришли изменёнными»; `correction-000`:
    `**Получатель:** Фомин Тимофей` → доставлено `**Получатель:Сазонов Бирюков
    Герман`; `long_order-001`: `Карпов Егор` → `Мещеряков Мухин Кирилл`.
  * g04 П3 hypothesis H1: «Перед чеканкой проверять найденный спан против уже
    выданных подмен РАЗГОВОРА (целая строка, часть, с инициалами, в падеже) и
    пропускать его без изменений».
  * g13 (`long_support`): one person, two substitutes — the real `Тарасова`
    became `кудрявцева`, and the same person written as initials `Тарасова Л. С.`
    got a DIFFERENT one; the third time, `REDACTED0557ab`.
  * g07 P5 (`rag-decompose-receipt`): «Эхо собственного вызова агента
    перемаскируется заново — в другую подмену или в `REDACTED…`»; the exact
    bytes: `"cardholder": "EGOR BOBROV"` is read back in the next request as
    `"cardholder": "REDACTED2aada2"`.
  * g10 П2 (`tool_chain_derive_validate`): «одна и та же реальная величина
    встречается моделью под 2–3 разными подменами в разных payload'ах (36/36
    кейсов `tool_chain`)».

THE NEGATIVES ARE THE HALF THAT KEEPS THE RULE HONEST. Widening «наше» narrows
masking, so every adversarial case in `family_negatives` is a REAL string that
must still be masked: a stranger who happens to share our substitute's surname, a
bare given name or patronymic of our substitute, a Latin stranger, a place that
shares a word with a person's substitute, and another CONVERSATION's rendering —
the rule is scoped to the dialogue the model could have read it in.

THE PRICE IS STATED, so that the widening is a decision and not a surprise:

  * A LONE SURNAME of this dialogue's substitute passes — that is the owner's
    «одна фамилия» — so a real person who happens to bear that word reaches the
    model in the clear. It is the same exposure `redact.mask_text` already
    documents for a whole substitute, it is bounded by the single-owner rule
    (one candidate in the DIALOGUE, `residual_of`'s scoping), and it is NOT
    extended: a bare given name or patronymic is refused, because the fake pools
    and the real population draw from one short list of Russian given names.
  * THE RULE IS NOT GATED ON THE CALLER'S OWN-RENDERING EVIDENCE, on purpose:
    the class-В defect (`mask(mask(x)) != mask(x)` on the engine's own output)
    lives in a plain chat and on `/mask` as much as in the tool loop, and the
    frozen scorer calls `is_own_substitute` without evidence at all. The price is
    cache discrimination: an entry written for a text before a derived surface of
    the dialogue existed can only be the MASKED answer, which is the fail-closed
    direction, never a re-minted substitute.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from testkit import load_dev_bundle  # noqa: E402

from pseudex.audit import AuditLog  # noqa: E402
from pseudex import translit  # noqa: E402
from pseudex.detect import Span  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, _neutral_redaction, mask_messages  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.morph_names import detect_gender, inflect_person  # noqa: E402
from pseudex.redact import is_own_substitute  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def _expect(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n        {detail}" if detail else ""))


# --------------------------------------------------------------------------- #
# the production shape: one vault + one cache per tenant, one view per request #
# --------------------------------------------------------------------------- #

_DETECTOR: Detector | None = None
_REAL_PERSON = "Клиент Иванов Пётр Сергеевич, тел 8 916 123-45-67"
# A person this dialogue NEVER showed. Every negative control uses them: if the
# rule passes them through, it is not a rule about identity but a hole.
_STRANGER = "Сидоров Аркадий Львович"


class Session:
    """One tenant store; `turn()` is one HTTP request of one conversation."""

    def __init__(self, convo: str) -> None:
        global _DETECTOR
        if _DETECTOR is None:
            _DETECTOR = Detector()
        self.vault = Vault(":memory:", "class-v")
        self.cache = MaskCache(4096)
        self.convo = convo

    def _context(self) -> MaskContext:
        return MaskContext(detector=_DETECTOR, vault=self.vault.for_conversation(self.convo),
                           audit=AuditLog(":memory:"), cache=self.cache,
                           org_id="class-v", agent_id="class-v", conversation_id=self.convo)

    def turn(self, messages: list[dict]) -> list[dict]:
        return mask_messages(messages, self._context(), False)

    def mask_one_text(self, text: str) -> str:
        """One standalone message, as a later request of this dialogue sees it.

        No tool call in the transcript, so the provenance evidence is empty and
        this is the EVIDENCE-FREE reading — the one a plain chat (and the public
        `/mask` entry) takes. The class-В rule has to hold here too: a dialogue
        without a tool call still shows the model a substitute and still gets it
        back in the next turn's replay.
        """
        return self.turn([{"role": "assistant", "content": text}])[0]["content"]

    def mask_one_leaf(self, key: str, leaf: str) -> str:
        """The model's own tool call carrying `leaf` under the field `key`."""
        arguments = json.dumps({key: leaf}, ensure_ascii=False)
        out = self.turn([
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "c1", "type": "function",
                             "function": {"name": "crm_upsert", "arguments": arguments}}]},
        ])
        masked = out[0]["tool_calls"][0]["function"]["arguments"]
        return json.loads(masked)[key]


def _latin(fake: str) -> str:
    """The substitute through the first declared transliteration table.

    g07's own bytes were `EGOR BOBROV`. This is a spelling the vault indexes by
    construction (`translit.declared_keys` at the mint), so a Latin rendering of
    our own substitute is one the engine already knows how to reproduce."""
    words: list[str] = []
    for word in fake.split():
        spellings = sorted(translit.variants(word))
        assert spellings, f"no declared Latin spelling for {word!r}"
        words.append(spellings[0].capitalize())
    return " ".join(words)


def _mint(session: Session) -> tuple[str, str]:
    """Turn 1 of the conversation. Returns (substitute, the user text to replay).

    The later turns replay this same first message, which is what an OpenAI SDK
    app does (`bench/agentpii4/gateway.py`: `_transcript.append(wire)` →
    `mask_messages([...self._transcript])`), and the substitute is the string the
    dialogue then shows the model for the rest of the dialogue."""
    masked = session.turn([{"role": "user", "content": _REAL_PERSON}])[0]["content"]
    # `\b` and not a substring: a random substitute's patronymic is routinely
    # «Иванович», and a substring test would call that a leak.
    assert not re.search(r"\bИванов\b|\bПётр\b|\bСергеевич\b", masked), \
        f"the real name reached the model: {masked!r}"
    fake = masked.split("Клиент ")[1].split(",")[0]
    assert len(fake.split()) == 3, f"expected a three-part substitute, got {fake!r}"
    return fake, masked


def _prose_echo(session: Session, user_text: str, written: str) -> str:
    """Turn 2: the transcript replays turn 1 and the ASSISTANT wrote `written`."""
    out = session.turn([
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "c0", "type": "function",
                         "function": {"name": "crm_find", "arguments": "{}"}}]},
        {"role": "assistant", "content": f"Записал: {written}"},
    ])
    return out[-1]["content"].split("Записал: ")[1]


# --------------------------------------------------------------------------- #
# family 1 — g04 П3 / g13: the model's own substitute written as PROSE         #
# --------------------------------------------------------------------------- #

def family_prose() -> None:
    print("\n[g04 П3 / g13] the model's own substitute, written in prose")

    session = Session("prose")
    fake, user_text = _mint(session)
    surname, name, patronymic = fake.split()
    print(f"        turn 1 showed the model: {fake}")

    # H1 verbatim: «целая строка, часть, с инициалами, в падеже».
    datv = inflect_person(fake, "datv", detect_gender(fake))
    assert datv != fake, f"the substitute does not inflect, the case contract is vacuous: {fake!r}"
    forms = {
        "целая строка": fake,
        "часть (фамилия и имя, без отчества)": f"{surname} {name}",
        "одна фамилия": surname,
        "инициалы": f"{surname} {name[0]}. {patronymic[0]}.",
        "падеж (дательный)": datv,
    }
    for label, written in forms.items():
        got = _prose_echo(session, user_text, written)
        _expect(got == written,
                f"assistant prose stays byte-identical — {label}",
                f"written={written!r} delivered_to_model={got!r}")

    # g04 П3 measures exactly this: `assistant_rewritten = 0`. A whole assistant
    # message built ONLY from renderings this dialogue showed must be a fixed
    # point of the mask — that is the idempotency `mask(mask(x)) == mask(x)`
    # states for the engine's own output, and it is asked here on the
    # EVIDENCE-FREE reading (no tool call in the transcript).
    written = (f"Записал {fake}, он же {surname} {name[0]}. {patronymic[0]}., "
               f"звонить {datv}")
    once = session.mask_one_text(written)
    twice = session.mask_one_text(once)
    _expect(once == written and twice == written,
            "an assistant message built only of our renderings is a fixed point",
            f"written={written!r} turn2={once!r} turn3={twice!r}")

    # The same substitute the model retyped in LATIN — the other script of our own
    # rendering, and a key the vault's own index declares.
    latin = _latin(fake)
    got = _prose_echo(session, user_text, latin)
    _expect(got == latin,
            "assistant prose stays byte-identical — наша подмена латиницей",
            f"written={latin!r} delivered_to_model={got!r}")

    # THE NEGATIVE CONTROL: a person this dialogue never showed must still be
    # masked. Without it the whole shield could be «never mask an assistant
    # message», which is a leak, not a fix.
    got = _prose_echo(session, user_text, _STRANGER)
    _expect("Сидоров" not in got and "Аркадий" not in got,
            "control: a DIFFERENT real person in assistant prose is still masked",
            f"written={_STRANGER!r} delivered_to_model={got!r}")


# --------------------------------------------------------------------------- #
# family 2 — g07 P5 / g10 П2: the model's own substitute in a JSON leaf        #
# --------------------------------------------------------------------------- #

def family_json_leaf() -> None:
    print("\n[g07 P5 / g10 П2] the model's own substitute, written into a tool field")

    session = Session("json")
    fake, _user_text = _mint(session)
    surname, name, patronymic = fake.split()
    print(f"        turn 1 showed the model: {fake}")

    # `cardholder` is the witness's own key. It prefix-matches `card`, CARD is a
    # numeric key type, the value has no digit, so `structured.detect_structured_kv`
    # demotes the span to OPAQUE — a type with no renderer, so the model read
    # `REDACTED<hex>` where its own substitute stood. The TYPE is gone by then;
    # the identity is not.
    for label, leaf in {
        "целая подмена": fake,
        "фамилия": surname,
        "инициалы": f"{surname} {name[0]}. {patronymic[0]}.",
    }.items():
        got = session.mask_one_leaf("cardholder", leaf)
        _expect(got == leaf,
                f"own substitute under a re-typing field key stays byte-identical — {label}",
                f"field='cardholder' written={leaf!r} delivered_to_model={got!r}")

    # The same substitute the model retyped in LATIN (g07's own bytes were
    # `EGOR BOBROV`): a derived script is still our rendering.
    latin = _latin(fake)
    got = session.mask_one_leaf("cardholder", latin)
    _expect(got == latin,
            "own substitute retyped in LATIN stays byte-identical",
            f"written={latin!r} delivered_to_model={got!r}")

    # The engine's OWN redaction marker is not data and must not become data: the
    # marker's hex digits read as a NUMBER under the same key, and the engine used
    # to mint a fake card over its own redaction on every request.
    marker = _neutral_redaction("NAME", "Иванов Пётр Сергеевич")
    got = session.mask_one_leaf("cardholder", marker)
    _expect(got == marker,
            "the engine's own REDACTED marker is a fixed point, not a new value",
            f"written={marker!r} delivered_to_model={got!r}")

    # The tool RESULT echoing the model's own rendering: g07 P5's other half.
    session2 = Session("json-result")
    fake2, user_text2 = _mint(session2)
    surname2 = fake2.split()[0]
    body = json.dumps({"cardholder": surname2}, ensure_ascii=False)
    out = session2.turn([
        {"role": "user", "content": user_text2},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "c0", "type": "function",
                         "function": {"name": "crm_find", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c0", "content": body},
    ])
    delivered = out[-1]["content"]
    _expect(json.loads(delivered)["cardholder"] == surname2,
            "a tool RESULT echoing our own rendering keeps the substitute",
            f"result_in={body!r} delivered_to_model={delivered!r}")

    # THE NEGATIVE CONTROL for the JSON leg: a different real person's name must
    # still not reach the model in the clear (its exact substitute does not
    # matter here — a redaction is a correct answer for a value that is not ours).
    got = session.mask_one_leaf("cardholder", _STRANGER)
    _expect("Сидоров" not in got and "Аркадий" not in got,
            "control: a DIFFERENT real person under the same key is still masked",
            f"delivered_to_model={got!r}")


# --------------------------------------------------------------------------- #
# family 3 — the exact boundary of «наше»: what must NOT be passed through     #
# --------------------------------------------------------------------------- #

def family_negatives() -> None:
    """Widening «наше» narrows masking, so the negatives are half the rule.

    Each of these is a REAL string a customer may write, not a contrived edge, and
    each must still be masked even though the dialogue IS showing a substitute."""
    print("\n[boundary] what the widened rule must NOT pass through")

    session = Session("boundary")
    fake, user_text = _mint(session)
    surname, name, patronymic = fake.split()
    print(f"        turn 1 showed the model: {fake}")

    def prose(text: str) -> str:
        return session.mask_one_text(text)

    # ONE SIGNAL IS NOT IDENTITY. «Юдин Аркадий Львович» shares our substitute's
    # surname and nothing else: every word must belong to ONE substitute, and
    # `residual_of` refuses when they do not.
    text = f"{surname} Аркадий Львович"
    _expect(prose(text) != text, "a stranger REUSING our surname stays masked",
            f"written={text!r} -> {prose(text)!r}")

    # A LONE GIVEN NAME IS A WORD, NOT A PERSON. The fake pools and the real
    # population draw from the same short list of Russian given names, so a bare
    # «Артём» marks nobody — the rule asks for the SURNAME slot.
    for label, word in (("given name", name), ("patronymic", patronymic),
                        ("given name + patronymic", f"{name} {patronymic}")):
        _expect(prose(word) != word, f"our substitute's bare {label} stays masked",
                f"written={word!r} -> {prose(word)!r}")

    # THE OTHER SCRIPT OF SOMEBODY ELSE. The Latin detector finds «Ivan Petrov»;
    # it is not a rendering of our substitute and must be masked like any name.
    _expect(prose("Ivan Petrov") != "Ivan Petrov",
            "a Latin STRANGER stays masked", f"-> {prose('Ivan Petrov')!r}")

    # A PLACE IS NOT A PERSON, AND IT HAS ITS OWN QUESTION. «улица Шилова 12» is
    # a real address that happens to carry a person's surname; the person rule
    # must not wave it through, and it does not — `is_own_substitute` leaves LOC
    # to `holds_minted_place`/`place_fragment_is_ours`, whose index is about
    # places. The direct check below pins that boundary on the SAME surface, so
    # it cannot pass by accident of the address parser.
    address = f"улица {surname}а 12"
    locs = [span for span in _DETECTOR.detect(address) if span.entity_type == "LOC"]
    see = session.mask_one_text(address)
    _expect(bool(locs) and surname not in see,
            "an address carrying our surname is a LOC span and stays masked",
            f"written={address!r} spans={[(s.entity_type, address[s.start:s.end]) for s in locs]}"
            f" -> {see!r}")
    view = session.vault.for_conversation(session.convo)
    as_name = Span(0, len(surname), "NAME", surname)
    as_place = Span(0, len(surname), "LOC", surname)
    _expect(is_own_substitute(as_name, view) and not is_own_substitute(as_place, view),
            "the SAME surface is ours as a NAME and not ours as a PLACE",
            f"NAME={is_own_substitute(as_name, view)} LOC={is_own_substitute(as_place, view)}")

    # THE SCOPE IS THE DIALOGUE THAT SHOWED IT. A substitute can only come back
    # from the conversation that read it; the same surface arriving in ANOTHER
    # dialogue is a real person who happens to bear the name (`is_minted_token`'s
    # own documented price). Same vault, different conversation.
    #
    # THE FORM IS A TWO-WORD ONE ON PURPOSE: a LONE surname is not always a
    # detected span at all (the dictionary gate decides an occurrence, and
    # `Рыбаков` standing alone is a word without context), so a bare-surname
    # check would pass for the wrong reason — by never being a span. The full
    # name and the surname+given name are always detected, which is what makes
    # these checks about the rule and not about the gate.
    other = Session("boundary-other")
    other.vault = session.vault
    for label, text in (("the whole substitute", fake), ("a two-word part", f"{surname} {name}")):
        got = other.mask_one_text(text)
        _expect(got != text, f"another conversation's {label} stays masked",
                f"written={text!r} -> {got!r}")

    # The control that proves the negatives are not vacuous: the SAME forms do
    # pass in the dialogue that showed them.
    got = session.mask_one_text(f"{surname} {name}")
    _expect(got == f"{surname} {name}",
            "and the same forms DO pass in the dialogue that showed them",
            f"-> {got!r}")


def main() -> int:
    load_dev_bundle()
    family_prose()
    family_json_leaf()
    family_negatives()
    failures = [name for ok, name, _ in RESULTS if not ok]
    print()
    print("=" * 78)
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} passed")
    if failures:
        print("CLASS В IS PRESENT — the engine rewrites its own substitutes:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("CLASS В IS CLOSED — the engine's own substitutes are a fixed point")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
