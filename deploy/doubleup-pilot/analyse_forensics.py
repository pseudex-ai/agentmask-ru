"""Forensics v2 — an entity ledger across the hops, then the defect classes.

v1 grouped replacement rows by their RAW surface, so the very thing the owner
called out slipped through: «улице Ленина 14, квартира 5», «Москве, ул. Ленина 14,
кв. 5» and «улицей Ленина» all have the same referent and three different
substitutes, yet no two raw strings are equal. This version canonicalises each
value to an ENTITY first (phone digits, email fold, person stems, address
street+house+flat), then compares the substitute signatures of that entity
across every hop and attempt.

Outputs, in .state/qa/forensics/:
  ledger.json          every entity with every hop: path, real surface, substitute
  defects.json         the classified defects, with instance rows
  and a human-readable report on stdout.

Classes:
  A  one entity, several substitutes (instability / «две подмены»)
  A2 one person, two identities (same surname+given, different substitute)
  C  one substitute, two entities (collision)
  D  over-masking (masked non-PII, wrong type, system date)
  E  real value present in the model request (lost masking)
  F  unresolved / placeholder (REDACTED, base_token null)
  G  format drift per hop (digits, word count, initials, address shape)
  H  tool hop received a substitute (fake) instead of a real value
  I  substitute left in the restored answer

    python3 analyse_forensics.py
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORENSICS = HERE / ".state" / "qa" / "forensics"
PHONE = re.compile(r"\+?\d[\d\s\-()]{8,}\d")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")
PLACEHOLDER = re.compile(r"REDACTED[0-9a-fA-F]*|<<[^>]*>>|\{\{[^}]*\}\}|\[[A-Z_]{3,}\]")
HAS_DIGIT = re.compile(r"\d")
PII_TYPES = {"PHONE", "EMAIL", "NAME", "SNILS", "INN", "CARD", "PASSPORT", "ADDR", "LOC",
             "DOB", "DATE", "BIRTH_CERT", "MILITARY_ID", "VEHICLE_DOC", "OGRN", "OGRNIP",
             "ACCOUNT", "IBAN", "VIN", "OMS", "UIN", "LOYALTY", "IMEI", "ICCID", "EPTS",
             "CARD_VERIFICATION_CODE", "ISSUER_OTP"}
GENERIC = {"ул", "улица", "улице", "улицей", "улицу", "улицы", "улицами", "улицам",
           "улицах", "д", "дом", "дому", "домом", "кв", "квартира", "квартиру",
           "квартиры", "квартирой", "г", "город", "городе", "города", "пр", "проспект",
           "пер", "переулок", "наб", "набережная", "оф", "офис", "эт", "этаж",
           "район", "обл", "область", "пункт", "пункта", "пункте", "посёлок",
           "поселок", "деревня", "село", "станица", "аул", "корпус", "корп", "стр",
           "строение", "литера", "лит", "шоссе", "проезд", "бульвар", "площадь",
           "тупик", "аллея", "микрорайон", "мкр", "тракт", "дорога", "линия"}


def _street_like_word(low: str) -> bool:
    """A street-type word in ANY case form is not a street NAME."""
    return low in GENERIC or low.startswith(("улиц", "переул", "просп", "проезд",
                                              "бульвар", "площад", "набереж",
                                              "шоссе", "тупик", "алле", "микрорайон",
                                              "тракт", "дорог", "лини"))
CITIES = {"москва", "москве", "москву", "москвой", "питер", "спб", "санкт",
          "петербург", "петербурге", "новосибирск", "екатеринбург", "казань"}


def as_text(value) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def phone_digits(value: str) -> str:
    d = re.sub(r"\D", "", value or "")
    if len(d) == 11 and d[0] in "78":
        d = "7" + d[1:]
    elif len(d) == 10:
        d = "7" + d
    return d


def fold(value: str) -> str:
    return (value or "").casefold().replace("ё", "е")


def stems(words, length: int = 5) -> tuple[str, ...]:
    return tuple(sorted({fold(word)[:length] for word in words if len(word) > 2}))


def is_initials(word: str) -> bool:
    return bool(re.fullmatch(r"[А-ЯЁA-Z]\.?(?:[А-ЯЁA-Z]\.?)?", word or ""))


def addr_parts(value: str) -> tuple[str, str, str] | None:
    """street stem | house digits | flat digits — the identity of an address."""
    text = re.sub(r"[«»\"'`*]", " ", value or "")
    tokens = re.findall(r"[А-Яа-яЁёA-Za-z\-]+|\d+", text)
    street = ""
    house = ""
    flat = ""
    for position, token in enumerate(tokens):
        low = fold(token)
        if token.isdigit():
            if street and not house:
                house = token
            elif flat is not None and street and house and not flat:
                flat = token
            continue
        if _street_like_word(low):
            continue
        # A TOWN IN ANY CASE IS NOT THE STREET. «Москвы, улицы Каштановой» —
        # «москвы» was not in the list of Moscow's forms, so the city stem became
        # the address key and one address split into two. Compare the first five
        # letters of the known forms, and take the street NAME from any case (a
        # street written in the genitive is lower-case after its type word).
        if low in CITIES or any(len(city) >= 5 and low.startswith(city[:5])
                                for city in CITIES):
            continue
        if not street and len(token) > 2:
            street = low[:4]
    # a flat follows «кв»/«квартира» explicitly; prefer that reading
    match = re.search(r"(?:кв|квартир\w*)\.?\s*(\d+)", text, re.IGNORECASE)
    if match:
        flat = match.group(1)
    if not street:
        return None
    return (street, house, flat)


def entity_of(row: dict) -> tuple[str, str]:
    """(class, canonical key) — the referent, not the wording."""
    kind = row.get("type") or "?"
    real = row.get("real") or ""
    if kind == "PHONE":
        return ("PHONE", phone_digits(real))
    if kind == "EMAIL":
        return ("EMAIL", re.sub(r"[^a-z0-9@.]", "", fold(real)))
    if kind == "NAME":
        words = [word for word in re.findall(r"[А-Яа-яЁёA-Za-z\-]+", real) if not is_initials(word)]
        # THREE LETTERS PER PART, BECAUSE CASE LIVES IN THE ENDING. Five-letter
        # stems split «Анна/Анне/Анну/Анны» into four entities — one person's
        # declensions counted as an identity split, and the substitute they SHARE
        # reported as a collision. Three letters survive the ending of a Russian
        # given name and are still specific enough for an instrument.
        return ("NAME", "|".join(sorted({fold(word)[:3] for word in words if len(word) > 2})))
    if kind in ("ADDR", "LOC"):
        parts = addr_parts(real)
        if parts:
            return ("ADDR", "|".join(parts))
        return ("LOC", fold(real).strip())
    if kind in ("DOB", "DATE"):
        return ("DATE", re.sub(r"\D", "", real)[:8])
    return (kind, fold(real).strip())


def _substitute_signature(entity_type: str, words: list[str]) -> str:
    """The substitute as a NAME OR A PLACE, not as a string.

    The engine inflects the substitute to the case of the mention («Раису» for
    «Екатерину», «Раисы» for «Екатерины»): that is the same person, and a
    raw-string signature counted it as a second substitute — the one false
    positive the first analysis left in the person class. A street is compared
    by its stem and its numbers, so a case ending or punctuation cannot pretend
    to be another address.
    """
    if entity_type == "NAME":
        # ONE PERSON IS ONE SURNAME, AND A SURNAME IS THREE LETTERS. The fake
        # given name and patronymic are re-drawn per writing («Наумов Лев
        # Павлович» / «Наумова Льва Павловича»), but the surname is what makes
        # the model see one family — and the case ending («Лев»/«Льва», «Майя»/
        # «Майи») was the fourth character that split a stable identity in two.
        return words[0].casefold()[:3] if words else ""
    if entity_type in ("LOC", "ADDR"):
        parts = []
        for word in words:
            digits = re.sub(r"\D+", "", word)
            if digits:
                parts.append(digits)
            else:
                parts.append(word.casefold()[:5])
        return "|".join(parts)
    return "|".join(words)


def substitute_of(row: dict) -> tuple[str, str]:
    """The substitute's signature in the same space as the entity key."""
    shown = row.get("shown") or ""
    kind = row.get("type") or "?"
    if kind == "PHONE":
        return ("PHONE", phone_digits(shown))
    if kind == "EMAIL":
        return ("EMAIL", re.sub(r"[^a-z0-9@.]", "", fold(shown)))
    if kind == "NAME":
        words = [word for word in re.findall(r"[А-Яа-яЁёA-Za-z\-]+", shown) if not is_initials(word)]
        return ("NAME", "|".join(stems(words)))
    if kind in ("ADDR", "LOC"):
        parts = addr_parts(shown)
        if parts:
            return ("ADDR", "|".join(parts))
        return ("LOC", fold(shown).strip())
    return (kind, fold(shown).strip())


