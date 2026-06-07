# Realistic RU User Messages for the PII-Detection Eval Set

Research for the RU PII tokenization gateway. Date: 2026-06-07.

Goal: make the synthetic eval set messy and realistic by mirroring how real RU users actually
write to support bots, booking assistants, and marketplaces (Ozon / WB / Avito / Я.Маркет
support, записи к врачу/салону, банковская поддержка, ЖКХ, такси/доставка).

> NOTE on method: the templates below are **synthetic reconstructions** of the phrasing,
> intent, and *formatting texture* observed in real public reviews/complaints/support threads
> (sources at the bottom). All names, phones, cards, addresses, СНИЛС/ИНН are **fabricated
> placeholders** — they reproduce real-world *formatting noise* without copying any real
> person's data. Use them as eval templates; regenerate the actual values from validators.

PII-type abbreviations used in annotations: **PHONE, NAME** (ФИО), **ADDR, DOB** (дата
рождения), **DATE** (event date, not DOB), **CARD, EMAIL, SNILS, INN, PASSP** (паспорт),
**OMS** (полис), **VU** (вод. удостоверение), **GRZ** (госномер), **ACCT** (лицевой счёт),
**TRACK/ORDER/ART/AMOUNT/TALON** = hard-negative number classes (must NOT be masked).

---

## TL;DR — what the eval set must capture

1. **Intent verbs are short and imperative**: «запишите», «отмените», «перенесите», «верните
   деньги», «проверьте», «где посылка», «не пришёл заказ», «оформите доставку». PII is dumped
   *around* the intent, often with no label.
2. **Phones come in ~8 formats** (8 / +7 / без кода / с пробелами / с дефисами / со скобками /
   слитно / с «доб.»). This is the single biggest source of regex misses.
3. **Names appear in oblique cases and with typos** («на Ивана», «для Анны Петровой», «запишите
   Свету») — pure regex won't catch them, NER must handle падежи.
4. **Addresses are free-form and abbreviated** («Ленина 5 кв 3», «мкр Северный д12», «ул
   Сердобольская д 43»). House/apt numbers look like bare digits.
5. **Dates are relative or partial** («на завтра», «15 марта», «01.02», «к 18:00»). DOB vs event
   DATE must be disambiguated by context, not format.
6. **One message often carries 3-5 PII types** with mixed RU/EN, lowercase, no punctuation,
   emoji, and surrounding chatter.
7. **Hard negatives dominate marketplace traffic**: трек-номер, номер заказа, артикул, сумма,
   номер ПВЗ, ID обращения — all look numeric/ID-like but are NOT personal data.

---

## PART 1 — Realistic message templates, grouped by intent

Each template marks PII spans with `«…»` and lists the **PII types** + **messy traits**.
Replace placeholder values with validator-generated ones at dataset-build time.

### A. Marketplace — заказ не пришёл / где посылка (Ozon, WB, Я.Маркет, Avito)

1. `не пришёл заказ 52905115-0017 уже месяц прошло где он??? телефон для связи 89031234567`
   - PII: **PHONE** (8-prefix, слитно). HARD-NEG: ORDER `52905115-0017`.
   - Traits: lowercase, no punctuation, multiple `?`, phone без меток.

2. `Здравствуйте! Где моя посылка трек RA123456789RU отслеживается до 24 февраля и всё, пропала`
   - PII: none. HARD-NEG: TRACK `RA123456789RU`, DATE-in-text.
   - Traits: polite opener then chaos; track looks like an ID but isn't PII.

3. `добрый день заказ не доставили, я Петрова Анна, тел +7 (912) 345-67-89, адрес Ленина 5 кв 3`
   - PII: **NAME, PHONE, ADDR**. Traits: name «Фамилия Имя», phone +7 со скобками, addr свободная.

4. `артикул 167284593 не тот цвет пришёл хочу вернуть деньги на карту 2202 2002 1234 5678`
   - PII: **CARD** (Мир, пробелы по 4). HARD-NEG: ART `167284593`.
   - Traits: card без метки «карта», артикул рядом — classic over-mask trap.

5. `Верните деньги за заказ № 0123-4567890. Оплачивал картой ****3797, сумма 4990 р`
   - PII: **CARD** (только last-4). HARD-NEG: ORDER, AMOUNT `4990 р`.
   - Traits: masked card last-4, сумма не маскировать.

