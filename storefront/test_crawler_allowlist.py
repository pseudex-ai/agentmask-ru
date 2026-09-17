"""Белый список роботов fail2ban: пропускает робота и НЕ создаёт лазейку.

ЗАЧЕМ. `deploy/fail2ban/pseudex-is-crawler` решает, кого НЕ банить, и ошибка в
нём стоит в обе стороны, причём в разные:

  * СЛИШКОМ СТРОГИЙ — робот поисковика отрезан на уровне пакетов
    (`chain = DOCKER-USER`), обход прерывается, сайт не индексируется. Ровно то,
    что этот релиз и чинит: сорок 404 за две минуты, час бана, после трёх банов
    неделя.

  * СЛИШКОМ МЯГКИЙ — любой сканер пишет `YandexBot` в `User-Agent` и перебирает
    коды на `/accounts/login/` без ограничения. Это ХУЖЕ, чем не иметь списка:
    без списка сканер банится, со сломанным — нет.

ВТОРАЯ ПОЛОВИНА ВАЖНЕЕ, И ОНА ЖЕ — ТА, КОТОРУЮ ЛЕГКО СДЕЛАТЬ НЕПРАВИЛЬНО.
Наивная реализация `host.endswith("googlebot.com")` пропускает
`evilgooglebot.com` — домен, который нападающий заводит себе за пять минут, и
PTR этого домена он назначает сам. Проверка одного лишь PTR пропускает его же.
Не пропускает его только ПОДТВЕРЖДЕНИЕ ПРЯМЫМ ЗАПРОСОМ: имя обязано
разрешаться обратно в тот же адрес, а `yandex.ru` разрешить может лишь сам
Яндекс. Обе ошибки закреплены тестом ниже.

ПОЧЕМУ DNS ПОДДЕЛЬНЫЙ. Тест, который для этого ходил бы в настоящий DNS,
проверял бы сеть и чужую зону: адреса роботов меняются, и «постоянно красная
тревога учит мьютить канал» — это из этого же репозитория. Логика от сети не
зависит, поэтому и проверяется без неё. Живой DNS был прогнан руками на
настоящих адресах (`77.88.55.88` → `yandex.ru`, `66.249.66.1` →
`crawl-66-249-66-1.googlebot.com`, `157.55.39.1` → `msnbot-….search.msn.com`) и
все три отвечают «робот», но гейтом это не становится намеренно.

И ВТОРАЯ ПОЛОВИНА, БЕЗ КОТОРОЙ ПЕРВАЯ БЕСПОЛЕЗНА: джейл обязан ЧИТАТЬ тот файл,
куда пишет Caddy. На бою он его не читал — Debian упаковывает fail2ban с
бэкендом `systemd` по умолчанию, и джейл с `logpath` на файл молча читал журнал,
куда контейнер не пишет вовсе. Поэтому здесь же проверяется, что у обоих веб-
джейлов `backend` задан ЯВНО, что `logpath` смотрит на нужный файл и что
`bootstrap.sh` ставит скрипт ровно по тому пути, который называет `jail.conf`.

Запуск:  cd storefront && .venv/bin/python test_crawler_allowlist.py
"""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "deploy" / "fail2ban" / "pseudex-is-crawler"


