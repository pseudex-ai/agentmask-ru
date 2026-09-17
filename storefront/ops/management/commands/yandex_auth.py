"""OAuth Яндекса: получить refresh-токен ОДИН РАЗ и больше не возвращаться.

ЗАЧЕМ КОМАНДА, А НЕ ИНСТРУКЦИЯ В ТЕКСТЕ. Обмен кода на токен выполняется
ровно один раз в жизни приложения, и выполняет его человек руками в момент,
когда голова занята другим. Скрипт, лежащий в репозитории, делает этот шаг
воспроизводимым: он же печатает адрес авторизации, он же кладёт секрет в
`.env` (с бэкапом и правами 600), он же проверяет, что токен действительно
работает, — и всё это одна команда вместо четырёх curl'ов, которые надо
вспомнить.

ЧТО ПЕЧАТАЕТСЯ, А ЧТО НЕТ. Refresh-токен печатается: это единственный способ
отдать его оператору, и он же — то, что кладётся в `.env`. Client secret не
печатается никогда: он уже лежит в `.env`, и его появление в терминале — это
его появление в истории шелла.

    python3 manage.py yandex_auth --url
    python3 manage.py yandex_auth <код> --env-file /opt/pseudex/deploy/.env
    python3 manage.py yandex_auth --status
"""

import datetime
import os
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ops import yandex_api

_KEY = "YANDEX_OAUTH_REFRESH_TOKEN"


