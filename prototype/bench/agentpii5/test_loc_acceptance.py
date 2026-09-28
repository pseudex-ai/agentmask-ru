"""C1 acceptance — composite LOC, two address entities, no real/fake hybrid, A2.

    cd prototype && source .venv/bin/activate && \
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_loc_acceptance

The acceptance half of the hop-format LOC closure (`PRE-RUN-CLOSURE.md` C1). The
audit's A2 disease was «переулок Мончегорская 10» and «Мончегорская 10» minting
TWO different fake streets because the street-type word survived into the vault
key. The engine fix (committed) makes the type word presentation-only, so the
street stem is the identity. This file proves the MASKING leg of that claim end
to end — no model, no network, one in-memory vault per conversation, driven
through the production path `envelope.mask_messages`.

WHAT IS PINNED, AND WHY EACH CLAIM IS NARROWED.

- COMPOSITE. «г. Уфа, переулок Мончегорская 10, кв. 54» masks as ONE address;
  the settlement stays real (a city identifies nobody and hiding it broke the
  agent — `vault._settlement_of`), while the street NAME, the house and the flat
  are all fake. The assertion is per ROLE, read through `morph_places.split_roles`
  (the one parser every consumer must reuse), never a substring hunt: «10» and
  «54» are ordinary-looking digits that a fake flat may contain, so only the
  role's own value is compared to the real one.
- TWO ENTITIES. Two different addresses in one message must produce two different
  fake streets — the collision guard that a live run found by «заречная 57 …
  энгельса 106» drawing the same fake street, and that `test_mint_consistency`
  does not exercise (it drives the vault directly, not the detection leg).
- NO HYBRID. The masked address may carry the real settlement but never a real
  street + fake house or fake street + real house: street, house and flat are
  fake TOGETHER. The check is stated as «every protected role differs from the
  real role», which is the forward-leg form of the §4.2 hybrid ban pinned by
  `test_location_hop_form` on the restore leg.
- A2. The same full address written with and without the type word, and the same
  city-less street written with and without it, resolve to ONE fake street and
  ONE fake house in one conversation.

THE OFFLINE REPLAY is the second half of C1: every `long_order-*` / `tool_chain-*`
case's message LOC values are pushed through `mask_messages` and checked for two
discrepancies — a real value that leaks into the masked transcript, and a real
value that split into more than one substitute. Zero of each is the claim.
"""

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from testkit import load_dev_bundle  # noqa: E402
from pseudex import morph_places  # noqa: E402
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_messages  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _session(org: str, convo: str) -> tuple[Vault, MaskContext]:
    """One conversation view over one tenant store, the production shape."""
    detector = Detector()
    base = Vault(":memory:", org)
    view = base.for_conversation(convo)
    context = MaskContext(
        detector=detector, vault=view, audit=AuditLog(":memory:"),
        cache=MaskCache(1024), org_id=org, agent_id="bench",
        conversation_id=convo)
    return view, context


def _mask(context: MaskContext, text: str) -> str:
    """Mask one user message through the production path and return its content."""
    masked = mask_messages([{"role": "user", "content": text}], context, False)[0]["content"]
    if not isinstance(masked, str):
        raise AssertionError("masked content changed its wire type")
    return masked


def _street_name(phrase: str) -> str:
    """The bare street name of an address, with the type word dropped."""
    roles = morph_places.split_roles(phrase)
    street = roles.get("street", "")
    if not street:
        return ""
    return " ".join(word for word in street.split()
                    if not morph_places.is_generic_word(word))


def _loc_forms(view: Vault) -> list[tuple[str, str]]:
    """(shown substitute, real original) for the LOC rows, substitutes only."""
    return [(shown, original) for shown, original, kind in view.shown_forms()
            if kind == "LOC" and shown != original]


# --- synthetic acceptance -------------------------------------------------------

REAL_FULL: str = "г. Уфа, переулок Мончегорская 10, кв. 54"
REAL_CITYLESS: str = "переулок Мончегорская 10"


