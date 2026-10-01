# AgentPII-RU v6 — OSS-tool producer/consumer fields: gap study for 41 under-covered types

Systematic evidence recovery. Scope: the 41 registry types named in the brief. Sources read in
order and cited as:

- `reg` = `docs/tz-agentpii6-registry.md` (Приложение А; card lines + §2.3/§2.4 tool table)
- `apis` = `w1/apis.json` (45 tools, exact `request[]`/`returns[].pii_paths`)
- `tA/tB/tC` = `w1/types-A.json` / `types-B.json` / `types-C.json` (per-type `field_keys` with
  `verified_in_primary_source` vs `proposed_not_verified`)
- `scov` = `research/2026-09-05-agent-scenario-coverage.md` §A (OSS field shapes)
- `oss` = `research/2026-09-07-oss-support-agents.md` §1.3 (vendor field-shape table)
- `MAN` = `data-local/v6-sources/MANIFEST.md` (live registers; language only, no tool fields)

**Rules applied.** A field path is "exact" only if it appears **verbatim** in one of the above
(either an `apis.json` `request[]`/`returns[]` path, or a `verified_in_primary_source` / primary-
quoted field name in `tA/tB/tC` / `reg` / `scov`). Everything else is `—` and the type goes to
list B. No field paths are invented here.

**Counts:** 23 types have exact local fields (list A) · 18 need web search (list B).

---

## 1. Per-type rows

Columns: `surface` (Поверхности, paraphrased, cite = card line) · `tool` (concrete OSS/API tool or
«нет в спеках») · `arg_fields` / `result_fields` (exact verbatim paths, else `—`) · `evidence`
(`primary` = official doc/schema quoted · `secondary` = OSS source/SDK/example · `summary` = search
snippet · `none`) · `needs_web_search`.

### Group A — identity / finance / insurance

