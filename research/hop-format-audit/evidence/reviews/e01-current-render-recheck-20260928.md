# E01 current-render — independent read-only acceptance review (2026-09-28)

Task: `hop-e01-current-render-review-20260928` · workspace `/Users/igor/Projects/Obscura-hop-audit`
(`pwd` verified = that root). Independent recheck of the **current** E01 candidate, after the
accepted S01 report `evidence/reviews/s01-unbound-privacy-recheck-20260928.md`, which explicitly
left the literal `long_order-058` PHONE-notation shape **not re-run**. This review closes that gap.

## Verdict, stated per E01 clause (docs/plan-hop-form-before-450.md line 51)

> Acceptance clause: «Одна сущность проходит несколько форм без смены личности; каждое
> сообщение/поле отражает собственную форму; кэш не возвращает форму чужого упоминания/диалога.»

| # | E01 clause | Verdict | Basis |
|---|---|---|---|
| 1 | One identity across several forms, no change of person | **PASS** | §3 A/B/C — substitute digits/identity stable in every lane; no wrong identity observed |
| 2 | Each message/field reflects **its own** form | **REJECT** | §4 — on the production two-request path the result renders in the **other** mention's notation, both directions |
| 3 | Cache does not return another mention's/dialogue's form | **REJECT** | §4 — pass-order/cache dependence: call 1 ≠ call 2 for an identical request |
| 4 | No `+8` / doubled country code | **PASS** | §3 — no `+8`, no `++` in any lane |
| 5 | No new vault row / audit slot from the echo leg | **PASS** | §3 A/B |
| 6 | Conservative S01 unbound privacy still holds | **PASS** | §5 — 7/7 shapes |
| 7 | Marker replacement targets the generated span | **REJECT (integrity; no PII leak)** | §6 — collision with a literal `\x00EO<N>\x01` in the result |

**Overall E01: REJECT.** The row's own literal case (`long_order-058`: user `8 …`, tool result
`+7…`) is still rendered in the user's `8 …` form on the production path. The accepted suite is
green because `test_phone_hop_form.py` forces the substitute to E.164 with
`patch("pseudex.vault._fake_phone", return_value=FAKE_PHONE)`, so the failing shapes are never
exercised with a naturally notated mint.

No code, test, wiki, corpus or saved transcript was modified. The only file written is this report.
`prototype/bench/agentpii5/actual_hops.py` and `test_actual_hops.py` were not opened, run, edited or
attributed (concurrent M02 writer).

---

## 1. Hashes, baseline, discipline

* Frozen E01 candidate: `prototype/pseudex/envelope.py` sha256
  `81fb0c4c2626ca0c68a07d05df77e803cb177a1ce6f702432ab987081f065955` — **matches** the task hash
  (recomputed here).
* `/tmp/s01-frozen/envelope.py` baseline sha256
  `2ee78458856717a6f86fb4735384db6a6cf4119efd7c34ada7a040e3a0cb5c6b`; the candidate is
  **+174 lines** over it, in 5 hunks. The E01 delta is exactly: `_surface_in` (casefold surface
  match), `_project_echo` (+ `_digits_in_form_of` import), `_ECHO_RESERVED`/`_reserve_echoes`/
  `_splice_reserved`, and `_mask_text_leg` (apply the call's evidence to the ORIGINAL span **before**
  detection). `git rev-parse HEAD` = `9c5acbb`.
* Read-only. Probes live in `/tmp/e01-recheck/` (`probe.py`, `micro2.py`) and import the engine; no
  engine file was written. No child sessions/subagents, no network, no provider, no paid 450.
* Runtime: `prototype/.venv/bin/python` 3.12.12, commands from `prototype/`.
* Context read: `wiki/MAP.md`, `wiki/INVARIANTS.md`, `wiki/AGENTMASK.md`, `docs/plan-hop-form-before-450.md`
  (rows S01 line 44, E01 line 51, E02 line 52, matrix §5), `docs/plan-hop-form-execution.md`
  (stage 2, lines 123–133), the literal `evidence/cases/long_order-058.md` dossier, and the accepted
  S01 report.

## 2. Recomputations (author-adjacent; reported as recomputation, not as proof)

