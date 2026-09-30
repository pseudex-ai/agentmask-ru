"""Снимок поиска за сутки: сколько страниц в индексе и где мы в выдаче.

    python3 manage.py seo_snapshot                 # собрать и сохранить
    python3 manage.py seo_snapshot --line          # одна строка для сводки
    python3 manage.py seo_snapshot --recrawl https://pseudex.ru/faq
    python3 manage.py seo_snapshot --history 14    # последние две недели

ЗАЧЕМ ОТДЕЛЬНАЯ КОМАНДА, ЕСЛИ СВОДКА И ТАК СОБИРАЕТ СНИМОК. Утренняя сводка
зовёт сбор, потому что он нужен ей здесь и сейчас. Эта команда нужна человеку:
посмотреть, что собралось, отправить переобход руками и НЕ ЖДАТЬ УТРА. Обе
ходят в одну и ту же функцию, поэтому разойтись они не могут.
"""

import datetime

from django.core.management.base import BaseCommand

from ops import seo
from ops.models import SeoDay


class Command(BaseCommand):
    help = "Собрать снимок поиска за сутки (индекс, позиции, запросы с показами)"

    def add_arguments(self, parser):
        parser.add_argument("--line", action="store_true",
                            help="напечатать строку для утренней сводки и выйти")
        parser.add_argument("--recrawl", nargs="*", default=[],
                            help="адреса для постановки в очередь переобхода")
        parser.add_argument("--history", type=int, default=0,
                            help="показать последние N суток")

    def handle(self, *args, **options):
        if options["line"]:
            today = datetime.date.today()
            snapshot = SeoDay.objects.filter(day=today).first() or seo.collect(today)
            before = SeoDay.objects.filter(day__lt=today).order_by("-day").first()
            for line in seo.digest_lines(snapshot, before):
                self.stdout.write(line)
            return

        snapshot = seo.collect(recrawl=options["recrawl"] or None)
        self.stdout.write(f"Снимок за {snapshot.day:%d.%m.%Y} сохранён")
        for line in seo.digest_lines(snapshot):
            self.stdout.write(line)
        # ИСТОЧНИК, КОТОРЫЙ МОЛЧИТ, НАЗЫВАЕТСЯ ВСЛУХ. Иначе пустое место на
        # экране читалось бы как «нас нет в поиске», а это разные новости.
        for name, state in (snapshot.sources or {}).items():
            if state != "ok":
                self.stdout.write(f"  {name}: {state}")
        if options["history"]:
            self.stdout.write("")
            for row in SeoDay.objects.all()[: options["history"]]:
                self.stdout.write(
                    f"  {row.day:%d.%m}  индекс {row.pages_in_index if row.pages_in_index is not None else '—'}"
                    f"  оценка {row.pages_in_index_estimate if row.pages_in_index_estimate is not None else '—'}"
                    f"  топ-10 {seo.in_top10(row)}/{len(row.positions)}")
