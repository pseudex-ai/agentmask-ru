"""Поверхность обратного прокси: `POST /v1/chat/completions`, ключ `sk-ps-…`.

ЧТО В НЕЙ ЕСТЬ, ЧЕГО НЕТ НИ У ОДНОЙ ДРУГОЙ. У прокси НЕТ ПОЛЯ для
`conversation_id`: его провод — это чат-API OpenAI, а там такого поля нет. Ключ
разговора он ВСЕГДА выводит из транскрипта (`envelope.conversation_key` — sha256
первых двух сообщений). Поэтому «разговор не назван» на этой поверхности
недостижимо по построению: разговор назван всегда, просто называет его не хост,
а хэш. Это и есть суть поверхности, и `honours_conversation_id = False` — её
объявление.

ОТСЮДА ВЫТЕКАЕТ ЦЕНА, И ЕЁ НАДО ЗНАТЬ, ЧИТАЯ СТОЛБЕЦ. Подмену чеканит
`Engine.mint` — общая на все поверхности (иначе четыре столбца сравнивались бы
по разным подменам), и она пишет в волт `tokens.minted_in` — разговор, В КОТОРОМ
подмена выдана. Восстановление ищет КУСОК только среди строк своего разговора
(`Vault._fragment_scopes`), и «своего» здесь значит `minted_in = <разговор
восстановления>` ЛИБО `minted_in` пустой. Отсюда три клетки столбца читаются
по-разному, и ни одна не читается как у сайдкара:

  разговор назван      чеканка положила `minted_in = "probe-<случай>"`, прокси
                       спрашивает под своим выведенным ключом — не совпадает
                       никогда, поэтому КУСОК не резолвится в принципе. Целая
                       подмена резолвится: она уникальна и мимо этих поисков.
  разговор не назван   чеканка положила `minted_in = ""`, а пустой совпадает с
                       любым разговором — значит спрашивается весь волт с
                       правилом единственного кандидата. Ровно та дверь, в
                       которую Б29 и ходит.
  память агента        `pseudonym_scope=customer` у прокси — настройка ПРОЦЕССА
                       (`PSEUDEX_PSEUDONYM_SCOPE`), а не поле запроса; прибор
                       выставляет её на время клетки (см. `_at_scope`).

ПОЧЕМУ ЭТО НЕ ЧИНИТСЯ ВНУТРИ ШВА. Родная конфигурация прокси — это когда
чеканка и восстановление идут В ОДНОМ вызове под одним выведенным ключом.
Получить её здесь нельзя: `carry` не чеканит (правило шва №1), а `minted_in`
пишется один раз, в момент чеканки. Поэтому столбец «прокси» — это ВЕРХНЯЯ
ОЦЕНКА потерь на куске, и сравнивать его клетку с клеткой сайдкара можно только
в колонке «разговор не назван». Сказано здесь, потому что число без этой фразы
прочли бы как «прокси теряет вдвое больше».

ЧТО ЕЩЁ ОТЛИЧАЕТ ЭТУ РУЧКУ: ОСТАТОК — ЧИСЛО, А НЕ ИМЕНА. Ответ прокси обязан
остаться OpenAI-формы, поэтому сигнал едет в заголовке `X-Pseudex-Residual` и
несёт ДЛИНУ списка, а не список. Приписать остаток конкретному куску нечем,
поэтому `reports_residual = False`: все отказы этой поверхности печатаются
тихими. Число из заголовка не выбрасывается — оно копится в `header_counts`,
и `test_instrument.py` требует, чтобы оно шевелилось: слепота этой клетки
ДОЛЖНА быть слепотой к АДРЕСАТУ, а не к самому факту.

МОДЕЛЬ ЗДЕСЬ — СВОЙ HTTP-СЕРВЕР, И ОТВЕТ ЕДЕТ К НЕЙ В ТЕЛЕ ЗАПРОСА. Прокси сам
ходит к провайдеру, значит имитированный агент живёт ВЫШЕ прокси, и прибор
обязан его подставить. Что именно «модель» скажет, она узнаёт из поля
`pseudex_fragments_reply` того же запроса: прокси маскирует `messages` и
`tools`, а прочие ключи тела передаёт апстриму дословно. Альтернатива — общий
словарь «идентификатор → ответ» между потоками — отвергнута: идентификатор
пришлось бы положить в сообщения, то есть в текст, который движок обязан
разобрать, и выдуманный нами маркер стал бы ещё одним кандидатом на обнаружение.
"""