| command (from `prototype/`) | result |
|---|---|
| `.venv/bin/python test_error_echo_privacy.py` | **305/305 passed**, exit 0 |
| `.venv/bin/python test_phone_hop_form.py` | **26/26 shared-envelope current-form hops passed**, exit 0 (`24/24` value+form, `11/11` regression controls) |
| `.venv/bin/python test_tool_result_context.py` | 13/13, exit 0 |
| `.venv/bin/python test_argument_form.py` | exit 0 |
| `python3 wiki/check.py` (repo root) | **0 finding(s)** |
| `.venv/bin/python /tmp/e01-recheck/probe.py` | fresh fixtures, §3–§6 |
| `.venv/bin/python /tmp/e01-recheck/micro2.py` | notation + F future-declaration |

The proof is the fresh fixtures below, built from my own spoken number
(`8 962 431 07 55`, spelled out), my own names (`тихомиров арсений`, `захаров пётр`,
`наумов кузьма`) and my own address — never copied from the suite's constants.

## 3. What passes

**A. PHONE, literal `long_order-058` digits (`8 988 999 09 49`).** Four result shapes
(`+79889990949`, reverse `89889990949`, grouped `8 988 999 09 49`, signed `+7 988 999-09-49`):
the real digits never survive, no `+8 `, no `+8(`, no `++`, and the substitute digits are preserved.
Vault rows `0->0`, audit `2->2`.

**B. NAME, current-request form.** lower / UPPER / title × (full real echo, 8-char cut): the call
leaf keeps the model's case, no raw real fragment, the result carries the current-case rendering,
no doubled first word, `rows 0->0`, and a model that writes the **real** name into the call still
gets a clean result (`крылов яков`). (One residual noted in the S01 report — a re-cased call leaf
with a retyped rendering — was not re-measured here; it is not a leak.)

**C. LOC representative.** Full real address, partial `кирова 53`, and street-only: the real street
is absent from the result and the result carries the one minted substitute
(`краснодар проспект озёрный 20 квартира 59`) — no hybrid splice, no wrong identity.

**D. User IN vs tool IN independent; conversation/tenant isolation.** The tool result is answered
from the call's own evidence; a foreign conversation view does not inherit the first dialogue's
substitute; ordinary quantities (`order 12345, count 8, code 7926547, sum 510.00`) come back
**byte-identical**. A stored substitute embedded in a longer ordinary token (`наумовский` for real
`наумов`) is **not** over-masked (the `_bounded` token check holds) — `probe.py` §E.

**E. S01 unbound privacy, seven shapes.** wrong id, id key absent, no declaration, mismatched tool
name, invalid JSON arguments, duplicate id, future declaration: the 70-char dictated fragment is
absent from all seven; the conservative neutral-redaction leg is intact (`probe.py` §F, `micro2.py`).

## 4. REJECT — the result does not keep its own notation on the production path

E01's defect, in the row's words, is «result `+7…` маскируется в прежней форме пользователя `8 …`».
The candidate fixes it only on a **cold** pass. Two independent reproducers (no suite constants;
`_fake_phone` patched to a fixed **8-notated** substitute, the same technique the suite uses to
force an E.164 one):

```
# real path: REQ1 mints, REQ2 carries the tool result (the dossier's turn 7)
patch(_fake_phone -> "8 968 929 95 73")
REQ1 user:  "телефон 8 988 999 09 49 звоните"
REQ2 call:  phone = "8 968 929 95 73"          (the as-is substitute)
REQ2 tool:  "bad: +7 988 999 09 49"            (the tool's own +7 form)
=> rendered = "8 968 929 95 73"   FAIL  (expected leading "+7")

# reverse direction
patch(_fake_phone -> "+79689299573")
REQ1 user:  "телефон +7 988 999 09 49 звоните"
REQ2 tool:  "bad: 89889990949"                 (8-flat)
=> rendered = "+79689299573"      FAIL  (expected leading "8")
```

Both directions fail exactly the assertion `test_phone_hop_form.py:84-86` states:
`leading = "8" if echoed.startswith("8") else "+7"; assert rendered.startswith(leading)`.
The suite passes because every lane patches the substitute to

`test_phone_hop_form.py:75` `with patch("pseudex.vault._fake_phone", return_value=FAKE_PHONE)`
(`FAKE_PHONE = "+79795553322"`, an E.164 substitute), whose own notation coincides with the `+7`
result — so lanes 1–2 pass by construction and lane 3 (8-flat result) passes through
`_digits_in_form_of`. No lane mints an `8 …` substitute against a `+7` result, which is precisely
`long_order-058`.

**Same defect as a cache/pass-order clause.** The identical request on one warm context:

```
8-notated mint, +7 echo:   call1 "+7 968 929 95 73" | call2..4 "8 968 929 95 73"
+7-notated mint, 8 echo:   call1 "89689299573"      | call2..4 "+79689299573"
```

