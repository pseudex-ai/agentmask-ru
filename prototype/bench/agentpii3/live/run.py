"""ЖИВОЙ ПРОГОН AgentPII-RU v3: настоящий агент через шлюз, сверка с ЭТАЛОНОМ.

    python3 bench/agentpii3/live/run.py --tier nano --ceiling 3.00
    python3 bench/agentpii3/live/run.py --ids result-118,sid-0033 --ceiling 0.50
    python3 bench/agentpii3/live/run.py --report live/runs/<id>.jsonl   # без модели

ОДНО ПЛЕЧО, И ЭТО РЕШЕНИЕ, А НЕ ЭКОНОМИЯ. Прогоняется только маскированное
плечо, а сверка идёт с ЭТАЛОННЫМ вызовом корпуса. Ось «прозрачность» (плечо
против плеча) отменена владельцем: как модель пользуется инструментами — не
дело этого бенчмарка. Второго плеча здесь нет и не должно появиться ни под
каким именем.

ЧТО ЖИВОЙ ПРОГОН ДОБАВЛЯЕТ К `score.py`. Офлайн-счётчик принимает модель
ИДЕАЛЬНОЙ — она копирует то, что увидела, — и этим изолирует вклад шлюза. Здесь
вместо фикции стоит `claude-sonnet-4-6`, и три оси считаются по тому, что он
действительно сделал:

  ОСЬ 1 — детекция. Арифметика по спанам, судья не нужен. Считается ровно тем
      же `score._tally_detection`, что и офлайн: живой и офлайновый отчёт должны
      быть сравнимы построчно, а два счётчика одной величины расходятся всегда.
      Денominator НЕ зависит от модели — сообщения, до которых разговор не
      дошёл, домаскируются в конце (`flush`) и считаются, иначе «модель не
      вызвала инструмент» тихо улучшало бы полноту.

  ОСЬ 2 — против эталона. Инструменты берутся из `mask_tools`, аргументы
      возвращаются через `unmask_arguments` — производственный путь, не
      `unmask_chunk`. Разница с офлайном одна: `model_saw` — это то, что
      НАПИСАЛА МОДЕЛЬ, а не то, что она «увидела бы». Где модель вызова не
      сделала, это `call_absent` — поведение модели, и оно считается ОТДЕЛЬНО,
      а не портит долю шлюза.

  ОСЬ 3 — утечка в ответе. Здесь судья главный, и без него ось не считается.
      Ответ агента прогоняется через `unmask_text` и уходит в `judge.py`
      (claude-sonnet-5) двумя независимыми `query()`. Волт даёт факты
      (какие подмены уцелели), модель отвечает на то, чего строкой не достать:
      подмену пересказали, склонили, разбили на части.

ЖИВОЙ ПРОГОН ОТВЕЧАЕТ НА ВОПРОС, КОТОРОГО ОФЛАЙН НЕ ЗАДАЁТ. В ярусе nano у 18
случаев из 30 `final` пуст: офлайн для них ось 3 — `unjudged`, потому что
симулировать нечего. Живой агент всё равно пишет ответ, и волт всё равно знает
каждую отчеканенную подмену, так что вопрос «не выдал ли он подмену за
настоящее» задаётся и там.

АВТОРИЗАЦИЯ, проверено на этой машине и НЕ импровизируется:
  * подписка берётся из связки ключей macOS. `ANTHROPIC_API_KEY` и
    `CLAUDE_CODE_OAUTH_TOKEN` не выставляются.
  * `CLAUDE_CONFIG_DIR` НЕ задаётся: пустой конфиг герметичен и не содержит
    учётных данных, после чего падает каждый вызов. Герметичность здесь даёт
    `setting_sources=[]` и `strict_mcp_config=True`, и стоит она ноль.
  * `CLAUDECODE` вычищается из окружения дочернего процесса — раннер обычно
    запускают изнутри сессии Claude Code, и вложенная ведёт себя иначе.
  * `permission_mode="bypassPermissions"`: пакетный прогон, вставший на диалоге
    разрешений, — это прогон, который висит на третьем случае всю ночь.

ПОТОЛОК ОДИН НА ВЕСЬ ПРОГОН, И ОН ОБЩИЙ С СУДЬЁЙ. `judge.SpendLedger` — тот же
объект, что раздаёт резервы судейским вызовам, поэтому инвариант
`committed + reserved <= ceiling` держится над агентом И судьёй сразу. Два
леджера означали бы два потолка и один общий счёт, который ни один из них не
видит.

СЛУЧАЙ, НЕ ВЛЕЗШИЙ В ОСТАТОК, ПОМЕЧАЕТСЯ НЕПОЛНЫМ, А НЕ ВЫБРАСЫВАЕТСЯ. Прогон,
тихо роняющий дорогое, отчитывается по дешёвому, а дешёвое — это короткое и
чистое, то есть ровно та популяция, где у нас и так всё хорошо.

ПОРЯДОК ИСПОЛНЕНИЯ — ОТ ДОРОГИХ К ДЕШЁВЫМ, и это корректность, а не удобство:
резерв держится на полную цену случая всё время его жизни, так что в порядке
выборки длинный случай не допускается никогда.

РЕЗУЛЬТАТ ПИШЕТСЯ ИНКРЕМЕНТАЛЬНО. Одна строка JSONL на случай, дописанная сразу
после него, до отчёта и до всего остального. Прогон на восьми длинных случаях
был убит таймаутом оболочки, и $4.46 сгорели без единого артефакта; больше
такого быть не может.
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import tempfile
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[3]))          # prototype/, for pseudex
if __package__ in (None, ""):
    sys.path.insert(0, str(_HERE.parents[1]))      # bench/agentpii3/
    sys.path.insert(0, str(_HERE.parent))          # bench/agentpii3/live/
    import judge as judge_mod                      # type: ignore[import-not-found]
    import schema                                  # type: ignore[import-not-found]
    import score                                   # type: ignore[import-not-found]
else:
    from bench.agentpii3 import schema, score
    from bench.agentpii3.live import judge as judge_mod

from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import (  # noqa: E402
    MaskContext,
    conversation_key,
    mask_messages,
    mask_tools,
)
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.redact import residual_tokens, unmask_arguments, unmask_text  # noqa: E402
from pseudex.vault import Vault  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

# --- the two models, named once -------------------------------------------
#
# Both are Claude, and `judge.stamp()` says so in the report rather than
# leaving a reader to assume an independent evaluation happened.
AGENT_MODEL: str = judge_mod.AGENT_MODEL
JUDGE_MODEL: str = judge_mod.JUDGE_MODEL

SERVER = "bench"
_PREFIX = f"mcp__{SERVER}__"
_NAMESPACE = uuid.UUID("2b7a4f1e-7c3d-4a95-9f21-0d6e8c5b4a30")

_ORG = "agentpii3-live"
_AGENT = "bench-live"
_OPAQUE_PREFIX = "REDACTED"

# The instruction a case with no system message gets. Fixed text, because a
# prompt we improvise per case would put the harness's own wording inside the
# number the harness reports.
DEFAULT_SYSTEM = ("Ты оператор поддержки. Выполняй просьбу клиента через "
                  "предложенные инструменты, не переспрашивай и не выдумывай "
                  "данных, которых нет в разговоре.")

FILLER_RESULT = '{"status": "ok"}'

# THE HARD PER-CASE CAP THE SDK ENFORCES, by context rung. Not one number: a
# `deep` case in this corpus carries FIFTY-NINE user turns and a `solo` one
# carries one, so a single cap either strangles the long cases or reserves
# twenty times what a short one can spend and lets the ceiling admit a quarter
# of the cases it could.
#
# ANCHORED TO A MEASUREMENT, not to a feeling: a short single-turn arm against
# `claude-sonnet-4-6` billed $0.0134 (agentpii2 probe, 30.08.2026) and the
# nano probe here (31.08.2026) is printed by every run in section 1. A cap that
# sits close to the mean TRUNCATES the multi-turn cases, and a truncated
# trajectory scored as a finished one is worse than a case that did not run.
CAPS: dict[str, float] = {"solo": 0.08, "short": 0.15, "long": 0.35,
                          "deep": 1.00}

# Per-arm wall clock = base + this many seconds per user turn. A flat timeout
# that fits a one-turn case kills a fifty-nine-turn one halfway and records it
# as a product problem.
SECONDS_PER_TURN: float = 20.0


# --- what the model did ---------------------------------------------------


@dataclass(frozen=True)
class ObservedCall:
    """A tool call exactly as the model emitted it.

    `arguments` is the plain dict the SDK hands the handler — not re-parsed, so
    a malformed argument object stays the model's problem instead of becoming
    the harness's.
    """

    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class AgentRun:
    """One case's live trajectory, plus what it cost and how it ended."""

    calls: tuple[ObservedCall, ...]
    replies: tuple[str, ...]          # one per user turn, in order
    final_text: str
    cost_usd: float
    model: str
    turns: int
    duration_ms: int
    is_error: bool
    subtype: str
    api_error_status: int | None
    errors: tuple[str, ...]
    session_id: str
    termination: str
    model_usage: dict[str, object] = field(default_factory=dict)


class HarnessError(RuntimeError):
    """The rig broke, and the case says nothing about the gateway.

    Its own class so `schema.TERMINATIONS` can put it where tau2-bench puts an
    INFRASTRUCTURE_ERROR: excluded from the rates, counted and printed beside
    them. AgentBench writes reward 0 for a harness exception, which records a
    broken rig as a model failure.
    """


def strip_prefix(name: str) -> str:
    """`mcp__bench__crm_get_client` -> `crm_get_client`.

    The prefix is the SDK's transport detail; the corpus names the function,
    and comparing against a transport-decorated name fails every case for the
    wrong reason.
    """
    return name[len(_PREFIX):] if name.startswith(_PREFIX) else name


def session_id(run_id: str, case_id: str) -> str:
    """A canonical dashed UUID, stable for a given run.

    The CLI rejects bare hex, and a random id makes a failed case unfindable in
    the session store afterwards.
    """
    return str(uuid.uuid5(_NAMESPACE, f"{run_id}|{case_id}"))


# --- one conversation through the production masking path -----------------


