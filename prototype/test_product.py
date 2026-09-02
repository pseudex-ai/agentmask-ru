"""Offline tests for the product layer: API-key tenancy + streaming detok."""

import os
import pathlib
import re
import tempfile

from pseudex.assets import ASSETS
from pseudex.audit import AuditLog, _preview
from pseudex.detect_all import Detector
from pseudex.envelope import MaskContext, conversation_key, mask_one
from pseudex.maskcache import MaskCache, content_key
from pseudex.names import is_known_name, trim_person_span
from pseudex.normalize import normalize
from pseudex.redact import StreamDetokenizer, mask_text, unmask_text
from pseudex.ru_pii import validate_inn, validate_luhn, validate_ogrn, validate_snils
from pseudex.tenants import Tenants
from pseudex.vault import _FAKE_FIRST, _FAKE_LAST, TOKEN_RE, _render_token, Vault
from testkit import load_dev_bundle

# Every type any detector can emit. quasi.py's DOB/AGE/MEDICAL and any future
# type fall through to the REDACTED… fallback shape.
_ENTITY_TYPES = ("PHONE", "EMAIL", "SNILS", "INN", "CARD", "PASSPORT", "DATE",
                 "NAME", "LOC", "DOB", "AGE", "MEDICAL", "OPAQUE",
                 # Document types added after the 152-ФЗ coverage checklist.
                 "OMS", "ACCOUNT", "DRIVER_LICENSE", "VEHICLE_DOC",
                 "INTL_PASSPORT", "OGRN", "PLATE", "IP", "BIRTH_CERT")


def test_audit() -> None:
    pathlib.Path("a.db").unlink(missing_ok=True)
    audit = AuditLog("a.db")
    audit.record("acme", "ag1", "PHONE", "+79185702864", "+79991234567")
    audit.record("acme", "ag1", "NAME", "Полина Жукова", "Иван Петров")
    audit.record("acme", "ag2", "EMAIL", "tok@x.ru", "real@x.ru")
    assert audit.counts("acme", 0.0, "") == {"PHONE": 1, "NAME": 1, "EMAIL": 1}
    assert audit.counts_for_agent("acme", "ag1") == {"PHONE": 1, "NAME": 1}
    recent = audit.recent("acme", 10)
    assert len(recent) == 3 and "•" in recent[0]["preview"]
    agent_recent = audit.recent_for_agent("acme", "ag1", 10)
    assert len(agent_recent) == 2 and all(r["type"] in ("PHONE", "NAME") for r in agent_recent)
    print(f"audit OK — org counts {audit.counts('acme', 0.0, '')}; ag1 counts {audit.counts_for_agent('acme', 'ag1')}; "
          f"preview '+79991234567' -> '{_preview('+79991234567')}'")
    pathlib.Path("a.db").unlink(missing_ok=True)


def test_tenants() -> None:
    pathlib.Path("t.db").unlink(missing_ok=True)
    tenants = Tenants("t.db")
    key = tenants.issue("acme", "https://api.example/v1", "sk-up-123")
    resolved = tenants.resolve(key)
    assert resolved is not None and resolved.customer_id == "acme"
    assert resolved.upstream_key == "sk-up-123"
    assert tenants.resolve("sk-ps-wrong") is None
    print(f"tenants OK — issued {key[:14]}…, resolves to {resolved.customer_id}; bad key -> None")
    pathlib.Path("t.db").unlink(missing_ok=True)


def test_stream_detok_split_token() -> None:
    vault = Vault(":memory:", "stream")
    token = vault.tokenize("+7 999 123-45-67", "PHONE")
    real = vault.detokenize(token)
    detok = StreamDetokenizer(vault)
    out = ""
    out += detok.feed("Перезвоню вам на ")
    out += detok.feed(token[:6])           # token split across two chunks
    out += detok.feed(token[6:] + " завтра")
    out += detok.flush()
    print(f"STREAM -> {out!r}")
    assert real in out, "split token was not detokenized"
    assert token not in out, "fake token leaked to user in stream"
    print("stream detok OK — split token restored to real value")


