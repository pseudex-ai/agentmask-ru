"""Read-only foundation adversaries, outputs confined to this review scope."""
from pathlib import Path
import sys,json,hashlib
from dataclasses import replace,asdict
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'prototype'))
from bench.agentpii5.test_answer_restoration import sample,sha,REAL,FAKE
from bench.agentpii5.answer_restoration import AnswerEvidence,DisclosureProof,answer_events,aggregate
from bench.agentpii5.contracts import MentionRecord,ModelResponse,ModelTrace,ToolResultRecord
from bench.agentpii5.fixtures import _case,_item,_in_message,_call,_with_calls,_run,_with_subs,_with_replies
OUT=Path(__file__).parent
FILES=[ROOT/'prototype/bench/agentpii5/answer_restoration.py',ROOT/'prototype/bench/agentpii5/test_answer_restoration.py']
BEFORE={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}
rows=[]
def show(label,c,r,e,expected):
 try:
  v=answer_events(c,r,evidence=e);a=aggregate((v,))
  result={'accepted':True,'events':[asdict(x) for x in v.events], 'summary':asdict(a)}
 except Exception as ex:result={'accepted':False,'exception_type':type(ex).__name__,'exception':str(ex)}
 rows.append({'label':label,'expected':expected,'result':result})
 print(label,'=>', result.get('exception_type') if not result['accepted'] else [(x['status'],x['expected'],x['joint_ok']) for x in result['events']])

# Exact copied B must return its B source literal, even beside an equivalent A alias.
ra=REAL; rb='8(916)4О2-11-87'; fa=FAKE; fb='8(999)000-11-22'
items=(_item('p1','PHONE',ra,REAL,'person1',_in_message(0,0,len(ra))),
       _item('p2','PHONE',rb,REAL,'person1',_in_message(1,0,len(rb))))
c=_case('multiple-forms','single',(ra,rb),items,())
r=_with_replies(_with_subs(_run(c.base.id),{'p1':fa,'p2':fb}),fb,'8(916)402-11-87','')
r=replace(r,mentions=(MentionRecord('p1',0,-1,fa,1),MentionRecord('p2',1,-1,fb,2)),request_count=2,
          model_trace=ModelTrace((ModelResponse(1,0,0,'',''),ModelResponse(2,1,0,fb,r.base.reply)),()))
p1=DisclosureProof('a',1,'p1','message',0,ra,fa,0,len(ra),0,len(fa),sha(ra),sha(fa))
p2=DisclosureProof('b',2,'p2','message',1,rb,fb,0,len(rb),0,len(fb),sha(rb),sha(fb))
show('exact_B_copy_with_A_alias_repaired',c,r,AnswerEvidence((p1,p2)),'must not joint-pass; raw exact B requires B literal containing Cyrillic О')
show('exact_B_copy_without_A_alias_repaired',c,replace(r,mentions=(r.mentions[1],),base=replace(r.base,substitutes={'p2':(fb,{})})),AnswerEvidence((p2,)),'must fail repaired literal')
# Note p1 item still exists but no p1 spelling/record to nominate it in the single-proof control.

# Valid whole tool proof baseline, then one malformed chronology/type field at a time.
c,r,e=sample()
r=_with_calls(r,(_call('crm_find_contact',{}, {},{},'',0),),(0,))
record=ToolResultRecord('crm_find_contact',0,0,0,'text',REAL,FAKE,{'p1':(0,len(REAL))},((0,len(REAL),FAKE,'PHONE'),),False)
r=replace(r,tool_results=(record,),model_trace=ModelTrace((ModelResponse(1,0,0,'',''),ModelResponse(2,0,1,FAKE,REAL)),(1,)))
p=DisclosureProof('tool',2,'p1','tool_result',0,REAL,FAKE,0,len(REAL),0,len(FAKE),sha(REAL),sha(FAKE));e=AnswerEvidence((p,))
show('tool_valid_control',c,r,e,'one matched event')
for name,clock in [('call_request_zero',0),('call_request_absent',-1),('call_request_boolean',True),('call_request_fractional',0.5)]:
 show(name,c,replace(r,model_trace=replace(r.model_trace,call_requests=(clock,))),e,'refuse invalid/unrecorded provider call ordinal, not success')
