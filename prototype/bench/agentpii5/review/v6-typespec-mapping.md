# v6 TypeSpec mapping — card → registry fields

> Для авторов v6-записей реестра. Как каждое поле карточки
> `docs/tz-agentpii6-registry.md` §1.2–1.4 ложится в поле `TypeSpec`
> (`prototype/bench/agentpii5/pii_types.py`). Один дом, один порядок — два автора
> одной группы не должны разойтись в конвенции.

## Классы (финал, D-070 + рекомендация G1-4 §13)

| тип | класс | generated_checksum |
|---|---|---|
| `IMEI` | `C` | `luhn` |
| `OMS_ENP` | `KC` | `luhn` |
| `BANK_ACCOUNT` | `KC` | `cbr515` |
| `VIN` | `KC` | `iso3779` |
| `LOYALTY_CARD_NUMBER` | `KC` | `gs1` |
| `IBAN` | `K` | `mod97` |
| `LOAN_UID` | `K` | `uid` |
| `OGRNIP` | `K` | `ogrnip` |
| `EPTS_NUMBER` | `K` | `epts` |
| `UIN` | `K` | `uin` |
| `COURT_CASE_UID` | `K` | `""` (алгоритм ВЫВЕДЕН, не опубликован — §1.8 «не выполнено») |
| `ICCID` | `K` | `luhn` |
| `INTL_PASSPORT` | `K` | `""` (на печатном номере КС нет; ICAO 7-3-1 — только в MRZ, отдельная производная форма) |
| все остальные | `K` | `""` |

Правило §1.0: у типа с НЕпустым `generated_checksum` значения генерируются
КС-валидными. Исключения: VIN (OD-62: 50% РФ с неверной КС) и 20-значный ICCID.

## Поле карточки → поле TypeSpec

| карточка | TypeSpec | правило |
|---|---|---|
| заголовок (`A-11 OGRNIP`) | `id` | id из скобок |
| — | `origin` | `"v6"` |
| — | `item_type` | `True` всегда (DATE — единственный не-item, и он v5) |
| класс (выше) | `type_class` | `C`/`K`/`KC` |
| класс (выше) | `generated_checksum` | имя из таблицы или `""` |
| — | `bare_typed` | `True` только у форм, уникальных по тесту коллизий (§1.6/§1.7); сейчас пишите `False`, уникальность решается позже |
| «Грамматика» | `grammar` | regex + варианты, дословно по карточке |
| «Грамматика» | `length` | диапазон с источником, дословно |
| статус в §1.1 | `grammar_status` | `ГОТОВ` \| `ГРАММАТИКА?` \| `ДЕРЖИМ` |
| «Cue / ключи» (до `·`) | `cues` | русские cue-слова, кортежем |
| «Cue / ключи» (после `·`) | `field_keys` | английские ключи, кортежем |
| «Отрасли» | `industries` | имена из `contracts_v6.INDUSTRIES` (перевести: ритейл→`retail`, банки→`banks_mfo_collectors`, авто→`auto`, телеком→`telecom`, недвижимость→`real_estate`, гостеприимство→`hospitality`, юруслуги→`legal`, госуслуги→`government_services`, образование→`education`, страхование→`insurance`, логистика→`logistics`, медицина→`medicine`, HR→`hr`, BI→`internal_bi`, маркетинг/CDP→`marketing_cdp`) |
| «ПД» | `pd_context` | кратко правило (OD-22/23/24), или `""` |
| §5.3 класс формы | `form_features` | признаки из таблицы §5.3 |
| §5.2 | `feature_labels` | (признак, кортеж меток) в порядке §5.2 |
| §5.2 | `abstain` | (признак, метка воздержания), или `()` |
| §1.0 | `identifying_roles` | `("digits",)` у цифровых; `()` у голой формы; по §1.0 |
| «Иглы» | `needle_kinds` | из карточки; `whole` всегда первым |
| — | `squeeze_separators` | `""` (класс разделителей иглы — позже, CQ-8) |
| — | `signature_tail` | `0` (только PHONE=10) |
| §5.5 | `value_notation` | `digits`\|`date`\|`squeezed`\|`glyph_fold`\|`ip_strict`\|`""` |
| «Движок» | `engine_labels` | метка движка (напр. OGRNIP→`("OGRN",)`); пусто, если id совпадает |
| §6.2 mint | `mint` | `id_digits` \| `id_alnum` \| `hex` \| `""` (по классу формы §5.3) |
| §9.2 hunt | `hunt` | `always` \| `by_shape` \| `covered` (по §9.2) |
| «Варианты»/§1.8 пример | `sample` | синтетический образец, КС-валидный |

