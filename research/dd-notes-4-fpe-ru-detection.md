# DD-4 — Buildable primitives: FPE tokenization + Russian PII detection + edge-case literature

Research date: 2026-06-07. Scope: (A) format-preserving tokenization/encryption, (B) Russian PII detection engines, (C) entity-consistency / re-identification / de-id-eval literature.

Evidence grades: **[A]** primary spec/standard/source code; **[B]** peer-reviewed paper / official docs; **[C]** vendor docs / reputable secondary; **[D]** blog / unverified.

Out of scope (other agents): Skyflow, Presidio operator internals, LangChain/LiteLLM/MCP proxies.

---

## A. FORMAT-PRESERVING ENCRYPTION (FPE)

### A.1 The headline finding — the standard moved out from under FF3-1

- **NIST SP 800-38G (2016, updated 2019-02-28)** specified two FPE modes: **FF1** and **FF3**. Both are AES-based Feistel constructions. Original domain requirement: radix^minlen ≥ **100** (recommended ≥ 1,000,000). [A] https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-38g.pdf , https://csrc.nist.gov/pubs/sp/800/38/g/upd1/final
- **SP 800-38G Rev. 1 — 1st Public Draft (2019-02)**: in response to Durak–Vaudenay, FF3 was revised to **FF3-1** (tweak reduced 64→**56 bits**, i.e. a 7-byte tweak). Minimum domain size for **both FF1 and FF3-1 raised to 1,000,000** (radix^minlen ≥ 1e6). [A] https://csrc.nist.gov/pubs/sp/800/38/g/r1/ipd
- **SP 800-38G Rev. 1 — 2nd Public Draft (2025-02-03)**: **FF3 / FF3-1 REMOVED entirely.** Only **FF1 remains approved.** Stated cause: Beyne's linear-cryptanalysis weakness in the tweak schedule that affects FF3/FF3-1 but **not** FF1. Comment period closed 2025-04-04. Other 2PD changes: FF1 domain size increased; inverse-AES prohibited; floating-point arithmetic disallowed in FF1 impls. [A] https://csrc.nist.gov/pubs/sp/800/38/g/r1/2pd

> **Bottom line for build:** As of June 2026, **FF1 is the only NIST-approved FPE mode.** Any new design built on FF3-1 is building on a mode NIST has formally moved to withdraw. This is decisive for the recommendation.

### A.2 The cryptanalysis chain (why FF3 died)

- **Durak & Vaudenay, "Breaking the FF3…" (CRYPTO 2017)** — first practical attack. Exploits bad domain separation; chosen-plaintext + chosen-tweak on small domains. ~O(N^5). [B] https://infoscience.epfl.ch/server/api/core/bitstreams/91d9aa22-93f6-4c76-af16-a9fabb591b01/content ; NIST acknowledgment: https://csrc.nist.gov/news/2017/recent-cryptanalysis-of-ff3
- **Hoang, Miller, Trieu, "Attacks Only Get Better…" (2019)** — improved to O(N^{17/6}) on Z_N × Z_N. [B] https://eprint.iacr.org/2019/244
- **Amon, Dunkelman, Keller, Ronen, Shamir, "Three Third-Generation Attacks on FF3" (EUROCRYPT 2021)** — further practical attacks. [B] https://eprint.iacr.org/2021/335
- **Beyne, "Linear Cryptanalysis of FF3-1 and FEA" (CRYPTO 2021)** — THE one that killed FF3-1. Attacks the *revised* FF3-1 (not just FF3). Data complexity O(N^{r/2 − 1.5}) where domain = N², r = rounds. Concrete: FF3-1 with **N = 10³ distinguished with ~2²³ queries**; left-half message recovery ~2²⁴. Does **not** apply to FF1. [B] https://eprint.iacr.org/2021/815 , slides https://iacr.org/submit/files/slides/2021/crypto/crypto2021/83/slides.pdf

> Practical read: these attacks need many chosen plaintexts under a fixed key and *bite hardest on small domains* (short fields — exactly the SNILS/phone/passport case). A phone number tokenizer is squarely in the danger zone for small-domain FPE.

### A.3 The FF1 patent caveat (real, but bounded)