def test_token_shapes() -> None:
    """LOAD-BEARING INVARIANT: unmask_text finds tokens by shape instead of
    scanning the vault, so every token _render_token can mint MUST be matched by
    TOKEN_RE in full. A shape that escapes it stops being reversible — and on the
    response leg that means a tool runs on a FAKE value. Tokens are random, so
    each type is sampled repeatedly."""
    for entity_type in _ENTITY_TYPES:
        for _ in range(200):
            token = _render_token(entity_type)
            assert TOKEN_RE.fullmatch(token), f"{entity_type} token {token!r} escapes TOKEN_RE"
    print(f"token shapes OK — {len(_ENTITY_TYPES)} types x200 samples all matched by TOKEN_RE")


def test_unmask_scales_with_text_not_vault() -> None:
    """Detokenization must stay correct when the vault is large, and must not
    resolve a value that was never tokenized for this customer."""
    vault = Vault(":memory:", "big")
    target = vault.tokenize("+7 999 123-45-67", "PHONE")
    for index in range(2000):  # noise the response never mentions
        vault.tokenize(f"+7 916 {index:03d}-11-22", "PHONE")
    restored = unmask_text(f"Ваш номер {target}, перезвоним.", vault)
    assert "+7 999 123-45-67" in restored, f"target token not restored: {restored!r}"
    assert target not in restored, "fake token leaked to user"
    untouched = unmask_text("Заказ 4512 и трек 77012345678901", vault)
    assert untouched == "Заказ 4512 и трек 77012345678901", f"over-restored: {untouched!r}"
    print(f"unmask OK on a 2001-token vault — {restored!r}")


def test_tool_receives_original_surface_form() -> None:
    """The tool must get the value EXACTLY as the user typed it.

    Without Pseudex in the path a tool would receive the user's own string, so
    handing it a re-formatted one is a behaviour change we impose — a CRM that
    matches phone numbers as strings would silently fail to find the record.
    Canonicalization stays, but only as the dedup key: both spellings still
    collapse to ONE token so the model sees one identity."""
    vault = Vault(":memory:", "surface")
    written = "+7 999 123-45-67"
    token = vault.tokenize(written, "PHONE")
    assert vault.detokenize(token) == written, \
        f"tool got {vault.detokenize(token)!r}, user wrote {written!r}"

    # Same number, other spelling -> same token (dedup key still canonical),
    # and the FIRST-seen form is kept so the tool sees a stable value.
    assert vault.tokenize("89991234567", "PHONE") == token, "formats must share one token"
    assert vault.detokenize(token) == written, "first-seen surface form must win"

    restored = unmask_text(f"Звоню на {token}", vault)
    assert written in restored, f"round-trip lost the original form: {restored!r}"
    print(f"surface form OK — user wrote {written!r}, tool receives {vault.detokenize(token)!r}")


def test_fake_names_are_self_recognised() -> None:
    """Every fake first name must be one OUR OWN detector recognises.

    The re-masking guard compares a detected span against the minted token, so
    the token has to be detected AS A WHOLE. Unusual names broke that: the
    gazetteer did not know `Аглая`, detection found only the surname `Котов`,
    that is not a minted token, so it was masked again and the person's identity
    drifted mid-conversation. Also checks the pool is big enough that an org
    cannot exhaust it — a flat five-name list used to hang the request path on
    the sixth distinct person."""
    unknown = [name for name in _FAKE_FIRST if not is_known_name(name)]
    assert not unknown, f"fake first names our own gazetteer cannot see: {unknown}"
    combinations = len(_FAKE_FIRST) * len(_FAKE_LAST)
    assert combinations >= 1000, f"NAME pool too small ({combinations}) — exhaustion is a hang"
    print(f"fake-name pool OK — {len(_FAKE_FIRST)}x{len(_FAKE_LAST)}={combinations} "
          f"combinations, all gazetteer-visible")


