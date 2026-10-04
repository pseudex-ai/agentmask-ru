export const meta = {
  name: 'obscura-sprint-19',
  description: 'Offline 19-row sprint with bounded DSH implementation, independent review and explicit stage gates',
  phases: [
    { title: 'Measurement and privacy' },
    { title: 'Shared boundary' },
    { title: 'Types and projections' },
    { title: 'Full loop' },
    { title: 'Final acceptance audit' },
  ],
}

const py = 'cd prototype && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python '
const command = {
  actual: py + '-m bench.agentpii5.test_actual_hops',
  causal: py + '-m bench.agentpii5.test_causal_hops',
  frozen: py + '-m bench.agentpii5.test_frozen_oracle',
  canary: py + '-m bench.agentpii5.test_payload_canary_integration',
  report: py + '-m bench.agentpii5.test_reportjson',
  phone: py + 'test_phone_hop_form.py',
  error: py + 'test_error_echo_privacy.py',
  name: py + 'test_names_morphology.py',
  nameCase: py + 'test_name_case_regression.py',
  loc: py + 'test_location_hop_form.py',
  locNegative: py + 'test_location_form_adversarial.py',
  other: py + 'test_other_hop_forms.py',
  spokenDate: py + 'test_spoken_date_form.py',
  spokenId: py + 'test_spoken_identifier_form.py',
  stream: py + '-m bench.agentpii5.test_harness_stream',
  loop: py + 'test_loop.py',
  product: py + 'test_product.py',
  perf: py + 'test_perf_masking.py',
  wiki: 'python3 wiki/check.py',
  diff: 'git --no-pager diff --check',
}
const initial = ['M01', 'M03', 'M04', 'S01', 'E01']
const all = ['M01', 'M02', 'M03', 'M04', 'S01', 'S02', 'E01', 'E02', 'E03', 'E04', 'E05', 'E06', 'E07', 'C01', 'C02', 'C03', 'C04', 'C05', 'C06']
const stages = [
  {
    title: 'Measurement and privacy',
    work: [
      { name: 'm02', ids: ['M02'], files: ['prototype/bench/agentpii5/actual_hops.py', 'prototype/bench/agentpii5/test_actual_hops.py'], checks: [command.actual],
        context: 'M02 v11 fixed the generic-city residual false positive, but the read-only E2E found tool_chain-036 c4 can still credit identity from a generic city role. Read the M02 v10/v11 review evidence. Keep residual orthogonal to typed identity, projection and value version.' },
      { name: 's02', ids: ['S02'], files: ['prototype/bench/agentpii5/harness.py', 'prototype/bench/agentpii5/payload_canaries.py', 'prototype/bench/agentpii5/test_payload_canary_integration.py', 'prototype/bench/agentpii5/test_reportjson.py'], checks: [command.canary, command.report],
        context: 'The real runner creates no construction-time canary/neighbor manifest, so saved 450 triples are unmeasured. read_captures uses the 4 MiB row cap for the whole file; duplicate case/repeat rows can double-count. Fix the real offline path and preserve NOT_MEASURED for old archives.' },
    ],
    regression: [command.actual, command.canary, command.report, command.diff],
  },
  {
    title: 'Shared boundary',
    work: [
      { name: 'e02', ids: ['E02'], files: ['prototype/pseudex/redact.py', 'prototype/pseudex/vault.py', 'prototype/test_phone_hop_form.py', 'prototype/test_argument_form.py'], checks: [command.phone, py + 'test_argument_form.py'],
        context: 'Read-only E2E reproduced minted +7 PHONE plus one agent digit: both OUT paths replace only the prefix and corrupt the real number; the 8-prefixed analogue leaves a fake at the tool. Add RED for extended and abbreviated runs, plus ordinary-number negatives. Never invent a real value or pass a known fake silently.' },
    ],
    regression: [command.phone, command.error, command.loop, command.diff],
  },
  {
    title: 'Types and projections',
    work: [
      { name: 'name', ids: ['E03', 'C05'], files: ['prototype/pseudex/morph_names.py', 'prototype/test_names_morphology.py', 'prototype/test_name_case_regression.py', 'prototype/test_name_subject_form.py'], checks: [command.name, command.nameCase, py + 'test_name_subject_form.py'],
        context: 'Read memory_anaphora-045 and search_rank-000. Separate gender at mint, canonical identity and reverse morphology. Reproduce the broad NAME random-mint failure with saved seed/state, or leave C05 open; preserve working female-name controls.' },
      { name: 'loc', ids: ['E04', 'E05', 'E06'], files: ['prototype/pseudex/morph_places.py', 'prototype/pseudex/vault.py', 'prototype/test_location_hop_form.py', 'prototype/test_location_form_adversarial.py', 'prototype/test_derived_forms.py'], checks: [command.loc, command.locNegative, py + 'test_derived_forms.py'],
        context: 'Read tool_chain-017, prompt_rule-026, memory_anaphora-119 and long_support-027. One address owner, selected components and current sender form; same street in two addresses cannot select another house, and a missing apartment is not added. Preserve value versions and scope.' },
      { name: 'forms', ids: ['C01', 'C02'], files: ['prototype/pseudex/date_form.py', 'prototype/pseudex/spoken.py', 'prototype/pseudex/ru_pii.py', 'prototype/test_other_hop_forms.py', 'prototype/test_spoken_date_form.py', 'prototype/test_spoken_identifier_form.py'], checks: [command.other, command.spokenDate, command.spokenId],
        context: 'Cover all ten v5 types at applicable IN/OUT boundaries with positives, negatives and cross-type ambiguity. Include supported spoken/written and Unicode/noise transformations. Unsupported forms stay explicit; PHONE green does not close another type.' },
      { name: 'quote', ids: ['C04'], files: ['prototype/pseudex/redact.py', 'prototype/test_hard_cases.py', 'prototype/test_other_hop_forms.py'], checks: [py + 'test_hard_cases.py', command.other],
        context: 'Read long_support-027 in context. Distinguish ordinary entity mention and metalinguistic quote without blanket quote exemption. Check summary and template separately. Follow OD-2 for unresolved intent; invent no new refusal policy.' },
    ],
    regression: [command.name, command.loc, command.other, command.spokenDate, command.spokenId, command.error, command.diff],
  },
  {
    title: 'Full loop',
    work: [
      { name: 'chains', ids: ['E07'], files: ['prototype/bench/agentpii5/harness.py', 'prototype/bench/agentpii5/test_harness_stream.py', 'prototype/test_loop.py'], checks: [command.stream, command.loop],
        context: 'Check actual A→B tool edges, retries, corrections, memory and two entities across four boundaries. Separate value transfer from agent action choice and missing provenance. Do not demand identical turn numbers.' },
      { name: 'transport', ids: ['C03', 'C06'], files: ['prototype/pseudex/proxy.py', 'prototype/pseudex/service.py', 'prototype/test_product.py', 'prototype/test_perf_masking.py', 'prototype/bench/agentpii5/test_harness_stream.py'], checks: [command.product, command.perf, command.stream],
        context: 'Verify nested JSON, scalar types, escaping, chunks and choice parity, vault persistence, tenant/conversation isolation, cache, and both proxy/sidecar paths. Fix a resource threshold before comparison. No new leak, wrong identity or false mask.' },
    ],
    regression: [command.actual, command.canary, command.phone, command.name, command.loc, command.other, command.stream, command.loop, command.product, command.perf, command.wiki, command.diff],
  },
]
const rules = 'Work only in /Users/igor/Projects/Obscura-hop-audit. Read the exact IDs in docs/plan-hop-form-before-450.md and their execution contract in docs/plan-hop-form-execution.md; those specs are authoritative. Read current PROGRESS and cited literal dossiers/reviews. Do not touch the main Obscura tree, paid 450/live provider, secrets, child agents, merge, push or deploy. Preserve unrelated changes and assertions/denominators. No speculative policy. Use the existing prototype/.venv and PYTHONDONTWRITEBYTECODE=1. Report exact paths, commands, exit codes and before/after evidence. A green local test is not a new 450 result.'
const schema = {
  type: 'object', required: ['rows', 'commands', 'scopeClean'], properties: {
    rows: { type: 'array', items: { type: 'object', required: ['id', 'verdict', 'resolution', 'evidence', 'gap'], properties: {
      id: { type: 'string' }, verdict: { enum: ['PASS', 'REJECT', 'UNKNOWN'] },
      resolution: { enum: ['FIX', 'NO_CHANGE', 'UNRESOLVED'] },
      evidence: { type: 'array', items: { type: 'string' } }, gap: { type: 'string' },
    } } },
    commands: { type: 'array', items: { type: 'object', required: ['command', 'exitCode', 'summary'], properties: {
      command: { type: 'string' }, exitCode: { type: 'integer' }, summary: { type: 'string' },
    } } },
    scopeClean: { type: 'boolean' },
  },
}
function passes(report, ids, required) {
  if (report === null || report.scopeClean !== true || !Array.isArray(report.rows) || report.rows.length !== ids.length || !Array.isArray(report.commands)) return false
  for (const id of ids) {
    const matches = report.rows.filter(row => row.id === id)
    if (matches.length !== 1 || matches[0].verdict !== 'PASS' || matches[0].resolution === 'UNRESOLVED' || matches[0].gap !== '' || matches[0].evidence.length < 2) return false
  }
  for (const item of required) {
    if (!report.commands.some(record => record.command === item && record.exitCode === 0 && record.summary.length > 0)) return false
  }
  return true
}