6. `курьер не привёз, позвоните мне 8 912 345 67 89 или мужу 8(912)345-67-90 спасибо`
   - PII: **PHONE ×2** (разные форматы: пробелы vs скобки+дефисы). Traits: два телефона в одном.

7. `заказ оформлен на электронку ivan.petrov92@mail.ru а доставка на пр-т Мира д12 под 2 кв 45`
   - PII: **EMAIL, ADDR**. Traits: «электронку» colloq, addr с «пр-т / под / кв», RU/EN mix.

8. `пвз №35417 закрыт, заказ 81234567 висит, заберите трекинг 80012345678901 не работает`
   - PII: none. HARD-NEG: ПВЗ `№35417`, ORDER `81234567`, РПО-трек `80012345678901` (14 цифр).
   - Traits: three numeric IDs, zero PII — must mask nothing.

9. `ozon rocket потерял посылку 0288-1234-5678 я Сидоров И.И. тел: 89261112233`
   - PII: **NAME** (Фамилия И.О.), **PHONE**. HARD-NEG: ORDER.
   - Traits: инициалы; phone с меткой «тел:» (easy case for contrast).

10. `Avito доставка кинули, продавец просил перевести на карту 5469380012345678 5000р не делайте так`
    - PII: **CARD** (Сбер, 16 слитно). HARD-NEG: AMOUNT.
    - Traits: card слитно без пробелов, warning narrative around it.

### B. Marketplace — возврат / отмена / претензия

11. `отмените заказ 49001234567 пожалуйста передумала, деньги верните на ту же карту`
    - PII: none (card implied, not stated). HARD-NEG: ORDER. Traits: «ту же карту» = no PII.

12. `хочу вернуть товар. ФИО Иванова Мария Сергеевна, паспорт 4509 123456, телефон 9151234567`
    - PII: **NAME** (полное), **PASSP** (серия 4 + номер 6), **PHONE** (10 цифр без 8/+7).
    - Traits: passport «4509 123456», phone без кода страны.

13. `претензия!!! оплатила 19.05 не получила. Карта 4276********1234 сумма списания 1331`
    - PII: **CARD** (Visa/Сбер masked middle). HARD-NEG: AMOUNT, DATE `19.05`.
    - Traits: партиал-маска карты, дата без года.

14. `деньги списали дважды 20:02 и 20:05, верните на сбер 4081781012345678 спасибо заранее`
    - PII: **CARD** (looks like счёт/карта — 16+ digit Сбер). HARD-NEG: times `20:02`.
    - Traits: 16-digit string is a card; time stamps are NOT PII.

### C. Запись к врачу / поликлиника / регистратура

15. `запишите меня к терапевту на завтра, Котова Елена, дата рождения 14.07.1989`
    - PII: **NAME, DOB** (`14.07.1989`). DATE-rel: «на завтра». Traits: DOB explicit, имя в им.п.

16. `можно перенести запись на пятницу? я Андрей Волков, тел 89997654321, талон 778-2034`
    - PII: **NAME, PHONE**. HARD-NEG: TALON `778-2034`, DATE-rel «пятницу».
    - Traits: талон number looks ID-like — do not mask.

17. `отмените запись к стоматологу на 15 марта 9:30 на имя Петрова И.`
    - PII: **NAME** (Петрова И., косвенно). HARD-NEG: DATE `15 марта`, time.
    - Traits: name в род./дат. падеже после «на имя».

18. `здравствуйте нужна запись к лору, снилс 112-233-445 95, полис 7712345678901234`
    - PII: **SNILS** (`XXX-XXX-XXX XX`), **OMS** (16 цифр, ЕНП). Traits: оба структурных ID без меток-границ.

19. `запишите ребёнка Машу 2018 г.р. к педиатру, мой номер +79161234567`
    - PII: **NAME** (диминутив), **DOB** (год only), **PHONE** (+7 слитно).
    - Traits: «2018 г.р.» = partial DOB, name уменьшительное.

20. `перезвоните 8-912-000-11-22 запись на узи на 01.02 в 8 утра, я Ольга`
    - PII: **PHONE** (дефисы), **NAME** (имя only). HARD-NEG: DATE `01.02`, time.

### D. Запись в салон / барбершоп

21. `запишите на стрижку завтра вечером, Света, телефон 9261112233`
    - PII: **NAME** (имя), **PHONE** (10 цифр без кода). Traits: имя only, casual.

