"""AgentPII-RU v4 — «шлюз не ломает агента».

The v3 benchmark measured whether the REAL value reached a hand-written expected
argument. v4 measures whether the tool call the agent makes WITH the gateway in
the loop has the same effect as the call it makes WITHOUT it. The ground truth is
a control arm — the same scripted conversation, unmasked, against the same
stateful mock backend — and the effect is compared at three levels, never one.

Read `README.md` in this directory before changing anything; `schema.py` is the
normative file and `docs/tz-agentpii4.md` explains why it is the way it is.
"""