phase('Measurement and privacy')
const baselineCommands = [command.actual, command.causal, command.frozen, command.error, command.phone]
const baselineScope = 'This is a regression check of the five bounded ACCEPTED_FIX decisions in PROGRESS, not a new decision on the entire 19-row matrix. M01: verify actual event/call/field/entity/version binding and moved-action/repeat/future controls; changed v11 aggregate counts from open M02 are evidence to report, not by themselves an M01 regression. M03: verify unknown carrier prevents optimistic attribution and the archived 0/450 model_trace stays explicitly unmeasured; do not require a new paid chronology run. M04: verify frozen oracle, content-sensitive digest and wrong-gateway mutants; archived 0/69 LOC repair witnesses stay explicitly unmeasured. S01: verify the seven refused call/result bindings, no real PHONE cut, no wrong-person substitution and ordinary-number/foreign-conversation negatives; the documented bare result with no conversation provenance is outside this accepted repair. E01: verify valid warm two-request PHONE notation and marker targeting; malformed +8/++ belongs to open C02. Reject any regression within these accepted scopes. Report every known limitation in evidence and keep it open under its assigned item; do not call it newly fixed. A PASS gap must be empty only for the bounded accepted scope.'
const baseline = await agent(rules + '\nRead-only preflight. ' + baselineScope + ' Run these focused controls and report each command and exit code: ' + baselineCommands.join(' | ') + '. Return exactly one row per ID. Include git status and report whether any conflicting writer is active.', {
  label: 'baseline-five', model: 'deepseek-flash', writes: [], schema,
})
if (!passes(baseline, initial, baselineCommands)) return { status: 'BLOCKED', stage: 'preflight', accepted: [], baseline }

