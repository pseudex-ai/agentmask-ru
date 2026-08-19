"""The swap layer: tokenize text on the way to the model, detokenize on the way back.

Detection is decoupled — the caller passes the spans (from any detector), so the
proxy can use the full ensemble (regex + checksum + NER) and tests can use a
lighter one. Reverse uses longest-token-first to avoid prefix collisions.
"""

import json
import re

from pseudex.detect import Span
from pseudex import morph_names, morph_places
from pseudex.profiling import stage
from pseudex.vault import LOC_TOKEN_PATTERN, TOKEN_RE, Vault, name_key, place_key

# A number-like run (digits + phone separators), >=7 digits — a candidate for
# digit-core detokenization when the model reformatted a numeric token.
_NUM_RUN = re.compile(r"(?<![\d])[+(]?\d[\d\s().\-]{5,}\d(?!\d)")


def _splice(text: str, spans: list[tuple[int, int, str]]) -> str:
    """Apply replacements right-to-left so the offsets of the not-yet-applied
    spans stay valid."""
    result = text
    for start, end, value in sorted(spans, key=lambda span: span[0], reverse=True):
        result = result[:start] + value + result[end:]
    return result


def mask_text(text: str, vault: Vault, spans: list[Span]) -> str:
    """Replace detected PII with consistent tokens. Pure w.r.t. text; mutates vault.

    A span whose value is ALREADY a token we issued is left untouched. This is
    load-bearing, not defensive: a fake NAME or LOC is by construction a
    well-formed name or place, so when the model echoes one back inside a new
    message, detection finds it again. Masking it a second time would mint a
    fresh token, which (a) makes the person's identity change every turn, (b)
    breaks the provider's prefix cache because the prefix is no longer stable,
    and (c) — worst — makes detokenization return the intermediate TOKEN instead
    of the real value, so the tool executes on a plausible but WRONG person.

    The content cache hides this from the obvious test: re-masking the same RAW
    text is a cache hit. The failure only appears when the token comes back
    inside different surrounding text, which is exactly what a multi-turn agent
    does.

    KNOWN LIMIT: a real person whose name exactly equals a minted fake name would
    be passed through unmasked. That needs a fake-name pool far larger than the
    current seed list (see names.py) — the same production swap already planned."""
    return _splice(text, [
        (span.start, span.end, _token_for_text(span, vault))
        for span in spans
        if not vault.is_minted_token(span.value)
    ])


def _token_for_text(span: Span, vault: Vault) -> str:
    """The token as it should READ in this sentence.

    The vault stores one nominative token per person; the text needs it in the
    case the original was written in, or the sentence says «Позвоните Руслан
    Хвостов» and the model repairs the disagreement. A repaired token does not
    match the vault, and then the customer's tool executes on a person who does
    not exist — silently, which is the worst way for this to fail.

    Only NAME is inflected. Numbers and documents have no case, and LOC is
    generated as a whole phrase whose internal agreement is the generator's job.
    """
    token = vault.tokenize(span.value, span.entity_type)
    if span.entity_type == "LOC":
        # Same reason as NAME: a nominative phrase dropped into an oblique slot
        # reads as broken Russian, and broken Russian is what makes a model
        # rewrite the token instead of using it.
        case = morph_places.detect_case(span.value)
        if case is None or case == "nomn":
            return token
        return morph_places.inflect_place(token, case)
    if span.entity_type != "NAME":
        return token
    case = morph_names.detect_case(span.value)
    if case is None or case == "nomn":
        return token
    # Gender comes from the REAL person, not from re-reading the token. The two
    # agree by construction — the token was minted for this gender — and asking
    # the token again can only lose: a fake first name the dictionary happens
    # not to know (София) makes the whole span read as the wrong gender, and
    # then the surname is inflected as a man's.
    return morph_names.inflect_person(
        token, case, morph_names.detect_gender(span.value))


