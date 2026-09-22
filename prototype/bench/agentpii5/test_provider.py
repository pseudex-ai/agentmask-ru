"""The provider layer, the HTTP gateway and the answer cache — offline, on a scripted transport.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_provider

ТЗ `docs/tz-bench-harness.md` §4, items 12, 13 and 14. Every check here is one
a revert makes red:

  * the prices are WRITTEN (item 12) — delete a row of `PRICES` and
    `prices_cover_the_declared_models` names the model nobody can charge for;
  * an unknown model is «цена неизвестна», never «бесплатно» — return 0.0 from
    `estimate_usd` instead of raising and `unpriced_is_unknown_not_free` goes red;
  * the keys never leave the environment — put one into `provider_block` and
    `keys_stay_in_the_environment` finds it, because the fake key is a string no
    other part of the record can contain;
  * `--gateway` is the client's own path (item 13) — the probe reads the running
    engine's version, and a refusal leaves it UNKNOWN instead of borrowing the
    tree's;
  * the cache never substitutes a live call (item 14) — make `recording` serve a
    hit and `cache_never_substitutes_a_live_call` goes red on the call counter.

NOTHING HERE TOUCHES A NETWORK OR A KEY. `scripted_transport` answers from a
table and records what it was asked, so both halves of a provider shape — the
request this module builds and the answer it reads — are checked without a
socket. The «key» below is a literal that exists only in this file.
"""
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii5 import contracts
from bench.agentpii5.contracts import AGENT_MODEL, JUDGE_MODEL
from bench.agentpii5.observe import observe
from bench.agentpii5.provider import (
    ADMIN_TOKEN_ENV,
    GATEWAY_TOKEN_ENV,
    PRICES,
    PROVIDER_ENV,
    PROVIDER_TABLE,
    AnswerCache,
    CacheMiss,
    HttpGateway,
    ModelAnswer,
    ProviderError,
    _auth_headers,
    answer_key,
    call_model,
    call_url,
    credential_names,
    credential_present,
    estimate_usd,
    gateway_block,
    model_block,
    parse_gateway,
    probe_gateway,
    provider_block,
    recording,
    replaying,
    replies_of_run,
    resolve_model,
    resolve_provider,
    run_block,
    scripted_transport,
    strip_userinfo,
)
from bench.agentpii5.records import arm_v5_from_record, merged_v5_records
from bench.agentpii5.report import v5_cases
from bench.agentpii5.test_report import RUN_ID, build_run

# A string that occurs nowhere else in the repository, so «is the key in this
# record» is a substring question with no false positives.
FAKE_KEY = "sk-ant-TESTKEY-4f0b9c1e-do-not-ship"
GATEWAY_URL = "http://engine.local:8000"


def _env(extra: dict[str, str]) -> dict[str, str]:
    """An environment with EVERY declared credential name carrying the same fake
    key: the leak test must not depend on which provider the code happened to
    pick."""
    env = {name: FAKE_KEY for provider in PROVIDER_TABLE.values()
           for name in provider.key_env}
    env["AGENTPII5_LOCAL_BASE_URL"] = "http://localhost:8000"
    env.update(extra)
    return env


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_provider_is_chosen_by_flag_then_environment() -> list[str]:
    """ТЗ §4.1: «выбор — флагом и переменной окружения». The flag wins, because
    a shell that has carried another provider since last week must not redirect
    a run the operator spelled out."""
    problems: list[str] = []
    if resolve_provider("", _env({})).name != "anthropic":
        problems.append("the default provider is not anthropic")
    if resolve_provider("", _env({PROVIDER_ENV: "openrouter"})).name != "openrouter":
        problems.append("the environment does not choose the provider")
    if resolve_provider("local", _env({PROVIDER_ENV: "openrouter"})).name != "local":
        problems.append("the environment beat the flag")
    try:
        resolve_provider("gpt", _env({}))
        problems.append("an unknown provider was accepted")
    except ProviderError as refused:
        if "gpt" not in str(refused) or "anthropic" not in str(refused):
            problems.append(f"the refusal names neither the value nor the choices: {refused}")
    return problems