def test_token_pool_does_not_exhaust() -> None:
    """Minting must stay bounded and unique well past any plausible org size.

    EVERY high-cardinality type, not just NAME. This test used to cover names
    only, which is why it passed while LOC could mint just 33 tokens and IP just
    254: the 34th distinct address an organisation sent raised out of
    `_unique_token` and became a permanent fail-closed 5xx for that customer.
    A delivery or logistics client crosses 33 addresses on its first day."""
    vault = Vault(":memory:", "pool")
    for entity_type, sample in (("NAME", "Человек Номер{}"),
                                ("LOC", "улица Тестовая {}, кв 1"),
                                ("IP", "10.{}.{}.1")):
        values = [sample.format(index, index) for index in range(300)]
        tokens = {vault.tokenize(value, entity_type) for value in values}
        assert len(tokens) == 300, (
            f"{entity_type}: minted only {len(tokens)} unique tokens for 300 values"
        )
    print("token pool OK — NAME/LOC/IP each mint 300 distinct tokens, no exhaustion")


def test_reformatted_document_tokens_resolve() -> None:
    """REGRESSION: the six document types were added to `_render_token` but not
    to `_NUMERIC_TYPES`, so their rows carried NULL digit signatures.

    A model that echoes a driver's licence as `9912345678` instead of
    `99 12 345678` then resolved to nothing, and the tool executed on the FAKE
    document number — which vault.py itself calls worse than a miss."""
    vault = Vault(":memory:", "docs")
    originals = {
        "DRIVER_LICENSE": "77 15 998877",
        "VEHICLE_DOC": "50 22 445566",
        "OMS": "7712345678901234",
        "ACCOUNT": "40817810099910004312",
        "INTL_PASSPORT": "750123456",
    }
    for entity_type, original in originals.items():
        token = vault.tokenize(original, entity_type)
        stripped = re.sub(r"\D", "", token)
        restored = unmask_text(f"проверьте {stripped}", vault)
        assert original in restored, (
            f"{entity_type}: reformatted token {stripped} did not resolve back "
            f"to {original} (got {restored!r})"
        )
    print(f"reformatted document tokens OK — {len(originals)} types survive "
          f"separator stripping")


def test_trim_person_span_keeps_offsets() -> None:
    """REGRESSION: `trim_person_span` rebuilt the value with `\" \".join(...)`,
    collapsing runs of whitespace. The caller sizes the span from
    `len(trimmed)`, so on `Иван  Петров` (double space — ordinary in CRM
    exports) masking replaced one character too few and left a fragment of the
    real surname in the text sent to the model."""
    for value in ("Иван  Петров Спасибо", "Получатель Иван Петров",
                  "Иван\nПетров Спасибо", "Ольга Смирнов Мои"):
        leading, trimmed = trim_person_span(value)
        assert value[leading:leading + len(trimmed)] == trimmed, (
            f"{value!r}: trimmed {trimmed!r} is not the slice at offset {leading}"
        )
    print("person-span offsets OK — trimmed value is always a slice of the source")


def test_echoed_token_is_not_billed() -> None:
    """REGRESSION: `mask_one` tokenized and audited EVERY detected span, then
    `mask_text` skipped the ones that were already our own tokens.

    So an echoed token still minted a vault row (fake -> another fake, burning a
    slot in a finite pool) and still recorded an audit event — and audit counts
    are what the licensing server bills on. In a multi-turn agent the model
    quotes its own tokens constantly, so the overcount grew with conversation
    length."""
    directory = tempfile.mkdtemp(prefix="pseudex_echo_")
    audit = AuditLog(pathlib.Path(directory, "audit.db").as_posix())
    vault = Vault(pathlib.Path(directory, "vault.db").as_posix(), "echo")
    context = MaskContext(detector=Detector(), vault=vault, audit=audit,
                          cache=MaskCache(64), org_id="echo", agent_id="a", conversation_id="")

    masked = mask_one("Клиент Иван Петров просит перезвонить", context)
    before = dict(audit.counts("echo", 0.0, ""))
    # The model echoes the token back inside DIFFERENT text, so the content cache
    # cannot hide the second pass.
    mask_one(f"Уточните у {masked.split('Клиент ')[1].split(' просит')[0]} детали", context)
    after = dict(audit.counts("echo", 0.0, ""))

    assert after.get("NAME", 0) == before.get("NAME", 0), (
        f"echoing our own token was billed again: NAME {before.get('NAME')} -> "
        f"{after.get('NAME')}"
    )
    print("echoed-token accounting OK — re-detecting our own token bills nothing")


