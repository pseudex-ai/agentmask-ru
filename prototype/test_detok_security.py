"""Detok surface hardening (pentest B1/B2/B4).

B1 — /unmask* wrote no audit row, so a compromised gateway credential could trawl
     the vault leaving no trace. Now every /unmask and /unmask_arguments call
     records a COUNTS-ONLY detok row (resolved + misses, never values) and is
     rate-limited per org.
B2 — org_id came from the body, unbound to the credential; a bound container
     (PSEUDEX_ORG) now refuses any other org (one tenant per container).
B4 — the audit preview disclosed first-2 + last-2 chars; narrowed to at most one
     char at each end, and nothing for a short value.

Not B3: /unmask stays reachable on an expired lease BY DESIGN (the customer's own
vault, and /mask being down already stops the agent) — that decision is left to
the owner; see the report.

Run:  python3 test_detok_security.py
"""
import contextlib
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# A temp DB dir + a bound org, set BEFORE importing the app (read at import time).
_TMP = tempfile.mkdtemp(prefix="pseudex-detok-test-")
os.environ["PSEUDEX_DB_DIR"] = _TMP
os.environ["PSEUDEX_VAULT_ENCRYPTION"] = "off"
os.environ.setdefault("PSEUDEX_GATEWAY_TOKEN", "test-gw")

import httpx  # noqa: E402
import testkit  # noqa: E402
from pseudex import service  # noqa: E402
from pseudex.audit import AuditLog, _preview  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.redact import mask_text  # noqa: E402

# Fake pools are leased (WS-2), so /unmask* (token recognition) needs a bundle.
testkit.load_dev_bundle()

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def test_preview_narrowed() -> None:
    """B4: a short value discloses nothing; a long one at most first+last."""
    short = _preview("14")          # house number
    code = _preview("4821")         # 4-digit
    phone = _preview("+79991234567")
    ok = (set(short) == {"•"}
          and code.count("•") >= 3
          and phone[0] == "+" and phone[-1] == "7" and phone.count("•") == len(phone) - 2)
    check(ok, "B4 preview narrowed (short hidden, long ≤2 chars)",
          f"'14'->{short!r} '4821'->{code!r} phone->{phone!r}")


def test_record_detok_counts_only() -> None:
    """B1: record_detok stores counts, never values; a sweep shows as volume."""
    a = AuditLog(os.path.join(_TMP, "audit_probe.db"))
    import time as _t
    since = _t.time() - 1
    for _ in range(5):
        a.record_detok("acme", "gateway", resolved=0, misses=20)  # sweep shape
    a.record_detok("acme", "gateway", resolved=3, misses=0)       # legit shape
    calls = a.detok_calls_since("acme", since)
    check(calls == 6, "B1 detok calls recorded (counts only)", f"calls={calls}")


def test_rate_limit() -> None:
    """B1: over the per-org cap → refused. The cap is counted from the SHARED audit
    (cross-worker), so recording rows is what trips it — not a per-worker counter."""
    saved = service._DETOK_MAX_PER_MIN
    service._DETOK_MAX_PER_MIN = 3
    try:
        org = "ratelimit-test-org"
        fresh = service._detok_rate_ok(org)                 # 0 rows -> allowed
        for _ in range(3):
            service.AUDIT.record_detok(org, "gateway", 1, 0)
        over = service._detok_rate_ok(org)                  # 3 >= 3 -> refused
        check(fresh and not over,
              "B1 detok rate limit trips over the cap (cross-worker, from audit)",
              f"fresh={fresh} over={over}")
    finally:
        service._DETOK_MAX_PER_MIN = saved


