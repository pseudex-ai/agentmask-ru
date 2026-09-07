"""The per-field divergence taxonomy: what happened to one value in one field.

Given the CONTROL arm's value for a field, the INTERVENTION arm's detokenised
value, the real item the control value binds to, and the substitute the model
read, decide ONE kind — first match wins — and, separately, what the model DID
to what it saw (`transform_of`). Two questions, two columns: a corpus whose
control arm only ever copies verbatim has failed to provoke anything, whatever
the effect says.

Pure functions, no I/O, no `pseudex`. The address splitter is the benchmark's
own (`schema._address_parts` via `parts.parts_of`) — the engine may not judge
whether its own parts came back.
"""
from dataclasses import dataclass

from bench.agentpii3.schema import classify_break, same_value
from bench.agentpii4 import derive
from bench.agentpii4.parts import is_part_of, parts_of, roles_covered
from bench.agentpii4.schema import PiiItem
from bench.agentpii4.tools import FieldSpec

DIVERGENCE_KINDS: tuple[str, ...] = (
    "agree", "absent", "absent_required", "extra", "residual", "validated_refused", "ref_refused",
    "control_erred", "derived", "same_person_variant", "other_person", "stale_value",
    "container_embedded", "reformatted", "fragment", "composed", "other")
TRANSFORM_KINDS: tuple[str, ...] = (
    "verbatim", "reformatted", "fragment", "composed", "derived",
    "container_embedded", "invented", "absent")


@dataclass(frozen=True)
class FieldObs:
    """One field as observed in one arm."""

    present: bool
    written: str        # what the model emitted (I: may hold a substitute)
    restored: str       # after unmask_arguments (C/C2: == written)
    parsed: str         # the mock's typed reading, "" when refused or absent
    refused_rule: str   # the mock's refusal rule, "" when accepted
    residual: tuple[str, ...]   # minted strings (whole or piece) still in `restored`


@dataclass(frozen=True)
class FieldVerdict:
    tool: str
    path: str
    pii_type: str
    item_id: str
    kind: str
    sub: str
    transform: str
    ref: str
    obs: str
    why: str


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold().replace("ё", "е")


def _typed_equal(left: str, right: str, spec: FieldSpec) -> bool:
    if spec.kind in ("plain", "enum", "derived"):
        # A derived value is a postcode, an age, an initial: compared as the
        # string it is, never through its SOURCE type's equality — two postcodes
        # read as addresses would both parse to nothing and «agree».
        if spec.derive == "postcode_zone":
            # The city determines the first three digits and nothing else; the
            # rest is whatever the model made up, in BOTH arms.
            return _digits(left)[:3] == _digits(right)[:3]
        if spec.derive == "age":
            return _digits(left) == _digits(right)
        return _norm(left) == _norm(right)
    if spec.role in ("house", "flat", "entrance", "building"):
        # «131а» and «131 а» are one house; the parser accepts both.
        return _norm(left).replace(" ", "") == _norm(right).replace(" ", "")
    if spec.pii_type:
        try:
            return same_value(left, right, spec.pii_type)
        except Exception:  # noqa: BLE001 - an unknown type is compared as text
            return _norm(left) == _norm(right)
    return _norm(left) == _norm(right)


def bind_item(spec: FieldSpec, ref: FieldObs, items: list[PiiItem]) -> PiiItem | None:
    """The real item the CONTROL wrote into this field, by typed equality of
    the whole value or of the role part. None when nothing binds."""
    if not spec.pii_type or not ref.present:
        return None
    candidates: list[PiiItem] = []
    for item in items:
        if item.type != spec.pii_type or item.stale:
            continue
        if spec.role and spec.role in item.parts:
            if _norm(ref.parsed or ref.restored) == _norm(item.parts[spec.role]):
                candidates.append(item)
                continue
            if spec.role == "digits" and _digits(ref.restored)[-10:] == _digits(item.parts[spec.role])[-10:]:
                candidates.append(item)
                continue
        try:
            if same_value(ref.restored, item.canonical, item.type) or same_value(ref.restored, item.value, item.type):
                candidates.append(item)
                continue
        except Exception:  # noqa: BLE001
            pass
        if is_part_of(ref.restored, item.parts) or is_part_of(ref.parsed, item.parts):
            candidates.append(item)
    if not candidates:
        return None
    return candidates[0]


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def _derived_ok(spec: FieldSpec, value: str, source_parts: dict[str, str], now: str) -> bool | None:
    """Does a derived value follow from these source parts? None = unverifiable."""
    if spec.derive == "postcode_zone":
        return derive.postcode_matches(value, source_parts.get("city", ""))
    if spec.derive == "timezone":
        accepted = derive.timezone(source_parts.get("city", ""))
        return (value in accepted) if accepted else None
    if spec.derive == "age":
        accepted = derive.age(source_parts.get("iso", ""), now)
        return (_digits(value) in accepted) if accepted else None
    if spec.derive == "gender":
        accepted = derive.gender(source_parts)
        return derive.gender_matches(value, accepted) if accepted else None
    if spec.derive == "initials":
        accepted = derive.initials(source_parts)
        return derive.initials_matches(value, accepted) if accepted else None
    if spec.derive == "translit":
        words = tuple(word for role in ("surname", "given") for word in [source_parts.get(role, "")] if word)
        return derive.translit_matches(value, words) if words else None
    return None


