"""AgentPII-RU v5 — ONE place that knows how a model is called, what it costs,
and what the gateway under test was (ТЗ `docs/tz-bench-harness.md` §4, items
12, 13, 14).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.provider --provider anthropic --agent claude-haiku-4-5

THREE THINGS LIVE HERE AND THEY ARE ONE THING. «Which model» decides the price,
the price decides the estimate, and the estimate decides whether a run may
start — so a second table of model ids somewhere else would be a second price,
and the two would disagree on the day one of them was updated. The run then
records BOTH: the exact id that went on the wire and the per-million price it
was billed at (§4.1), because a number nobody can reprice is a number nobody
can compare a year later.

KEYS ARE READ FOR PRESENCE AND NEVER FOR CONTENT. Every function here takes the
environment as a `Mapping` and returns the NAMES of the variables it wants; the
only place a value is touched is `_auth_headers`, which builds a header for one
live call and hands it to the transport. Nothing in this module puts an
environment value into a record, a log line or an exception — `test_provider`
plants a distinctive fake key and demands its absence from every string the
module produces. A refusal that quoted the key to explain itself would be the
one leak nobody would look for.

THE TRANSPORT IS A PARAMETER, WHICH IS WHY THIS FILE HAS NO NETWORK. `Transport`
is one HTTP round trip as a callable; `urllib_transport` builds the real one and
`scripted_transport` builds the one the tests drive. A provider shape (the
Anthropic Messages body, the OpenAI-compatible chat body) is then a pure
function from a prompt to a request and from a response to a `ModelAnswer`, and
both halves are exercised offline.

THE CACHE (item 14) NEVER SUBSTITUTES A LIVE CALL. `recording` always calls the
model and writes what came back; `replaying` never calls and raises `CacheMiss`
naming the key. Two functions rather than one flag, because a boolean that
decides whether money is spent is a boolean somebody flips by accident — and
the whole point of the cache is to re-score a finished run, not to make a run
look cheaper than it was.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from bench.agentpii5 import records
from bench.agentpii5.contracts import AGENT_MODEL, JUDGE_MODEL


class ProviderError(ValueError):
    """Anything this module refuses to guess: an unknown provider, a model with
    no declared price, a gateway URL that is not one, a cache miss under
    `--replay`. The message names the value and what would make it work — never
    a credential."""


# --- §4.1 the providers ------------------------------------------------------------------

PROVIDERS: tuple[str, ...] = ("anthropic", "openrouter", "local")
# The flag's environment twin (ТЗ §4.1 «выбор — флагом и переменной окружения»).
# The flag wins when both are set: a shell that has carried `openrouter` since
# last week must not silently redirect a run the operator spelled out.
PROVIDER_ENV: str = "AGENTPII5_PROVIDER"
GATEWAY_ENV: str = "AGENTPII5_GATEWAY"


@dataclass(frozen=True)
class Provider:
    """How one endpoint is spoken to. `key_env` are the NAMES of the variables
    that may carry the credential, in the order they are tried; `base_url_env`
    is the variable that may move the endpoint (a local model has no fixed
    host); `shape` picks the request builder and the response reader."""

    name: str
    base_url: str                    # the default endpoint, "" when the env must name it
    base_url_env: str
    key_env: tuple[str, ...]
    shape: str                       # "messages" (Anthropic) | "chat" (OpenAI-compatible)
    note: str


# THE ANTHROPIC ENTRY NAMES TWO VARIABLES ON PURPOSE. The SDK path the harness
# already uses resolves `ANTHROPIC_API_KEY` and then `ANTHROPIC_AUTH_TOKEN`
# (an OAuth profile is a third source this module cannot see), so a run driven
# through the provider layer and a run driven through the SDK must look for the
# same credential or «ключа нет» would mean two different things on two paths.
PROVIDER_TABLE: dict[str, Provider] = {
    "anthropic": Provider(
        name="anthropic", base_url="https://api.anthropic.com",
        base_url_env="ANTHROPIC_BASE_URL",
        key_env=("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
        shape="messages",
        note="первичный путь: тот же ключ, что берёт claude_agent_sdk в harness.py"),
    "openrouter": Provider(
        name="openrouter", base_url="https://openrouter.ai/api",
        base_url_env="OPENROUTER_BASE_URL", key_env=("OPENROUTER_API_KEY",),
        shape="chat",
        note="чужие модели под одной крышей; id провайдера входит в id модели"),
    "local": Provider(
        name="local", base_url="", base_url_env="AGENTPII5_LOCAL_BASE_URL",
        key_env=("AGENTPII5_LOCAL_API_KEY",), shape="chat",
        note="vLLM / llama.cpp / ollama — OpenAI-совместимый /v1/chat/completions"),
}
ANTHROPIC_VERSION: str = "2023-06-01"


def resolve_provider(flag: str, env: Mapping[str, str]) -> Provider:
    """The provider a run uses: the flag, else the environment, else the
    Anthropic path the benchmark was measured on.

    A name outside `PROVIDERS` is a refusal naming the three, never a silent
    fall-through to the default: a typo that quietly ran on another endpoint
    would produce numbers attributed to a model that never answered."""
    name = flag or env.get(PROVIDER_ENV, "") or "anthropic"
    if name not in PROVIDER_TABLE:
        raise ProviderError(
            f"провайдер {name!r} неизвестен: есть {', '.join(PROVIDERS)} "
            f"(флаг --provider или переменная {PROVIDER_ENV})")
    return PROVIDER_TABLE[name]


def base_url_of(provider: Provider, env: Mapping[str, str]) -> str:
    """The endpoint, with the environment allowed to move it. A `local`
    provider with nothing set is a refusal: there is no sensible default host
    for someone else's GPU, and «http://localhost:8000» guessed here would send
    a paid-looking run at whatever happens to listen there."""
    url = env.get(provider.base_url_env, "") or provider.base_url
    if not url:
        raise ProviderError(
            f"провайдер {provider.name!r} не знает адреса: задайте "
            f"{provider.base_url_env}=http://host:port")
    return url.rstrip("/")


def credential_names(provider: Provider) -> tuple[str, ...]:
    """The variable NAMES that may carry the credential. The manifest and the
    repro command print these; the values are never read outside
    `_auth_headers`."""
    return provider.key_env


def credential_present(provider: Provider, env: Mapping[str, str]) -> bool:
    """Whether ONE of the names carries something non-empty. A boolean rather
    than the name that matched: which variable a machine happens to use is the
    operator's business, and a manifest that named it would tell a reader where
    to look for the secret."""
    return any(env.get(name, "").strip() for name in provider.key_env)


# --- §4.1 the prices --------------------------------------------------------------------

@dataclass(frozen=True)
class Price:
    """USD per MILLION tokens, input and output.

    NO CACHE-READ OR CACHE-WRITE COLUMN, and the omission is deliberate: this
    table exists to be written into a run record, and a number invented here
    would be indistinguishable in that record from one that was read off the
    price list. The two columns below are the ones `docs/tz-bench-harness.md`
    §4.1 asks for («цены за миллион токенов»)."""

    input_usd_per_mtok: float
    output_usd_per_mtok: float


@dataclass(frozen=True)
class PriceRow:
    """One (provider, model) price with its provenance. `as_of` and `source`
    travel into `meta.json` beside the number, because a price with no date is
    a price nobody can check against the day the run happened."""

    provider: str
    model_id: str
    price: Price
    as_of: str
    source: str


_ANTHROPIC_LIST: str = "прайс-лист Anthropic (skill claude-api, таблица моделей)"
# The two ids `contracts` declares, under BOTH spellings the tree uses.
# `contracts.AGENT_MODEL` carries a date suffix and `contracts.JUDGE_MODEL`
# does not; the table has to price whatever a past run actually sent, and a
# lookup that normalised the id would be a second opinion about which model
# answered. Listed, not computed — see `PRICE_ALIASES` for why that is not a
# `startswith`.
PRICES: tuple[PriceRow, ...] = (
    PriceRow('deepseek', 'deepseek-flash', Price(0.30, 1.20), '2026-09-26',
             'https://api-docs.deepseek.com/quick_start/pricing/ (peak-rate estimate)'),
    PriceRow("anthropic", "claude-haiku-4-5", Price(1.0, 5.0), "2026-06-24", _ANTHROPIC_LIST),
    PriceRow("anthropic", "claude-haiku-4-5-20251001", Price(1.0, 5.0), "2026-06-24",
             _ANTHROPIC_LIST),
    PriceRow("anthropic", "claude-sonnet-5", Price(2.0, 10.0), "2026-06-24", _ANTHROPIC_LIST),
    PriceRow("anthropic", "claude-sonnet-4-6", Price(3.0, 15.0), "2026-06-24", _ANTHROPIC_LIST),
    PriceRow("anthropic", "claude-opus-5", Price(5.0, 25.0), "2026-06-24", _ANTHROPIC_LIST),
)
# A PREFIX MATCH WAS REJECTED. «claude-haiku-4-5-20251001».startswith(«claude-haiku-4-5»)
# is true and so is «claude-sonnet-4-6-…».startswith(«claude-sonnet-4») — the
# day a cheaper or dearer dated snapshot ships, a prefix rule prices it off its
# ancestor and nobody notices, because the wrong price still looks like a price.
# Every id is spelled.
PRICE_BY_KEY: dict[tuple[str, str], PriceRow] = {
    (row.provider, row.model_id): row for row in PRICES}
DEEPSEEK_CACHED_USD_PER_MTOK: float = 0.006

MODEL_ROLES: tuple[str, ...] = ("agent", "judge")


@dataclass(frozen=True)
class ModelChoice:
    """One role's model, exactly as it goes on the wire, with the price it is
    billed at or the reason there is none.

    `price is None` is «цена неизвестна», never «бесплатно». A run may proceed
    on an unpriced model — that is the operator's call, and refusing would make
    the benchmark unable to measure a model the table has not met — but the
    record then SAYS so, and `estimate_usd` refuses to invent a total."""

    role: str
    provider: str
    model_id: str
    price: Price | None
    price_as_of: str
    price_source: str
    unpriced_reason: str


def resolve_model(provider: Provider, role: str, model_id: str) -> ModelChoice:
    """The choice for one role. `model_id` is passed through untouched: an id
    is the provider's word, and normalising it here would mean the record and
    the wire disagreed about which model answered."""
    if role not in MODEL_ROLES:
        raise ProviderError(f"роль {role!r} не из {MODEL_ROLES}")
    if not model_id.strip():
        raise ProviderError(f"роль {role!r} без идентификатора модели")
    row = PRICE_BY_KEY.get((provider.name, model_id))
    if row is None:
        return ModelChoice(
            role=role, provider=provider.name, model_id=model_id, price=None,
            price_as_of="", price_source="",
            unpriced_reason=f"цены на {provider.name}/{model_id} нет в таблице "
                            f"bench/agentpii5/provider.py::PRICES — допишите строку с датой "
                            f"и источником, иначе прогон нельзя оценить и нельзя переоценить")
    return ModelChoice(role=role, provider=provider.name, model_id=model_id, price=row.price,
                       price_as_of=row.as_of, price_source=row.source, unpriced_reason="")


def estimate_usd(choice: ModelChoice, input_tokens: int, output_tokens: int) -> float:
    """What that many tokens cost at the recorded price. Refuses on an unpriced
    model rather than returning 0.0 — a free-looking estimate is the one number
    that would let a run start believing it costs nothing."""
    if choice.price is None:
        raise ProviderError(f"{choice.role}: {choice.unpriced_reason}")
    if input_tokens < 0 or output_tokens < 0:
        raise ProviderError(f"{choice.role}: отрицательные токены "
                            f"({input_tokens}, {output_tokens})")
    return (input_tokens * choice.price.input_usd_per_mtok
            + output_tokens * choice.price.output_usd_per_mtok) / 1_000_000


def model_block(choice: ModelChoice) -> dict[str, object]:
    """One role's model as it is written into `meta.json` and `runs.json`
    (ТЗ §4.1). The price is a nested object with its own date and source, so a
    reader can tell «$1/MTok as of 2026-06-24» from «нет цены» without knowing
    this module."""
    priced: dict[str, object] | None = None if choice.price is None else {
        "input_usd_per_mtok": choice.price.input_usd_per_mtok,
        "output_usd_per_mtok": choice.price.output_usd_per_mtok,
        "as_of": choice.price_as_of, "source": choice.price_source}
    return {"role": choice.role, "provider": choice.provider, "model_id": choice.model_id,
            "price": priced, "unpriced_reason": choice.unpriced_reason}


def provider_block(provider: Provider, choices: Sequence[ModelChoice],
                   env: Mapping[str, str]) -> dict[str, object]:
    """The whole §4.1 record: which endpoint, which models at which prices, and
    WHICH VARIABLE NAMES the credential was looked for in.

    The names are in the record on purpose and the values never are: a run a
    colleague has to repeat needs to know what to export, and a record that
    carried the secret would make every run directory a credential store."""
    return {"provider": provider.name, "base_url": base_url_of(provider, env),
            "shape": provider.shape, "key_env": list(provider.key_env),
            "key_present": credential_present(provider, env),
            "models": [model_block(one) for one in choices]}


# --- the transport seam ------------------------------------------------------------------

class Transport(Protocol):
    """One HTTP round trip. A PARAMETER everywhere, which is what keeps this
    module runnable with no network: `scripted_transport` answers from a table
    and `urllib_transport` does the real thing."""

    def __call__(self, method: str, url: str, body: dict[str, object] | None,
                 headers: Mapping[str, str]) -> tuple[int, dict[str, object]]: ...


def urllib_transport(timeout_s: float) -> Transport:
    """The real round trip, on the standard library.

    `urllib` rather than `httpx`: this module must be importable by a test that
    installs nothing, and the one thing it does with a socket is POST JSON. A
    non-2xx answer is RETURNED with its body, never raised — the caller decides
    whether a 429 is fatal, and an exception here would lose the body that says
    which of the four things went wrong."""
    def send(method: str, url: str, body: dict[str, object] | None,
             headers: Mapping[str, str]) -> tuple[int, dict[str, object]]:
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url=url, data=payload, method=method,
                                         headers={**dict(headers), "content-type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as answer:
                return int(answer.status), _as_object(answer.read().decode("utf-8"))
        except urllib.error.HTTPError as failed:
            return int(failed.code), _as_object(failed.read().decode("utf-8"))
    return send


def _as_object(raw: str) -> dict[str, object]:
    """A JSON object, or the body under `_raw` when it is not one. A gateway
    behind a proxy answers HTML on a bad path, and a reader that raised here
    would report «не JSON» without the page that says «502 Bad Gateway»."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}
    if not isinstance(parsed, dict):
        return {"_raw": raw}
    return {str(key): value for key, value in parsed.items()}


