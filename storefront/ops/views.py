"""Операторская консоль: все клиенты, один клиент, цепи отчётов, тарифы.

ПОЧЕМУ ОНА ЖИВЁТ В ВИТРИНЕ, А НЕ НА ЛИЦЕНЗИОННОМ СЕРВЕРЕ. Экран «все клиенты»
соединяет две базы: витрина знает организацию, подписку и счета, лицензионный
сервер — лизы, ёмкость и разрывы цепи. У сервера нет ни названий компаний, ни
писем, ни счетов, и заводить их там значило бы сделать его вторым местом, где
живут деньги. Джойн возможен только здесь.

ЧТО ЭТА КОНСОЛЬ НЕ ПОКАЗЫВАЕТ И НЕ БУДЕТ. `docs/tz-site.md` §1: «на сайте нельзя
нарисовать ни одного экрана, где виден диалог, сообщение, токен или значение».
Здесь только счётчики, идентификаторы и деньги. Ничего из трафика клиента сюда не
приходит вообще — витрина не имеет к нему доступа и не должна его получить, иначе
мы перестаём быть вне контура.

ОНА ОБЯЗАНА ОТКРЫВАТЬСЯ, КОГДА ЛИЦЕНЗИОННЫЙ СЕРВЕР ЛЕЖИТ. Это ровно та минута,
ради которой её открывают. `billing.licensing` поднимает `LicensingError` и не
глотает его — для клиентских путей это правильно, там молчание превращается в
тикет «я заплатил, и ничего не произошло». Здесь наоборот: ошибка ловится во вью и
становится плашкой, а всё, что витрина знает сама, остаётся на экране.
"""

import csv
import datetime
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django_otp.decorators import otp_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from ops.models import DemandDay
from storefront_web import detection_types
from django.views.decorators.http import require_POST

from accounts.models import Organization

_log = logging.getLogger("ops")
from billing import licensing
from billing import reconcile as billing_reconcile
from billing import services
from billing.models import Invoice, Plan, PlanChange, Subscription
from ops.analytics_models import Funnel, UsageDay, Visit

# СТРАНИЦА БЬЁТСЯ О ПОТОЛОК ПАКЕТНОЙ РУЧКИ, А НЕ О ЧИСЛО КЛИЕНТОВ.
# `/admin/fleet` отвечает 400 сверх двухсот идентификаторов — намеренно, чтобы
# один URL не превращался в сколь угодно долгую работу под локом store. Размер
# страницы должен быть заведомо меньше, иначе консоль ломается ровно тогда, когда
# клиентов становится много, то есть в самый неудачный момент.
PAGE_SIZE = 50


def _ops_gate(view):
    """Staff И подтверждённый TOTP — единый гейт всех страниц консоли.

    `staff_member_required` проверяет только is_staff и НЕ знает про второй
    фактор, поэтому одного его мало: утёкшего пароля staff-аккаунта хватило бы на
    все рычаги биллинга и раскрытие ПД. Оборачиваем в `otp_required` (по
    умолчанию требует подтверждённое устройство ВСЕГДА, не «если настроено»), а
    без верификации отправляем на вход В АДМИНКУ — там поле для кода, — а не на
    клиентскую форму `/accounts/login/`. Порядок обёрток важен: otp_required
    снаружи, чтобы не-staff с валидным кодом всё равно упирался в staff-проверку.
    """
    return otp_required(
        staff_member_required(view),
        login_url=f"/{settings.ADMIN_PATH}/login/",
        redirect_field_name="next",
    )


def _fleet_rows(organizations) -> tuple[dict, str]:
    """Состояние лизы по списку организаций — ОДНИМ обращением.

    Возвращает и ошибку строкой, а не бросает: вызывающий рисует плашку и
    остальную страницу. Пустой список организаций не стоит ни одного обращения.
    """
    org_ids = [org.id for org in organizations]
    try:
        return licensing.fleet(org_ids), ""
    except licensing.LicensingError as error:
        return {}, str(error)


def _unpaid_by_org(org_ids: list[str]) -> dict[str, Decimal]:
    """Сколько у каждой организации невыставленных денег.

    Одним запросом на всю страницу, а не по счёту на строку: тридцать строк —
    тридцать запросов, и экран, который открывают в аварии, начинает тормозить
    ровно тогда, когда он нужен.

    СУММА В `Decimal`, НИКОГДА В `int`. `int(total)` отрезает копейки у КАЖДОГО
    счёта, и ошибка копится по строкам — а `billing.models.Invoice` про это
    сказал прямо: «ошибка округления в цифре, которую клиент сверяет с выпиской
    банка, — не косметика, а спор».
    """
    rows = (Invoice.objects
            .filter(organization_id__in=org_ids, state=Invoice.ISSUED)
            .values_list("organization_id", "total"))
    unpaid: dict[str, Decimal] = {}
    for org_id, total in rows:
        unpaid[org_id] = unpaid.get(org_id, Decimal("0")) + (total or Decimal("0"))
    return unpaid


@_ops_gate
def demand(request):
    """Спрос на типы, которых мы не находим — по нему строится очередь работ.

    ЧИТАЕТСЯ НЕ ПОПУЛЯРНОСТЬ, А ДЕФИЦИТ. Рядом с числом стоит, покрыта ли группа
    сегодня, потому что «имена спросили сто раз» — это не задача, а «телеком
    спросили двадцать» — задача. Сортировка по числу внутри непокрытых, а
    покрытые идут ниже отдельным списком: они здесь как подтверждение, что
    спрашивают не только про дырки.

    ТЗ вертикалей §1 называет это достаточной причиной для конфигуратора даже
    без денег: сегодня очередь работ строится из наших догадок.
    """
    try:
        days = min(365, max(1, int(request.GET.get("days", "30"))))
    except ValueError:
        days = 30
    since = timezone.localdate() - datetime.timedelta(days=days - 1)
    totals = dict(DemandDay.objects.filter(day__gte=since)
                  .values_list("group")
                  .annotate(total=Sum("count"))
                  .values_list("group", "total"))
    rows = []
    for group in detection_types.GROUPS:
        rows.append({"code": group["code"], "label": group["label"],
                     "covered": bool(group.get("found")),
                     "total": totals.get(group["code"], 0)})
    # ГРУППЫ, КОТОРЫХ БОЛЬШЕ НЕТ В РЕЕСТРЕ, НЕ ТЕРЯЮТСЯ. Формулировки будут
    # меняться, коды — исчезать, а числа за прошлый квартал останутся в базе;
    # молча их не показывать значило бы тихо переписать историю спроса.
    known = {group["code"] for group in detection_types.GROUPS}
    retired = [{"code": code, "label": code, "covered": False, "total": total,
                "retired": True}
               for code, total in sorted(totals.items()) if code not in known]
    gaps = sorted([row for row in rows if not row["covered"]],
                  key=lambda row: (-row["total"], row["label"]))
    covered = sorted([row for row in rows if row["covered"]],
                     key=lambda row: (-row["total"], row["label"]))
    return render(request, "ops/demand.html", {
        "days": days, "gaps": gaps, "covered": covered, "retired": retired,
        "asked": sum(totals.values()), "periods": (30, 90, 365),
    })


