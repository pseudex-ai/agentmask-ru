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
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Organization
from billing import licensing
from billing import reconcile as billing_reconcile
from billing.models import Invoice, Plan

# СТРАНИЦА БЬЁТСЯ О ПОТОЛОК ПАКЕТНОЙ РУЧКИ, А НЕ О ЧИСЛО КЛИЕНТОВ.
# `/admin/fleet` отвечает 400 сверх двухсот идентификаторов — намеренно, чтобы
# один URL не превращался в сколь угодно долгую работу под локом store. Размер
# страницы должен быть заведомо меньше, иначе консоль ломается ровно тогда, когда
# клиентов становится много, то есть в самый неудачный момент.
PAGE_SIZE = 50


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


@staff_member_required
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


@staff_member_required
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


@staff_member_required
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


@staff_member_required
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


@staff_member_required
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


@staff_member_required
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


@staff_member_required
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