def scripted_transport(script: Mapping[tuple[str, str], tuple[int, dict[str, object]]],
                       seen: list[tuple[str, str, dict[str, object] | None]]) -> Transport:
    """A transport that answers from a table and RECORDS what it was asked.

    `seen` is the caller's list, so a test can assert on the request body — the
    half of a provider shape that a canned response cannot check. An unscripted
    (method, url) raises rather than answering 404: a test that silently got a
    404 would be testing the error path it did not mean to."""
    def send(method: str, url: str, body: dict[str, object] | None,
             headers: Mapping[str, str]) -> tuple[int, dict[str, object]]:
        del headers      # deliberately unread: a scripted transport must not need the key
        seen.append((method, url, body))
        answer = script.get((method, url))
        if answer is None:
            raise ProviderError(f"сценарий не знает {method} {url}; есть "
                                f"{sorted(f'{one[0]} {one[1]}' for one in script)}")
        return answer
    return send


# --- calling a model ---------------------------------------------------------------------

@dataclass(frozen=True)
class ModelAnswer:
    """What one call produced. `cost_usd` is COMPUTED from the recorded price
    and the reported tokens — this path has no `total_cost_usd` the way the
    Claude Code SDK does, and a cost the provider did not state is better
    derived from a price the record carries than left at zero."""

    text: str
    model_reported: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


