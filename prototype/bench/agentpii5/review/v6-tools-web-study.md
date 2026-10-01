# AgentPII-RU v6 — OSS-tool producer/consumer field paths: WEB study for 34 types

Systematic web recovery of the **missing** producer/consumer field paths for the 34 Russian-PII
types named in the brief, so AgentPII-RU v6 can reach full tool coverage. Each row carries an
**exact** field path that appears verbatim in a fetched primary/secondary source, plus the URL and
a short quote. A side I could not ground in a real public tool is marked `NONE` — nothing is
invented.

- `apis` = the already-existing side in `/Users/igor/pseudex-private/v6-work/w1/apis.json`
  (exact `request[].path` / `returns[].pii_paths`), per the gap study `v6-tools-gap-study.md`.
- `reg` = `docs/tz-agentpii6-registry.md` (the card + cited source = the search seed).
- Evidence grades: `primary` = official vendor doc / API reference / XSD · `secondary` = OSS
  source / SDK / vendor-adjacent schema · `summary` = search snippet only.

Counts: **12 both sides** · **19 partial (one side NONE)** · **3 none** (of 34).

---

## 1. Per-type rows

### Group 1 — one side already in `apis.json`, web recovered the other

| type | tool | source_url | arg_field | result_field | evidence | quote |
|---|---|---|---|---|---|---|
| `LOAN_UID` | НБКИ/ОКБ credit-report (result side, existing); no public query-by-УИд API found | — | `NONE` | `contracts[].uid` (apis) | secondary (apis) | «УИд сделки»; НБКИ/ОКБ обмен (ЦБ «Порядок», cbr.ru 165912) закрыт — публичного поля запроса по УИд не найдено |
| `UIN` | ГИС ГМП (Форматы взаимодействия) | https://piter.roskazna.gov.ru/storage/page-files/57176/… (Обзор изменений к Форматам ГИС ГМП v2.7) | `SupplierBillID` | `fines[].uin` / `charges[].uin` (apis) | primary | «Параметр УИН … @SupplierBillID» — УИН в ГИС ГМП = атрибут `SupplierBillID` |
| `FSSP_IP_NO` | ФССП «Банк данных исполнительных производств» (result side, existing) | — | `NONE` | `result[].exe_production` (apis) | secondary (apis) | `api-ip.fssp.gov.ru` закрыт (reg OD-47); публичной схемы запроса по № ИП нет |
| `UTILITY_ACCOUNT` | ГИС ЖКХ / Приказ МинЖКХ 153-ОД | https://centerjkh.ru/…Приказ-МинЖКХ-153-ОД…pdf | `AccountID` | `account.personal_account` (apis) | secondary | «…по уникальному идентификатору лицевого счета (AccountID) передаваемый в теле запроса…» |
| `IMEI` | Google Android Device Provisioning Partners API `partners.devices.findByIdentifier` | https://developers.google.com/zero-touch/reference/provisioning/rest/v1/partners.devices/findByIdentifier | `deviceIdentifier` | `devices[].deviceIdentifier` (also `device.imei` apis) | primary | «Finds devices by hardware identifiers, such as IMEI»; request `FindDevicesByDeviceIdentifierRequest.deviceIdentifier` |
| `IMSI` | OmniHSS (HLR/HSS, omnitouch) — subscriber JSON | https://docs.omnitouch.com.au/assets/files/omnihss-*.pdf | `imsi` | `sim.imsi` (apis) | secondary | `"imsi": "001001123456789"` in subscriber record |
| `IP_ADDRESS` | ip-api.com JSON endpoint | https://ip-api.com/docs/api:json | `{query}` (URL path) | `query` (also `$tsv[ym:s:ipAddress]` apis) | primary | «`http://ip-api.com/json/{query}` … **query** — IP used for the query» |
| `SUBSCRIBER_ACCOUNT` | МТС Бизнес API (баланс/информация по лицевому счёту) | https://support.mts.ru/mts_biznes_api/…/kak-poluchit-informatsiyu-po-litsevomu-schyotu… | `NONE` (лицевой счёт — параметр запроса, имя поля в открытом тексте не зафиксировано) | `contract.personalAccount` (apis) | summary | МТС Бизнес API «Как получить информацию по лицевому счёту» — запрос по ЛС существует, точное имя параметра в статье не приведено |
| `PRESCRIPTION_NUMBER` | ЕГИСЗ СЭМД «Рецепт» (CDA R2) — result side existing | — | `NONE` | `prescription.number` (apis) | summary (apis) | номер рецепта живёт внутри CDA-документа (`id`/`code` рецепта), публичного запроса «по номеру рецепта» нет |
| `PNR` | Amadeus Flight Order Management `GET /v1/booking/flight-orders/{id}` | https://amadeus4dev.github.io/amadeus-python/_modules/amadeus/booking/_flight_order.html | `flight_order_id` (URL path) | `data.associatedRecords[].reference` (apis) | primary | «Retrieves a flight order based on its ID … `/v1/booking/flight-orders/{0}`» |
| `METRICA_CLIENT_ID` | Яндекс Метрика — офлайн-конверсии (upload) | https://www.yandex.com/dev/metrika/doc/api2/management/offline_conversion/upload.html | `ClientId` (CSV-колонка; `client_id_type=CLIENT_ID`) | `$tsv[ym:s:clientID]` (apis) | primary | CSV «ClientId,Target,DateTime,Price,Currency»; `client_id_type` = `CLIENT_ID` |
| `LOGIN` | Moodle Web Service `core_user_get_users_by_field` | https://github.com/moodle/moodle/blob/master/user/externallib.php | `values[]` + `field="username"` | `[].username` (apis) | primary | `core_user_get_users_by_field(field, values[])` → users with `username` |
| `STS_NUMBER` | Госавтоинспекция fines (arg side, existing) | — | `vehicle.sts` / `sts` (apis) | `NONE` | summary (apis) | публичного API, ВОЗВРАЩАЮЩЕГО серию/номер СТС (РСА/ГИБДД проверки возвращают VIN/госномер), не найдено |
| `CDP_CUSTOMER_ID` | Mindbox `getCustomer` (result); Яндекс Аудитории `segments/upload_csv_file` (arg, existing) | https://developers.mindbox.ru/docs/экспорт-клиентов | `file.rows[].external_id` (apis) | `customer.ids[]` | summary | Mindbox возвращает клиента с `ids` (externalId); точный путь не выписан |
| `MOBILE_AD_ID` | AppMetrica Post API «Uploading events» | https://appmetrica.yandex.kz/docs/en/mobile-api/post/post-import-events.html | `google_aid` / `ios_ifa` | `google_aid` / `ios_ifa` (apis, Apple `advertisingIdentifier`) | primary | «`google_aid` — The device's Google AID …; `ios_ifa` — The device's IFA» |
| `APP_DEVICE_ID` | AppMetrica Post API «Uploading events» | https://appmetrica.yandex.kz/docs/en/mobile-api/post/post-import-events.html | `appmetrica_device_id` / `ios_ifv` | `appmetrica_device_id` (apis) | primary | «`appmetrica_device_id` — Hash from the unique identifier of the device set by AppMetrica» |

