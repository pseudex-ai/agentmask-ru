# RU market segment + billing model for pseudex

Research date: **2026-08-15**. All pages fetched today unless marked otherwise.
Method constraint: **WebSearch was exhausted for this session (200/200)**. Every finding below
comes from a URL fetched directly. Nothing here is filled in from memory. Where a site could not
be reached it is listed in §5 as unreached, not guessed.

Convention used throughout:
- **[F]** = I fetched the page and it says this (quote or figure taken from the page).
- **[M]** = the page's marketing implies this but does not state it.
- **[X]** = could not verify today.

---

## 0. TL;DR

1. **The founder's claim is FALSE as stated.** Reversible PII masking for LLM traffic is not a gap
   in Russia — it is a commodity. At least six reachable products do it, one of them free
   (LiteLLM + Presidio), one bundled into a markup the customer already pays (KodikRouter, +10%).
   An anti-malware.ru market review dated **29 July 2026** names **eleven** Russian AI-gateway
   vendors.
2. **A narrower version of the claim is TRUE.** No vendor I could reach documents substituting the
   *real value back into a tool-call argument so the tool executes on real data*. Two vendors
   (Strazh, Луми 42) claim tool-call *control*; one (AppSec.AIGate) lists tool-call *inspection*
   as "В разработке" for **Q3–Q4 2026**. Inspection and control are not substitution. That is
   pseudex's actual differentiator — and it has a publicly announced closing date.
3. **Nobody in the segment publishes a price.** Eleven vendors, zero public price lists. The
   anti-malware.ru review says pricing is "Completely absent … no cost comparisons or pricing
   models provided for any solution."
4. **The current tier structure has a structural arithmetic bug**: the overage rate
   (0.40 ₽/1000 = 0.0004 ₽/request) is **50× to 242× cheaper than the price per request implied by
   the included volume**. No customer ever has a reason to upgrade a tier, and the largest
   customers pay the least per unit of value. See §3.1.

---

## PART 1 — WHO ELSE SOLVES THIS IN RUSSIA

### 1.1 The market map exists and is dated

**https://www.anti-malware.ru/analytics/Market_Analysis/AI-Firewall-AI-Secure-Gateway**
"AI Secure Gateway / AI Firewall: обзор российского рынка защиты LLM и корпоративного ИИ",
Оксана Гриднева, **29 July 2026**. [F]

This is the single most important source in this report. It names eleven Russian vendors and
states plainly that the segment is new:

> "по России цифр пока нет: рынок ещё не сформировался" [F]
> "рынок фактически формируется с нуля" [F]
> "объемы отечественного рынка пока не подсчитаны" [F]

On pricing across all eleven vendors: **"Completely absent from the review — no cost comparisons
or pricing models provided for any solution."** [F]

On 152-ФЗ, the review has exactly one explicit reference — ITGLOBAL.COM's AIaaS, "что
соответствует требованиям 152-ФЗ", about filtering and logging on Russian infrastructure. No
vendor in the review is positioned primarily on cross-border-transfer liability. [F]

### 1.2 Vendor-by-vendor: masking, reversibility, tool calls, price

| Vendor / product | Masks PII | Reversible | Tool-call handling | Price published |
|---|---|---|---|---|
| **Jay Guard** (Just AI) | yes, 25+ types incl. ФИО/паспорт | **yes** | not documented | no |
| **Cloud.ru Guardrails** | yes | **yes** | not documented | no separate line item |
| **KodikRouter** | yes | **yes, persistent map** | not mentioned | **yes — +10% markup** |
| **StarGuard AI** (Orion soft) | yes, to spec-tokens | **yes** | not documented | price list = PDF only |
| **INFERA AI.Firewall** | yes | "демаскирование" mentioned | not documented | no |
| **Strazh** | mask **and** block | not stated | **claims control of tool calls** | no |
| **Луми 42** | LLM firewall | not stated | **claims control of tool calls** | no |
| **HiveTrace / DataClean** | yes | not stated | **monitors + blocks** tool calls | no (quote) |
| **AppSec.AIGate** | yes | appears one-way | **"В разработке", Q3–Q4 2026** | no |
| **Innostage AIDR** | prevents leaks | not addressed | not mentioned | no |
| **SolidWall AI SG** (SolidLab) | not mentioned | n/a | not mentioned | no |
| **LiteLLM + Presidio** (OSS) | yes | **yes (`output_parse_pii`)** | `pre_mcp_call` mode exists | **free** |
| **InfoWatch** | **no — blocks** | n/a | n/a | no |
| **Solar Dozor** | classic DLP, no AI | n/a | n/a | no |
| **Zecurion** | classic DLP, no AI | n/a | n/a | no |

**Jay Guard** — https://just-ai.com/modul-maskirovania-dannuh, https://jaycopilot.com/help/jayguard/,
https://habr.com/ru/companies/just_ai/articles/946392/ [F]
> "Заменяет чувствительную информацию в запросе на псевдонимы, сохраняя семантику. После ответа
> LLM восстанавливает реальные данные на стороне клиента"
> "более 25 типов данных: ФИО, телефоны, паспортные данные, реквизиты, токены, email, IP"
> On-prem / Private Cloud / Hybrid; "Данные не покидают периметр компании"

The Habr technical article confirms the mechanism is a lookup table — "сохраняется таблица
соответствия (lookup table) между оригинальными значениями и сгенерированными метками" — and that
de-anonymisation happens by "подставляя оригинальное имя и телефон обратно **в текст ответа**". [F]
The article is explicitly scoped to "текстовых данных" and says nothing about function calling,
tool arguments, or structured API parameters. [F]

