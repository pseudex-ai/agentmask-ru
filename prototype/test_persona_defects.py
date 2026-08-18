"""The five defects the 18.08.2026 persona run found, and no corpus of ours did.

WHY THIS FILE EXISTS. Every one of these was live in a product whose golden set
read 100%, whose adversarial set read 100% with zero false masks, and whose
nineteen licensing gates passed. They were found by three people using the real
thing for the first time — and four of the five are SILENT: no 5xx, no counter
moves, `/reveal` returns null, and a person who does not exist is written into
the customer's system.

A defect found outside the corpora has to leave a permanent guard behind, or it
comes back the same way it arrived: invisibly. The generated sets cannot hold
these — three of them are about what happens to a value AFTER detection said
yes, and the corpora only ever asked whether detection says yes.

    python3 test_persona_defects.py
"""

import sys

import testkit
from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.envelope import MaskContext, mask_one
from pseudex.maskcache import MaskCache
from pseudex.normalize import normalize
from pseudex.vault import Vault


def _mask(detector: Detector, text: str) -> tuple[str, Vault]:
    vault = Vault(":memory:", "personas")
    context = MaskContext(detector=detector, vault=vault, audit=AuditLog(":memory:"),
                          cache=MaskCache(64), org_id="personas", agent_id="personas")
    return mask_one(text, context), vault


def _named(detector: Detector, text: str) -> list[str]:
    return [text[s.start:s.end] for s in detector.detect(text)
            if s.entity_type == "NAME"]


def check_lookalike_inside_a_word(detector: Detector) -> list[str]:
    """A look-alike at a word edge must not fold into a digit.

    «ч» is the look-alike for 4, and «Валентинович» stands right before a phone
    number. The digit run reached through the space, folded the «ч», and the
    patronymic became «Валентинови4»: the name span ended one character early,
    the vault stored «Соколов Игорь Валентинови», and the orphaned «ч» glued
    itself to the substitute — «Лебедев Никита Радиславч», a string in no vault.
    `/unmask` could never resolve it and `/reveal` returned null, so the booking
    named a person who does not exist and nobody could find out who was meant.
    """
    text = ("Запиши двоих: Соколов Игорь Валентинович +7 916 214-88-03 на 15:00 и "
            "Петрова Марина Сергеевна 8 925 111-22-33 на 16:00")
    problems: list[str] = []
    if "Валентинович" not in normalize(text):
        problems.append(f"нормализация повредила отчество: {normalize(text)!r}")
    masked, vault = _mask(detector, text)
    rows = vault._conn.execute(
        "SELECT canonical, token FROM tokens WHERE entity_type='NAME'").fetchall()
    stored = {canonical for canonical, _ in rows}
    for expected in ("Соколов Игорь Валентинович", "Петрова Марина Сергеевна"):
        if expected not in stored:
            problems.append(f"в волте нет {expected!r}, есть {sorted(stored)}")
    for canonical, token in rows:
        if vault.detokenize(token) != canonical:
            problems.append(f"круг разорван: {token!r} -> {vault.detokenize(token)!r}")
    # The orphaned character glues itself to the substitute, so the masked text
    # is where it shows even when the vault looks fine.
    for word in masked.split():
        if word.endswith("ч") and word[:-1].endswith(("ов", "ев", "ин")):
            problems.append(f"осиротевший символ прилип к подмене: {word!r}")
    return problems


def check_lowercase_oblique_full_name(detector: Detector) -> list[str]:
    """A lower-case name in an oblique case must not leak whole.

    «запишите марину петрову» produced NOTHING. `_lemma` took `parse(word)[0]`,
    and «марину» offers «марин» (a man) and «марина» (a woman) at the SAME score
    of 0.500 — the winner is arbitrary. It picked the man, the gazetteer had no
    such entry, and the surname beside it is invisible to the bulk dictionary,
    which is capital-only by design. Both words went to the model in the clear,
    in the register support traffic is actually written in.
    """
    cases = ("запишите марину петрову на пятницу в 11, тел 89162148803",
             "запишите петрову марину на пятницу",
             "перезвони марине петровой",
             "запишите игоря соколова на завтра",
             "запишите анну иванову на среду")
    return [f"утекло целиком: {text!r}" for text in cases
            if not _named(detector, text)]


