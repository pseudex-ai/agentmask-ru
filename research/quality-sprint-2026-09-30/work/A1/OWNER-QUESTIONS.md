# A1 → owner: новые решения O-DATA

Статус: `OWNER_PENDING`. Целевые показатели качества (≥99% на выборке + support/ДИ, ≥300 независимых позитивных единиц) **уже решены** и здесь не переспрашиваются. Ниже — только то, что действительно не выбрано и без чего нельзя объявить G7.

Каждый вопрос: эпизод → что известно/неизвестно → применимый принцип → варианты → цена → предлагаемое доказательство. Числа взяты из `INVENTORY.json` / `DATA-GAPS.csv` (реальные подсчёты, не оценки).

## Q-A1-1 — unit of independence

**Вопрос.** Accept (type, identity) as the independence cluster, with one primary occurrence per identity in the acceptance sample? Or require each identity to contribute exactly one occurrence, discarding the rest?

**Предложение A1.** (type, identity) cluster + one primary occurrence sampled per identity

**Цена/последствие.** the first option keeps more data; the second loses the multi-form evidence (declined, Latin, possessive) that the defect classes live in

## Q-A1-2 — source of support

**Вопрос.** May authored synthetic corpora carry the ≥300/type support, or must NAME/LOC headline support come from third-party human text?

**Предложение A1.** authored corpora carry the product-scope headline; external corpora stay a separate strict axis

**Цена/последствие.** third-party-only support is not reachable for PASSPORT/SNILS/INN/CARD/PLATE on any corpus on this host

## Q-A1-3 — underpowered native types

**Вопрос.** For PASSPORT 63 / SNILS 128 / INN 144 / CARD 123 / PLATE 154 independent identities in the frozen 1800-case corpus: expand the corpus toward 300/type, or accept descriptive status for them now?

**Предложение A1.** expand generation for the five underpowered types; keep them in the table as DESCRIPTIVE until then

**Цена/последствие.** expansion multiplies annotation items; descriptive status delays a 99% claim for those five types

## Q-A1-4 — v6 per-type support

**Вопрос.** The planned 500-case v6 corpus projects to ≈25–34 independent units per new type — an order of magnitude below 300. Claim v6 per type, or per family, or expand the corpus to ≈4,400–6,100 cases?

**Предложение A1.** headline per family with ≥300 independent units; per-type claims only where the corpus supports them

**Цена/последствие.** per-type 99% for 55 types requires a corpus several times larger

## Q-A1-5 — public/fictional stratum

**Вопрос.** Are public-figure, fictional and stage-name occurrences inside the 99% headline denominator or a separately published stratum?

**Предложение A1.** protected and counted, but published as a separate stratum (the gate instrument already reports 'public' separately, 57 of 587 labels)

**Цена/последствие.** inside the headline, one hard public-name case can move the number; outside it, a real protection class becomes invisible

## Q-A1-6 — blind split custody

**Вопрос.** Who generates and holds the fresh blind acceptance split, and may an agent generate it under a sealed procedure without reading labels?

**Предложение A1.** human owner custody; agent may generate the text, never the labels

**Цена/последствие.** requires owner time at freeze; without it there is no blind acceptance

## Q-A1-7 — annotation budget

**Вопрос.** Authorize ≈9,000–17,000 human review items, and the split between paid/owner labeling?

**Предложение A1.** approve native+PPV+specificity first (≈9,000 items), v6 later

**Цена/последствие.** the full number is the price of a genuine ≥300/type, blind PPV claim

## Q-A1-8 — holdout tier status

**Вопрос.** May the pinned 359-ID tier serve as the secondary blind tier given its membership is known, or must acceptance use only a new split?

**Предложение A1.** secondary tier with the 0/359 caveat printed; primary is a new split

**Цена/последствие.** using it alone would repeat the historical access ambiguity

## Q-A1-9 — temporary-secret support

**Вопрос.** Does synthetic CVC/OTP/3DS material count as independent support for their ≥300 target, and who defines the operation contexts?

**Предложение A1.** synthetic-only support, with an explicit 'synthetic' column kept separate from product-text support

**Цена/последствие.** no real payment data may be used, so synthetic is the only available source; the owner must accept the different evidentiary weight

## Q-A1-10 — address component boundary

**Вопрос.** Are entrance/floor a required protected unit when written, or only when attached to a house number?

**Предложение A1.** required when they belong to a personal address occurrence; a bare 'подъезд 3' with no address is ADDRESS_COMPONENT_ONLY and stays a negative

**Цена/последствие.** the stricter reading over-masks building-service text

## Что A1 НЕ спрашивает (уже решено владельцем)

- порог ≥99% по point estimate + публикация CI (`OWNER-DECISIONS.md#L19`);
- support ≥300 независимых позитивных единиц (`REMAINING-DECISIONS.md#L34`);
- два независимых разметчика без detector output (`REMAINING-DECISIONS.md#L33`);
- лексическая неоднозначность «жене» без свидетельств имени не маскируется и не считается автоматическим FP (`REMAINING-DECISIONS.md#L8`);
- притяжательные/публичные/вымышленные имена защищаются (`#L7`,`#L9`);
- CVC/OTP/SMS/3DS входят в quality denominator, lifecycle отложен (`#L21-L25`).
