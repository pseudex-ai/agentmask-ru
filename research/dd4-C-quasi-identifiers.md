# DD4-C — Quasi-Identifiers: Proven Frameworks for What/How to Detect

Research date: 2026-06-07. Scope: quasi-identifiers (indirect identifiers) only — DOB/age,
dates, geography, gender, diagnosis/medical. EXCLUDES phone/noise and structured/JSON (other agents).

Evidence grades: [A] primary regulation/standard or canonical shared-task paper · [B] official
tool docs / peer-reviewed paper · [C] reputable secondary (compliance vendor, summary) · [D] blog/opinion.

Our detector miss this addresses: free-text quasi-IDs like "1954 года рождения" (year of birth),
age, city, diagnosis — currently ignored.

---

## 1. HIPAA Safe Harbor — the canonical "what counts as an identifier" checklist

**Source of truth:** 45 CFR §164.514(b)(2)(i), enumerated (A)–(R) = 18 identifier classes.
The covered entity removes ALL 18 for the individual AND their relatives, employers, household members,
THEN (b)(2)(ii) must also have no "actual knowledge" the residual could re-identify. [A]

Primary: https://www.law.cornell.edu/cfr/text/45/164.514 (Cornell LII, verbatim eCFR) [A]
HHS narrative guidance: https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html [A]
(HHS page 403s to bots; content cross-confirmed via HIPAA Journal which quotes it [C].)

### The 18 identifiers (A)–(R), verbatim where load-bearing
- (A) Names
- **(B) All geographic subdivisions smaller than a State**, including street address, city, county,
  precinct, ZIP code, and their equivalent geocodes, **except for the initial three digits of the ZIP
  code if, according to current Census Bureau data: (1) the geographic unit formed by combining all
  ZIP codes with the same three initial digits contains more than 20,000 people; and (2) the initial
  three digits of a ZIP code for all such geographic units containing 20,000 or fewer people is changed
  to 000.** (HHS lists the 17 restricted 3-digit prefixes from 2000 census, e.g. 036, 692, 878...). [A]
- **(C) All elements of dates (except year) for dates that are directly related to an individual,
  including birth date, admission date, discharge date, death date; and all ages over 89 and all
  elements of dates (including year) indicative of such age, except that such ages and elements may be
  aggregated into a single category of "age 90 or older."** [A]
  → DIRECTLY covers our "1954 года рождения" miss. Rule: **year alone is OK; full DOB is NOT.**
    Age is fine up to 89; **age ≥90 (and any date implying it) must be bucketed to "90+".**
- (D) Telephone numbers · (E) Fax numbers · (F) Email addresses · (G) Social security numbers
- (H) Medical record numbers · (I) Health plan beneficiary numbers · (J) Account numbers
- (K) Certificate/license numbers · (L) Vehicle identifiers & serial numbers incl. license plates
- (M) Device identifiers & serial numbers · (N) Web URLs · (O) IP addresses
- (P) Biometric identifiers (incl. finger/voice prints) · (Q) Full-face photographic & comparable images
- (R) Any other unique identifying number, characteristic, or code (catch-all)

### Key interpretive takeaways for our gateway
- HIPAA treats **DOB, dates, geography <state, and age≥90 as IDENTIFIERS that must be removed/generalized**,
  not as benign quasi-IDs. This is the proven, regulator-blessed "what to detect" checklist. [A]