| type | surface | tool | arg_fields | result_fields | evidence | needs_web_search |
|---|---|---|---|---|---|---|
| `BIRTH_CERT` | bank child account/deposit, child DMS/OMS policy, school/kindergarten, Госуслуги (reg:59) | «нет в спеках» | — | — | none (`doc_type=03` ФНС marked UNVERIFIED, reg:63) | **yes** |
| `CIVIL_ACT_CERT` | death-benefit payout, bank surname change, notary/inheritance (reg:78) | «нет в спеках» | — | — | none | **yes** |
| `RESIDENCE_PERMIT` | bank/МФО non-resident KYC «ВНЖ серия 82…», employer, hotel migration register (reg:98) | «нет в спеках» (Bitrix24 `RQ_IDENT_DOC_NUM` is generic, shared with passport) | — | — | summary (reg:102 «Bitrix24 с видом документа ВНЖ») | **yes** |
| `MILITARY_ID` | bank/МФО 18–27 questionnaire, HR воинский учёт in 1С ЗУП / Т-2 (reg:135) | «нет в спеках» (1С ЗУП named, no field path) | — | — | none | **yes** |
| `IBAN` | inbound SWIFT «IBAN получателя RU…», marketplace/freelance payout, Bitrix24 bankdetail (reg:225) | Bitrix24 crm.requisite (bank detail) | — | — (consumer field only) | primary — `RQ_IBAN` verified on apidocs.bitrix24.ru (reg:228, tA `field_keys`) | **no** |
| `LOAN_UID` | credit-contract individual conditions (УИд), НБКИ/ОКБ report «УИд сделки», cession register (reg:284) | НБКИ/ОКБ credit report; collector/MFO CRM | — | `contracts[].uid` (apis:902, `credit_report_request`); `loan.uid` (apis:1099, `debtor_card_get`) | secondary (`credit_report_request`), summary (`debtor_card_get`) | **no** |
| `CREDIT_SUBJECT_CODE` | loan application, ЦККИ request via bank/Госуслуги, bank chat dictation (reg:333) | «нет в спеках» | — | — | none | **yes** |
| `DMS_POLICY` | clinic booking by ДМС, insurer guarantee letter, HR DMS roster (reg:397) | «нет в спеках» | — | — | none | **yes** |
| `KASKO_POLICY` | claim «по полису КАСКО №…», autoloan collateral, repair referral (reg:438) | «нет в спеках» | — | — | none | **yes** |
| `INSURANCE_CLAIM_NUMBER` | SMS «по убытку №…», settlement chat, ombudsman appeal (reg:452) | «нет в спеках» (`claim_id` is OUR_FICTION and NOT declared as PII path, reg:1747) | — | — | none (reg:464–465 flags the `insurance_claim_create.claim_id` gap) | **yes** |
| `UIN` | ГИБДД/ФНС/ФССП charge, платежка field 22 «Код», «оплата по УИН» (reg:572) | ГИС ГМП (Госавтоинспекция fines; ГИС ГМП charges) | — | `fines[].uin` (apis:2482, `traffic_fines_check`); `charges[].uin` (apis:4262, `budget_charges_find`) | summary | **no** |
| `COURT_CASE_UID` | court act header «УИД…», sudrf card, судебный приказ/исполлист (reg:609) | «нет в спеках» | — | — | none | **yes** |
| `ARBITRAZH_CASE_NO` | kad.arbitr.ru card, citizen bankruptcy (ЕФРСБ), litigation CRM (reg:630) | kad.arbitr.ru (Картотека арбитражных дел) | `case_number` (apis:3786) | `cases[].number` (apis:3804) | summary | **no** |
| `COURT_CASE_NO_SOU` | судебный приказ (collectors/ЖКХ), повестка, act header, исполлист «дело №» (reg:650) | ФССП bank-of-proceedings; ГАС «Правосудие»/sudrf | `case_number` (apis:3960, `court_document_fetch`) | `result[].details` (apis:1021, `fssp_proceedings_search`) | primary/secondary (fssp), synthetic (court_document_fetch) | **no** |
| `FSSP_IP_NO` | возбуждение ИП, bank arrest order, HR garnishment, collectors CRM (reg:667) | ФССП «Банк данных исполнительных производств» (api-ip.fssp.gov.ru) | — | `result[].exe_production` (apis:1020) | primary/secondary (reg:1767–1768 notes API closed → `synthetic`) | **no** |
| `EXEC_DOC_NO` | исполлист in collector/bank file, заявление о возбуждении ИП (reg:685) | «нет в спеках» | — | — | none | **yes** |
| `STS_NUMBER` | ОСАГО application, fines search by СТС, car-service CRM, ДКП/leasing (reg:702) | ОСАГО claim (ПВУ); Госавтоинспекция fines | `vehicle.sts` (apis:2352, `insurance_claim_create`); `sts` (apis:2464, `traffic_fines_check`) | — | summary | **no** |
| `PTS_NUMBER` | autoloan collateral register, ДКП, ОСАГО/КАСКО, classifieds «ПТС оригинал» (reg:722) | «нет в спеках» | — | — | none | **yes** |
| `DRIVER_LICENSE` | ОСАГО driver list, carsharing/taxi onboarding, HR drivers, fines by ВУ (reg:743) | Госавтоинспекция/Госуслуги «Проверка водителя» | `license_number` (apis:2617) | `license` (apis:2643) | summary | **no** |
| `UTILITY_ACCOUNT` | квитанция/ЕПД «Лицевой счёт», energy/water/gas app & call-centre, autopay, судебный приказ (reg:836) | ГИС ЖКХ (dom.gosuslugi.ru) | — | `account.personal_account` (apis:3090) | summary | **no** |
| `ESIA_OID` | bank/МФО KYC after «вход через Госуслуги», ЕСИА-integrated logs, admissions (reg:869) | ЕСИА REST API (Госуслуги) | `prn_oid` (REST path `rs/prns/{prn_oid}/roles`, reg:867) | `personOid` (reg:866) | primary — «"personOid" — идентификатор зарегистрированной учётной записи» (reg:866, tB) | **no** |

### Group C — telecom / medical / education / HR / hospitality / marketing-CD

