"""Model I/O contracts. Benchmark semantics do not belong to a connector."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeAlias

Json: TypeAlias = str | int | float | bool | None | list["Json"] | dict[str, "Json"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Json]


@dataclass(frozen=True)
class ToolResult:
    text: str
    success: bool


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_usd: float
    cost_basis: str


@dataclass(frozen=True)
class Conversation:
    replies: tuple[str, ...]
    usage: Usage
    turns: int
    session_id: str
    duration_ms: int


class DialogueHooks(Protocol):
    def user(self, index: int) -> str: ...
    def assistant(self, text: str) -> None: ...
    def response(self, text: str) -> None: ...
    def tool(self, name: str, arguments: dict[str, Json]) -> ToolResult: ...


class AgentConnector(Protocol):
    async def converse(self, system: str, tools: tuple[ToolSpec, ...],
                       user_indices: tuple[int, ...], hooks: DialogueHooks,
                       timeout_s: float, max_calls: int) -> Conversation: ...


class JudgeConnector(Protocol):
    async def evaluate(self, system: str, prompt: str,
                       schema: dict[str, Json], timeout_s: float) -> Conversation: ...


class ConnectorError(RuntimeError):
    """A connector failed, independently of the gateway under test."""


class ConnectorLimit(ConnectorError):
    """A configured turn, tool, token or request limit was reached."""


def json_value(value: object) -> Json:
    """Validate the JSON boundary instead of accepting arbitrary SDK objects."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {str(key): json_value(item) for key, item in value.items()}
    raise ConnectorError(f"non-JSON transport value: {type(value).__name__}")


def json_object(value: object) -> dict[str, Json]:
    converted = json_value(value)
    if not isinstance(converted, dict):
        raise ConnectorError("expected JSON object")
    return converted


ToolHandler: TypeAlias = Callable[[str, dict[str, Json]], ToolResult]
