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

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from billing import licensing, services

_log = logging.getLogger("billing.cycle")
from billing.services import _int_or_zero
from billing.models import Invoice, Subscription

# Из `services`, а не отсюда: это же число печатается на лендинге, и три копии
# одного срока разъезжаются молча.
GRACE_DAYS = services.GRACE_DAYS


def _period_volume(organization, reported: dict) -> int:
    """Сколько запросов ЭТОТ период уже стоил, а не сколько их было за всю жизнь.

    Счётчик лицензионного сервера накопительный, поэтому за период — разница с
    ватермаркой последнего невоидного счёта. Та же арифметика, что в
    `build_invoice`; если бы она разошлась, письмо предупреждало бы об одном
    числе, а счёт приходил бы на другое.
    """
    billable = reported.get("capacity_billable")
    billable = billable if isinstance(billable, int) and not isinstance(billable, bool) else 0
    previous = (Invoice.objects.filter(organization=organization)
                .exclude(state=Invoice.VOID)
                .order_by("-period_end", "-id").first())
    watermark = max(0, previous.requests_billable_at_period_end if previous else 0)
    return max(0, billable - watermark)


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

        self._detect_container_steps()
        self._warn_about_volume()
        self._issue_for_ended_trials(now)
        self._issue_for_ended_periods(now)
        self._stop_overdue(now)
        self._resume_stuck()

        prefix = "БЫЛО БЫ: " if dry else ""
        for line in self.done:
            self.stdout.write(prefix + line)
        self.stdout.write(f"{len(self.done)} действий")
        # В ЛОГ — ТОЖЕ, И ВСЕГДА. stdout команды видит тот, кто её запустил
        # руками; часовой цикл запускает systemd, и «сколько счетов выставил
        # цикл в 03:00» — вопрос к Loki, а не к терминалу. Ноль действий —
        # это тоже запись: цикл, который молчит, неотличим от цикла, который
        # не бежал.
        _log.info("billing cycle done", extra={
            "dry_run": dry, "actions": len(self.done),
            "lines": self.done[:50]})

    # --- 0: что происходит на ЧУЖОМ железе ---------------------------------

    def _detect_container_steps(self) -> None:
        """Отметить, кто впервые поднял контейнер и кто впервые им воспользовался.

        ЭТО ДВА ШАГА ВОРОНКИ, НЕ ВИДНЫЕ ИЗ БРАУЗЕРА ВООБЩЕ. Между «получил
        ключ» и «поднял контейнер» отваливается больше всего людей, и отвал
        этот происходит на ЧУЖОМ железе: человек скопировал команду, не открыл
        порт наружу, получил отказ и ушёл. Ни одна аналитика на странице этого
        не увидит — факт приезжает к нам арендой.

        И РАЗНИЦА МЕЖДУ ДВУМЯ ШАГАМИ — САМОЕ СОДЕРЖАТЕЛЬНОЕ, ЧТО ЗДЕСЬ ЕСТЬ.
        Контейнер может подняться и не получить НИ ОДНОГО запроса: человек
        довёл установку до конца, а до включения в свой шлюз не дошёл. Это
        совершенно другой диагноз, чем «не смог запустить», и чинится он другим
        — не инструкцией по докеру, а примером интеграции. Шаг `first_mask`
        был ОБЪЯВЛЕН в модели и не записывался ничем, поэтому воронка
        обрывалась на «поднял контейнер», а следующий её шаг — «получил счёт» —
        уже стоял ненулевым. Ровно та болезнь, которую этот репозиторий ловит
        механически в гейтах: объявленный интерфейс без единого вызова.

        Спрашивается только про тех, у кого хотя бы одного шага ещё нет:
        пакетная ручка отвечает про названных, и список сам собой сжимается по
        мере того, как клиенты поднимаются.
        """
        from ops.analytics_models import Funnel

        leased_seen = set(Funnel.objects.filter(step=Funnel.FIRST_LEASE)
                          .values_list("organization_id", flat=True))
        masked_seen = set(Funnel.objects.filter(step=Funnel.FIRST_MASK)
                          .values_list("organization_id", flat=True))
        pending = [s.organization_id for s in Subscription.objects.all()
                   if s.organization_id not in leased_seen
                   or s.organization_id not in masked_seen]
        if not pending:
            return
        try:
            fleet = licensing.fleet(pending)
        except licensing.LicensingError:
            # Наша авария. Молчим и попробуем через час.
            return
        for org_id, row in fleet.items():
            # ПОЛЯ ВЛОЖЕНЫ В `usage`, А НЕ ЛЕЖАТ СВЕРХУ. Первая версия читала
            # `row.get("instances")` по докстроке ручки, а не по её ответу, —
            # там всегда None, и шаг «поднял контейнер» не засёкся бы НИ РАЗУ.
            # Отказ, который выглядит как «никто не поднимает контейнеры».
            usage = row.get("usage") or {}
            # `capacity_granted` МОНОТОННА, а `instances` считает аренды в
            # текущем окне TTL. Вопрос здесь — «поднимал ли КОГДА-НИБУДЬ», и
            # клиент, поднявший контейнер месяц назад и остановивший его,
            # показывает ноль инстансов и всё равно проходил этот шаг.
            # Ёмкость выдаётся на первой же аренде и назад не едет.
            leased = (_int_or_zero(usage.get("capacity_granted"))
                      or _int_or_zero(usage.get("reports"))
                      or row.get("instances"))
            # `requests` — ТОТ ЖЕ СЧЁТЧИК, ПО КОТОРОМУ ВЫСТАВЛЯЕТСЯ СЧЁТ, и он
            # монотонен по той же причине. Второго источника здесь быть не
            # может: воронка и инвойс, разошедшиеся в том, работал ли клиент,
            # — это два ответа на один вопрос.
            masked = _int_or_zero(usage.get("requests"))

            # ПОРЯДОК ШАГОВ — СВОЙСТВО ДАННЫХ, А НЕ ОФОРМЛЕНИЕ. Замаскировать,
            # не взяв аренды, нельзя: без лиза движок не детектирует вовсе.
            # Поэтому запрос, дошедший до нас, сам по себе доказывает аренду —
            # и без этой строки организация, впервые увиденная уже работающей,
            # получила бы `first_mask` при пустом `first_lease`, то есть
            # воронку, в которой следующий шаг больше предыдущего.
            if masked:
                leased = leased or masked

            if leased and org_id not in leased_seen:
                self.done.append(f"{org_id}: впервые поднял контейнер")
                if not self.dry:
                    Funnel.objects.create(step=Funnel.FIRST_LEASE,
                                          organization_id=org_id)
            if masked and org_id not in masked_seen:
                self.done.append(f"{org_id}: первый замаскированный запрос")
                if not self.dry:
                    Funnel.objects.create(step=Funnel.FIRST_MASK,
                                          organization_id=org_id)

    # --- 0б: предупредить о расходе ДО того, как придёт счёт ---------------

    def _warn_about_volume(self) -> None:
        """Письмо на переходе через включённый объём и через порог.

        ЗАЧЕМ. Обслуживание при перерасходе не останавливается — это решение, и
        оно правильное: рубильник из-за наших денег останавливает бизнес
        клиента. Но без предупреждения «не останавливаем» означало «узнаете из
        счёта», а счёт приходит, когда обсуждать уже нечего.

        Два письма за период и ни одним больше. Первое — «включённый объём
        выбран, пока бесплатно»; второе — «дальше каждая тысяча стоит столько-
        то». Второе и есть то, ради чего это написано: между ними лежит порог,
        и клиент имеет право узнать о нём заранее, а не постфактум.

        Ступень хранится строкой на подписке и обнуляется при продлении, так
        что цикл идемпотентен и может идти хоть каждую минуту.
        """
        live = (Subscription.objects
                .select_related("organization", "plan")
                .filter(state__in=(Subscription.TRIAL, Subscription.ACTIVE)))
        for subscription in live:
            organization = subscription.organization
            try:
                reported = licensing.usage(organization.id).get("usage", {})
            except licensing.LicensingError:
                # Молчим: недоступный лицензионный сервер — это НАША авария,
                # и превращать её в тревогу клиенту неправильно.
                continue
            if not isinstance(reported, dict):
                continue

            # СНИМОК ПИШЕТСЯ ДО ВСЯКИХ УСЛОВИЙ, И ПРОВЕРКА СТАВКИ ПЕРЕЕХАЛА
            # СЮДА РАДИ ЭТОГО. Раньше клиент на тарифе без ставки за объём
            # пропускался ДО запроса расхода — то есть у него не было бы ни
            # одной точки ряда, и «замолчал» про него сказать было бы нечем.
            # Лишних обращений это не создаёт: ставка есть у всех наших
            # тарифов, а `continue` там стоял на случай тарифа, собранного
            # руками.
            self._snapshot_usage(organization.id, reported)

            terms = subscription.terms
            rate = terms["metered_per_1k"] or 0
            if not rate:
                continue
            used = _period_volume(organization, reported)
            included = int(terms["included_requests"] or 0)
            floor = int(terms["metered_floor"] or 0)

            # ГЛОБАЛЬНЫЙ ПОТОЛОК (решение владельца): докуп только до потолка, дальше
            # буфер с оффером апгрейда, за буфером — ЖЁСТКИЙ СТОП (как неоплата, но
            # обратимо апгрейдом/новым периодом). Обслуживание при перерасходе БОЛЬШЕ
            # НЕ безгранично: клиент не получает бесконечный сюрприз-счёт.
            zone = services.classify_zone(used, subscription.plan)
            if zone["zone"] == "stopped":
                if not subscription.volume_capped:
                    self.done.append(
                        f"{organization.id}: ЛИМИТ ИСЧЕРПАН — стоп "
                        f"({used} при потолке {zone['cap']} + буфер)")
                    # РУБИЛЬНИК В TRY, КАК В `_stop_overdue`. Отказ лицензионного
                    # сервера по ОДНОЙ организации не имеет права уронить весь
                    # часовой цикл: иначе не выставятся счета, не остановятся
                    # просрочки, команда выйдет ненулём — и по стампу здоровья
                    # это «биллинг мёртв».
                    if not self.dry and self._set_status(organization.id, "suspended"):
                        # Флаг ПОВЕРХ состояния: клиент остаётся TRIAL/ACTIVE, и
                        # его счёт выставится сам на своём переходе. Ставится
                        # только после успешного рубильника — иначе кабинет
                        # покажет «остановлен», а движок продолжит работать.
                        subscription.volume_capped = True
                        subscription.save(update_fields=["volume_capped"])
                        services.funnel("capped", organization.id,
                                        f"{used} запросов, потолок {zone['cap']}")
                continue
            if subscription.volume_capped:
                # Вернулись под потолок (новый период сдвинул ватермарку /
                # подняли лимит) — снять стоп. Состояние (TRIAL/ACTIVE) не
                # трогаем: оно не терялось.
                self.done.append(f"{organization.id}: снова под потолком — возобновление")
                if not self.dry and self._set_status(organization.id, "active"):
                    subscription.volume_capped = False
                    subscription.volume_notified = Subscription.NOTIFIED_NONE
                    subscription.save(update_fields=["volume_capped", "volume_notified"])
                continue

            stage = subscription.volume_notified
            if zone["in_buffer"] and stage != Subscription.NOTIFIED_BUFFER:
                # В буфере за потолком: ещё служим, но следующая зона — ЖЁСТКИЙ
                # СТОП, и письмо обязано это сказать, а не обещать «ничего не
                # остановится». Шлём оффер апгрейда (первый месяц выгодно).
                self._send_volume_notice(subscription, used, included, floor,
                                         rate, kind="buffer", zone=zone)
                stage = Subscription.NOTIFIED_BUFFER
            elif used >= included + floor and stage not in (
                    Subscription.NOTIFIED_METERED, Subscription.NOTIFIED_BUFFER):
                self._send_volume_notice(subscription, used, included, floor,
                                         rate, kind="metered", zone=zone)
                stage = Subscription.NOTIFIED_METERED
            elif used >= included and stage == Subscription.NOTIFIED_NONE:
                # Ступень «включённое выбрано, но полоса ещё бесплатна» СУЩЕСТВУЕТ
                # только при floor > 0. При floor = 0 (наша политика) её нет:
                # пересечение включённого сразу означает тарификацию, и ветка
                # выше (metered) срабатывает на том же пороге. Условие оставлено
                # ради тарифа, которому руками вернули полосу.
                self._send_volume_notice(subscription, used, included, floor,
                                         rate, kind="included", zone=zone)
                stage = Subscription.NOTIFIED_INCLUDED
            if stage != subscription.volume_notified:
                self.done.append(
                    f"{organization.id}: предупреждение о расходе ({stage}), "
                    f"{used} запросов при включённых {included}")
                if not self.dry:
                    subscription.volume_notified = stage
                    subscription.save(update_fields=["volume_notified"])

    def _set_status(self, org_id: str, status: str) -> bool:
        """Рубильник на лицензионном сервере, чей отказ НЕ роняет цикл.

        Возвращает True при успехе — вызывающий пишет локальное зеркало только
        тогда, чтобы кабинет не разошёлся с реальным обслуживанием. Отказ по
        одной организации логируется в stderr, как в `_stop_overdue`, и цикл
        идёт дальше.
        """
        try:
            licensing.set_status(org_id, status)
            return True
        except licensing.LicensingError as error:
            self.stderr.write(f"{org_id}: не удалось выставить статус "
                              f"{status}: {error}")
            return False

    def _snapshot_usage(self, org_id: str, reported: dict) -> None:
        """Одна строка в сутки: накопленный расход клиента на сейчас.

        ПЕРЕЗАПИСЬ, А НЕ ДОПИСЫВАНИЕ: цикл идёт каждый час, и двадцать четыре
        строки за сутки сделали бы разность соседних суток бессмысленной.
        Последнее значение суток и есть их итог.
        """
        if self.dry:
            return
        from ops.analytics_models import UsageDay

        requests = _int_or_zero(reported.get("requests"))
        UsageDay.objects.update_or_create(
            organization_id=org_id, day=timezone.localdate(),
            defaults={"requests": requests})

    def _send_volume_notice(self, subscription, used: int, included: int,
                            floor: int, rate, kind: str, zone: dict) -> None:
        """Письмо о расходе, ТРИ разных по смыслу. Не один флаг `charging`:
        буфер шлёт «дальше СТОП», и обещать в нём «ничего не остановится» —
        ровно та ложь, которую этот метод чинит."""
        address = _billing_email(subscription.organization)
        if not address or self.dry:
            return
        link = f"{settings.SITE_URL}/app/"
        # Полоса упоминается ТОЛЬКО когда она есть: при floor = 0 фраза «и ещё 0
        # сверх них не начислялись» — мусор, который путает.
        free_band = (f" Следующие {floor} запросов сверх включённого пока не "
                     f"начислялись.") if floor > 0 else ""
        if kind == "buffer":
            cap = zone.get("cap", 0)
            buffer_end = zone.get("buffer_end", 0)
            discount = subscription.plan.upgrade_first_month_discount_pct
            deal = (f" Первый месяц старшего тарифа — со скидкой {discount}%."
                    if discount else "")
            subject = "pseudex — объём почти на глобальном потолке, дальше остановка"
            body = (f"Здравствуйте!\n\n"
                    f"За текущий период через шлюз прошло {used} запросов — это "
                    f"уже за глобальным потолком тарифа ({cap}). Сейчас работает "
                    f"буфер, но он конечный ({buffer_end}), и за ним обслуживание "
                    f"ОСТАНОВИТСЯ — как при неоплате, только снимается это "
                    f"переходом на старший тариф или новым периодом, а не "
                    f"платежом.\n\n"
                    f"Если такой объём теперь постоянный — перейдите на тариф "
                    f"выше: он и дешевле этого перерасхода, и снимает потолок."
                    f"{deal} Посчитаем вместе, ответьте на это письмо.\n\n"
                    f"Текущий расход и до потолка видно в кабинете:\n{link}\n")
        elif kind == "metered":
            subject = "pseudex — объём сверх включённого начинает тарифицироваться"
            body = (f"Здравствуйте!\n\n"
                    f"За текущий период через шлюз прошло {used} запросов, "
                    f"включено {included}.{free_band}\n\n"
                    f"Дальше каждая тысяча запросов сверх включённого стоит "
                    f"{rate} ₽. Ничего не остановится — превышение попадёт "
                    f"отдельной строкой в счёт за период (до глобального "
                    f"потолка тарифа).\n\n"
                    f"Текущий расход и начисление видно в кабинете:\n{link}\n\n"
                    f"Если такой объём теперь постоянный, тариф выше почти "
                    f"наверняка дешевле — посчитаем вместе.\n")
        else:  # included — только при floor > 0
            subject = "pseudex — включённый объём тарифа выбран"
            body = (f"Здравствуйте!\n\n"
                    f"За текущий период через шлюз прошло {used} запросов — "
                    f"это весь включённый в тариф объём ({included}).\n\n"
                    f"Пока ничего не меняется:{free_band} Мы напишем ещё раз, "
                    f"когда начнётся тарификация.\n\n"
                    f"Расход виден в кабинете:\n{link}\n")
        send_mail(subject=subject, message=body, from_email=None,
                  recipient_list=[address], fail_silently=True)

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

        # СТУПЕНЬ ПРЕДУПРЕЖДЕНИЙ ОБНУЛЯЕТСЯ ВМЕСТЕ С ПЕРИОДОМ: иначе клиент,
        # предупреждённый в январе, в феврале не услышит ничего.
        Subscription.objects.filter(organization=organization).update(
            volume_notified=Subscription.NOTIFIED_NONE)
        invoice = services.build_invoice(organization, period_start, period_end)
        invoice.state = Invoice.ISSUED
        invoice.issued_at = now
        invoice.save(update_fields=["state", "issued_at"])
        services.funnel("invoice_issued", organization.id, invoice.number)
        self._send_invoice(organization, invoice)

    def _send_invoice(self, organization, invoice: Invoice) -> None:
        address = _billing_email(organization)
        if not address:
            return
        lines = [f"абонплата {invoice.plan_amount} ₽"]
        if invoice.metered_amount > 0:
            lines.append(f"объём сверх включённого: {invoice.metered_requests} "
                         f"запросов — {invoice.metered_amount} ₽")
        if invoice.discount_amount > 0:
            title = invoice.discount_offer.title if invoice.discount_offer else "скидка"
            lines.append(f"{title}: −{invoice.discount_amount} ₽")
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
