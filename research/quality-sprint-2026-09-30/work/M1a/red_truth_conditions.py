"""Adversarial truth-condition checks against the EXISTING M04 prototype.

A failed requirement is an expected RED, not an interpreter/setup failure.
No engine/provider imports, no original run mutation. Fixtures are synthetic.
"""
from pathlib import Path
import sys, json
from dataclasses import replace, asdict

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'prototype'))
from bench.agentpii5.answer_restoration import answer_events, aggregate
from bench.agentpii5.contracts import MentionRecord, ModelResponse, ModelTrace
from bench.agentpii5.fixtures import _case,_item,_in_message,_run,_with_subs,_with_replies


def fixture(kind,source,canonical,fake,raw,delivered,request_index=0):
    item=_item('p1',kind,source,canonical,'person1',_in_message(0,0,len(source)))
    case=_case('truth-condition','single',(source,),(item,),())
    run=_with_replies(_with_subs(_run(case.base.id),{'p1':fake}),raw,delivered,'')
    run=replace(run,mentions=(MentionRecord('p1',0,-1,fake,request_index),),
                request_count=max(1, request_index),
                model_trace=ModelTrace((ModelResponse(1,0,0,raw,delivered),),()))
    return case,run


def run_checks():
    cases=[]
    def check(name,case,run,predicate,requirement):
        result=answer_events(case,run); summary=aggregate((result,))
        ok=bool(predicate(result,summary))
        cases.append({'name':name,'pass':ok,'requirement':requirement,
                      'events':[asdict(e) for e in result.events],
                      'text_status':result.text_status,'aggregate':asdict(summary)})
        print(('PASS' if ok else 'RED'),name)
    real='+79164021187';fake='+79990001122'
    c,r=fixture('PHONE',real,real,fake,fake+' / '+fake,real+' / '+fake)
    check('each_repeated_fake_is_local',c,r,
          lambda v,a:len(v.events)==2 and sum(e.joint_ok for e in v.events)==1 and sum(e.residual for e in v.events)==1,
          'one correct occurrence cannot hide the second unchanged fake')
    c,r=fixture('NAME','игрь','игорь','егрь','егрь','игорь')
    check('exact_copy_does_not_silently_repair_source_typo',c,r,
          lambda v,a:a.overall.joint_ok==0,
          'verbatim fake must return source literal игрь, not corrected canonical игорь; cannot pass')
    c,r=fixture('NAME','игрь','игорь','егрь','егрь','игрь')
    check('correct_literal_source_can_earn_value',c,r,
          lambda v,a:a.overall.value_ok==1,
          'actual source typo must not be charged as wrong restoration solely because canonical differs')
    c,r=fixture('PHONE',real,real,fake,fake,real,request_index=99)
    check('unmapped_push_clock_is_not_provider_provenance',c,r,
          lambda v,a:a.overall.candidates==1 and a.overall.unresolved==1 and not a.overall.joint_ok,
          'mention request_index99 vs response request1 are different clocks; no snapshot relation proves availability, so unknown not pass')
    c,r=fixture('NAME','Иванова Елена','Иванова Елена','Пахомова Ольга','П.О.','И.Е.')
    check('known_initials_not_silent_zero_denominator',c,r,
          lambda v,a:a.overall.candidates>=1,
          'known derived fake initials need candidate/provenance uncertainty or measured event, not answers_without_substitutes')
    c,r=fixture('LOC','переулок Пушкина, дом 14','переулок Пушкина, дом 14',
                'переулок Липовый, дом 21','переулок Липовый, дом 21','улица Пушкина, дом 14')
    check('street_type_is_value_identity_not_only_form',c,r,
          lambda v,a:a.overall.candidates>=1 and a.overall.value_ok==0,
          'улица and переулок are different identities; a form failure alone cannot excuse a false value pass')
    c,r=fixture('PHONE',real,real,fake,'Телефон '+fake+', заказ c-3','Телефон '+real+', заказ c-8')
    check('nonpii_id_change_never_clean_answer',c,r,
          lambda v,a:v.text_status=='changed' and not a.answer_restore_clean,
          'all raw literal gaps outside minimal written fake must be preserved')
    c,r=fixture('PHONE',real,real,fake,fake,fake)
    r=replace(r,reply_whole=real,stream_mismatch=True)
    check('actual_stream_defeats_correct_whole',c,r,
          lambda v,a:a.overall.residual==1 and not a.overall.joint_ok,
          'delivered reply is the scored boundary; whole answer is diagnostic only')
    assert not any(m=='pseudex' or m.startswith('pseudex.') for m in sys.modules)
    out=Path(__file__).parent/'RED-RESULTS.json'
    out.write_text(json.dumps({'checks':len(cases),'red':sum(not c['pass'] for c in cases),
        'source_scope':'existing unmodified M04 prototype; synthetic fixtures; not a paid-run replay',
        'cases':cases},ensure_ascii=False,indent=2)+'\n')
    print(f"truth conditions: {sum(c['pass'] for c in cases)}/{len(cases)} satisfied")
    return 1 if any(not c['pass'] for c in cases) else 0

if __name__=='__main__':raise SystemExit(run_checks())