class LiveGateway:
    """One case's masking session: what the model reads, and what was replaced.

    A class because it owns external state with a lifetime — the vault view and
    the growing transcript — which is this repo's one sanctioned reason for one.

    TWO PASSES OVER THE SAME TEXT, ON PURPOSE. The model reads what
    `envelope.mask_messages` produced, which is the shipped path and the one
    whose cache, audit and conversation scope must be exercised. The ARITHMETIC
    needs the spans, and `mask_messages` returns strings. So every scripted
    message is also run through `score._mask_message` — the same two functions
    production composes, minus the cache and the audit, neither of which can
    change WHAT the model sees — and the two results are compared. A mismatch
    is a harness error and stops the case: the spans axis 1 counts would then
    be describing text the model never read.
    """

    def __init__(self, case: schema.Case, detector: Detector, vault: Vault,
                 audit: AuditLog, cache: MaskCache) -> None:
        conversation = case.conversation_id or conversation_key(
            [{"role": message.role, "content": message.content}
             for message in case.messages])
        self._case = case
        self._detector = detector
        self._base = vault
        self._view = vault.for_conversation(conversation)
        self._conversation = conversation
        self._context = MaskContext(detector=detector, vault=self._view,
                                    audit=audit, cache=cache, org_id=_ORG,
                                    agent_id=_AGENT,
                                    conversation_id=conversation)
        self._transcript: list[dict[str, object]] = []
        self._masked: dict[int, score.Masked] = {}
        self._reached: set[int] = set()
        self._tool_pieces: list[score.Piece] = []
        self._tools: list[dict[str, object]] | None = None
        # A fault raised INSIDE an MCP handler cannot propagate: the SDK turns
        # it into a tool error and the model carries on, so the harness would
        # silently score a case whose masking it could not verify. Collected
        # here and re-raised by the caller after the trajectory ends.
        self._faults: list[str] = []

    @property
    def conversation_id(self) -> str:
        return self._conversation

    @property
    def reached(self) -> tuple[int, ...]:
        return tuple(sorted(self._reached))

    def prime(self, lead: schema.Case) -> None:
        """Mask an earlier conversation into the SAME tenant vault, no model.

        `preceded_by` says this case was preceded by another against one tenant,
        and the `scope` family's claim — that a partial mention here must NOT
        resolve against that one — is empty unless the lead really is in the
        vault. Running the lead through the model would double its cost and add
        nothing: the claim is about the vault, and the model never sees it.
        """
        lead_conversation = lead.conversation_id or conversation_key(
            [{"role": message.role, "content": message.content}
             for message in lead.messages])
        context = MaskContext(detector=self._detector,
                              vault=self._base.for_conversation(lead_conversation),
                              audit=self._context.audit,
                              cache=self._context.cache, org_id=_ORG,
                              agent_id=_AGENT,
                              conversation_id=lead_conversation)
        mask_messages(
            [{"role": message.role, "content": message.content}
             for message in lead.messages], context, False)

    def tools(self) -> list[dict[str, object]]:
        """The tool schemas as the model receives them.

        MASKED BEFORE THE CONVERSATION, which is where this differs from
        `score.py` and cannot not differ. Offline the tools are masked after the
        messages so a value first seen in a description gets the substitute the
        conversation already minted. Live, the schemas go out at session start —
        they ARE the first request, together with the system prompt — so the
        order here is the order a real gateway sees.

        Computed ONCE and kept: a second `mask_tools` would mint against a vault
        the conversation has since filled, and the schemas the model is holding
        would stop being the schemas the report describes.
        """
        if self._tools is not None:
            return self._tools
        masked = mask_tools([dict(schema_) for schema_ in self._case.tools],
                            self._context, False)
        if not isinstance(masked, list):
            raise HarnessError("mask_tools вернул не список — контракт изменён")
        for schema_ in self._case.tools:
            for text in _descriptions(schema_):
                self._tool_pieces.extend(self._observe(text).pieces)
        self._tools = [one for one in masked if isinstance(one, dict)]
        return self._tools

    def push(self, index: int) -> str:
        """Append one scripted corpus message and return what the model reads.

        THE WHOLE TRANSCRIPT IS RE-MASKED, not just the new message: the
        substitute a later mention gets depends on what earlier ones put in the
        vault, and masking message by message would be a different product. It
        is also the shape of a real request — an OpenAI-compatible body carries
        the whole array every time.
        """
        message = self._case.messages[index]
        text = schema.message_text(self._case, index)
        wire: dict[str, object] = {"role": message.role, "content": text}
        if message.name:
            wire["name"] = message.name
        self._transcript.append(wire)
        masked = mask_messages([dict(one) for one in self._transcript],
                               self._context, False)
        content = masked[-1].get("content")
        if not isinstance(content, str):
            raise HarnessError(f"{self._case.id}: сообщение {index} вернулось "
                               f"не строкой из mask_messages")
        observed = self._observe(text)
        if observed.masked != content:
            # FAIL CLOSED. The arithmetic pass and the production pass disagree
            # about this message, so every offset axis 1 is about to count
            # describes a string the model did not read.
            raise HarnessError(
                f"{self._case.id}: маскирование сообщения {index} разошлось — "
                f"производственный путь дал {content[:60]!r}, счётный "
                f"{observed.masked[:60]!r}")
        self._masked[index] = observed
        self._reached.add(index)
        return content

    def note(self, text: str) -> None:
        """Record a turn the model itself produced.

        Already masked — it was written from masked input — so it is appended,
        never re-derived. It IS re-masked on the next push, along with the rest
        of the transcript, and that is deliberate: production does exactly that,
        and a substitute the model reshaped into something the vault no longer
        recognises is a real defect this exercises rather than hides.
        """
        self._transcript.append({"role": "assistant", "content": text})

    def flush(self) -> None:
        """Mask what the conversation never reached, for the detection axis.

        NOT pushed into the transcript — the model never saw these — but masked
        all the same, because the detection denominator must not be a function
        of what the model chose to do. A model that never calls the tool would
        otherwise remove that tool result's gold spans from the denominator and
        the recall would rise for the wrong reason.
        """
        for index in range(len(self._case.messages)):
            if index not in self._masked:
                self._masked[index] = self._observe(
                    schema.message_text(self._case, index))

    def messages(self) -> tuple[score.Masked, ...]:
        missing = [index for index in range(len(self._case.messages))
                   if index not in self._masked]
        if missing:
            raise HarnessError(f"{self._case.id}: не замаскированы сообщения "
                               f"{missing} — flush() не вызван")
        return tuple(self._masked[index]
                     for index in range(len(self._case.messages)))

    def substitutes(self) -> tuple[str, ...]:
        """Every fake this dialogue minted, which is what the judge must get.

        `judge.only_what_the_vault_matched` is the warning: passing only the
        substitutes a string search still finds in the reply answers the
        substitute question before asking it, and leaves out exactly what the
        question exists for — the declined fake, the retold address, the one
        spelled in words. A runner holds the vault and knows the whole list.
        """
        minted = {piece.substitute for message in self._masked.values()
                  for piece in message.pieces}
        minted |= {piece.substitute for piece in self._tool_pieces}
        return tuple(sorted(value for value in minted if value.strip()))

    def restore_arguments(self, arguments: dict[str, object],
                          ) -> tuple[dict[str, str], list[str]]:
        """Detokenise a tool call the way the sidecar does, and report residuals.

        `unmask_arguments`, never a flat replace: an argument object is JSON and
        a real value is arbitrary text, so «ООО "Заря"» spliced in by string
        substitution injects two bare quotes and the call stops parsing. The
        residual list is the other half — a substitute that resolved to nothing
        leaves well-formed JSON and a 200, and the caller has no other way to
        find out that a fake reached the tool.
        """
        restored = unmask_arguments(
            json.dumps(arguments, ensure_ascii=False), self._base)
        try:
            parsed = json.loads(restored)
        except json.JSONDecodeError:
            return ({}, ["<детокенизация сломала собственный JSON>"])
        if not isinstance(parsed, dict):
            return ({}, ["<детокенизация вернула не объект>"])
        values = {str(name): _flat(value) for name, value in parsed.items()}
        residual: list[str] = []
        for value in values.values():
            residual.extend(residual_tokens(value, self._base))
        return values, residual

    def restore_text(self, text: str) -> str:
        """The assistant's prose on the way back to the customer.

        A different endpoint from the one above and deliberately so: flat text
        is what `/unmask` handles, and routing a tool argument through it is the
        defect `unmask_arguments` exists to prevent.
        """
        return unmask_text(text, self._base)

    @property
    def vault(self) -> Vault:
        return self._base

    @property
    def faults(self) -> tuple[str, ...]:
        return tuple(self._faults)

    def fault(self, why: str) -> None:
        self._faults.append(why)

    def _observe(self, text: str) -> score.Masked:
        return score._mask_message(text, self._detector, self._view)


