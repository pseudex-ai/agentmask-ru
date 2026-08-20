"""The coding-agent onboarding prompt.

A module rather than a template block because this text is the product's
onboarding: it is executed, not read. It has to be verifiable, and a string
built in a template cannot be tested.

WHY A PROMPT AT ALL. The connection is two commands, which is easy for someone
who knows where their project calls a model — and that is the assumption that
excludes everyone else. The prompt hands the search, the container and the
verification to an agent that is already sitting in the customer's repository.

Agent-agnostic on purpose: it is plain instructions plus shell, so Claude Code,
Codex, Cursor and the rest all execute it. Naming only one would be both a
narrower claim than the truth and a reason for someone using another agent to
assume the product is not for them.

THE VERIFICATION STEP IS THE POINT. Anyone can start a container and change an
environment variable and believe they are done; the failure mode that matters is
traffic quietly going around the proxy, which looks exactly like success. Step 5
proves masking actually ran by reading the counters back, and the prompt says to
STOP if they are empty rather than report a job well done.
"""

# Kept out of the f-string so the braces in the JSON payload do not have to be
# escaped, which is where this kind of text usually rots.
_CHECK_BODY = (
    '{"model":"<модель, которую использует проект>",'
    '"messages":[{"role":"user",'
    '"content":"Клиент Иванов Пётр Сергеевич, телефон +7 916 214-88-03, '
    'адрес Москва, Ленинский проспект 42"}]}'
)


