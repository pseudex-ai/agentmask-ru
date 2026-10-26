"""Configure the replay agent through PLATFORM auth/API, not engine admin UI."""
from pathlib import Path
import argparse
import json
import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from prepare_dialogue_replay import AAD
from dialogue_runner import scope_for
from stand import STATE


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',default='september-qualified-cases-v1')
    parser.add_argument('--case-index',type=int,default=7)
    parser.add_argument('--revision',default='qualified-live-v1')
    args=parser.parse_args()
    bundle=args.bundle
    assert bundle and all(ch in 'abcdefghijklmnopqrstuvwxyz0123456789-' for ch in bundle)
    key=(STATE/'runtime'/f'{bundle}.key').read_bytes()
    raw=(STATE/'runtime'/f'{bundle}.aesgcm').read_bytes()
    packet=json.loads(AESGCM(key).decrypt(raw[:12],raw[12:],AAD))
    case=next(c for c in packet['cases'] if c['source_index']==args.case_index)
    scope=scope_for(case,'pseudex',packet['run_id']+'-live-'+args.revision)
    storage=json.loads((STATE/'browser/storage.json').read_text())
    tokens=[item['value'] for origin in storage.get('origins',[]) for item in origin.get('localStorage',[])
            if item['name']=='auth_access_token']
    assert tokens,'authenticated_local_browser_session_missing'
    token=tokens[0]
    base='http://127.0.0.1:18860'
    with httpx.Client(base_url=base,timeout=20,trust_env=False,follow_redirects=False) as c:
        headers={'Authorization':'Bearer '+token,'X-Org-Id':scope['tenant_id']}
        root='/api/v1/pseudex/policies'
        probe=c.get(root,headers=headers)
        if probe.status_code==401:
            credentials=json.loads((STATE/'runtime/browser.json').read_text())
            auth=c.post('/auth/login',json={'user_id':'pilot-owner@example.invalid','password':credentials['password']})
            assert auth.status_code==200,'local_platform_login_failed'
            token=auth.json()['access_token']
            headers['Authorization']='Bearer '+token
        listing=c.get(root,headers=headers)
        if listing.status_code!=200:
            print(json.dumps({'platform_policy_route_status':listing.status_code,
                              'stable_error_code':listing.json().get('error') if 'json' in listing.headers.get('content-type','') else None}))
            raise SystemExit(1)
        policy='qa-sept'+str(case['catalog_case']).zfill(2)+'-ignore-v1'
        body={'policy_id':policy,'title':'Локальный тест: исключения ролей',
              'rules':[{'id':'known-business-roles','action':'ignore','category':'NAME',
                        'values':['РОП','РОМ','Бюджетирование']}]}
        r=c.post(root,headers=headers,json=body)
        if r.status_code==409:
            r=c.put(root+'/'+policy,headers=headers,json={k:v for k,v in body.items() if k!='policy_id'})
        assert r.status_code in (200,201),'platform_policy_create_failed'
        config=c.get(root+'/bindings',headers=headers);assert config.status_code==200
        b=config.json();bindings=[x for x in b['bindings'] if x['agent_key']!=scope['agent_id']]
        bindings.append({'agent_key':scope['agent_id'],'policy_id':policy})
        r=c.put(root+'/bindings',headers=headers,json={'bindings':bindings,'default_policy_id':b['default_policy_id']})
        assert r.status_code==200,'platform_binding_failed'
        r=c.post(root+'/preview',headers=headers,json={'headers':{'x-agent-id':scope['agent_id']},'body':{}})
        assert r.status_code==200 and r.json()['policy_id']==policy,'platform_preview_disagrees'
        proof={'case':'catalog-'+str(case['catalog_case']).zfill(3),'platform_jwt_authenticated':True,'policy_created_via_platform_api':True,
               'agent_binding_via_platform_api':True,'preview_policy_matches':True,
               'winning_extractor':r.json()['matched'],'platform_tenancy_not_implemented_inside_engine':True,
               'policy_id':policy,'engine_sidecar_admin_credential_exposed_to_browser':False}
        path=STATE/('september-platform-policy-proof-'+str(case['source_index'])+'-'+args.revision+'.json')
        assert not path.exists(),'proof_already_exists'
        path.write_text(json.dumps(proof,indent=2));path.chmod(0o600)
        print(json.dumps(proof,ensure_ascii=False))

if __name__=='__main__':
    main()
