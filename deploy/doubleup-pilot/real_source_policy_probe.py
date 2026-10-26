"""Compare false-positive policies on unchanged archived dialogues, HTTP only.

This does NOT call a model and does NOT claim a tool/model completed the source
work. Both full original user sequences go through the actual combined container.
All requests/responses remain encrypted; stdout contains only counts/verdicts.
"""
from pathlib import Path
import json
import re
import sys
import uuid
import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent/'prototype'))
from bench.doubleup.storage import RunStore, hashed
from bench.doubleup.date_pii_catalog import ms
from qualify_september_replay import original_text, CUTOFF_MS

FRAGMENTS = ('РОП', 'РОМ', 'Бюджетирование')


def occurrences(text, word):
    return len(re.findall(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text, re.I))


def run():
    source = RunStore('september-pii-catalog-v5', False)
    source_manifest = source.verify()
    snapshot = RunStore(source_manifest['source_snapshot'], False)
    snapshot.verify()
    inventory = snapshot.read_encrypted('original-user-candidate-inventory.aesgcm')
    by_thread = {}
    for message in inventory['user_messages']:
        by_thread.setdefault(message['thread_id'], []).append(message)
    credentials = json.loads((HERE/'.state/credentials.json').read_text())
    admin = {'Authorization':'Bearer '+credentials['admin']}
    gateway = {'Authorization':'Bearer '+credentials['gateway']}
    out = RunStore('september-source-policy-http-v1', True)
    ident = 'qa-source-fp-' + uuid.uuid4().hex[:10]
    bound_key, unbound_key = ident+'-bound', ident+'-control'
    rows = []
    with httpx.Client(base_url='http://127.0.0.1:18862', timeout=120, trust_env=False) as client:
        bindings = client.get('/policies/bindings', headers=admin)
        bindings.raise_for_status()
        original = bindings.json()
        configured = False
        try:
            r = client.post('/policies', headers=admin, json={'policy_id':ident,
                'title':'QA: observed business-role false positives',
                'rules':[{'id':'business-roles','action':'ignore','category':'NAME','values':list(FRAGMENTS)}]})
            r.raise_for_status()
            configured = True
            b = list(original['bindings']) + [{'agent_key':bound_key,'policy_id':ident}]
            r = client.put('/policies/bindings', headers=admin, json={
                'bindings':b,'default_policy_id':original['default_policy_id']})
            r.raise_for_status()
            for number in (32,77):
                case = source.read_encrypted(f'case-{number:03}.aesgcm')
                all_messages = sorted(by_thread[case['thread']['thread_id']],key=lambda x:ms(x['created_at']))
                assert len(all_messages)==len(case['user_messages_in_window']), 'pre_cutoff_history_must_not_be_stripped'
                assert all(ms(x['created_at'])>=CUTOFF_MS for x in all_messages), 'source_before_september'
                turns = [{'role':'user','content':original_text(message)} for message in all_messages]
                scope={'org_id':'doubleup-qualitative-policy-test','agent_id':'trusted-local-probe',
                       'conversation_id':ident+'-case-'+str(number),'pseudonym_scope':'conversation',
                       'request_id':ident+'-request-'+str(number),
                       'messages':turns,'inspection':True}
                responses=[]
                for key in (unbound_key,bound_key):
                    response=client.post('/mask',headers={**gateway,'X-Agent-Id':key},json=scope)
                    responses.append({'status':response.status_code,'response':response.json()})
                out.encrypt(f'case-{number:03}.aesgcm',{'source':case,'raw_body':scope,'policy_id':ident,
                                                       'control':responses[0],'configured':responses[1]})
                assert all(r['status']==200 for r in responses),'mask_request_failed'
                texts=['\n'.join(msg['content'] for msg in r['response']['messages']) for r in responses]
                original_text_all='\n'.join(message['content'] for message in turns)
                comparisons={word:{'original':occurrences(original_text_all,word),
                                   'default':occurrences(texts[0],word),
                                   'configured':occurrences(texts[1],word)} for word in FRAGMENTS}
                # Original source evidence is used only as a conservative check
                # that known exact personal values did not survive to model input.
                leaks=[]
                for idx,text in enumerate(texts):
                    leaks.append(sum(bool(item.get('surface')) and item['surface'] in text
                                     for item in case['user_pii']['evidence']))
                row={'case':'catalog-'+str(number).zfill(3),'turns':len(turns),
                     'source_sequence_preserved':True,'fragments':comparisons,
                     'exact_source_pii_occurrences_remaining_control':leaks[0],
                     'exact_source_pii_occurrences_remaining_configured':leaks[1],
                     'all_configured_fragments_preserved':all(v['original']==v['configured'] for v in comparisons.values()),
                     'actual_false_positive_reduction':any(v['configured']>v['default'] for v in comparisons.values()),
                     'mask_inspection_versions':[r['response'].get('inspection',{}).get('version') for r in responses],
                     'provider_calls':0,'source_tool_execution_in_this_probe':False,
                     'source_user_sequence_sha256':hashed(turns)}
                row['passed']=row['all_configured_fragments_preserved'] and row['actual_false_positive_reduction'] and leaks[1]==0
                rows.append(row)
        finally:
            if configured:
                r=client.put('/policies/bindings',headers=admin,json={
                    'bindings':original['bindings'],'default_policy_id':original['default_policy_id']})
                r.raise_for_status()
                r=client.delete('/policies/'+ident,headers=admin);r.raise_for_status()
    out.encrypt('report.aesgcm',{'cases':rows})
    out.finish({'kind':'actual_source_policy_http_probe','cases':len(rows),'passed':sum(x['passed'] for x in rows),
                'provider_calls':0,'raw_values_encrypted':True,'source_mutations':0})
    out.verify()
    print(json.dumps({'source_policy_comparison':rows,'not_a_model_or_tool_completion_test':True},ensure_ascii=False))
    if not all(row['passed'] for row in rows):raise SystemExit(1)

if __name__=='__main__':
    run()
