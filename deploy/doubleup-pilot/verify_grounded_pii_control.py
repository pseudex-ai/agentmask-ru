"""Non-vacuous boundary checks for actual executions, not a quality score."""
from pathlib import Path
import json,re,sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'prototype'))
from bench.doubleup.storage import RunStore
from prepare_dialogue_replay import AAD


def strings(value):
    if isinstance(value,dict):
        for item in value.values():yield from strings(item)
    elif isinstance(value,list):
        for item in value:yield from strings(item)
    elif isinstance(value,str):
        yield value
        if value.lstrip().startswith(('{','[')):
            try:item=json.loads(value)
            except ValueError:return
            if isinstance(item,(dict,list)):yield from strings(item)


def text(value):return '\n'.join(strings(value))


def calls(response):
    return {call['id']:call for choice in (response or {}).get('choices',[])
            for call in choice.get('message',{}).get('tool_calls',[])}


def main():
    state=HERE/'.state';b='source-grounded-pii-control-v1'
    key=(state/'runtime'/f'{b}.key').read_bytes();raw=(state/'runtime'/f'{b}.aesgcm').read_bytes()
    packet=json.loads(AESGCM(key).decrypt(raw[:12],raw[12:],AAD));case=packet['cases'][0]
    pii={v for name,values in case['expected_values'].items() if name!='labels' for v in values}
    labels=set(case['expected_values']['labels'])
    assert len(pii)==3,'control_requires_three_real_source_values'
    archive=RunStore('source-grounded-pii-control-evidence-v1',False);archive.verify();reports=[]
    for mode in ('none','builtin','pseudex'):
        data=archive.read_encrypted(mode+'.aesgcm');summary=archive.read_encrypted(mode+'-summary.aesgcm')
        seen=set();remaining=set();dispatch_count=dispatch_exact=dispatch_changed=results=0
        outputs_with_all_source=outputs_with_all_labels=0
        executed_with_all_source=executed_with_all_labels=0
        mask_roles={'user_to_model':0,'tool_to_model':0}
        restored={'model_to_tool':0,'model_to_user':0}
        for item in data['attempts']:
            source=text(item['source_request']);out=text(item.get('model_request'))
            encountered={v for v in pii if v in source};seen|=encountered
            # Check ALL expected source surfaces too, not only those remaining
            # after a builtin filter has already changed source_request.
            remaining|={v for v in pii if v in out}
            raw_calls=calls(item.get('model_response'));restored_calls=calls(item.get('restored_response'))
            for dispatch in item.get('tool_dispatches',[]):
                dispatch_count+=1;args=dispatch['arguments'];body=text(args)
                executed_with_all_source+=all(v in body for v in pii)
                executed_with_all_labels+=all(v in body for v in labels)
                raw_call=raw_calls.get(dispatch['tool_call_id']);restored_call=restored_calls.get(dispatch['tool_call_id'])
                assert raw_call and restored_call,'unlinked_actual_dispatch'
                dispatch_exact+=json.loads(restored_call['function']['arguments'])==args
                dispatch_changed+=json.loads(raw_call['function']['arguments'])!=args
            for result in item.get('tool_results',[]):
                if not result.get('completed'):continue
                results+=1;body=text(result.get('raw_result'))
                outputs_with_all_source+=all(v in body for v in pii)
                outputs_with_all_labels+=all(v in body for v in labels)
            for r in (item.get('inspection') or {}).get('replacements',[]):
                m=re.match(r'/messages/(\d+)/content',r['path'])
                if m:
                    role=item['source_request']['messages'][int(m[1])]['role']
                    if role=='user':mask_roles['user_to_model']+=1
                    if role=='tool':mask_roles['tool_to_model']+=1
            for r in (item.get('restoration') or {}).get('replacements',[]):
                if '/tool_calls/' in r['path']:restored['model_to_tool']+=1
                elif r['path'].endswith('/content'):restored['model_to_user']+=1
        row={'mode':mode,'new_controlled_dialogue_not_historical_replay':True,
             'completed_user_turns':summary['turns'],'actual_tool_dispatches':dispatch_count,
             'tool_errors':summary['tool_errors'],'distinct_original_values':len(pii),
             'distinct_original_values_remaining_in_model_payload':len(remaining),
             'dispatches_equal_verified_restored_response':dispatch_exact,
             'dispatches_changed_by_restoration':dispatch_changed,
             'dispatches_with_all_three_original_values':executed_with_all_source,
             'dispatches_with_all_negative_controls':executed_with_all_labels,
             'completed_tool_results':results,'tool_results_with_all_three_original_values':outputs_with_all_source,
             'tool_results_with_all_negative_controls':outputs_with_all_labels,
             'recorded_mask_operations_including_resent_history':mask_roles,
             'recorded_restoration_operations':restored,
             'not_a_precision_recall_or_task_success_metric':True}
        if mode=='pseudex':
            row['passed']=(summary['turns']==3 and summary['tool_errors']==0 and dispatch_count==3
                and dispatch_exact==dispatch_count and dispatch_changed==dispatch_count
                and executed_with_all_source==dispatch_count and executed_with_all_labels==dispatch_count
                and outputs_with_all_source==results==3 and outputs_with_all_labels==results
                and len(remaining)==0 and all(n>0 for n in mask_roles.values())
                and restored['model_to_tool']>0)
        reports.append(row)
    result={'cases':reports,'pseudex_protection_cycle_passed':next(r['passed'] for r in reports if r['mode']=='pseudex'),
            'provider_calls_from_verification':0,'source_values_exposed_in_report':False}
    p=state/'source-grounded-pii-control-verification.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2));p.chmod(0o600)
    print(json.dumps(result,ensure_ascii=False))
    if not result['pseudex_protection_cycle_passed']:raise SystemExit(1)

if __name__=='__main__':main()