def _flat(value: object) -> str:
    """One argument value as a comparable string.

    A model may answer a string parameter with a number or a boolean; the
    reference is a string, and `json.dumps` of a bare number is the number, so
    nothing is invented by flattening here.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _descriptions(schema_: dict[str, object]) -> list[str]:
    """Every free-text description in one tool schema, which is what `mask_tools`
    rewrites. Names, types and enums are the contract and are never touched."""
    found: list[str] = []
    function = schema_.get("function")
    if not isinstance(function, dict):
        return found
    if isinstance(function.get("description"), str):
        found.append(function["description"])
    parameters = function.get("parameters")
    if isinstance(parameters, dict) and isinstance(parameters.get("properties"), dict):
        for one in parameters["properties"].values():
            if isinstance(one, dict) and isinstance(one.get("description"), str):
                found.append(one["description"])
    return found


# --- driving the agent ----------------------------------------------------


def _system_prompt(case: schema.Case, gateway: LiveGateway) -> str:
    for index, message in enumerate(case.messages):
        if message.role == "system":
            return gateway.push(index)
    return DEFAULT_SYSTEM


def _tool_results(case: schema.Case) -> dict[str, list[int]]:
    """Tool name -> the corpus message indexes holding its scripted results.

    The corpus scripts history, never the behaviour under test: a `tool` message
    holds the result the customer's CRM would have returned, and the harness
    serves that same string when the model calls the tool. Consumed in order, so
    a model that looks twice gets the second record rather than the first again.
    """
    served: dict[str, list[int]] = defaultdict(list)
    for index, message in enumerate(case.messages):
        if message.role == "tool" and message.name:
            served[message.name].append(index)
    return served


def _mcp_tools(case: schema.Case, gateway: LiveGateway,
               masked_schemas: list[dict[str, object]],
               sink: list[ObservedCall]) -> list[object]:
    """One in-process MCP tool per function the case offers.

    The schemas handed to the SDK are the MASKED ones, unchanged — `@tool`
    accepts a full JSON Schema, and translating them would make the benchmark's
    published claim («replay this against any provider») false for the one
    provider it actually runs against.
    """
    served = _tool_results(case)
    queues = {name: list(indexes) for name, indexes in served.items()}
    built: list[object] = []
    for schema_ in masked_schemas:
        function = schema_.get("function")
        if not isinstance(function, dict):
            continue
        name = str(function.get("name", ""))
        description = str(function.get("description", "") or name)
        parameters = function.get("parameters")
        parameters = parameters if isinstance(parameters, dict) else {
            "type": "object", "properties": {}}

        def make(tool_name: str) -> object:
            async def handler(args: dict[str, object]) -> dict[str, object]:
                sink.append(ObservedCall(name=tool_name, arguments=dict(args)))
                queue = queues.get(tool_name) or []
                if not queue:
                    return {"content": [{"type": "text", "text": FILLER_RESULT}]}
                # The LAST recorded result is reused once the queue drains
                # rather than falling back to the filler: a model that looks
                # something up twice must not be told the record vanished.
                index = queue.pop(0) if len(queue) > 1 else queue[0]
                try:
                    served_text = gateway.push(index)
                except HarnessError as broken:
                    # The SDK would turn a raised exception into a tool error
                    # the model then reasons about, and the case would be
                    # scored as if the masking had been verified. Recorded and
                    # re-raised by `run_agent`, which fails the case closed.
                    gateway.fault(str(broken))
                    return {"content": [{"type": "text", "text": FILLER_RESULT}]}
                return {"content": [{"type": "text", "text": served_text}]}
            return tool(tool_name, description, parameters)(handler)

        built.append(make(name))
    return built


def _user_turns(case: schema.Case) -> int:
    return sum(1 for message in case.messages if message.role == "user")


def _timeout(case: schema.Case, base: float) -> float:
    return base + SECONDS_PER_TURN * _user_turns(case)


def _options(case: schema.Case, model: str, cap_usd: float, run_id: str,
             servers: dict[str, object], allowed: list[str], system: str,
             workdir: str) -> ClaudeAgentOptions:
    """Hermetic options. Everything the CLI could pick up off the filesystem is
    off, and the ONE thing that must be inherited — the keychain credential — is
    inherited because `CLAUDE_CONFIG_DIR` is left alone."""
    env = {key: value for key, value in os.environ.items()
           if key != "CLAUDECODE"}
    return ClaudeAgentOptions(
        model=model,
        tools=[],                     # no built-in tools: only the case's own
        mcp_servers=servers,
        allowed_tools=allowed,
        strict_mcp_config=True,
        setting_sources=[],
        permission_mode="bypassPermissions",
        system_prompt=system,
        # Three assistant turns per user turn plus slack: a case whose model
        # looks something up, reads the result and then acts spends three on one.
        max_turns=3 * _user_turns(case) + 10,
        max_budget_usd=cap_usd,
        session_id=session_id(run_id, case.id),
        cwd=workdir,
        env=env,
    )


def _termination(result: ResultMessage | None) -> str:
    """One of `schema.TERMINATIONS`, from what the SDK actually reported.

    tau2-bench excludes INFRASTRUCTURE_ERROR rows from its metrics and prints
    the excluded count beside them; AgentBench writes reward 0 instead, so a
    broken rig is recorded as a model failure. This follows tau2.
    """
    if result is None:
        return "harness_error"
    if not result.is_error and result.subtype == "success":
        return "done"
    if "max_turns" in result.subtype or "max_budget" in result.subtype:
        return "max_steps"
    return "provider_error"


async def run_agent(case: schema.Case, gateway: LiveGateway, model: str,
                    cap_usd: float, run_id: str, timeout_s: float) -> AgentRun:
    """Replay one case's user turns against the real model, through the gateway.

    Raises `asyncio.TimeoutError` on the caller's timeout — deliberately NOT
    caught here. A timed-out run has no `ResultMessage` and therefore no
    measured cost, and the only honest thing to do with it is charge the
    reservation in full and record the case incomplete.
    """
    calls: list[ObservedCall] = []
    system = _system_prompt(case, gateway)
    masked_schemas = gateway.tools()
    server = create_sdk_mcp_server(
        SERVER, tools=_mcp_tools(case, gateway, masked_schemas, calls))
    allowed = [_PREFIX + str(one["function"]["name"])
               for one in masked_schemas
               if isinstance(one.get("function"), dict)]

    replies: list[str] = []
    # THE LAST ResultMessage CARRIES THE SESSION'S COST, and that is measured,
    # not assumed: four turns of one session reported 0.00125 -> 0.00217 ->
    # 0.00328 -> 0.00460, monotonically, so `total_cost_usd` is CUMULATIVE and
    # summing the per-turn values would bill the run several times over.
    # `num_turns` is the opposite — it read 1 on every one of those four — so it
    # IS per query and has to be added up. One message, two different meanings.
    result: ResultMessage | None = None
    failed: ResultMessage | None = None
    turns = 0
    model_name = model
    workdir = tempfile.mkdtemp(prefix="agentpii3-live-")
    options = _options(case, model, cap_usd, run_id, {SERVER: server}, allowed,
                       system, workdir)

    async def drive() -> None:
        nonlocal result, failed, turns, model_name
        async with ClaudeSDKClient(options=options) as client:
            for index, message in enumerate(case.messages):
                if message.role != "user":
                    continue
                await client.query(gateway.push(index))
                turn: list[str] = []
                async for reply in client.receive_response():
                    if isinstance(reply, AssistantMessage):
                        text = "".join(block.text for block in reply.content
                                       if isinstance(block, TextBlock))
                        if text:
                            turn.append(text)
                    elif isinstance(reply, ResultMessage):
                        result = reply
                        turns += int(reply.num_turns)
                        if failed is None and (reply.is_error
                                               or reply.subtype != "success"):
                            # THE FIRST FAILURE, KEPT. Only the last
                            # ResultMessage survives otherwise, so a turn that
                            # errored in the middle of a long case would be
                            # invisible in a run that ended cleanly.
                            failed = reply
                        if reply.model_usage:
                            # The model the RUN billed, which is not always the
                            # one requested: Claude Code bills a small model for
                            # its own bookkeeping alongside the one under test,
                            # and a result claiming one model when two were
                            # charged is a cost nobody can reconcile.
                            model_name = max(
                                reply.model_usage.items(),
                                key=lambda row: float(
                                    (row[1] or {}).get("costUSD", 0.0)
                                    if isinstance(row[1], dict) else 0.0))[0]
                joined = "\n".join(turn)
                replies.append(joined)
                if joined:
                    gateway.note(joined)

    await asyncio.wait_for(drive(), timeout=timeout_s)

    if gateway.faults:
        raise HarnessError(f"{case.id}: {gateway.faults[0]}")
    if result is None:
        raise HarnessError(f"{case.id}: поток закончился без ResultMessage")
    worst = failed or result
    return AgentRun(
        calls=tuple(calls),
        replies=tuple(replies),
        # THE REPLY TO THE LAST USER TURN, which is what the customer reads at
        # the end. An earlier turn's prose is checked deterministically as well
        # (see `_axis3`), but the owner's question is about the final answer.
        final_text=next((one for one in reversed(replies) if one.strip()), ""),
        cost_usd=float(result.total_cost_usd or 0.0),
        model=model_name,
        turns=turns,
        duration_ms=int(result.duration_ms),
        is_error=bool(worst.is_error),
        subtype=str(worst.subtype),
        api_error_status=worst.api_error_status,
        errors=tuple(str(one) for one in (worst.errors or ())),
        session_id=options.session_id or "",
        termination=_termination(worst),
        model_usage=dict(result.model_usage or {}),
    )


# --- axis 2: the reference call against what the model really did ---------


@dataclass(frozen=True)
class CallOutcome:
    """One reference call, judged against the model's trajectory."""

    name: str
    matched: bool
    candidates: int
    outcomes: tuple[score.ArgumentOutcome, ...]
    unlocatable: int
    residual: tuple[str, ...]


def _judge_candidate(case: schema.Case, call: schema.ExpectedCall,
                     observed: ObservedCall | None,
                     messages: tuple[score.Masked, ...],
                     values: list[tuple[str, str, str]],
                     vault: Vault, gateway: LiveGateway,
                     ) -> tuple[list[score.ArgumentOutcome], int, list[str]]:
    """Score one candidate call. `observed is None` means the model never called.

    WHERE THE ARGUMENT SITS IS FOUND EXACTLY AS OFFLINE (`score._locate`), and
    that is the point: the location decides whose datum it is and whether the
    gateway touched it, and both of those are properties of the transcript, not
    of the model. What comes from the model is only the VALUE it wrote.
    """
    by_id = {item.id: item for item in case.pii}
    restored: dict[str, str] = {}
    residual: list[str] = []
    if observed is not None:
        restored, residual = gateway.restore_arguments(observed.arguments)

    outcomes: list[score.ArgumentOutcome] = []
    unlocatable = 0
    for argument in call.judged_args:
        expected = call.arguments.get(argument, "")
        where = score._locate(case, call, argument, expected, messages)
        if where is None:
            # Reported as its own count and never silently passed: the gateway
            # did not touch what it could not see, and a reader has to know the
            # denominator moved before reading the rate.
            unlocatable += 1
            continue
        raw = messages[where.msg].text[where.start:where.end]
        touched = score._seen(messages[where.msg], where.start,
                              where.end) != raw
        wrote = observed.arguments.get(argument) if observed else None
        model_saw = _flat(wrote) if wrote is not None else ""
        came_back = restored.get(argument, "")
        absent = observed is None or wrote is None
        if where.item_id:
            item = by_id[where.item_id]
            others = [(kind, value) for identity, kind, value in values
                      if identity != item.identity]
            # `call_absent` is `schema`'s own name for it and says what it
            # means: the model never made the call, which is not the gateway.
            # It is counted apart from the gateway's rate rather than folded in.
            kind = ("call_absent" if absent else
                    score._break_kind(item, expected, model_saw, came_back,
                                      touched, others, vault))
            outcomes.append(score.ArgumentOutcome(
                case_id=case.id, register=case.register, family=case.family,
                tool=call.name, argument=argument, pii_type=item.type,
                kind=kind, intact=(kind == "ok"), touched=touched,
                expected=expected, model_saw=model_saw, restored=came_back,
                how=where.how))
            continue
        # NO PERSONAL DATUM HERE, so the demand is byte identity and nothing
        # softer. An order number that comes back as a different order number is
        # a broken call even though every character of it is well formed.
        outcomes.append(score.ArgumentOutcome(
            case_id=case.id, register=case.register, family=case.family,
            tool=call.name, argument=argument, pii_type="",
            kind="call_absent" if absent else "", intact=(
                not absent and came_back == expected),
            touched=touched, expected=expected, model_saw=model_saw,
            restored=came_back, how=where.how))
    return outcomes, unlocatable, residual


