# DD5 — Monetization & Metering for a Self-Hosted PII Gateway

Research date: 2026-06-07. Scope: monetization / licensing / private metering ONLY.
Deployment/integration architecture is owned by another agent and deliberately excluded.

Core constraint driving everything below: the gateway runs **inside the customer's
perimeter**; their data + their LLM-provider API key never traverse our infrastructure.
Therefore we can never bill on a SaaS pass-through basis (tokens/requests we observe).
Monetization must come from (a) a **license** the customer pays for, and (b) **private
metering** — sending only aggregate counters, never payloads.

Evidence grades:
- **A** — primary vendor doc / source code / spec / law text
- **B** — vendor marketing / pricing page / official blog
- **C** — reputable third-party analysis (consultancies, review sites)
- **D** — single secondary source, directional only

---

## 1. Licensing models for self-hosted / on-prem software

### Taxonomy (what the options actually are)

| Model | What it locks to | Pros | Cons |
|---|---|---|---|
| **Signed license key (offline)** | A JWT/signed blob validated locally by the app; no callback needed to *run* | Works air-gapped; trivial to ship; no infra | Hard to enforce overage; relies on honor + audit |
| **Node-locked** | Hostname / machine fingerprint / cluster ID | Prevents copy-spread | Painful for elastic/containerized deploys; re-host friction |
| **Floating / concurrent** | A license server hands out N concurrent seats | Good for shared tooling | Needs an always-up license server in customer net |
| **Seat / named-user** | Count of provisioned users | Predictable; maps to org size | Needs reliable user counting; true-up disputes |
| **Capacity-based** | Throughput, data volume, # protected endpoints/workstations, # "clients" | Aligns price to value | Requires metering you can trust without seeing data |
| **Perpetual + annual support/maintenance** | One-time license, recurring support/updates | RU/enterprise procurement loves it | Lower recurring revenue than subscription |

### How proven self-hosted infra tools actually bill

**LiteLLM (LLM gateway — closest analog to us).**
The enterprise license is a **signed JWT set as an env var** `LITELLM_LICENSE="eyJ..."`;
the proxy validates it locally and unlocks "Enterprise Edition" features. Tiers: Enterprise
Basic ~$250/mo (UI, SSO, Prometheus metrics, JWT auth, guardrails); Premium ~$30k/yr
(SLA, governance, compliance assistance). All tiers are self-hosted; the customer runs the
Docker image + their own Postgres/Redis. Pricing is "depends on deployment size — contact us."
The public docs do NOT disclose node-lock vs floating, telemetry, or air-gap behavior — it's
sales-scoped. [Grade A for the JWT-key mechanism; B/C for pricing]
- https://docs.litellm.ai/docs/enterprise  (A — license is a JWT env var, local validation)
- https://www.litellm.ai/enterprise  (B)
- https://www.truefoundry.com/blog/litellm-pricing-guide  (C — $250/mo, ~$30k/yr tiers)

**HashiCorp Vault (open-core + enterprise license — the GOLD-STANDARD reference).**
Source-available under BSL 1.1 (since Aug 2023); Community covers core secrets, Enterprise
adds namespaces, replication, DR, Sentinel, HSM. Enterprise = a flat, sales-quoted license
(community reports low-six-figures/yr; not node-priced). Critically, Vault has a fully
documented **dual metering model** (see §2) — automated utilization reporting + manual
air-gapped reporting. This is the single best template for us. [A for license/feature split
and metering; C for price figures]
- https://developer.hashicorp.com/vault/docs/enterprise  (A — feature split)
- https://developer.hashicorp.com/vault/docs/license  (A — enterprise license keys)
- https://infisical.com/blog/hashicorp-vault-pricing  (C — six-figure quotes, opacity)

**GitLab (open-core, self-managed — GOLD-STANDARD for seat metering).**
Seats are **generic, not named** ("seats you buy can be distributed however you choose").
Self-managed instances sync subscription data **once a day** to customers.gitlab.com over
HTTPS: billable users count + historical max user count. Air-gapped customers use an
**Offline (Cloud) License** and submit usage **monthly/quarterly by email**. (Full detail §2.)
[A]
- https://about.gitlab.com/pricing/licensing-faq/  (A — generic seats, true-ups)
- https://docs.gitlab.com/administration/license_usage/  (A — exact export fields)

**Sentry (Fair Source / FSL).**
Self-hosted Sentry under the **Functional Source License** is **free and unmetered** — there
is NO billing system in the self-hosted build; per-event pricing exists only on SaaS. FSL
forbids reselling it as a competing service, then converts to Apache-2.0 after 2 years.
Lesson: Sentry does NOT monetize self-hosting at all — it monetizes Cloud. A cautionary
data point for a self-hosted-first product. [A]
- https://blog.sentry.io/introducing-the-functional-source-license-freedom-without-free-riding/  (A)
- https://develop.sentry.dev/self-hosted/  (A — no billing/pricing in self-hosted)