def test_tokens_are_not_valid_documents() -> None:
    """A token must never be a valid instance of ANY type, not just its own.

    The rule was applied to the СНИЛС/ИНН/card generators and missed on PHONE,
    whose 11 digits are the same shape as a СНИЛС — about 1% passed that
    checksum. Those tokens were re-masked as СНИЛС when the model echoed them
    (СНИЛС outranks PHONE, and the re-masking guard misses because detection
    reports the digits without the leading `+`), so the number changed
    mid-conversation and the tool received the wrong value.

    Sampled rather than reasoned about: the generators are random, and a 1-in-100
    collision is invisible in a single draw — which is exactly why this went
    unnoticed until a test happened to roll one."""
    samples = 5000
    collisions = [token for token in (_render_token("PHONE") for _ in range(samples))
                  if validate_snils(token.lstrip("+"))]
    assert not collisions, (
        f"{len(collisions)}/{samples} PHONE tokens are valid СНИЛС, e.g. {collisions[:3]}"
    )
    for entity_type, checker in (("SNILS", validate_snils), ("INN", validate_inn),
                                 ("OGRN", validate_ogrn)):
        bad = [token for token in (_render_token(entity_type) for _ in range(500))
               if checker(token)]
        assert not bad, f"{entity_type} minted a CHECKSUM-VALID token: {bad[:3]}"
    cards = [token for token in (_render_token("CARD") for _ in range(500))
             if validate_luhn(token)]
    assert not cards, f"CARD minted a Luhn-VALID token: {cards[:3]}"
    print(f"token/document collisions OK — {samples} PHONE samples, none a valid СНИЛС")


def test_lookalike_table_is_complete() -> None:
    """REGRESSION: the digit-lookalike table had Cyrillic 'о' twice and was
    therefore MISSING Greek small omicron — a dict literal silently keeps the
    last value for a repeated key. An obfuscated phone written with the Greek
    letter never folded to digits and reached the model unmasked."""
    obfuscated = "+7 9" + chr(0x3BF) + "9 123-45-67"
    assert normalize(obfuscated) == "+7 909 123-45-67", (
        f"Greek small omicron not folded: {normalize(obfuscated)!r}"
    )
    assert chr(0x3BF) in ASSETS.get().lookalike
    print("lookalike table OK — Greek small omicron folds to a digit")


def test_masking_own_token_is_stable() -> None:
    """REGRESSION (found by the DeepSeek paired run): a multi-turn agent echoes
    our token back inside NEW text, so detection meets it again.

    A fake NAME or LOC is by construction a well-formed name or place, so it is
    re-detected — and re-masking it mints a fresh token. Consequences, worst
    first: detokenization then returns the intermediate TOKEN, so the tool acts
    on a plausible but WRONG person; the person's identity changes every turn;
    and the provider's prefix cache dies because the prefix stops being stable.

    Note this is NOT covered by re-masking the same raw string — that is a
    content-cache hit. The token has to arrive inside different surrounding text,
    which is what a real agent turn does."""
    detector = Detector()
    vault = Vault(":memory:", "echo")
    # Address included on purpose: the LOC token is now a generated street with a
    # house number rather than a value from a flat list, so re-detection has a
    # real chance of carving it up differently — and a differently-carved span is
    # not literally a minted token, which is exactly how the guard gets missed.
    real = ("Клиент Иван Петров просит перезвонить, телефон +7 999 123-45-67, "
            "адрес улица Ленина 5, кв 12")

    first = mask_text(real, vault, detector.detect(real))
    # Different surrounding text each pass -> the cache cannot mask the bug.
    second = mask_text(first, vault, detector.detect(first))
    third = mask_text(f"Повтор: {second}", vault, detector.detect(f"Повтор: {second}"))

    assert first == second, f"re-masking our own token changed it: {first!r} -> {second!r}"
    assert second in third, f"token unstable inside new context: {third!r}"
    assert "Иван Петров" not in second and "+7 999 123-45-67" not in second, "LEAK"

    restored = unmask_text(third, vault)
    assert "Иван Петров" in restored, f"real name not restored: {restored!r}"
    assert "+7 999 123-45-67" in restored, f"real phone not restored: {restored!r}"
    print(f"token stability OK — {first!r} survives re-masking and round-trips")


