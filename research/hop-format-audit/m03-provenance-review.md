# M03 — what the record establishes about answer/chain provenance (revised after architect review)

Status: read-only. **No causal label, no new record implementation, no
measurement change proposed.** Revision removes the earlier `CAUSAL` verdict and
the `AvailabilityRecord` proposal, which the architect rejected: *availability is
not model causality*, and a user-written value reused after a result proves no
tool origin at all.

Scope: `docs/plan-hop-form-before-450.md` M03. Constraints: no scheduled turns, no
future mint tables, no restored value choosing identity, no children/network, only
this file edited.

## 1. The three states the existing record can distinguish

Classes computed only from persisted fields
(`MentionRecord.{item_id,msg,result_seq,substitute,request_index}`,
`ToolResultRecord.{seq,turn,spans_real}`, `ArmRunV5.{call_turns,request_count}`):

| state | literal definition | what it may be read as |
|---|---|---|
| **unique-result-only lineage** | exactly ONE `(result_seq, item_id)` discloses the substitute that stands in the consumer; no message and no second result carries it | the record names one result as the only place that value was ever disclosed to the model |
| **mixed sources** | ≥ 2 `(result_seq, item_id)` disclose it, or a message mention and a result mention both carry it | the record cannot separate them; no single-result origin exists |
| **unavailable** | the substitute (or its surface) appears in no result row at all | nothing to trace; must print as such and never as a pass |

**None of the three is causality.** Unique-result-only lineage is the strongest
statement the record supports, and it is still a statement about *disclosure*, not
about what the model drew on. A value the user wrote stays user-written no matter
how many later results repeat it.

## 2. Literal evidence, computed from the four dossiers (not constructed)

Method: group mentions with `result_seq >= 0` by substitute and report the
disclosing `(result_seq, item_id)` set; values verbatim from `## Actual gateway
arm (…)` of each file.

**`memory_anaphora-012.md`** (`request_count 9`, `call_turns [1,4,4,5]`) — the
successful-chain reference. UNIQUE: `'мухин'`→`1/i1`, `'савва'`→`1/i2`,
`'игоревич'`→`1/i3`, `'bvatkjyl@example.ru'`→`1/i5`, `'1969-08-26'`→`1/i6`,
`'родниковая'`→`1/i7`. MIXED: `'89289855496'`→`[(1,'i4'),(2,'i4'),(3,'i4')]`.
Never disclosed by any result: `i8, i9, i10, i11` (all user-written). So even the
best dossier's answer leg is partly traceable: hops 7 (`i1`) and 16 (`i8`) ride
unique lineage or a user message, hops 17 (`i9` PHONE) and the `i4`/`i11` hops are
mixed.

**`tool_chain-017.md`** (`request_count 21`, 18 calls). **No** unique lineage
among result-disclosed values: `'8-952-190-62-13'`→`[(1,'i4'),(11,'i4'),(13,'i4')]`;
`'г Казань, ул Грушевая, д 1'`→14 pairs across `seq 2..10` under **both** `i8` and
`i9`; `'петренко'`, `'василий'`, `'семёнович'`, `'zdshxzeq@example.ru'`,
`'1984-01-07'`, `'барбарисовая'` each `[(1,…),(13,…)]`. Never disclosed by any
result: `i10` — the phone the user wrote in message 1 (`8-982-385-93-29`), i.e. the
value the answer is about. Answer hops 16–18 are `observed` while that phone item
has no result lineage at all.

**`long_support-027.md`** (`request_count 15`, `call_turns [1,1,1,1,2,2,3,4,4,5]`).
Every result-disclosed value is MIXED, several under *two item ids at the same
result*: `'щукина'`→`[(1,'i1'),(1,'i8'),(3,'i1'),(5,'i1'),(6,'i1'),(8,'i1'),(9,'i1')]`;
`'8 947 028 21 09'`→`[(1,'i11'),(1,'i4'),(3,'i4'),(5,'i4'),(6,'i4'),(8,'i4'),(9,'i4')]`;
likewise `'зоя'`, `'максимовна'`, `'ikuywdli@example.ru'`, `'1989-08-17'`,
`'вишнёвая'`. Never disclosed by any result: `i15, i16, i17`. Answer hops 24
(`i4`) and 30 (`i11`) are both `observed` with the same restored string; the record
cannot say which item either was about.

**`memory_anaphora-028.md`** (`request_count 8`, `call_turns [1,3,3]`). UNIQUE:
`'сергеевич'`→`1/i3`, `'rfamnvlh@example.ru'`→`1/i5`, `'2000-03-22'`→`1/i6`,
`'каштановая'`→`1/i7`. MIXED: `'+7 918 724-94-67'`→`[(1,'i4'),(2,'i4'),(3,'i4')]`,
`'устинов'`/`'назар'`→`[(1,…),(3,…)]`. Never disclosed by any result:
`i8, i9, i10, i11`. The dossier's final reply text names `Лебедев Артур` (`i10`)
and `Ерохин Пётр`; neither string stands in any `spans_real` of the run (results
are `seq=1 i1..i7`, `seq=2 i4`, `seq=3 i1,i2,i4`).