- **US Patent 7,864,952 (Voltage Security; now Micro Focus / OpenText)** covers the FFX→FF1 construction. Priority **2006-06-28**, filed **2006-12-06**, **adjusted expiration 2029-02-20**. [A] https://patents.google.com/patent/US7864952
- Voltage filed a **Letter of Assurance** with NIST: licenses available on application at a "reasonable" fee (RAND, not royalty-free). [A] https://csrc.nist.gov/CSRC/media/Projects/Block-Cipher-Techniques/documents/BCM/proposed-modes/ffx/ffx-voltage-ip.pdf
- This is exactly why **HashiCorp Vault implements FF3-1, not FF1** and why **mysto/python-fpe explicitly excludes FF1 from scope.** [C] https://github.com/hashicorp/vault/issues/5894 , https://github.com/mysto/python-fpe

> So we sit in a vise: **FF1 = approved but patent-encumbered until 2029-02; FF3-1 = patent-clear but withdrawn/broken.** This tension must surface in the design decision.

### A.4 OSS FPE libraries (Python / Go) — survey

| Library | Modes | Lang | License | Last release | Maturity / gotchas |
|---|---|---|---|---|---|
| **mysto/python-fpe (`ff3`)** | FF3, FF3-1 | Python ≥3.9 | Apache-2.0 | v1.0.2, 2024-03-13 | Most maintained Python FPE. **Now ships a banner: "NIST's Feb-2025 Draft 2 has entirely withdrawn FF3/FF3-1… for educational/experimental use."** No FF1 (patent). radix10→max 56 chars; radix36→36; radix62→32. minlen enforces radix^minlen ≥ 1e6. [A] https://github.com/mysto/python-fpe , https://pypi.org/project/ff3/ |
| **FPE (PyPI `FPE`)** | **FF1 + FF3-1** | Python | MIT | v0.1.2, 2021-11-28 | Has FF1. **Minimally maintained** (~last touched 2021). Convenience format wrappers (DIGITS/CREDITCARD/LETTERS/EMAIL/CPR), not raw radix. Patent risk inherited (ships FF1). [C] https://pypi.org/project/FPE/ |
| **pyffx** | FFX (not NIST FF1/FF3) | Pure Python | MIT | v0.3.0, 2019-05-12 | Implements *FFX method 2* — predecessor to FF1, **not the NIST FF1 standard**. Unmaintained. Fine for non-compliance-critical tokens; do not claim NIST conformance. [C] https://github.com/emulbreh/pyffx |
| **capitalone/fpe** | **FF1 + FF3** | Go | Apache-2.0 | maintained | Reference Go impl, AES via stdlib crypto/aes. Has FF1. Most-cited Go FPE. Patent risk inherited (ships FF1). [A] https://github.com/capitalone/fpe |
| **ubiqsecurity/ubiq-fpe-go** | FF1 + FF3-1 | Go | (vendor) | merged into ubiq-go (deprecated standalone) | Vendor lib; now folded into the Ubiq client SDK. [C] https://github.com/ubiqsecurity/ubiq-fpe-go |

> For Python, **there is no well-maintained, standards-clean, FF1-only OSS lib.** `ff3` is well-maintained but is the withdrawn mode; `FPE` has FF1 but is stale; `pyffx` is FFX-not-FF1. Go is healthier (capitalone/fpe has FF1, Apache-2.0, maintained).

### A.5 Vault transform engine — the reference design

HashiCorp Vault **transform** secrets engine offers three transformation types — pick the one matching the threat model: [C] https://developer.hashicorp.com/vault/docs/secrets/transform

- **`fpe`**: FF3-1 over AES-256. **Stateless** (Vault stores no secret), **deterministic** (same plaintext+key+tweak → same ciphertext, so colliding plaintexts collide in ciphertext — an *intended leakage property*). Tweak = exactly **7 bytes** (= 56-bit FF3-1 tweak). Reversible. [C] https://developer.hashicorp.com/vault/docs/secrets/transform/ff3-tweak-details
- **`tokenization`**: token is a **Base58 string of unrelated length**, **irreversible from token alone**, **NOT format-preserving**, and **stateful** (mapping stored internally or in external store). This is the vault-lookup model.
- **`masking`**: one-way redaction (e.g. ****-1234).

> The Vault split *is itself the design taxonomy* you need: format-preserving + deterministic + stateless (FPE) vs. random + reversible-via-vault + stateful (tokenization). It also demonstrates choosing FF3-1 specifically to dodge the FF1 patent.

