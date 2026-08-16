# Сторонние компоненты

Файл ships вместе с образом. Он существует не для галочки: один из компонентов
распространяется под лицензией с условием share-alike, и обязательство по нему —
именно указание авторства.

---

## Морфологический словарь русского языка

**pymorphy3-dicts-ru** — данные словаря, собранные из корпуса **OpenCorpora**.

| | |
|---|---|
| Данные | Creative Commons Attribution-Share Alike 3.0 Unported |
| Код пакета | MIT |
| Источник | http://opencorpora.org/ |
| Текст лицензии | https://creativecommons.org/licenses/by-sa/3.0/ |

### Почему это не делает продукт BY-SA

Словарь включён в образ **в неизменном виде**, рядом с независимым от него
кодом. По терминологии лицензии это *Collection*, а не *Adaptation*, и
раздел 4(a) говорит об этом прямо:

> This does not require the Collection apart from the Work itself to be made
> subject to the terms of this License.

Share-alike распространяется на *переработку* произведения. Мы словарь не
изменяем и не производим от него новых словарей — движок загружает его как есть.
Обязательство, которое остаётся, — атрибуция, и она выполнена этим файлом.

**Если словарь когда-нибудь будет дополнен или переработан** — например, если в
него добавят свои словоформы — переработанный словарь придётся распространять
под той же лицензией. Код продукта это по-прежнему не затронет, но такой словарь
перестанет быть тем, что можно держать в закрытом лизинговом бандле. Это
единственный сценарий, в котором вопрос возвращается.

---

## Прочее

- **pymorphy3** — MIT, https://github.com/no-plagiarism/pymorphy3
- **natasha**, **razdel**, **navec**, **slovnet** — MIT, https://github.com/natasha
- **phonenumbers** (libphonenumber) — Apache License 2.0
- **FastAPI**, **Starlette**, **uvicorn** — BSD 3-Clause
- **httpx**, **h11**, **anyio** — BSD / MIT
- **cryptography** — Apache License 2.0 / BSD

Полный список версий — в `requirements.txt` образа.
