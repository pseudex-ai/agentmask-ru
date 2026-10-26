"""Archive real backend boundary evidence; print no source values or tokens."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'prototype'))
from bench.doubleup.storage import RunStore
from dialogue_runner import scope_for,unseal
from prepare_dialogue_replay import AAD

REMOTE=r'''
import json,os,sys,logging
logging.disable(logging.CRITICAL)
assert os.environ.get('MONGO_DB_NAME')=='doubleup_pilot'
from repository.pseudex_pilot_inspections import get_inspection_store
from services.pseudex_pilot import _restore, PilotProtectionError
scope=json.loads(sys.stdin.read());store=get_inspection_store()
rows=store.list_attempts(scope['tenant_id'],scope['thread_id'])
entries=[store.get_attempt(scope['tenant_id'],r['attempt_id']) for r in reversed(rows)]
diagnostic=[]
for item in entries:
 if item['mode']=='pseudex' and item['status']=='failed' and not item.get('model_request'):
  import httpx
  from services.pseudex_pilot import sidecar_scope, _masked_body
  body=item['source_request']
  with httpx.Client(trust_env=False,timeout=90) as c:
   r=c.post(os.environ['PSEUDEX_BASE_URL'].rstrip('/')+'/mask',
      headers={'Authorization':'Bearer '+os.environ['PSEUDEX_GATEWAY_TOKEN'],'X-Agent-Id':scope['agent_id']},
      json={**sidecar_scope(scope,item['attempt_id']), 'messages':body['messages'],
            **({'tools':body['tools']} if 'tools' in body else {}),'inspection':True})
  try:data=r.json()
  except ValueError:data={'error':'non_json_engine_error'}
  check=None
  if r.status_code==200:
   try:_masked_body(body,data);check='routing_preserved'
   except PilotProtectionError:check='routing_changed'
  diagnostic.append({'phase':'mask_before_provider','http_status':r.status_code,
    'error':data.get('error'),'category':data.get('category'),'routing_check':check,
    'response_fields':list(data),'new_provider_calls':0})
 if item['mode']=='pseudex' and item['status']=='failed' and isinstance(item.get('model_response'),dict) and item['model_response'].get('choices'):
  try:
   _restore(item['model_response'],scope,item['attempt_id'])
   diagnostic.append({'replay_restore_ok':True,'new_provider_calls':0})
  except Exception as e:
   allowed={'Sidecar reported unresolved tokens','Sidecar rejected pilot operation',
            'Malformed restoration receipt','Text-encoded tool protocol is unsupported in protected mode',
            'Sidecar operation unavailable or malformed','Sidecar changed completion structure',
            'Sidecar changed completion tool routing'}
   code=str(e) if str(e) in allowed else 'restore_refused_other'
   diagnostic.append({'replay_restore_ok':False,'error_type':type(e).__name__,'error_code':code,'new_provider_calls':0})
print(json.dumps({'attempts':entries,'diagnostic':diagnostic},ensure_ascii=True))
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',default='september-qualified-cases-v1')
    parser.add_argument('--case-index',type=int,default=7)
    parser.add_argument('--revision',default='qualified-live-v1')
    parser.add_argument('--archive',required=True)
    args=parser.parse_args()
    state=HERE/'.state';bundle=args.bundle
    assert bundle and all(ch in 'abcdefghijklmnopqrstuvwxyz0123456789-' for ch in bundle)
    key=(state/'runtime'/f'{bundle}.key').read_bytes();raw=(state/'runtime'/f'{bundle}.aesgcm').read_bytes()
    packet=json.loads(AESGCM(key).decrypt(raw[:12],raw[12:],AAD))
    case=next(c for c in packet['cases'] if c['source_index']==args.case_index)
    folder=state/(packet['run_id']+'-live-'+args.revision)
    archive=RunStore(args.archive,True)
    reports=[]
    for mode in ('none','builtin','pseudex'):
        scope=scope_for(case,mode,folder.name)
        r=subprocess.run(['docker','exec','-i','obscura-doubleup-pilot-graph_server-1',
                          'python','-c',REMOTE],input=json.dumps(scope).encode(),capture_output=True,timeout=90)
        if r.returncode:raise RuntimeError('backend_private_evidence_export_failed')
        try: evidence=json.loads(r.stdout)
        except ValueError:raise RuntimeError('backend_export_not_private_json') from None
        archive.encrypt(mode+'.aesgcm',evidence)
        rows=evidence['attempts']
        summary={'case':'source-case-'+str(case['catalog_case']).zfill(3),'mode':mode,'attempts':len(rows),
                 'failed_attempts':sum(x['status']=='failed' for x in rows),
                 'tool_dispatches':sum(len(x.get('tool_dispatches',[])) for x in rows),
                 'tool_results':sum(len(x.get('tool_results',[])) for x in rows),
                 'mask_receipts':sum(bool(x.get('inspection')) for x in rows),
                 'restore_receipts':sum(bool(x.get('restoration')) for x in rows),
                 'diagnostic':evidence['diagnostic'],
                 'new_provider_calls':0}
        prefix=case['case_id']+'-'+mode
        complete=folder/(prefix+'.complete.aesgcm')
        if complete.exists():
            x=unseal(complete,key,prefix+':complete')
            summary.update(status='complete',turns=x['turns'],tool_errors=x['tool_errors'],url=x['url'])
        else:
            failed=list(folder.glob(prefix+'*.failed.aesgcm'))
            if failed:
                f=failed[-1];x=unseal(f,key,f.name[:-len('.failed.aesgcm')]+':failed')
                summary.update(status='stopped',turns=x['counts']['turns'],tool_errors=x['counts']['tool_errors'],
                               model_statuses=x['actual_bridge_payload'].get('model_statuses'))
        archive.encrypt(mode+'-summary.aesgcm',summary)
        reports.append(summary)
    archive.finish({'kind':'actual_doubleup_live_three_mode_boundary_evidence','arms':3,
                    'provider_calls_from_export':0,'source_mutations':0})
    archive.verify()
    public=[{k:v for k,v in row.items() if k!='url'} for row in reports]
    path=state/(args.archive+'-summary.json');path.write_text(json.dumps(public,ensure_ascii=False,indent=2));path.chmod(0o600)
    print(json.dumps({'arms':public},ensure_ascii=False))

if __name__=='__main__':
    main()
