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

## Открыто — не скрывать ради55/55

- Legacyadapterвывода providerlinkedproof изсуществующихcaptures. Пока noneevidenceконсервативноUNKNOWN, неновыйenginequalityrate.
- Полноценныеliteralrole/disclosureparts, Latin/initialstransformationsиomission/typo supportснезависимымoracle. InitialscandidateUNKNOWNнеполнаяподдержка.
- Unique monotone alignment. СтарыйSequenceMatcherwindowещёиспользуетсякакdevэвристика; оннедостаточендляG2acceptanceиостанетсяподотдельнымиadversarialchecks.
- Перспановыеformabstentions инеполныеvalueчасти,унификацияcoverage-discoveryblindspots.
- Unmappedchangesнеавтоматическидоказанныеnon-PIIcorruption,покаunsupportedlegitimatesubstitutionнеможетбытьисключена.
- ПолныйindependentreviewG2, историческиеcounterinvariance,новыйofflineoutput иM1cпроводка.

## Заморозка для foundation re-review

На время отдельногоreview не менять этидвафайла/55controlinputs. Остальныеагентымогутчитать,нопишуттолькосвоиreviewscopes. FullgateG2остаётсяFAILнезависимоотприёмкиэтогопромежуточногослоя. Первый foundation reviewer завершился преждевременно(до итогового вердикта), но дал четыре подтверждённых дефекта; они исправлены. Требуется повторный независимый foundation review на замороженных входах перед commit приёмки.
