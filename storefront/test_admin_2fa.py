"""2FA (TOTP) на админку и /ops/: пароль — не всё, нужен ещё код.

Доказывает разбор требования владельца (лёгкий 2FA, без тяжёлых зависимостей):
  * staff-пользователь БЕЗ подтверждённого OTP НЕ попадает ни в админку, ни в
    /ops/ (редирект на вход) — один утёкший пароль больше не открывает доступ к
    ПД клиентов и к рычагам биллинга;
  * с подтверждённым TOTP-устройством в сессии обе точки открываются;
  * management-команда enroll_totp создаёт устройство и печатает otpauth-URI,
    чтобы владельца можно было привязать ПО SSH и не запереть себя (аварийный
    выход: телефон потерян — заводим заново через ssh, доступ к серверу есть).

Запуск:  cd storefront && .venv/bin/python test_admin_2fa.py
"""
import io
import os
import sys


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "admin-2fa-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-2fa-test.db"
    os.environ["SITE_URL"] = "http://localhost"
    if os.path.exists("/tmp/pseudex-2fa-test.db"):
        os.remove("/tmp/pseudex-2fa-test.db")
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)

    from django.conf import settings
    from django.test import Client
    from django.core.management import call_command as run
    from accounts.models import User
    from django_otp import DEVICE_ID_SESSION_KEY
    from django_otp.plugins.otp_totp.models import TOTPDevice

    ok = True
    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    admin_url = f"/{settings.ADMIN_PATH}/"
    ops_url = f"/{settings.ADMIN_PATH}/ops/tariffs/"

    user = User.objects.create_superuser(email="op@example.com", password="pw-strong-123")
    c = Client()
    c.force_login(user)

    # --- пароль есть (force_login), но сессия НЕ verified: закрыто ---
    r_admin = c.get(admin_url)
    check(r_admin.status_code == 302,
          "админка закрыта без 2FA (redirect на вход)", f"code={r_admin.status_code}")
    r_ops = c.get(ops_url)
    check(r_ops.status_code == 302,
          "/ops/ закрыт без 2FA (redirect на вход)", f"code={r_ops.status_code}")

    # --- подтверждённое устройство + сессия помечена verified: открыто ---
    device = TOTPDevice.objects.create(user=user, name="test", confirmed=True)
    s = c.session
    s[DEVICE_ID_SESSION_KEY] = device.persistent_id
    s.save()

    r_admin2 = c.get(admin_url)
    check(r_admin2.status_code == 200, "с 2FA админка открыта", f"code={r_admin2.status_code}")
    r_ops2 = c.get(ops_url)
    check(r_ops2.status_code == 200, "с 2FA /ops/ открыт", f"code={r_ops2.status_code}")

    # --- обычный клиент (не staff) не проходит даже verified ---
    plain = User.objects.create_user(email="client@example.com", password="pw-strong-000")
    c2 = Client()
    c2.force_login(plain)
    pdev = TOTPDevice.objects.create(user=plain, name="t", confirmed=True)
    s2 = c2.session
    s2[DEVICE_ID_SESSION_KEY] = pdev.persistent_id
    s2.save()
    check(c2.get(ops_url).status_code == 302,
          "не-staff с 2FA всё равно не в /ops/", f"code={c2.get(ops_url).status_code}")

    # --- enroll_totp: аварийный выход по SSH ---
    User.objects.create_superuser(email="owner@example.com", password="pw-strong-456")
    buf = io.StringIO()
    run("enroll_totp", "owner@example.com", stdout=buf)
    out = buf.getvalue()
    check(TOTPDevice.objects.filter(user__email="owner@example.com", confirmed=True).exists(),
          "enroll_totp создал ПОДТВЕРЖДЁННОЕ устройство")
    check("otpauth://totp/" in out,
          "enroll_totp напечатал otpauth-URI для привязки в приложении", out[:60])

    # --- повторный enroll не плодит устройства, а пере-создаёт одно ---
    buf2 = io.StringIO()
    run("enroll_totp", "owner@example.com", stdout=buf2)
    check(TOTPDevice.objects.filter(user__email="owner@example.com").count() == 1,
          "повторный enroll_totp держит ровно одно устройство (сброс, не дубль)")

    print("=" * 60)
    if not ok:
        raise SystemExit("admin 2FA not correct")
    print("admin 2FA OK — пароль не открывает, TOTP открывает, staff-гейт цел, "
          "enroll по SSH работает")
    return 0


if __name__ == "__main__":
    sys.exit(main())
