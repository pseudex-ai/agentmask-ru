"""Prepare a short fully retained source dialogue from the final catalog."""
from pathlib import Path
import copy
import json
import os
import sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'prototype'))
from bench.doubleup.storage import RunStore,hashed,canonical
from bench.doubleup.date_pii_catalog import ms
from bench.doubleup.mongo_dialogues import normalized_events
from bench.doubleup.source_resources import build_resources,attachment_locators
from bench.doubleup.replay_tools import ReplayTools
from qualify_september_replay import original_text,CUTOFF_MS,ENVIRONMENT
from prepare_dialogue_replay import AAD
from prepare_live import write_private
from budget import load_pricing,quote


def main():
    s=RunStore('september-pii-catalog-v5',False);manifest=s.verify()
    x=s.read_encrypted('case-026.aesgcm')
    assert x['criteria']['pii_reaches_tools']
    snapshot=RunStore(manifest['source_snapshot'],False);snapshot.verify()
    raw=snapshot.read_encrypted('original-user-candidate-inventory.aesgcm')
    messages=sorted((u for u in raw['user_messages'] if u['thread_id']==x['thread']['thread_id']),key=lambda u:ms(u['created_at']))
    assert len(messages)==len(x['user_messages_in_window'])==3
    assert all(ms(u['created_at'])>=CUTOFF_MS for u in messages)
    assert not attachment_locators({'mongo_user_messages':messages},26)
    turns=[{'role':'user','content':original_text(u)} for u in messages]
    evidence=None;provenance=None
    for run in reversed(manifest['tools_run'].split(',')):
        archive=RunStore(run,False)
        filename='tc-'+x['source_thread_sha256'][:16]+'.aesgcm'
        if not (archive.path/filename).exists():continue
        if not (archive.path/'manifest.json').is_file():continue
        m=archive.verify()
        data=archive.read_encrypted(filename)
        if data.get('complete'):
            evidence=data;provenance={'run':run,'artifact':filename,'manifest_sha256':hashed(m)};break
    assert evidence is not None,'complete_observation_join_missing'
    trace_map={t['id']:t for t in evidence['traces']};events=[]
    for tid,obs in evidence['observations'].items():events.extend(normalized_events(trace_map[tid],obs))
    gens=sorted((o for o in events if o['type']=='GENERATION' and isinstance(o.get('output'),dict)
                 and o['output'].get('tool_calls') and isinstance(o.get('input'),list)),key=lambda o:(str(o.get('start')),o['id']))
    assert gens,'source_executor_missing'
    systems=[copy.deepcopy(m) for m in gens[0]['input'] if isinstance(m,dict) and m.get('role')=='system']
    assert systems and all(isinstance(m.get('content'),str) for m in systems)
    names={sp['name'] for sp in evidence['tool_spans']};assert names=={'run_code'}
    cs=RunStore('safe-local-replay-plan-v4',False);cs.verify();contracts={'run_code':cs.read_encrypted('tool-contracts.aesgcm')['run_code']}
    d={'thread':x['thread'],'mongo_user_messages':messages,'user_turns':turns,'langfuse':{'complete':True,'events':events},
       'source_context':{'application_activity':{'source_tool_execution_spans':evidence['tool_spans']}}}
    resources=build_resources(d,26);ReplayTools(contracts,resources,'qualification')
    adapted=systems+[{'role':'system','content':ENVIRONMENT}]
    tools=[{'type':'function','function':{'name':name,'description':c['description'],'parameters':c['parameters']}} for name,c in contracts.items()]
    initial=quote({'model':'deepseek-v4-flash','messages':adapted+[turns[0]],'tools':tools,
                   'max_tokens':8192,'stream':False,'thinking':{'type':'disabled'}},load_pricing(HERE/'.state/pricing.json'))
    case={'case_id':hashed(['september-pii-catalog-v5','case-026.aesgcm']),'source_index':25,'catalog_case':26,
          'source_run':'september-pii-catalog-v5','source_user_turns':turns,'source_user_sequence_sha256':hashed(turns),
          'system_messages':adapted,'source_system_before_environment_sha256':hashed(systems),
          'source_provenance':provenance,'contracts':contracts,'tools':tools,'resources':resources,
          'max_tokens':8192,'max_tool_steps_per_turn':24,'initial_quote':initial}
    packet={'run_id':'september-final-case26-v1','model':'deepseek-v4-flash','cases':[case],
            'source_user_sequences_unmodified':True,'historical_answers_injected':False,'original_orchestrator_reproduced':False}
    key=AESGCM.generate_key(bit_length=256);nonce=os.urandom(12);bundle='september-final-case26-v1';runtime=HERE/'.state/runtime'
    write_private(runtime/(bundle+'.key'),key);write_private(runtime/(bundle+'.aesgcm'),nonce+AESGCM(key).encrypt(nonce,canonical(packet),AAD))
    print(json.dumps({'case':'catalog-026','full_original_user_turns':3,'text_chars':sum(len(t['content']) for t in turns),
                      'pii_types':sorted(x['user_pii']['occurrences']),'pii_in_source_tool_results':True,
                      'safe_tools':['run_code'],'initial_three_arm_reservation_usd':initial['reserved_nano']*3/1e9,
                      'original_input_bytes_not_fabricated':True,'provider_calls':0}))

if __name__=='__main__':main()
