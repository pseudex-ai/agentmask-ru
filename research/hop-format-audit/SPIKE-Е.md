# SPIKE Е — прибор/корпус смешивает причины

## Корень

Прибор отвечает **одним символом на три разных вопроса** и **одним знаменателем на три разных
популяции**. Это не «неточность скорера»: пока `absent` (агент не написал), `unmasked`
(подстановки в листе не было — и причин у этого три) и настоящий промах восстановления делят
одну клетку, число `end_to_end 41%` — утверждение о **траектории свободного агента**, а не о
движке. DIAGNOSIS (§Рефрейм, §Е) называет это первым по важности именно потому, что до
развязывания знаменателей любая правка движка не сдвинет headline: сигнал утонет в шуме.

Три факта, живущие сегодня под одним словом `unmasked` (`contracts.py:1649-1653`,
`observe.py:1151`):

1. **Агент не написал лист** — вызвал инструмент и оставил позицию пустой. Это факт об агенте,
   ровно тот, для которого заведён `out_absent`, — но на уровень ниже его не опустили
   (`observe._out_status` не отличает пустую строку от «значения нет вовсе»).
2. **Движок осознанно не маскировал** — населённый пункт внутри адреса, родовое слово,
   пол, домен. `pseudex/vault.py:1144-1163::_settlement_of` объясняет, ПОЧЕМУ это правильно
   («what the law does not protect stays true»), и `contracts.py:1094::GENERIC_PIECE_ROLES`
   уже перечисляет эти роли. Движок прав — прибор ставит промах.
3. **В лист ушло чужое значение** — не настоящее и не подмена (третья величина). Инструмент
   получил не то, и `form_match` этого не увидит: `verdict is None`, `produced == reference`.

Плюс четыре приборных дефекта той же природы:

4. **`optional` чтится только когда нет ВЫЗОВА.** `contracts.py:153-157` обещает: «an optional
   hop that did not happen is not observed and counts nowhere». `observe.py:1164-1166` проверяет
   `call is None`, и пустой лист внутри состоявшегося вызова до этой ветки не доходит вовсе.
   Корпус свою работу сделал (`scenarios5/common.py:465`, `revise.py:246`:
   `optional = not spec.required`), наблюдатель её отменяет.
5. **Обязательный хоп объявляется на листе, который правильный шлюз не может заработать.**
   `courier_book.address.locality` — `required=True, role='city'`: `_settlement_of` держит город
   реальным **по построению**, а `arg_hop` решает обязательность только по `FieldSpec.required`.
6. **Расписание принадлежит корпусу.** `observe.call_for_hop` (`observe.py:732`) берёт
   `same[hop.call_ordinal]` строго внутри `hop.turn`: вызов, сделанный ходом раньше, читается
   `absent`, хотя значение доехало верно.
7. **Эквивалентности листьев нет.** `crm_upsert_contact.contact.address.* ≡
   courier_book.address.*`, `contact.address.city ≡ address.locality` — таблицы нет, и агент,
   записавший тот же payload в семантически тот же лист, получает `absent`.

Итог: `end_to_end`/`chain_value`/`multi_all_out` (`metrics.py:404-430`, `819-843`, `860-875`) и
`form_hOUT` (`metrics.py:575-590`) считают по **расписанию корпуса**, а не по тому, что шлюз
сделал. Свидетели:
- **g02** (`memory_anaphora`): `end_to_end 67/226 = 0.296`; разложение 226 объявленных листьев —
  **observed 67, absent 150, unmasked 9**; `multi_all_out 0/56` (в 55 из 56 ходов агент не написал
  ОБА листа — сцена не даёт интервала, который требует схема `courier_book`); честная оценка
  группы по написанным листьям ≈96%. P6: `m-083/086/106` — `crm_find_contact.query.phone` внутри
  СДЕЛАННОГО вызова пуст, статус всё равно `unmasked`.
