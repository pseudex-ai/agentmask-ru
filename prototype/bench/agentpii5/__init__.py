"""AgentPII-RU v5 — tool-result-first, the FORM on every hop, a live agent.

v4 asked one question: did the gateway change what the agent DID (three arms,
paired levels, TOST). v5 keeps that question and its harness untouched — this
package IMPORTS `bench.agentpii4` the way v4 imports v3, and never edits it —
and adds the questions v4 was structurally blind to: the form of every value on
every hop INSIDE the gateway arm, the tool-result leg as the base loop, memory,
RAG, documents, and a calibrated judge that sees the customer's view.

`contracts.py` is the normative file: every dataclass, enum, metric name and
feature name the six components build against. `CHECKLIST.md` is the
conformance walk. `briefs/` are the per-component orders. Read
`docs/tz-agentpii5.md` before changing any of them.

The private benchmark is never published; nothing here goes to `public/`.
"""
