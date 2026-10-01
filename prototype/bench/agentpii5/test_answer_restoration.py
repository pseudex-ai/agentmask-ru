"""M04 evidence controls; raw outcomes never manufacture disclosure proof.

Pure unit fixtures explicitly construct provider-input captures. Legacy mention
metadata alone is UNKNOWN. This suite is not the full G2/adapter acceptance.
"""
from dataclasses import replace
import hashlib
import sys

from bench.agentpii5.answer_restoration import (
    AnswerEvidence, DisclosureProof, answer_events, aggregate, render, ESTIMATOR_VERSION,
)
from bench.agentpii5.contracts import MentionRecord, ModelResponse, ModelTrace, ToolResultRecord
from bench.agentpii5.fixtures import _case, _item, _in_message, _run, _with_subs, _with_replies, _call, _with_calls

REAL='+79164021187'
FAKE='+79990001122'


def sha(text): return hashlib.sha256(text.encode()).hexdigest()


def sample(raw=FAKE, delivered=REAL, kind='PHONE', real=REAL, fake=FAKE, canonical=None):
    """Construct capture evidence independently of the restored result."""
    item=_item('p1',kind,real,canonical or real,'person1',_in_message(0,0,len(real)))
    case=_case('m04','single',(real,), (item,), ())
    run=_with_replies(_with_subs(_run('m04'),{'p1':fake}),raw,delivered,'')
    run=replace(run,mentions=(MentionRecord('p1',0,-1,fake,1),),request_count=1,
                model_trace=ModelTrace((ModelResponse(1,0,0,raw,delivered),),()))
    proof=DisclosureProof('fixture-provider-input-1',1,'p1','message',0,real,fake,
                          0,len(real),0,len(fake),sha(real),sha(fake))
    return case,run,AnswerEvidence((proof,))


def score(case,run,evidence):
    return aggregate((answer_events(case,run,evidence=evidence),))