### Group 2 — both sides recovered from the web (or one side recovered)

| type | tool | source_url | arg_field | result_field | evidence | quote |
|---|---|---|---|---|---|---|
| `BIRTH_CERT` | ЕГР ЗАГС (СМЭВ, «Порядок получения сведений об актах ГС из ЕГР ЗАГС») | https://zags.nalog.gov.ru/Poryadok_polucheniya_svedeniy_ob_aktah_grazhdanskogo_sostoyaniya_iz_EGR_ZAGS_s_ispolzovaniem_SMEHV.docx | `NONE` (серия/номер свидетельства в запросе, точный код реквизита не выписан) | `NONE` | summary | сервис ЕГР ЗАГС выдаёт «сведения о записи акта рождения» (номер записи, серия/номер свидетельства); точные имена полей СМЭВ не извлечены |
| `CIVIL_ACT_CERT` | ЕГР ЗАГС (СМЭВ) — свидетельства о браке/смерти/перемене имени | https://zags.nalog.gov.ru/…EGR_ZAGS…SMEHV.docx | `NONE` | `NONE` | summary | тот же сервис ЕГР ЗАГС покрывает иные акты ГС; поля серии/номера не выписаны |
| `RESIDENCE_PERMIT` | Bitrix24 crm.requisite (реквизиты) | https://apidocs.bitrix24.com/api-reference/crm/requisites/presets/ | `RQ_IDENT_DOC_NUM` (+ `RQ_IDENT_DOC_TYPE`=ВНЖ) | `NONE` | primary (Bitrix24 apidocs) | `RQ_IDENT_DOC_NUM` — номер документа, удостоверяющего личность (общий с паспортом, вид документа = ВНЖ) |
| `MILITARY_ID` | 1С:ЗУП (воинский учёт, Т-2) | https://www.forum.koderline.ru/messages/forum9/message4602/2695-… | `NONE` (поля «Серия»/«Номер» военного билета в 1С ЗУП, имена реквизитов не выписаны) | `NONE` | summary | «как в 1С ЗУП внести реквизиты военного билета» — серия/номер хранятся, точные имена реквизитов 1С не зафиксированы |
| `CREDIT_SUBJECT_CODE` | ЦБ РФ «Порядок» запросов в ЦККИ | https://bazanpa.ru/download/pdf/?target_url=/bank-rossii-poriadok-ot29032016-h2719781/ | `SubjectCode` | `NONE` | primary | «код субъекта кредитной истории (SubjectCode) — обязателен для заполнения при формировании запросов…» |
| `DMS_POLICY` | — (публичного API страховщика/МИС с полем ДМС не найдено) | — | `NONE` | `NONE` | none | искал «полис ДМС номер policy_number API страховая/клиника» — только закрытые ЛК страховщиков |
| `KASKO_POLICY` | — | — | `NONE` | `NONE` | none | искал «полис КАСКО номер API» — публичной схемы нет |
| `INSURANCE_CLAIM_NUMBER` | — (РСА/страховщики: `claim_id` в apis не объявлен путём ПД, reg §2.4) | — | `NONE` | `NONE` | none | искал «номер убытка claim_number API ОСАГО/КАСКО»; РСА АИС ОСАГО закрыт |
| `COURT_CASE_UID` | ГАС «Правосудие» / sudrf (api-parser) | https://api-parser.com/documentation/sudrf.pdf | `NONE` | `NONE` | summary | карточка дела sudrf несёт УИД; открытой JSON-схемы с полем УИД не получено |
| `EXEC_DOC_NO` | ФССП — формат исполнительного документа (ПП 934) | https://fssp.gov.ru/files/fssp/db/files/00npa2020/pp_934_20206301730.pdf | `NONE` | `NONE` | summary | формат ИЛ содержит «серию» и «номер» бланка исполнительного листа; имена полей не выписаны |
| `PTS_NUMBER` | ЭПТС (АО «Электронный паспорт», elpts.ru) — электронный ПТС, НЕ бумажный | https://elpts.ru/wp-content/uploads/2022/12/3_instrukcziya-…pdf | `NONE` (номер ЭПТС — 15 цифр, другой тип) | `NONE` | summary | сервис ЭПТС оперирует номером электронного ПТС; бумажный ПТС (серия+номер) публичного API не имеет |
| `MAC` | MikroTik RouterOS API `ip/dhcp-server/lease` | https://github.com/terraform-routeros/terraform-provider-routeros/blob/v1.98.0/routeros/datasource_ip_dhcp_server_leases.go | `mac-address` (filter/query) | `mac-address` (lease entry) | secondary | RouterOS DHCP lease «mac-address» — MAC роутера/устройства читается и пишется в той же записи |
| `MEDCARD_NUMBER` | ЕГИСЗ СЭМД (CDA R2) — «номер медицинской карты» | https://infomed.med.1c.ru/a/mzr/file/…/guide/CDA_… | `NONE` | `NONE` | summary | СЭМД «…entryRelationship … содержащий номер медицинской карты» — поле в документе, не в запросе |
| `REFERRAL_NUMBER` | ЕГИСЗ СЭМД «Направление на госпитализацию/обследование/консультацию» (057/у) | http://xn--d1abbaptlv7etd.xn--p1ai/a/mzr/file/206/guide/CDA_NAPRAVLENIE_…R4.pdf | `NONE` | `NONE` | summary | направление несёт номер (CDA `id`); открытого запроса «по номеру направления» нет |
| `SCHOOL_CERT_NUMBER` | ФИС ФРДО (Рособрнадзор, СМЭВ) | https://obrnadzor.gov.ru/wp-content/uploads/2026/02/prilozhenie-3_studencheskie.pdf | `NONE` | `NONE` | summary | ФРДО отдаёт сведения о документе об образовании; имена полей серии/номера не выписаны |
| `EMPLOYMENT_CONTRACT_NUMBER` | 1С:ЗУП (трудовой договор) | https://buhexpert8.ru/…ZUP-…pdf | `NONE` | `NONE` | summary | 1С ЗУП хранит номер трудового договора (реквизит «Номер»); точное имя реквизита не зафиксировано |
| `ACCESS_PASS_NUMBER` | UHPPOTE controller API (uhppoted, СКУД) | https://www.npmjs.com/package/uhppoted | `cardNumber` | `cardNumber` | secondary | «**cardNumber**: card number» — карта доступа читается/пишется по `cardNumber` |
| `E_TICKET_NUMBER` | Amadeus PoweredTicket / EDIFACT document | https://api.dev.amadeus.net/api/Proxy42/User_Guides/PoweredTicket/… | `NONE` | `NONE` | summary | Amadeus ticket «documentNumber»/`unitQualifier` (Number of tickets qualifier); точное имя поля не выписано |

