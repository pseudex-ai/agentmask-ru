# Разбор расхождений I≠C на уровне state — v4-live-medium-s6060

троек с расхождением: 292 из 651 · исключено 429

## Причины

| причина | троек |
|---|---|
| other | 133 |
| derived-only | 100 |
| partial-call | 24 |
| Б8-echo | 14 |
| control_erred | 7 |
| Б9-span | 7 |
| typo-normalised | 5 |
| residual | 1 |
| Б10-city | 1 |

## По видам

| вид | other | derived-only | partial-call | Б8-echo | control_erred | Б9-span | typo-normalised | residual | Б10-city |
|---|---|---|---|---|---|---|---|---|---|
| chain | 34 | 47 | 0 | 0 | 1 | 0 | 2 | 1 | 0 |
| compare | 15 | 0 | 0 | 13 | 0 | 0 | 1 | 0 | 0 |
| container | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| correction | 24 | 25 | 19 | 0 | 1 | 1 | 0 | 0 | 0 |
| decompose | 14 | 0 | 0 | 0 | 1 | 4 | 0 | 0 | 0 |
| derive | 28 | 12 | 0 | 0 | 3 | 2 | 2 | 0 | 0 |
| result_feed | 14 | 16 | 5 | 1 | 0 | 0 | 0 | 0 | 0 |
| summary | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| validate | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Тройки

