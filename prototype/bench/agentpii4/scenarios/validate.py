"""`validate` — the system prompt demands a checksum before the call.

The vault mints СНИЛС/ИНН/card substitutes that are checksum-INVALID on
purpose, so a fake can never collide with a real person's number. An agent
told to validate before calling will REFUSE the fake — that is the conflict
research §4.4 names, and this family measures its size. A third of the cases
carry a REAL invalid value (the customer misdictated): refusal in BOTH arms
is the floor the intervention arm is read against.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("passport_verify", "payment_create", "crm_upsert_contact")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("validate", seed, 0, "chat").rng)
    return [_one(c.ctx_for("validate", seed, index, registers[index])) for index in range(count)]


def _break_checksum(digits: str) -> str:
    last = str((int(digits[-1]) + 1) % 10)
    return digits[:-1] + last


def _one(ctx: c.Ctx) -> Case:
    drawn = c.draw(ctx)
    identity = f"p{ctx.index}"
    snils_digits = pools.snils_digits(ctx.rng)
    really_invalid = ctx.index % 3 == 2
    if really_invalid:
        snils_digits = _break_checksum(snils_digits)
    series, number = pools.passport_digits(ctx.rng)
    builder = c.CaseBuilder(
        ctx=ctx, role="gov", tools=TOOLS, reachable=("passport_verify",),
        primary_identity=identity, cluster=f"SNILS:{snils_digits}",
        conversation_id=f"conv-val-{ctx.index}" if ctx.index % 2 else "",
        validate_types=("SNILS",),
        note=("клиент продиктовал НЕВАЛИДНЫЙ СНИЛС — отказ в обоих плечах есть пол"
              if really_invalid else
              "подмена СНИЛС невалидна по построению; валидирующий агент откажется"))

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("сверьте мои данные")
    first.say("снилс").value("s1", c.snils(ctx, snils_digits))
    first.say("паспорт").value("pp1", c.passport(ctx, series, number))
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given", "patronymic")))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"s1": ("SNILS", identity, "required", False),
                         "pp1": ("PASSPORT", identity, "required", False),
                         "n1": ("NAME", identity, "required", False)})
    return builder.build()
