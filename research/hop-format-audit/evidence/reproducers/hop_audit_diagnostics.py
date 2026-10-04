"""Additional evidence counts; use recorded observations, never model calls."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0,'/private/tmp')
import hop_audit_extract as audit
from bench.agentpii5 import metrics, observe, records, report

all_obs=[]; diagnostic={}; per_case=[]
for label,path in audit.RUNS.items():
 run=report.run_id_of(path)
 triples=records.read_rows(records.run_file(path,run,'<run>.triples.jsonl'))
 keys={(r['case_id'],r['repeat']) for r in triples if r['status']=='complete'}
 selected=[o for o in report.v5_observations(path,()).observations if (o.case.base.id,o.repeat) in keys]
 all_obs.extend(selected)
 for o in selected:
  per_case.append({'case_id':o.case.base.id,'repeat':o.repeat,'source':label,'behaviour':o.case.behaviour,'metrics':audit.lines([o]),'hop_statuses':dict(Counter(f'{h.hop.kind}/{h.hop.owner}/{h.status}' for h in o.hops)),'manual_review':'not_reviewed'})
 for r in records.read_rows(records.run_file(path,run,'<run>.arms.jsonl')):
  casefile=audit.OUT/'cases'/f"{r['case_id']}.md"
  if casefile.exists() and r['arm']!='I' and (r['case_id'],r['repeat']) in keys:
   filename=audit.OUT/'cases'/f"{r['case_id']}.controls.{r['arm']}.json"
   audit.write_json(filename,r)
for owner,rows in metrics.by_axis(all_obs,'hop_owner').items():
 diagnostic[owner]={'statuses':dict(Counter(h.status for o in rows for h in o.hops)), 'strict_form_with_residual':{'hits':(line:=metrics.METRIC_FUNCTIONS['form_hIN' if owner.startswith('IN/') else 'form_hOUT'](rows)).hits,'total':line.total+sum(h.status=='residual' for o in rows for h in o.hops)}}
declared=[(o,h) for o in all_obs for h in o.hops if h.declared and h.hop.kind=='OUT' and h.hop.owner=='tool_arg']
present=[(o,h) for o,h in declared if h.status!='absent']
good=sum(h.status=='observed' and metrics._item_value_ok(h,metrics._item_of(o,h.hop.item_id)) for o,h in present)
diagnostic['conditional_value']={'hits':good,'present_total':len(present),'declared_total':len(declared),'warning':'Diagnostic only; original end_to_end unchanged'}
chain=metrics._transitions(all_obs)
diagnostic['chain_present_total']=sum(h.status!='absent' for o,h,s in chain)
diagnostic['absent_calls_with_tool_elsewhere']=sum(any(c.name==h.hop.tool_name for c in o.run.base.calls) for o,h in declared if h.status=='absent')
diagnostic['actual_calls']=sum(len(o.run.base.calls) for o in all_obs)
diagnostic['declared_absent_example']=[{'case':o.case.base.id,'hop':records.hop_observation_to_json(h),'actual_calls':[(c.seq,c.name) for c in o.run.base.calls], 'call_turns':o.run.call_turns} for o,h in declared if h.status=='absent'][:2]
audit.write_json(audit.OUT/'diagnostics.json',diagnostic)
audit.write_json(audit.OUT/'case-index.json',per_case)
print(json.dumps(diagnostic,ensure_ascii=False,indent=2))
