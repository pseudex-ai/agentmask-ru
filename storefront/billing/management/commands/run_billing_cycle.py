"""Один проход биллингового цикла: выставить, напомнить, остановить, дочинить.

ЗАЧЕМ ЭТО СУЩЕСТВУЕТ. `build_invoice`, `mark_paid` и `mark_unpaid` были
написаны, покрыты тестами и НЕ ВЫЗЫВАЛИСЬ НИОТКУДА: единственным упоминанием
`build_invoice` в проде была подсказка в `deploy/simulate.py` «начертите счёт из
django shell». Значит триал не кончался никогда, счёт не выставлялся никогда, а
неплательщик работал вечно. Набор исправных механизмов без того, кто их зовёт, —
это не бизнес, это библиотека.

ЧЕТЫРЕ ПЕРЕХОДА, И ПОРЯДОК НЕ СЛУЧАЕН:

  1. триал кончился         -> счёт (первый в жизни клиента)
  2. оплаченный период истёк -> счёт (продление)
  3. счёт просрочен          -> остановка обслуживания
  4. оплачен, но не возобновлён -> повторить возобновление

Четвёртый — сторож, а не переход. `mark_paid` записывает деньги ПЕРВЫМИ и
возобновляет обслуживание вторым, поэтому его сетевой отказ оставляет клиента
оплаченным и стоящим. Единственное, что это чинит, — повторный вызов, и у
банковского перевода нет доставки, которая его принесёт. Поэтому зовём отсюда.

ИДЕМПОТЕНТНОСТЬ — ЕДИНСТВЕННОЕ ТРЕБОВАНИЕ К ЭТОЙ КОМАНДЕ. Расписание может
запустить её дважды, systemd — повторить после падения, оператор — руками.
Каждый шаг проверяет, не сделан ли он уже, СТРОКОЙ В БАЗЕ, а не флагом в
памяти: счёт за период существует или не существует, и это видно всем процессам
сразу.

    python3 manage.py run_billing_cycle            # сделать
    python3 manage.py run_billing_cycle --dry-run  # только показать
"""

from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from billing import licensing, services
from billing.models import Invoice, Subscription

# Из `services`, а не отсюда: это же число печатается на лендинге, и три копии
# одного срока разъезжаются молча.
GRACE_DAYS = services.GRACE_DAYS


def _billing_email(organization) -> str:
    """Кому слать счёт. Владельцу организации.

    Не `organization.email` — такого поля нет; адрес живёт на пользователе через
    `Membership`. Пустая строка означает «слать некому», и это НЕ ошибка цикла:
    остановка неплательщика важнее письма и не должна падать вместе с ним.
    """
    membership = (organization.memberships
                  .select_related("user")
                  .order_by("created_at")
                  .first())
    return membership.user.email if membership else ""


