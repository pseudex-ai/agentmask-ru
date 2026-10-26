# Integration sign-off — per-agent policy (historical, NOT current acceptance)

Owner-decision correction: F4 was explicitly rejected. Pseudex is a gateway
orchestrated by the trusted customer backend: configurable attribution → opaque
agent_key → policy_id, else instance default. Do not reintroduce an org axis or
mandatory org policy ownership as a pilot blocker. See BUILD-BRIEF-2h.md and
archive user seq 7331, 8208/8217, 9989; assistant withdrawal seq 9991.
This document's old green/red claims below are historical, not renewed evidence.

Consolidated result of tracks T1–T6 and the adversarial review (T6). All engine
changes are UNCOMMITTED in `.claude/worktrees/must-core`; the owner merges.

## Green (verified this run)

- T6 adversarial review: 15 findings documented in
  `docs/must-core/20-policy-adversarial-review.md`.
- F1 (High, policy spoof via body): `body:user`/`body:metadata.agent_id` removed
  from `DEFAULT_EXTRACTORS`; `test_agent_policy.py` green.
- F2 (High, cache leak): `policy_source` added to `_cache_epoch` in
  `envelope.py`; regression in `test_agent_policy_http.py` (src-a vs src-b) green.
- F3 (Medium, proxy block pre-check): resolved policy + rules/source passed to
  `management.blocked_category` in `proxy.py`; syntax OK.
- F5 (Medium, secret label mismatch): `CARD_VERIFICATION_CODE`/`ISSUER_OTP` added
  to secret sets in `agentpolicy.py`, `actions.py`, `custom.py`; tests green.
- T5 multi-agent isolation: `test_agent_isolation.py` — 8-agent matrix, clean.
- T2 backend policy write path: `tests/test_pseudex_policies.py` 48 passed.
- Core engine no-regression: `test_loop.py` (round-trip), `test_persona_defects.py`
  (10/10), `test_overmasking.py` (99.5% precision, ≥98.9% certified).

## Red / not done (honest)

- F4 — WITHDRAWN by owner; not a remaining finding or release requirement.
- F6/F7 (Medium, audit of mutations / suppressed spans) — not implemented.
- F8/F9 (Medium/Low, perf + rate-limit/body-cap on `/policies*`) — not done.
- T1 platform policy screen — partial (`src/app/api/policies.ts` only; screen +
  Playwright e2e not finished).
- T3 real-PII corpus Sept 2026+ — subagent failed, no catalog.
- T4 real-dialogue replay with PII-in-tools — not run (blocked on T3).

## File manifest (uncommitted)

Engine: `prototype/pseudex/{agentpolicy,envelope,actions,custom,proxy}.py`
Tests:  `prototype/{test_agent_policy,test_agent_policy_http}.py` (edited),
         `prototype/test_agent_isolation.py` (new)
Docs:   `docs/must-core/20-policy-adversarial-review.md` (new)
Backend: `doubleup-backend-pilot/{routes,services}/pseudex_policies.py`,
         `tests/test_pseudex_policies.py`, `user_api_with_remote_graphs.py`
Frontend: `doubleup-frontend-pilot/src/app/api/policies.ts`