| тройка | вид | регистр | C вызвал | I вызвал | C′≈C | классы полей | причина | пример: агент / контроль |
|---|---|---|---|---|---|---|---|---|
| chain-000|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-001|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Novikova Natalia` / `Novikova Natalya` [derived] |
| chain-001|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Novikova Natalya` / `Novikova Natalia` [derived] |
| chain-002|0 | chain | voice_itn | find | find,upsert,notify_sms | нет | extra:14 | other | crm_upsert_contact.contact.address.city: агент `Краснодар` / контроль `` [extra] |
| chain-002|1 | chain | voice_itn | find | find,upsert,notify_sms | нет | extra:13 | other | crm_upsert_contact.contact.address.city: агент `Краснодар` / контроль `` [extra] |
| chain-003|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-003|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:3 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1997-10-05` [absent] |
| chain-005|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukova Zinaida` / `Bityukova Zinaida` [derived] |
| chain-005|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-006|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-006|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-007|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukov Oleg` / `Bityukov Oleg` [derived] |
| chain-007|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukov Oleg` / `Bityukov Oleg` [derived] |
| chain-008|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 extra:1 derived:1 | other | crm_upsert_contact.contact.address.street: агент `мончгорская` / контроль `мончегорская` [control_erred/i10] |
| chain-008|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 absent:1 derived:1 | other | crm_upsert_contact.contact.address.street: агент `мончгорская` / контроль `Мончегорская` [control_erred/i10] |
| chain-009|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 absent:1 derived:1 | other | crm_upsert_contact.contact.address.street: агент `чапава` / контроль `чапаева` [control_erred/i10] |
| chain-009|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 derived:1 | other | crm_upsert_contact.contact.address.street: агент `чапава` / контроль `Чапаева` [control_erred/i10] |
| chain-010|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Erokhin Petr` / `Erokhin Pyotr` [derived] |
| chain-010|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | — | other |  |
| chain-011|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-011|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-012|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-012|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-013|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 residual:1 | residual | crm_upsert_contact.contact.address.street: агент `энгельма` / контроль `Энгельса` [control_erred/i10] |
| chain-013|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 derived:1 | other | crm_upsert_contact.contact.address.street: агент `энгельма` / контроль `Энгельса` [control_erred/i10] |
| chain-014|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-014|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-015|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-015|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-016|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-016|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-017|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-017|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-018|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-018|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 extra:1 derived:1 | derived-only | crm_find_contact.query.last_name: агент `` / контроль `Миллер` [absent] |
| chain-020|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Miller Valerii` / `Miller Valeriy` [derived] |
| chain-020|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Miller Valerii` / `Miller Valeriy` [derived] |
| chain-021|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukova Zinaida` / `Bityukova Zinaida` [derived] |
| chain-021|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Н.В.` / `З.Н.` [derived] |
| chain-022|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-022|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-023|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Sokolova Anastasia` / `Sokolova Anna` [derived] |
| chain-023|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-024|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 | control_erred | crm_upsert_contact.contact.address.street: агент `грибоедого` / контроль `Грибоедова` [control_erred/i10] |
| chain-024|1 | chain | voice_raw | find | find,upsert,notify_sms | да | extra:14 | other | crm_upsert_contact.contact.address.city: агент `Воткинск` / контроль `` [extra] |
| chain-025|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-026|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-027|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-027|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-028|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-029|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukov Oleg` / `Bityukov Oleg` [derived] |
| chain-029|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-030|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-030|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-031|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-031|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-033|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-033|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-034|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-034|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-035|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | — | other |  |
| chain-035|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-036|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Zabolotnyj Ruslan` / `Zabolotny Ruslan` [derived] |
| chain-036|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Zabolotnyj Ruslan` / `Zabolotny Ruslan` [derived] |
| chain-037|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-037|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-038|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | — | other |  |
| chain-038|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | — | other |  |
| chain-039|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-040|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-040|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-041|0 | chain | voice_raw | find,find,upsert,notify_sms | find,upsert,notify_sms | да | absent:2 control_erred:1 other:1 | other | crm_find_contact.query.phone: агент `+79120204363` / контроль `+79120244363` [control_erred/i4] |
| chain-041|1 | chain | voice_raw | find,find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 absent:1 other:1 extra:1 | other | crm_find_contact.query.phone: агент `+79120204363` / контроль `+79120244363` [control_erred/i4] |
| chain-042|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | other:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `проезд неерасова` / контроль `проезд Некрасова` [other/unbound] |
| chain-042|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | other:1 extra:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `проезд неерасова` / контроль `проезд некрасова` [other/unbound] |
| chain-043|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 derived:1 | other | crm_upsert_contact.contact.address.street: агент `депуттская` / контроль `Депутатская` [control_erred/i10] |
| chain-043|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 derived:1 | other | crm_upsert_contact.contact.address.street: агент `депуттская` / контроль `Депутатская` [control_erred/i10] |
| chain-044|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:2 derived:2 absent:1 reformatted:1 | other | crm_find_contact.query.last_name: агент `` / контроль `Громова` [absent] |
| chain-044|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | reformatted:1 | other | crm_upsert_contact.contact.address.house: агент `106в` / контроль `106` [reformatted] |
| chain-045|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukova Zinaida` / `Bityukova Zinaida` [derived] |
| chain-045|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukova Zinaida` / `Bityukova Zinaida` [derived] |
| chain-046|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Kukushkin Valerii` / `Kukushkin Valeriy` [derived] |
| chain-046|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:3 derived:1 | derived-only | crm_upsert_contact.contact.birth_date: агент `1970-03-10` / контроль `` [extra] |
| chain-047|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Miller Valerii` / `Miller Valeriy` [derived] |
| chain-047|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Miller Valerii` / `Miller Valeriy` [derived] |
| compare-005|0 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-006|0 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book | нет | absent:11 ref_refused:1 | other | courier_book.address.building: агент `26` / контроль `26 к5` [ref_refused/house_format] |
| compare-006|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 | other | courier_book.address.building: агент `26` / контроль `26к5` [ref_refused/house_format] |
| compare-009|0 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 control_erred:1 | other | courier_book.address.building: агент `187` / контроль `187к5` [ref_refused/house_format] |
| compare-010|1 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | да | other:1 | typo-normalised | courier_book.contact.name: агент `пётр` / контроль `Петр` [other/inflected] |
| compare-011|0 | compare | chat | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `92` [absent] |
| compare-011|1 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `92` [absent] |
| compare-013|1 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-014|0 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book | нет | absent:10 ref_refused:1 | other | courier_book.address.building: агент `12` / контроль `12 корп. 3` [ref_refused/house_format] |
| compare-015|0 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | да | absent:10 | Б8-echo | courier_book.address.building: агент `` / контроль `20к1` [absent] |
| compare-016|0 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | нет | fragment:1 | other | courier_book.contact.name: агент `валерий` / контроль `Валерия` [fragment/given] |
| compare-018|0 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 other_person:1 | Б8-echo | address_suggest.query: агент `Можга улица грибоеодва 24` / контроль `Можга, Грибоедова 24` [other_person/p18.sugg1] |
| compare-018|1 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 other_person:1 | Б8-echo | address_suggest.query: агент `Можга, грибоеодва, 24` / контроль `Можга, улица Грибоедова, 24` [other_person/p18.sugg1] |
| compare-019|0 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | нет | absent:11 | Б8-echo | courier_book.address.building: агент `` / контроль `2а к3` [absent] |
| compare-019|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | да | absent:10 | Б8-echo | courier_book.address.building: агент `` / контроль `2а к3` [absent] |
| compare-024|1 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | нет | — | other |  |
| compare-026|0 | compare | sloppy | address_sugg,courier_book | address_sugg,address_sugg,courier_book | да | other_person:2 extra:1 | Б8-echo | address_suggest.query: агент `Абакан, каллашникова, 10` / контроль `Абакан, Калашникова, 10` [other_person/p26.sugg1] |
| compare-026|1 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 other_person:1 | Б8-echo | address_suggest.query: агент `Абакан, каллашникова, 10` / контроль `Абакан, Калашникова 10` [other_person/p26.sugg1] |
| compare-028|0 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 other_person:1 | Б8-echo | address_suggest.query: агент `Сарапул, шумайова 27 а` / контроль `Сарапул, Шумайлова 27а` [other_person/p28.sugg1] |
| compare-028|1 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | other_person:2 | Б8-echo | address_suggest.query: агент `Сарапул, шумайова 27 а` / контроль `Сарапул, Шумайлова 27а` [other_person/p28.sugg1] |
| compare-029|0 | compare | voice_raw | address_sugg | address_sugg,courier_book | нет | extra:5 | other | courier_book.address.building: агент `122` / контроль `` [extra] |
| compare-029|1 | compare | voice_raw | address_sugg | address_sugg,courier_book | да | extra:5 | other | courier_book.address.building: агент `122` / контроль `` [extra] |
| compare-033|0 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 | other | courier_book.address.building: агент `14` / контроль `14к4` [ref_refused/house_format] |
| compare-033|1 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book | да | absent:5 ref_refused:1 | other | courier_book.address.building: агент `14` / контроль `14к4` [ref_refused/house_format] |
| compare-034|0 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-036|0 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-038|0 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 | other | courier_book.address.building: агент `106` / контроль `106к2` [ref_refused/house_format] |
| compare-041|0 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `20б` [absent] |
| compare-041|1 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `20б` [absent] |
| container-016|0 | container | voice_raw | notify_sms | notify_sms | да | ref_refused:1 | other | notify_sms.number: агент `+79523039099` / контроль `+7952339099` [ref_refused/phone_not_e164] |
| correction-000|0 | correction | voice_raw | upsert,courier_book | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-000|1 | correction | voice_raw | — | courier_book,upsert | нет | extra:16 | other | courier_book.address.building: агент `29` / контроль `` [extra] |
| correction-001|0 | correction | chat | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-001|1 | correction | chat | courier_book | courier_book,upsert | нет | extra:9 | other | crm_upsert_contact.contact.address.city: агент `Воткинск` / контроль `` [extra] |
| correction-002|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Fomin Viacheslav` / контроль `Fomin Vyacheslav` [other/misderived] |
| correction-002|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-003|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | absent:1 | other | crm_upsert_contact.contact.initials: агент `` / контроль `Н.` [absent] |
| correction-003|1 | correction | voice_itn | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Самара` [absent] |
| correction-004|0 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | partial-call | courier_book.address.street: агент `ленна` / контроль `Ленина` [control_erred/i2] |
| correction-004|1 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | partial-call | courier_book.address.street: агент `ленна` / контроль `Ленина` [control_erred/i2] |
| correction-005|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-005|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-006|0 | correction | voice_itn | courier_book,upsert | upsert,courier_book | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `С.` / `А.` [derived] |
| correction-006|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Е.` / `А.` [derived] |
| correction-007|1 | correction | chat | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Самара` [absent] |
| correction-008|0 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | partial-call | courier_book.address.street: агент `вишнвая` / контроль `Вишнёвая` [control_erred/i2] |
| correction-008|1 | correction | voice_raw | courier_book | courier_book,upsert,notify_sms | нет | extra:10 control_erred:1 | other | courier_book.address.street: агент `вишнвая` / контроль `Вишнёвая` [control_erred/i2] |
| correction-009|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Т.` / `И.` [derived] |
| correction-009|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `В.` / `И.` [derived] |
| correction-010|0 | correction | voice_raw | upsert,courier_book | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-010|1 | correction | voice_raw | upsert,courier_book | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Колпино` [absent] |
| correction-011|0 | correction | sloppy | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-011|1 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-012|0 | correction | sloppy | courier_book | courier_book | нет | control_erred:1 | control_erred | courier_book.address.street: агент `комисарова` / контроль `Комиссарова` [control_erred/i2] |
| correction-012|1 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | partial-call | courier_book.address.street: агент `комисарова` / контроль `Комиссарова` [control_erred/i2] |
| correction-013|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Р.` / `И.` [derived] |
| correction-013|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Л.` / `И.` [derived] |
| correction-014|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Т.` / `А.` [derived] |
| correction-014|1 | correction | chat | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-015|0 | correction | voice_itn | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Ижевск` [absent] |
| correction-015|1 | correction | voice_itn | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Ижевск` [absent] |
| correction-016|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-016|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | control_erred:1 absent:1 derived:1 other:1 | other | courier_book.contact.name: агент `фёдорова юлия` / контроль `Юлия Фёдорова` [control_erred/i3] |
| correction-017|0 | correction | voice_raw | courier_book,upsert | upsert,courier_book | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `С.` / `К.` [derived] |
| correction-017|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Я.` / `К.` [derived] |
| correction-018|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | control_erred:2 extra:1 derived:1 | other | courier_book.address.street: агент `челюксинцев` / контроль `Челюскинцев` [control_erred/i2] |
| correction-018|1 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | control_erred:2 absent:1 derived:1 other:1 | other | courier_book.address.street: агент `челюксинцев` / контроль `Челюскинцев` [control_erred/i2] |
| correction-019|0 | correction | chat | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-019|1 | correction | chat | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-020|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | да | control_erred:2 other:1 | other | courier_book.address.street: агент `моннчегорская` / контроль `Мончегорская` [control_erred/i2] |
| correction-020|1 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | control_erred:2 absent:1 derived:1 other:1 | other | courier_book.address.street: агент `моннчегорская` / контроль `Мончегорская` [control_erred/i2] |
| correction-021|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `И.` / `Е.` [derived] |
| correction-021|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `И.` / `Е.` [derived] |
| correction-022|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-022|1 | correction | voice_raw | upsert,courier_book | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-023|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Р.` / `О.` [derived] |
| correction-023|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-024|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-024|1 | correction | chat | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-025|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-025|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| correction-026|0 | correction | voice_raw | upsert,courier_book | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `А.` / `И.` [derived] |
| correction-026|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Х.` / `И.` [derived] |
| correction-027|0 | correction | voice_itn | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-027|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `В.` / `М.` [derived] |
| correction-028|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bitiukova Zinaida` / контроль `Bityukova Zinaida` [other/misderived] |
| correction-029|0 | correction | chat | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Краснодар` [absent] |
| correction-029|1 | correction | chat | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Краснодар` [absent] |
| correction-030|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Kuznetsov Dmitrii` / контроль `Kuznetsov Dmitry` [other/misderived] |
| correction-030|1 | correction | chat | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-031|0 | correction | sloppy | courier_book,upsert | — | нет | absent:16 | Б9-span | courier_book.address.building: агент `` / контроль `33` [absent] |
| correction-031|1 | correction | sloppy | courier_book,upsert | courier_book,courier_book | нет | absent:10 extra:6 stale_value:2 | partial-call | courier_book.address.building: агент `61` / контроль `33` [stale_value/p31.addr] |
| correction-032|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-032|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-033|0 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Voronina Maria` / контроль `Voronina Elena` [other/misderived] |
| correction-033|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `В.` / `Е.` [derived] |
| correction-034|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Vasilev Ivan` / контроль `Vasiliev Ivan` [other/misderived] |
| correction-034|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-035|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-035|1 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| decompose-001|0 | decompose | voice_raw | courier_book | courier_book | да | reformatted:1 other:1 | other | courier_book.address.building: агент `27в` / контроль `27` [reformatted] |
| decompose-001|1 | decompose | voice_raw | courier_book | courier_book | нет | reformatted:1 other:1 | other | courier_book.address.building: агент `27в` / контроль `27` [reformatted] |
| decompose-004|0 | decompose | chat | courier_book | courier_book,courier_book,courier_book | да | extra:13 validated_refused:1 | other | courier_book.address.porch: агент `3к` / контроль `3` [validated_refused/not_an_integer] |
| decompose-004|1 | decompose | chat | courier_book | courier_book,courier_book | да | extra:6 validated_refused:1 | other | courier_book.address.porch: агент `3к` / контроль `3` [validated_refused/not_an_integer] |
| decompose-005|0 | decompose | voice_itn | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `ZINAIDA BITIUKOVA` / контроль `ZINAIDA BITYUKOVA` [other/misderived] |
| decompose-005|1 | decompose | voice_itn | payment_crea | — | да | absent:2 | Б9-span | payment_create.payment_method_data.card.cardholder: агент `` / контроль `ZINAIDA BITYUKOVA` [absent] |
| decompose-007|0 | decompose | clean | courier_book | courier_book | нет | control_erred:1 | control_erred | courier_book.contact.name: агент `Миллер Валерий` / контроль `Валерий Миллер` [control_erred/i2] |
| decompose-008|1 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VIKTORIA VORONINA` / контроль `ELENA VORONINA` [other/misderived] |
| decompose-013|0 | decompose | chat | courier_book | — | да | absent:7 | Б9-span | courier_book.address.building: агент `` / контроль `39` [absent] |
| decompose-013|1 | decompose | chat | courier_book | courier_book | да | validated_refused:1 | other | courier_book.address.porch: агент `6к` / контроль `6` [validated_refused/not_an_integer] |
| decompose-014|1 | decompose | chat | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `KSENIA GROMOVA` / контроль `MARINA GROMOVA` [other/misderived] |
| decompose-017|0 | decompose | sloppy | payment_crea | payment_crea | нет | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VIACHESLAV FOMIN` / контроль `VYACHESLAV FOMIN` [other/misderived] |
| decompose-017|1 | decompose | sloppy | payment_crea | payment_crea | нет | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VYACHESLAV FOMIN` / контроль `VIACHESLAV FOMIN` [other/misderived] |
| decompose-019|0 | decompose | sloppy | courier_book | courier_book,courier_book,courier_book | да | extra:13 validated_refused:1 control_erred:1 | other | courier_book.address.porch: агент `1к` / контроль `1` [validated_refused/not_an_integer] |
| decompose-019|1 | decompose | sloppy | courier_book | — | да | absent:7 | Б9-span | courier_book.address.building: агент `` / контроль `123` [absent] |
| decompose-020|0 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VALERII MILLER` / контроль `VALERIY MILLER` [other/misderived] |
| decompose-020|1 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VALERII MILLER` / контроль `VALERIY MILLER` [other/misderived] |
| decompose-037|0 | decompose | chat | courier_book | courier_book,courier_book,courier_book | да | extra:13 validated_refused:1 | other | courier_book.address.porch: агент `4к` / контроль `4` [validated_refused/not_an_integer] |
| decompose-037|1 | decompose | chat | courier_book | — | да | absent:7 | Б9-span | courier_book.address.building: агент `` / контроль `26` [absent] |
| derive-000|0 | derive | chat | clinic_book | clinic_book | да | — | other |  |
| derive-004|1 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| derive-005|0 | derive | chat | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bitiukova Zinaida` / контроль `Bityukova Zinaida` [other/misderived] |
| derive-005|1 | derive | chat | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bitiukova Zinaida` / контроль `Bityukova Zinaida` [other/misderived] |
| derive-008|0 | derive | voice_raw | clinic_book | clinic_book | да | — | other |  |
| derive-008|1 | derive | voice_raw | clinic_book | clinic_book | нет | — | other |  |
| derive-009|1 | derive | voice_itn | upsert | upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-010|1 | derive | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 | control_erred | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-012|0 | derive | chat | clinic_book | clinic_book | да | — | other |  |
| derive-012|1 | derive | chat | clinic_book | clinic_book | да | — | other |  |
| derive-013|0 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Fomin Viacheslav` / контроль `Fomin Vyacheslav` [other/misderived] |
| derive-013|1 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Fomin Gennady` / контроль `Fomin Vyacheslav` [other/misderived] |
| derive-016|0 | derive | voice_raw | clinic_book | — | да | absent:7 | Б9-span | clinic_book.patient.age: агент `` / контроль `70` [absent] |
| derive-016|1 | derive | voice_raw | clinic_book | — | да | absent:7 | Б9-span | clinic_book.patient.age: агент `` / контроль `70` [absent] |
| derive-018|0 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 | other | delivery_create_order.to_location.address: агент `пер. лениа, 11, кв. 150` / контроль `переулок Ленина, 11, кв. 150` [other/unbound] |
| derive-018|1 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 | typo-normalised | delivery_create_order.to_location.address: агент `переулок лениа, 11, кв. 150` / контроль `переулок Ленина, 11, кв. 150` [other/unbound] |
| derive-020|0 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `46` / `45` [derived] |
| derive-020|1 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `46` / `45` [derived] |
| derive-021|0 | derive | chat | upsert | upsert | нет | extra:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-021|1 | derive | chat | upsert | upsert | да | extra:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-024|0 | derive | voice_raw | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `57` / `56` [derived] |
| derive-024|1 | derive | voice_raw | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `57` / `56` [derived] |
| derive-025|0 | derive | voice_raw | upsert | upsert | нет | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Gromova Lidia` / контроль `Gromova Marina` [other/misderived] |
| derive-027|1 | derive | voice_raw | callback_sch | callback_sch | да | control_erred:1 | control_erred | callback_schedule.phone: агент `+79611669251` / контроль `+79601669251` [control_erred/i2] |
| derive-028|1 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `24` / `25` [derived] |
| derive-032|0 | derive | chat | clinic_book | clinic_book | да | other:1 | other | clinic_book.patient.age: агент `26` / контроль `27` [other/misderived] |
| derive-033|0 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valerii` / контроль `Miller Valeriy` [other/misderived] |
| derive-033|1 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valerii` / контроль `Miller Valeriy` [other/misderived] |
| derive-036|0 | derive | voice_itn | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| derive-036|1 | derive | voice_itn | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| derive-037|0 | derive | voice_itn | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valerii` / контроль `Miller Valeriy` [other/misderived] |
| derive-037|1 | derive | voice_itn | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valerii` / контроль `Miller Valeriy` [other/misderived] |
| derive-040|0 | derive | voice_raw | clinic_book | clinic_book | да | — | other |  |
| derive-040|1 | derive | voice_raw | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `38` / `39` [derived] |
| derive-041|0 | derive | sloppy | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Poliakova Valentina` / контроль `Polyakova Valentina` [other/misderived] |
| derive-041|1 | derive | sloppy | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Poliakova Maria` / контроль `Polyakova Valentina` [other/misderived] |
| derive-044|0 | derive | chat | clinic_book | clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `23` / `24` [derived] |
| derive-044|1 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `23` / `24` [derived] |
| derive-045|0 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bitiukova Zinaida` / контроль `Bityukova Zinaida` [other/misderived] |
| derive-045|1 | derive | voice_raw | upsert | upsert | да | absent:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| derive-046|0 | derive | voice_raw | delivery_cre | delivery_cre | да | other:1 | other | delivery_create_order.to_location.address: агент `улица шумайлого, 26, кв. 208` / контроль `улица Шумайлова, дом 26, квартира 208` [other/unbound] |
| derive-046|1 | derive | voice_raw | delivery_cre | delivery_cre | да | other:1 | typo-normalised | delivery_create_order.to_location.address: агент `ул. шумайлого, д. 26, кв. 208` / контроль `ул. Шумайлова, д. 26, кв. 208` [other/unbound] |
| derive-048|0 | derive | chat | clinic_book | clinic_book | да | — | other |  |
| derive-049|0 | derive | voice_itn | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valeriia` / контроль `Miller Valeria` [other/misderived] |
| derive-049|1 | derive | voice_itn | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valeriia` / контроль `Miller Valeria` [other/misderived] |
| derive-050|1 | derive | chat | delivery_cre | delivery_cre | нет | control_erred:1 | control_erred | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-052|1 | derive | voice_itn | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `64` / `65` [derived] |
| result_feed-003|0 | result_feed | chat | find,clinic_book | find,clinic_book,notify_sms | да | derived:1 extra:1 | derived-only | notify_sms.number: агент `+79030041566` / контроль `` [extra] |
| result_feed-005|0 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | да | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79261234567` [absent] |
| result_feed-005|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79261234567` [absent] |
| result_feed-009|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | other:1 | other | clinic_book.patient.age: агент `27` / контроль `28` [other/misderived] |
| result_feed-009|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-013|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book,notify_sms | нет | extra:1 | other | notify_sms.number: агент `+79998831789` / контроль `` [extra] |
| result_feed-013|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `64` / `65` [derived] |
| result_feed-014|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| result_feed-015|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `56` / `57` [derived] |
| result_feed-015|1 | result_feed | sloppy | find,clinic_book,notify_sms | find,clinic_book | да | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79129876543` [absent] |
| result_feed-016|0 | result_feed | voice_raw | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79778446323` [absent] |
| result_feed-016|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book,notify_sms | нет | extra:1 | other | notify_sms.number: агент `+79778446323` / контроль `` [extra] |
| result_feed-017|0 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79993861689` [absent] |
| result_feed-017|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79993861689` [absent] |
| result_feed-019|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-019|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | other:1 | other | clinic_book.patient.age: агент `27` / контроль `28` [other/misderived] |
| result_feed-020|0 | result_feed | chat | find,clinic_book,notify_sms | find | нет | absent:8 | Б8-echo | clinic_book.patient.age: агент `` / контроль `45` [absent] |
| result_feed-020|1 | result_feed | chat | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `46` / `45` [derived] |
| result_feed-021|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `33` / `32` [derived] |
| result_feed-021|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `33` / `32` [derived] |
| result_feed-023|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-023|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-026|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-026|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `51` / `52` [derived] |
| result_feed-027|0 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book,notify_sms | нет | — | other |  |
| result_feed-027|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | да | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79035416931` [absent] |
| result_feed-028|0 | result_feed | chat | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-028|1 | result_feed | chat | find,clinic_book | find,clinic_book,notify_sms | нет | derived:1 extra:1 | derived-only | notify_sms.number: агент `+79099042924` / контроль `` [extra] |
| result_feed-029|1 | result_feed | chat | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-031|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `29` / `30` [derived] |
| result_feed-032|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book,notify_sms | да | extra:1 | other | notify_sms.number: агент `+79512022704` / контроль `` [extra] |
| result_feed-032|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `27` / `26` [derived] |
| result_feed-033|0 | result_feed | chat | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `57` / `56` [derived] |
| result_feed-033|1 | result_feed | chat | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `57` / `56` [derived] |
| result_feed-034|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-034|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79097619209` [absent] |
| summary-011|0 | summary | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 | control_erred | delivery_create_order.recipient.phones[0].number: агент `+79279061650` / контроль `+79279661650` [control_erred/i2] |
| summary-018|0 | summary | voice_raw | find,delivery_cre | — | да | absent:6 | Б10-city | crm_find_contact.query.phone: агент `` / контроль `+79992635617` [absent] |
| validate-017|0 | validate | voice_raw | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `181-547-959 03` / контроль `` [extra] |
| validate-029|1 | validate | chat | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `013-184-880 31` / контроль `` [extra] |
| validate-032|1 | validate | sloppy | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `513-209-526 47` / контроль `` [extra] |
