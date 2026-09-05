# Разбор расхождений I≠C на уровне state — v4-live-medium-s6060

троек с расхождением: 433 из 1057 · исключено 23

## Причины

| причина | троек |
|---|---|
| other | 155 |
| derived-only | 149 |
| typo-normalised | 45 |
| partial-call | 29 |
| control-partial | 16 |
| Б8-echo | 14 |
| control-refused | 12 |
| Б9-span | 9 |
| residual | 1 |
| case-only | 1 |
| control_erred | 1 |
| Б10-city | 1 |

## По видам

| вид | other | derived-only | typo-normalised | partial-call | control-partial | Б8-echo | control-refused | Б9-span | residual | case-only | control_erred | Б10-city |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chain | 30 | 69 | 14 | 0 | 4 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| compare | 11 | 0 | 10 | 0 | 2 | 13 | 11 | 0 | 0 | 1 | 0 | 0 |
| container | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| correction | 28 | 36 | 10 | 24 | 4 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| decompose | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 1 | 0 |
| derive | 39 | 19 | 7 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| result_feed | 16 | 25 | 0 | 5 | 5 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| summary | 1 | 0 | 4 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| validate | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Тройки

| тройка | вид | регистр | C вызвал | I вызвал | C′≈C | классы полей | причина | пример: агент / контроль |
|---|---|---|---|---|---|---|---|---|
| chain-000|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-000|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-001|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Novikova Natalia` / `Novikova Natalya` [derived] |
| chain-001|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Novikova Natalya` / `Novikova Natalia` [derived] |
| chain-001|2 | chain | chat | find | find,upsert,notify_sms | нет | extra:13 | control-partial | crm_upsert_contact.contact.address.city: агент `Абакан` / контроль `` [extra] |
| chain-002|0 | chain | voice_itn | find | find,upsert,notify_sms | нет | extra:14 | control-partial | crm_upsert_contact.contact.address.city: агент `Краснодар` / контроль `` [extra] |
| chain-002|1 | chain | voice_itn | find | find,upsert,notify_sms | нет | extra:13 | control-partial | crm_upsert_contact.contact.address.city: агент `Краснодар` / контроль `` [extra] |
| chain-003|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-003|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:3 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1997-10-05` [absent] |
| chain-003|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-005|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukova Zinaida` / `Bityukova Zinaida` [derived] |
| chain-005|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-005|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-006|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-006|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-007|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukov Oleg` / `Bityukov Oleg` [derived] |
| chain-007|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukov Oleg` / `Bityukov Oleg` [derived] |
| chain-007|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukov Oleg` / `Bityukov Oleg` [derived] |
| chain-008|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 extra:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `мончгорская` / контроль `мончегорская` [control_erred/i10] |
| chain-008|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 absent:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `мончгорская` / контроль `Мончегорская` [control_erred/i10] |
| chain-008|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 extra:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `мончгорская` / контроль `Мончегорская` [control_erred/i10] |
| chain-009|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 absent:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `чапава` / контроль `чапаева` [control_erred/i10] |
| chain-009|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `чапава` / контроль `Чапаева` [control_erred/i10] |
| chain-009|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 absent:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `чапава` / контроль `Чапаева` [control_erred/i10] |
| chain-010|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Erokhin Petr` / `Erokhin Pyotr` [derived] |
| chain-010|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Erokhin Pyotr` / `Yerokhin Pyotr` [derived] |
| chain-011|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-011|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-012|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-012|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-012|2 | chain | voice_raw | find,find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_find_contact.query.phone: агент `` / контроль `+79628938949` [absent] |
| chain-013|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 residual:1 | residual | crm_upsert_contact.contact.address.street: агент `энгельма` / контроль `Энгельса` [control_erred/i10] |
| chain-013|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `энгельма` / контроль `Энгельса` [control_erred/i10] |
| chain-013|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukov Oleg` / `Bityukov Oleg` [derived] |
| chain-014|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-014|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-014|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-015|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-015|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-016|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-016|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-016|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:3 | other | crm_upsert_contact.contact.birth_date: агент `` / контроль `1972-01-16` [absent] |
| chain-017|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-017|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-017|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-018|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-018|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 extra:1 derived:1 | derived-only | crm_find_contact.query.last_name: агент `` / контроль `Миллер` [absent] |
| chain-018|2 | chain | voice_raw | find,find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 absent:1 derived:1 | other | crm_find_contact.query.phone: агент `+79609662096` / контроль `+79609606296` [control_erred/i4] |
| chain-019|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Т.О.` / `А.И.` [derived] |
| chain-020|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Miller Valerii` / `Miller Valeriy` [derived] |
| chain-020|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Miller Valerii` / `Miller Valeriy` [derived] |
| chain-021|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukova Zinaida` / `Bityukova Zinaida` [derived] |
| chain-021|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 | derived-only | crm_upsert_contact.contact.initials: `Н.В.` / `З.Н.` [derived] |
| chain-022|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-022|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-022|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-023|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Sokolova Anastasia` / `Sokolova Anna` [derived] |
| chain-023|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:2 absent:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-023|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-024|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `грибоедого` / контроль `Грибоедова` [control_erred/i10] |
| chain-024|1 | chain | voice_raw | find | find,upsert,notify_sms | да | extra:14 | control-partial | crm_upsert_contact.contact.address.city: агент `Воткинск` / контроль `` [extra] |
| chain-024|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | control_erred:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `грибоедого` / контроль `Грибоедова` [control_erred/i10] |
| chain-025|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-025|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-026|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-026|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| chain-027|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-027|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-027|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-028|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-028|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-029|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukov Oleg` / `Bityukov Oleg` [derived] |
| chain-029|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-029|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-030|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-030|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-030|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Kuzneczov Dmitrii` / `Kuznetsov Dmitry` [derived] |
| chain-031|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-031|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-031|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Zaxarov Vladislav` / `Zakharov Vladislav` [derived] |
| chain-032|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| chain-033|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-033|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-033|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Meshcheryakov Dmitrii` / `Kuznetsov Dmitry` [derived] |
| chain-034|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-034|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-034|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-035|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-036|0 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Zabolotnyj Ruslan` / `Zabolotny Ruslan` [derived] |
| chain-036|1 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Zabolotnyj Ruslan` / `Zabolotny Ruslan` [derived] |
| chain-036|2 | chain | chat | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-037|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-037|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-038|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 | other | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-039|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| chain-040|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-040|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| chain-040|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bukin Sergey` / `Bukin Sergei` [derived] |
| chain-041|0 | chain | voice_raw | find,find,upsert,notify_sms | find,upsert,notify_sms | да | absent:2 control_erred:1 other:1 | other | crm_find_contact.query.phone: агент `+79120204363` / контроль `+79120244363` [control_erred/i4] |
| chain-041|1 | chain | voice_raw | find,find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 absent:1 other:1 extra:1 | other | crm_find_contact.query.phone: агент `+79120204363` / контроль `+79120244363` [control_erred/i4] |
| chain-041|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | absent:2 extra:1 other:1 | other | crm_find_contact.query.last_name: агент `` / контроль `Новиков` [absent] |
| chain-042|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | other:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `проезд неерасова` / контроль `проезд Некрасова` [other/unbound] |
| chain-042|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | other:1 extra:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `проезд неерасова` / контроль `проезд некрасова` [other/unbound] |
| chain-042|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | other:1 extra:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `проезд неерасова` / контроль `проезд Некрасова` [other/unbound] |
| chain-043|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `депуттская` / контроль `Депутатская` [control_erred/i10] |
| chain-043|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | control_erred:1 derived:1 | typo-normalised | crm_upsert_contact.contact.address.street: агент `депуттская` / контроль `Депутатская` [control_erred/i10] |
| chain-044|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | extra:2 derived:2 absent:1 reformatted:1 | other | crm_find_contact.query.last_name: агент `` / контроль `Громова` [absent] |
| chain-044|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | reformatted:1 | other | crm_upsert_contact.contact.address.house: агент `106в` / контроль `106` [reformatted] |
| chain-044|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | нет | reformatted:1 extra:1 | other | crm_upsert_contact.contact.address.house: агент `106в` / контроль `106` [reformatted] |
| chain-045|0 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukova Zinaida` / `Bityukova Zinaida` [derived] |
| chain-045|1 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukova Zinaida` / `Bityukova Zinaida` [derived] |
| chain-045|2 | chain | voice_raw | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Bitiukova Zinaida` / `Bityukova Zinaida` [derived] |
| chain-046|0 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Kukushkin Valerii` / `Kukushkin Valeriy` [derived] |
| chain-046|1 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | extra:3 derived:1 | derived-only | crm_upsert_contact.contact.birth_date: агент `1970-03-10` / контроль `` [extra] |
| chain-046|2 | chain | voice_itn | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Kukushkin Valerii` / `Kukushkin Valeriy` [derived] |
| chain-047|0 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Miller Valerii` / `Miller Valeriy` [derived] |
| chain-047|1 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | да | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Miller Valerii` / `Miller Valeriy` [derived] |
| chain-047|2 | chain | sloppy | find,upsert,notify_sms | find,upsert,notify_sms | нет | derived:1 | derived-only | crm_upsert_contact.contact.name_latin: `Miller Valerii` / `Miller Valeriy` [derived] |
| compare-005|0 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-006|0 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book | нет | absent:11 ref_refused:1 | control-refused | courier_book.address.building: агент `26` / контроль `26 к5` [ref_refused/house_format] |
| compare-006|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 | control-refused | courier_book.address.building: агент `26` / контроль `26к5` [ref_refused/house_format] |
| compare-009|0 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 control_erred:1 | control-refused | courier_book.address.building: агент `187` / контроль `187к5` [ref_refused/house_format] |
| compare-009|2 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book | да | absent:10 ref_refused:1 | control-refused | courier_book.address.building: агент `187` / контроль `187 корпус 5` [ref_refused/house_format] |
| compare-010|1 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | да | other:1 | typo-normalised | courier_book.contact.name: агент `пётр` / контроль `Петр` [other/inflected] |
| compare-010|2 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | да | other:1 | typo-normalised | courier_book.contact.name: агент `пётр` / контроль `Петр` [other/inflected] |
| compare-011|0 | compare | chat | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `92` [absent] |
| compare-011|1 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `92` [absent] |
| compare-011|2 | compare | chat | address_sugg,courier_book | address_sugg | нет | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `92` [absent] |
| compare-013|1 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-013|2 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-014|0 | compare | voice_raw | address_sugg,courier_book,courier_book,courier_book | address_sugg,courier_book | нет | absent:10 ref_refused:1 | control-refused | courier_book.address.building: агент `12` / контроль `12 корп. 3` [ref_refused/house_format] |
| compare-014|2 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 control_erred:1 ref_refused:1 extra:1 | control-refused | address_suggest.query: агент `Можга, совхозная, 12` / контроль `Можга, улица Совхозная, 12 корпус 3` [control_erred/i1] |
| compare-015|0 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | да | absent:10 | Б8-echo | courier_book.address.building: агент `` / контроль `20к1` [absent] |
| compare-015|2 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | нет | absent:11 | Б8-echo | courier_book.address.building: агент `` / контроль `20к1` [absent] |
| compare-016|0 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | нет | fragment:1 | other | courier_book.contact.name: агент `валерий` / контроль `Валерия` [fragment/given] |
| compare-016|2 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | да | fragment:1 | other | courier_book.contact.name: агент `валерий` / контроль `Валерия` [fragment/given] |
| compare-017|2 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | да | other:1 | case-only | courier_book.contact.name: агент `Петр` / контроль `Руслан` [other/inflected] |
| compare-018|0 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 same_person_variant:1 | typo-normalised | address_suggest.query: агент `Можга улица грибоеодва 24` / контроль `Можга, Грибоедова 24` [same_person_variant/i2] |
| compare-018|1 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 same_person_variant:1 | typo-normalised | address_suggest.query: агент `Можга, грибоеодва, 24` / контроль `Можга, улица Грибоедова, 24` [same_person_variant/i2] |
| compare-018|2 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 same_person_variant:1 | typo-normalised | address_suggest.query: агент `Можга, грибоеодва, 24` / контроль `Можга, улица Грибоедова, 24` [same_person_variant/i2] |
| compare-019|0 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | нет | absent:11 | Б8-echo | courier_book.address.building: агент `` / контроль `2а к3` [absent] |
| compare-019|1 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | да | absent:10 | Б8-echo | courier_book.address.building: агент `` / контроль `2а к3` [absent] |
| compare-019|2 | compare | voice_raw | address_sugg,courier_book,courier_book | address_sugg | да | absent:10 other:1 | Б8-echo | address_suggest.query: агент `Можга, депутатская 2а корп 3` / контроль `Можга, Депутатская, 2а` [other/inflected] |
| compare-020|2 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | нет | fragment:1 | other | courier_book.contact.name: агент `валерий` / контроль `Валерия` [fragment/given] |
| compare-021|2 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-024|1 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | нет | — | other |  |
| compare-024|2 | compare | chat | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-026|0 | compare | sloppy | address_sugg,courier_book | address_sugg,address_sugg,courier_book | да | same_person_variant:2 extra:1 | typo-normalised | address_suggest.query: агент `Абакан, каллашникова, 10` / контроль `Абакан, Калашникова, 10` [same_person_variant/i2] |
| compare-026|1 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 same_person_variant:1 | typo-normalised | address_suggest.query: агент `Абакан, каллашникова, 10` / контроль `Абакан, Калашникова 10` [same_person_variant/i2] |
| compare-026|2 | compare | sloppy | address_sugg,courier_book | address_sugg,address_sugg | да | absent:5 same_person_variant:1 extra:1 | typo-normalised | address_suggest.query: агент `Абакан улица каллашникова 10` / контроль `Абакан, улица Калашникова, 10` [same_person_variant/i2] |
| compare-028|0 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 same_person_variant:1 | typo-normalised | address_suggest.query: агент `Сарапул, шумайова 27 а` / контроль `Сарапул, Шумайлова 27а` [same_person_variant/i2] |
| compare-028|1 | compare | sloppy | address_sugg,courier_book | address_sugg,courier_book | да | same_person_variant:2 | typo-normalised | address_suggest.query: агент `Сарапул, шумайова 27 а` / контроль `Сарапул, Шумайлова 27а` [same_person_variant/i2] |
| compare-028|2 | compare | sloppy | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `27а` [absent] |
| compare-029|0 | compare | voice_raw | address_sugg | address_sugg,courier_book | нет | extra:5 | control-partial | courier_book.address.building: агент `122` / контроль `` [extra] |
| compare-029|1 | compare | voice_raw | address_sugg | address_sugg,courier_book | да | extra:5 | control-partial | courier_book.address.building: агент `122` / контроль `` [extra] |
| compare-029|2 | compare | voice_raw | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `122` [absent] |
| compare-033|0 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 | control-refused | courier_book.address.building: агент `14` / контроль `14к4` [ref_refused/house_format] |
| compare-033|1 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book | да | absent:5 ref_refused:1 | control-refused | courier_book.address.building: агент `14` / контроль `14к4` [ref_refused/house_format] |
| compare-034|0 | compare | voice_itn | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-036|0 | compare | voice_raw | address_sugg,courier_book | address_sugg,courier_book | да | — | other |  |
| compare-038|0 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 | control-refused | courier_book.address.building: агент `106` / контроль `106к2` [ref_refused/house_format] |
| compare-038|2 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 extra:1 | control-refused | courier_book.address.building: агент `106` / контроль `106к2` [ref_refused/house_format] |
| compare-040|2 | compare | chat | address_sugg,courier_book,courier_book | address_sugg,courier_book | нет | absent:5 ref_refused:1 | control-refused | courier_book.address.building: агент `127` / контроль `127к2` [ref_refused/house_format] |
| compare-041|0 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `20б` [absent] |
| compare-041|1 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `20б` [absent] |
| compare-041|2 | compare | chat | address_sugg,courier_book | address_sugg | да | absent:5 | Б8-echo | courier_book.address.building: агент `` / контроль `20б` [absent] |
| container-016|0 | container | voice_raw | notify_sms | notify_sms | да | ref_refused:1 | control-refused | notify_sms.number: агент `+79523039099` / контроль `+7952339099` [ref_refused/phone_not_e164] |
| container-016|1 | container | voice_raw | — | notify_sms | да | extra:1 | other | notify_sms.number: агент `+79523039099` / контроль `` [extra] |
| correction-000|0 | correction | voice_raw | upsert,courier_book | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-000|1 | correction | voice_raw | — | courier_book,upsert | нет | extra:16 | other | courier_book.address.building: агент `29` / контроль `` [extra] |
| correction-000|2 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-001|0 | correction | chat | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-001|1 | correction | chat | courier_book | courier_book,upsert | нет | extra:9 | control-partial | crm_upsert_contact.contact.address.city: агент `Воткинск` / контроль `` [extra] |
| correction-001|2 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Г.` / `В.` [derived] |
| correction-002|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Fomin Viacheslav` / контроль `Fomin Vyacheslav` [other/misderived] |
| correction-002|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-002|2 | correction | voice_raw | courier_book | courier_book,upsert | нет | extra:10 | control-partial | crm_upsert_contact.contact.address.city: агент `Сарапул` / контроль `` [extra] |
| correction-003|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | absent:1 | other | crm_upsert_contact.contact.initials: агент `` / контроль `Н.` [absent] |
| correction-003|1 | correction | voice_itn | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Самара` [absent] |
| correction-004|0 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | typo-normalised | courier_book.address.street: агент `ленна` / контроль `Ленина` [control_erred/i2] |
| correction-004|1 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | typo-normalised | courier_book.address.street: агент `ленна` / контроль `Ленина` [control_erred/i2] |
| correction-004|2 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | control_erred:2 extra:1 derived:1 other:1 | other | courier_book.address.street: агент `ленна` / контроль `Ленина` [control_erred/i2] |
| correction-005|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-005|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-005|2 | correction | voice_raw | upsert,courier_book | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `А.` / `З.` [derived] |
| correction-006|0 | correction | voice_itn | courier_book,upsert | upsert,courier_book | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `С.` / `А.` [derived] |
| correction-006|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Е.` / `А.` [derived] |
| correction-006|2 | correction | voice_itn | courier_book,upsert | upsert,courier_book | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Н.` / `А.` [derived] |
| correction-007|1 | correction | chat | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Самара` [absent] |
| correction-007|2 | correction | chat | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Самара` [absent] |
| correction-008|0 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | typo-normalised | courier_book.address.street: агент `вишнвая` / контроль `Вишнёвая` [control_erred/i2] |
| correction-008|1 | correction | voice_raw | courier_book | courier_book,upsert,notify_sms | нет | extra:10 control_erred:1 | typo-normalised | courier_book.address.street: агент `вишнвая` / контроль `Вишнёвая` [control_erred/i2] |
| correction-008|2 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:9 control_erred:1 | typo-normalised | courier_book.address.street: агент `вишнвая` / контроль `Вишнёвая` [control_erred/i2] |
| correction-009|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Т.` / `И.` [derived] |
| correction-009|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `В.` / `И.` [derived] |
| correction-009|2 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Б.` / `И.` [derived] |
| correction-010|0 | correction | voice_raw | upsert,courier_book | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-010|1 | correction | voice_raw | upsert,courier_book | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Колпино` [absent] |
| correction-010|2 | correction | voice_raw | upsert,courier_book,notify_sms | courier_book,upsert | нет | derived:1 other:1 absent:1 | partial-call | crm_upsert_contact.contact.name_latin: агент `Erokhin Petr` / контроль `Erokhin Pyotr` [other/misderived] |
| correction-011|0 | correction | sloppy | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-011|1 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-011|2 | correction | sloppy | upsert,courier_book | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-012|0 | correction | sloppy | courier_book | courier_book | нет | control_erred:1 | typo-normalised | courier_book.address.street: агент `комисарова` / контроль `Комиссарова` [control_erred/i2] |
| correction-012|1 | correction | sloppy | courier_book,upsert | courier_book | нет | absent:10 control_erred:1 | typo-normalised | courier_book.address.street: агент `комисарова` / контроль `Комиссарова` [control_erred/i2] |
| correction-012|2 | correction | sloppy | courier_book | courier_book,upsert | нет | extra:10 control_erred:1 | typo-normalised | courier_book.address.street: агент `комисарова` / контроль `Комиссарова` [control_erred/i2] |
| correction-013|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Р.` / `И.` [derived] |
| correction-013|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Л.` / `И.` [derived] |
| correction-013|2 | correction | chat | upsert | courier_book,upsert | нет | extra:7 derived:1 | derived-only | courier_book.address.building: агент `23` / контроль `` [extra] |
| correction-014|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Т.` / `А.` [derived] |
| correction-014|1 | correction | chat | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-014|2 | correction | chat | courier_book,upsert | courier_book | да | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Глазов` [absent] |
| correction-015|0 | correction | voice_itn | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Ижевск` [absent] |
| correction-015|1 | correction | voice_itn | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Ижевск` [absent] |
| correction-015|2 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Р.` / `О.` [derived] |
| correction-016|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-016|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | control_erred:1 absent:1 derived:1 other:1 | other | courier_book.contact.name: агент `фёдорова юлия` / контроль `Юлия Фёдорова` [control_erred/i3] |
| correction-016|2 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-017|0 | correction | voice_raw | courier_book,upsert | upsert,courier_book | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `С.` / `К.` [derived] |
| correction-017|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Я.` / `К.` [derived] |
| correction-017|2 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-018|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | control_erred:2 extra:1 derived:1 | typo-normalised | courier_book.address.street: агент `челюксинцев` / контроль `Челюскинцев` [control_erred/i2] |
| correction-018|1 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | control_erred:2 absent:1 derived:1 other:1 | other | courier_book.address.street: агент `челюксинцев` / контроль `Челюскинцев` [control_erred/i2] |
| correction-018|2 | correction | sloppy | courier_book | courier_book | нет | control_erred:1 | typo-normalised | courier_book.address.street: агент `челюксинцев` / контроль `Челюскинцев` [control_erred/i2] |
| correction-019|0 | correction | chat | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-019|1 | correction | chat | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-019|2 | correction | chat | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-020|0 | correction | sloppy | courier_book,upsert | courier_book,upsert | да | control_erred:2 other:1 | other | courier_book.address.street: агент `моннчегорская` / контроль `Мончегорская` [control_erred/i2] |
| correction-020|1 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | control_erred:2 absent:1 derived:1 other:1 | other | courier_book.address.street: агент `моннчегорская` / контроль `Мончегорская` [control_erred/i2] |
| correction-020|2 | correction | sloppy | courier_book,upsert | courier_book,upsert | нет | control_erred:3 extra:1 derived:1 other:1 | other | courier_book.address.street: агент `моннчегорская` / контроль `Мончегорская` [control_erred/i2] |
| correction-021|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `И.` / `Е.` [derived] |
| correction-021|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `И.` / `Е.` [derived] |
| correction-021|2 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Meshcheryakova Elena` / контроль `Voronina Elena` [other/misderived] |
| correction-022|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-022|1 | correction | voice_raw | upsert,courier_book | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-022|2 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:9 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Глазов` [absent] |
| correction-023|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Р.` / `О.` [derived] |
| correction-023|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-023|2 | correction | voice_raw | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-024|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-024|1 | correction | chat | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Воткинск` [absent] |
| correction-024|2 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Kuznetsov Dmitrii` / контроль `Kuznetsov Dmitry` [other/misderived] |
| correction-025|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-025|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | extra:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `F` / контроль `` [extra] |
| correction-025|2 | correction | voice_itn | courier_book | upsert,courier_book | нет | extra:10 | control-partial | crm_upsert_contact.contact.address.city: агент `Глазов` / контроль `` [extra] |
| correction-026|0 | correction | voice_raw | upsert,courier_book | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `А.` / `И.` [derived] |
| correction-026|1 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Х.` / `И.` [derived] |
| correction-026|2 | correction | voice_raw | upsert,courier_book,notify_sms | courier_book,upsert | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79608745165` [absent] |
| correction-027|0 | correction | voice_itn | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-027|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `В.` / `М.` [derived] |
| correction-027|2 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | extra:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| correction-028|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bitiukova Zinaida` / контроль `Bityukova Zinaida` [other/misderived] |
| correction-028|2 | correction | voice_itn | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Можга` [absent] |
| correction-029|0 | correction | chat | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Краснодар` [absent] |
| correction-029|1 | correction | chat | courier_book,upsert | courier_book | да | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Краснодар` [absent] |
| correction-030|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Kuznetsov Dmitrii` / контроль `Kuznetsov Dmitry` [other/misderived] |
| correction-030|1 | correction | chat | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-030|2 | correction | chat | courier_book | courier_book,upsert | нет | extra:9 | control-partial | crm_upsert_contact.contact.address.city: агент `Сарапул` / контроль `` [extra] |
| correction-031|0 | correction | sloppy | courier_book,upsert | — | нет | absent:16 | Б9-span | courier_book.address.building: агент `` / контроль `33` [absent] |
| correction-031|1 | correction | sloppy | courier_book,upsert | courier_book,courier_book | нет | absent:10 extra:6 stale_value:2 | partial-call | courier_book.address.building: агент `61` / контроль `33` [stale_value/p31.addr] |
| correction-031|2 | correction | sloppy | upsert,courier_book | — | нет | absent:16 | Б9-span | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-032|0 | correction | chat | courier_book,upsert | courier_book,upsert | нет | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-032|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | absent:1 derived:1 | derived-only | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-032|2 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Д.` / `И.` [derived] |
| correction-033|0 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Voronina Maria` / контроль `Voronina Elena` [other/misderived] |
| correction-033|1 | correction | chat | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `В.` / `Е.` [derived] |
| correction-033|2 | correction | chat | upsert,courier_book | courier_book,upsert | нет | derived:1 | derived-only | crm_upsert_contact.contact.initials: `В.` / `Е.` [derived] |
| correction-034|0 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Vasilev Ivan` / контроль `Vasiliev Ivan` [other/misderived] |
| correction-034|1 | correction | voice_itn | courier_book,upsert | courier_book,upsert | да | absent:1 derived:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| correction-034|2 | correction | voice_itn | courier_book,upsert | courier_book,upsert | нет | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Vasilev Ivan` / контроль `Vasilyev Ivan` [other/misderived] |
| correction-035|0 | correction | voice_raw | courier_book,upsert | courier_book,upsert | нет | absent:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| correction-035|1 | correction | voice_raw | courier_book,upsert | courier_book | нет | absent:10 | partial-call | crm_upsert_contact.contact.address.city: агент `` / контроль `Абакан` [absent] |
| correction-035|2 | correction | voice_raw | courier_book,upsert | courier_book,upsert | да | derived:1 | derived-only | crm_upsert_contact.contact.initials: `Т.` / `А.` [derived] |
| decompose-001|0 | decompose | voice_raw | courier_book | courier_book | да | reformatted:1 other:1 | other | courier_book.address.building: агент `27в` / контроль `27` [reformatted] |
| decompose-001|1 | decompose | voice_raw | courier_book | courier_book | нет | reformatted:1 other:1 | other | courier_book.address.building: агент `27в` / контроль `27` [reformatted] |
| decompose-001|2 | decompose | voice_raw | courier_book | courier_book | да | reformatted:1 other:1 | other | courier_book.address.building: агент `27в` / контроль `27` [reformatted] |
| decompose-002|2 | decompose | chat | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `PETR EROXIN` / контроль `PETR EROKHIN` [other/misderived] |
| decompose-004|0 | decompose | chat | courier_book | courier_book,courier_book,courier_book | да | extra:13 validated_refused:1 | other | courier_book.address.porch: агент `3к` / контроль `3` [validated_refused/not_an_integer] |
| decompose-004|1 | decompose | chat | courier_book | courier_book,courier_book | да | extra:6 validated_refused:1 | other | courier_book.address.porch: агент `3к` / контроль `3` [validated_refused/not_an_integer] |
| decompose-004|2 | decompose | chat | courier_book | courier_book,courier_book,courier_book | да | extra:13 validated_refused:1 | other | courier_book.address.porch: агент `3к` / контроль `3` [validated_refused/not_an_integer] |
| decompose-005|0 | decompose | voice_itn | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `ZINAIDA BITIUKOVA` / контроль `ZINAIDA BITYUKOVA` [other/misderived] |
| decompose-005|1 | decompose | voice_itn | payment_crea | — | да | absent:2 | Б9-span | payment_create.payment_method_data.card.cardholder: агент `` / контроль `ZINAIDA BITYUKOVA` [absent] |
| decompose-005|2 | decompose | voice_itn | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `ZINAIDA BITIUKOVA` / контроль `ZINAIDA BITYUKOVA` [other/misderived] |
| decompose-007|0 | decompose | clean | courier_book | courier_book | нет | control_erred:1 | control_erred | courier_book.contact.name: агент `Миллер Валерий` / контроль `Валерий Миллер` [control_erred/i2] |
| decompose-008|1 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VIKTORIA VORONINA` / контроль `ELENA VORONINA` [other/misderived] |
| decompose-013|0 | decompose | chat | courier_book | — | да | absent:7 | Б9-span | courier_book.address.building: агент `` / контроль `39` [absent] |
| decompose-013|1 | decompose | chat | courier_book | courier_book | да | validated_refused:1 | other | courier_book.address.porch: агент `6к` / контроль `6` [validated_refused/not_an_integer] |
| decompose-013|2 | decompose | chat | courier_book | courier_book,courier_book,courier_book | да | extra:13 validated_refused:1 | other | courier_book.address.porch: агент `6к` / контроль `6` [validated_refused/not_an_integer] |
| decompose-014|1 | decompose | chat | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `KSENIA GROMOVA` / контроль `MARINA GROMOVA` [other/misderived] |
| decompose-017|0 | decompose | sloppy | payment_crea | payment_crea | нет | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VIACHESLAV FOMIN` / контроль `VYACHESLAV FOMIN` [other/misderived] |
| decompose-017|1 | decompose | sloppy | payment_crea | payment_crea | нет | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VYACHESLAV FOMIN` / контроль `VIACHESLAV FOMIN` [other/misderived] |
| decompose-017|2 | decompose | sloppy | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VIACHESLAV FOMIN` / контроль `VYACHESLAV FOMIN` [other/misderived] |
| decompose-019|0 | decompose | sloppy | courier_book | courier_book,courier_book,courier_book | да | extra:13 validated_refused:1 control_erred:1 | other | courier_book.address.porch: агент `1к` / контроль `1` [validated_refused/not_an_integer] |
| decompose-019|1 | decompose | sloppy | courier_book | — | да | absent:7 | Б9-span | courier_book.address.building: агент `` / контроль `123` [absent] |
| decompose-019|2 | decompose | sloppy | courier_book | courier_book,courier_book,courier_book | да | extra:13 validated_refused:1 control_erred:1 | other | courier_book.address.porch: агент `1к` / контроль `1` [validated_refused/not_an_integer] |
| decompose-020|0 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VALERII MILLER` / контроль `VALERIY MILLER` [other/misderived] |
| decompose-020|1 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VALERII MILLER` / контроль `VALERIY MILLER` [other/misderived] |
| decompose-020|2 | decompose | voice_raw | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `VALERII MILLER` / контроль `VALERIY MILLER` [other/misderived] |
| decompose-026|2 | decompose | chat | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `ARTYOM GROMOV` / контроль `ARTEM GROMOV` [other/misderived] |
| decompose-032|2 | decompose | chat | payment_crea | payment_crea | да | other:1 | other | payment_create.payment_method_data.card.cardholder: агент `OLGA KUZNECZOVA` / контроль `OLGA KUZNETSOVA` [other/misderived] |
| decompose-037|0 | decompose | chat | courier_book | courier_book,courier_book,courier_book | да | extra:13 validated_refused:1 | other | courier_book.address.porch: агент `4к` / контроль `4` [validated_refused/not_an_integer] |
| decompose-037|1 | decompose | chat | courier_book | — | да | absent:7 | Б9-span | courier_book.address.building: агент `` / контроль `26` [absent] |
| decompose-037|2 | decompose | chat | courier_book | courier_book | да | validated_refused:1 | other | courier_book.address.porch: агент `4к` / контроль `4` [validated_refused/not_an_integer] |
| derive-000|0 | derive | chat | clinic_book | clinic_book | да | — | other |  |
| derive-000|2 | derive | chat | clinic_book | clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `38` / контроль `39` [other/misderived] |
| derive-004|1 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| derive-004|2 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| derive-005|0 | derive | chat | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bitiukova Zinaida` / контроль `Bityukova Zinaida` [other/misderived] |
| derive-005|1 | derive | chat | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bitiukova Zinaida` / контроль `Bityukova Zinaida` [other/misderived] |
| derive-008|0 | derive | voice_raw | clinic_book | clinic_book | да | — | other |  |
| derive-008|1 | derive | voice_raw | clinic_book | clinic_book | нет | — | other |  |
| derive-008|2 | derive | voice_raw | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `41` / `42` [derived] |
| derive-009|1 | derive | voice_itn | upsert | upsert | нет | extra:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-010|1 | derive | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 | typo-normalised | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-012|0 | derive | chat | clinic_book | clinic_book | да | — | other |  |
| derive-012|1 | derive | chat | clinic_book | clinic_book | да | — | other |  |
| derive-012|2 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `38` / `39` [derived] |
| derive-013|0 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Fomin Viacheslav` / контроль `Fomin Vyacheslav` [other/misderived] |
| derive-013|1 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Fomin Gennady` / контроль `Fomin Vyacheslav` [other/misderived] |
| derive-013|2 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Fomin Viacheslav` / контроль `Fomin Vyacheslav` [other/misderived] |
| derive-016|0 | derive | voice_raw | clinic_book | — | да | absent:7 | Б9-span | clinic_book.patient.age: агент `` / контроль `70` [absent] |
| derive-016|1 | derive | voice_raw | clinic_book | — | да | absent:7 | Б9-span | clinic_book.patient.age: агент `` / контроль `70` [absent] |
| derive-016|2 | derive | voice_raw | clinic_book | — | да | absent:7 | Б9-span | clinic_book.patient.age: агент `` / контроль `70` [absent] |
| derive-018|0 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 | other | delivery_create_order.to_location.address: агент `пер. лениа, 11, кв. 150` / контроль `переулок Ленина, 11, кв. 150` [other/unbound] |
| derive-018|1 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 | typo-normalised | delivery_create_order.to_location.address: агент `переулок лениа, 11, кв. 150` / контроль `переулок Ленина, 11, кв. 150` [other/unbound] |
| derive-018|2 | derive | sloppy | delivery_cre | delivery_cre | да | other:1 | other | delivery_create_order.to_location.address: агент `пер. лениа, 11, кв. 150` / контроль `переулок Ленина, 11, кв. 150` [other/unbound] |
| derive-020|0 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `46` / `45` [derived] |
| derive-020|1 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `46` / `45` [derived] |
| derive-020|2 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `46` / `45` [derived] |
| derive-021|0 | derive | chat | upsert | upsert | нет | extra:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-021|1 | derive | chat | upsert | upsert | да | extra:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-021|2 | derive | chat | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Kukushkin Valerii` / контроль `Kukushkin Valeriy` [other/misderived] |
| derive-024|0 | derive | voice_raw | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `57` / `56` [derived] |
| derive-024|1 | derive | voice_raw | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `57` / `56` [derived] |
| derive-024|2 | derive | voice_raw | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `57` / `56` [derived] |
| derive-025|0 | derive | voice_raw | upsert | upsert | нет | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Gromova Lidia` / контроль `Gromova Marina` [other/misderived] |
| derive-025|2 | derive | voice_raw | upsert | upsert | да | derived:1 other:1 | other | crm_upsert_contact.contact.name_latin: агент `Meshcheryakova Marina` / контроль `Gromova Marina` [other/misderived] |
| derive-027|1 | derive | voice_raw | callback_sch | callback_sch | да | control_erred:1 | typo-normalised | callback_schedule.phone: агент `+79611669251` / контроль `+79601669251` [control_erred/i2] |
| derive-028|1 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `24` / `25` [derived] |
| derive-028|2 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `24` / `25` [derived] |
| derive-032|0 | derive | chat | clinic_book | clinic_book | да | other:1 | other | clinic_book.patient.age: агент `26` / контроль `27` [other/misderived] |
| derive-033|0 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valerii` / контроль `Miller Valeriy` [other/misderived] |
| derive-033|1 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valerii` / контроль `Miller Valeriy` [other/misderived] |
| derive-033|2 | derive | voice_raw | upsert | upsert | нет | extra:1 other:1 | other | crm_upsert_contact.contact.gender: агент `M` / контроль `` [extra] |
| derive-036|0 | derive | voice_itn | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| derive-036|1 | derive | voice_itn | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| derive-036|2 | derive | voice_itn | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| derive-037|0 | derive | voice_itn | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valerii` / контроль `Miller Valeriy` [other/misderived] |
| derive-037|1 | derive | voice_itn | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valerii` / контроль `Miller Valeriy` [other/misderived] |
| derive-037|2 | derive | voice_itn | upsert | upsert | да | absent:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `M` [absent] |
| derive-040|0 | derive | voice_raw | clinic_book | clinic_book | да | — | other |  |
| derive-040|1 | derive | voice_raw | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `38` / `39` [derived] |
| derive-040|2 | derive | voice_raw | clinic_book | clinic_book | нет | — | other |  |
| derive-041|0 | derive | sloppy | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Poliakova Valentina` / контроль `Polyakova Valentina` [other/misderived] |
| derive-041|1 | derive | sloppy | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Poliakova Maria` / контроль `Polyakova Valentina` [other/misderived] |
| derive-041|2 | derive | sloppy | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Poliakova Valentina` / контроль `Polyakova Valentina` [other/misderived] |
| derive-042|2 | derive | voice_itn | delivery_cre | delivery_cre | да | control_erred:1 | typo-normalised | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-044|0 | derive | chat | clinic_book | clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `23` / `24` [derived] |
| derive-044|1 | derive | chat | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `23` / `24` [derived] |
| derive-045|0 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bitiukova Zinaida` / контроль `Bityukova Zinaida` [other/misderived] |
| derive-045|1 | derive | voice_raw | upsert | upsert | да | absent:1 other:1 | other | crm_upsert_contact.contact.gender: агент `` / контроль `F` [absent] |
| derive-045|2 | derive | voice_raw | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Bitiukova Zinaida` / контроль `Bityukova Zinaida` [other/misderived] |
| derive-046|0 | derive | voice_raw | delivery_cre | delivery_cre | да | other:1 | other | delivery_create_order.to_location.address: агент `улица шумайлого, 26, кв. 208` / контроль `улица Шумайлова, дом 26, квартира 208` [other/unbound] |
| derive-046|1 | derive | voice_raw | delivery_cre | delivery_cre | да | other:1 | typo-normalised | delivery_create_order.to_location.address: агент `ул. шумайлого, д. 26, кв. 208` / контроль `ул. Шумайлова, д. 26, кв. 208` [other/unbound] |
| derive-048|0 | derive | chat | clinic_book | clinic_book | да | — | other |  |
| derive-049|0 | derive | voice_itn | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valeriia` / контроль `Miller Valeria` [other/misderived] |
| derive-049|1 | derive | voice_itn | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valeriia` / контроль `Miller Valeria` [other/misderived] |
| derive-049|2 | derive | voice_itn | upsert | upsert | да | other:1 | other | crm_upsert_contact.contact.name_latin: агент `Miller Valeriia` / контроль `Miller Valeria` [other/misderived] |
| derive-050|1 | derive | chat | delivery_cre | delivery_cre | нет | control_erred:1 | typo-normalised | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-050|2 | derive | chat | delivery_cre | delivery_cre | да | control_erred:1 | typo-normalised | delivery_create_order.recipient.name: агент `ерохин пётр` / контроль `Ерохин Петр` [control_erred/i1] |
| derive-052|1 | derive | voice_itn | clinic_book | clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `64` / `65` [derived] |
| result_feed-003|0 | result_feed | chat | find,clinic_book | find,clinic_book,notify_sms | да | derived:1 extra:1 | derived-only | notify_sms.number: агент `+79030041566` / контроль `` [extra] |
| result_feed-003|2 | result_feed | chat | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-004|2 | result_feed | chat | find,clinic_book | find,clinic_book | нет | other:1 | other | clinic_book.patient.age: агент `57` / контроль `58` [other/misderived] |
| result_feed-005|0 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | да | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79261234567` [absent] |
| result_feed-005|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79261234567` [absent] |
| result_feed-005|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-009|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | other:1 | other | clinic_book.patient.age: агент `27` / контроль `28` [other/misderived] |
| result_feed-009|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-013|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book,notify_sms | нет | extra:1 | control-partial | notify_sms.number: агент `+79998831789` / контроль `` [extra] |
| result_feed-013|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `64` / `65` [derived] |
| result_feed-014|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| result_feed-014|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `42` / `41` [derived] |
| result_feed-015|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `56` / `57` [derived] |
| result_feed-015|1 | result_feed | sloppy | find,clinic_book,notify_sms | find,clinic_book | да | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79129876543` [absent] |
| result_feed-015|2 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `56` / `57` [derived] |
| result_feed-016|0 | result_feed | voice_raw | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79778446323` [absent] |
| result_feed-016|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book,notify_sms | нет | extra:1 | control-partial | notify_sms.number: агент `+79778446323` / контроль `` [extra] |
| result_feed-016|2 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `37` / `38` [derived] |
| result_feed-017|0 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79993861689` [absent] |
| result_feed-017|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79993861689` [absent] |
| result_feed-017|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book,notify_sms | нет | extra:1 | control-partial | notify_sms.number: агент `+79993861689` / контроль `` [extra] |
| result_feed-019|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-019|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | other:1 | other | clinic_book.patient.age: агент `27` / контроль `28` [other/misderived] |
| result_feed-019|2 | result_feed | sloppy | find,clinic_book,notify_sms | find,clinic_book,notify_sms | да | other:1 | other | clinic_book.patient.age: агент `27` / контроль `28` [other/misderived] |
| result_feed-020|0 | result_feed | chat | find,clinic_book,notify_sms | find | нет | absent:8 | Б8-echo | clinic_book.patient.age: агент `` / контроль `45` [absent] |
| result_feed-020|1 | result_feed | chat | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `46` / `45` [derived] |
| result_feed-020|2 | result_feed | chat | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `46` / `45` [derived] |
| result_feed-021|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `33` / `32` [derived] |
| result_feed-021|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `33` / `32` [derived] |
| result_feed-021|2 | result_feed | voice_raw | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79892320740` [absent] |
| result_feed-023|0 | result_feed | sloppy | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-023|1 | result_feed | sloppy | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-026|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-026|1 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `51` / `52` [derived] |
| result_feed-026|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book,notify_sms | нет | extra:1 | control-partial | notify_sms.number: агент `+79607234737` / контроль `` [extra] |
| result_feed-027|0 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book,notify_sms | нет | — | other |  |
| result_feed-027|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | да | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79035416931` [absent] |
| result_feed-028|0 | result_feed | chat | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-028|1 | result_feed | chat | find,clinic_book | find,clinic_book,notify_sms | нет | derived:1 extra:1 | derived-only | notify_sms.number: агент `+79099042924` / контроль `` [extra] |
| result_feed-029|1 | result_feed | chat | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-029|2 | result_feed | chat | find,clinic_book | find,clinic_book | нет | — | other |  |
| result_feed-031|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `29` / `30` [derived] |
| result_feed-031|2 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `29` / `30` [derived] |
| result_feed-032|0 | result_feed | voice_raw | find,clinic_book | find,clinic_book,notify_sms | да | extra:1 | control-partial | notify_sms.number: агент `+79512022704` / контроль `` [extra] |
| result_feed-032|1 | result_feed | voice_raw | find,clinic_book | find,clinic_book | да | derived:1 | derived-only | clinic_book.patient.age: `27` / `26` [derived] |
| result_feed-032|2 | result_feed | voice_raw | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `27` / `26` [derived] |
| result_feed-033|0 | result_feed | chat | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `57` / `56` [derived] |
| result_feed-033|1 | result_feed | chat | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `57` / `56` [derived] |
| result_feed-033|2 | result_feed | chat | find,clinic_book,notify_sms | find,clinic_book | нет | derived:1 absent:1 | derived-only | notify_sms.number: агент `` / контроль `+79050794728` [absent] |
| result_feed-034|0 | result_feed | voice_itn | find,clinic_book | find,clinic_book | да | — | other |  |
| result_feed-034|1 | result_feed | voice_itn | find,clinic_book,notify_sms | find,clinic_book | нет | absent:1 | partial-call | notify_sms.number: агент `` / контроль `+79097619209` [absent] |
| result_feed-034|2 | result_feed | voice_itn | find,clinic_book | find,clinic_book | нет | derived:1 | derived-only | clinic_book.patient.age: `46` / `47` [derived] |
| summary-011|0 | summary | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 | typo-normalised | delivery_create_order.recipient.phones[0].number: агент `+79279061650` / контроль `+79279661650` [control_erred/i2] |
| summary-011|1 | summary | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 | typo-normalised | delivery_create_order.recipient.phones[0].number: агент `+79279061650` / контроль `+79279661650` [control_erred/i2] |
| summary-011|2 | summary | voice_raw | delivery_cre | delivery_cre | нет | control_erred:1 | typo-normalised | delivery_create_order.recipient.phones[0].number: агент `+79279061650` / контроль `+79279661650` [control_erred/i2] |
| summary-018|0 | summary | voice_raw | find,delivery_cre | — | да | absent:6 | Б10-city | crm_find_contact.query.phone: агент `` / контроль `+79992635617` [absent] |
| summary-018|1 | summary | voice_raw | delivery_cre | find,delivery_cre | да | extra:1 validated_refused:1 | control-partial | crm_find_contact.query.phone: агент `+76666252016` / контроль `` [extra] |
| summary-018|2 | summary | voice_raw | find,delivery_cre | find,delivery_cre | нет | extra:1 absent:1 validated_refused:1 | other | crm_find_contact.query.last_name: агент `громова` / контроль `` [extra] |
| summary-028|2 | summary | voice_raw | find,delivery_cre | delivery_cre | нет | absent:1 other:1 | typo-normalised | crm_find_contact.query.phone: агент `` / контроль `+79990750454` [absent] |
| validate-017|0 | validate | voice_raw | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `181-547-959 03` / контроль `` [extra] |
| validate-023|2 | validate | voice_itn | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `738-092-586 32` / контроль `` [extra] |
| validate-029|1 | validate | chat | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `013-184-880 31` / контроль `` [extra] |
| validate-032|1 | validate | sloppy | passport_ver | passport_ver | нет | extra:1 | other | passport_verify.snils: агент `513-209-526 47` / контроль `` [extra] |