def _load():
    """Загрузить скрипт без расширения `.py` как модуль.

    `spec_from_file_location` по имени файла без суффикса возвращает спецификацию
    без загрузчика (`spec.loader is None`), и импорт падает на `module_from_spec`.
    SourceFileLoader называет загрузчик явно.

    БАЙТКОД НЕ ПИШЕТСЯ. Иначе загрузка оставляет `__pycache__` прямо в
    `deploy/fail2ban/` — мусор в дереве деплоя от прогона проверки. В движке это
    запрещено настройкой (`PYTHONDONTWRITEBYTECODE=1`); здесь то же самое
    делается на время загрузки.
    """
    loader = importlib.machinery.SourceFileLoader("pseudex_is_crawler", str(_SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    written = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = written
    return module


def fake_dns(ptr_of, ips_of):
    """Поддельный DNS: `ptr_of` — адрес→имя, `ips_of` — имя→адреса."""

    def reverse(ip, timeout=None):
        return ptr_of.get(ip)

    def forward(name, timeout=None):
        return set(ips_of.get(name, ()))

    return reverse, forward


def main() -> int:
    crawler = _load()
    ok = True

    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}"
              + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    # ── граница метки: имя принадлежит домену или нет ──────────────────────
    # `endswith` без точки перед доменом пропускает ВСЁ это, и каждое имя
    # нападающий может завести сам.
    boundary = [
        # (имя, принадлежит ли официальному домену, чем это имя является)
        ("crawl.googlebot.com", True, "настоящее имя Googlebot"),
        ("crawl-66-249-66-1.googlebot.com", True, "настоящее имя Googlebot"),
        ("msnbot-157-55-39-1.search.msn.com", True, "настоящее имя Bing"),
        ("5-255-253-1.spider.yandex.com", True, "настоящее имя Яндекса"),
        ("yandex.ru", True, "ровно домен, без поддомена"),
        ("YANDEX.RU.", True, "регистр и точка на конце не важны"),
        ("evilgooglebot.com", False, "СКЛЕЕНО без точки — endswith-ловушка"),
        ("googlebot.com.attacker.ru", False, "домен в НАЧАЛЕ чужого имени"),
        ("notyandex.ru", False, "endswith-ловушка для yandex.ru"),
        ("yandex.ru.evil.com", False, "домен в начале чужого имени"),
        ("evil.com", False, "чужой домен"),
    ]
    for name, expected, why in boundary:
        got = crawler.matches_domain(name, crawler.CRAWLER_DOMAINS)
        check(got == expected, f"«{name}» → {expected} ({why})", f"получено {got}")

    # ── подтверждение прямым запросом: то, ради чего всё это ──────────────
    real = ("crawl.googlebot.com", {"crawl.googlebot.com": {"66.249.66.1"}})
    reverse, forward = fake_dns({"66.249.66.1": real[0]}, real[1])
    check(crawler.is_crawler("66.249.66.1", reverse=reverse, forward=forward),
          "настоящий робот пропускается")

    # ПОДДЕЛКА: PTR в официальном домене, но прямой запрос указывает на ДРУГОЙ
    # адрес. Ровно так выглядит чужой адрес с украденным именем, и пропустить
    # его значит отдать белый список нападающему.
    reverse, forward = fake_dns(
        {"203.0.113.66": "crawl.googlebot.com"},
        {"crawl.googlebot.com": {"66.249.66.1"}})
    check(not crawler.is_crawler("203.0.113.66", reverse=reverse, forward=forward),
          "подделанный PTR без подтверждения НЕ пропускается")

    # Прямой запрос не ответил вовсе: DNS недоступен или имя висит. Отказ должен
    # быть в сторону бана, а не пропуска.
    reverse, forward = fake_dns(
        {"203.0.113.66": "crawl.googlebot.com"}, {})
    check(not crawler.is_crawler("203.0.113.66", reverse=reverse, forward=forward),
          "молчащий прямой запрос — отказ (fail-closed)")

    # PTR чужой домен, прямой запрос честно подтверждает: домен нападающего
    # сходится сам с собой и всё равно не должен ничего значить.
    reverse, forward = fake_dns(
        {"203.0.113.66": "bot.myscanner.example"},
        {"bot.myscanner.example": {"203.0.113.66"}})
    check(not crawler.is_crawler("203.0.113.66", reverse=reverse, forward=forward),
          "чужой домен не пропускается, даже если подтверждается")

    # ── вход, который не должен ничего пропустить ─────────────────────────
    reverse, forward = fake_dns({}, {})
    for bad in ("", "не-адрес", "999.1.1.1", "66.249.66.1/24"):
        check(not crawler.is_crawler(bad, reverse=reverse, forward=forward),
              f"негодный аргумент не пропускается: {bad!r}")

    # Нет PTR вовсе — имя не назначено, значит и подтверждать нечего.
    reverse, forward = fake_dns({}, {"crawl.googlebot.com": {"66.249.66.1"}})
    check(not crawler.is_crawler("66.249.66.1", reverse=reverse, forward=forward),
          "адрес без PTR не пропускается")

    # ── адрес сравнивается как адрес, а не как строка ─────────────────────
    # Одно имя, несколько адресов: подтверждением служит НАЛИЧИЕ нужного.
    reverse, forward = fake_dns(
        {"66.249.66.1": "crawl.googlebot.com"},
        {"crawl.googlebot.com": {"66.249.66.2", "66.249.66.1", "66.249.66.3"}})
    check(crawler.is_crawler("66.249.66.1", reverse=reverse, forward=forward),
          "адрес найден среди нескольких ответов")

    # IPv6 сравнивается как адрес: `2001:db8::1` и `2001:0db8:0:0::1` — один и
    # тот же адрес, записанный по-разному, и строковое сравнение их разведёт.
    reverse, forward = fake_dns(
        {"2001:db8::1": "spider.yandex.com"},
        {"spider.yandex.com": {"2001:0db8:0:0:0:0:0:1"}})
    check(crawler.is_crawler("2001:db8::1", reverse=reverse, forward=forward),
          "IPv6 сравнивается по значению, а не по написанию")

    # Разные семейства адресов не совпадают никогда.
    reverse, forward = fake_dns(
        {"2001:db8::1": "spider.yandex.com"},
        {"spider.yandex.com": {"192.0.2.1"}})
    check(not crawler.is_crawler("2001:db8::1", reverse=reverse, forward=forward),
          "адрес другого семейства не подтверждает")

    # ── код возврата для fail2ban: 0 — не банить, всё прочее — банить ─────
    # `fail2ban/server/filter.py` (1.0.2) считает вердикт так:
    #     ret_ignore = ret and ret_ignore == 0
    # то есть «не банить» — ЭТО РОВНО НОЛЬ, а не «успешный запуск». Проверяем
    # границу через сам `main`, потому что именно её читает fail2ban.
    check(crawler.main(["prog", "не-адрес"]) != 0,
          "main возвращает ненулевое на негодном аргументе")
    check(crawler.main(["prog"]) != 0, "main без аргумента возвращает ненулевое")

    # ── И ГЛАВНОЕ: ДЖЕЙЛ ВООБЩЕ ЧИТАЕТ ЛОГ ────────────────────────────────
    # Всё, что выше, проверяет скрипт. Но скрипт бесполезен, если джейл не
    # читает тот файл, куда пишет Caddy, — а именно это и было на бою: Debian
    # упаковывает fail2ban с бэкендом `systemd` по умолчанию, джейл с `logpath`
    # на файл МОЛЧА читал журнал systemd, и в `/var/log/fail2ban.log` стояло
    # `uses systemd`, а `get <jail> logpath` отвечал «No file is currently
    # monitored». `Total failed: 0` при 1369 строках 4xx в самом файле.
    #
    # ОТСУТСТВИЕ ЯВНОГО `backend` — ЭТО И ЕСТЬ ДЕФЕКТ, поэтому проверяется
    # именно его наличие, а не «работает ли оно сейчас»: значение по умолчанию
    # живёт в чужом пакете и меняется без нас.
    jail_conf = _SCRIPT.parent / "jail.conf"
    text = jail_conf.read_text(encoding="utf-8")
    jails = {}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1]
            jails[current] = {}
        elif current and "=" in stripped and not stripped.startswith("#"):
            key, _, value = stripped.partition("=")
            jails[current][key.strip()] = value.strip()

    for name in ("pseudex-web-scan", "pseudex-web-login"):
        section = jails.get(name, {})
        check(bool(section), f"раздел [{name}] существует", str(sorted(jails)))
        backend = section.get("backend", "")
        check(backend in ("polling", "pyinotify", "gamin"),
              f"[{name}]: бэкенд задан явно и читает файл",
              f"backend={backend!r} — без этого Debian берёт systemd, "
              f"а Caddy в журнал не пишет")
        check(section.get("logpath", "").endswith("caddy/access.log"),
              f"[{name}]: logpath смотрит на файл Caddy",
              section.get("logpath", ""))
        check(section.get("ignorecommand", "").endswith("pseudex-is-crawler <ip>"),
              f"[{name}]: зовёт скрипт белого списка", section.get("ignorecommand", ""))
        check("key=" in section.get("ignorecache", ""),
              f"[{name}]: результат кэшируется",
              "без кэша проверка зовётся на каждой строке лога")

    # ПУТЬ В КОНФИГЕ ПРОТИВ ПУТИ УСТАНОВКИ. `ignorecommand` назван абсолютным
    # путём, и разойтись с `bootstrap.sh` он может молча: fail2ban тогда просто
    # не найдёт команду, а это, по семантике выше, означает «банить». Дефект,
    # который выглядит как работающая защита.
    bootstrap = (_SCRIPT.parent.parent / "bootstrap.sh").read_text(encoding="utf-8")
    check("/usr/local/bin/" in bootstrap and "pseudex-is-crawler" in bootstrap,
          "bootstrap.sh ставит скрипт туда, откуда его зовёт jail.conf",
          "иначе fail2ban не найдёт команду и будет банить всех")

    print("=" * 60)
    if not ok:
        raise SystemExit("crawler allowlist is not correct")
    print("crawler OK — робот пропускается по подтверждённому имени, подделка и "
          "чужой домен не пропускаются, джейл читает файл Caddy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
