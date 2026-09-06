"""The rig, tested for free.

    python3 bench/agentpii4/smoke.py            # level A: fake gateway, expected verdicts
    python3 bench/agentpii4/smoke.py --engine   # three arms through the REAL gateway,
                                                # scripted agent, full report — $0

Level A asserts that every taxonomy class is PRODUCIBLE and lands where it
should: a deriving agent behind a fake city yields `derived`, a validating
agent refuses only in the intervention arm, a fake gateway that does not
resolve pieces yields `residual`. A class the rig cannot produce on demand is
a class the live run could never report.

`--engine` is the same scripted policies through `RealGateway`, which is the
production path with the real vault. Its report is headed «СКРИПТОВЫЙ АГЕНТ»
and is never merged with a live number: it proves the plumbing, not the model.

IT IS A SAMPLE, NOT A FIXED NUMBER, AND THE AGENT IS NOT WHAT VARIES. The vault
mints substitutes with `secrets`, so every process draws a different fake and
the same corpus scores differently — measured over ten runs of the 474-case
corpus, L1 100.0 always, L2 99.8-100.0, L3 state 98.7-99.4, L3 VALUES
97.7-98.3. A move under about 0.7pp is the draw, not a change; `--repeats N`
averages it down. Read a movement of a WHOLE FAMILY (30 of 30 to 0 of 30) as
signal and a tenth of a point as weather.
"""
import argparse
import sys
from pathlib import Path

from bench.agentpii4 import report
from bench.agentpii4.compare import ArmRun, Triple, pair_runs
from bench.agentpii4.fake_agent import POLICIES, FakeGateway, Policy, scripted_run, seed_backend
from bench.agentpii4.gateway import PassThrough
from bench.agentpii4.schema import Case

_HERE = Path(__file__).resolve().parent


def _load(path: Path) -> list[Case]:
    import json
    from bench.agentpii4.schema import case_from_json
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [case_from_json(one) for one in raw["corpus"]]


def _triple(case: Case, policy_c: Policy, policy_i: Policy, gateway_i: object, repeat: int = 0) -> Triple:
    c = scripted_run(case, "C", repeat, PassThrough(case), seed_backend(case), policy_c)
    i = scripted_run(case, "I", repeat, gateway_i, seed_backend(case), policy_i)
    c2 = scripted_run(case, "C2", repeat, PassThrough(case), seed_backend(case), policy_c)
    return Triple(case.id, repeat, c, i, c2)


def _kinds(case: Case, triple: Triple) -> dict[str, list[str]]:
    from bench.agentpii4.compare import compare_triple
    ic, _cc = compare_triple(case, triple)
    return {f"{f.tool}.{f.path}": [f.kind, f.sub, f.transform] for f in ic.fields}