@_ops_gate
def fleet(request):
    """Все клиенты одним списком, с красным флагом там, где цепь порвана."""
    organizations = (Organization.objects
                     .select_related("subscription__plan")
                     .order_by("-created_at"))
    page = Paginator(organizations, PAGE_SIZE).get_page(request.GET.get("page"))
    state, error = _fleet_rows(page.object_list)
    unpaid = _unpaid_by_org([org.id for org in page.object_list])
    # ПОТОЛОК БЕРЁТСЯ ОТТУДА, ГДЕ ОН ПРИНУЖДАЕТСЯ, а не из витринного `Plan`.
    # Эти два числа обязаны сходиться, но теперь тариф правится на сервере без
    # выката — и первая же правка сделала бы КАЖДОГО клиента «сверх лимита» на
    # экране, оставаясь совершенно правильной на деле. Экран тарифов существует
    # ровно чтобы такое расхождение показать; флот показывать его не должен.
    try:
        limits = {row["code"]: row["max_instances"] for row in licensing.plans()}
    except licensing.LicensingError:
        limits = {}

    rows = []
    for organization in page.object_list:
        licence = state.get(organization.id, {})
        usage = licence.get("usage", {}) if isinstance(licence, dict) else {}
        subscription = getattr(organization, "subscription", None)
        rows.append({
            "organization": organization,
            "subscription": subscription,
            "plan": subscription.plan if subscription else None,
            "instances": len(licence.get("instances", []) or []),
            "allowed": (limits.get(subscription.plan.code,
                                   subscription.plan.max_instances)
                        if subscription else 0),
            "requests": int(usage.get("requests", 0) or 0),
            "billable": int(usage.get("capacity_billable", 0) or 0),
            # Красный флаг. Он и есть причина, по которой экран существует:
            # разрывы цепи писались в базу с самого начала и не были видны
            # никому — их ловил только набор атак, то есть машина, а не человек.
            "chain_breaks": int(usage.get("chain_breaks", 0) or 0),
            "unverified": int(usage.get("unverified_reports", 0) or 0),
            "missing": int(usage.get("reports_missing", 0) or 0),
            "unpaid": unpaid.get(organization.id, 0),
        })
    return render(request, "ops/fleet.html", {
        "rows": rows, "page": page, "error": error,
        "flagged": sum(1 for row in rows if row["chain_breaks"]),
    })


@_ops_gate
def customer(request, org_id: str):
    """Один клиент: подписка, счета, ёмкость, инстансы и график по суткам."""
    organization = (Organization.objects
                    .select_related("subscription__plan")
                    .filter(pk=org_id).first())
    if organization is None:
        messages.error(request, f"Организации {org_id} нет.")
        return redirect("ops_fleet")

    usage, instances, history, processes, error = {}, [], [], [], ""
    try:
        usage = licensing.usage(organization.id).get("usage", {}) or {}
        # ИНСТАНСЫ БЕРУТСЯ У `/admin/instances`, А НЕ ИЗ ОТВЕТА `/admin/usage`.
        # Оба поля называются `instances`, и это ловушка: у `/admin/usage` там
        # сырые строки аренд (`instance_id`/`process_id`/`issued_at`, по строке
        # на выдачу, с освобождёнными и с потолком в сотню), а таблица ниже
        # рисует `last_lease` и `state` — их там просто нет, так что колонка
        # «состояние» молча зеленела бы у КАЖДОЙ строки, включая отпущенные
        # слоты.
        instances = licensing.instances(organization.id).get("instances", []) or []
        detail = licensing.chains(organization.id)
        history = detail.get("history", []) or []
        processes = detail.get("processes", []) or []
    except licensing.LicensingError as caught:
        error = str(caught)

    return render(request, "ops/customer.html", {
        "organization": organization,
        "subscription": getattr(organization, "subscription", None),
        "invoices": organization.invoices.all()[:12],
        "keys": organization.keys.filter(revoked_at__isnull=True),
        "usage": usage, "instances": instances, "processes": processes,
        "history": _with_daily_deltas(history), "error": error,
    })


def _with_daily_deltas(history: list[dict]) -> list[dict]:
    """Прирост за сутки — РАЗНОСТЬ СОСЕДНИХ ТОЧЕК, и считается она здесь.

    Срез хранит накопительный итог на конец суток, как и `usage`, — так же, как
    `build_invoice` вычитает ватермарку предыдущего счёта. Хранить прирост
    значило бы вычислять его на записи, то есть верить, что предыдущая запись
    случилась; здесь верить нечему, вычитание видно глазом.

    `width` — доля от самых нагруженных суток, чтобы существующий примитив
    `.meter` нарисовал столбик без единой строки JavaScript и без библиотеки.
    """
    rows, previous = [], None
    for point in history:
        requests = int(point.get("requests", 0) or 0)
        # У ПЕРВОЙ ТОЧКИ ОКНА ПРЕДШЕСТВЕННИКА НЕТ, И ЕЁ ПРИРОСТ НЕИЗВЕСТЕН.
        #
        # Здесь стояло «нет предыдущей — значит прирост равен накопленному», и
        # это верно ровно для первых суток жизни клиента. Для окна в тридцать
        # суток над накопительным рядом первая строка получала ПОЖИЗНЕННЫЙ итог,
        # становилась пиком и придавливала все настоящие столбики к нулю: график
        # за месяц выглядел бы как один столбик слева и ровная полоса справа.
        delta = None if previous is None else max(0, requests - previous)
        rows.append({**point, "delta": delta})
        previous = requests
    peak = max((row["delta"] for row in rows if row["delta"] is not None), default=0)
    for row in rows:
        row["width"] = (round(row["delta"] / peak * 100)
                        if peak and row["delta"] is not None else 0)
    return rows


