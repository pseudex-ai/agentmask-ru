# Разбор расхождений I≠C на уровне state — v4-live-small

троек с расхождением: 195 из 261 · исключено 2

## Причины

| причина | троек |
|---|---|
| other | 80 |
| derived-only | 59 |
| Б8-echo | 29 |
| typo-normalised | 9 |
| partial-call | 4 |
| residual | 4 |
| Б9-span | 3 |
| control_erred | 3 |
| case-only | 2 |
| validate-refuse | 2 |

## По видам

| вид | other | derived-only | Б8-echo | typo-normalised | partial-call | residual | Б9-span | control_erred | case-only | validate-refuse |
|---|---|---|---|---|---|---|---|---|---|---|
| chain | 20 | 15 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| compare | 4 | 0 | 27 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| correction | 21 | 4 | 0 | 2 | 3 | 1 | 3 | 0 | 0 | 0 |
| decompose | 9 | 0 | 0 | 2 | 0 | 3 | 0 | 3 | 0 | 0 |
| derive | 19 | 22 | 0 | 1 | 0 | 0 | 0 | 0 | 2 | 0 |
| result_feed | 6 | 18 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| validate | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |

## Тройки

| тройка | вид | регистр | C вызвал | I вызвал | C′≈C | классы полей | причина | пример: агент / контроль |
|---|---|---|---|---|---|---|---|---|
| chain-000|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-003|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Poliakova Valentina` / `Polyakova Valentina` [derived] |
| chain-003|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Poliakova Valentina` / `Polyakova Valentina` [derived] |
| chain-003|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:3 derived:1 | derived-only | crm_upsert_contact.contact.birth_date: агент `` / контроль `1974-10-08` [absent] |
| chain-004|0 | chain | voice_raw | find,find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:2 control_erred:1 | other | crm_find_contact.query.phone: агент `+79508008881` / контроль `+79505800881` [control_erred/i4] |
| chain-004|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 extra:1 | other | crm_find_contact.query.last_name: агент `` / контроль `Захаров` [absent] |
| chain-004|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:2 extra:1 derived:1 | derived-only | crm_find_contact.query.last_name: агент `` / контроль `Захаров` [absent] |
| chain-008|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-008|1 | chain | sloppy | find,upsert,notify_sms | find | нет | absent:13 | Б8-echo | crm_upsert_contact.contact.address.city: агент `` / контроль `Самара` [absent] |
| chain-008|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Gromov Dmitry` / `Gromov Artem` [derived] |
| chain-009|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-013|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-013|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-014|0 | chain | voice_raw | find,upsert,notify_sms | find | нет | absent:13 | Б8-echo | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| chain-014|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Kuznetsov Dmitrij` / `Kuznetsov Dmitry` [derived] |
| chain-014|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-015|0 | chain | voice_itn | find | find,upsert,notify_sms | нет | extra:14 | other | crm_upsert_contact.contact.address.city: агент `Сортавала` / контроль `` [extra] |
| chain-015|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-015|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-021|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-021|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | — | other |  |
| chain-021|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-024|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-024|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-026|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | reformatted:1 absent:1 derived:1 | other | crm_upsert_contact.contact.address.house: агент `122` / контроль `118` [reformatted] |
| chain-026|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-026|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-029|0 | chain | voice_itn | find | find,upsert,notify_sms | нет | extra:14 | other | crm_upsert_contact.contact.address.city: агент `Абакан` / контроль `` [extra] |
| chain-029|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Sergeev Vitaly` / `Sergeev Kirill` [derived] |
| chain-029|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-031|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-031|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-031|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-033|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Vasilev Dmitry` / `Vasiliev Ivan` [derived] |
| chain-038|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-043|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Lebedev Maksim` / `Lebedev Maxim` [derived] |
| chain-043|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| compare-005|0 | compare | sloppy | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `160` [absent] |
| compare-005|1 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `160` [absent] |
| compare-005|2 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | нет | — | other |  |
| compare-009|0 | compare | voice_itn | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `10` [absent] |
| compare-009|1 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `10` [absent] |
| compare-009|2 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `10` [absent] |
| compare-011|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | да | absent:11 | Б8-echo | courier_book.address.building: агент `` / контроль `3к5` [absent] |
| compare-011|2 | compare | voice_raw | address_sugg | address_sugg,address_sugg,courier_book | нет | extra:6 | other | address_suggest.query: агент `Глазов химзаводская 3в` / контроль `` [extra] |
| compare-014|0 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | other:1 | typo-normalised | courier_book.contact.name: агент `марин` / контроль `Марина` [other/inflected] |
| compare-014|1 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | other:1 | typo-normalised | courier_book.contact.name: агент `марин` / контроль `Марина` [other/inflected] |
| compare-014|2 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | composed:1 other:1 | typo-normalised | courier_book.address.street: агент `Краснодарский край, г Краснодар, Вишн…` / контроль `Вишнёвая` [composed] |
| compare-017|0 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `33` [absent] |
| compare-017|1 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `33` [absent] |
| compare-017|2 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `33` [absent] |
| compare-028|0 | compare | voice_itn | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `155` [absent] |
| compare-028|1 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `155` [absent] |
| compare-028|2 | compare | voice_itn | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `155` [absent] |
| compare-029|0 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `100` [absent] |
| compare-029|1 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `100` [absent] |
| compare-029|2 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `100` [absent] |
| compare-034|0 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book,courier_book,courier_book | нет | other:3 reformatted:1 | other | courier_book.address.building: агент `65 корп. 1` / контроль `65 корпус 1` [reformatted] |
| compare-034|1 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book,courier_book,courier_book | нет | other:3 control_erred:1 | other | courier_book.contact.name: агент `петра` / контроль `Пётр` [other/inflected] |
| compare-034|2 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book,courier_book | да | extra:6 other:2 validated_refused:1 | typo-normalised | courier_book.contact.name: агент `петра` / контроль `Петр` [other/inflected] |
| compare-035|0 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `79` [absent] |
| compare-035|2 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `79` [absent] |
| compare-036|0 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `82` [absent] |
| compare-036|1 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `82` [absent] |
| compare-036|2 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `82` [absent] |
| compare-039|0 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `121` [absent] |
| compare-040|0 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `26` [absent] |
| compare-040|1 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `26` [absent] |
| compare-040|2 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `26` [absent] |
| compare-041|0 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `148` [absent] |
| compare-041|1 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `148` [absent] |
| compare-041|2 | compare | voice_itn | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `148` [absent] |
| correction-010|0 | correction | chat | courier_book | courier_book,upsert | да | extra:10 | other | crm_upsert_contact.contact.address.city: агент `Ижевск` / контроль `` [extra] |
| correction-010|1 | correction | chat | courier_book | courier_book,upsert | да | extra:9 | other | crm_upsert_contact.contact.address.city: агент `Ижевск` / контроль `` [extra] |
| correction-010|2 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Erokhin Petr` / контроль `Erokhin Pyotr` [other/misderived] |
| correction-012|0 | correction | chat | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Можга` [absent] |
| correction-012|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `И.` / `О.` [derived] |
| correction-012|2 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Т.` / `О.` [derived] |
| correction-013|0 | correction | sloppy | courier_book,upsert | upsert,courier_book | нет | derived:2 control_erred:1 other:1 | other | courier_book.contact.name: агент `миллер валерия` / контроль `Валерия Миллер` [control_erred/i3] |
| correction-013|1 | correction | sloppy | upsert,courier_book | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-013|2 | correction | sloppy | upsert,courier_book | courier_book,upsert | нет | derived:2 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valeriia` / контроль `Miller Valeria` [other/misderived] |
| correction-016|0 | correction | chat | courier_book | courier_book | нет | — | other |  |
| correction-016|1 | correction | chat | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Колпино` [absent] |
| correction-016|2 | correction | chat | upsert,courier_book | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Колпино` [absent] |
| correction-017|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Fedorova Viktoria` / контроль `Fedorova Yulia` [other/misderived] |
| correction-017|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | control_erred:1 absent:1 derived:1 other:1 | other | courier_book.contact.name: агент `фёдорова юлия` / контроль `Юлия Фёдорова` [control_erred/i3] |
| correction-017|2 | correction | voice_itn | courier_book,upsert | upsert,courier_book | да | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Fyodorova Yuliya` / контроль `Fedorova Yulia` [other/misderived] |
| correction-018|0 | correction | voice_raw | courier_book,upsert | — | нет | absent:16 | Б9-span | courier_book.address.building: агент `` / контроль `177` [absent] |
| correction-018|1 | correction | voice_raw | courier_book,upsert | — | нет | absent:16 | Б9-span | courier_book.address.building: агент `` / контроль `177` [absent] |
| correction-021|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-021|1 | correction | sloppy | courier_book,upsert | courier_book,upsert | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-021|2 | correction | sloppy | courier_book | upsert,courier_book | нет | extra:9 | other | crm_upsert_contact.contact.address.city: агент `Можга` / контроль `` [extra] |
| correction-024|0 | correction | voice_raw | — | courier_book,upsert | нет | extra:16 | other | courier_book.address.building: агент `155` / контроль `` [extra] |
| correction-024|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | absent:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-024|2 | correction | voice_raw | upsert,courier_book | upsert,courier_book | нет | control_erred:2 derived:1 | other | crm_upsert_contact.contact.phone: агент `+79609078592` / контроль `+79699078592` [control_erred/i4] |
| correction-025|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | reformatted:1 derived:1 other:1 | other | courier_book.address.building: агент `125` / контроль `37` [reformatted] |
| correction-025|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Gromova Ludmila` / контроль `Gromova Marina` [other/misderived] |
| correction-025|2 | correction | voice_itn | upsert,courier_book | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `В.` / `М.` [derived] |
| correction-030|0 | correction | voice_raw | courier_book | courier_book,upsert | нет | extra:9 other:2 | typo-normalised | courier_book.address.street: агент `дом сто восемьдесят пять квартира пят…` / контроль `Мончегорская` [other/unbound] |
| correction-030|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | other:5 extra:1 derived:1 | typo-normalised | courier_book.address.street: агент `дом сто восемьдесят пять квартира пят…` / контроль `Мончегорская` [other/unbound] |
| correction-030|2 | correction | voice_raw | upsert,courier_book | — | нет | absent:16 | Б9-span | crm_upsert_contact.contact.address.city: агент `` / контроль `Сарапул` [absent] |
| correction-031|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bitiukov Oleg` / контроль `Bityukov Oleg` [other/misderived] |
| correction-031|1 | correction | sloppy | upsert,courier_book | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-031|2 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-032|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | residual:1 absent:1 derived:1 | residual | courier_book.address.street: агент `Жасминовая` / контроль `Кирочная` [residual] |
| correction-032|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | extra:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| decompose-007|0 | decompose | sloppy | courier_book | courier_book | да | other:1 | typo-normalised | courier_book.address.street: агент `проезд неркасова` / контроль `проезд Некрасова` [other/unbound] |
| decompose-007|1 | decompose | sloppy | courier_book | courier_book | нет | other:1 residual:1 | residual | courier_book.address.street: агент `неркасова проезд` / контроль `проезд Некрасова` [other/unbound] |
| decompose-007|2 | decompose | sloppy | courier_book | courier_book | да | other:2 | typo-normalised | courier_book.address.street: агент `проезд неркасова` / контроль `проезд Некрасова` [other/unbound] |
| decompose-008|1 | decompose | sloppy | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `PETR EROXIN` / контроль `PETR EROKHIN` [other/misderived] |
| decompose-016|0 | decompose | clean | courier_book | courier_book | да | composed:1 | other | courier_book.address.street: агент `141 подъезд 5 кв. 175` / контроль `Маяковского` [composed] |
| decompose-016|1 | decompose | clean | courier_book | courier_book | да | composed:1 | other | courier_book.address.street: агент `141 подъезд 5 кв. 175` / контроль `Маяковского` [composed] |
| decompose-016|2 | decompose | clean | courier_book | courier_book | да | composed:1 | other | courier_book.address.street: агент `141 подъезд 5 кв. 175` / контроль `Маяковского` [composed] |
| decompose-019|0 | decompose | sloppy | courier_book | courier_book | да | control_erred:1 | control_erred | courier_book.address.street: агент `луогвая` / контроль `Луговая` [control_erred/i1] |
| decompose-019|1 | decompose | sloppy | courier_book | courier_book | да | control_erred:1 | control_erred | courier_book.address.street: агент `луогвая` / контроль `Луговая` [control_erred/i1] |
| decompose-025|0 | decompose | voice_raw | — | courier_book | нет | extra:7 | other | courier_book.address.building: агент `17` / контроль `` [extra] |
| decompose-025|2 | decompose | voice_raw | courier_book | courier_book | нет | control_erred:1 | control_erred | courier_book.contact.phone: агент `+79505556677` / контроль `+79005556677` [control_erred/i3] |
| decompose-029|1 | decompose | clean | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VALERII MILLER` / контроль `VALERIY MILLER` [other/misderived] |
| decompose-029|2 | decompose | clean | — | payment_crea | нет | extra:2 | other | payment_create.payment_method_data.card.cardholder: агент `VALERII MILLER` / контроль `` [extra] |
| decompose-033|0 | decompose | voice_raw | passport_ver | passport_ver | да | control_erred:1 residual:1 validated_refused:1 | residual | passport_verify.passport.series: агент `4019` / контроль `4919` [control_erred/i1] |
| decompose-033|1 | decompose | voice_raw | passport_ver | passport_ver | да | control_erred:1 residual:1 validated_refused:1 | residual | passport_verify.passport.series: агент `4019` / контроль `4919` [control_erred/i1] |
| decompose-033|2 | decompose | voice_raw | passport_ver | passport_ver | да | control_erred:1 composed:1 validated_refused:1 | other | passport_verify.passport.series: агент `4019` / контроль `4919` [control_erred/i1] |
| decompose-041|1 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VLADISLAV MESHCHERYAKOV` / контроль `VLADISLAV ZAKHAROV` [other/misderived] |
| derive-002|0 | derive | chat | delivery_cre | delivery_cre | да | other:1 derived:1 | other | delivery_create_order.recipient.name: агент `фёдоров юлий` / контроль `Фёдорова Юлия` [other/inflected] |
| derive-002|1 | derive | chat | delivery_cre | delivery_cre | да | other:1 derived:1 | other | delivery_create_order.recipient.name: агент `фёдоров юлий` / контроль `Фёдорова Юлия` [other/inflected] |
| derive-002|2 | derive | chat | delivery_cre | delivery_cre | да | other:1 derived:1 | other | delivery_create_order.recipient.name: агент `фёдоров юлий` / контроль `Фёдорова Юлия` [other/inflected] |
| derive-007|0 | derive | voice_itn | callback_sch | callback_sch | да | derived:1 | derived-only | callback_schedule.timezone: `Europe/Moscow` / `Europe/Samara` [derived] |
| derive-007|1 | derive | voice_itn | callback_sch | callback_sch | да | derived:1 | derived-only | callback_schedule.timezone: `Europe/Moscow` / `Europe/Samara` [derived] |
| derive-007|2 | derive | voice_itn | callback_sch | callback_sch | да | derived:1 | derived-only | callback_schedule.timezone: `Europe/Moscow` / `Europe/Samara` [derived] |
| derive-008|0 | derive | sloppy | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `36` / `28` [derived] |
| derive-008|1 | derive | sloppy | clinic_book | clinic_book | да | other:1 | other | clinic_book.patient.age: агент `9` / контроль `28` [other/misderived] |
| derive-008|2 | derive | sloppy | clinic_book | clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `44` / `28` [derived] |
| derive-013|0 | derive | voice_raw | upsert | upsert | нет | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bukin Sergei` / контроль `Bukin Sergey` [other/misderived] |
| derive-013|1 | derive | voice_raw | upsert | upsert | нет | extra:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-013|2 | derive | voice_raw | upsert | upsert | нет | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bukin Sergei` / контроль `Bukin Sergey` [other/misderived] |
| derive-014|0 | derive | chat | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `188300` / `443000` [derived] |
| derive-014|1 | derive | chat | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `301480` / `443099` [derived] |
| derive-014|2 | derive | chat | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `186790` / `443099` [derived] |
| derive-017|1 | derive | sloppy | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Kuznetsova Klavdia` / контроль `Kuznetsova Olga` [other/misderived] |
| derive-017|2 | derive | sloppy | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Kuzneczova Olga` / контроль `Kuznetsova Olga` [other/misderived] |
| derive-018|0 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 derived:1 | other | delivery_create_order.recipient.name: агент `громов марин` / контроль `Громова Марина` [other/inflected] |
| derive-018|1 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 derived:1 | other | delivery_create_order.recipient.name: агент `громов марин` / контроль `Громова Марина` [other/inflected] |
| derive-018|2 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 derived:1 | other | delivery_create_order.recipient.name: агент `громов марин` / контроль `Громова Марина` [other/inflected] |
| derive-020|0 | derive | voice_raw | clinic_book | clinic_book | да | other:1 | case-only | clinic_book.patient.last_name: агент `родилсяя` / контроль `Миллер` [other/inflected] |
| derive-020|2 | derive | voice_raw | clinic_book | clinic_book | да | other:1 | case-only | clinic_book.patient.last_name: агент `родилсяя` / контроль `Миллер` [other/inflected] |
| derive-022|0 | derive | chat | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `301470` / `443022` [derived] |
| derive-022|1 | derive | chat | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `155800` / `443010` [derived] |
| derive-022|2 | derive | chat | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `155800` / `443010` [derived] |
| derive-026|0 | derive | voice_itn | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `301440` / `427960` [derived] |
| derive-026|1 | derive | voice_itn | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `601293` / `427960` [derived] |
| derive-026|2 | derive | voice_itn | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `187550` / `427960` [derived] |
| derive-027|0 | derive | voice_itn | callback_sch | callback_sch | да | derived:1 | derived-only | callback_schedule.timezone: `Europe/Moscow` / `Europe/Samara` [derived] |
| derive-027|1 | derive | voice_itn | callback_sch | callback_sch | да | derived:1 | derived-only | callback_schedule.timezone: `Europe/Moscow` / `Europe/Samara` [derived] |
| derive-027|2 | derive | voice_itn | callback_sch | callback_sch | да | derived:1 | derived-only | callback_schedule.timezone: `Europe/Moscow` / `Europe/Samara` [derived] |
| derive-030|1 | derive | voice_raw | delivery_cre | delivery_cre | да | other:1 derived:1 | typo-normalised | delivery_create_order.to_location.address: агент `ул. зарчная, д. 97в, кв. 234` / контроль `ул. Заречная, д. 97в, кв. 234` [other/unbound] |
| derive-030|2 | derive | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 other:1 derived:1 | other | delivery_create_order.recipient.phones[0].number: агент `+79628889900` / контроль `+79628889890` [control_erred/i2] |
| derive-033|0 | derive | voice_raw | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-033|1 | derive | voice_raw | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-033|2 | derive | voice_raw | upsert | upsert | да | absent:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-034|0 | derive | voice_raw | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `301462` / `427790` [derived] |
| derive-034|1 | derive | voice_raw | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `188300` / `427790` [derived] |
| derive-034|2 | derive | voice_raw | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `155800` / `427790` [derived] |
| derive-036|0 | derive | voice_itn | clinic_book | clinic_book,clinic_book,clinic_book | да | extra:14 derived:1 validated_refused:1 other:1 | other | clinic_book.patient.birth_date: агент `1992` / контроль `1992-06-02` [validated_refused/date_not_iso8601] |
| derive-036|1 | derive | voice_itn | clinic_book | clinic_book,clinic_book | да | extra:7 derived:1 validated_refused:1 other:1 | other | clinic_book.patient.birth_date: агент `1992` / контроль `1992-06-02` [validated_refused/date_not_iso8601] |
| derive-036|2 | derive | voice_itn | clinic_book | clinic_book,clinic_book,clinic_book,clinic_book | да | extra:21 other:1 validated_refused:1 | other | clinic_book.patient.age: агент `14` / контроль `34` [other/misderived] |
| derive-046|0 | derive | voice_itn | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `301454` / `186790` [derived] |
| derive-046|2 | derive | voice_itn | delivery_cre | delivery_cre | да | derived:1 | derived-only | delivery_create_order.to_location.postal_code: `188300` / `186790` [derived] |
| result_feed-002|1 | result_feed | voice_raw | find | find,clinic_book | да | extra:7 | other | clinic_book.patient.age: агент `18` / контроль `` [extra] |
| result_feed-003|0 | result_feed | chat | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `25` / `65` [derived] |
| result_feed-003|1 | result_feed | chat | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `4` / `65` [derived] |
| result_feed-003|2 | result_feed | chat | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `57` / `65` [derived] |
| result_feed-004|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `39` / `58` [derived] |
| result_feed-004|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `8` / `58` [derived] |
| result_feed-004|2 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `35` / `58` [derived] |
| result_feed-007|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `6` / `31` [derived] |
| result_feed-007|1 | result_feed | sloppy | find,clinic_book,notify_sms | find,clinic_book | нет | other:1 absent:1 | partial-call | clinic_book.patient.age: агент `47` / контроль `31` [other/misderived] |
| result_feed-007|2 | result_feed | sloppy | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79161587676` [absent] |
| result_feed-009|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `56` / `24` [derived] |
| result_feed-009|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `57` / `24` [derived] |
| result_feed-009|2 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `8` / `24` [derived] |
| result_feed-028|0 | result_feed | chat | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `8` / `53` [derived] |
| result_feed-028|1 | result_feed | chat | find | find,clinic_book | нет | extra:7 | other | clinic_book.patient.age: агент `63` / контроль `` [extra] |
| result_feed-028|2 | result_feed | chat | find,clinic_book,notify_sms | find,clinic_book,notify_sms | нет | other:1 | other | clinic_book.patient.age: агент `37` / контроль `53` [other/misderived] |
| result_feed-031|0 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79510443707` [absent] |
| result_feed-031|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | other:1 | other | clinic_book.patient.age: агент `5` / контроль `61` [other/misderived] |
| result_feed-031|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | other:1 | other | clinic_book.patient.age: агент `16` / контроль `61` [other/misderived] |
| result_feed-033|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `6` / контроль `46` [other/misderived] |
| result_feed-033|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79876955394` [absent] |
| result_feed-033|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `28` / `46` [derived] |
| result_feed-035|0 | result_feed | sloppy | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79777778899` [absent] |
| result_feed-035|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `22` / `55` [derived] |
| result_feed-035|2 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `49` / `55` [derived] |
| validate-000|0 | validate | voice_raw | passport_ver,passport_ver | — | да | absent:12 | validate-refuse | passport_verify.passport.number: агент `` / контроль `141783` [absent] |
| validate-018|0 | validate | chat | passport_ver | — | да | absent:6 | validate-refuse | passport_verify.passport.number: агент `` / контроль `343601` [absent] |
| validate-019|0 | validate | voice_raw | passport_ver | passport_ver | да | absent:1 | other | passport_verify.snils: агент `` / контроль `252-814-525 64` [absent] |