## Формы §5.3 → form_features (копия для сверки)

- цифры: `IMEI, ICCID, IMSI, OMS_ENP, BANK_ACCOUNT, OGRNIP, EPTS_NUMBER, UIN, ELN_NUMBER, SCHOOL_CERT_NUMBER, E_TICKET_NUMBER, METRICA_CLIENT_ID, ESIA_OID, EID, LOYALTY_CARD_NUMBER` → `("grouping","separators","digit_count")`
- цифровые серия+номер: `INTL_PASSPORT, RESIDENCE_PERMIT, STS_NUMBER, DRIVER_LICENSE, DIPLOMA_NUMBER` → `("grouping","separators","by_fields")`
- буквенно-цифровые: `VIN, PTS_NUMBER, GIS_ZHKH_ELS, MILITARY_ID, OSAGO_POLICY, BIRTH_CERT, CIVIL_ACT_CERT, EXEC_DOC_NO, PNR, IBAN` → `("grouping","separators","case_class","script")`
- структурные: `CADASTRAL_NUMBER, ARBITRAZH_CASE_NO, COURT_CASE_NO_SOU, FSSP_IP_NO, COURT_CASE_UID, EGRN_REG_NO, EGRN_REQUEST_NO, PLEDGE_NOTICE_NO` → `("separators","case_class","script")`
- hex/UUID: `LOAN_UID, MOBILE_AD_ID, MAC, APP_DEVICE_ID` → `("grouping","separators","case_class")`
- свободная за cue: `LOAN_CONTRACT_NUMBER, INSURANCE_CLAIM_NUMBER, DMS_POLICY, KASKO_POLICY, TEMP_RESIDENCE_PERMIT, CREDIT_SUBJECT_CODE, MEDCARD_NUMBER, PRESCRIPTION_NUMBER, REFERRAL_NUMBER, STUDENT_ID_NUMBER, RECORD_BOOK_NUMBER, EMPLOYMENT_CONTRACT_NUMBER, ACCESS_PASS_NUMBER, EMPLOYEE_TAB_NUMBER, SUBSCRIBER_ACCOUNT, UTILITY_ACCOUNT, CDP_CUSTOMER_ID, LOGIN, MIGRATION_CARD_NUMBER` → `("separators","case_class","padding")`
- IP: `IP_ADDRESS` → `("notation","padding")`

## Метки признаков §5.2 (копия)

- `grouping`: закрытый список на тип (группировки + `solid`, `other`)
- `separators`: `none space hyphen dot slash colon numsign mixed`
- `case_class`: `lower upper mixed none`
- `script`: `cyrillic latin mixed none`
- `by_fields`: `fields string`
- `padding`: `padded unpadded none`
- `digit_count`: `as_grammar other`
- `notation` (только IP): `v4_dotted v4_padded v6_full v6_compressed other`

Воздержания (`abstain`): признак без букв → `case_class`=`none`, `script`=`none`;
признак не применим → названную в §5.2 метку. Неназванное воздержание запрещено.

## Что НЕ входит в карточку и пишется сейчас консервативно

`bare_typed=False`, `squeeze_separators=""`, `signature_tail=0` у всех; `hunt` по
§9.2 (цифровые `by_shape`, буквенно-цифровые `covered`); `mint` по классу формы
(цифры→`id_digits`, буквенно-цифровые→`id_alnum`, hex→`hex`, свободная за cue→`""`).