The product page does add one new phrase since the June research: "контроль цепочек действий
AI-агентов" (control of AI-agent action chains). [F] That is marketing-level; no mechanism is
described. **[M]** on whether it touches tool-call arguments.

**Cloud.ru Guardrails** — https://cloud.ru/docs/foundation-models/ug/topics/concepts__guardrails.html [F]
Masks credentials, API keys, IP, phone, email, ИНН, card, IBAN. Placeholders are `<EMAIL_1>`-shaped.
On response it "performs data unmasking — restoring the original values". Docs say protection rules
are "recommended when working with external models". Detection rules come partly from open sources
(gitleaks.toml). **Note against June's research: this is no longer described as locked to Cloud.ru's
own models.** No tool-call handling documented. Pricing: the Foundation Models tariff
(https://cloud.ru/documents/tariffs/evolution/foundation-models) contains only token, web-search and
cache line items — **no guardrails line item**, i.e. masking appears to be included free. [F]

**KodikRouter** — https://kodikrouter.ru/, https://kodikrouter.ru/pricing [F]
This is the commercially closest competitor and the most dangerous one.
> "Детерминированная детокенизация, персистентная карта псевдонимов и подробный аудит-лог."
> "Соответствие 152-ФЗ" / "Данные не покидают Россию"
> "Цена провайдера +10% за маршрутизацию, PII-маскирование и поддержку"
> "Абонентской платы нет ни на одном тарифе"

That first quote is pseudex's vault, described in pseudex's own terms — deterministic
detokenisation over a persistent pseudonym map, plus audit. Sold at **zero marginal cost**: the
masking is inside a 10% routing markup the customer pays anyway for model access. Base tier: 300+
models, 600 RPM, 30-day security logs. Enterprise tier: DPA, isolated namespace, HSM keys, **custom
PII detectors**, on-premise option, 3-year log retention, 99.95% SLA — price "custom". RPM scales
with account balance, ₽0 → 500 RPM up to ₽200 000+ → 10 000 RPM. Unused balance refunded in 14
business days. **Tool calls are not mentioned anywhere on the site.** [F]

**StarGuard AI** (Orion soft) — https://www.orionsoft.ru/starguardai [F]
Reverse proxy, in front of cloud models. Explicitly reversible:
> "маскирует их на спецтокены до отправки в облачную модель. Ответ модели демаскируется обратно"
30-day self-service trial. A "Прайс-лист" exists but only as a downloadable PDF — **the price is
not on the page**. No tool-call handling documented. [F]

**Strazh** — https://strazhai.ru/ plus the anti-malware review [F]
The review quotes: *"Контролирует запросы, контекст, ответы и поддерживаемые вызовы инструментов"*
and, in the agent-protection section, *"контроль использования конкретных инструментов, проверять
их описание, аргументы и результат вызова."* The vendor's own site talks about
"Блокировка/маскирование утечек секретов" and "Возможность замены/удаления критичных данных до
отправки", and BYOK ("Работаем с вашими API-ключами (BYOK) — единый биллинг и управление").
**Nothing states that a masked value is substituted back so the tool runs on real data.** Reading
their own words, "проверять аргументы" is inspection/policy, not substitution. No price. [F]

**Луми 42** — https://lumi42.ru/ (site body unreachable — title only), review quotes: [F]
> "Встраивается как слой контроля между корпоративными приложениями, LLM и инструментами.
> Доступны on-premise и облачная схемы инсталляции, поддерживается multitenancy, GPU-ускорители
> не требуются."
> "Полный контроль запросов, ответов и вызовов инструментов для локальных инсталляций."
On-prem, multitenant, no GPU needed — architecturally the closest shape to pseudex. Whether
"контроль вызовов инструментов" means substitution is **[X] unverified**; the site body did not
render.

**HiveTrace** — https://hivetrace.ru/ [F]
Release 4.2 added "monitoring of AI-agent tool calls" and "support for blocking tool calls", and
expanded DataClean's "cleaning of messages from personal data". Reversibility not stated. Deploys
on-premise / Yandex Cloud / Cloud.ru. Pricing: none — "evaluate the task and prepare a proposal".

**AppSec.AIGate** — https://appsec.global/appsecaigate [F]
"Автоматическое маскирование персональных данных, секретов и токенов" plus jailbreak/injection
blocking. Docker Compose or Kubernetes, on-prem / private cloud. Masking appears one-way. The
roadmap is the load-bearing fact: **"Инспекция вызовов инструментов агентами" — "В разработке",
Q3–Q4 2026.** No price.

**Innostage AIDR** — https://innostage-group.ru/products/aidr/ [F]
Transparent proxy, "блокирует prompt-инъекции и предотвращает утечки данных … ПДн, коммерческой
тайны". Docker on Astra Linux / RedOS / Alt Linux / Ubuntu, "включен в реестр российского ПО".
Leak *prevention*, not masking. No price.

**INFERA AI.Firewall** — https://inferasecurity.ru/ai_firewall/ [F]
> "различные режимы реагирования, включая блокировку сообщения, маскирование и демаскирование
> чувствительной информации"
So unmasking exists. Deployment shapes: "Proxy, API GW, Guardrails". No tool calls, no price.

**SolidWall AI Security Gateway** — https://solidlab.ru/products/ai-security-gateway.html [F]
This is a WAF wearing an AI hat — OWASP-shaped protection, positive security model, bot/brute-force
defence, Active/Active clustering. **No PII masking mentioned at all.** Not a competitor.

### 1.3 The Russian DLP incumbents: they are not in this market

- **InfoWatch** — https://www.infowatch.ru/products and
  https://www.infowatch.ru/ib-resheniya/zaschita-dannykh-pri-rabote-s-ii-servisami [F]
  They *do* have an AI solution page. It **blocks**, it does not mask:
  > "Перехват трафика и блокировка передачи конфиденциальных данных в ИИ-сервисы"
  > "Запросы сотрудников в нейросети"
  It is delivered by Traffic Monitor + Activity Monitor + Vision, i.e. **employee browser/desktop
  monitoring, not an API gateway.** Different buyer (СБ/ИБ department policing staff), different
  problem (shadow AI usage), different insertion point. Not a competitor for an agent backend.
- **Solar Dozor** — https://rt-solar.ru/products/solar_dozor/ [F] Classic DLP: channels, UBA,
  incident investigation, 2.7 TB/day archive, FSTEC trust level 4, registry #25822. **No AI, LLM,
  ChatGPT or masking-for-AI content on the page.** "Рассчитать стоимость" form, no price.
- **Zecurion** — https://www.zecurion.ru/products/ [F] DLP, DCAP, NGFW, SWG, Storage Security.
  **No AI/LLM references anywhere on the products page.**
- **Гарда Маскирование** — **[X] 403 today.** June research recorded it as static/DB
  de-identification, not real-time LLM traffic.
- **СёрчИнформ** — **[X] unreachable today** (HTTP header parse error on two URLs).

**Reading:** the DLP incumbents have the enterprise distribution, the FSTEC certificates and the
registry entries, and they are pointed at the wrong insertion point. That is simultaneously
pseudex's opening and its biggest channel risk (§4.4).

### 1.4 The self-build path — and what it actually costs

**Microsoft Presidio** moved twice this year: `microsoft.github.io/presidio` → 301 →
`data-privacy-stack.github.io/presidio` → 301 → **https://presidio.dataprivacystack.org/** [F].
The rename out of the `microsoft` namespace into a "data privacy stack" org is itself worth noting
— the project no longer sits under Microsoft's GitHub org. [F, mechanism = HTTP 301 chain]

- Presidio **does** support reversible de-identification: "Encryption/Decryption" with a tutorial
  and samples for "Encrypting and Decrypting identified entities". [F]
- **Russian is not supported out of the box.** The supported-entities page
  (https://presidio.dataprivacystack.org/supported_entities/) lists entities by country: USA, UK,
  Spain, Italy, Poland, Singapore, Australia, India, Finland, Korea, Nigeria, Philippines, Canada,
  Sweden, South Africa, Thailand, Turkey, Germany. **No Russia. No СНИЛС, ИНН, паспорт РФ, or RU
  phone format recognisers.** [F]
- No agent or tool-call capability documented. [F]

**LiteLLM** — https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2 [F] — is the crutch
everyone actually builds. It wraps Presidio's analyzer + anonymizer as Docker containers, supports
`MASK` and `BLOCK` actions, and critically supports **`output_parse_pii: True`**, which will "check
the LLM response and replace the masked token with the user-submitted values". A `pre_mcp_call`
mode exists for MCP requests. **This is not an enterprise-only feature.** [F] LiteLLM enterprise
pricing is not published: https://www.litellm.ai/enterprise offers "Start free", a "30-day trial
key … Full Enterprise features, self-hosted", and "Talk to sales" — no figures. [F]

**So the honest cost of the crutch:** free software, plus the work of writing Russian recognisers
Presidio does not ship (ФИО morphology, СНИЛС/ИНН checksums, паспорт, RU address), plus the work of
handling tool-call arguments, which neither LiteLLM nor Presidio does. pseudex's engine is exactly
those two pieces of work. **The crutch is real, it is free, and it is 70% of the job for a
text-only chat use case.** It is 0% of the job for an agent that executes tools on real values.

### 1.5 Model platforms

- **GigaChat** — https://developers.sber.ru/docs/ru/gigachat/api/overview [F] No PII
  masking/anonymisation/guardrails documented on the API overview. Compliance story is jurisdiction
  (RU processing), not tokenisation.
- **Yandex AI Studio** — **[X] unreached.** `yandex.cloud/ru/docs/ai-studio/` now 301s to
  `aistudio.yandex.ru/docs/ru/`, which serves a CAPTCHA to WebFetch. Three attempts, three
  CAPTCHAs. Cannot confirm or deny a PII filter today.
- **Cloud.ru** — has Guardrails (above), plus Evolution AI Factory: ML Inference, Foundation Models,
  Managed RAG, ML Finetuning, Notebooks, **Evolution AI Agents** ("Создание и интеграция
  мультиагентных систем"). [F] They are building the agent platform *and* the masking layer.
- **MTS / MWS** — **[X] unreached** (TLS: "unable to verify the first certificate").
- **T-Bank AI** — **[X] not attempted** (no known URL; WebSearch exhausted).

### 1.6 Verdict on Part 1

The segment pseudex sells into is **not empty and not virgin — it is crowded and pre-commercial.**
Eleven named vendors, a market review written about them three weeks ago, and zero published
prices. Everyone does masking. Six do it reversibly. Nobody documents the tool-call substitution
loop, and the first roadmap entry pointing at that territory says Q3–Q4 2026 — i.e. **now**.

---

## PART 2 — HOW ADJACENT RUSSIAN B2B SaaS PRICES

All pricing below was fetched from the vendor's own page today, 2026-08-15.

### 2.1 The table

| Product | URL | Model | Billing unit | Period | Free / trial |
|---|---|---|---|---|---|
| amoCRM | www.amocrm.ru/buy/ | per-seat | user/month | **6 mo minimum, no monthly** | 14-day trial |
| Битрикс24 | www.bitrix24.ru/prices/ | **flat tier bundling N users** | company | monthly or annual (−35%) | free, unlimited users, 25 GB |
| МойСклад | www.moysklad.ru/subscription/ | flat tier bundling users+POS+юрлица+storage | company | monthly; 3/6/12-mo prepay −5…−20% | **free forever** (5 users, 1 юрлицо, 100 items) + 14-day trial |
| RetailCRM | www.retailcrm.ru/pricing/ | base bundle + per-seat add-on + volume caps | mixed | monthly, −10% annual | free (1 user, 300 orders/mo, 5 000 customers) |
| Saby / СБИС | saby.ru/tariffs | à la carte blocks | per-user block, per-GB, per-message, per-year | **quarterly / annual** | limited free |
| Контур.Диадок | kontur.ru/diadoc/price | **pure per-document, declining unit price** | outgoing document | packages, 1-year expiry | 25 outgoing / 30 days; **incoming free forever** |
| Контур.Экстерн | kontur.ru/extern/price | tariff per company profile | legal entity | **annual** | — |
| Selectel | selectel.ru/prices/ | resource metering | **per hour, per GB, per API request** | hourly accrual | none (100 ₽ deposit); first 3 checks free |
| Timeweb Cloud | timeweb.cloud/services/cloud-servers | flat plans | ₽/мес | monthly | free test on request |
| Dadata | dadata.ru/pricing/ | **subscription = daily rate cap** | requests/day | **annual only** | free 10 000 req/day |
| GigaChat | developers.sber.ru/docs/ru/gigachat/tariffs/legal-tariffs | token metering + prepaid packages | per 1 000 tokens | packages expire in 12 mo; postpay min 600 ₽/mo | — |
| Cloud.ru FM | cloud.ru/documents/tariffs/evolution/foundation-models | token metering | per 1M tokens | pay-as-you-go | Evolution Free Tier |
| KodikRouter | kodikrouter.ru/pricing | **% markup on spend** | +10% of provider token cost | none — no subscription | — |
| LiteLLM | litellm.ai/enterprise | OSS + "talk to sales" | — | — | 30-day enterprise trial key |

### 2.2 The figures worth quoting

**amoCRM** [F] — 599 / 1 299 / 1 799 ₽ per user per month. The FAQ is explicit:
> "Стоимость тарифных планов установлена для подписки от полугода, помесячной оплаты в настоящее
> время нет."
14-day trial, no card apparent in the signup flow. **So: yes, the "no monthly billing at all"
pattern is real — but amoCRM is the extreme, not the norm.** Bitrix24, МойСклад, RetailCRM and
Timeweb all bill monthly and use prepay as a *discount*, not a gate.

**Битрикс24** [F] — the key structural fact: the price is **flat for the whole company at a user
ceiling**, not per seat.
| Tariff | Users | ₽/mo | with annual −35% | Storage |
|---|---|---|---|---|
| Бесплатный | ∞ | 0 | — | 25 GB |
| Базовый | 5 | 2 490 | 1 619 | 1 TB |
| Стандартный | 50 | 6 990 | 4 544 | 5 TB |
| Профессиональный | 100 | 13 990 | 9 094 | 10 TB |
| Энтерпрайз | 250–10 000+ | 33 990 – 999 990 | −35% | 15–120 TB |
Upgrade triggers: user ceiling, storage ceiling, feature gates (KEDO, BI). Note the free tier has
**unlimited users** — they gate on storage and features, never on headcount.

**МойСклад** [F] — 0 / 495 / 840 (1 400) / 2 460 (4 100) / 5 880 (9 800) ₽/mo, currently −40%
until 31 Aug. The tier bundles four independent dimensions at once: users, points of sale, legal
entities, storage. Trial expiry does **not** cut you off:
> "Ваш тарифный план переключится на «Бесплатный» (до 5 пользователей, 1 юрлицо, до 100 товаров /
> контрагентов / документов)"
Prepay discount ladder: "Оплатите сразу 3, 6 или 12 месяцев и получите скидку" — 5% to 20%.

**RetailCRM** [F] — the closest to pseudex's shape (base fee + included volume + priced extras).
Free tier: "1 пользователь", "до 300 заказов в месяц", "до 5 000 клиентов в базе". Professional:
9 360 ₽/mo annual (10 400 ₽ monthly) including "от 3 пользователей", 10 000 customers, 10 000
emails, 5 000 loyalty members. Extra user: "3 200 рублей в месяц". −10% annual.
**Note what they meter: stored entities and sent emails — stocks and outputs, never API calls.**

**Контур.Диадок** [F] — the most instructive pricing curve in this whole report:
| Documents/yr | Price ₽ | ₽ per document |
|---|---|---|
| 250 | 2 950 | 11.80 |
| 600 | 6 300 | 10.50 |
| 1 200 | 12 300 | 10.25 |
| 3 000 | 29 600 | 9.87 |
| 6 000 | 55 500 | 9.25 |
| 12 000 | 105 800 | 8.82 |
| 20 000 | 169 300 | 8.47 |
| 50 000 | 351 100 | 7.02 |
Unit price falls **40%** from the smallest to the largest package — monotonically, with no cliff.
Packages live until exhausted or one year, whichever first. Two policy quotes that matter:
> "Получение документов в Контур.Диадоке — бесплатное" / "Входящие документы бесплатны всегда"
> "Оплата производится только за документы, по которым завершен процесс документооборота"
They bill **only for completed work**, and the half of the traffic that is pure receiving is free
forever. Trial: "25 отправленных документов на 30 дней в подарок".

**Dadata** [F] — the single best structural analogue for a request-metered developer API in RU,
and it deliberately is **not** a request-metered product:
- Free: "10 000 запросов в день"
- Лёгкий 14 000 ₽/year → 50 000 req/day
- Расширенный 28 000 ₽/year → 100 000 req/day
- Максимальный 56 000 ₽/year → 200 000+ req/day
The tier is a **daily rate cap, not a monthly pool**, and overage is not billed — the service stops:
> "Сервисы по подписке отключатся до 00:00 следующего дня."
Separately, à la carte per-record pricing exists for the things that have real unit cost:
"20 коп./адрес", "7 ₽/емейл", "7 ₽/бренд". **Annual minimum, no shorter cycle.**

**Selectel** [F] — infrastructure meters on resource-time and bytes:
1 vCPU = 1.0071 ₽/hour (735.19 ₽/mo); ice-class S3 = 0.89 ₽/GB/mo; fast network SSD v2 = 0.0332
₽/GB/hour. Per-request billing exists but is priced as a rounding error: **S3 GET = 0.00036 ₽**.
No free tier ("no free testing"), 100 ₽ deposit to evaluate. Preemptible VMs up to −75%; "Freeze"
stops vCPU/RAM charges while keeping disks.

**Timeweb Cloud** [F] — 900 / 1 080 / 1 800 / 2 790 ₽/мес flat monthly, not hourly. Free trial on
individual request. Currently promoting "До 12.5 млн токенов на тест ИИ-агента" — i.e. Timeweb is
now also in the AI-agent business.

**GigaChat, legal entities** [F] — per 1 000 tokens incl. VAT: Lite 0.065 ₽ sync / 0.0325 ₽ async;
Pro 0.5 / 0.25; Max 0.65 / 0.325. Prepaid packages: 300M tokens = 19 500 ₽, 1B = 65 000 ₽,
"Пакеты действительны в течение 12 месяцев со дня оплаты". Postpay minimum 600 ₽/month if used,
nothing if unused.

**Cloud.ru Foundation Models** [F] — per 1M tokens: Claude Haiku 4.5 = 161 ₽ in / 805 ₽ out;
Claude Opus 4.1 = 2 415 ₽ in / 12 075 ₽ out. Guardrails: no separate line item.

### 2.3 Patterns that generalise

1. **Per-seat is the minority.** Bitrix24 and МойСклад bundle a seat ceiling into a flat company
   price; RetailCRM sells a bundle and charges for seats only above it. Only amoCRM is purely
   per-seat — and it compensates with a 6-month minimum. For pseudex this is moot anyway: there
   are no seats, the users are agents.
2. **Monthly-only is rare; prepay is the default posture.** Kontur (annual), Dadata (annual only),
   Diadoc (annual packages), Saby (quarterly), GigaChat packages (12-month expiry), amoCRM
   (6-month minimum). Monthly exists at Bitrix24/МойСклад/Timeweb but always at a 10–35% penalty
   versus annual.
3. **Nobody meters API calls as the primary unit.** Infrastructure meters resource-time and bytes
   (Selectel); document platforms meter completed business artefacts (Diadoc); data APIs meter
   *records enriched* and cap the *rate* (Dadata); model platforms meter tokens. Where per-request
   pricing exists at all (Selectel S3 GET), it is priced at 0.00036 ₽ — deliberately negligible,
   because the request is not where the cost or the value is.
4. **Where a volume cap exists, breaching it usually stops the service rather than generating an
   invoice.** Dadata switches off until midnight; МойСклад downgrades to free. Russian buyers are
   not sold surprise overage bills.
5. **Unit price declines with volume, monotonically.** Diadoc is the clean example (−40%). None of
   these products charge the biggest customer the most per unit.
6. **Free tiers are ubiquitous and structurally generous** — Bitrix24 free with unlimited users,
   МойСклад free forever, RetailCRM 300 orders/mo, Dadata 10k req/day, Diadoc incoming free
   forever. The free tier is used to make the product structurally present, then gated on a
   dimension that correlates with company size.

---

## PART 3 — THE BILLING MODEL QUESTION

Current published intent: **2 900 / 9 900 / 29 900 ₽/mo**, included **30k / 300k / 1.5M**
requests, **0.40 ₽ per 1 000** above.

### 3.1 The arithmetic bug — this is the headline

| Tier | ₽/mo | Included req | **Implied ₽ per 1 000 inside allowance** | Overage ₽/1 000 | Ratio |
|---|---|---|---|---|---|
| 1 | 2 900 | 30 000 | **96.67** | 0.40 | **242×** |
| 2 | 9 900 | 300 000 | **33.00** | 0.40 | **82×** |
| 3 | 29 900 | 1 500 000 | **19.93** | 0.40 | **50×** |

The marginal price is between 50× and 242× *below* the average price. Three consequences, all bad:

1. **The tier ladder never triggers.** A tier-1 customer running 3M requests/month pays
   2 900 + (2 970 000 / 1 000 × 0.40) = **4 088 ₽** — versus 29 900 ₽ on tier 3, for the same
   volume. Nobody will ever upgrade. The "included volume" numbers are decorative.
2. **Revenue is capped near the entry price.** A customer at 10M requests/month pays
   2 900 + 3 988 = **6 888 ₽/mo**. Your single largest, most agent-heavy, highest-value customer —
   exactly the one with the most cross-border exposure — pays under 7 000 ₽.
3. **It contradicts your own commercial plan.** `docs/payment-provider-request.md:23` states
   "Средний чек **19 000 – 49 000 ₽ в месяц**". Under this tier table that average check is
   arithmetically unreachable: tier 2 is 9 900 and tier 3 only gets there if a customer buys it
   without needing it. Fix one or the other before the payment-provider application goes out.

**So the answer to "does per-request billing punish the high-volume customers we want?" is: no —
as priced, it does the exact opposite.** It hands them a 50–242× volume discount and dissolves the
upgrade path. That is a worse failure than punishing them, because it is invisible in a pitch deck
and fatal in a P&L.

### 3.2 Is "request" the right unit at all? No.

Independent of the pricing bug, the request is the wrong meter here, for four reasons:

1. **A request is not the value delivered.** What the customer buys is "this real personal datum
   did not cross the border, and I can prove it". That is measured in **protected values**, not
   HTTP calls.
2. **pseudex's own architecture already says so.** Per `CLAUDE.md`: the mask cache keys on raw
   content and **"Audit is recorded on the cache miss only — the same value re-sent in a growing
   transcript is one protected value, not N."** The system already decided that the meaningful
   accounting unit is the distinct value. Billing on requests contradicts the product's own
   internal model of what happened.
3. **Request count is a function of the customer's agent loop, not their business.** A framework
   doing six tool-call round-trips per user turn bills 6× for the same protected data. That is a
   tax on precisely the agentic architecture pseudex exists to serve — the real version of
   "punishing the customers we want".
4. **It is gameable.** Batching N messages into one request cuts the bill N-fold and changes
   nothing about the protection delivered. A meter the customer can trivially move is a meter that
   invites arguments at renewal.

**Candidate units, ranked:**

| Unit | Fit | Precedent found today | Verdict |
|---|---|---|---|
| **Protected values** (distinct canonical values tokenised/month) | matches value, matches the vault's `(customer, canonical)` key, matches audit dedup, matches the legal story | Dadata "20 коп./адрес" (per record enriched); Diadoc per completed document | **primary meter** |
| **Rate band** (RPS/RPM ceiling) | fits an in-perimeter gateway the customer sizes against their own load; no trust needed in a usage counter | Dadata daily cap; KodikRouter balance→RPM ladder | **tier discriminator** |
| **Instance / environment** (per container, per prod/stage) | procurement-friendly, predictable, matches RU on-prem licensing habit | Innostage/InfoWatch quote-per-deployment | **platform fee** |
| Requests | gameable, mis-aligned, punishes agent loops | Selectel S3 GET at 0.00036 ₽ — priced as negligible on purpose | **demote to a guardrail, not a meter** |
| Seats | there are no humans in the loop | amoCRM | **reject** |
| Tokens | you don't see the model's bill; you're not the router | GigaChat, Cloud.ru, KodikRouter | **reject** (would only work if pseudex became a router — see §4.2) |

### 3.3 Recommended structure

**Shape: flat platform fee per environment + metered protected values with a declining unit price
+ an RPM ceiling per tier. Annual or semi-annual prepay as the default; monthly at a premium.**

Three tiers, discriminated on the two things that correlate with company size — *rate ceiling* and
*included protected values* — not on request count:

| | Старт | Рабочий | Промышленный |
|---|---|---|---|
| Platform fee (1 prod environment) | 9 900 ₽/mo | 29 000 ₽/mo | 79 000 ₽/mo |
| Included protected values / mo | 25 000 | 250 000 | 1 500 000 |
| Effective ₽ per 1 000 protected | 396 | 116 | 53 |
| Overage per 1 000 protected | 320 ₽ | 100 ₽ | 45 ₽ |
| RPM ceiling | 300 | 1 500 | 6 000+ |
| Extra environment (stage/DR) | +30% | +30% | included |

Design rules taken directly from what I found:
- **Overage sits just below the in-tier rate (~80%), never 50× below.** This is the Diadoc curve
  (11.80 → 7.02 ₽/doc, −40% monotonic) rather than a cliff. The upgrade decision then becomes real:
  you upgrade because the *next tier's* unit price is better and the RPM ceiling is binding.
- **The RPM ceiling is what actually forces the upgrade**, per Dadata and KodikRouter. A rate cap
  is enforceable inside the customer's perimeter without trusting a billing counter, which matters
  because pseudex cannot see payloads and its counters are self-reported.
- **Free tier: yes, and structurally generous.** Every RU comparable has one. Suggest free forever
  at 1 environment / 5 000 protected values per month / 60 RPM — enough to run a real pilot and a
  small production workload, gated on rate and volume so it grows into a paid tier. Cap-breach
  behaviour should follow Dadata and МойСклад: **degrade or stop, do not invoice a surprise.**
  (Note the fail-closed rule in `CLAUDE.md` makes "stop" the architecturally natural behaviour
  anyway — but a *billing* stop must be distinguishable from a *safety* stop in the error surface,
  or you will have a support incident that looks like a leak.)
- **Prepay default.** 6-month and 12-month prepay at −10% / −20% (МойСклад's ladder), monthly
  available at list. Do not copy amoCRM's "no monthly at all" — that works for a CRM with a 3-year
  average life, not for infrastructure a customer is piloting.
- **Publish the price.** Eleven competitors, zero published prices. Being the only vendor in the
  segment with a public price list is a distribution advantage, not a negotiating weakness: it
  converts the "запросить демо" wall into self-serve evaluation, which is how developer-facing
  products actually get adopted. StarGuard has a price list — as a PDF you must ask for. That is a
  gap you can walk through.

### 3.4 Lock-in and the vault — feature, liability, or both

**Where the lock-in actually is, structurally:**

1. **The token vault.** Persistent SQLite keyed by `(customer, canonical)`. A customer who leaves
   cannot decode their own historical tokens — every agent transcript, audit log, ticket, and any
   token-bearing field they wrote into their own CRM becomes undecodable.
2. **The leased bundle.** Per `CLAUDE.md`, detection quality lives entirely in the leased asset
   bundle, and the degradation ladder ends at `EXPIRED` → assets unloaded → `/mask` 503. Stop
   paying, and detection stops — not degrades, stops.

**Assessment — the two are not equivalent, and the founder should lean on exactly one of them.**

*The vault lock-in is both a liability and hollow.*

- **Hollow:** the SQLite file sits in the customer's own mounted `OBSCURA_DB_DIR`. They can
  `sqlite3 .dump` it without asking. Any lock-in you claim from it is a lock-in they can break in
  one command the moment a competent engineer looks. Building a commercial strategy on a hostage
  the hostage-taker doesn't control is not a strategy.
- **Liability:** the vault is a database of real personal data by construction. A customer who
  cannot resolve their own historical tokens has a problem the moment a data subject exercises a
  right of access or erasure against records that only exist in tokenised form. Selling a
  compliance product whose architecture creates a compliance defect in the buyer's own posture is
  a position that does not survive contact with the buyer's DPO. *(This inference is mine — I did
  not fetch the text of 152-ФЗ today, so treat the specific legal mechanism as unverified in this
  document. `research/legal-152fz-developer-liability.md` covers it from earlier work.)*
- **What comparables do:** the pattern in the RU market is explicitly anti-hostage. Diadoc:
  "Входящие документы бесплатны всегда" — the received archive is never held ransom. KodikRouter:
  "Неиспользованный остаток возвращается в течение 14 рабочих дней". МойСклад downgrades to a free
  tier instead of cutting access. None of these vendors monetise the customer's inability to
  leave.

*The bundle lease is the lock-in worth leaning on.* It is honest — the customer is subscribing to
ongoing detection quality against a moving target (new formats, new gazetteers, new evasions) — it
is technically enforced and already built, and it does not hold the customer's own data hostage.
"Your detection stops when you stop paying" is a normal software subscription. "Your historical
records become unreadable when you stop paying" is a hostage situation, and a buyer's security
review will name it as one.

**Recommendation:** ship a documented `export-vault` command producing a portable, encrypted
mapping file, and put data portability in the contract. Then say so in the sales motion — in a
segment where every competitor is a "запросить демо" black box, "here is how you leave" is a
differentiator, not a concession. Convert the founder's instinct ("завязать их бизнес на себе")
into the bundle lease + token stability across turns + the audit trail they need for a regulator,
all of which are things they keep paying for because they keep wanting them.

---

## PART 4 — CONCLUSION

### 4.1 Is "no normal solution exists" TRUE?

**No, as stated it is false, and it was already false before pseudex started.** Reversible PII
masking in front of an LLM is available today in Russia from at least six reachable products,
including one that is free (LiteLLM + Presidio, `output_parse_pii: True`) and one that charges zero
marginal cost for it (KodikRouter, folded into a +10% routing markup). A Russian market review
published **three weeks ago** enumerates eleven vendors in the segment.

**The narrower claim survives:** nobody I could reach documents putting the *real value back into a
tool-call argument so the tool executes on real data*. Two vendors claim tool-call *control*
(Strazh, Луми 42), one does tool-call *monitoring and blocking* (HiveTrace 4.2), and one has
tool-call *inspection* on a roadmap for **Q3–Q4 2026** (AppSec.AIGate). Inspection, monitoring,
blocking and control are all read-or-veto operations. Substitution is a write operation, and it is
the hard one, because it means the gateway is in the execution path of a real business action.

The founder's experience — "everyone builds their own crutches" — is accurate about *why* people
build them (Presidio ships no Russian recognisers at all; LiteLLM stops at text) but wrong about
*whether products exist*. They exist, they are numerous, and they are three weeks into being
catalogued by the trade press.

### 4.2 Closest competitor and how they beat us

**Commercially: KodikRouter.** They describe pseudex's core mechanism in pseudex's own vocabulary
— "детерминированная детокенизация, персистентная карта псевдонимов" — attach it to "Соответствие
152-ФЗ" and "Данные не покидают Россию", and charge **nothing extra for it**. Masking rides free
inside a 10% markup on tokens the customer buys anyway. They also solve the customer's *first*
problem (access to 300+ foreign models from Russia), which is more urgent than the customer's
second problem (152-ФЗ liability). They beat pseudex by making the purchase decision disappear:
you don't evaluate a PII gateway, you just point your base URL at them and masking is on.
Their weakness is the mirror image: they are the router, so the data does traverse their
infrastructure — which is exactly the objection pseudex's in-perimeter Docker answers.

**Technically: Луми 42 and Strazh.** Both claim control over "вызовы инструментов", both offer
on-premise, Луми 42 is multitenant and needs no GPU. If either already does value substitution and
just hasn't written it down, pseudex's differentiator is gone today rather than in two quarters.
I could not fetch either site's body — this is the highest-value open question in the report.

**Channel: Innostage AIDR, StarGuard AI, Jay Guard.** Registry-listed, FSTEC-adjacent, enterprise
sales motion, existing relationships with the CISOs who sign. They beat pseudex not on product but
on being already on the approved-vendor list when the budget line opens.

### 4.3 Recommended pricing model (summary)

Flat platform fee per environment + **protected values** as the meter (not requests) + an RPM
ceiling as the upgrade trigger + declining unit price with volume + a generous free tier + prepay
discounts + **published prices**. Detail and figures in §3.3. The single most urgent change is not
the unit — it is fixing the 50–242× gap between the in-tier rate and the overage rate, which
currently makes the tier ladder inoperative and caps revenue near the entry price.

### 4.4 The single biggest risk

**The differentiator is a feature gap with a published closing date, and pseudex has no
distribution to convert it before it closes.**

Concretely: masking has already been commoditised to zero marginal cost (KodikRouter +10%, LiteLLM
free, Cloud.ru with no guardrails line item). The only thing pseudex sells above that line is
tool-call value substitution. AppSec.AIGate has tool-call inspection shipping **Q3–Q4 2026**; two
vendors already claim tool-call control; Cloud.ru is building Evolution AI Agents and Guardrails in
the same product family and can fold substitution into a platform they already own. Meanwhile the
buyers who sign are reached through the registry/FSTEC/integrator channel that Innostage,
InfoWatch, SberTech and Orion already own, and pseudex is not in it.

If tool-call substitution ships inside something that is already free, or inside the cloud the
customer's agents already run on, the paid tier has no reason to exist. The window is two to four
quarters, and it is a distribution race, not an engineering race.

---

## 5. WHAT I COULD NOT REACH — brief for a rerun with search available

WebSearch was exhausted (200/200) for this entire session, so this list is genuinely blind spots,
not laziness. Every item below is a fetch that failed today.

**Hard blockers (retry with search or a browser):**
1. **Яндекс AI Studio** — `yandex.cloud/ru/docs/ai-studio/` and `/ru/prices` now 301 to
   `aistudio.yandex.ru`, which serves a CAPTCHA. **The product has moved to its own domain this
   year.** Unknown whether they now ship a PII filter or guardrails. High priority — a Yandex-native
   masking feature would reshape the segment.
2. **Луми 42** (lumi42.ru) — page returns title only ("LLMFW — LLM Firewall для безопасности ИИ").
   Their tool-call claim is the closest thing to pseudex's differentiator. **Highest-value gap.**
3. **Strazh** (strazhai.ru) — partial fetch; `/pricing` 404. Need to know whether "проверять
   аргументы" means substitution.
4. **ShieldMind.pro** — both `/` and `/landing` return title only.
5. **Platform V SOWA AI** (cybersecurity.sbertech.ru) — HTTP 401.
6. **МТС / MWS AI** (mws.ru) — TLS certificate verification failure.
7. **СёрчИнформ** (searchinform.ru, /products/) — HTTP header parse error, both URLs.
8. **Гарда Маскирование** (garda.ai) — HTTP 403.
9. **StarGuard AI price list** — exists as a PDF behind a form; the only known price list in the
   segment. Worth obtaining.

**Part 2 gaps:**
10. **Wazzup** — 403 on `wazzup24.com/prices/`, `/prices`, and `wazzup24.ru/prices/`.
11. **Диадок direct** (www.diadoc.ru) — 403; covered via kontur.ru/diadoc/price instead.
12. **Контур.Фокус** (focus.kontur.ru/site/prices) — 404; a developer-facing per-request RU API
    would have been a useful second data point alongside Dadata.
13. **Контур.Экстерн** — page reached but the SMB/accounting-firm tariff figures are not on it;
    only "Нулевая отчетность от 2 000 ₽ в год" and "Кадровые отчеты 3 600 ₽ в год" are public.

**Not attempted (no URL known, search unavailable):**
14. **T-Bank AI** — no reachable product URL identified.
15. **red_mad_robot red_mad_router / Guardrails** — covered in June research, not re-verified today.
16. **Google DLP / Sensitive Data Protection availability in RU** — not attempted.
17. **Habr / vc.ru discovery of startups launched since July 2026** — Habr's search page
    (`habr.com/ru/search/?q=…`) renders results client-side and returns "Нажмите на иконку поиска,
    чтобы увидеть результаты" to a fetcher. Any RU startup that launched after the 29 July
    anti-malware review would be invisible to this session.

**Internal inconsistency flagged for the founder (not a research gap):**
18. `docs/payment-provider-request.md:23` states an average check of "19 000 – 49 000 ₽ в месяц",
    which the 2 900 / 9 900 / 29 900 tier table cannot produce (§3.1). One of the two documents is
    wrong and the payment provider will read both.
