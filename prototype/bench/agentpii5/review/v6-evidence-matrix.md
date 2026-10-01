# v6 evidence matrix — полный корпус 500/15 (D-070)

> Статус: **первый полный проход** (2026-09-28). Правит D-070 + верхний блок
> `docs/tz-agentpii6.md`. Пилот 180 и G2-pilot отменены как ворота. Матрица
> «источник→процесс→producer→consumer→сценарий→формы→негативы→приёмка» по всем
> 63 кандидатам реестра.
>
> **Разделение доказательств** (правило владельца 2026-09-28):
> - **OSS / API / v5** → схема инструмента и точные поля (producer/result,
>   consumer/argument). Классы: `primary` (справочник/первоисточник) /
>   `secondary` (официальная страница/справка) / `summary` (пересказ).
> - **датасеты** (`data-local/v6-sources/MANIFEST.md`) → язык, формы сообщений,
>   вариативность кейсов, опечатки. Значения из них НЕ переносятся.
> - Synthetic API запрещён (D-069). Тип без доказанной схемы — открытый вопрос.

## Источники, которыми заземляется матрица

| источник | что даёт |
|---|---|
| `docs/tz-agentpii6-registry.md` §2.3 | 45 предложенных инструментов `apis.json`: отрасль, вертикаль, формы, типы в арг./результате, эхо, происхождение |
| `docs/tz-agentpii6-registry.md` §2.4 | дыры инструментального слоя: 28 без инструмента, 16 только в результате, 2 только в аргументе |
| `research/2026-09-05-agent-scenario-coverage.md` §A | точные поля CRM/интеграций: Bitrix24 `crm.requisite` (`RQ_OGRNIP`, `RQ_INN`, `RQ_IDENT_DOC_SER/NUM/DATE/ISSUED_BY`), amoCRM `custom_fields_values[]`, RetailCRM `customers`, YClients, Unisender `importContacts`, DaData `clean/phone`, ЮKassa `receipts.customer`, T-Bank `Receipt.{Email,Phone}`, МТС Exolve `SendSMS` |
| `research/2026-09-07-oss-support-agents.md` §1.3 | официальные CRM-схемы (Zendesk, Intercom, Salesforce, HubSpot, МойСклад, SendGrid, Twilio): формы полей ФИО/адрес/телефон/даты |
| `prototype/bench/agentpii5/tools.py` + `briefs/tools.md` | 55 реализованных v5-инструментов с точными `result_pii`-путями и формами (`bank_client_find`, `form_parse`, `patient_find`, `referral_create`, `crm_*`, файлы, RAG) — evidence class `implemented-v5` |
| `data-local/v6-sources/MANIFEST.md` | 15 датасетов → отрасли и язык (медицина, обращения граждан, юрвопросы, отзывы WB/Яндекс.Карт, WildChat, edu) |

## Покрытие типов инструментом (по `apis.json` §2.3/§2.4, [ФАКТ])

**Обе стороны (arg→result) — 17:** `BANK_ACCOUNT`, `LOAN_CONTRACT_NUMBER`,
`OMS_ENP`, `ELN_NUMBER`, `LOYALTY_CARD_NUMBER`, `OSAGO_POLICY`, `VIN`,
`EPTS_NUMBER`, `DRIVER_LICENSE`, `ICCID`, `CADASTRAL_NUMBER`, `GIS_ZHKH_ELS`,
`EMPLOYEE_TAB_NUMBER`, `ARBITRAZH_CASE_NO`, `COURT_CASE_NO_SOU`, `DIPLOMA_NUMBER`,
`MIGRATION_CARD_NUMBER` (ДЕРЖИМ, OD-32).

**Только результат (нет OUT/tool_arg) — 16:** `INTL_PASSPORT`, `LOAN_UID`,
`OGRNIP`, `UIN`, `FSSP_IP_NO`, `EGRN_REG_NO`, `UTILITY_ACCOUNT`, `IMEI`, `IMSI`,
`IP_ADDRESS`, `SUBSCRIBER_ACCOUNT`, `PRESCRIPTION_NUMBER`, `STUDENT_ID_NUMBER`,
`PNR`, `METRICA_CLIENT_ID`, `LOGIN` (плюс `STS_NUMBER`/`CDP_CUSTOMER_ID` — только
аргумент). Нарушает V6T-08/K6-03; нужен consumer (или реклассификация по §2.4 п. 9).

