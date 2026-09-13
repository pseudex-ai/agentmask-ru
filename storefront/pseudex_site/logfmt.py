"""Логи как JSON с полями, а не как строка, из которой потом выковыривают смысл.

ЗАЧЕМ. `_log.error("payment %s underpays %s: %s < %s", ...)` читается человеком и
НЕ ищется машиной: чтобы найти всё по одной организации, нужна регулярка, которая
знает порядок аргументов в каждом вызове. В Loki это превращает поиск в `grep` с
веб-интерфейсом — то есть в то же, что `docker logs`, только медленнее.

С полями вопрос «что происходило со счётом PS-2026-09-0614a28b» — это один
фильтр, и он работает одинаково для витрины, биллинга и лицензионного сервера.

ЧТО ТОЧНО НЕ ПОПАДАЕТ В ЛОГ. Продукт существует ради того, чтобы персональные
данные не оказывались там, где их не ждут; собственный лог — ровно такое место.
Поэтому поля добавляются ЯВНО через `extra=`, а не автоматическим сбором
локальных переменных: автоматика однажды вынесет в лог `email`, и заметит это
никто, потому что лог никто не читает построчно.

ФОРМАТ ВЫБИРАЕТСЯ ОКРУЖЕНИЕМ. В разработке JSON мешает читать; `PSEUDEX_LOG_JSON`
по умолчанию выключен локально и включён в контейнере.
"""

import datetime
import json
import logging

# Поля записи, которые logging кладёт сам. Всё, что НЕ здесь, — это то, что
# добавил вызывающий через `extra=`, и именно оно интересно.
_STANDARD = frozenset((
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
    "message", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "taskName", "thread", "threadName",
))


class JsonFormatter(logging.Formatter):
    """Одна запись — одна строка JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.datetime.fromtimestamp(
                record.created, datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # ПОЛЯ ВЫЗЫВАЮЩЕГО ИДУТ ПОВЕРХ, НО НЕ ЗАТИРАЮТ СЛУЖЕБНЫЕ. `extra={"msg":
        # ...}` — реальная ошибка, и запись, потерявшая собственное сообщение,
        # выглядит в Loki как пустая строка с правильным временем.
        for key, value in record.__dict__.items():
            if key in _STANDARD or key.startswith("_") or key in payload:
                continue
            payload[key] = value if isinstance(
                value, (str, int, float, bool, type(None))) else repr(value)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        # `default=str` — ПОСЛЕДНЯЯ ЗАЩИТА, А НЕ ОСНОВНАЯ. Значения уже
        # приведены выше; это ловит только то, что пролезло служебным полем.
        # Исключение внутри форматтера означает потерянную строку лога, и
        # теряется она ровно в аварии, когда пишут больше обычного.
        return json.dumps(payload, ensure_ascii=False, default=str)


# ── ИДЕНТИФИКАТОР ЗАПРОСА ───────────────────────────────────────────────────
#
# САМОЕ ЦЕННОЕ ПОЛЕ, И ЕГО НЕВОЗМОЖНО ДОБАВИТЬ ПОЗЖЕ РУКАМИ. Одна регистрация
# порождает записи в четырёх местах — вью, сервисах, биллинге, воронке, — и без
# общего идентификатора «что произошло с этим человеком» собирается по времени,
# то есть неправильно, как только запросов больше одного в секунду.
#
# `ContextVar`, А НЕ ПОЛЕ ЗАПРОСА: логирующий код не видит request и не должен
# — иначе каждая функция ниже вью обязана принимать его аргументом ради логов.
# Django выполняет запрос в одном контексте, и asgiref сохраняет контекст при
# уходе в тредпул, поэтому значение доезжает до самого низа.

import contextvars
import uuid

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    """Подставляет текущий идентификатор запроса в КАЖДУЮ запись.

    Фильтр, а не обязанность вызывающего: поле, которое надо не забыть, забудут
    ровно там, где оно понадобится.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        current = request_id.get()
        if current:
            record.rid = current
        return True


class RequestIdMiddleware:
    """Идентификатор на каждый запрос, и он же уходит в ответ.

    ЗАГОЛОВОК В ОТВЕТЕ — НЕ УКРАШЕНИЕ. Клиент, приславший «у меня не
    открывается», называет строку из заголовка, и она находит ровно его запрос
    вместо получаса чтения логов вокруг названного времени.

    ЧУЖОЙ `X-Request-ID` НЕ ПРИНИМАЕТСЯ. Он приходит из интернета, значит его
    содержимое выбирает посторонний: подставленный перевод строки разрежет
    запись лога надвое, а повторяющееся значение склеит чужие запросы в один.
    Свой, всегда.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        token = request_id.set(uuid.uuid4().hex[:16])
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id.get()
            return response
        finally:
            request_id.reset(token)