@_ops_gate
def chains(request):
    """Только порванное. Экран, который не должен показывать ничего."""
    # СТРАНИЦАМИ, А НЕ ПЕРВЫМИ ПЯТЬЮДЕСЯТЬЮ. Здесь стоял срез `[:PAGE_SIZE]` без
    # всякой навигации: разрыв у пятьдесят первого клиента был бы НАВСЕГДА
    # невидим на экране, заведённом ровно для того, чтобы разрывы показывать.
    page = Paginator(Organization.objects.select_related("subscription__plan")
                     .order_by("-created_at"), PAGE_SIZE).get_page(request.GET.get("page"))
    organizations = list(page.object_list)
    state, error = _fleet_rows(organizations)
    broken = []
    for organization in organizations:
        usage = (state.get(organization.id, {}) or {}).get("usage", {}) or {}
        breaks = int(usage.get("chain_breaks", 0) or 0)
        unverified = int(usage.get("unverified_reports", 0) or 0)
        malformed = int(usage.get("malformed_reports", 0) or 0)
        missing = int(usage.get("reports_missing", 0) or 0)
        if not (breaks or unverified or malformed or missing):
            continue
        broken.append({
            "organization": organization, "chain_breaks": breaks,
            "unverified": unverified, "malformed": malformed, "missing": missing,
        })
    broken.sort(key=lambda row: row["chain_breaks"], reverse=True)
    return render(request, "ops/chains.html", {
        "broken": broken, "error": error, "page": page,
        "checked": len(organizations)})


@_ops_gate
def plans(request):
    """Тарифы двух сторон рядом.

    Слева наши строки продажи (`billing.Plan`), справа — то, по чему
    лицензионный сервер на самом деле принимает решения. Числа обязаны сходиться,
    и до сих пор расхождение ловил только тест; здесь оно видно глазом, а тариф,
    которого сервер не знает, подсвечен отдельно — на нём клиент не получит ключ
    вовсе, потому что `/admin/issue` отвечает на незнакомый тариф 400.
    """
    error = ""
    try:
        remote = {row["code"]: row for row in licensing.plans()}
    except licensing.LicensingError as caught:
        remote, error = {}, str(caught)

    rows = []
    for plan in Plan.objects.all():
        row = remote.get(plan.code)
        rows.append({
            "plan": plan, "remote": row,
            "known": row is not None,
            # Единственное число, которое обе стороны называют одним и тем же
            # именем, — потолок инстансов. Остальное живёт только на сервере.
            "diverged": bool(row) and row["max_instances"] != plan.max_instances,
        })
    orphans = [row for code, row in sorted(remote.items())
               if not Plan.objects.filter(code=code).exists()]
    return render(request, "ops/plans.html", {
        "rows": rows, "orphans": orphans, "error": error,
        "fields": ("max_instances", "processes_per_instance", "grant_size",
                   "quantum_min", "quantum_max", "reserve_max"),
    })


@_ops_gate
@require_POST
def edit_plan(request, code: str):
    """Правка тарифа уходит на лицензионный сервер, а не в нашу базу.

    `actor` — почта вошедшего сотрудника, и она обязательна на той стороне: она
    единственная отличает правленную строку от посеянной, поэтому запись без неё
    сделала бы `source` выдумкой. Та же дисциплина, что у `actor` в журнале
    раскрытий: журнал без того, кто это сделал, — не журнал.
    """
    values: dict[str, object] = {}
    for field in ("max_instances", "processes_per_instance", "grant_size",
                  "quantum_min", "quantum_max", "reserve_max"):
        raw = request.POST.get(field, "").strip()
        if not raw:
            continue
        try:
            values[field] = int(raw)
        except ValueError:
            # Отказ говорит, ЧТО ДЕЛАТЬ, а не что случилось — правило
            # формулировок из `docs/tz-site.md` §7.
            messages.error(request, f"«{field}»: нужно целое число, пришло «{raw}».")
            return redirect("ops_plans")
    if not values:
        messages.error(request, "Нечего менять — ни одно поле не заполнено.")
        return redirect("ops_plans")
    try:
        plan = licensing.set_plan(code, values, actor=request.user.email)
    except licensing.LicensingError as error:
        messages.error(request, f"Лицензионный сервер отказал: {error}")
        return redirect("ops_plans")
    messages.success(request, f"Тариф {code} изменён: "
                              f"{', '.join(f'{k}={v}' for k, v in values.items())}. "
                              f"Автор записан как {plan.get('updated_by', '')}.")
    return redirect("ops_plans")


