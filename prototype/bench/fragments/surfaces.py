"""ШОВ ПРИБОРА: поверхность — это объект с одним методом «проведи и верни, что вернулось».

Четыре поверхности движка отвечают на один и тот же вопрос («этот кусок — моя
подмена?») и платят за ответ по-разному, поэтому клетка таблицы — это (сторона ×
ПОВЕРХНОСТЬ × область × наполненность). Здесь лежат две: аргумент инструмента и
проза ответа. Поток (`/unmask_chunk`) и обратный прокси (`POST
/v1/chat/completions`) добавляются ВТОРЫМ агентом и НЕ ТРЕБУЮТ правки ни одного
файла этого каталога — контракт ниже и есть весь шов.

ЧТОБЫ ПОДКЛЮЧИТЬСЯ, второй агент кладёт рядом `extra_surfaces.py` с функцией

    def surfaces(engine: Engine) -> tuple[Surface, ...]

и реализует в ней `Surface`. Больше ничего: `available()` подхватит её сам,
`measure.py` прогонит её поверхности по всем клеткам, а `README.md` описывает
контракт дословно.

ПОЧЕМУ ЧЕКАНКА НЕ ЧАСТЬ ЭТОГО ИНТЕРФЕЙСА. Подмену чеканит `Engine.mint` — одна
на все поверхности, потому что волт один и общий по `(customer, canonical)`.
Если бы каждая поверхность чеканила своё, четыре столбца таблицы сравнивались бы
по разным подменам, а разница между ними читалась бы как разница поверхностей.
Обратный прокси видит тот же волт, когда его тенант назван именем клетки.

ПОЧЕМУ ПРИЗНАКИ ПОВЕРХНОСТИ ОБЪЯВЛЯЮТСЯ, А НЕ ВЫВОДЯТСЯ. `reports_residual`
и `honours_conversation_id` — это утверждения о самой ручке: `/unmask_chunk` не
отдаёт остаток ни в теле, ни в заголовке, а обратный прокси всегда выводит ключ
разговора из транскрипта. Клетка, слепая по построению, обязана печататься как
слепая, а не как чистая: «прибор, который не может провалиться, — не прибор».
"""

import importlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from bench.fragments.engine import Engine, EngineError

SIDE_OURS = "ours"
SIDE_FOREIGN = "foreign"


@dataclass(frozen=True)
class Scope:
    """Область, в которой шлюз задаёт вопрос о принадлежности куска."""

    name: str
    conversation_id: str
    pseudonym_scope: str


@dataclass(frozen=True)
class Passage:
    """Ровно то, что написал имитированный агент, во всех представлениях.

    Оба представления несут ОДНИ И ТЕ ЖЕ куски: поверхность берёт своё. Это не
    флаг-переключатель, а запись с несколькими полями — аргументная поверхность
    читает `fields`, прозаическая `prose`, потоковая режет `prose` на дельты,
    прокси кладёт в ответ и то и другое.
    """

    tool_name: str
    fields: tuple[tuple[str, str], ...]
    prose: str

    def arguments_json(self) -> str:
        return json.dumps(dict(self.fields), ensure_ascii=False)


@dataclass(frozen=True)
class Returned:
    """Что вернулось заказчику после восстановления."""

    surface: str
    fields: tuple[tuple[str, str], ...]
    prose: str
    residual: tuple[str, ...]


@runtime_checkable
class Surface(Protocol):
    """Одна поверхность движка. Один метод: провести и вернуть, что вернулось."""

    name: str
    carries_fields: bool
    carries_prose: bool
    reports_residual: bool
    honours_conversation_id: bool

    def carry(self, org_id: str, passage: Passage, scope: Scope) -> Returned:
        ...


def _residual_of(answer: Mapping[str, object]) -> tuple[str, ...]:
    found = answer.get("residual_tokens", ())
    if not isinstance(found, list):
        return ()
    return tuple(str(one) for one in found)


