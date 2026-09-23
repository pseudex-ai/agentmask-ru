"""Настоящий движок, поднятый один раз и управляемый так, как им управляет шлюз заказчика.

ПРОДУКТОВЫЙ ПУТЬ, А НЕ РУЧНАЯ ЗАПИСЬ В ВОЛТ. Подмену чеканит `POST /mask` —
та же ручка, тот же детектор, тот же волт, что в образе. Альтернатива —
положить пару «настоящее → фейк» прямо в `Vault` — отвергнута: она меряет
восстановление на записи, которой чеканка никогда не делала (другой ключ,
другая область, другой LINKED-ряд), и ровно этой подменой понятий бенчмарк
AgentPII уже однажды сообщил ~180 несуществующих поломок телефона.

КАК ПРИБОР УЗНАЁТ ОТЧЕКАНЕННУЮ ПОДМЕНУ. Каждое настоящее значение едет в
отдельном сообщении с фиксированной русской подводкой («Телефон клиента: »),
и подмена — это ровно остаток замаскированного сообщения после подводки.
Подводка выбрана так, чтобы движок её не трогал; если тронул — это `MintFailed`,
а не тихая подстановка. Читать подмену через `/spans` нельзя: `peek_token` там
спрашивается у волта БЕЗ области разговора, то есть ответ на другой вопрос.
"""

import json
import os
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

# `uvicorn` конфигурации из окружения не читает, поэтому живёт наверху, как все
# импорты. Наверх нельзя ровно `pseudex.service`, `licensing.server` и `testkit`
# — они читают её на ИМПОРТЕ, а окружение полно только внутри `start`.
import uvicorn


class EngineError(RuntimeError):
    """Движок ответил не тем, на что прибор имеет право рассчитывать."""


class SubstituteCoincided(EngineError):
    """Отчеканенная подмена совпала с настоящим значением.

    Не поломка движка, а редкое законное событие (его меряет
    `test_collisions.py`), но для ЭТОГО прибора случай становится неизмеримым:
    нечего терять и нечего возвращать. Собственный класс, а не разбор текста
    сообщения: отличать одну ошибку от другой по подстроке — это связь, которая
    рвётся от правки формулировки и молчит об этом.
    """


class MintFailed(EngineError):
    """Чеканка не состоялась или её результат нечитаем.

    Поднимается явно и останавливает прогон: случай, для которого подмена
    неизвестна, нельзя ни провести, ни зачесть — зачтённый молча, он стал бы
    зелёной клеткой без единого сравнения, как `values_ok` над пустым списком
    полей в v4.
    """


@dataclass(frozen=True)
class Seed:
    """Одно настоящее значение заказчика и подводка, по которой движок его видит."""

    role: str
    cue: str
    value: str


