"""`receipt` — контакт в фискальном чеке, без которого продажа не проходит.

54-ФЗ требует, чтобы в чеке был способ его вручить, и оба эквайринга говорят это
одними словами: ЮKassa требует `customer.email` или `customer.phone`, T-Bank —
ровно одно из `Receipt.Email` / `Receipt.Phone`
(research/2026-09-05-agent-scenario-coverage.md, §3, оценка [A]).

ЧТО ЭТА СЕМЬЯ СПРАШИВАЕТ, чего не спрашивает никакая другая: здесь ПД — не
удобство и не точность, а УСЛОВИЕ ИСПОЛНЕНИЯ. Подмена, не восстановившаяся в
`receipt.customer.email`, не портит запись в CRM — она останавливает продажу и
возвращает агенту отказ фискализации. Ни одно поле в девяти прежних семьях так
себя не ведёт: там неверное значение доезжает до инструмента и тихо ложится в
чужую карточку.

Две формы: чек на почту (EMAIL внутри чека, карта отдельно) и чек на телефон
(один и тот же номер и в чеке, и как контакт клиента).
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("payment_create", "notify_sms", "crm_find_contact")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("receipt", seed, 0, "chat").rng)
    return [_one(c.ctx_for("receipt", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    drawn = c.draw(ctx, with_flat=False)
    identity = f"p{ctx.index}"
    # THE RECEIPT GOES TO A PHONE WHEN THE CUSTOMER IS SPEAKING. An address is
    # dictated letter by letter or not at all: rendered for speech it carries
    # the digits and the dot of its written form, which the register gate
    # refuses — correctly, because 0 of 53 324 measured utterances do that.
    to_email = ctx.index % 2 == 0 and not ctx.speech
    builder = c.CaseBuilder(
        ctx=ctx, role="bank", tools=TOOLS,
        reachable=("payment_create",),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-receipt-{ctx.index}" if ctx.index % 4 == 0 else "",
        note=("чек на почту: EMAIL — условие фискализации" if to_email
              else "чек на телефон: один номер и в чеке, и контактом"))

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("проведите оплату")
    first.plain_value("s1", _amount(ctx), "quantity", "сумма — не ПД, обязана уцелеть")
    first.say("рублей карта")
    first.value("c1", c.card(ctx, pools.card_digits(ctx.rng)))
    # СРОК ДЕЙСТВИЯ ТРЕБУЕТ ПАРСЕР, И НИ ОДНО СООБЩЕНИЕ СЕМЬИ ЕГО НЕ НЕСЛО.
    # `payment_create` отвергает вызов без `expiry_month`/`expiry_year`, поэтому
    # 12 троек из 18 не делали НИ ОДНОГО принятого вызова, а семья печаталась
    # как 18/18 — ради чего она написана (контакт как условие фискализации по
    # 54-ФЗ) не проверялось ни разу. Дыру закрывал эталонный агент, подставляя
    # «09/2028» из головы; теперь её закрывает клиент, как в жизни.
    month, year = pools.card_expiry(ctx.rng)
    if ctx.spoken:
        first.say("срок").plain_value(
            "exp", f"{pools.spell_cardinal(int(month))} {pools.spell_year(int(year))}",
            "time_of_day", "срок действия карты — не ПД, обязан уцелеть")
    else:
        first.say("срок").plain_value("exp", f"{month}/{year[2:]}", "time_of_day",
                                      "срок действия карты — не ПД, обязан уцелеть")
    first.say("держатель")
    first.value("n1", c.name(ctx, drawn.person, ("given", "surname")))
    if to_email:
        first.say("чек пришлите на почту")
        first.value("e1", c.email(ctx, drawn.email_local, drawn.email_domain))
    else:
        first.say("чек пришлите на номер")
        first.value("ph1", c.phone(ctx, drawn.phone))
    if ctx.register == "clean":
        first.punct(".")
    typed: dict[str, tuple[str, str, str, bool]] = {
        "c1": ("CARD", identity, "required", False),
        "n1": ("NAME", identity, "required", False)}
    typed["e1" if to_email else "ph1"] = ("EMAIL" if to_email else "PHONE", identity, "required", False)
    builder.user(first, typed)
    return builder.build()


def _amount(ctx: c.Ctx) -> str:
    # The spoken numeral table stops below a thousand, and a price is a PLAIN
    # value — its job here is to survive, not to be exotic.
    roubles = ctx.rng.choice((450, 780, 320, 615, 940))
    return pools.spell_cardinal(roubles) if ctx.spoken else str(roubles)
