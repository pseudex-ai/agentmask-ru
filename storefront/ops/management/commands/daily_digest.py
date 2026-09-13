"""Утренняя сводка в телеграм: что случилось за сутки и что с этим делать.

ЗАЧЕМ ОТДЕЛЬНО ОТ СТОРОЖА. `deploy/watch.sh` кричит, когда что-то СЛОМАЛОСЬ, и
молчит, когда всё хорошо — это правильно для тревоги и бесполезно для
управления. Сводка приходит РАЗ В СУТКИ И ВСЕГДА, даже когда цифры нулевые:
ноль регистраций третий день подряд — это факт, ради которого её и читают, а
канал, который молчит в такой день, сообщает «всё в порядке».

ЧТО ВНУТРИ И ПОЧЕМУ ИМЕННО ЭТО. Сводка отвечает на три вопроса, которые задают
утром: сколько пришло и откуда, где отвалились, и кто должен денег. Всё
остальное — на экране, за которым надо идти специально; сюда попадает то, ради
чего стоит открыть телефон.

ПЕРСОНАЛЬНЫХ ДАННЫХ ЗДЕСЬ НЕТ. Ни почт, ни названий организаций — только
идентификаторы и числа. Телеграм — чужой сервис, и отправлять туда почту
клиента значило бы сделать ровно то, от чего продукт защищает.

    python3 manage.py daily_digest            # отправить
    python3 manage.py daily_digest --dry-run  # напечатать
"""

import datetime
import os
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from billing.models import Invoice, Subscription
from ops.analytics_models import Funnel, Visit

_NOTIFY = Path("/deploy/notify.sh")


class Command(BaseCommand):
    help = "Сводка за сутки в телеграм"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options) -> None:
        now = timezone.now()
        since = now - datetime.timedelta(days=1)
        before = since - datetime.timedelta(days=1)
        today = timezone.localdate()

        lines: list[str] = []

        # --- трафик, со сравнением. Число без вчерашнего не говорит ничего.
        live = Visit.objects.filter(at__gte=since, is_bot=False)
        visits = live.count()
        visitors = live.values("visitor").distinct().count()
        was = (Visit.objects.filter(at__gte=before, at__lt=since, is_bot=False)
               .values("visitor").distinct().count())
        delta = f" ({visitors - was:+d} ко вчера)" if was else ""
        lines.append(f"Посетителей: {visitors}{delta}, просмотров {visits}")

        top = list(live.exclude(referrer_host="").values("referrer_host")
                   .annotate(n=Count("visitor", distinct=True)).order_by("-n")[:3])
        if top:
            lines.append("Источники: " + " · ".join(
                f"{r['referrer_host']} {r['n']}" for r in top))

        # --- воронка за сутки. Отказы отдельно: они называют, что чинить.
        steps = dict(Funnel.objects.filter(at__gte=since)
                     .values_list("step").annotate(n=Count("id")))
        funnel = " → ".join(
            f"{title} {steps.get(code, 0)}"
            for code, title in Funnel.STEPS
            if code != Funnel.SIGNUP_REFUSED and steps.get(code))
        lines.append("Воронка: " + (funnel or "движения не было"))

        refused = list(Funnel.objects.filter(step=Funnel.SIGNUP_REFUSED, at__gte=since)
                       .values("detail").annotate(n=Count("id")).order_by("-n"))
        if refused:
            lines.append("Форма отказала: " + ", ".join(
                f"{r['detail'] or 'без причины'} {r['n']}" for r in refused))

        # --- деньги. Три числа, каждое требует действия или его отсутствия.
        paid = Invoice.objects.filter(paid_at__gte=since)
        if paid.exists():
            total = sum(i.total for i in paid)
            lines.append(f"💰 Оплачено: {paid.count()} счёт(ов) на {total} ₽")

        overdue = Invoice.objects.filter(state=Invoice.ISSUED,
                                         due_at__lt=today).count()
        if overdue:
            lines.append(f"⚠️ Просрочено счетов: {overdue}")

        stuck = Invoice.objects.filter(state=Invoice.PAID,
                                       service_resumed_at__isnull=True).count()
        if stuck:
            lines.append(f"🔴 Оплачено, но обслуживание НЕ возобновлено: {stuck} — "
                         f"мы должны клиенту работу")

        trials = Subscription.objects.filter(
            state=Subscription.TRIAL,
            trial_ends_at__lte=now + datetime.timedelta(days=3)).count()
        if trials:
            lines.append(f"Пробный период кончается в ближайшие 3 дня: {trials}")

        active = Subscription.objects.filter(state=Subscription.ACTIVE).count()
        past_due = Subscription.objects.filter(state=Subscription.PAST_DUE).count()
        lines.append(f"Подписок: {active} активных, {past_due} остановленных")

        body = "\n".join(lines)
        title = f"Сводка за сутки · {today:%d.%m.%Y}"

        if options["dry_run"]:
            self.stdout.write(f"{title}\n{body}")
            return
        self._send(title, body)

    def _send(self, title: str, body: str) -> None:
        """Через тот же `notify.sh`, что и сторож.

        ОДИН КАНАЛ ОТПРАВКИ, А НЕ ВТОРОЙ СВОЙ: отправка — единственное место,
        где ошибка молчалива по природе, и второй экземпляр её логики означал бы
        два места, где она может сломаться по-разному.
        """
        if not _NOTIFY.exists():
            self.stdout.write(f"{title}\n{body}")
            self.stderr.write(f"нет {_NOTIFY} — сводка напечатана, а не отправлена")
            return
        subprocess.run(["sh", str(_NOTIFY), "info", title, body],
                       check=False, timeout=30, env=os.environ.copy())
