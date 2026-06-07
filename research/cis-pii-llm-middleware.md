# CIS/Russian PII-Protection Middleware for LLM / AI-Agent Pipelines (152-ФЗ)

Research date: 2026-06-07. Market: CIS / Russian Federation.
Question: Does anyone already offer a **tool-call-aware, reversible-tokenization PII middleware** for LLM/agent pipelines under 152-ФЗ — where (a) PII in the user msg + RAG context is tokenized before the LLM, (b) when the model emits `find_order(phone="<TOKEN>")` the middleware swaps the token back to the real value **server-side in RF** to run the tool, (c) the tool result is re-tokenized before going back to the model, (d) the real↔token vault stays in RF?

Confidence convention: HIGH = vendor docs / primary legal text; MEDIUM = reputable secondary (habr/vc/cnews/tadviser); LOW = thin/inferred.

---

## TL;DR VERDICT

**No CIS player ships the full tool-call-aware reversible-tokenization loop as described.** Multiple vendors do **reversible request/response masking** (text in → tokens → LLM → tokens restored in the answer). That covers steps (a) and a text-only version of restoring the final answer. **None publicly document step (b)+(c): intercepting a function/tool call, swapping the token in the JSON args back to the real value to execute the tool server-side, then re-tokenizing the tool result before it re-enters the model.** The closest are **Just AI Jay Guard**, **Cloud.ru Guardrails Filter**, and **KodikRouter** — all text-level reversible masking, all explicitly silent on function-calling. The gap is independently confirmed by the Ideco "LLM Firewall is obsolete" article and is exactly the unsolved problem Brikko names in its own retrospective.

---

## 1. PLAYER-BY-PLAYER