class ToolArgumentSurface:
    """`POST /unmask_arguments` — аргументы вызова инструмента, собранные шлюзом.

    Один JSON на вызов, а не поле за полем, и это несущее: предшественники слали
    `street` и `house` ПОРОЗНЬ, поэтому не видели ни того, что разложенный по
    полям адрес восстанавливается целиком, ни того, что он перестал.
    """

    name = "argument"
    carries_fields = True
    carries_prose = False
    reports_residual = True
    honours_conversation_id = True

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def carry(self, org_id: str, passage: Passage, scope: Scope) -> Returned:
        body: dict[str, object] = {
            "org_id": org_id,
            "arguments": [passage.arguments_json()],
            "pseudonym_scope": scope.pseudonym_scope,
        }
        if scope.conversation_id:
            body["conversation_id"] = scope.conversation_id
        answer = self._engine.post("/unmask_arguments", body)
        arguments = answer.get("arguments")
        if not isinstance(arguments, list) or len(arguments) != 1:
            raise EngineError(f"/unmask_arguments вернул не один аргумент: {answer}")
        restored = json.loads(arguments[0])
        if not isinstance(restored, dict):
            raise EngineError(f"/unmask_arguments вернул не объект: {arguments[0]!r}")
        return Returned(
            surface=self.name,
            fields=tuple((str(key), str(value)) for key, value in restored.items()),
            prose="",
            residual=_residual_of(answer),
        )


class ProseSurface:
    """`POST /unmask` — проза ответа, та, которую читает человек.

    Отдельная поверхность, а не «тот же случай другими словами»: в прозе движок
    восстанавливает в согласовании, а в аргументе — дословно в форме агента, так
    что одно и то же решение о принадлежности куска стоит здесь разного.
    """

    name = "prose"
    carries_fields = False
    carries_prose = True
    reports_residual = True
    honours_conversation_id = True

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def carry(self, org_id: str, passage: Passage, scope: Scope) -> Returned:
        body: dict[str, object] = {
            "org_id": org_id,
            "response": {"choices": [{"index": 0, "message": {
                "role": "assistant", "content": passage.prose}}]},
            "pseudonym_scope": scope.pseudonym_scope,
        }
        if scope.conversation_id:
            body["conversation_id"] = scope.conversation_id
        answer = self._engine.post("/unmask", body)
        response = answer.get("response")
        if not isinstance(response, dict):
            raise EngineError(f"/unmask вернул не объект: {answer}")
        content = response["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise EngineError(f"/unmask вернул не строку в прозе: {response}")
        return Returned(
            surface=self.name,
            fields=(),
            prose=content,
            residual=_residual_of(answer),
        )


def _extra(engine: Engine) -> tuple[Surface, ...]:
    """Поверхности второго агента, если он их уже положил.

    Ловится РОВНО отсутствие ровно этого модуля и ничего больше: сломанный
    `extra_surfaces.py` обязан упасть с собственной ошибкой, а не исчезнуть из
    таблицы, оставив клетки пустыми и зелёными.
    """
    name = "bench.fragments.extra_surfaces"
    # `importlib`, а не `from ... import ...`: отсутствие подмодуля пакета второй
    # формой приходит как `ImportError` без имени, и отличить «второй агент ещё
    # не положил файл» от «файл есть и падает» стало бы невозможно.
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name == name:
            return ()
        raise
    built = module.surfaces(engine)
    for one in built:
        if not isinstance(one, Surface):
            raise EngineError(
                f"extra_surfaces.surfaces() вернул {one!r}, который не реализует Surface")
    return tuple(built)


def available(engine: Engine) -> tuple[Surface, ...]:
    """Все поверхности этого прогона: две здешние плюс всё, что принёс второй агент."""
    mine: Sequence[Surface] = (ToolArgumentSurface(engine), ProseSurface(engine))
    return tuple(mine) + _extra(engine)
