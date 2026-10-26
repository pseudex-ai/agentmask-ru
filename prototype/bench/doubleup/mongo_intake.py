"""Read-only Mongo thread export; Langfuse joins use original dialogue identities.

Credentials are loaded in RAM from the authorized GitOps config, passed through
stdin (never argv/env logs), and never archived. The one-shot driver has Docker
logging disabled; original EJSON travels only over a captured local pipe into an
immutable encrypted RunStore. No repository/GraphManager constructors are used:
those create indexes even on a nominal read.
"""

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

import yaml

from .storage import PilotError, RunStore, hashed

CONFIG = Path('/Users/igor/Projects/2up/projects/2up-aiplatform-gitops/2up-aiplatform-backend/values-prod.yaml')
IMAGE = '2up-aiplatform-backend-user_api:latest'
MAX_BYTES = 64 * 1024 * 1024

READER = r'''
import json,sys,re
from pymongo import MongoClient
from bson import json_util
config=json.loads(sys.stdin.readline())
phase='connect'
try:
    with MongoClient(config['uri'],serverSelectionTimeoutMS=5000,connectTimeoutMS=5000,socketTimeoutMS=30000,
            appname='doubleup-local-readonly-thread-export') as client:
        db=client[config['database']]
        # A candidate signal, NOT PII annotation/recall: prioritize conversations
        # containing contact/identifier-like source text for qualitative review.
        signal=r'(?i)([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|(?:\+7|8)[ ()-]*\d{3}[ ()-]*\d{3}[ ()-]*\d{2}[ ()-]*\d{2}|паспорт|снилс|фио|телефон)'
        pipeline=[{'$match':{'sender.type':{'$in':['user','assistant']}}},
            {'$group':{'_id':'$thread_id','message_documents':{'$sum':1},
                'users':{'$sum':{'$cond':[{'$eq':['$sender.type','user']},1,0]}},
                'assistants':{'$sum':{'$cond':[{'$eq':['$sender.type','assistant']},1,0]}},
                'first':{'$min':'$created_at'},'last':{'$max':'$created_at'}}},
            {'$match':{'users':{'$gte':config['min_turns']},'assistants':{'$gte':config['min_turns']},'_id':{'$ne':None}}},
            {'$sort':{'last':-1,'users':-1,'_id':1}},{'$limit':100}]
        phase='candidate_counts'
        candidates=list(db.messages.aggregate(pipeline,maxTimeMS=20000))
        result={'format':'mongo-extended-json-canonical-v2','candidates':candidates,'threads':[],
            'source_collection_counts':{name:db[name].estimated_document_count(maxTimeMS=4000) for name in ('threads','messages','graph_states','thread_compactions')},
            'read_only':True,'mutations':0,'candidate_bound':100,'all_thread_messages_no_date_window':True}
        for candidate in candidates:
            if len(result['threads'])>=config['limit']:break
            phase='thread_export'
            tid=candidate['_id'];thread=db.threads.find_one({'thread_id':tid})
            if not thread:continue
            candidate['signals']=db.messages.count_documents({'thread_id':tid,'content.text':{'$regex':signal}},maxTimeMS=5000)
            if not candidate['signals']:continue
            messages=list(db.messages.find({'thread_id':tid}).sort([('created_at',1),('_id',1)]))
            roots={'thread_id':tid,'checkpoint_ns':''}
            earliest=db.graph_states.find_one(roots,sort=[('ts',1),('checkpoint_id',1)])
            latest=db.graph_states.find_one(roots,sort=[('ts',-1),('checkpoint_id',-1)])
            compactions=list(db.thread_compactions.find({'thread_id':tid}).sort('created_at',1))
            result['threads'].append({'candidate':candidate,'thread':thread,'messages':messages,
                'root_checkpoint_count':db.graph_states.count_documents(roots),
                'earliest_root_checkpoint':earliest,'latest_root_checkpoint':latest,'compactions':compactions})
        print(json_util.dumps({'ok':True,'payload':result},json_options=json_util.CANONICAL_JSON_OPTIONS))
except Exception as error:
    print(json.dumps({'ok':False,'error_type':type(error).__name__,'server_code':getattr(error,'code',None),'phase':phase}))
'''


