# DD3 — Distinguishing ADDRESS-as-PII from PLACE-REFERENCE (non-PII)

**Date:** 2026-06-07 · **Method:** web research → primary sources (federal regs, papers, repos).
**Problem:** PII gateway masks ALL locations; over-masks non-PII place references
("часы работы магазина в Москве", weather, store branch, currency). Locations precision ~67%.
**Goal:** most LACONIC reliable rule to keep a real address ("доставьте на ул. Ленина 5")
masked while leaving a bare toponym / landmark unmasked.

**Evidence grades:** **[A]** verbatim from primary source (statute/paper/code) ·
**[B]** official docs / single primary · **[C]** asserted by a primary/secondary ·
**[D]** my inference.

Companion notes in repo: `dd2-notes-C-disambiguation.md`, `deep-dive-detection-upgrade.md`,
`legal-152fz-developer-liability.md`. Prototype: `prototype/obscura/ru_pii.py`.

---

## 1. Established granularity rules / precedent (the cleanest lever)

### 1.1 HIPAA Safe Harbor — the exact geographic rule [A]
45 CFR §164.514(b)(2)(i)(B). Verbatim (confirmed across 3 sources: eCFR API, Bricker mirror,
HHS de-id guidance):

> "All geographic subdivisions smaller than a State, including street address, city, county,
> precinct, zip code, and their equivalent geocodes, except for the initial three digits of a
> zip code if, according to the current publicly available data from the Bureau of the Census:
> (1) The geographic unit formed by combining all zip codes with the same three initial digits
> contains more than 20,000 people; and (2) The initial three digits of a zip code for all such
> geographic units containing 20,000 or fewer people is changed to 000."

KEY TAKEAWAYS for us:
- **STATE is NOT an identifier.** The rule removes everything *smaller than a state*. A bare
  state-level region is allowed to remain. [A]
- **Street / city / county / precinct / ZIP ARE identifiers** and must be removed. So HIPAA puts
  the cut line at *city and below = PII; state and above = OK*. [A]
- **3-digit ZIP exception** = a coarse-grained geo (≥20k pop) is acceptable; fine-grained is not.
  This is the precedent for "coarse toponym OK, precise locator not OK." [A]
- CAVEAT for us: HIPAA is **categorical, not contextual** — under Safe Harbor a *city* is always
  a removable identifier *inside a medical record about an identified patient*. The whole record
  is already about a person. So HIPAA's "city = PHI" assumes the person-link already exists. Our
  problem is the opposite: in a chatbot, "магазин в Москве" has NO person-link. HIPAA gives us
  the **granularity ladder**, not a license to mask every city. [A statute / D our application]

Sources:
- https://www.ecfr.gov/current/title-45/section-164.514 (authoritative; via API renderer) [A]
- https://www.bricker.com/insights/resources/key/HIPAA-Privacy-Regulations-...-164-514-b [A]
- https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html [B]
- https://www.hipaajournal.com/de-identification-protected-health-information/ [C]

### 1.2 GDPR — location is PII only when linked to an identifiable person [A/B]
Recital 26 sets the identifiability test: take account of "all the means reasonably likely to be
used, such as singling out, either by the controller or by another person to identify the natural
person directly or indirectly," weighing cost/time/available technology. [A]

Engineering reading that matches our case exactly: a record `<426, "New York">` is **not** personal
data because you cannot trace it to a natural person; but `<userID, cityName>` becomes personal as
soon as *some* record links userID to a person. So **the same city string is PII or not depending
on the person-link**, not on the city itself. This is the legal backbone of a contextual rule. [B]

- https://gdpr-info.eu/recitals/no-26/ [A] · https://www.privacy-regulation.eu/en/recital-26-GDPR.htm [A]
- https://medium.com/@marton.waszlavik/gdpr-for-engineers-what-is-personal-data-ce2b62d856c3 [C]
  (the `<userID, city>` framing)
- Oxford IDPL, "They who must not be identified": https://academic.oup.com/idpl/article/10/1/11/5802594 [B]

### 1.3 Russian 152-ФЗ — same "identifiability" stance [B/C]
152-ФЗ Art. 3: ПДн = "любая информация, относящаяся к прямо или косвенно определённому или
определяемому физическому лицу." Address of registration/residence (адрес регистрации /
проживания) is explicitly an example of ПДн **when it relates to a subject**. Commentary
consistently states individual depersonalized fragments are not ПДн alone; it's the *aggregate /
link to a person* that makes them ПДн. Same principle as GDPR: bare city alone ≈ low identifying
value; address tied to a named/addressed person = ПДн. [B/C]
- https://www.consultant.ru/document/cons_doc_LAW_61801/ [B] (statute text)
- See repo `legal-152fz-developer-liability.md` for the operator-vs-developer liability angle.

