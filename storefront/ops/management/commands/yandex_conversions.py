"""Офлайн-конверсии: рассказать Метрике о том, чего счётчик увидеть не мог.

ПОЧЕМУ СЕРВЕР, А НЕ `reachGoal` НА СТРАНИЦЕ. Обе конверсии случаются там, где
счётчика нет и быть не должно: `/activate` несёт в адресе подписанный токен,
`/welcome` показывает клиенту его лицензионный ключ. Поставить туда счётчик
значило бы отдать токен и ключ третьей стороне — ровно то, от чего продукт
защищает. Оплата не имеет страницы вовсе: её подтверждает вебхук ЮKassa.

Поэтому конверсия уходит С СЕРВЕРА, офлайн-загрузкой, и привязывается по
`yclid` — идентификатору клика по объявлению Директа, который дописывается к
рекламной ссылке и сохраняется у нас вместе с первым касанием. `ClientId`
Метрики потребовал бы куки (лендинг обещает их не ставить), `UserId` — нашего
собственного сквозного идентификатора, которого мы сознательно не заводим.

ЦЕЛИ ДОЛЖНЫ СУЩЕСТВОВАТЬ ЗАРАНЕЕ, и заводит их эта же команда (`--setup-goals`):
офлайн-конверсия сопоставляется с целью ПО ИДЕНТИФИКАТОРУ, и опечатка в нём не
даёт ошибки — Метрика принимает файл, сопоставляет ноль записей и сообщает об
этом статусом `LINKAGE_FAILURE` через три часа.

    python3 manage.py yandex_conversions --setup-goals   # один раз
    python3 manage.py yandex_conversions --dry-run       # посмотреть
    python3 manage.py yandex_conversions                 # отправить
"""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ops import yandex_api
from ops.analytics_models import ConversionSent, Funnel

# ИДЕНТИФИКАТОР ЦЕЛИ И ЧЕЛОВЕЧЕСКОЕ ИМЯ — РЯДОМ, ПОТОМУ ЧТО ЭТО ОДНО РЕШЕНИЕ.
# Идентификатор уходит в Метрику и в CSV; имя видит владелец в панели, когда
# смотрит отчёт по рекламе. Разнести их по разным местам значило бы завести
# цель «signup» с подписью, не имеющей к ней отношения.
#
# РЕГИСТРАЦИИ ЗДЕСЬ НЕТ, И ЭТО НЕ ЗАБЫВЧИВОСТЬ. Её цель считает БРАУЗЕР: экран
# «проверьте почту» — публичная страница со счётчиком, и `reachGoal` уходит от
# посетителя, то есть под баннер согласия. Оставить её ещё и тут значило бы
# считать одно событие дважды — а Метрика не складывает браузерную цель с
# офлайн-конверсией, она показывает обе. Активация и оплата в браузере
# невозможны: первая несёт токен в адресе, вторая не имеет страницы вовсе.
TARGETS = [
    (Funnel.ACTIVATED, "activated", "pseudex: подтверждение почты"),
    (Funnel.PAID, "paid", "pseudex: оплата"),
]