| type | surface | tool | arg_fields | result_fields | evidence | needs_web_search |
|---|---|---|---|---|---|---|
| `IMEI` | operator customer-care (stolen ME), retail warranty/repair, gadget insurance, antifraud (reg:918) | BSS оператора (TM Forum TMF632 Party Management) | — | `device.imei` (apis:2724, `subscriber_profile_get`) | secondary | **no** |
| `IMSI` | core/BSS tickets, HLR/HSS exports, SIM-swap, roaming/billing (reg:978) | BSS оператора (TMF632) | — | `sim.imsi` (apis:2723) | secondary | **no** |
| `MAC` | home-internet «продиктуйте MAC роутера», captive-portal logs, corporate NAC/Wi-Fi (reg:994) | «нет в спеках» | — | — | none (engine already detects MAC; no OSS field name) | **yes** |
| `IP_ADDRESS` | antifraud logs «вход с нового IP», web-analytics exports, ISP static IP (reg:1011) | Яндекс Метрика Logs API | — | `$tsv[ym:s:ipAddress]` (apis:5021, `web_visits_export`) | primary | **no** |
| `SUBSCRIBER_ACCOUNT` | operator payment forms «лицевой счёт», support chat, bank bill-pay templates (reg:1037) | BSS оператора (TMF632) | — | `contract.personalAccount` (apis:2720) | secondary | **no** |
| `MEDCARD_NUMBER` | МИС patient-card lookup, prescriptions (1094н), lab results (reg:1074) | «нет в спеках» — `remd_documents_search.items[].document_number` is MISLABELED (it is the ЭМД document number, not the medcard — reg:1745, reg:1085) | — | — | none (secondary mislabel, not a medcard field) | **yes** |
| `ELN_NUMBER` | HR/1С:ЗУП ЭЛН import, clinic → patient «Ваш ЭЛН №», СФР status (reg:1102) | СФР «Система учёта ЭЛН» — FileOperationsLnService `getLNData` | `ln_code` (apis:1169) | `data.row.lnCode` (apis:1199) | primary — `lnCode`, `LN_CODE`, `prevLnCode`, `nextLnCode` verified in СФР spec v2.3 (reg:1105) | **no** |
| `PRESCRIPTION_NUMBER` | pharmacy e-recipe reservation, clinic re-issue of льготный рецепт, pharmacy CRM (reg:1123) | МИС → ЕГИСЗ СЭМД «Рецепт» | — | `prescription.number` (apis:1527, `e_prescription_create`) | summary | **no** |
| `REFERRAL_NUMBER` | lab/MRI booking «номер направления», ДМС guarantee letter, hospitalisation queue (reg:1138) | «нет в спеках» | — | — | none | **yes** |
| `SCHOOL_CERT_NUMBER` | college/university admission, HR young employees, Госуслуги/ФРДО duplicates (reg:1184) | «нет в спеках» | — | — | none | **yes** |
| `STUDENT_ID_NUMBER` | student discounts, university LMS/deans' office, hostel registration (reg:1198) | Moodle Web Services `core_user_get_users_by_field` | `values` (apis:4520) | `[].idnumber` (apis:4540) | primary (Moodle; `idnumber` also reg:1201) | **no** |
| `EMPLOYMENT_CONTRACT_NUMBER` | КЭДО contract signing, payroll disputes, employment verification letters (reg:1240) | «нет в спеках» | — | — | none | **yes** |
| `ACCESS_PASS_NUMBER` | СКУД logs in BI, visitor pass ordering, HR offboarding (reg:1256) | «нет в спеках» | — | — | none | **yes** |
| `PNR` | airline/OTA support «номер бронирования» + surname, hotel confirmations, travel BI (reg:1273) | Amadeus Self-Service Flight Order Management (GDS) | — | `data.associatedRecords[].reference` (apis:3422) | primary (Amadeus swagger example `2ZYVAL`) | **no** |
| `E_TICKET_NUMBER` | airline refund/exchange, travel-policy BI, OTA support (reg:1289) | «нет в спеках» | — | — | none | **yes** |
| `MOBILE_AD_ID` | mobile attribution exports (AppMetrica `google_aid`/`ios_ifa`), CDP retargeting, antifraud (reg:1354) | AppMetrica Logs API; Apple `advertisingIdentifier` | — | `google_aid`, `ios_ifa` (AppMetrica); `advertisingIdentifier` (Apple) — verified (reg:1356, tC) | primary | **no** |
| `APP_DEVICE_ID` | AppMetrica Logs/Post exports, CDP push targeting, support «пришлите device id» (reg:1374) | AppMetrica Logs API «installations» | — | `appmetrica_device_id` (reg:1377, tC verified) | primary | **no** |
| `METRICA_CLIENT_ID` | offline-conversion upload (ClientId column), CRM↔Метрика stitching, BI session joins (reg:1393) | Яндекс Метрика Logs API | — | `$tsv[ym:s:clientID]` (apis:5020); `ClientId`, `_ym_uid` verified (reg:1395) | primary | **no** |
| `CDP_CUSTOMER_ID` | CDP segment exports / audience APIs, BI by customer_id, support «найти клиента по ID» (reg:1408) | Яндекс Аудитории API (`segments/upload_csv_file`) | `file.rows[].external_id` (apis:4811) | — | summary (label `CLIENT_ID`; path only in arg) | **no** |
| `LOGIN` | account-recovery support, LMS/intranet accounts, BI audit logs (reg:1424) | Moodle Web Services `core_user_get_users_by_field` | — | `[].username` (apis:4542) | primary (Moodle `username`, example `gromova.m`) | **no** |

