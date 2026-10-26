"""Read-only real chat selection requiring contacts in ORIGINAL USER messages."""

import argparse
from collections import Counter
import json
import subprocess
import sys

from .mongo_intake import IMAGE, read_config
from .mongo_dialogues import EvidenceClient, application_client
from .qualify_dialogues import evidence
from .storage import RunStore, hashed

READER = r'''
import json,sys
from pymongo import MongoClient
from bson import json_util
c=json.loads(sys.stdin.readline())
try:
 with MongoClient(c['uri'],serverSelectionTimeoutMS=5000,socketTimeoutMS=30000,appname='doubleup-readonly-sensitive-dialogue-intake') as client:
  db=client[c['database']]
  grouped=list(db.messages.aggregate([{'$match':{'sender.type':{'$in':['user','assistant']}}},
   {'$group':{'_id':'$thread_id','users':{'$sum':{'$cond':[{'$eq':['$sender.type','user']},1,0]}},'assistants':{'$sum':{'$cond':[{'$eq':['$sender.type','assistant']},1,0]}},'last':{'$max':'$created_at'}}},
   {'$match':{'users':{'$gte':3},'assistants':{'$gte':3},'_id':{'$ne':None}}},{'$sort':{'last':-1,'_id':1}}],maxTimeMS=20000))
  chosen=grouped[:c['candidate_cap']];ids=[x['_id'] for x in chosen]
  threads=list(db.threads.find({'thread_id':{'$in':ids}}, {'_id':0,'thread_id':1,'org_id':1,'user_id':1,'graph_id':1,'project_id':1,'title':1,'created_at':1,'last_activity':1,'status':1}))
  users=list(db.messages.find({'thread_id':{'$in':ids},'sender.type':'user'}, {'_id':0,'thread_id':1,'message_id':1,'content':1,'created_at':1}).sort([('created_at',1),('message_id',1)]))
  graph_ids=list({x['graph_id'] for x in threads if x.get('graph_id')})
  graphs=list(db.graphs.find({'graph_id':{'$in':graph_ids}}, {'_id':0,'graph_id':1,'builtin_id':1,'type':1}))
  print(json_util.dumps({'ok':True,'payload':{'eligible_total':len(grouped),'candidate_cap':c['candidate_cap'],'candidates':chosen,'threads':threads,'user_messages':users,'graph_types':graphs,'original_user_messages_all_history':True,'remote_mutations':0}},json_options=json_util.CANONICAL_JSON_OPTIONS))
except Exception as e:print(json.dumps({'ok':False,'error_type':type(e).__name__,'code':getattr(e,'code',None)}))
'''


def number(value):
    return int(value.get('$numberInt', value.get('$numberLong', 0))) if isinstance(value, dict) else int(value)


def collect(run_id, candidate_cap, selection_limit):
    if not 10 <= candidate_cap <= 400 or not 6 <= selection_limit <= 50:
        raise RuntimeError('invalid_selection_bounds')
    store = RunStore(run_id, True)
    result = subprocess.run(['docker','run','--rm','--network','host','--log-driver','none','-i',IMAGE,'python','-c',READER],
        input=json.dumps({**read_config(),'candidate_cap':candidate_cap}).encode(),capture_output=True,timeout=120)
    if result.returncode or len(result.stdout)>96*1024*1024:raise RuntimeError('source_read_or_size_refused')
    value=json.loads(result.stdout)
    if value.get('ok') is not True:raise RuntimeError('source_read_failed')
    raw=value['payload'];store.encrypt('original-user-candidate-inventory.aesgcm',raw)
    client=EvidenceClient(application_client(),store,1,1)
    sessions,proof=client.paginated('/api/public/sessions',{},30)
    session_ids={row['id'] for row in sessions}
    users={}
    for message in raw['user_messages']:users.setdefault(message['thread_id'],[]).append(message)
    thread_map={row['thread_id']:row for row in raw['threads']}
    graph_map={row['graph_id']:row.get('builtin_id','custom_or_unknown') for row in raw['graph_types']}
    candidates=[];summary=[]
    for row in raw['candidates']:
        tid=row['_id'];thread=thread_map.get(tid)
        if not thread or not thread.get('org_id') or not thread.get('user_id'):continue
        contacts=[]
        for index,message in enumerate(users.get(tid,[])):
            contacts.extend(evidence(message.get('content'),f'/source_user_messages/{index}/content'))
        if not contacts:continue
        types=Counter(x['type'] for x in contacts)
        record={'thread':thread,'source_user_messages':users.get(tid,[]),'user_contact_evidence':contacts,
            'mongo_user_documents':number(row['users']),'mongo_assistant_documents':number(row['assistants']),
            'application_session_present':tid in session_ids,'graph_type':graph_map.get(thread.get('graph_id'),'unknown')}
        candidates.append(record)
        summary.append({'thread_sha256':hashed(tid),'user_message_documents':record['mongo_user_documents'],
            'user_contact_occurrences':dict(types),'application_session_present':record['application_session_present'],
            'graph_type':record['graph_type']})
    # No outcome selection: source contact evidence + real app-session membership,
    # deterministic round-robin tenants and graph types before any model replay.
    ready=[record for record in candidates if record['application_session_present']]
    buckets={}
    for record in ready:buckets.setdefault((record['thread']['org_id'],record['graph_type']),[]).append(record)
    selected=[]
    while buckets and len(selected)<selection_limit:
        for key in sorted(list(buckets),key=hashed):
            selected.append(buckets[key].pop(0))
            if not buckets[key]:del buckets[key]
            if len(selected)>=selection_limit:break
    store.encrypt('qualified-candidates.aesgcm',{'candidates':candidates,'selected':selected,
        'original_values_unchanged':True,'contact_shape_evidence_not_manual_labels':True})
    manifest=store.finish({'kind':'real_user_sensitive_chat_inventory','candidate_cap':candidate_cap,
        'eligible_multiuser_threads':number(raw['eligible_total']),'scanned_candidate_threads':len(raw['candidates']),
        'source_user_message_documents':len(raw['user_messages']),'user_contact_dialogues':len(candidates),
        'contact_dialogues_with_app_session':len(ready),'selected_for_full_export':len(selected),
        'application_sessions_complete':proof,'source_contact_summary':summary,
        'selected_summary':[{'thread_sha256':hashed(r['thread']['thread_id']),'users':r['mongo_user_documents'],
            'graph_type':r['graph_type'],'contact_types':dict(Counter(x['type'] for x in r['user_contact_evidence']))} for r in selected],
        'provider_calls':0,'remote_mutations':0,'source_values_encrypted':True,'manual_pii_labels':False,
        'source_credential_values_archived':False,'requests':client.client.requests})
    store.verify()
    print(json.dumps({key:manifest[key] for key in ('run_id','eligible_multiuser_threads','scanned_candidate_threads',
        'source_user_message_documents','user_contact_dialogues','contact_dialogues_with_app_session','selected_for_full_export',
        'selected_summary','provider_calls','remote_mutations')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True)
    parser.add_argument('--candidate-cap',type=int,default=300);parser.add_argument('--selection-limit',type=int,default=30)
    args=parser.parse_args()
    try:collect(args.run_id,args.candidate_cap,args.selection_limit)
    except Exception as error:
        print(json.dumps({'ok':False,'error_type':type(error).__name__,'code':'sensitive_inventory_unavailable'}),file=sys.stderr)
        raise SystemExit(2)
