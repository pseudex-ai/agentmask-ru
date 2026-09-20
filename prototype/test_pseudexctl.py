"""`pseudexctl`: вердикты, доказательство ротации и форма команд.

ЧТО ЗДЕСЬ ВООБЩЕ МОЖНО ПРОВЕРИТЬ БЕЗ DOCKER, И ПОЧЕМУ ЭТО НЕ ОТГОВОРКА.
Инструмент состоит из трёх разных вещей, и только одна из них требует
контейнера:

  1. КАКИЕ КОМАНДЫ СОБИРАЮТСЯ — чистая строка, и ошибка в ней (том смонтирован
     не туда, роль с опечаткой, забытый `--network none`) не видна никак: docker
     послушно выполнит неправильное. `--dry-run` печатает ровно то, что
     выполнилось бы, поэтому это проверяемо здесь.
  2. ВЕРДИКТЫ `doctor` — тело `/status` на входе, «что сломано и что делать» на
     выходе. Функция, а не побочный эффект, именно ради этого.
  3. ДОКАЗАТЕЛЬСТВО РОТАЦИИ — сравнение подстановок до и после. Ровно то, чего
     сегодня не проверяет ни один гейт: `rekey_store` доказывает, что файл
     открывается новым ключом, и НЕ доказывает, что подстановки, уже лежащие в
     CRM клиента, всё ещё разворачиваются.

Живая ротация против настоящего тома остаётся за гейтами. Здесь — логика,
которая на живом прогоне уже поздно.
"""

import argparse
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# ЗАГРУЖАЕТСЯ ПО ПУТИ, ПОТОМУ ЧТО У ФАЙЛА НЕТ РАСШИРЕНИЯ, и это не оплошность:
# клиент получает его как команду `pseudexctl`, а не как модуль. Проверять же
# надо ИМЕННО ТОТ файл, который ему уедет, а не его копию с `.py`.
# УМОЛЧАНИЯ ФИКСИРУЮТСЯ ЗДЕСЬ, потому что инструмент читает их из окружения.
# Утверждения ниже говорят про `pseudex-data` и `pseudex`; у оператора,
# экспортировавшего PSEUDEX_VOLUME под свой стенд, они падали бы, не найдя ни
# одного дефекта, — проверка, зависящая от чужого профиля, учит игнорировать
# собственный красный.
for _name in ("PSEUDEX_CONTAINER", "PSEUDEX_IMAGE", "PSEUDEX_VOLUME",
              "PSEUDEX_URL", "PSEUDEX_ADMIN_TOKEN", "PSEUDEX_VAULT_KEY",
              "PSEUDEX_VAULT_KEY_CMD", "PSEUDEX_VAULT_KEY_FILE",
              "PSEUDEX_WORKERS", "PSEUDEX_WORKER_MB"):
    os.environ.pop(_name, None)

_PATH = Path(__file__).resolve().parent / "pseudexctl"
_spec = importlib.util.spec_from_loader(
    "pseudexctl", importlib.machinery.SourceFileLoader("pseudexctl", str(_PATH)))
pseudexctl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pseudexctl)

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


class FakeRunner(pseudexctl.Runner):
    """Тот же интерфейс, но наружу не ходит и ЗАПОМИНАЕТ, о чём его просили."""

    def __init__(self, http_replies=None, docker_replies=None) -> None:
        super().__init__(dry_run=False, verbose=False)
        self.docker_calls: list[list[str]] = []
        self.http_calls: list[tuple[str, str]] = []
        self._http = list(http_replies or [])
        self._docker = list(docker_replies or [])

    def docker(self, args, timeout: int = 600):
        self.docker_calls.append(args)
        return self._docker.pop(0) if self._docker else (0, "")

    def http(self, url, token, method="GET", timeout: int = 30):
        self.http_calls.append((method, url))
        return self._http.pop(0) if self._http else (200, "{}")