---

## 2. List A — exact local fields (ready to implement a tool now) · 23 types

| type | tool | exact field(s) · source:line |
|---|---|---|
| `IBAN` | Bitrix24 crm.requisite | `RQ_IBAN` — reg:228 (verified on apidocs.bitrix24.ru) |
| `LOAN_UID` | НБКИ/ОКБ credit report; collector CRM | `contracts[].uid` — apis:902; `loan.uid` — apis:1099 |
| `UIN` | ГИС ГМП (fines / charges) | `fines[].uin` — apis:2482; `charges[].uin` — apis:4262 |
| `ARBITRAZH_CASE_NO` | kad.arbitr.ru | arg `case_number` — apis:3786; result `cases[].number` — apis:3804 |
| `COURT_CASE_NO_SOU` | ФССП; ГАС Правосудие | result `result[].details` — apis:1021; arg `case_number` — apis:3960 |
| `FSSP_IP_NO` | ФССП bank-of-proceedings | result `result[].exe_production` — apis:1020 |
| `STS_NUMBER` | ОСАГО claim; Госавтоинспекция fines | arg `vehicle.sts` — apis:2352; arg `sts` — apis:2464 |
| `DRIVER_LICENSE` | Госавтоинспекция/Госуслуги | arg `license_number` — apis:2617; result `license` — apis:2643 |
| `UTILITY_ACCOUNT` | ГИС ЖКХ | result `account.personal_account` — apis:3090 |
| `ESIA_OID` | ЕСИА REST (Госуслуги) | `personOid` — reg:866; arg `prn_oid` (REST path `rs/prns/{prn_oid}/roles`) — reg:867 |
| `IMEI` | BSS оператора (TMF632) | result `device.imei` — apis:2724 |
| `IMSI` | BSS оператора (TMF632) | result `sim.imsi` — apis:2723 |
| `IP_ADDRESS` | Яндекс Метрика Logs | result `$tsv[ym:s:ipAddress]` — apis:5021 |
| `SUBSCRIBER_ACCOUNT` | BSS оператора (TMF632) | result `contract.personalAccount` — apis:2720 |
| `ELN_NUMBER` | СФР FileOperationsLnService `getLNData` | arg `ln_code` — apis:1169; result `data.row.lnCode` — apis:1199; `lnCode`/`LN_CODE`/`prevLnCode`/`nextLnCode` — reg:1105 |
| `PRESCRIPTION_NUMBER` | МИС → ЕГИСЗ СЭМД «Рецепт» | result `prescription.number` — apis:1527 |
| `STUDENT_ID_NUMBER` | Moodle `core_user_get_users_by_field` | arg `values` — apis:4520; result `[].idnumber` — apis:4540 |
| `PNR` | Amadeus Flight Order Management | result `data.associatedRecords[].reference` — apis:3422 |
| `MOBILE_AD_ID` | AppMetrica Logs; Apple | `google_aid`, `ios_ifa`, `advertisingIdentifier` — reg:1356 (verified) |
| `APP_DEVICE_ID` | AppMetrica Logs «installations» | `appmetrica_device_id` — reg:1377 (verified) |
| `METRICA_CLIENT_ID` | Яндекс Метрика Logs | result `$tsv[ym:s:clientID]` — apis:5020; `ClientId`/`_ym_uid` — reg:1395 (verified) |
| `CDP_CUSTOMER_ID` | Яндекс Аудитории API | arg `file.rows[].external_id` — apis:4811 |
| `LOGIN` | Moodle `core_user_get_users_by_field` | result `[].username` — apis:4542 |

Note on provenance of the four "primary-doc-only, no `apis.json` tool" rows above (`IBAN`, `ESIA_OID`,
`MOBILE_AD_ID`, `APP_DEVICE_ID`): they carry exact field names verified against vendor docs
(Bitrix24 apidocs, ЕСИА методические рекомендации, AppMetrica Logs API, Apple docs) but have **no**
tool in the 45-tool `apis.json` set — the registry §2.4 lists them in "28 типов без инструмента".
They are ready for the *detection/field-key* layer; a tool schema must still be authored.

---

## 3. List B — types needing web search · 18 types