MAX_TOKENS: int = 4096


def _auth_headers(provider: Provider, env: Mapping[str, str]) -> dict[str, str]:
    """The ONE place an environment value is read. The value goes straight into
    a header for one call; it is never returned, never logged and never put in
    a record. A missing credential is a refusal naming the VARIABLES, not the
    value that is missing from them."""
    for name in provider.key_env:
        value = env.get(name, "").strip()
        if value:
            if provider.shape == "messages":
                return {"x-api-key": value, "anthropic-version": ANTHROPIC_VERSION}
            return {"authorization": f"Bearer {value}"}
    if provider.name == "local":
        # A model on the operator's own machine usually wants no credential at
        # all, and demanding one would make the local path unusable. Every other
        # provider refuses: an unauthenticated call to a paid endpoint is a 401
        # that costs a minute and reads like an outage.
        return {}
    raise ProviderError(f"провайдер {provider.name!r}: ни одна из переменных "
                        f"{', '.join(provider.key_env)} не задана")


def _messages_request(choice: ModelChoice, prompt: str, system: str) -> dict[str, object]:
    """The Anthropic Messages body. `temperature` is NOT sent: the judge's own
    transport cannot set it (R-56) and a second path that could would produce
    verdicts at a temperature no calibration stamp certifies."""
    body: dict[str, object] = {"model": choice.model_id, "max_tokens": MAX_TOKENS,
                               "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    return body


def _chat_request(choice: ModelChoice, prompt: str, system: str) -> dict[str, object]:
    """The OpenAI-compatible body OpenRouter and every local server speak."""
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return {"model": choice.model_id, "max_tokens": MAX_TOKENS, "messages": messages}


def _messages_answer(choice: ModelChoice, body: dict[str, object]) -> ModelAnswer:
    blocks = body.get("content")
    if not isinstance(blocks, list):
        raise ProviderError(f"ответ Messages без content: {sorted(body)}")
    text = "".join(str(one.get("text", "")) for one in blocks
                   if isinstance(one, dict) and one.get("type") == "text")
    usage = body.get("usage")
    used = usage if isinstance(usage, dict) else {}
    ins = int(used.get("input_tokens", 0) or 0)
    outs = int(used.get("output_tokens", 0) or 0)
    return ModelAnswer(text=text, model_reported=str(body.get("model", choice.model_id)),
                       input_tokens=ins, output_tokens=outs,
                       cost_usd=0.0 if choice.price is None else estimate_usd(choice, ins, outs))


def _chat_answer(choice: ModelChoice, body: dict[str, object]) -> ModelAnswer:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError(f"ответ chat/completions без choices: {sorted(body)}")
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    text = str(message.get("content", "")) if isinstance(message, dict) else ""
    usage = body.get("usage")
    used = usage if isinstance(usage, dict) else {}
    ins = int(used.get("prompt_tokens", 0) or 0)
    outs = int(used.get("completion_tokens", 0) or 0)
    return ModelAnswer(text=text, model_reported=str(body.get("model", choice.model_id)),
                       input_tokens=ins, output_tokens=outs,
                       cost_usd=0.0 if choice.price is None else estimate_usd(choice, ins, outs))


def call_url(provider: Provider, env: Mapping[str, str]) -> str:
    """Where a call goes, per shape. Declared here so the manifest and the call
    cannot disagree about the path a run used."""
    base = base_url_of(provider, env)
    return f"{base}/v1/messages" if provider.shape == "messages" else f"{base}/v1/chat/completions"


def call_model(provider: Provider, choice: ModelChoice, prompt: str, system: str,
               env: Mapping[str, str], transport: Transport) -> ModelAnswer:
    """One call, through whichever shape the provider speaks.

    A non-2xx is a refusal carrying the STATUS and the provider's own body: the
    four ways this fails (no key, no credit, rate limit, wrong model id) are
    indistinguishable without it, and a run that stopped on «HTTP 400» has told
    the operator nothing."""
    url = call_url(provider, env)
    body = (_messages_request(choice, prompt, system) if provider.shape == "messages"
            else _chat_request(choice, prompt, system))
    status, answer = transport("POST", url, body, _auth_headers(provider, env))
    if status // 100 != 2:
        raise ProviderError(f"{provider.name} {url} ответил {status}: "
                            f"{json.dumps(answer, ensure_ascii=False)[:400]}")
    return (_messages_answer(choice, answer) if provider.shape == "messages"
            else _chat_answer(choice, answer))


# --- §4.3 the model-answer cache (item 14) ------------------------------------------------

CACHE_VERSION: int = 1
# OUTSIDE THE REPOSITORY AND OUTSIDE `/tmp`, for the reason `CLAUDE.md` states
# about the external corpora: `/tmp` is cleared on reboot (NEREL was lost that
# way twice) and a cache inside the tree would make the working tree dirty on
# every run, which §6.1 turns into a refusal to start.
DEFAULT_CACHE_DIR: Path = Path.home() / ".cache" / "pseudex-bench" / "agentpii5-answers"


class CacheMiss(ProviderError):
    """`--replay` asked for an answer the cache does not hold. Its own class
    because the caller's choice is different from every other refusal here:
    re-run that case live, or accept that this run cannot be re-scored."""


def answer_key(model: str, prompt: str, seed: int) -> str:
    """The cache key: model, prompt and seed, hashed with a version and a
    separator that cannot occur in any of them.

    THE PROMPT IS PART OF THE KEY, NOT A LABEL BESIDE IT. A judge rubric that
    changed by one word is another instrument (`calibration_problems` refuses a
    stamp over another prompt for the same reason), and a cache keyed on the
    model alone would serve the old rubric's verdicts to the new one for ever.
    """
    if seed < 0:
        raise ProviderError(f"сид {seed} отрицательный: ключ кеша должен быть воспроизводим")
    raw = f"{CACHE_VERSION}\x1f{model}\x1f{seed}\x1f{prompt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CachedAnswer:
    """One stored answer. `prompt_sha256` is kept beside the key so a human
    reading the directory can tell two entries of one model apart without the
    prompt itself — the prompt may carry the customer's masked dialogue, and a
    cache directory is not a place to keep a copy of it."""

    key: str
    model: str
    seed: int
    prompt_sha256: str
    text: str
    cost_usd: float
    written_at: str


class AnswerCache:
    """The stored answers of past calls, one JSON file per key.

    A class because it is a connector to external state (a directory two
    processes may share), which is the one case `CLAUDE.md` keeps classes for.
    One file per key rather than one appended log: a re-score reads a handful of
    keys out of tens of thousands, and a log would have to be parsed whole to
    answer «есть ли этот ответ»."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def _path(self, key: str) -> Path:
        # Two levels of fan-out: a single directory with 40 000 entries is slow
        # to list on every filesystem this runs on, and the operator does list it.
        return self._root / key[:2] / f"{key}.json"

    def get(self, model: str, prompt: str, seed: int) -> CachedAnswer | None:
        key = answer_key(model, prompt, seed)
        path = self._path(key)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ProviderError(f"{path}: в кеше не объект, а {type(raw).__name__}")
        return CachedAnswer(key=str(raw["key"]), model=str(raw["model"]), seed=int(raw["seed"]),
                            prompt_sha256=str(raw["prompt_sha256"]), text=str(raw["text"]),
                            cost_usd=float(raw["cost_usd"]), written_at=str(raw["written_at"]))

    def put(self, model: str, prompt: str, seed: int, text: str,
            cost_usd: float) -> CachedAnswer:
        key = answer_key(model, prompt, seed)
        entry = CachedAnswer(key=key, model=model, seed=seed,
                             prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                             text=text, cost_usd=round(cost_usd, 6),
                             written_at=datetime.now(timezone.utc).isoformat())
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"key": entry.key, "model": entry.model, "seed": entry.seed,
             "prompt_sha256": entry.prompt_sha256, "text": entry.text,
             "cost_usd": entry.cost_usd, "written_at": entry.written_at},
            ensure_ascii=False, indent=2), encoding="utf-8")
        return entry

    def count(self) -> int:
        return sum(1 for _one in self._root.glob("*/*.json")) if self._root.exists() else 0


ModelCall = Callable[[str, int], ModelAnswer]


def recording(live: ModelCall, cache: AnswerCache, model: str) -> ModelCall:
    """The ordinary path: ALWAYS call, then write what came back.

    It does not read the cache, and that is the item's own rule («кеш никогда не
    подменяет живой вызов в обычном прогоне»). A wrapper that served a hit would
    make one run's numbers depend on what another run happened to have asked —
    and the saving would show up as a run that cost less than it measured."""
    def call(prompt: str, seed: int) -> ModelAnswer:
        answer = live(prompt, seed)
        cache.put(model, prompt, seed, answer.text, answer.cost_usd)
        return answer
    return call


def replaying(cache: AnswerCache, model: str) -> ModelCall:
    """`--replay`: serve from the cache and NEVER call. A miss raises with the
    key and the model, because the honest repair is to run that case live, not
    to substitute something plausible."""
    def call(prompt: str, seed: int) -> ModelAnswer:
        hit = cache.get(model, prompt, seed)
        if hit is None:
            raise CacheMiss(f"--replay: в кеше {cache.root} нет ответа "
                            f"{answer_key(model, prompt, seed)[:16]} "
                            f"(модель {model}, сид {seed}) — этот случай надо прогнать живьём")
        return ModelAnswer(text=hit.text, model_reported=model, input_tokens=0,
                           output_tokens=0, cost_usd=0.0)
    return call


def replies_of_run(run_dir: Path) -> dict[tuple[str, int, str], tuple[str, ...]]:
    """Every arm's own turn replies, off the run files — the proof that a
    finished run is re-scored without a single call.

    The other half of item 14 and the one that matters most: when the OBSERVER
    changes, the arms have to be rebuilt, and everything the observer reads is
    already in `<run>.arms.v5.jsonl`. Named here rather than left implicit so a
    test can drive a re-score with a transport that raises if it is touched."""
    out: dict[tuple[str, int, str], tuple[str, ...]] = {}
    for row in records.merged_v5_records(run_dir):
        run = records.arm_v5_from_record(row)
        out[(run.base.case_id, run.base.repeat, run.base.arm)] = run.turn_replies
    return out


# --- §4.2 the gateway under test (item 13) -----------------------------------------------

GATEWAY_MODES: tuple[str, ...] = ("inprocess", "http")
UNKNOWN: str = "неизвестно"


@dataclass(frozen=True)
class GatewayTarget:
    """What the gateway arm ran against, as `meta.json` records it (ТЗ §4.2).

    `engine_version` and `image_digest` are "" when nobody could say, and the
    record prints «неизвестно» rather than guessing: comparing 0.3.17 with
    0.3.18 is the whole point of the HTTP path, and a version invented from the
    working tree would attribute a container's numbers to the source beside
    it."""

    mode: str
    base_url: str
    engine_version: str
    image_digest: str
    learned_from: str


def strip_userinfo(url: str) -> str:
    """`http://user:secret@host:8000` → `http://host:8000`.

    A credential in a URL is still a credential, and this URL goes into
    `meta.json`, `runs.json` and the repro command. Stripped rather than
    refused: an operator who put a token in the URL should get a working run
    and a clean record, not a lecture at the start of a paid run."""
    parts = urllib.parse.urlsplit(url)
    if not parts.hostname:
        return url
    host = parts.hostname + (f":{parts.port}" if parts.port else "")
    return urllib.parse.urlunsplit((parts.scheme, host, parts.path, parts.query, ""))


def parse_gateway(value: str, image_digest: str) -> GatewayTarget:
    """`--gateway` into a target. Empty is the in-process path the benchmark has
    always used; anything else must be an http(s) URL, and a value that is not
    one is a refusal naming it — «localhost:8000» without a scheme would
    otherwise be read as a relative path and fail three steps later."""
    if not value.strip():
        return GatewayTarget(mode="inprocess", base_url="", engine_version="",
                             image_digest=image_digest, learned_from="")
    parts = urllib.parse.urlsplit(value.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ProviderError(
            f"--gateway {value!r} не адрес: нужен http://host:port или https://host "
            f"(пусто — шлюз в том же процессе, как раньше)")
    return GatewayTarget(mode="http", base_url=strip_userinfo(value.strip()).rstrip("/"),
                         engine_version="", image_digest=image_digest,
                         learned_from="")


def probe_gateway(target: GatewayTarget, admin_token_env: str, env: Mapping[str, str],
                  transport: Transport) -> GatewayTarget:
    """Ask a RUNNING engine what it is: `GET /status` → `engine.version`.

    The admin token, because `/status` is the operator surface and the gateway
    token deliberately cannot reach it (`CLAUDE.md`, «two surfaces on the
    sidecar»). A refusal or an answer without the field leaves `engine_version`
    empty and says WHERE that was learned — silence is «неизвестно», never
    «та же, что в дереве»."""
    if target.mode != "http":
        return target
    token = env.get(admin_token_env, "").strip()
    headers = {"authorization": f"Bearer {token}"} if token else {}
    url = f"{target.base_url}/status"
    status, body = transport("GET", url, None, headers)
    if status // 100 != 2:
        return GatewayTarget(mode=target.mode, base_url=target.base_url, engine_version="",
                             image_digest=target.image_digest,
                             learned_from=f"GET /status → {status}; версия {UNKNOWN}"
                                          + ("" if token else f" (нет {admin_token_env})"))
    engine = body.get("engine")
    version = str(engine.get("version", "")) if isinstance(engine, dict) else ""
    return GatewayTarget(mode=target.mode, base_url=target.base_url, engine_version=version,
                         image_digest=target.image_digest,
                         learned_from="GET /status" if version else
                         f"GET /status без engine.version; версия {UNKNOWN}")


def gateway_block(target: GatewayTarget) -> dict[str, object]:
    """The §4.2 record. Empty strings become `null`, so a reader cannot mistake
    «не спросили» for «пусто»."""
    return {"mode": target.mode,
            "base_url": target.base_url or None,
            "engine_version": target.engine_version or None,
            "image_digest": target.image_digest or None,
            "learned_from": target.learned_from or None}


class HttpGateway:
    """The customer's own path to a running engine: the sidecar's HTTP surface.

    A class for the same reason `Vault` is one — a connector to external state.
    It speaks exactly the four endpoints the gateway arm needs (`/mask`,
    `/unmask`, `/unmask_arguments`, `/spans`) with the GATEWAY token, and
    `/status` with the ADMIN one, because the two surfaces are separate on
    purpose and a client that held one credential for both would undo that.

    IT DOES NOT IMPORT `pseudex`, AND THAT IS THE POINT OF ITEM 13. The
    in-process gateway can only measure the source tree it was imported from;
    this one measures whatever is listening, which is how 0.3.17 and 0.3.18 are
    told apart."""

    def __init__(self, base_url: str, org_id: str, gateway_token_env: str,
                 admin_token_env: str, env: Mapping[str, str], transport: Transport) -> None:
        self._base = base_url.rstrip("/")
        self._org = org_id
        self._gateway_env = gateway_token_env
        self._admin_env = admin_token_env
        self._env = env
        self._send = transport

    def _headers(self, name: str) -> dict[str, str]:
        token = self._env.get(name, "").strip()
        if not token:
            raise ProviderError(f"шлюз по HTTP: переменная {name} не задана — "
                                f"без неё движок ответит 401")
        return {"authorization": f"Bearer {token}"}

    def _post(self, path: str, body: dict[str, object], env_name: str) -> dict[str, object]:
        url = f"{self._base}{path}"
        status, answer = self._send("POST", url, body, self._headers(env_name))
        if status // 100 != 2:
            raise ProviderError(f"шлюз {url} ответил {status}: "
                                f"{json.dumps(answer, ensure_ascii=False)[:400]}")
        return answer

    def mask(self, messages: Sequence[dict[str, object]], conversation_id: str,
             tools: Sequence[dict[str, object]] | None) -> tuple[list[object], list[object] | None]:
        body: dict[str, object] = {"org_id": self._org, "messages": list(messages),
                                   "conversation_id": conversation_id}
        if tools is not None:
            body["tools"] = list(tools)
        answer = self._post("/mask", body, self._gateway_env)
        masked = answer.get("messages")
        if not isinstance(masked, list):
            raise ProviderError(f"/mask вернул без messages: {sorted(answer)}")
        back = answer.get("tools")
        return masked, back if isinstance(back, list) else None

    def unmask(self, text: str, conversation_id: str) -> tuple[str, tuple[str, ...]]:
        answer = self._post("/unmask", {"org_id": self._org, "response": text,
                                        "conversation_id": conversation_id},
                            self._gateway_env)
        restored = answer.get("response")
        if not isinstance(restored, str):
            raise ProviderError(f"/unmask вернул без response: {sorted(answer)}")
        residual = answer.get("residual_tokens")
        return restored, tuple(str(one) for one in residual) if isinstance(residual, list) else ()

    def unmask_arguments(self, arguments: Sequence[str],
                         conversation_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """The tool-call leg, and it may NEVER go through `/unmask_chunk`: that
        endpoint substitutes flat text and «ООО "Заря"» put into a JSON string
        by plain replacement injects two bare quotes. The engine's own rule,
        restated here because this client is a second caller of it."""
        answer = self._post("/unmask_arguments",
                            {"org_id": self._org, "arguments": list(arguments),
                             "conversation_id": conversation_id}, self._gateway_env)
        restored = answer.get("arguments")
        if not isinstance(restored, list):
            raise ProviderError(f"/unmask_arguments вернул без arguments: {sorted(answer)}")
        residual = answer.get("residual_tokens")
        return (tuple(str(one) for one in restored),
                tuple(str(one) for one in residual) if isinstance(residual, list) else ())

    def spans(self, texts: Sequence[str]) -> list[object]:
        answer = self._post("/spans", {"org_id": self._org, "texts": list(texts)},
                            self._gateway_env)
        found = answer.get("results")
        if not isinstance(found, list):
            raise ProviderError(f"/spans вернул без results: {sorted(answer)}")
        return found

    def status(self) -> dict[str, object]:
        url = f"{self._base}/status"
        status, answer = self._send("GET", url, None, self._headers(self._admin_env))
        if status // 100 != 2:
            raise ProviderError(f"{url} ответил {status}: "
                                f"{json.dumps(answer, ensure_ascii=False)[:400]}")
        return answer


GATEWAY_TOKEN_ENV: str = "PSEUDEX_GATEWAY_TOKEN"
ADMIN_TOKEN_ENV: str = "PSEUDEX_ADMIN_TOKEN"


# --- what a run records about all of this -------------------------------------------------

def run_block(provider: Provider, choices: Sequence[ModelChoice], target: GatewayTarget,
              env: Mapping[str, str]) -> dict[str, object]:
    """The one object `meta.json` and `runs.json` both embed (§4.1, §4.2).

    ONE WRITER for the two files, because the registry row and the run's own
    meta are read side by side by `trend` and by `repro`, and two spellings of
    the same fact are one rename away from a trend that compares a model with
    itself under two names."""
    return {"provider": provider_block(provider, choices, env),
            "gateway": gateway_block(target)}


def main() -> int:
    """What a run WOULD record, printed without spending anything. The command
    an operator runs to check that a model id is priced before starting."""
    parser = argparse.ArgumentParser(description="провайдер, модели, цены, шлюз — без вызовов")
    parser.add_argument("--provider", default="")
    parser.add_argument("--agent", default=AGENT_MODEL)
    parser.add_argument("--judge", default=JUDGE_MODEL)
    parser.add_argument("--gateway", default="")
    parser.add_argument("--image-digest", default="")
    args = parser.parse_args()
    env = dict(os.environ)
    provider = resolve_provider(args.provider, env)
    choices = [resolve_model(provider, "agent", args.agent),
               resolve_model(provider, "judge", args.judge)]
    target = parse_gateway(args.gateway or env.get(GATEWAY_ENV, ""), args.image_digest)
    print(json.dumps(run_block(provider, choices, target, env),
                     ensure_ascii=False, indent=2, sort_keys=True))
    for one in choices:
        if one.price is None:
            print(f"ВНИМАНИЕ {one.role}: {one.unpriced_reason}", file=sys.stderr)
    return 0 if all(one.price is not None for one in choices) else 1


if __name__ == "__main__":
    raise SystemExit(main())