def _selfcheck(tokens: dict[str, str]) -> str:
    return json.dumps({"spans": [{"value": value, "token": token, "type": "NAME"}
                                 for value, token in tokens.items()]})


def check_command_shapes() -> None:
    """КОМАНДА — ЭТО СТРОКА, И ОШИБКА В НЕЙ НЕВИДИМА: docker выполнит
    неправильное молча и с нулевым кодом."""
    runner = FakeRunner()
    parsed = _real_parse(["probe"])
    parsed.run(parsed, runner)
    command = " ".join(runner.docker_calls[0])
    check("probe монтирует том туда, где движок его ищет",
          "-v pseudex-data:/data" in command and "PSEUDEX_DB_DIR=/data" in command,
          command)
    # ДИАГНОСТИКА НЕ ХОДИТ В СЕТЬ, и контейнер, который НЕ МОЖЕТ, доказывает это
    # лучше обещания в докстринге.
    check("одноразовые роли запускаются без сети", "--network none" in command)
    check("контейнер не остаётся мусором", "--rm" in command)

    runner = FakeRunner()
    parsed = _real_parse(["preflight", "--memory", "512m"])
    parsed.run(parsed, runner)
    check("preflight умеет спросить про ДРУГОЙ лимит, не трогая контейнер",
          "--memory=512m" in " ".join(runner.docker_calls[0]))

    runner = FakeRunner()
    parsed = _real_parse(["restore", "/tmp/x.tgz"])
    code = parsed.run(parsed, runner)
    check("restore без --yes ничего не делает",
          code == 2 and not runner.docker_calls, f"код {code}")


def _real_parse(argv: list[str]):
    """Разбор идёт НАСТОЯЩИМ парсером инструмента, а не его копией здесь.

    Копия расходится с оригиналом ровно тогда, когда это важно: у неё нет
    умолчаний, которые кто-то поменял, и она не знает про добавленный флаг.
    Поэтому `parse_args` подменяется на время вызова и результат забирается
    исключением — до того, как команда начнёт что-то делать.
    """
    saved = argparse.ArgumentParser.parse_args
    captured = {}

    def spy(self, args=None, namespace=None):
        result = saved(self, args, namespace)
        captured["ns"] = result
        raise _Parsed(result)

    argparse.ArgumentParser.parse_args = spy
    try:
        pseudexctl.main(argv)
    except _Parsed as parsed:
        return parsed.namespace
    finally:
        argparse.ArgumentParser.parse_args = saved
    raise AssertionError("парсер не сработал")


class _Parsed(Exception):
    def __init__(self, namespace) -> None:
        super().__init__("parsed")
        self.namespace = namespace


