# C01 baseline — non-PHONE hop types versus the §1 current-sender contract

**Status: RED. 47/66 contract checks pass, 19 fail.** The earlier version of this
file reported 59/59 green; that was wrong — it froze the engine's current
behaviour as expected. Withdrawn. Expectations here come from
[`docs/tz-hop-form-adaptation.md`](../docs/tz-hop-form-adaptation.md) §1
(content from the entity, form from the CURRENT sender on all four boundaries),
and the engine is measured against them.

**Test:** `prototype/test_other_hop_forms.py` (66 checks, 2 questions).
**Command, from `prototype/`:**

```bash
PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python test_other_hop_forms.py
```

## Revision

| item | value |
|---|---|
| commit | `9c5acbb13e02ae3b230a31411bef2877ecc23ef3` |
| `prototype/version.txt` | `0.3.19` |
| `pseudex/vault.py` | `048a4f1c941d9b474cdfda6d0bfde4087e5f3e69567636c4f5d2b57683931646` |
| `pseudex/redact.py` | `bf8e064b43301d1ea3ead6359f05e681dba6a88da199aa4b7b94a5ce23496311` |
| `pseudex/detect.py` | `5d51d926cc88c01accc98af4c098a878472a6bd5116115f41bb70ba778fabf7a` |
| `test_other_hop_forms.py` | `50d1a0470b3c8c252fd7011ceacdcec26e69cc21db27b0bdab3ccf8570ecb00b` |

Seams: literal `Span` objects into `mask_text` (no detector), real ephemeral
`Vault`, real dev bundle, `unmask_arguments` + `unmask_text`. Mints pinned at the
boundary (`_fake_snils`/`_fake_inn`/`_fake_card`; `secrets.choice`/`randbelow`
for the inlined EMAIL/PASSPORT/PLATE/DOB mints). No expectation computed by an
engine function. `test_phone_hop_form.py` now passes 35 checks in this worktree;
C01 covers the other seven types.

## Counts

```
checks by type: CARD 8, CONTROL 8, DOB 7, EMAIL 7, INN 8, PASSPORT 7, PLATE 9, SNILS 12
checks by kind: in-form 15, in-identity 13, out-tool 11, out-prose 10, part 9,
                negative 4, json 2, isolation 2
other_hop_forms: 47/66 contract checks passed
```

## Failures versus the contract (19)

**Boundary 1 — user → model: a mention's substitute must keep that mention's form.**
7 REDs, each `got` the *first* mention's form:

| type | second writing | want | got |
|---|---|---|---|
| SNILS | `11223344595` | `08538756919` | `085-387-569 19` |
| INN | `50 01 007322 59` | `00 12 345678 87` | `001234567887` |
| CARD | `4276-1600-1234-5675` | `0123-4567-8901-2347` | `0123 4567 8901 2347` |
| PASSPORT | `45 09 123456` | `00 02 345678` | `0002 345678` |
| DOB | `02.06.1975` | `11.07.1975` | `11 июля 1975` |
| EMAIL | `IVAN.PETROV@MAIL.RU` | `ABCDEFGH@EXAMPLE.RU` | `abcdefgh@example.ru` |
| PLATE | `A123BC777` | `M456TY789` | `М456ТУ789` |

Row count is already 1 (one canonical content) — the defect is form, not identity.
Three more IN reds: EMAIL upper-case mention is lower-cased; PLATE Latin mention
comes back Cyrillic; PLATE lower-case mention comes back upper Cyrillic.

**Boundary 4 — agent → human: the answer's mention owns the form.** 7 REDs; every
prose check returns the customer's first-written form instead of the agent's:

| type | agent wrote | want | got |
|---|---|---|---|
| SNILS | `08538756919` | `11223344595` | `112-233-445 95` |
| SNILS | `085 387 569 19` | `112 233 445 95` | `112-233-445 95` |
| INN | `0012 3456 7887` | `5001 0073 2259` | `500100732259` |
| CARD | `0123-4567-8901-2347` | `4276-1600-1234-5675` | `4276 1600 1234 5675` |
| PASSPORT | `0002345678` | `4509123456` | `4509 123456` |
| EMAIL | `ABCDEFGH@EXAMPLE.RU` | `IVAN.PETROV@MAIL.RU` | `ivan.petrov@mail.ru` |
| PLATE | `м456ту789` / `M456TY789` | `а123вс777` / `A123BC777` | `А123ВС777` |

**Boundary 2 — agent → tool.** Only one RED: PLATE Latin look-alikes return the
Cyrillic real value (`А123ВС777`) instead of the agent's Latin script
(`A123BC777`). SNILS/INN/CARD/PASSPORT/DOB/EMAIL tool form already passes.

Boundary 3 (tool result → model) is the same `mask_text` seam as boundary 1 and is
not separately exercised here.

## Passing under the contract (47)

IN form A for all 7 types; IN canonical content for 6 (DOB content is the
one-row check); OUT tool form for SNILS grouping/bare, INN grouping, CARD
dashes/bare, PASSPORT bare, DOB ISO/dotted, EMAIL upper, PLATE lower; OUT prose
for DOB ISO/dotted; selected parts (SNILS first group/last four, INN last four,
CARD last four, PASSPORT series); all 8 controls (quantities, prose numbers,
non-PII JSON and prose neighbours, escaped-JSON neighbour, re-parse, two
wrong-tenant isolations).

## Documented limitations (kept as refusals, not pattern support)

- SNILS two-digit control `19` and unnamed middle group `387` stay fake.
- INN two-digit prefix `00` stays fake.
- EMAIL local part without a domain (`abcdefgh`) stays fake.

These have no named role; the checks pin that they stay fake so a later change
cannot silently start resolving them.

## Open questions (neither pass nor fail)

1. **DOB, ambiguous date.** `05.06.2025` is read day-first by `_date_canonical`;
   no rule separates `dd.mm` from `mm.dd` when both are ≤ 12. C01 pins only the
   unambiguous notations and asserts no reading.
2. **PLATE, region width.** A 2-digit region can mint a 3-digit one; region width
   is not part of the §1 current-sender form contract and needs an explicit
   decision.