class Command(BaseCommand):
    help = "Отправить офлайн-конверсии в Метрику (и завести цели)"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true",
                            help="показать, что было бы отправлено")
        parser.add_argument("--setup-goals", action="store_true",
                            help="завести цели в счётчике и выйти")
        parser.add_argument("--limit", type=int, default=5000,
                            help="потолок строк на одну цель за запуск")

    def handle(self, *args, **options) -> None:
        # Setup mutates Metrika before _send can apply its dry-run branch.
        # Reject the combination here as call_command can bypass CLI parsing.
        if options["dry_run"] and options["setup_goals"]:
            raise CommandError(
                "--setup-goals нельзя сочетать с --dry-run: настройка целей "
                "изменяет Метрику. Для просмотра используйте только --dry-run."
            )
        if not settings.METRIKA_ID:
            raise CommandError(
                "PSEUDEX_METRIKA_ID не задан — конверсию некуда отправлять."
            )
        if options["setup_goals"]:
            return self._setup_goals()
        # `--dry-run` НЕ ТРЕБУЕТ НИ ТОКЕНА, НИ ФЛАГА: он ничего не отправляет,
        # и посмотреть, что ушло бы, нужно ровно до того, как это включено.
        if not options["dry_run"]:
            # ОТПРАВКА — ЯВНОЕ РЕШЕНИЕ, А НЕ СЛЕДСТВИЕ ТОКЕНА. Счётчик
            # спрашивает согласие баннером, а конверсия уходит с сервера и на
            # него не смотрит: без этого флага отказавшийся «Не считать» всё
            # равно отдал бы в Яндекс факт своей регистрации. Это не
            # осторожность, а соответствие разделу 9bis политики, который
            # обещает, что без ответа не уходит ничего.
            if not settings.YANDEX_CONVERSIONS:
                raise CommandError(
                    "PSEUDEX_YANDEX_CONVERSIONS не поднят: отправка конверсий "
                    "выключена. Она уходит С СЕРВЕРА и не спрашивает согласия "
                    "баннером, поэтому включается отдельным решением "
                    "владельца (см. .env.example). Что ушло бы — --dry-run."
                )
            if not yandex_api.configured():
                raise CommandError(
                    "Яндекс API не настроен: нет refresh-токена. "
                    "Сначала `manage.py yandex_auth --url`."
                )
        self._send(options["dry_run"], options["limit"])

    def _setup_goals(self) -> None:
        """Завести недостающие цели. Существующие не трогаются.

        ПОИСК ПО ИДЕНТИФИКАТОРУ, А НЕ ПО ИМЕНИ. Цель могла быть заведена
        владельцем вручную под другим названием — вторая такая же разделила бы
        статистику надвое, и обе выглядели бы рабочими.
        """
        # ИДЕНТИФИКАТОР ЧИТАЕТСЯ ИЗ `url`, А НЕ `value`. У Метрики строка
        # условия лежит в `url` независимо от типа цели — так же, как при
        # создании. Читать `value` значило бы не найти ни одной существующей
        # цели и завести дубли, разделив статистику надвое.
        existing = {(goal.get("conditions") or [{}])[0].get("url", "")
                    for goal in yandex_api.goals()}
        for _step, identifier, name in TARGETS:
            if identifier in existing:
                self.stdout.write(f"цель {identifier} уже есть")
                continue
            try:
                yandex_api.create_goal(name, identifier)
            except yandex_api.YandexError as error:
                raise CommandError(f"не удалось завести цель {identifier}: "
                                   f"{error}") from None
            self.stdout.write(self.style.SUCCESS(f"заведена цель {identifier}"))
        self.stdout.write(
            "Цели появятся в панели сразу, но статистика по ним начнёт "
            "наполняться после первой загрузки."
        )

    def _send(self, dry_run: bool, limit: int) -> None:
        from accounts.models import Organization

        # ТОЛЬКО ОРГАНИЗАЦИИ С YCLID. Без него Метрика не привяжет конверсию ни
        # к какому визиту, и строка не «отправится неудачно» — она не
        # отправится вовсе. Поэтому отбор здесь, а не в момент загрузки: так
        # видно, сколько клиентов пришло не по рекламе, и это число — ответ на
        # вопрос «работает ли канал», а не мусор в логе.
        clicked = dict(Organization.objects.exclude(source_yclid="")
                       .values_list("id", "source_yclid"))
        sent = set(ConversionSent.objects.values_list("organization_id", "target"))
        total_sent = total_skipped = 0

        for step, identifier, name in TARGETS:
            # РАННЕЕ СОБЫТИЕ, А НЕ ЛЮБОЕ. Организация, заплатившая трижды,
            # обязана дать ОДНУ конверсию «оплата»: повтор учит Директ на
            # завышенной ценности, а `ConversionSent` гарантирует
            # единственность только между запусками, не внутри одного.
            rows, seen = [], set()
            for org_id, at, detail in (Funnel.objects.filter(step=step)
                                       .order_by("at")
                                       .values_list("organization_id", "at",
                                                    "detail")):
                if org_id in seen or org_id not in clicked:
                    continue
                if (org_id, identifier) in sent:
                    continue
                seen.add(org_id)
                rows.append({
                    # `org_id` НЕ УХОДИТ В CSV — он здесь для нашей отметки.
                    # Обратный поиск «по yclid найти организацию» дал бы неверную
                    # отметку, если один и тот же человек зарегистрировался
                    # дважды: у двух организаций один клик, и вторая осталась бы
                    # без конверсии навсегда.
                    "org_id": org_id,
                    "target": identifier, "at": at,
                    "yclid": clicked[org_id],
                    # ЦЕНА ЕСТЬ ТОЛЬКО У ОПЛАТЫ, и лежит она в `detail` — так
                    # её записал биллинг. Отдельный запрос к счетам был бы
                    # вторым источником той же правды, и он разошёлся бы с
                    # первым ровно тогда, когда счёт исправили.
                    "price": _price(detail) if step == Funnel.PAID else None,
                    "currency": "RUB",
                })
                if len(rows) >= limit:
                    break

            if not rows:
                self.stdout.write(f"{identifier}: нечего отправлять")
                continue
            if dry_run:
                self.stdout.write(f"{identifier}: {len(rows)} строк (dry-run)")
                continue

            result = yandex_api.upload_conversions(rows, comment=name)
            uploading = result.get("uploading") or {}
            # ОТМЕТКА ТОЛЬКО ПОСЛЕ УСПЕШНОГО ОТВЕТА. Запись «отправлено»,
            # сделанная до запроса, при отказе Метрики оставила бы конверсию
            # неотправленной навсегда — и это ровно тот молчаливый пропуск,
            # ради которого таблица заведена.
            for row in rows:
                ConversionSent.objects.get_or_create(
                    organization_id=row["org_id"],
                    target=identifier,
                    defaults={"uploading_id": uploading.get("id") or 0,
                              "status": uploading.get("status", "")})
            total_sent += result.get("sent", len(rows))
            total_skipped += result.get("skipped", 0)
            self.stdout.write(self.style.SUCCESS(
                f"{identifier}: отправлено {result.get('sent', len(rows))}, "
                f"загрузка {uploading.get('id')} "
                f"({uploading.get('status', '?')})"))

        if dry_run:
            self.stdout.write("dry-run: ничего не отправлено")
            return
        self.stdout.write(f"Итого строк: {total_sent}, без yclid пропущено: "
                          f"{total_skipped}. Отчёты обновятся в течение 3 часов.")


def _price(detail: str):
    """Сумма из `detail` шага «заплатил». Не разобралась — цены нет.

    ЦЕНА НЕ ОБЯЗАТЕЛЬНА ДЛЯ КОНВЕРСИИ, а вот падать из-за неё нельзя: шаг
    воронки уже случился, и деньги пришли. Строка без цены засчитается как
    конверсия без ценности — это хуже, чем с ценой, и несравнимо лучше, чем
    отсутствие конверсии.
    """
    try:
        return Decimal(detail)
    except (InvalidOperation, TypeError, ValueError):
        return None