def _match_calls(case: schema.Case, messages: tuple[score.Masked, ...],
                 observed: tuple[ObservedCall, ...],
                 values: list[tuple[str, str, str]], vault: Vault,
                 gateway: LiveGateway) -> list[CallOutcome]:
    """Pair each reference call with the model's best attempt at it.

    MATCHED UNORDERED AND BY BEST FIT. tau2-bench searches the whole trajectory
    per expected action, BFCL's checker is an unordered multiset and its
    `method_invoke_order_checker` is committed COMMENTED OUT: order is a
    property of the model and the owner ruled model behaviour out of scope.
    Best fit rather than first fit for the same reason — a model that calls the
    tool twice, once wrong and once right, DID reach the reference call, and
    charging the gateway for the model's first draft would measure the wrong
    thing.
    """
    taken: set[int] = set()
    results: list[CallOutcome] = []
    for call in case.calls:
        candidates = [index for index, one in enumerate(observed)
                      if index not in taken
                      and strip_prefix(one.name) == call.name]
        best: tuple[int, int, list[score.ArgumentOutcome], int, list[str]] | None = None
        for index in candidates:
            outcomes, unlocatable, residual = _judge_candidate(
                case, call, observed[index], messages, values, vault, gateway)
            hits = sum(1 for one in outcomes if one.intact)
            if best is None or hits > best[1]:
                best = (index, hits, outcomes, unlocatable, residual)
        if best is None:
            outcomes, unlocatable, residual = _judge_candidate(
                case, call, None, messages, values, vault, gateway)
            results.append(CallOutcome(name=call.name, matched=False,
                                       candidates=0, outcomes=tuple(outcomes),
                                       unlocatable=unlocatable,
                                       residual=tuple(residual)))
            continue
        taken.add(best[0])
        results.append(CallOutcome(name=call.name, matched=True,
                                   candidates=len(candidates),
                                   outcomes=tuple(best[2]),
                                   unlocatable=best[3],
                                   residual=tuple(best[4])))
    return results


# --- axis 3: what the customer reads --------------------------------------


def _digit_runs(text: str) -> list[str]:
    """Maximal digit-bearing runs, the candidates a demanded number can be in.

    A reply is prose and `schema.same_value` compares whole strings, so the
    candidates have to be carved out before the rule can be applied. Separators
    a phone or a document number legitimately carries are kept inside the run;
    everything else ends it.
    """
    runs: list[str] = []
    current: list[str] = []
    for character in text:
        if character.isdigit() or (current and character in " -()+."):
            current.append(character)
        else:
            if any(one.isdigit() for one in current):
                runs.append("".join(current).strip(" -.()"))
            current = []
    if any(one.isdigit() for one in current):
        runs.append("".join(current).strip(" -.()"))
    return runs


def _came_back(required: str, kind: str, reply: str) -> bool:
    """Whether a demanded value is present in a REAL agent's prose.

    THREE TESTS, AND EACH ONE IS THE PROSE ANALOGUE OF A RULE THAT ALREADY
    EXISTS, never a new rule about what counts as the same value:

      1. the value stands in the reply verbatim (casefold), which is
         `schema.same_value`'s text branch with the reply as the haystack;
      2. for a numeric type, `schema.same_value` applied to each digit-bearing
         run of the reply — a phone the agent wrote as +7 (999) 123-45-67 is the
         same phone, and the rule that says so is the type's own;
      3. for a text type, every whitespace-separated part of the demand stands
         in the reply. An agent writes «ваш адрес — улица Гусева, дом 81,
         квартира 117» where the demand is «Гусева, 81, кв. 117», and a
         substring test alone manufactures a defect out of that. This errs
         toward NOT reporting a violation, which is the safe direction for a
         diagnostic: it invents no defect it cannot see, and a value that really
         did not come back has parts that really are absent.
    """
    folded = reply.casefold()
    if required.casefold() in folded:
        return True
    if kind in schema.DIGIT_TYPES:
        return any(schema.same_value(run, required, kind)
                   for run in _digit_runs(reply))
    parts = [part.strip(" ,.;:«»\"'()").casefold()
             for part in required.split()]
    parts = [part for part in parts if part]
    return bool(parts) and all(part in folded for part in parts)


def _answer_request(case: schema.Case, reply: str, vault: Vault,
                    minted: tuple[str, ...]) -> score.JudgeRequest:
    """The reply as the CUSTOMER sees it, with the vault facts already decided.

    THE VAULT FACTS ARE NOT THE JUDGE'S BUSINESS. Which strings this dialogue
    minted, and which of them survived detokenisation, are facts only the
    gateway's own vault can supply; a model asked to guess them would invent
    them. So they arrive already decided and the judge is left with what a model
    is actually for.
    """
    kinds = {item.canonical: item.type for item in case.pii}
    kinds.update({item.value: item.type for item in case.pii})
    surviving = tuple(residual_tokens(reply, vault))
    opaque = tuple(value for value in surviving
                   if value.startswith(_OPAQUE_PREFIX))
    missing = tuple(required for required in case.final.must_contain
                    if not _came_back(required, kinds.get(required, ""), reply))
    return score.JudgeRequest(
        case_id=case.id,
        question=("остались ли настоящие ПД в ответе клиенту, и не выдана ли "
                  "подмена за настоящее значение"),
        answer=reply,
        must_contain=case.final.must_contain,
        must_not_contain=case.final.must_not_contain,
        closed_answer=case.final.answer,
        substitutes_present=surviving,
        # ВСЕ отчеканенные, не только уцелевшие в тексте. Судья, которому дают
        # лишь то, что уже нашёл строковый поиск, отвечает на заданный вопрос
        # вместо незаданного — это и есть `judge.only_what_the_vault_matched`.
        # Поле появилось в `score.JudgeRequest` вместе с починкой судьи, а этот
        # вызов остался прежним, и живой прогон падал на первом же случае с
        # TypeError — после того как за агента уже заплачено.
        substitutes_minted=minted,
        residual_present=opaque,
        missing=missing)


async def _judge_answer(request: score.JudgeRequest,
                        substitutes: tuple[str, ...],
                        config: judge_mod.JudgeConfig,
                        ) -> tuple[score.JudgeVerdict, judge_mod.Judgement | None,
                                   str]:
    """The deterministic floor, raised by whatever the model could PROVE.

    `judge.sdk_judge` is the synchronous adapter and it wraps `judge_answer` in
    `anyio.run`, which cannot be called from inside a running loop. So the same
    three public functions are composed here instead — `case_under_judgement`,
    `judge_answer`, `merge` — and nothing about the judge is re-implemented:
    the prompt, the blindness guard, the quote rule and the severity merge all
    stay where they are.

    A judgement the ceiling would not admit leaves a VAULT FACT standing (a
    substitute the vault matched in the reply is not an opinion) and turns
    anything softer into `unjudged`. Axis 3 without a judge is not a clean bill.
    """
    base = score.deterministic_judge(request)
    under = judge_mod.case_under_judgement(request, lambda _r: substitutes)
    try:
        judgement = await judge_mod.judge_answer(
            under, judge_mod.oracle_literals(request), config)
    except judge_mod.BudgetExhausted as exhausted:
        if base.verdict in ("clean", score.UNJUDGED):
            return (score.JudgeVerdict(
                verdict=score.UNJUDGED,
                why=f"судья не запущен: {exhausted}",
                judged_by="none/бюджет"), None, str(exhausted))
        return base, None, str(exhausted)
    except judge_mod.JudgeCallFailed as failure:
        if base.verdict in ("clean", score.UNJUDGED):
            return (score.JudgeVerdict(
                verdict=score.UNJUDGED, why=f"судья не ответил: {failure}",
                judged_by="none/отказ"), None, str(failure))
        return base, None, str(failure)
    return judge_mod.merge(base, judgement), judgement, ""


def _finding_row(finding: judge_mod.Finding) -> dict[str, object]:
    """One judge finding, WITH ITS QUOTE.

    A verdict without a quote is indistinguishable from a model judging its own
    impression of the text, so the quote is stored in the artefact and not only
    weighed at merge time.
    """
    return {"question": finding.question, "asked": finding.asked,
            "found": finding.found, "value": finding.value,
            "quote": finding.quote, "confidence": finding.confidence,
            "why": finding.why, "valid": finding.valid,
            "invalid": finding.invalid_reason, "attempts": finding.attempts,
            "cost_usd": round(finding.cost_usd, 6)}


# --- one case, end to end -------------------------------------------------


def _cap(case: schema.Case) -> float:
    return CAPS.get(case.context, CAPS["short"])


def _shippable(case: schema.Case) -> bool:
    """True when every source this case quotes may be written to a file.

    Measuring with a corpus is not the same permission as shipping it, and a
    results file on disk is shipping. Today every source is CC BY 4.0; the guard
    is here so that stops being an accident.
    """
    return all(message.source is None
               or message.source.licence in schema.SHIPPABLE_LICENCES
               for message in case.messages)