STREET_TYPE = re.compile(
    r"(?i)(?<![а-яё])(?:ул|улиц\w*|переул\w*|проспект\w*|пр-т|проезд\w*|бульвар\w*|"
    r"площад\w*|набережн\w*|шоссе|тупик\w*|алле\w*|дорог\w*|тракт\w*|линия|микрорайон\w*)"
    r"(?![а-яё])")


def over_mask_reason(row: dict) -> str | None:
    """Why this masked span does not look like personal data. A WIDE net: the
    report puts candidates in front of a human, it never asserts from a heuristic
    alone. Each reason is a hypothesis to check against the detector."""
    kind = row.get("type") or ""
    real = (row.get("real") or "").strip()
    if len(real) < 3:
        return None
    if kind in PII_TYPES and kind not in ("NAME", "LOC", "ADDR", "DATE", "DOB"):
        return None  # carries its own proof (checksum/shape)
    if PHONE.search(real) and len(phone_digits(PHONE.search(real).group())) >= 10:
        return None
    if EMAIL.search(real):
        return None
    if kind == "NAME":
        if not any(word[:1].isupper() for word in real.split()):
            return "masked as NAME but carries no capitalised person shape"
        return None
    if kind in ("DATE", "DOB"):
        digits = re.sub(r"\D", "", real)
        if len(digits) == 8 and digits.startswith("2026"):
            return "current-year date (system prompt «сегодня») masked as DOB"
        return None
    if kind == "ADDR":
        if not HAS_DIGIT.search(real) and len(real.split()) < 2:
            return "address span without a house number and without a street phrase"
        if fold(real).startswith(("последн", "предыдущ", "следующ")):
            return "ordinal/quantity phrase accepted as a street"
        return None
    if kind == "LOC":
        # A MASKED ADDRESS IS NOT OVER-MASKING. The old line flagged every LOC
        # row, and 88 of them in one run were the customer's own address
        # («улице Ленина 14, квартира 5»): the reason text said «check whether it
        # is a place reference», which is the REPORT's job, not the flag's.
        if not any(char.isdigit() for char in real) and len(real.split()) <= 2:
            # A STREET IS NOT A BARE SETTLEMENT. «улица Ленина», «улицей
            # Ленина», «улицы Абрикосовая» were flagged as settlements and the
            # flag fired on the engine's own streets — 22 false over-mask
            # records in one run. A street-type word (or a known street form)
            # makes the span an address, which is what the engine masks.
            if STREET_TYPE.search(real):
                return None
            return "a bare settlement was masked"
        return None
    return "masked with no personal-data shape"


