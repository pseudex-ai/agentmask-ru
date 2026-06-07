# DD5 — Deployment & Integration Architecture for a PII-Tokenization Gateway

**Date:** 2026-06-07
**Scope:** Deployment models, provider-key custody, integration mechanism trade-offs, OpenAI-compatible coverage.
**Out of scope (other agent):** monetization, licensing.

**Context recap:** We are building a PII-tokenization gateway for LLM agents under CIS / 152-ФЗ. The
current design is a CLOUD reverse-proxy: the customer points `base_url` at OUR server and gives US
their provider API key. Two fatal problems: (1) customers will not hand a third party their provider
key; (2) if traffic transits our cloud, raw PII leaves the customer perimeter BEFORE masking —
defeating the entire "data stays local / in-RF" value proposition. Goal: find the proven
deployment + integration architecture that keeps BOTH the provider key AND the raw PII inside the
customer perimeter, while staying easy to integrate.

**Evidence grades:** [A] primary vendor doc / source code / spec · [B] vendor marketing / official blog
· [C] reputable secondary (engineering blog, comparison) · [D] forum / unverified.

---

## 0. Bottom line (TL;DR)

- The current cloud-proxy design is **architecturally wrong for the stated value prop**. Every
  privacy-first precedent that actually keeps data + key in the perimeter does so by running the
  gateway **inside the customer's network** (self-hosted container / data-plane-in-VPC), NOT by
  routing through the vendor's cloud.
- **Strongest, most directly-copyable precedent: LiteLLM (self-hosted proxy) + Microsoft Presidio
  (self-hosted analyzer/anonymizer) doing `pre_call` PII masking with reversible output parsing.**
  This is exactly our pattern — proven, OSS, and documented. [A]
- **Portkey's hybrid (data-plane-in-VPC) and Skyflow's BYO-cloud vault** prove the enterprise market
  accepts/expects the "control plane is ours, data plane is yours" split. [A]/[B]
- **Helicone's proxy-vs-async** split is the proof that being on the critical path is a liability;
  serious players offer an off-critical-path mode. [A]
- **Integration verdict:** ship a **self-hosted, OpenAI-compatible reverse proxy as the default**
  (language-agnostic, one-line `base_url` swap, key+PII never leave the box), and offer an
  **in-process SDK** as the zero-network-hop option for latency-sensitive / single-language teams.
  Avoid SaaS proxy and TLS-MITM egress proxy as defaults.
- **OpenAI-compatible coverage:** "OpenAI-compatible endpoint" covers the large majority of providers
  (OpenAI, Azure, OpenRouter, vLLM, Ollama, **YandexGPT/Yandex AI Studio**, most aggregators). The
  notable RU exception is **GigaChat (Sber)** which is NOT natively OpenAI-compatible and needs an
  adapter (e.g. `gpt2giga`). [A]

---

## 1. Deployment models — where does masking happen relative to the customer perimeter

### 1.1 Skyflow — LLM Privacy Vault

- Skyflow positions as a **data privacy vault** that **intercepts data flows between the UI and the
  LLM** via Skyflow APIs/SDKs/Connections; de-identification (tokenization/masking) happens **inside
  Skyflow's infrastructure** before data reaches the LLM, and deterministic tokens in the LLM
  response are swapped back to plaintext for authorized users. [A]
  - URL: https://www.skyflow.com/post/generative-ai-data-privacy-skyflow-llm-privacy-vault
- Deployment: marketed as a **SaaS / managed vault** with **global data-residency** (vaults in 100+
  / 150+ countries, run on AWS, customer chooses region), plus **BYOK (bring-your-own-encryption-
  keys)** and VPC-style deployment. [B]
  - URL: https://www.skyflow.com/post/private-llms-data-protection-potential-and-limitations
  - URL: https://aws.amazon.com/blogs/apn/how-to-scale-for-global-saas-growth-with-a-skyflow-data-privacy-vault-on-aws/
- **Key caveat for us:** Skyflow's default flow sends "user input from the front-end UI **directly to
  Skyflow**" — i.e., raw PII transits Skyflow first. That is exactly the "data leaves perimeter
  before masking" failure mode we must avoid, UNLESS deployed in a private/BYO-cloud arrangement.
  The public docs are explicit on residency but **vague on a true in-customer-VPC, no-vendor-transit
  mode**. [A] (absence noted)
- **Takeaway:** Skyflow proves the tokenize-before-LLM + detokenize-on-response pattern and the
  data-residency demand, but its center of gravity is SaaS/regional-residency, not "never leaves
  customer box." Not a clean fit for a 152-ФЗ "stays on-prem" promise without the private-cloud SKU.

