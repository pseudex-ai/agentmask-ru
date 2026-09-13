"""Ночная свёртка визитов и удаление сырья старше срока.

ДВЕ РАЗНЫЕ ПАМЯТИ, И ЭТО ГЛАВНОЕ РЕШЕНИЕ ФАЙЛА.

  * СЫРЬЁ живёт 90 суток и отвечает на вопрос «с какой страницы пришёл вот тот
    визит». Такой вопрос задают о недавнем, и хранить ради него годы — значит
    держать таблицу, которая растёт линейно и не нужна.
  * СВЁРТКА живёт вечно и отвечает на «сколько было в марте» и «рос ли канал».
    Такой вопрос задают через год, и ответить на него сырьём, которого уже нет,
    нельзя.

Отсюда порядок внутри прохода: сначала свернуть, потом удалить. Обратный
порядок однажды удалил бы сутки, которые ещё не свёрнуты, и дыра в ряду
осталась бы навсегда — восстановить её неоткуда.

СВЁРТКА ИДЕМПОТЕНТНА и пересчитывает СУТКИ ЦЕЛИКОМ, а не дописывает: команда
может идти дважды, может догонять пропущенные дни после простоя, и результат
один и тот же. Дописывание сломалось бы на первом же повторе.

    python3 manage.py rollup_analytics
    python3 manage.py rollup_analytics --keep-days 180
"""

import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from ops.analytics_models import Visit, VisitDay

# Сколько суток держим СЫРЬЁ. Свёртка не удаляется никогда.
KEEP_DAYS = 90

# Измерения свёртки. Кортежем, а не списком полей врозь: добавить разрез — это
# одна строка здесь, а не миграция, потому что измерение хранится значением.
DIMENSIONS = (
    ("path", "path"),
    ("referrer", "referrer_host"),
    ("utm_source", "utm_source"),
    ("utm_campaign", "utm_campaign"),
    ("device", "device"),
    ("browser", "browser"),
    ("os", "os"),
)


class Command(BaseCommand):
    help = "Свернуть визиты по суткам и удалить сырьё старше срока"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--keep-days", type=int, default=KEEP_DAYS)
        parser.add_argument("--days", type=int, default=7,
                            help="сколько последних суток пересчитать")

    def handle(self, *args, **options) -> None:
        today = timezone.localdate()
        # ПЕРЕСЧИТЫВАЕМ НЕСКОЛЬКО ПОСЛЕДНИХ СУТОК, а не только вчерашние:
        # команда могла не идти — простой, перезапуск, авария — и один день
        # окна закрыл бы дыру только если её не было.
        days = [today - datetime.timedelta(days=n)
                for n in range(1, max(1, options["days"]) + 1)]
        written = 0
        for day in days:
            written += self._rollup(day)

        cutoff = today - datetime.timedelta(days=options["keep_days"])
        removed, _ = Visit.objects.filter(at__date__lt=cutoff).delete()
        self.stdout.write(f"свёрнуто строк: {written} за {len(days)} сут · "
                          f"удалено сырья: {removed} старше {cutoff}")

    def _rollup(self, day: datetime.date) -> int:
        rows = Visit.objects.filter(at__date=day, is_bot=False)
        written = 0
        with transaction.atomic():
            # Сутки пересчитываются целиком: старые строки этих суток удаляются
            # перед записью, иначе повтор удвоил бы числа.
            VisitDay.objects.filter(day=day).delete()

            total = rows.aggregate(visits=Count("id"),
                                   visitors=Count("visitor", distinct=True))
            if not total["visits"]:
                return 0
            VisitDay.objects.create(day=day, dimension="total", value="",
                                    visits=total["visits"],
                                    visitors=total["visitors"] or 0)
            written += 1

            for name, field in DIMENSIONS:
                grouped = (rows.exclude(**{field: ""}).values(field)
                           .annotate(visits=Count("id"),
                                     visitors=Count("visitor", distinct=True)))
                VisitDay.objects.bulk_create([
                    VisitDay(day=day, dimension=name, value=row[field][:200],
                             visits=row["visits"], visitors=row["visitors"])
                    for row in grouped
                ])
                written += len(grouped)
        return written
