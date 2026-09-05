"""`analytics` — НЕСКОЛЬКО людей в одной реплике и сводка по ним.

Каждая прежняя семья говорит об одном человеке; аналитик в CRM спрашивает про
многих сразу — «сколько наших из Самары», «сгруппируй этих по городам». Именно
на такой фразе слой ключ→значение однажды типизировал целый абзац как ОДНО имя,
двое клиентов слились в девятисловную подмену, а города исчезли из вида модели —
считать стало нечего (research/2026-09-05, §2; починено 36aada2).

ЧТО ЭТА СЕМЬЯ СПРАШИВАЕТ, чего не спрашивает никакая другая:

  * ГРАНИЦА между людьми: два человека в одном предложении — это две
    идентичности и две подмены, а не одна длинная;
  * ГОРОД остаётся настоящим (он никого не определяет, 152-ФЗ ст. 3 п. 1) —
    иначе агрегат «по городам» считает выдуманные города;
  * массив в аргументе: `members[].name` — путь с индексом, и подмена каждой
    строки обязана вернуться в СВОЮ строку.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("crm_segment_report", "crm_find_contact", "notify_sms")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("analytics", seed, 0, "chat").rng)
    return [_one(c.ctx_for("analytics", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    cities = list(pools.CITIES)[:10]
    first_city = ctx.rng.choice(cities)
    second_city = ctx.rng.choice([one for one in cities if one != first_city])
    first_person = c.draw(ctx, city=first_city)
    # The second person comes from the foreign pool, as `container` does: it can
    # never coincide with a shared cluster person, so two identities stay two.
    second_person = c.draw(c.ctx_for("analytics", ctx.seed, ctx.index * 100 + 1, ctx.register), foreign=True)
    identity_a = f"p{ctx.index}a"
    identity_b = f"p{ctx.index}b"
    builder = c.CaseBuilder(
        ctx=ctx, role="crm", tools=TOOLS,
        reachable=("crm_segment_report",),
        primary_identity=identity_a, cluster=f"NAME:{c.full_name_canonical(first_person.person)}",
        conversation_id=f"conv-analytics-{ctx.index}" if ctx.index % 3 == 0 else "",
        note="двое в одной фразе и сводка по городам; города настоящие, границы людей — разные")

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("сгруппируйте по городам клиенты")
    first.value("n1", c.name(ctx, first_person.person, ("surname", "given")))
    first.say(f"из {first_city}")
    first.say("и")
    first.value("n2", c.name(ctx, second_person.person, ("surname", "given")))
    first.say(f"из {second_city}")
    # A PERIOD, AND IT CARRIES THE DIGIT. `voice_itn` is defined by inverse text
    # normalisation being on — a case with no number in it is a `voice_raw` case
    # in disguise, and the register gate says so. An analyst always names a
    # window, so the digit is the scenario's own, not a prop.
    first.say("за")
    first.plain_value("q1", _period(ctx), "quantity", "период — не ПД, обязан уцелеть")
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"n1": ("NAME", identity_a, "required", False),
                         "n2": ("NAME", identity_b, "required", False)})
    return builder.build()


def _period(ctx: c.Ctx) -> str:
    """«30 дней» / «тридцать дней» — a window an analyst always names."""
    days = ctx.rng.choice((7, 14, 30, 60, 90))
    return f"{pools.spell_cardinal(days)} дней" if ctx.spoken else f"{days} дней"