| type | best search query |
|---|---|
| `BIRTH_CERT` | `1С ЗУП свидетельство о рождении серия номер реквизит поле выгрузка` |
| `CIVIL_ACT_CERT` | `ЕГР ЗАГС свидетельство о браке/смерти серия номер поле API` |
| `RESIDENCE_PERMIT` | `вид на жительство ВНЖ серия 82 номер поле 1С / Bitrix24 RQ_IDENT_DOC` |
| `MILITARY_ID` | `1С ЗУП воинский учёт военный билет серия номер поле (Т-2)` |
| `CREDIT_SUBJECT_CODE` | `код субъекта кредитной истории ЦККИ/НБКИ поле API` |
| `DMS_POLICY` | `полис ДМС номер policy_number field insurer/clinic API` |
| `KASKO_POLICY` | `полис КАСКО номер field insurance claim API` |
| `INSURANCE_CLAIM_NUMBER` | `страховой убыток номер claim_number field ОСАГО/КАСКО API` |
| `COURT_CASE_UID` | `УИД уникальный идентификатор дела sudrf/ГАС Правосудие поле API` |
| `EXEC_DOC_NO` | `исполнительный лист серия номер ФССП API поле` |
| `PTS_NUMBER` | `ПТС паспорт транспортного средства серия номер поле ГИБДД/ЭПТС API` |
| `MAC` | `MAC address field name router/captive-portal API schema` |
| `MEDCARD_NUMBER` | `номер медицинской карты / ЭМК поле МИС ЕГИСЗ СЭМД` |
| `REFERRAL_NUMBER` | `номер направления 057/у ЕГИСЗ СЭМД направление поле` |
| `SCHOOL_CERT_NUMBER` | `аттестат серия номер поле ФИС ФРДО API` |
| `EMPLOYMENT_CONTRACT_NUMBER` | `1С ЗУП трудовой договор номер поле (ТрудовойДоговор.Номер)` |
| `ACCESS_PASS_NUMBER` | `номер пропуска / badge_id / card_uid field СКУД API` |
| `E_TICKET_NUMBER` | `номер электронного билета e-ticket field airline/RЖД API` |

Best 3 queries (samples):

1. `1С ЗУП военный билет / трудовой договор / свидетельство о рождении реквизиты поле выгрузка` (covers the HR/identity blanks MILITARY_ID, EMPLOYMENT_CONTRACT_NUMBER, BIRTH_CERT)
2. `ЕГИСЗ СЭМД номер медицинской карты / номер направления / рецепт поле XSD` (MEDCARD_NUMBER, REFERRAL_NUMBER, and cross-check PRESCRIPTION)
3. `ФССП/ГАС Правосудие УИД дела и исполнительный лист серия номер поле API` (COURT_CASE_UID, EXEC_DOC_NO)

---

### Method notes (what was checked, what was not)

- Every one of the 41 types has a registry card (`reg` §1.2–§1.4) with a «Поверхности» line and a
  `field_keys` list in `tA/tB/tC`; those `field_keys` are cue/key candidates, **not** producer/consumer
  field paths, unless the source marks them `verified_in_primary_source` / primary-quoted. Only the
  latter were promoted to list A.
- `apis.json` is the authoritative tool layer: its `request[].path` → `pii_type` and
  `returns[].pii_paths` are the exact producer/consumer paths used in list A; label→registry-id
  translation follows the registry §2.3 tool table (e.g. `CLIENT_ID`→`METRICA_CLIENT_ID`/`CDP_CUSTOMER_ID`,
  `CREDIT_UID`→`LOAN_UID`, `FSSP_IP_NUMBER`→`FSSP_IP_NO`, `CONTRACT_NUMBER`→`LOAN_CONTRACT_NUMBER`,
  `PERSONAL_ACCOUNT`→`UTILITY_ACCOUNT`/`SUBSCRIBER_ACCOUNT`, `ELN_CODE`→`ELN_NUMBER`,
  `TAB_NUMBER`→`EMPLOYEE_TAB_NUMBER`, `STUDENT_ID`→`STUDENT_ID_NUMBER`, `LOYALTY_CARD`→`LOYALTY_CARD_NUMBER`).
- `survey.json` / `extension.json` / `MANIFEST.md` contribute register language and cue-typo counts
  only; they carry no tool field paths, so they do not change any list.
- `MEDCARD_NUMBER` and `INSURANCE_CLAIM_NUMBER` both have near-misses that the registry explicitly
  flags as wrong/undeclared (§2.4 items 1 & 3) — therefore they stay in list B despite a *looking*
  exact path (`items[].document_number`, `claim_id`).