def test_prices_cover_the_declared_models() -> list[str]:
    """Item 12: the exact ids and the per-million prices are WRITTEN into the
    record. Both models `contracts` declares must resolve to a price, or the
    benchmark's own run cannot be costed."""
    provider = PROVIDER_TABLE["anthropic"]
    problems: list[str] = []
    for role, model in (("agent", AGENT_MODEL), ("judge", JUDGE_MODEL)):
        choice = resolve_model(provider, role, model)
        if choice.price is None:
            problems.append(f"{role}: {model} has no price — {choice.unpriced_reason}")
            continue
        block = model_block(choice)
        priced = block["price"]
        if not isinstance(priced, dict):
            problems.append(f"{role}: the record carries no price object")
            continue
        for field in ("input_usd_per_mtok", "output_usd_per_mtok", "as_of", "source"):
            if not priced.get(field):
                problems.append(f"{role}: the price record has no {field}")
        if block["model_id"] != model:
            problems.append(f"{role}: the record rewrote the model id to {block['model_id']!r}")
    # The other side: the table is not empty and every row prices something.
    if not PRICES:
        problems.append("the price table is empty")
    for row in PRICES:
        if row.price.input_usd_per_mtok <= 0 or row.price.output_usd_per_mtok <= 0:
            problems.append(f"{row.provider}/{row.model_id}: a non-positive price")
        if not row.as_of or not row.source:
            problems.append(f"{row.provider}/{row.model_id}: a price with no date or source")
    return problems


def test_unpriced_is_unknown_not_free() -> list[str]:
    """A model the table has not met costs «неизвестно». A zero would let a run
    start believing it is free, and every later estimate would inherit it."""
    choice = resolve_model(PROVIDER_TABLE["local"], "agent", "qwen3-32b-instruct")
    problems: list[str] = []
    if choice.price is not None:
        problems.append("a model outside the table was priced anyway")
    if "PRICES" not in choice.unpriced_reason:
        problems.append(f"the reason does not say where to add the row: {choice.unpriced_reason!r}")
    try:
        estimate_usd(choice, 1000, 1000)
        problems.append("estimate_usd invented a total for an unpriced model")
    except ProviderError:
        pass
    # The other side, or «it raises» would pass on a function that always raises.
    priced = resolve_model(PROVIDER_TABLE["anthropic"], "agent", "claude-haiku-4-5")
    if abs(estimate_usd(priced, 1_000_000, 1_000_000) - 6.0) > 1e-9:
        problems.append("1M in + 1M out on $1/$5 is not $6")
    return problems


def test_keys_stay_in_the_environment() -> list[str]:
    """Item 12: «ключи — только из окружения, никогда в файлах прогона и никогда
    в логах». Every string this module produces for a record is searched for the
    key; the one place it legitimately appears is the header of a live call."""
    env = _env({})
    provider = resolve_provider("anthropic", env)
    choices = [resolve_model(provider, "agent", AGENT_MODEL),
               resolve_model(provider, "judge", JUDGE_MODEL)]
    target = parse_gateway(f"http://user:{FAKE_KEY}@engine.local:8000", "sha256:abc")
    produced = [json.dumps(run_block(provider, choices, target, env), ensure_ascii=False),
                json.dumps(provider_block(provider, choices, env), ensure_ascii=False),
                json.dumps(gateway_block(target), ensure_ascii=False),
                json.dumps([model_block(one) for one in choices], ensure_ascii=False),
                call_url(provider, env)]
    problems: list[str] = [f"the key reached a record: {one[:120]!r}"
                           for one in produced if FAKE_KEY in one]
    # A refusal must not quote the key either — the leak nobody would look for.
    try:
        HttpGateway(GATEWAY_URL, "org", GATEWAY_TOKEN_ENV, ADMIN_TOKEN_ENV, {},
                    scripted_transport({}, [])).spans(["привет"])
        problems.append("a gateway with no token was allowed to call")
    except ProviderError as refused:
        if GATEWAY_TOKEN_ENV not in str(refused):
            problems.append(f"the refusal does not name the variable: {refused}")
        if FAKE_KEY in str(refused):
            problems.append("the refusal quoted the key")
    # The other half: the environment really does carry it, or every assertion
    # above would pass on an empty environment.
    if not credential_present(provider, env):
        problems.append("the fixture environment carries no credential — the test is vacuous")
    if FAKE_KEY not in json.dumps(_auth_headers(provider, env)):
        problems.append("the one place a key may appear does not carry it")
    if credential_names(provider) != provider.key_env:
        problems.append("credential_names does not report the declared names")
    return problems


