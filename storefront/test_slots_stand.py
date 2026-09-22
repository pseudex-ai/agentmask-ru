"""ЭТО НЕ ПРОВЕРКА, А СТЕНД: настоящий лицензионный сервер, снятые с него ответы.

`test_slots.py` рисует экраны слотов по ответу `/admin/instances`. Раньше этот
ответ был написан рукой — и в нём стояли поля, которых сервер не присылает
(`released_by`) и числа, которых он в этом состоянии не даёт (`live_processes`
у отобранного места). Проверка, собранная из полей, которых сервер никогда не
шлёт, провалиться не может: она проверяет фантазию автора.

Поэтому ответы СНИМАЮТСЯ. Этот файл поднимает `python3 -m licensing.devserver`
на свободном порту с временной базой, доводит организацию до каждого состояния
НАСТОЯЩИМИ вызовами (`/v1/lease`, `/v1/usage`, `/v1/release`) — включая
настоящее отобрание места у замолчавшего контейнера и настоящий отказ по
потолку рабочих процессов — и печатает снятые тела в JSON.

ПОЧЕМУ ОТДЕЛЬНЫМ ПРОЦЕССОМ И ДРУГИМ ИНТЕРПРЕТАТОРОМ. Ключ процесса — это
X25519-личность из `pseudex.bundle`; она живёт в окружении ДВИЖКА
(`prototype/.venv`), где нет django, а в окружении витрины нет ни `pyrage`, ни
`fastapi`. Витрина не имеет права зависеть от движка (MAP §6), поэтому связь
между ними здесь ровно одна и та, что и в проде: JSON по HTTP.

ПОЧЕМУ СНИМОК, А НЕ ЖИВОЙ ПРОКСИ. Занятость зависит от времени: при
`PSEUDEX_ALIVE_SECONDS=3` живой контейнер замолкает раньше, чем браузер успеет
открыть вторую страницу, и пять состояний не удержать в одном кадре. Снимок —
это байты сервера в тот момент, когда все состояния существовали разом.

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

# СРОКИ СТЕНДА. Молчание — три секунды вместо десяти минут, иначе состояние
# «замолчал» стоило бы десяти минут ожидания на каждом прогоне; эхо и бюджет
# перевыдач подняты, чтобы в одном часе поместились все переходы, которые
# клиент делает за сутки. Все три — штатные переменные сервера, а не правка
# кода: экран печатает то, что сервер назвал, и числа стенда видны на нём как
# есть.
ALIVE_SECONDS = 3.0
ECHO_SECONDS = 20.0
BUDGET_PER_HOUR = 6
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
            "PSEUDEX_ALIVE_SECONDS": str(ALIVE_SECONDS),
            "PSEUDEX_RELEASE_ECHO_SECONDS": str(ECHO_SECONDS),
            "PSEUDEX_RELEASE_BUDGET_PER_HOUR": str(BUDGET_PER_HOUR),
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

    def __init__(self, stand: Stand, key: str, instance_id: str) -> None:
        self.stand, self.key, self.instance_id = stand, key, instance_id
        self.process_key = generate_process_key()
        self.lease_id = None
        self.seq = 0

    def lease(self) -> httpx.Response:
        body = {"key": self.key, "instance_id": self.instance_id,
                "process_id": f"{self.instance_id}-{self.process_key.public[:8]}",
                "pubkey": self.process_key.public, "engine_version": VERSION,
                "lease_contract": 3, "lease_id": self.lease_id,
                "nonce": uuid.uuid4().hex}
        response = httpx.post(f"{self.stand.base}/v1/lease", json=body, timeout=60.0)
        if response.status_code == 200:
            self.lease_id = response.json().get("lease_id")
        return response

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


def _container(stand: Stand, key: str, name: str, workers: int,
               beat: bool) -> tuple[list[Worker], dict | None]:
    """Поднять контейнер с `workers` воркерами. Отказ ВОЗВРАЩАЕТСЯ, а не глотается."""
    made: list[Worker] = []
    for _ in range(workers):
        worker = Worker(stand, key, name)
        response = worker.lease()
        if response.status_code != 200:
            return made, _refusal(response)
        if beat:
            worker.heartbeat()
        made.append(worker)
    return made, None


def _four_states(stand: Stand) -> dict:
    """ЧЕТЫРЕ СОСТОЯНИЯ КОНТЕЙНЕРА В ОДНОЙ ОРГАНИЗАЦИИ, все доведённые вызовами.

    Порядок не произволен: место отбирают у того, кого дольше всех не слышали,
    поэтому замолчавший первым (`vol-taken`) и становится отобранным, когда на
    его место приходит следующий контейнер. Тариф «старт» — один контейнер,
    иначе отбирать было бы нечего.
    """
    key = stand.issue("slotco", "start")
    taken, refused = _container(stand, key, "vol-taken", 2, beat=True)
    assert refused is None, refused
    time.sleep(ALIVE_SECONDS + 0.4)          # его перестали слышать

    # ОТБОР МЕСТА — НАСТОЯЩИЙ: этот допуск вытесняет молчащего, сервер
    # закрывает его строки с `released_by='silence'` и списывает единицу.
    gone, refused = _container(stand, key, "vol-gone", 1, beat=True)
    assert refused is None, refused
    for worker in gone:
        worker.release()                     # а этот остановился САМ

    dead, refused = _container(stand, key, "vol-dead", 1, beat=False)
    assert refused is None, refused
    time.sleep(ALIVE_SECONDS + 0.4)          # и замолчал

    alive, refused = _container(stand, key, "vol-alive", 3, beat=True)
    assert refused is None, refused

    snapshot, snapshot_at = _grab(stand, "slotco")
    # ШЕСТОЙ КОНТЕЙНЕР ПРИ ЗАНЯТОМ СЛОТЕ — отказ, который клиент читает в логах
    # своего движка, снятый тем же прогоном.
    sixth = Worker(stand, key, "vol-sixth")
    busy = _refusal(sixth.lease())

    # ОТОБРАННЫЙ ЕЩЁ РАБОТАЕТ. Это и есть случай, ради которого экран обязан
    # назвать отбор отбором: его движок жив, отчитывается, и получит 409.
    taken[0].heartbeat()
    echo, echo_at = _grab(stand, "slotco")
    renewal = _refusal(taken[0].lease())

    return {"org_id": "slotco", "plan": "start", "holding": "vol-alive",
            "silent": "vol-dead", "released": "vol-gone", "reclaimed": "vol-taken",
            "instances": snapshot, "instances_at": snapshot_at,
            "instances_after_echo": echo, "instances_after_echo_at": echo_at,
            "usage": stand.admin_get("/admin/usage", {"org_id": "slotco"}),
            "chains": stand.admin_get("/admin/chains", {"org_id": "slotco"}),
            "refusals": {"slot_busy": busy, "reclaimed_renewal": renewal},
            "workers": {"alive": len(alive), "dead": len(dead)}}


def _process_ceiling(stand: Stand) -> dict:
    """ПОТОЛОК РАБОЧИХ ПРОЦЕССОВ — настоящий: 32 воркера проходят, 33-й нет.

    Отдельная организация, потому что потолок считается по ВСЕЙ организации:
    молчащий ключ соседнего контейнера занял бы место в тех же тридцати двух и
    отказ пришёл бы по другой причине.
    """
    key = stand.issue("ceilco", "start")
    workers, refused = _container(stand, key, "vol-big", 32, beat=True)
    assert refused is None, refused
    # ПУЛЬС ПЕРЕД СНИМКОМ И ПЕРЕД ПОСЛЕДНЕЙ ПОПЫТКОЙ, а не только при аренде:
    # тридцать две аренды занимают около секунды, и при сроке молчания стенда
    # первые ключи успевали замолкнуть — тогда отказ приходил бы по
    # переоткрытию их мест, а снимок показывал бы меньше живых процессов, чем
    # называет отказ. Круг повторяется, пока сервер не увидит их всеми живыми:
    # предмет замера — момент, когда потолок ПОЛОН.
    instances, at = {}, 0.0
    for _ in range(3):
        for worker in workers:
            worker.heartbeat()
        instances, at = _grab(stand, "ceilco")
        if instances["instances"][0]["live_processes"] == len(workers):
            break
    assert instances["instances"][0]["live_processes"] == len(workers), instances
    refused = _refusal(Worker(stand, key, "vol-big").lease())
    assert refused["status"] == 409, refused
    assert str(len(workers)) in refused["detail"], refused
    return {"org_id": "ceilco", "plan": "start", "holding": "vol-big",
            "admitted": len(workers),
            "instances": instances, "instances_at": at,
            "usage": stand.admin_get("/admin/usage", {"org_id": "ceilco"}),
            "chains": stand.admin_get("/admin/chains", {"org_id": "ceilco"}),
            "refusals": {"process_ceiling": refused}}


def collect(db_path: str, log_path: str) -> dict:
    stand = Stand(db_path, log_path)
    try:
        return {"alive_seconds": ALIVE_SECONDS, "engine_version": VERSION,
                "slots": _four_states(stand), "ceiling": _process_ceiling(stand),
                # Флот называет организации сам: ручка их не перечисляет —
                # она экономит round-trip, а не расширяет права.
                "fleet": stand.admin_get("/admin/fleet",
                                         {"org_ids": "slotco,ceilco"}),
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
