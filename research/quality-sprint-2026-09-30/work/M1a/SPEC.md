# M1a — truth conditions before publishing an answer score

## Binding

GOAL-BRIEF P02/P03/P06/P07/P11/P16; OWNER-DECISIONS M04; REMAINING-DECISIONS blocks2/4. Старый answer_real и saved paid run не меняются. Новый estimator оценивает каждый реально написанный fake в фактически доставленном тексте, с raw-only identity и явной неопределённостью.

## Executed RED on preserved prototype

`PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python research/quality-sprint-2026-09-30/work/M1a/red_truth_conditions.py` → exit1; RED.log и RED-RESULTS.json. Setup/import не падает, все8условий исполнены.3PASS/5RED:

1. **RED literal typo restore false positive:** source«игрь», canonical«игорь», copiedfake«егрь», delivered«игорь». Прототип засчитывает исправленный canonical вместо literal source.
2. **RED literal typo restore false negative:** тот же source/fake, delivered«игрь» не получает value success, хотя это буквальный исходник.
3. **RED provenance clock:** usermention request_index99 и providerresponse request1 — разные счётчики. Без exactdisclosure relation прототип всё равно засчитывает успех через msg<=turn. Это доказательство недостающего основания, не разрешение сравнивать99>1 как одинаковые часы.
4. **RED initials:** raw«П.О.» от известногоfake«Пахомова Ольга» исчезает как zero candidates. Полная derived-form поддержка ещё не доказана; такое исчезновение нельзя называть ответом без подмен.
5. **RED LOC identity:** delivered«улица Пушкина14» получает value_ok для expected«переулок Пушкина14»; form error не исправляет falsevaluepass.

ПоложительныеконтролиPASS: дваповтора считаются раздельно(одинrestored,второйfake); c-3→c-8 ловится как non-PIIrewrite; deliveredfakeпобеждаетправильныйreply_whole. Это не полныйG2PASS, а исходная точка design/RED.

## Предлагаемый механизм новой версии (ещё не implementation acceptance)

### A. Явная evidence-модель

Разделить **mappingidentity** (person/type/value-version/role) и **literal source at disclosure**. Источникliteral — конкретныйspan исходногоuser/toolpayload, а не просто item.canonical. Спеллингиfake с metadata не доказательство model exposure.

Disclosures должны быть связаны с фактическим response/requestboundary. User msg<=turn и конечный mint сами по себе не достаточны; разные часы push/provider нельзя численно сравнить. Exactrequestcaptures могут дать доказательство только после проверенного correspondence. При невозможности восстановить эту связь на legacytrace — provenance_unavailable, не fabricatedproof. Tooldisclosure можно связать через call_requests/available_results и exact source slot/piece; partial/overlapping mappings явнонеопределённы.

### B. Буквальное копирование и изменённая форма отдельно

Если raw occurrence byte-equal действительно раскрытомуfake, ожидается соответствующий literal source, включаяопечатки/регистр/форму. Если агент изменил форму, сравнение идёт по доказанной identity+поддержанному formtransform. Отсутствие необходимогоsource literal → UNKNOWN, не fallback наканон дляудобногоPASS. Value иform остаются раздельными.

### C. Кандидаты по RAW и полнота формы

Каждыйrawoccurrence отдельный; unchangedfake остаётся. Достоверныеwhole, roleparts, morphology, initials, Latin иdigits должныиметь testablepopulation. Приunknownrendering не применятьfourletterprefix какidentity; предложенныйcandidate с недоказаннымidentity остаётсяunresolved. ЧтобыпубликоватьscoreвсегоNAME/LOC, нуженкаркасderivedcoverage и явныеblindspots, а не толькоinitialsinglefix.

### D. Identity addresses

Streettype входит вvalueidentity согласноowner. Не изменятьhistoricalvalues_equalмолча: новыйmeterproperty/версияиmutationtest, затемявнаяintegrationM1c. Genericword можетостатьсяliteral, ноgenericsemanticclass не удаляетсяизidentity.

### E. Доставленные интервалы иliteral gaps

SequenceMatcher может предложить интервалы, но не доказатьуникальнуюalignment. Нужна token-aware monotone correspondence с проверкой repeatedanchors/adjacenttokens/sharedsuffix/insertion/deletion иотдельнымUNKNOWN. Правильноеrealвдругомместеответанеспасаетневерноеoccurrence. Non-PIIliterals не разрешаетсяпрятатьвширокуюdiffобласть. Проверкаactualstream, потомwholediagnostic.

## Scope / gates

Lead owns only new M04 module/tests and work/M1a. Никакихobserver/contracts/report/live wiring доM1c; никакихengineфиксов. Next: independentdesignreview, расширение adversarial tests иimmutableevidence API, затем новуюверсиюimplement. G2 остаётсяFAIL доGREENвсехtruthconditions иindependentreview. Историческийrunнепересчитыватькакновыйenginegain.