### 1.2 LiteLLM — self-hosted proxy (CLOSEST PRECEDENT)

- LiteLLM is an OSS AI gateway you **run on your own infrastructure**; "only the model providers see
  your prompts, and only your virtual-key holders see your provider credentials." [B]/[A]
  - URL: https://github.com/BerriAI/litellm/
- **Provider keys** are added per-model and stored **encrypted in your own Postgres** (encrypted with
  `LITELLM_SALT_KEY`); `LITELLM_MASTER_KEY` is the proxy's own root auth, separate from provider
  keys. Stack = proxy + Postgres + Redis, all in customer infra. [A]
  - URL: https://docs.litellm.ai/docs/proxy/virtual_keys
- **PII masking**: LiteLLM integrates **Microsoft Presidio** as a guardrail. Presidio runs as
  **self-hosted Docker containers (analyzer :5002, anonymizer :5001) on localhost** in the
  customer's environment. Masking runs in **`pre_call` mode — before the LLM call, on input** — so
  **raw PII does not leave the customer infra before masking**. Output parsing restores original
  values in the response (reversible). Supports **ad-hoc / custom recognizers**. [A]
  - URL: https://docs.litellm.ai/docs/tutorials/presidio_pii_masking
  - URL: https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2
  - URL: https://microsoft.github.io/presidio/samples/docker/litellm/
- **This is our exact target architecture, already proven and shipping**: self-hosted OpenAI-
  compatible proxy + local PII detection + reversible token mapping + provider key held locally.

### 1.3 Portkey — SaaS + hybrid (data-plane-in-VPC)

- Portkey Enterprise offers a **hybrid deployment**: the **Data Plane runs in the customer VPC**
  (AI Gateway + cache store + data store), the **Control Plane is Portkey-hosted** (dashboard,
  configs, analytics). [A]
  - URL: https://portkey.ai/docs/self-hosting/hybrid-deployments/architecture