def _blank(record: dict[str, object]) -> dict[str, object]:
    """Strip every value carried out of a licensed case, keeping the shape."""
    marker = "<лицензионный источник>"
    record["answer_text"] = marker
    for row in record.get("arguments") or []:
        for key in ("expected", "model_saw", "restored"):
            row[key] = marker
    answer = record.get("answer")
    if isinstance(answer, dict):
        for name in ("leak", "substitution"):
            finding = answer.get("findings", {}).get(name)
            if isinstance(finding, dict):
                finding["quote"] = marker
                finding["value"] = marker
    return record


async def _one_case(case: schema.Case, lead: schema.Case | None,
                    detector: Detector, vault: Vault, audit: AuditLog,
                    cache: MaskCache, ledger: judge_mod.SpendLedger,
                    config: judge_mod.JudgeConfig, model: str, run_id: str,
                    timeout_s: float,
                    values_chain: dict[str, list[tuple[str, str, str]]],
                    ) -> dict[str, object]:
    """Run one case, or record why it did not run. Never raises for one case."""
    cap = _cap(case)
    record: dict[str, object] = {
        "id": case.id, "family": case.family, "register": case.register,
        "context": case.context, "cluster": case.cluster,
        "selection": case.provenance.selection,
        "weight": case.provenance.weight,
        "axes": list(schema.judged_axes(case)),
        "cap_usd": round(cap, 6), "agent_cost_usd": 0.0, "judge_cost_usd": 0.0,
        "cost_usd": 0.0, "status": "incomplete", "termination": "harness_error",
        "reason": "", "produced": [], "arguments": [], "links": [],
        "answer": {}, "answer_text": "",
    }
    try:
        await ledger.reserve(cap)
    except judge_mod.BudgetExhausted as exhausted:
        # NOT DROPPED. A run that sheds what it cannot afford reports the cheap
        # cases, and the cheap cases are the short clean ones — the population
        # whose numbers are already good.
        record["reason"] = str(exhausted)
        record["termination"] = "harness_error"
        return record

    started = time.monotonic()
    gateway = LiveGateway(case, detector, vault, audit, cache)
    record["conversation_id"] = gateway.conversation_id
    spent = 0.0
    agent: AgentRun | None = None
    try:
        if lead is not None:
            gateway.prime(lead)
        agent = await run_agent(case, gateway, model, cap, run_id,
                                _timeout(case, timeout_s))
        spent = agent.cost_usd
        record["termination"] = agent.termination
    except asyncio.TimeoutError:
        record["termination"] = "timeout"
        record["reason"] = f"таймаут {_timeout(case, timeout_s):.0f}s"
        # A timed-out run produced no ResultMessage and therefore no measured
        # cost. The reservation is charged IN FULL rather than at zero: the run
        # did happen and did bill, and a ledger that books it at zero lets the
        # next case spend money that is already gone.
        spent = cap
    except HarnessError as broken:
        record["termination"] = "harness_error"
        record["reason"] = f"HarnessError: {broken}"
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as broken:
        record["termination"] = "harness_error"
        record["reason"] = f"{type(broken).__name__}: {broken}"
    finally:
        await ledger.settle(f"agent/{case.id}", cap, spent)
        record["agent_cost_usd"] = round(spent, 6)

    # AXIS 1 IS SCORED EVEN WHEN THE MODEL LEG FAILED. Detection happened on
    # every message the gateway saw, and `flush` supplies the rest; throwing it
    # away because the provider returned a 529 would discard a measurement that
    # cost real money and says nothing about the provider.
    try:
        gateway.flush()
        messages = gateway.messages()
        for item in case.pii:
            held = messages[item.msg].text[item.start:item.end]
            if held != item.value:
                raise HarnessError(
                    f"{case.id}: item {item.id} claims {item.value!r} at "
                    f"[{item.start}:{item.end}] of message {item.msg}, which "
                    f"holds {held!r} — every offset in this case is wrong")
        produced = score._observed(messages)
        record["produced"] = [asdict(span) for span in produced]
        record["reached_messages"] = list(gateway.reached)
    except HarnessError as broken:
        record["reason"] = f"{record['reason'] or ''} | {broken}".strip(" |")
        record["wall_s"] = round(time.monotonic() - started, 2)
        record["cost_usd"] = round(spent, 6)
        return record

    if agent is not None:
        record.update(_agent_row(agent))
    if agent is None or agent.termination in schema.EXCLUDED_TERMINATIONS:
        record["axes_scored"] = ["detect"]
        record["wall_s"] = round(time.monotonic() - started, 2)
        record["cost_usd"] = round(spent, 6)
        return record

    # AXIS 2.
    values = ([(item.identity, item.type, item.canonical) for item in case.pii]
              + values_chain.get(case.preceded_by, []))
    values_chain[case.id] = values
    if case.calls:
        record["dispatch"] = score._dispatch_intact(
            case, gateway.tools(), messages)
        calls = _match_calls(case, messages, agent.calls, values,
                             gateway.vault, gateway)
        record["arguments"] = [asdict(one) for call in calls
                               for one in call.outcomes]
        record["calls"] = [
            {"name": one.name, "matched": one.matched,
             "candidates": one.candidates, "unlocatable": one.unlocatable,
             "residual": list(one.residual),
             "whole": bool(one.matched and one.outcomes
                           and all(x.intact for x in one.outcomes)
                           and not one.unlocatable)}
            for one in calls]
        made = {strip_prefix(one.name) for one in agent.calls}
        record["calls_extra"] = sorted(
            made - {call.name for call in case.calls})
        record["model_calls"] = [
            {"name": strip_prefix(one.name), "arguments": one.arguments}
            for one in agent.calls]
    record["links"] = _link_rows(case, messages, gateway)

    # AXIS 3.
    reply = gateway.restore_text(agent.final_text)
    record["answer_text"] = reply
    request = _answer_request(case, reply, gateway.vault, gateway.substitutes())
    verdict, judgement, trouble = await _judge_answer(
        request, gateway.substitutes(), config)
    judge_cost = judgement.cost_usd if judgement else 0.0
    record["judge_cost_usd"] = round(judge_cost, 6)
    record["answer"] = {
        "verdict": verdict.verdict, "why": verdict.why,
        "judged_by": verdict.judged_by,
        "judged": judgement is not None,
        "trouble": trouble,
        "substitutes_minted": len(gateway.substitutes()),
        "substitutes_present": list(request.substitutes_present),
        "residual_present": list(request.residual_present),
        "missing": list(request.missing),
        "findings": ({"leak": _finding_row(judgement.leak),
                      "substitution": _finding_row(judgement.substitution)}
                     if judgement else {}),
    }
    # ALSO, DETERMINISTICALLY, OVER EVERY REPLY. The owner's axis is the final
    # answer, and that is what the judge grades; a substitute standing in turn
    # three is still a fake shown to the customer, and the vault can say so for
    # nothing.
    earlier: list[str] = []
    for one in agent.replies[:-1]:
        earlier.extend(residual_tokens(gateway.restore_text(one),
                                       gateway.vault))
    record["earlier_turns_residual"] = sorted(set(earlier))

    record["status"] = "complete"
    record["axes_scored"] = list(schema.judged_axes(case))
    record["cost_usd"] = round(spent + judge_cost, 6)
    record["wall_s"] = round(time.monotonic() - started, 2)
    return record if _shippable(case) else _blank(record)


def _agent_row(agent: AgentRun) -> dict[str, object]:
    return {
        "model": agent.model, "turns": agent.turns,
        "duration_ms": agent.duration_ms, "subtype": agent.subtype,
        "is_error": agent.is_error, "api_error_status": agent.api_error_status,
        "errors": list(agent.errors), "session_id": agent.session_id,
        "model_usage": {name: round(float(row.get("costUSD", 0.0)), 6)
                        for name, row in agent.model_usage.items()
                        if isinstance(row, dict)},
    }


def _link_rows(case: schema.Case, messages: tuple[score.Masked, ...],
               gateway: LiveGateway) -> list[dict[str, object]]:
    """WHOSE CALL IT IS. Part of axis 2, not a fourth axis.

    Two people wearing one pseudonym means whichever of them the call names, the
    other one's call lands on him — and that outcome is reachable with every
    argument comparing equal, which is why it is measured rather than inferred
    from the break kinds. Only within-case pairs are judged here: a `scope` pair
    naming another case needs both conversations' substitutes, and the live run
    holds one gateway per case.
    """
    rendered = {item.id: score._seen(messages[item.msg], item.start, item.end)
                for item in case.pii}
    rows: list[dict[str, object]] = []
    for link in case.links:
        if link.kind == "unjudged" or link.case:
            rows.append({"kind": link.kind if not link.case else "вне случая",
                         "held": None, "evidence": ""})
            continue
        left = rendered.get(link.left)
        right = rendered.get(link.right)
        left_masked = left is not None and left != _value_of(case, link.left)
        right_masked = right is not None and right != _value_of(case, link.right)
        if not (left_masked and right_masked):
            rows.append({"kind": "не замаскировано", "held": None,
                         "evidence": ""})
            continue
        if link.kind == "different":
            held = left.casefold() != right.casefold()
            evidence = f"{left!r} и {right!r}"
        else:
            left_real = gateway.restore_text(left)
            right_real = gateway.restore_text(right)
            held = score._one_person(left_real, right_real)
            evidence = f"{left!r} -> {left_real!r} против {right!r} -> {right_real!r}"
        rows.append({"kind": link.kind, "held": held,
                     "evidence": f"{evidence} — {link.why[:52]}"})
    return rows


def _value_of(case: schema.Case, item_id: str) -> str:
    for item in case.pii:
        if item.id == item_id:
            return item.value
    return ""


# --- the run --------------------------------------------------------------


def _chains(cases: list[schema.Case]) -> list[list[schema.Case]]:
    """Cases grouped by the vault they must share, each group in dependency order.

    ONE VAULT PER GROUP AND NOT ONE PER RUN. A tenant's vault is shared across
    conversations in production, but a corpus is not a tenant: unrelated
    conversations in one vault exhaust the substitute pools, and an exhausted
    pool is a 5xx, not a measurement. A group is the connected component under
    `preceded_by` — exactly the cases whose claims are about each other — and
    inside it the order is the one where a `preceded_by` always ran first.
    """
    return [score._order(group) for group in score._groups(cases)]