22. `можно на маникюр к Алине на субботу? меня зовут Кристина, +7 905 444 33 22`
    - PII: **NAME ×2** (мастер Алина + клиент Кристина — оба ФИО-like!), **PHONE**.
    - Traits: AMBIGUOUS — two names, one is staff. Eval must mark client name; staff name is edge.

23. `отмените мою запись на окрашивание 12.06 на имя Гульназ, номер тот же что писала раньше`
    - PII: **NAME**. HARD-NEG: DATE `12.06`. Traits: «номер тот же» = no phone present.

24. `перенесите на др время плиз, записана как Аня Ж., тлф 89031234567 🙏`
    - PII: **NAME** (Аня Ж.), **PHONE**. Traits: «тлф» опечатка-сокращение, emoji, «др время».

### E. Банковская поддержка / чат

25. `заблокировали карту почему?? проверьте баланс по карте 5536 9137 0000 1234`
    - PII: **CARD** (Mastercard/Тинькофф, пробелы). Traits: full PAN dumped in chat.

26. `здравствуйте я Дмитрий Кузнецов, паспорт 45 09 123456, подтвердите операцию на 15000`
    - PII: **NAME, PASSP** (серия с пробелом `45 09`). HARD-NEG: AMOUNT.
    - Traits: passport серия split `45 09`.

27. `не приходит смс на +7(926)111-22-33 не могу войти, инн 771234567890 если надо`
    - PII: **PHONE** (+7 скобки), **INN** (12 цифр физлица). Traits: ИНН без метки-границ.

28. `верните комиссию на счёт 40817810099910004312 списали 199 руб ни за что`
    - PII: **ACCT** (р/с 20 цифр) — treat as financial PII. HARD-NEG: AMOUNT `199 руб`.
    - Traits: 20-digit счёт vs 16-digit card — different length, both sensitive.

29. `оформите справку, я родился 03.11.1975, снилс 11223344595 (без чёрточек написал)`
    - PII: **DOB, SNILS** (11 цифр слитно, без дефисов!). Traits: SNILS unformatted — regex must allow both.

### F. ЖКХ / управляющая компания / обращение

30. `нет горячей воды! адрес ул Гагарина д 7 кв 14, лицевой счёт 1234567890`
    - PII: **ADDR**. HARD-NEG: ACCT/лицевой счёт `1234567890` (10 digits — IS personal-ish; see note).
    - NOTE: лицевой счёт ЖКХ ties to a person → mark as **ACCT** PII; but length collides with phone/order.

31. `передаю показания счётчика: 04512 и 03317, квартира 45 дом 12 по Ленина, Иванов`
    - PII: **NAME, ADDR**. HARD-NEG: meter readings `04512 / 03317`.
    - Traits: meter numbers look like codes — must NOT mask; addr inverted order.

32. `жалоба на отопление, проживаю Сергей Иванович по мкр Северный д12 под3 кв 8, т 89164445566`
    - PII: **NAME** (имя+отчество), **ADDR**, **PHONE**. Traits: «мкр … д12 под3» сжато.

33. `прошу перерасчёт за январь, фио Громова Т.А., л/с 50 0123 4567, тел 8 800 уже не помню`
    - PII: **NAME** (Фамилия Т.А.). HARD-NEG: л/с `50 0123 4567`, AMOUNT-period.
    - Traits: «8 800 уже не помню» = phrase, not a real number — should NOT be parsed as phone.

### G. Такси / курьерская доставка

34. `забыл телефон в такси, водитель не берёт. мой второй номер 89261110000 машина а123вс77`
    - PII: **PHONE, GRZ** (`а123вс77`, lowercase RU plate). Traits: ГРЗ строчными, RU letters.

35. `оформите доставку на сегодня к 18:00, адрес Тверская 10 офис 5, получатель Никита, 9031112233`
    - PII: **NAME, ADDR, PHONE**. HARD-NEG: time. Traits: «офис 5», phone 10 цифр.

36. `курьер не звонит! я по адресу проспект Победы дом 33 корпус 2 подъезд 4 квартира 88`
    - PII: **ADDR** (full free-form). Traits: «дом/корпус/подъезд/квартира» полностью словами.

### H. Mixed / hard cases (multi-PII, no labels, ambiguous)