def check_archive_commands() -> None:
    """ДВЕ КОМАНДЫ, КОТОРЫЕ МОГУТ СТЕРЕТЬ ТОМ, И ПРОВЕРЕНЫ ОНИ НЕ БЫЛИ.

    `restore` склеивал имя файла в строку `sh -c`. Это не теоретическая
    придирка: `restore "/tmp/vault backup.tgz"` выполнял `rm -rf /data/*`
    успешно, а распаковку — уже нет, потому что шелл видел два слова. Том стёрт,
    восстанавливать нечем, и всё это с нулевым кодом у `rm`.
    """
    archive = Path(tempfile.mkdtemp(prefix="pseudexctl-")) / "vault backup.tgz"
    archive.write_bytes(b"")
    runner = FakeRunner(docker_replies=[(0, "false")])
    parsed = _real_parse(["restore", str(archive), "--yes"])
    parsed.run(parsed, runner)
    command = runner.docker_calls[-1]
    shell_string = command[command.index("-c") + 1]
    check("имя файла не попадает в строку шелла",
          "vault backup" not in shell_string, shell_string)
    check("имя приезжает переменной окружения, а не подстановкой",
          "ARCHIVE=vault backup.tgz" in command, str(command))
    check("шелл раскрывает её В КАВЫЧКАХ",
          '"/archive/$ARCHIVE"' in shell_string, shell_string)

    # НАЙДЕНО ЭТОЙ ЖЕ ПРОВЕРКОЙ: путь кончается слэшем, `basename` пуст, guard
    # на дефис и слэш его пропускал — и `tar xzf "/archive/"` падал уже ПОСЛЕ
    # `rm -rf /data/*`. Стёртый том, другим путём.
    runner = FakeRunner(docker_replies=[(0, "false")])
    parsed = _real_parse(["restore", "/tmp/x.tgz; rm -rf /", "--yes"])
    code = parsed.run(parsed, runner)
    check("путь, из которого не выходит имя файла, не доходит до docker",
          code == 2 and not any(call[:1] == ["run"] for call in runner.docker_calls),
          f"код {code}")

    runner = FakeRunner(docker_replies=[(0, "false")])
    parsed = _real_parse(["restore", "/tmp/такого-файла-нет-12345.tgz", "--yes"])
    code = parsed.run(parsed, runner)
    check("несуществующий архив не стирает том",
          code == 2 and not any(call[:1] == ["run"] for call in runner.docker_calls),
          f"код {code}")

    # ЖИВОЙ ДВИЖОК ОТМЕНЯЕТ ВОССТАНОВЛЕНИЕ: воркеры пишут в отвязанные inode и
    # затирают только что восстановленное. `rekey`, который делает МЕНЬШЕ,
    # движок останавливает.
    runner = FakeRunner(docker_replies=[(0, "true")])
    parsed = _real_parse(["restore", str(archive), "--yes"])
    code = parsed.run(parsed, runner)
    check("restore на живом контейнере отказывается",
          code == 2 and not any(call[:1] == ["run"] for call in runner.docker_calls),
          f"код {code}")

    # ПРЕДУПРЕЖДЕНИЕ ПОСЛЕ СНЯТОЙ КОПИИ — ЭТО ОПИСАНИЕ ИСПОРЧЕННОГО ФАЙЛА.
    runner = FakeRunner(docker_replies=[(0, "true")])
    parsed = _real_parse(["backup", "/tmp/x.tgz"])
    code = parsed.run(parsed, runner)
    check("backup на живом контейнере отказывается ДО копирования",
          code == 2 and not any(call[:1] == ["run"] for call in runner.docker_calls),
          f"код {code}")

    runner = FakeRunner(docker_replies=[(0, "false"), (0, "")])
    parsed = _real_parse(["backup", "/tmp/x.tgz"])
    code = parsed.run(parsed, runner)
    check("на остановленном — снимает", code == 0, f"код {code}")
    check("и не тянет чужой образ ради tar",
          "alpine" not in " ".join(runner.docker_calls[-1]),
          " ".join(runner.docker_calls[-1]))


def check_secrets_never_printed() -> None:
    """ИНСТРУМЕНТ, У КОТОРОГО ПРОСЯТ ПОКАЗАТЬ КОМАНДУ, ПОКАЗЫВАЛ КЛЮЧ ОТ ВОЛТА —
    в терминал, в историю и в тикет поддержки, куда вывод и вставляют."""
    done = subprocess.run(
        [sys.executable, str(_PATH), "--dry-run", "probe"],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "PSEUDEX_VAULT_KEY": "СЕКРЕТ-НЕ-ПЕЧАТАТЬ"})
    printed = done.stdout + done.stderr
    check("ключ волта не печатается", "СЕКРЕТ-НЕ-ПЕЧАТАТЬ" not in printed, printed)
    # И НЕ ЕДЕТ В argv: `-e ИМЯ` без значения docker берёт из окружения
    # вызывающего, поэтому ключ не появляется ни в `ps`, ни в истории.
    check("и передаётся по имени, а не значением",
          "-e PSEUDEX_VAULT_KEY " in printed or printed.rstrip().endswith("-e PSEUDEX_VAULT_KEY")
          or "-e PSEUDEX_VAULT_KEY\n" in printed, printed)