async def _drive(chains: list[list[schema.Case]], leads: dict[str, schema.Case],
                 detector: Detector, ledger: judge_mod.SpendLedger,
                 config: judge_mod.JudgeConfig, model: str, run_id: str,
                 timeout_s: float, concurrency: int, sink: Path,
                 ) -> list[dict[str, object]]:
    limiter = asyncio.Semaphore(max(1, concurrency))
    total = sum(len(chain) for chain in chains)
    records: list[dict[str, object]] = []
    done = 0

    # EXECUTION ORDER IS MOST-EXPENSIVE-FIRST, and it is a correctness choice
    # rather than a scheduling nicety: a reservation is held at full cap for the
    # life of a case, so running the cheap ones first spends the ledger down and
    # then refuses the one case whose cap is large. At nano a `deep` case
    # reserves 1.00 of a 3.00 ceiling — in draw order it is admitted never, and
    # «the run sheds the expensive cases and reports the cheap ones» is exactly
    # the failure the incomplete-not-dropped rule exists to prevent.
    schedule = sorted(chains, key=lambda chain: -max(_cap(one) for one in chain))

    async def worker(chain: list[schema.Case]) -> None:
        nonlocal done
        async with limiter:
            # ONE VAULT PER CHAIN, and the chain runs inside one worker so the
            # `preceded_by` case really has run before the one that depends on
            # it — a claim about the vault asked before the row exists answers
            # «not linked» for the wrong reason.
            vault = Vault(":memory:", _ORG)
            audit = AuditLog(":memory:")
            cache = MaskCache(1024)
            values_chain: dict[str, list[tuple[str, str, str]]] = {}
            for case in chain:
                record = await _one_case(
                    case, leads.get(case.id), detector, vault, audit, cache,
                    ledger, config, model, run_id, timeout_s, values_chain)
                # WRITTEN BEFORE ANYTHING ELSE. A shell timeout during the next
                # case must not cost this one's result.
                with sink.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                records.append(record)
                done += 1
                answer = record.get("answer") or {}
                print(f"  [{done}/{total}] {case.id} {record['status']}/"
                      f"{record['termination']} "
                      f"${float(record['cost_usd']):.4f} "
                      f"ось3={answer.get('verdict', '—')}", flush=True)

    await asyncio.gather(*(worker(chain) for chain in schedule))
    return records


# --- aggregation ----------------------------------------------------------


@dataclass
class LiveTally:
    """Axes 2 and 3 as the live run sees them. Counters only, never rates.

    A stored rate is a rate somebody can compute with the wrong denominator
    later; every share printed is derived from a pair printed beside it.
    """

    dispatch: list[int] = field(default_factory=lambda: [0, 0])
    whole_calls: list[int] = field(default_factory=lambda: [0, 0])
    calls_absent: int = 0
    calls_extra: int = 0
    plain_args: list[int] = field(default_factory=lambda: [0, 0])
    pii_args: list[int] = field(default_factory=lambda: [0, 0])
    touched_args: list[int] = field(default_factory=lambda: [0, 0])
    absent_args: int = 0
    unlocatable: int = 0
    residual_calls: int = 0
    breaks: "Counter[str]" = field(default_factory=Counter)
    breaks_by_type: dict[str, list[int]] = field(
        default_factory=lambda: defaultdict(lambda: [0, 0]))
    links: dict[str, list[int]] = field(
        default_factory=lambda: defaultdict(lambda: [0, 0]))
    answers: "Counter[str]" = field(default_factory=Counter)
    # [asked, total]: how often the judge was actually put a question, not how
    # often a Judgement object came back. A dialogue where the gateway minted
    # nothing and the case forbids nothing has NOTHING to ask about, and
    # counting that as «the judge worked» would let a run with no masking at all
    # report a full judged denominator.
    judged: list[int] = field(default_factory=lambda: [0, 0])
    nothing_to_ask: int = 0
    earlier_residual: int = 0
    terminations: "Counter[str]" = field(default_factory=Counter)
    # Refused by the ceiling, which is NOT a harness failure even though it
    # shares `harness_error`'s exclusion: `schema.TERMINATIONS` is the corpus's
    # vocabulary and a runner may not grow it. Counted here so the report can
    # say the word out loud — a run that refused cases and printed only a rate
    # is the exact failure the incomplete-not-dropped rule exists to prevent.
    refused_budget: int = 0
    broken: list[dict[str, object]] = field(default_factory=list)
    verdicts: list[tuple[str, str, str, str]] = field(default_factory=list)


def _aggregate(records: list[dict[str, object]], by_id: dict[str, schema.Case],
               dump: int) -> tuple[score.Tally, LiveTally]:
    """Every number in the report, from the per-case records and nothing else.

    ONE aggregation path, used by the live run and by `--report` over a saved
    JSONL alike. Two would drift, and a report that disagrees with the run it
    describes is worse than no report.

    Axis 1 goes through `score._tally_detection` — the OFFLINE counter, not a
    live copy of it. The live and offline reports have to be comparable line by
    line, and two implementations of one rate always diverge eventually.
    """
    tally = score._empty_tally()
    live = LiveTally()
    for record in records:
        case = by_id.get(str(record["id"]))
        if case is None:
            continue
        live.terminations[str(record.get("termination", "?"))] += 1
        live.refused_budget += int("потолок" in str(record.get("reason", "")))
        produced = [schema.MaskedSpan(msg=int(one["msg"]), start=int(one["start"]),
                                      end=int(one["end"]), type=str(one["type"]))
                    for one in record.get("produced") or []]
        if produced or record.get("reached_messages") is not None:
            # `_tally_detection` reads the message text for the dump only, and
            # that text is the corpus's own — so the tally is rebuilt exactly,
            # with no vault and no model.
            messages = tuple(
                score.Masked(text=schema.message_text(case, index), masked="",
                             pieces=())
                for index in range(len(case.messages)))
            score._tally_detection(case, messages, produced, tally, "", dump)

        if record.get("status") != "complete":
            continue

        if case.calls:
            live.dispatch[1] += 1
            live.dispatch[0] += int(not record.get("dispatch"))
        for call in record.get("calls") or []:
            live.whole_calls[1] += 1
            live.whole_calls[0] += int(bool(call.get("whole")))
            live.calls_absent += int(not call.get("matched"))
            live.unlocatable += int(call.get("unlocatable") or 0)
            live.residual_calls += int(bool(call.get("residual")))
        live.calls_extra += len(record.get("calls_extra") or [])

        for row in record.get("arguments") or []:
            kind = str(row.get("kind") or "")
            if kind == "call_absent":
                live.absent_args += 1
                live.breaks[kind] += 1
                continue
            if not row.get("pii_type"):
                live.plain_args[1] += 1
                live.plain_args[0] += int(bool(row.get("intact")))
                if not row.get("intact") and len(live.broken) < dump * 8:
                    live.broken.append(row)
                continue
            live.pii_args[1] += 1
            live.pii_args[0] += int(kind == "ok")
            if row.get("touched"):
                live.touched_args[1] += 1
                live.touched_args[0] += int(kind == "ok")
            live.breaks[kind] += 1
            bucket = live.breaks_by_type[str(row["pii_type"])]
            bucket[1] += 1
            bucket[0] += int(kind == "ok")
            if kind != "ok" and len(live.broken) < dump * 8:
                live.broken.append(row)

        for link in record.get("links") or []:
            row = live.links[str(link.get("kind"))]
            row[1] += 1
            row[0] += int(bool(link.get("held")))

        answer = record.get("answer") or {}
        if answer:
            live.answers[str(answer.get("verdict"))] += 1
            live.judged[1] += 1
            findings = answer.get("findings") or {}
            asked = [one for one in findings.values() if one.get("asked")]
            live.judged[0] += int(bool(asked))
            live.nothing_to_ask += int(bool(answer.get("judged")) and not asked)
            quote = ""
            for finding in findings.values():
                if finding.get("found") and finding.get("quote"):
                    quote = str(finding["quote"])
            if (str(answer.get("verdict")) != "clean"
                    and len(live.verdicts) < dump * 8):
                live.verdicts.append((str(record["id"]),
                                      str(answer.get("verdict")),
                                      str(answer.get("why"))[:120], quote[:90]))
        live.earlier_residual += int(bool(record.get("earlier_turns_residual")))
    return tally, live


# --- the report -----------------------------------------------------------


def _cost_section(records: list[dict[str, object]], by_id: dict[str, schema.Case],
                  ladder: schema.Ladder, ceiling: float, spent: float) -> None:
    print("\n" + "=" * 72)
    print("1. ЦЕНА — измеренная (ResultMessage.total_cost_usd), не оценённая")
    print("=" * 72)
    share = (f"{100.0 * spent / ceiling:.1f}%" if ceiling > 0 else "—")
    agent = sum(float(one.get("agent_cost_usd") or 0.0) for one in records)
    judge = sum(float(one.get("judge_cost_usd") or 0.0) for one in records)
    print(f"   потолок ${ceiling:.2f} · израсходовано ${spent:.4f} ({share})")
    print(f"   агент ${agent:.4f} · судья ${judge:.4f}")
    ran = [one for one in records if float(one.get("cost_usd") or 0.0) > 0.0]
    if not ran:
        print("   ни один случай не дошёл до модели — цены нет")
        return
    costs = [float(one["cost_usd"]) for one in ran]
    print(f"   на случай: среднее ${statistics.mean(costs):.4f} · медиана "
          f"${statistics.median(costs):.4f} · мин ${min(costs):.4f} · "
          f"макс ${max(costs):.4f}")

    print(f"\n   {'ДЛИНА':<8}{'СЛУЧ':>6}{'АГЕНТ':>10}{'СУДЬЯ':>10}{'ВСЕГО':>10}"
          f"{'КАП':>8}")
    print("   " + "-" * 52)
    per_rung: dict[str, float] = {}
    for rung in schema.CONTEXT_RUNGS:
        rows = [one for one in ran if one.get("context") == rung]
        if not rows:
            continue
        mean = statistics.mean(float(one["cost_usd"]) for one in rows)
        per_rung[rung] = mean
        print(f"   {rung:<8}{len(rows):>6}"
              f"{statistics.mean(float(one['agent_cost_usd']) for one in rows):>10.4f}"
              f"{statistics.mean(float(one['judge_cost_usd']) for one in rows):>10.4f}"
              f"{mean:>10.4f}{CAPS.get(rung, 0.0):>8.2f}")

    print("\n   ПРОЕКЦИЯ НА ОСТАЛЬНЫЕ ЯРУСЫ — по СОСТАВУ яруса, не по средней.")
    print("   Ярусы вложены и стратифицированы, доли ступеней в них разные, и")
    print("   средняя, умноженная на размер, врёт тем сильнее, чем длиннее ярус.")
    for name, ids in sorted(ladder.tiers.items(),
                            key=lambda pair: len(pair[1])):
        rungs = Counter(by_id[one].context for one in ids if one in by_id)
        if not rungs:
            continue
        known = sum(count for rung, count in rungs.items() if rung in per_rung)
        projection = sum(per_rung.get(rung, 0.0) * count
                         for rung, count in rungs.items())
        gap = sum(count for rung, count in rungs.items() if rung not in per_rung)
        note = (f" (+{gap} случаев на ступенях, которых этот прогон не мерил)"
                if gap else "")
        print(f"     {name:<7}{len(ids):>5} случаев ≈ ${projection:7.2f}"
              f"  [по {known} измеренным ступеням]{note}")