def _check_composite() -> None:
    """One composite address masks to ONE fake address; only the settlement stays."""
    view, context = _session("loc-composite", "c1")
    masked = _mask(context, REAL_FULL)
    real_roles = morph_places.split_roles(REAL_FULL)
    fake_roles = morph_places.split_roles(masked)

    check(fake_roles.get("city") == "Уфа",
          "the settlement stays real (a city identifies nobody)",
          f"city={fake_roles.get('city')!r}")
    check(_street_name(masked) != _street_name(REAL_FULL),
          "the street name is faked",
          f"real={_street_name(REAL_FULL)!r} fake={_street_name(masked)!r}")
    check(fake_roles.get("house") != real_roles.get("house"),
          "the house number is faked",
          f"real={real_roles.get('house')!r} fake={fake_roles.get('house')!r}")
    check(fake_roles.get("flat") != real_roles.get("flat"),
          "the flat number is faked",
          f"real={real_roles.get('flat')!r} fake={fake_roles.get('flat')!r}")
    # The real street NAME never reaches the model, in any case or form.
    check(_street_name(REAL_FULL).casefold() not in masked.casefold(),
          "no real part leaks into the masked address",
          f"masked={masked!r}")
    # One LOC substitute, not a town and a street minted separately.
    forms = _loc_forms(view)
    check(len(forms) == 1, "the composite address minted exactly one LOC substitute",
          f"rows={[(s, o) for s, o in forms]}")


def _check_two_entities() -> None:
    """Two addresses in one message produce two DIFFERENT fake streets."""
    view, context = _session("loc-two", "c1")
    address_b = "г. Казань, улица Ленина 5, кв. 2"
    text = f"адрес A: {REAL_FULL}; адрес B: {address_b}"
    masked = _mask(context, text)

    forms = _loc_forms(view)
    check(len(forms) == 2,
          "two addresses minted two LOC substitutes",
          f"rows={[(s, o) for s, o in forms]}")
    names = {_street_name(shown).casefold() for shown, _ in forms}
    check(len(names) == 2,
          "the two substitutes carry two different fake streets",
          f"fake streets={sorted(names)}")
    # Neither fake street may be the real street of the OTHER address.
    check(_street_name(REAL_FULL).casefold() not in masked.casefold()
          and "ленина" not in masked.casefold(),
          "no real street of either address leaks",
          f"masked={masked!r}")


def _check_no_hybrid() -> None:
    """The masked address never mixes a real and a fake protected part.

    «real street + fake house» is the §4.2 hybrid: every role that IS protected
    must be fake, so a partial fake is impossible by construction of the roles.
    The settlement is the only part allowed to stay real, and it is checked
    separately in `_check_composite`."""
    view, context = _session("loc-no-hybrid", "c1")
    masked = _mask(context, REAL_FULL)
    real_roles = morph_places.split_roles(REAL_FULL)
    fake_roles = morph_places.split_roles(masked)
    protected = ("street", "house", "flat")
    for role in protected:
        check(fake_roles.get(role) != real_roles.get(role),
              f"the {role} role is not a real value (no real/fake hybrid)",
              f"real={real_roles.get(role)!r} fake={fake_roles.get(role)!r}")
    # The fake street, house and flat are all present — a coherent fake, not a
    # half-masked address with a role dropped out.
    check(all(fake_roles.get(role) for role in protected),
          "the masked address keeps every protected role",
          f"roles={fake_roles}")


