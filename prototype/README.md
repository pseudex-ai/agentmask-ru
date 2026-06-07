# Obscura — prototype

PII tokenization middleware for LLM agents. Sits between the agent and the LLM
provider as an **OpenAI-compatible reverse proxy**: real PII never reaches the
model; the client's tools still run on real values.

## Why it's framework-agnostic
Every agent framework (LangGraph, Pydantic AI, LlamaIndex, n8n, …) speaks the
OpenAI/Anthropic HTTP dialect and lets you set a custom `base_url`. We intercept
at that layer, not the framework. Integration = change one URL.

## Run the proof (no deps, no LLM)
```bash
cd prototype
python3 test_loop.py
```
Expect: the masked message has a fake phone/email, the tool call detokenizes
back to the real values, and `PASS`.

## Run the proxy
```bash
cd prototype
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OBSCURA_UPSTREAM_BASE_URL=https://api.openai.com/v1   # or a local model: http://localhost:11434/v1
export OBSCURA_UPSTREAM_KEY=sk-...                           # real provider key
uvicorn obscura.proxy:app --port 4000
```

## Integrate (the "one line")
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:4000/v1", api_key="obscura-dev")
```
The proxy logs every message it forwards upstream — confirm no real PII leaves.

## Status / scope
- [x] OpenAI `/v1/chat/completions`, non-streaming
- [x] regex detection: phone, email (zero ML)
- [x] consistent format-preserving tokens, longest-first reverse
- [x] detokenize assistant content + `tool_calls[].arguments`
- [ ] streaming (SSE) — next
- [ ] RU NER (ФИО/адрес) via Presidio + Natasha/GLiNER — next (the recall moat)
- [ ] СНИЛС/ИНН/паспорт/карта regex+checksum pack
- [ ] persistent per-customer vault in RF; Anthropic `/v1/messages` dialect
