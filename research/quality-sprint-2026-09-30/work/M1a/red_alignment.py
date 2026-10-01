"""Adversarial alignment REDs for M04 v2-dev WITH explicit disclosure evidence.

Exercises the alignment path (which only runs when provenance is proved).
Synthetic, no engine/provider, no raw runs.
"""
import hashlib, json, sys
from dataclasses import replace
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'prototype'))
from bench.agentpii5.answer_restoration import (AnswerEvidence, DisclosureProof,
                                                answer_events, aggregate)
from bench.agentpii5.contracts import MentionRecord, ModelResponse, ModelTrace
from bench.agentpii5.fixtures import _case,_item,_in_message,_run,_with_subs,_with_replies

REAL='+79164021187'; FAKE='+79990001122'
def sha(t): return hashlib.sha256(t.encode()).hexdigest()

def evidence(item_id, real, fake):
    return DisclosureProof(f'proof-{item_id}',1,item_id,'message',0,real,fake,
                           0,len(real),0,len(fake),sha(real),sha(fake))

def fixture(kind, source, canonical, fake, raw, delivered, item_id='p1', identity='person1'):
    item=_item(item_id,kind,source,canonical,identity,_in_message(0,0,len(source)))
    case=_case('align','single',(source,),(item,),())
    run=_with_replies(_with_subs(_run(case.base.id),{item_id:fake}),raw,delivered,'')
    run=replace(run,mentions=(MentionRecord(item_id,0,-1,fake,1),),request_count=1,
                model_trace=ModelTrace((ModelResponse(1,0,0,raw,delivered),),()))
    return case,run,AnswerEvidence((evidence(item_id,source,fake),))

def score(c,r,e): return aggregate((answer_events(c,r,evidence=e),)).overall

def main():
    cases=[]
    def add(label,line): cases.append({'label':label,'candidates':line.candidates,'measurable':line.measurable,
        'value_ok':line.value_ok,'form_ok':line.form_ok,'joint_ok':line.joint_ok,
        'unresolved':line.unresolved,'statuses':dict(line.statuses)})

    # 1. Repeated identical fake, one restored, one left fake (per-occurrence local).
    c,r,e=fixture('PHONE',REAL,REAL,FAKE,FAKE+' / '+FAKE,REAL+' / '+FAKE)
    add('repeated-fake-one-restored',score(c,r,e))

    # 2. Insertion of an extra literal around the token (gap fidelity).
    c,r,e=fixture('PHONE',REAL,REAL,FAKE,'до '+FAKE+' после','до X '+REAL+' Y после')
    add('insertion-around-token',score(c,r,e))

    # 3. Deletion of surrounding literal.
    c,r,e=fixture('PHONE',REAL,REAL,FAKE,'до '+FAKE+' после',REAL)
    add('deletion-around-token',score(c,r,e))

    # 4. Shared suffix: surrounding literal is identical on both sides of two values.
    c,r,e=fixture('PHONE',REAL,REAL,FAKE,'префикс '+FAKE+' хвост','префикс '+REAL+' хвост')
    add('shared-surrounding-literals',score(c,r,e))

    # 5. Wrong real elsewhere must not rescue this occurrence.
    c,r,e=fixture('PHONE',REAL,REAL,FAKE,FAKE+'; старый '+REAL,'+79261234567; старый '+REAL)
    add('wrong-real-elsewhere',score(c,r,e))

    # 6. Two identical fakes collapse into one real (crossing/overlap).
    c,r,e=fixture('PHONE',REAL,REAL,FAKE,FAKE+' '+FAKE,REAL)
    add('two-fakes-collapse-to-one-real',score(c,r,e))

    out=Path(__file__).parent/'RED-ALIGNMENT.json'
    out.write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
    for c in cases: print(c['label'],'->',c)
    print(f'{len(cases)} adversarial alignment cases recorded')
    return 0

if __name__=='__main__':raise SystemExit(main())