- **g04** (`long_order+correction`): `end_to_end 64/351 = 0.182` при **273/345 absent**; по
  написанным листьям `64/72 = 0.889`; `form OUT/tool_arg 423/560 = 0.755` против **423/441 =
  0.959** на сравнимых; П8 — все 119 `unmasked` группы по листьям: city 82, целый address 11,
  locality 9, building 6, sflat 6, street/flat/house по 1, телефон/номер 2.
- **g01**, **g07**, **g08**, **g14** — в разделе «Механизм» и в RED-тесте.

## Механизм (файл+строки)

Путь одного OUT-листа, шаг за шагом.

**Шаг 1. Наблюдатель ищет вызов по расписанию корпуса.** `observe.observe` (`observe.py:1405-1447`)
для `OUT`/`tool_arg` зовёт `_out_call` (`observe.py:1155-1175`) → `call_for_hop`
(`observe.py:732-735`):
```python
same = [call for _index, call in calls_of_turn(run, hop.turn) if call.name == hop.tool_name]
return same[hop.call_ordinal] if 0 <= hop.call_ordinal < len(same) else None
```
Ход — **объявленный** (`hop.turn`), ординал — **объявленный**. Отсюда g14: 118/150 (79%)
знаменателя `end_to_end` — `absent`, из них **68** — инструмент вызван, но в другом ходу;
`_extra_call_hops` (`observe.py:1339+`) видит этот вызов как `declared=False` и в знаменатели не
пускает. g04 формулирует то же: «агент сделал тот же вызов в другом ходу, другим `ordinal`».

**Шаг 2. Пустой вызов → `absent`, пустой ЛИСТ → `unmasked`.** Там же:
```python
call = call_for_hop(run, hop)
if call is None:
    return None if hop.optional else _flat(case, repeat, hop, True, item.type, "", "", "absent")
written = leaf_text(flatten(call.written), hop.tool_name, hop.path)   # ""
```
`call is None` — единственное место, где читается `hop.optional`. Дальше `written == ""` уходит в
`_out_status`.

**Шаг 3. `_out_status` — воронка, у которой один выход.** `observe.py:1126-1153`:
```python
if not _leaf_carries(item, spec, surfaces, minted, written, own):
    return "unmasked"          # ← observe.py:1151: три разных факта в одну строку
return "residual" if _leaf_carries(item, spec, surfaces, minted, restored, own) else "observed"
```
`_leaf_carries` (`observe.py:1104-1124`) отвечает ровно на один вопрос — «стоит ли в листе кусок
ПОДМЕНЫ». Отрицательный ответ не различает: лист пуст / в листе настоящее значение (движок не
маскировал — по праву или по отказу) / в листе третья величина. `produced`/`reference` при этом
берутся из `restored`/`written`, поэтому у «пусто» и у «чужое» сравнение — строка сама с собой,
`verdict=None`, и в отчёте нет ни одной клетки, где этот факт назван. Свидетели: g02 P6
(`m-083/086/106` — пустой лист; `095/118/120` — подделка ушла в инструмент: та же метка),
g01 P6а (18 из 25 `unmasked tool_arg` — `courier_book.address.locality` с НАСТОЯЩИМ городом),
g04 П8 (102 из 119 — город/место), g07 P7б (`address.locality` «не может стать `observed` по
построению»), g08 P1 (42 `unmasked` = 24 необязательных незаполненных листа + 8 городов с
ВЕРНЫМ значением + 5 `kb_search.query` + 2 переписанных телефоном + 2 LOC-части +
1 `mail_search`), g14 P4 (19 `unmasked` = 9 город + 10 незаполненных необязательных).