@dataclass(frozen=True)
class Minted:
    """Пара «настоящее → отчеканенное», как её сделал продуктовый путь."""

    role: str
    real: str
    fake: str


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Engine:
    """Живой сайдкар на петле: одна дверь для всех поверхностей прибора.

    Класс, а не набор функций, ровно по правилу репозитория: это коннектор к
    внешнему состоянию (процесс, порт, том). Настоящий сокет, а не ASGI-транспорт
    в памяти — чтобы второй агент подключил поток и обратный прокси, не трогая
    ни строки здесь.
    """

    def __init__(self, database_dir: Path) -> None:
        self._database_dir = database_dir
        self._token = "fragments-gateway"
        self._port = 0
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if not self._port:
            raise EngineError("движок ещё не поднят: base_url спрашивать рано")
        return f"http://127.0.0.1:{self._port}"

    @property
    def gateway_token(self) -> str:
        return self._token

    def start(self) -> None:
        """Поднять лицензионный сервер, загрузить связку и запустить сайдкар.

        Импорты здесь, а не наверху файла, и это несущее: `pseudex.service` и
        `licensing.server` читают конфигурацию из окружения на ИМПОРТЕ, а
        окружение становится полным только внутри этой функции. Так же
        поступает `testkit.start_local_license` и по той же причине.
        """
        os.environ["PSEUDEX_DB_DIR"] = str(self._database_dir)
        os.environ["PSEUDEX_GATEWAY_TOKEN"] = self._token
        os.environ["PSEUDEX_ADMIN_TOKEN"] = "fragments-admin"
        # Том прибора живёт минуты и не содержит ничего, кроме выдуманных людей;
        # шифровать его нечем и незачем, зато `off` убирает зависимость от
        # sqlcipher-ключа в окружении разработчика.
        os.environ["PSEUDEX_VAULT_ENCRYPTION"] = "off"
        # Область псевдонимов объявляется В КАЖДОМ запросе (ось прибора), а
        # переменная окружения — это умолчание процесса, которое иначе тихо
        # переписало бы клетку.
        os.environ.pop("PSEUDEX_PSEUDONYM_SCOPE", None)

        import testkit  # noqa: PLC0415

        testkit.start_local_license()
        testkit.load_dev_bundle()

        from pseudex import service  # noqa: PLC0415

        service.LICENSE.acquire()
        service.LICENSE.start()
        self._port = _free_port()
        server = uvicorn.Server(uvicorn.Config(
            service.app, host="127.0.0.1", port=self._port, log_level="error"))
        self._server = server
        self._thread = threading.Thread(target=server.run, daemon=True)
        self._thread.start()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if server.started:
                return
            time.sleep(0.05)
        raise EngineError("сайдкар не поднялся за 60 секунд")

    def stop(self) -> None:
        server = self._server
        if server is None:
            return
        server.should_exit = True
        thread = self._thread
        if thread is not None:
            thread.join(timeout=10)

    def post(self, path: str, body: Mapping[str, object]) -> dict[str, object]:
        """Один запрос к сайдкару. Любой не-200 — явная ошибка с телом ответа.

        Без повторов и без «вернём пустое»: прибор, который молча проглотил
        отказ движка, напечатал бы чистую клетку там, где случай не проводился.
        """
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._token}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as answer:
                return json.loads(answer.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            raise EngineError(
                f"{path} ответил {error.code}: {detail} · тело запроса "
                f"{json.dumps(body, ensure_ascii=False)[:500]}") from error

    def mint(self, org_id: str, conversation_id: str, pseudonym_scope: str,
             seeds: Sequence[Seed]) -> tuple[Minted, ...]:
        """Отчеканить подмены для значений одного случая, по одному сообщению на значение.

        По сообщению на значение, а не одно общее: из общего подмены пришлось бы
        вырезать выравниванием, а выравнивание по изменившемуся тексту — это
        догадка, и её ошибки легли бы в числа как поломки движка.
        """
        minted: list[Minted] = []
        for seed in seeds:
            body: dict[str, object] = {
                "org_id": org_id,
                "agent_id": "fragments",
                "messages": [{"role": "user", "content": seed.cue + seed.value}],
                "pseudonym_scope": pseudonym_scope,
            }
            if conversation_id:
                body["conversation_id"] = conversation_id
            answer = self.post("/mask", body)
            messages = answer.get("messages")
            if not isinstance(messages, list) or len(messages) != 1:
                raise MintFailed(f"/mask вернул не одно сообщение на {seed.role}: {answer}")
            content = messages[0].get("content")
            if not isinstance(content, str):
                raise MintFailed(f"/mask вернул не строку на {seed.role}: {messages[0]}")
            if not content.startswith(seed.cue):
                raise MintFailed(
                    f"подводка {seed.cue!r} не пережила маскирование на {seed.role}: "
                    f"{content!r} — подмену из этого сообщения не вырезать")
            fake = content[len(seed.cue):].strip()
            if fake == seed.value:
                # Бегун ловит это и печатает клетку как НЕ ИЗМЕРЕННУЮ: зачесть
                # её зелёной было бы тем же нулём из пустого списка, из-за
                # которого v4 печатал 18 из 18.
                raise SubstituteCoincided(
                    f"подмена совпала с настоящим значением {seed.role}={seed.value!r} — "
                    f"случай о восстановлении подмены, которой нечем отличиться")
            if not fake:
                raise MintFailed(f"движок стёр {seed.role}={seed.value!r} вместо подмены")
            minted.append(Minted(role=seed.role, real=seed.value, fake=fake))
        return tuple(minted)

    def fill(self, org_id: str, conversation_id: str, pseudonym_scope: str,
             seeds: Sequence[Seed]) -> tuple[Minted, ...]:
        """Фоновый диалог: отчеканить и вернуть ТО, ЧТО подменилось.

        Отдельный метод, а не «mint помягче»: у фона другой договор. Его дело —
        наполнить волт и дать цифры для столкновения, и подмена, случайно
        совпавшая с настоящим значением, просто не годится в материал. Пустой
        диалог — другое дело: если не подменилось НИЧЕГО, сломано обнаружение,
        и молчать об этом нельзя.
        """
        minted: list[Minted] = []
        for seed in seeds:
            try:
                minted.extend(self.mint(org_id, conversation_id, pseudonym_scope, (seed,)))
            except SubstituteCoincided:
                continue
        if not minted:
            raise MintFailed(
                f"в фоновом диалоге не подменилось НИ ОДНО значение "
                f"({[seed.value for seed in seeds]}) — сломано обнаружение")
        return tuple(minted)


def workspace() -> Path:
    """Том прибора: свежий каталог на прогон, чтобы наполненность мерилась честно."""
    return Path(tempfile.mkdtemp(prefix="fragments-"))
