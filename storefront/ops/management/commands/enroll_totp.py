"""Привязать TOTP-устройство к аккаунту оператора — по SSH, без входа в UI.

Это АВАРИЙНЫЙ ВЫХОД и одновременно первичная настройка второго фактора. Админка
после включения 2FA требует подтверждённое устройство, а завести его через саму
админку нельзя, пока в неё не пускает второй фактор, — замкнутый круг. Команда
разрывает его снаружи: оператор с доступом к серверу (ssh есть по определению)
создаёт устройство, сканирует QR/URI в Google Authenticator и дальше входит с
кодом. Тот же путь, если телефон потерян: пере-выпустить и привязать заново.

    docker compose exec storefront python manage.py enroll_totp <email>

ПЕЧАТАЕТ СЕКРЕТ В STDOUT — это осознанно: канал уже доверенный (ssh на root), а
показать otpauth-URI негде иначе. Не логировать вывод в общий журнал.
"""
import io

import qrcode
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "Создать/пере-выпустить TOTP-устройство для аккаунта и напечатать QR."

    def add_arguments(self, parser):
        parser.add_argument("email", help="email аккаунта оператора")

    def handle(self, *args, **options):
        email = options["email"]
        user_model = get_user_model()
        try:
            user = user_model.objects.get(email=email)
        except user_model.DoesNotExist as error:
            raise CommandError(f"нет аккаунта с email {email}") from error

        # РОВНО ОДНО устройство на аккаунт: повторный запуск ПЕРЕ-выпускает, а не
        # плодит — иначе старый потерянный секрет остаётся действующим.
        TOTPDevice.objects.filter(user=user).delete()
        device = TOTPDevice.objects.create(user=user, name="pseudex", confirmed=True)

        url = device.config_url
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        ascii_qr = io.StringIO()
        qr.print_ascii(out=ascii_qr, invert=True)

        self.stdout.write(ascii_qr.getvalue())
        self.stdout.write("")
        self.stdout.write(f"Аккаунт: {email}")
        self.stdout.write(f"otpauth URI (если QR не сканируется): {url}")
        self.stdout.write("")
        self.stdout.write("Отсканируй QR в Google Authenticator (или вставь URI "
                          "вручную). После этого вход в админку требует 6-значный код.")