**PostHog (MIT core).**
MIT-licensed self-hostable core; Enterprise features (RBAC/SAML/SSO) are proprietary add-ons.
But PostHog **deliberately killed paid self-hosting** — "no longer possible to buy licenses
for self-hosted versions"; self-host is "for hobbyists," explicitly unsupported. They steer
everyone to Cloud (usage-based: free <1M events/mo). Lesson: usage-based metering of a
self-hosted analytics product proved operationally not worth it for them. [A/B]
- https://posthog.com/docs/self-host  (A)
- https://posthog.com/docs/self-host/open-source/support  (A — paid self-host discontinued)

**Portkey (AI gateway — direct analog).**
Core gateway went **Apache-2.0 open source (Mar 2026)**; the managed platform is Free / $49-mo
/ Enterprise. On-prem is **Enterprise-only via an air-gapped deployment option** (Apr 2026).
Same shape as us: open OSS core, monetize enterprise + air-gap. [B/C]
- https://portkey.ai/pricing  (B)
- https://github.com/portkey-ai/gateway  (A — Apache-2.0 core)
- https://www.truefoundry.com/blog/portkey-pricing-guide  (C)

**What's standard (synthesis).** Open-core (OSS core + proprietary enterprise tier) unlocked
by a **signed offline license key**, sold as either (a) **capacity/seat** (GitLab, InfoWatch,
Solar) or (b) **flat enterprise** (Vault, LiteLLM). Pure usage-based metering of self-hosted
software is rare and several leaders (Sentry, PostHog) abandoned it as not worth the friction.

---

## 2. Usage telemetry WITHOUT data egress (the central problem)

The proven pattern: **phone home COUNTS, not content**. Two documented exemplars:

### HashiCorp Vault — automated + manual license utilization reporting [A]
- **Automated**: every ~24h Vault makes an outbound HTTPS call to
  `reporting.hashicorp.services:443` sending **computed metrics only**: client counts
  (`clientcount.current_month_estimate`, `previous_month_complete`, split entity/nonentity),
  plus license ID, product+version, cluster ID, billing start date, snapshot metadata.
- Explicit privacy guarantee: reporting "shares the minimum data required to validate license
  utilization... consists mostly of computed metrics and **never contains personally
  identifiable information (PII) or other sensitive information**."
- **Air-gapped / manual**: if no outbound network, customer opts out and runs
  `vault operator utilization` CLI (or queries `sys/utilization` API) to produce a payload,
  then sends it to HashiCorp manually. Same metrics, human-in-the-loop, zero auto-egress.
- https://developer.hashicorp.com/vault/docs/enterprise/license/utilization-reporting  (A)
- https://developer.hashicorp.com/vault/docs/license/utilization/manual-reporting  (A)
- https://www.datocms-assets.com/2885/1684160815-hashicorp_licenseutilizationreportingfaq.pdf  (A — FAQ; "computed metrics... never PII")

### GitLab — Service Ping + Seat Link + Offline Cloud License [A]
- Service Ping: weekly payload, **mostly row-counts of DB tables**; "does not send any project
  names, usernames, or any other specific data." Free instances opt-out; paid instances on.
- Seat Link / daily sync: billable users count + historical max user count to
  customers.gitlab.com over encrypted HTTPS — drives true-ups.
- **Offline Cloud License** (the air-gap answer): "an alternative to online License Sync by
  requesting you to manually provide usage data to GitLab on a monthly basis." License file
  delivered by email; customer exports usage and emails it to renewals-service@customers.gitlab.com.
  Export file fields: license key, licensee email, start/end dates, company, generation
  timestamp, and a **historical table of {timestamp, billable_user_count}** — nothing else.
- https://docs.gitlab.com/administration/settings/usage_statistics/  (A — no names/usernames sent)
- https://about.gitlab.com/pricing/licensing-faq/cloud-licensing/  (A — offline = monthly manual)
- https://docs.gitlab.com/administration/license_usage/  (A — exact export fields)

### Synthesis — what gets sent vs never sent
- **SENT (safe):** aggregate counters (request count, # protected fields, # active seats,
  bytes-scanned-bucketed), license ID, product version, cluster/instance ID, period
  timestamps, validation pings.
- **NEVER sent:** the prompt text, the PII itself, the LLM-provider key, user identities,
  project/field names.
- **Air-gapped is a first-class, documented norm** in security/infra markets — both Vault and
  GitLab ship an explicit manual/offline path (CLI export + email/portal upload monthly). For
  a RU/security buyer this is not an edge case; it is an expectation. [A]

---

## 3. Open-core vs closed self-hosted (trust angle)