def read_config(path=CONFIG):
    values = yaml.safe_load(path.read_text())
    env = values.get('env', {}) if isinstance(values, dict) else {}
    uri, database = env.get('MONGO_URI'), env.get('MONGO_DB_NAME')
    if not isinstance(uri, str) or not uri.startswith('mongodb://') or not isinstance(database, str) or not database:
        raise PilotError('mongo_export_config_missing')
    return {'uri': uri, 'database': database}


def collect(run_id, limit, min_turns):
    if not 1 <= limit <= 10 or not 3 <= min_turns <= 100:
        raise PilotError('mongo_export_bounds_invalid')
    store = RunStore(run_id, True)
    config = {**read_config(), 'limit': limit, 'min_turns': min_turns}
    process = subprocess.run(['docker', 'run', '--rm', '--network', 'host', '--log-driver', 'none', '-i',
        IMAGE, 'python', '-c', READER], input=json.dumps(config).encode(), capture_output=True, timeout=120)
    if process.returncode or len(process.stdout) > MAX_BYTES:
        raise PilotError('mongo_export_process_or_size_refused')
    try:
        response = json.loads(process.stdout)
    except ValueError:
        raise PilotError('mongo_export_response_invalid') from None
    if response.get('ok') is not True:
        failure = {key: response.get(key) for key in ('error_type','server_code','phase')}
        store.finish({'kind':'mongo_export_failure','failure':failure,'remote_mutations':0,'provider_calls':0})
        print(json.dumps({'mongo_read_failure':failure}),file=sys.stderr)
        raise PilotError('mongo_export_read_failed')
    payload = response['payload']
    store.encrypt('mongo-originals.aesgcm', payload)
    def number(value):
        if isinstance(value, dict):
            return int(value.get('$numberInt', value.get('$numberLong', 0)))
        return int(value or 0)
    summaries = [{'thread_sha256': hashed(item['thread']['thread_id']),
        'user_message_documents': number(item['candidate']['users']),
        'assistant_message_documents': number(item['candidate']['assistants']),
        'candidate_signal_messages': number(item['candidate']['signals']),
        'exported_message_documents': len(item['messages']),
        'root_checkpoints': number(item['root_checkpoint_count']),
        'compactions': len(item['compactions']),
        'has_latest_checkpoint': bool(item['latest_root_checkpoint']),
        'has_earliest_checkpoint': bool(item['earliest_root_checkpoint'])} for item in payload['threads']]
    manifest = store.finish({'kind':'mongo_thread_export','created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'min_user_turns':min_turns,'thread_limit':limit,'candidate_threads':len(payload['candidates']),
        'exported_threads':len(summaries),'threads':summaries,'source_config_path':str(CONFIG),
        'raw_ejson_preserved':True,'all_thread_messages_no_date_window':True,
        'selection_is_pii_candidate_signal_not_annotation':True,'requires_checkpoint_history_dedup':True,
        'provider_calls':0,'remote_mutations':0,'credentials_archived':False,'docker_logging':'none'})
    return {'run_id':run_id,'candidate_threads':len(payload['candidates']),'exported_threads':len(summaries),
        'threads':manifest['threads'],'provider_calls':0,'remote_mutations':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--limit',type=int,default=6)
    parser.add_argument('--min-turns',type=int,default=5)
    args=parser.parse_args()
    try:
        print(json.dumps(collect(args.run_id,args.limit,args.min_turns)))
    except Exception as error:
        code=error.args[0] if isinstance(error,PilotError) and error.args and str(error.args[0]).startswith('mongo_') else 'mongo_export_unavailable'
        print(json.dumps({'ok':False,'error_code':code}),file=sys.stderr)
        raise SystemExit(2)


if __name__=='__main__':main()
