"""ЗАПЛАТИТЬ МОЖНО В ЛЮБОЙ МОМЕНТ, А ПРОБУ НЕЛЬЗЯ БРАТЬ БЕСКОНЕЧНО.

ЧТО ЭТО ЛОВИТ, И ПОЧЕМУ ЭТО БЫЛО НЕВИДИМО. Заплатить было физически нечем:
`pay_invoice` оплачивает только УЖЕ ВЫСТАВЛЕННЫЙ счёт, а счета выставляет
месячный цикл — по окончании пробы или периода. Во время пробы счёта не
существует, значит у человека, готового отдать деньги сегодня, не было ни одной
кнопки, кроме годовой предоплаты. Ни один тест этого не ловил, потому что все
они проверяли ЖИЗНЕННЫЙ ЦИКЛ подписки — а он работал; отсутствовала дверь, и
отсутствие двери не ломает ни одной проверки, которая ходит через окно.

Вторая половина: проба выдавалась каждой новой почте без единой проверки и шла
НА ВЫБРАННОМ тарифе — отметил «Промышленный», получил миллион запросов
бесплатно, завёл второй ящик, получил ещё.

Сеть здесь подменяется: `mark_paid` ходит на лицензионный сервер, а предмет
проверки — что происходит с подпиской и счётом, а не то, доступен ли он.

Запуск:  cd storefront && .venv/bin/python test_paywall.py
"""
import os
import sys
from datetime import timedelta


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "paywall-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-paywall.db"
    os.environ["SITE_URL"] = "http://localhost"
    if os.path.exists("/tmp/pseudex-paywall.db"):
        os.remove("/tmp/pseudex-paywall.db")
    import django
    django.setup()
    from django.core.management import call_command
    from django.test.utils import setup_test_environment
    setup_test_environment()
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)

    from django.utils import timezone
    from billing import licensing, services
    from billing.models import Invoice, Plan, Subscription

    ok = True
    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    # Сеть — заглушкой. Записываем ВЫЗОВЫ: перевод тарифа на лицензионном
    # сервере это половина обещания «вы перешли на старший тариф», и его
    # отсутствие выглядит снаружи точно как успех.
    calls = []
    licensing.set_status = lambda org_id, status: calls.append(("status", org_id, status))
    licensing.set_org_plan = lambda org_id, plan: calls.append(("plan", org_id, plan)) or 1
    # Расход тоже заглушкой: месячный счёт спрашивает его у лицензионного
    # сервера, а предмет проверки — выставился ли счёт вообще, а не сколько в нём
    # строк. Ноль расхода делает счёт чистой абонплатой, что здесь и нужно.
    licensing.usage = lambda org_id: {"usage": {}}

    trial = services.trial_plan()
    check(trial is not None and trial.code == "free",
          "пробный тариф есть и это отдельная строка", str(trial))
    check(trial.included_requests < Plan.objects.get(code="start").included_requests,
          "лимиты пробы МЕНЬШЕ «Старта»",
          f"free={trial.included_requests} start={Plan.objects.get(code='start').included_requests}")

    # ── 1. проба идёт на пробном тарифе, выбор запоминается ────────────────
    org = services.create_account("first@acme-corp.ru", "Акме", "industrial", "203.0.113.7")
    sub = org.subscription
    check(sub.plan_id == "free",
          "новый аккаунт садится на ПРОБНЫЙ тариф, а не на выбранный",
          f"оказался на {sub.plan_id}")
    check(sub.intended_plan_id == "industrial",
          "выбранный тариф запомнен как намерение", str(sub.intended_plan_id))
    check(org.trial_granted and sub.trial_ends_at > timezone.now(),
          "первому — бесплатные дни выданы")
    check((sub.trial_ends_at - timezone.now()).days >= trial.trial_days - 1,
          f"и их столько, сколько стоит в тарифе ({trial.trial_days})")

    # ── 2. счёт по требованию, с подарком ──────────────────────────────────
    industrial = Plan.objects.get(code="industrial")
    invoice = services.build_switch_invoice(org, industrial)
    check(invoice.target_plan_id == "industrial" and invoice.state == Invoice.ISSUED,
          "во время пробы счёт ВЫСТАВЛЯЕТСЯ по требованию",
          f"{invoice.state} -> {invoice.target_plan_id}")
    check(invoice.total == industrial.monthly_price,
          "на сумму месяца выбранного тарифа", str(invoice.total))
    check(invoice.bonus_days == industrial.first_payment_bonus_days
          and invoice.bonus_days > 0,
          "и несёт подарочные дни за первый платёж", str(invoice.bonus_days))

    again = services.build_switch_invoice(org, industrial)
    check(again.pk == invoice.pk,
          "повторное нажатие отдаёт ТОТ ЖЕ счёт, а не второй",
          "две вкладки иначе дали бы два платежа")

    other = services.build_switch_invoice(org, Plan.objects.get(code="start"))
    invoice.refresh_from_db()
    check(other.pk != invoice.pk and invoice.state == Invoice.VOID,
          "передумал — прежний неоплаченный счёт аннулирован",
          "иначе можно случайно оплатить тариф, от которого отказался")

    # ── 3. оплата переводит на тариф и добавляет подарок ───────────────────
    #
    # Ключ выпускается ДО оплаты — так устроен продукт, — и здесь он нужен ещё
    # и затем, чтобы проверить перевод тарифа на лицензионном сервере: тариф
    # записан на КЛЮЧЕ, и без ключа переводить нечего.
    import hashlib as _hashlib
    from billing.models import LicenseKey as _Key
    _Key.objects.create(organization=org, prefix="ps_live_test",
                        key_hash=_hashlib.sha256(b"ps_live_test-key").hexdigest(),
                        environment="live", label="проверка")
    paid = services.build_switch_invoice(org, industrial)
    services.mark_paid(paid, payment_ref="test-1")
    sub.refresh_from_db()
    check(sub.plan_id == "industrial", "оплата ПЕРЕВЕЛА на выбранный тариф", sub.plan_id)
    check(sub.state == Subscription.ACTIVE, "подписка активна", sub.state)
    days = (sub.current_period_end - timezone.now()).days
    check(days >= 30 + paid.bonus_days - 1,
          f"период = месяц плюс подарок ({30 + paid.bonus_days} дней)", f"вышло {days}")
    check(sub.trial_ends_at <= timezone.now(),
          "проба закрыта, чтобы цикл не выставил по ней второй счёт")
    check(("plan", org.id, "industrial") in calls,
          "лицензионный сервер ПЕРЕВЕДЁН на новый тариф",
          f"вызовы: {calls}")
    check(sub.terms_monthly_price == industrial.monthly_price,
          "условия сняты с НОВОГО тарифа", str(sub.terms_monthly_price))

    # ── 4. второй платёж подарка не даёт ───────────────────────────────────
    second = services.build_switch_invoice(org, Plan.objects.get(code="work"))
    check(second.bonus_days == 0,
          "подарок только за ПЕРВЫЙ платёж", str(second.bonus_days))
    services.mark_paid(second, payment_ref="test-2")
    sub.refresh_from_db()
    check(sub.plan_id == "work", "смена тарифа у платящего тоже работает", sub.plan_id)

    # ── 5. повтор с того же адреса — без бесплатных дней ───────────────────
    repeat = services.create_account("second@other-corp.ru", "", "start", "203.0.113.7")
    check(not repeat.trial_granted,
          "повтор с того же адреса пробы не получает")
    check(repeat.subscription.trial_ends_at <= timezone.now(),
          "бесплатные дни ему не начислены")
    check(services.bonus_days_for(repeat, industrial, False) == 0,
          "и подарка за первый платёж тоже нет",
          "иначе подарок стал бы новым способом брать продукт бесплатно")

    # ── 5b. проба НАЧАТА (был запрос через движок) — подарка нет ────────────
    # Подарок платит за решение купить, не выработав пробу. Кто уже прогнал
    # свои сценарии — получил то, ради чего проба была; лишние дни поверх лишние.
    fresh = services.create_account("buy-before-trial@corp-x.ru", "", "start", "203.0.113.9")
    check(fresh.trial_granted, "новой почте пробу выдали")
    check(services.bonus_days_for(fresh, industrial, False)
          == industrial.first_payment_bonus_days,
          "не начавшему пробу — подарок равен настройке тарифа",
          str(industrial.first_payment_bonus_days))
    check(services.bonus_days_for(fresh, industrial, True) == 0,
          "начавшему пробу (хоть один запрос через движок) — подарка нет")

    # ── 6. тот же КОРПОРАТИВНЫЙ домен — тоже повтор ────────────────────────
    same_domain = services.create_account("third@acme-corp.ru", "", "start", "198.51.100.4")
    check(not same_domain.trial_granted,
          "повтор с того же корпоративного домена пробы не получает")

    # ── 7. а общий почтовый домен НЕ считается ─────────────────────────────
    services.create_account("someone@gmail.com", "", "start", "198.51.100.5")
    public_mail = services.create_account("another@gmail.com", "", "start", "198.51.100.6")
    check(public_mail.trial_granted,
          "gmail не считается компанией: второй человек пробу получает",
          "иначе первый зарегистрировавшийся с gmail отрезал бы всех остальных")

    # ── 8. проба кончилась — обслуживание ВСТАЛО, а не продлилось даром ────
    #
    # Решение владельца: «сервис останавливается». Общая ветка цикла собрала бы
    # счёт на 0 ₽ (цена бесплатного тарифа — ноль), погасила бы его сама и
    # оставила клиента обслуживаться дальше: получился бы бесплатный тариф
    # навсегда, то есть прямо противоположное принятому решению. Ошибка тихая —
    # снаружи выглядит как «всё работает».
    from django.core.management import call_command as _call
    from django.core import mail as _mail
    ending = services.create_account("ends@third-corp.ru", "", "start", "198.51.100.20")
    ending.subscription.trial_ends_at = timezone.now() - timedelta(minutes=1)
    ending.subscription.save(update_fields=["trial_ends_at"])
    invoices_before = Invoice.objects.filter(organization=ending).count()
    calls.clear()
    _mail.outbox = []
    _call("run_billing_cycle", verbosity=0)
    ending.subscription.refresh_from_db()
    check(ending.subscription.state == Subscription.PAST_DUE,
          "по концу пробы подписка переходит в «не оплачена»",
          ending.subscription.state)
    check(("status", ending.id, "unpaid") in calls,
          "и обслуживание на лицензионном сервере ОСТАНОВЛЕНО", str(calls))
    check(Invoice.objects.filter(organization=ending).count() == invoices_before,
          "счёт на ноль рублей при этом НЕ выставляется",
          "документ ни о чём, который придёт письмом и заставит искать, что с ним делать")
    check(any("бесплатный период закончился" in m.subject.lower() for m in _mail.outbox),
          "человеку написали, что произошло и что делать",
          f"писем: {[m.subject for m in _mail.outbox]}")

    # ── 9. счёт на покупку НЕ блокирует месячный счёт того же дня ──────────
    #
    # Защита от двойного счёта в цикле отбирает по `period_start`, а у счёта на
    # покупку это СЕГОДНЯШНИЙ день (его выставляет нажатие кнопки, а не
    # календарь). Без исключения он молча запрещал бы выставить месячный счёт
    # клиенту, купившему тариф сегодня: период кончился, счёта нет, деньги не
    # выставлены — и видно это только через месяц по недостающей выручке.
    # Ровно та же ловушка уже была с годовым счётом, и это её второй случай.
    buyer = services.create_account("cycle@fourth-corp.ru", "", "start", "198.51.100.30")
    bought = services.build_switch_invoice(buyer, Plan.objects.get(code="start"))
    services.mark_paid(bought, payment_ref="test-cycle")
    buyer.subscription.refresh_from_db()
    buyer.subscription.current_period_end = timezone.now() - timedelta(minutes=1)
    buyer.subscription.save(update_fields=["current_period_end"])
    _call("run_billing_cycle", verbosity=0)
    monthly = Invoice.objects.filter(organization=buyer,
                                     target_plan__isnull=True).first()
    check(monthly is not None,
          "по концу периода месячный счёт всё-таки выставлен",
          "счёт на покупку того же дня его блокировал")

    # ── 10. заплатить можно РАНЬШЕ, чем выпущен ключ ───────────────────────
    #
    # Пока платили только по счёту, ключ существовал всегда — счёт приходил
    # тому, кто уже работал. С кнопкой «оплатить сейчас» человек может заплатить
    # в первый же день, не пройдя по ссылке из письма, и возобновлять тогда
    # нечего. Раньше это была бы ошибка обработки платежа, ЮKassa начала бы
    # повторять доставку, и каждая попытка падала бы так же — при том что деньги
    # записаны и всё в порядке.
    early = services.create_account("early@fifth-corp.ru", "", "start", "198.51.100.31")
    early_invoice = services.build_switch_invoice(early, Plan.objects.get(code="start"))
    # Имя проверки одно на обе ветки: провал записывается ТАМ, ГДЕ СЛУЧИЛСЯ,
    # а не выносится флагом наружу — исключение, превращённое в булево,
    # теряет собственный текст, и читать в отчёте будет нечего.
    survives = "оплата до выпуска ключа обрабатывается, а не падает"
    try:
        services.mark_paid(early_invoice, payment_ref="test-early")
    except Exception as error:  # noqa: BLE001 — предмет проверки именно любой отказ
        check(False, survives, f"упало: {error}")
    else:
        early_invoice.refresh_from_db()
        check(early_invoice.state == Invoice.PAID, survives,
              f"состояние счёта: {early_invoice.state}")
        check(early_invoice.service_resumed_at is not None,
              "и счёт помечен обработанным, иначе ЮKassa будет повторять вечно")

    # ── 11. КНОПКА ДЕЙСТВИТЕЛЬНО ЕСТЬ НА ЭКРАНЕ ────────────────────────────
    #
    # Всё выше проверяет механику, а жалоба владельца была про ЭКРАН: «нельзя
    # оплатить, вообще нигде, только вот тут пересылает на ЮKassa» — то есть
    # единственной кнопкой была годовая предоплата. Механика, до которой нет
    # кнопки, для клиента не существует.
    from django.test import Client
    from accounts.models import Membership
    fresh = services.create_account("cabinet@another-corp.ru", "", "work", "198.51.100.9")
    member = Membership.objects.get(organization=fresh).user
    client = Client()
    client.force_login(member)
    cabinet = client.get("/app/").content.decode()
    check('action="/app/subscribe"' in cabinet,
          "в кабинете НА ПРОБЕ есть форма оплаты тарифа",
          "именно её отсутствие и было жалобой: платить нечем")
    check('value="work"' in cabinet and 'selected' in cabinet,
          "и в ней подставлен тариф, выбранный при регистрации")
    check("дней в подарок" in cabinet,
          "подарок за первый платёж назван на экране",
          "иначе повода платить сегодня по-прежнему нет")

    # И у повторного аккаунта экран говорит правду, а не молчит.
    repeat_member = Membership.objects.get(organization=repeat).user
    client2 = Client()
    client2.force_login(repeat_member)
    repeat_cabinet = client2.get("/app/").content.decode()
    check("Бесплатные дни этому аккаунту не выдавались" in repeat_cabinet,
          "повтору экран объясняет, почему у него нет пробы",
          "молчащий отказ выглядит как поломка продукта")
    check('action="/app/subscribe"' in repeat_cabinet,
          "и заплатить он всё равно может")

    print("=" * 60)
    if not ok:
        raise SystemExit("paywall is not correct")
    print("paywall OK — заплатить можно в любой момент, смена тарифа доходит до "
          "лицензионного сервера, проба выдаётся один раз и на своих лимитах")
    return 0


if __name__ == "__main__":
    sys.exit(main())