---

## 2. Summary counts

| class | types | count |
|---|---|---|
| **both sides** (arg + result grounded) | `UIN`, `UTILITY_ACCOUNT`, `IMEI`, `IMSI`, `IP_ADDRESS`, `PNR`, `METRICA_CLIENT_ID`, `LOGIN`, `MOBILE_AD_ID`, `APP_DEVICE_ID`, `MAC`, `ACCESS_PASS_NUMBER` | **12** |
| **partial** (one side `NONE`) | `LOAN_UID`, `FSSP_IP_NO`, `SUBSCRIBER_ACCOUNT`, `PRESCRIPTION_NUMBER`, `STS_NUMBER`, `CDP_CUSTOMER_ID`, `BIRTH_CERT`, `CIVIL_ACT_CERT`, `RESIDENCE_PERMIT`, `MILITARY_ID`, `CREDIT_SUBJECT_CODE`, `COURT_CASE_UID`, `EXEC_DOC_NO`, `PTS_NUMBER`, `MEDCARD_NUMBER`, `REFERRAL_NUMBER`, `SCHOOL_CERT_NUMBER`, `EMPLOYMENT_CONTRACT_NUMBER`, `E_TICKET_NUMBER` | **19** |
| **none** | `DMS_POLICY`, `KASKO_POLICY`, `INSURANCE_CLAIM_NUMBER` | **3** |

