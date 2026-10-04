# E01 current-render **v2** — independent read-only acceptance attack (2026-09-28)

Task: `hop-e01-current-render-v2-review-20260928` · workspace `/Users/igor/Projects/Obscura-hop-audit`
(`pwd` verified = that root). Independent attack on the **v2** candidate (`envelope.py` sha256
`8fe487fe…`), after the v1 recheck `evidence/reviews/e01-current-render-recheck-20260928.md`
(REJECT: own-form on the warm path, cache/pass-order, marker collision). Own digits, own fixtures,
natural mint; no author constant reused.

**Verdict against E01's own clause** (docs/plan-hop-form-before-450.md line 51: «Одна сущность
проходит несколько форм без смены личности; каждое сообщение/поле отражает собственную форму; кэш
не возвращает форму чужого упоминания/диалога»):

| # | E01 clause | v2 verdict | Basis |
|---|---|---|---|
| 1 | One identity across several forms, no change of person | **PASS** | §3, §5: 17/17 production-lane checks, both directions |
| 2 | Each message/field reflects **its own** form | **PASS** | §3: `8`-mint/`+7`-result and `+7`-mint/`8`-result both correct, warm and repeated |
| 3 | Cache does not return another mention's/dialogue's form | **PASS** | §3 `first == again`; §5 foreign conversation; §4 nonce markers |
| — | Marker targeting (v1 REJECT) | **PASS (fixed)** | §4: 17/17 collision probes, payload markers preserved, no engine control byte survives |
| — | S01 seven refused bindings + controls | **PASS** | §5: 7/7 refusals, 5/5 armed-substitute repeats, ordinary numbers byte-identical, rows 0→0 |
| — | **No `+8` / `++`** (control asserted by `test_phone_hop_form.py`) | **REJECT** | §6: a `+8`- or `++`-shaped tool echo is mirrored into `+8 <fake>` / `++7 <fake>` |

**E01's own clause: PASS (3/3).** One REJECT-level residual outside the clause's wording but inside
E01 acceptance as operated: the `+8`/`++` control. Two boundaries marked in §7.

No source, test, wiki, corpus or saved run was modified. The only file written is this report. The
S02 writer's file was not opened, run or touched. No child sessions, no network, no provider, no
paid 450.

## 1. Hashes and diff

* Candidate `prototype/pseudex/envelope.py` sha256
  `8fe487feffe5925329bfd9a6d1cfe8c2b06bf42d44d35610875c5cf1249b1f38` — **matches** the task hash
  (recomputed here); 1663 lines.
* v1 `81fb0c4c2626ca0c68a07d05df77e803cb177a1ce6f702432ab987081f065955`: no artifact for it exists
  in the workspace or `/tmp` (checked; only the v1 report names it), so v1 was **not re-run**. The
  v1→v2 delta is read from the v2 source and the diff below.
* S01 frozen `/tmp/s01-frozen/envelope.py` = `2ee78458856717a6f86fb4735384db6a6cf4119efd7c34ada7a040e3a0cb5c6b`
  (recomputed), 5 hunks / +315 diff lines over the candidate. v2 over S01-frozen adds exactly:
  `_surface_in`, `_phone_echo_is_a_cut`, the rewritten `_project_echo`, the `nonce`-bearing
  `_echo_marker`/`_free_marker_nonce`, `_reserve_echoes`/`_splice_reserved`, `_mask_text_leg`.
* `git rev-parse HEAD` = `9c5acbb`; HEAD's `envelope.py` = `ac3d7e0b…` (older than v1 and v2).
* Runtime: `prototype/.venv/bin/python` from `prototype/`; probes in `/tmp/e01v2/` (`probe.py`,
  `plus8.py`).
* Fresh fixtures, never the suite's constants: real `8 962 431 07 55` (`+7 962 431 07 55`,
  `79624310755`) and `+7 913 748 20 66`; names `тихомиров арсений`; address
  `краснодар проспект кирова 53 квартира 79`. Mint is the **natural** `vault._fake_phone`
  (`+79…`), shown in the user's notation by the vault — **no `_fake_phone` patch anywhere**.

## 2. Recomputations of the accepted suites