def transform_of(written: str, seen: str, seen_parts: dict[str, str], spec: FieldSpec,
                 now: str) -> str:
    """What the model DID to the value it read, whatever the outcome."""
    if not written:
        return "absent"
    if not seen:
        return "invented"
    if _norm(written) == _norm(seen):
        return "verbatim"
    if spec.container and _norm(seen) in _norm(written):
        return "container_embedded"
    if spec.derive:
        verdict = _derived_ok(spec, written, seen_parts, now)
        if verdict:
            return "derived"
    role = is_part_of(written, seen_parts)
    if role:
        return "verbatim" if spec.role == role else "fragment"
    if roles_covered(written, seen_parts) >= 2 and spec.role:
        return "composed"
    if spec.pii_type:
        try:
            if same_value(written, seen, spec.pii_type):
                return "reformatted"
        except Exception:  # noqa: BLE001
            pass
    if _norm(seen) in _norm(written):
        return "composed"
    return "invented"


def classify_field(spec: FieldSpec, ref: FieldObs, obs: FieldObs, real: PiiItem | None,
                   others: list[PiiItem], stale: list[PiiItem],
                   substitute: tuple[str, dict[str, str]] | None, now: str,
                   tool: str, path: str,
                   alternates: tuple[tuple[str, dict[str, str]], ...] = ()) -> FieldVerdict:
    """The ordered decision list. First match wins.

    `alternates` are the OTHER substitutes the model read for the same person
    — one identity is minted twice when the message says «букин сергей» and
    the CRM record the tool returned says «Букин Сергей Иванович». Initials
    derived from the second are still derived from a substitute, and a check
    that knows only the first filed them as `misderived`.
    """
    item_id = real.id if real else ""
    seen, seen_parts = substitute if substitute else ("", {})
    candidates = tuple(one for one in (substitute, *alternates) if one is not None)
    transform = "invented"
    for seen_one, parts_one in candidates or ((seen or ref.restored, seen_parts or (dict(real.parts) if real else {})),):
        transform = transform_of(obs.written, seen_one or ref.restored,
                                 parts_one or (dict(real.parts) if real else {}), spec, now)
        if transform != "invented":
            break

    def verdict(kind: str, sub: str = "", why: str = "") -> FieldVerdict:
        return FieldVerdict(tool, path, spec.pii_type, item_id, kind, sub, transform,
                            ref.restored, obs.restored, why)

    if not ref.present and not obs.present:
        return verdict("agree", "both_absent")
    if ref.present and not obs.present:
        # AN OPTIONAL FIELD ONE ARM OMITTED IS A COIN TOSS; A REQUIRED ONE IS
        # NOT. `FieldSpec.required` stood on 69 specifications and was read by
        # no scorer, so «the control filled the field the tool demands and the
        # gateway arm did not» scored as agreement. Two kinds, because the
        # optional half of that argument still holds.
        return verdict("absent_required" if spec.required else "absent")
    if not ref.present and obs.present:
        return verdict("extra")
    if obs.residual and not _typed_equal(obs.parsed or obs.restored, ref.parsed or ref.restored, spec):
        # A substitute that happens to EQUAL the real value (a fake city drawn
        # from the same pool as the customer's) is not a residual: the tool got
        # the right value. Only a residual that changed the value counts.
        return verdict("residual", "", f"подмена дошла до инструмента: {obs.residual[0]}")
    if obs.refused_rule and not ref.refused_rule:
        return verdict("validated_refused", obs.refused_rule)
    if ref.refused_rule and not obs.refused_rule:
        return verdict("ref_refused", ref.refused_rule)
    if _typed_equal(obs.parsed or obs.restored, ref.parsed or ref.restored, spec):
        return verdict("agree")
    # THE CONTROL CAN BE WRONG, and then «I differs from C» is the gateway being
    # RIGHT. «восемь девятьсот пятьдесят пяять…» was heard by the control as
    # +79005556677 and restored by the gateway as the corpus's +79505556677;
    # «сорок девятнадцать» became 4919 in the control and 4019 through the
    # gateway. The corpus canonical is the tie-breaker, and the class is kept
    # apart because it is neither agreement nor a defect of the gateway.
    if spec.kind == "identity" and spec.pii_type and real is None:
        truth = bind_item(spec, obs, [item for item in others if not item.stale] + ([real] if real else []))
        if truth is not None:
            return verdict("control_erred", truth.id, "контроль ошибся; шлюз восстановил эталон корпуса")
    if spec.kind == "derived":
        if real is not None:
            from_real = _derived_ok(spec, obs.restored, dict(real.parts), now)
            if from_real:
                return verdict("agree", "derived_from_real")
        # СВЯЗЫВАНИЕ ПО РАВЕНСТВУ НЕ РАБОТАЕТ ДЛЯ ПРОИЗВОДНОГО, И ЭТО ДЕФЕКТ
        # ПРИБОРА, А НЕ ШЛЮЗА. `bind_item` ищет запись, чьё ЗНАЧЕНИЕ равно
        # написанному, а «BUKIN SERGEY» не равно ни «букин», ни «сергей» — оно
        # из них ВЫВЕДЕНО; вдобавок у производного поля `pii_type` пуст, и
        # `bind_item` выходит на первой строке. Поэтому `real` был None, и обе
        # ветки ниже давали `unverifiable` или `misderived` там, где оба плеча
        # написали корректный транслит ОДНОГО человека. Сам контроль пишет и
        # «SERGEI», и «SERGEY» — на живом прогоне 07.09 окончание «-ей» стоит
        # как EY 12 раз и как EI 7, — так что это шум модели, названный
        # дефектом шлюза.
        #
        # ЭТО НЕ ПОСЛАБЛЕНИЕ. Проверка строже равенства: ОБА плеча должны
        # выводиться из частей ОДНОЙ И ТОЙ ЖЕ настоящей записи, и запись должна
        # быть единственной. Транслит чужого человека, инициалы чужого
        # человека, возраст от чужой даты — всё это по-прежнему расхождение.
        if real is None and (spec.source_type or spec.pii_type):
            wanted = spec.source_type or spec.pii_type
            shared = [item for item in others
                      if item.type == wanted and not item.stale
                      and _derived_ok(spec, obs.restored, dict(item.parts), now)
                      and _derived_ok(spec, ref.restored, dict(item.parts), now)]
            if len(shared) == 1:
                return verdict("agree", "derived_from_real")
        unverifiable = False
        for _seen_one, parts_one in candidates:
            from_fake = _derived_ok(spec, obs.restored, parts_one, now)
            if from_fake:
                return verdict("derived", "from_substitute",
                               "значение выведено из ПОДМЕНЫ; восстановление недостижимо")
            if from_fake is None:
                unverifiable = True
        if unverifiable:
            return verdict("derived", "unverifiable")
        return verdict("other", "misderived")
    for other in others:
        if other.type == spec.pii_type:
            try:
                if same_value(obs.restored, other.canonical, other.type) or is_part_of(obs.restored, other.parts):
                    # THE SAME PERSON, ANOTHER SPELLING. The customer wrote
                    # «каллашникова 10»; the control, reading the typo, sent the
                    # directory's «Калашникова, 10» and bound to the directory
                    # item; the gateway returned the customer's own words, which
                    # are ALSO an item of this case — the message one. Ten fields
                    # on the 05.09 medium run were filed as `other_person` this
                    # way, and every one was one person, one place, two spellings.
                    # The identity's first segment names the person («p18.sugg0»,
                    # «p18.addr»); a different person has a different one.
                    if real is not None and _person_of(other.identity) == _person_of(real.identity):
                        return verdict("same_person_variant", other.id,
                                       "то же лицо и место в другом написании: контроль нормализовал, шлюз вернул как написано")
                    return verdict("other_person", other.identity)
            except Exception:  # noqa: BLE001
                continue
    for old in stale:
        if old.type == spec.pii_type:
            try:
                if same_value(obs.restored, old.canonical, old.type) or is_part_of(obs.restored, old.parts):
                    return verdict("stale_value", old.identity)
            except Exception:  # noqa: BLE001
                continue
    if spec.container:
        return verdict("container_embedded", "differs_inside")
    if spec.pii_type:
        try:
            if same_value(obs.restored, ref.restored, spec.pii_type):
                return verdict("reformatted")
        except Exception:  # noqa: BLE001
            pass
    if real is not None:
        if is_part_of(obs.restored, real.parts) and _norm(obs.restored) != _norm(ref.restored):
            return verdict("fragment", is_part_of(obs.restored, real.parts))
        if roles_covered(obs.restored, real.parts) >= 2 and spec.role:
            return verdict("composed")
        sub = classify_break(real, ref.restored, obs.restored,
                             [(one.type, one.canonical) for one in others])
        return verdict("other", sub)
    return verdict("other", "unbound")


