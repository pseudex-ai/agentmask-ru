"""Replay six exact captured HTTP inputs to a fixed container, no provider.

A source NAME encoded as JSON Unicode must not survive a decoded payload read.
Receipts are independently rebuilt at exact codepoint offsets. All raw evidence
stays encrypted. This is a regression replay, not a new live-model completion.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys
import uuid
import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'prototype'))
from bench.doubleup.storage import RunStore
from prepare_dialogue_replay import AAD
from verify_grounded_pii_control import strings


def field(node,path):
    for key in path.split('/')[1:]:
        key=key.replace('~1','/').replace('~0','~')
        node=node[int(key)] if isinstance(node,list) else node[key]
    return node


def validate_receipt(before,after):
    receipt=after['inspection']
    assert receipt['version']==1 and receipt['complete'] is True
    assert receipt['offset_unit']=='unicode_codepoint'
    groups=defaultdict(list)
    for r in receipt['replacements']:
        raw=field(before,r['path']);masked=field(after,r['path'])
        a,b,x,y=(r[k] for k in ('source_start','source_end','output_start','output_end'))
        assert isinstance(raw,str) and isinstance(masked,str)
        assert 0<=a<b<=len(raw) and 0<=x<=y<=len(masked)
        assert raw[a:b]!=masked[x:y]
        groups[r['path']].append(r)
    for path,rs in groups.items():
        raw=field(before,path);masked=field(after,path)
        for r in sorted(rs,key=lambda r:r['source_start'],reverse=True):
            raw=raw[:r['source_start']]+masked[r['output_start']:r['output_end']]+raw[r['source_end']:]
        assert raw==masked,'unrecorded_mask_transformation'
    return len(receipt['replacements'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);args=parser.parse_args()
    state=HERE/'.state';bundle='source-grounded-pii-control-v1'
    key=(state/'runtime'/f'{bundle}.key').read_bytes();raw=(state/'runtime'/f'{bundle}.aesgcm').read_bytes()
    packet=json.loads(AESGCM(key).decrypt(raw[:12],raw[12:],AAD));case=packet['cases'][0]
    expected={v for kind,values in case['expected_values'].items() if kind!='labels' for v in values}
    labels=set(case['expected_values']['labels'])
    prior=RunStore('source-grounded-pii-control-evidence-v1',False);prior.verify()
    attempts=prior.read_encrypted('pseudex.aesgcm')['attempts'];assert len(attempts)==6
    credentials=json.loads((state/'credentials.json').read_text())
    archive=RunStore(args.run_id,True);results=[]
    with httpx.Client(base_url='http://127.0.0.1:18862',trust_env=False,timeout=90) as c:
        for i,item in enumerate(attempts):
            source=item['source_request']
            body={'org_id':item['tenant_id'],'conversation_id':item['thread_id'],
                  'agent_id':item['agent_id'],'request_id':uuid.uuid4().hex,
                  'pseudonym_scope':'conversation','inspection':True,
                  'messages':source['messages'],**({'tools':source['tools']} if 'tools' in source else {})}
            response=c.post('/mask',headers={'Authorization':'Bearer '+credentials['gateway'],
                                           'X-Agent-Id':item['agent_id']},json=body)
            try:masked=response.json()
            except ValueError:masked={'error':'non_json_engine_error'}
            archive.encrypt(f'request-{i+1}.aesgcm',{'request':body,'response':masked,'http_status':response.status_code})
            row={'request':i+1,'http_status':response.status_code,'provider_calls':0}
            if response.status_code==200:
                visible='\n'.join(strings({'messages':masked['messages'],'tools':masked.get('tools',[])}))
                row['original_values_remaining_after_json_decode']=sum(v in visible for v in expected)
                row['all_expected_originals_present_in_source']=all(v in '\n'.join(strings(body)) for v in expected)
                row['negative_control_labels_kept']=all(v in visible for v in labels)
                try:
                    row['replacements']=validate_receipt(body,masked)
                    row['receipts_exact']=True
                except (AssertionError,KeyError,TypeError):row['receipts_exact']=False
                row['all_tool_arguments_valid_json']=all(isinstance(json.loads(call['function']['arguments']),dict)
                    for msg in masked['messages'] for call in msg.get('tool_calls',[]))
                row['passed']=(row['original_values_remaining_after_json_decode']==0
                    and row['all_expected_originals_present_in_source'] and row['negative_control_labels_kept']
                    and row['receipts_exact'] and row['all_tool_arguments_valid_json'])
            else:row['passed']=False
            results.append(row)
    report={'all_six_actual_captured_inputs_passed':all(r['passed'] for r in results),
            'requests':results,'new_model_calls':0,'historical_request_replay_only':True}
    archive.encrypt('report.aesgcm',report);archive.finish({'kind':'decoded_pii_runtime_regression',
        'requests':len(results),'passed':sum(r['passed'] for r in results),'provider_calls':0})
    archive.verify()
    path=state/(args.run_id+'.json');path.write_text(json.dumps(report,indent=2));path.chmod(0o600)
    print(json.dumps(report))
    if not report['all_six_actual_captured_inputs_passed']:raise SystemExit(1)

if __name__=='__main__':main()