const accepted = [...initial]
const evidence = [{ package: 'baseline-five', report: baseline }]
for (const stage of stages) {
  phase(stage.title)
  for (const work of stage.work) {
    let feedback = 'First cycle: use the latest independent review, not an old candidate claim.'
    let done = false
    for (let cycle = 1; cycle <= 3; cycle += 1) {
      const brief = ' Package=' + work.name + '; IDs=' + work.ids.join(',') + '; cycle=' + cycle + '/3; allowed files=' + work.files.join(',') + '; focused commands=' + work.checks.join(' | ') + '; current blocker=' + work.context + '; previous feedback=' + feedback
      const author = await agent(rules + '\nRole: implementer. First reproduce a literal RED on the real path, or prove no change is needed with independent positive and negative controls. Implement one shared mechanism for this package, run focused commands, and report one row per ID with resolution FIX or NO_CHANGE. Mark UNKNOWN/UNRESOLVED whenever a clause is unproved. Do not edit PROGRESS to claim acceptance.' + brief, {
        label: work.name + '-author-' + cycle, model: 'deepseek-flash', writes: work.files, schema,
      })
      if (!passes(author, work.ids, work.checks)) {
        feedback = 'Author has not demonstrated every row and focused command: ' + JSON.stringify(author)
        evidence.push({ package: work.name, cycle, author, verdict: 'REJECT' })
        continue
      }
      const required = work === stage.work[stage.work.length - 1] ? [...work.checks, ...stage.regression] : work.checks
      const validation = await agent(rules + '\nRole: independent offline validator. No repository edits; temporary test logs under /private/tmp are allowed. Run EXACTLY these commands from the worktree root and report each real exit code and the temporary stdout/stderr log path: ' + required.join(' | ') + '. Inspect actual diff for out-of-scope edits, weakened assertions, changed denominators and engine/observer conflation. Return one row per ID; a missing command or unproved clause is UNKNOWN. Author report: ' + JSON.stringify(author) + brief, {
        label: work.name + '-validate-' + cycle, model: 'deepseek-flash', writes: [], schema,
      })
      if (!passes(validation, work.ids, required)) {
        evidence.push({ package: work.name, cycle, author, validation, verdict: 'REJECT' })
        feedback = 'Independent validation failed: ' + JSON.stringify(validation)
        continue
      }
      const review = await agent(rules + '\nRole: independent adversarial reviewer. No repository edits. Read the actual diff, every acceptance clause, and the validator test logs; independently rerun at least one relevant negative or counterexample. Attack identity, residual, leak, wrong form, overmask and adjacent types as relevant. Return one row per ID. Any untested clause is UNKNOWN, not PASS. Author report: ' + JSON.stringify(author) + '. Validator report: ' + JSON.stringify(validation) + brief, {
        label: work.name + '-review-' + cycle, model: 'deepseek-flash', writes: [], schema,
      })
      const valid = passes(review, work.ids, [])
      evidence.push({ package: work.name, cycle, author, review, validation, verdict: valid ? 'CANDIDATE_ACCEPTED' : 'REJECT' })
      if (valid) {
        accepted.push(...work.ids)
        done = true
        break
      }
      feedback = 'Independent review=' + JSON.stringify(review) + '; validation=' + JSON.stringify(validation)
    }
    if (!done) return { status: 'BLOCKED', stage: stage.title, package: work.name, accepted, evidence, reason: 'three cycles without all rows and stage gate passing' }
  }
}