async def _app_calls() -> None:
    """B2 at the HTTP layer: bound container refuses another org; the bound org's
    /unmask writes a detok audit row."""
    service._BOUND_ORG = "acme"
    gw = {"Authorization": f"Bearer {os.environ['PSEUDEX_GATEWAY_TOKEN']}"}
    transport = httpx.ASGITransport(app=service.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        wrong = await client.post("/unmask", headers=gw,
            json={"org_id": "globex", "response": {"choices": []}})
        right = await client.post("/unmask", headers=gw,
            json={"org_id": "acme", "response": {"choices": [
                {"message": {"content": "nothing to resolve"}}]}})
    before = service.AUDIT.detok_calls_since("acme", 0)
    check(wrong.status_code == 403, "B2 bound container refuses another org",
          f"globex->{wrong.status_code} acme->{right.status_code}")
    check(right.status_code == 200 and before >= 1,
          "B1 /unmask on the bound org writes a detok audit row",
          f"acme->{right.status_code} detok_rows={before}")


def test_app_org_bind_and_audit() -> None:
    import anyio
    try:
        anyio.run(_app_calls)
    finally:
        service._BOUND_ORG = ""


def test_detok_counts_values_not_calls() -> None:
    """F2: one call resolving N values records N, not 1 — a batch of many values in
    ONE call cannot hide under a per-CALL cap. Counts the actual minted tokens the
    call resolved (present in input, gone from output), via the same residual_tokens
    the residual signal already uses."""
    org = "batch-values-org"
    v = service._vault(org)
    toks = [v.tokenize(f"+7 999 111 22 {i:02d}", "PHONE") for i in range(3)]
    one_arg = "звоните " + " и ".join(toks)              # 3 values, ONE call/arg
    _restored, _residual, disclosed = service._unmask_arguments_for([one_arg], org)
    check(disclosed == 3,
          "F2 one batched call counts 3 resolved VALUES (a call-counter sees 1)",
          f"disclosed={disclosed}")


def test_rate_limit_by_values() -> None:
    """F2: the cap is on VALUES disclosed, not calls. One call disclosing `cap`
    values trips it; a pure-miss sweep does not consume the disclosure budget."""
    saved = service._DETOK_MAX_PER_MIN
    service._DETOK_MAX_PER_MIN = 5
    try:
        org = "values-cap-org"
        fresh = service._detok_rate_ok(org)                   # 0 -> allowed
        service.AUDIT.record_detok(org, "gateway", 5, 0)      # ONE call, 5 values
        over = not service._detok_rate_ok(org)                # 5 >= 5 -> refused
        calls = service.AUDIT.detok_calls_since(org, 0)
        values = service.AUDIT.detok_values_since(org, 0)
        service.AUDIT.record_detok(org, "gateway", 0, 50)     # sweep, no values
        after_sweep = service.AUDIT.detok_values_since(org, 0)
        check(fresh and over and calls == 1 and values == 5 and after_sweep == 5,
              "F2 rate limit counts VALUES not calls (one batched call trips it)",
              f"calls={calls} values={values} after_sweep={after_sweep}")
    finally:
        service._DETOK_MAX_PER_MIN = saved


async def _chunk_audit_calls() -> None:
    """F1: /unmask_chunk writes a counts-only detok row when it discloses a value."""
    service._BOUND_ORG = ""
    org = "chunk-audit-org"
    tok = service._vault(org).tokenize("+7 999 777 66 55", "PHONE")
    gw = {"Authorization": f"Bearer {os.environ['PSEUDEX_GATEWAY_TOKEN']}"}
    before = service.AUDIT.detok_calls_since(org, 0)
    transport = httpx.ASGITransport(app=service.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/unmask_chunk", headers=gw, json={
            "org_id": org, "delta": f"на {tok} перезвоним", "carry": "", "flush": True})
    after = service.AUDIT.detok_calls_since(org, 0)
    summary = service.AUDIT.detok_summary(org, 0)
    real_back = "777" in r.json().get("text", "")
    check(r.status_code == 200 and after == before + 1
          and summary["resolved"] >= 1 and real_back,
          "F1 /unmask_chunk writes a detok audit row on disclosure",
          f"status={r.status_code} rows {before}->{after} "
          f"resolved={summary['resolved']} real={real_back}")