| command (from `prototype/`) | result |
|---|---|
| `.venv/bin/python test_phone_hop_form.py` | 26/26 shared-envelope hops **and** 16/16 warm two-request notation hops, 24/24 value+form, 11/11 regression controls, exit 0 |
| `.venv/bin/python test_error_echo_privacy.py` | **311/311 passed**, exit 0 |
| `.venv/bin/python test_tool_result_context.py` | 13/13, exit 0 |
| `.venv/bin/python test_argument_form.py` | exit 0 |
| `.venv/bin/python test_derived_forms.py` | **flaky**: one run 2 failures (`ю → yu` ICAO/GOST), later runs clean — byte-identical to the recorded S01-frozen failure `/tmp/s01-frozen/test_derived_forms.observed-failure.log`; **pre-existing, not v2** |
| `python3 wiki/check.py` (repo root) | **0 finding(s)** |
| `PYTHONPATH=. .venv/bin/python /tmp/e01v2/probe.py` | **110 passed / 1 failed** (the `+8` in §6) |

## 3. PASS — the production two-request `long_order-058`, both directions, natural mint

`REQ1` masks the user turn alone (minting the row); `REQ2` masks `[user, assistant call, tool result]`
with the call leaf set to the substitute the dialogue actually showed. 17/17 checks.

```
8-notated natural mint, tool result in +7 form
  shown (user turn, natural) = "8 935 177 14 49"   (8-notated, never "+8")
  call leaf (as-is)          = "8 935 177 14 49"   -> call leaf preserved
  tool result                = "bad: +7 962 431 07 55"
  rendered                   = "+7 935 177 14 49"  PASS  (own +7 form, real digits absent,
                                                     no "+8"/"++", user's 8-form not imported,
                                                     canonicalise(rendered) == canonicalise(shown))
+7-notated natural mint, tool result in 8 form
  shown                      = "+79689299573"-shaped
  rendered                   = "8 …"               PASS  (own 8 form, no "+8"/"++")
repeat of the identical request -> byte-identical result   PASS  (cache/pass-order)
```

Clause 2 and clause 3 therefore **PASS on the exact defect v1 rejected**, under a naturally notated
mint — which is what `test_phone_hop_form.py`'s E.164 patch could not exercise. Mechanism confirmed
by reading: `_project_echo`'s PHONE branch now asks the **fragment's** notation before `as_is`
(`envelope.py:997-999`), and the `+` is claimed with the digits in `_reserve_echoes`
(`:1098-1101`).

## 4. PASS — marker collision is fixed

`_free_marker_nonce` (`:1042-1055`) picks the first nonce whose `\x00EO{nonce}:{index}\x01` tokens are
absent from the raw text, and `_splice_reserved` (`:1119-1128`) can then only find this pass's own
token. 17/17 probes:

* literal old-format `\x00EO0\x01` **before** and **after** a real echo: preserved exactly; the
  substitute landed on the echoed span; no `\x00` survives outside the payload's own bytes;
* new-format `\x00EO0:0\x01` and `\x00EO1:0\x01` in the payload (nonce-forcing) **and** before/after
  the echo: both preserved, nonce advanced, substitute on the echo, no engine byte survives;
* two claimed spans of the same identity in one body (`+7…` and `8 …`): both carry the substitute,
  no control byte, real digits absent;
* list/block content: text block protected, payload marker preserved, `image_url` block passed
  through untouched; unrelated `unrelated@mail.ru` masked in every lane.

The v1 counterexample (`{"a": "\x00EO0\x01", "b": "+7…", …}` writing the substitute over `a`) no
longer reproduces.

## 5. PASS — S01 regression, boundaries and rows

* **Seven refused bindings** (wrong id, id key absent, no declaration, mismatched tool name, invalid
  JSON arguments, duplicate id, future declaration): the dictated/digital cut of the user's own
  number is absent in **7/7**, no person's substitute is guessed, no `+8`/`++`; the **armed control**
  carries its own substitute on **5/5 fresh fixtures** (so the refusals are not vacuous).
* ordinary quantities `order 12345, count 8, code 7926547, sum 510.00, id 796243107` come back
  **byte-identical**;
* a foreign conversation neither imports A's substitute nor B's own, and keeps a fragment it never
  carried;
* echo leg mints **no** new vault row (`shown_forms` 1 → 1).
* NAME lower / UPPER / Title, full echo and 8-character cut: the real fragment is absent and the
  result carries the current-case rendering in every case; the 8-char cut was repeated on **6/6**
  fresh fixtures without a leak (see §7 for the separate `derived_forms` flake).
* LOC representative (`кирова 53 квартира 79`): real street absent, no hybrid splice, one minted
  substitute.

## 6. REJECT — the no-`+8` / `++` control (`_phone_echo_is_a_cut` / `_project_echo`)