def test_unmask_reformatted_phone() -> None:
    """The model rewrites +7… as 8… — the digit signature must still resolve it."""
    vault = Vault(":memory:", "reformat")
    token = vault.tokenize("+7 999 123-45-67", "PHONE")
    rewritten = "8" + token[2:]  # +79021384756 -> 89021384756
    restored = unmask_text(f"Звоню на {rewritten}", vault)
    assert "+7 999 123-45-67" in restored, f"reformatted token not restored: {restored!r}"
    print(f"reformatted-token detok OK — {rewritten} -> {restored!r}")



def test_conversation_scope_is_isolated() -> None:
    """The scope a partial mention may be resolved in, and its three boundaries.

    Linking «Ленина 14» to a fuller address said earlier is only ever safe
    inside one conversation — the same street and house exist in every Russian
    city, so a link that escaped its conversation would send a courier to
    whoever spoke first. Three things have to hold for that boundary to be real,
    and each of them failed silently in an earlier shape of this change.

    1. The identity must survive the transcript GROWING, or every turn is its
       own conversation and the scope never links anything.
    2. It must SEPARATE conversations that share a system prompt, which almost
       all of an agent's conversations do.
    3. The MASK CACHE must respect it. The cache keys on content, so without
       the scope in the key the first conversation's answer is served to every
       later one and the isolation above is decoration.

    The vault view is checked for the opposite property: it must SHARE the
    connection and the lock (a per-conversation database would give one person
    a new identity every dialogue) while owning the scope.
    """
    opening = [{"role": "system", "content": "Ты помощник службы доставки."},
               {"role": "user", "content": "здравствуйте, это Игорь"}]
    grown = opening + [{"role": "assistant", "content": "слушаю"},
                       {"role": "user", "content": "адрес ленина 14"}]
    assert conversation_key(opening) == conversation_key(grown), \
        "identity must not change as the transcript grows"

    other = [{"role": "system", "content": "Ты помощник службы доставки."},
             {"role": "user", "content": "здравствуйте, это Анна"}]
    assert conversation_key(opening) != conversation_key(other), \
        "a shared system prompt must not put two customers in one scope"

    assert content_key("acme", "c1", "адрес ленина 14") \
        != content_key("acme", "c2", "адрес ленина 14"), \
        "the mask cache must not serve one conversation's link to another"
    assert content_key("acme", "c1", "адрес ленина 14") \
        == content_key("acme", "c1", "адрес ленина 14"), \
        "and it must still hit within one conversation, or the O(n^2) case returns"

    with tempfile.TemporaryDirectory() as directory:
        vault = Vault(os.path.join(directory, "vault.db"), "acme")
        first, second = vault.for_conversation("c1"), vault.for_conversation("c2")
        assert first._conn is vault._conn and first._lock is vault._lock, \
            "a view must share the connection and the lock, not open its own"
        assert (first._conversation, second._conversation, vault._conversation) \
            == ("c1", "c2", ""), "each view owns its scope; the shared vault has none"
        assert (first.tokenize("+7 999 111 22 33", "PHONE")
                == second.tokenize("+7 999 111 22 33", "PHONE")), \
            "one person keeps one pseudonym ACROSS conversations — the scope " \
            "narrows what may be LINKED, never what is already known"
    print("conversation scope OK — isolated in the cache, shared in the vault")