### A.6 Deterministic FPE vs random-token+vault — the core tradeoff

| Property | Deterministic FPE | Random token + vault lookup (Presidio/Vault-tokenization style) |
|---|---|---|
| Referential consistency (join across records) | **Yes, free, stateless** | Yes, but **requires a stored map** |
| State / storage | None (key only) | **Vault/DB of token↔value pairs** (operational + breach surface) |
| Reversibility | Yes (with key+tweak) | Yes (lookup); token alone is meaningless |
| Format preserved | Yes (validators don't break) | Only if you template it; Vault tokenization is NOT format-preserving |
| **Leakage** | **Equality/frequency pattern leaks**: identical plaintexts → identical tokens. Frequency analysis + small domain → re-identification | No deterministic leakage if tokens are random per value |
| Small-domain crypto risk | Real (Beyne/Durak–Vaudenay) | None (no cipher to attack) |

- **Quantified leakage of deterministic encryption** — deterministic schemes leak the *equality pattern* (which records share a value) and *frequency distribution*; with auxiliary data this enables functional/full recovery. [B] https://www.researchgate.net/publication/337175550_Quantifying_Information_Leakage_of_Deterministic_Encryption
- FPE specifically: no IV, no authentication → "fewer security guarantees than deterministic AES-SIV." [C] https://www.fortanix.com/faq/tokenization/format-preserving-encryption
- Google Cloud DLP frames the same axis as **deterministic vs. format-preserving pseudonymization**, recommending deterministic AES-SIV (non-format-preserving) when leakage matters more than format. [C] https://docs.cloud.google.com/sensitive-data-protection/docs/pseudonymization

> **When is deterministic tokenization a re-identification risk?** When (a) the domain is small (phone/SNILS/passport — few millions of values), and/or (b) the value's *frequency distribution is skewed* (popular surnames, common cities), and/or (c) an adversary has auxiliary data to link the equality pattern (e.g. "the token that appears 400× is the most common surname"). For *high-cardinality, near-uniform* fields the risk is low. **Per-record random tweaks defeat the equality leak but also destroy cross-record consistency** — so you cannot have both stateless determinism AND no equality leakage.

---

## B. RUSSIAN-LANGUAGE PII DETECTION

### B.0 Structural fact that shapes everything

**Russian NER engines detect FREE-TEXT entities (ФИО / PER, адрес / LOC, ORG). Structured identifiers — телефон, СНИЛС, ИНН, паспорт — are NOT NER targets; they need REGEX + CHECKSUM recognizers.** Natasha exposes PER/LOC/ORG via Slovnet plus rule extractors (Names/Dates/Money/Addr) but has **no** СНИЛС/ИНН/passport/phone detection. [A] https://github.com/natasha/natasha

So a complete RU pipeline = **NER (names/addresses) + PatternRecognizers (СНИЛС/ИНН/паспорт/телефон with checksum validation)**. СНИЛС and ИНН both have published checksum algorithms → validate to cut false positives. [C] https://github.com/kdmatrosov/validation-codes , https://gist.github.com/Aleksandr-ru/c9cb1b28bf0acb6578464bd3006a31fe

### B.1 Recall numbers — the data (each carries its dataset/condition)

**SPbLitGuide benchmark (arXiv 2506.02589, 2025) — PERSON only, 1,000 docs / 5,611 PERSON labels, Russian cultural-events newsletters.** [B] https://arxiv.org/html/2506.02589v1

| Model | Precision | **Recall** | F1 | Note |
|---|---|---|---|---|
| DeepPavlov `ner_rus_bert` | 0.96 | **0.65** | 0.78 | high P, low R — silent leak |
| DeepPavlov `ner_ontonotes_bert_mult` | 0.94 | **0.71** | 0.81 | multilingual |
| RoBERTa Large NER Russian | 0.92 | **0.77** | 0.84 | |
| **spaCy Russian pipeline** | 0.84 | **0.81** | 0.83 | best recall among local models |
| gpt-3.5-turbo-0125 | 0.95 | 0.71 | 0.81 | |
| gpt-4-turbo | 0.99 | 0.69 | 0.81 | |
| gpt-4o (simple API) | 0.96 | **0.86** | 0.91 | |
| gpt-4o (JSON output) | 0.96 | **0.90** | 0.93 | |
| **gpt-4.1 (JSON output)** | — | **0.95** | — | highest recall reported |

> Critical: **best non-LLM recall ≈ 0.81 (spaCy)**; high-precision BERT models drop to **0.65 recall** — i.e. ~35% of PERSON mentions silently missed. For a de-id (privacy) task, **recall is the safety metric** and these local numbers are alarming on hard literary text. (Caveat: SPbLitGuide is adversarially hard — dense, ambiguous person mentions — so these are lower bounds vs. typical structured text.)

**Natasha / Slovnet self-reported** (averaged over Collection5, factRuEval-2016, BSNLP-2019, Gareev): **PER F1 0.97, LOC 0.91, ORG 0.85**; vs DeepPavlov BERT PER 0.98 / LOC 0.92 / ORG 0.86. Slovnet is ~27 MB / 205 MB RAM / ~25 docs-s on CPU vs DeepPavlov 2 GB / 6 GB GPU. On the *nerus* synthetic set alone: PER 99.7 / LOC 98.6 / ORG 97.2. **These are F1, not recall, and on news text — not directly comparable to the SPbLitGuide recall column.** [A] https://natasha.github.io/ner/ , https://github.com/natasha/natasha

**GLiNER PII (English-centric multi-domain PII set):**
- `urchade/gliner_multi_pii-v1` — **Apache-2.0**, the model Presidio's `GLiNERRecognizer` recommends. Multilingual base. [C] https://microsoft.github.io/presidio/samples/python/gliner/
- `knowledgator/gliner-pii-large-v1.0` — P 87.4 / **R 79.4** / F1 83.25; base variant F1 80.99; edge 75.50. 60+ PII types incl. passport/SSN/phone/address. Apache-2.0. Tagged multilingual but **Russian recall not separately benchmarked in the card.** [C] https://huggingface.co/knowledgator/gliner-pii-large-v1.0 , https://huggingface.co/knowledgator/gliner-pii-base-v1.0
- GLiNER architecture: BERT-like bidirectional encoder, **zero-shot** (entity types given at inference), parallel extraction; original paper outperforms ChatGPT zero-shot on NER benchmarks. [B] https://arxiv.org/abs/2311.08526 (Zaratiana et al., 2023-11-14)

### B.2 Ranked recommendation — RU PII detectors

Ranked for a **high-recall de-identification** goal (recall > precision), local-deployable first.

1. **GLiNER (`gliner_multi_pii-v1`, Apache-2.0) via Presidio `GLiNERRecognizer`** — best recall/coverage tradeoff that is *local, zero-shot, and multilingual*. Catches IDs/dates/phones that generic NER misses; you define RU labels (ФИО/адрес/телефон/паспорт) at runtime. Integration: built-in `from presidio_analyzer.predefined_recognizers import GLiNERRecognizer`, ONNX CPU path available. **Caveat:** Russian recall not separately published — must be validated on RU data before trusting. [C] https://microsoft.github.io/presidio/samples/python/gliner/
2. **Natasha / Slovnet (MIT, 27 MB)** — best *pure-Russian* names/addresses engine; tiny, fast, CPU-only, MIT. Plugs into Presidio as a custom NlpEngine/recognizer, or run standalone and feed spans. Strong PER on news; **weaker on hard/ambiguous text and no structured-ID detection.** Pair with regex recognizers. [A] https://github.com/natasha/natasha , https://natasha.github.io/ner/
3. **spaCy `ru_core_news_lg` (MIT)** — **native Presidio NlpEngine** (Presidio supports spaCy + Stanza out of the box), best recall among local models on SPbLitGuide (0.81). Easiest integration path. PER/LOC/ORG only. [B] https://arxiv.org/html/2506.02589v1 , https://huggingface.co/spacy/ru_core_news_lg , https://microsoft.github.io/presidio/analyzer/customizing_nlp_models/
4. **DeepPavlov `ner_rus_bert` / `ner_ontonotes_bert_mult` (Apache-2.0)** — highest precision (0.96) but **lowest recall (0.65–0.71)** → worst for a leak-averse de-id task despite "BERT" prestige. Heavy (2 GB, GPU). Use only if precision is the goal. [B] https://arxiv.org/html/2506.02589v1
5. **RoBERTa Large NER Russian** — balanced (R 0.77 / F1 0.84), middle-of-pack. [B] https://arxiv.org/html/2506.02589v1
6. **LLM (GPT-4o/4.1 JSON-mode)** — highest recall (0.90–0.95) but **not local, cost/latency, data-egress concern** for PII. A ceiling/oracle, or a second-pass catcher, not the primary local engine. [B] https://arxiv.org/html/2506.02589v1
7. **Stanza (Apache-2.0)** — Presidio-supported NlpEngine; RU model available but no RU-specific recall in the surveyed lit; generally below spaCy-RU here. Fallback. [B] https://microsoft.github.io/presidio/analyzer/customizing_nlp_models/

**Structured-ID layer (mandatory, regardless of NER choice):** Presidio `PatternRecognizer` regex + checksum for **телефон / СНИЛС (123-456-789 01 + checksum) / ИНН (10 or 12 digit + checksum) / паспорт (XXXX XXXXXX)**. NER will not catch these. [C] https://github.com/kdmatrosov/validation-codes

**Integration path (common):** Presidio Analyzer = NlpEngine (spaCy-ru OR Stanza-ru OR Natasha-as-custom) + RecognizerRegistry (GLiNERRecognizer + RU PatternRecognizers). To add a language you adapt the NlpEngine config + add recognizers, then `registry.add_recognizer(...)`. [C] https://microsoft.github.io/presidio/analyzer/languages/ , https://microsoft.github.io/presidio/tutorial/05_languages/ . There is **no pre-built RU SNILS/INN recognizer pack in Presidio** — must be authored.

### B.3 The detection-recall leak risk (eval literature)

- De-id evaluation uses precision / **recall (sensitivity)** / F1; **recall is the privacy-critical metric — every false negative is a silent PII leak.** [B] https://www.sciencedirect.com/science/article/pii/S1386505625004423
- i2b2 clinical de-id corpora (2006/2014, CEGS N-GRID 2016) are the standard benchmarks; strong systems report **~95% recall at ~79% precision** — i.e. recall is deliberately traded above precision, and *still misses ~5%*. [C] https://intuitionlabs.ai/pdfs/open-source-phi-de-identification-a-technical-review.pdf
- Missed (false-negative) PII clusters on **ambiguous instances a human would also hesitate on**; in-depth review found the residual leaks rarely compromised confidentiality — but this is domain-dependent and not a guarantee. [B] https://pubmed.ncbi.nlm.nih.gov/39716217/
- **How recall is measured:** span/token-level matching of detected vs. gold PII; recall = TP/(TP+FN). The SPbLitGuide entity-level numbers above are the cleanest RU example.

> Design implication: **a single detector at <100% recall is a silent-leak generator.** Mitigations from the literature: (1) ensemble/union of detectors (best-in-class de-id tools use ensemble learning — https://www.cell.com/patterns/pdfExtended/S2666-3899(21)00081-7), (2) regex safety-net for structured IDs (deterministic 100% on well-formed inputs), (3) recall-tuned thresholds, (4) an LLM/large-model second pass as a catcher.

---

## C. EDGE-CASE LITERATURE

### C.1 Entity consistency (pseudonymization) — utility vs. re-identification
- Consistent pseudonymization (same entity → same surrogate) is *required* for cross-record / longitudinal joins. Done via canonicalize→cluster→assign-one-surrogate-per-cluster. [C] https://docs.cloud.google.com/sensitive-data-protection/docs/pseudonymization
- BUT consistency *re-introduces the equality pattern* — same vulnerability as deterministic FPE: an adversary can count occurrences and link. BRATsynthetic (arXiv 2210.16125) contrasts **Consistent** vs. **inconsistent (Markov-chain) surrogate replacement** precisely because consistency aids linkage; inconsistent replacement breaks tracking but defeats re-linkage. [B] https://arxiv.org/abs/2210.16125
- A pseudonymized record with a recoverable code **remains PII/PHI** (HIPAA): consistency = reversible-by-design = still regulated data. [C] https://pmc.ncbi.nlm.nih.gov/articles/PMC11197357/

> **The unifying insight:** deterministic-FPE leakage (A.6), consistent-tokenization leakage, and consistent-pseudonymization leakage are the *same phenomenon* — the equality/frequency pattern. You can have stateless cross-record consistency, or no equality leakage, **but not both** without per-context keys/tweaks (which then need state to stay consistent).

### C.2 Indirect / quasi-identifiers & re-identification
- **Sweeney (2000): 87% of the US population uniquely identified by {5-digit ZIP, gender, date-of-birth}** (216M / 248M, 1990 census). [B] https://www.researchgate.net/publication/267716853_Simple_Demographics_Often_Identify_People_Uniquely , EPIC copy https://epic.org/wp-content/uploads/privacy/reidentification/Sweeney_Article.pdf
- Sweeney's **MA GIC re-linkage (1997)**: re-identified the Governor by joining "anonymized" health records to public voter rolls on QIs.
- **k-anonymity** (Sweeney): each record indistinguishable from ≥ k−1 others on QIs, via generalization + suppression. [B] same source
> **For this build:** quasi-identifiers (address + date + amount) are NOT caught by token-level PII detection. Even if every direct identifier (ФИО, телефон, СНИЛС) is perfectly tokenized, **the residual combination {city/адрес + date + transaction amount} can re-identify.** Direct-PII tokenization ≠ anonymization. If outputs are aggregated/shared, k-anonymity-style generalization on quasi-identifiers is a separate, necessary control.

### C.3 De-identification evaluation methodology
- Ensemble learning beats single models for de-id recall (best-in-class clinical de-id). [B] https://www.cell.com/patterns/pdfExtended/S2666-3899(21)00081-7
- Transformer benchmark for medical de-id (2025) — current SOTA single-center multi-specialty evaluation methodology. [B] https://www.cell.com/iscience/fulltext/S2589-0042(25)01993-5

---

## RECOMMENDATIONS (synthesis)

**Tokenization primitive:**
- **If format MUST be preserved and you want statelessness/consistency:** use **FF1** (only NIST-approved mode) — but note (a) **patent until 2029-02-20** (RAND license), (b) weak OSS Python support (`FPE` lib is stale; capitalone/fpe is the clean Go option), (c) deterministic equality leakage on small domains (phone/SNILS) is the residual risk.
- **Do NOT build new on FF3-1** — withdrawn by NIST 2PD (2025-02), broken by Beyne on exactly the small domains we care about. (Vault uses it only to dodge the FF1 patent; even `ff3` ships a withdrawal warning.)
- **Default recommendation:** **random-token + vault-lookup (stateful)** for the irreversibility/no-leakage path, and **format templating** layered on top *only where a validator demands it*. This sidesteps both the patent and the cryptanalysis, at the cost of holding a mapping store. Use deterministic FPE only for fields that (a) need cross-record joins AND (b) are high-cardinality/near-uniform AND (c) tolerate equality-pattern leakage.

**RU detector stack (high-recall de-id):** GLiNER `gliner_multi_pii-v1` (primary, validate RU recall first) ∪ Natasha/Slovnet or spaCy-ru (names/addresses) ∪ regex+checksum PatternRecognizers (телефон/СНИЛС/ИНН/паспорт) — union, not single model, because every detector at <100% recall silently leaks. LLM JSON-mode as optional second-pass catcher (recall 0.90–0.95) if data-egress is acceptable.

**Edge cases:** (1) consistency ⇒ equality leakage (same as deterministic FPE) — don't assume consistent tokens are "anonymous"; (2) {address+date+amount} quasi-identifiers re-identify even with perfect direct-PII tokenization (Sweeney 87%) — needs separate k-anonymity control if aggregated outputs are shared; (3) recall is the privacy metric — measure it, ensemble it, regex-net it.

## OPEN QUESTIONS / UNCERTAINTY LEDGER
- No published **Russian-specific** recall for GLiNER PII or Piiranha — must benchmark on RU PII data before trusting (claimed multilingual ≠ measured RU recall). [gap]
- SPbLitGuide is adversarially hard literary text; recall on clean structured RU text is likely higher — true operating recall is unknown without project-domain eval. [gap]
- FF1 patent licensing terms ("reasonable fee") are unquantified; whether OSS use is pursued by Micro Focus/OpenText in practice is unclear (de-facto tolerated for capitalone/fpe). [gap]
- SP 800-38G Rev.1 2PD comments closed 2025-04; final Rev.1 not yet published as of 2026-06 — FF3 removal is in *draft*, not yet final standard (but direction is unambiguous). [verify at publication]