Exact counterexample, own digits, natural mint (`/tmp/e01v2/plus8.py`):

```
echoed by the tool : "+8 962 431 07 55"     rendered : "+8 935 177 14 49"
echoed by the tool : "+89624310755"         rendered : "+89699759311"
echoed by the tool : "+8 (962) 431-07-55"   rendered : "+8 (951) 241-94-35"
echoed by the tool : "++7 962 431 07 55"    rendered : "++7 917 084 27 45"
```

The real digits never survive and the identity is preserved (`canonicalize(rendered) ==
canonicalize(shown)`), so this is **not a disclosure** — it is an invalid surface reaching the model.
Root: `_phone_echo_is_a_cut` reads `written in renderings` — the `8`-trunk rendering is a rendering,
so a `+8…` echo is classified as a **re-notation**, not a cut, and `_project_echo` calls
`_digits_in_form_of(fragment, substitute)`, whose phone branch keeps the written prefix
(`written_digits[:-10] == "8"`) while the model's `+` is preserved → `+8 <fake>`. The `++` case is
the same branch: `_NUMBER_RE` matches from the second `+`, the first `+` is left outside the span,
and the replacement brings its own `+7` → `++7 <fake>`.

Why this is a REJECT item: `test_phone_hop_form.py:96` and `:126` assert `"+8" not in` / `"++" not
in` the result, and `_digits_in_form_of`'s own docstring says the phone branch exists precisely to
avoid «+8 916…». No accepted lane echoes a `+8`/`++` shape, so the control is green by omission — the
same gap shape the v1 report found for the 8-notated mint. The previous report's clause table listed
«no `+8` / doubled country code» as an E01 control; under that reading this clause is **REJECT**.

## 7. Boundaries, clearly marked (not counted as E01 failures)

* **Sub-floor flat cuts are not claimed.** A flat 9-digit cut of the real (`896243107`, `962431075`)
  is returned **as written**; `_ECHO_DIGIT_BOUNDARY["PHONE"]` holds a bare flat run to the whole
  significant length (10), so a 9-digit flat run is deliberately not read as a phone. The signed
  (`+796243107`) and grouped (`8 962 431 07`) and 10-digit flat (`7962431075`) cuts **are** claimed
  and protected. This floor is pre-existing (S01/`_numeric_echo_spans`) and v2 does not move it.
  Counterexamples are exact; whether a 9-digit subscriber cut must be protected is an S01-boundary
  decision, not an E01-form decision.
* **A real phone prefix inside a longer ordinary run** (`track: 7962431075512345`) is left as
  written: the run is not a prefix of any rendering, so `_numeric_echo_spans` refuses it. Documented
  boundary, unchanged by v2, stated for completeness — the value there is the ordinary run, not the
  phone.
* **`test_derived_forms.py` flake** (§2) is a random-fixture failure identical to the recorded
  S01-frozen log, so it predates v2 and does not implicate the warm-notation or marker changes.
* Untested in this budget: live `proxy.py`/`service.py` HTTP wrappers (both call
  `envelope.mask_messages`, so the finding is on both legs by construction); production frequency of
  `+8`/`++`-shaped tool echoes (the shape is malformed tool output, not observed traffic); a
  `+8`/`++` lane in the accepted suite (does not exist — that is the gap).

## 8. Reproduction

```
cd /Users/igor/Projects/Obscura-hop-audit/prototype
.venv/bin/python test_phone_hop_form.py         # 26/26 + 16/16 warm, exit 0
.venv/bin/python test_error_echo_privacy.py     # 311/311, exit 0
.venv/bin/python test_tool_result_context.py    # 13/13
.venv/bin/python test_argument_form.py          # exit 0
PYTHONPATH=. .venv/bin/python /tmp/e01v2/probe.py    # 110 passed / 1 failed (+8)
PYTHONPATH=. .venv/bin/python /tmp/e01v2/plus8.py    # the +8 / ++ counterexamples
cd .. && python3 wiki/check.py                   # 0 findings
```

**E01 v2: PASS on its own clause** — one identity across forms (1), each field its own form (2), no
foreign/cached form (3); the v1 marker REJECT is fixed and the S01 refusals and no-new-row controls
hold. **One REJECT-level residual**: a malformed `+8`/`++` tool echo is mirrored into an invalid
`+8 <fake>` / `++7 <fake>` surface, contra the suite's own no-`+8`/`++` control (§6). This is an
independent review, not formal acceptance; Codex owns acceptance.
