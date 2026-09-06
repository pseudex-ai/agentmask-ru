# Разбор расхождений I≠C на уровне state — v4-live-medium-s6060-r2

троек с расхождением: 573 из 1419 · исключено 3

## Причины

| причина | троек |
|---|---|
| other | 253 |
| engine-fault | 164 |
| typo-normalised | 53 |
| derived-only | 35 |
| partial-call | 19 |
| Б8-echo | 18 |
| control_erred | 16 |
| control-partial | 13 |
| residual | 1 |
| case-only | 1 |

## По видам

| вид | other | engine-fault | typo-normalised | derived-only | partial-call | Б8-echo | control_erred | control-partial | residual | case-only |
|---|---|---|---|---|---|---|---|---|---|---|
| chain | 52 | 0 | 17 | 24 | 0 | 1 | 0 | 2 | 0 | 0 |
| compare | 1 | 52 | 6 | 0 | 0 | 17 | 0 | 0 | 0 | 0 |
| container | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| correction | 22 | 59 | 2 | 0 | 12 | 0 | 0 | 3 | 0 | 0 |
| crm_note | 30 | 0 | 1 | 0 | 2 | 0 | 0 | 1 | 0 | 0 |
| decompose | 6 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| derive | 22 | 5 | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| lookup_list | 44 | 0 | 10 | 10 | 0 | 0 | 0 | 0 | 1 | 0 |
| result_feed | 26 | 30 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| send_template | 37 | 3 | 3 | 0 | 4 | 0 | 16 | 5 | 0 | 0 |
| summary | 1 | 0 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| validate | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Тройки