`call1 != call2` for identical input, converging on the **mint/user** notation. This is the
accepted suite's own invariant at `test_phone_hop_form.py:120`
(`assert first == again, "a cache hit changed the result's form"`) and at `:121`
(`assert stored not in first`) — green only under the E.164 patch.

**Mechanism (localized, lines).** `_project_echo` (`envelope.py:933-987`) short-circuits an exact
echo with `if as_is or fragment == real or ...: return substitute` (`:955`); `as_is` is
`value.substitute in renderings` (`:1022`) and `renderings` is the frozen provenance snapshot taken
before the pass. On a cold pass the row/rendering is absent, the lane reaches
`_digits_in_form_of` (`:966`) and re-notates; on a warm pass `as_is` is true and the substitute's own
notation is returned verbatim. The result therefore follows the **mint**, not the echoed field, once
the row exists — which is the normal multi-turn case. Fix direction belongs to the author (Codex owns
formal acceptance); this report only localizes the binding point the row asked to localize.

## 5. Controls held

* Ordinary quantities byte-identical (§3 D); foreign conversation does not import A's substitute.
* S01 seven unbound shapes intact (§3 E).
* No new vault/audit row from the echo leg (A/B).

## 6. REJECT (integrity, no PII leak) — marker collision

`_reserve_echoes` lifts a bound echo into `\x00EO<N>\x01` (`envelope.py:990-1050`) and
`_splice_reserved` (`:1053-1059`) puts it back with `text.replace(f"{_ECHO_RESERVED}{index}\x01",
replacement, 1)` — **first occurrence**, not the recorded offset. A tool result that literally
carries the marker bytes is targeted instead of the generated span:

```
tool result: {"a": "\x00EO0\x01", "b": "+79624310755", "c": "unrelated@mail.ru"}
masked:      {"a": "8 947 733 83 26", "b": "\x00EO0\x01", "c": "oitbmwkm@example.ru"}
```

* raw real phone `79624310755`: **absent** (no PII leak);
* unrelated email: **masked** (detection still runs on the rest);
* but the generated marker at `b` **survives raw** in the model-visible body, and the substitute is
  written over the attacker-controlled literal at `a` — i.e. replacement does **not** target the
  generated span, contradicting `_splice_reserved`'s "put the call-backed renderings where their
  markers survived". A lone marker with no claim also passes through unchanged (`probe.py` §D2);
  that one is arguably plain pass-through of tool bytes, but the collision case is the engine's own
  marker escaping.

Severity: integrity/protocol (a control byte reaches the provider; a substitute is mis-positioned),
**not** a disclosure — the claimed real spans are still removed. It is a concrete counterexample to
the "marker replaced afterwards" property and should be fixed with an offset/placeholder scheme that
cannot be forged by the payload (e.g. a per-pass random marker, or splice by recorded index).

## 7. Not measured in this budget

* **Mutation test of the new precedence** (`_mask_text_leg` reverting to mask-first) was **not run**
  under time; the assertions that would catch it are
  `test_error_echo_privacy.py:1645` (`..._retyped_name_replay_carries_its_current_case_into_the_result`)
  and the `leading` check in `test_phone_hop_form.py:84-86`, but §4 shows those are green because the
  failing notation lane is patched out — so a mutation probe is required before claiming the
  precedence is pinned.
* The live HTTP wrappers (`proxy.py`/`service.py`) were not started; both call
  `envelope.mask_messages`, so the finding is on both legs by construction.
* Production frequency of marker-shaped tool bytes, and the JSON/multipart marker-crossing paths,
  were exercised only through string and single-block content — a list/block fixture was not run.

## 8. Reproduction

```
cd /Users/igor/Projects/Obscura-hop-audit/prototype
.venv/bin/python test_error_echo_privacy.py         # 305/305
.venv/bin/python test_phone_hop_form.py             # 26/26
.venv/bin/python test_tool_result_context.py        # 13/13
.venv/bin/python test_argument_form.py              # exit 0
.venv/bin/python /tmp/e01-recheck/probe.py          # fresh fixtures
.venv/bin/python /tmp/e01-recheck/micro2.py         # notation + future declaration
cd .. && python3 wiki/check.py                       # 0 findings
```

**E01: REJECT** — clauses 2 and 3 (own-form and cache) fail on the production two-request path with
a naturally notated mint; clause 7 (marker targeting) fails as an integrity defect. Identity
stability, no-`+8`, no-new-row, S01 unbound privacy, isolation and ordinary-quantity controls all
**PASS**. This is an independent review, not a formal acceptance; Codex owns acceptance.