def claude_prompt(license_key: str, image: str, ui_port: str,
                  license_url: str = "") -> str:
    """The text the customer pastes into their coding agent, whichever it is."""
    # Only printed when this deployment knows a licensing address of its own.
    # The image carries the production default, so adding the line always would
    # be noise in the command every real customer copies — and omitting it always
    # is what sent three personas into a wall on the local stand.
    license_url_line = (f"     -e PSEUDEX_LICENSE_URL={license_url} \\\n"
                        if license_url else "")
    return f"""Подключи pseudex к этому проекту.

Что это: контейнер, который прячет персональные данные от языковой модели и
возвращает настоящие значения обратно в аргументы вызовов инструментов. Он
OpenAI-совместимый — приложение ходит в него вместо провайдера, код при этом
менять не нужно.

Ключ лицензии: {license_key}
Образ: {image}

Выполни по шагам. После каждого шага покажи, что получилось.

1. НАЙДИ, КУДА ПРОЕКТ ХОДИТ ЗА МОДЕЛЬЮ.
   Ищи OPENAI_BASE_URL, base_url=, ANTHROPIC_BASE_URL, конфиги LiteLLM,
   клиентов openai/anthropic в коде. Скажи, что нашёл и какой адрес у
   провайдера. Если адрес нигде не задан — используется OpenAI по умолчанию,
   то есть https://api.openai.com/v1

   Если проект ходит в Anthropic, Gemini, GigaChat или YandexGPT их родными
   API — остановись и скажи мне. У них другой формат запроса, там нужна
   другая схема подключения (через LiteLLM), и делать её вслепую не надо.

2. ПОЛОЖИ КЛЮЧ В .env
   PSEUDEX_LICENSE_KEY={license_key}
   Проверь, что .env перечислен в .gitignore. Ключ не коммить и не печатать
   в логи.

3. ПОДНИМИ КОНТЕЙНЕР.
   Подставь в PSEUDEX_UPSTREAM адрес провайдера, найденный на шаге 1.

   docker run -d --name pseudex --restart unless-stopped \\
     -p 8000:8000 -p 127.0.0.1:{ui_port}:{ui_port} \\
     -v pseudex-data:/data \\
     -e PSEUDEX_ROLE=proxy \\
     -e PSEUDEX_UPSTREAM=<адрес провайдера из шага 1> \\
     -e PSEUDEX_LICENSE_KEY=$PSEUDEX_LICENSE_KEY \\
{license_url_line}     {image}

   Если порт 8000 занят — возьми другой (например 8010) и дальше подставляй
   его везде вместо 8000. Не убивай чужие контейнеры.

   Убедись, что контейнер ДЕЙСТВИТЕЛЬНО запустился, прежде чем ждать:
   docker ps --filter name=pseudex --format '{{{{.Names}}}} {{{{.Status}}}}'

   Пустой вывод значит, что docker run упал — покажи его ошибку и остановись.
   Проверять порт вместо этого нельзя: на нём может отвечать чужой сервис, и
   тогда проверка пройдёт, а контейнера не будет.

   Потом дождись готовности — до минуты, поднимаются словари морфологии:
   until curl -fsS localhost:8000/health | grep -q '"license":"active"'; do
     sleep 2
     docker ps --filter name=pseudex --format '{{{{.Names}}}}' | grep -q pseudex \\
       || {{ echo "контейнер остановился"; docker logs pseudex --tail 30; break; }}
   done

4. ПЕРЕКЛЮЧИ ПРИЛОЖЕНИЕ НА КОНТЕЙНЕР.
   OPENAI_BASE_URL=http://localhost:8000/v1

   Ключ провайдера НЕ МЕНЯЙ — он остаётся ваш, приложение шлёт его как
   раньше, контейнер пересылает его наверх нетронутым.

   Меняй переменную окружения, а не код. Если базовый адрес зашит в коде —
   вынеси его в переменную и скажи мне, где именно он был.

5. ПРОВЕРЬ, ЧТО МАСКИРОВАНИЕ ДЕЙСТВИТЕЛЬНО РАБОТАЕТ.
   Возьми выдуманного человека. НЕ используй настоящие данные клиентов.

   curl -s localhost:8000/v1/chat/completions \\
     -H "Authorization: Bearer $<переменная с ключом провайдера>" \\
     -H 'Content-Type: application/json' \\
     -d '{_CHECK_BODY}'

   Потом посмотри счётчики:

   curl -s localhost:8000/usage \\
     -H "Authorization: Bearer $<переменная с ключом провайдера>"

   В ответе protected_counts должен содержать NAME, PHONE и LOC.

   ЕСЛИ СЧЁТЧИКИ ПУСТЫЕ — НЕ ПРОДОЛЖАЙ И НЕ СООБЩАЙ ОБ УСПЕХЕ. Это значит,
   что трафик идёт мимо контейнера, и данные уходят в модель как есть.
   Покажи docker logs pseudex и разберись, почему запрос не дошёл.

6. ОТКРОЙ ЛОКАЛЬНЫЙ ИНТЕРФЕЙС.
   docker logs pseudex 2>&1 | grep 'локальный интерфейс' -A2

   Там видно, что именно было защищено, журнал раскрытий и самопроверка.
   Контейнер печатает ссылку со своим ВНУТРЕННИМ портом {ui_port} — если ты
   опубликовал интерфейс на другом, подставь свой. Токен из ссылки верный.

7. НАСТРОЙ РЕЗЕРВНУЮ КОПИЮ ТОМА pseudex-data.

   В томе лежит СООТВЕТСТВИЕ «настоящее значение → подмена». Ваши системы —
   CRM, база заказов, журналы — уже хранят подмены. Без тома они превращаются
   в строки, к которым нет обратного пути: ни мы, ни вы восстановить их не
   сможем, потому что настоящие значения есть только там.

   Это не про наш отказ и не про лицензию. Это про `docker volume rm`,
   переезд на другую машину и умерший диск.

   docker run --rm -v pseudex-data:/data -v "$PWD":/backup alpine \\
     tar czf /backup/pseudex-data-$(date +%F).tar.gz -C /data .

   Положи это в тот же планировщик, где лежат остальные ваши бэкапы, и
   проверь ВОССТАНОВЛЕНИЕ хотя бы раз — копия, которую никто не разворачивал,
   это не копия.

   Том шифруется вашими средствами, как любой другой том с персональными
   данными: права доступа, шифрование диска, шифрование резервных копий.

ПРАВИЛА, КОТОРЫЕ НЕЛЬЗЯ НАРУШАТЬ:
- Никогда не подставляй настоящие персональные данные в проверочные запросы.
- Порт {ui_port} публикуй только на 127.0.0.1. Там видны настоящие значения,
  и `-p {ui_port}:{ui_port}` на облачной машине откроет их в интернет.
- Не коммить ключ лицензии и не выводить его в вывод команд.
- Если шаг 5 не сходится — это не мелочь, а незащищённый трафик. Останавливайся.
- Том pseudex-data не удалять и не пересоздавать. Он единственный носитель
  соответствия между подменами в ваших системах и настоящими значениями.
"""