def test_short_address_resolves_to_the_full_one() -> None:
    """«вы находитесь на Ленина 14?» while «г. Москва, ул. Ленина, д. 14» stands
    in the same conversation.

    They keyed apart — one canonicalises to `москва улица ленин 14`, the other
    to `ленин 14` — so the model was handed two unrelated fake addresses and
    asked whether they were the same place. It answered no, correctly, about the
    wrong question. Nothing was broken; the two mentions had no way to be one
    thing.

    Four properties, and each one failed on the way here.

    1. The short mention gets the CORRESPONDING PART of the substitute the full
       address already has — same street, same house — not a second random one.
    2. It gets back exactly what it wrote: no city and no flat if it named
       neither. A projection carrying a flat the sentence never had is a more
       specific address than the person gave.
    3. The round trip still returns the WRITTEN value, «Ленина 14», because the
       tool must execute on what the customer said.
    4. The link does NOT escape its conversation. Written into `tokens` under
       the plain key, it would have been served to the next customer who wrote
       the same street — a courier sent to whoever spoke first.

    And the refusal: two addresses on the same street in one dialogue (home and
    delivery) means neither links. That is Fellegi-Sunter's middle outcome with
    no human to refer it to, so it collapses to «do not guess».
    """
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "vault.db")
        talk = Vault(path, "acme").for_conversation("dialog-1")
        full = talk.tokenize("г. Москва, ул. Ленина, д. 14", "LOC")
        short = talk.tokenize("Ленина 14", "LOC")
        assert short and short != full, "a short mention is not the full address"
        assert short in full, f"{short!r} must be the street and house of {full!r}"
        assert not any(char.isdigit() for char in full[:full.index(short)]), \
            "what the projection drops must be the CITY, not part of the street"
        assert unmask_text(f"адрес {short}", talk) == "адрес Ленина 14", \
            "the tool receives what the customer wrote, not the fuller form"

        elsewhere = Vault(path, "acme").for_conversation("dialog-2")
        assert elsewhere.tokenize("Ленина 14", "LOC") != short, \
            "a link decided in one conversation must not be served to another"

        crowded = Vault(path, "acme").for_conversation("dialog-3")
        crowded.tokenize("Москва, ул. Мира, д. 7", "LOC")
        crowded.tokenize("Казань, ул. Мира, д. 7", "LOC")
        ambiguous = crowded.tokenize("Мира 7", "LOC")
        assert not any(ambiguous in crowded.tokenize(value, "LOC")
                       for value in ("Москва, ул. Мира, д. 7", "Казань, ул. Мира, д. 7")), \
            "two owners in one conversation means neither is linked"

        # The flat is mirrored, not inherited: it belongs to the full address.
        flats = Vault(path, "acme").for_conversation("dialog-4")
        flats.tokenize("г. Казань, ул. Садовая, д. 3, кв. 12", "LOC")
        brief = flats.tokenize("садовая 3", "LOC")
        assert brief and "кв" not in brief, \
            f"{brief!r} carries a flat the mention never named"
    print("short-address linking OK — same place, own shape, one conversation")

