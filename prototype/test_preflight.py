"""Предполётная проверка памяти: арифметика, чтение cgroup и контракт со шеллом.

ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ НА САМОМ ДЕЛЕ. Не «функция считает деление» — а то, что
контейнер, которому не хватает памяти, ОСТАНАВЛИВАЕТСЯ СЛОВАМИ и до фан-аута.
Раньше на его месте был комментарий в `entrypoint.sh`, а комментарий не умеет
отказывать: воркеры стартовали, OOM-killer забирал одного, супервизор ронял
контейнер со статусом 137, и это число не называет ни память, ни нас.

Три уровня, и средний — самый важный:

  1. `preflight.plan` — решение и его причина в словах.
  2. КОНТРАКТ ПОТОКОВ между `serve_main.py` и `entrypoint.sh`: ровно одна
     строка stdout (число воркеров), всё человеческое — в stderr. Диагностика,
     утёкшая в stdout, стала бы числом воркеров, и `seq 1 "$WORKERS"` не
     запустил бы НИ ОДНОГО процесса — контейнер, который «стартовал» и молчит.
  3. Отказ доезжает до шелла: `entrypoint.sh` выходит и не печатает ключ шлюза,
     то есть до фан-аута дело не дошло.

Без pytest, как всё здесь: запустить, прочитать строки, ненулевой код — сломано.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pseudex import preflight

_HERE = Path(__file__).resolve().parent

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def _limit_dir(files: dict[str, str]) -> str:
    root = tempfile.mkdtemp(prefix="pseudex-cgroup-")
    for relative, text in files.items():
        path = Path(root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def check_limit_reading() -> None:
    v2 = _limit_dir({"memory.max": "2147483648\n"})
    check("cgroup v2 — memory.max читается",
          preflight.memory_limit_mb(v2, {}) == 2048)

    unlimited = _limit_dir({"memory.max": "max\n"})
    check("cgroup v2 — «max» это отсутствие предела, а не ноль",
          preflight.memory_limit_mb(unlimited, {}) is None)

    v1 = _limit_dir({"memory/memory.limit_in_bytes": "1073741824\n"})
    check("cgroup v1 — limit_in_bytes читается",
          preflight.memory_limit_mb(v1, {}) == 1024)

    # v1 ПИШЕТ ЧАСОВОЙ, А НЕ ФЛАГ, и точное число зависит от размера страницы —
    # поэтому сравнение «абсурдно большое», а не равенство константе.
    sentinel = _limit_dir({"memory/memory.limit_in_bytes": "9223372036854771712\n"})
    check("cgroup v1 — часовой «без предела» не превращается в 8 ЭБ памяти",
          preflight.memory_limit_mb(sentinel, {}) is None)

    check("PSEUDEX_MEMORY_LIMIT_MB перебивает файл",
          preflight.memory_limit_mb(v2, {"PSEUDEX_MEMORY_LIMIT_MB": "512"}) == 512,
          "вложенный рантайм показывает память ХОЗЯИНА, и оператор должен уметь сказать правду")

    # МУСОР НЕ РОНЯЕТ СТАРТ И НЕ ВЫКЛЮЧАЕТ ПРОВЕРКУ. Раньше он возвращал None,
    # то есть опечатка в переменной незаметно отменяла весь предполёт —
    # подробнее в check_limit_syntax.
    check("мусор в переменной не роняет старт и не отменяет проверку",
          preflight.memory_limit_mb(v2, {"PSEUDEX_MEMORY_LIMIT_MB": "полтора"}) == 2048)

    missing = _limit_dir({})
    check("нет ни одного файла — нет и предела",
          preflight.memory_limit_mb(missing, {}) is None)


def check_plan() -> None:
    plan = preflight.plan(None, 8, {})
    check("без предела запускается столько, сколько ядер",
          plan["verdict"] == "unknown" and plan["workers"] == 8)

    plan = preflight.plan(4096, 8, {})
    check("что влезает — то и запускается",
          plan["verdict"] == "ok" and plan["workers"] == 8, plan["reason"])

    # ЯВНО НАЗВАННОЕ ЧИСЛО — ЭТО НАМЕРЕНИЕ, и тихо запустить четверть от него
    # значит сделать развёртывание вчетверо слабее, чем за него заплатили, и
    # никогда об этом не сказать.
    plan = preflight.plan(1024, 8, {"PSEUDEX_WORKERS": "8"})
    check("явные восемь в гигабайт — отказ, а не тихое понижение",
          plan["verdict"] == "refused" and plan["workers"] == 0)
    check("отказ называет, сколько влезет и сколько дать",
          "PSEUDEX_WORKERS=2" in plan["reason"] and "2978" in plan["reason"],
          plan["reason"])

    # НАШУ СОБСТВЕННУЮ ДОГАДКУ МЫ ПОНИЖАЕМ САМИ: отказывать из-за числа, которое
    # мы же и вывели из nproc, значит отказывать из-за собственного допущения.
    plan = preflight.plan(1024, 8, {})
    check("выведенное из ядер понижается, а не отказывает",
          plan["verdict"] == "reduced" and plan["workers"] == 2, plan["reason"])

    # НИЖЕ ОДНОГО ВОРКЕРА ПОНИЖАТЬ НЕ ДО ЧЕГО.
    plan = preflight.plan(400, 8, {})
    check("ниже одного воркера — отказ даже когда число вывели мы",
          plan["verdict"] == "refused" and plan["workers"] == 0, plan["reason"])
    check("и говорит минимум, который надо дать",
          "528" in plan["reason"], plan["reason"])

    # 828 МБ ВЫБРАНЫ ТАК, ЧТОБЫ ОТВЕТЫ РАЗОШЛИСЬ: с интерфейсом (828-178)//350
    # это один воркер, без него (828-128)//350 — два. На круглом гигабайте оба
    # дают двойку, и утверждение «>=» прошло бы, даже если бюджет интерфейса
    # вовсе не вычитался.
    without_ui = preflight.plan(828, 8, {"PSEUDEX_UI": "0"})
    with_ui = preflight.plan(828, 8, {})
    check("выключенный интерфейс возвращает свою память в бюджет",
          without_ui["workers"] == 2 and with_ui["workers"] == 1,
          f"без UI {without_ui['workers']}, с UI {with_ui['workers']}")

    tuned = preflight.plan(1024, 8, {"PSEUDEX_WORKER_MB": "150"})
    check("цена воркера настраивается — трафик клиента не нам предсказывать",
          tuned["workers"] == 5, tuned["reason"])

    broken = preflight.plan(1024, 8, {"PSEUDEX_WORKER_MB": "ноль целых"})
    check("испорченная ручка откатывается к умолчанию, а не роняет контейнер",
          broken["worker_mb"] == preflight.DEFAULT_WORKER_MB)


def _run_role(env: dict[str, str]) -> subprocess.CompletedProcess:
    full = dict(os.environ)
    full.update({"PSEUDEX_ROLE": "preflight"})
    full.update(env)
    return subprocess.run([sys.executable, str(_HERE / "serve_main.py")],
                          capture_output=True, text=True, timeout=120,
                          cwd=_HERE, env=full)


def check_role_contract() -> None:
    ok = _run_role({"PSEUDEX_MEMORY_LIMIT_MB": "8192", "PSEUDEX_WORKERS": "2"})
    check("роль preflight выходит нулём, когда влезает", ok.returncode == 0)
    # РОВНО ОДНА СТРОКА, И ОНА ЧИСЛО. Строка диагностики, попавшая в stdout,
    # стала бы значением WORKERS в шелле.
    check("stdout роли — единственное число",
          ok.stdout.strip().isdigit() and len(ok.stdout.strip().splitlines()) == 1,
          repr(ok.stdout))
    check("человеческое ушло в stderr", "preflight" in ok.stderr)

    # ПРЕДЕЛ СЧИТАЕТСЯ ОТ ЯДЕР ЭТОЙ МАШИНЫ, А НЕ БЕРЁТСЯ КОНСТАНТОЙ. Жёсткая
    # 1024 требовала не меньше трёх ядер: на двухъядерном раннере `plan(1024, 2)`
    # даёт «влезает», строки ВНИМАНИЕ нет, и проверка падала на факте о железе, а
    # не о продукте. Понижение вообще существует только при двух ядрах и больше —
    # при одном понижать не до чего, и правильный ответ там «влезает».
    cpus = preflight.cpus_available()
    if cpus > 1:
        room = preflight.DEFAULT_UI_MB + preflight.DEFAULT_HEADROOM_MB \
            + preflight.DEFAULT_WORKER_MB * (cpus - 1)
        lowered = _run_role({"PSEUDEX_MEMORY_LIMIT_MB": str(room)})
        check("понижение печатает число, а причину — в stderr",
              lowered.returncode == 0 and lowered.stdout.strip() == str(cpus - 1)
              and "ВНИМАНИЕ" in lowered.stderr,
              f"ядер {cpus}, ответ {lowered.stdout!r}")
    else:
        one = _run_role({"PSEUDEX_MEMORY_LIMIT_MB": "8192"})
        check("на одном ядре понижать не до чего — и роль это и говорит",
              one.returncode == 0 and one.stdout.strip() == "1"
              and "ВНИМАНИЕ" not in one.stderr, repr(one.stdout))

    refused = _run_role({"PSEUDEX_MEMORY_LIMIT_MB": "1024", "PSEUDEX_WORKERS": "8"})
    check("отказ — ненулевой код", refused.returncode != 0)
    check("и на stdout при отказе нет числа, которое шелл принял бы за ответ",
          refused.stdout.strip() == "", repr(refused.stdout))


def check_limit_syntax() -> None:
    """«2g» — ЭТО ТО, ЧТО НАПИШУТ, потому что так пишут в docker.

    Переменная возвращала None на всём, что не голое число, — то есть опечатка
    ВЫКЛЮЧАЛА предполёт целиком, и напечатанная причина винила в этом монтаж
    cgroup. Непонятое значение обязано жаловаться и падать обратно на файлы.
    """
    v2 = _limit_dir({"memory.max": "2147483648\n"})
    for text, expected in (("2048", 2048), ("2g", 2048), ("2G", 2048),
                           ("2048m", 2048), (" 2g ", 2048)):
        check(f"PSEUDEX_MEMORY_LIMIT_MB={text!r} понято как {expected} МБ",
              preflight.memory_limit_mb(v2, {"PSEUDEX_MEMORY_LIMIT_MB": text}) == expected)
    check("непонятое значение не выключает проверку, а падает на cgroup",
          preflight.memory_limit_mb(v2, {"PSEUDEX_MEMORY_LIMIT_MB": "полтора"}) == 2048)

    # `${PSEUDEX_UI:-1}` в шелле считает пустую строку единицей, и бюджет обязан
    # считать так же — иначе интерфейс стартует, а памяти под него не заложено.
    check("пустой PSEUDEX_UI — это включённый интерфейс, как и в шелле",
          preflight.plan(828, 8, {"PSEUDEX_UI": ""})["workers"] == 1)


def _stub(directory: Path, preflight_action: str) -> Path:
    """Заглушка вместо бинарника: она отвечает на роли ровно как он.

    Настоящий движок здесь не годится — воркер поднимает модель, лезет за
    арендой и живёт минутами, а проверяется поведение ШЕЛЛА.
    """
    path = directory / "stub-serve"
    path.write_text(
        "#!/bin/sh\n"
        'case "${PSEUDEX_ROLE:-engine}" in\n'
        f"    preflight) {preflight_action} ;;\n"
        "    probe) exit 0 ;;\n"
        "    ui) sleep 30 ;;\n"
        "    *) echo \"stub worker\"; exit 7 ;;\n"
        "esac\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _sh_entrypoint(env: dict[str, str]) -> subprocess.CompletedProcess:
    """`entrypoint.sh` под заглушкой, и ЗАВИСАНИЕ ЗДЕСЬ — ЭТО РЕЗУЛЬТАТ.

    Таймаут короткий намеренно: отказы, которые проверяются ниже, при регрессии
    выглядят не как неверный код возврата, а как ВЕЧНОЕ ОЖИДАНИЕ — супервизор
    обходит пустой список процессов и спит. Исключение наружу превратило бы это
    в трассировку посреди прогона (проверено: так и вышло, и `grep FAIL` не
    нашёл ничего), поэтому оно ловится и становится обычным провалом с кодом
    -1 — то есть строкой, которую видно там же, где все остальные.
    """
    try:
        return subprocess.run(["sh", str(_HERE / "entrypoint.sh")],
                              capture_output=True, text=True, timeout=30,
                              cwd=_HERE, env=env)
    except subprocess.TimeoutExpired as expired:
        def _text(raw) -> str:
            if raw is None:
                return ""
            return raw if isinstance(raw, str) else raw.decode("utf-8", "replace")
        return subprocess.CompletedProcess(
            expired.cmd, -1, _text(expired.stdout) + "\n[ЗАВИС: 30 с]",
            _text(expired.stderr))


def _run_entrypoint(preflight_action: str) -> subprocess.CompletedProcess:
    directory = Path(tempfile.mkdtemp(prefix="pseudex-entry-"))
    env = dict(os.environ)
    env.update({"PSEUDEX_SERVE_CMD": str(_stub(directory, preflight_action)),
                "PSEUDEX_UI": "0", "PSEUDEX_DB_DIR": str(directory)})
    return _sh_entrypoint(env)


def check_entrypoint() -> None:
    refused = _run_entrypoint("exit 1")
    check("отказ предполёта останавливает контейнер", refused.returncode == 4,
          f"код {refused.returncode}")
    # ДО ФАН-АУТА ДЕЛО НЕ ДОШЛО, и доказывается это тем, что не напечатан ключ
    # шлюза: он печатается строкой выше самого цикла запуска.
    check("и останавливает ДО фан-аута",
          "ключ шлюза" not in refused.stdout and "worker" not in refused.stdout,
          repr(refused.stdout[-200:]))
    check("и говорит человеку, что случилось",
          "не хватает памяти" in refused.stdout)

    # НАЙДЕНО НЕГАТИВНЫМ ПРОГОНОМ ЭТОЙ ЖЕ ПРОВЕРКИ: со снятым `if !` роль
    # выходила единицей, WORKERS становился пустым, `seq 1 ""` не запускал
    # ничего — и супервизор крутился вечно по пустому списку. Контейнер при этом
    # «работает» для `docker ps` и не делает ничего. Пустой и мусорный ответ
    # обязаны быть отказом, а не покоем.
    empty = _run_entrypoint("exit 0")
    check("пустой ответ предполёта — отказ, а не вечный сон",
          empty.returncode == 4 and "вместо числа" in empty.stdout,
          f"код {empty.returncode}")
    garbage = _run_entrypoint("echo 'два с половиной'")
    check("мусор вместо числа — тоже отказ", garbage.returncode == 4,
          f"код {garbage.returncode}")
    zero = _run_entrypoint("echo 0")
    check("ноль воркеров — отказ", zero.returncode == 4,
          f"код {zero.returncode}")

    # РОЛЬ, ОБЪЯВЛЕННАЯ В ДОКУМЕНТАЦИИ, ОБЯЗАНА БЫТЬ ОДНОРАЗОВОЙ НА САМОМ ДЕЛЕ.
    # `preflight` не было в списке одноразовых ролей, поэтому
    # `docker run -e PSEUDEX_ROLE=preflight` шёл дальше по файлу, печатал ключ
    # шлюза и «запускал» воркеров, каждый из которых просто печатал число.
    directory = Path(tempfile.mkdtemp(prefix="pseudex-oneshot-"))
    env = dict(os.environ)
    env.update({"PSEUDEX_SERVE_CMD": str(_stub(directory, "echo 3")),
                "PSEUDEX_ROLE": "preflight", "PSEUDEX_UI": "0",
                "PSEUDEX_DB_DIR": str(directory)})
    oneshot = _sh_entrypoint(env)
    check("PSEUDEX_ROLE=preflight — одноразовая роль, а не запуск шлюза",
          oneshot.returncode == 0 and "ключ шлюза" not in oneshot.stdout
          and "starting" not in oneshot.stdout, repr(oneshot.stdout))

    started = _run_entrypoint("echo 3")
    check("принятое число становится числом воркеров",
          "starting 3 worker(s)" in started.stdout, repr(started.stdout[:200]))
    # Заглушка-воркер выходит семёркой, и супервизор обязан отдать её наружу:
    # именно так «воркер умер» отличается от чистой остановки.
    check("код упавшего воркера доезжает наружу", started.returncode == 7,
          f"код {started.returncode}")


def main() -> None:
    check_limit_reading()
    check_plan()
    check_limit_syntax()
    check_role_contract()
    check_entrypoint()
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} — {', '.join(FAILURES)}")
        raise SystemExit(1)
    print("preflight OK — контейнер, которому не хватает памяти, "
          "останавливается словами и до фан-аута")


if __name__ == "__main__":
    main()