| тройка | вид | регистр | C вызвал | I вызвал | C′≈C | классы полей | причина | пример: агент / контроль |
|---|---|---|---|---|---|---|---|---|
| chain-000|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-000|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:3 derived:1 | derived-only | crm_upsert_contact.contact.birth_date: агент `` / контроль `1987-03-14` [absent] |
| chain-001|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:3 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1973-09-10` [absent] |
| chain-001|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-002|0 | chain | voice_itn | find | find,upsert,notify_sms | нет | extra:14 | control-partial | crm_upsert_contact.contact.address.city: агент `Краснодар` / контроль `` [extra] |
| chain-002|2 | chain | voice_itn | find | find,upsert,notify_sms | нет | extra:14 | control-partial | crm_upsert_contact.contact.address.city: агент `Краснодар` / контроль `` [extra] |
| chain-003|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-003|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-004|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-005|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-005|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-005|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-006|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:3 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1993-07-23` [absent] |
| chain-006|1 | chain | chat | find,upsert,notify_sms | find | да | absent:14 | Б8-echo | crm_upsert_contact.contact.address.city: агент `` / контроль `Колпино` [absent] |
| chain-006|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-007|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-007|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-008|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `мончгорская` / контроль `Мончегорская` [control_erred/i10] |
| chain-008|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `мончгорская` / контроль `Мончегорская` [control_erred/i10] |
| chain-008|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 absent:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `мончгорская` / контроль `Мончегорская` [control_erred/i10] |
| chain-009|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `чапава` / контроль `Чапаева` [control_erred/i10] |
| chain-009|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 extra:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `чапава` / контроль `чапаева` [control_erred/i10] |
| chain-009|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 absent:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `чапава` / контроль `Чапаева` [control_erred/i10] |
| chain-010|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-010|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-010|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Erokhin Petr` / `Yerokhin Pyotr` [derived] |
| chain-013|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 absent:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `энгельма` / контроль `Энгельса` [control_erred/i10] |
| chain-013|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-013|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `энгельма` / контроль `Энгельса` [control_erred/i10] |
| chain-014|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-014|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-014|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Kuznetsov Dmitriy` / `Kuznetsov Dmitry` [derived] |
| chain-016|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-017|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Gromov Artem` / `Gromov Artyom` [derived] |
| chain-018|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:2 extra:1 | other | crm_find_contact.query.last_name: агент `` / контроль `Миллер` [absent] |
| chain-018|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-020|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-020|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-021|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-021|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:3 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1959-03-22` [absent] |
| chain-021|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-023|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-024|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 extra:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `грибоедого` / контроль `Грибоедова` [control_erred/i10] |
| chain-024|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `грибоедого` / контроль `Грибоедова` [control_erred/i10] |
| chain-024|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 absent:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `грибоедого` / контроль `Грибоедова` [control_erred/i10] |
| chain-025|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-025|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-026|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-027|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-027|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-028|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-029|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-030|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-030|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-030|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-031|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-031|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-031|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-032|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-032|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-033|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Kuznetsov Dmitriy` / `Kuznetsov Dmitry` [derived] |
| chain-033|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-034|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-035|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Sokolova Maya` / `Sokolova Anna` [derived] |
| chain-036|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-036|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-036|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-037|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-037|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-038|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-038|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-038|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-039|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-039|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-039|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-040|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-040|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-040|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bukin Sergey` / `Bukin Sergei` [derived] |
| chain-041|0 | chain | voice_raw | find,find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:2 control_erred:1 other:1 | other | crm_find_contact.query.phone: агент `+79120204363` / контроль `+79120244363` [control_erred/i4] |
| chain-041|1 | chain | voice_raw | find,find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 absent:1 other:1 | other | crm_find_contact.query.phone: агент `+79120204363` / контроль `+79120244363` [control_erred/i4] |
| chain-041|2 | chain | voice_raw | find,find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 absent:1 other:1 | other | crm_find_contact.query.phone: агент `+79120204363` / контроль `+79120244363` [control_erred/i4] |
| chain-042|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | other:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `проезд неерасова` / контроль `проезд Некрасова` [other/unbound] |
| chain-042|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | other:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `проезд неерасова` / контроль `проезд Некрасова` [other/unbound] |
| chain-042|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:3 other:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `проезд неерасова` / контроль `проезд Некрасова` [other/unbound] |
| chain-043|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 absent:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `депуттская` / контроль `Депутатская` [control_erred/i10] |
| chain-043|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 absent:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `депуттская` / контроль `Депутатская` [control_erred/i10] |
| chain-043|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 absent:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `депуттская` / контроль `Депутатская` [control_erred/i10] |
| chain-044|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 extra:1 reformatted:1 | other | crm_find_contact.query.last_name: агент `` / контроль `Громова` [absent] |
| chain-044|1 | chain | voice_raw | find,upsert,notify_sms | find,find,upsert,notify_sms | да | absent:2 extra:2 reformatted:1 | other | crm_find_contact.query.last_name: агент `` / контроль `Громова` [absent] |
| chain-044|2 | chain | voice_raw | find,upsert,notify_sms | find,find,upsert,notify_sms | нет | extra:4 reformatted:1 | other | crm_upsert_contact.contact.address.house: агент `106в` / контроль `106` [reformatted] |
| chain-045|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:3 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1975-11-02` [absent] |
| chain-046|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Kukushkin Valeriy` / `Kukushkin Valery` [derived] |
| chain-046|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-047|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-047|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-047|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Miller Valeriy` / `Miller Valery` [derived] |
| compare-000|0 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | нет | — | engine-fault |  |
| compare-000|1 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | да | — | engine-fault |  |
| compare-000|2 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `183` / контроль `` [extra] |
| compare-001|2 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | да | — | engine-fault |  |
| compare-002|1 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | да | reformatted:1 | engine-fault | courier_book.address.building: агент `177` / контроль `21` [reformatted] |
| compare-002|2 | compare | chat | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `21` / контроль `` [extra] |
| compare-004|0 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `181` / контроль `` [extra] |
| compare-005|0 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | нет | — | engine-fault |  |
| compare-006|0 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | да | ref_refused:1 | engine-fault | courier_book.address.building: агент `26` / контроль `26к5` [ref_refused/house_format] |
| compare-006|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | нет | ref_refused:1 absent:1 | engine-fault | courier_book.address.building: агент `26` / контроль `26к5` [ref_refused/house_format] |
| compare-006|2 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 | engine-fault | courier_book.address.building: агент `26` / контроль `26к5` [ref_refused/house_format] |
| compare-007|0 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `21б` [absent] |
| compare-007|1 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 reformatted:1 | engine-fault | courier_book.address.building: агент `59` / контроль `21б` [reformatted] |
| compare-007|2 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `21б` [absent] |
| compare-008|0 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `19` / контроль `` [extra] |
| compare-008|2 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `19` / контроль `` [extra] |
| compare-009|0 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 other:1 | engine-fault | courier_book.address.building: агент `187` / контроль `187к5` [ref_refused/house_format] |
| compare-009|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | нет | ref_refused:1 control_erred:1 | engine-fault | courier_book.address.building: агент `187` / контроль `187к5` [ref_refused/house_format] |
| compare-009|2 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | нет | ref_refused:1 control_erred:1 | engine-fault | courier_book.address.building: агент `187` / контроль `187к5` [ref_refused/house_format] |
| compare-010|2 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | нет | other:1 | engine-fault | courier_book.contact.name: агент `пётр` / контроль `Петр` [other/inflected] |
| compare-011|0 | compare | chat | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `92` [absent] |
| compare-011|1 | compare | chat | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `92` [absent] |
| compare-011|2 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `92` [absent] |
| compare-012|1 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | reformatted:1 | engine-fault | courier_book.address.building: агент `76` / контроль `9` [reformatted] |
| compare-013|1 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | да | reformatted:1 | engine-fault | courier_book.address.building: агент `179` / контроль `21` [reformatted] |
| compare-013|2 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `21` / контроль `` [extra] |
| compare-014|0 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book | нет | absent:10 ref_refused:1 | engine-fault | courier_book.address.building: агент `12` / контроль `12 корп. 3` [ref_refused/house_format] |
| compare-014|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | да | ref_refused:1 | engine-fault | courier_book.address.building: агент `12` / контроль `12к3` [ref_refused/house_format] |
| compare-014|2 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | нет | ref_refused:1 | engine-fault | courier_book.address.building: агент `12` / контроль `12к3` [ref_refused/house_format] |
| compare-015|0 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | да | absent:10 | Б8-echo | courier_book.address.building: агент `` / контроль `20к1` [absent] |
| compare-015|1 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg | да | absent:15 | Б8-echo | courier_book.address.building: агент `` / контроль `20 к1` [absent] |
| compare-015|2 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg | да | absent:15 | Б8-echo | courier_book.address.building: агент `` / контроль `20 к1` [absent] |
| compare-016|0 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 fragment:1 | engine-fault | courier_book.contact.name: агент `валерий` / контроль `Валерия` [fragment/given] |
| compare-016|1 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | нет | fragment:1 | engine-fault | courier_book.contact.name: агент `валерий` / контроль `Валерия` [fragment/given] |
| compare-017|1 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `4` / контроль `` [extra] |
| compare-018|0 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 same_person_variant:1 | typo-normalised | address_suggest.query: агент `Можга, грибоеодва, 24` / контроль `Можга, улица Грибоедова, 24` [same_person_variant/i2] |
| compare-018|1 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 same_person_variant:1 | typo-normalised | address_suggest.query: агент `Можга улица грибоеодва 24` / контроль `Можга, улица Грибоедова, 24` [same_person_variant/i2] |
| compare-018|2 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 same_person_variant:1 | typo-normalised | address_suggest.query: агент `Можга, грибоеодва, 24` / контроль `Можга, улица Грибоедова, 24` [same_person_variant/i2] |
| compare-019|0 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | да | absent:10 | Б8-echo | courier_book.address.building: агент `` / контроль `2а к3` [absent] |
| compare-019|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | нет | absent:10 | Б8-echo | courier_book.address.building: агент `` / контроль `2а к3` [absent] |
| compare-019|2 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | нет | absent:10 | Б8-echo | courier_book.address.building: агент `` / контроль `2а к.3` [absent] |
| compare-020|0 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 fragment:1 | engine-fault | courier_book.contact.name: агент `валерий` / контроль `Валерия` [fragment/given] |
| compare-020|1 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `15` / контроль `` [extra] |
| compare-020|2 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | нет | — | engine-fault |  |
| compare-021|1 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `199` / контроль `` [extra] |
| compare-023|0 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | нет | ref_refused:1 absent:1 | engine-fault | courier_book.address.building: агент `32` / контроль `32к1` [ref_refused/house_format] |
| compare-023|2 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | нет | ref_refused:1 | engine-fault | courier_book.address.building: агент `32` / контроль `32к1` [ref_refused/house_format] |
| compare-024|1 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | да | — | engine-fault |  |
| compare-024|2 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | нет | reformatted:1 | engine-fault | courier_book.address.building: агент `8` / контроль `114` [reformatted] |
| compare-025|0 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | да | — | engine-fault |  |
| compare-025|2 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `21` / контроль `` [extra] |
| compare-026|0 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | same_person_variant:1 reformatted:1 | engine-fault | address_suggest.query: агент `Абакан, каллашникова, 10` / контроль `Абакан, Калашникова 10` [same_person_variant/i2] |
| compare-026|1 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | same_person_variant:1 reformatted:1 | other | address_suggest.query: агент `Абакан, каллашникова, 10` / контроль `Абакан, Калашникова, 10` [same_person_variant/i2] |
| compare-026|2 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 same_person_variant:1 | typo-normalised | address_suggest.query: агент `Абакан, каллашникова, 10` / контроль `Абакан, Калашникова 10` [same_person_variant/i2] |
| compare-027|1 | compare | chat | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `95` / контроль `` [extra] |
| compare-027|2 | compare | chat | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `95` / контроль `` [extra] |
| compare-028|0 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 same_person_variant:1 | typo-normalised | address_suggest.query: агент `Сарапул улица шумайова 27 а` / контроль `Сарапул, Шумайлова 27а` [same_person_variant/i2] |
| compare-028|1 | compare | sloppy | address_sugg,courier_book | address_sugg,address_sugg | да | absent:5 same_person_variant:1 extra:1 | typo-normalised | address_suggest.query: агент `Сарапул, шумайова, 27 а` / контроль `Сарапул Шумайлова 27а` [same_person_variant/i2] |
| compare-028|2 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `27а` [absent] |
| compare-029|0 | compare | voice_raw | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `122` [absent] |
| compare-029|1 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `122` [absent] |
| compare-030|0 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `114` / контроль `` [extra] |
| compare-032|0 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 reformatted:1 | engine-fault | courier_book.address.building: агент `68` / контроль `142` [reformatted] |
| compare-033|0 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | нет | ref_refused:1 | engine-fault | courier_book.address.building: агент `14` / контроль `14к4` [ref_refused/house_format] |
| compare-033|1 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:6 control_erred:1 ref_refused:1 | engine-fault | address_suggest.query: агент `Воткинск, калашникова, 14` / контроль `Воткинск улица Калашникова 14 корпус 4` [control_erred/i1] |
| compare-034|0 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 | engine-fault | courier_book.address.building: агент `13` / контроль `` [extra] |
| compare-034|1 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | нет | — | engine-fault |  |
| compare-034|2 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book,courier_book | да | extra:5 other:1 | engine-fault | courier_book.contact.name: агент `Петр` / контроль `Игорь` [other/inflected] |
| compare-036|2 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | нет | — | engine-fault |  |
| compare-038|2 | compare | chat | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book | нет | absent:10 ref_refused:1 | engine-fault | courier_book.address.building: агент `106` / контроль `106 корпус 2` [ref_refused/house_format] |
| compare-040|0 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book,courier_book | да | ref_refused:1 control_erred:1 | engine-fault | courier_book.address.building: агент `127` / контроль `127к2` [ref_refused/house_format] |
| compare-040|1 | compare | chat | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book | нет | absent:10 ref_refused:1 | engine-fault | courier_book.address.building: агент `127` / контроль `127к2` [ref_refused/house_format] |
| compare-040|2 | compare | chat | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book,courier_book | нет | absent:5 ref_refused:2 extra:1 | engine-fault | courier_book.address.building: агент `127` / контроль `127 корп. 2` [ref_refused/house_format] |
| compare-041|0 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `20б` [absent] |
| compare-041|1 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `20б` [absent] |
| compare-041|2 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `20б` [absent] |
| container-016|0 | container | voice_raw | — | notify_sms | да | extra:1 | other | notify_sms.number: агент `+79523039099` / контроль `` [extra] |
| container-016|1 | container | voice_raw | find | notify_sms | да | extra:1 absent:1 | other | notify_sms.number: агент `+79523039099` / контроль `` [extra] |
| container-016|2 | container | voice_raw | — | find,notify_sms | да | extra:2 | other | crm_find_contact.query.phone: агент `+79523039099` / контроль `` [extra] |
| container-021|0 | container | chat | import_csv | import_csv | да | container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| container-021|2 | container | chat | import_csv | import_csv | да | container_embedded:1 | other | crm_import_csv.csv: агент `last_name;first_name;phone;email;birt…` / контроль `last_name;first_name;phone;email;birt…` [container_embedded/differs_inside] |
| correction-000|0 | correction | voice_raw | courier_book,upsert,notify_sms | courier_book,upsert,courier_book,upsert | нет | extra:16 other:1 absent:1 | engine-fault | crm_upsert_contact.contact.name_latin: агент `Bukin Sergey` / контроль `Bukin Sergei` [other/misderived] |
| correction-000|1 | correction | voice_raw | upsert,courier_book,notify_sms | courier_book,upsert,courier_book,upsert | нет | extra:16 other:1 absent:1 | engine-fault | crm_upsert_contact.contact.name_latin: агент `Bukin Sergey` / контроль `Bukin Sergei` [other/misderived] |
| correction-000|2 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 | engine-fault | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-001|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-001|1 | correction | chat | courier_book | courier_book,upsert | нет | extra:9 | control-partial | crm_upsert_contact.contact.address.city: агент `Воткинск` / контроль `` [extra] |
| correction-001|2 | correction | chat | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-002|0 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 | engine-fault | crm_upsert_contact.contact.address.city: агент `` / контроль `Сарапул` [absent] |
| correction-002|1 | correction | voice_raw | courier_book,upsert | upsert,courier_book,courier_book | нет | extra:6 | engine-fault | courier_book.address.building: агент `155` / контроль `` [extra] |
| correction-002|2 | correction | voice_raw | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:16 | engine-fault | courier_book.address.building: агент `155` / контроль `` [extra] |
| correction-003|0 | correction | voice_itn | upsert,courier_book | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Самара` [absent] |
| correction-003|1 | correction | voice_itn | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Самара` [absent] |
| correction-004|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:16 control_erred:2 | engine-fault | courier_book.address.street: агент `ленна` / контроль `Ленина` [control_erred/i2] |
| correction-004|1 | correction | voice_raw | courier_book,upsert | courier_book,courier_book | да | absent:9 extra:6 control_erred:1 | engine-fault | courier_book.address.street: агент `ленна` / контроль `Ленина` [control_erred/i2] |
| correction-004|2 | correction | voice_raw | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:15 control_erred:2 other:1 | engine-fault | courier_book.address.street: агент `ленна` / контроль `Ленина` [control_erred/i2] |
| correction-005|0 | correction | voice_raw | upsert,courier_book | courier_book,upsert | нет | — | other |  |
| correction-005|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-005|2 | correction | voice_raw | upsert,courier_book | courier_book,upsert | да | — | other |  |
| correction-006|0 | correction | voice_itn | courier_book | courier_book,upsert,courier_book,upsert | нет | extra:26 | engine-fault | crm_upsert_contact.contact.address.city: агент `Воткинск` / контроль `` [extra] |
| correction-006|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:16 | engine-fault | courier_book.address.building: агент `146` / контроль `` [extra] |
| correction-006|2 | correction | voice_itn | courier_book,upsert | courier_book,upsert,courier_book,upsert | да | extra:16 | engine-fault | courier_book.address.building: агент `146` / контроль `` [extra] |
| correction-007|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| correction-007|1 | correction | chat | courier_book,upsert | courier_book | да | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Самара` [absent] |
| correction-008|0 | correction | voice_raw | courier_book,upsert | courier_book,courier_book | нет | absent:10 extra:6 control_erred:1 | engine-fault | courier_book.address.street: агент `вишнвая` / контроль `Вишнёвая` [control_erred/i2] |
| correction-008|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert,courier_book,upsert | да | extra:17 control_erred:2 | engine-fault | courier_book.address.street: агент `вишнвая` / контроль `Вишнёвая` [control_erred/i2] |
| correction-008|2 | correction | voice_raw | courier_book,upsert | upsert,courier_book,courier_book | нет | extra:7 control_erred:2 other:1 | engine-fault | courier_book.address.street: агент `вишнвая` / контроль `Вишнёвая` [control_erred/i2] |
| correction-009|2 | correction | chat | upsert,courier_book | courier_book,upsert | нет | — | other |  |
| correction-010|0 | correction | voice_raw | upsert,courier_book | courier_book,upsert,courier_book,upsert | нет | extra:16 other:1 | engine-fault | crm_upsert_contact.contact.name_latin: агент `Erokhin Petr` / контроль `Erokhin Pyotr` [other/misderived] |
| correction-010|1 | correction | voice_raw | upsert,courier_book | courier_book,upsert,courier_book,upsert | да | extra:15 absent:1 other:1 | engine-fault | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-010|2 | correction | voice_raw | upsert,courier_book | courier_book,upsert,courier_book,upsert | нет | extra:15 absent:1 other:1 | engine-fault | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-011|0 | correction | sloppy | courier_book,upsert | courier_book | да | absent:9 | engine-fault | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-011|1 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-011|2 | correction | sloppy | courier_book,upsert | courier_book,courier_book | нет | absent:9 extra:6 | engine-fault | courier_book.address.building: агент `39` / контроль `` [extra] |
| correction-012|0 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | engine-fault | courier_book.address.street: агент `комисарова` / контроль `Комиссарова` [control_erred/i2] |
| correction-012|1 | correction | sloppy | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:15 control_erred:2 absent:1 | engine-fault | courier_book.address.street: агент `комисарова` / контроль `Комиссарова` [control_erred/i2] |
| correction-012|2 | correction | sloppy | courier_book,upsert | upsert,courier_book,courier_book | нет | extra:6 control_erred:2 absent:1 other:1 | engine-fault | courier_book.address.street: агент `комисарова` / контроль `Комиссарова` [control_erred/i2] |
| correction-013|0 | correction | chat | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:16 | engine-fault | courier_book.address.building: агент `23` / контроль `` [extra] |
| correction-013|1 | correction | chat | courier_book,upsert | courier_book,upsert,courier_book,upsert | да | extra:16 | engine-fault | courier_book.address.building: агент `23` / контроль `` [extra] |
| correction-013|2 | correction | chat | courier_book,upsert | courier_book,courier_book | да | absent:10 extra:6 | engine-fault | courier_book.address.building: агент `23` / контроль `` [extra] |
| correction-014|0 | correction | chat | courier_book,upsert | courier_book,upsert | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-014|1 | correction | chat | courier_book,upsert | courier_book | да | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Глазов` [absent] |
| correction-014|2 | correction | chat | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Глазов` [absent] |
| correction-015|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-015|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-015|2 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-016|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert,courier_book,upsert | да | extra:16 | engine-fault | courier_book.address.building: агент `69` / контроль `` [extra] |
| correction-016|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:16 | engine-fault | courier_book.address.building: агент `69` / контроль `` [extra] |
| correction-016|2 | correction | voice_itn | courier_book,upsert | courier_book,courier_book | нет | absent:9 extra:6 control_erred:1 | engine-fault | courier_book.contact.name: агент `фёдорова юлия` / контроль `Юлия Фёдорова` [control_erred/i3] |
| correction-017|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-018|0 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:8 control_erred:1 | engine-fault | courier_book.address.street: агент `челюксинцев` / контроль `Челюскинцев` [control_erred/i2] |
| correction-018|1 | correction | sloppy | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:17 control_erred:2 other:1 | engine-fault | courier_book.address.street: агент `челюксинцев` / контроль `Челюскинцев` [control_erred/i2] |
| correction-018|2 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:9 control_erred:1 | engine-fault | courier_book.address.street: агент `челюксинцев` / контроль `Челюскинцев` [control_erred/i2] |
| correction-019|1 | correction | chat | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-019|2 | correction | chat | courier_book,upsert | courier_book,upsert,courier_book,upsert | да | extra:15 absent:1 | engine-fault | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-020|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | да | control_erred:2 absent:1 other:1 | other | courier_book.address.street: агент `моннчегорская` / контроль `Мончегорская` [control_erred/i2] |
| correction-020|1 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | control_erred:2 | typo-normalised | courier_book.address.street: агент `моннчегорская` / контроль `Мончегорская` [control_erred/i2] |
| correction-020|2 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | control_erred:2 | typo-normalised | courier_book.address.street: агент `моннчегорская` / контроль `Мончегорская` [control_erred/i2] |
| correction-021|0 | correction | voice_raw | courier_book,upsert | upsert,courier_book | да | — | other |  |
| correction-021|2 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-022|0 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 | engine-fault | crm_upsert_contact.contact.address.city: агент `` / контроль `Глазов` [absent] |
| correction-022|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:15 absent:1 | engine-fault | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-022|2 | correction | voice_raw | upsert,courier_book | courier_book,upsert,courier_book,upsert | нет | extra:18 | engine-fault | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-023|0 | correction | voice_raw | courier_book | courier_book,upsert,courier_book,upsert | да | extra:24 | engine-fault | crm_upsert_contact.contact.address.city: агент `Воткинск` / контроль `` [extra] |
| correction-023|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert,courier_book,upsert | да | extra:17 | engine-fault | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-023|2 | correction | voice_raw | upsert,courier_book | courier_book,upsert,courier_book,upsert | нет | extra:15 absent:1 | engine-fault | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-024|0 | correction | chat | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-024|2 | correction | chat | courier_book,upsert | courier_book,upsert | нет | absent:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-025|0 | correction | voice_itn | courier_book,upsert | upsert,courier_book | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| correction-025|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert,upsert,upsert | нет | extra:21 other:1 validated_refused:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| correction-026|0 | correction | voice_raw | upsert,courier_book | upsert,courier_book,courier_book | нет | extra:6 | engine-fault | courier_book.address.building: агент `22` / контроль `` [extra] |
| correction-026|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:16 | engine-fault | courier_book.address.building: агент `22` / контроль `` [extra] |
| correction-026|2 | correction | voice_raw | upsert,courier_book | upsert | нет | absent:6 | partial-call | courier_book.address.building: агент `` / контроль `22` [absent] |
| correction-027|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:15 other:1 | engine-fault | crm_upsert_contact.contact.name_latin: агент `Lebedev Maksim` / контроль `Lebedev Maxim` [other/misderived] |
| correction-027|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:16 | engine-fault | courier_book.address.building: агент `11` / контроль `` [extra] |
| correction-027|2 | correction | voice_itn | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:17 other:1 | engine-fault | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-028|0 | correction | voice_itn | courier_book,upsert | courier_book | да | absent:10 | engine-fault | crm_upsert_contact.contact.address.city: агент `` / контроль `Можга` [absent] |
| correction-028|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert,courier_book,upsert | да | extra:15 absent:1 | engine-fault | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-028|2 | correction | voice_itn | courier_book,upsert | courier_book | нет | absent:10 | engine-fault | crm_upsert_contact.contact.address.city: агент `` / контроль `Можга` [absent] |
| correction-029|0 | correction | chat | courier_book,upsert | courier_book | да | absent:10 | engine-fault | crm_upsert_contact.contact.address.city: агент `` / контроль `Краснодар` [absent] |
| correction-029|1 | correction | chat | courier_book,upsert | courier_book | нет | absent:10 | engine-fault | crm_upsert_contact.contact.address.city: агент `` / контроль `Краснодар` [absent] |
| correction-029|2 | correction | chat | courier_book,upsert | courier_book | да | absent:10 | engine-fault | crm_upsert_contact.contact.address.city: агент `` / контроль `Краснодар` [absent] |
| correction-030|0 | correction | chat | courier_book | courier_book,upsert | нет | extra:10 | control-partial | crm_upsert_contact.contact.address.city: агент `Сарапул` / контроль `` [extra] |
| correction-030|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-030|2 | correction | chat | courier_book | upsert,courier_book | да | extra:10 | control-partial | crm_upsert_contact.contact.address.city: агент `Сарапул` / контроль `` [extra] |
| correction-031|0 | correction | sloppy | upsert,courier_book | courier_book,upsert | да | other:4 | other | crm_upsert_contact.contact.address.city: агент `павильно` / контроль `Абакан` [other/unbound] |
| correction-031|1 | correction | sloppy | courier_book,upsert | courier_book,upsert | да | other:4 control_erred:1 extra:1 | other | courier_book.address.locality: агент `павильно` / контроль `Абакан` [other/unbound] |
| correction-031|2 | correction | sloppy | courier_book,upsert | courier_book | да | absent:10 other:2 | partial-call | courier_book.address.locality: агент `павильно` / контроль `Абакан` [other/unbound] |
| correction-032|0 | correction | chat | courier_book | courier_book,upsert,courier_book,upsert | нет | extra:26 | engine-fault | crm_upsert_contact.contact.address.city: агент `Глазов` / контроль `` [extra] |
| correction-032|1 | correction | chat | courier_book,upsert | courier_book,courier_book | да | absent:10 extra:6 | engine-fault | courier_book.address.building: агент `24` / контроль `` [extra] |
| correction-032|2 | correction | chat | courier_book,upsert | courier_book,courier_book | нет | absent:10 extra:6 | engine-fault | courier_book.address.building: агент `24` / контроль `` [extra] |
| correction-033|0 | correction | chat | courier_book,upsert | courier_book,upsert,courier_book,upsert | да | extra:16 | engine-fault | courier_book.address.building: агент `69` / контроль `` [extra] |
| correction-033|1 | correction | chat | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:16 | engine-fault | courier_book.address.building: агент `69` / контроль `` [extra] |
| correction-033|2 | correction | chat | courier_book,upsert | courier_book,upsert,courier_book,upsert | нет | extra:16 | engine-fault | courier_book.address.building: агент `69` / контроль `` [extra] |
| correction-034|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Vasilev Ivan` / контроль `Vasiliev Ivan` [other/misderived] |
| correction-034|1 | correction | voice_itn | courier_book,upsert,notify_sms | courier_book,upsert | нет | other:1 absent:1 | partial-call | crm_upsert_contact.contact.name_latin: агент `Vasilev Ivan` / контроль `Vasiliev Ivan` [other/misderived] |
| correction-034|2 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Vasilev Ivan` / контроль `Vasiliev Ivan` [other/misderived] |
| correction-035|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert,courier_book,upsert | да | extra:15 absent:1 | engine-fault | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-035|1 | correction | voice_raw | upsert,courier_book | upsert,courier_book,courier_book | нет | extra:6 | engine-fault | courier_book.address.building: агент `65` / контроль `` [extra] |
| correction-035|2 | correction | voice_raw | upsert,courier_book | courier_book,courier_book | нет | absent:10 extra:6 | engine-fault | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| crm_note-000|0 | crm_note | voice_itn | find,add_note,upsert | find,add_note,upsert | да | extra:3 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| crm_note-000|1 | crm_note | voice_itn | find,add_note,upsert,add_note | find,add_note,upsert | нет | extra:3 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| crm_note-000|2 | crm_note | voice_itn | find,add_note,upsert,add_note | find,add_note,add_note | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `колпино` [absent] |
| crm_note-001|0 | crm_note | sloppy | find,add_note | find,add_note | да | — | other |  |
| crm_note-001|1 | crm_note | sloppy | find,add_note | find,add_note | нет | — | other |  |
| crm_note-001|2 | crm_note | sloppy | find,add_note | find,add_note | да | — | other |  |
| crm_note-002|0 | crm_note | chat | find,add_note,upsert,add_note | find,add_note,add_note,upsert | да | extra:9 | other | crm_upsert_contact.contact.birth_date: агент `1957-01-20` / контроль `` [extra] |
| crm_note-002|1 | crm_note | chat | find,add_note,upsert,add_note | find,add_note,add_note,upsert | нет | — | other |  |
| crm_note-002|2 | crm_note | chat | find,add_note,upsert | find,add_note,add_note,upsert | нет | extra:9 | other | crm_upsert_contact.contact.birth_date: агент `1957-01-20` / контроль `` [extra] |
| crm_note-003|1 | crm_note | chat | find,add_note | find,add_note | да | — | other |  |
| crm_note-004|2 | crm_note | sloppy | find,add_note,upsert,add_note | find,add_note,upsert | нет | extra:3 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| crm_note-005|2 | crm_note | voice_itn | find,add_note | find,add_note | нет | — | other |  |
| crm_note-006|0 | crm_note | voice_raw | find,add_note,upsert,add_note | find,add_note,upsert,add_note | да | extra:3 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| crm_note-006|1 | crm_note | voice_raw | find,add_note,upsert,add_note | find,add_note,upsert,add_note | да | extra:3 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| crm_note-006|2 | crm_note | voice_raw | find,add_note,upsert,add_note | find,add_note,upsert,add_note | да | extra:5 | other | crm_upsert_contact.contact.birth_date: агент `1994-02-25` / контроль `` [extra] |
| crm_note-008|1 | crm_note | voice_itn | find,add_note,upsert | find,add_note,upsert,add_note | нет | absent:2 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1999-02-10` [absent] |
| crm_note-008|2 | crm_note | voice_itn | find,add_note,upsert | find,add_note,add_note,upsert | да | extra:4 | other | crm_upsert_contact.contact.first_name: агент `олег` / контроль `` [extra] |
| crm_note-010|0 | crm_note | voice_raw | find,add_note,upsert | find,add_note,upsert | да | absent:2 extra:2 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1992-06-30` [absent] |
| crm_note-010|2 | crm_note | voice_raw | find,add_note,upsert,add_note | find,add_note,upsert | нет | extra:4 | other | crm_upsert_contact.contact.first_name: агент `пётр` / контроль `` [extra] |
| crm_note-012|1 | crm_note | voice_raw | find,add_note,upsert | find,add_note,upsert | да | extra:3 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| crm_note-012|2 | crm_note | voice_raw | find,add_note,upsert,add_note | find,add_note,upsert | да | absent:2 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1966-05-07` [absent] |
| crm_note-014|0 | crm_note | voice_raw | find,add_note,upsert,add_note | find,add_note,upsert | нет | absent:2 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `2003-09-08` [absent] |
| crm_note-014|2 | crm_note | voice_raw | find,add_note,upsert,add_note | find,add_note,upsert | нет | extra:3 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| crm_note-016|0 | crm_note | sloppy | find,add_note,upsert,add_note | find,add_note,add_note | нет | absent:8 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `краснодар` [absent] |
| crm_note-016|2 | crm_note | sloppy | find,add_note,upsert,add_note | find,add_note,upsert | нет | other:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `проезд энгеьса` / контроль `проезд энгельса` [other/unbound] |
| crm_note-018|1 | crm_note | voice_raw | find,add_note,add_note | find,add_note,upsert | нет | extra:8 | control-partial | crm_upsert_contact.contact.address.city: агент `Краснодар` / контроль `` [extra] |
| crm_note-018|2 | crm_note | voice_raw | find,add_note,upsert | find,add_note,upsert | нет | absent:2 extra:2 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1965-12-14` [absent] |
| crm_note-020|0 | crm_note | voice_raw | find,add_note,upsert | find,add_note,upsert | нет | absent:2 other:1 | other | crm_upsert_contact.contact.address.street: агент `лермонтого бульвар` / контроль `бульвар Лермонтова` [other/unbound] |
| crm_note-020|1 | crm_note | voice_raw | find,add_note,upsert | find,add_note,upsert | да | absent:2 extra:2 other:1 | other | crm_upsert_contact.contact.address.street: агент `лермонтого бульвар` / контроль `бульвар лермонтова` [other/unbound] |
| crm_note-020|2 | crm_note | voice_raw | find,add_note,upsert | find,add_note,upsert | да | absent:2 other:1 | other | crm_upsert_contact.contact.address.street: агент `лермонтого бульвар` / контроль `бульвар лермонтова` [other/unbound] |
| crm_note-021|0 | crm_note | chat | find,add_note | find,add_note | да | — | other |  |
| crm_note-021|1 | crm_note | chat | find,add_note | find,add_note | да | — | other |  |
| crm_note-022|0 | crm_note | voice_raw | find,add_note,upsert | find,add_note,upsert,add_note | да | absent:2 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1964-01-03` [absent] |
| crm_note-022|2 | crm_note | voice_raw | find,add_note,upsert | find,add_note,upsert,add_note | да | absent:6 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1964-01-03` [absent] |
| decompose-001|0 | decompose | voice_raw | courier_book | courier_book | да | other:1 | engine-fault | courier_book.address.street: агент `комиссарого бульвар` / контроль `бульвар Комиссарова` [other/unbound] |
| decompose-001|1 | decompose | voice_raw | courier_book | courier_book,courier_book | да | extra:7 other:1 | engine-fault | courier_book.address.street: агент `комиссарого бульвар` / контроль `бульвар Комиссарова` [other/unbound] |
| decompose-001|2 | decompose | voice_raw | courier_book | courier_book | да | other:1 | engine-fault | courier_book.address.street: агент `комиссарого бульвар` / контроль `бульвар Комиссарова` [other/unbound] |
| decompose-007|0 | decompose | clean | courier_book | courier_book,courier_book | да | extra:7 | engine-fault | courier_book.address.building: агент `70` / контроль `` [extra] |
| decompose-010|2 | decompose | voice_itn | courier_book | courier_book,courier_book | да | extra:7 | engine-fault | courier_book.address.building: агент `8` / контроль `` [extra] |
| decompose-011|1 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VYACHESLAV FOMIN` / контроль `VIACHESLAV FOMIN` [other/misderived] |
| decompose-011|2 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VYACHESLAV FOMIN` / контроль `VIACHESLAV FOMIN` [other/misderived] |
| decompose-013|0 | decompose | chat | courier_book | courier_book | нет | — | engine-fault |  |
| decompose-016|2 | decompose | voice_itn | courier_book | courier_book,courier_book | да | extra:7 | engine-fault | courier_book.address.building: агент `12 б` / контроль `` [extra] |
| decompose-017|2 | decompose | sloppy | payment_crea | payment_crea | нет | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VYACHESLAV FOMIN` / контроль `VIACHESLAV FOMIN` [other/misderived] |
| decompose-019|0 | decompose | sloppy | courier_book | courier_book | да | control_erred:1 | engine-fault | courier_book.address.street: агент `пушшкина` / контроль `Пушкина` [control_erred/i1] |
| decompose-019|1 | decompose | sloppy | courier_book | courier_book | да | control_erred:1 | engine-fault | courier_book.address.street: агент `пушшкина` / контроль `Пушкина` [control_erred/i1] |
| decompose-019|2 | decompose | sloppy | courier_book | courier_book | да | control_erred:1 | engine-fault | courier_book.address.street: агент `пушшкина` / контроль `Пушкина` [control_erred/i1] |
| decompose-020|2 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `ALEXANDER MILLER` / контроль `VALERIY MILLER` [other/misderived] |
| decompose-025|2 | decompose | chat | courier_book | courier_book,courier_book | да | extra:7 | engine-fault | courier_book.address.building: агент `196` / контроль `` [extra] |
| decompose-026|2 | decompose | chat | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `ARTYOM GROMOV` / контроль `ARTEM GROMOV` [other/misderived] |
| decompose-031|1 | decompose | voice_itn | courier_book | courier_book,courier_book | да | extra:7 | engine-fault | courier_book.address.building: агент `186` / контроль `` [extra] |
| decompose-031|2 | decompose | voice_itn | courier_book | courier_book,courier_book | да | extra:7 | engine-fault | courier_book.address.building: агент `186` / контроль `` [extra] |
| decompose-032|1 | decompose | chat | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `MAYA KUZNETSOVA` / контроль `OLGA KUZNETSOVA` [other/misderived] |
| decompose-040|0 | decompose | clean | courier_book | courier_book,courier_book | да | extra:7 | engine-fault | courier_book.address.building: агент `28в` / контроль `` [extra] |
| decompose-040|2 | decompose | clean | courier_book | courier_book,courier_book | да | extra:7 | engine-fault | courier_book.address.building: агент `28в` / контроль `` [extra] |
| derive-000|1 | derive | chat | clinic_book | clinic_book | да | other:1 | other | clinic_book.patient.age: агент `38` / контроль `39` [other/misderived] |
| derive-000|2 | derive | chat | clinic_book | clinic_book | да | other:1 | other | clinic_book.patient.age: агент `38` / контроль `39` [other/misderived] |
| derive-007|2 | derive | voice_raw | — | callback_sch | нет | extra:2 | other | callback_schedule.phone: агент `+79507044983` / контроль `` [extra] |
| derive-009|2 | derive | voice_itn | upsert | upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-010|0 | derive | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 | typo-normalised | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-010|2 | derive | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 | typo-normalised | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-011|2 | derive | chat | callback_sch | callback_sch,callback_sch | да | extra:2 | engine-fault | callback_schedule.phone: агент `+79776400928` / контроль `` [extra] |
| derive-012|1 | derive | chat | clinic_book | clinic_book | да | — | other |  |
| derive-013|0 | derive | voice_raw | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-013|2 | derive | voice_raw | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-017|2 | derive | sloppy | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| derive-018|0 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 | typo-normalised | delivery_create_order.to_location.address: агент `переулок лениа, 11, кв. 150` / контроль `переулок Ленина, 11, кв. 150` [other/unbound] |
| derive-018|1 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 | typo-normalised | delivery_create_order.to_location.address: агент `переулок лениа, 11, кв. 150` / контроль `переулок Ленина, 11, кв. 150` [other/unbound] |
| derive-018|2 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 | other | delivery_create_order.to_location.address: агент `пер. лениа, 11, кв. 150` / контроль `переулок Ленина, 11, кв. 150` [other/unbound] |
| derive-021|0 | derive | chat | upsert | upsert | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-021|1 | derive | chat | upsert | upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-021|2 | derive | chat | upsert | upsert | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-027|0 | derive | voice_raw | callback_sch | callback_sch | нет | control_erred:1 | engine-fault | callback_schedule.phone: агент `+79611669251` / контроль `+79601669251` [control_erred/i2] |
| derive-027|2 | derive | voice_raw | callback_sch | callback_sch | да | control_erred:1 | typo-normalised | callback_schedule.phone: агент `+79611669251` / контроль `+79601669251` [control_erred/i2] |
| derive-029|0 | derive | voice_itn | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-029|1 | derive | voice_itn | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-032|1 | derive | chat | clinic_book | clinic_book | да | other:1 | other | clinic_book.patient.age: агент `26` / контроль `27` [other/misderived] |
| derive-033|1 | derive | voice_raw | upsert | upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-037|1 | derive | voice_itn | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-042|0 | derive | voice_itn | delivery_cre | delivery_cre | да | control_erred:1 | typo-normalised | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-042|2 | derive | voice_itn | delivery_cre | delivery_cre | да | control_erred:1 | typo-normalised | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-044|0 | derive | chat | clinic_book | clinic_book | нет | — | engine-fault |  |
| derive-045|0 | derive | voice_raw | upsert | upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| derive-046|0 | derive | voice_raw | delivery_cre | delivery_cre | да | other:1 | typo-normalised | delivery_create_order.to_location.address: агент `ул. шумайлого, д. 26, кв. 208` / контроль `ул. Шумайлова, д. 26, кв. 208` [other/unbound] |
| derive-046|1 | derive | voice_raw | delivery_cre | delivery_cre | да | other:1 | other | delivery_create_order.to_location.address: агент `улица шумайлого, 26, кв. 208` / контроль `ул. Шумайлова, д. 26, кв. 208` [other/unbound] |
| derive-046|2 | derive | voice_raw | delivery_cre | delivery_cre | нет | other:1 | typo-normalised | delivery_create_order.to_location.address: агент `ул. шумайлого, д. 26, кв. 208` / контроль `ул. Шумайлова, д. 26, кв. 208` [other/unbound] |
| derive-048|0 | derive | chat | clinic_book | clinic_book | да | other:1 | other | clinic_book.patient.age: агент `46` / контроль `47` [other/misderived] |
| derive-048|1 | derive | chat | clinic_book | clinic_book | да | other:1 | other | clinic_book.patient.age: агент `46` / контроль `47` [other/misderived] |
| derive-050|0 | derive | chat | delivery_cre | delivery_cre | да | control_erred:1 | typo-normalised | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-050|1 | derive | chat | delivery_cre | delivery_cre | нет | control_erred:1 | typo-normalised | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-051|0 | derive | voice_raw | callback_sch | callback_sch | нет | control_erred:1 | engine-fault | callback_schedule.phone: агент `+79774094000` / контроль `+79007749000` [control_erred/i2] |
| derive-052|1 | derive | voice_itn | clinic_book | clinic_book | нет | — | engine-fault |  |
| derive-053|0 | derive | sloppy | upsert | upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| lookup_list-000|0 | lookup_list | voice_raw | find,upsert | find,upsert | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| lookup_list-001|2 | lookup_list | voice_raw | find,upsert | find,upsert | нет | other:1 | typo-normalised | crm_upsert_contact.contact.email: агент `gromova892@gmail.com` / контроль `gromova89@gmail.com` [other/inflected] |
| lookup_list-002|0 | lookup_list | voice_itn | find,upsert | find,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bukin Sergey` / `Bukin Sergei` [derived] |
| lookup_list-002|1 | lookup_list | voice_itn | find,upsert | find,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bukin Sergey` / `Bukin Sergei` [derived] |
| lookup_list-002|2 | lookup_list | voice_itn | find,upsert | find,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| lookup_list-003|0 | lookup_list | chat | find,find,upsert | find,find,upsert | да | absent:1 residual:1 | residual | crm_upsert_contact.contact.email: агент `` / контроль `bityukov77@bk.ru` [absent] |
| lookup_list-003|2 | lookup_list | chat | find,find,upsert | find,find,upsert | да | absent:2 | other | crm_upsert_contact.contact.email: агент `` / контроль `bityukov77@bk.ru` [absent] |
| lookup_list-004|0 | lookup_list | voice_raw | find,upsert | find,upsert,upsert | да | extra:12 same_person_variant:2 control_erred:1 absent:1 | other | crm_upsert_contact.contact.address.flat: агент `35` / контроль `26` [same_person_variant/i21] |
| lookup_list-004|1 | lookup_list | voice_raw | find,upsert | find,upsert,upsert | да | extra:12 same_person_variant:2 control_erred:1 | other | crm_upsert_contact.contact.address.flat: агент `35` / контроль `26` [same_person_variant/i21] |
| lookup_list-004|2 | lookup_list | voice_raw | find,upsert | find,upsert,upsert | нет | extra:13 same_person_variant:2 control_erred:1 | other | crm_upsert_contact.contact.address.flat: агент `35` / контроль `26` [same_person_variant/i21] |
| lookup_list-005|0 | lookup_list | voice_itn | find,find,upsert | find,find,upsert,upsert | да | extra:12 | other | crm_upsert_contact.contact.address.city: агент `самара` / контроль `` [extra] |
| lookup_list-005|1 | lookup_list | voice_itn | find,find,upsert,upsert | find,upsert | нет | absent:13 other:1 extra:1 | typo-normalised | crm_find_contact.query.phone: агент `` / контроль `+79855221598` [absent] |
| lookup_list-005|2 | lookup_list | voice_itn | find,upsert | find,upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| lookup_list-006|0 | lookup_list | sloppy | find,upsert | find,upsert | да | other:1 | other | crm_upsert_contact.contact.address.street: агент `калаашникова бульвар` / контроль `бульвар Калашникова` [other/unbound] |
| lookup_list-006|1 | lookup_list | sloppy | find,upsert | find,upsert | нет | other:1 | other | crm_upsert_contact.contact.address.street: агент `калаашникова бульвар` / контроль `бульвар Калашникова` [other/unbound] |
| lookup_list-006|2 | lookup_list | sloppy | find,upsert | find,upsert | нет | other:1 extra:1 | other | crm_upsert_contact.contact.address.street: агент `калаашникова бульвар` / контроль `бульвар Калашникова` [other/unbound] |
| lookup_list-007|0 | lookup_list | chat | find,find,upsert | find,find,upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| lookup_list-007|1 | lookup_list | chat | find,upsert | find,find,upsert | да | extra:2 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| lookup_list-007|2 | lookup_list | chat | find,upsert | find,find,upsert | да | extra:2 other:1 | typo-normalised | crm_upsert_contact.contact.email: агент `fomin962@list.ru` / контроль `fomin96@list.ru` [other/inflected] |
| lookup_list-008|0 | lookup_list | chat | find,upsert | find,upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| lookup_list-008|1 | lookup_list | chat | find,upsert | find,upsert | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| lookup_list-009|0 | lookup_list | chat | find,upsert,upsert | find,find,upsert,upsert | нет | other:1 extra:1 | typo-normalised | crm_upsert_contact.contact.email: агент `sergeev90@bk.ru` / контроль `sergeev902@bk.ru` [other/inflected] |
| lookup_list-009|1 | lookup_list | chat | find,upsert | find,find,upsert | нет | absent:1 extra:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| lookup_list-009|2 | lookup_list | chat | find,upsert,upsert | find,find,upsert | нет | absent:12 extra:2 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| lookup_list-010|0 | lookup_list | sloppy | find,upsert | find,upsert | нет | fragment:1 derived:1 | other | crm_upsert_contact.contact.address.house: агент `147 в` / контроль `147` [fragment/house] |
| lookup_list-010|1 | lookup_list | sloppy | find,upsert | find,upsert | нет | fragment:1 | other | crm_upsert_contact.contact.address.house: агент `147 в` / контроль `147` [fragment/house] |
| lookup_list-010|2 | lookup_list | sloppy | find,upsert | find,upsert | нет | fragment:1 extra:1 | other | crm_upsert_contact.contact.address.house: агент `147 в` / контроль `147` [fragment/house] |
| lookup_list-011|0 | lookup_list | chat | find,find,upsert,upsert | find,find,upsert | нет | absent:12 other:1 extra:1 | typo-normalised | crm_upsert_contact.contact.email: агент `gromova73@gmail.com` / контроль `gromova732@gmail.com` [other/inflected] |
| lookup_list-011|1 | lookup_list | chat | find,find,upsert | find,find,upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| lookup_list-012|0 | lookup_list | chat | find,upsert | find,upsert | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| lookup_list-012|2 | lookup_list | chat | find,upsert | find,upsert | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| lookup_list-013|0 | lookup_list | chat | find,find,upsert | find,find,upsert,upsert | да | extra:12 | other | crm_upsert_contact.contact.address.city: агент `сарапул` / контроль `` [extra] |
| lookup_list-013|1 | lookup_list | chat | find,find,upsert | find,find,upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| lookup_list-013|2 | lookup_list | chat | find,find,upsert | find,find,upsert,upsert | нет | extra:12 derived:1 | derived-only | crm_upsert_contact.contact.address.city: агент `сарапул` / контроль `` [extra] |
| lookup_list-014|0 | lookup_list | voice_raw | find,upsert | find,upsert,upsert | нет | extra:9 same_person_variant:2 control_erred:1 derived:1 | other | crm_upsert_contact.contact.address.flat: агент `163` / контроль `13` [same_person_variant/i21] |
| lookup_list-014|1 | lookup_list | voice_raw | find,upsert | find,upsert,upsert | да | extra:12 same_person_variant:2 control_erred:1 derived:1 | other | crm_upsert_contact.contact.address.flat: агент `163` / контроль `13` [same_person_variant/i21] |
| lookup_list-015|0 | lookup_list | voice_itn | find,find,upsert,upsert | find,find,upsert | нет | absent:13 | other | crm_upsert_contact.contact.address.city: агент `` / контроль `Сарапул` [absent] |
| lookup_list-015|1 | lookup_list | voice_itn | find,find,upsert,upsert | find,find,upsert | нет | absent:14 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| lookup_list-016|0 | lookup_list | voice_itn | find,upsert | find,upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| lookup_list-016|1 | lookup_list | voice_itn | find,upsert | find,upsert | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| lookup_list-017|0 | lookup_list | sloppy | find,find,upsert | find,find,upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| lookup_list-017|2 | lookup_list | sloppy | find,find,upsert | find,upsert | нет | absent:1 extra:1 | other | crm_find_contact.query.phone: агент `` / контроль `+79052422172` [absent] |
| lookup_list-019|0 | lookup_list | voice_raw | find,upsert | find,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Kuznetsov Dmitriy` / `Kuznetsov Dmitry` [derived] |
| lookup_list-019|1 | lookup_list | voice_raw | find,find,upsert | find,find | нет | absent:13 control_erred:1 | typo-normalised | crm_find_contact.query.phone: агент `+79513146255` / контроль `+79503146255` [control_erred/i11] |
| lookup_list-019|2 | lookup_list | voice_raw | find,find,upsert | find,find,upsert | нет | absent:2 | other | crm_upsert_contact.contact.email: агент `` / контроль `kuznecov922@bk.ru` [absent] |
| lookup_list-020|0 | lookup_list | chat | find,upsert | find,upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| lookup_list-020|2 | lookup_list | chat | find,upsert | find,upsert | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| lookup_list-021|0 | lookup_list | chat | find,find,upsert | find,find,upsert | нет | other:1 extra:1 | typo-normalised | crm_upsert_contact.contact.email: агент `lebedev892@gmail.com` / контроль `lebedev89@gmail.com` [other/inflected] |
| lookup_list-021|1 | lookup_list | chat | find,find,upsert | find,find,upsert | да | other:1 extra:1 | typo-normalised | crm_upsert_contact.contact.email: агент `lebedev892@gmail.com` / контроль `lebedev89@gmail.com` [other/inflected] |
| lookup_list-021|2 | lookup_list | chat | find,find,upsert | find,find,upsert | нет | other:1 extra:1 derived:1 | typo-normalised | crm_upsert_contact.contact.email: агент `lebedev892@gmail.com` / контроль `lebedev89@gmail.com` [other/inflected] |
| lookup_list-022|1 | lookup_list | voice_raw | find,upsert | find,upsert,upsert | нет | extra:14 same_person_variant:2 control_erred:1 | other | crm_upsert_contact.contact.address.flat: агент `160` / контроль `7` [same_person_variant/i21] |
| lookup_list-023|0 | lookup_list | voice_raw | find,upsert,upsert | find,find,upsert | нет | absent:14 extra:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| lookup_list-023|2 | lookup_list | voice_raw | find,upsert | find,find,upsert,upsert | да | extra:13 | other | crm_find_contact.query.phone: агент `+79264931413` / контроль `` [extra] |
| lookup_list-024|0 | lookup_list | sloppy | find,upsert | find,upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| lookup_list-024|1 | lookup_list | sloppy | find,upsert | find,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Gromov Artem` / `Gromov Artyom` [derived] |
| lookup_list-024|2 | lookup_list | sloppy | find,upsert | find,upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| lookup_list-025|0 | lookup_list | voice_raw | find,upsert | find,find,upsert | да | extra:2 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| lookup_list-025|2 | lookup_list | voice_raw | find,find,upsert | find,find,upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| lookup_list-026|0 | lookup_list | voice_raw | find,upsert | find,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bukin Sergey` / `Bukin Sergei` [derived] |
| lookup_list-026|1 | lookup_list | voice_raw | find,upsert | find,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| lookup_list-026|2 | lookup_list | voice_raw | find,upsert | find,upsert | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.birth_date: агент `` / контроль `1962-09-08` [absent] |
| lookup_list-027|2 | lookup_list | voice_itn | find,find,upsert | find,find,upsert | нет | other:1 | typo-normalised | crm_upsert_contact.contact.email: агент `lebedeva722@bk.ru` / контроль `lebedeva72@bk.ru` [other/inflected] |
| lookup_list-028|0 | lookup_list | voice_itn | find,upsert | find,upsert | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| lookup_list-029|0 | lookup_list | voice_raw | find,upsert | find,find,upsert | да | absent:2 extra:1 | other | crm_upsert_contact.contact.email: агент `` / контроль `tarasova88@gmail.com` [absent] |
| lookup_list-029|1 | lookup_list | voice_raw | find,upsert | find,find,upsert | нет | absent:1 extra:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| result_feed-003|0 | result_feed | chat | find,clinic_book | find,clinic_book,clinic_book | нет | extra:7 | engine-fault | clinic_book.patient.age: агент `63` / контроль `` [extra] |
| result_feed-003|1 | result_feed | chat | find,clinic_book | find,clinic_book,notify_sms | да | derived:1 extra:1 | derived-only | notify_sms.number: агент `+79030041566` / контроль `` [extra] |
| result_feed-003|2 | result_feed | chat | find,clinic_book | find,clinic_book | да | derived:1 | engine-fault | clinic_book.patient.age: `63` / `64` [derived] |
| result_feed-004|0 | result_feed | chat | find,clinic_book,notify_sms | find,clinic_book | да | other:1 absent:1 | partial-call | clinic_book.patient.age: агент `57` / контроль `58` [other/misderived] |
| result_feed-004|2 | result_feed | chat | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-005|0 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book,clinic_book | нет | extra:7 absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79261234567` [absent] |
| result_feed-005|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-005|2 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book,notify_sms | нет | — | other |  |
| result_feed-009|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-009|1 | result_feed | voice_raw | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79273581776` [absent] |
| result_feed-009|2 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | — | engine-fault |  |
| result_feed-013|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-013|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-014|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-014|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-014|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book,clinic_book | да | extra:7 | engine-fault | clinic_book.patient.age: агент `41` / контроль `` [extra] |
| result_feed-015|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `56` / контроль `57` [other/misderived] |
| result_feed-015|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-015|2 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | — | engine-fault |  |
| result_feed-016|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book,clinic_book | да | extra:7 | engine-fault | clinic_book.patient.age: агент `38` / контроль `` [extra] |
| result_feed-016|1 | result_feed | voice_raw | find,clinic_book,notify_sms | find,clinic_book,clinic_book | да | extra:7 absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79778446323` [absent] |
| result_feed-016|2 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | — | engine-fault |  |
| result_feed-017|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | — | engine-fault |  |
| result_feed-017|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-017|2 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book,clinic_book | нет | extra:7 absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79993861689` [absent] |
| result_feed-019|0 | result_feed | sloppy | find,clinic_book,notify_sms | find,clinic_book,clinic_book | нет | extra:7 absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79623666028` [absent] |
| result_feed-019|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | — | engine-fault |  |
| result_feed-019|2 | result_feed | sloppy | find,clinic_book | find,clinic_book,clinic_book | нет | extra:7 | engine-fault | clinic_book.patient.age: агент `28` / контроль `` [extra] |
| result_feed-020|0 | result_feed | chat | find,clinic_book,notify_sms | find,clinic_book,clinic_book | нет | extra:7 absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79221112233` [absent] |
| result_feed-020|1 | result_feed | chat | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-020|2 | result_feed | chat | find,clinic_book | find,clinic_book,clinic_book | нет | extra:7 | engine-fault | clinic_book.patient.age: агент `45` / контроль `` [extra] |
| result_feed-021|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book,clinic_book | нет | extra:7 | engine-fault | clinic_book.patient.age: агент `32` / контроль `` [extra] |
| result_feed-021|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book,clinic_book | нет | extra:7 | engine-fault | clinic_book.patient.age: агент `32` / контроль `` [extra] |
| result_feed-021|2 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-023|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `64` / контроль `65` [other/misderived] |
| result_feed-023|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `64` / контроль `65` [other/misderived] |
| result_feed-023|2 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `64` / контроль `65` [other/misderived] |
| result_feed-026|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-026|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `51` / контроль `52` [other/misderived] |
| result_feed-026|2 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book,clinic_book | нет | extra:7 absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79607234737` [absent] |
| result_feed-027|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-027|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book,notify_sms | нет | extra:1 | control-partial | notify_sms.number: агент `+79035416931` / контроль `` [extra] |
| result_feed-027|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book,clinic_book | да | extra:7 | engine-fault | clinic_book.patient.age: агент `24` / контроль `` [extra] |
| result_feed-028|0 | result_feed | chat | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-028|2 | result_feed | chat | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-029|0 | result_feed | chat | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79825673198` [absent] |
| result_feed-029|1 | result_feed | chat | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-029|2 | result_feed | chat | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79825673198` [absent] |
| result_feed-031|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book,clinic_book | нет | extra:7 | engine-fault | clinic_book.patient.age: агент `30` / контроль `` [extra] |
| result_feed-031|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book,clinic_book | да | extra:7 | engine-fault | clinic_book.patient.age: агент `30` / контроль `` [extra] |
| result_feed-031|2 | result_feed | voice_raw | find,clinic_book | find,clinic_book,clinic_book | нет | extra:7 | engine-fault | clinic_book.patient.age: агент `30` / контроль `` [extra] |
| result_feed-032|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-032|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book,clinic_book | нет | extra:7 | engine-fault | clinic_book.patient.age: агент `26` / контроль `` [extra] |
| result_feed-032|2 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-033|0 | result_feed | chat | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-033|1 | result_feed | chat | find,clinic_book | find,clinic_book | да | — | engine-fault |  |
| result_feed-033|2 | result_feed | chat | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79050794728` [absent] |
| result_feed-034|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | other:1 | other | clinic_book.patient.age: агент `46` / контроль `47` [other/misderived] |
| result_feed-034|2 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | engine-fault | notify_sms.number: агент `` / контроль `+79097619209` [absent] |
| send_template-000|0 | send_template | voice_itn | send_templat | send_templat | нет | — | other |  |
| send_template-000|1 | send_template | voice_itn | send_templat | send_templat | нет | — | other |  |
| send_template-000|2 | send_template | voice_itn | send_templat | send_templat | нет | — | other |  |
| send_template-001|0 | send_template | chat | send_templat,callback_sch,send_templat | send_templat,callback_sch,send_templat | нет | — | other |  |
| send_template-001|1 | send_template | chat | find,send_templat,send_templat,callback_sch | send_templat,callback_sch,send_templat | нет | absent:1 | partial-call | crm_find_contact.query.phone: агент `` / контроль `+79295861786` [absent] |
| send_template-002|0 | send_template | sloppy | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `колпино переулок чапаевва 18 квартира…` / контроль `Колпино, пер. Чапаева, 18, кв. 52` [control_erred/i3] |
| send_template-002|1 | send_template | sloppy | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `колпино переулок чапаевва 18 квартира…` / контроль `Колпино, пер. Чапаева, 18, кв. 52` [control_erred/i3] |
| send_template-002|2 | send_template | sloppy | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `колпино переулок чапаевва 18 квартира…` / контроль `Колпино, переулок Чапаева, 18, кв. 52` [control_erred/i3] |
| send_template-003|0 | send_template | voice_itn | send_templat,callback_sch,send_templat | send_templat,callback_sch | нет | absent:3 extra:1 | other | send_template.variables.phone: агент `+79293636757` / контроль `` [extra] |
| send_template-003|1 | send_template | voice_itn | send_templat,callback_sch | send_templat,callback_sch | нет | — | other |  |
| send_template-003|2 | send_template | voice_itn | send_templat,callback_sch,send_templat | send_templat,send_templat | нет | absent:2 | partial-call | callback_schedule.phone: агент `` / контроль `+79293636757` [absent] |
| send_template-004|0 | send_template | voice_raw | send_templat | send_templat | да | — | other |  |
| send_template-004|1 | send_template | voice_raw | send_templat | send_templat | нет | — | other |  |
| send_template-004|2 | send_template | voice_raw | send_templat | send_templat,send_templat | нет | extra:4 validated_refused:2 | other | send_template.variables.address: агент `ижевск проспект репина сто шестьдесят…` / контроль `Ижевск, проспект Репина, 169, квартир…` [validated_refused/unknown_variable] |
| send_template-005|0 | send_template | sloppy | send_templat,callback_sch | send_templat,callback_sch,send_templat | да | extra:3 absent:1 | other | send_template.variables.phone: агент `` / контроль `+79261234567` [absent] |
| send_template-005|1 | send_template | sloppy | send_templat,callback_sch | send_templat,callback_sch | нет | — | other |  |
| send_template-005|2 | send_template | sloppy | send_templat,callback_sch | send_templat,send_templat | нет | absent:3 extra:3 | partial-call | send_template.variables.phone: агент `` / контроль `+79261234567` [absent] |
| send_template-006|0 | send_template | voice_itn | send_templat | send_templat | нет | — | other |  |
| send_template-006|1 | send_template | voice_itn | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `сортавала бульвар комиссарова 153 ква…` / контроль `г. Сортавала, бул. Комиссарова, д. 15…` [control_erred/i3] |
| send_template-006|2 | send_template | voice_itn | send_templat | send_templat | да | — | other |  |
| send_template-007|0 | send_template | voice_raw | send_templat,send_templat | send_templat,callback_sch,send_templat | нет | extra:2 | control-partial | callback_schedule.phone: агент `+79614220619` / контроль `` [extra] |
| send_template-007|1 | send_template | voice_raw | send_templat,send_templat | send_templat | нет | absent:3 extra:1 | other | send_template.variables.phone: агент `+79614220619` / контроль `` [extra] |
| send_template-007|2 | send_template | voice_raw | send_templat,send_templat | send_templat,callback_sch,send_templat | да | extra:2 | control-partial | callback_schedule.phone: агент `+79614220619` / контроль `` [extra] |
| send_template-008|0 | send_template | voice_raw | send_templat | send_templat | да | control_erred:1 | control_erred | send_template.variables.address: агент `воткинск бульвар энгльса восемьдесят …` / контроль `Воткинск, бульвар Энгельса, 89, кв. 2…` [control_erred/i3] |
| send_template-008|1 | send_template | voice_raw | send_templat | send_templat | да | control_erred:1 | control_erred | send_template.variables.address: агент `воткинск бульвар энгльса восемьдесят …` / контроль `Воткинск, бульвар Энгельса, 89, кв. 2…` [control_erred/i3] |
| send_template-008|2 | send_template | voice_raw | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `воткинск бульвар энгльса восемьдесят …` / контроль `Воткинск, бульвар Энгельса, 89, кв. 2…` [control_erred/i3] |
| send_template-009|0 | send_template | voice_raw | send_templat,send_templat | send_templat,callback_sch | нет | extra:3 absent:3 | control-partial | send_template.variables.phone: агент `+79851068841` / контроль `` [extra] |
| send_template-009|1 | send_template | voice_raw | send_templat,callback_sch,send_templat | send_templat,callback_sch,send_templat | нет | — | other |  |
| send_template-009|2 | send_template | voice_raw | send_templat,callback_sch | send_templat,callback_sch | нет | — | other |  |
| send_template-010|0 | send_template | chat | send_templat | send_templat | нет | — | other |  |
| send_template-010|1 | send_template | chat | send_templat | send_templat | нет | — | other |  |
| send_template-010|2 | send_template | chat | send_templat | send_templat | да | — | other |  |
| send_template-011|1 | send_template | voice_raw | send_templat,callback_sch | send_templat,callback_sch | да | — | other |  |
| send_template-011|2 | send_template | voice_raw | send_templat,callback_sch,send_templat | send_templat,callback_sch | нет | absent:3 extra:1 | other | send_template.variables.phone: агент `+79617282231` / контроль `` [extra] |
| send_template-012|0 | send_template | voice_raw | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `глазов улица зелноградская дом восемн…` / контроль `г. Глазов, ул. Зеленоградская, д. 18,…` [control_erred/i3] |
| send_template-012|1 | send_template | voice_raw | send_templat | send_templat,send_templat | нет | extra:4 validated_refused:2 | other | send_template.variables.address: агент `глазов улица зелноградская дом восемн…` / контроль `Глазов, ул. Зеленоградская, д. 18, кв…` [validated_refused/unknown_variable] |
| send_template-012|2 | send_template | voice_raw | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `глазов улица зелноградская дом восемн…` / контроль `г. Глазов, ул. Зеленоградская, д. 18,…` [control_erred/i3] |
| send_template-013|0 | send_template | chat | send_templat,callback_sch | send_templat,callback_sch,send_templat | нет | extra:3 absent:1 | other | send_template.variables.phone: агент `` / контроль `+79295794524` [absent] |
| send_template-013|1 | send_template | chat | send_templat,callback_sch,send_templat | send_templat,callback_sch | нет | absent:3 extra:1 | other | send_template.variables.phone: агент `+79295794524` / контроль `` [extra] |
| send_template-013|2 | send_template | chat | send_templat,callback_sch,send_templat | send_templat,callback_sch | нет | absent:3 extra:1 | other | send_template.variables.phone: агент `+79295794524` / контроль `` [extra] |
| send_template-014|0 | send_template | voice_itn | send_templat | send_templat | нет | — | other |  |
| send_template-014|1 | send_template | voice_itn | send_templat | send_templat | нет | — | other |  |
| send_template-014|2 | send_template | voice_itn | send_templat | send_templat | нет | — | other |  |
| send_template-015|0 | send_template | voice_itn | send_templat,callback_sch | send_templat,callback_sch,send_templat | нет | extra:3 absent:1 | other | send_template.variables.phone: агент `` / контроль `+79129876543` [absent] |
| send_template-015|1 | send_template | voice_itn | send_templat,callback_sch | send_templat,callback_sch | нет | — | other |  |
| send_template-015|2 | send_template | voice_itn | send_templat,callback_sch,send_templat | send_templat,callback_sch,send_templat | нет | — | other |  |
| send_template-016|0 | send_template | voice_raw | send_templat | send_templat | нет | — | other |  |
| send_template-016|1 | send_template | voice_raw | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `сортавала проспект энгельса сорок пят…` / контроль `г. Сортавала, проспект Энгельса, 45, …` [control_erred/i3] |
| send_template-016|2 | send_template | voice_raw | send_templat | send_templat | нет | — | other |  |
| send_template-017|1 | send_template | chat | send_templat,callback_sch | send_templat,callback_sch,send_templat | нет | extra:3 absent:1 | other | send_template.variables.phone: агент `` / контроль `+79194810355` [absent] |
| send_template-017|2 | send_template | chat | send_templat,callback_sch,send_templat | send_templat,callback_sch,send_templat | нет | — | other |  |
| send_template-018|0 | send_template | sloppy | send_templat | send_templat | да | control_erred:1 | control_erred | send_template.variables.address: агент `ижевск проезд комсомолбский 163 кв 1` / контроль `Ижевск, проезд Комсомольский, 163, кв…` [control_erred/i3] |
| send_template-018|1 | send_template | sloppy | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `ижевск проезд комсомолбский 163 кв 1` / контроль `Ижевск, проезд Комсомольский, 163, кв…` [control_erred/i3] |
| send_template-018|2 | send_template | sloppy | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `ижевск проезд комсомолбский 163 кв 1` / контроль `Ижевск, проезд Комсомольский, 163, кв…` [control_erred/i3] |
| send_template-019|0 | send_template | chat | send_templat,send_templat | send_templat,callback_sch,send_templat | да | extra:2 | control-partial | callback_schedule.phone: агент `+79624191403` / контроль `` [extra] |
| send_template-019|1 | send_template | chat | send_templat,send_templat | send_templat,callback_sch,send_templat | нет | extra:2 | control-partial | callback_schedule.phone: агент `+79624191403` / контроль `` [extra] |
| send_template-019|2 | send_template | chat | send_templat,callback_sch,send_templat | send_templat,callback_sch | нет | absent:3 extra:1 | other | send_template.variables.phone: агент `+79624191403` / контроль `` [extra] |
| send_template-020|0 | send_template | voice_raw | send_templat | send_templat | да | control_erred:1 | typo-normalised | send_template.number: агент `+79221112233` / контроль `+79222112233` [control_erred/i2] |
| send_template-020|1 | send_template | voice_raw | send_templat | send_templat | да | control_erred:1 | typo-normalised | send_template.number: агент `+79221112233` / контроль `+79222112233` [control_erred/i2] |
| send_template-020|2 | send_template | voice_raw | send_templat | send_templat | да | control_erred:1 | typo-normalised | send_template.number: агент `+79221112233` / контроль `+79222112233` [control_erred/i2] |
| send_template-021|0 | send_template | chat | send_templat,send_templat | send_templat,send_templat | нет | — | other |  |
| send_template-021|1 | send_template | chat | send_templat,callback_sch,send_templat | send_templat,send_templat | нет | absent:2 | partial-call | callback_schedule.phone: агент `` / контроль `+79826230955` [absent] |
| send_template-022|0 | send_template | sloppy | send_templat | send_templat | да | control_erred:1 | control_erred | send_template.variables.address: агент `можга проспект гагарина 178кв158` / контроль `Можга, пр. Гагарина, 178, кв. 158` [control_erred/i3] |
| send_template-022|1 | send_template | sloppy | send_templat | send_templat | да | control_erred:1 | control_erred | send_template.variables.address: агент `можга проспект гагарина 178кв158` / контроль `Можга, проспект Гагарина, 178, кв. 158` [control_erred/i3] |
| send_template-022|2 | send_template | sloppy | send_templat | send_templat | нет | control_erred:1 | control_erred | send_template.variables.address: агент `можга проспект гагарина 178кв158` / контроль `Можга, проспект Гагарина, 178, кв. 158` [control_erred/i3] |
| send_template-023|0 | send_template | chat | send_templat,callback_sch | send_templat,callback_sch,send_templat,callback_sch,notify_sms | да | extra:6 | engine-fault | send_template.number: агент `+79654642648` / контроль `` [extra] |
| send_template-023|1 | send_template | chat | send_templat,callback_sch | send_templat,callback_sch,send_templat,callback_sch | нет | extra:5 | engine-fault | send_template.number: агент `+79654642648` / контроль `` [extra] |
| send_template-023|2 | send_template | chat | send_templat,callback_sch | send_templat,callback_sch,send_templat,callback_sch | нет | extra:5 | engine-fault | send_template.number: агент `+79654642648` / контроль `` [extra] |
| summary-011|0 | summary | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 | typo-normalised | delivery_create_order.recipient.phones[0].number: агент `+79279061650` / контроль `+79279661650` [control_erred/i2] |
| summary-011|2 | summary | voice_raw | delivery_cre | delivery_cre | да | control_erred:1 | typo-normalised | delivery_create_order.recipient.phones[0].number: агент `+79279061650` / контроль `+79279661650` [control_erred/i2] |
| summary-018|0 | summary | voice_raw | delivery_cre | find | да | absent:5 extra:1 | other | delivery_create_order.recipient.name: агент `` / контроль `Громова Марина Борисовна` [absent] |
| summary-018|1 | summary | voice_raw | delivery_cre | find,delivery_cre | да | validated_refused:1 extra:1 | control-partial | delivery_create_order.recipient.phones[0].number: агент `+74031831603` / контроль `+79992635617` [validated_refused/phone_invalid] |
| summary-018|2 | summary | voice_raw | delivery_cre | delivery_cre | да | other:1 | case-only | delivery_create_order.recipient.phones[0].number: агент `+73511358387` / контроль `+79992635617` [other/inflected] |
| summary-028|0 | summary | voice_raw | find,delivery_cre | delivery_cre | да | absent:1 other:1 | typo-normalised | crm_find_contact.query.phone: агент `` / контроль `+79990750454` [absent] |
| validate-008|0 | validate | chat | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `707-379-019 11` / контроль `` [extra] |
| validate-011|2 | validate | voice_raw | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `400-724-841 37` / контроль `` [extra] |
| validate-014|2 | validate | voice_itn | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `165-459-400 89` / контроль `` [extra] |
| validate-017|0 | validate | voice_raw | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `181-547-959 03` / контроль `` [extra] |
| validate-020|1 | validate | voice_raw | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `801-742-725 79` / контроль `` [extra] |
| validate-029|1 | validate | chat | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `013-184-880 31` / контроль `` [extra] |
| validate-032|0 | validate | sloppy | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `513-209-526 47` / контроль `` [extra] |