### 1.4 i2b2/UTHealth 2014 — the clinical de-id precedent that splits address by part [A]
The 2014 i2b2/UTHealth de-id corpus (the de-facto clinical de-id benchmark) annotates LOCATION
with **per-component subcategories**: Room, Department, Hospital, Organization, **Street, City,
State, Country, ZIP**, Other. Annotation guideline, verbatim:

> "Each part of an address will get its own tag. For example: 32 Vassar Street — Street;
> Cambridge — City; MA — State; 02142 — ZIP; USA — Country." [A]

This is direct precedent that **granularity is the natural axis** — production de-id systems do
NOT treat "location" as one blob; they tag street/house separately from city/state. (Note: i2b2
is *stricter* than HIPAA — it tags state/country too — because every note is already about a
patient, i.e. the person-link is given. Same caveat as §1.1.) [A]
- https://pmc.ncbi.nlm.nih.gov/articles/PMC4978170/ [A] (annotation paper)
- 2014 i2b2 Track 1 overview: https://pmc.ncbi.nlm.nih.gov/articles/PMC4989908/ [B]

**Precedent verdict:** There IS an established granularity ladder
(street/house/ZIP = identifier; state/region = not), and an established *identifiability*
principle (location is PII only when linked to a person). Neither alone solves our chatbot case;
**combined** (granularity + person-link/intent) they do. That combination = our laconic rule (§4).

---

## 2. NLP approaches to the PERSON↔LOCATION association (lightweight → heavy)

Ranked by reliability-per-weight for our gateway hot path.

### 2.1 Address-granularity heuristic (LIGHTEST, most reliable single signal) [A/D]
Signal: does the span contain a **street + house number** (or ZIP / apartment / "д./дом/кв./стр.")
vs a **bare toponym** (just a city/region word)?
- Backed by HIPAA (§1.1) and i2b2 (§1.4): street+house is categorically the identifier; bare
  city is the borderline case.
- Implementation: cheap. RU street markers `ул\.|улица|просп|пр-?кт|пер\.|переулок|ш\.|шоссе|
  наб\.|бул|пл\.|проезд` + a house-number token (`д\.?\s*\d+|\bдом\s+\d+|,\s*\d+[а-я]?\b`) +
  unit markers `кв\.|кв\b|корп|стр\.|пом`. If street-marker AND number → ADDRESS (mask).
- For canonical parsing use **libpostal** (openvenues/libpostal): statistical NLP street parser,
  multilingual incl. RU, returns components `house_number, road, city, state, postcode...`.
  Heavier (C lib + ~2GB model) but is the reference parser. Lightweight alt: a regex/gazetteer
  pass; or `Natasha/yargy` AddrExtractor for RU (see `dd2-notes-B-ru-address.md`). [B]
- **Reliability:** very high for the positive case (street+house ≈ always an address). Misses the
  "bare city as someone's address" case → needs the trigger signal (§2.2). [D]
- Repos: https://github.com/openvenues/libpostal [B] · Deepparse https://arxiv.org/pdf/2311.11846 [C]

### 2.2 Address-INTENT trigger words (dependency-light, cheap) [C/D]
Signal: is an *address-intent* cue near the location?
- ADDRESS-intent triggers (RU): `доставь*, доставка, привез*, приедет, отправь* на, адрес,
  по адресу, прописан, зарегистрирован, проживает, живёт, живу, переезжаю на, забери* по`.
- REFERENCE/non-PII triggers: `часы работы, режим работы, график, где находится, как добраться,
  погода, курс (валют), магазин/филиал/отделение в, есть ли … в, работает ли … в`.
- Implementation: a char/token window around the location span (Presidio uses prefix=5 tokens by
  default; suffix context is OFF by default — see `dd2-notes-C`). A **deny/down-weight on
  reference triggers** + **boost on address triggers**. Presidio ships boost-only (no deny path)
  so the deny must be BUILT (≈30 lines). [A from dd2-notes-C / C]
- **Reliability:** good as a tie-breaker for bare toponyms; brittle as the sole signal (triggers
  can be far from the span, negation, multi-intent). Best COMBINED with §2.1. [D]

### 2.3 First/second-person possessive cues [C/D]
Signal: `мой адрес, мне на …, доставьте мне, я живу/прописан/зарегистрирован, наш офис`.
First/second-person + a locator strongly implies the speaker's own address → PII. Third-person
generic ("магазин работает в Москве") implies a reference. Cheap regex; high precision on the
positive ("мой адрес — …") but low recall (many real addresses have no possessive). Use as a
**high-confidence booster**, not a gate. [D]