- Note: a standalone **diagnosis is NOT in the 18** — under Safe Harbor a diagnosis stays in the data
  (it's the payload being de-identified). Diagnosis becomes a *quasi-identifier / sensitive attribute*
  problem only in the **dataset** setting (re-id by rare condition), handled by Expert Determination /
  k-anon, not by the Safe Harbor list. [A] (Relevant: under RU 152-ФЗ / GDPR Art.9, health data is a
  *special category* and is sensitive regardless — see §3.)
- **Safe Harbor vs Expert Determination:** Safe Harbor = mechanical removal of the 18 (cheap, no stats).
  Expert Determination = a qualified statistician certifies "very small" re-id risk (covers quasi-ID
  combinations Safe Harbor can't, used for richer datasets). [A]

---

## 2. k-anonymity / l-diversity / DP — and WHEN to mask vs generalize

### Definitions (proven, peer-reviewed)
- **k-anonymity** (Sweeney 2002): each record indistinguishable from ≥ k−1 others on the *quasi-identifiers*;
  the indistinguishable group = an "equivalence class." Protects against **identity disclosure**. [A/B]
- **l-diversity** (Machanavajjhala): each equivalence class has ≥ l "well-represented" values for each
  sensitive attribute → protects **attribute disclosure** (e.g. all-same-diagnosis in a class). [B]
- **t-closeness**: sensitive-attribute distribution in each class within distance t (Earth Mover's
  Distance) of the global distribution. [B]
- **δ-presence**: bounds probability an individual is even *in* the dataset → **membership disclosure**. [B]
- **Differential privacy**: privacy is a property of the *processing method* (calibrated noise), not the
  dataset; protects all disclosure types for **aggregate queries**. [B]

ARX privacy-models doc: https://arx.deidentifier.org/overview/privacy-criteria/ [B]
ARX paper (Prasser et al., JBI): https://pmc.ncbi.nlm.nih.gov/articles/PMC4419984/ [B]

### The PROVEN tools (ranked by maturity for this exact job)
| Tool | What it is | Maturity | Notes |
|---|---|---|---|
| **ARX** (arx.deidentifier.org) | Java GUI+API; k-anon, k-map, l-div, t-close, δ-presence, DP, game-theoretic + risk analysis | A — biomedical standard | Operates on **tabular datasets**, not single messages. Generalization hierarchies + suppression. |
| **sdcMicro** (R, CRAN) | Stat. disclosure control: recoding, local suppression, microaggregation, risk est. | A — used by national statistics offices/UN/World Bank | k-anon via **recode-then-local-suppress**; suppression = replace value with NA. |
| **Google DP library** (C++/Java/Go) | Aggregate stats with DP noise | A | Explicitly for **aggregate statistics across users**, "protect users not records." NOT for single-record/free-text masking. |
| **Microsoft Presidio** | Free-text PII detect+anonymize (NLP+regex+context) | A for text | See §3. The right family for a *gateway*; k-anon tools are the wrong family. |

ARX classifies attributes 4 ways and treats each differently (this is the core mask-vs-generalize logic):
- **Identifying** (name, SSN) → **removed entirely** (= mask/redact).
- **Quasi-identifying** (gender, DOB, ZIP) → **transformed via generalization hierarchies / suppression**
  (e.g. DOB→year→decade; ZIP→3 digits→state) to reach k-anonymity.
- **Sensitive** (diagnosis) → **kept unmodified** but *constrained* via l-diversity/t-closeness.
- **Insensitive** → kept. [B]

### THE DECISION: mask a quasi-ID vs generalize/aggregate it
**Critical insight (load-bearing for our gateway):** k-anonymity/generalization is only definable over a
**dataset / set of records** — "indistinguishable from k−1 others" requires the other records to exist.
- **Dataset/table setting** → GENERALIZE/aggregate (ARX, sdcMicro): DOB→year/age-band, ZIP→region,
  age≥90→"90+". This preserves analytic utility while hitting a k threshold. [A/B]
- **Single free-text message (our case)** → there is NO equivalence class, so k-anon is *undefined*; you
  cannot "generalize to k." The proven remedy is **detect-and-mask/redact** (Presidio family) OR
  coarsen the value in place (DOB→keep year only; age≥90→"90+"), mirroring the *Safe Harbor mechanical
  rules* rather than a statistical k-anon computation. [A for the SH rules; B for Presidio]
- Bottom line: **HIPAA Safe Harbor is the right mental model for a streaming gateway** (mechanical per-message
  transforms); **k-anon/l-div/DP belong to the batch/dataset/analytics pipeline**, not the real-time path.

GDPR/health framing (context, [C]): quasi-IDs (DOB, gender, postal code, rare condition) re-identify in
combination; anonymization (irreversible) vs pseudonymization (reversible, still personal data). IAPP
WP / Censinet summaries. Use to justify masking sensitive health terms even though diagnosis isn't a
HIPAA-18 item.

---

## 3. Detecting quasi-identifiers IN TEXT (DOB / age / dates / medical)

### Dates / DOB / age — proven detection
- **Regex + context** is the proven, lightweight workhorse. Canonical evidence: the **2014 i2b2/UTHealth
  de-identification shared task** (the reference benchmark for clinical PHI in free text). [A]
  Overview: https://pmc.ncbi.nlm.nih.gov/articles/PMC4989908/ [A]
  - Best system (U. Nottingham) micro-F1 **0.9360** on i2b2-PHI; **best systems = hybrid CRF + hand-written
    rules.** A fully rule-based system (San Marcos) handled DATE/AGE/ID by tokenizing and classifying
    digit vs non-digit tokens with lexical clues — i.e. **DATE and AGE are among the easiest, most
    regex-friendly categories** (PROFESSION and LOCATION were the hardest). [A]
  - i2b2 deliberately went **beyond HIPAA Safe Harbor** (it redacts full dates incl. year, professions,
    room/department) because longitudinal records can re-identify even when each is "HIPAA-compliant." [A]
- **Microsoft Presidio**: ships a default **`DATE_TIME`** entity ("Absolute or relative dates or periods or
  times smaller than a day") via pattern+context. **No generic `AGE` entity by default** (Azure Text
  Analytics integration exposes an Age entity; otherwise add a custom recognizer). [B]
  Docs: https://github.com/microsoft/presidio/blob/main/docs/supported_entities.md [B]
  → For "1954 года рождения" / "age 71" we need a small **custom recognizer**: regex for 4-digit years in
    birth context (года рождения, г.р., род., DOB, born) + age patterns (\d{1,3}\s*(лет|года|год|y/?o)) with
    context boosting. Cheap, deterministic, high precision.

### Medical / diagnosis detection (special category under 152-ФЗ)
- 152-ФЗ treats health data as a **special category** (специальная категория ПДн) — stricter than ordinary
  PII (parallels GDPR Art.9). So detecting & masking medical terms is justified independent of the HIPAA-18. [C]
- **Presidio medical NER**: optional `MedicalNERRecognizer` (needs `transformers` extra; default model
  `blaze999/Medical-NER`) → emits `MEDICAL_DISEASE_DISORDER`, `MEDICAL_MEDICATION`,
  `MEDICAL_THERAPEUTIC_PROCEDURE`, `MEDICAL_CLINICAL_EVENT`, etc. **English-oriented**; not loaded by
  default. Also a default `MEDICAL_LICENSE` entity (a number, not a diagnosis). [B]
- **Russian medical NER (proven, HF-available):**
  - **RuDReC** corpus + models **RuDR-BERT / EnRuDR-BERT / EnDR-BERT** (cimm-kzn). Entities: drug name,
    drug class/form, **drug indication / disease symptom**, ADR, "finding." RuDR-BERT NER macro-F1 ≈ **74.85%**.
    Models on HF: https://huggingface.co/cimm-kzn ; repo https://github.com/cimm-kzn/RuDReC [B]
    Caveat: trained on consumer drug reviews, disease/symptom is a *secondary* label — domain-shifted for
    clinical text; license unspecified in README (verify before use).
  - **RuMedBench / RuMedNER** (Sberbank-AILab) — Russian medical language-understanding benchmark incl. NER;
    **RuBioBERT / RuBioRoBERTa** are SOTA Russian biomedical encoders. arXiv:2201.06499; repo
    https://github.com/sb-ai-lab/MedBench ; RuBioRoBERTa arXiv:2204.03951. [B]
  - **RuCCoD** (arXiv:2502.21263) — first Russian EHR dataset with disease entities **linked to ICD-10**;
    **RuMedTop3** predicts top-3 ICD-10 from symptoms. Basis for an ICD-term gazetteer. [B]
- **Gazetteer fallback (proven, lightweight):** ICD-10 term/code lists (incl. Russian МКБ-10) as a
  dictionary matcher. Cheapest path to catch named diagnoses without a model; ICD code regex (e.g. `[A-Z]\d{2}(\.\d)?`)
  for explicit codes. [C]

---

## 4. PROVEN recommendation for a real-time PII gateway (single message, not a dataset)

**Frame:** the gateway is a per-message transform → use the **Safe-Harbor-style mechanical rules + Presidio-style
detect-and-mask**, NOT k-anon/ARX/DP (those need a dataset and belong in batch analytics). [A/B]

### Detect + mask (high value, low cost, do these)
1. **Year of birth / DOB** — custom regex + birth-context (года рождения, г.р., род., DOB, born) →
   mask, OR coarsen to year only per Safe Harbor (C). Directly fixes the "1954 года рождения" miss. [A]
2. **Age** — regex `\d{1,3}\s*(лет|год[а]?|y/?o|years? old)`; **bucket age ≥ 90 → "90+"** (Safe Harbor C). [A]
3. **Explicit dates** — Presidio `DATE_TIME` / date regex; mask full dates, optionally keep year. [A/B]
4. **Medical / diagnosis (special category under 152-ФЗ)** — tiered:
   - Tier 1 (cheap, ship first): **МКБ-10/ICD-10 gazetteer + ICD code regex.** [C]
   - Tier 2 (if budget): **RuBioRoBERTa/RuDR-BERT NER** for disease/symptom spans (heavier, GPU/latency cost). [B]

### Impractical / low ROI for a single-message gateway (don't over-invest)
- **City/region/gender alone** → weak single-message signal, high false-positive/over-redaction risk; their
  power is *combinatorial* (k-anon territory) which is undefined for one message. Detect city only when it
  co-occurs with other quasi-IDs, or skip. [A reasoning from k-anon being dataset-bound]
- **Catch-all (R) "any unique characteristic"** → not mechanizable in real time; accept residual risk.
- **k-anonymity / l-diversity / DP generalization** → architecturally wrong for streaming single messages
  (no equivalence class). Reserve for any batch/dataset export path. [A/B]

### Lightweight architecture
- **Regex + context recognizers** for DOB/age/dates (deterministic, microsecond-scale, the i2b2-proven
  approach for these easy categories). [A]
- **Gazetteer/dictionary** (ICD/МКБ-10) for diagnoses as the default medical layer. [C]
- **Optional model layer** (Presidio custom recognizer wrapping a RU biomedical NER) gated behind a
  latency/cost budget for higher diagnosis recall. [B]
- Action = **mask/redact or coarsen-in-place** (DOB→year, age≥90→"90+") — mirror Safe Harbor, don't try to
  compute k. [A]

---

## Open questions / caveats
- RuDReC/RuDR-BERT license is unspecified in README — verify before production use. [B]
- RU medical NER models are domain-shifted (drug reviews / EHR) — expect recall drop on chat-style text;
  benchmark on real gateway traffic before trusting. [B]
- "Year only is OK" is a HIPAA stance; under 152-ФЗ/GDPR even a year + other quasi-IDs may re-identify —
  if the threat model is strict, mask year of birth entirely rather than keep it. [A regulation / C interpretation]

## Primary citations
- 45 CFR §164.514 — https://www.law.cornell.edu/cfr/text/45/164.514 [A]
- HHS De-identification Guidance — https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html [A]
- ARX privacy models — https://arx.deidentifier.org/overview/privacy-criteria/ [B]
- ARX paper — https://pmc.ncbi.nlm.nih.gov/articles/PMC4419984/ [B]
- sdcMicro localSuppression — https://rdrr.io/cran/sdcMicro/man/localSuppression.html [B]
- Google DP library — https://github.com/google/differential-privacy [B]
- Presidio supported entities — https://github.com/microsoft/presidio/blob/main/docs/supported_entities.md [B]
- 2014 i2b2/UTHealth de-id overview — https://pmc.ncbi.nlm.nih.gov/articles/PMC4989908/ [A]
- RuDReC repo / models — https://github.com/cimm-kzn/RuDReC · https://huggingface.co/cimm-kzn [B]
- RuMedBench — arXiv:2201.06499 · https://github.com/sb-ai-lab/MedBench [B]
- RuBioRoBERTa — arXiv:2204.03951 [B]
- RuCCoD (ICD-10 RU) — arXiv:2502.21263 [B]