def check_key_cmd_keeps_network() -> None:
    """`PSEUDEX_VAULT_KEY_CMD` — ЭТО ВЫЗОВ МЕНЕДЖЕРА СЕКРЕТОВ ВНУТРИ КОНТЕЙНЕРА.

    Безусловный `--network none` превращал здоровый том в «НЕ ОТКРЫВАЕТСЯ» —
    самый пугающий вердикт инструмента, выданный по причине, которую этот же
    инструмент и создал.
    """
    runner = FakeRunner()
    parsed = _real_parse(["probe"])
    saved = os.environ.get("PSEUDEX_VAULT_KEY_CMD")
    os.environ["PSEUDEX_VAULT_KEY_CMD"] = "vault kv get -field=key secret/pseudex"
    try:
        parsed.run(parsed, runner)
    finally:
        if saved is None:
            os.environ.pop("PSEUDEX_VAULT_KEY_CMD", None)
        else:
            os.environ["PSEUDEX_VAULT_KEY_CMD"] = saved
    check("с KEY_CMD сеть не отключается",
          "none" not in runner.docker_calls[0], " ".join(runner.docker_calls[0]))

    runner = FakeRunner()
    parsed = _real_parse(["probe"])
    parsed.run(parsed, runner)
    check("без него — отключается", "none" in runner.docker_calls[0])


def check_rekey_proof() -> None:
    """ЭТОГО НЕ ПРОВЕРЯЛ НИКТО: что подстановки пережили смену ключа."""
    same = {"Иванов Пётр Сергеевич": "Волков Андрей", "+7 916 214-88-03": "+7 916 000-00-00"}
    check("совпавшие подстановки — ротация прошла без потерь",
          pseudexctl._verdict_after_rekey(same, dict(same), 200) == 0)

    moved = dict(same)
    moved["Иванов Пётр Сергеевич"] = "Зайцев Роман"
    check("СМЕНИВШАЯСЯ подстановка — отказ, а не «ну и ладно»",
          pseudexctl._verdict_after_rekey(same, moved, 200) == 1)

    # Пустой ответ после ротации — это НЕ «ничего не изменилось». Так выглядит
    # потерянный том: значения не найдены, сравнивать нечего, и наивное
    # сравнение множеств сказало бы «совпало».
    check("пустой ответ после ротации — тоже отказ",
          pseudexctl._verdict_after_rekey(same, {}, 200) == 1)
    check("нездоровый /selfcheck после ротации — отказ",
          pseudexctl._verdict_after_rekey(same, dict(same), 503) == 1)

    # ПРОВЕРКА НЕВОЗМОЖНА ДО РОТАЦИИ — ЗНАЧИТ РОТАЦИИ НЕ БУДЕТ. Иначе оператор
    # получил бы смену ключа и слова «проверить не смогли» — худшее из двух.
    runner = FakeRunner(http_replies=[(503, "")])
    parsed = _real_parse(["rekey", "--verify"])
    code = parsed.run(parsed, runner)
    check("нечего сравнивать -> том не трогаем",
          code == 1 and not any("run" in call for call in runner.docker_calls),
          f"код {code}, докер-вызовы {[c[0] for c in runner.docker_calls]}")

    # Полный проход: движок отвечает, ротация удалась, подстановки те же.
    # Три ответа, а не два: между ними появилось ОЖИДАНИЕ ГОТОВНОСТИ. Без него
    # проверка спрашивала /selfcheck в секунду `docker start`, получала
    # connection refused и объявляла отказом собственное нетерпение.
    runner = FakeRunner(http_replies=[(200, _selfcheck(same)), (200, "ok"),
                                      (200, _selfcheck(same))])
    parsed = _real_parse(["rekey", "--verify"])
    code = parsed.run(parsed, runner)
    started = [call for call in runner.docker_calls if call[:1] == ["start"]]
    check("удачная ротация: движок остановлен, ключ сменён, движок запущен",
          code == 0 and started, f"код {code}")

    # ОТКАЗ РОТАЦИИ ОБЯЗАН ВЕРНУТЬ ДВИЖОК. Оставить контейнер остановленным
    # после неудачи значит превратить сбой ротации в простой шлюза.
    runner = FakeRunner(http_replies=[(200, _selfcheck(same))],
                        docker_replies=[(0, ""), (1, "ТОМ РАЗЪЕХАЛСЯ")])
    parsed = _real_parse(["rekey", "--verify"])
    code = parsed.run(parsed, runner)
    check("неудачная ротация возвращает движок, а не оставляет его лежать",
          code != 0 and any(call[:1] == ["start"] for call in runner.docker_calls),
          f"код {code}")