**Consequence for M03's row**: an `observed` answer hop proves the reply carried
the real value; it never proves which result supplied it, and in three of the four
dossiers the answer is about items with **no unique result lineage at all**.
«Старый OUT/answer выдавался за ответ после tool result» is therefore not an
occasional instrument slip — it is the normal reading of the current record.
## 3. `reply_raw` is the last NON-EMPTY reply, not the last reply

Verified at `harness.py:551` (`v4_harness` leg) —
`raw = next((reply for reply in reversed(result.replies) if reply.strip()), '')`
— and again at line 670 for the streaming leg. `ArmRunV5.reply_raw` and
`ArmRunV5.base.reply` are therefore the last turn that produced **text**; any later
empty assistant turn, and **any tool call made after that last text turn**, is not
in `reply_raw`. `answer_spans` aligns `reply_raw` against `base.reply`, so a
restoration change in such a later call is invisible to every answer line.
`turn_replies` (restored, per turn, `harness.restored_turn_replies`) is the only
record of the later turns, and no metric reads it except the judge
(`judge.dialogue_context`). Every answer line must say it is about the last text
turn, not the end of the dialogue.

## 4. Chain edges (`source_hop`) — what is already recorded

`Hop.source_hop` is the only recorded A→B edge, and it is a corpus declaration:
`metrics._transitions` reads it with four filters (declared; OUT; owner in
`contracts.ACTING_OUT_OWNERS`; source an IN/tool hop of a *different* tool), while
`actual_hops.py` leaves chains untouched by design (SCOPE, 46–50). An observed run
therefore has **no observed chain edge** — only a declared one beside the
disclosure sets of §2, and the two can disagree (§2, `tool_chain-017`).

## 5. Bound on this review

Read: `docs/plan-hop-form-before-450.md` (M01–M04); `prototype/bench/agentpii5/`
`actual_hops.py`, `contracts.py`, `observe.py`, `metrics.py`, `records.py`,
`harness.py` (lines 540–570, 615–700, 905–945), `test_actual_hops.py`;
`bench/agentpii4/compare.py`; the four dossiers named in §2.
Not read: the 450-run corpus, controls JSON, any secret/config/env file.

## 6. M02 review of the current `actual_hops.py` patch — **no finding**

Read-only scope: `_projection_owner` (320–344), `_one_entity` (347–364),
`_role_parts` (232–250), `_entity_of` (306–317), `_decide` (476–525), and
`test_actual_hops.py` 686–812. The pinned suite passes (`actual_hops: PASS`, 30
checks). Adversarial probes (synthetic fixtures from `fixtures._item/_case/_call`,
`PYTHONDONTWRITEBYTECODE=1`, scripts in `/tmp/m03probe/`, no repository file
written; the untracked mtimes of `prototype/bench/agentpii5/*.py` are unchanged)
covered: whole item + singleton-role item with the same value and different fakes;
the same with the other item's real value in the leaf; two singleton surnames
sharing one fake; conflicting full versions (`p1`/`p1-new`); a stale twin; a
cross-document fake; a fake-equals-real surname; a singleton-role part equal to
another item's whole value. **No probe produced a wrong-identity credit, a collapse
of conflicting versions, or a real/fake collision pass.** Sharpest outputs:

```
A2 not the chosen item's value:  st=value_wrong item='p1' cand=('p1','p1-surname') value_ok=False
B  two singleton surnames:       st=ambiguous   cand=('p1','p2')
C  stale twin:                   st=matched     cand=('p1','p1-old')
E  fake==real surname:           st=residual    item='pS' value_ok=False
```

Two structural observations, not defects: (1) `matched` on a value-shared
whole+part pair is a projection, not a collapse — `_one_entity` groups them by one
`_entity_of`, `_decide` credits `min(id)`, and `candidate_ids` carries both ids,
exactly as `test_whole_and_declared_part_share_one_projection` asserts; when the
values differ the same input is `ambiguous` (probe B), so the collapse is bounded
by the canonical and not by a shared surname. (2) `_entity_of` omits `stale`, so a
stale twin with a byte-identical value collapses into the live item (probe C); the
contract's version rule is about a *changed* value, which `_entity_of` keys on, so
this is only worth chasing if the corpus can carry a `.old` record identical to its
`.new`. Had a defect been found it would appear here as a reproducer with the
failing assertion; none was found.

## 7. What this leaves open for M03

Questions, not decisions: (a) for an answer about an item with no unique result
lineage, what is printed — repeatedly per dossier — so a reader sees the
mixed/unavailable class instead of an `observed` hop; (b) whether the answer leg may
use `turn_replies` (already recorded) to cover turns after the last non-empty
`reply_raw`; (c) whether `metrics.chain_*` keeps scoring declared `source_hop` when
the observed disclosure sets contradict it.