LETTER_SPACED = re.compile(r"^[А-ЯЁA-Z](?:-[а-яёa-z])+$")


def _name_words(text: str) -> list[str]:
    return [word for word in re.findall(r"[А-Яа-яЁёA-Za-z\-]+", text)
            if not is_initials(word)]


def _surname_only_ambiguity(entry: dict, signatures: dict) -> bool:
    """True when the ONLY evidence linking these forms is a shared surname.

    The engine links a lone surname to a full name when the conversation holds
    exactly one person with it; it refuses when the data cannot decide, and that
    refusal shows up here as several substitutes. Only that refusal is excused:
    if any named form's substitute surname equals the lone form's, the family is
    the same and the split is the engine's, not the data's.
    """
    named_families: set[str] = set()
    lone_families: set[str] = set()
    for hops in signatures.values():
        for hop in hops:
            shown_words = re.findall(r"[А-Яа-яЁёA-Za-z\-]+", hop.get("shown") or "")
            family = shown_words[0].casefold()[:4] if shown_words else ""
            # A NAMED FORM is anything wider than the surname: a second word or
            # an initial. «Кузнецова Д. А.» counts as named even though the
            # initials are not full words.
            wide = (len(_name_words(hop["real"])) >= 2
                    or len(re.findall(r"[А-Яа-яЁёA-Za-z\-]+", hop["real"])) >= 2)
            if wide:
                named_families.add(family)
            else:
                lone_families.add(family)
    if not lone_families or not named_families:
        return False
    return not (named_families & lone_families)


