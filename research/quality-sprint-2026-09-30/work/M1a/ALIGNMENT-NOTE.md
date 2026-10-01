# M1a: состояние уникального выравнивания — открытый элемент (step 6)

Результат adversarial-прогона [red_alignment.py](<research/quality-sprint-2026-09-30/work/M1a/red_alignment.py>) → [RED-ALIGNMENT.json](<research/quality-sprint-2026-09-30/work/M1a/RED-ALIGNMENT.json>), на текущем char-level `_mapped_window` (с уточнением границы `a<x<b` для вставок).

| Случай | Текущий вердикт | Оценка |
|---|---|---|
| repeated-fake-one-restored | matched + residual | корректно (пер-вхождение локально) |
| insertion-around-token | **value_wrong** | **известное ограничение**: соседняя вставка литерала («X »/« Y») сливается char-level SequenceMatcher в replace-opcode; правильный вердикт — value_ok + отдельный gap-change |
| deletion-around-token | alignment_unresolved | корректно (консервативно) |
| shared-surrounding-literals | matched | корректно |
| wrong-real-elsewhere | value_wrong | корректно |
| two-fakes-collapse-to-one-real | alignment_unresolved | корректно |

## Почему не word-level

Пробная word-level (whitespace) версия ломала телефоны с внутренними пробелами/разделителями (`+7 999 000-11-22` → одна word vs три), регрессируя существующий контроль «value cannot excuse format repair». Откат выполнен; 55/55 контролов снова зелёные.

## Требование reviewer (не выполнено)

Уникальное монотонное соответствие по literal anchors/token boundaries/length changes, где неоднозначные случаи (повторяющиеся anchors, соседние токены, crossing edits, вставка/удаление внутри значения) дают `alignment_unresolved`, а соседняя вставка литерала — отдельный gap-change, а не value_wrong. Нужен выравниватель, который не теряет многословные значения (phone/date с разделителями) и не сливает граничные вставки с заменой значения.

## Следующий шаг

Отдельный RED→GREEN цикл: токенизация по «жёстким» границам (не-знаковые символы) + анкерное монотонное соответствие с проверкой единственности; пер-тип длина/форма реального значения как ограничение, но без выбора mapping «чтобы value стало зелёным». До этого alignment остаётся открытым, G2 не повышается.

Сам по себе этот документ и RED-ALIGNMENT не меняют product source; единственная правка кода в этом цикле — уточнение границы вставки в `_mapped_window` (без регрессии, 55/55).