def _axis1_section(tally: score.Tally, dump: int) -> None:
    print("\n" + "=" * 72)
    print("2. ОСЬ 1. ДЕТЕКЦИЯ — арифметика по спанам, судья не нужен")
    print("=" * 72)
    print("ПОЛНОТА — спан найден И С ТЕМ ЖЕ ТИПОМ. ПОКРЫТИЕ — найден ЦЕЛИКОМ.")
    print("Разница между ними — утёкший хвост, ушедший к модели в открытую.")
    print("Считается тем же счётчиком, что и офлайн: строки сравнимы напрямую.")
    score._cut(tally, "type", list(schema.TYPES) + ["ВСЕГО"], "ТИП")
    score._cut(tally, "register", list(schema.REGISTERS), "РЕГИСТР")
    score._cut(tally, "family", list(schema.FAMILIES), "СЕМЕЙСТВО")
    score._cut(tally, "context", list(schema.CONTEXT_RUNGS), "ДЛИНА")

    if tally.by_selection:
        print(f"\n{'СТРАТА':<14}{'ВХОЖД':>7}{'ПОЛНОТА':>9}{'ПОКРЫТИЕ':>10}")
        print("-" * 40)
        for name in schema.SELECTIONS:
            row = tally.by_selection.get(name)
            if not row or not row[0]:
                continue
            print(f"{name:<14}{row[0]:>7}{score._share(row[1], row[0]):>9}"
                  f"{score._share(row[2], row[0]):>10}")
        recall = schema.weighted_rate(tally.weighted["recall"])
        coverage = schema.weighted_rate(tally.weighted["coverage"])
        print(f"{'взвешенно':<14}{'':>7}{recall * 100:>8.1f}%"
              f"{coverage * 100:>9.1f}%")

    total = tally.negatives.get(("ВСЕГО", "total"), [0, 0])
    if total[1]:
        print(f"\n{'НЕГАТИВЫ':<22}{'ВХОЖД':>7}{'РАЗЛИЧ':>8}{'ЧИСТО':>9}")
        print("-" * 46)
        for family in schema.NEGATIVE_FAMILIES:
            row = tally.negatives.get((family, "family"))
            if not row or not row[1]:
                continue
            print(f"{family:<22}{row[1]:>7}"
                  f"{len(tally.negative_values[(family, 'family')]):>8}"
                  f"{score._share(row[0], row[1]):>9}")
        print("-" * 46)
        print(f"{'ВСЕГО':<22}{total[1]:>7}"
              f"{len(tally.negative_values[('ВСЕГО', 'total')]):>8}"
              f"{score._share(total[0], total[1]):>9}")
    if tally.optional[1]:
        print(f"\nнеобязательные (optional): замаскировано {tally.optional[0]}/"
              f"{tally.optional[1]} — маска не ошибка, пропуск не утечка")
    print(f"диагностика: спанов вне золота и вне негативов: {tally.unclaimed[0]}")

    if tally.misses:
        print(f"\n--- ПРОПУЩЕНО ({len(tally.misses)}) ---")
        for _case_id, kind, value, text in tally.misses[:dump]:
            print(f"  {kind:<9}{value!r:34} в {text[:52]!r}")
    if tally.partials:
        print(f"\n--- НАЙДЕНО ЧАСТИЧНО, ХВОСТ УТЁК ({len(tally.partials)}) ---")
        for _case_id, kind, value, tail in tally.partials[:dump]:
            print(f"  {kind:<9}{value!r:34} к модели ушло {tail!r}")
    if tally.false_masks:
        print(f"\n--- ЗАМАСКИРОВАНО ЗРЯ ({len(tally.false_masks)}) ---")
        for _case_id, value, why, _text in tally.false_masks[:dump]:
            print(f"  {value!r:26} — {why[:44]}")


def _axis2_section(live: LiveTally, dump: int) -> None:
    print("\n" + "=" * 72)
    print("3. ОСЬ 2. ВЫЗОВ ИНСТРУМЕНТА ПРОТИВ ЭТАЛОНА")
    print("=" * 72)
    print("Сверка с ЭТАЛОННЫМ вызовом корпуса, НЕ с плечом без шлюза. Модель")
    print("настоящая, поэтому её собственные промахи отделены: вызова не было —")
    print("это `call_absent`, поведение модели, и в долю шлюза оно не входит.")
    if live.dispatch[1]:
        print(f"\nтот ли инструмент  — контракт цел и имя дожило до подсказки: "
              f"{live.dispatch[0]}/{live.dispatch[1]} = "
              f"{score._share(live.dispatch[0], live.dispatch[1]).strip()}")
    if live.whole_calls[1]:
        print(f"ЭТАЛОННЫЙ ВЫЗОВ ЦЕЛИКОМ — сделан и все судимые аргументы верны: "
              f"{live.whole_calls[0]}/{live.whole_calls[1]} = "
              f"{score._share(live.whole_calls[0], live.whole_calls[1]).strip()}")
        print(f"   из них модель не сделала вовсе: {live.calls_absent} "
              f"(поведение модели) · лишних вызовов: {live.calls_extra}")
    if live.plain_args[1]:
        print(f"те ли аргументы    — без ПД (номер заказа, id клиента), пришли "
              f"дословно: {live.plain_args[0]}/{live.plain_args[1]} = "
              f"{score._share(live.plain_args[0], live.plain_args[1]).strip()}")
    if live.pii_args[1]:
        print(f"настоящее значение — дошло через unmask_arguments: "
              f"{live.pii_args[0]}/{live.pii_args[1]} = "
              f"{score._share(live.pii_args[0], live.pii_args[1]).strip()}")
        print(f"   из них шлюз действительно подменял: {live.touched_args[1]}, "
              f"дошло {live.touched_args[0]}/{live.touched_args[1]} = "
              f"{score._share(live.touched_args[0], live.touched_args[1]).strip()}")
        print("   вторая строка и есть вклад шлюза; первая включает значения,")
        print("   которых он не коснулся — их промах уже посчитан осью 1")
        print(f"\n{'ТИП':<14}{'АРГУМ':>7}{'ДОШЛО':>9}")
        print("-" * 32)
        for kind in schema.TYPES:
            row = live.breaks_by_type.get(kind)
            if not row or not row[1]:
                continue
            print(f"{kind:<14}{row[1]:>7}{score._share(row[0], row[1]):>9}")
    broken = {kind: count for kind, count in live.breaks.items() if kind != "ok"}
    if broken:
        print("\nрасхождения с эталоном:")
        for kind, count in sorted(broken.items(), key=lambda pair: -pair[1]):
            print(f"  {kind:<20}{count:>6}")
    if live.residual_calls:
        print(f"\nВЫЗОВОВ, В КОТОРЫЕ УШЁЛ НАШ ЖЕ ФЕЙК: {live.residual_calls} — "
              f"инструмент отработал 200 по человеку, которого нет")
    if live.unlocatable:
        print(f"аргументов, не найденных в стенограмме: {live.unlocatable} — "
              f"шлюз их не касался, из счёта исключены")
    judged = {name: row for name, row in live.links.items()
              if name in ("same", "different")}
    if judged:
        print("\nсвязи подмен (кому уйдёт вызов):")
        for name, row in sorted(judged.items()):
            label = ("один человек — одна подмена" if name == "same"
                     else "разные люди — разные подмены")
            print(f"  {label:<32}{row[0]}/{row[1]}")
        for name in ("unjudged", "не замаскировано", "вне случая"):
            row = live.links.get(name)
            if row and row[1]:
                print(f"  {name:<32}{row[1]} (не судится)")
    if live.broken:
        print(f"\n--- ЭТАЛОННЫЙ ВЫЗОВ РАЗОШЁЛСЯ ({len(live.broken)}) ---")
        for row in live.broken[:dump]:
            print(f"  {row['case_id']:<22} {row['tool']}.{row['argument']} "
                  f"[{row.get('kind') or 'изменён'}] {row['register']}/"
                  f"{row['family']}")
            print(f"      ждали   {row['expected']!r}")
            print(f"      модель  {row['model_saw']!r}")
            print(f"      пришло  {row['restored']!r}")


