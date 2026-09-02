# Разбор расхождений I≠C на уровне state — v4-live-small

троек с расхождением: 252 из 355 · исключено 5

## Причины

| причина | троек |
|---|---|
| derived-only | 101 |
| other | 66 |
| Б8-echo | 30 |
| Б10-city | 19 |
| validate-refuse | 16 |
| Б9-span | 10 |
| residual | 6 |
| control_erred | 4 |

## По видам

| вид | derived-only | other | Б8-echo | Б10-city | validate-refuse | Б9-span | residual | control_erred |
|---|---|---|---|---|---|---|---|---|
| chain | 45 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| compare | 0 | 6 | 30 | 0 | 0 | 0 | 0 | 0 |
| container | 0 | 8 | 0 | 0 | 0 | 0 | 6 | 0 |
| correction | 12 | 17 | 0 | 0 | 0 | 1 | 0 | 0 |
| decompose | 11 | 13 | 0 | 0 | 0 | 3 | 0 | 4 |
| derive | 14 | 4 | 0 | 19 | 0 | 6 | 0 | 0 |
| result_feed | 19 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| validate | 0 | 9 | 0 | 0 | 16 | 0 | 0 | 0 |

## Тройки

| тройка | вид | регистр | C вызвал | I вызвал | C′≈C | классы полей | причина | пример: агент / контроль |
|---|---|---|---|---|---|---|---|---|
| chain-000|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 extra:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-000|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-000|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `И.В.` / `С.И.` [derived] |
| chain-003|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-003|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:3 derived:2 | derived-only | crm_upsert_contact.contact.birth_date: агент `` / контроль `1974-10-08` [absent] |
| chain-003|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-004|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:2 derived:2 extra:1 | derived-only | crm_find_contact.query.last_name: агент `` / контроль `Захаров` [absent] |
| chain-004|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 extra:1 | derived-only | crm_find_contact.query.last_name: агент `` / контроль `Захаров` [absent] |
| chain-004|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 extra:1 | derived-only | crm_find_contact.query.last_name: агент `` / контроль `Захаров` [absent] |
| chain-008|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Д.Я.` / `А.В.` [derived] |
| chain-008|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 other:1 | other | crm_upsert_contact.contact.last_name: агент `артём` / контроль `Громов` [other/inflected] |
| chain-008|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 extra:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-009|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-009|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `К.В.` / `В.Ю.` [derived] |
| chain-009|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-013|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Г.Г.` / `К.С.` [derived] |
| chain-013|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 extra:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-013|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-014|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `В.Г.` / `Д.А.` [derived] |
| chain-014|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `В.И.` / `Д.А.` [derived] |
| chain-014|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:3 derived:2 | derived-only | crm_upsert_contact.contact.birth_date: агент `` / контроль `2003-05-10` [absent] |
| chain-015|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Н.Ф.` / `О.Д.` [derived] |
| chain-015|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-015|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Л.А.` / `О.Д.` [derived] |
| chain-021|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-021|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:3 derived:2 | derived-only | crm_upsert_contact.contact.birth_date: агент `` / контроль `1997-07-24` [absent] |
| chain-021|2 | chain | chat | find | find,upsert,notify_sms | нет | extra:13 | other | crm_upsert_contact.contact.address.city: агент `Ижевск` / контроль `` [extra] |
| chain-024|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-024|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-024|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-026|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Т.В.` / `Р.Ф.` [derived] |
| chain-026|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 other:1 | other | crm_upsert_contact.contact.last_name: агент `руслан` / контроль `Заболотный` [other/inflected] |
| chain-026|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 extra:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-029|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-029|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Б.О.` / `К.С.` [derived] |
| chain-029|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Н.Д.` / `К.С.` [derived] |
| chain-031|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Т.М.` / `Н.В.` [derived] |
| chain-031|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `У.Г.` / `Н.В.` [derived] |
| chain-031|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Ж.М.` / `Н.В.` [derived] |
| chain-033|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `В.М.` / `И.П.` [derived] |
| chain-033|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-033|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `М.П.` / `И.П.` [derived] |
| chain-038|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 extra:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-038|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `В.В.` / `В.Ю.` [derived] |
| chain-038|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Д.В.` / `В.Ю.` [derived] |
| chain-043|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Л.А.` / `М.К.` [derived] |
| chain-043|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 extra:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-043|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| compare-005|0 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `160` [absent] |
| compare-005|1 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `160` [absent] |
| compare-005|2 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `160` [absent] |
| compare-009|0 | compare | voice_itn | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `10` [absent] |
| compare-009|1 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `10` [absent] |
| compare-009|2 | compare | voice_itn | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `10` [absent] |
| compare-011|0 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `3в` [absent] |
| compare-011|1 | compare | voice_raw | address_sugg,address_sugg,courier_book | address_sugg | нет | absent:6 | Б8-echo | address_suggest.query: агент `` / контроль `Глазов, Химзаводская 3 корпус 5` [absent] |
| compare-011|2 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg | да | absent:15 other:1 | Б8-echo | address_suggest.query: агент `Глазов, химзаводская, 3в, корпус 5` / контроль `Глазов, Химзаводская, 3` [other/inflected] |
| compare-014|0 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | other:1 | other | courier_book.contact.name: агент `марин` / контроль `Марина` [other/inflected] |
| compare-014|1 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | other:1 | other | courier_book.contact.name: агент `марин` / контроль `Марина` [other/inflected] |
| compare-014|2 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | other:1 | other | courier_book.contact.name: агент `марин` / контроль `Марина` [other/inflected] |
| compare-017|0 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `33` [absent] |
| compare-017|1 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `33` [absent] |
| compare-017|2 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `33` [absent] |
| compare-021|0 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | other_person:1 other:1 | Б8-echo | courier_book.address.building: агент `59а` / контроль `59` [other_person/p21.sugg1] |
| compare-028|0 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `155` [absent] |
| compare-028|1 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `155` [absent] |
| compare-028|2 | compare | voice_itn | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `155` [absent] |
| compare-029|0 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `100` [absent] |
| compare-029|1 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `100` [absent] |
| compare-029|2 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `100` [absent] |
| compare-034|0 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book,courier_book | нет | absent:5 other:2 ref_refused:1 | other | courier_book.contact.name: агент `петра` / контроль `Петр` [other/inflected] |
| compare-034|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | нет | other:2 control_erred:1 | other | courier_book.contact.name: агент `петра` / контроль `Пётр` [other/inflected] |
| compare-034|2 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 other:1 | other | courier_book.address.building: агент `65` / контроль `65 к1` [ref_refused/house_format] |
| compare-035|0 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `79` [absent] |
| compare-035|1 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `79` [absent] |
| compare-035|2 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `79` [absent] |
| compare-036|0 | compare | chat | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `82` [absent] |
| compare-036|1 | compare | chat | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `82` [absent] |
| compare-036|2 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `82` [absent] |
| compare-039|0 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `121` [absent] |
| compare-039|2 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `121` [absent] |
| compare-041|0 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `148` [absent] |
| compare-041|1 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `148` [absent] |
| compare-041|2 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `148` [absent] |
| container-011|0 | container | voice_raw | import_csv | import_csv | да | container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-011|1 | container | voice_raw | import_csv | import_csv | да | container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-011|2 | container | voice_raw | import_csv | import_csv | да | container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-015|0 | container | voice_raw | import_csv | import_csv | да | residual:1 | residual | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [residual] |
| container-015|1 | container | voice_raw | import_csv | import_csv | да | residual:1 | residual | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [residual] |
| container-015|2 | container | voice_raw | import_csv | import_csv | да | residual:1 | residual | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [residual] |
| container-017|0 | container | voice_itn | import_csv | import_csv,import_csv,import_csv,import_csv | да | extra:3 container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-017|1 | container | voice_itn | import_csv | import_csv,import_csv,import_csv,import_csv,import_csv | да | extra:4 container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-017|2 | container | voice_itn | import_csv | import_csv | да | container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-023|0 | container | voice_itn | import_csv | import_csv,import_csv,import_csv,import_csv | да | extra:3 container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-023|1 | container | voice_itn | import_csv | import_csv,import_csv,import_csv,import_csv | да | extra:3 container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-029|0 | container | voice_raw | import_csv | import_csv | да | residual:1 | residual | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [residual] |
| container-029|1 | container | voice_raw | import_csv | import_csv | да | residual:1 | residual | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [residual] |
| container-029|2 | container | voice_raw | import_csv | import_csv | да | residual:1 | residual | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [residual] |
| correction-010|0 | correction | chat | courier_book,upsert | courier_book | нет | absent:9 | other | crm_upsert_contact.contact.address.city: агент `` / контроль `Ижевск` [absent] |
| correction-012|0 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 fragment:1 other:1 | other | crm_upsert_contact.contact.last_name: агент `ольга` / контроль `Кузнецова` [fragment/given] |
| correction-012|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-012|2 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `А.` / `О.` [derived] |
| correction-013|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-013|1 | correction | sloppy | courier_book,upsert | courier_book,upsert | да | derived:2 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Sorokin Dmitry` / контроль `Miller Valeria` [other/misderived] |
| correction-013|2 | correction | sloppy | courier_book,upsert | courier_book | да | absent:10 | other | crm_upsert_contact.contact.address.city: агент `` / контроль `Сарапул` [absent] |
| correction-016|0 | correction | chat | courier_book,upsert | courier_book | нет | absent:9 | other | crm_upsert_contact.contact.address.city: агент `` / контроль `Колпино` [absent] |
| correction-016|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `П.` / `Л.` [derived] |
| correction-016|2 | correction | chat | courier_book,upsert | courier_book | нет | absent:9 | other | crm_upsert_contact.contact.address.city: агент `` / контроль `Колпино` [absent] |
| correction-017|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `И.` / `Ю.` [derived] |
| correction-017|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:2 extra:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| correction-017|2 | correction | voice_itn | courier_book,upsert | courier_book | да | absent:10 | other | crm_upsert_contact.contact.address.city: агент `` / контроль `Глазов` [absent] |
| correction-018|2 | correction | voice_raw | courier_book,upsert | — | нет | absent:15 | Б9-span | courier_book.address.building: агент `` / контроль `177` [absent] |
| correction-021|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `М.` / `И.` [derived] |
| correction-021|1 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.email: агент `` / контроль `azulaysara868@gmail.com` [absent] |
| correction-021|2 | correction | sloppy | courier_book,upsert | courier_book,upsert | да | derived:2 extra:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-024|0 | correction | voice_raw | — | courier_book,upsert | да | extra:15 | other | courier_book.address.building: агент `155` / контроль `` [extra] |
| correction-024|1 | correction | voice_raw | courier_book | courier_book | нет | reformatted:1 | other | courier_book.address.building: агент `114` / контроль `155` [reformatted] |
| correction-025|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| correction-025|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | extra:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| correction-025|2 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | derived:2 extra:1 | derived-only | crm_upsert_contact.contact.email: агент `azulaysara868@gmail.com` / контроль `` [extra] |
| correction-030|0 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:9 other:1 | other | courier_book.address.street: агент `дом сто восемьдесят пять квартира пят…` / контроль `Мончегорская` [other/unbound] |
| correction-030|1 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:9 other:1 | other | courier_book.address.street: агент `дом сто восемьдесят пять квартира пят…` / контроль `Мончегорская` [other/unbound] |
| correction-030|2 | correction | voice_raw | courier_book | courier_book | нет | other:2 | other | courier_book.address.street: агент `дом сто восемьдесят пять квартира пят…` / контроль `Мончегорская` [other/unbound] |
| correction-031|0 | correction | sloppy | courier_book | courier_book,upsert | нет | extra:9 | other | crm_upsert_contact.contact.address.city: агент `Сарапул` / контроль `` [extra] |
| correction-031|1 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:9 | other | crm_upsert_contact.contact.address.city: агент `` / контроль `Сарапул` [absent] |
| correction-031|2 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:9 | other | crm_upsert_contact.contact.address.city: агент `` / контроль `Сарапул` [absent] |
| correction-032|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `М.` / `С.` [derived] |
| correction-032|2 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:2 | derived-only | crm_upsert_contact.contact.initials: `М.` / `С.` [derived] |
| decompose-007|0 | decompose | sloppy | courier_book | courier_book | да | other:2 | other | courier_book.address.street: агент `проезд неркасова` / контроль `проезд Некрасова` [other/unbound] |
| decompose-007|1 | decompose | sloppy | courier_book | courier_book | да | other:2 | other | courier_book.address.street: агент `проезд неркасова` / контроль `проезд Некрасова` [other/unbound] |
| decompose-007|2 | decompose | sloppy | courier_book | courier_book | да | other:2 | other | courier_book.address.street: агент `проезд неркасова` / контроль `проезд Некрасова` [other/unbound] |
| decompose-008|0 | decompose | sloppy | payment_crea | payment_crea | да | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `MATVEY SHILOV` / `PETR EROKHIN` [derived] |
| decompose-008|1 | decompose | sloppy | payment_crea | payment_crea | да | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `SVYATOSLAV NAUMOV` / `PETR EROKHIN` [derived] |
| decompose-008|2 | decompose | sloppy | payment_crea | payment_crea | да | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `GLEB BELYAEV` / `PETR EROKHIN` [derived] |
| decompose-010|0 | decompose | chat | courier_book | courier_book | да | other:1 | other | courier_book.address.street: агент `проезд ижевск ленина` / контроль `проезд Ленина` [other/unbound] |
| decompose-010|1 | decompose | chat | courier_book | courier_book | да | other:1 | other | courier_book.address.street: агент `проезд ижевск ленина` / контроль `проезд Ленина` [other/unbound] |
| decompose-010|2 | decompose | chat | courier_book | courier_book | да | other:1 | other | courier_book.address.street: агент `проезд ижевск ленина` / контроль `проезд Ленина` [other/unbound] |
| decompose-016|0 | decompose | clean | courier_book | courier_book | да | composed:1 | other | courier_book.address.street: агент `141 подъезд 5 кв. 175` / контроль `Маяковского` [composed] |
| decompose-016|1 | decompose | clean | courier_book | courier_book | да | composed:1 | other | courier_book.address.street: агент `141 подъезд 5 кв. 175` / контроль `Маяковского` [composed] |
| decompose-016|2 | decompose | clean | courier_book | courier_book | да | composed:1 | other | courier_book.address.street: агент `141 подъезд 5 кв. 175` / контроль `Маяковского` [composed] |
| decompose-019|0 | decompose | sloppy | courier_book | courier_book | да | control_erred:1 | control_erred | courier_book.address.street: агент `луогвая` / контроль `Луговая` [control_erred/i1] |
| decompose-019|1 | decompose | sloppy | courier_book | courier_book | да | control_erred:1 | control_erred | courier_book.address.street: агент `луогвая` / контроль `Луговая` [control_erred/i1] |
| decompose-019|2 | decompose | sloppy | courier_book | courier_book | да | control_erred:1 | control_erred | courier_book.address.street: агент `луогвая` / контроль `Луговая` [control_erred/i1] |
| decompose-025|2 | decompose | voice_raw | courier_book | courier_book | нет | control_erred:1 | control_erred | courier_book.contact.phone: агент `+79505556677` / контроль `+79005556677` [control_erred/i3] |
| decompose-028|0 | decompose | chat | courier_book | courier_book | да | composed:1 | other | courier_book.address.street: агент `сортавала заречная` / контроль `Заречная` [composed] |
| decompose-028|1 | decompose | chat | courier_book | courier_book | да | composed:1 | other | courier_book.address.street: агент `сортавала заречная` / контроль `Заречная` [composed] |
| decompose-028|2 | decompose | chat | courier_book | courier_book | да | composed:1 | other | courier_book.address.street: агент `сортавала заречная` / контроль `Заречная` [composed] |
| decompose-029|0 | decompose | clean | payment_crea | payment_crea | да | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `YAN RYBAKOV` / `VALERIY MILLER` [derived] |
| decompose-029|1 | decompose | clean | payment_crea | payment_crea | да | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `YURIY TIKHONOV` / `VALERIY MILLER` [derived] |
| decompose-029|2 | decompose | clean | payment_crea | payment_crea | нет | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `KONSTANTIN ZHUKOV` / `VALERIY MILLER` [derived] |
| decompose-033|0 | decompose | voice_raw | passport_ver | — | да | absent:6 | Б9-span | passport_verify.passport.number: агент `` / контроль `313559` [absent] |
| decompose-033|1 | decompose | voice_raw | passport_ver | — | да | absent:6 | Б9-span | passport_verify.passport.number: агент `` / контроль `313559` [absent] |
| decompose-033|2 | decompose | voice_raw | passport_ver | passport_ver | да | control_erred:1 validated_refused:1 | other | passport_verify.passport.series: агент `4019` / контроль `4919` [control_erred/i1] |
| decompose-035|0 | decompose | voice_itn | payment_crea | payment_crea | да | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `INNA SAZONOVA` / `ANNA SOKOLOVA` [derived] |
| decompose-035|1 | decompose | voice_itn | payment_crea | payment_crea | да | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `KARINA RYBAKOVA` / `ANNA SOKOLOVA` [derived] |
| decompose-035|2 | decompose | voice_itn | payment_crea | payment_crea | да | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `ROZA FOMINA` / `ANNA SOKOLOVA` [derived] |
| decompose-041|0 | decompose | voice_raw | payment_crea | — | да | absent:2 | Б9-span | payment_create.payment_method_data.card.cardholder: агент `` / контроль `VLADISLAV ZAKHAROV` [absent] |
| decompose-041|1 | decompose | voice_raw | payment_crea | payment_crea | да | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `MATVEY SHCHUKIN` / `VLADISLAV ZAKHAROV` [derived] |
| decompose-041|2 | decompose | voice_raw | payment_crea | payment_crea | да | derived:1 | derived-only | payment_create.payment_method_data.card.cardholder: `IGNAT TSVETKOV` / `VLADISLAV ZAKHAROV` [derived] |
| derive-002|0 | derive | chat | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Фёдорова Юлия` [absent] |
| derive-002|1 | derive | chat | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Фёдорова Юлия` [absent] |
| derive-007|0 | derive | voice_itn | callback_sch | — | да | absent:2 | Б10-city | callback_schedule.phone: агент `` / контроль `+79274481140` [absent] |
| derive-007|1 | derive | voice_itn | callback_sch | callback_sch | да | derived:1 | derived-only | callback_schedule.timezone: `Europe/Moscow` / `Europe/Samara` [derived] |
| derive-007|2 | derive | voice_itn | callback_sch | — | да | absent:2 | Б10-city | callback_schedule.phone: агент `` / контроль `+79274481140` [absent] |
| derive-008|0 | derive | sloppy | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `12` / `28` [derived] |
| derive-008|1 | derive | sloppy | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `7` / `28` [derived] |
| derive-008|2 | derive | sloppy | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `22` / `28` [derived] |
| derive-013|0 | derive | voice_raw | upsert | — | да | absent:7 | Б9-span | crm_upsert_contact.contact.first_name: агент `` / контроль `Сергей` [absent] |
| derive-013|1 | derive | voice_raw | upsert | — | нет | absent:7 | Б9-span | crm_upsert_contact.contact.first_name: агент `` / контроль `Сергей` [absent] |
| derive-013|2 | derive | voice_raw | upsert | — | нет | absent:6 | Б9-span | crm_upsert_contact.contact.first_name: агент `` / контроль `Сергей` [absent] |
| derive-017|0 | derive | sloppy | upsert | upsert | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Ж.М.` / `О.Д.` [derived] |
| derive-017|1 | derive | sloppy | upsert | upsert | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `К.М.` / `О.Д.` [derived] |
| derive-017|2 | derive | sloppy | upsert | upsert | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Л.И.` / `О.Д.` [derived] |
| derive-018|0 | derive | sloppy | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Громова Марина` [absent] |
| derive-018|1 | derive | sloppy | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Громова Марина` [absent] |
| derive-018|2 | derive | sloppy | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Громова Марина` [absent] |
| derive-020|2 | derive | voice_raw | clinic_book | — | да | absent:7 | Б9-span | clinic_book.patient.age: агент `` / контроль `45` [absent] |
| derive-022|1 | derive | chat | delivery_cre | — | нет | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Миллер Валерий` [absent] |
| derive-022|2 | derive | chat | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Миллер Валерий` [absent] |
| derive-025|0 | derive | sloppy | upsert | upsert | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `М.А.` / `М.Б.` [derived] |
| derive-025|1 | derive | sloppy | upsert | upsert | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `А.В.` / `М.Б.` [derived] |
| derive-025|2 | derive | sloppy | upsert | upsert | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Л.И.` / `М.Б.` [derived] |
| derive-026|0 | derive | voice_itn | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Миллер Валерий` [absent] |
| derive-026|2 | derive | voice_itn | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Миллер Валерий` [absent] |
| derive-027|0 | derive | voice_itn | callback_sch | callback_sch | да | derived:1 | derived-only | callback_schedule.timezone: `Asia/Yekaterinburg` / `Europe/Samara` [derived] |
| derive-027|1 | derive | voice_itn | callback_sch | — | да | absent:2 | Б10-city | callback_schedule.phone: агент `` / контроль `+79828655311` [absent] |
| derive-027|2 | derive | voice_itn | callback_sch | — | да | absent:2 | Б10-city | callback_schedule.phone: агент `` / контроль `+79828655311` [absent] |
| derive-033|0 | derive | voice_raw | upsert | — | да | absent:7 | Б9-span | crm_upsert_contact.contact.first_name: агент `` / контроль `Кирилл` [absent] |
| derive-033|1 | derive | voice_raw | upsert | upsert | да | other:2 | other | crm_upsert_contact.contact.initials: агент `В.С.` / контроль `К.С.` [other/misderived] |
| derive-033|2 | derive | voice_raw | upsert | — | да | absent:7 | Б9-span | crm_upsert_contact.contact.first_name: агент `` / контроль `Кирилл` [absent] |
| derive-034|0 | derive | voice_raw | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Букин Сергей` [absent] |
| derive-034|1 | derive | voice_raw | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Букин Сергей` [absent] |
| derive-034|2 | derive | voice_raw | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Букин Сергей` [absent] |
| derive-036|0 | derive | voice_itn | clinic_book | clinic_book,clinic_book | да | extra:7 derived:1 validated_refused:1 other:1 | other | clinic_book.patient.birth_date: агент `1992` / контроль `1992-06-02` [validated_refused/date_not_iso8601] |
| derive-036|1 | derive | voice_itn | clinic_book | clinic_book | да | other:2 | other | clinic_book.patient.age: агент `20` / контроль `34` [other/misderived] |
| derive-036|2 | derive | voice_itn | clinic_book | clinic_book,clinic_book | да | extra:7 derived:1 validated_refused:1 other:1 | other | clinic_book.patient.birth_date: агент `1992` / контроль `1992-06-02` [validated_refused/date_not_iso8601] |
| derive-046|0 | derive | voice_itn | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Сергеев Кирилл` [absent] |
| derive-046|1 | derive | voice_itn | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Сергеев Кирилл` [absent] |
| derive-046|2 | derive | voice_itn | delivery_cre | — | да | absent:5 | Б10-city | delivery_create_order.recipient.name: агент `` / контроль `Сергеев Кирилл` [absent] |
| derive-053|0 | derive | chat | upsert | upsert | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-053|1 | derive | chat | upsert | upsert | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `М.Г.` / `И.В.` [derived] |
| derive-053|2 | derive | chat | upsert | upsert | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `С.Я.` / `И.В.` [derived] |
| result_feed-002|0 | result_feed | voice_raw | find | find,clinic_book | да | extra:7 | other | clinic_book.patient.age: агент `13` / контроль `` [extra] |
| result_feed-003|0 | result_feed | chat | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `20` / `65` [derived] |
| result_feed-003|1 | result_feed | chat | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `29` / `65` [derived] |
| result_feed-003|2 | result_feed | chat | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `59` / `65` [derived] |
| result_feed-004|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `66` / `58` [derived] |
| result_feed-004|1 | result_feed | sloppy | find,clinic_book,notify_sms | find,clinic_book,notify_sms | нет | derived:1 | derived-only | clinic_book.patient.age: `65` / `58` [derived] |
| result_feed-004|2 | result_feed | sloppy | find,clinic_book,notify_sms | find,clinic_book | да | absent:1 | other | notify_sms.number: агент `` / контроль `+79821651435` [absent] |
| result_feed-007|0 | result_feed | sloppy | find,clinic_book | find,clinic_book,notify_sms | нет | derived:1 extra:1 | derived-only | notify_sms.number: агент `+79161587676` / контроль `` [extra] |
| result_feed-007|1 | result_feed | sloppy | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79161587676` [absent] |
| result_feed-007|2 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `51` / `31` [derived] |
| result_feed-009|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `51` / `24` [derived] |
| result_feed-009|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `53` / `24` [derived] |
| result_feed-009|2 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `44` / `24` [derived] |
| result_feed-028|0 | result_feed | chat | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `64` / `53` [derived] |
| result_feed-028|1 | result_feed | chat | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `19` / `53` [derived] |
| result_feed-028|2 | result_feed | chat | find,clinic_book | find,clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `9` / контроль `53` [other/misderived] |
| result_feed-031|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | other:1 | other | clinic_book.patient.age: агент `48` / контроль `61` [other/misderived] |
| result_feed-031|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | other | notify_sms.number: агент `` / контроль `+79510443707` [absent] |
| result_feed-031|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book,notify_sms | нет | derived:1 extra:1 | derived-only | notify_sms.number: агент `+79510443707` / контроль `` [extra] |
| result_feed-033|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `44` / `46` [derived] |
| result_feed-033|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `25` / `46` [derived] |
| result_feed-033|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `4` / `46` [derived] |
| result_feed-035|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `64` / `55` [derived] |
| result_feed-035|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `50` / `55` [derived] |
| result_feed-035|2 | result_feed | sloppy | find | find,clinic_book | нет | extra:7 | other | clinic_book.patient.age: агент `45` / контроль `` [extra] |
| validate-000|0 | validate | voice_raw | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `141783` [absent] |
| validate-000|1 | validate | voice_raw | passport_ver | passport_ver | да | absent:1 | other | passport_verify.snils: агент `` / контроль `017-897-237 96` [absent] |
| validate-000|2 | validate | voice_raw | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `141783` [absent] |
| validate-006|0 | validate | voice_itn | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `126611` [absent] |
| validate-006|1 | validate | voice_itn | passport_ver | passport_ver | да | absent:1 | other | passport_verify.snils: агент `` / контроль `530-663-406 64` [absent] |
| validate-006|2 | validate | voice_itn | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `126611` [absent] |
| validate-008|0 | validate | sloppy | passport_ver | — | да | absent:5 | validate-refuse | passport_verify.passport.number: агент `` / контроль `268305` [absent] |
| validate-017|1 | validate | sloppy | — | passport_ver | да | extra:5 | other | passport_verify.passport.number: агент `759266` / контроль `` [extra] |
| validate-017|2 | validate | sloppy | — | passport_ver | да | extra:5 | other | passport_verify.passport.number: агент `759266` / контроль `` [extra] |
| validate-018|0 | validate | chat | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `343601` [absent] |
| validate-018|1 | validate | chat | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `343601` [absent] |
| validate-018|2 | validate | chat | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `343601` [absent] |
| validate-019|0 | validate | voice_raw | passport_ver,passport_ver | — | да | absent:12 | validate-refuse | passport_verify.passport.number: агент `` / контроль `136791` [absent] |
| validate-019|1 | validate | voice_raw | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `136791` [absent] |
| validate-019|2 | validate | voice_raw | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `136791` [absent] |
| validate-020|2 | validate | voice_itn | passport_ver | — | нет | absent:5 | validate-refuse | passport_verify.passport.number: агент `` / контроль `887065` [absent] |
| validate-022|1 | validate | voice_raw | passport_ver,passport_ver | passport_ver | да | absent:6 | other | passport_verify.passport.number: агент `` / контроль `797566` [absent] |
| validate-022|2 | validate | voice_raw | passport_ver | passport_ver | да | validated_refused:1 | other | passport_verify.snils: агент `011-883-127-28` / контроль `011-883-127 28` [validated_refused/snils_format] |
| validate-028|0 | validate | sloppy | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `329642` [absent] |
| validate-028|1 | validate | sloppy | passport_ver | passport_ver | да | absent:1 | other | passport_verify.snils: агент `` / контроль `286-332-010 66` [absent] |
| validate-028|2 | validate | sloppy | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `329642` [absent] |
| validate-029|2 | validate | chat | — | passport_ver | да | extra:5 | other | passport_verify.passport.number: агент `354448` / контроль `` [extra] |
| validate-035|0 | validate | chat | — | passport_ver | да | extra:5 | other | passport_verify.passport.number: агент `202966` / контроль `` [extra] |
| validate-035|1 | validate | chat | passport_ver | — | нет | absent:5 | validate-refuse | passport_verify.passport.number: агент `` / контроль `202966` [absent] |
| validate-035|2 | validate | chat | passport_ver | — | нет | absent:5 | validate-refuse | passport_verify.passport.number: агент `` / контроль `202966` [absent] |