### 2.4 Dependency-parse / relation triggers (mid weight) [C]
Signal: syntactic path location→governing verb. Verb-in-dependency-path is a classic RE feature
(subject-verb-object triples; trigger lists + geo gazetteers). E.g. `доставить —(obl)→ [LOC]`
with prep `на/по` → address; `работать/находиться —(obl)→ [LOC]` with `в` → reference.
- spaCy `ru_core_news_*` already gives the parse (you likely run it for NER anyway → near-zero
  marginal cost). Extract: head verb lemma + the preposition governing the LOC.
- **Reliability:** better than bag-of-triggers (respects attachment, handles distance), but RU
  parser errors on messy field text reduce gains. A pragmatic middle. [C]
- Refs: dependency-path RE features — TAMU L17 slides, Devopedia "Relation Extraction". [C]

### 2.5 Zero-shot relation extraction — GLiREL (heaviest of the "lightweight" options) [A/B]
`jackboyla/GLiREL` (Boylan, Hokamp, Ghalandari — NAACL 2025). Predicts relation labels between
*multiple entity pairs in a single forward pass*; SOTA zero-shot on FewRel & Wiki-ZSL. You pass
tokens + NER spans + candidate labels (`["resides at","delivery address","located in"]`) and get
scored relations. [A abstract]
- Pros: no training; directly answers "is this LOC the person's address?" as a relation between a
  PERSON/1st-person span and the LOC.
- Cons for us: **license CC-BY-NC-SA-4.0 (non-commercial)** — likely a blocker; **English-centric**
  (no documented RU support); needs an entity layer first; large-v0 is a transformer (heavier than
  regex). Keep as a research baseline, not hot-path. [B]
- Repo: https://github.com/jackboyla/GLiREL · paper https://arxiv.org/abs/2501.03172 [A]

