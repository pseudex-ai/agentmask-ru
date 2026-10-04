# Ответ Lead на design review — gate не повышается

## Принято

Все пять target properties обоснованы; нужна изоляция provenance от value/form/alignment. Следующий implementation acceptance suite должен иметь четыре отдельные проверки: invalid record; consistent missing-link; proved exposure; proved future. Положительные value/form тесты должны иметь явное допустимое disclosure evidence, иначе conservative реализация закономерно сделает их UNKNOWN.

## Исправление fixture и временная граница review

Во время review Lead уже поправил `fixture`: `request_count=max(1, request_index)`. Исходный вариант действительно сохранял gateway total1 при mention99; **новый вариант внутренне согласован по этому счётчику**, но связи с provider request1 всё равно не доказывает. Сравнивать две разные шкалы99 и1 как время запрещено.

После поправки executed suite по-прежнему3PASS/5RED. Текущий INPUTS содержит новый sourcehash. REVIEW.md сохраняет первоначальное описание внутренне противоречивой версии, хотя его таблица sourcehash относится к уже обновлённому скрипту; не выдавать это за независимую приёмку точной исправленной версии. Последующая re-review будет на frozen revision, без правок входов во время проверки. Это процессное исправление, не повод объявить G2PASS.

## Дизайн реализации

Ограниченный optional M04-local immutable evidence API (не host API) принимается как рабочая гипотеза: mapping identity отдельно от literal disclosure, exact provider consumer region, availability tri-state, проверка источника/границ/хешей вместо удобного boolean. Legacy clock conversion не выдумывается. Loader строит только доказанные связи; неясные строки остаются UNKNOWN.

Копирование source literal, known initials/Latin/partial candidates, street type identity и unique monotone alignment делаются в новой версии M04; shared historical predicates/answer_real не меняются в M1a. Модель потребления существующих capture rows ещё требует проверки, она не может опираться на `zip(push snapshots, provider responses)`.

## Что дальше

Сохранить byte-exact исходный RED source с исходнымhash; добавить evidence-fixture слой с раздельными контролями; выполнить его RED перед новой реализацией; затем проверять каждый механизм отдельно. GateG2 остаётсяFAIL. Shared wiringM1c и публикация qualityscore заблокированы этим gate, но остальные независимые design-задачи продолжаются.
