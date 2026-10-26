"""Expose actual archived ROOT dialogues in the PRIVATE LOCAL chat, no inference."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

from stand import ROOT, STATE

sys.path.insert(0,str(ROOT/'prototype'))
from bench.doubleup.storage import RunStore

IMPORTER=r'''
import json,os,sys,logging
logging.disable(logging.CRITICAL)
from datetime import datetime,timezone
from pymongo import MongoClient
from langchain_core.messages import messages_from_dict
from langgraph.checkpoint.base import empty_checkpoint
from graph_manager.mongo_graph_saver import MongoSaver
if os.environ.get('PSEUDEX_PILOT')!='1' or os.environ.get('MONGO_DB_NAME')!='doubleup_pilot':raise RuntimeError('local_only')
p=json.load(sys.stdin);scope=p['scope'];org='doubleup-source-corpus'
if scope['tenant_id']!=org or scope['owner_id']!='pilot-owner':raise RuntimeError('source_scope_refused')
client=MongoClient(os.environ['MONGO_URI']);db=client['doubleup_pilot'];now=datetime.now(timezone.utc)
db.organizations.update_one({'org_id':org},{'$setOnInsert':{'org_id':org,'slug':org,'name':'Исходные диалоги с чувствительными данными','owner_id':'pilot-owner','status':'active','created_at':now}},upsert=True)
db.organization_members.update_one({'org_id':org,'user_id':'pilot-owner'},{'$setOnInsert':{'org_id':org,'user_id':'pilot-owner','role':'owner','status':'active','created_at':now}},upsert=True)
db.graphs.update_one({'graph_id':scope['agent_id']},{'$set':{'graph_id':scope['agent_id'],'org_id':org,'user_id':'pilot-owner','builtin_id':'simple_chat','type':'builtin','enabled':True,'public':False,'name':p['label'],'description':'Сохранённый исходный диалог MongoDB + Langfuse. Только просмотр: это не новый прогон и не ответ пилотной модели.','pilot_source_original':True,'pilot_source_run':p['source_run'],'pilot_source_agent_type':p['source_agent_type'],'model_id':'source-original-read-only','ai_model':'source-original-read-only','tools':[],'default_tools':[],'retrieval':{'enabled':False},'kb_tools':False,'security_level':3,'created_at':now}},upsert=True)
messages=messages_from_dict([{'type':m['type'],'data':m} for m in p['messages']])
checkpoint=empty_checkpoint();checkpoint['channel_values']={'messages':messages}
saver=MongoSaver();saver.put({'configurable':{'thread_id':scope['thread_id'],'checkpoint_ns':''}},checkpoint,{'source':'update','step':0,'parents':{},'source_original':True,'source_run':p['source_run']},{})
db.threads.update_one({'thread_id':scope['thread_id']},{'$set':{'thread_id':scope['thread_id'],'org_id':org,'graph_id':scope['agent_id'],'user_id':'pilot-owner','title':p['label'],'status':'active','created_at':now,'last_activity':now,'message_count':len(messages),'pilot_source_original':True,'pilot_source_run':p['source_run']}},upsert=True)
client.close();print(json.dumps({'ok':True,'messages':len(messages),'provider_calls':0}))
'''


def import_case(index):
    source_run=f'real-sensitive-corpus-{index:03d}-v1';store=RunStore(source_run,False);manifest=store.verify()
    if not manifest.get('complete_qualified'):raise RuntimeError('unqualified_or_incomplete_source')
    private=store.read_encrypted('complete-sensitive-dialogue.aesgcm');dialogue=private['dialogue']
    stable=manifest['source_thread_sha256'];scope={'tenant_id':'doubleup-source-corpus','owner_id':'pilot-owner',
        'agent_id':str(uuid.uuid5(uuid.NAMESPACE_URL,'source-corpus:graph:'+stable)),
        'thread_id':str(uuid.uuid5(uuid.NAMESPACE_URL,'source-corpus:thread:'+stable))}
    hops=manifest['user_contacts_in_tool_arguments'] or manifest['user_contacts_in_tool_results']
    label=f'Исходник {index:02d} · {manifest["root_user_turns"]} ходов · '+('контакты в тулах' if hops else 'контакты в переписке')
    request={'scope':scope,'label':label,'source_run':source_run,'source_agent_type':manifest['source_graph_type'],'messages':dialogue['messages']}
    process=subprocess.run(['docker','exec','-i','obscura-doubleup-pilot-graph_server-1','python','-c',IMPORTER],
        input=json.dumps(request,ensure_ascii=True).encode(),capture_output=True,timeout=30)
    if process.returncode:raise RuntimeError('local_source_import_failed')
    result=json.loads(process.stdout.strip().splitlines()[-1]);assert result['ok']
    traces=dialogue['langfuse']['trace_details'];first=traces[0] if traces else {}
    html=first.get('htmlPath');source_url='https://langfuse.inf.2up.dev'+html if isinstance(html,str) and html.startswith('/') else None
    trace_map={trace['id']:trace for trace in traces};tool_links=[];seen=set()
    for proof in private['sensitivity']['tool_execution_contact_evidence']:
        trace=trace_map.get(proof['trace_id'],{});html=trace.get('htmlPath')
        if proof['name'] in seen or not isinstance(html,str) or not html.startswith('/'):continue
        seen.add(proof['name']);tool_links.append({'name':proof['name'],
            'source_trace_url':'https://langfuse.inf.2up.dev'+html,
            'contacts_in_arguments':bool(proof['arguments']),'contacts_in_result':bool(proof['result'])})
    return {'index':index,'label':label,'source_run':source_run,'user_turns':manifest['root_user_turns'],
        'source_contact_types':manifest['source_contact_types'],'source_tool_execution_spans':manifest['source_tool_execution_spans'],
        'tool_calls_with_contacts':manifest['tool_calls_with_contacts'],'tools_with_contacts':manifest['tools_with_contacts'],
        'user_contacts_in_tool_arguments':manifest['user_contacts_in_tool_arguments'],'user_contacts_in_tool_results':manifest['user_contacts_in_tool_results'],
        'source_trace_count':len(traces),'source_observation_count':dialogue['langfuse']['counts']['observations'],
        'url':f'http://127.0.0.1:18880/{scope["tenant_id"]}/assistantnew/{scope["agent_id"]}?thread={scope["thread_id"]}',
        'first_source_trace_url':source_url,'source_tool_trace_links':tool_links,'original_history_not_replay':True,'provider_calls':0,'remote_mutations':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--case',type=int,action='append',required=True);args=parser.parse_args()
    rows=[import_case(index) for index in args.case];target=STATE/'source-corpus-local-catalog.json'
    previous=json.loads(target.read_text()) if target.exists() else {'cases':[]}
    merged={row['index']:row for row in previous['cases']};merged.update({row['index']:row for row in rows})
    report={'cases':[merged[index] for index in sorted(merged)],'source_originals_only':True,'raw_pii_in_catalog':False,'provider_calls':0}
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False));target.chmod(0o600)
    print(json.dumps({'imported':rows,'provider_calls':0,'new_model_answers':0}))
