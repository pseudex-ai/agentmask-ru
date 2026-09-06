"""`normalize` — инструмент-нормализатор чистит ПД, и шлюз не должен мешать.

«запишите иванов пётр телефон восемь девятьсот шестнадцать … адрес ленина
четырнадцать квартира три» → normalize_contact(имя, телефон, адрес) → тот же
контакт, но с большой буквы, телефон в E.164, адрес разложен на улицу и дом →
crm_upsert_contact уже НОРМАЛИЗОВАННЫМИ полями.

ПОЧЕМУ ЭТО НЕ ПОВТОРЯЕТ `decompose`. Там раскладывает АГЕНТ, и мы измеряем, что
он сделал с подменой. Здесь раскладывает ТРЕТЬЯ СТОРОНА: агент отдаёт подмену
как есть, получает её обратно ПЕРЕПИСАННОЙ — с большой буквы, в E.164, без
запятых — и пишет дальше уже это. Восстановитель встречает свой токен, который
переформатировала не модель, а чужой сервис, и по строке отличить одно от
другого нельзя. Это тот же путь, что «модель переписала подмену», пройденный
снаружи.

ТЕЛЕФОН ЗДЕСЬ ГЛАВНЫЙ, а не имя: клиент диктует его словами или через дефисы, и
нормализатор возвращает `+7…`. Именно на этом шаге «цифровая подпись» волта
(`unmask_text` переиндексирует по цифрам) обязана сработать — токен, который
пришёл словами, а ушёл цифрами, не совпадает ни с чем по строке.

ЧТО СЕМЬЯ НАШЛА НА ПЕРВОМ ЖЕ ПРОГОНЕ, и это решение владельца, а не дефект кода.
Агент отдаёт нормализатору подмену «8-907-965-91-00», тот возвращает
«+79079659100» — ровно то, ради чего его звали, — шлюз маскирует ответ и
показывает модели СНОВА «8-907-965-91-00», потому что волт хранит одну форму на
человека и побеждает ПЕРВАЯ увиденная (`vault._digits_in_customer_form`, «first
writer wins: … what the tool gets is stable across turns instead of flipping
with phrasing»). Агент пишет её в поле, объявленное строгим E.164, и мок
отказывает — а контрольное плечо проходит. 40 полей, класс `validated_refused`.

Правило про первую форму принято намеренно и по названной причине; цена ему —
вот эта: НОРМАЛИЗАЦИЯ ТРЕТЬЕЙ СТОРОНОЙ ОТМЕНЯЕТСЯ ШЛЮЗОМ. Менять правило значит
вернуть то, от чего оно защищало (форма в инструменте скачет от фразы к фразе),
поэтому семья это ИЗМЕРЯЕТ, а не чинит.

Регистр `voice_raw` для этой семьи не декорация: там телефон и дом СЛОВАМИ, и
нормализатор возвращает то, чего в исходном сообщении не было ни одним символом.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("normalize_contact", "crm_upsert_contact", "crm_find_contact", "courier_book",
         "notify_sms", "crm_add_note")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("normalize", seed, 0, "chat").rng)
    return [_one(c.ctx_for("normalize", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    drawn = c.draw(ctx, city=city, with_flat=True)
    identity = f"p{ctx.index}"
    reachable = ["normalize_contact", "crm_upsert_contact"]
    reachable.append("notify_sms" if ctx.index % 2 else "courier_book")
    if ctx.index % 5 == 0:
        reachable.append("crm_add_note")
    builder = c.CaseBuilder(
        ctx=ctx, role="crm", tools=TOOLS, reachable=tuple(reachable),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-norm-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="нормализатор переписывает подмену и агент пишет дальше ЕЁ; "
             "восстановитель встречает свой токен в чужой форме")

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("запишите нового клиента")
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given", "patronymic")))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say("адрес")
    second.value("a1", c.address(ctx, drawn.address))
    second.say(ctx.rng.choice(("приведите к стандартному виду и сохраняйте",
                               "почистите через справочник и записывайте",
                               "нормализуйте и заносите в базу")))
    if ctx.register == "clean":
        second.punct(".")
    builder.user(second, {"a1": ("LOC", identity + ".home", "required", False)})
    return builder.build()
