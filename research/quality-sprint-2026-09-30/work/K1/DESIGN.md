# K1 — core mechanism design (sole writer: lead)

Входы: S1 revision-2 (4 воспроизведённых RED + decision-coverage), OWNER-DECISIONS/REMAINING-DECISIONS (принципы), pinned source `0bfda236`. K1 — единственный writer `vault/redact/envelope/stream/shared identity helpers`; НЕ engine-detection (D1 отдельно). Метрика M1c уже замеряет RED→GREEN.

## Дефект A2 — tool-result collision (one byte string, two people)

- Место: `envelope.py` handoff `role:"tool"` получает `recorded` как conservative leg (line 112, 420, 507-577).
- Симптом (S1): surname реального человека, byte-identical выданной подмене, остаётся; reverse leg разрешает его в первого человека.
- Решение владельца: `Forward collision` — различать по доказанному source/context/identity, НЕ по role; если неразличимо → отказ затронутой операции; непрерывность выданных подмен обязательна. `REMAINING §Блок 2` — сначала использовать существующую history/provenance; новые API-поля не разрешены.
- Механизм (кандидат): в handoff tool-сообщения не применять blanket `recorded`; для каждого real в tool result проверять, доказано ли, что это echo выданной подмены (точный source slot из spans_real + выданная подмена), а не внешний new-real. Неразличимое → refuse affected call (fail-closed), не молчаливый passthrough.
- RED: A2 fixture (3 variant, fresh vault) → surname не в clear; reverse leg не резолвит в чужого человека.

## Дефект B — NAME рождается, но outranked ADDR

- Место: `detect_all.py:253` «EVIDENCE BEATS A GUESS» — ADDR (priority 4) outranks NAME (3), чтобы улица «Пушкина» не стала NAME. Но полное лицо «битюкова зинаида» (surname+given) глотается частичным ADDR «битюкова».
- Решение: полные личные части защищаются; одна персона — согласованная подмена whole+parts.
- Механизм (кандидат): в `_resolve` не давать частичному ADDR-span вытеснять NAME, покрывающий **больше** идентифицирующих частей того же лица (surname+given), если NAME пережил suppress. Street-only («Пушкина» без given) остаётся ADDR.
- RED: B fixture → финальные spans содержат NAME (все части), given `зинаида` не уходит raw.

## Дефект C — whole/parts split при переупорядоченном prior row

- Симптом: одна персона в `c1` «Зинаида Битюкова», в `c2` полное имя затем только фамилия → два разных substitute для одного real.
- Решение: one person → one consistent substitute для whole и parts; conversation scope; clean C2 control держится (нельзя просто замораживать parts глобально).
- Механизм (кандидат): при mint части (surname/given) искать уже выданный whole-substitute той же identity в scope; переиспользовать его часть, а не mint новый. Source-order и cross-conversation вариант обязателен.
- RED: C fixture → один substitute для whole и parts; C2 остаётся зелёным.

## Дефект D1 — invented country prefix на restore leg

- Место: `redact.py:1682 _digits_in_form_of` оставляет то, что перед последними 10 цифрами; guard только `+8`/`++`.
- Симптом: invented `+3`/`+9` получает real последние 10 цифр под чужим префиксом, `residual=[]` — ни real, ни видимый отказ.
- Решение: `REMAINING §Блок 2` — explicit agent form > schema; не чинить изменённую identity молча; unresolved near-miss → refuse. Только новое equivalence/exception (напр. расширение `7↔8`/bare набора) — owner choice (не открыт).
- Механизм (кандидат): invented prefix вне одобренного набора (`+7`/`8`/bare/`++`/`+8`) → refuse unsafe delivery (не подставлять real цифры под чужим префиксом), либо сохранять форму с явным отказом.
- RED: D1 fixture → invented `+3`/`+9` НЕ доставляет real subscriber digits; `surviving_substitutes`/отказ виден.

## Порядок и гейты

K1 = G4 (RED→GREEN, mutation→RED, counterexample, independent review, tests after final diff) + G5 (privacy/identity) + G6 (fidelity). Каждый дефект — отдельный changeset с RED-тестом; общий core writer — lead. После K1 → V1 (v6 integration), затем D1 (detection), N1, C1.

## Не входит в K1

D2 (non-PII rewrite, NOT_MEASURED) и исторический E1 (stream, vault-state unreconstructed) — отдельные follow-up, не блок K1. Новые provenance API-поля — только после доказанной недостаточности существующих.