**Шаг 4. Знаменатели.** `metrics.end_to_end` (`metrics.py:404-430`) — `total += 1` на КАЖДЫЙ
объявленный лист, включая `absent` (и, что видно в `A2` RED-теста, даже НЕОБЯЗАТЕЛЬНЫЙ хоп с
пустым листом); хит — только `status == "observed" and _item_value_ok(...)`. `_transitions`
(`metrics.py:793-817`) и `_multi_turns` (`metrics.py:846-859`) фильтруют только `declared` и
`not optional`, статус не смотрят вовсе, — поэтому ход, где агент не написал ничего, это `0/1`
(g02: 55 из 56). `form_hOUT` (`metrics.py:575-590`) берёт знаменатель по `status in ("observed",
"unmasked")` — то есть пустой лист внутри СДЕЛАННОГО вызова считается и там. Единственная
декомпозиция — `out_absent` (`metrics.py:593-600`), диагностика, и она **недосчитывает ровно на
число пустых листов**: RED-тест C9 печатает `out_absent 0/3` там, где ненаписанных листьев два и
оба — пустые слоты внутри сделанного вызова (сегодня они `unmasked`, и потому не в счёте). Значит и «273 из 345» g04
измерено на сломанном статусе и после починки сдвинется.

**Шаг 5. Контракт `optional` нарушен собственным docstring.** `contracts.py:153-157`:
«An optional hop that did not happen is not observed and counts nowhere; a required hop that did
not happen is `absent`». `_out_answer` (`observe.py:1309-1323`) это правило исполняет:
`return None if hop.optional else ...`. `_out_call` — нет. Асимметрия двух веток одного файла и
есть дефект; корпус уже пометил такие листья необязательными (`scenarios5/common.py:441-467`,
`optional=not spec.required`; `revise.py:241-246`).

**Шаг 6. Причина необязательности выбрана неверно.** `arg_hop`
(`scenarios5/common.py:441-467`) решает обязательность по `FieldSpec.required`, а роль листа не
смотрит. Проверено (`spec_v5_for("courier_book", "address.locality")`): `required=True,
role='city'`, роль ∈ `contracts.GENERIC_PIECE_ROLES` (`contracts.py:1094`). `vault._settlement_of`
(`vault.py:1144-1163`) маскирует улицу и дом, а город внутри адреса **оставляет настоящим**,
поэтому требуемый хоп на этом листе не заработает НИ ОДИН правильный шлюз (g07
decompose-001/004, g01, g03, g04, g14 — «в `end_to_end` и `form_hOUT` каждый такой лист —
промах по построению»). То же у `delivery_create_order.to_location.city` (`required=True`).
Второй корпусный случай: g14 P2 — 9 кейсов объявляют пять ОБЯЗАТЕЛЬНЫХ хопов
`delivery_create_order`/`notify_sms`, которые запрещает правило самого кейса (`>100`), и
контрольное плечо отказывает по тому же доводу; это 9 из 30 знаменателей `multi_all_out = 0`.

**Шаг 7. Второй оценщик уже написан и не подключён к headline.** `actual_hops.py` (M0,
`ESTIMATOR_VERSION = "m0-actual-out-v14"`) читает только `run.base.calls`, и `absent` там не
существует: «an action never taken is not a crossing», статусы `matched/mixed/residual/
value_wrong/unmasked_known/ambiguous/unattributed/not_identifiable/not_applicable`
(`actual_hops.py:246-256`). `hop_report.py:1-15` печатает три оценщика рядом и запрещает
смешивать их числа («THREE ESTIMATORS, THREE LABELS, NEVER MERGED»), `live.py:97,104` их уже
собирает. Но отчёт v5 (`report.py`) печатает только расписание корпуса — 744 объявленных
tool-arg хопа на сохранённых 450 читаются `absent`, пока одноимённый инструмент работал в
другом ходу.

## RED-тест (путь + что показывает)

**`/tmp/spike_e_red.py`** — self-contained, без модели и сети; грузит bundle как
`test_loc_settlement_echo.py` (`sys.path.insert(0, "<repo>/prototype")` →
`from testkit import load_dev_bundle; load_dev_bundle()`), затем гоняет **реальный** наблюдатель
(`bench.agentpii5.observe.observe`) и **реальные** строки (`bench.agentpii5.metrics`) на
рукописных прогонах из `bench.agentpii5.fixtures`.