def check_doctor_verdicts() -> None:
    """Тело /status на входе, «что делать» на выходе."""
    healthy = json.dumps({
        "engine": {"assets_loaded": True,
                   "memory": {"worker_mb_budget": 350, "largest_process_mb": 300,
                              "limit_mb": 4096},
                   "version": "0.3.16",
                   "release": {"version": "0.3.16", "running_latest": True,
                               "latest": "0.3.16", "latest_in_cycle": "0.3.16",
                               "min_supported": "0.3.15", "deprecated_at": None,
                               "sunset_at": None, "notice": None,
                               "upgrade": "pseudexctl upgrade --to 0.3"}},
        "vault": {"on_disk": "encrypted"},
        "license": {"state": "active"},
    })

    def marks(body: str) -> list[str]:
        """Жалобы — всё, что не OK: строка «движок X — новейшая» есть всегда,
        и это не жалоба, а ответ на вопрос, который задают первым."""
        return [mark for mark, _what, _todo in pseudexctl._read_status(body)
                if mark != pseudexctl.OK]

    check("здоровый движок не рождает ни одной жалобы",
          marks(healthy) == [], str(pseudexctl._read_status(healthy)))
    check("новейшая версия названа так, а не промолчана",
          any(mark == pseudexctl.OK and "новейшая" in what
              for mark, what, _t in pseudexctl._read_status(healthy)))

    plaintext = json.loads(healthy)
    plaintext["vault"]["on_disk"] = "plaintext"
    check("открытый том — это ОТКАЗ, а не предупреждение",
          pseudexctl.BAD in marks(json.dumps(plaintext)))

    mixed = json.loads(healthy)
    mixed["vault"]["on_disk"] = "mixed"
    check("оборванная миграция — предупреждение: перезапуск дошифрует",
          marks(json.dumps(mixed)) == [pseudexctl.WARN])

    unloaded = json.loads(healthy)
    unloaded["engine"]["assets_loaded"] = False
    check("нет словарей — это остановка, а не «детекция похуже»",
          pseudexctl.BAD in marks(json.dumps(unloaded)))

    fat = json.loads(healthy)
    fat["engine"]["memory"]["largest_process_mb"] = 900
    text = " ".join(what for _m, what, _t in pseudexctl._read_status(json.dumps(fat)))
    check("воркер выше бюджета назван до того, как его заберёт OOM-killer",
          "900" in text and "350" in text, text)

    nolimit = json.loads(healthy)
    nolimit["engine"]["memory"]["limit_mb"] = None
    check("без лимита памяти предполёт ничего не проверял, и это сказано",
          pseudexctl.WARN in marks(json.dumps(nolimit)))

    # ВРАЧ, ЗАМОЛЧАВШИЙ НА ПЕРВОМ СИМПТОМЕ, ХУЖЕ ОТСУТСТВУЮЩЕГО.
    check("мусор вместо JSON не роняет инструмент",
          len(pseudexctl._read_status("<html>502 Bad Gateway</html>")) == 1)
    check("у каждой жалобы есть следующее действие",
          all(todo for mark, _w, todo in pseudexctl._read_status(json.dumps(plaintext))
              if mark != pseudexctl.OK))

    # ЛЕСТНИЦА ВЕРСИЙ (D-055): что говорит сервер — то и печатает врач, и у
    # каждой ступени своё действие. Молчание сервера — НЕ «новейшая».
    def version_lines(body: dict) -> list[tuple[str, str, str]]:
        return [line for line in pseudexctl._read_status(json.dumps(body))
                if "движок" in line[1] or "уведомление" in line[1]]

    newer = json.loads(healthy)
    newer["engine"]["release"].update({"running_latest": False, "latest": "0.4.1",
                                       "upgrade": "pseudexctl upgrade --to 0.4"})
    lines = version_lines(newer)
    check("есть новее — предупреждение с версией и командой обновления",
          lines and lines[0][0] == pseudexctl.WARN and "0.4.1" in lines[0][1]
          and lines[0][2] == "pseudexctl upgrade --to 0.4", str(lines))

    deprecated = json.loads(json.dumps(newer))
    deprecated["engine"]["release"].update({"deprecated_at": 1759622400, "sunset_at": 1806883200})
    lines = version_lines(deprecated)
    check("снята с поддержки — предупреждение с датой окончания обслуживания",
          lines and lines[0][0] == pseudexctl.WARN and "2027-04-05" in lines[0][1]
          and "откажет" in lines[0][2], str(lines))

    refused = json.loads(json.dumps(deprecated))
    refused["license"] = {"state": "expired", "code": "unsupported_client"}
    lines = version_lines(refused)
    check("426 — отказ, названный отказом по версии, а не «оплатите»",
          lines and lines[0][0] == pseudexctl.BAD and "426" in lines[0][1]
          and "0.3.15" in lines[0][2], str(lines))

    silent = json.loads(healthy)
    silent["engine"]["release"] = {"version": "0.3.16", "running_latest": None, "latest": None,
                                   "latest_in_cycle": None, "min_supported": None,
                                   "deprecated_at": None, "sunset_at": None, "notice": None,
                                   "upgrade": None}
    lines = version_lines(silent)
    check("сервер промолчал — это «неизвестно», а не «новейшая»",
          lines and lines[0][0] == pseudexctl.WARN and "не сообщил" in lines[0][1], str(lines))

    noticed = json.loads(healthy)
    noticed["engine"]["release"]["notice"] = {"id": "n-1", "severity": "critical",
                                              "text": "обновитесь", "url": "https://pseudex.ru/a/1"}
    lines = version_lines(noticed)
    check("критическое уведомление — отказ со ссылкой",
          any(mark == pseudexctl.BAD and "обновитесь" in what and todo.startswith("https://")
              for mark, what, todo in lines), str(lines))