phase('Final acceptance audit')
const panels = [
  ['M01', 'M02', 'M03', 'M04', 'S01', 'S02', 'E01'],
  ['E02', 'E03', 'E04', 'E05', 'E06', 'E07'],
  ['C01', 'C02', 'C03', 'C04', 'C05', 'C06'],
]
const audits = await parallel(panels.map((ids, index) => () => agent(rules + '\nRole: independent final panel ' + (index + 1) + '/3. No repository edits. Inspect the final diff, current tests and every original acceptance clause for these IDs: ' + ids.join(',') + '. Return exactly one row per ID with at least two concrete pieces of evidence and an empty gap only for PASS. Recheck old accepted rows for regressions. Do not infer PASS from previous agent claims.', {
  label: 'final-panel-' + (index + 1), model: 'deepseek-flash', writes: [], schema,
})))
if (!audits.every((report, index) => passes(report, panels[index], []))) return { status: 'BLOCKED', stage: 'Final acceptance audit', accepted, audits, evidence }

const finalCommands = [command.actual, command.causal, command.frozen, command.canary, command.report, command.phone, command.error, command.name, command.nameCase, command.loc, command.locNegative, command.other, command.spokenDate, command.spokenId, command.stream, command.loop, command.product, command.perf, command.wiki, command.diff]
const integration = await agent(rules + '\nRole: final read-only integration validator. Run EXACTLY these offline commands from the worktree root and record real exit codes: ' + finalCommands.join(' | ') + '. Inspect the full diff for scope, authorship, ten-type coverage, proxy/sidecar parity, no privacy regression and honest before/after denominators. Return one row with id INTEGRATION, resolution NO_CHANGE, and concrete evidence for global readiness. No paid 450.', {
  label: 'final-integration', model: 'deepseek-flash', writes: [], schema,
})
if (!passes(integration, ['INTEGRATION'], finalCommands)) return { status: 'BLOCKED', stage: 'Final acceptance audit', accepted, audits, integration, evidence }

let reportFeedback = 'First reporting cycle.'
let finalReport = null
for (let cycle = 1; cycle <= 3; cycle += 1) {
  const reporter = await agent(rules + '\nRole: sprint recorder. Update only research/hop-format-audit/PROGRESS.md after the three independent panels and integration gate passed. Record 19 distinct ACCEPTED_FIX or ACCEPTED_NO_CHANGE outcomes with exact local evidence, separate observer changes from engine changes, and state that no new 450 was run. Do not invent cost or metrics; refer to the workflow cost ledger when exact accounting is unavailable. Run python3 wiki/check.py and git --no-pager diff --check. Return one REPORT row. Panel rows: ' + JSON.stringify(audits.map(report => report.rows)) + '. Integration command exits: ' + JSON.stringify(integration.commands.map(record => ({ command: record.command, exitCode: record.exitCode }))) + '. Previous feedback: ' + reportFeedback, {
    label: 'final-report-author-' + cycle, model: 'deepseek-flash', writes: ['research/hop-format-audit/PROGRESS.md'], schema,
  })
  if (!passes(reporter, ['REPORT'], [command.wiki, command.diff])) {
    reportFeedback = 'Recorder did not prove the report: ' + JSON.stringify(reporter)
    continue
  }
  const checker = await agent(rules + '\nRole: independent final report reviewer. Do not edit files. Inspect the actual PROGRESS.md diff against all 19 accepted rows, the original matrix and the workflow evidence. Reject missing rows, invented before/after numbers, absent denominators, inaccurate cost claims or any statement that a new 450 ran. Run python3 wiki/check.py and git --no-pager diff --check. Return one REPORT row with concrete evidence. Recorder report: ' + JSON.stringify(reporter), {
    label: 'final-report-review-' + cycle, model: 'deepseek-flash', writes: [], schema,
  })
  if (passes(checker, ['REPORT'], [command.wiki, command.diff])) {
    finalReport = { reporter, checker }
    break
  }
  reportFeedback = 'Independent report review rejected: ' + JSON.stringify(checker)
}
if (finalReport === null) return { status: 'BLOCKED', stage: 'Final acceptance audit', accepted, audits, integration, evidence, reason: 'three reporting cycles failed' }
return { status: 'AUTONOMOUS_OFFLINE_19_OF_19', accepted: all, audits, integration, finalReport, evidence, note: 'Offline DSH evidence only; no paid 450, merge, push or deployment.' }