Прогон: `cd prototype && source .venv/bin/activate && PYTHONDONTWRITEBYTECODE=1
.venv/bin/python /tmp/spike_e_red.py` → **exit 1, 4/18 passed** (проходят только четыре
GUARD-проверки — они и должны проходить). Что показывает каждая группа:

| проверка | что утверждает | что печатает СЕЙЧАС |
|---|---|---|
| A1 | пустой слот внутри СДЕЛАННОГО вызова — `absent` | `status='unmasked'` (g02 m-083/086/106) |
| A2 | необязательный хоп с пустым слотом не считается нигде | `unmasked`, `end_to_end 0/1`, `form_hOUT 0/1` |
| B1/B2/B3 | три причины — три разных статуса `engine_kept`/`not_masked`/`leaf_foreign`/`absent` | все три `'unmasked'` |
| B5 | passthrough — `not_masked`, осознанное исключение — `engine_kept` | оба `'unmasked'` |
| B4 | `contracts.HOP_STATUSES` несёт расщепление | `observed/leaked/residual/unmasked/absent` |
| C1/C2 | декомпозиция объявлена строками рядом со строгими | нет ни одной из 8 строк |
| C3/C5/C7 | **GUARD**: строгие знаменатели не сдвинуты | `multi_all_out 0/1`, `end_to_end 0/1`, `1/3` |
| C4 | честная строка по ходу читает 1/1 по написанным | строки нет |
| C6 | город: честная доля `0/0` («н/п»), исключение напечатано | строк нет |
| C8/C9 | `end_to_end_written 1/1` рядом с headline `1/3`; `agent_absent 2/3` | `out_absent 0/3` (недосчёт) |
| D1/D2 | хоп на листе роли `city` не может быть обязательным | `arg_hop(...).optional == False` |

Дословный хвост прогона (сохранён в `/tmp/spike_e_red.out`):

```
  FAIL  A1 empty slot in a call the agent MADE is `absent`  status='unmasked'
  FAIL  A2 an OPTIONAL hop the agent skipped (call made, slot empty) counts nowhere
        status='unmasked' end_to_end=Line(hits=0, total=1) form_hOUT=Line(hits=0, total=1)
  FAIL  B1 the three causes of a missing substitute are three DISTINCT statuses
        engine-kept='unmasked' foreign='unmasked' empty='unmasked'
  FAIL  C8 the engine's real rate is published beside it, 1/1  end_to_end_written=None
  FAIL  C9 `agent_absent` is printed as its own population  out_absent=Line(hits=0, total=3)
  PASS  C3 GUARD: `multi_all_out` still counts a turn nobody wrote as a miss  hits=0, total=1
  PASS  C5 GUARD: `end_to_end` keeps its strict denominator (passthrough still 0)  hits=0, total=1
  PASS  C7 GUARD: the headline denominator is unchanged (corpus timetable)  hits=1, total=3
4/18 passed
```

Гарды (`C3/C5/C7`) стоят в тесте намеренно: спайк обязан доказать, что лечение **не** сужает
headline, — иначе он воспроизводит дефект v4 D3 («a triple with nothing to compare passed all
five levels» / «did the arm act at all»), ради которого `end_to_end` и переписывался
(`metrics.py:24-28`, `contracts.py:1308`).

## Подход как грамотно

Массовое правило в семи частях; ни одна не подгоняется под кейс.

**Е-1. Один статус — один факт.** В `observe._out_status` (`observe.py:1126-1153`) заменить
единственный `return "unmasked"` решением, где **порядок веток и есть контракт**:

```
если written пуст                     → (см. Е-2)
если _leaf_carries(written)           → residual | observed      (как сейчас)
иначе если leaf_value_ok(item,tool,path,written):
        spec.role in GENERIC_PIECE_ROLES и (surfaces или minted)
                                      → "engine_kept"
        иначе                          → "not_masked"
иначе                                  → "leaf_foreign"
```