37. `иван 89031234567 москва ленина 5 кв 3 паспорт 4509123456 верните деньги 1500`
    - PII: **NAME, PHONE, ADDR, PASSP**. HARD-NEG: AMOUNT.
    - Traits: ALL lowercase, no punctuation, passport `4509123456` слитно (10 digits no space), 5 spans.

38. `Hi, my name is Ivan Petrov, тел +7 916 123 45 67, please cancel order 8123456`
    - PII: **NAME** (Latin), **PHONE**. HARD-NEG: ORDER. Traits: RU/EN mix, Latin transliterated name.

39. `номер 9261234567 это мой а 9261234500 это жены, запишите обоих 20го числа`
    - PII: **PHONE ×2** (bare 10-digit, no 8/+7). HARD-NEG: «20го» relative date.
    - Traits: two bare phone numbers with zero markers — easiest to miss.

40. `снилс 112-233-445 95 инн 771234567890 паспорт 4509 123456 это для записи в мфц на завтра`
    - PII: **SNILS, INN, PASSP** all in one line. Traits: three structured IDs adjacent, only spacing separates them.

41. `0123456789 — это номер заказа а не телефон!! не путайте, верните 3200`
    - PII: none. HARD-NEG: ORDER `0123456789` (10 digits → collides with bare phone!), AMOUNT.
    - Traits: **the canonical disambiguation case** — 10-digit string that is explicitly an order, not a phone.

42. `пишу с почты anna_k.2024@yandex.ru, заказ #ОЗN-7788, телефон для курьера 8 (495) 123-45-67`
    - PII: **EMAIL, PHONE** (8 скобки). HARD-NEG: ORDER `#ОЗN-7788` (mixed Cyrillic/Latin/digit).
    - Traits: email с цифрами/точкой/подчёркиванием, order с буквенным префиксом.

43. `вод удостоверение 77 АА 123456 машина в456ор199, оформите пропуск на Кузнецова`
    - PII: **VU** (`77 АА 123456`), **GRZ** (`в456ор199`), **NAME**. Traits: ВУ серия Cyrillic, plate 3-digit region.

44. `я бабушка Зинаида Павловна, мне 80 лет, помогите вернуть пенсию на карту 2200123456789012`
    - PII: **NAME** (имя+отчество), **CARD** (Мир 16 слитно). HARD-NEG: «80 лет» (age, not DOB — borderline).
    - Traits: narrative, age in words, card слитно.

### I. Hard-negative-heavy messages (should mask ZERO spans)

45. `статус заказа 0288-1234-5678: трек 80098765432109, артикул 167284593, сумма 4990, ПВЗ 35417`
    - PII: **NONE**. HARD-NEG: ORDER, TRACK(14-digit РПО), ART, AMOUNT, ПВЗ. Over-mask trap, 5 numeric IDs.

46. `обращение №RU-2026-0098123 по заказу 81234567, трек RB987654321RU, жду ответ`
    - PII: **NONE**. HARD-NEG: ticket ID, ORDER, TRACK (2-letter+9digit+2-letter).

47. `купон SALE2026 на 1500р, бонусов 320, кэшбэк 5%, когда зачислят на счёт?`
    - PII: **NONE**. HARD-NEG: promo code, AMOUNT, bonus count, percent. No personal data.

48. `модель iPhone 15 Pro 256gb imei 356789012345678 не включается, чек 00012345`
    - PII: edge — IMEI is device-identifying (mark per policy). HARD-NEG: SKU/model, чек number.
    - Traits: IMEI (15 digits) looks like SNILS-length but is device ID.

---

## PART 2 — Messy-formatting cheat-sheet per PII type

### PHONE (highest-variance type)
- `89031234567` (8 + слитно) · `8 903 123 45 67` (8 + пробелы) · `8-903-123-45-67` (дефисы)
- `8 (903) 123-45-67` / `8(903)123-45-67` (скобки) · `+7 903 123 45 67` / `+79031234567`
- `+7 (903) 123-45-67` · `9031234567` (bare 10, no 8/+7) · `903 123 45 67` (bare spaced)
- `8 800 333 33 33` (8-800 service) · с «доб. 123» · «тел/тлф/т/номер/моб/сотовый» markers OR none
- TRAP: «8 800 уже не помню», «звоните на тот же» = phrases, not numbers.