**Без инструмента — 28:** `BIRTH_CERT`, `CIVIL_ACT_CERT`, `RESIDENCE_PERMIT`,
`TEMP_RESIDENCE_PERMIT`, `MILITARY_ID`, `IBAN`, `CREDIT_SUBJECT_CODE`,
`DMS_POLICY`, `KASKO_POLICY`, `INSURANCE_CLAIM_NUMBER`, `COURT_CASE_UID`,
`EXEC_DOC_NO`, `PTS_NUMBER`, `EGRN_REQUEST_NO`, `EPGU_APPLICATION_NO`, `ESIA_OID`,
`PLEDGE_NOTICE_NO`, `MAC`, `EID`, `MEDCARD_NUMBER`, `REFERRAL_NUMBER`,
`SCHOOL_CERT_NUMBER`, `RECORD_BOOK_NUMBER`, `EMPLOYMENT_CONTRACT_NUMBER`,
`ACCESS_PASS_NUMBER`, `E_TICKET_NUMBER`, `MOBILE_AD_ID`, `APP_DEVICE_ID`.

## Точные поля, которые закрывают часть «дыр» (research, не `apis.json`)

`apis.json` не исследовал несколько семейств как зеркала реальных API. Research
файлы их заземляют:

| семейство | точные поля (producer→consumer) | класс | закрывает типы |
|---|---|---|---|
| реквизиты продавца | Bitrix24 `crm.requisite`: `RQ_OGRNIP`, `RQ_INN`, `RQ_KPP`, `RQ_NAME`/`RQ_FIRST_NAME`/`RQ_LAST_NAME`, `RQ_IDENT_DOC`/`RQ_IDENT_DOC_SER`/`RQ_IDENT_DOC_NUM`/`RQ_IDENT_DOC_DATE`/`RQ_IDENT_DOC_ISSUED_BY` | primary (A) | `OGRNIP` (аргумент), паспорт серия/номер по полям, ИНН |
| KYC-анкета | тот же `crm.requisite` (`RQ_IDENT_DOC_*`) + `guest_arrival_notify` (миграционная карта, паспорт иностранца, виза) | primary | `INTL_PASSPORT`, `RESIDENCE_PERMIT` (как identity-document), `CREDIT_SUBJECT_CODE` (Bitrix24 `RQ_*` поля) |
| профиль CDP / импорт | Unisender `importContacts` (`fields`/`data`, ≤500/вызов, `{{...}}`-подстановки); DaData `clean/phone` (нормализация); ЮKassa `customer.{full_name,email,phone,inn}` | primary (A/B) | `CDP_CUSTOMER_ID` (аргумент импорта), `LOGIN` (через `lms_user_get`), `METRICA_CLIENT_ID` (через `web_visits_export`) |
| 54-ФЗ чек | ЮKassa `receipts.customer` / T-Bank `Receipt.{Email,Phone}` (одно из двух обязательно) | primary (A) | негатив/контекст для `BANK_ACCOUNT`, `EMAIL`, `PHONE` |
| CRM-запись | amoCRM `custom_fields_values[{field_id, values[{value, enum_code}]}]` — числовой `field_id` + ключ `value` | primary (B) | класс «значение под безымянным ключом» (D5/D6) — нужен инструмент `opaque_field` |
| массовый список | SendGrid `personalizations[]` (до 1000), HubSpot/amoCRM batch (до 50), Unisender `importContacts` | primary (A/B) | массив коррелированных ПД одного человека |

## Отрасли × датасеты (язык/формы, из MANIFEST)

