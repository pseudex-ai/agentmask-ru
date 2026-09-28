# M02 v14 scorer — independent adversarial acceptance review

Reviewer: DSH subagent (independent adversarial reviewer), parent session
`session-e2835ab5-2723-4584-9e76-f4dd468a97ac`. **NOT the author.** Read-only on
all code; this file is the only artefact written. Date: 2026-09-28. No network,
no provider, no paid generation, no child sessions, no merge.
Candidate: `prototype/bench/agentpii5/actual_hops.py`, estimator
`m0-actual-out-v14` (worktree branch `research/hop-format-audit`, uncommitted).

## Verdict

| Row | Verdict | One line |
|---|---|---|
| **M02** | **ACCEPTED_FIX (scorer)** | All five acceptance clauses hold on independent probes: a matching surname across two people stays `ambiguous` (1a/1b), an old vs new value version of one field stays `ambiguous` with both values visible (2), a 2–3 digit number never attributes to a phone and the full fake in the wrong field is still `residual` (3), the residual flag is identical with an owner and with a forced no-owner and is computed by a single ownerless reader `_leaf_leak` (4), and a city-only identity is refused as `unattributed` (5). The denominator is honest: every column divides by one `candidates` set that includes `ambiguous`/`unattributed`/`not_identifiable`/`mixed`, and `not_applicable` is printed separately outside it (6). |

## 1. Hashes and run identity

| artefact | sha256 |
|---|---|
| `prototype/bench/agentpii5/actual_hops.py` | `d40a9c94eae3c688c4b382a7f21db60ad80a6dd64cb192c29095f7b9190df689` |
| `prototype/bench/agentpii5/test_actual_hops.py` | `df219e4f873c6f85009154429976d2d86f0a133398eb180f61c140f18d30bca3` |

`ESTIMATOR_VERSION` printed by the import is `m0-actual-out-v14`, matching the
task's candidate name.

## 2. What was run (all local, offline, reproducible)

Run from `prototype/` with `PYTHONDONTWRITEBYTECODE=1` and `.venv/bin/python`:

```
python -m bench.agentpii5.test_actual_hops     # exit 0 — 53/53 PASS (see below)
python -m bench.agentpii5.test_hop_report      # exit 0 — "hop_report: PASS"
PYTHONPATH=. .venv/bin/python /tmp/probe_m02.py   # exit 0 — reviewer probes 1–6
PYTHONPATH=. .venv/bin/python - <<'PY' …           # exit 0 — reviewer probes 7–8
```

`test_actual_hops` printed 53 checks, all `PASS`, final line `actual_hops: PASS`,
exit code 0. `test_hop_report` exists and printed `hop_report: PASS (offline,
manifest, events, historical + causal lines, immutable output)`, exit code 0.

The reviewer probe script `/tmp/probe_m02.py` (throwaway, NOT committed to the
repo) uses the **public entry point** `actual_events(case, run)` plus
`aggregate`/`render`, and the same fixtures builders the repo's own test imports
(`bench.agentpii5.fixtures._item/_case/_run/_with_calls/_with_mentions/_with_subs/_call`,
`bench.agentpii5.contracts.MentionRecord`). Private helpers are inspected for
structure only (`inspect.signature`/`inspect.getsource`), never called to
manufacture a verdict.

## 3. Probes and observed results (exact API calls)

Every probe below calls `actual_events(case, run)` and reports
`(status, item_id, candidate_ids, value_ok, residual, attributed)`.

### 3.1 Matching surname across two different people must not merge owners

Two different people (`i1` vs `i2`) wearing the SAME surname, attacked from both
sides of the leaf:

```
1a  real shared surname written AND restored
    p1 = NAME "Иванова Елена" (i1)   p9 = NAME "Иванова Анна" (i2)
    leaf contact.last_name  written="Иванова"  restored="Иванова"
    -> ('ambiguous', '', ['p1','p9'], value_ok=False, residual=False, attributed=False)

1b  two DIFFERENT people whose FAKES share a surname
    p1 fake "Пахомова Ольга" (i1)   p9 fake "Пахомова Анна" (i2)
    leaf contact.last_name  written="Пахомова"  restored="Иванова"
    -> ('ambiguous', '', ['p1','p9'], value_ok=False, residual=False, attributed=False)
```

