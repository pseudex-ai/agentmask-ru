# C04 — quote / metalinguistic-quote assessment (independent), 2026-09-28

Reviewer: independent subagent (read-only on code; this file is the single written artifact).
Scope: sprint row **C04** and open decision **OD-2** — distinguish a *metalinguistic quote*
(the agent discussing a string/marker itself, e.g. «клиент написал „8 977 122 70 49" без пробелов»)
from an *ordinary entity mention*, **without** a blanket "skip everything in quotes" heuristic.
Referenced dossier: `research/hop-format-audit/evidence/cases/long_support-027.md` (the agent quotes
«25 гектаров» in its `ticket_create.text` and `escalate_to_human.summary`).

- Plan rows read: `docs/plan-hop-form-before-450.md` C04 (line 66) and OD-2 (line 130).
- `docs/tz-hop-form-adaptation.md` §4 does **not** mention quotes (grep for `кавыч|цитат|quote`
  returns nothing there; §4.2 «Проекции и неоднозначность» is the OD-2 background).
- Code inspected: `prototype/pseudex/detect_all.py` (full read), `prototype/pseudex/redact.py`
  (grep + mask/unmask entry points), plus a package-wide grep for the quote characters.

## 1. (a) Is there a blanket quote-exemption? — NO

Grep for `«`, `»`, `“`, `”`, `"` across `prototype/pseudex/*.py`:

- **`detect_all.py`**: the characters appear only in comments and docstrings. The detection
  pipeline (`normalize → detect_pii / detect_structured / spoken / credentials / vehicle / NER /
  gazetteer / KV / quasi → suppress → _resolve`) never reads or skips quote characters.
- **`redact.py`**: the characters appear only in comments and docstrings. `mask_text` /
  `unmask_text` / `unmask_arguments` never test for quotes.
- The **only** code use of quote characters anywhere in the package is
  `pseudex/address.py:885` — `_PAIR_GAP_RE = re.compile(r"[\s,.:;()«»\"'-]{0,3}\Z")`. This is a
  **gap-separator** regex: it admits quotes as *punctuation between two adjacent address tokens*
  when merging a city + street into one span. It is not a skip and not an exemption; it does the
  opposite of exempting (it lets detection work *through* a quote).

Conclusion: there is **no heuristic that skips or exempts content inside « » or " "**. The
acceptance requirement ("must NOT have a blanket quote-exemption") is satisfied.

## 2. (b) Observed behaviour on the real path

Probes run with `testkit.load_dev_bundle()` + `Detector` + `Vault(":memory:","acme")`
+ `mask_text` / `unmask_text` (throwaway `/tmp` scripts, `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.`).

**Quoted PII is treated as an ordinary entity mention — fail-closed (masked and restored,
identically to the unquoted form).**

| input | spans | masked | restored |
|---|---|---|---|
| `клиент написал «8 977 122 70 49» без пробелов` | PHONE `8 977 122 70 49` | `«8 913 382 93 66»` | exact round-trip ✓ |
| `клиент написал 8 977 122 70 49 без пробелов` | PHONE `8 977 122 70 49` | `8 938 159 04 47` | exact round-trip ✓ |
| `клиент написал "8 977 122 70 49" без пробелов` | PHONE `8 977 122 70 49` | `"8 992 046 02 89"` | exact round-trip ✓ |
| `в карточке указано «Миллер Валерия»` | NAME `Миллер Валерия` | `«Тихонова Светлана»` | exact round-trip ✓ |
| `в карточке указано Миллер Валерия` | NAME `Миллер Валерия` | `Лебедева Жанна` | exact round-trip ✓ |
| `адрес был «Курск, переулок Загородный»` | LOC `Курск, переулок Загородный` | `«Курск, переулок Абрикосовый»` | exact round-trip ✓ |
| `адрес был «Курск, переулок Загородный, д. 16»` | LOC full | `«Курск, переулок Липовый, д. 79»` | exact round-trip ✓ |

The quotes are pure punctuation: the span is the PII substring *inside* the quotes, the quotes
survive untouched, and `unmask_text` restores the real value inside the same quotes. A JSON
argument carrying the phone in a quoted string also masks/restores (`{"phone":"8 977 122 70 49"}` →
`{"phone":"8 983 554 50 54"}` → `{"phone":"8 977 122 70 49"}`).

**Quoted marker / measurement is NOT spuriously masked** (it is not PII, and the engine does not
flag it — not because of any quote rule):

| input | spans | result |
|---|---|---|
| `дополнительно упомянуто «25 гектаров»` | — (none) | untouched ✓ |
| `в карточке было «ул. Вишнёвая»` | LOC `ул. Вишнёвая` | masked (it *is* a street name+marker) |
| `клиент написал «ул.» без названия` | — (none) | untouched ✓ |
| `«д.»` (bare marker) | — (none) | untouched ✓ |
| `«кв. 142»` (flat alone) | — (none) | untouched ✓ |

The dossier's own metalinguistic quote «25 гектаров» is not masked — correct, and it is the
*same* class the overmasking suite already pins as a hard negative («Территория завода 5 гектаров…»,
`test_overmasking.py` line 84). The bare abbreviations «ул.», «д.» are not masked because no
recognizer claims a bare marker; a *street name* with its marker («ул. Вишнёвая») is a real
address and is masked as one.

### Boundary observation — «д. 7»

`«д. 7»` (house marker + number) **is** masked as LOC (`«д. 2»`), and identically when unquoted
(`д. 7` → `д. 3`; `дом 7` → `дом 3`). This is **not quote-caused**: the address recognizer's
marker+number anchor (`address.py` `_HOUSE_AFTER_RE`, «ленина, д. 5» / «ленина д14») treats a bare
house number as a minimal address fragment. It is exactly the OD-2 "semantically unresolvable"
situation — the engine cannot know whether «д. 7» is a metalinguistic remark about the marker or a
real house number — and the correct response per OD-2 is to leave it as documented uncertainty,
**not** to exempt quoted text. This is a pre-existing address-detection precision property, out of
C04's quote scope, and is unaffected by the presence or absence of quotes.

## 3. Required test runs

From `prototype/`, worktree venv, `PYTHONDONTWRITEBYTECODE=1`:

```
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_hard_cases.py   -> EXIT=0
    "hard cases OK — detected, restored, and nothing over-masked"

$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_overmasking.py  -> EXIT=0
    фраз, написанных руками: 42   затронуто 0  (контракт: ноль)
    фраз настоящей речи:     1092  затронуто 6
    всего:        1134
    затронуто:    6
    наблюдаемая точность: 99.5%   (было 69.2% до правок 16.08)
    СЕРТИФИЦИРУЕТ:        не ниже 98.9%   (95%, точный биномиальный)
```

Overmasking line to record: **наблюдаемая точность 99.5% — 6 ложных срабатываний на 1134 фразах,
сертифицирует не ниже 98.9%**. The 6 false positives are NAME homographs («алиса», «алекса»,
«латиной», «монти») — none of them quote-related.

## 4. Verdict — ACCEPTED_NO_CHANGE

1. **No blanket quote-exemption exists** — the only quote-character code is a gap-separator regex
   that admits quotes as punctuation while merging address halves, never a skip.
2. **Quoted PII is handled fail-closed** — a phone, a name and an address inside « » (or `" `)
   are detected, masked and restored exactly like unquoted mentions; the quotes are inert
   punctuation.
3. **Quoted markers/measurements are not spuriously masked** — «25 гектаров», bare «ул.», bare
   «д.», «кв. 142» stay untouched; the only quoted "marker" that masks is «д. 7», which is a
   genuine house-number fragment the address recognizer masks regardless of quotes.
4. The metalinguistic-vs-mention distinction that C04 worries about is therefore **not solved by
   any quote heuristic** — it is left as the semantically-unresolvable boundary that OD-2 already
   documents (keep the current API, diagnose uncertainty, no guessing the person, no automatic
   "don't replace everything in quotes"). No code change is warranted for this row.

No counterexample in C04's own scope (a quote-induced over-mask or a quote-induced skipped leak)
was reproduced.