### 2.6 Context-aware SLM — CAPID (the "do it properly" option) [A]
CAPID (arXiv 2602.10074, 2026) is the closest published framing to our exact problem: existing
systems "mask all PII indiscriminately, degrading response quality"; CAPID adds a **binary
relevance label per span — retain vs mask** and explicitly handles **the same entity (a location)
being PII in one context and not another** ("critical for an immigration question but irrelevant
for fatigue management"). Method: fine-tuned **small** LM (Llama-3.2-3B / 3.1-8B + LoRA) on 2,107
synthetic spans. Results: span F1 0.96 (vs 0.48 untrained), **relevance accuracy 0.93** (vs 0.51),
beats GPT-4.1-mini on Reddit (0.80 vs 0.69), preserves 22–28% more downstream utility vs full
masking. **Code + model open-sourced.** [A]
- What to steal: the **task framing** (span + type + binary retain/mask relevance) and the
  synthetic-data recipe; possibly the labeling schema for an offline labeller. The 3B model is
  heavier than our rule budget but is the credible upgrade path if rules plateau.
- https://arxiv.org/html/2602.10074v1 [A] · pdf https://arxiv.org/pdf/2602.10074 [A]

---

## 3. GitHub repos / papers — what to steal · weight · grade

| Source | What it gives | What to steal | Weight | Grade |
|---|---|---|---|---|
| **45 CFR §164.514(b)(2)(i)(B)** (eCFR) | Statutory granularity ladder: street/city/ZIP=ID, state=OK; 3-digit-ZIP coarse exception | The cut line "city-and-below vs state-and-above" + coarse-geo exception | none (a rule) | **[A]** |
| **i2b2/UTHealth 2014** (PMC4978170) | Per-part LOCATION tags (Street/City/State/ZIP); "each part its own tag" | Granularity schema; eval categories for our own labels | none | **[A]** |
| **GDPR Recital 26** + Oxford IDPL | Identifiability test; `<userID,city>` framing | "location is PII only via person-link" → the contextual half of the rule | none | **[A]/[B]** |
| **microsoft/presidio** | Recognizers, LemmaContextAwareEnhancer (boost-only, prefix=5, suffix=0) | Context-window mechanism; integrate our deny+trigger as custom recognizer | light (already in stack) | **[A]** (see dd2-notes-C) |
| **Presidio GLiNER sample** | How to bolt an external span model in | Integration pattern only (GLiNER RU F1 is poor — dd2-notes-A) | medium | **[B]** |
| **openvenues/libpostal** | Statistical multilingual address parser → components | `house_number`+`road` presence = address signal | heavy (C lib ~2GB) | **[B]** |
| **Natasha/yargy AddrExtractor** (RU) | RU rule-based address spans | RU street/house grammar for the granularity test | light | **[B]** (dd2-notes-B) |
| **jackboyla/GLiREL** (NAACL'25) | Zero-shot RE person↔location | Relation framing; label set | heavy + **NC license** | **[A]** |
| **CAPID** (arXiv 2602.10074, 2026) | Context-aware retain-vs-mask SLM; same-entity-different-context | Task framing + synthetic data recipe; upgrade path | heavy (3B SLM) | **[A]** |

---

## 4. The most LACONIC viable solution

There is **nothing cleaner/more established than granularity + person-link**; that *is* the
precedent (HIPAA granularity ladder × GDPR/152-ФЗ identifiability). Encode it as a 3-clause rule
applied to each LOCATION span the NER/regex layer emits:

```
For each LOCATION span:
  1. ADDRESS (street-marker + house-number / ZIP / apt-marker present)
        → ALWAYS MASK.                                    # HIPAA+i2b2: street/house = identifier
  2. BARE TOPONYM (city / region / country, no house-level detail):
        a. address-intent trigger in window               # доставка|адрес|прописан|живёт|по адресу
           OR 1st/2nd-person possessive (мой адрес|мне на|я живу)
              → MASK.                                      # person-link present → PII
        b. reference trigger in window                     # часы работы|погода|где находится|магазин в|курс
              → DO NOT MASK.                               # explicit non-PII reference
        c. neither trigger:
              → DO NOT MASK by default (treat bare city as non-PII),
                 unless gateway is in HIGH-SAFETY mode → MASK.   # tunable fail-safe
  3. STATE / COUNTRY / large region alone → DO NOT MASK.   # HIPAA: state-and-above not an identifier
```

Window = Presidio-style ±N tokens (start prefix=5; ADD suffix, off by default in Presidio — see
dd2-notes-C). Triggers = two small RU gazetteers (address-intent vs reference). House/street test
= regex or Natasha AddrExtractor. ~30–60 lines, zero new heavy deps; reuses the spaCy parse you
already run if you want §2.4 attachment instead of bag-of-words triggers.

**Why this and not a model:** matches established law (defensible), is deterministic/auditable
(important under 152-ФЗ liability — see legal note), and the literature (CAPID) confirms even the
*model* approach is solving exactly this retain-vs-mask split — so the rule is the right shape,
just cheaper. Escalate to a CAPID-style 3B SLM only if the rule plateaus.

### False-positive / false-negative risks
- **FN (under-mask, the privacy-dangerous one):** a real address written as a bare city with no
  trigger — "я в Казани" meaning the user's whereabouts; or trigger sits outside the window
  (long sentence, clause boundary). Mitigation: clause/sentence-level window not fixed token
  count; default-mask in HIGH-SAFETY mode; possessive/1st-person cue as an extra catch. [D]
- **FP (over-mask, our current pain):** address-intent trigger near a *reference* location
  ("узнай адрес магазина в Москве" — "адрес" is a trigger but the location is a store, not the
  user). Mitigation: when BOTH an address-trigger and a reference-trigger (магазин/филиал/
  отделение/где находится) are present, reference wins; require the location to attach to a
  1st/2nd-person subject for the address branch (§2.3/2.4). [D]
- **Granularity edge:** house number that's actually an order/track/sum number adjacent to a city
  → reuse the numeric-disambiguation deny layer from `dd2-notes-C` (track=14 digits never PII). [D]
- **Toponym-as-name / org:** "Москва" in a brand/org ("Динамо Москва") — the org-vs-place split
  is a separate FP class; lean on NER label (GPE vs ORG) before applying this rule. [D]

### Quick wins (ship first, cheapest)
1. Stop masking STATE/COUNTRY/region-only spans → immediate precision gain, zero FN risk per
   HIPAA (§1.1, §3). [A-backed]
2. Add reference-trigger deny list (часы работы|погода|где находится|магазин/филиал/отделение в|
   курс) → kills the headline FP cases ("часы работы магазина в Москве"). [C]
3. Keep ALWAYS-MASK on street+house → preserves recall on real addresses. [A-backed]

---

## Open questions
- Optimal window: fixed ±N tokens vs sentence/clause boundary? (FN risk lives here.) [D]
- Does our NER reliably emit GPE vs LOC vs ORG for RU? (org-place FP depends on it — dd2-notes-A.) 
- HIGH-SAFETY default-mask for trigger-less bare cities: product/legal call (152-ФЗ posture).
- Worth wiring §2.4 dependency attachment, or do flat triggers suffice at our precision target?
- CAPID model RU performance unknown (English/Reddit eval); would need RU fine-tune to adopt.
