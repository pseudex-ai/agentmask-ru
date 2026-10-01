# A1 — SPEC: точный acceptance manifest для O-DATA и независимый протокол разметки

Статус: **design/RED-волна, не product implementation.** Gate задачи — `GATE.json`,
`status = OWNER_PENDING`. Этот документ ничего не объявляет принятым: строгий
quality-gate G7, релиз и production остаются открытыми. `production_artifact_gate`
из B0 остаётся `NOT_MEASURED` и блокирует RG release-A/B.

## 1. Что именно требуется от A1

Постановка ([FIRST-WAVE-TASKS.json:8](<research/quality-sprint-2026-09-30/work/FIRST-WAVE-TASKS.json#L8>),
[SPRINT-PLAN.md:119](<research/quality-sprint-2026-09-30/SPRINT-PLAN.md#L119>)):

> Подготовить точный draft acceptance manifest для O-DATA и независимый протокол
> разметки **из уже существующих source counts и согласованного owner scope**.
> Не производить final gold и **не выбирать сэмплы по детекторным предсказаниям**.

Обязательный результат O-DATA ([SPRINT-PLAN.md:159](<research/quality-sprint-2026-09-30/SPRINT-PLAN.md#L159>)):
единица подсчёта, список slices, тип CI, support, cluster-ключ для повторов, бюджет
разметки и невидимый разработчику acceptance split.

## 2. Binding-решения, из которых выведен манифест

| ID | Источник | Literal | Что фиксирует |
|---|---|---|---|
| OWNER-Q1 | [OWNER-DECISIONS.md:19](<research/quality-sprint-2026-09-30/OWNER-DECISIONS.md#L19>) | «≥99% на выборке + размер и ДИ» | point estimate ≥99% на согласованных type/register, support и CI публикуются; **нижняя граница CI ≥99% не выбрана** |
| OWNER-SUPPORT | [REMAINING-DECISIONS.md:34](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L34>) | «не менее 300 независимых позитивных единиц на основной заявляемый тип/срез плюс достаточная отдельная проверка precision» | orient 300; повторы/шаблоны не независимые единицы; малый срез не полная приёмка |
| OWNER-LABELERS | [REMAINING-DECISIONS.md:33](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L33>) | «два независимых разметчика, сначала только исходный текст/правила, без detector output» | протокол разметки; расхождения — владельцу |
| OWNER-LEXAMB | [REMAINING-DECISIONS.md:8](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L8>) | «Не маскировать по одной двусмысленной форме» | «жене» без свидетельств имени — не автоматический NAME и не автоматический FP |
| OWNER-ALLPARTS | [OWNER-DECISIONS.md:37](<research/quality-sprint-2026-09-30/OWNER-DECISIONS.md#L37>) | «Да, это дефект, защищаем все части» | FIO: все части одной персоны защищены; частичный промах — утечка, не recall |
| OWNER-ADDR | [OWNER-DECISIONS.md:38](<research/quality-sprint-2026-09-30/OWNER-DECISIONS.md#L38>) | «все личные компоненты, не маркеры» | улица+тип+дом+корпус+квартира+подъезд+этаж — личные компоненты; голый топоним — нет |
| OWNER-MALFORMED-ID | [OWNER-DECISIONS.md:27](<research/quality-sprint-2026-09-30/OWNER-DECISIONS.md#L27>) | «Защищать при доказанном типовом контексте» | ошибочный личный ID — позитив, форму не исправлять |
| OWNER-PUBLIC | [REMAINING-DECISIONS.md:9](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L9>) | «Одинаково защищать все личные имена» | публичные/вымышленные/сценические — позитивы; отдельная страта |
| OWNER-BRAND | [REMAINING-DECISIONS.md:10](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L10>) | «Да, по значению в контексте» | бренд/компания/группа не NAME только по форме; без blacklist |
| OWNER-POSSESSIVE | [REMAINING-DECISIONS.md:7](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L7>) | «Да, защищать и сохранять форму» | «Жениного/Олино» при подтверждении — позитив с сохранением грамматики |
| OWNER-PPV-VS-SPEC | [GOAL-BRIEF.md:156](<research/quality-sprint-2026-09-30/GOAL-BRIEF.md#L156-L158>) | «NEREL any-annotation-support не настоящая PPV; clean-negative specificity не precision» | PPV и specificity — разные оси и разные frame |
| OWNER-SECRET | [REMAINING-DECISIONS.md:21-25](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L21-L25>) | CVC «В любой ответ той же операции»; OTP/3DS/SMS «Да, исследовать всё семейство» | временные секреты в denominator, синтетический изолированный путь, lifecycle отложен |

## 3. Принцип, который проверяет предложение

Манифест приёмки обязан быть устроен так, чтобы **прибор не мог дать PASS по
построению**:

1. **Независимость.** Одно и то же лицо/адрес/шаблон, повторённое N раз, — одна
   единица (`(type, identity)` cluster); повторения и шаблонные копии не набирают 300.
2. **Слепота.** Все уже сгенерированные и/или прочитанные наборы помечены
   `known_diagnostic` и не могут быть blind acceptance; blind split генерируется
   заново к freeze и его labels держит человек-владелец.
3. **PPV ≠ specificity.** PPV считается на сэмпле детекторных **позитивов**;
   specificity — на отдельном предрегистрированном frame **негативов**. Числа не
   сливаются и не подменяют друг друга.
4. **Пустой знаменатель и малый N — не успех.** `NOT_MEASURED` при нулевом
   знаменателе; `DESCRIPTIVE_INSUFFICIENT_SUPPORT` ниже 300 независимых единиц;
   тип/срез остаётся в таблице, но не получает headline PASS.
5. **Два разметчика, слепые к детектору**, плюс владелец на расхождениях и
   стратифицированной проверке согласованных меток.

## 4. Что реально посчитано (не оценка)

Read-only инвентаризация: [inventory_sources.py](<research/quality-sprint-2026-09-30/work/A1/inventory_sources.py>)
→ [INVENTORY.json](<research/quality-sprint-2026-09-30/work/A1/INVENTORY.json>),
[INVENTORY.log](<research/quality-sprint-2026-09-30/work/A1/INVENTORY.log>) (exit 0);
деривация [derive_gaps.py](<research/quality-sprint-2026-09-30/work/A1/derive_gaps.py>)
→ [DATA-GAPS.csv](<research/quality-sprint-2026-09-30/work/A1/DATA-GAPS.csv>) (511 строк),
[DATA-GAPS-SUMMARY.json](<research/quality-sprint-2026-09-30/work/A1/DATA-GAPS-SUMMARY.json>)
(exit 0).

Детектор не импортировался, bundle не загружался, ни один prediction/eval/hop/judge
артефакт не читался; `ru_prose.jsonl` (0 байт) — отсутствует, а не «пустой PASS».

| Source | Count |
|---|---|
| `corpus.v5.json` (frozen v5 case definitions) | 1800 cases · 16 287 PII occurrences · 2201 уникальных identity · 1260 clusters · 663 conversations · 1800 authored negatives |
| paid run `cc3a551f` corpus | 813 cases · 8191 occurrences · 1183 identity · 594 clusters · 303 conversations |
| `dataset.json` / `dirty.json` | 100 cases / 298 entities · 150 cases / 150 entities / 12 negatives |
| `stress.json` / `stress2.json` | 600 cases / 1033 entities / 152 negatives · 600 / 1033 / 129 |
| `bench/gate/labels.json` | **587** размеченных вхождений (`person 271`, `other 209`, `public 57`, `place 26`, `address 24`); кандидатов 3054 |
| NEREL v1.1 dev+test | 1908 person-annotation rows · 187 docs (182 с person) |
| PII-Bench domain+entity | 1810 rows · 1667 entity occurrences |
| MASSIVE ru | 1215 person-slot occurrences · 888 unique surface (slot ≠ PII NAME) |
| RuDevices voice/rudevices addresses | 1373 / 650 records; «адрес с номером» 43 / 154 |
| v6 registry | 66 entries = 55 ORIGIN_V6 + 11 v5; 9 «ГРАММАТИКА?»; 15 industries; **0 сгенерированных v6 cases на хосте** |
| temporary secrets | корпуса нет; 4 CVC episode records, context-matrix, probes — prior research |

### 4.1 Реальные разрывы до 300 независимых единиц

Из [DATA-GAPS-SUMMARY.json](<research/quality-sprint-2026-09-30/work/A1/DATA-GAPS-SUMMARY.json>)
(identity clusters внутри frozen 1800-case корпуса):

| Type | occurrences | independent identities | gap до 300 |
|---|---:|---:|---:|
| NAME | 6373 | 1188 | 0 |
| LOC | 2797 | 985 | 0 |
| PHONE | 3181 | 883 | 0 |
| DOB | 1562 | 544 | 0 |
| EMAIL | 1298 | 459 | 0 |
| PLATE | 289 | 154 | 146 |
| INN | 263 | 144 | 156 |
| SNILS | 224 | 128 | 172 |
| CARD | 200 | 123 | 177 |
| PASSPORT | 100 | 63 | 237 |

Пять из десяти native типов **не имеют 300 независимых единиц ни в одном наборе
на хосте**; это не «маленькая выборка» по недосмотру, а измеренный дефицит, который
надо либо закрыть расширением генерации, либо честно назвать descriptive (вопрос
`Q-A1-3`).

### 4.2 v6 не может дать 300/тип при 500 кейсах

[TZ v6 §4.3](<research/hop-format-audit/next-sprint-review/v6-snapshot/tz-agentpii6.md#L620>)
планирует 500 случаев, 15 отраслей, 55 новых типов при 2,72–3,74 новых типа на
случай → **≈25–34 независимые единицы на новый тип**, на порядок ниже 300. Для
300/тип по проекции нужно ≈4400–6100 случаев. Это arithmetic из чужого ТЗ, не
измерение (v6-корпуса на хосте нет), и это развилка `Q-A1-4`.

### 4.3 Наблюдаемое расхождение прибора

README гейта говорит «600 размеченных вручную вхождений» (300 замаскировано + 300
пропущено), а durable `labels.json` содержит **587**. 13 размеченных вхождений в
текущем файле отсутствуют — зафиксировано как наблюдаемое расхождение, не
разрешено и не «исправлено» здесь. Кандидатов в snapshot 3054 (2476 + 578).

## 5. Точное требование к O-DATA (что предлагается принять)

Полный манифест — [ACCEPTANCE-PROPOSAL.json](<research/quality-sprint-2026-09-30/work/A1/ACCEPTANCE-PROPOSAL.json>).
В сжатом виде:

1. **Registry scope:** 10 native item types (DATE отдельно, non-item) + 55 новых v6
   типов + временные секреты (CVC/CVV/CID/OTP/SMS_CODE/THREEDS, synthetic isolated);
   lifecycle/storage/admin/API/HITL — вне scope.
2. **Slices:** оси `pii_type × register {clean,chat,sloppy,voice_raw,voice_itn} ×
   surface (22 case kinds как прокси) × hop_direction × transport × document_form`;
   headline только при ≥300 независимых позитивов на слайсе.
3. **Units:** позитивная единица = gold-вхождение с cluster-ключом; NAME
   раскрывается в parts; whole coverage требует все написанные части; PPV-единица =
   детекторный позитив; specificity-единица = предрегистрированный негатив.
4. **Clusters:** `(type, identity)`, для адреса — address identity, для документа —
   case/conversation, для шаблона — `provenance.shape` (в v5 пусто → fallback
   `(case id, type, identity)` фиксируется как ограничение независимости).
5. **Known vs blind:** 15 наборов перечислены как `known_diagnostic`;
   blind acceptance — новый split при freeze, labels у человека-владельца; 359-ID
   tier — только вторичный с оговоркой 0/359.
6. **Разметка:** 2 слепых разметчика, 12 категорий меток, правила для
   «жене»/FIO all parts/притяжательных/публичных/бренда/подъезда-этажа/ошибочных
   личных ID/бизнес-номеров; disputes — владельцу; стратифицированная проверка
   согласованных.
7. **CI/статусы:** Wilson 95% + cluster bootstrap (deff печатается); point estimate
   ≥99% по решению владельца; `NOT_MEASURED` при нулевом знаменателе;
   `DESCRIPTIVE_INSUFFICIENT_SUPPORT` при n<300; никакого усреднения по слайсам.
8. **Неизменяемость/доступ:** sha256 всех артефактов при freeze; append-only JSONL
   access log на каждое чтение blind-артефакта; labels/blind/detector outputs — в
   разных каталогах с разными владельцами.
9. **Бюджет:** в human review items (не в деньгах): формула + планировочный расчёт
   `units_native_only=6600` / `units_full_scope=8320`; labeler-items 13 200 / 16 640;
   owner disputes 330–990 / 416–1248; стратифицированная проверка согласованных
   707–790; итог ≈14 200–14 800 (native+PPV+specificity) и ≈17 800–18 600 (полный
   scope с v6 и временными секретами). Ставка расхождений 5–15% — **допущение, не
   измерение**; budget GO остаётся за владельцем.

## 6. Неприемлемые альтернативы

- считать occurrences, а не независимые identity-кластеры, за support;
- добирать 300 лёгкими регистрами и объявлять сложный регистр покрытым;
- использовать authored gold как frame для PPV;
- называть clean-negative specificity точностью;
- считать MASSIVE person-slot PII NAME автоматически;
- принять prior `name-labels-blind-proposal` за gold;
- объявлять малый срез полной приёмкой или убирать неподдержанный тип из таблицы;
- менять условие владельца «point estimate ≥99% + CI» в любую сторону;
- править blind split/labels на месте после чтения;
- называть уже измеренный чужой корпус fresh holdout;
- вводить новые provenance API-поля (сейчас не разрешены).

## 7. Открытые вопросы (OWNER_PENDING)

10 вопросов вынесены в [OWNER-QUESTIONS.md](<research/quality-sprint-2026-09-30/work/A1/OWNER-QUESTIONS.md):
единица независимости, источник support, 5 недоукомплектованных native типов,
v6 per-type vs per-family, страта публичных имён, custodian blind split, бюджет
разметки, статус 359-ID tier, synthetic support для временных секретов, граница
подъезд/этаж. Ожидаемый ответ — O-DATA decision id; до него D1/Q1 не могут
объявлять quality gates по этому протоколу.

## 8. Границы этой задачи

Сделано: read-only инвентаризация источников, точные counts/hashes, gap-арифметика,
манифест-предложение, протокол разметки, CI/статусы, cost в review items, owner
вопросы. Не сделано намеренно: final gold, выбор сэмплов, любая правка engine/
scorer/benchmark/corpus, downloads/installs, provider-вызовы, изменение
`EXECUTION.json`/usage-журнала, любые git-мутации. `GATE.json` = `OWNER_PENDING`;
никакой части всего качества или paid GO эти ворота не подтверждают.