Почему именно так: `metrics.leaf_value_ok` (`metrics.py:183-227`) — уже существующий и
единственный предикат «лист получил то, что спрашивает» (R-53: второе определение того же
факта обязано разойтись). `engine_kept` против `not_masked` требуют **двух сигналов, и оба уже
приходят в `_out_status`** (`observe.py:1126-1128`: `spec` и `surfaces`/`minted`):
роль ∈ `GENERIC_PIECE_ROLES` — это и есть авторский список исключений продукта
(`vault._settlement_of`, `vault.py:1144`: «what the law does not protect stays true»), а
непустые `surfaces`/`minted` доказывают, что движок для этой сущности был разбужен и оставил
часть настоящей СОЗНАТЕЛЬНО. Ни одного из двух в одиночку не хватает: без роли passthrough
gateway получит «сознательно оставил» на каждом листе, а без записи минта лист города,
вытекший целиком, будет оправдан. `leaf_foreign` сегодня невидим полностью: третья величина
в листе — это `end_to_end 0/1` без причины.
`contracts.HOP_STATUSES` (`contracts.py:1674`) становится
`("observed","leaked","residual","absent","engine_kept","not_masked","leaf_foreign")`, и
docstring `HopObservation` (`contracts.py:1641-1661`) переписывается по факту и владельцу.

**Е-2. Контракт `optional` — в код, по ЛИСТУ, а не по вызову.** В `observe._out_call`
(`observe.py:1155-1175`) до `_out_status`:
```python
if not written:
    return None if hop.optional else _flat(case, repeat, hop, True, item.type, "", "", "absent")
```
Почему: `contracts.py:153-157` это уже обещает, `_out_answer` (`observe.py:1322`) это уже
делает, корпус уже расставил `optional` (`scenarios5/common.py:465`, `revise.py:246`) — чинится
асимметрия внутри одного файла. Эффект массовый: g08 (24 листа), g14 P4 (10 листьев), g02
(необязательные листья внутри сделанных вызовов).

**Е-3. Headline не сужать — расщеплять и печатать расщепление.** `end_to_end`, `round_trip`,
`chain_value/form`, `multi_all_out` остаются байт-в-байт (их строгий знаменатель — и защита от
passthrough, и урок v4 D3). Рядом — зарегистрированные строки в `contracts.METRICS`
(`contracts.py:1300-1360`) и `metrics.METRIC_FUNCTIONS` (`metrics.py:1293`):

* `end_to_end_written` (family `public`) — хит = `observed` и `_item_value_ok`; знаменатель =
  объявленные OUT/tool_arg листья со статусом `observed`/`residual`/`leaf_foreign`. Это и есть
  честная доля движка; `absent` и `no_mint` (обе половины) выведены **и напечатаны рядом**.
  У passthrough знаменатель пуст → «н/п», а не 100%: его ловит `leak`.
* диагностики: `out_written` (популяция), `out_no_mint` (= `engine_kept` + `not_masked`),
  `out_engine_kept`, `out_not_masked`, `out_leaf_foreign`; уже существующий `out_absent`
  (`metrics.py:593`) начинает говорить правду только после Е-2 — сегодня он печатает `0/3` там,
  где ненаписанных листьев два.
* `multi_all_out_written`, `chain_value_written`, `chain_form_written` — то же правило популяции
  на уровне хода/перехода (`metrics._multi_turns` 846, `_transitions` 793).
* `report.BESIDE` (`report.py:112-121`) из `dict[str, str]` становится один-ко-многим (кортеж),
  чтобы счётчики печатались ПОД своей строкой — комментарий самой таблицы этого и требует («a
  second such pair is one row here rather than a second special case»).
* каждой новой не-диагностической строке нужен тройной fixture zero/one/adversarial
  (`fixtures.py:1287`), иначе `report.gate_all` (`report.py:163-174`) отказывает метрике и отчёт
  печатает «НЕПОЛНЫЙ»; публичный файл подхватит её сам (`reportjson.py:97-99`).