### NAME (ФИО) — requires NER, падежи
- `Иванова Мария Сергеевна` (полное) · `Петрова А.` / `Сидоров И.И.` (инициалы)
- `на Ивана` / `для Анны Петровой` / `записана как Аня Ж.` (косвенные падежи)
- `Света` / `Маша` / `Никита` (имя/диминутив only) · Latin `Ivan Petrov`
- typos: «Алексанр», «Дмитрйи»; lowercase «иван петров»; mixed «Anna_K».

### ADDR — free-form, abbreviations
- `Ленина 5 кв 3` · `ул Гагарина д 7 кв 14` · `мкр Северный д12 под3 кв 8`
- `пр-т Мира д12 под 2 кв 45` · `проспект Победы дом 33 корпус 2 подъезд 4 квартира 88`
- inverted: `квартира 45 дом 12 по Ленина` · с городом `москва ленина 5` (lowercase)
- house/apt are bare digits — collide with hard-negatives.

### DATE vs DOB
- DOB: `14.07.1989` · `03.11.1975` · `2018 г.р.` · `мне 80 лет` (age, borderline)
- Event DATE: `15 марта` · `01.02` (no year) · `на завтра` / `на пятницу` / `20го числа` / `к 18:00`
- Disambiguation is CONTEXTUAL: «дата рождения 14.07.1989» = DOB; «запись на 15 марта» = event.

### CARD
- `2202 2002 1234 5678` (Мир, пробелы) · `5469380012345678` (слитно) · `****3797` / `4276********1234` (masked)
- markers «карта/карту/на сбер/на тинёк» OR none. Length 16; Мир starts 22, Visa 4, MC 5.

### Structured IDs
- SNILS: `112-233-445 95` (canonical) · `11223344595` (слитно, no separators)
- INN: `771234567890` (физлицо 12 цифр) · 10 цифр (юрлицо)
- PASSP: `4509 123456` · `45 09 123456` · `4509123456` (слитно)
- OMS/полис: `7712345678901234` (ЕНП 16 digits) — collides with card length!
- VU: `77 АА 123456` (Cyrillic серия) · GRZ: `а123вс77` / `в456ор199` (lower/upper, 2-3 digit region)
- ACCT (р/с / л/с): `40817810099910004312` (20 digits) · `50 0123 4567` (ЖКХ л/с, varied)

### General noise (apply to ANY template)
- all-lowercase, no punctuation, `???`/`!!!`, emoji 🙏😡, RU/EN code-switch,
- typos («тлф», «электронку», «снилс без чёрточек»), filler text around the PII,
- multiple PII crammed with only spaces between them.

---

## PART 3 — Hard-negative number patterns (MUST NOT be masked)

These dominate marketplace/support traffic and are the #1 over-masking risk. Detector must
NOT treat them as PII (esp. not as phone/card/SNILS by length alone):

| Class | Example formats | Why it looks like PII | Disambiguator |
|---|---|---|---|
| **Трек-номер (междунар.)** | `RA123456789RU`, `RB987654321CN` | alphanumeric ID | 2 lat letters + 9 digits + 2 lat letters (UPU S10) |
| **Трек / РПО (Почта России)** | `80098765432109` (14 digits) | 14-digit run | exactly 14 digits, context «трек/отслеж» |
| **Номер заказа** | `52905115-0017`, `0288-1234-5678`, `81234567`, `0123456789` | 8-10 digits = collides w/ bare phone | context «заказ/order №»; often hyphen-grouped 4-4 or with prefix |
| **Артикул / SKU** | `167284593`, `WB-167284593` | 7-9 digits = collides w/ phone | context «артикул/SKU/арт» |
| **Сумма / цена** | `4990 р`, `1331`, `15000`, `199 руб`, `3200` | bare 3-5 digit number | currency token «р/руб/₽» or «сумма/списали/верните N» |
| **Дата/время** | `01.02`, `15 марта`, `20:02`, `18:00`, `2018` | digit groups | event-context, time has `:`, partial date no year |
| **Показания счётчика** | `04512`, `03317` | 5-digit codes | context «показания/счётчик/счетчик» |
| **Талон / номер очереди** | `778-2034` | hyphenated digits | context «талон/запись/очередь» |
| **Номер ПВЗ / магазина** | `№35417`, `ПВЗ 35417` | 5-digit | context «ПВЗ/пункт выдачи/магазин» |
| **ID обращения / тикет** | `RU-2026-0098123`, `обращение №...` | alphanumeric | context «обращение/тикет/заявка №» |
| **Промокод / купон** | `SALE2026`, `ПРОМО300` | alphanumeric | letters+digits, context «промокод/купон/скидка» |
| **Бонусы / кэшбэк / %** | `бонусов 320`, `кэшбэк 5%`, `320 баллов` | bare number | context «бонус/балл/кэшбэк/%» |
| **Модель / объём** | `iPhone 15 Pro 256gb`, `Xiaomi 13` | digits next to product | product-name context |
| **Чек / № документа** | `чек 00012345` | leading-zero digit run | context «чек/квитанция №» |