def _axis3_section(live: LiveTally, dump: int) -> None:
    print("\n" + "=" * 72)
    print("4. ОСЬ 3. УТЕЧКА В ИТОГОВОМ ОТВЕТЕ — здесь судья главный")
    print("=" * 72)
    print("Ответ агента прогнан через unmask_text и отдан судье двумя")
    print("независимыми query(): «осталось ли настоящее значение» и «выдана ли")
    print("подмена за настоящее». Волт называет факты, модель — то, чего")
    print("строкой не достать: подмену пересказали, склонили, разбили.")
    print(judge_mod.stamp())
    total = sum(live.answers.values())
    if not total:
        print("\n  ни один случай не дошёл до ответа")
        return
    print()
    for verdict in schema.ANSWER_VERDICTS:
        count = live.answers.get(verdict, 0)
        if count:
            print(f"  {verdict:<20}{count:>6}  = {count / total * 100:5.1f}%")
    unjudged = live.answers.get(score.UNJUDGED, 0)
    if unjudged:
        print(f"  {score.UNJUDGED:<20}{unjudged:>6}  = "
              f"{unjudged / total * 100:5.1f}%  считается ОТДЕЛЬНО, "
              f"не как чисто")
    print(f"\n  судья получил вопрос на {live.judged[0]}/{live.judged[1]} "
          f"случаях")
    if live.nothing_to_ask:
        print(f"  на {live.nothing_to_ask} спрашивать было НЕ О ЧЕМ: корпус не "
              f"называет запретных значений И шлюз не отчеканил ни одной")
        print("  подмены. Второе — это промах ОСИ 1, а не чистый ответ, и здесь")
        print("  оно названо, чтобы не читалось как «судья подтвердил чистоту».")
    if live.earlier_residual:
        print(f"  НЕ ТОЛЬКО ИТОГОВЫЙ: в промежуточных репликах подмены уцелели "
              f"в {live.earlier_residual} случаях (детерминированно, по волту)")
    if live.verdicts:
        print(f"\n--- ВЕРДИКТЫ НЕ «ЧИСТО», С ЦИТАТОЙ ({len(live.verdicts)}) ---")
        print("  вердикт без цитаты не засчитывается — иначе неотличимо, судил")
        print("  он текст или своё представление о нём")
        for case_id, verdict, why, quote in live.verdicts[:dump]:
            print(f"  {case_id:<22}{verdict}")
            print(f"      {why}")
            if quote:
                print(f"      цитата: {quote!r}")


def _fragility_section(records: list[dict[str, object]], live: LiveTally,
                       dump: int) -> None:
    print("\n" + "=" * 72)
    print("5. ЧТО ДЕЛАЛО ПРОГОН ХРУПКИМ, И ЧЕГО ОН НЕ ПОКРЫЛ")
    print("=" * 72)
    print("исходы (tau2-bench: инфраструктурные исключаются из долей, но")
    print("печатаются рядом; gateway_5xx — исход продукта и НЕ исключается):")
    for name in schema.TERMINATIONS:
        count = live.terminations.get(name, 0)
        if count:
            excluded = " (исключён из долей)" if name in schema.EXCLUDED_TERMINATIONS else ""
            print(f"  {name:<16}{count:>4}{excluded}")
    if live.refused_budget:
        print(f"\nНЕ ВЛЕЗЛИ В ПОТОЛОК: {live.refused_budget} случаев. Они "
              f"ПОМЕЧЕНЫ НЕПОЛНЫМИ, а не выброшены —")
        print("прогон, тихо роняющий дорогое, отчитывается по дешёвому, а "
              "дешёвое — это короткое")
        print("и чистое, то есть та популяция, где у нас и так всё хорошо.")
    incomplete = [one for one in records if one.get("status") != "complete"]
    if incomplete:
        print(f"\nНЕЗАВЕРШЁННЫХ {len(incomplete)} (учтены, не выброшены):")
        for one in incomplete[:dump]:
            print(f"  {str(one['id']):<24}{str(one.get('reason'))[:70]}")
    troubles: "Counter[str]" = Counter()
    for one in records:
        if one.get("api_error_status"):
            troubles[f"HTTP {one['api_error_status']}"] += 1
        for error in one.get("errors") or []:
            troubles[str(error)[:60]] += 1
    if troubles:
        print("\nошибки провайдера:")
        for name, count in troubles.most_common():
            print(f"  {name}: {count}")
    walls = [float(one["wall_s"]) for one in records if one.get("wall_s")]
    if walls:
        print(f"\nстена на случай: медиана {statistics.median(walls):.1f}s · "
              f"макс {max(walls):.1f}s")


def _report(payload: dict[str, object], records: list[dict[str, object]],
            by_id: dict[str, schema.Case], ladder: schema.Ladder,
            dump: int) -> int:
    tally, live = _aggregate(records, by_id, dump)
    print()
    print("=" * 72)
    print(f"AgentPII-RU v3 · ЖИВОЙ ПРОГОН · агент {payload['model']} · "
          f"судья {payload['judge_model']}")
    print(f"прогон {payload['run_id']} · ярус {payload['tier']} · "
          f"{len(records)} случаев · корпус {str(payload['digest'])[:12]}")
    print("ОДНО ПЛЕЧО: только через шлюз, сверка с ЭТАЛОНОМ. Оси «прозрачность»")
    print("здесь нет и не будет — как модель пользуется инструментами, этот")
    print("бенчмарк не меряет.")
    print("=" * 72)
    _cost_section(records, by_id, ladder, float(payload["ceiling_usd"]),
                  float(payload["spent_usd"]))
    _axis1_section(tally, dump)
    _axis2_section(live, dump)
    _axis3_section(live, dump)
    _fragility_section(records, live, dump)
    bound = schema.TIER_ZERO_FAILURE_BOUND.get(str(payload["tier"]))
    if bound is not None:
        print(f"\nна ярусе {payload['tier']} ноль отказов означает не "
              f"«безошибочно», а «истинная доля отказов ниже "
              f"{bound * 100:.2f}% с 95%»")
    print("ось 1 воспроизводится побитово: детекция детерминирована. оси 2 и 3")
    print("гуляют — подмены чеканятся случайно (secrets), а модель недетерминирована.")
    incomplete = sum(1 for one in records if one.get("status") != "complete")
    return 0 if not incomplete else 1


# --- entry point ----------------------------------------------------------


def _load(path: Path) -> tuple[list[schema.Case], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ([schema.case_from_json(raw) for raw in payload["corpus"]],
            str(payload["digest"]))


def _ladder(path: Path) -> schema.Ladder:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return schema.Ladder(
        version=int(raw["version"]), seed=int(raw["seed"]),
        corpus_sha256=str(raw["corpus_sha256"]),
        tiers={name: tuple(ids) for name, ids in raw["tiers"].items()})


def main() -> int:
    here = _HERE.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?",
                        default=str(here.parent / "corpus.json"))
    parser.add_argument("--ladder", default=str(here.parent / "ladder.json"))
    parser.add_argument("--tier", default="nano", choices=sorted(schema.TIER_SIZES))
    parser.add_argument("--ids", default="",
                        help="запятые: точный список случаев вместо яруса")
    parser.add_argument("--ceiling", type=float, default=3.0,
                        help="потолок трат на весь прогон, USD (агент + судья)")
    parser.add_argument("--model", default=AGENT_MODEL)
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0,
                        help="база на случай; +20с на каждый ход пользователя")
    parser.add_argument("--out", default=str(here / "runs"))
    parser.add_argument("--dump", type=int, default=12)
    parser.add_argument("--report", default="",
                        help="пересобрать отчёт из сохранённого JSONL, "
                             "без модели и без трат")
    args = parser.parse_args()

    everything, digest = _load(Path(args.corpus))
    by_id = {case.id: case for case in everything}
    ladder = _ladder(Path(args.ladder))

    if args.report:
        source = Path(args.report)
        records = [json.loads(line) for line in
                   source.read_text(encoding="utf-8").splitlines() if line.strip()]
        meta = source.with_suffix(".meta.json")
        payload: dict[str, object] = (
            json.loads(meta.read_text(encoding="utf-8")) if meta.exists()
            else {"run_id": source.stem, "model": args.model,
                  "judge_model": args.judge_model, "tier": args.tier,
                  "digest": digest, "ceiling_usd": args.ceiling})
        payload["spent_usd"] = round(
            sum(float(one.get("cost_usd") or 0.0) for one in records), 6)
        return _report(payload, records, by_id, ladder, args.dump)

    if args.ids:
        wanted = [one.strip() for one in args.ids.split(",") if one.strip()]
        missing = [one for one in wanted if one not in by_id]
        if missing:
            print(f"нет таких случаев: {missing}", file=sys.stderr)
            return 2
        cases = [by_id[one] for one in wanted]
        tier_name = "ids"
    else:
        cases = schema.tier(everything, ladder, args.tier)
        tier_name = args.tier
    if not cases:
        print("выборка пуста", file=sys.stderr)
        return 2

    # A `preceded_by` lead outside the selection is masked into the same vault
    # WITHOUT a model call: the claim it supports is about the vault, and running
    # it live would double its cost to measure nothing.
    selected = {case.id for case in cases}
    leads = {case.id: by_id[case.preceded_by] for case in cases
             if case.preceded_by and case.preceded_by in by_id
             and case.preceded_by not in selected}

    load_dev_bundle()
    detector = Detector()
    run_id = str(uuid.uuid4())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sink = out / f"{run_id}.jsonl"
    ledger = judge_mod.SpendLedger(out / f"{run_id}.spend.tsv", args.ceiling)
    config = judge_mod.JudgeConfig(
        model=args.judge_model, ledger=ledger,
        query_cap_usd=judge_mod.QUERY_CAP_USD, retries=judge_mod.RETRIES,
        trace_path=out / f"{run_id}.judge.jsonl")

    payload = {
        "run_id": run_id, "model": args.model, "judge_model": args.judge_model,
        "tier": tier_name, "digest": digest, "ceiling_usd": args.ceiling,
        "started": datetime.now(timezone.utc).isoformat(),
        "ids": [case.id for case in cases], "spent_usd": 0.0,
    }
    # WRITTEN BEFORE THE FIRST DOLLAR. A run killed by a shell timeout must
    # still name itself, its ceiling and its case list on disk.
    (out / f"{run_id}.meta.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"прогон {run_id} · агент {args.model} · судья {args.judge_model} · "
          f"{len(cases)} случаев · потолок ${args.ceiling:.2f}", flush=True)
    print(f"инкрементальная запись: {sink}", flush=True)
    started = time.time()
    records = asyncio.run(_drive(_chains(cases), leads, detector, ledger, config,
                                 args.model, run_id, args.timeout,
                                 args.concurrency, sink))
    order = {case.id: index for index, case in enumerate(cases)}
    records.sort(key=lambda one: order.get(str(one["id"]), 0))

    payload["finished"] = datetime.now(timezone.utc).isoformat()
    payload["spent_usd"] = round(ledger.committed(), 6)
    payload["wall_s"] = round(time.time() - started, 1)
    payload["cases"] = records
    (out / f"{run_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    code = _report(payload, records, by_id, ladder, args.dump)
    print(f"\nрезультат: {out / (run_id + '.json')}")
    print(f"по случаям: {sink}")
    print(f"след судьи: {out / (run_id + '.judge.jsonl')}")
    return code


if __name__ == "__main__":
    sys.exit(main())