class Command(BaseCommand):
    help = "OAuth Яндекса: адрес авторизации, обмен кода, проверка токена"

    def add_arguments(self, parser) -> None:
        parser.add_argument("code", nargs="?", default="",
                            help="код со страницы авторизации (одноразовый)")
        parser.add_argument("--url", action="store_true",
                            help="напечатать адрес авторизации и выйти")
        parser.add_argument("--status", action="store_true",
                            help="проверить, что токен жив и видит аккаунт")
        parser.add_argument("--env-file", default="",
                            help=f"куда записать {_KEY} (с бэкапом, chmod 600)")

    def handle(self, *args, **options) -> None:
        client_id = os.environ.get("YANDEX_OAUTH_CLIENT_ID", "")
        if options["url"]:
            return self._url(client_id)
        if options["status"]:
            return self._status()
        if not options["code"]:
            raise CommandError(
                "Укажите код со страницы авторизации, либо --url, либо --status."
            )
        if not client_id or not os.environ.get("YANDEX_OAUTH_CLIENT_SECRET"):
            raise CommandError(
                "Нет YANDEX_OAUTH_CLIENT_ID / YANDEX_OAUTH_CLIENT_SECRET. "
                "Обмен кода без пары приложения невозможен."
            )
        self._exchange(options["code"], options["env_file"])

    def _url(self, client_id: str) -> None:
        """Адрес, который открывает владелец. Печатается, а не открывается.

        Команда, открывающая браузер, на сервере без графической сессии просто
        падает; здесь же адрес можно скопировать на машину, где браузер есть, —
        и это обычный случай, потому что авторизуется владелец аккаунта, а не
        сервер.
        """
        if not client_id:
            raise CommandError("Нет YANDEX_OAUTH_CLIENT_ID в окружении.")
        self.stdout.write(
            "https://oauth.yandex.ru/authorize?response_type=code"
            f"&client_id={client_id}"
        )
        self.stdout.write(
            "\nОткройте адрес под тем аккаунтом Яндекса, который владеет "
            "счётчиком Метрики и кампаниями Директа.\n"
            "Яндекс покажет код — передайте его сюда:\n"
            "  manage.py yandex_auth <код> --env-file <путь к .env>"
        )

    def _exchange(self, code: str, env_file: str) -> None:
        try:
            payload = yandex_api.exchange_code(code)
        except yandex_api.YandexError as error:
            # КОД ОДНОРАЗОВЫЙ И ЖИВЁТ НЕДОЛГО. Самая частая причина отказа —
            # не неверный код, а повторно использованный или просроченный;
            # сказать это вслух дешевле, чем оставить оператора гадать.
            raise CommandError(
                f"{error}\nКод одноразовый и недолговечный — получите новый "
                "по `yandex_auth --url`."
            ) from None
        refresh = payload.get("refresh_token", "")
        if not refresh:
            raise CommandError(
                "Яндекс выдал access-токен без refresh-токена. Так бывает, "
                "если приложение не запрашивает offline-доступ: без refresh "
                "интеграция умрёт через час. Проверьте настройки приложения."
            )
        self.stdout.write(self.style.SUCCESS("Токен получен."))
        self.stdout.write(f"{_KEY}={refresh}")
        if env_file:
            self._write(Path(env_file), refresh)
        else:
            self.stdout.write(
                f"\nПоложите строку в .env как {_KEY}=... вручную "
                "или повторите с --env-file."
            )

    def _write(self, path: Path, refresh: str) -> None:
        """Правка `.env` НА МЕСТЕ, с бэкапом и правами.

        Не «дописать в конец»: файл, в который дописали второй раз, содержит
        две строки одного имени, и какая из них победит — зависит от того, как
        читает их docker compose. Бэкап именован временем, потому что
        «.env.bak» перезаписывается вторым запуском ровно тогда, когда первый
        бэкап понадобился.
        """
        if not path.exists():
            raise CommandError(f"Нет файла {path}")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.bak-{stamp}")
        shutil.copy2(path, backup)
        lines = path.read_text(encoding="utf-8").splitlines()
        replaced = False
        for index, line in enumerate(lines):
            if line.strip().startswith(f"{_KEY}="):
                lines[index] = f"{_KEY}={refresh}"
                replaced = True
        if not replaced:
            lines.append(f"{_KEY}={refresh}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
        self.stdout.write(self.style.SUCCESS(
            f"Записано в {path} (бэкап: {backup.name}, права 600, "
            f"{'заменена' if replaced else 'добавлена'} строка)."
        ))
        self.stdout.write(
            "Контейнер подхватит значение при следующем пересоздании — "
            "то есть при ближайшей выкатке тега."
        )

    def _status(self) -> None:
        if not yandex_api.configured():
            self.stdout.write(
                "Интеграция выключена: нет client_id / client_secret / "
                "refresh-токена. Это не ошибка — витрина работает без неё."
            )
            return
        try:
            token = yandex_api.access_token()
            found = yandex_api.counters()
        except yandex_api.YandexError as error:
            raise CommandError(f"Токен не работает: {error}") from None
        self.stdout.write(self.style.SUCCESS(
            f"Access-токен получен ({len(token)} символов), "
            f"счётчиков видно: {len(found)}."
        ))
        for counter in found[:10]:
            # `site` — СТРОКА, А НЕ СЛОВАРЬ. Первая версия читала
            # `site.domain` и падала на живом ответе: у Метрики это просто
            # домен. Поймано первым же обращением к настоящему API — на
            # выдуманном ответе такая форма выглядела правдоподобно.
            self.stdout.write(f"  {counter.get('id')}  {counter.get('site', '')}  "
                              f"{counter.get('name', '')}")
        # ДИРЕКТ ПРОВЕРЯЕТСЯ ОТДЕЛЬНО И НЕ РОНЯЕТ ПРОВЕРКУ. Заявка на доступ
        # рассматривается до семи дней, и всё это время Директ отвечает ошибкой
        # 58 — при том что Метрика уже работает. Общая проверка, падающая на
        # этом, сказала бы «токен не работает» про работающий токен.
        try:
            campaigns = yandex_api.direct_campaigns()
        except yandex_api.YandexError as error:
            self.stdout.write(
                f"Директ: {error}\n"
                "  Если это «Incomplete registration» / ошибка 58 — заявка на "
                "доступ к API ещё не одобрена. Метрике это не мешает."
            )
            return
        self.stdout.write(self.style.SUCCESS(
            f"Директ: кампаний видно {len(campaigns)}."
        ))