| Factor | Open-core | Closed self-hosted |
|---|---|---|
| Security-buyer trust | **High** — they can read the code, confirm no exfiltration, audit the data path | Lower — must trust claims / NDA source review |
| Adoption / land | **High** — free OSS core = bottom-up trial, community | Slower — every eval gated by sales |
| Privacy-product fit | **Strong** — "we phone home only counts" is *verifiable* in source | Weaker — privacy promise is unverifiable |
| Monetization risk | Free-riding / OSS cannibalizing enterprise | None |
| Eng overhead | Maintain clean OSS/EE boundary, dual licensing | Simpler single build |

For a **privacy/PII product the verifiability of open-core is itself a feature**: a security
buyer worried about data egress can grep the telemetry code and confirm only counters leave.
That is a stronger trust signal than any certificate. Vault, GitLab, Portkey, LiteLLM, PostHog
all run open-core. Sentry's FSL ("source-available, no free-riding") is a middle path that
still lets buyers inspect.

**What to keep OPEN (core):** the PII detection/redaction engine + proxy data path (this is
what buyers must inspect to trust no leakage), basic single-node operation.
**What to gate behind ENTERPRISE license:** SSO/SAML, RBAC, audit log, multi-node/HA,
centralized policy management, compliance reporting, priority support — i.e., the GitLab/Vault
EE pattern. The redaction quality can also be partially gated (advanced detectors/dictionaries)
if differentiation requires it, but keep the trust-critical data path inspectable.

**License choice for the open core:** a **Fair Source / BSL / FSL-style source-available
license** (read + self-host allowed, reselling-as-a-service forbidden) gives inspectability
WITHOUT letting a competitor lift the engine. This matches Sentry (FSL), Vault (BSL),
Portkey (Apache for max adoption). For a small vendor fearing a larger RU integrator forking
us, BSL/FSL > Apache.

---

## 4. RU market specifics (152-ФЗ context)

### Two different "ФСТЭК" things — do not conflate [A]
1. **Лицензия ФСТЭК (operator licensing)** — permission to *perform TZKI activity* (install/
   integrate СЗИ for others). Issued to a company, **бессрочно** (perpetual), entered in a
   registry. Cost to obtain from scratch: ~600k–1.5M ₽. Relevant if WE or our integrators do
   installation services.
   - https://habr.com/ru/companies/flant/articles/805559/  (A — process; perpetual)
   - https://fstec.ru/tekhnicheskaya-zashchita-informatsii/litsenzirovanie-tzi  (A)
2. **Сертификат ФСТЭК на продукт (product certification, СЗИ)** — the *software* is certified
   to a **уровень доверия (УД, 1–6; 1 = highest)** per ФСТЭК prikaz №55 (2018) / №76 (2020),
   and listed in the **государственный реестр сертифицированных СЗИ** (reestr.fstec.ru/reg3).
   Required to sell into systems where certified products are mandatory (КИИ, gov, often 152-ФЗ
   ISPDn at higher classes). **This is the cert that matters for a PII gateway.**
   - https://reestr.fstec.ru/reg3  (A — registry)
   - https://www.basealt.ru/about/blog/article/view/chto-takoe-urovni-doverija-fstehk-rossii  (A — УД levels)

### Реестр отечественного ПО (Минцифры) [A]
Separate from ФСТЭК. Being in the **единый реестр российских программ** (reestr.digital.gov.ru)
proves Russian origin, grants **VAT exemption (НДС)** and is effectively mandatory to sell to
state/КИИ buyers under import-substitution rules. Requires declaring who provides maintenance/
support and limits foreign royalty outflow (<30% of revenue).
- https://reestr.digital.gov.ru/  (A)
- https://www.garant.ru/gardium/guide/reestr-po-rf-chto-eto/  (A — VAT exemption, requirements)

### How RU security/privacy vendors actually license [A/C]
- **InfoWatch Traffic Monitor (DLP):** licensed **per workstation (рабочая станция) and per
  interceptor**, modular (buy only needed modules, expand later), sold in **1/2/3-year** terms;
  certified by ФСТЭК.
  - https://www.syssoft.ru/Infowatch/InfoWatch-Traffic-Monitor/  (C — per-workstation, terms)
  - https://www.infowatch.ru/company/about/licences  (A — ФСТЭК certs)
- **Solar Dozor (DLP, ГК Солар):** deployed **on the org's own compute**; licensed **by number
  of users with access / by employees under control per module**; модular; price on request.
  - https://rt-solar.ru/products/solar_dozor/blog/2087/  (C — by users/devices/traffic/volume)
  - https://rt-solar.ru/products/solar_dozor/descriptions/  (C)