- **What stays in the customer VPC:** API keys & virtual keys (held in local cache), **prompt
  payloads** ("All LLM traffic stays within your network boundary", "Complete isolation of sensitive
  prompt data and responses"), and request/response logs (optional, customer blob store). [A]
- **What the control plane sees:** only routing configs (synced via 1-min heartbeats), provider-
  integration metadata, and **anonymized metrics** (model used, token counts, response times).
  "Prompt content and LLM responses never transit to Portkey's infrastructure." [A]
- Gateway keeps **all config objects in a local cache** so each request is served without a real-time
  round-trip to the control plane, and **keeps operating if disconnected** from the control plane —
  important resilience property. Deployed as containers (K8s/ECS), Terraform provided. [A]
- **Explicit tradeoff (honest):** control-plane sovereignty is NOT achievable in hybrid — the
  dashboard/guardrail-config/analytics aggregation remain Portkey-hosted by design. [C]
  - URL: https://thenewstack.io/portkey-gateway-open-source/ (gateway is also OSS, 2T tokens/day)
- **Takeaway:** Validates the "data plane in customer VPC, control plane ours" pattern as
  enterprise-acceptable. For strict 152-ФЗ we'd want even the control plane optionally on-prem
  (or no control plane at all).

### 1.4 Helicone — proxy vs async logging (critical-path lesson)

- Helicone's primary integration is a **proxy** (swap `base_url`); proxy adds "negligible logging
  delay" (benchmarked sub-10ms). But it also offers **async logging** (via OpenLLMetry) where
  "the actual logging of the event is **not on the critical path**", so "if Helicone is down or
  there is a network issue, it will not affect your application" — **0 propagation delay**. [A]
  - URL: https://docs.helicone.ai/references/proxy-vs-async
- **Tradeoff:** async cannot offer gateway features (rate limiting, caching, retries) — those require
  the proxy. [A]
- **Takeaway for us:** being in the request critical path is a real liability (availability +
  latency). Our masking gateway MUST be on the critical path (it's the whole point), so the design
  must minimize the blast radius: run **in-process / in-perimeter**, not as a remote hop, so a
  network partition to a vendor cloud can never take down the customer's LLM calls. Helicone's async
  mode is the precedent for "don't make us a remote single point of failure."

### 1.5 Cloudflare AI Gateway / Kong AI Gateway (where they sit)

- **Cloudflare AI Gateway**: managed **edge** service sitting between app and LLM provider on
  Cloudflare's global network (310+ cities); zero infra setup, but **traffic transits Cloudflare
  edge** — i.e., SaaS proxy on the critical path, off-perimeter. [B]/[C]
  - URL: https://www.cloudflare.com/products/ai-gateway/
  - URL: https://developers.cloudflare.com/ai-gateway/demos/
- **Kong AI Gateway**: extends the **self-hostable Kong API gateway** via plugins; sits as a gateway
  in front of LLM traffic, governed like other API traffic. Self-hostable → can live in customer
  perimeter, but operationally heavy. [C]
  - URL: https://www.respan.ai/market-map/compare/cloudflare-ai-gateway-vs-kong-ai-gateway
- **Takeaway:** Cloudflare = wrong model for us (off-perimeter SaaS). Kong = right locus (self-hosted,
  in-perimeter) but heavyweight and not PII-specialized.

### 1.6 red_mad_router (red_mad_robot) — RU 152-ФЗ precedent

- RU platform for centralized LLM management; **on-premise is a basic deployment scenario** — deploys
  into the company's secured infrastructure, SSO, infosec requirements. [B]
  - URL: https://redmadrouter.ru/
  - URL: https://www.cnews.ru/news/line/2026-04-16_kontrol_vmesto_eksperimentov
- Has a **Guardrails / PII + unwanted-content filtering module** for safety when calling external
  LLMs, plus logging/audit/access control. Connects models via an **OpenAI-compatible interface** so
  providers don't each need separate integration. [B]
- **Takeaway:** the most direct RU competitor confirms the on-prem + OpenAI-compatible + PII-filter
  recipe is the expected shape for the 152-ФЗ market. Their existence both validates demand and sets
  the integration bar (OpenAI-compatible, on-prem).

### 1.7 Microsoft Presidio (the detection/masking engine, not a gateway)

- Presidio = **library/SDK** (Analyzer + Anonymizer + Image Redactor + Structured), usable as a
  **Python package (in-process)** OR as **dockerized REST services**. Fully customizable/pluggable;
  deployable into any environment. [A]
  - URL: https://github.com/microsoft/presidio
  - URL: https://microsoft.github.io/presidio/
- Integrates into gateways: LiteLLM (above), Azure APIM ("PII Shield"), MCP gateways. [B]/[C]
  - URL: https://techcommunity.microsoft.com/blog/azuredevcommunityblog/introducing-pii-shield-a-privacy-proxy-for-every-llm-call/4514726
- **Takeaway:** Presidio is the canonical detection/masking layer to embed — both as in-process lib
  and as a local sidecar. Either way it runs **inside the perimeter**.

---

## 2. Provider-key custody — how proven players avoid holding the customer's key

| Player | How the provider key is handled | Stays in customer perimeter? | Grade |
|---|---|---|---|
| LiteLLM (self-host) | Per-model provider keys encrypted in customer's own Postgres; proxy runs in customer infra | **Yes** | [A] |
| Portkey hybrid | API keys + virtual keys held in local cache in customer VPC data plane | **Yes** | [A] |
| Skyflow | Vault-mediated; BYOK supported; default flow routes data through Skyflow SaaS | Partial / only in private-cloud SKU | [B] |
| Cloudflare AI GW | Keys configured in Cloudflare; traffic transits Cloudflare | **No** (SaaS) | [C] |
| red_mad_router | On-prem deployment → keys in customer infra | **Yes** | [B] |

**Pattern that solves our problem:** *bring-your-own-key INSIDE the customer's own deployment.* When
the gateway runs in the customer perimeter, the provider key is simply a local secret the customer
configures — **we never receive it.** This is the LiteLLM / Portkey-hybrid / red_mad_router model.
The **"virtual key"** concept (LiteLLM, Portkey) is a complementary layer: issue revocable internal
keys to apps/teams that map to the real provider key, so even internal callers don't see the provider
credential. [A]

This directly kills both stated problems:
1. We never hold the customer's provider key (it's a local secret in their box).
2. Raw PII is masked locally before any byte goes to the provider — nothing transits our cloud.

---

## 3. Integration mechanism trade-offs

| Mechanism | Data leaves perimeter? | Integration effort | Language-agnostic | Key custody | Critical-path risk | Notes |
|---|---|---|---|---|---|---|
| **SaaS reverse-proxy (current design)** | **YES — before masking** ✗ | 1-line base_url | Yes | **We hold key** ✗ | Vendor outage = customer outage | The thing we must abandon |
| **Self-hosted reverse-proxy (base_url → LOCAL)** | No (masking local) ✓ | 1-line base_url + run a container | **Yes** ✓ | Local secret ✓ | In-perimeter only ✓ | **Recommended default.** Precedent: LiteLLM+Presidio, Portkey hybrid, red_mad_router |
| **In-process SDK / library** | No (never leaves process) ✓✓ | Wrap the client / swap import; per-language | **No** (one SDK per lang) ✗ | Local secret ✓ | None (no network hop) ✓✓ | Precedent: LiteLLM Python SDK, Presidio as a lib. Best privacy + latency, worst polyglot story |
| **Sidecar container** | No (loopback) ✓ | Deploy alongside app; point client at localhost | **Yes** ✓ | Local secret ✓ | In-perimeter only ✓ | Precedent: PII-masking sidecar pattern; k8s-native. Same wire contract as reverse-proxy |
| **Forward/egress proxy + TLS MITM** | No (masking local) ✓ | No app change, but install enterprise CA in every trust store | **Yes** (transparent) ✓ | Local secret ✓ | In-perimeter only ✓ | TLS interception "significantly weakens security properties"; brittle cert pinning; ops-heavy. Avoid as default |
| **MCP gateway** | No (in-perimeter) ✓ | Only covers MCP tool-call traffic | Yes (MCP) | Local secret ✓ | In-perimeter only ✓ | Precedent: MCP Manager, TrueFoundry. Complementary, not a replacement for chat-completions masking |

Sources: LiteLLM SDK vs proxy (https://docs.litellm.ai/ , https://github.com/BerriAI/litellm/) [A];
sidecar PII pattern (https://dev.to/dhroov7/how-we-built-a-pii-masking-layer-for-llm-apis-local-detection-reversible-tokens-one-line-to-12c8 ,
https://blog.logrocket.com/build-local-ai-proxy-redact-pii-before-llms/) [C];
TLS-MITM weakening (https://blog.cloudflare.com/monsters-in-the-middleboxes/) [C];
MCP gateways (https://mcpmanager.ai/blog/pii-redaction-for-mcp-servers/ ,
https://www.truefoundry.com/blog/enterprise-ai-security-with-mcp-gateway-runtime-guardrails) [C].

### Verdict on "data never leaves perimeter + minimal integration + language-agnostic"

- **In-process SDK** = best privacy & latency (zero network hop, PII never even leaves the process),
  but **not language-agnostic** (need an SDK per language) and requires code changes.
- **Self-hosted reverse-proxy (local base_url)** = best *combination*: one-line `base_url` change,
  **language-agnostic** (any OpenAI client), data + key stay local. The single tradeoff vs SDK is a
  loopback/in-cluster network hop (negligible — Helicone benchmarks proxy overhead sub-10ms). [A]
- **Sidecar** is the same wire contract as the reverse-proxy, packaged for k8s — offer as a
  deployment topology, not a separate integration.
- **TLS-MITM egress proxy** is the only "zero-code, all-languages, all-traffic" option but pays for
  it with CA-trust-store rollout, cert-pinning breakage, and a documented weakening of TLS security.
  Niche / opt-in only.
- **MCP gateway** addresses a different surface (agent tool calls) — additive, not a substitute.

---

## 4. Per-provider work — is "OpenAI-compatible endpoint" enough?

**Mostly yes.** The OpenAI `/v1/chat/completions` schema is the de-facto lingua franca; a single
OpenAI-compatible ingress covers the large majority of providers via `base_url` swap:

| Provider | OpenAI-compatible? | base_url | Adapter needed? | Grade |
|---|---|---|---|---|
| OpenAI / Azure OpenAI | Native | api.openai.com / azure | No | [A] |
| OpenRouter (aggregator) | Yes — normalizes schema across 100s of models incl. Anthropic, Gemini | https://openrouter.ai/api/v1 | No | [A] |
| vLLM (self-host) | Yes (OpenAI-compatible server, port 8000) | local | No | [A] |
| Ollama (local) | Yes (partial — chat/completions, vision) | localhost:11434/v1 | No | [A] |
| **YandexGPT / Yandex AI Studio** | **Yes** — OpenAI-compatible Completions API; **streaming + tool calling supported** | https://llm.api.cloud.yandex.net/v1 (needs folder id) | No | [A] |
| **GigaChat (Sber)** | **NO native OpenAI compatibility** — different request/response format | gigachat.devices.sberbank.ru/api/v1 (native) | **YES — adapter** (`gpt2giga`, `gigachat-adapter`) | [A] |

Sources: OpenRouter (https://openrouter.ai/docs/quickstart ,
https://openrouter.ai/docs/api/reference/overview) [A]; vLLM/Ollama
(https://docs.ollama.com/api/openai-compatibility , https://docs.litellm.ai/docs/providers/openai_compatible) [A];
YandexGPT (https://yandex.cloud/en/docs/ai-studio/concepts/openai-compatibility — base_url
https://llm.api.cloud.yandex.net/v1, streaming + tool calls supported;
https://github.com/yandex-cloud/yandex-ai-studio-sdk) [A];
GigaChat NOT native (https://github.com/ai-forever/gpt2giga — "redirects requests sent to OpenAI or
Anthropic APIs to GigaChat API" because GigaChat's native format differs;
https://docs.litellm.ai/docs/providers/gigachat ; https://github.com/antonko/gigachat-adapter) [A].

### Conclusion on per-provider work

- **Build ONE OpenAI-compatible ingress.** It covers OpenAI, Azure, OpenRouter, vLLM, Ollama, and —
  importantly for RU — **YandexGPT** out of the box.
- **GigaChat is the one RU provider that needs an adapter** (its API is not OpenAI-shaped). Two
  options: (a) ship a thin GigaChat adapter ourselves, or (b) rely on the existing OSS proxies
  (`gpt2giga` / `gigachat-adapter`) / let LiteLLM's GigaChat provider handle translation. Don't build
  generic per-provider adapters — just this one (plus optionally Anthropic Messages format if a
  customer insists, though OpenRouter/LiteLLM already normalize that).
- Caveat: "OpenAI-compatible" ≠ feature-identical. Edge differences exist (some providers limit
  certain params, JSON-mode, tool-call quirks). For a masking gateway this is low-risk because we
  mostly pass messages through; but tool/function-calling payloads need masking-aware handling
  regardless of provider (covered in DD on tool-call tokenization).

---

## 5. Ranked recommendation for our case (privacy-first, 152-ФЗ, key+data stay with customer)

**Rank 1 — Self-hosted, OpenAI-compatible reverse proxy deployed INSIDE the customer perimeter
(default product).**
- Why: one-line `base_url` change → language-agnostic, minimal integration; PII masked locally
  (`pre_call`) so **nothing transits our cloud**; provider key is a **local secret we never see**;
  proven by LiteLLM+Presidio, Portkey hybrid data-plane, and RU's red_mad_router. [A]
- Deliver as a Docker/Helm artifact (so it doubles as a **sidecar** topology in k8s).
- Detection/masking engine: embed Presidio-style local detection (+ our RU-specific detectors),
  reversible token vault kept local (in-process or local Redis), output parsing to re-identify on
  response. [A]

**Rank 2 — In-process SDK (offered alongside, for latency-critical / single-language teams).**
- Why: strongest privacy (PII never leaves the process) + zero network hop. Precedent: LiteLLM
  Python SDK, Presidio-as-library. Cost: one SDK per language → start with Python (+ TS/Go later). [A]

**Rank 3 — Optional Portkey-style "control plane" — but keep it OFFLINE-CAPABLE and on-prem-able.**
- If we want a management dashboard/analytics, copy Portkey's split: config/metrics only, **prompt
  content + responses never leave the customer perimeter**, gateway keeps running if the control
  plane is unreachable. For strict 152-ФЗ, offer a fully on-prem control plane (no vendor cloud at
  all). [A]

**Reject — SaaS reverse-proxy (current design) and TLS-MITM egress proxy as defaults.**
- SaaS proxy violates both core constraints (we'd hold the key; PII leaves perimeter pre-masking).
- TLS-MITM is the only zero-code/all-language option but weakens TLS, breaks on cert pinning, and is
  ops-heavy — opt-in niche only. [C]

**Provider strategy:** one OpenAI-compatible ingress (covers OpenAI/Azure/OpenRouter/vLLM/Ollama/
**Yandex**) + a single **GigaChat adapter** for the one RU provider that isn't OpenAI-shaped.

---

## 6. Open questions / uncertainty ledger

- Skyflow's exact "no-vendor-transit, in-customer-VPC" mode is under-documented publicly — confirm
  whether their private-cloud SKU truly avoids data transit, for competitive positioning. [B, low conf]
- Yandex AI Studio OpenAI-compat doc was behind a CAPTCHA on direct fetch; streaming + tool-calling
  support confirmed via secondary + SDK repo, but the *exact unsupported-param list* not captured —
  verify against the live doc before committing tool-call masking specifics. [A on support, gap on exclusions]
- GigaChat: decide build-vs-reuse for the adapter (our own thin proxy vs LiteLLM's provider vs
  `gpt2giga`). Licensing/maintenance implications are the other agent's lane.
- Tool/function-calling masking across providers (args contain PII) is provider-sensitive even under
  "OpenAI-compatible" — cross-reference DD on tool-call tokenization.
