"""Complete real source ROOT histories + application tool traces, contacts mandatory.

No model inference, no customer writes, no synthetic conversations. Per-case
stores are independent, encrypted and immutable, so bounded GET work can run in
four threads without sharing response counters/keys/files.
"""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import json
import subprocess
import sys

from .mongo_intake import IMAGE, read_config
from .mongo_dialogues import (EvidenceClient, application_client, application_activity, decode_offline,
    explicit_context, join_session, list_session, message_role, normalize_mongo, public_summary)
from .qualify_dialogues import evidence
from .storage import RunStore, hashed

READER = r'''
import json,sys
from pymongo import MongoClient
from bson import json_util
c=json.loads(sys.stdin.readline())
try:
 with MongoClient(c['uri'],serverSelectionTimeoutMS=5000,socketTimeoutMS=20000,appname='doubleup-readonly-complete-sensitive-corpus') as client:
  db=client[c['database']];q={'thread_id':c['thread_id'],'checkpoint_ns':''}
  thread=db.threads.find_one({'thread_id':c['thread_id'],'org_id':c['org_id'],'user_id':c['user_id']})
  if not thread:raise ValueError('source_scope_mismatch')
  item={'thread':thread,'root_checkpoint_count':db.graph_states.count_documents(q),
    'earliest_root_checkpoint':db.graph_states.find_one(q,sort=[('ts',1),('checkpoint_id',1)]),
    'latest_root_checkpoint':db.graph_states.find_one(q,sort=[('ts',-1),('checkpoint_id',-1)]),
    'compactions':list(db.thread_compactions.find({'thread_id':c['thread_id']}).sort('created_at',1))}
  print(json_util.dumps({'ok':True,'item':item},json_options=json_util.CANONICAL_JSON_OPTIONS))
except Exception as e:print(json.dumps({'ok':False,'error_type':type(e).__name__}))
'''