### Just AI — Jay Guard  (closest "reversible masking" player)
- **What it does:** Gateway that masks sensitive data before the LLM and **de-anonymizes on the way back**: "заменяет в запросе выявленную часть на заглушку, сохраняя при этом семантику запроса"; on response "data is decoded back". Reversible by design (lookup table maps original ↔ placeholder, e.g. `[PERSON_1]`, `[PHONE_1]`).
- **Entities:** NER (PER/ORG/LOC via spaCy multilingual + flair, fine-tuned on RU synthetic+manual data) PLUS regex for phone, email, address, and **RU-specific документы: паспорт, СНИЛС, ИНН**. Article claims competitors don't handle RU doc formats — Jay Guard does. (HIGH)
- **Deployment:** cloud or on-prem; "гибкая архитектура… как в облаке, так и on-premise". Targets OpenAI/Anthropic use.
- **Tool-call reversibility:** **NOT documented.** Product docs + the Just AI Habr deep-dive describe only text request/response masking. Mapping-vault location (RF?) not stated in public docs (would be in the Спецификация-JayGuard-API.pdf / admin guide, not fetched). (MEDIUM-HIGH that it's text-only; LOW on vault residency)
- Sources: https://habr.com/ru/companies/just_ai/articles/946392/ ; https://just-ai.com/modul-maskirovania-dannuh ; https://jaycopilot.com/help/jayguard/ ; https://www.cnews.ru/projects/2025/Just_AI_predstavila_gotovoe_reshenie_dlya_AI-agentov

### red_mad_robot — red_mad_router + "Guardrails" module
- Platform for managing LLMs in business (launched ~Apr 2026). Guardrails "filters personal data before sending the request to the model, restricts unwanted responses, allows setting different policies for LLM"; adds logging + access control. Also has OCR+NER work for **masking PII on images**.
- **Tool-call reversibility:** **No public evidence.** The public material is marketing-level — no mention of function-calling, reversible token↔PII vaulting, or tool-arg swapping. Depth appears to be **input-side filtering/masking**, not a tool-call-aware reversible loop. (MEDIUM that it's text/image masking; cannot confirm reversibility at all from public sources — LOW)
- Sources: https://redmadrobot.ru/it-infrastruktura/kontrol-vmesto-eksperimentov-sobrali-platformu-dlya-upravleniya-llm-v-biznese ; https://www.cnews.ru/news/line/2026-04-16_kontrol_vmesto_eksperimentov ; (image masking) https://habr.com/ru/publications/1011450/

### Cloud.ru — Guardrails Filter  (Apr 2026, reversible, cloud-locked)
- Checks request text for **personal info, bank details, API keys & other secrets**, masks them, sends de-identified request to the model, and **"подставляет реальные значения обратно"** (restores real values) in the response. So: **reversible text masking, confirmed.**
- **Limitation:** currently works only with **Cloud.ru Foundation Models** (not arbitrary foreign models); on-prem promised later. **Tool-call handling: not mentioned.** (HIGH on reversible text; HIGH on cloud-lock; tool-call = absent)
- Source: https://www.anti-malware.ru/news/2026-04-09-111332/49657

### KodikRouter — RU LLM API gateway  (reversible masking + ~400 models)
- OpenAI-compatible gateway that **"automatically finds and masks PII before sending to the model, then restores original values in responses"** — explicitly framed as 152-ФЗ help, masking is free. Routes to ~400 models incl. Claude/GPT/Gemini and open DeepSeek/Qwen/Kimi. Has an "Extractions" field showing what de-identification happened.
- **Tool-call reversibility:** **not addressed.** Vault residency: not stated. (HIGH on reversible text masking + foreign routing; tool-call = absent)
- Source: https://vc.ru/dev/2926996-zapushchen-rossiiskii-api-shlyuz-kodikrouter

### Brikko — OpenAI-compatible gateway (honest negative; names the exact problem)
- Author states PII-masking is **"в PRД расписан, в коде ещё не реализован"** and Function calling/tools **"не реализовано"**. Crucially names the legal crux: with mapping tables **"данные остаются персональными по букве 152-ФЗ"** and indirect identifiers (address, diagnosis, contract #) still re-identify even after direct PII is masked. Concludes true compliance ⇒ local inference on RU models (YandexGPT/GigaChat), not masking-then-foreign. Dual-server: РФ-server holds PDn+billing, "never leaves RF jurisdiction". (HIGH — primary author statement)
- Source: https://vc.ru/ai/2897202-openai-sovmestimyj-shlyuz-brikko-dlya-rossijskih-kompanij

### RU AI-firewall startups (block/mask, NOT reversible, NOT tool-arg-aware)
- **AppSec.AIGate** (AppSec Solutions, Apr–May 2026): proxy that masks sensitive data + blocks prompt-injection. Behavior is **one-way block/mask** ("запрос заблокирован… есть чувствительные данные"); no reversibility, no tool-call parameter handling. (MEDIUM)
  - https://cisoclub.ru/fajrvol-blokirujushhij-ataki-na-iskusstvennyj-intellekt-razrabotali-v-rossii/ ; https://www.anti-malware.ru/news/2026-05-05-111332/49924
- **INFERA AI.Firewall**: analyzes requests to external LLMs, **blocks** text with confidential data. One-way DLP-style. (MEDIUM)
  - https://habr.com/ru/companies/infera_security/articles/1035282/
- **Ideco** thought-piece ("LLM Firewall: устарел, не успев родиться"): argues text-filtering firewalls fail for agents because agents need **"контроль tool calls, API-запросов, file I/O, shell"** and act with **"реальные права в системах"**. Confirms the tool-call layer is the gap; **names no vendor that solves PII in tool calls** (lists LlamaFirewall, NeMo, Prisma AIRS — none for this). (HIGH that the gap is real & unfilled)
  - https://habr.com/ru/companies/ideco/articles/1021292/

### RU cloud/model platforms — built-in de-id?
- **Yandex AI Studio:** no turnkey tool-call PII gateway. Pattern is DIY — strip/mask PII in Cloud Functions/DataSphere **before** the LLM (medical case: PDn never leaves the org контур; cloud logging off). Yandex's **AI-SAFE v1.0** framework recommends removing/masking PII before LLM/KB but is guidance, not a reversible tool-call product. (MEDIUM)
  - https://storage.yandexcloud.net/.../AI%20Secure%20Agentic%20Framework%20Essentials%20(AI-SAFE)%20v%201.0.pdf ; https://habr.com/ru/companies/raft/articles/1013906/
- **GigaChat / SberCloud:** value prop is **RU jurisdiction + local processing** (compliance by locality, not by tokenization). Built-in content filters, attempts to strip direct identifiers before training; vendor guidance warns auto-anonymization is risky for real secrets. No tool-call PII vault. (MEDIUM)
- **MTS AI / MWS:** own models via MTS AI Cloud; no documented tool-call PII middleware found. (LOW)

### RU DLP / data-security vendors
- **InfoWatch:** classic DLP (e.g., InfoWatch Gateway intercepts corporate mail/traffic for DLP). No LLM/agent reversible PII gateway found. (MEDIUM)
- **Solar (Ростелеком):** positions data-leak risk as the AI-adoption blocker (CIPR-2026: 80% cite leaks; 45% adopt AI with no security budget), Solar Dozor is classic DLP. No LLM tool-call PII product found. (MEDIUM)
- **Garda — "Гарда Маскирование":** **static/DB de-identification** ("обезличивание данных и надёжности передачи третьим лицам") — anonymizing databases before sharing, **not** a real-time LLM tool-call gateway. Not repositioned for agent pipelines. (MEDIUM-HIGH)
  - https://garda.ai/products/data-protection/datamasking
- **Zecurion, Makves, СёрчИнформ:** classic DLP/DAG; no evidence of an LLM/agent reversible PII gateway. (LOW-MEDIUM)
- **T1 Сфера.Обезличивание:** dedicated **обезличивание** product — batch/static de-identification, not an LLM tool-call middleware. (MEDIUM)
  - https://www.tadviser.ru/index.php/Продукт:Т1:_Сфера.Обезличивание_данных

### Hivetrace (ITMO AI Security Lab) — Dataclean
- **Hivetrace Dataclean** de-identifies PII for LLM apps; Hivetrace also does LLM red-teaming + runtime monitoring (blocks toxic content, warns on PII leak, policy mgmt for agents).
- **Most useful empirical finding (Raft/Igor Novikov study, ~Mar–Apr 2026):** on a banking agent (102 synthetic requests), **pseudonymization ≈ negligible accuracy loss; masking (`XXXX`) causes a noticeable drop**, because pseudonyms keep the data-type hint. BUT they explicitly note **PII is not used by the app to actually execute the task** — i.e. **the tool-call case is the acknowledged open gap**, not solved. (HIGH on the empirical result; HIGH that tool-call is unsolved there)
  - https://habr.com/ru/companies/raft/articles/1013906/ ; https://medium.com/@igor_novikov/the-effect-of-personal-data-removal-on-the-quality-of-llm-agents-1384e4f8e4a2 ; https://generation-ai.ru/cases/hivetrace ; https://hivetrace.ru/

---

## 2. RU PII NER QUALITY BAR (detection feasibility)

- **Natasha / Slovnet:** F1 **PER 0.97, LOC 0.91, ORG 0.85**; ~1 pp below DeepPavlov BERT NER but 75× smaller, 30× less RAM, 2× faster CPU. Good for ФИО/гео; weak/none for structured RU IDs out of the box.
- **DeepPavlov BERT NER:** SOTA RU general NER (PER/LOC/ORG); same caveat on structured IDs.
- **Pullenti:** commercial, strong on RU-specific structured extraction (addresses, orgs, documents); often best for адрес/паспорт-style fields.
- **Structured RU IDs (телефон, СНИЛС, ИНН, паспорт, email):** in practice handled by **regex + checksum validation**, NOT NER — СНИЛС/ИНН have control digits; Jay Guard/Cloud.ru/KodikRouter all use hybrid regex+ML. **Bar:** ФИО ~0.95+ F1 achievable; phone/email/СНИЛС/ИНН/паспорт ~0.98+ with validated regex; **address remains the hardest** (Pullenti/Natasha+Stanza compared specifically for addresses). nerus = the training corpus behind Slovnet. (MEDIUM-HIGH)
  - https://natasha.github.io/ner/ ; https://github.com/natasha/slovnet ; https://newtechaudit.ru/nlp-raspoznavaniyu-adresov/

---

## 3. 152-ФЗ LEGAL REALITY (load-bearing)

### Does reversible tokenization count as обезличивание?
**No — not while you hold the key.** Primary points (HIGH):
- **Definition (ст. 3):** обезличивание = actions making it impossible to attribute data to a subject **"без использования дополнительной информации"**. The "additional information" = your token↔value vault. If you (or any operator in the chain) can reverse it, the data is **still personal data**.
- **New regime (ФЗ-233 of 08.08.2024 → ст. 13.1; rules in force 01.09.2025; Roskomnadzor Order No. 140 of 19.06.2025 — 5 approved methods incl. "введение идентификаторов" i.e. pseudonymization):** the legal-analysis sources are explicit:
  - **"шифрование без уничтожения ключа"** is **NOT** anonymization — only a protective measure.
  - **"ни одна последующая операция обработки не должна позволить установить личность субъекта"** — if the operator holds the key, this fails.
  - During the de-identification *process* you handle raw PDn, so full 152-ФЗ applies; data leaves 152-ФЗ scope **only after** a result that **cannot** be re-identified by the holder.
  - Mapping table must be **stored separately**, keys/methodology **not disclosed to third parties**.
- **Net:** the tokenization-proxy approach is **pseudonymization = a security control**, NOT обезличивание. The tokens you send out are typically NOT "personal data" *for the foreign model that lacks the key* — but **for you the operator the underlying record stays personal data**, and you remain a full 152-ФЗ operator. (HIGH)
- Sources: https://legalacts.ru/doc/152_FZ-o-personalnyh-dannyh/glava-1/statja-3/ ; https://habr.com/ru/articles/931348/ ; https://www.consultant.ru/law/hotdocs/90337.html ; https://denuo.legal/ru/insights/news/I22/ ; https://e-office24.ru/news/trebovaniya-k-obezlichivaniyu-personalnykh-dannykh/

### Is "real PII stays in RF, only tokens go to a foreign/cheaper model" accepted?
**Partially — and it is the strongest available posture, but NOT a clean safe harbor.** (MEDIUM-HIGH)
- **Localization (ст. 18 ч. 5, since 01.07.2025):** bans **primary collection** of RU citizens' PDn into databases located abroad (запись, систематизация, накопление, хранение, уточнение, извлечение). It governs the **collection** stage, not all downstream processing.
- **Roskomnadzor (24.03.2025):** clarified localization does **not** by itself restrict **cross-border transfer of previously-collected** data. So: collect+store in RF, then transfer is a separate regime.
- **The viable architecture per the legal sources:** keep collection/storage/the vault in RF; if anything crosses the border it should be **de-identified**, because **"обезличивание до передачи… устраняет нарушение: обезличенные данные выходят из-под режима Закона"** — BUT that quote presumes *true* irreversibility, which a key-holding token proxy does **not** achieve. So sending *tokens* to OpenAI is far safer than raw PDn and likely defensible, yet it is **not** the statutory "обезличенные данные" exemption while you hold the vault.
- **Cross-border to USA specifically:** US is **not** on the "adequate protection" list ⇒ stricter трансграничная передача procedure + separate consent; raw PDn to ChatGPT/Claude breaches up to 4 norms at once. Tokenization materially reduces but does not formally eliminate this. (MEDIUM-HIGH)
- Sources: https://comply.ru/tpost/c43ezsout1-lokalizatsiya-i-transgranichnaya-peredac ; https://b-152.ru/hranenie-personalnyh-dannyh-za-granicej ; https://www.lidings.com/ru/media/legalupdates/localization_pd_update/

### Enforcement / fines (2025–2026)
- Localization breach: up to **6 млн ₽** (first), **18 млн ₽** (repeat).
- Leak fines: 3–5 / 5–10 / 15–20 млн ₽ by subject count; **repeat leak = оборотный штраф 1–3% годовой выручки** (min 20 млн, max 500 млн ₽). Consent for transfer must be a **separate document** since 01.09.2025.
- Sources: https://www.consultant.ru/legalnews/27142/ ; https://www.arbitr-praktika.ru/article/2742-shtrafy-za-personalnye-dannye ; https://securegpt.ru/blog/ai-personal-data-legal-risks

---

## 4. THE SINGLE BIGGEST OPEN GAP

The **tool-call / function-calling reversible loop**: intercept the model's `find_order(phone="<TOKEN>")`, **detokenize the JSON arg to the real value server-side in RF to execute the tool, then re-tokenize the (PII-laden) tool result before it re-enters the model.** Every shipping RU product stops at text request/response masking. The agent/tool layer is named as the unsolved frontier (Ideco), empirically left out of the only RU benchmark (Hivetrace/Raft "PII not used by the app to execute the task"), and explicitly unbuilt by Brikko. **Secondary gaps:** (i) indirect identifiers (address/diagnosis/contract#) survive direct-PII masking and re-identify; (ii) keeping the vault truly RF-resident with separation-of-key controls per Order 140; (iii) round-trip token **consistency** across multi-turn + RAG so the same person maps to the same token everywhere (needed for agent reasoning).

---

## 5. CONFIDENCE

- "No CIS product ships the full tool-call reversible loop": **HIGH** (negative confirmed across vendor docs + Ideco + Brikko + Hivetrace/Raft).
- Closest players are Jay Guard / Cloud.ru / KodikRouter doing reversible **text** masking: **HIGH**.
- Depth of red_mad_robot Guardrails (text/image masking, reversibility unconfirmed): **LOW-MEDIUM** (marketing-only public material).
- Legal verdict (reversible tokenization ≠ обезличивание while key held; pseudonymization = security control): **HIGH** (primary law + Order 140 + multiple legal firms).
- "Tokens-to-foreign-model is defensible but not a clean safe harbor": **MEDIUM-HIGH**.
- NER quality bar: **MEDIUM-HIGH**.
