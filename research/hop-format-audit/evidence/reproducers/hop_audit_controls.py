"""Paired control evidence from the same 450 completed triples."""
import sys
import json
sys.path.insert(0,'/private/tmp')
import hop_audit_extract as audit
from bench.agentpii5 import report,records
from bench.agentpii4 import report as old
import testkit

# Existing v3 taxonomy lazily imports engine address morphology; record this dependency.
testkit.load_dev_bundle()

scored=[]; cases={}; manifest={}
for label,path in audit.RUNS.items():
 run=report.run_id_of(path)
 keys={(r['case_id'],r['repeat']) for r in records.read_rows(records.run_file(path,run,'<run>.triples.jsonl')) if r['status']=='complete'}
 part_cases,triples,excluded=report._load_run(path)
 chosen=[t for t in triples if (t.case_id,t.repeat) in keys]
 assert len(chosen)==len(keys)
 scored.extend(old.score_triples(part_cases,chosen));cases.update(part_cases)
for level,label in old.LEVELS:
 rows=old.comparable_triples(scored,level)
 ic=sum(bool(old._level_flag(x.ic,level)) for x in rows)
 cc=sum(bool(old._level_flag(x.cc,level)) for x in rows)
 manifest[level]={'comparable':len(rows),'IC_agree':ic,'CC_agree':cc,'effect_pp':100*(ic-cc)/len(rows) if rows else None}
audit.write_json(audit.OUT/'paired-controls.json',manifest)
print(json.dumps(manifest,ensure_ascii=False,indent=2))