def check_dry_run_touches_nothing() -> None:
    """`--dry-run` обязан быть ПОЛНОСТЬЮ сухим: инструмент, который «почти»
    ничего не делает, читают один раз и потом боятся."""
    # Архив настоящий: `restore` теперь отказывается, если восстанавливать
    # нечем, — и это правильнее, чем стереть том и упасть на распаковке.
    archive = Path(tempfile.mkdtemp(prefix="pseudexctl-dry-")) / "vault.tgz"
    archive.write_bytes(b"")
    done = subprocess.run(
        [sys.executable, str(_PATH), "--dry-run", "restore", str(archive), "--yes"],
        capture_output=True, text=True, timeout=120)
    printed = done.stdout + done.stderr
    check("--dry-run печатает команду и не выполняет её",
          "docker run" in printed and done.returncode == 0, printed.strip()[:120])
    check("и ключи в напечатанном не появляются",
          "PSEUDEX_VAULT_KEY=" not in printed)


def main() -> None:
    check_command_shapes()
    check_archive_commands()
    check_secrets_never_printed()
    check_key_cmd_keeps_network()
    check_rekey_proof()
    check_doctor_verdicts()
    check_dry_run_touches_nothing()
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} — {', '.join(FAILURES)}")
        raise SystemExit(1)
    print("pseudexctl OK — команды собираются верно, вердикты называют следующий "
          "шаг, ротация доказывает, что детокенизация выжила")


if __name__ == "__main__":
    main()