Both refuse attribution and keep both candidate ids visible; neither picks the
min-id owner. (Matches `test_two_people_sharing_a_part_are_ambiguous` and the
CAN-FAIL half of `test_semantic_duplicate_items_are_one_entity`.)

### 3.2 Old vs new value version of the same field stays distinguishable

One person (`i1`), two PHONE values — the old and the new — both fakes in one leaf:

```
2a  p2  = PHONE "+79164021187" (old)   p2b = PHONE "+79261234567" (new), same identity i1
    leaf SMS text  written="звоните +79990001122 или +79991112233"
                   restored="звоните +79164021187 или +79261234567"
    -> ('ambiguous', '', ['p2','p2b'], value_ok=False, residual=False, attributed=False)

2b  same person, same address field, stale old vs fresh new VALUE
    i7 = LOC "лермонтова" stale=True   i8 = LOC "пихтовая" stale=False
    leaf SMS text  written="ул Сосновая или Берёзовая"  restored="ул лермонтова или пихтовая"
    -> ('ambiguous', '', ['i7','i8'], value_ok=False, residual=False, attributed=False)
```

`_entity_of` keys on identity+type+value+parts (not identity alone), so the two
values are two entities; no silent min-id pick and no cross-version credit.

### 3.3 A short unrelated number must not be attributed to a phone/identifier

A PHONE item `+79164021187`, fake `+79990001122`, with short quantities in
non-phone leaves. `"11"` and `"87"` are literal substrings of the real phone's
digit run — the strongest form of this trap:

```
3   call clinic_book  patient.age="25"  month="11"  order_id="87"   (all unchanged)
    -> patient.age: not_applicable, month: not_applicable, order_id: not_applicable
       (zero candidate events; nothing attributed to the phone)

3b  CAN-FAIL: full fake phone in the wrong field stays observable
    call clinic_book  month="+79990001122"  restored unchanged
    -> month: status='residual', residual=True   (not silently exempted)
```

Also probed the typed role leaf: a short `"25"` in `contact.phone` is
`unattributed` (visible, unresolved, no value credit), while the FULL real phone
in `contact.phone` is `unmasked_known` on `p2`. The `_value_ok` PHONE branch
requires a 10–11 digit run, so a 2–3 digit quantity can never pass it.

### 3.4 Residual is measured independently of the owner choice

Same case, same `restored` text (so the same standing fake), toggling only
whether the written side names an owner:

```
4   p1 = NAME "Иванова Елена" fake "Пахомова Ольга"
    pb = LOC "лермонтова" fake "Пихтовая"   (minted street, not in customer's vocab)

A   owner chosen:
    written="Клиент Пахомова Ольга, адрес уточняется"
    restored="Клиент Иванова Елена, адрес: Пихтовая"
    -> ('residual', 'p1', ['p1'], value_ok=False, residual=True, attributed=True)

B   forced no-owner (written side carries no substitute):
    written="Клиент, адрес уточняется"
    restored="Клиент Иванова Елена, адрес: Пихтовая"   # SAME restored text
    -> ('unattributed', '', [], value_ok=False, residual=True, attributed=False)
```

The residual flag is `True` in both — the standing fake of `pb` is reported
whether or not `p1` is chosen, and the ownerless row carries `residual=True`
with `item_id=''`. Structural confirmation: `_leaf_leak`'s signature is
`(case, run, spec, restored, own, call_turn, call_seq)` — **no chosen-entity
argument** — and its body iterates `for item in case.base.pii`, i.e. it scans
every item with an available surface before any owner decision is made.
`_restoration` calls it before `_value_ok`, so the leak question cannot be
gated on the winner.

### 3.5 A city-only identity is refused