def _check_a2_type_word() -> None:
    """A2: the street-type word is presentation, not identity.

    The same street written with and without «переулок» — full address and
    city-less form — resolves to ONE fake street and ONE fake house in one
    conversation. Before the fix the two keys differed and the model met two
    streets for one place."""
    view, context = _session("loc-a2", "c1")
    with_type = _mask(context, REAL_FULL)
    without_type = _mask(context, "г. Уфа, Мончегорская 10, кв. 54")
    check(_street_name(with_type) == _street_name(without_type),
          "full address: the type word does not split the fake street",
          f"{with_type!r} vs {without_type!r}")
    check(morph_places.split_roles(with_type).get("house")
          == morph_places.split_roles(without_type).get("house"),
          "full address: the type word does not split the fake house", "")

    cityless_with = _mask(context, "переулок Мончегорская 10")
    cityless_without = _mask(context, "Мончегорская 10")
    check(_street_name(cityless_with) == _street_name(cityless_without),
          "city-less street: the type word does not split the fake street",
          f"{cityless_with!r} vs {cityless_without!r}")
    check(morph_places.split_roles(cityless_with).get("house")
          == morph_places.split_roles(cityless_without).get("house"),
          "city-less street: the type word does not split the fake house", "")
    # The FULL and the city-less mention of one place share the street+house.
    check(morph_places.street_house_key(with_type)
          == morph_places.street_house_key(cityless_with),
          "full and city-less mentions link to one street+house", "")


# --- offline replay over the real corpus ---------------------------------------

def _corpus_loc_cases() -> list[dict[str, object]]:
    corpus_path = _HERE.parent / "corpus.v5.json"
    with open(corpus_path, encoding="utf-8") as handle:
        corpus = json.load(handle)["corpus"]
    picked: list[dict[str, object]] = []
    for case in corpus:
        case_id = str(case["base"]["id"])
        if not (case_id.startswith("long_order") or case_id.startswith("tool_chain")):
            continue
        if any(item.get("type") == "LOC" for item in case["base"].get("pii", [])):
            picked.append(case)
    return picked


def _replay_corpus() -> None:
    """Mask every message LOC value of the real LOC cases and count discrepancies.

    A discrepancy is (a) a real value whose protected part leaks into the masked
    transcript, or (b) a real value that split into more than one substitute.
    Zero of each is the claim that the A2 fix holds on the corpus, not only on
    the synthetic address above."""
    cases = _corpus_loc_cases()
    leaks: list[str] = []
    splits: list[str] = []
    checked_values = 0
    for case in cases:
        case_id = str(case["base"]["id"])
        view, context = _session(f"replay-{case_id}", case_id)
        masked_transcript: list[str] = []
        for message in case["base"]["messages"]:
            if message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, str):
                    masked = _mask(context, content)
                    masked_transcript.append(masked)
        # Leak check: the real street NAME of each message LOC value is absent
        # from the masked transcript. The house/flat are checked through the role
        # in the synthetic tests; here the distinctive name is the canary.
        for item in case["base"].get("pii", []):
            if item.get("type") != "LOC" or item.get("where", {}).get("kind") != "message":
                continue
            checked_values += 1
            value = str(item["value"])
            street = _street_name(value)
            if street and any(street.casefold() in masked.casefold() for masked in masked_transcript):
                leaks.append(f"{case_id}: {value!r}")
        # Consistency check: one real value -> one substitute.
        by_real: dict[str, set[str]] = {}
        for shown, original in _loc_forms(view):
            by_real.setdefault(original, set()).add(shown)
        for original, showns in by_real.items():
            if len(showns) > 1:
                splits.append(f"{case_id}: {original!r} -> {sorted(showns)}")

    check(not leaks,
          f"corpus replay: no real street leaks ({checked_values} message LOC values)",
          f"leaks={leaks[:5]}")
    check(not splits,
          f"corpus replay: no value split into two substitutes ({len(cases)} cases)",
          f"splits={splits[:5]}")


def main() -> int:
    load_dev_bundle()
    _check_composite()
    _check_two_entities()
    _check_no_hybrid()
    _check_a2_type_word()
    _replay_corpus()
    failures = [name for ok, name, _ in RESULTS if not ok]
    print()
    print("=" * 72)
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} passed")
    if failures:
        print("LOC acceptance NOT in place:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("LOC acceptance: composite, two entities, no hybrid and A2 all hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
