"""Recompute completed-only metrics and export literal case evidence, without model calls."""
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, '/Users/igor/Projects/Obscura-v5-codex/prototype')
from bench.agentpii5 import metrics, records, report

OUT = Path('/private/tmp/hop-audit-evidence')
RUNS = {
 'A': Path('/private/tmp/v5-quarter-deepseek-nojudge-clean-20260926'),
 'B': Path('/private/tmp/v5-quarter-deepseek-missing-20260926-r2'),
 'C': Path('/private/tmp/v5-quarter-deepseek-remaining-20260926'),
 'D': Path('/private/tmp/v5-quarter-deepseek-final3-20260926'),
}
NAMES = ('leak','coverage','residual','end_to_end','form_hIN','form_hOUT','chain_value','chain_form','consistency','memory_consistency','multi_all_out','overmask','out_absent')

def lines(observations):
 return {name: {'hits': (line:=metrics.METRIC_FUNCTIONS[name](observations)).hits, 'total':line.total,'rate':line.rate} for name in NAMES}

def write_json(path, data):
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def case_text(one, label):
 chunks=[f'# {one.case.base.id} | source {label} | repeat {one.repeat}',
         'Synthetic benchmark evidence. Verbatim serialized fields; no inferred verdicts.',
         '## Case specification',json.dumps(asdict(one.case),ensure_ascii=False,indent=2),
         '## Actual gateway arm (written/restored calls, tool results, answers, mentions)',
         json.dumps(asdict(one.run),ensure_ascii=False,indent=2),
         '## Recorded observer hops',json.dumps([records.hop_observation_to_json(h) for h in one.hops],ensure_ascii=False,indent=2)]
 return '\n\n'.join(chunks)+'\n'

def main():
 OUT.mkdir(exist_ok=True)
 (OUT/'cases').mkdir(exist_ok=True)
 (OUT/'bridge').mkdir(exist_ok=True)
 combined=[]; manifest={}; sources={}; seen=set(); hashes={}
 for label,path in RUNS.items():
  run=report.run_id_of(path)
  triples=records.read_rows(records.run_file(path,run,'<run>.triples.jsonl'))
  keys={(r['case_id'],r['repeat']) for r in triples if r['status']=='complete'}
  assert not (seen & keys),(label,seen & keys)
  seen |= keys
  half=report.v5_observations(path,())
  selected=[o for o in half.observations if (o.case.base.id,o.repeat) in keys]
  assert len(selected)==len(keys)
  combined.extend(selected)
  sources.update({o.case.base.id:label for o in selected})
  manifest[label]={'path':str(path),'run_id':run,'complete':len(keys),'raw_observations':len(half.observations),'excluded_observation_ids':[o.case.base.id for o in half.observations if (o.case.base.id,o.repeat) not in keys], 'metrics':lines(selected), 'ledger_usd':report._ledger_total(records.run_file(path,run,'<run>.spend.tsv'))}
  for file in sorted(path.glob('*')):
   if file.is_file() and file.suffix in ('.json','.jsonl','.tsv'):
    hashes[str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
 assert len(combined)==450
 buckets=metrics.by_axis(combined,'hop_owner')
 forms={owner:lines(rows)['form_hIN' if owner.startswith('IN/') else 'form_hOUT'] for owner,rows in buckets.items()}
 out=[h for o in combined for h in o.hops if h.hop.kind=='OUT' and h.hop.owner=='tool_arg' and h.declared]
 chain=metrics._transitions(combined)
 cohorts={
   'declared_tool_arg_status':dict(Counter(h.status for h in out)),
   'chain_target_status':dict(Counter(h.status for _,h,_ in chain)),
   'out_form_differs':dict(Counter(d for o in combined for h in o.hops if h.hop.kind=='OUT' and h.verdict for d in h.verdict.differs)),
 }
 write_json(OUT/'audit.json',{'runs':manifest,'unique_complete':len(combined),'metrics':lines(combined),'forms':forms,'diagnostics':cohorts,'source_sha256':hashes})
 # Deterministic contrasting samples: different families and failure signals, plus good hops.
 predicates={
  'names':lambda o:any(h.pii_type=='NAME' and h.verdict and not h.verdict.same for h in o.hops),
  'numbers':lambda o:any(h.pii_type in ('PHONE','DOB','SNILS','CARD','PASSPORT','INN') and h.hop.kind=='OUT' and (h.status=='residual' or h.verdict and not h.verdict.same) for h in o.hops),
  'chains':lambda o:o.case.base.id.startswith(('tool_chain-','long_order-','long_support-')) and any(h.pii_type=='LOC' or h.hop.source_hop>=0 for h in o.hops),
  'skeptic':lambda o:o.case.behaviour in ('memory_anaphora','parallel_batch','tool_result_first') or any(h.status=='unmasked' for h in o.hops),
 }
 groups={}; used=set()
 for group,predicate in predicates.items():
  selected=[]; families=Counter()
  for o in sorted(combined,key=lambda o:hashlib.sha256((group+o.case.base.id).encode()).hexdigest()):
   family=o.case.base.id.rsplit('-',1)[0]
   if o.case.base.id not in used and predicate(o) and families[family]<2:
    selected.append(o);used.add(o.case.base.id);families[family]+=1
   if len(selected)==6:break
  groups[group]=[o.case.base.id for o in selected]
  for o in selected:
   (OUT/'cases'/f'{o.case.base.id}.md').write_text(case_text(o,sources[o.case.base.id]))
 write_json(OUT/'samples.json',groups)
 print(json.dumps({'metrics':lines(combined),'forms':forms,'cohorts':cohorts,'samples':groups,'raw_vs_complete':{k:[v['raw_observations'],v['complete']] for k,v in manifest.items()}},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