@_ops_gate
def analytics(request):
    """Аналитика: воронка первой, трафик вторым. Порядок — это утверждение.

    ПРОСМОТРЫ НЕ ОТВЕЧАЮТ НИ НА ОДИН ВОПРОС, КОТОРЫЙ СТОИТ ДЕНЕГ. «Пришло 400
    человек» не говорит, что делать дальше; «из 400 форму отправили 12, ключ
    получили 9, контейнер подняли 2» говорит, где чинить, и называет место —
    между ключом и контейнером. Поэтому воронка наверху, а трафик под ней.

    ВСЕ РАЗРЕЗЫ СЧИТАЮТСЯ БЕЗ БОТОВ ПО УМОЛЧАНИЮ и переключаются одной
    ссылкой. Лендинг с десятью живыми посетителями и двумя сотнями обходов
    краулеров показывает 210 и врёт в двадцать раз — а по этому числу выбирают
    канал.
    """
    days = max(1, min(365, int(request.GET.get("days", "30") or 30)))
    with_bots = request.GET.get("bots") == "1"
    since = timezone.now() - datetime.timedelta(days=days)
    today = timezone.localdate()

    visits = Visit.objects.filter(at__gte=since)
    if not with_bots:
        visits = visits.filter(is_bot=False)

    # --- воронка -----------------------------------------------------------
    # Считается по РАЗНЫМ ключам на разных участках, и это не небрежность:
    # до выпуска ключа человек опознаётся суточным отпечатком, после — своей
    # организацией. Склеить их сквозным идентификатором было бы можно, и это
    # ровно тот идентификатор, которого мы не заводим.
    steps = []
    for code, title in Funnel.STEPS:
        if code == Funnel.SIGNUP_REFUSED:
            continue
        rows = Funnel.objects.filter(step=code, at__gte=since)
        count = (rows.values("visitor").distinct().count() if code == Funnel.LANDING
                 else rows.values("organization_id").distinct().count()
                 if code != Funnel.LANDING else rows.count())
        steps.append({"code": code, "title": title, "count": count})
    # ШАГ С НУЛЁМ, ЗА КОТОРЫМ СТОИТ НЕНУЛЕВОЙ, НЕВОЗМОЖЕН ПО СМЫСЛУ, и это
    # единственный способ увидеть с экрана, что шаг перестали ЗАПИСЫВАТЬ.
    # Воронка упорядочена: заплатить, не замаскировав ни одного запроса,
    # нельзя, как нельзя замаскировать, не подняв контейнера. Поэтому дыра
    # выглядит не как «клиенты отвалились», а как арифметическая невозможность
    # — и её надо назвать вслух, иначе ноль читается как отвал и посылает
    # чинить продукт вместо аналитики. Так и жил `first_mask`: объявлен в
    # модели, не записан никем, а на экране выглядел провалом конверсии.
    from ops import collect as _collect
    steps = _collect.flag_unwired(steps)

    top = steps[0]["count"] if steps and steps[0]["count"] else 0
    previous = None
    for row in steps:
        row["share"] = round(row["count"] / top * 100, 1) if top else 0
        # Конверсия ИЗ ПРЕДЫДУЩЕГО шага, а не из вершины: именно она называет
        # место, где отваливаются, а доля от вершины только описывает итог.
        row["from_previous"] = (round(row["count"] / previous * 100, 1)
                                if previous else None)
        row["lost"] = (previous - row["count"]) if previous is not None else 0
        previous = row["count"] or None

    # --- почему отказала форма --------------------------------------------
    # Отдельно от воронки: это не шаг, а диагноз. «Отваливаются на форме»
    # ничего не говорит; «восемь из десяти — уже зарегистрированы» говорит, что
    # чинить надо ссылку на вход, а не форму.
    refusals = list(Funnel.objects.filter(step=Funnel.SIGNUP_REFUSED, at__gte=since)
                    .values("detail").annotate(n=Count("id")).order_by("-n"))

    # --- трафик ------------------------------------------------------------
    def cut(field, limit=12):
        rows = (visits.exclude(**{field: ""}).values(field)
                .annotate(visits=Count("id"), visitors=Count("visitor", distinct=True))
                .order_by("-visitors")[:limit])
        return [{"value": r[field], "visits": r["visits"], "visitors": r["visitors"]}
                for r in rows]

    # Ряд по суткам — для графика и для ответа «растём или нет».
    by_day = list(visits.annotate(day=TruncDate("at")).values("day")
                  .annotate(visits=Count("id"),
                            visitors=Count("visitor", distinct=True))
                  .order_by("day"))
    peak = max((d["visits"] for d in by_day), default=0) or 1
    for row in by_day:
        row["height"] = round(row["visits"] / peak * 100)

    bots = Visit.objects.filter(at__gte=since, is_bot=True).count()
    total_visits = visits.count()
    total_visitors = visits.values("visitor").distinct().count()

    # --- ДЕНЬГИ. Главное число бизнеса, и его на этом экране не было вовсе.
    #
    # MRR СЧИТАЕТСЯ ПО СНИМКУ УСЛОВИЙ, А НЕ ПО ЦЕНЕ ТАРИФА. Действующая
    # подписка живёт по условиям, снятым при продаже (`terms_monthly_price`), и
    # правка тарифа доходит до неё только на продлении. Считать по прайсу
    # значило бы показывать выручку, которой нет: конструктор поднял цену —
    # MRR «вырос», а платят по-прежнему старую.
    active = list(Subscription.objects.filter(state=Subscription.ACTIVE)
                  .select_related("plan"))
    mrr = sum((s.terms_monthly_price or s.plan.monthly_price for s in active),
              Decimal("0"))
    paying_orgs = {s.organization_id for s in active}

    paid_invoices = Invoice.objects.filter(state=Invoice.PAID, paid_at__gte=since)
    revenue = paid_invoices.aggregate(total=Sum("total"))["total"] or Decimal("0")
    # ОБЪЁМ СВЕРХ ВКЛЮЧЁННОГО — ОТДЕЛЬНОЙ СТРОКОЙ, а не внутри выручки: это
    # единственная её часть, которая растёт без единой новой продажи, и
    # спутать её с ростом клиентской базы значит принять неверное решение.
    metered = paid_invoices.aggregate(total=Sum("metered_amount"))["total"] or Decimal("0")

    trials = Subscription.objects.filter(state=Subscription.TRIAL).count()
    # Выбрали платный тариф и ещё не заплатили: не проба и не отток, третья
    # колонка. Без неё они не видны нигде — ни в пробах, ни в платящих.
    pending = Subscription.objects.filter(state=Subscription.PENDING).count()
    past_due = Subscription.objects.filter(state=Subscription.PAST_DUE).count()
    cancelled = Subscription.objects.filter(
        cancel_at_period_end=True).exclude(state=Subscription.CANCELLED).count()
    lost = Subscription.objects.filter(state=Subscription.CANCELLED).count()

    # КОНВЕРСИЯ ТРИАЛА — ПО КОГОРТЕ ЗАКОНЧИВШИХСЯ, А НЕ ПО ВСЕМ. Триалы,
    # которые ещё идут, не провалились — они просто не решили, и, попав в
    # знаменатель, занижали бы конверсию ровно в темпе притока новых клиентов.
    decided = Subscription.objects.filter(trial_ends_at__lt=timezone.now())
    decided_n = decided.count()
    converted = decided.filter(state__in=[Subscription.ACTIVE,
                                          Subscription.PAST_DUE]).count()

    money = {
        "mrr": mrr, "revenue": revenue, "metered": metered,
        "paying": len(active), "trials": trials, "pending": pending,
        "past_due": past_due, "cancelling": cancelled, "lost": lost,
        "invoices_paid": paid_invoices.count(),
        "average": (revenue / paid_invoices.count()) if paid_invoices.count() else Decimal("0"),
        "trial_conversion": (round(converted / decided_n * 100, 1)
                             if decided_n else None),
        "trial_decided": decided_n,
    }

    # --- ВРЕМЯ ДО ЦЕННОСТИ. Сколько проходит от ключа до первой маскировки.
    #
    # ЭТО ГЛАВНОЕ ЧИСЛО ОНБОРДИНГА, и оно уже лежало в базе двумя отметками
    # воронки, которые никто не вычитал друг из друга. Конверсия говорит
    # СКОЛЬКО дошло, медиана — НАСКОЛЬКО ТРУДНО было: те же 60% за двадцать
    # минут и за четыре дня требуют разных действий.
    #
    # МЕДИАНА, А НЕ СРЕДНЕЕ: один клиент, поднявший контейнер через месяц,
    # сдвигает среднее так, что оно перестаёт описывать кого бы то ни было.
    def _minutes_between(first_step: str, second_step: str) -> list[int]:
        starts = dict(Funnel.objects.filter(step=first_step)
                      .exclude(organization_id="")
                      .values_list("organization_id", "at"))
        spans = []
        for org_id, at in Funnel.objects.filter(step=second_step).exclude(
                organization_id="").values_list("organization_id", "at"):
            started = starts.get(org_id)
            if started and at >= started:
                spans.append(int((at - started).total_seconds() // 60))
        return sorted(spans)

    def _median(values: list[int]):
        if not values:
            return None
        middle = len(values) // 2
        return (values[middle] if len(values) % 2
                else (values[middle - 1] + values[middle]) // 2)

    to_lease = _minutes_between(Funnel.KEY_ISSUED, Funnel.FIRST_LEASE)
    to_mask = _minutes_between(Funnel.KEY_ISSUED, Funnel.FIRST_MASK)
    speed = {
        "to_lease": _median(to_lease), "to_lease_n": len(to_lease),
        "to_mask": _median(to_mask), "to_mask_n": len(to_mask),
    }

    # --- КТО ЗАМОЛЧАЛ. Самый сильный сигнал оттока, и он был невидим.
    #
    # НАКОПИТЕЛЬНЫЙ СЧЁТЧИК НЕ УМЕЕТ ПАДАТЬ. `usage.requests` монотонен — это
    # правильно для счёта и бесполезно для вопроса «работает ли клиент ещё»:
    # платящий, у которого трафик кончился месяц назад, на экране флота стоит
    # с тем же большим числом, что и в лучший свой день. Разность соседних
    # суток из нашего собственного следа (`UsageDay`) — единственное место, где
    # это видно, и приходит оно за МЕСЯЦЫ до отказа платить.
    #
    # ВОПРОС ЗАДАЁТСЯ ТОЛЬКО ПРО ТЕХ, КТО КОГДА-ТО РАБОТАЛ. Клиент, не
    # поднявший контейнер ни разу, — это провал онбординга, он уже посчитан
    # воронкой, и в списке оттока он был бы шумом, который заслонит настоящий.
    quiet = []
    for org_id in paying_orgs | {s.organization_id for s in
                                 Subscription.objects.filter(state=Subscription.TRIAL)}:
        series = list(UsageDay.objects.filter(organization_id=org_id)
                      .order_by("-day")[:30])
        if len(series) < 2 or not series[0].requests:
            continue
        stalled_since = min(row.day for row in series
                            if row.requests == series[0].requests)
        silent = (today - stalled_since).days
        if silent >= 3:
            quiet.append({"org_id": org_id, "days": silent,
                          "requests": series[0].requests,
                          "paying": org_id in paying_orgs})
    quiet.sort(key=lambda row: row["days"], reverse=True)

    # --- КАМПАНИИ ДО ДЕНЕГ. Ради этого атрибуция и переехала на организацию.
    #
    # ВИЗИТЫ СЧИТАЮТСЯ ПО ВИЗИТАМ, А ВСЁ ОСТАЛЬНОЕ — ПО ОРГАНИЗАЦИЯМ, и это два
    # разных источника, склеенные по имени кампании. Иначе никак: между визитом
    # и оплатой стоят недели, а отпечаток посетителя живёт сутки.
    campaigns: dict[str, dict] = {}

    def _row(key: str) -> dict:
        return campaigns.setdefault(key, {
            "value": key, "visits": 0, "visitors": 0, "signups": 0,
            "masked": 0, "paying": 0, "revenue": Decimal("0")})

    for row in (visits.values("utm_campaign", "utm_source", "referrer_host")
                .annotate(visits=Count("id"),
                          visitors=Count("visitor", distinct=True))):
        key = (row["utm_campaign"] or row["utm_source"]
               or row["referrer_host"] or "прямой заход")
        into = _row(key)
        into["visits"] += row["visits"]
        into["visitors"] += row["visitors"]

    masked_orgs = set(Funnel.objects.filter(step=Funnel.FIRST_MASK)
                      .values_list("organization_id", flat=True))
    revenue_by_org = {
        r["organization_id"]: r["total"] for r in
        Invoice.objects.filter(state=Invoice.PAID).values("organization_id")
        .annotate(total=Sum("total"))}

    for org in Organization.objects.filter(created_at__gte=since):
        key = (org.source_utm_campaign or org.source_utm_source
               or org.source_referrer or "прямой заход")
        into = _row(key)
        into["signups"] += 1
        if org.id in masked_orgs:
            into["masked"] += 1
        if org.id in paying_orgs:
            into["paying"] += 1
        into["revenue"] += revenue_by_org.get(org.id, Decimal("0"))

    channels = sorted(campaigns.values(),
                      key=lambda r: (r["paying"], r["signups"], r["visitors"]),
                      reverse=True)[:15]
    for row in channels:
        row["to_signup"] = (round(row["signups"] / row["visitors"] * 100, 1)
                            if row["visitors"] else None)

    return render(request, "ops/analytics.html", {
        "days": days, "with_bots": with_bots, "today": today,
        "steps": steps, "refusals": refusals,
        "money": money, "speed": speed, "channels": channels,
        "quiet": quiet,
        "by_day": by_day, "peak": peak,
        "total_visits": total_visits, "total_visitors": total_visitors,
        "bots": bots,
        "bot_share": round(bots / (total_visits + bots) * 100, 1) if total_visits + bots else 0,
        "pages": cut("path"), "referrers": cut("referrer_host"),
        "sources": cut("utm_source"), "campaigns": cut("utm_campaign"),
        "devices": cut("device", 6), "browsers": cut("browser", 8),
        "systems": cut("os", 6),
        "plans_chosen": list(Funnel.objects
                             .filter(step=Funnel.SIGNUP_SUBMITTED, at__gte=since)
                             .values("detail").annotate(n=Count("id")).order_by("-n")),
    })


# Коммерческие поля тарифа: их правит конструктор, и они живут ТОЛЬКО у нас.
# Лицензионный сервер про деньги не знает и знать не должен — он решает, кому
# выдавать ёмкость, а не сколько это стоит.
_MONEY_FIELDS = (
    ("monthly_price", "₽ в месяц", "decimal"),
    ("included_requests", "включено запросов", "int"),
    ("metered_per_1k", "₽ за 1000 сверх", "decimal"),
    ("metered_floor", "порог тарификации", "int"),
    # Настраиваемые владельцем коммерческие ручки: потолок объёма, буфер, скидка
    # апгрейда и ГОДОВАЯ скидка. Пусто — не трогать; потолок/буфер, если их не
    # задавать руками, авто-выводятся из включённого (`derive_cap_and_buffer`).
    ("overage_cap_requests", "потолок объёма (докуп до)", "int"),
    ("buffer_requests", "буфер за потолком", "int"),
    ("upgrade_first_month_discount_pct", "скидка апгрейда, %", "int"),
    ("annual_discount_pct", "годовая скидка, %", "int"),
)
# Ручной ввод этих полей ОТМЕНЯЕТ авто-вывод потолка/буфера из включённого.
_CAP_FIELDS = frozenset({"overage_cap_requests", "buffer_requests"})
# Проценты: 0..100. Больше 100 инвертировало бы цену (скидка > стоимости).
_PCT_FIELDS = frozenset({"upgrade_first_month_discount_pct", "annual_discount_pct"})


@_ops_gate
def constructor(request):
    """Конструктор тарифов: создать, изменить, увидеть цену правки.

    ГЛАВНОЕ СВОЙСТВО ЭКРАНА — ОН ПОКАЗЫВАЕТ, КОГО ПРАВКА КОСНЁТСЯ И КОГДА.
    Действующие подписки считаются по СНИМКУ условий, снятому при продаже и
    обновляемому в момент продления, поэтому новая цена доходит до клиента
    только на следующем периоде. Экран называет число таких клиентов вслух:
    правка, после которой «ничего не изменилось», — самый частый способ
    поменять цену и не понять, что она ещё месяц не действует.

    И называет ИСКЛЮЧЕНИЕ. Потолок инстансов и RPM исполняет лицензионный
    сервер, а он знает тарифы по КОДУ, не по версии условий: эти два числа
    меняются сразу для всех. Обещать здесь изоляцию значило бы соврать.
    """
    if request.method == "POST":
        return _apply_plan_edit(request)

    rows = []
    for plan in Plan.objects.all():
        subs = list(Subscription.objects.filter(plan=plan)
                    .select_related("plan", "organization"))
        rows.append({
            "plan": plan,
            "subscribers": len(subs),
            # Сколько клиентов доработают период на прежних условиях. Ноль
            # означает «правка уже у всех», а не «правки не было».
            "on_old": sum(1 for s in subs if s.on_old_terms),
            "next_renewal": min((s.current_period_end for s in subs), default=None),
            "changes": list(plan.changes.all()[:6]),
        })
    return render(request, "ops/constructor.html", {
        "rows": rows, "fields": _MONEY_FIELDS,
        "admin_path": settings.ADMIN_PATH,
    })


def _apply_plan_edit(request):
    """Одна правка коммерческих условий тарифа, с записью в журнал.

    Пустое поле — не трогать. Ноль — это значение, а не пропуск: тариф без
    тарификации объёма ставится именно нулевой ставкой, и путать одно с другим
    нельзя.
    """
    code = (request.POST.get("code") or "").strip()
    plan = Plan.objects.filter(code=code).first()
    if plan is None:
        # СОЗДАНИЕ. Новый тариф начинается невидимым: цена, включённый объём и
        # порог у него ещё не заданы, а строка, попавшая на лендинг раньше, чем
        # в неё вписали цену, продаётся за ноль рублей.
        title = (request.POST.get("title") or "").strip()
        if not code or not title:
            messages.error(request, "Нужны код и название — по коду тариф "
                                    "узнаёт лицензионный сервер.")
            return redirect("ops_constructor")
        plan = Plan.objects.create(code=code, title=title, monthly_price=0,
                                   is_public=False, sort_order=99)
        PlanChange.objects.create(plan=plan, field="создан", was="",
                                  became=title, actor=request.user.email)
        messages.success(request, f"Тариф «{title}» создан и СКРЫТ с лендинга. "
                                  f"Впишите условия и опубликуйте.")
        return redirect("ops_constructor")

    changed: list[str] = []
    included_changed = False
    cap_set_by_hand = False
    for field, label, kind in _MONEY_FIELDS:
        raw = (request.POST.get(field) or "").strip()
        if raw == "":
            continue
        try:
            value = Decimal(raw.replace(",", ".")) if kind == "decimal" else int(raw)
        except (InvalidOperation, ValueError):
            messages.error(request, f"«{label}»: нужно число, пришло «{raw}».")
            return redirect("ops_constructor")
        if value < 0:
            messages.error(request, f"«{label}»: отрицательным быть не может.")
            return redirect("ops_constructor")
        if field in _PCT_FIELDS and value > 100:
            messages.error(request, f"«{label}»: процент не может быть больше 100.")
            return redirect("ops_constructor")
        was = getattr(plan, field)
        if was == value:
            continue
        setattr(plan, field, value)
        if field == "included_requests":
            included_changed = True
        if field in _CAP_FIELDS:
            cap_set_by_hand = True
        PlanChange.objects.create(plan=plan, field=field, was=str(was),
                                  became=str(value), actor=request.user.email,
                                  note=(request.POST.get("note") or "")[:200])
        changed.append(f"{label}: {was} → {value}")
        # ПРАВКА ЦЕНЫ — В ЛОГ, А НЕ ТОЛЬКО В ЖУРНАЛ ТАБЛИЦЫ. Журнал отвечает
        # «что менялось», лог отвечает «что менялось В ТУ ЖЕ МИНУТУ, когда
        # клиент получил счёт не на ту сумму» — рядом со строкой invoice built.
        _log.warning("plan edited", extra={"plan": plan.code, "field": field,
                                          "was": str(was), "became": str(value),
                                          "by": request.user.email})

    publish = request.POST.get("is_public")
    if publish is not None:
        wanted = publish == "1"
        if wanted != plan.is_public:
            PlanChange.objects.create(plan=plan, field="на лендинге",
                                      was="да" if plan.is_public else "нет",
                                      became="да" if wanted else "нет",
                                      actor=request.user.email)
            plan.is_public = wanted
            changed.append("на лендинге: " + ("да" if wanted else "нет"))

    # ПОТОЛОК ПЕРЕ-ВЫВОДИТСЯ ВМЕСТЕ С ВКЛЮЧЁННЫМ — но только если оператор НЕ
    # задал потолок/буфер руками в этой же правке (тогда уважаем его число).
    # Правка `included_requests` без этого оставляла абсолютный потолок ниже
    # нового включённого — и клиент, пересёкший включённое, останавливался без
    # докупа. Плана без потолка (0 = Enterprise) это не касается.
    if included_changed and not cap_set_by_hand and plan.overage_cap_requests > 0:
        cap, buffer = services.derive_cap_and_buffer(plan.included_requests)
        if cap != plan.overage_cap_requests or buffer != plan.buffer_requests:
            plan.overage_cap_requests = cap
            plan.buffer_requests = buffer
            changed.append(f"потолок объёма: → {cap} (буфер {buffer})")

    if not changed:
        messages.error(request, "Нечего менять — все поля пусты или совпадают.")
        return redirect("ops_constructor")

    plan.save()
    waiting = sum(1 for s in Subscription.objects.filter(plan=plan)
                  if s.on_old_terms)
    tail = (f" Действующих подписок на прежних условиях: {waiting} — "
            f"новые условия дойдут до них при продлении."
            if waiting else " Действующих подписок на прежних условиях нет.")
    messages.success(request, f"{plan.title}: {'; '.join(changed)}.{tail}")
    return redirect("ops_constructor")


def _period_totals(usage: dict, invoice) -> tuple[int, str]:
    """Сколько мы выставляем ЗА ПЕРИОД, и как именно это число получено.

    СВЕРЯЮТ КОНКРЕТНЫЙ СЧЁТ, А НЕ «ТО, ЧТО НАКАПАЛО ПОСЛЕ НЕГО». Спор начинается
    со счёта в руках, поэтому число обязано быть тем самым, что на нём напечатано:
    `Invoice.requests_billable_in_period` записан при выставлении и переживает
    любые последующие отчёты.

    Здесь стояло «накопленное минус ватермарка последнего счёта», то есть объём
    ЕЩЁ НЕ ВЫСТАВЛЕННОГО периода, — и подписано это было именем того самого
    счёта. Клиент, пришедший спорить про INV-N, получал бы разницу с чужим
    числом и тем большую, чем дольше он работает после выставления.

    Счёта нет — сверять можно только текущий незакрытый период, и тогда это
    сказано прямо, а не подразумевается.
    """
    if invoice is not None:
        return max(0, int(invoice.requests_billable_in_period or 0)), (
            f"со счёта {invoice.number} за "
            f"{invoice.period_start:%d.%m.%Y}—{invoice.period_end:%d.%m.%Y}")
    total = int(usage.get("capacity_billable", 0) or 0)
    return total, ("счетов ещё не было — сверяется ТЕКУЩИЙ незакрытый период, "
                   f"накопленный с первого отчёта установки: {total}")


@_ops_gate
def reconcile(request, org_id: str):
    """Свести наш счёт с числом из лога шлюза клиента.

    ОБЕЩАНИЕ `docs/billing-integrity.md` НАКОНЕЦ ИСПОЛНИМО РУКАМИ. Единица
    тарификации — запрос именно потому, что «запрос виден в логе шлюза самого
    клиента», и спор о деньгах должен превращаться в сравнение двух независимых
    источников. Сравнивать до сих пор было нечем.

    ЧИСЛО, А НЕ ФАЙЛ. Форма принимает одно число, а не лог: в логе шлюза лежат
    тела запросов, то есть персональные данные, и принимать их сюда значило бы
    сломать ровно ту границу, ради которой продукт существует.
    """
    organization = (Organization.objects
                    .select_related("subscription__plan")
                    .filter(pk=org_id).first())
    if organization is None:
        messages.error(request, f"Организации {org_id} нет.")
        return redirect("ops_fleet")

    usage, history, plan_row, error = {}, [], {}, ""
    subscription = getattr(organization, "subscription", None)
    try:
        usage = licensing.usage(organization.id).get("usage", {}) or {}
        history = licensing.chains(organization.id).get("history", []) or []
        if subscription:
            plan_row = next((row for row in licensing.plans()
                             if row["code"] == subscription.plan.code), {})
    except licensing.LicensingError as caught:
        error = str(caught)

    # Сверяется НАЗВАННЫЙ счёт, а по умолчанию — последний выставленный: с ним
    # и приходят спорить.
    invoices = list(organization.invoices.exclude(state=Invoice.VOID)
                    .order_by("-period_end", "-id")[:24])
    wanted = request.GET.get("invoice", "").strip()
    invoice = next((item for item in invoices if item.number == wanted),
                   invoices[0] if invoices else None)
    ours, ours_explained = _period_totals(usage, invoice)
    quantum_max = int(plan_row.get("quantum_max", 0) or 0)
    reserve_max = int(plan_row.get("reserve_max", 0) or 0)

    result, theirs_raw = None, request.GET.get("theirs", "").strip()
    if theirs_raw and not error:
        try:
            theirs = int(theirs_raw.replace(" ", "").replace(" ", ""))
        except ValueError:
            messages.error(request, f"«{theirs_raw}»: нужно целое число запросов.")
            return redirect("ops_reconcile", org_id=org_id)
        result = billing_reconcile.reconcile(
            ours=ours, theirs=theirs,
            quantum_max=quantum_max, reserve_max=reserve_max,
            # Полоса складывается ПО ПРОЦЕССАМ: леджер ёмкости ключуется на ключ
            # процесса, и `billable` зажимает каждый отдельно, а потом сложит.
            processes=int(usage.get("capacity_processes", 0) or 0),
            reports_missing=int(usage.get("reports_missing", 0) or 0),
            chain_breaks=int(usage.get("chain_breaks", 0) or 0),
            unverified_reports=int(usage.get("unverified_reports", 0) or 0),
            unacked_quanta=int(usage.get("capacity_unacked_quanta", 0) or 0),
        )

    return render(request, "ops/reconcile.html", {
        "organization": organization, "subscription": subscription,
        "ours": ours, "ours_explained": ours_explained,
        "theirs_raw": theirs_raw, "result": result, "error": error,
        "plan_row": plan_row,
        "band": billing_reconcile.band_width(
            quantum_max, reserve_max, int(usage.get("capacity_processes", 0) or 0)),
        "processes": int(usage.get("capacity_processes", 0) or 0),
        "invoices": invoices, "invoice": invoice,
        "not_billable": billing_reconcile.NOT_BILLABLE,
        "rows": billing_reconcile.daily_rows(history),
    })


@_ops_gate
def usage_csv(request, org_id: str):
    """Посуточный ряд НАШИХ чисел — файлом, чтобы клиент разложил его по своим.

    Выгрузка, а не загрузка: наружу уходят только счётчики, внутрь не приходит
    ничего. Одно число в форме сверки годится для итога за период, но найти, В
    КАКИЕ СУТКИ разошлось, можно только рядом — ради этого `usage_daily` и
    заведён.
    """
    organization = Organization.objects.filter(pk=org_id).first()
    if organization is None:
        raise Http404("организация не найдена")
    try:
        history = licensing.chains(organization.id).get("history", []) or []
    except licensing.LicensingError as error:
        messages.error(request, f"Лицензионный сервер не отвечает: {error}")
        return redirect("ops_reconcile", org_id=org_id)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    # Имя файла из ИДЕНТИФИКАТОРА, а не из названия организации: название —
    # свободная строка, а она уехала бы в заголовок ответа.
    safe = "".join(char for char in organization.id if char.isalnum() or char in "-_")
    response["Content-Disposition"] = f'attachment; filename="pseudex-{safe}-usage.csv"'
    writer = csv.writer(response)
    # `day_utc`, А НЕ `day`. Срез режется по UTC (`time.gmtime` на стороне
    # лицензионного сервера), а витрина рисует в Europe/Moscow: без пометки
    # вечерний московский трафик молча ложится в предыдущую строку, и клиент,
    # раскладывающий выгрузку по СВОИМ суткам, ищет расхождение там, где его нет.
    # Резать по клиентскому поясу нельзя — сервер его не знает и знать не должен;
    # значит остаётся назвать пояс честно.
    writer.writerow(["day_utc", "requests_total", "requests_delta",
                     "values_total", "reports", "instances"])
    for row in billing_reconcile.daily_rows(history):
        writer.writerow([row["day"], row["requests_total"], row["requests_delta"],
                         row["values_total"], row["reports"], row["instances"]])
    return response


@_ops_gate
def yandex(request):
    """Экран «Яндекс»: реклама и статистика с той стороны.

    ЭКРАН ОБЯЗАН ОТКРЫВАТЬСЯ, КОГДА ЯНДЕКС НЕ ОТВЕЧАЕТ, и по той же причине,
    что и остальная консоль: его открывают ровно в ту минуту, когда что-то
    пошло не так. Отказ API ловится и становится плашкой; всё, что витрина
    знает сама, — сколько конверсий мы отправили и когда, — остаётся на экране.

    ПОЧЕМУ ОТДЕЛЬНЫЙ ЭКРАН, А НЕ БЛОК В «АНАЛИТИКЕ». Там первопартийные числа:
    наши визиты, наша воронка, наши деньги, и они сходятся с базой. Здесь
    чужие: Метрика считает своим счётчиком и своим определением визита, Директ
    живёт по своим кампаниям. Две цифры «сколько пришло» рядом на одном экране
    читаются как расхождение и заставляют искать ошибку там, где её нет.
    """
    from ops import yandex_api
    from ops.analytics_models import ConversionSent

    days = max(1, min(365, int(request.GET.get("days", "30") or 30)))
    status = {"configured": yandex_api.configured(), "counter": settings.METRIKA_ID}
    summary, campaigns, metrika_error, direct_error = None, None, "", ""
    if status["configured"]:
        if settings.METRIKA_ID:
            try:
                summary = yandex_api.metrika_summary(days)
            except yandex_api.YandexError as error:
                metrika_error = str(error)
        else:
            metrika_error = ("PSEUDEX_METRIKA_ID не задан — счётчика нет, "
                             "статистики не будет даже с рабочим токеном.")
        try:
            campaigns = yandex_api.direct_campaigns()
        except yandex_api.YandexError as error:
            direct_error = str(error)

    sent = (ConversionSent.objects.values("target")
            .annotate(n=Count("id")).order_by("target"))
    return render(request, "ops/yandex.html", {
        "days": days, "status": status, "summary": summary,
        "campaigns": campaigns, "metrika_error": metrika_error,
        "direct_error": direct_error,
        "direct_pending": "Incomplete registration" in direct_error
                          or "58" in direct_error,
        "conversions": [{"target": row["target"], "count": row["n"]} for row in sent],
        "conversion_total": sum(row["count"] for row in sent),
    })