def test_fuller_mention_reuses_the_substitute() -> None:
    """A FULLER mention arriving AFTER a shorter one, in the same conversation,
    grows the substitute already minted instead of minting a second one.

    The live v4 pilot: the customer says «центральная сто», the model asks the
    address directory, the directory answers «Краснодар, центральная, 100», and
    the tool result was masked with an unrelated substitute — the model could
    not match what it had just asked for (30 of 42 `compare` triples, twice a
    neighbour's record picked). Names: «букин сергей» in the turn, «Букин
    Сергей Иванович» in the CRM record, joined by the model into a double
    surname.

    Pinned: the short token is a literal substring of the grown full one; both
    round-trip to what was written; a later short mention links back; the link
    does not cross conversations; two short candidates refuse; fragments of the
    short token still resolve after the extension; the spoken house number and
    the written one share the key while the stored canonical does not move.
    """
    import json
    import re as _re
    from pseudex.morph_places import address_key, street_house_key
    from pseudex.redact import unmask_arguments
    from pseudex.vault import LOC_TOKEN_PATTERN

    assert street_house_key("центральная сто") == street_house_key("Краснодар, центральная, 100")
    assert street_house_key("клубная 160 второй подъезд") == street_house_key("Клубная, 160, подъезд 2")
    assert address_key("центральная сто") == "центральный сто", "the stored canonical must not move"

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "v.db")
        talk = Vault(path, "acme").for_conversation("d-1")
        short = talk.tokenize("центральная сто", "LOC")
        full = talk.tokenize("Краснодар, центральная, 100", "LOC")
        assert full != short and short in full, f"{full!r} must grow {short!r}"
        assert _re.fullmatch(LOC_TOKEN_PATTERN, full), full
        assert unmask_text(f"адрес {full}", talk) == "адрес Краснодар, центральная, 100"
        assert unmask_text(f"адрес {short}", talk) == "адрес центральная сто"
        assert talk.tokenize("центральная 100", "LOC") == short, "a later short mention links back"
        street_word, house = short.split()[1], short.split()[-1]
        restored = json.loads(unmask_arguments(json.dumps(
            {"address": {"locality": full.split(",")[0], "street": street_word, "building": house}},
            ensure_ascii=False), talk))["address"]
        assert restored == {"locality": "Краснодар", "street": "центральная", "building": "100"}, restored

        flats = Vault(path, "acme").for_conversation("d-2")
        brief = flats.tokenize("садовая три квартира пять", "LOC")
        grown = flats.tokenize("Казань, Садовая, 3, кв. 5", "LOC")
        assert brief.split(",")[0] in grown and "кв." in grown, (brief, grown)

        elsewhere = Vault(path, "acme").for_conversation("d-3")
        s2 = elsewhere.tokenize("школьная шестьдесят три", "LOC")
        f2 = Vault(path, "acme").for_conversation("d-4").tokenize("Воткинск, Школьная, 63", "LOC")
        assert s2 not in f2, "a link decided in one conversation must not be served to another"

        crowded = Vault(path, "acme").for_conversation("d-5")
        a1 = crowded.tokenize("мира семь", "LOC")
        a2 = crowded.tokenize("Мира 7 кв 3", "LOC")
        a3 = crowded.tokenize("Казань, Мира, 7", "LOC")
        assert a1 not in a3 and a2 not in a3, "two short candidates mean a guess, and a guess is refused"

        people = Vault(path, "acme").for_conversation("p-1")
        two = people.tokenize("букин сергей", "NAME")
        three = people.tokenize("Букин Сергей Иванович", "NAME")
        assert three.split()[:2] == two.split() and len(three.split()) == 3, (two, three)
        assert people.detokenize(three) == "Букин Сергей Иванович"
        assert people.detokenize(two) == "букин сергей"
        assert people.tokenize("Сергей Иванович Букин", "NAME") == three
        assert people.tokenize("Сергей", "NAME") == two.split()[1], "a lone given name collapses onto the chain"
        args = json.loads(unmask_arguments(json.dumps(
            {"last_name": two.split()[0], "first_name": two.split()[1]}, ensure_ascii=False), people))
        assert args == {"last_name": "Букин", "first_name": "Сергей"}, args
        assert unmask_text(f"{two.split()[1]} {two.split()[0]} звонил", people) == "Букин Сергей звонил"

        a = Vault(path, "acme").for_conversation("p-2").tokenize("гусева марина", "NAME")
        b = Vault(path, "acme").for_conversation("p-3").tokenize("Гусева Марина Олеговна", "NAME")
        assert b.split()[:2] != a.split(), "a name grown in one conversation is not grown from another's"

        twins = Vault(path, "acme").for_conversation("p-4")
        p1 = twins.tokenize("иванов пётр", "NAME")
        p2 = twins.tokenize("пётр иванович", "NAME")
        p3 = twins.tokenize("Иванов Пётр Иванович", "NAME")
        assert p3.split()[:2] != p1.split() and p3.split()[1:] != p2.split(), "two shorter people refuse"
    print("fuller-mention reuse OK — one place and one person, in either order")


if __name__ == "__main__":
    load_dev_bundle()
    test_tenants()
    test_stream_detok_split_token()
    test_audit()
    test_token_shapes()
    test_unmask_scales_with_text_not_vault()
    test_tool_receives_original_surface_form()
    test_fake_names_are_self_recognised()
    test_token_pool_does_not_exhaust()
    test_masking_own_token_is_stable()
    test_unmask_reformatted_phone()
    test_reformatted_document_tokens_resolve()
    test_trim_person_span_keeps_offsets()
    test_echoed_token_is_not_billed()
    test_tokens_are_not_valid_documents()
    test_lookalike_table_is_complete()
    test_conversation_scope_is_isolated()
    test_short_address_resolves_to_the_full_one()
    test_fuller_mention_reuses_the_substitute()