def one(index, candidate, source_run, source_manifest):
    run_id=f'real-sensitive-corpus-{index+1:03d}-v1';store=RunStore(run_id,True)
    thread=candidate['thread'];config={**read_config(),**{k:thread[k] for k in ('thread_id','org_id','user_id')}}
    process=subprocess.run(['docker','run','--rm','--network','host','--log-driver','none','-i',IMAGE,'python','-c',READER],
        input=json.dumps(config).encode(),capture_output=True,timeout=60)
    if process.returncode or len(process.stdout)>64*1024*1024:raise RuntimeError('source_root_read_refused')
    raw=json.loads(process.stdout)
    if raw.get('ok') is not True:raise RuntimeError('source_root_scope_or_read_failed')
    item=raw['item'];original_users=copy.deepcopy(candidate['source_user_messages'])
    # sender.type is source-query evidence, not a guessed role. Keep original
    # projected source documents separately; no old AI duplicate dedup by text.
    item['messages']=[{**message,'sender':{'type':'user'}} for message in original_users]
    item['candidate']={'_id':thread['thread_id'],'users':candidate['mongo_user_documents'],
                       'assistants':candidate['mongo_assistant_documents']}
    payload={'format':'mongo-extended-json-canonical-v2','threads':[item],
        'original_user_documents':original_users,'user_role_from_original_query':True,
        'source_user_messages_all_history':True,'remote_mutations':0}
    store.encrypt('mongo-originals.aesgcm',payload)
    decoded=decode_offline(payload,store)
    dialogue=normalize_mongo(item,decoded[0])
    dialogue['source_completeness']['all_mongo_message_docs_no_date_window']=False
    dialogue['source_completeness']['all_original_user_docs_no_date_window']=True
    dialogue['source_completeness']['mongo_assistant_duplicate_docs_not_reexported']=True
    root_evidence=[entry for number,message in enumerate(dialogue['user_turns'])
                   for entry in evidence(message['content'],f'/user_turns/{number}/content')]
    if not root_evidence:
        store.encrypt('original-root-dialogue.aesgcm',dialogue)
        return store.finish({'kind':'source_case_not_qualified','source_run':source_run,'source_manifest_sha256':hashed(source_manifest),
            'source_index':index,'reason':'no_high_confidence_contact_in_retained_root_user_messages',
            'provider_calls':0,'remote_mutations':0,'root_originals_retained':True})
    client=EvidenceClient(application_client(),store,650,1000)
    rows,proof=list_session(client,dialogue['thread'])
    dialogue['langfuse']=join_session(client,dialogue,rows,proof)
    context=explicit_context([('mongo_root_messages',[{**m,'role':message_role(m)} for m in dialogue['messages']]),
        ('langfuse',dialogue['langfuse'])])
    context['application_activity']=application_activity(dialogue['langfuse']);dialogue['source_context']=context
    user_keys={(x['type'],x['canonical']) for x in root_evidence};tool_proofs=[];input_keys=set();output_keys=set()
    for span in context['application_activity']['source_tool_execution_spans']:
        inputs=evidence(span['arguments'],'/input');outputs=evidence(span['result'],'/output')
        if inputs or outputs:
            tool_proofs.append({'observation_id':span['observation_id'],'trace_id':span['trace_id'],
                'name':span['name'],'arguments':inputs,'result':outputs,'source_semantics':span['source_semantics']})
        input_keys.update((x['type'],x['canonical']) for x in inputs);output_keys.update((x['type'],x['canonical']) for x in outputs)
    private={'dialogue':dialogue,'sensitivity':{'original_user_contact_evidence':candidate['user_contact_evidence'],
        'retained_root_user_contact_evidence':root_evidence,'tool_execution_contact_evidence':tool_proofs},
        'original_values_unchanged':True,'manual_pii_annotation':False}
    store.encrypt('complete-sensitive-dialogue.aesgcm',private)
    store.encrypt('http-provenance.aesgcm',{'responses':client.client.response_receipts,'pages':client.pages,
        'trace_detail_requests':client.trace_requests,'observation_requests':client.observation_requests})
    complete=dialogue['source_completeness']['authoritative_root_export_complete'] and dialogue['langfuse']['complete']
    summary={'kind':'complete_real_sensitive_dialogue','source_run':source_run,'source_manifest_sha256':hashed(source_manifest),
        'catalog_index':index,'source_thread_sha256':hashed(thread['thread_id']),'source_graph_type':candidate['graph_type'],
        'root_user_turns':len(dialogue['user_turns']),'root_messages':len(dialogue['messages']),
        'authoritative_root_complete':dialogue['source_completeness']['authoritative_root_export_complete'],
        'cross_source_user_projection_equal':dialogue['source_completeness']['cross_source_user_projection_equal'],
        'root_gaps':dialogue['source_completeness']['gaps'],'langfuse_complete':dialogue['langfuse']['complete'],
        'source_contact_evidence_present':bool(root_evidence),'source_contact_types':dict(Counter(x['type'] for x in root_evidence)),
        'source_tool_execution_spans':len(context['application_activity']['source_tool_execution_spans']),
        'tool_calls_with_contacts':len(tool_proofs),'tools_with_contacts':sorted({x['name'] for x in tool_proofs}),
        'user_contacts_in_tool_arguments':len(user_keys&input_keys),'user_contacts_in_tool_results':len(user_keys&output_keys),
        'source_trace_count':len(dialogue['langfuse']['trace_details']),
        'source_observation_count':len(dialogue['langfuse']['independent_observations']),
        'complete_qualified':bool(complete),'provider_calls':0,'remote_mutations':0,'manual_pii_labels':False,
        'requests':client.client.requests,'retries':client.client.retries,'source_values_encrypted':True}
    result=store.finish(summary);store.verify();return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',default='real-sensitive-chat-inventory-v1')
    parser.add_argument('--limit',type=int,default=30);args=parser.parse_args()
    if not 6<=args.limit<=30:raise SystemExit('invalid_limit')
    source=RunStore(args.source,False);parent=source.verify();selected=source.read_encrypted('qualified-candidates.aesgcm')['selected'][:args.limit]
    outcomes=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(one,index,record,args.source,parent):index for index,record in enumerate(selected)}
        for job in as_completed(jobs):
            index=jobs[job]
            try:
                result=job.result();outcomes.append(result)
                print(json.dumps({'case':index+1,'run_id':result['run_id'],'complete_qualified':result.get('complete_qualified',False),
                    'user_turns':result.get('root_user_turns'),'tool_calls_with_contacts':result.get('tool_calls_with_contacts'),
                    'user_contacts_in_tool_arguments':result.get('user_contacts_in_tool_arguments'),
                    'user_contacts_in_tool_results':result.get('user_contacts_in_tool_results'),'provider_calls':0}),flush=True)
            except Exception as error:
                outcomes.append({'catalog_index':index,'failed':True,'error_type':type(error).__name__})
                print(json.dumps({'case':index+1,'failed':True,'error_type':type(error).__name__,'provider_calls':0}),flush=True)
    store=RunStore('real-sensitive-corpus-catalog-v1',True)
    store.encrypt('case-handoffs.aesgcm',outcomes)
    result=store.finish({'kind':'real_sensitive_corpus_catalog','source_run':args.source,'cases':outcomes,
        'complete_qualified_cases':sum(bool(x.get('complete_qualified')) for x in outcomes),
        'cases_with_tool_contacts':sum(bool(x.get('tool_calls_with_contacts')) for x in outcomes),
        'cases_user_contact_into_tools':sum(bool(x.get('user_contacts_in_tool_arguments') or x.get('user_contacts_in_tool_results')) for x in outcomes),
        'provider_calls':0,'remote_mutations':0,'manual_pii_labels':False})
    print(json.dumps({key:result[key] for key in ('run_id','complete_qualified_cases','cases_with_tool_contacts','cases_user_contact_into_tools','provider_calls','remote_mutations')}))


if __name__=='__main__':main()