### What RU enterprise expects (synthesis) [B/C]
- **On-prem / inside-perimeter is the default**, not the exception (sovereignty + 152-ФЗ).
- **Perpetual license + annual support/maintenance (техподдержка)** is the culturally expected
  shape; pure subscription is accepted but procurement (esp. gov) prefers a capitalizable
  perpetual + recurring СТП. Many vendors now also sell term (1/2/3 yr).
- **Capacity metric = per workstation / per user / per protected endpoint** (InfoWatch, Solar).
  For us the natural analog is **per protected application/integration or per seat/user behind
  the gateway**, NOT per request (can't see requests without the data).
- **Channel: reseller/distributor-driven** (Softline, Syssoft, AzONE, etc.) — direct sales are
  the exception; expect to sell through a partner channel.
- **Air-gapped/offline licensing is normal and often required** — see §2; align with the
  Vault/GitLab manual-export pattern.
- **Certifications gate the deal:** реестр отечественного ПО (for state/КИИ + VAT) and ФСТЭК
  product certification (СЗИ, УД level) are table stakes for serious 152-ФЗ/КИИ buyers.

---

## 5. RANKED monetization recommendation (self-hosted RU PII gateway)

### License model — ranked

1. **(RECOMMENDED) Open-core + signed offline license key, priced per protected
   application/integration (capacity), sold perpetual + annual support; term option available.**
   - Mirror Vault/GitLab: OSS-inspectable core (engine + data path) builds the trust a privacy
     buyer demands; enterprise tier (SSO, RBAC, audit, HA, central policy) unlocked by a
     **locally-validated signed JWT** (LiteLLM pattern) — works fully air-gapped, no run-time
     callback.
   - Capacity metric = **# protected applications/integrations or # seats/users behind the
     gateway** (the InfoWatch/Solar "per workstation/per user" analog), NOT per request — we
     cannot and must not count requests by reading them.
   - **Perpetual + annual СТП** matches RU procurement; offer 1/3-yr term as alternative.
2. **(Fallback) Flat enterprise license per deployment/cluster** (Vault/LiteLLM style),
   sales-scoped by size. Simplest to enforce; weaker value-alignment; fine for early big deals.
3. **(Avoid) Pure per-request/usage billing.** Structurally impossible without seeing data;
   Sentry & PostHog abandoned self-hosted usage metering — strong negative signal.

### How to meter usage privately (counts only)

- **Embed a utilization counter** that aggregates locally: requests processed (bucketed),
  # PII entities redacted, # active protected apps, # active seats, peak concurrency — **never
  payloads, never the PII, never the provider key, never user identities**. Mirror the Vault
  guarantee verbatim in our docs: telemetry "consists of computed metrics and never contains
  PII or sensitive information." Because we're open-core, this claim is **grep-verifiable**.
- **Two delivery modes (ship both, like Vault):**
  - *Connected:* optional ~24h outbound HTTPS of the counters blob for auto true-up.
  - *Air-gapped (default-safe for RU):* a `veilgate utilization export` CLI producing a signed
    counters file the customer reviews and submits **monthly/quarterly by email/portal**
    (GitLab Offline Cloud License pattern). No automatic egress at all.
- **Enforcement** stays soft (honor + contractual audit + the signed-license feature gate),
  exactly as Vault/GitLab do — hard kill-switches alienate security buyers and break air-gap.

### Open-core decision

- **YES, go open-core**, source-available under **BSL/FSL-style license** (inspectable, self-
  hostable, no resell-as-competitor). For a privacy product, inspectability of the data path +
  telemetry IS the trust argument — stronger than closed-source claims.
- **Open:** detection/redaction engine, proxy data path, single-node operation, the telemetry
  code itself (so buyers verify counts-only).
- **Enterprise (licensed):** SSO/SAML, RBAC, audit log, HA/multi-node, central policy mgmt,
  compliance/utilization reporting, priority support — the GitLab/Vault EE split.

### RU-market must-dos (parallel to monetization)

- Pursue **реестр отечественного ПО** (VAT exemption + state/КИИ eligibility) and **ФСТЭК
  product certification (СЗИ, target УД level)** — table stakes for 152-ФЗ/КИИ deals.
- Sell **perpetual + annual техподдержка** through a **reseller/distributor channel**.
- Treat **air-gapped licensing as a first-class feature**, not an afterthought.

---

## Open questions / uncertainty ledger
- Exact $ for Vault/LiteLLM enterprise are third-party estimates (C), not vendor-published.
- Whether a per-application vs per-seat capacity metric resonates better with RU buyers needs
  customer validation (InfoWatch=per-workstation, Solar=per-user — both differ from our unit).
- ФСТЭК product certification timeline/cost for a PII gateway not quantified here (process is
  months-to-years; needs a certification lab quote).
- LiteLLM's air-gap/telemetry behavior is undocumented publicly — could not confirm whether its
  JWT license validates offline indefinitely or requires periodic refresh (assumed offline-OK).