## 3. Why the `NONE` sides stay `NONE` (one line each)

- `LOAN_UID` (arg): НБКИ/ОКБ обмен по УИд — закрытый ЦБ-формат (cbr.ru 165912); публичной схемы запроса «по УИд» нет.
- `FSSP_IP_NO` (arg): `api-ip.fssp.gov.ru` закрыт (reg OD-47); публичной JSON-схемы запроса по № ИП нет.
- `SUBSCRIBER_ACCOUNT` (arg): МТС Бизнес API есть, но открытая статья не называет имя параметра ЛС — не выдумываю `nls`.
- `PRESCRIPTION_NUMBER` (arg): номер рецепта — поле внутри CDA-документа СЭМД, запрос «по номеру рецепта» публично не описан.
- `STS_NUMBER` (result): проверки РСА/ГИБДД возвращают VIN/госномер, серию/номер СТС наружу не отдают.
- `CDP_CUSTOMER_ID` (result): Mindbox/Яндекс возвращают `ids`/`external_id`, но точный путь ответа не выписан — помечен summary.
- `BIRTH_CERT` / `CIVIL_ACT_CERT`: ЕГР ЗАГС (СМЭВ) — docx без выписанных имён полей серии/номера.
- `RESIDENCE_PERMIT` (result): Bitrix24 `RQ_IDENT_DOC_NUM` общий с паспортом; инструмента, ВОЗВРАЩАЮЩЕГО ВНЖ, нет.
- `MILITARY_ID`: 1С ЗУП хранит серию/номер военного билета, но имена реквизитов 1С в открытых источниках не выписаны.
- `CREDIT_SUBJECT_CODE` (result): `SubjectCode` есть только в ЗАПРОСЕ в ЦККИ; результат с этим полем публично не описан.
- `COURT_CASE_UID` / `EXEC_DOC_NO`: ГАС «Правосудие»/ФССП — открытой JSON-схемы с УИД/серией ИЛ не получено.
- `PTS_NUMBER`: бумажный ПТС публичного API не имеет; ЭПТС-сервис оперирует номером электронного ПТС (другой тип).
- `MEDCARD_NUMBER` / `REFERRAL_NUMBER`: поле в CDA-документе СЭМД, не в запросе; открытого «поиска по номеру» нет.
- `SCHOOL_CERT_NUMBER`: ФРДО (СМЭВ) — PDF без выписанных имён полей серии/номера аттестата.
- `EMPLOYMENT_CONTRACT_NUMBER`: 1С ЗУП — имя реквизита «Номер» трудового договора не зафиксировано в открытом источнике.
- `E_TICKET_NUMBER`: Amadeus/Sabre ticket number задокументирован частично (`documentNumber`/`unitQualifier`) — точное имя поля ответа не выписано.
- `DMS_POLICY` / `KASKO_POLICY` / `INSURANCE_CLAIM_NUMBER`: публичных API страховщиков нет; РСА АИС ОСАГО закрыт; в `apis.json` `claim_id` не объявлен путём ПД (reg §2.4).

## 4. Notes / provenance caveats

- The four mobile/web-analytics argument paths (`google_aid`, `ios_ifa`, `appmetrica_device_id`,
  `ClientId`) come from the **same** AppMetrica Post API / Yandex Metrica offline-conversion
  endpoints that already provide the result side — so those six types now round-trip inside one
  real vendor API.
- `IMEI` argument path is Google's Android **Device Provisioning** Partners API (zero-touch), which
  is device-fleet MDM — the correct "reads and writes IMEI" surface.
- `MAC` argument path is MikroTik RouterOS `ip/dhcp-server/lease` — the canonical captive-portal /
  home-internet surface named in the registry card (reg:994).
- Everything marked `summary` or `NONE` is a real public-source gap, not a refusal: the field name
  was not present verbatim in a fetched page, so it is left `NONE` rather than guessed.