```
5   whole LOC "смольный" (city=челябинск) + street-only projection "смольный"
    i8 substitute = "г Челябинск, ул Пихтовая, д 83"  (generic city "Челябинск"
    is the customer's OWN city, carried in a GENERIC role)
    leaf address_suggest.query  written=restored="Челябинск 19 километров"
    -> ('unattributed', '', [], value_ok=False, residual=False, attributed=False)
```

The generic settlement proves no minted part and chooses no identity (v12); the
leaf stays visible as `unattributed`, never credited to `i8`. (Mirrors
`test_generic_city_role_does_not_choose_an_identity`.)

### 3.6 Whole/part projection is gated on proved belonging (extra)

```
7   whole NAME "Иванова Елена" (i1)  vs  surname-only part "Иванова" of a
    DIFFERENT person (i2) — the part's surname equals the whole's surname.
    leaf contact.last_name  written="Пахомова"  restored="Иванова"
    -> ('ambiguous', '', ['p1','p9'], residual=False, attributed=False)
```

`_projection_owner` requires identical `identity` (+type, +stale, +declared
part), so a surname-only record of another person does not project onto the
whole. Belonging is proved by the corpus identity, never by a shared surname.

## 4. Denominator honesty

Probe 6 built one run producing `matched`-class, `ambiguous`, `unattributed` and
`not_applicable` leaves together and inspected `aggregate` + `render`:

```
runs 1 · events 3 · not_applicable 1 (in no denominator)
all:        candidates 2  attributed 0  value 0  form 0  residual 0  joint 0
statuses:   matched 0  mixed 0  residual 0  value_wrong 0  unmasked_known 0
            ambiguous 1  unattributed 1  not_identifiable 0
```

Assertions verified: `events_total == candidates + not_applicable`;
`value_ok <= candidates`, `attributed <= candidates`, `joint_ok <= candidates`;
the `statuses` tuple contains **every** `CANDIDATE_STATUSES` key (count 0 when
absent); and `sum(status counts) == candidates`. Nothing hides
`unattributed`/`ambiguous`/`not_identifiable`/`mixed` — they are inside the
single shared denominator, and `not_applicable` is the one status printed
separately and excluded, with the render line saying so explicitly. The header
states that `attributed/value/form/residual/joint` all divide by `candidates`.

## 5. Author claims that hold (independently reproduced)

* **v14 keeps the residual flag independent of the owner choice** — probe 4
  (flag identical across owner/no-owner runs; `_leaf_leak` is ownerless by
  signature and scans every item).
* **v14 refuses a city-only identity** — probe 5 (`unattributed`, not credited).
* **The v14 LOC notation rescue is a bounded false-negative rescue** — the
  suite's `test_joined_address_notation_is_not_a_wrong_value`,
  `test_notation_rescue_asks_every_declared_role` and
  `test_joined_address_refuses_competing_values` (wrong street, wrong house,
  extra numbers, wrong street-type, a competing value, an old-address note) all
  PASS, so the rescue cannot buy a wrong value.
* **Neighbouring controls intact** — `test_same_surname_and_old_new_versions_never_charge_the_collider`,
  `test_two_people_sharing_a_part_are_ambiguous`,
  `test_same_identity_different_value_is_ambiguous`,
  `test_short_numbers_do_not_attribute_without_a_role`,
  `test_standing_fake_is_residual_under_the_resolved_identity`,
  `test_generic_city_role_does_not_choose_an_identity`,
  `test_leaf_residual_survives_a_resolved_identity` all PASS.

## 6. Cost / accounting

Zero provider calls, zero network, zero paid generations, no child sessions, no
workflow. Every command is local and replayable; the reviewer probe lives in
`/tmp/probe_m02.py` (not committed) plus two inline heredoc probes. No `.py`
file in the repo was modified; the only written artefact is this markdown file.
Stop rule: no counterexample was found after the five mandated probe classes
plus two extra edge probes, which is sufficient for ACCEPTED_FIX.
