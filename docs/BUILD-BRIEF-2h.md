# 2-hour close-out brief: DoubleUp × Pseudex integration

Binding contract for finishing the pilot and reaching evidence-backed confidence
for a high-stakes client. Every track below is authoritative; do not re-plan.

## Source of truth
- Engine (feat/must-core, committed+pushed 3fed052a): /Users/igor/Projects/Obscura/.claude/worktrees/must-core
- Backend: /Users/igor/Projects/Obscura/.claude/worktrees/doubleup-backend-pilot
- Frontend: /Users/igor/Projects/Obscura/.claude/worktrees/doubleup-frontend-pilot
- Pilot harness: /Users/igor/Projects/Obscura/.claude/worktrees/doubleup-pilot
- Policy contract: docs/must-core/19-per-agent-policy-contract.md
- Already green (do NOT redo, carry forward): engine policy 29/29; container gate 8/8; backend pilot 80; UI localui 78 + browser render.

## Owner-approved architecture — already decided, do not reopen

- Pseudex is the customer's gateway, not a model of the customer's org/user hierarchy.
- Configurable attribution (header/body/LiteLLM metadata) yields an opaque
  `agent_key`; bindings map `agent_key → policy_id`, otherwise instance default.
- The customer's trusted backend orchestrates through the API and supplies the
  appropriate key. No particular `graph_id`, org structure, or mandatory key
  namespace is imposed by Pseudex.
- F4 (adding an org axis / requiring per-org policy ownership as this pilot's
  acceptance blocker) was REJECTED by the owner. Do not reintroduce the same
  requirement as a purported backend gap without a separate confirmed defect.
- Evidence: supplied session archive, human seq 7331, 8208, approval 8217, repeated
  clarification 9989; assistant explicitly withdrew F4 at seq 9991.
- JSON decoding must apply to BOTH built-in recognition and customer dictionaries.
  Leaving one on the raw wire is an incomplete implementation, not an owner
  decision or an accepted product limitation.

## Parallel tracks (independent flash agents; each returns to a reviewer)
T1  Platform policy screen (DoubleUp frontend): list/create/edit/delete policies,
    bind agent→policy, set attribution, preview. UI testing ONLY via Playwright.
    Exit: real browser E2E green + node tests + tsc.
T2  Backend policy write path: expose /policies* to the platform API, store/route
    per-agent config, forward agent id, multi-agent binding. Exit: backend tests + Playwright.
T3  Real-PII corpus Sept 2026+ (already running): Mongo + app Langfuse, PII in
    user text AND tool args/results. Exit: encrypted catalog of 5+ cases.
T4  Real dialogue replay with PII-in-tools (depends on T3): run 3–5 cases in
    none/builtin/pseudex with ignore policy; prove over-masking fix + real round-trip.
    Exit: per-case report + chat links + saved evidence.
T5  Multi-agent isolation: 10 agents, 10 policies, one per request; assert each
    agent's own ignore applies and others' do not. Exit: gate green.
T6  Security/adversarial review of /policies* + integration seams: auth, injection,
    path traversal, rate limit, secret-header refusal, error leakage. Exit: findings closed.

## Sequential spine (gates)
1. T1+T2 converge on one API contract (read doc 19) → reviewer confirms.
2. T3 → T4 (T4 blocks on T3).
3. T5 after T2 binding works.
4. T6 runs alongside; findings must be fixed before final sign-off.

## Hard invariants (HALT on any failure — never fabricate, never auto-promote)
- No raw PII / names / phones / emails / credentials / source ids in outputs or logs.
- UI verification ONLY via Playwright; no manual "looks fine".
- Real-PII round-trip proof requires the tool actually executed on a restored value.
- Over-masking fix proof: genuine PII still masked while role/year/abbreviation is not.
- No commits/pushes/MRs by agents; owner merges.
- Any gate red = report honestly, do not claim green.

## Do / Do not
- DO atomic scoped edits, run the owning suite before returning.
- DO NOT pull later work forward, skip a gate, invent data, or claim a scenario
  (multi-agent, images, streaming) you did not run.