**Е-4. Достижимость — свойство корпуса, а не прибора.** `scenarios5/common.py::arg_hop`
(441-467) и `revise.py:241-246`:
```python
optional = (not spec.required) or spec.role in contracts.GENERIC_PIECE_ROLES
```
Почему: `courier_book.address.locality` и `delivery_create_order.to_location.city` —
`required=True, role='city'`, а `vault._settlement_of` держит город внутри адреса настоящим **по
решению продукта**; обязательный хоп на таком листе — обещание, которое нельзя выполнить
(g07: «хоп, который не может стать `observed` по построению»). Вторая половина — проверка
достижимости на сборке, класс R04 (`schema.py:126-134`, `contracts.V5_CASE_RULES:505-512`): обязательный
OUT-хоп допустим, только если сценарий к этому ходу **источает все обязательные поля схемы** и
правило самого кейса не запрещает действие (g14 P2 — 9 кейсов против своего же правила `>100`;
g02 P4 — `courier_book` требует `interval.from/to`, сцена их не даёт, и 55 из 56 многоходов
читаются `0/1`). Недостижимый кейс — отказ сборки, не «denominator из поведения агента».

**Е-5. Расписание корпуса оставить расписанием, а второй оценщик — опубликовать.** Не трогать
`call_for_hop` (`observe.py:732`) — это расписание, и его 68 g14-хопов именно для второго
оценщика. Массовое правило: напечатать таблицу `actual_hops` (M0 v14) в том же отчёте рядом со
scheduled-строками, под метками, которые `hop_report.py` уже определяет, и в headline назвать
оценщика. Почему нельзя «починить» `call_for_hop` окном ходов: это смена смысла знаменателя под
старым именем — ровно то, от чего предостерегает `actual_hops.py:124-126` («an estimator that
moves a denominator under the same name lets a counting fix be read as an engine improvement»).

**Е-6. Эквивалентность — авторская таблица, а не догадка.** В `contracts` добавить замкнутое
отображение `(tool, path) → семантический лист`, сворачивающее `courier_book.address.*`,
`crm_upsert_contact.contact.address.*`, `crm_upsert_card.contact.address.*`,
`delivery_create_order.to_location.*` и `contact.address.city ≡ address.locality`; объявленный
хоп удовлетворяется семантически равным листом, который прогон реально написал, а `arg_hop`
падает, если семья объявила два эквивалентных листа на один переход. Почему: g08 — 25 из 30
`absent` группы это ровно расхождение «корпус объявил `courier_book`, агент написал
`crm_upsert_contact`». Таблица обязана быть замкнутой и авторской: `actual_hops` предупреждает,
что сопоставление по имени инструмента «can tie a re-search, a second delivery, or data the
agent had not been given to the wrong event».

**Е-7. Нотационно-устойчивое сравнение — граница с Ж, не дубль.** Предикат значения остаётся
один (`metrics.value_matches`/`part_matches`, `metrics.py:108-121` + `contracts.NEEDLE_KINDS`).
Е владеет только тем, что `end_to_end_written` читает ТОТ ЖЕ предикат, что `end_to_end`, — тогда
две строки различаются популяцией и ничем больше, и их можно печатать рядом.

## Затронутые модули