class Command(BaseCommand):
    help = "Один проход биллингового цикла"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true",
                            help="показать, что произошло бы, и ничего не менять")

    def handle(self, *args, **options) -> None:
        dry = options["dry_run"]
        now = timezone.now()
        self.dry = dry
        self.done: list[str] = []

        self._issue_for_ended_trials(now)
        self._issue_for_ended_periods(now)
        self._stop_overdue(now)
        self._resume_stuck()

        prefix = "БЫЛО БЫ: " if dry else ""
        for line in self.done:
            self.stdout.write(prefix + line)
        self.stdout.write(f"{len(self.done)} действий")

    # --- 1 и 2: выставление ------------------------------------------------

    def _issue_for_ended_trials(self, now) -> None:
        expired = (Subscription.objects
                   .select_related("organization", "plan")
                   .filter(state=Subscription.TRIAL, trial_ends_at__lte=now))
        for subscription in expired:
            self._issue(subscription, now, "триал кончился")

    def _issue_for_ended_periods(self, now) -> None:
        # ОТМЕНИВШИЙ НЕ ПОЛУЧАЕТ СЧЁТА. `cancel_at_period_end` значит «доработаю
        # оплаченное и уйду»; выставить ему счёт за следующий период — это
        # списать деньги за услугу, от которой он отказался письменно.
        due = (Subscription.objects
               .select_related("organization", "plan")
               .filter(state=Subscription.ACTIVE,
                       cancel_at_period_end=False,
                       current_period_end__lte=now))
        for subscription in due:
            self._issue(subscription, now, "период истёк")

        cancelling = (Subscription.objects
                      .filter(state=Subscription.ACTIVE,
                              cancel_at_period_end=True,
                              current_period_end__lte=now))
        for subscription in cancelling:
            self.done.append(f"{subscription.organization_id}: отменена по концу периода")
            if self.dry:
                continue
            licensing.set_status(subscription.organization_id, "unpaid")
            subscription.state = Subscription.CANCELLED
            subscription.save(update_fields=["state"])

    def _issue(self, subscription, now, why: str) -> None:
        organization = subscription.organization
        period_start = subscription.current_period_end.date()
        period_end = (subscription.current_period_end + timedelta(days=30)).date()

        # ИДЕМПОТЕНТНОСТЬ СТРОКОЙ. Счёт за этот период уже может существовать —
        # цикл запустили дважды, или прошлый проход упал после создания счёта и
        # до отправки письма. Проверяется НЕ состояние подписки (оно меняется
        # только после оплаты), а наличие невоидного счёта на этот период.
        if Invoice.objects.filter(organization=organization,
                                  period_start=period_start).exclude(
                                      state=Invoice.VOID).exists():
            return

        self.done.append(f"{organization.id}: счёт за {period_start}..{period_end} ({why})")
        if self.dry:
            return

        invoice = services.build_invoice(organization, period_start, period_end)
        invoice.state = Invoice.ISSUED
        invoice.issued_at = now
        invoice.save(update_fields=["state", "issued_at"])
        self._send_invoice(organization, invoice)

    def _send_invoice(self, organization, invoice: Invoice) -> None:
        address = _billing_email(organization)
        if not address:
            return
        lines = [f"абонплата {invoice.plan_amount} ₽"]
        if invoice.metered_amount > 0:
            lines.append(f"объём сверх включённого: {invoice.metered_requests} "
                         f"запросов — {invoice.metered_amount} ₽")
        # ПИСЬМО НЕ НЕСЁТ НИЧЕГО СЕКРЕТНОГО, как и все остальные наши письма:
        # ссылка на кабинет, а не ключ и не платёжный токен.
        link = f"{settings.SITE_URL}/app/invoices/{invoice.number}"
        send_mail(
            subject=f"pseudex — счёт {invoice.number} на {invoice.total} ₽",
            message=("Здравствуйте!\n\n"
                     f"Счёт {invoice.number} за период "
                     f"{invoice.period_start:%d.%m.%Y}–{invoice.period_end:%d.%m.%Y}:\n\n"
                     + "\n".join("  " + line for line in lines)
                     + f"\n\nИтого: {invoice.total} ₽. Оплатить до "
                     f"{invoice.due_at:%d.%m.%Y}.\n\n{link}\n"),
            from_email=None,
            recipient_list=[address],
            fail_silently=True,
        )

    # --- 3: остановка ------------------------------------------------------

    def _stop_overdue(self, now) -> None:
        deadline = (now - timedelta(days=GRACE_DAYS)).date()
        overdue = (Invoice.objects
                   .select_related("organization")
                   .filter(state=Invoice.ISSUED, due_at__lt=deadline))
        for invoice in overdue:
            subscription = getattr(invoice.organization, "subscription", None)
            if subscription is None or subscription.state == Subscription.PAST_DUE:
                continue
            self.done.append(f"{invoice.organization_id}: остановлен, счёт "
                             f"{invoice.number} просрочен с {invoice.due_at}")
            if self.dry:
                continue
            # `mark_unpaid` ходит на лицензионный сервер ПЕРВЫМ и поднимает его
            # отказ наружу. Здесь это ловится на уровне одного клиента: одна
            # недоступная организация не должна оставить остальных работать
            # бесплатно.
            try:
                services.mark_unpaid(invoice.organization)
            except licensing.LicensingError as error:
                self.stderr.write(f"{invoice.organization_id}: остановить не удалось: {error}")

    # --- 4: сторож ---------------------------------------------------------

    def _resume_stuck(self) -> None:
        """Оплачен, но обслуживание не вернулось.

        `mark_paid` пишет деньги первыми и возобновляет вторым, поэтому сетевой
        отказ оставляет ровно это состояние. У ЮKassa конечное окно повторов, у
        банковского перевода повторов нет вовсе — значит единственный, кто это
        дочинит, здесь.
        """
        stuck = (Invoice.objects
                 .select_related("organization")
                 .filter(state=Invoice.PAID, service_resumed_at__isnull=True))
        for invoice in stuck:
            self.done.append(f"{invoice.organization_id}: повторное возобновление "
                             f"по оплаченному {invoice.number}")
            if self.dry:
                continue
            try:
                services.mark_paid(invoice)
            except services.ServiceNotResumed as error:
                self.stderr.write(f"{invoice.organization_id}: и снова не удалось: {error}")