def unmask_text(text: str, vault: Vault) -> str:
    """Replace tokens with their real values, then catch numeric tokens the model
    REFORMATTED via a digit-signature match.

    Candidates are found by SHAPE (`Vault.TOKEN_RE`) and resolved in batched
    indexed lookups, so the cost tracks the length of the answer rather than the
    size of the vault. The previous approach loaded every token the org had ever
    minted and substring-scanned the text once per token, which made an org with
    100k tokens pay 100k scans on every single response."""
    with stage("unmask.total"):
        restored = _restore_reformatted(_restore_tokens(text, vault), vault)
        return _restore_inflected(restored, vault)


# The ГОСТ plate alphabet was chosen precisely because every letter in it has a
# Latin twin — that is why a Russian plate is readable abroad. It is also why a
# model happily rewrites «Р984ОМ003» as «R984OM003»: to it the two are the same
# string in two scripts. The rewritten form is no longer the token, so the vault
# misses it and the customer's tool receives the fake.
#
# Seen in a persona run, once in four round trips, on a real tool call. Phones
# have had a second line of defence since the digit-signature reindex — a plate
# is the same failure with a different alphabet, and this is its equivalent.
_PLATE_FOLD = str.maketrans("ABEKMHOPCTYXabekmhopctyx", "АВЕКМНОРСТУХавекмнорстух")


def _restore_tokens(text: str, vault: Vault) -> str:
    matches = list(TOKEN_RE.finditer(text))
    if not matches:
        return text
    candidates = {match.group() for match in matches}
    # Offer the Cyrillic reading of every candidate as well. A miss costs one
    # indexed point query, and folding is only meaningful for the plate alphabet
    # — any other token is unchanged by it, so nothing else can be affected.
    folded = {value: value.translate(_PLATE_FOLD) for value in candidates}
    values = vault.detokenize_many(candidates | set(folded.values()))
    return _splice(text, [
        (match.start(), match.end(),
         values.get(match.group()) or values[folded[match.group()]])
        for match in matches
        if match.group() in values or folded[match.group()] in values
    ])


def _restore_reformatted(text: str, vault: Vault) -> str:
    """Numeric tokens the model rewrote (+7… -> 8…, separators stripped) no longer
    match their minted shape, so they are resolved by digit signature instead."""
    runs = [(match, re.sub(r"\D", "", match.group())) for match in _NUM_RUN.finditer(text)]
    if not runs:
        return text
    candidates: set[str] = set()
    for _, digits in runs:
        candidates.add(digits)
        if len(digits) >= 10:
            candidates.add(digits[-10:])
    resolved = vault.resolve_digit_signatures(candidates)
    if not resolved:
        return text
    spans: list[tuple[int, int, str]] = []
    for match, digits in runs:
        # Full signature wins over the phone last-10 fallback.
        value = resolved.get(digits) or (resolved.get(digits[-10:]) if len(digits) >= 10 else None)
        if value is not None:
            spans.append((match.start(), match.end(), value))
    return _splice(text, spans)