def level_a(cases: list[Case]) -> int:
    failures = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"{'PASS' if condition else 'FAIL'}  {label}{('  ' + detail) if detail and not condition else ''}")
        failures += 0 if condition else 1

    by_kind: dict[str, Case] = {}
    for case in cases:
        by_kind.setdefault(case.kind, case)

    # A deriving agent reading a fake city writes a postcode of the FAKE's zone.
    case = by_kind["derive"]
    delivery = next(c for c in cases if c.kind == "derive" and "delivery_create_order" in c.expects.reachable_tools)
    kinds = _kinds(delivery, _triple(delivery, POLICIES["deriver"], POLICIES["deriver"], FakeGateway(delivery)))
    postcode = kinds.get("delivery_create_order.to_location.postal_code", ["?"])
    check("deriver: postal_code from a fake city -> derived", postcode[0] == "derived", str(postcode))
    clinic = next(c for c in cases if c.kind == "derive" and "clinic_book" in c.expects.reachable_tools)
    kinds = _kinds(clinic, _triple(clinic, POLICIES["deriver"], POLICIES["deriver"], FakeGateway(clinic)))
    age = kinds.get("clinic_book.patient.age", ["?"])
    check("deriver: age from a fake birth date -> derived", age[0] == "derived", str(age))
    gender = kinds.get("clinic_book.patient.gender", ["?"])
    check("deriver: gender from a gender-preserving fake -> agree", gender[0] == "agree", str(gender))

    # A validating agent refuses the checksum-invalid fake in I only.
    validate = next(c for c in cases if c.kind == "validate" and "невалидн" not in c.note.lower().split("клиент")[0])
    validate = next(c for c in cases if c.kind == "validate" and c.note.startswith("подмена"))
    triple = _triple(validate, POLICIES["validator"], POLICIES["validator"], FakeGateway(validate))
    from bench.agentpii4.compare import compare_triple
    ic, cc = compare_triple(validate, triple)
    check("validator: I refuses to call (no_call) while C′≈C", ic.levels.tools_sub == "no_call" and cc.levels.tools,
          f"{ic.levels.tools_sub} / {cc.levels.tools}")
    really_invalid = next(c for c in cases if c.kind == "validate" and c.note.startswith("клиент"))
    ic2, cc2 = compare_triple(really_invalid, _triple(really_invalid, POLICIES["validator"], POLICIES["validator"], FakeGateway(really_invalid)))
    check("validator: a REALLY invalid value -> both arms refuse, L1 agrees", ic2.levels.tools and cc2.levels.tools,
          f"{ic2.levels.tools_sub} / {cc2.levels.tools_sub}")

    # A decomposing agent with piece resolution agrees; without it, residual.
    chain = by_kind["chain"]
    kinds = _kinds(chain, _triple(chain, POLICIES["decomposer"], POLICIES["decomposer"], FakeGateway(chain, resolve_pieces=True)))
    street = kinds.get("crm_upsert_contact.contact.address.street", ["?"])
    check("decomposer + piece resolution: street -> agree", street[0] == "agree", str(street))
    kinds = _kinds(chain, _triple(chain, POLICIES["decomposer"], POLICIES["decomposer"], FakeGateway(chain, resolve_pieces=False)))
    street = kinds.get("crm_upsert_contact.contact.address.street", ["?"])
    check("decomposer without piece resolution: street -> residual", street[0] == "residual", str(street))

    # A copier agrees verbatim everywhere it can.
    summary = by_kind["summary"]
    ic, _ = compare_triple(summary, _triple(summary, POLICIES["copier"], POLICIES["copier"], FakeGateway(summary)))
    check("copier: L1/L2 agree", ic.levels.tools and ic.levels.keys, f"{ic.levels}")

    # A sloppy agent drops optional fields: `absent` where the control wrote them.
    courier = next(c for c in cases if c.kind == "decompose" and "courier_book" in c.expects.reachable_tools)
    ic, _ = compare_triple(courier, _triple(courier, POLICIES["decomposer"], POLICIES["sloppy"], FakeGateway(courier)))
    dropped = [f.kind for f in ic.fields if f.path in ("address.sflat", "address.porch")]
    check("sloppy vs decomposer: dropped flat/porch -> absent or keys differ",
          "absent" in dropped or not ic.levels.keys, str(dropped))

    # A correction case: the stale value is what a copier-of-first would send.
    correction = by_kind["correction"]
    ic, _ = compare_triple(correction, _triple(correction, POLICIES["decomposer"], POLICIES["decomposer"], FakeGateway(correction)))
    check("correction: decomposer uses the CURRENT address (agree)", ic.levels.state, str(ic.levels.state_diff[:2]))

    # THE AGENT MAY NEVER WRITE A REAL VALUE IT WAS SHOWN A SUBSTITUTE FOR.
    # Not a property of the gateway — a property of the INSTRUMENT, and one it
    # lost twice while the turn structure was being built: once by reading a
    # seed card's sibling fields off the real item, once by falling back to the
    # real item's parts when it could not parse a spoken date. Both times every
    # level reported agreement, because both arms then held the same value. A
    # leak the rig itself commits is invisible to every other number here.
    written_real = _real_values_written(cases)
    check("scripted agent: no real value written in arm I", not written_real,
          "; ".join(f"{cid} {kind} {probe!r} (shown {shown!r})"
                    for cid, kind, probe, shown in written_real[:4]))

    # A MUTATING CALL WAITS FOR THE CUSTOMER TO STOP DICTATING. Without it the
    # turn-by-turn planner booked on the first turn with half the request and
    # again on the second; through the real gateway the two arms did not agree
    # on how many calls that was.
    late = _late_write_cases(cases)
    check("turn structure: a write is deferred while a later message adds to it",
          bool(late), f"no case defers a write ({len(cases)} scanned)")

    # Noise floor: a noisy C′ produces disagreement with C.
    noisy = Policy("noisy", noise=0.6, seed=3)
    disagreements = 0
    for case in cases[:12]:
        c = scripted_run(case, "C", 0, PassThrough(case), seed_backend(case), POLICIES["copier"])
        c2 = scripted_run(case, "C2", 0, PassThrough(case), seed_backend(case), noisy)
        i = scripted_run(case, "I", 0, FakeGateway(case), seed_backend(case), POLICIES["copier"])
        _, cc = compare_triple(case, Triple(case.id, 0, c, i, c2))
        disagreements += 0 if cc.levels.tools else 1
    check("noisy C′: the floor is non-zero", disagreements > 0, str(disagreements))
    print()
    print("ИТОГО:", "PASS" if not failures else f"FAIL ({failures})")
    return failures