async def _chunk_limit_calls() -> None:
    """F1: /unmask_chunk is under the same value cap as /unmask."""
    service._BOUND_ORG = ""
    saved = service._DETOK_MAX_PER_MIN
    service._DETOK_MAX_PER_MIN = 1
    try:
        org = "chunk-cap-org"
        tok = service._vault(org).tokenize("+7 999 500 40 30", "PHONE")   # a real minted token
        service.AUDIT.record_detok(org, "gateway", 5, 0)      # already over the cap
        gw = {"Authorization": f"Bearer {os.environ['PSEUDEX_GATEWAY_TOKEN']}"}
        transport = httpx.ASGITransport(app=service.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            # A delta carrying a MINTED token — a chunk that could disclose is what the cap
            # gates; a chunk with no minted token discloses nothing and is not rate-limited
            # (the minted-token early-out).
            r = await client.post("/unmask_chunk", headers=gw, json={
                "org_id": org, "delta": f"на {tok} перезвоним", "carry": "", "flush": True})
        check(r.status_code == 429, "F1 /unmask_chunk honors the detok rate limit",
              f"status={r.status_code}")
    finally:
        service._DETOK_MAX_PER_MIN = saved


def test_unmask_chunk_audited_and_limited() -> None:
    import anyio
    try:
        anyio.run(_chunk_audit_calls)
        anyio.run(_chunk_limit_calls)
    finally:
        service._BOUND_ORG = ""


@contextlib.contextmanager
def _forced_street(street: str):
    """Pin the fake street the pool draws, so two dialogues collide ON PURPOSE.

    The draw is random, so a test that waited for the collision would catch the
    defect about once in forty runs — which is a test that does not exist."""
    real = secrets.choice

    def choice(seq):
        seq = list(seq)
        return street if street in seq else real(seq)

    secrets.choice = choice
    try:
        yield
    finally:
        secrets.choice = real


def _mint_bare_street(org: str, conversation: str, said: str) -> str:
    """The fake a dialogue is shown for a BARE street — no house, no flat, so
    the row it writes has the degenerate key. Minted the way the masking leg
    mints it, because this file stands up no licence server and `/mask` is the
    one endpoint that needs one; everything asserted below is the RESTORING
    side, over HTTP."""
    vault = service._vault(org).for_conversation(conversation)
    shown = mask_text(said, vault, Detector().detect(said))
    return shown.split("набережную", 1)[1].strip().rstrip(".,")


async def _unnamed_conversation_calls() -> None:
    """A LEG THAT NAMES NO CONVERSATION GETS THE SINGLE CANDIDATE, NOT ALL OF THEM.

    `/mask` derives a conversation from the transcript when the host sends no
    `conversation_id` — there is one to derive from. The restoring legs have no
    transcript, so they used to run on the bare customer vault, and the rule
    that keeps one dialogue's bare street out of another's tool
    (`Vault._answers_another_dialogue`) read an empty scope as «nothing to
    compare» and stood down: dialogue B's agent got dialogue A's REAL street
    (Б28). The disclosure was open exactly where the value is HANDED BACK, on
    all three legs at once.

    REFUSING OUTRIGHT IS NOT THE FIX, AND THAT IS WHY THIS TEST HAS TWO HALVES.
    The documented sidecar client (`docs/integration-diva-backend-api.md`,
    `POST /unmask {org_id, response}`) sends no `conversation_id` at all, so «no
    dialogue, no answer» silently breaks a working integration. The rule is the
    one the conversation scope itself stands on: exactly one candidate in the
    whole vault → answer; two → refuse. So a customer with ONE dialogue about
    this street keeps working, and a customer with two no longer confuses them.

    And the refusal has to be AUDIBLE: D-067 prices the narrowing as «the
    street comes back as a residual token, visibly, instead of answering with
    somebody else's street silently», and a 200 with a fake inside and an empty
    `residual_tokens` is that silence.
    """
    service._BOUND_ORG = ""
    gw = {"Authorization": f"Bearer {os.environ['PSEUDEX_GATEWAY_TOKEN']}"}
    transport = httpx.ASGITransport(app=service.app)
    said = "подъезжаем на набережную Ольгина"

    # ONE CANDIDATE: one dialogue ever spoke of this street.
    alone = "unnamed-one-candidate"
    with _forced_street("Каштановой"):
        only = _mint_bare_street(alone, "conv-A", said)
    # TWO CANDIDATES: a second dialogue of the same customer is shown a fake
    # street with the SAME name (its own address carries a house, so the two
    # rows are two different places wearing one street word).
    both = "unnamed-two-candidates"
    with _forced_street("Каштановой"):
        fake = _mint_bare_street(both, "conv-A", said)
        second = "адрес изобильная 60 кв 186"
        mask_text(second, service._vault(both).for_conversation("conv-B"),
                  Detector().detect(second))

    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        sole = await client.post("/unmask_arguments", headers=gw, json={
            "org_id": alone,
            "arguments": [json.dumps({"street": only}, ensure_ascii=False)]})
        # The agent of ANOTHER dialogue writes that street into a tool argument.
        argument = json.dumps({"street": fake}, ensure_ascii=False)
        nameless = await client.post("/unmask_arguments", headers=gw,
                                     json={"org_id": both, "arguments": [argument]})
        named = await client.post("/unmask_arguments", headers=gw,
                                  json={"org_id": both, "conversation_id": "conv-A",
                                        "arguments": [argument]})
        answer = {"choices": [{"message": {"content": f"везём на {fake}"}}]}
        nameless_answer = await client.post("/unmask", headers=gw,
                                            json={"org_id": both, "response": answer})
        chunk = await client.post("/unmask_chunk", headers=gw, json={
            "org_id": both, "delta": f"везём на {fake}", "carry": "", "flush": True})

    lone = sole.json()
    check("Ольгина" in lone["arguments"][0] and not lone.get("residual_tokens"),
          "a client that names no conversation still gets the single candidate",
          f"{lone}")

    body = nameless.json()
    check("Ольгина" not in body["arguments"][0] and fake in body["arguments"][0],
          "/unmask_arguments with no conversation refuses when two dialogues own the street",
          f"{body['arguments'][0]}")
    check(body.get("residual_tokens") == [fake]
          and nameless.headers.get("X-Pseudex-Residual") == "1",
          "…and says so: the unresolved substitute is in residual_tokens",
          f"residual={body.get('residual_tokens')} header={nameless.headers.get('X-Pseudex-Residual')}")
    check("Ольгина" in named.json()["arguments"][0]
          and not named.json().get("residual_tokens"),
          "…while the dialogue that minted it still gets the real street, with no residual",
          f"{named.json()}")

    answered = nameless_answer.json()
    text = answered["response"]["choices"][0]["message"]["content"]
    check("Ольгина" not in text and fake in text,
          "/unmask with no conversation refuses the ambiguous street too",
          text)
    check(answered.get("residual_tokens") == [fake],
          "…and /unmask reports it as residual too", f"{answered.get('residual_tokens')}")
    check("Ольгина" not in chunk.json()["text"],
          "/unmask_chunk with no conversation does not answer with it either",
          chunk.json()["text"])


def test_unnamed_conversation_is_not_every_conversation() -> None:
    import anyio
    try:
        anyio.run(_unnamed_conversation_calls)
    finally:
        service._BOUND_ORG = ""


async def _restoring_leg_takes_the_declared_scope() -> None:
    """ONE DECLARATION, BOTH LEGS — `pseudonym_scope` on the way BACK.

    `PSEUDEX_PSEUDONYM_SCOPE=customer` and `Vault.with_pseudonym_scope` were
    applied on the masking leg only, and no `/unmask*` body accepted the field
    at all. A host whose agent has memory therefore minted account-wide and
    restored per dialogue — the one combination that helps nobody: the
    substitute the agent recalled was recognised on the way in and refused on
    the way out.

    Asserted on the shape the declaration is FOR: a bare street minted in
    dialogue A, asked about by a dialogue that minted nothing of its own — the
    agent recalling it out of its memory store. At `conversation` scope it is
    refused (and visibly so); at `customer` scope, declared in the body, the
    same call answers. And the body beats the environment, exactly as on
    `/mask` — that is what lets one engine serve an agent with memory next to
    one without.
    """
    service._BOUND_ORG = ""
    gw = {"Authorization": f"Bearer {os.environ['PSEUDEX_GATEWAY_TOKEN']}"}
    transport = httpx.ASGITransport(app=service.app)
    org = "declared-memory-org"
    said = "подъезжаем на набережную Ольгина"
    with _forced_street("Каштановой"):
        fake = _mint_bare_street(org, "conv-A", said)
        second = "адрес изобильная 60 кв 186"
        mask_text(second, service._vault(org).for_conversation("conv-B"),
                  Detector().detect(second))
    argument = json.dumps({"street": fake}, ensure_ascii=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        default = await client.post("/unmask_arguments", headers=gw, json={
            "org_id": org, "conversation_id": "conv-Z", "arguments": [argument]})
        declared = await client.post("/unmask_arguments", headers=gw, json={
            "org_id": org, "conversation_id": "conv-Z", "arguments": [argument],
            "pseudonym_scope": "customer"})
        answered = await client.post("/unmask", headers=gw, json={
            "org_id": org, "conversation_id": "conv-Z", "pseudonym_scope": "customer",
            "response": {"choices": [{"message": {"content": f"везём на {fake}"}}]}})
        chunked = await client.post("/unmask_chunk", headers=gw, json={
            "org_id": org, "conversation_id": "conv-Z", "pseudonym_scope": "customer",
            "delta": f"везём на {fake}", "carry": "", "flush": True})
        misspelt = await client.post("/unmask_arguments", headers=gw, json={
            "org_id": org, "arguments": [argument], "pseudonym_scope": "tenant"})

    check("Ольгина" not in default.json()["arguments"][0]
          and default.json().get("residual_tokens") == [fake],
          "conversation scope (the default) still refuses another dialogue's bare street",
          f"{default.json()}")
    check("Ольгина" in declared.json()["arguments"][0]
          and not declared.json().get("residual_tokens"),
          "…and a body that declares agent memory gets it on /unmask_arguments",
          f"{declared.json()}")
    check("Ольгина" in answered.json()["response"]["choices"][0]["message"]["content"],
          "…on /unmask too",
          f"{answered.json()}")
    check("Ольгина" in chunked.json()["text"], "…and on /unmask_chunk",
          f"{chunked.json()}")
    check(misspelt.status_code == 400,
          "a misspelt pseudonym_scope is a 400, never a silent fallback",
          f"status={misspelt.status_code} body={misspelt.text}")


def test_restoring_leg_takes_the_declared_scope() -> None:
    import anyio
    try:
        anyio.run(_restoring_leg_takes_the_declared_scope)
    finally:
        service._BOUND_ORG = ""


async def _signal_names_every_refused_fragment() -> None:
    """THE SIGNAL SPEAKS ABOUT WHAT THE AGENT WROTE, AND ABOUT EVERY CLASS OF IT.

    Two halves, and both are what the customer's code reads off the wire.

    IT MUST NOT CRY WOLF. `residual_tokens` asked the vault about the windows of
    the ALREADY-RESTORED answer, and «several of my substitutes wear this street
    name» is true of a REAL street that happens to share it — so a CORRECT
    restoration came back with a non-empty `residual_tokens` and an
    `X-Pseudex-Residual` header (5 of 50 dialogues of the documented client). We
    publish that list as a reason to refuse a tool call; a list that fires on a
    correct answer is worse than no list.

    AND IT MUST NOT GO QUIET. Only the STREET refusal was reported. A house
    number and a phone's digit tail refused in silence — 22 and 6 of the same
    50 — because the question was never asked about them: a key carrying digits
    was skipped as «answered customer-wide», which is a statement about the
    SCOPE and not about whether the string is ours.
    """
    service._BOUND_ORG = ""
    gw = {"Authorization": f"Bearer {os.environ['PSEUDEX_GATEWAY_TOKEN']}"}
    transport = httpx.ASGITransport(app=service.app)
    org = "residual-every-class"
    detector = Detector()

    def show(conversation: str, said: str) -> str:
        vault = service._vault(org).for_conversation(conversation)
        return mask_text(said, vault, detector.detect(said))

    # Two dialogues are shown a fake street by the SAME name…
    with _forced_street("Каштановой"):
        show("conv-A", "адрес ольгина 14 кв 7")
        show("conv-B", "адрес изобильная 60 кв 186")
    # …and a third speaks of the REAL Каштановая. Its own answer is correct.
    shown = show("conv-C", "адрес каштановая 77 кв 4, телефон +7 912 345-67-89")
    fake_address = shown.split("адрес ", 1)[1].split(", телефон", 1)[0].strip()
    fake_phone = shown.rsplit("телефон ", 1)[1].strip().rstrip(".")
    house = next(word.strip(".,") for word in fake_address.split()
                 if word.strip(".,").isdigit())
    tail = "".join(character for character in fake_phone if character.isdigit())[-4:]

    correct = {"choices": [{"message": {"content": None, "tool_calls": [
        {"id": "c", "type": "function", "function": {
            "name": "crm", "arguments": json.dumps({"address": fake_address},
                                                   ensure_ascii=False)}}]}}]}
    pieces = json.dumps({"house": house, "last_digits": tail}, ensure_ascii=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        restored = await client.post("/unmask", headers=gw, json={
            "org_id": org, "conversation_id": "conv-C", "response": correct})
        refused = await client.post("/unmask_arguments", headers=gw, json={
            "org_id": org, "conversation_id": "conv-Z", "arguments": [pieces]})
        mine = await client.post("/unmask_arguments", headers=gw, json={
            "org_id": org, "conversation_id": "conv-C", "arguments": [pieces]})

    back = restored.json()
    answer = back["response"]["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    check("каштановая" in answer.lower() and "77" in answer,
          "the dialogue that minted the address gets it back whole", answer)
    check(not back.get("residual_tokens")
          and restored.headers.get("X-Pseudex-Residual") is None,
          "…with NO residual: the alarm is about the substitute, not the answer",
          f"residual={back.get('residual_tokens')} "
          f"header={restored.headers.get('X-Pseudex-Residual')}")

    left = refused.json()
    stood = json.loads(left["arguments"][0])
    check(stood["house"] == house and stood["last_digits"] == tail,
          "a house and a digit tail asked from another dialogue are refused",
          f"{left['arguments'][0]}")
    check(sorted(left.get("residual_tokens") or []) == sorted({house, tail}),
          "…and BOTH are named in residual_tokens — no class refuses in silence",
          f"residual={left.get('residual_tokens')} expected={sorted({house, tail})}")

    ours = json.loads(mine.json()["arguments"][0])
    check(ours["house"] == "77" and ours["last_digits"] == "6789"
          and not mine.json().get("residual_tokens"),
          "…while the dialogue that minted them still gets the real values",
          f"{mine.json()}")


def test_signal_names_every_refused_fragment() -> None:
    import anyio
    try:
        anyio.run(_signal_names_every_refused_fragment)
    finally:
        service._BOUND_ORG = ""


async def _proxy_leg_calls() -> None:
    """THE PROXY'S WAY BACK IS SCOPED TOO, AND BY ITS OWN TRANSCRIPT.

    This shape names no conversation on the wire at all — it derives one from
    the messages (`conversation_key`) on the way in AND on the way back, so the
    two legs meet. That is what makes the narrowing bite here: a bare street
    minted under one transcript is not read under another, the fake stays where
    it stood, and the caller learns about it from `X-Pseudex-Residual`, which
    is the only channel an OpenAI-shaped answer leaves for it.

    AND THE DECLARED PSEUDONYM SCOPE REACHES THIS LEG TOO. This shape carries
    no body field for it — the envelope is OpenAI's — so the declaration is
    `PSEUDEX_PSEUDONYM_SCOPE`, and it used to be read on the way IN only: a
    customer who set it got account-wide minting and conversation-scoped
    restoring. The last check is the same call under the same stub with the
    setting on.

    The upstream is a stub: what is under test is the pair of legs around it,
    not the provider.
    """
    from pseudex import proxy  # noqa: PLC0415

    key = "sk-ps-test-proxy-scope"
    proxy.TENANTS.upsert(key, "proxy-scope-org", "http://upstream.invalid/v1", "up-key")
    # A BARE STREET minted under transcript A, through the proxy's own masking
    # leg — so the conversation it lands under is the one the proxy derives.
    said = "подъезжаем на набережную Ольгина"
    first = [{"role": "user", "content": said}]
    minting = proxy._get_vault("proxy-scope-org").for_conversation(
        proxy.conversation_key(first))
    fake = mask_text(said, minting, Detector().detect(said)).split("набережную", 1)[1].strip()

    async def _stub(body, tenant):
        return {"choices": [{"message": {"role": "assistant", "content": None,
                                         "tool_calls": [{"id": "1", "type": "function",
                                                         "function": {"name": "dispatch",
                                                                      "arguments": json.dumps(
                                                                          {"street": fake},
                                                                          ensure_ascii=False)}}]}}]}

    class _Serving:
        def is_serving(self):
            return True

    saved = (proxy._forward, proxy.LICENSE, proxy.metering.bill)
    proxy._forward, proxy.LICENSE = _stub, _Serving()
    proxy.metering.bill = lambda *args, **kwargs: None
    try:
        transport = httpx.ASGITransport(app=proxy.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            headers = {"Authorization": f"Bearer {key}"}
            # ANOTHER transcript — another derived conversation.
            other = await client.post("/v1/chat/completions", headers=headers, json={
                "messages": [{"role": "user", "content": "а куда ехать, напомни"}],
                "tools": [{"type": "function", "function": {"name": "dispatch"}}]})
            same = await client.post("/v1/chat/completions", headers=headers,
                                     json={"messages": first, "tools": [
                                         {"type": "function",
                                          "function": {"name": "dispatch"}}]})
            proxy._PSEUDONYM_SCOPE = "customer"
            declared = await client.post("/v1/chat/completions", headers=headers, json={
                "messages": [{"role": "user", "content": "а куда ехать, напомни"}],
                "tools": [{"type": "function", "function": {"name": "dispatch"}}]})
    finally:
        proxy._forward, proxy.LICENSE, proxy.metering.bill = saved
        proxy._PSEUDONYM_SCOPE = "conversation"

    theirs = other.json()["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    check("Ольгина" not in theirs and fake in theirs,
          "proxy: another transcript does not get this one's real street",
          f"{theirs} status={other.status_code}")
    check(other.headers.get("X-Pseudex-Residual") == "1",
          "…and the proxy says so in X-Pseudex-Residual",
          f"{other.headers.get('X-Pseudex-Residual')}")
    ours = same.json()["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    check("Ольгина" in ours and "X-Pseudex-Residual" not in same.headers,
          "…while the transcript that minted it still gets the real street",
          f"{ours} residual={same.headers.get('X-Pseudex-Residual')}")
    memory = declared.json()["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    check("Ольгина" in memory and "X-Pseudex-Residual" not in declared.headers,
          "…and a host that declared agent memory gets it on the proxy's way back",
          f"{memory} residual={declared.headers.get('X-Pseudex-Residual')}")


def test_proxy_response_leg_is_scoped() -> None:
    import anyio
    anyio.run(_proxy_leg_calls)


def test_name_trawl_visible() -> None:
    """WS-7 exfiltrator #2: a NAME/VALUE-guess sweep resolves nothing AND leaves no
    residual, so `miss_rate` stays 0.0 and the trawl used to hide. It now shows as
    `unproductive` calls (resolved nothing) — the sweep signal that catches BOTH a
    token-guess (high miss_rate) and a name-guess (miss_rate 0) trawl."""
    legit_org, trawl_org = "trawl-legit", "trawl-sweep"
    for _ in range(10):
        service.AUDIT.record_detok(legit_org, "gateway", resolved=3, misses=0)
    for _ in range(200):
        service.AUDIT.record_detok(trawl_org, "gateway", resolved=0, misses=0)  # guessed non-tokens
    legit = service.AUDIT.detok_summary(legit_org, 0)
    trawl = service.AUDIT.detok_summary(trawl_org, 0)
    check(legit["unproductive"] == 0
          and trawl["unproductive"] == 200 and trawl["unproductive_rate"] == 1.0
          and trawl["miss_rate"] == 0.0,
          "name-trawl (miss_rate=0) is visible as unproductive calls",
          f"legit_unprod={legit['unproductive']} trawl_unprod={trawl['unproductive']} "
          f"trawl_miss_rate={trawl['miss_rate']}")


def main() -> None:
    test_preview_narrowed()
    test_record_detok_counts_only()
    test_rate_limit()
    test_rate_limit_by_values()
    test_detok_counts_values_not_calls()
    test_app_org_bind_and_audit()
    test_unmask_chunk_audited_and_limited()
    test_unnamed_conversation_is_not_every_conversation()
    test_restoring_leg_takes_the_declared_scope()
    test_proxy_response_leg_is_scoped()
    test_signal_names_every_refused_fragment()
    test_name_trawl_visible()
    failed = [n for ok, n, _ in RESULTS if not ok]
    print("=" * 60)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("detok hardening not in place:", failed)
        raise SystemExit(1)
    print("detok: /unmask* audited + org-bound + rate-limited; preview narrowed.")


if __name__ == "__main__":
    main()
