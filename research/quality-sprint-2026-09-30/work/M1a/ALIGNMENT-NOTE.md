# M1a: выравнивание — исправлено (round 7)

G2-readiness review (`76fef59f`) поставил NOT_READY с жёстким блокером: LOC false-negative от char-level SequenceMatcher (финальная «4» дома падала как boundary insert на `x==b`, правило `a<x<b` её отбрасывало). Исправлено двумя изменениями:

1. **Word-level выравнивание — primary.** `_word_window` (whitespace-токены) мапит значение по границам слов; оно не фрагментирует «Липовая→Пушкина» и «21→14» и не сливает соседние литералы. При чистом соответствии (равное число слов, contiguous) используется оно; иначе fallback на char-level `_mapped_window`.
2. **Exact-copy narrowing.** На exact-copy пути (`raw==fake` с единственным proved literal) окно сужается до точного вхождения literal (`text.find(literal)`), чтобы граничная вставка соседнего литерала не давала `value_wrong`; излишек остаётся gap-change (`text_status=changed`).

## Проверка adversarial-кейсов (red_alignment.py)

| Случай | Было | Стало |
|---|---|---|
| correct LOC verbatim | value_wrong | **matched** |
| wrong street type | value_wrong | value_wrong ✓ |
| insertion-around-token | value_wrong | **matched + text_status=changed** |
| deletion-around-token | alignment_unresolved | alignment_unresolved ✓ |
| shared-surrounding-literals | matched | matched ✓ |
| wrong-real-elsewhere | value_wrong | value_wrong ✓ |
| two-fakes-collapse | alignment_unresolved | alignment_unresolved ✓ |

59/59 контролов, 6 legacy suites зелёные. Позитивный LOC control добавлен в suite.

## Осталось до G2 (по reviewer)

- **Known-unknown surfacing** (обязательно): Latin/partial-roles должны давать видимый счётчик unsupported, не 0 candidates без пометки.
- **Swapped-person pin** (обязательно, но уже корректно по point 5 — см. существующий unknown-competitor и wrong-real-elsewhere тесты).
- Optional: Latin/translit value, partial-role proof, spoken/stream completeness.

Единственная правка кода — два M1a файла; engine/scorer/raw неизменны.