# One to three capitalised Cyrillic words — the shape a personal name takes in
# running text. Deliberately permissive: a false positive costs one indexed
# lookup that finds nothing, a false negative costs a fake value delivered to a
# tool as if it were real.
_NAME_WORD = re.compile(r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?")

# A place phrase in any case: the generic word inflects (улица/улице/улицу), the
# adjectival name agrees with it, the house number never moves. A bare settlement
# is covered by the name windows above, which already match single capitalised
# words.
# The SAME pattern the minting side uses, not a second hand-written copy of the
# same vocabulary. They were two copies and they drifted: the generator learned
# to mint «ул. Осиновая» and «Тополиный проспект» to mirror the customer's own
# wording, while this one still knew only the full words in one order — so the
# restoration window never covered the token, the lookup never ran, and a fake
# address went to the tool. Deriving it removes the possibility.
_PLACE_RUN = re.compile(LOC_TOKEN_PATTERN)


def _place_windows(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Framings of one address run: as matched, plus a following «, кв. N», plus
    the preceding «Город, ». Deduplicated, longest first so the fullest framing
    wins the overlap resolution below."""
    candidates = {(start, end)}
    tail = _FLAT_TAIL.match(text, end)
    if tail is not None:
        candidates.add((start, tail.end()))
    head = _CITY_HEAD.search(text[:start])
    if head is not None and head.end() == start:
        candidates.add((head.start(), end))
        if tail is not None:
            candidates.add((head.start(), tail.end()))
    return sorted(candidates, key=lambda pair: pair[1] - pair[0], reverse=True)


_FLAT_TAIL = re.compile(r",?\s*(?:кв|квартир\w*|офис\w*|оф)\.?\s*\d{1,4}")
_CITY_HEAD = re.compile(r"(?-i:[А-ЯЁ])[а-яё-]+,\s*$")


def _name_windows(text: str) -> list[tuple[int, int, str]]:
    """Every contiguous 1-3 word window of capitalised Cyrillic words.

    Windows rather than maximal runs, because a sentence-initial word is
    capitalised too: `Позвоните Ивану Щукину` is one run of three, and looking
    it up whole finds nothing while `Ивану Щукину` would have matched. Misses
    are free — an indexed point query that returns no row — so enumerating is
    cheaper than being clever about which word starts a sentence.
    """
    words = [(m.start(), m.end(), m.group()) for m in _NAME_WORD.finditer(text)]
    windows: list[tuple[int, int, str]] = []
    for i in range(len(words)):
        for size in (3, 2, 1):
            if i + size > len(words):
                continue
            start, end = words[i][0], words[i + size - 1][1]
            # Only if the words are adjacent — a window may not jump a comma or
            # a lowercase word, which would join two unrelated names.
            if re.fullmatch(r"[А-ЯЁа-яё\s-]+", text[start:end]) is None:
                continue
            windows.append((start, end, text[start:end]))
    return windows


def _restore_inflected(text: str, vault: Vault) -> str:
    """NAME tokens the model put into another case no longer match their minted
    shape, so they are resolved by case-invariant key instead.

    Exactly parallel to `_restore_reformatted` for numbers, and the reason a
    fake no longer reaches a customer's tool when the model writes `Руслану
    Хвостову` instead of the nominative it was handed. Longest window first, so
    a full name wins over its own surname and half a name is never replaced.
    """
    # Names and places are gathered into ONE list before anything is resolved.
    # Doing places in a second pass let a name window claim the overlapping text
    # first, and the address was then never restored — a fake address delivered
    # to a tool, which is the failure this whole path exists to prevent.
    windows = _name_windows(text)
    # Each window carries BOTH signatures, because a single capitalised word can
    # be either kind and the two normalisers disagree: `Еловцке` is a settlement,
    # and asking the PERSON normaliser about it returns it unchanged, so the row
    # is never found. A wrong-kind key costs one indexed lookup that misses.
    keys: dict[tuple[int, int], list[str]] = {}
    for start, end, surface in windows:
        candidates: list[str] = []
        for signature in (name_key, place_key):
            try:
                candidates.append(signature(surface))
            except Exception:  # noqa: BLE001 - morphology must never break a response
                continue
        keys[(start, end)] = candidates
    # SEVERAL CANDIDATE WINDOWS PER MATCH, not one. A single regex has to guess
    # where the address ends — before the flat, after it, with the city or
    # without — and a boundary one component off produces a different lemma
    # signature and no match at all. That guess was the last source of
    # intermittent restoration failures: each individual case looked like its own
    # bug and the pattern kept needing another special case.
    #
    # Names never had this problem because `_name_windows` enumerates instead of
    # guessing. A miss costs one indexed point query that returns nothing, so
    # offering the vault three or four framings of the same text is cheap and
    # removes the guess entirely.
    for match in _PLACE_RUN.finditer(text):
        for start, end in _place_windows(text, match.start(), match.end()):
            surface = text[start:end]
            try:
                keys[(start, end)] = [place_key(surface)]
            except Exception:  # noqa: BLE001
                continue
            windows.append((start, end, surface))
    if not windows:
        return text
    resolved = vault.resolve_name_keys_typed({k for group in keys.values() for k in group})
    if not resolved:
        return text
    spans: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for start, end, surface in sorted(windows, key=lambda w: w[1] - w[0], reverse=True):
        found = next((resolved[k] for k in keys.get((start, end), [])
                      if k in resolved), None)
        if found is None:
            continue
        entity_type, value = found
        if any(a < end and start < b for a, b in taken):
            continue
        taken.append((start, end))
        spans.append((start, end, _in_case_of(value, surface, entity_type)))
    return _splice(text, spans)


def _in_case_of(value: str, surface: str, entity_type: str = "NAME") -> str:
    """Put the real name into the case the token was standing in.

    Both readings of "restore" are legitimate and they disagree, so neither can
    be the only answer:

      * a TOOL ARGUMENT wants the person's name — `create_lead(name=...)` should
        receive «Иванов Пётр Сергеевич», not the dative the sentence happened to
        need;
      * TEXT SHOWN TO A HUMAN wants the sentence to still parse — «Позвоните
        Иванов Пётр Сергеевич» is what a machine translation reads like.

    Matching the case of what was replaced satisfies both without a mode flag:
    inside JSON the model writes the value in the nominative, so the nominative
    comes back; inside prose it writes the case the sentence needs, and the same
    case comes back.
    """
    # DISPATCH ON THE RECORDED TYPE. A place put through the person inflector is
    # read as a run of name parts, and «Санкт-Петербурге» — already in the case
    # asked for — came back «Санкт-Петербургее».
    if entity_type in ("LOC", "ADDR"):
        case = morph_places.detect_case(surface)
        if case is None or case == "nomn":
            return value
        return morph_places.inflect_place(value, case)
    case = morph_names.detect_case(surface)
    if case is None or case == "nomn":
        return value
    return morph_names.inflect_person(value, case, morph_names.detect_gender(value))


# Longest token across our format-preserving tokens is well under this.
_STREAM_KEEP = 64


# A run of capitalised words, or of digits and the separators that hold a number
# together. These are the shapes `_restore_inflected` slides its windows over, so
# a stream must never cut inside one.
_STREAM_RUN_RE = re.compile(
    r"[А-ЯЁA-Z][а-яёa-z]+(?:[\s,]+[А-ЯЁA-Z][а-яёa-z]+)*"
    r"|[\d+()][\d\s+()\-]*\d")


def _safe_cut(raw: str, cut: int) -> int:
    """Move a stream cut back so it cannot land inside a resolvable run.

    The carry withholds the last `_STREAM_KEEP` characters, which protects a
    token sitting at the END of the buffer. It does nothing for one STRADDLING
    the cut, and that is the common case: «Клиент Рыбакова Варвара Олеговна,
    адрес …» is 75 characters, so the cut fell at 11 — inside the surname — and
    «Клиент Рыба» went out while the carry began mid-word. The name was then
    resolved by neither half and the customer read the fake in the chat.

    Cutting on a word boundary is not enough either: a three-part name is three
    words, and `_restore_inflected` resolves it as ONE window. So the cut retreats
    to the start of whatever run it is standing in — after that, every run is
    wholly on one side or the other.

    Reported by a persona as «streaming loses the name when the answer also has
    an address», 3 of 3. The address made the buffer long enough for the cut to
    reach the name; with a shorter answer nothing was ever emitted before flush,
    which is why the same case passed without one.
    """
    for match in _STREAM_RUN_RE.finditer(raw):
        if match.start() < cut < match.end():
            return match.start()
    return cut


def unmask_stream_chunk(delta: str, carry: str, vault: Vault, flush: bool) -> tuple[str, str]:
    """Detokenize one streamed delta, returning (emit, new_carry).

    STATELESS by design: the caller owns the carry. A host gateway (LiteLLM) runs
    many worker processes, so keeping per-stream state inside the sidecar would
    need a shared store plus TTL cleanup for streams that die mid-flight. Handing
    the carry back to the caller — which already holds the connection — removes
    that whole class of problem.

    The carry withholds the last `_STREAM_KEEP` chars from the user until more
    arrives, so a token split across two SSE chunks is still replaced. Privacy
    note: streaming only affects the RESPONSE leg (fake -> real for the user); the
    model already received a fully-masked request, so a rare split is cosmetic,
    never a real-PII leak."""
    raw = carry + delta
    if flush:
        return unmask_text(raw, vault), ""
    if len(raw) <= _STREAM_KEEP:
        return "", raw
    cut = _safe_cut(raw, len(raw) - _STREAM_KEEP)
    if cut <= 0:
        return "", raw
    return unmask_text(raw[:cut], vault), raw[cut:]


def unmask_arguments(raw: str, vault: Vault) -> str:
    """Detokenise a tool call's `arguments` AS JSON, not as flat text.

    THE ARGUMENTS ARE JSON AND THE REAL VALUE IS ARBITRARY TEXT. Substituting
    «ООО "АЭРОМЭП"» into a JSON string by plain replacement injects two bare
    quotes and the object stops parsing — the model gets a tool call it cannot
    read back, and the provider answers 400 on the next turn. On Russian
    business traffic that is not an edge case: every legal entity is written
    with quotes, and the same applies to a backslash or a newline in an address.

    So the string is parsed, every string LEAF is detokenised on its own, and
    the result is re-serialised — which escapes whatever the real value happens
    to contain, by construction rather than by a list of characters we
    remembered to handle.

    Masking stays flat text ON PURPOSE and the asymmetry is deliberate: the
    KEY types the VALUE there (`{"passport": "4509123456"}`), so a recogniser
    that only ever saw one value at a time would lose the evidence that types
    it. Fakes are format-preserving and carry no quotes, so flat substitution
    cannot break the JSON on the way out.

    Arguments that are not valid JSON fall back to flat text: a model is free
    to emit a broken object, and refusing to detokenise it would send a FAKE to
    the tool — the one outcome worse than imperfect text.
    """
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return unmask_text(raw, vault)

    def walk(node: object) -> object:
        if isinstance(node, str):
            return unmask_text(node, vault)
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, dict):
            # Keys are the tool's own schema, not customer text — but a token
            # can only ever appear in a value, so rewriting keys would be a way
            # to break the schema and never a way to restore a value.
            return {key: walk(value) for key, value in node.items()}
        return node

    return json.dumps(walk(parsed), ensure_ascii=False)


def residual_tokens(text: str, vault: Vault) -> list[str]:
    """Minted tokens still standing in text that has already been detokenized.

    THE SIGNAL EVERY PERSONA ASKED FOR, in the same words three times: «мне
    хватило бы заголовка X-Pseudex-Residual». When the model reorders a name,
    shortens it, or reformats a plate, the restored form no longer matches and
    the FAKE goes to the customer's tool — with a 200, empty counters and nothing
    in the log. Their code cannot find out, so they cannot fail closed on their
    own side.

    Read-only and cheap: the candidates are the same shapes `unmask_text` already
    scans for, and each is one indexed lookup that MISSES for a real value and
    HITS for a substitute we minted. A hit here means one thing only — this
    string is ours, and it should not have survived.
    """
    candidates = {match.group() for match in TOKEN_RE.finditer(text)}
    # A NAME the model REWROTE no longer matches any token, so `TOKEN_RE` alone
    # would miss exactly the case this exists for. Capitalised runs are offered
    # too, and the vault decides which of them are made of its own words.
    candidates |= {surface for _start, _end, surface in _name_windows(text)}
    if not candidates:
        return []
    known = vault.detokenize_many(candidates)
    residual = {value for value in candidates if value in known}
    residual |= {value for value in candidates
                 if value not in known and vault.residual_of(value) is not None}
    # MAXIMAL WINDOWS ONLY. «Римма Цветкова» is one leftover, not three; a caller
    # reading a count would otherwise see the same defect three times and could
    # not tell one damaged name from several.
    return sorted(value for value in residual
                  if not any(value != other and value in other
                             for other in residual))


class StreamDetokenizer:
    """Stateful wrapper over `unmask_stream_chunk` for the in-process proxy leg,
    where one object can own the carry for the life of a single stream."""

    def __init__(self, vault: Vault) -> None:
        self._vault = vault
        self._carry = ""

    def feed(self, chunk: str) -> str:
        emit, self._carry = unmask_stream_chunk(chunk, self._carry, self._vault, False)
        return emit

    def flush(self) -> str:
        emit, self._carry = unmask_stream_chunk("", self._carry, self._vault, True)
        return emit
