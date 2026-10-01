# M1a: foundation v2-dev — не полный G2 PASS

## Изменены только два M1a файла

- prototype/bench/agentpii5/answer_restoration.py
- prototype/bench/agentpii5/test_answer_restoration.py

Это изменение нового незавершённого evaluator, не engine и не старых38официальныхmetrics/observer. Всеoriginalrawruns неизменны. До M1c новыймодульнеподключёнвUI/reportharness.

## Реализовано

1. Immutable `DisclosureProof` и `AnswerEvidence` как optionalkeyword pure API. Нетbooleanavailableизвне. Целостностьpayloadhashes, source/fakebounds, item/source slots, providerordinals иchronology проверяются. Структурнаявалидацияневыдаётсязааутентификациюsourceorigin: legacyadapterможетстроитьproofтолькоизреальнойlinkedcapture, неzippush/provider.
2. Gatewaypush/requestcount и providerrequest разныечасы. Legacymentions/mintsтолькоnominatecandidate; безproofнеearnsuccess. Available/future/unknownраздельны. Внутренненевалиднаяpushmetadata/schema вызываетValueError, не«enginefailure».
3. Exactfakecopy сверяетсясsource literalконкретногоdisclosure, не repairedcanonical. Valueversionidentityотдельнаотliteralпредставления.
4. ExplicitstreettypecomparisonвM04, старыйsharedvalues_equalнеизменён.
5. InitialsпоявляютсякакrawcandidateсвидимойUNKNOWN, а неsilentzero. PartsбездоказаннойliteralrolecorrespondenceтожеUNKNOWN.
6. Nestedчужойcandidateнепропадаетподwholeinterval; sourceidentityневыбираетсяпоправильномуdelivered.
7. Providerfinalanswer — exactпоследнийnonemptyturn; совпавшийearlierturnнеfallback.
8. Wholetoolproof проверяетactualrecordedpiece/slot+maskedoffsetdrift, availablecallresultchronology,sourcevalueversion. User+toolоднойmappingнеoriginambiguity.

## Выполненный subset

`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_answer_restoration` изprototype → exit0, **55/55** controls; EVIDENCE-CONTROLS.log.

Онипокрываютvalid/invalid/missing/futureproof, message/toolsource, repeatedoccurrences, wrongrealelsewhere, sourceerrorliteral, streettype, initialsvisibility, no-token/no-op, non-PIIidrewrite иactualstreamvswhole. Прежние28checks с ихдоизменениявыводомсохраненыв B0архиве/PROTOTYPE-BASELINE.log, исходныеRED8/5сохраненыотдельно.

## Foundation-review regressions (после независимого промежуточного review)

Независимый foundation reviewer обнаружил четыре дефекта поверх заявленных открытых работ; все четыре исправлены и закреплены регрессиями (55 контролов вместо47):

1. **Чужой alias не спасает exact copy.** Раньше `exact_copy=raw==chosen.fake` при `chosen`=первый available mapping; raw, байтово равный fake другого mapping, шёл в canonical путь и проходил value. Теперь `exact_copy = len(literal_choices)==1`, где `literal_choices` — literals только тех available mapping, чей fake==raw. Value сверяется с этим literal.
2. **Целые ординалы хронологии.** `call_requests` обязан быть ровно длиной в accepted calls, каждый — существующий целый provider request; `available_results` — целое 0..len(calls). bool/float/отсутствующий request отклоняются.
3. **Тип записанной замены.** В tool proof engine_type куска обязан совпадать с declared item.type; неизвестный тип больше не проходит молча.
4. **Будущее доказательство не стирает unknown.** `availability` сокращён до available/unknown: proof с request после consumer не может доказать, что то же написание не было известно раньше по другому каналу; такой кандидат остаётся unknown-конкурентом, а не выпадает из maps.

## Доказуемые инициалы (round 4)

Инициалы теперь доказуемы через раскрытие полного имени. `initials_of` возвращает squeezed-инициалы (кириллица+латиница); `_spelling_matches` и `_initials_value_equal` сопоставляют raw-вхождение «П.О.» с fake «Пахомова Ольга» и сверяют delivered с реальными инициалами «И.Е.». Кандидат становится available при доказанном whole-name disclosure. Bare «ПО» намеренно не кандидат (лексическая неоднозначность, P09). 58/58 контролов.

## Открыто — не скрывать ради58/58

- Legacyadapterвывода providerlinkedproof изсуществующихcaptures. Пока noneevidenceконсервативноUNKNOWN, неновыйenginequalityrate.
- Latin (транслитерация) и partial roles (только фамилия/имя) всё ещё unknown-кандидаты, не доказуемые — нужен тот же механизм привязки derived-формы к whole-name disclosure.
- Unique monotone alignment. СтарыйSequenceMatcherwindowещёиспользуетсякакdevэвристика; известное ограничение — соседняя вставка литерала сливается в value replace (см. ALIGNMENT-NOTE.md). Недостаточно дляG2acceptance.
- Перспановыеformabstentions инеполныеvalueчасти,унификацияcoverage-discoveryblindspots.
- Unmappedchangesнеавтоматическидоказанныеnon-PIIcorruption,покаunsupportedlegitimatesubstitutionнеможетбытьисключена.
- ПолныйindependentreviewG2, историческиеcounterinvariance,новыйofflineoutput иM1cпроводка.

## Заморозка для foundation re-review

На время отдельногоreview не менять этидвафайла/58controlinputs. Остальныеагентымогутчитать,нопишуттолькосвоиreviewscopes. FullgateG2остаётсяFAILнезависимоотприёмкиэтогопромежуточногослоя. Первый foundation reviewer завершился преждевременно(до итогового вердикта), но дал четыре подтверждённых дефекта; они исправлены. Повторный foundation review (2f5d5333) дал PASS_FOUNDATION на 55 контролов; инициалы добавлены после него и требуют отдельного incremental review перед G2/M1c.