def analyse(document: dict) -> tuple[dict, list, dict]:
    tester = document.get("tester")
    ledger: dict[str, dict] = {}
    collisions: dict[str, set] = defaultdict(set)
    defects: dict[str, list] = defaultdict(list)

    # Every substitute this run ever showed or named. The echo/reserve leg
    # answers with a substitute the transcript already carries and mints
    # nothing — `base_token: null` there means «nothing was created», not
    # «unresolved», and counting it as a defect hides the real ones.
    known_fakes: set[str] = set()
    for attempt in document.get("attempts") or []:
        for row in attempt.get("replacements") or []:
            for field in ("shown", "base_token"):
                value = (row.get(field) or "").strip()
                if len(value) >= 4:
                    known_fakes.add(value)

    for number, attempt in enumerate(document.get("attempts") or []):
        model_request = as_text(attempt.get("model_request"))
        restored = as_text(attempt.get("restored_response"))
        shown_signatures = {}
        for row in attempt.get("replacements") or []:
            if not row.get("real") or row.get("shown") is None:
                continue
            if LETTER_SPACED.match((row.get("real") or "").strip()) or LETTER_SPACED.match(
                    (row.get("shown") or "").strip()):
                # THE MODEL SPELLED A SUBSTITUTE OUT LETTER BY LETTER («Л-у-г-а»)
                # or the probe wrote one that way: neither is a person writing a
                # name, and counting it as an identity split blames the engine
                # for the model's formatting.
                continue
            cls, key = entity_of(row)
            sub_cls, sub_key = substitute_of(row)
            entry = ledger.setdefault(f"{cls}:{key}", {
                "tester": tester, "class": cls, "key": key,
                "type": row.get("type"), "real_forms": set(), "hop": [],
            })
            entry["real_forms"].add(row["real"])
            entry["hop"].append({"attempt": number, "path": row.get("path"),
                                 "real": row["real"], "shown": row.get("shown"),
                                 "type": row.get("type"), "base_token": row.get("base_token")})
            shown_signatures.setdefault(f"{sub_cls}:{sub_key}", []).append(row)

            if row.get("base_token") is None and row.get("shown") != row.get("real"):
                if (row.get("shown") or "").strip() in known_fakes:
                    defects["F_echo"].append({
                        "tester": tester, "attempt": number, "path": row.get("path"),
                        "type": row.get("type"), "real": row["real"],
                        "shown": row.get("shown"),
                        "why": "the echo/reserve leg answered with a substitute this "
                               "run already carries; nothing was minted"})
                else:
                    defects["F_unresolved"].append({
                        "tester": tester, "attempt": number, "path": row.get("path"),
                        "type": row.get("type"), "real": row["real"],
                        "shown": row.get("shown"),
                        "reason": "base_token null and the substitute is not one "
                                  "this run already showed"})
            if PLACEHOLDER.search(row.get("shown") or ""):
                if row.get("type") == "OPAQUE":
                    # AN OPAQUE VALUE IS MASKED BY DESIGN: the customer put a
                    # non-shaped value under a field that names a numbered
                    # document, and the policy is «never in the clear», rendered
                    # as a REDACTED marker instead of a fake number. It is not
                    # an unresolved substitute.
                    defects["F_by_design"].append({
                        "tester": tester, "attempt": number, "path": row.get("path"),
                        "type": row.get("type"), "real": row["real"],
                        "shown": row.get("shown"),
                        "why": "numeric field with a non-shaped value: masked as OPAQUE"})
                    continue
                defects["F_unresolved"].append({
                    "tester": tester, "attempt": number, "path": row.get("path"),
                    "type": row.get("type"), "real": row["real"], "shown": row.get("shown"),
                    "reason": "placeholder instead of a substitute"})
            reason = over_mask_reason(row)
            if reason:
                defects["D_overmask"].append({
                    "tester": tester, "attempt": number, "path": row.get("path"),
                    "type": row.get("type"), "real": row["real"], "shown": row.get("shown"),
                    "why": reason})

            # G. format drift between real and substitute, per type
            if row.get("type") == "PHONE":
                if len(phone_digits(row["real"])) != len(phone_digits(row.get("shown") or "")):
                    defects["G_format"].append({
                        "tester": tester, "attempt": number, "type": "PHONE",
                        "real": row["real"], "shown": row.get("shown"),
                        "why": f"digits {len(phone_digits(row['real']))}->"
                               f"{len(phone_digits(row.get('shown') or ''))}"})
            if row.get("type") == "NAME":
                real_words = len([w for w in row["real"].split() if w])
                shown_words = len([w for w in (row.get("shown") or "").split() if w])
                if real_words != shown_words:
                    defects["G_format"].append({
                        "tester": tester, "attempt": number, "type": "NAME",
                        "real": row["real"], "shown": row.get("shown"),
                        "why": f"words {real_words}->{shown_words}"})
                if any(is_initials(word) for word in row["real"].split()) and not any(
                        is_initials(word) for word in (row.get("shown") or "").split()):
                    defects["G_format"].append({
                        "tester": tester, "attempt": number, "type": "NAME",
                        "real": row["real"], "shown": row.get("shown"),
                        "why": "initials expanded to a full name; the model cannot map it back"})
            if row.get("type") in ("ADDR", "LOC"):
                real_parts = addr_parts(row["real"])
                shown_parts = addr_parts(row.get("shown") or "")
                if real_parts and shown_parts:
                    if (bool(real_parts[1]) != bool(shown_parts[1])
                            or bool(real_parts[2]) != bool(shown_parts[2])):
                        defects["G_format"].append({
                            "tester": tester, "attempt": number, "type": row["type"],
                            "real": row["real"], "shown": row.get("shown"),
                            "why": f"address shape {real_parts}->{shown_parts}"})

        # E. lost masking: the real value present in the request the provider got
        for row in attempt.get("replacements") or []:
            real = (row.get("real") or "").strip()
            if row.get("type") not in PII_TYPES or len(real) < 5:
                continue
            if row.get("type") == "LOC" and not any(ch.isdigit() for ch in real) \
                    and len(real.split()) <= 2:
                # A BARE SETTLEMENT IS REAL BY DESIGN (D-081/W8): a courier
                # cannot deliver to a fake town, so the town stays and only the
                # street and the house are substituted. Counting the town as
                # leaked personal data would report the rule as a defect.
                continue
            if real in model_request:
                defects["E_leak"].append({
                    "tester": tester, "attempt": number, "path": row.get("path"),
                    "type": row.get("type"), "real": real,
                    "why": "real value appears verbatim in the model request"})

        # I. restoration: the substitute still sitting in the restored answer
        for row in attempt.get("replacements") or []:
            shown = (row.get("shown") or "").strip()
            real = (row.get("real") or "").strip()
            if len(shown) < 5 or shown == real:
                continue
            if shown in restored:
                defects["I_restore_leftover"].append({
                    "tester": tester, "attempt": number, "type": row.get("type"),
                    "real": real, "shown": shown,
                    "why": "substitute still present in the restored answer"})
        for match in PLACEHOLDER.finditer(restored):
            defects["F_unresolved"].append({
                "tester": tester, "attempt": number, "path": "restored_response",
                "type": "?", "real": "", "shown": match.group(),
                "reason": "placeholder in the restored answer"})

        # H. the tool hop: a substitute in arguments means a fake reached the tool
        signatures = set()
        for row in attempt.get("replacements") or []:
            shown = (row.get("shown") or "").strip()
            if len(shown) >= 5:
                signatures.add(shown)
        for dispatch in attempt.get("tool_dispatches") or []:
            arguments = as_text(dispatch.get("arguments") if isinstance(dispatch, dict) else dispatch)
            for signature in signatures:
                if signature in arguments:
                    defects["H_tool_fake"].append({
                        "tester": tester, "attempt": number, "shown": signature,
                        "arguments": arguments[:500],
                        "why": "a substitute reached the tool arguments"})
        # ONE SUBSTITUTE, SEVERAL ENTITIES — entities, not attempts. Every
        # attempt of one dialogue shows the same substitute for the same person;
        # counting attempts reported the stable identity as a collision (64
        # «collisions» that were one entity seen eight times).
        for key, rows in shown_signatures.items():
            for row in rows:
                cls, entity = entity_of(row)
                collisions[key].add((tester, f"{cls}:{entity}"))

    for key, entry in ledger.items():
        entry["real_forms"] = sorted(entry["real_forms"])
        signatures = {}
        for hop in entry["hop"]:
            sub = substitute_of({"type": hop["type"], "shown": hop["shown"]})
            signatures.setdefault(_substitute_signature(entry["type"], sub), []).append(hop)
        if len(signatures) > 1:
            cls = entry["class"]
            if cls == "NAME" and _surname_only_ambiguity(entry, signatures):
                # A LONE SURNAME DOES NOT NAME A PERSON. «Кузнецова» and
                # «Кузнецова Д. А.» may be one woman or two people sharing a
                # surname, and the engine's single-candidate rule refuses to
                # guess — minting a fresh substitute is the honest answer, not a
                # defect. Reported separately so it cannot hide a real split:
                # when the substitutes' surnames MATCH, the family is the same
                # and the split is real.
                defects["S_surname_ambiguous"].append({
                    "tester": tester, "key": entry["key"],
                    "real_forms": entry["real_forms"],
                    "substitutes": sorted(signatures),
                    "why": "lone surname and named forms with different substitute "
                           "surnames: identity cannot be decided from the data"})
                continue
            defects["A_two_substitutes"].append({
                "tester": tester, "class": cls, "key": entry["key"],
                "type": entry["type"], "real_forms": entry["real_forms"],
                "substitutes": {sig: [{"attempt": h["attempt"], "path": h["path"],
                                       "shown": h["shown"]} for h in hops[:6]]
                                for sig, hops in signatures.items()}})
            if cls == "NAME":
                defects["A2_person_split"].append({
                    "tester": tester, "key": entry["key"], "real_forms": entry["real_forms"],
                    "substitutes": sorted(signatures)})

    for key, owners in collisions.items():
        if len(owners) > 1:
            defects["C_collision"].append({"key": key, "owners": sorted(owners)})

    return ({"tester": tester, "entities": len(ledger),
             "attempts": len(document.get("attempts") or [])}, list(ledger.values()),
            dict(defects))