def check_key_typed_spans_survive(detector: Detector) -> list[str]:
    """A KV-typed span carries its own evidence and must not be re-gated.

    `{"passport": "4509123456"}` was typed correctly BY THE KEY and then thrown
    away by the cue rule, which knows «паспорт» and not the Latin «passport».
    The same number after the Russian word was masked, so one customer's JSON
    field leaked while another's prose did not.
    """
    cases = ('{"passport": "4509123456"}', '{"passport": "4509 123456"}',
             'passport: 4509123456', '{"account": "40817810099910004312"}',
             '{"snils": "11223344595"}', '{"phone": "+79161112233"}')
    return [f"ключ не типизирует значение: {text!r}" for text in cases
            if not detector.detect(text)]


def check_account_is_not_one_word(detector: Detector) -> list[str]:
    """A bank account is anchored to more than the single word «счёт».

    One sentence, one value, two outcomes: «счёт 4081…, реквизиты 4081…» masked
    the first and leaked the second. The page promises detection «по формату
    счёта РФ»; it was the word.
    """
    text = "счёт 40817810099910004312, реквизиты 40817810099910004312"
    problems: list[str] = []
    found = [s for s in detector.detect(text) if s.entity_type == "ACCOUNT"]
    if len(found) != 2:
        problems.append(f"ACCOUNT найдено {len(found)} из 2 в {text!r}")
    masked, _vault = _mask(detector, text)
    if "40817810099910004312" in masked:
        problems.append(f"настоящий номер ушёл к модели: {masked!r}")
    return problems


def check_ambiguous_keys_stay_out(detector: Detector) -> list[str]:
    """«счёт» and «реквизиты» may not be KV KEYS, only cue words.

    A `KEY_TYPE` entry types the WHOLE value with no shape check. Adding these
    two — which reads natural, and which this author did — made «Реквизиты:
    СНИЛС 647-436-713 22, карта …» one account number that swallowed the СНИЛС
    inside it: -12 of 298 on the golden set, instantly. In Russian business
    writing «счёт» is an invoice more often than a bank account, and
    «Реквизиты:» introduces a LIST.

    Guarded here and not only by the golden set, because the golden set says
    only THAT recall fell; this says which sentence and why.
    """
    problems: list[str] = []
    mixed = "Реквизиты: СНИЛС 647-436-713 22, карта 4090 9743 9533 9426, дата 21.01.1979."
    kinds = {s.entity_type for s in detector.detect(mixed)}
    for expected in ("SNILS", "CARD"):
        if expected not in kinds:
            problems.append(f"{expected} проглочен в {mixed!r}, найдено {sorted(kinds)}")
    for clean in ("Счёт 1234 от 15.05.2025", "Счёт: 1234 от 15.05.2025",
                  "номер счёта 1234", "реквизиты договора 815",
                  "Реквизиты для оплаты в приложении"):
        spans = detector.detect(clean)
        if spans:
            problems.append(f"деловой текст замаскирован: {clean!r} -> "
                            f"{[(s.entity_type, s.value) for s in spans]}")
    return problems



