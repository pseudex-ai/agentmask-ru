# Разбор расхождений I≠C на уровне state — v4-live-small

троек с расхождением: 123 из 222 · исключено 0

## Причины

| причина | троек |
|---|---|
| other | 59 |
| derived-only | 20 |
| validate-refuse | 12 |
| Б8-echo | 10 |
| partial-call | 9 |
| control_erred | 7 |
| Б10-city | 2 |
| typo-normalised | 2 |
| residual | 1 |
| Б9-span | 1 |

## По видам

| вид | other | derived-only | validate-refuse | Б8-echo | partial-call | control_erred | Б10-city | typo-normalised | residual | Б9-span |
|---|---|---|---|---|---|---|---|---|---|---|
| chain | 11 | 9 | 0 | 3 | 0 | 0 | 1 | 0 | 0 | 0 |
| compare | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| container | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| correction | 10 | 8 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| decompose | 4 | 0 | 0 | 0 | 0 | 6 | 0 | 2 | 0 | 0 |
| derive | 9 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| result_feed | 9 | 1 | 0 | 1 | 3 | 0 | 0 | 0 | 0 | 0 |
| summary | 2 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| validate | 4 | 0 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Тройки

| тройка | вид | регистр | C вызвал | I вызвал | C′≈C | классы полей | причина | пример: агент / контроль |
|---|---|---|---|---|---|---|---|---|
| chain-000|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-003|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Poliakova Valentina` / `Polyakova Valentina` [derived] |
| chain-003|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Poliakova Valentina` / `Polyakova Valentina` [derived] |
| chain-004|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 extra:1 derived:1 | derived-only | crm_find_contact.query.last_name: агент `` / контроль `Захаров` [absent] |
| chain-004|1 | chain | voice_raw | — | find,upsert,notify_sms | нет | extra:14 | other | crm_find_contact.query.phone: агент `+79508008881` / контроль `` [extra] |
| chain-008|0 | chain | sloppy | find,upsert | find,upsert,notify_sms | нет | absent:1 extra:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-008|1 | chain | sloppy | find,upsert,notify_sms | — | нет | absent:15 | Б10-city | crm_find_contact.query.phone: агент `` / контроль `+79250111503` [absent] |
| chain-009|0 | chain | sloppy | find,upsert,notify_sms | find | да | absent:14 | Б8-echo | crm_upsert_contact.contact.address.city: агент `` / контроль `Глазов` [absent] |
| chain-009|1 | chain | sloppy | find,upsert,notify_sms | find | да | absent:13 | Б8-echo | crm_upsert_contact.contact.address.city: агент `` / контроль `Глазов` [absent] |
| chain-013|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-014|0 | chain | voice_raw | find,upsert,notify_sms | find | нет | absent:13 | Б8-echo | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| chain-014|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:2 derived:1 | derived-only | crm_upsert_contact.contact.birth_date: агент `` / контроль `2003-05-10` [absent] |
| chain-015|1 | chain | voice_itn | find | find,upsert,notify_sms | да | extra:14 | other | crm_upsert_contact.contact.address.city: агент `сортавала` / контроль `` [extra] |
| chain-021|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-021|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-026|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-026|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-029|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-031|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-031|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-033|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-033|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Meshcheryakov Ivan` / `Vasilev Ivan` [derived] |
| chain-043|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:3 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1973-10-03` [absent] |
| chain-043|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:2 absent:1 derived:1 | derived-only | crm_find_contact.query.last_name: агент `лебедев` / контроль `` [extra] |
| compare-009|0 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | нет | — | other |  |
| compare-011|0 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book | нет | absent:10 ref_refused:1 | other | courier_book.address.building: агент `3в` / контроль `3к5` [ref_refused/house_format] |
| compare-011|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 | other | courier_book.address.building: агент `3в` / контроль `3к5` [ref_refused/house_format] |
| compare-014|0 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 other_person:1 | Б8-echo | address_suggest.query: агент `Краснодар, вишёнвая, 28` / контроль `Краснодар, Вишнёвая, 28` [other_person/p14.sugg1] |
| compare-014|1 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 other_person:1 | Б8-echo | address_suggest.query: агент `Краснодар, вишёнвая, 28` / контроль `Краснодар, Вишнёвая, 28` [other_person/p14.sugg1] |
| compare-021|0 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | other_person:1 | Б8-echo | address_suggest.query: агент `Сортавала, нидняя 59` / контроль `Сортавала улица Нижняя 59` [other_person/p21.sugg1] |
| compare-028|0 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | нет | fragment:1 | other | courier_book.contact.name: агент `евгений` / контроль `Евгения` [fragment/given] |
| compare-028|1 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | нет | fragment:1 | other | courier_book.contact.name: агент `евгений` / контроль `Евгения` [fragment/given] |
| compare-034|0 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg | нет | absent:15 other:1 | Б8-echo | address_suggest.query: агент `Самара, пушкна, 65, корп. 1` / контроль `Самара, улица Пушкина, 65 корпус 1` [other/unbound] |
| compare-034|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | да | absent:10 other:1 | Б8-echo | address_suggest.query: агент `Самара, пушкна, 65, корп. 1` / контроль `Самара, улица Пушкина, 65 корпус 1` [other/unbound] |
| compare-035|1 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `79` [absent] |
| compare-036|0 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | нет | — | other |  |
| container-005|0 | container | sloppy | import_csv | import_csv | да | container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-015|0 | container | voice_raw | import_csv | import_csv,import_csv,import_csv | да | extra:2 residual:1 | residual | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [residual] |
| container-017|0 | container | voice_itn | import_csv | import_csv,import_csv,import_csv,import_csv,import_csv,import_csv | да | extra:5 container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-023|0 | container | voice_itn | import_csv | import_csv,import_csv,import_csv,import_csv | да | extra:3 container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-029|0 | container | voice_raw | import_csv | import_csv,import_csv,import_csv | да | extra:2 container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| correction-010|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-010|1 | correction | chat | courier_book | courier_book,upsert | нет | extra:9 | other | crm_upsert_contact.contact.address.city: агент `Ижевск` / контроль `` [extra] |
| correction-012|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `И.` / `О.` [derived] |
| correction-012|1 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Г.` / `О.` [derived] |
| correction-013|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | да | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valeriia` / контроль `Miller Valeria` [other/misderived] |
| correction-013|1 | correction | sloppy | courier_book,upsert | courier_book,upsert | да | absent:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-016|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-016|1 | correction | chat | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Колпино` [absent] |
| correction-017|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-017|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Fedorova Iuliia` / контроль `Fedorova Yulia` [other/misderived] |
| correction-018|0 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | partial-call | courier_book.contact.phone: агент `+79257203145` / контроль `+79257231145` [control_erred/i4] |
| correction-018|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | control_erred:2 absent:1 derived:1 | other | courier_book.contact.phone: агент `+79257203145` / контроль `+79257231145` [control_erred/i4] |
| correction-021|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Л.` / `И.` [derived] |
| correction-021|1 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Можга` [absent] |
| correction-024|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-024|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-025|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| correction-025|1 | correction | voice_itn | courier_book,upsert | upsert,courier_book | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| correction-030|0 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Сарапул` [absent] |
| correction-030|1 | correction | voice_raw | upsert,courier_book | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Сарапул` [absent] |
| correction-031|0 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | partial-call | courier_book.address.street: агент `нвоая` / контроль `Новая` [control_erred/i2] |
| correction-031|1 | correction | sloppy | upsert,courier_book | courier_book,upsert | нет | control_erred:2 derived:1 other:1 | other | crm_upsert_contact.contact.address.street: агент `нвоая` / контроль `Новая` [control_erred/i2] |
| correction-032|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bukin Sergei` / контроль `Bukin Sergey` [other/misderived] |
| correction-032|1 | correction | voice_itn | courier_book | upsert,courier_book | нет | extra:9 | other | crm_upsert_contact.contact.address.city: агент `Ижевск` / контроль `` [extra] |
| decompose-007|0 | decompose | sloppy | courier_book | courier_book | да | other:2 | typo-normalised | courier_book.address.street: агент `проезд неркасова` / контроль `проезд Некрасова` [other/unbound] |
| decompose-007|1 | decompose | sloppy | courier_book | courier_book | да | other:2 | typo-normalised | courier_book.address.street: агент `проезд неркасова` / контроль `Проезд Некрасова` [other/unbound] |
| decompose-008|1 | decompose | sloppy | payment_crea | payment_crea | нет | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `PETR EROKHIN` / контроль `PETR YEROKHIN` [other/misderived] |
| decompose-019|0 | decompose | sloppy | courier_book | courier_book | да | control_erred:1 | control_erred | courier_book.address.street: агент `луогвая` / контроль `Луговая` [control_erred/i1] |
| decompose-019|1 | decompose | sloppy | courier_book | courier_book | да | control_erred:1 | control_erred | courier_book.address.street: агент `луогвая` / контроль `Луговая` [control_erred/i1] |
| decompose-025|0 | decompose | voice_raw | courier_book | courier_book | нет | control_erred:1 | control_erred | courier_book.contact.phone: агент `+79505556677` / контроль `+79005055677` [control_erred/i3] |
| decompose-025|1 | decompose | voice_raw | courier_book | courier_book | нет | control_erred:1 | control_erred | courier_book.contact.phone: агент `+79505556677` / контроль `+79005556677` [control_erred/i3] |
| decompose-029|0 | decompose | clean | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VALERII MILLER` / контроль `VALERIY MILLER` [other/misderived] |
| decompose-029|1 | decompose | clean | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VALERII MILLER` / контроль `VALERIY MILLER` [other/misderived] |
| decompose-033|0 | decompose | voice_raw | passport_ver | passport_ver | да | control_erred:1 | control_erred | passport_verify.passport.series: агент `4019` / контроль `4919` [control_erred/i1] |
| decompose-033|1 | decompose | voice_raw | passport_ver | passport_ver | да | control_erred:1 | control_erred | passport_verify.passport.series: агент `4019` / контроль `4919` [control_erred/i1] |
| decompose-041|0 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VLADISLAV MESHCHERYAKOV` / контроль `VLADISLAV ZAKHAROV` [other/misderived] |
| derive-008|0 | derive | sloppy | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `29` / `28` [derived] |
| derive-008|1 | derive | sloppy | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `29` / `28` [derived] |
| derive-013|0 | derive | voice_raw | upsert | upsert | нет | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Meshcheryakov Sergei` / контроль `Bukin Sergei` [other/misderived] |
| derive-013|1 | derive | voice_raw | upsert | upsert | нет | extra:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-020|0 | derive | voice_raw | clinic_book | clinic_book | нет | derived:1 other:1 | other | clinic_book.patient.last_name: агент `родилсяя` / контроль `Миллер` [other/inflected] |
| derive-020|1 | derive | voice_raw | clinic_book | — | нет | absent:7 | Б9-span | clinic_book.patient.age: агент `` / контроль `45` [absent] |
| derive-030|1 | derive | voice_raw | delivery_cre | delivery_cre | нет | other:1 | other | delivery_create_order.to_location.address: агент `ул. зарчная, д. 97в, кв. 234` / контроль `ул. Зарничная, д. 97В, кв. 234` [other/unbound] |
| derive-033|1 | derive | voice_raw | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-036|0 | derive | voice_itn | clinic_book | clinic_book,clinic_book | да | extra:7 other:1 validated_refused:1 | other | clinic_book.patient.age: агент `64` / контроль `34` [other/misderived] |
| derive-036|1 | derive | voice_itn | clinic_book | clinic_book,clinic_book | да | extra:7 derived:1 validated_refused:1 | other | clinic_book.patient.birth_date: агент `0206-19-92` / контроль `1992-06-02` [validated_refused/date_invalid] |
| derive-053|0 | derive | chat | upsert | upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-053|1 | derive | chat | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| result_feed-003|1 | result_feed | chat | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-004|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-007|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-007|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-009|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book,notify_sms | нет | extra:1 | other | notify_sms.number: агент `+79099312815` / контроль `` [extra] |
| result_feed-009|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-028|0 | result_feed | chat | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79776996134` [absent] |
| result_feed-028|1 | result_feed | chat | find,clinic_book,notify_sms | find | нет | absent:8 | Б8-echo | clinic_book.patient.age: агент `` / контроль `53` [absent] |
| result_feed-031|0 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79510443707` [absent] |
| result_feed-031|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79510443707` [absent] |
| result_feed-033|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `45` / контроль `46` [other/misderived] |
| result_feed-033|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-035|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `54` / `55` [derived] |
| result_feed-035|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `54` / контроль `55` [other/misderived] |
| summary-000|0 | summary | sloppy | delivery_cre | delivery_cre | нет | other:1 | other | delivery_create_order.to_location.address: агент `загорондый проспект, 199, кв. 109` / контроль `пр-т Загородный, 199, кв. 109` [other/unbound] |
| summary-000|1 | summary | sloppy | delivery_cre | delivery_cre | да | other:1 | other | delivery_create_order.to_location.address: агент `загорондый проспект, д. 199, кв. 109` / контроль `пр. Загородный, 199, кв. 109` [other/unbound] |
| summary-003|0 | summary | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 | control_erred | delivery_create_order.recipient.phones[0].number: агент `+79524139091` / контроль `+79524139901` [control_erred/i2] |
| summary-006|0 | summary | sloppy | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Лебедев Максим Константинович` [absent] |
| validate-000|0 | validate | voice_raw | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `141783` [absent] |
| validate-000|1 | validate | voice_raw | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `141783` [absent] |
| validate-006|0 | validate | voice_itn | passport_ver | passport_ver | да | absent:1 | other | passport_verify.snils: агент `` / контроль `530-663-406 64` [absent] |
| validate-006|1 | validate | voice_itn | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `126611` [absent] |
| validate-018|0 | validate | chat | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `343601` [absent] |
| validate-018|1 | validate | chat | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `343601` [absent] |
| validate-019|0 | validate | voice_raw | passport_ver | passport_ver | да | absent:1 | other | passport_verify.snils: агент `` / контроль `252-814-525 64` [absent] |
| validate-019|1 | validate | voice_raw | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `136791` [absent] |
| validate-020|0 | validate | voice_itn | passport_ver | — | нет | absent:5 | validate-refuse | passport_verify.passport.number: агент `` / контроль `887065` [absent] |
| validate-022|0 | validate | voice_raw | passport_ver,passport_ver | — | да | absent:12 | validate-refuse | passport_verify.passport.number: агент `` / контроль `797566` [absent] |
| validate-022|1 | validate | voice_raw | passport_ver,passport_ver | — | да | absent:12 | validate-refuse | passport_verify.passport.number: агент `` / контроль `797566` [absent] |
| validate-028|0 | validate | sloppy | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `329642` [absent] |
| validate-028|1 | validate | sloppy | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `329642` [absent] |
| validate-029|0 | validate | chat | — | passport_ver | нет | extra:5 | other | passport_verify.passport.number: агент `354448` / контроль `` [extra] |
| validate-032|0 | validate | voice_itn | — | passport_ver | да | extra:5 | other | passport_verify.passport.number: агент `285851` / контроль `` [extra] |
| validate-035|1 | validate | chat | passport_ver | — | нет | absent:5 | validate-refuse | passport_verify.passport.number: агент `` / контроль `202966` [absent] |