| отрасль | датасеты (`data-local/v6-sources/`) |
|---|---|
| медицина | `medqa.csv`, `hfr.jsonl`, `mdl.parquet` (синтетика), `om.jsonl` (медицина) |
| банки/МФО/коллекторы | `don.csv`, `kursk.csv`, `ryaz.csv` (обращения), `q9111_0.parquet` (долги/страховка), `om.jsonl` (право) |
| госуслуги/ЖКХ | `don.csv`, `kursk.csv`, `ryaz.csv` (обращения граждан) |
| юруслуги/ФССП | `q9111_0.parquet`, `om.jsonl` (право), `don.csv` |
| ритейл/маркетинг/CDP | `wb09.zst` (отзывы WB), `geo_0.parquet` (Яндекс.Карт), `om.jsonl` |
| телеком | `geo_0.parquet` (IMEI, номера заказов), `wc0/wc10.parquet` (WildChat) |
| образование | `abit.parquet` (СГТУ), `om.jsonl` (вузы) |
| гостеприимство/логистика | `cod_ru_test.json` (бронь/жильё), `geo_0.parquet` |
| страхование/авто | `q9111_0.parquet`, `geo_0.parquet` (договоры) |
| HR/BI | `om.jsonl` (HR), нет живого регистра (D-068 цена) |

## Оставшиеся пробелы — конкретные, не сокращение scope

После полного прохода (`apis.json` + research + v5 + MANIFEST) не имеют
подтверждённой пары точных полей producer→consumer:

1. **Зеркало ФССП (OD-47).** `FSSP_IP_NO` и `COURT_CASE_NO_SOU` идут только из
   `fssp_proceedings_search` (результат), чей API закрыт (HTTP 410 на 2026-09-24,
   поля из статьи 2022). `EXEC_DOC_NO` — без инструмента. Нужен либо
   `documented-procedure` с читаемой схемой межведомственного обмена, либо тип
   ждёт.
2. **Документы личности без потребителя:** `BIRTH_CERT`, `CIVIL_ACT_CERT`,
   `MILITARY_ID` — в Bitrix24 `RQ_IDENT_DOC_*` типизируются как «документ», но
   конкретного КЛЮЧА/пути для серии/номера свидетельства или военного билета в
   прочитанных справочниках нет.
3. **Медицинские номера:** `MEDCARD_NUMBER`, `REFERRAL_NUMBER`, `DMS_POLICY` —
   в v5 есть `patient_find`/`referral_create`, но номер медкарты/направления и
   полис ДМС как отдельные пути результата не заземлены. `eln_get` заземляет
   только `ELN_NUMBER`.
4. **Сервисная заявка устройства:** `IMEI` есть только как результат
   `subscriber_profile_get`; схемы «сервисной заявки с IMEI» как инструмента в
   прочитанных источниках нет.
5. **ДЕРЖИМ/слабое основание:** `IBAN`, `COURT_CASE_UID`, `MAC`, `EID`,
   `ESIA_OID`, `PTS_NUMBER`, `SCHOOL_CERT_NUMBER`, `RECORD_BOOK_NUMBER`,
   `EMPLOYMENT_CONTRACT_NUMBER`, `ACCESS_PASS_NUMBER`, `E_TICKET_NUMBER`,
   `MOBILE_AD_ID`, `APP_DEVICE_ID`, `EGRN_REQUEST_NO`, `EPGU_APPLICATION_NO`,
   `PLEDGE_NOTICE_NO`, `KASKO_POLICY`, `INSURANCE_CLAIM_NUMBER`,
   `TEMP_RESIDENCE_PERMIT` — первоисточника схемы поля нет в прочитанных файлах.

Эти пробелы — вход для отдельных вопросов владельцу (каждый со своим списком
отсутствующих полей), а не основание для synthetic API.

## Следующий шаг (после этой матрицы)

1. Владелец подтверждает/дополняет источники для пробелов 1–5.
2. Фаза 1: открыть реестр типов v5 (`pii_types.py` + производные, W0-R1…R13),
   без v6-кейсов; G1 — старые таблицы/порядок/digest/perfect/nano byte-identical.
3. Компоненты по зависимости §12.2; затем корпус 500/15.