import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import ModuleType

# `uvicorn` конфигурации из окружения не читает — поэтому наверху, как все
# импорты. Наверх нельзя ровно `pseudex.proxy`: он читает окружение на ИМПОРТЕ,
# а полно оно только после `Engine.start`.
import uvicorn

from bench.fragments.engine import Engine, EngineError
from bench.fragments.surfaces import Passage, Returned, Scope

# Ключ тела, которым имитированный агент передаёт «модели» её реплику.
REPLY_FIELD = "pseudex_fragments_reply"
# Первое сообщение запроса. Из него (и только из него) прокси выводит ключ
# разговора. Нейтральное и без единой цифры НАМЕРЕННО: всё, что сюда положено,
# проходит через детектор, и выдуманный нами идентификатор случая стал бы либо
# кандидатом в ИНН, либо кандидатом в секрет. Разговор прокси здесь ничего не
# решает — решает `minted_in`, записанный при чеканке (см. докстроку модуля).
PROMPT = "Оформите заказ по данным из карточки клиента."
UPSTREAM_KEY = "fragments-upstream-key"
RESIDUAL_HEADER = "X-Pseudex-Residual"


def _hush_per_request_logs() -> None:
    """Заткнуть ДВА журнала, которые шумят ровно пропорционально этой поверхности.

    `pseudex` пишет INFO на каждое сообщение, уходящее апстриму (это его след
    доказательства «настоящие ПД провод не пересекали»), а `httpx` — строку на
    каждый запрос к «модели». На полутора тысячах вызовов отчёт тонет в них
    целиком. Глушится ровно INFO и ровно у этих двух: поднять порог всему
    корню значило бы спрятать предупреждения лицензии, которые прибор обязан
    показывать, — они приходят WARNING и остаются видимы.
    """
    for name in ("pseudex", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _free_port() -> int:
    """Свободный порт. Своя копия, а не приватная функция чужого модуля: три
    строки дешевле связи, которая рвётся от переименования."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _ModelHandler(BaseHTTPRequestHandler):
    """«Провайдер»: возвращает ровно ту реплику, которую ему прислали в теле."""

    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        """Тишина. Иначе каждый вызов печатает строку в stderr и прогон тонет."""

    def _answer(self, status: int, payload: Mapping[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 — имя задано базовым классом
        if self.path != "/v1/chat/completions":
            # Явный отказ, а не 404 по умолчанию: прокси, постучавший не туда,
            # обязан сказать об этом словами, а не превратиться в 502.
            self._answer(400, {"error": f"поддельный апстрим знает только "
                                        f"/v1/chat/completions, спросили {self.path}"})
            return
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        reply = request.get(REPLY_FIELD)
        if not isinstance(reply, dict):
            self._answer(400, {"error": f"в теле нет {REPLY_FIELD} — реплику "
                                        f"имитированного агента взять неоткуда"})
            return
        self._answer(200, {
            "id": "fragments-1",
            "object": "chat.completion",
            "created": 0,
            "model": request.get("model", ""),
            "choices": [{
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    # None, а не "": пустая строка — это контент, который движок
                    # обязан восстановить, и остаток вызова смешался бы с
                    # остатком прозы в одном заголовке.
                    "content": None,
                    "tool_calls": [{
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": reply["tool"],
                                     "arguments": reply["arguments"]},
                    }],
                },
            }],
        })


class ProxySurface:
    """Обратный прокси, поднятый целиком: «модель», сам прокси и тенант на орг.

    Класс-коннектор к внешнему состоянию (два процесса-сервера, таблица
    тенантов) — ровно тот случай, для которого правило репозитория класс и
    допускает.
    """

    name = "proxy"
    # Читается по вызову инструмента: именно туда уезжает переписанное число
    # заказчика, и именно эту клетку сравнивают с колонкой «argument».
    carries_fields = True
    carries_prose = False
    # Заголовок несёт ЧИСЛО, а не имена. См. докстроку модуля.
    reports_residual = False
    honours_conversation_id = False

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._keys: dict[str, str] = {}
        _hush_per_request_logs()
        self.header_counts: list[int] = []
        self._model_port = _free_port()
        self._proxy_port = _free_port()
        self._start_model()
        self._proxy = self._start_proxy()

    @property
    def upstream_base_url(self) -> str:
        return f"http://127.0.0.1:{self._model_port}/v1"

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._proxy_port}"

    def _start_model(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", self._model_port), _ModelHandler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()

    def _start_proxy(self) -> ModuleType:
        """Настоящий `pseudex.proxy` на петле, со своим жизненным циклом.

        Именно сервером, а не ASGI-транспортом в памяти: аренду берёт `lifespan`,
        а ASGI-транспорт его не запускает — пришлось бы выдавать лицензию руками,
        то есть мерить прокси, который в продукте не живёт.
        """
        import pseudex.proxy as proxy  # noqa: PLC0415 — читает окружение на импорте

        server = uvicorn.Server(uvicorn.Config(
            proxy.app, host="127.0.0.1", port=self._proxy_port, log_level="error"))
        threading.Thread(target=server.run, daemon=True).start()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if server.started:
                return proxy
            time.sleep(0.05)
        raise EngineError("обратный прокси не поднялся за 60 секунд")

    def _key(self, org_id: str) -> str:
        """Ключ `sk-ps-…` этого орга. Тенант выпускается с `customer_id = org_id`,
        и это единственное, чем прокси попадает в ТОТ ЖЕ волт, что сайдкар:
        `proxy._get_vault` берёт волт по `tenant.customer_id`."""
        key = self._keys.get(org_id)
        if key is None:
            key = self._proxy.TENANTS.issue(org_id, self.upstream_base_url, UPSTREAM_KEY)
            self._keys[org_id] = key
        return key

    def _at_scope(self, pseudonym_scope: str) -> None:
        """Объявить область псевдонимов так, как её объявляет заказчик, — процессом.

        У прокси нет поля запроса для `pseudonym_scope` и не будет: его провод —
        чат-API OpenAI. Настройка живёт в `PSEUDEX_PSEUDONYM_SCOPE` и читается
        модулем на импорте, поэтому переменной окружения здесь уже не обойтись —
        прибор выставляет ту же величину прямо в модуле. Оставить её
        неподвижной было бы хуже: строка таблицы с надписью «память агента»
        печаталась бы результатом прогона БЕЗ памяти, то есть клетка врала бы
        именем. Вызовы прибора идут по одному, и область постоянна внутри блока
        клетки, поэтому присваивание не может застать чужой запрос в полёте.
        """
        if not hasattr(self._proxy, "_PSEUDONYM_SCOPE"):
            raise EngineError(
                "pseudex.proxy больше не хранит область псевдонимов в "
                "_PSEUDONYM_SCOPE — столбец прокси нечем поставить в клетку")
        self._proxy._PSEUDONYM_SCOPE = pseudonym_scope

    def _post(self, org_id: str, body: Mapping[str, object]) -> tuple[dict[str, object], int]:
        request = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._key(org_id)}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as answer:
                residual = answer.headers.get(RESIDUAL_HEADER, "0")
                return json.loads(answer.read().decode("utf-8")), int(residual)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            raise EngineError(
                f"прокси ответил {error.code}: {detail} · тело запроса "
                f"{json.dumps(body, ensure_ascii=False)[:500]}") from error

    def carry(self, org_id: str, passage: Passage, scope: Scope) -> Returned:
        """Один ход агента через прокси: маска на входе, восстановление на выходе.

        `scope.conversation_id` не отправляется никуда и не может быть отправлен
        — см. докстроку модуля. Это не пропуск в реализации, а то, что эта
        поверхность и меряет.
        """
        self._at_scope(scope.pseudonym_scope)
        answer, residual = self._post(org_id, {
            "model": "fragments-mock",
            "messages": [{"role": "user", "content": PROMPT}],
            REPLY_FIELD: {"tool": passage.tool_name,
                          "arguments": passage.arguments_json()},
        })
        self.header_counts.append(residual)
        calls = answer["choices"][0]["message"]["tool_calls"]
        if len(calls) != 1:
            raise EngineError(f"прокси вернул не один вызов инструмента: {answer}")
        restored = json.loads(calls[0]["function"]["arguments"])
        if not isinstance(restored, dict):
            raise EngineError(f"прокси вернул аргументы не объектом: {calls[0]}")
        return Returned(
            surface=self.name,
            fields=tuple((str(key), str(value)) for key, value in restored.items()),
            prose="",
            residual=(),
        )