def test_scripted_transport_per_provider_shape() -> list[str]:
    """Both shapes, request and response. A canned answer alone would leave the
    request unchecked, which is the half that decides WHICH model answered."""
    problems: list[str] = []
    env = _env({})

    messages_env = env
    provider = PROVIDER_TABLE["anthropic"]
    choice = resolve_model(provider, "agent", "claude-haiku-4-5")
    seen: list[tuple[str, str, dict[str, object] | None]] = []
    url = call_url(provider, messages_env)
    transport = scripted_transport({("POST", url): (200, {
        "model": "claude-haiku-4-5", "content": [{"type": "text", "text": "готово"}],
        "usage": {"input_tokens": 1000, "output_tokens": 2000}})}, seen)
    answer = call_model(provider, choice, "вопрос", "система", messages_env, transport)
    if answer.text != "готово":
        problems.append(f"Messages: the text was not read: {answer.text!r}")
    if abs(answer.cost_usd - (1000 * 1.0 + 2000 * 5.0) / 1_000_000) > 1e-12:
        problems.append(f"Messages: the cost was not computed from the price: {answer.cost_usd}")
    body = seen[0][2]
    if not isinstance(body, dict) or body.get("model") != "claude-haiku-4-5":
        problems.append(f"Messages: the request does not name the model: {body}")
    if isinstance(body, dict) and body.get("system") != "система":
        problems.append("Messages: the system prompt was dropped")

    chat_provider = PROVIDER_TABLE["openrouter"]
    chat_choice = resolve_model(chat_provider, "judge", "claude-sonnet-5")
    chat_seen: list[tuple[str, str, dict[str, object] | None]] = []
    chat_url = call_url(chat_provider, env)
    chat = scripted_transport({("POST", chat_url): (200, {
        "model": "anthropic/claude-sonnet-5",
        "choices": [{"message": {"role": "assistant", "content": "верно"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20}})}, chat_seen)
    chat_answer = call_model(chat_provider, chat_choice, "вопрос", "", env, chat)
    if chat_answer.text != "верно":
        problems.append(f"chat: the text was not read: {chat_answer.text!r}")
    if chat_answer.model_reported != "anthropic/claude-sonnet-5":
        problems.append("chat: the provider's own model id was not recorded")
    chat_body = chat_seen[0][2]
    if not isinstance(chat_body, dict) or chat_body.get("messages") != [
            {"role": "user", "content": "вопрос"}]:
        problems.append(f"chat: the request body is wrong: {chat_body}")
    if "openrouter" not in chat_url or not chat_url.endswith("/v1/chat/completions"):
        problems.append(f"chat: the url is not the OpenAI-compatible one: {chat_url}")

    # A non-2xx must carry the status AND the body, or the four ways this fails
    # are one message.
    broken = scripted_transport({("POST", url): (429, {"error": {"message": "rate limit"}})}, [])
    try:
        call_model(provider, choice, "вопрос", "", messages_env, broken)
        problems.append("a 429 was read as an answer")
    except ProviderError as refused:
        if "429" not in str(refused) or "rate limit" not in str(refused):
            problems.append(f"the refusal loses the status or the body: {refused}")
    return problems


def test_gateway_is_the_clients_own_path() -> list[str]:
    """Item 13. Empty is the in-process path; an address is the customer's own
    path and the engine itself says which version is listening."""
    problems: list[str] = []
    here = parse_gateway("", "")
    if here.mode != "inprocess" or here.base_url:
        problems.append(f"an empty --gateway is not the in-process path: {here}")
    try:
        parse_gateway("engine.local:8000", "")
        problems.append("a value with no scheme was accepted as a URL")
    except ProviderError as refused:
        if "engine.local:8000" not in str(refused):
            problems.append(f"the refusal does not name the value: {refused}")
    if strip_userinfo("http://u:p@host:8000/x") != "http://host:8000/x":
        problems.append("the credential was left in the URL")

    target = parse_gateway(GATEWAY_URL, "sha256:deadbeef")
    good = scripted_transport({("GET", f"{GATEWAY_URL}/status"): (200, {
        "engine": {"version": "0.3.18", "assets_loaded": True}})}, [])
    probed = probe_gateway(target, ADMIN_TOKEN_ENV, {ADMIN_TOKEN_ENV: FAKE_KEY}, good)
    if probed.engine_version != "0.3.18":
        problems.append(f"the running engine's version was not read: {probed}")
    if probed.image_digest != "sha256:deadbeef":
        problems.append("the image digest was lost")
    block = gateway_block(probed)
    if block["mode"] != "http" or block["engine_version"] != "0.3.18":
        problems.append(f"the record does not say what the gateway was: {block}")

    # A refusal leaves the version UNKNOWN. Borrowing the working tree's version
    # for a container that answered 401 is the one lie this field exists to
    # prevent — it would attribute a container's numbers to the source beside it.
    closed = scripted_transport({("GET", f"{GATEWAY_URL}/status"): (401, {"error": "no token"})}, [])
    blind = probe_gateway(target, ADMIN_TOKEN_ENV, {}, closed)
    if blind.engine_version:
        problems.append(f"a 401 produced a version anyway: {blind.engine_version!r}")
    if "401" not in blind.learned_from or ADMIN_TOKEN_ENV not in blind.learned_from:
        problems.append(f"the record does not say why the version is unknown: {blind.learned_from!r}")
    if gateway_block(blind)["engine_version"] is not None:
        problems.append("an unknown version was written as something other than null")
    # An in-process target is never probed, however the transport would answer.
    if probe_gateway(here, ADMIN_TOKEN_ENV, {}, good) != here:
        problems.append("the in-process target was probed")
    return problems


def test_http_gateway_speaks_the_four_endpoints() -> list[str]:
    """The gateway arm's own surface, over HTTP, with the GATEWAY token — and
    `/status` with the ADMIN one, because the two surfaces are separate on
    purpose (`CLAUDE.md`, «two surfaces on the sidecar»)."""
    env = {GATEWAY_TOKEN_ENV: "gw-token", ADMIN_TOKEN_ENV: "admin-token"}
    seen: list[tuple[str, str, dict[str, object] | None]] = []
    transport = scripted_transport({
        ("POST", f"{GATEWAY_URL}/mask"): (200, {"messages": [{"role": "user", "content": "м"}],
                                                "tools": [{"name": "t"}]}),
        ("POST", f"{GATEWAY_URL}/unmask"): (200, {"response": "Иванова",
                                                  "residual_tokens": ["Пахомова"]}),
        ("POST", f"{GATEWAY_URL}/unmask_arguments"): (200, {"arguments": ["{\"a\": \"Иванова\"}"]}),
        ("POST", f"{GATEWAY_URL}/spans"): (200, {"results": [[{"start": 0, "end": 7}]]}),
        ("GET", f"{GATEWAY_URL}/status"): (200, {"engine": {"version": "0.3.18"}}),
    }, seen)
    client = HttpGateway(GATEWAY_URL, "agentpii5", GATEWAY_TOKEN_ENV, ADMIN_TOKEN_ENV,
                         env, transport)
    problems: list[str] = []
    masked, tools = client.mask([{"role": "user", "content": "Иванова"}], "conv", [{"name": "t"}])
    if not masked or tools is None:
        problems.append(f"/mask did not return both halves: {masked} {tools}")
    restored, residual = client.unmask("Пахомова", "conv")
    if restored != "Иванова" or residual != ("Пахомова",):
        problems.append(f"/unmask lost the restoration or the residue: {restored!r} {residual}")
    arguments, arg_residual = client.unmask_arguments(["{\"a\": \"Пахомова\"}"], "conv")
    if arguments != ("{\"a\": \"Иванова\"}",) or arg_residual != ():
        problems.append(f"/unmask_arguments is wrong: {arguments} {arg_residual}")
    if not client.spans(["Иванова"]):
        problems.append("/spans returned nothing")
    if str(client.status().get("engine", {}).get("version")) != "0.3.18":  # type: ignore[union-attr]
        problems.append("/status was not read")
    paths = [one[1].rsplit("/", 1)[-1] for one in seen]
    if paths != ["mask", "unmask", "unmask_arguments", "spans", "status"]:
        problems.append(f"the client called something else: {paths}")
    # The conversation must travel: without it the engine's scope rule is
    # decoration, and the round trip would resolve against another dialogue.
    mask_body = seen[0][2]
    if not isinstance(mask_body, dict) or mask_body.get("conversation_id") != "conv":
        problems.append(f"/mask was called without the conversation: {mask_body}")
    # `/status` under the GATEWAY token would undo the split; the client must
    # refuse when the ADMIN variable is unset even though the gateway one is.
    half = HttpGateway(GATEWAY_URL, "agentpii5", GATEWAY_TOKEN_ENV, ADMIN_TOKEN_ENV,
                       {GATEWAY_TOKEN_ENV: "gw-token"}, transport)
    try:
        half.status()
        problems.append("/status was called without the admin token")
    except ProviderError as refused:
        if ADMIN_TOKEN_ENV not in str(refused):
            problems.append(f"the refusal does not name the admin variable: {refused}")
    return problems


def test_cache_key_carries_model_prompt_and_seed() -> list[str]:
    """Item 14: «ключ кеша включает модель, промпт и сид». Change any one of the
    three and the key must move, or a rubric edited by one word would be served
    the old rubric's verdicts for ever."""
    base = answer_key("m", "p", 0)
    problems: list[str] = []
    for label, other in (("model", answer_key("m2", "p", 0)),
                         ("prompt", answer_key("m", "p2", 0)),
                         ("seed", answer_key("m", "p", 1))):
        if other == base:
            problems.append(f"the key does not carry the {label}")
    if answer_key("m", "p", 0) != base:
        problems.append("the key is not stable for one input")
    try:
        answer_key("m", "p", -1)
        problems.append("a negative seed produced a key")
    except ProviderError:
        pass
    return problems


def test_cache_never_substitutes_a_live_call() -> list[str]:
    """Item 14's own rule: `recording` ALWAYS calls, `replaying` NEVER does.

    Two functions rather than a flag, and the counter is what proves it: a
    wrapper that served a hit would make one run's numbers depend on what
    another run happened to have asked, and the run would cost less than it
    measured."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        cache = AnswerCache(Path(tmp) / "answers")
        calls = [0]

        def live(prompt: str, seed: int) -> ModelAnswer:
            calls[0] += 1
            return ModelAnswer(text=f"ответ {prompt} {seed}", model_reported="m",
                               input_tokens=1, output_tokens=1, cost_usd=0.5)

        record = recording(live, cache, "m")
        first = record("вопрос", 3)
        second = record("вопрос", 3)
        if calls[0] != 2:
            problems.append(f"the recording path served a cached hit: {calls[0]} live calls")
        if first.text != second.text:
            problems.append("two live calls of one scripted model disagreed")
        if cache.count() != 1:
            problems.append(f"the cache holds {cache.count()} entries for one key")
        stored = cache.get("m", "вопрос", 3)
        if stored is None or stored.text != first.text:
            problems.append("what was recorded is not what came back")
        if stored is not None and stored.cost_usd != 0.5:
            problems.append("the cost was not recorded beside the answer")

        replay = replaying(cache, "m")
        before = calls[0]
        played = replay("вопрос", 3)
        if played.text != first.text:
            problems.append("--replay served something else")
        if calls[0] != before:
            problems.append("--replay reached the live call")
        try:
            replay("другой вопрос", 3)
            problems.append("--replay invented an answer for a key it does not hold")
        except CacheMiss as missed:
            if "--replay" not in str(missed) or "m" not in str(missed):
                problems.append(f"the miss names neither the flag nor the model: {missed}")
    return problems


def test_a_finished_run_rescores_with_no_call() -> list[str]:
    """The other half of item 14: everything a changed OBSERVER needs is already
    in `<run>.arms.v5.jsonl`, so a re-score touches no model at all.

    The check runs the OBSERVER over the stored arms — the work a changed
    observer would redo — and asserts hops come out. «No calls» proved by a
    counter alone would pass on a path that called nothing because it did
    nothing."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = build_run(Path(tmp), RUN_ID, True)
        replies = replies_of_run(run_dir)
        if not replies:
            problems.append("the run's own replies could not be read back")
        for key, turns in replies.items():
            if not turns:
                problems.append(f"{key}: an arm whose turns did not survive the write")
        if not any(arm == "I" for _case, _repeat, arm in replies):
            problems.append("the gateway arm is not among the replies")
        cases = v5_cases(run_dir)
        observed = 0
        for row in merged_v5_records(run_dir):
            run = arm_v5_from_record(row)
            case = cases.get(run.base.case_id)
            if case is None or run.base.arm != "I":
                continue
            observed += len(observe(case, run, None, None).hops)
        if not observed:
            problems.append("re-observing the stored arms produced no hop — a run that "
                            "cannot be re-scored offline is a run the cache cannot help")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("provider_is_chosen_by_flag_then_environment", test_provider_is_chosen_by_flag_then_environment),
        ("prices_cover_the_declared_models", test_prices_cover_the_declared_models),
        ("unpriced_is_unknown_not_free", test_unpriced_is_unknown_not_free),
        ("keys_stay_in_the_environment", test_keys_stay_in_the_environment),
        ("scripted_transport_per_provider_shape", test_scripted_transport_per_provider_shape),
        ("gateway_is_the_clients_own_path", test_gateway_is_the_clients_own_path),
        ("http_gateway_speaks_the_four_endpoints", test_http_gateway_speaks_the_four_endpoints),
        ("cache_key_carries_model_prompt_and_seed", test_cache_key_carries_model_prompt_and_seed),
        ("cache_never_substitutes_a_live_call", test_cache_never_substitutes_a_live_call),
        ("a_finished_run_rescores_with_no_call", test_a_finished_run_rescores_with_no_call),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("provider: PASS" if not failures else "provider: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
