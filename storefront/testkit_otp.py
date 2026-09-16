"""Вход в операторскую консоль ИЗ ТЕСТА, со вторым фактором.

ЗАЧЕМ ОТДЕЛЬНЫЙ ФАЙЛ. Консоль закрыта `otp_required` поверх `staff_member_required`,
поэтому `force_login` её больше НЕ открывает: сессия без подтверждённого
устройства уезжает на вход в админку, а тест видит редирект и `.context is None`
— ошибка, по которой совершенно не видно, что дело во втором факторе. Так уже
сломались две проверки (`test_analytics`, `test_ops_renders`), и каждая следующая
сломалась бы так же, пока эти четыре строки живут копией в каждом файле.

Устройство создаётся ПОДТВЕРЖДЁННЫМ и кладётся прямо в сессию. Код при этом не
считается намеренно: предмет проверки — экраны консоли, а не работа TOTP; её
проверяет `test_admin_2fa.py`, и там вход идёт настоящей формой с настоящим кодом.
"""


def verify_otp(client, user):
    """Сделать сессию клиента прошедшей второй фактор. Возвращает устройство."""
    from django_otp import DEVICE_ID_SESSION_KEY
    from django_otp.plugins.otp_totp.models import TOTPDevice

    device, _ = TOTPDevice.objects.get_or_create(
        user=user, name="test", defaults={"confirmed": True})
    if not device.confirmed:
        device.confirmed = True
        device.save(update_fields=["confirmed"])
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return device


def login_staff(client, user):
    """`force_login` плюс второй фактор — то, чем открывается консоль."""
    client.force_login(user)
    verify_otp(client, user)
    return client
