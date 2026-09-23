"""ЭТО НЕ ПРОВЕРКА, А СТЕНД: настоящий лицензионный сервер, снятые с него ответы.

`test_slots.py` рисует экраны слотов по ответу `/admin/instances`. Раньше этот
ответ был написан рукой — и в нём стояли поля, которых сервер не присылает
(`released_by`) и числа, которых он в этом состоянии не даёт. Проверка,
собранная из полей, которых сервер никогда не шлёт, провалиться не может: она
проверяет фантазию автора.

Поэтому ответы СНИМАЮТСЯ. Этот файл поднимает `python3 -m licensing.devserver`
на свободном порту с временной базой, доводит организацию до каждого состояния
НАСТОЯЩИМИ вызовами (`/v1/lease`, `/v1/meter`, `/v1/usage`, `/v1/release`,
`/admin/release`) — включая настоящий фенсинг с настоящим 409 — и печатает
снятые тела в JSON.

СОСТОЯНИЯ ДРУГИЕ, ПОТОМУ ЧТО ИХ БОЛЬШЕ НЕТ У СЕРВЕРА. `silent`, `reclaimed` и
потолок рабочих процессов были суждениями о том, жив ли контейнер; сервер их не
выносит и не отдаёт. Стенд доводит организацию до того, что существует:
занятый слот, занятый слот с поколением, которое попрощалось, свободный слот с
ДОЦЕЖИВАЮЩИМ поколением и просто свободный слот.

ПОЧЕМУ ОТДЕЛЬНЫМ ПРОЦЕССОМ И ДРУГИМ ИНТЕРПРЕТАТОРОМ. Ключ процесса — это
X25519-личность из `pseudex.bundle`; она живёт в окружении ДВИЖКА
(`prototype/.venv`), где нет django, а в окружении витрины нет ни `pyrage`, ни
`fastapi`. Витрина не имеет права зависеть от движка (MAP §6), поэтому связь
между ними здесь ровно одна и та, что и в проде: JSON по HTTP.

ПОЧЕМУ СНИМОК, А НЕ ЖИВОЙ ПРОКСИ. Состояния слотов меняются на каждом вызове
стенда, и пока браузер открывает вторую страницу, доцеживающее поколение может
получить новое. Снимок — это байты сервера в тот момент, когда все четыре
состояния существовали разом.

    prototype/.venv/bin/python storefront/test_slots_stand.py --out /tmp/slots.json
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

_ENGINE = Path(__file__).resolve().parents[1] / "prototype"
sys.path.insert(0, str(_ENGINE))
from pseudex.bundle import generate_process_key  # noqa: E402

# СРОКОВ У СТЕНДА БОЛЬШЕ НЕТ, И ЭТО САМО ПО СЕБЕ РЕЗУЛЬТАТ. Прежний сжимал
# `PSEUDEX_ALIVE_SECONDS` с десяти минут до трёх секунд, потому что иначе
# состояние «замолчал» стоило бы десяти минут ожидания на прогон, и поднимал
# эхо и бюджет перевыдач, чтобы в один час поместились переходы суток. Ни
# одного из этих трёх сроков не существует: сервер не судит по молчанию, и
# каждое состояние достигается ВЫЗОВОМ, а не ожиданием. Прогон стал короче на
# все секунды, которые раньше уходили на сон.
VERSION = "0.3.18"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Stand:
    """Настоящий `licensing.devserver` на 127.0.0.1 с временной базой."""

    def __init__(self, db_path: str, log_path: str) -> None:
        self.port, self.admin_port = _free_port(), _free_port()
        self.token = uuid.uuid4().hex
        env = dict(os.environ)
        env.update({
            "PSEUDEX_LICENSE_DB": db_path,
            "PSEUDEX_LICENSE_ADMIN_TOKEN": self.token,
            "PSEUDEX_LICENSE_STOREFRONT_TOKEN": self.token,
            "PSEUDEX_LICENSE_PORT": str(self.port),
            "PSEUDEX_LICENSE_ADMIN_PORT": str(self.admin_port),
            "PSEUDEX_LEASE_TTL_SECONDS": "86400",
            "PSEUDEX_LOG_LEVEL": "WARNING",
        })
        self.log = open(log_path, "w")
        self.proc = subprocess.Popen([sys.executable, "-m", "licensing.devserver"],
                                     cwd=str(_ENGINE), env=env,
                                     stdout=self.log, stderr=subprocess.STDOUT)
        self.base = f"http://127.0.0.1:{self.port}"
        self.admin_base = f"http://127.0.0.1:{self.admin_port}"
        # СТАРТ МЕДЛЕННЫЙ И ЭТО НОРМАЛЬНО: сервер собирает бандл (197 тысяч
        # фамилий, 165 тысяч улиц ГАР) до первого ответа, и на занятой машине
        # это десятки секунд. Поэтому срок щедрый, а СМЕРТЬ ПРОЦЕССА замечается
        # сразу и с хвостом лога: ждать минуту того, кто уже упал с
        # трассировкой, — это провал не там, где причина.
        deadline = time.monotonic() + 180.0
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                self.log.close()
                tail = Path(log_path).read_text()[-4000:]
                raise RuntimeError(
                    f"лицензионный сервер упал на старте (код {self.proc.returncode}):"
                    f"\n{tail}")
            try:
                if httpx.get(f"{self.base}/health", timeout=2.0).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        self.stop()
        raise RuntimeError(
            f"лицензионный сервер не ответил на {self.base}/health за 180 с; "
            f"лог: {log_path}")

    def admin_get(self, path: str, params: dict) -> dict:
        response = httpx.get(f"{self.admin_base}{path}", params=params, timeout=20.0,
                             headers={"Authorization": f"Bearer {self.token}"})
        response.raise_for_status()
        return response.json()

    def admin_post(self, path: str, body: dict) -> dict:
        response = httpx.post(f"{self.admin_base}{path}", json=body, timeout=20.0,
                              headers={"Authorization": f"Bearer {self.token}"})
        response.raise_for_status()
        return response.json()

    def issue(self, org_id: str, plan: str) -> str:
        response = httpx.post(f"{self.admin_base}/admin/issue", timeout=20.0,
                              json={"org_id": org_id, "plan": plan},
                              headers={"Authorization": f"Bearer {self.token}"})
        response.raise_for_status()
        return response.json()["key"]

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()


class Worker:
    """ОДИН uvicorn-воркер: собственный ключ процесса, рождённый в памяти."""

    def __init__(self, stand: Stand, key: str, instance_id: str,
                 start_id: str) -> None:
        self.stand, self.key, self.instance_id = stand, key, instance_id
        # ОДИН `start_id` НА ВСЕХ ВОРКЕРОВ СТАРТА — ровно так его чеканит
        # `entrypoint.sh` до фан-аута. Случайный на процесс сделал бы из одного
        # контейнера N поколений, и они отфенсили бы друг друга.
        self.start_id = start_id
        self.process_key = generate_process_key()
        self.lease_id = None
        self.seq = 0
        self.slot_no = None
        self.epoch = None

    def lease(self) -> httpx.Response:
        body = {"key": self.key, "instance_id": self.instance_id,
                "start_id": self.start_id,
                "process_id": f"{self.instance_id}-{self.process_key.public[:8]}",
                "pubkey": self.process_key.public, "engine_version": VERSION,
                "lease_contract": 3, "lease_id": self.lease_id,
                "nonce": uuid.uuid4().hex}
        response = httpx.post(f"{self.stand.base}/v1/lease", json=body, timeout=60.0)
        if response.status_code == 200:
            payload = response.json()
            self.lease_id = payload.get("lease_id")
            self.slot_no, self.epoch = payload.get("slot_no"), payload.get("epoch")
        return response

    def meter(self) -> httpx.Response:
        """`POST /v1/meter` — покупка кванта ёмкости с фенсинг-тегом в `ack`.

        Именно ПОКУПКА, а не отчёт, даёт слоту `last_purchase_at` и оставляет
        отфенсенному поколению полосу, которую экран называет словом «до».
        """
        body = {"key": self.key, "pubkey": self.process_key.public,
                "nonce": uuid.uuid4().hex,
                "ack": {"consumed": 0, "slot_no": self.slot_no,
                        "epoch": self.epoch}}
        answer = httpx.post(f"{self.stand.base}/v1/meter", json=body, timeout=20.0)
        if answer.status_code == 429:
            # ОДИН КВАНТ В СЕКУНДУ НА КЛЮЧ — это НАША полоса, а не потолок
            # тарифа: честный движок приходит сюда раз в четыре минуты. Стенд её
            # пережидает, а не отключает, иначе снятое тело описывало бы лимит
            # частоты вместо фенсинга.
            time.sleep(1.05)
            answer = httpx.post(f"{self.stand.base}/v1/meter", json=body, timeout=20.0)
        return answer

    def heartbeat(self) -> httpx.Response:
        """`POST /v1/usage` — пульс, который движок шлёт своим таймером."""
        self.seq += 1
        body = {"key": self.key, "instance_id": self.instance_id,
                "pubkey": self.process_key.public,
                "usage": {"requests": 12, "values": 7, "entities": {"PHONE": 7},
                          "seq": self.seq, "prev": ""}}
        return httpx.post(f"{self.stand.base}/v1/usage", json=body, timeout=20.0)

    def release(self) -> httpx.Response:
        return httpx.post(f"{self.stand.base}/v1/release", timeout=20.0,
                          json={"key": self.key, "instance_id": self.instance_id,
                                "pubkey": self.process_key.public})


def _grab(stand: Stand, org_id: str) -> tuple[dict, float]:
    """Снимок `/admin/instances` И МОМЕНТ, В КОТОРЫЙ ОН СНЯТ.

    Отметки в теле абсолютные, а занятость — величина относительно «сейчас»,
    поэтому без момента съёмки снимок нельзя ни проверить, ни нарисовать: через
    минуту он описывал бы контейнер, который «на связи 1 мин назад» и при этом
    живой при сроке молчания в три секунды.
    """
    at = time.time()
    return stand.admin_get("/admin/instances", {"org_id": org_id}), at


def _refusal(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        body = {"error": "", "detail": response.text}
    return {"status": response.status_code, "error": str(body.get("error", "")),
            "detail": str(body.get("detail", ""))}


def _container(stand: Stand, key: str, name: str, start_id: str, workers: int,
               buy: bool) -> tuple[list[Worker], dict | None]:
    """Поднять контейнер с `workers` воркерами. Отказ ВОЗВРАЩАЕТСЯ, а не глотается."""
    made: list[Worker] = []
    for _ in range(workers):
        worker = Worker(stand, key, name, start_id)
        response = worker.lease()
        if response.status_code != 200:
            return made, _refusal(response)
        worker.heartbeat()
        if buy:
            worker.meter()
        made.append(worker)
    return made, None


def _slot_states(stand: Stand) -> dict:
    """ЧЕТЫРЕ СОСТОЯНИЯ СЛОТА В ОДНОЙ ОРГАНИЗАЦИИ, все доведённые ВЫЗОВАМИ.

    Тариф «Рабочий» — четыре слота, потому что показать надо и занятый, и
    свободный разом. Ни одно состояние здесь не достигается ожиданием: молчание
    больше ничего не значит, и это главная разница с прежним стендом.

      слот 1 — занят, поколение покупает ёмкость (обычная жизнь);
      слот 2 — занят, поколение попрощалось (`/v1/release` записан и НЕ читается
               ни одним решением: слот всё ещё его);
      слот 3 — свободен, но на нём ДОЦЕЖИВАЕТ поколение, у которого слот забрала
               поддержка: экран обязан сказать про остаток «до», а не «оно
               остановлено» — второго мы не знаем;
      слот 4 — свободен и пуст.
    """
    key = stand.issue("slotco", "work")
    live, refused = _container(stand, key, "vol-live", "S-live", 2, buy=True)
    assert refused is None, refused
    polite, refused = _container(stand, key, "vol-polite", "S-polite", 1, buy=True)
    assert refused is None, refused
    for worker in polite:
        worker.release()
    drained, refused = _container(stand, key, "vol-drained", "S-drained", 1, buy=True)
    assert refused is None, refused

    # РЫЧАГ ПОДДЕРЖКИ — НАСТОЯЩИЙ ВЫЗОВ: эпох слота поднят, держатель снят,
    # поколение доцеживает купленное.
    freed = stand.admin_post("/admin/release",
                             {"org_id": "slotco", "instance_id": "vol-drained"})
    assert freed.get("slots") == 1, freed

    snapshot, snapshot_at = _grab(stand, "slotco")
    # И ОТКАЗ, КОТОРЫЙ ЭТО ПОКОЛЕНИЕ ПРОЧТЁТ В ЛОГАХ СВОЕГО ДВИЖКА, снятый тем
    # же прогоном: 409 `fenced`, а не `instance_limit`.
    fenced_by_admin = _refusal(drained[0].meter())
    assert fenced_by_admin["status"] == 409, fenced_by_admin

    return {"org_id": "slotco", "plan": "work", "holding": "vol-live",
            "released": "vol-polite", "draining": "vol-drained",
            "instances": snapshot, "instances_at": snapshot_at,
            "usage": stand.admin_get("/admin/usage", {"org_id": "slotco"}),
            "chains": stand.admin_get("/admin/chains", {"org_id": "slotco"}),
            "refusals": {"fenced_by_admin": fenced_by_admin},
            "workers": {"live": len(live)}}


def _fenced_by_claim(stand: Stand) -> dict:
    """ПЕРЕЗАПУСК НА ТАРИФЕ В ОДИН СЛОТ: новое поколение фенсит предыдущее.

    Отдельная организация, потому что нужен ПОЛНЫЙ тариф: при свободном слоте
    новый старт возьмёт свободный, и вытеснения не случится вовсе. Это тот
    самый случай, ради которого вся конструкция и делалась, — OOM-килл и
    `docker compose up -d` идут здесь одним путём.
    """
    key = stand.issue("fenceco", "start")
    first, refused = _container(stand, key, "vol-one", "S1", 1, buy=True)
    assert refused is None, refused
    second, refused = _container(stand, key, "vol-one", "S2", 1, buy=True)
    # ПЕРЕЗАПУСК ОБЯЗАН ПОДНИМАТЬСЯ, А НЕ ОТКАЗЫВАТЬСЯ: выпущенный 0.3.17 на
    # этом же месте отвечал 409 на 6-м, 9-м и 3-м честном старте.
    assert refused is None, refused
    snapshot, snapshot_at = _grab(stand, "fenceco")
    fenced = _refusal(first[0].meter())
    assert fenced["status"] == 409 and fenced["error"] == "fenced", fenced
    return {"org_id": "fenceco", "plan": "start", "holding": "vol-one",
            "instances": snapshot, "instances_at": snapshot_at,
            "usage": stand.admin_get("/admin/usage", {"org_id": "fenceco"}),
            "chains": stand.admin_get("/admin/chains", {"org_id": "fenceco"}),
            "refusals": {"fenced_by_claim": fenced},
            "epochs": {"first": first[0].epoch, "second": second[0].epoch}}


def collect(db_path: str, log_path: str) -> dict:
    stand = Stand(db_path, log_path)
    try:
        return {"engine_version": VERSION,
                "slots": _slot_states(stand), "fenced": _fenced_by_claim(stand),
                # Флот называет организации сам: ручка их не перечисляет —
                # она экономит round-trip, а не расширяет права.
                "fleet": stand.admin_get("/admin/fleet",
                                         {"org_ids": "slotco,fenceco"}),
                "plans": stand.admin_get("/admin/plans", {})}
    finally:
        stand.stop()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--db", default="")
    parser.add_argument("--log", default="")
    args = parser.parse_args()
    db_path = args.db or os.path.join(os.path.dirname(args.out), "licensing.db")
    log_path = args.log or os.path.join(os.path.dirname(args.out), "licensing.log")
    captured = collect(db_path, log_path)
    Path(args.out).write_text(json.dumps(captured, ensure_ascii=False, indent=1))
    print(f"снято: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
