"""Independent adversarial probes for G2 re-review of M1a v2-dev fixes.

Constructs fixtures independently of the parent's suite to verify the four
REQUIRED items from g2-review/REVIEW.md §5 and hunt for new false-passes.
"""
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT/'prototype'))
from bench.agentpii5.answer_restoration import (AnswerEvidence, DisclosureProof,
                                                answer_events, aggregate)
from bench.agentpii5.contracts import MentionRecord, ModelResponse, ModelTrace
from bench.agentpii5.fixtures import _case, _item, _in_message, _run, _with_subs, _with_replies

def sha(t): return hashlib.sha256(t.encode()).hexdigest()

def mk(kind, real, fake, raw, delivered, identity='person1', item_id='p1', canonical=None):
    item=_item(item_id, kind, real, canonical or real, identity, _in_message(0,0,len(real)))
    case=_case('probe','single',(real,),(item,),())
    run=_with_replies(_with_subs(_run(case.base.id),{item_id:fake}),raw,delivered,'')
    run=replace(run,mentions=(MentionRecord(item_id,0,-1,fake,1),),request_count=1,
                model_trace=ModelTrace((ModelResponse(1,0,0,raw,delivered),),()))
    proof=DisclosureProof(f'proof-{item_id}',1,item_id,'message',0,real,fake,0,len(real),0,len(fake),sha(real),sha(fake))
    return case, run, AnswerEvidence((proof,))

def ev_of(c,r,e):
    run=answer_events(c,r,evidence=e)
    agg=aggregate((run,))
    return run, agg

results=[]
def rec(name, run, agg, verdict, note=''):
    results.append({'name':name,'verdict':verdict,'note':note,
        'candidates':agg.overall.candidates,'value_ok':agg.overall.value_ok,
        'joint_ok':agg.overall.joint_ok,'residual':agg.overall.residual,
        'text_status':run.text_status,'unmapped':run.unmapped_changes,
        'unsupported':run.unsupported_spellings,
        'statuses':dict(agg.overall.statuses),
        'events':[{'raw':ev.raw_start,'delivered':ev.delivered,'status':ev.status,
                   'text':ev.delivered,'value_ok':ev.value_ok} for ev in run.events]})

def main():
    # 1. LOC positive control: verbatim correct restore -> matched.
    c,r,e=mk('LOC','улица Пушкина, дом 14','улица Липовая, дом 21',
             'улица Липовая, дом 21','улица Пушкина, дом 14')
    run,agg=ev_of(c,r,e)
    ok = agg.overall.joint_ok==1 and agg.overall.value_ok==1 and agg.overall.candidates==1
    rec('loc-positive-verbatim', run, agg, 'PASS' if ok else 'FAIL', 'expect matched')

    # 2. Wrong street type -> value_wrong.
    c,r,e=mk('LOC','переулок Пушкина, дом 14','переулок Липовый, дом 21',
             'переулок Липовый, дом 21','улица Пушкина, дом 14')
    run,agg=ev_of(c,r,e)
    ok = agg.overall.value_ok==0 and agg.overall.joint_ok==0
    rec('loc-wrong-street-type', run, agg, 'PASS' if ok else 'FAIL', 'expect value_wrong')

    # 3. insertion-around-token -> value_ok + text_status=changed.
    c,r,e=mk('PHONE','+79164021187','+79990001122',
             'до +79990001122 после','до X +79164021187 Y после')
    run,agg=ev_of(c,r,e)
    ok = agg.overall.value_ok==1 and run.text_status=='changed'
    rec('insertion-around-token', run, agg, 'PASS' if ok else 'FAIL', 'expect value_ok + changed')

    # 4. Latin spelling -> unsupported_spellings >= 1, not silent zero.
    c,r,e=mk('NAME','Иванова Елена','Пахомова Ольга',
             'Pakhomova Olga','Ivanova Elena')
    run,agg=ev_of(c,r,e)
    ok = run.unsupported_spellings>=1
    rec('latin-unsupported-surfaced', run, agg, 'PASS' if ok else 'FAIL', 'expect unsupported>=1')

    # 5. Swapped-person: p1 fake restored with p2 real -> value_wrong.
    A_real='+79164021187'; A_fake='+79990001122'; B_real='+79261234567'
    c,r,e=mk('PHONE',A_real,A_fake,A_fake,B_real)
    other=replace(c.base.pii[0],id='p2',identity='person2',canonical=B_real,value=B_real)
    c=replace(c,base=replace(c.base,pii=c.base.pii+(other,)))
    run,agg=ev_of(c,r,e)
    ok = agg.overall.value_ok==0 and agg.overall.joint_ok==0
    rec('swapped-person-value-wrong', run, agg, 'PASS' if ok else 'FAIL', 'expect value_wrong (identity from source)')

    # False-pass hunt 6: boundary insertion WITHOUT gap-change flag (text_status must be changed).
    c,r,e=mk('PHONE','+79164021187','+79990001122',
             '+79990001122','X+79164021187')
    run,agg=ev_of(c,r,e)
    ok = (run.text_status=='changed') or (agg.overall.joint_ok==0)
    rec('boundary-insertion-gap-flagged', run, agg, 'PASS' if ok else 'FAIL', 'must not silently pass')

    # False-pass hunt 7: two identical real literals in delivered -> narrowed wrong.
    c,r,e=mk('PHONE','+79164021187','+79990001122',
             '+79990001122','+79164021187 +79164021187')
    run,agg=ev_of(c,r,e)
    # value_ok may be true (the literal IS present); the concern is gap-change flag:
    ok = run.text_status in ('changed','unresolved') or agg.overall.joint_ok==0
    rec('two-identical-real-literals', run, agg, 'PASS' if ok else 'FAIL', 'extra literal must not hide')

    out=Path(__file__).parent/'probes.json'
    out.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    for r in results:
        print(f"[{r['verdict']}] {r['name']}: cand={r['candidates']} value_ok={r['value_ok']} joint={r['joint_ok']} residual={r['residual']} text={r['text_status']} unmapped={r['unmapped']} unsupported={r['unsupported']}")
    fails=[r['name'] for r in results if r['verdict']=='FAIL']
    print(f"\n{len(results)-len(fails)}/{len(results)} PASS; {fails or 'no FAIL'}")
    return 1 if fails else 0

if __name__=='__main__':
    raise SystemExit(main())