def main():
    failures=[];checks=0
    def check(ok,why):
        nonlocal checks
        checks+=1
        if not ok: failures.append(why)
    def rejected(c,r,e,why):
        try:answer_events(c,r,evidence=e)
        except ValueError:check(True,why)
        else:check(False,why)

    c,r,e=sample()
    s=score(c,r,e)
    check(s.overall.candidates==s.overall.joint_ok==1,'explicit whole-token capture earns restoration')
    check(s.answer_restore_clean==1,'clean answer with a token is measured')
    check(not c.hops and s.overall.candidates==1,'timetable is irrelevant')
    s=score(c,r,None)
    check(s.overall.candidates==s.overall.unresolved==1 and s.overall.joint_ok==0,'same bytes without exposure proof are UNKNOWN')
    r=replace(r,request_count=99,mentions=(MentionRecord('p1',0,-1,FAKE,99),))
    check(score(c,r,None).overall.unresolved==1,'consistent push99/provider1 clocks do not establish availability')
    check(score(c,r,e).overall.joint_ok==1,'explicit provider proof independent of gateway push clock')
    rejected(c,replace(r,request_count=1),e,'out-of-range gateway metadata is refused, not scored')
    c,r,e=sample()
    rejected(c,r,AnswerEvidence((replace(e.disclosures[0],source_sha256='bad'),)),'source hash mismatch')
    rejected(c,r,AnswerEvidence((replace(e.disclosures[0],masked_end=999),)),'bounds mismatch')
    rejected(c,r,AnswerEvidence((replace(e.disclosures[0],item_id='missing'),)),'unknown item')
    rejected(c,r,AnswerEvidence((e.disclosures[0],e.disclosures[0])),'duplicate proof ids')
    rejected(c,r,AnswerEvidence((replace(e.disclosures[0],source_text='wrong',source_sha256=sha('wrong')),)),'source cannot be chosen to fit delivery')
    future=replace(e.disclosures[0],request=2)
    r=replace(r,model_trace=ModelTrace(r.model_trace.responses+(ModelResponse(2,0,0,'',''),),()))
    check(score(c,r,AnswerEvidence((future,))).overall.unresolved==1,'explicit later disclosure cannot earn earlier restoration')

    c,r,e=sample()
    rejected(c,r,AnswerEvidence((replace(e.disclosures[0],request=True),)),'boolean is not a provider ordinal')
    rejected(c,replace(r,model_trace=ModelTrace((ModelResponse(2,0,0,'',''),ModelResponse(1,0,0,FAKE,REAL)),())),e,'non-monotone provider clock refused')
    r=replace(r,model_trace=ModelTrace((ModelResponse(1,0,0,FAKE,REAL),ModelResponse(2,1,0,'later nonempty','later nonempty')),()))
    check(score(c,r,e).overall.unresolved==1,'earlier coincidental raw match cannot replace final-turn proof')

    # Actual source/result bytes plus accepted-call chronology; no gateway-push
    # conversion and no ownership inference from the delivered answer.
    c,r,e=sample()
    r=_with_calls(r,(_call('crm_find_contact',{}, {},{},'',0),),(0,))
    record=ToolResultRecord('crm_find_contact',0,0,0,'text',REAL,FAKE,{'p1':(0,len(REAL))},((0,len(REAL),FAKE,'PHONE'),),False)
    r=replace(r,tool_results=(record,),model_trace=ModelTrace((ModelResponse(1,0,0,'',''),ModelResponse(2,0,1,FAKE,REAL)),(1,)))
    toolproof=DisclosureProof('fixture-tool-input-2',2,'p1','tool_result',0,REAL,FAKE,0,len(REAL),0,len(FAKE),sha(REAL),sha(FAKE))
    check(score(c,r,AnswerEvidence((toolproof,))).overall.joint_ok==1,'tool-only explicit disclosure counts')
    check(score(c,r,AnswerEvidence(e.disclosures+(toolproof,))).overall.joint_ok==1,'same user/tool mapping is not origin ambiguity')
    rejected(c,r,AnswerEvidence((replace(toolproof,request=1),)),'same-response result is not already available')
    rejected(c,replace(r,tool_results=(replace(record,pieces=((1,len(REAL),FAKE,'PHONE'),)),)),AnswerEvidence((toolproof,)),'overlap does not establish whole source slot proof')

    # FOUNDATION-REVIEW REGRESSIONS: four confirmed v2-dev defects now pinned.
    # (1) Exact copy must not be rescued by an unrelated alias's canonical.
    bfake='89990001122'; breal='89164021187'; repaired='79164021187'
    c,r,e=sample(raw=bfake,delivered=repaired)
    r=_with_calls(r,(_call('crm',{}, {},{},'',0),),(0,))
    record=ToolResultRecord('crm',0,0,0,'text',breal,bfake,{'p1':(0,len(breal))},((0,len(breal),bfake,'PHONE'),),False)
    r=replace(r,tool_results=(record,),
              model_trace=ModelTrace((ModelResponse(1,0,0,'',''),ModelResponse(2,0,1,bfake,repaired)),(1,)))
    toolproof_b=DisclosureProof('fixture-tool-b',2,'p1','tool_result',0,breal,bfake,0,len(breal),0,len(bfake),sha(breal),sha(bfake))
    s=score(c,r,AnswerEvidence(e.disclosures+(toolproof_b,)))
    check(s.overall.value_ok==0 and s.overall.joint_ok==0,'exact copy judged against its own literal, not another alias canonical')

    # (2) Provider chronology ordinals must be exact whole ints, not bool/float.
    rejected(c,r,AnswerEvidence((replace(toolproof,request=True),)),'boolean provider ordinal refused')
    c,r,e=sample(); r=_with_calls(r,(_call('crm',{}, {},{},'',0),),(0,))
    r=replace(r,model_trace=ModelTrace((ModelResponse(1,0,0,'',''),ModelResponse(2,0,1,FAKE,REAL)),(0.5,)))
    rejected(c,r,e,'non-integer call_requests refused')
    r=replace(r,model_trace=ModelTrace((ModelResponse(1,0,0,'',''),ModelResponse(2,0,1,FAKE,REAL)),(99,)))
    rejected(c,r,e,'call_requests naming a missing request refused')
    r=replace(r,model_trace=ModelTrace((ModelResponse(1,0.5,0,'',''),),()))
    rejected(c,r,e,'non-integer available_results refused')
    r=replace(r,model_trace=ModelTrace((ModelResponse(1,True,0,'',''),),()))
    rejected(c,r,e,'boolean available_results refused')

    # (3) A replaced piece must carry the item's declared engine type.
    c,r,e=sample(); r=_with_calls(r,(_call('crm',{}, {},{},'',0),),(0,))
    record=ToolResultRecord('crm',0,0,0,'text',REAL,FAKE,{'p1':(0,len(REAL))},((0,len(REAL),FAKE,'NOT_A_TYPE'),),False)
    r=replace(r,tool_results=(record,),model_trace=ModelTrace((ModelResponse(1,0,0,'',''),ModelResponse(2,0,1,FAKE,REAL)),(1,)))
    rejected(c,r,AnswerEvidence((toolproof,)),'unknown replaced piece engine type refused')

    # (4) A future proof must not erase a legacy unknown competitor.
    c,r,e=sample()
    other=replace(c.base.pii[0],id='p2',identity='person2')
    c=replace(c,base=replace(c.base,pii=c.base.pii+(other,)))
    r=replace(r,mentions=r.mentions+(MentionRecord('p2',0,-1,FAKE,1),))
    future_p2=DisclosureProof('p2-future',2,'p2','message',0,REAL,FAKE,0,len(REAL),0,len(FAKE),sha(REAL),sha(FAKE))
    r=replace(r,model_trace=ModelTrace(r.model_trace.responses+(ModelResponse(2,0,0,'',''),),()))
    s=score(c,r,AnswerEvidence((e.disclosures[0],future_p2)))
    check(s.overall.unresolved==1 and s.overall.joint_ok==0,'future proof cannot erase a legacy unknown competitor')

    c,r,e=sample('Готово.','Готово.')
    s=score(c,r,e)
    check(s.overall.candidates==0 and s.answers_without_substitutes==1 and s.answer_restore_clean==0,'no written fake is N/A')
    c,r,e=sample(REAL,REAL)
    check(score(c,r,e).overall.candidates==0,'real passthrough earns no restoration')
    c,r,e=sample(FAKE,FAKE)
    s=score(c,r,e)
    check(s.overall.candidates==1 and s.overall.residual==1 and s.overall.joint_ok==0,'unchanged fake is inside denominator')
    c,r,e=sample(FAKE+' / '+FAKE,REAL+' / '+FAKE)
    s=score(c,r,e)
    check(s.overall.candidates==2 and s.overall.joint_ok==1 and s.overall.residual==1,'both repeated occurrences scored locally')
    check(s.answer_restore_clean==0,'second fake prevents clean-answer success')
    c,r,e=sample(FAKE+'; старый '+REAL,'+79261234567; старый '+REAL)
    check(score(c,r,e).overall.joint_ok==0,'correct real elsewhere cannot rescue wrong local value')
    c,r,e=sample('+79990003122','+79990003122')
    check(score(c,r,e).overall.candidates==0,'changed agent digit is not an exact fake')

    c,r,e=sample(FAKE,REAL)
    other=replace(c.base.pii[0],id='p2',identity='person2',canonical='+79261234567',value='+79261234567')
    c=replace(c,base=replace(c.base,pii=c.base.pii+(other,)))
    r=replace(r,mentions=r.mentions+(MentionRecord('p2',0,-1,FAKE,1),))
    check(score(c,r,e).overall.unresolved==1,'unknown competing raw identity not erased by one proved mapping')
    c,r,e=sample()
    e=AnswerEvidence((e.disclosures[0],replace(e.disclosures[0],record_id='second-source-same-mapping')))
    check(score(c,r,e).overall.joint_ok==1,'same mapping repeated evidence is not origin ambiguity')
    c,r,e=sample()
    r=replace(r,mentions=(),model_trace=None)
    check(score(c,r,None).overall.unresolved==1,'mint without trace nominates candidate, never proves exposure')
    rejected(c,r,e,'explicit evidence without chronology refused')
    c,r,e=sample()
    r=replace(r,model_trace=ModelTrace((ModelResponse(1,0,0,'unrelated',REAL),),()))
    check(score(c,r,e).overall.unresolved==1,'no arbitrary last-response fallback')
    c,r,e=sample('Сейчас проверю.\n'+FAKE,'Сейчас проверю.\n'+REAL)
    r=replace(r,model_trace=ModelTrace((ModelResponse(1,0,0,'Сейчас проверю.','Сейчас проверю.'),ModelResponse(2,0,0,FAKE,REAL)),()))
    check(score(c,r,e).overall.joint_ok==1,'exact same-turn joined responses map to their own intervals')

    c,r,e=sample(FAKE,FAKE)
    r=replace(r,reply_whole=REAL,stream_mismatch=True)
    check(score(c,r,e).overall.residual==1,'actual stream defeats correct whole reply')
    c,r,e=sample('Телефон '+FAKE+', заказ c-3','Телефон '+REAL+', заказ c-8')
    s=score(c,r,e)
    check(s.answer_text_changed==1 and s.answer_restore_clean==0,'non-PII identifier rewrite fails fidelity')
    c,r,e=sample('Без подмен: заказ c-3','Без подмен: заказ c-8')
    check(score(c,r,e).answer_text_changed==1,'no-token literal rewrite is still visible')
    c,r,e=sample('A '+FAKE+' Z','A '+REAL+' Z')
    check(score(c,r,e).answer_text_preserved==1,'literal prefix/suffix intact')
    c,r,e=sample('+7 999 000-11-22','+7 916 402-11-87')
    check(score(c,r,e).overall.joint_ok==1,'agent renotation separate from exact-copy branch')
    c,r,e=sample('+7 999 000-11-22',REAL)
    s=score(c,r,e)
    check(s.overall.value_ok==1 and s.overall.joint_ok==0,'value cannot excuse format repair')

    c,r,e=sample('егрь','игорь','NAME','игрь','егрь',canonical='игорь')
    check(score(c,r,e).overall.joint_ok==0,'exact fake cannot silently correct source typo')
    c,r,e=sample('егрь','игрь','NAME','игрь','егрь',canonical='игорь')
    check(score(c,r,e).overall.value_ok==1,'source literal typo earns value with explicit proof')
    c,r,e=sample('П.О.','И.Е.','NAME','Иванова Елена','Пахомова Ольга')
    s=score(c,r,e)
    check(s.overall.candidates==1 and s.overall.joint_ok==1 and s.overall.value_ok==1,
          'rewritten initials of a proved whole-name disclosure earn value')
    c,r,e=sample('П.О.','П.О.','NAME','Иванова Елена','Пахомова Ольга')
    s=score(c,r,e)
    check(s.overall.residual==1 and s.overall.joint_ok==0,'unchanged fake initials are residual, not success')
    c,r,e=sample('П.О.','И.П.','NAME','Иванова Елена','Пахомова Ольга')
    s=score(c,r,e)
    check(s.overall.value_ok==0 and s.overall.joint_ok==0,'wrong restored initials are value_wrong')
    c,r,e=sample('ПО','ИЕ','NAME','Иванова Елена','Пахомова Ольга')
    check(score(c,r,e).overall.candidates==0,
          'bare two-letter form is not an initials candidate (lexical ambiguity, P09)')
    c,r,e=sample('переулок Липовый, дом 21','улица Пушкина, дом 14','LOC','переулок Пушкина, дом 14','переулок Липовый, дом 21')
    check(score(c,r,e).overall.value_ok==0,'street type belongs to identity')
    # Positive LOC control (G2 acceptance): verbatim correct restore -> matched.
    c,r,e=sample('улица Липовая, дом 21','улица Пушкина, дом 14','LOC','улица Пушкина, дом 14','улица Липовая, дом 21')
    s=score(c,r,e)
    check(s.overall.candidates==1 and s.overall.value_ok==1 and s.overall.joint_ok==1,
          'correct verbatim LOC restore is matched, not value_wrong')
    c,r,e=sample('8','8')
    check(score(c,r,e).overall.candidates==0,'short fragment cannot nominate phone')
    # Unsupported spelling must be surfaced, not silently dropped from the denominator.
    c,r,e=sample(raw='Pakhomova Olga',delivered='Ivanova Elena',kind='NAME',real='Иванова Елена',fake='Пахомова Ольга')
    check(score(c,r,e).unsupported_spellings>=1,'unsupported (Latin) spelling surfaces a count, not a silent zero')
    c,r,e=sample('','')
    check(score(c,r,e).answers_without_substitutes==1,'empty output not restoration100')
    c,r,e=sample()
    check(ESTIMATOR_VERSION in '\n'.join(render(score(c,r,e))),'render explicitly versioned')
    check(not any(n=='pseudex' or n.startswith('pseudex.') for n in sys.modules),'no engine import')
    for f in failures:print('FAIL',f)
    print(f'answer_restoration evidence controls: {checks-len(failures)}/{checks} pass; NOT full G2 acceptance')
    return bool(failures)

if __name__=='__main__':raise SystemExit(main())