| файл | что меняется |
|---|---|
| `prototype/bench/agentpii5/observe.py` | `_out_status` (1126-1153) — расщепление; `_out_call` (1155-1175) — `optional` по листу; согласование с `_out_answer` (1309-1323) |
| `prototype/bench/agentpii5/contracts.py` | `HOP_STATUSES` (1674), docstring `HopObservation` (1641-1661) и `Hop.optional` (153-157), строки `METRICS` (1300-1360), таблица семантических листьев |
| `prototype/bench/agentpii5/metrics.py` | новые строки; переиспользование `leaf_value_ok` (183), `_multi_turns` (846), `_transitions` (793); `form_hOUT` (575-590) и `out_absent` (593) — знаменатель после расщепления |
| `prototype/bench/agentpii5/fixtures.py` | тройки zero/one/adversarial на каждую новую метрику (1287) |
| `prototype/bench/agentpii5/report.py` | `BESIDE` (112-121) один-ко-многим; печать блока actual-hop рядом со scheduled |
| `prototype/bench/agentpii5/reportjson.py` | версия схемы отчёта (`PUBLIC_LINES` 97-99 подхватит строки сам) |
| `prototype/bench/agentpii5/hop_report.py`, `live.py`, `actual_hops.py` | подключение уже существующего оценщика к headline-отчёту; сами оценщики не переписываются |
| `prototype/bench/agentpii5/scenarios5/common.py`, `revise.py`, `schema.py` | `arg_hop` (441-467), `optional=not spec.required` (246), проверка достижимости класса R04 (126-134) |
| тесты пакета | `test_observe.py`, `test_metrics.py`, `test_fixtures.py`, `test_report.py`, `test_reportjson.py`, `test_report_frozen.py`, `test_actual_hops.py` — числа `unmasked` сдвинутся по построению |

**Не трогается:** `prototype/pseudex/**` (класс Е — прибор; у движка здесь дефекта нет),
холдаут 359, `bench/agentpii3/score.py` (заморожен), сохранённые прогоны.

## Риски

1. **Двигается каждое число, читающее `unmasked`** — `end_to_end`, `round_trip`, `form_hOUT`,
   `chain_*`, `multi_*`, `residual`, срезы, а также `actual_hops`/`causal_hops` и замороженные
   фикстуры отчёта. Дисциплина detect-change: снять ПОСЛЕДОВАТЕЛЬНЫЙ before-snapshot архива,
   менять узко, снять after, сверить позитивы И негативы; просел — откат. Числа в g01–g15
   измерены на СТАРОМ корпусе и после правок сдвинутся — их нельзя цитировать как «до/после»
   без перепрогона.
2. **`engine_kept` может спрятать настоящий over-masking.** Если движок начнёт маскировать
   населённые пункты, такие листья станут `observed`/`residual` — и это будет видно. Поэтому
   строка `out_engine_kept` обязана ПЕЧАТАТЬСЯ, а не вычитаться молча (прецедент J1.1:
   `answer_optional_only` печатает то, что `answer_real` выбросил из знаменателя).
3. **`engine_kept` опирается и на роль, и на запись минта.** В рукописной записи без
   `substitutes` лист города станет `not_masked` (движок «не маскировал»); фикстуры обязаны
   строить запись минта, а честная доля не должна считаться на прогоне с пустым `substitutes`.
4. **`*_written` не должен воскресить v4 D3.** Строгая строка печатается ПЕРВОЙ и остаётся
   критерием; sibling — только подпись к ней (`report._printing_order`, `report.py:1070`; печать — `report.py:979-990`).
5. **Эквивалентность листьев — суждение.** Неверная запись таблицы зачтёт значение, которого
   агент не нес; при двух эквивалентных листьях с разными значениями правило обязано падать, а
   не выбирать.
6. **Схема отчёта.** `BESIDE` один-ко-многим + новое семейство строк = новая версия отчёта
   (прецедент `hop_report.REPORT_VERSION`), иначе читатель, закрепивший старый файл, прочтёт
   новый блок под старым именем.
7. **RED-тест живёт в `/tmp`** (ограничение спайка) и переживёт перезагрузку только как листинг
   в этом файле; в фазе 2 он переносится в пакет как
   `bench/agentpii5/test_spike_e.py` и там становится GREEN-критерием.

## Методологическая развилка

Оставляем ли headline-знаменатели `end_to_end`/`chain_value`/`multi_all_out` строго корпусными, а
честную долю по написанным и восстановимым листьям публикуем ОТДЕЛЬНОЙ строкой
`end_to_end_written` (тогда сквозной passthrough по-прежнему читается `0` на строгой строке и
ловится `leak`), — или владелец разрешает сузить знаменатель самих headline-строк, приняв, что
passthrough печатает там «н/п»?