def main() -> None:
    documents = [json.loads(path.read_text()) for path in sorted(FORENSICS.glob("tester-*.json"))]
    if not documents:
        raise SystemExit("no transcripts — run collect_forensics.py first")
    summaries, ledger, all_defects = [], [], defaultdict(list)
    for document in documents:
        summary, entities, defects = analyse(document)
        summaries.append(summary)
        ledger.extend(entities)
        for name, rows in defects.items():
            all_defects[name].extend(rows)

    totals = {name: len(rows) for name, rows in all_defects.items()}
    print("=" * 100)
    print("HOP FORENSICS v2 — entities, not raw strings")
    print("=" * 100)
    for summary in summaries:
        print(f"  {summary['tester']}: attempts {summary['attempts']}, entities {summary['entities']}")
    print("  totals:", dict(sorted(totals.items())))

    print("\nA. ONE ENTITY, SEVERAL SUBSTITUTES")
    for item in all_defects["A_two_substitutes"]:
        real = " / ".join(item["real_forms"][:3])
        forms = list(item["substitutes"])
        print(f"  [{item['tester']}] {item['class']} «{real[:90]}» -> {len(forms)} substitutes")
        for sig, hops in list(item["substitutes"].items())[:6]:
            print(f"      {sig[:90]}   (a{hops[0]['attempt']}, {len(hops)} hops)")

    print("\nA2. ONE PERSON, TWO IDENTITIES")
    for item in all_defects["A2_person_split"]:
        print(f"  [{item['tester']}] «{item['real_forms'][0]}» -> {item['substitutes']}")

    print("\nC. ONE SUBSTITUTE, SEVERAL ENTITIES")
    for item in all_defects["C_collision"]:
        print(f"  {item['key']} -> {item['owners']}")

    print("\nD. OVER-MASKING")
    grouped = defaultdict(list)
    for row in all_defects["D_overmask"]:
        grouped[(row["type"], row["real"], row["shown"])].append((row["tester"], row["attempt"]))
    for (kind, real, shown), where in sorted(grouped.items(), key=lambda kv: -len(kv[1]))[:40]:
        print(f"  {kind:6s} «{real[:60]}» -> «{shown[:50]}»  ×{len(where)}")

    print("\nE. LOST MASKING")
    for row in all_defects["E_leak"][:40]:
        print(f"  [{row['tester']}] a{row['attempt']} {row['type']} «{row['real'][:60]}» at {row['path']}")

    print("\nF. UNRESOLVED / PLACEHOLDER")
    for row in all_defects["F_unresolved"][:40]:
        print(f"  [{row['tester']}] a{row['attempt']} {row['reason']}: shown={row['shown']!r} real={row['real']!r}")

    print("\nG. FORMAT DRIFT")
    seen = set()
    for row in all_defects["G_format"]:
        marker = (row["type"], row["real"], row["shown"], row["why"])
        if marker in seen:
            continue
        seen.add(marker)
        print(f"  {row['why']:45s} «{row['real'][:45]}» -> «{row['shown'][:45]}» ×?[{row['tester']}a{row['attempt']}]")

    print("\nH. TOOL HOP RECEIVED A SUBSTITUTE")
    for row in all_defects["H_tool_fake"][:20]:
        print(f"  [{row['tester']}] a{row['attempt']} «{row['shown']}» in {row['arguments']!r}")

    print("\nI. SUBSTITUTE LEFT IN THE RESTORED ANSWER")
    for row in all_defects["I_restore_leftover"][:30]:
        print(f"  [{row['tester']}] a{row['attempt']} {row['type']} shown=«{row['shown']}» real=«{row['real']}»")

    (FORENSICS / "ledger.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=1))
    (FORENSICS / "defects.json").write_text(json.dumps(
        {"summaries": summaries, "totals": totals, "defects": all_defects},
        ensure_ascii=False, indent=1))
    print("\nwritten:", FORENSICS / "ledger.json", "and", FORENSICS / "defects.json")


if __name__ == "__main__":
    main()