def check_usage_needs_a_real_key() -> list[str]:
    """`/usage` on the proxy takes a KNOWN key, never the pass-through one.

    `_tenant` accepts an unrecognised key when an upstream is configured, and on
    `/v1/chat/completions` that is right: the key is the customer's own provider
    credential and the provider is the only party who can judge it. `/usage`
    sends nothing upstream, so nobody judged it — any string returned the shared
    org's counters, token list and masked previews, on a port the recommended
    command publishes to every interface.

    The non-ASCII case is here too: «Bearer левый» used to answer 500 with a
    traceback, because `hmac.compare_digest` refuses a `str` outside ASCII and
    ASGI hands headers over latin-1 decoded. An authorisation path is the last
    place that should answer with a stack.
    """
    import asyncio
    import os
    import tempfile

    import httpx

    # A DB DIR OF ITS OWN, set before the import that reads it. `proxy` resolves
    # `PSEUDEX_DB_DIR` at module load and defaults to «.», so without this the
    # check reads whatever tenants.db happens to lie in the working directory —
    # and a stale one from an older schema turns a 401 assertion into a 500.
    os.environ["PSEUDEX_DB_DIR"] = tempfile.mkdtemp(prefix="persona-defects-")
    os.environ.setdefault("PSEUDEX_UPSTREAM_BASE_URL", "https://api.openai.com/v1")
    os.environ.setdefault("PSEUDEX_UPSTREAM_KEY", "sk-test")
    from pseudex import proxy, service

    async def status(app, path, headers) -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            return (await client.get(path, headers=headers)).status_code

    cases = (
        ("прокси, кириллический мусор", proxy.app, "/usage",
         {b"Authorization": "Bearer sk-совершенно-левый".encode()}, 401),
        ("прокси, латинский мусор", proxy.app, "/usage",
         {"Authorization": "Bearer sk-any-garbage"}, 401),
        ("прокси, без заголовка", proxy.app, "/usage", {}, 401),
        ("сайдкар, кириллический мусор", service.app, "/usage?org_id=x",
         {b"Authorization": "Bearer левый".encode()}, 401),
    )
    problems: list[str] = []
    for label, app, path, headers, expected in cases:
        got = asyncio.run(status(app, path, headers))
        if got != expected:
            problems.append(f"{label}: HTTP {got}, ждали {expected}")
    return problems



def check_colloquial_names(detector: Detector) -> list[str]:
    """The familiar register, which is the one an agent actually receives.

    The gazetteer held the polite diminutive («Саша», «Катя») and not the
    familiar one. A persona running a barbershop bot measured it on the wire:
    of fourteen colloquial names TEN reached the model in the clear, while
    «макс», «юля», «паша» were caught — so the product looked like it worked.
    Its own page listed «ФИО» as a supported type with «Иванову Петру
    Сергеевичу» beside it; a telegram bot never writes that.

    The negatives matter as much: «вика» and «света» are ordinary words too, and
    the verb is what separates them. A deny-list of plants could not have done
    it — «посадил вику» and «запиши вику» differ only in what is being asked.
    """
    leaked = ("виталик", "димон", "серёга", "колян", "танюха", "вовчик",
              "ленка", "стас", "алёнка", "иру")
    problems = [f"утекло: {word!r}" for word in leaked
                if not any(s.entity_type == "NAME"
                           for s in detector.detect(f"запиши {word} на 12"))]
    for text in ("посадил вику под окном", "вика взошла в мае",
                 "света в комнате была тусклая"):
        if detector.detect(text):
            problems.append(f"обычное слово замаскировано: {text!r}")
    return problems


CHECKS = (
    ("нормализация: look-alike на краю слова", check_lookalike_inside_a_word),
    ("строчное ФИО в косвенном падеже", check_lowercase_oblique_full_name),
    ("KV-спан несёт своё свидетельство", check_key_typed_spans_survive),
    ("счёт держится на формате, не на слове", check_account_is_not_one_word),
    ("двусмысленные слова не ключи", check_ambiguous_keys_stay_out),
    ("/usage требует известный ключ", lambda _detector: check_usage_needs_a_real_key()),
    ("просторечные имена не утекают", check_colloquial_names),
)


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    failed = 0
    for title, check in CHECKS:
        problems = check(detector)
        print(f"{'FAIL' if problems else 'PASS'}  {title}")
        for problem in problems:
            print(f"        {problem}")
        failed += bool(problems)
    print()
    if failed:
        print(f"дефектов персон ожило: {failed} из {len(CHECKS)}")
        return 1
    print(f"все {len(CHECKS)} дефекта прогона персон закрыты")
    return 0


if __name__ == "__main__":
    sys.exit(main())