Borderline (mask per policy, document the call):
- **Лицевой счёт ЖКХ** (`1234567890`) — ties to a person → treat as ACCT PII, but length
  collides with order/phone; rely on «лицевой счёт / л/с» context.
- **IMEI** (`356789012345678`, 15 digits) — device ID, often regulated as PII; collides with
  SNILS-without-separators length-wise → disambiguate by «imei» token.
- **Возраст** («80 лет») — not DOB, but quasi-identifier.

Key collision summary (length alone is NOT a classifier):
- **10 digits** → bare phone OR order OR INN-юрлицо OR лицевой счёт.
- **16 digits** → card OR полис ОМС (ЕНП).
- **11 digits** → SNILS-без-дефисов OR 8+10-digit phone.
- **14 digits** → РПО трек (never PII).
- **15 digits** → IMEI (device) — visually close to SNILS-len.

---

## Sources

- Ozon refund complaint (verbatim user text, order/track/date phrasing): https://irecommend.ru/content/ozon-ne-vozvrashchaet-dengi
- Ozon "не пришёл заказ" guidance (claim fields: order №, date, sum): https://www.potrebinforms.ru/poleznaya_informaciya/pamyatki_potrebitelyam/ne_prishel_zakaz_s_ozon_chto_delat/
- Rospotrebnadzor virtual reception (Ozon refund thread): https://zpp.rospotrebnadzor.ru/Forum/Appeals/Details/37255
- Wildberries complaints aggregator (card last-4, addresses, date/time formats): https://www.sikayetvar.com/ru/wildberries-ru
- WB "не доставили / не возвращают" complaint (vc.ru): https://vc.ru/claim/247732-wildberries-ne-dostavili-zakaz-i-ne-vozvrashayut-za-nego-dengi
- WB support ignoring tickets (vc.ru): https://vc.ru/claim/1536776-podderzhka-wildberries-ignoriruet-moe-obrashenie
- Avito complaints aggregator: https://www.sikayetvar.com/ru/avito-ru
- Avito fraud / refund schemes (phone/card transfer phrasing): https://t-j.ru/avito-delivery-fraud/ · https://els24.com/article/317-kak-vernut-dengi-s-avito/
- ProDoctorov e-registry patient reviews (booking/cancel/transfer phrasing): https://prodoctorov.ru/saratov/lpu/22640-elektronnaya-registratura-saratova/otzivi/
- Beauty-salon online booking patterns: https://salonmap.ru/salony/salony-parikmakherskie
- T-Bank support chat / card-block phrasing: https://www.tbank.ru/bank/help/interfaces/bank-app/use/chat/ · https://www.banki.ru/services/responses/bank/response/11013340/
- ЖКХ complaint templates (address, лицевой счёт, показания fields): https://ppt.ru/art/jkh/kak-napisat-zayavlenie-v-upravlyayushchuyu-kompaniyu · https://t-j.ru/guide/zhaloba-na-uk/
- Yandex Taxi/Delivery "забыл телефон" support flow: https://taxi.yandex.ru/support/taxi-all-app/forgot.html · https://yandex.ru/support/delivery-profile/ru/express/troubleshooting
- Track-number vs order-number vs РПО format reference (UPU S10, 14-digit РПО): https://moyaposylka.ru/carriers/ozon · https://otveto.ru/blog/uchet-tovarov/ozon-treker-otslezhivanie-zakaza-trek-nomer-i-statusy-dostavki/
- RU phone number formats (8 / +7 / spaces / dashes / parens): https://en.wikipedia.org/wiki/Telephone_numbers_in_Russia · https://phonenumberformats.com/countries/ru-phone-number-format
- СНИЛС / ИНН / паспорт format reference: https://sfr.gov.ru/grazhdanam/personificirovannyj_uchet/snils/ · https://allo.tochka.com/inn