show('fractional_available_results',c,replace(r,model_trace=replace(r.model_trace,responses=(r.model_trace.responses[0],replace(r.model_trace.responses[1],available_results=0.5)))),e,'refuse fractional boundary, not success')
show('boolean_available_results',c,replace(r,model_trace=replace(r.model_trace,responses=(r.model_trace.responses[0],replace(r.model_trace.responses[1],available_results=True)))),e,'refuse boolean boundary, not success')
show('tool_wrong_piece_type',c,replace(r,tool_results=(replace(record,pieces=((0,len(REAL),FAKE,'NAME'),)),)),e,'type discrepancy must be explicit; decide if typed-evidence refusal or separate diagnostic, not invisible')
show('tool_unknown_piece_type',c,replace(r,tool_results=(replace(record,pieces=((0,len(REAL),FAKE,'NOT_A_TYPE'),)),)),e,'refuse invalid piece type')

# Metadata schema: integer checks need to cover the record, not only DisclosureProof.
c,r,e=sample()
show('boolean_gateway_total',c,replace(r,request_count=True),e,'refuse bool gateway total')
show('fractional_gateway_mention',c,replace(r,mentions=(replace(r.mentions[0],request_index=0.5),)),e,'refuse fractional push index')
show('boolean_provider_turn',c,replace(r,model_trace=replace(r.model_trace,responses=(replace(r.model_trace.responses[0],turn=True),))),e,'refuse bool provider turn')

# Adding a later positive capture does not prove an earlier unknown never existed.
c,r,e=sample()
other=_item('p2','PHONE','+79261234567','+79261234567','person2',_in_message(1,0,12))
c=replace(c,base=replace(c.base,pii=c.base.pii+(other,),messages=c.base.messages+(replace(c.base.messages[0],content=other.value),)))
r=replace(r,request_count=2,mentions=r.mentions+(MentionRecord('p2',1,-1,FAKE,1),),
          model_trace=ModelTrace((ModelResponse(1,1,0,FAKE,REAL),ModelResponse(2,1,0,'','')),()))
show('unknown_competitor_before_future_capture',c,r,e,'unknown competitor makes ownership unresolved')
future=DisclosureProof('later-p2',2,'p2','message',1,other.value,FAKE,0,len(other.value),0,len(FAKE),sha(other.value),sha(FAKE))
show('unknown_competitor_after_adding_future_capture',c,r,AnswerEvidence(e.disclosures+(future,)),
     'must remain unresolved unless earlier exposure absence is explicitly proved; later positive capture is not exhaustive-history evidence')
show('proved_future_without_unknown_hint_control',c,replace(r,mentions=(r.mentions[0],)),AnswerEvidence(e.disclosures+(future,)),
     'future-only competitor must not invalidate proved present p1 mapping')

# Unknown competitor same identity/value but different role must not disappear.
c,r,e=sample('Пахомова Ольга','Иванова Елена','NAME','Иванова Елена','Пахомова Ольга')
other=_item('p2','NAME','Сидорова Анна','Сидорова Анна','other-person',_in_message(0,0,13))
c=replace(c,base=replace(c.base,pii=c.base.pii+(other,)))
r=replace(r,mentions=r.mentions+(MentionRecord('p2',0,-1,'Ольга',1),))
show('nested_other_identity',c,r,e,'unresolved, not matched')

AFTER={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}
assert BEFORE==AFTER
assert not any(x=='pseudex' or x.startswith('pseudex.') for x in sys.modules)
(OUT/'PROBES.json').write_text(json.dumps({'source_hashes_before':BEFORE,'source_hashes_after':AFTER,'unchanged':True,'probes':rows},ensure_ascii=False,indent=2)+'\n')
print('unchanged source hashes; no engine import; probes',len(rows))