def _probes(item: object) -> tuple[str, ...]:
    """Every rendering of ONE real value the agent could write.

    Not `item.parts` wholesale: `street_type` is «улица» and `gender` is «m» —
    structure, not the value, and a seeded card legitimately carries them past
    the substitute."""
    roles = {"DOB": ("iso",), "NAME": ("surname", "given", "patronymic"),
             "LOC": ("street",), "PHONE": ("digits",), "SNILS": ("digits",),
             "INN": ("digits",), "CARD": ("digits",),
             "PASSPORT": ("series", "number", "digits")}
    out = {item.value, item.canonical}                     # type: ignore[attr-defined]
    out.update(item.parts.get(role, "") for role in roles.get(item.type, ()))  # type: ignore[attr-defined]
    return tuple(one for one in out if len(one) >= 4)


def _real_values_written(cases: list[Case]) -> list[tuple[str, str, str, str]]:
    import re as _re
    from bench.agentpii4.tools import flatten
    found: list[tuple[str, str, str, str]] = []
    for case in cases:
        gateway = FakeGateway(case)
        run = scripted_run(case, "I", 0, gateway, seed_backend(case), POLICIES["decomposer"])
        shown = gateway.substitutes_seen()
        text = " ".join(str(value) for call in run.calls
                        for value in flatten(call.written).values() if isinstance(value, str))
        for item in case.pii:
            substitute = shown.get(item.id)
            if not substitute:
                continue
            for probe in _probes(item):
                if probe.casefold() in substitute.casefold():
                    continue
                if _re.search(rf"(?<![\w\u0400-\u04ff]){_re.escape(probe)}(?![\w\u0400-\u04ff])",
                              text, _re.IGNORECASE):
                    found.append((case.id, item.type, probe, substitute))
    return found


def _late_write_cases(cases: list[Case]) -> list[str]:
    """Cases where a mutating call is held back past the first user message."""
    from bench.agentpii4.fake_agent import plan_calls
    from bench.agentpii4.tools import REGISTRY
    late: list[str] = []
    for case in cases:
        turns = [index for index, message in enumerate(case.messages) if message.role == "user"]
        if len(turns) < 2:
            continue
        gateway = FakeGateway(case)
        first = plan_calls(case, gateway, POLICIES["decomposer"], turns[0], frozenset(), ())
        whole = plan_calls(case, gateway, POLICIES["decomposer"], turns[-1], frozenset(), ())
        early = {name for name, _ in first if REGISTRY[name].mutating}
        eventual = {name for name, _ in whole if REGISTRY[name].mutating}
        if eventual - early:
            late.append(case.id)
    return late


def engine_run(cases: list[Case], policy_name: str, repeats: int) -> int:
    from testkit import load_dev_bundle
    from bench.agentpii4.gateway import RealGateway
    from pseudex.audit import AuditLog
    from pseudex.detect_all import Detector
    from pseudex.maskcache import MaskCache
    from pseudex.vault import Vault
    load_dev_bundle()
    detector = Detector()
    policy = POLICIES[policy_name]
    runs: list[ArmRun] = []
    for case in cases:
        for repeat in range(repeats):
            runs.append(scripted_run(case, "C", repeat, PassThrough(case), seed_backend(case), policy))
            gateway = RealGateway(case, detector, Vault(":memory:", "agentpii4"), AuditLog(":memory:"), MaskCache(256))
            runs.append(scripted_run(case, "I", repeat, gateway, seed_backend(case), policy))
            runs.append(scripted_run(case, "C2", repeat, PassThrough(case), seed_backend(case), policy))
    triples, excluded = pair_runs(runs)
    by_id = {case.id: case for case in cases}
    scored = report.score_triples(by_id, triples)
    for line in report.render(by_id, scored, excluded,
                              f"СКРИПТОВЫЙ АГЕНТ «{policy_name}» — не живой прогон; три плеча через настоящий шлюз",
                              dump=12):
        print(line)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?", default=str(_HERE / "corpus.json"))
    parser.add_argument("--engine", action="store_true")
    parser.add_argument("--policy", default="decomposer", choices=sorted(POLICIES))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0, help="first N cases (0 = all)")
    args = parser.parse_args()
    cases = _load(Path(args.corpus))
    if args.limit:
        cases = cases[:args.limit]
    if args.engine:
        return engine_run(cases, args.policy, args.repeats)
    return 1 if level_a(cases) else 0


if __name__ == "__main__":
    sys.exit(main())