def _person_of(identity: str) -> str:
    return identity.split(".", 1)[0]


def substitute_parts(pii_type: str, surface: str) -> dict[str, str]:
    return parts_of(pii_type, surface)


def main() -> int:
    from bench.agentpii4.schema import Locus
    failures = 0
    spec_postcode = FieldSpec("to_location.postal_code", "derived", "LOC", "", "postcode_zone", "LOC")
    real = PiiItem("i1", "LOC", "p", "ижевск улица клубная 85", "ижевск улица клубная 85",
                   {"city": "ижевск", "street": "клубная", "house": "85"},
                   Locus("message", 1, 0, 1, "", ""), "required", False, False)
    ref = FieldObs(True, "426034", "426034", "426034", "", ())
    obs = FieldObs(True, "196655", "196655", "196655", "", ())
    fake = ("Колпино, улица Ивовая 12", {"city": "колпино", "street": "ивовая", "house": "12"})
    v = classify_field(spec_postcode, ref, obs, real, [], [], fake, "2026-09-02", "t", "to_location.postal_code")
    if v.kind != "derived" or v.sub != "from_substitute":
        failures += 1
        print("FAIL derived", v)
    spec_phone = FieldSpec("number", "identity", "PHONE", "digits")
    ref2 = FieldObs(True, "+79164021187", "+79164021187", "+79164021187", "", ())
    obs2 = FieldObs(True, "+79990001122", "+79164021187", "+79164021187", "", ())
    v2 = classify_field(spec_phone, ref2, obs2, None, [], [], ("+79990001122", {"digits": "9990001122"}), "2026-09-02", "t", "number")
    if v2.kind != "agree" or v2.transform != "verbatim":
        failures += 1
        print("FAIL agree", v2)
    obs3 = FieldObs(True, "+79990001122", "+79990001122", "+79990001122", "", ("+79990001122",))
    v3 = classify_field(spec_phone, ref2, obs3, None, [], [], ("+79990001122", {"digits": "9990001122"}), "2026-09-02", "t", "number")
    if v3.kind != "residual":
        failures += 1
        print("FAIL residual", v3)
    obs4 = FieldObs(True, "89164021187", "89164021187", "", "phone_not_e164", ())
    v4 = classify_field(spec_phone, ref2, obs4, None, [], [], None, "2026-09-02", "t", "number")
    if v4.kind != "validated_refused":
        failures += 1
        print("FAIL refused", v4)
    spec_street = FieldSpec("address.street", "identity", "LOC", "street")
    real_addr = PiiItem("i2", "LOC", "p", "ленина 14 кв 5", "ленина 14 кв 5",
                        {"street": "ленина", "house": "14", "flat": "5"},
                        Locus("message", 1, 0, 1, "", ""), "required", False, False)
    ref5 = FieldObs(True, "Ленина", "Ленина", "ленина", "", ())
    obs5 = FieldObs(True, "улица Ленина", "улица Ленина", "улица ленина", "", ())
    v5 = classify_field(spec_street, ref5, obs5, real_addr, [], [], ("улица Речная", {"street": "речная"}), "2026-09-02", "t", "address.street")
    if v5.kind not in ("reformatted", "agree"):
        failures += 1
        print("FAIL street reformat", v5)
    print("taxonomy: PASS" if not failures else f"taxonomy: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
