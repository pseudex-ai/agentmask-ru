---
name: prod-server
description: Боевой сервер pseudex (Timeweb VPS `pseudex-prod`, 201.34.151.187) — как на него зайти, что где лежит, как читать состояние выкатки и сервисов, как выкатить/откатить и чего на нём нельзя делать. Использовать для любой работы на проде: диагностика, логи, первичная настройка, обновление .env, ручная выкатка. Чтение свободно; остановка сервисов, правка .env, откат — только с подтверждением владельца. Секреты хоста в чат не печатать.
allowed-tools:
  - Bash
  - Read
---

# Боевой сервер `pseudex-prod`

## Вход

```bash
ssh pseudex-prod            # ~/.ssh/config: root@201.34.151.187, ключ ~/.ssh/pseudex_prod
```

Ключ — отдельный, только для этого хоста (`~/.ssh/pseudex_prod`, зарегистрирован в
Timeweb как `pseudex-prod`, id 773175). Парольный вход sshd запрещает
`bootstrap.sh`; если `grep PasswordAuthentication /etc/ssh/sshd_config.d/*` не
говорит `no` — bootstrap ещё не прогонялся.

Хост: Timeweb Cloud, Санкт-Петербург, Ubuntu 24.04, 4 vCPU, 8 ГБ, 80 ГБ NVMe,
IPv6 `2a03:6f01:1:2::2:3c72`. Управление самой машиной (перезагрузка, снимок,
консоль) — скилл `timeweb`.

## Что где лежит

| Путь | Что |
|---|---|
| `/opt/pseudex` | клон репозитория; агент делает `git checkout <тег>` — **руками не редактировать**, следующий обход перепишет |
| `/opt/pseudex/deploy/.env` | ВСЕ секреты стенда, 600, не в гите. Значения — из `~/pseudex-*.txt` владельца и его менеджера паролей |
| `/opt/pseudex/deploy/.env.seller` | реквизиты продавца (счета, оферта), не в гите |
| `/opt/pseudex/deploy/secrets/license-admin-token` | полный токен для Prometheus, файлом |
| `/opt/pseudex/deploy/backups/` | локальные копии обеих баз, ежедневно |
| `/opt/pseudex/deploy/.deployed` | какая версия выкачена сейчас (пишет агент) |
| docker volumes `pseudex_*` | postgres, license-data, loki/prometheus/grafana, caddy (сертификаты) |

Полная карта сервисов, тревог и восстановления — `docs/operations.md`; здесь
только то, что нужно, чтобы не искать.

## Первый круг диагностики (чтение, без подтверждения)

```bash
ssh pseudex-prod 'cd /opt/pseudex && docker compose -f deploy/compose.yml ps'
ssh pseudex-prod 'systemctl status pseudex-agent.timer pseudex-agent.service --no-pager'
ssh pseudex-prod 'journalctl -u pseudex-agent -n 50 --no-pager'
ssh pseudex-prod 'systemctl list-timers --no-pager pseudex-\*'
ssh pseudex-prod 'df -h / && free -m'
ssh pseudex-prod 'cd /opt/pseudex && docker compose -f deploy/compose.yml logs --no-color --tail 100 <сервис>'
```

Логи контейнеров могут содержать данные клиентов — **в чат не пересылать
целиком**, только строки ошибки. Grafana/Loki — через туннель:
`ssh -L 3000:127.0.0.1:3000 pseudex-prod` → http://localhost:3000.

## Как это выкатывается (чтобы не мешать)

Раз в минуту `pseudex-agent.timer` → `deploy/agent.sh`: `git fetch --tags` →
самый свежий `v[0-9]*` → `cosign verify` пяти образов по личности
`release.yml@refs/tags/vX.Y.Z` → `compose up -d --wait` → откат на прежний тег,
если нездорово. Значит:

- **Выкатить** = `ship` в GitHub (workflow_dispatch) или ручной тег; на хосте
  ничего делать не нужно. Проверить: `journalctl -u pseudex-agent -f`.
- **Откатить / заморозить** = строка `PSEUDEX_PIN=vX.Y.Z` в `deploy/.env`
  (юнит читает его как `EnvironmentFile`): агент держит эту версию и не
  выкатывает новые, пока строка стоит. Альтернатива — `git tag -f` на прежний
  коммит и push. См. заголовок `deploy/agent.sh`. Только с подтверждением
  владельца.
- **Профили** (`observability`, `support`) включаются в `deploy/.env`
  строкой `COMPOSE_PROFILES=`, не флагом `--profile`: агент делает `up -d` без
  флагов.
- Конфиги из чекаута (Caddyfile, alerts.yml, config.yaml бота) применяются
  выкаткой тега, который их менял (`PSEUDEX_CONF_REV`); ручная правка на хосте
  живёт до следующего обхода.

## Первичная настройка (один раз, по шагам)

1. Ключ развёртывания для клона приватного репозитория — на хосте:
   `ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N "" -C pseudex-prod-deploy`,
   публичную половину — `gh repo deploy-key add … --title pseudex-prod` (read-only).
2. `git clone git@github.com:Isk4R1oT/Obscura.git /opt/pseudex && sudo bash /opt/pseudex/deploy/bootstrap.sh`
   — печатает шаблон `.env` и останавливается.
3. Заполнить `deploy/.env` (значения из `~/pseudex-release-keys.txt`,
   `~/pseudex-backup-keys.txt`, `~/pseudex-bot-token.txt` владельца) — **по
   ssh, не через чат**; `COMPOSE_PROFILES=observability,support`.
4. `sudo bash deploy/bootstrap.sh` ещё раз — включает таймеры; агент выкатит
   свежий тег сам в течение минуты.
5. Только когда `docker compose ps` зелёный по IP — A-записи `pseudex.ru`,
   `license.pseudex.ru` → `201.34.151.187` (Let's Encrypt копит неудачи на домен,
   если запись стоит раньше стека).

## Чего на проде нельзя

- Печатать `.env`, токены, пароли в чат — только имена переменных и «задано/пусто».
- `docker compose down -v`, `docker volume rm`, `rm` в `backups/` — никогда без
  явного «да» владельца на конкретную команду: том постгреса и `license-data`
  невосстановимы иначе как из restic.
- Редактировать файлы в `/opt/pseudex` мимо гита — агент перепишет.
- Запускать гейты/тесты на проде — для этого есть CI и локальный стенд.
