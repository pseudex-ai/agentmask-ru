"""Сверка операторского интерфейса с журналом прогона — один в один.

WHY THIS IS A SEPARATE INSTRUMENT AND NOT A LINE IN THE RUN.

The customer sees the product through this interface and nothing else. If the
run protected eleven values and the screen lists nine, the two missing ones are
invisible for ever: nobody compares a screen against a JSONL they do not have.
So the screen is measured the way the detector is measured — against an
independent record, with both directions counted.

FOUR QUESTIONS, and each fails loudly:

  1. СЧЁТЧИК ЗАПРОСОВ. `/stats.requests_total` against the number of completions
     the run actually made. This is the number the customer is billed on, so a
     drift here is a commercial defect, not a cosmetic one.
  2. КАЖДАЯ СТРОКА ЭКРАНА НАСТОЯЩАЯ. Every token in `/events` is revealed, and
     the value behind it must literally occur in what the run sent. A row that
     reveals a value nobody wrote is an invented record.
  3. НИЧЕГО НЕ ПРОПАЛО. Everything the engine's own detector finds in what the
     run sent must appear among the revealed values. This is the direction that
     catches a screen quietly showing less than happened.
  4. ЖУРНАЛ РАСКРЫТИЙ. Our reveals — and only ours — are added to `/reveals`,
     against our actor, and none of the records carries the value.

The reveals in step 2 are REAL reveals against a real audit log; that is the
point, and step 4 is what proves it. Run it against a stand, never against a
customer's container.

    python3 bench/agentrun/audit_match.py masked.journal.jsonl \\
        --engine http://127.0.0.1:8000 --admin-token "$TOKEN" --org default
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx  # noqa: E402

ACTOR = "сверка-с-журналом"

# Types the interface is expected to account for. DATE is excluded on purpose:
# a date is personal by association, so the same string is protected in one
# message and correctly left alone in another, and demanding a row for every
# occurrence would report a defect where the rule is working.
_ACCOUNTED = frozenset({"PHONE", "EMAIL", "NAME", "LOC", "SNILS", "INN",
                        "CARD", "PASSPORT", "PLATE", "ACCOUNT"})


def journal_sent(path: str) -> tuple[list[str], int]:
    """The client's own words, and how many completions the run asked for.

    Only `user` content is taken. Tool results and the assistant's replies are
    OUR text and the engine's own output; counting them would ask the interface
    to account for values it minted rather than values the customer sent.
    """
    texts: list[str] = []
    requests = 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        requests += 1
        for message in record.get("sent") or []:
            if message.get("role") == "user" and isinstance(message.get("content"), str):
                texts.append(message["content"])
    return texts, requests


def api(engine: str, token: str) -> httpx.Client:
    return httpx.Client(base_url=engine.rstrip("/"),
                        headers={"Authorization": f"Bearer {token}"}, timeout=30.0)


def all_events(client: httpx.Client, org: str) -> list[dict[str, object]]:
    """Every page. A first-page-only check passes while the tail is broken."""
    out: list[dict[str, object]] = []
    offset = 0
    while True:
        page = client.get("/events", params={"org_id": org, "limit": 200,
                                             "offset": offset, "period": "14d"})
        page.raise_for_status()
        body = page.json()
        rows = body.get("events") or []
        out.extend(rows)
        offset += len(rows)
        if not rows or offset >= int(body.get("total") or 0):
            return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("journal")
    parser.add_argument("--engine", default="http://127.0.0.1:8000")
    parser.add_argument("--admin-token", required=True)
    parser.add_argument("--gateway-token", required=True,
                        help="ключ шлюза: /spans гейтится им, не операторским")
    parser.add_argument("--org", default="default")
    parser.add_argument("--dump", type=int, default=12)
    args = parser.parse_args()

    texts, requests = journal_sent(args.journal)
    haystack = "\n".join(texts)
    client = api(args.engine, args.admin_token)
    failures: list[str] = []

    print(f"журнал: {requests} запросов, {len(texts)} клиентских сообщений\n")

    # ── 1. счётчик запросов ────────────────────────────────────────────────
    stats = client.get("/stats", params={"org_id": args.org, "days": 1})
    stats.raise_for_status()
    shown = int(stats.json().get("requests_total") or 0)
    ok = shown == requests
    print(f"{'СХОДИТСЯ' if ok else 'РАСХОДИТСЯ'}  запросы: экран {shown} / журнал {requests}")
    if not ok:
        failures.append(f"счётчик запросов: {shown} против {requests}")

    # ── 2. каждая строка экрана — настоящее значение ───────────────────────
    before = client.get("/reveals", params={"org_id": args.org, "limit": 1})
    before.raise_for_status()
    reveals_before = int(before.json().get("total") or 0)

    events = all_events(client, args.org)
    tokens = sorted({str(e.get("token")) for e in events if e.get("token")})
    revealed: dict[str, str] = {}
    invented: list[tuple[str, str]] = []
    misses: list[str] = []
    for token in tokens:
        response = client.post("/reveal", json={"org_id": args.org,
                                                "token": token, "actor": ACTOR})
        response.raise_for_status()
        value = response.json().get("value")
        if not value:
            misses.append(token)
            continue
        revealed[token] = value
        if value not in haystack:
            invented.append((token, value))

    print(f"{'СХОДИТСЯ' if not invented and not misses else 'РАСХОДИТСЯ'}  "
          f"строки экрана: {len(events)} событий, {len(tokens)} разных токенов, "
          f"раскрыто {len(revealed)}, не нашлось в прогоне {len(invented)}, "
          f"пустых раскрытий {len(misses)}")
    if invented:
        failures.append(f"{len(invented)} строк раскрываются в значение, которого не было в прогоне")
        for token, value in invented[:args.dump]:
            print(f"    придумано: {token} -> {value!r}")
    if misses:
        failures.append(f"{len(misses)} токенов на экране ничего не раскрывают")
        for token in misses[:args.dump]:
            print(f"    пусто: {token}")

    # ── 3. ничего не пропало ───────────────────────────────────────────────
    #
    # IDENTITY IS THE ENGINE'S, NOT OURS. The first version compared the written
    # value against the revealed one as strings, and reported «+7 (931) 256-07-70»
    # and a second spelling of the same street as missing rows. They were not
    # missing: both are the SAME entity written twice, collapsed to one token on
    # purpose, and the screen showing one row for one person is the product
    # working. A checker that re-derives identity re-derives it differently, and
    # then measures the difference between the two implementations.
    #
    # So the question is asked in the engine's own terms: `/spans` reports which
    # token each detected value belongs to, WITHOUT minting one, and that token
    # either has a row on the screen or it does not.
    spans = httpx.post(f"{args.engine.rstrip('/')}/spans",
                       json={"org_id": args.org, "texts": texts},
                       headers={"Authorization": f"Bearer {args.gateway_token}"},
                       timeout=60.0)
    spans.raise_for_status()
    expected: dict[str, tuple[str, str]] = {}
    untokenized: list[tuple[str, str]] = []
    for text, found in zip(texts, spans.json()["results"]):
        for span in found:
            if span["type"] not in _ACCOUNTED:
                continue
            written = text[span["start"]:span["end"]]
            if span.get("token"):
                expected[str(span["token"])] = (span["type"], written)
            else:
                # Detected now but never tokenized during the run. Either the
                # value only appears in text the gateway did not mask, or a
                # recognizer fires here and did not there — both are real.
                untokenized.append((span["type"], written))
    shown = set(tokens)
    lost = [(token, meta) for token, meta in expected.items() if token not in shown]
    ok = not lost and not untokenized
    print(f"{'СХОДИТСЯ' if ok else 'РАСХОДИТСЯ'}  "
          f"покрытие: движок опознал {len(expected)} защищённых значений, "
          f"на экране есть {len(expected) - len(lost)}, нет {len(lost)}, "
          f"без токена {len(untokenized)}")
    if lost:
        failures.append(f"{len(lost)} защищённых значений не видно в интерфейсе")
        for token, (kind, written) in lost[:args.dump]:
            print(f"    нет строки: [{kind}] {written!r} -> {token}")
    if untokenized:
        failures.append(f"{len(untokenized)} значений опознаны, но не были замаскированы в прогоне")
        for kind, written in untokenized[:args.dump]:
            print(f"    без токена: [{kind}] {written!r}")

    # ── 3b. одно значение — одна строка ────────────────────────────────────
    #
    # Not a pass/fail, a number the operator has to be able to trust. The
    # sidecar records audit on a mask-cache MISS, so a value re-sent in a
    # growing transcript is one protected value; the proxy has no such cache,
    # so the same value is recorded once per turn. The requests counter is what
    # the tariff is consumed by and it is exact — but «значений защищено» is the
    # figure on the customer's own screen, and it must not drift from what
    # happened.
    per_token: dict[str, int] = {}
    for event in events:
        per_token[str(event.get("token"))] = per_token.get(str(event.get("token")), 0) + 1
    repeats = {token: count for token, count in per_token.items() if count > 1}
    print(f"{'СХОДИТСЯ' if not repeats else 'ВНИМАНИЕ '}  "
          f"строк на значение: {len(events)} строк на {len(tokens)} значений"
          + (f", повторяются {len(repeats)}" if repeats else ""))

    # ── 4. журнал раскрытий ────────────────────────────────────────────────
    log = client.get("/reveals", params={"org_id": args.org, "limit": 200})
    log.raise_for_status()
    body = log.json()
    ours = [r for r in body.get("reveals") or [] if r.get("actor") == ACTOR]
    leaked = [r for r in ours
              if any(value and value in json.dumps(r, ensure_ascii=False)
                     for value in revealed.values())]
    # THE DELTA, not the total. Counting the whole log made a second run of this
    # checker report twenty records for ten reveals and call it a pass — the
    # check would have survived the engine recording nothing at all, as long as
    # an earlier run had left enough rows behind.
    added = int(body.get("total") or 0) - reveals_before
    ok = added == len(tokens) and not leaked
    print(f"{'СХОДИТСЯ' if ok else 'РАСХОДИТСЯ'}  раскрытия: "
          f"сделали {len(tokens)}, добавилось записей {added}, "
          f"под нашим именем всего {len(ours)}, значение попало в запись {len(leaked)}")
    if added != len(tokens):
        failures.append(f"записано {added} раскрытий вместо {len(tokens)}")
    if leaked:
        failures.append("запись о раскрытии содержит само значение")

    print()
    if failures:
        print("РАСХОЖДЕНИЙ: " + str(len(failures)))
        for item in failures:
            print("  - " + item)
        return 1
    print("админка сходится с журналом один в один")
    return 0


if __name__ == "__main__":
    sys.exit(main())
