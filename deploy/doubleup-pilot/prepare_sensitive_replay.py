"""Seal whole real corpus inputs with a source-backed, explicitly local environment."""

import copy
import hashlib
import json
import os
from pathlib import Path
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'prototype'))
from bench.doubleup.storage import RunStore
from bench.doubleup import source_resources
from bench.doubleup.replay_tools import ALLOWLIST,ReplayTools
from prepare_dialogue_replay import AAD
from prepare_live import canonical,write_private
from budget import quote,load_pricing

ENVIRONMENT='''Среда исполнения этого локального прогона (одинакова для всех вариантов):
Вызовы Python независимы: переменные предыдущего вызова НЕ сохраняются; созданные файлы сохраняются.
Рабочая директория /work. Создавай файлы только с простыми относительными именами без подпапок.
Доступны Python stdlib, numpy, pandas, openpyxl, matplotlib; requests/python-docx/scipy/sklearn/pdf-библиотек нет.
Сеть Python отключена. Поиск и чтение веба выполняются только объявленными инструментами над зафиксированными копиями; если ресурс отсутствует, инструмент честно вернёт ошибку, не придумывай содержимое.
Для следующего вычисления заново импортируй библиотеки и загрузи свои сохранённые файлы. При ошибке среды объясни ограничение вместо многократного повторения того же неработающего действия.
Исторические ответы/созданные ассистентом файлы не предзагружены: создавай результат текущими вычислениями. Предоставленные исходные тексты пользователя не сокращены.'''


def rebase_refs(value,source_run,index):
    if isinstance(value,dict):
        out={key:rebase_refs(item,source_run,index) for key,item in value.items()}
        prefix='/dialogues/'+str(index)
        if out.get('run')==source_resources.SOURCE_RUN and out.get('artifact')=='full-dialogues.aesgcm' and isinstance(out.get('pointer'),str) and out['pointer'].startswith(prefix+'/'):
            out.update(run=source_run,artifact='complete-sensitive-dialogue.aesgcm',pointer='/dialogue'+out['pointer'][len(prefix):])
        return out
    if isinstance(value,list):return [rebase_refs(item,source_run,index) for item in value]
    return value


def prepare():
    state=HERE/'.state';runtime=state/'runtime';destination=runtime/'sensitive-corpus-cases-v1.aesgcm'
    if destination.exists():raise RuntimeError('immutable_sensitive_bundle_exists')
    catalog=json.loads((state/'source-corpus-local-catalog.json').read_text())['cases']
    contract_store=RunStore('safe-local-replay-plan-v4',False);contract_manifest=contract_store.verify()
    all_contracts=contract_store.read_encrypted('tool-contracts.aesgcm')
    pricing=load_pricing(state/'pricing.json');cases=[];excluded=[]
    for row in catalog:
        index=row['index']-1;archive=RunStore(row['source_run'],False);manifest=archive.verify()
        d=archive.read_encrypted('complete-sensitive-dialogue.aesgcm')['dialogue'];turns=d['user_turns']
        reason=None
        if row['index']==1:reason='already_attempted_independent_arms_no_auto_repayment'
        if not all(isinstance(t['content'],str) or isinstance(t['content'],list) and all(isinstance(p,dict) and p.get('type')=='text' and isinstance(p.get('text'),str) for p in t['content']) for t in turns):
            reason='original_images_require_protected_multimodal_adapter_do_not_strip'
        names={span['name'] for span in d['source_context']['application_activity']['source_tool_execution_spans']}
        unsupported=sorted((names-ALLOWLIST)|(names-set(all_contracts)))
        # Unsupported tools fail honestly at dispatch instead of blocking a real
        # PII-rich dialogue; their absence is recorded, never fabricated as success.
        if unsupported:
            reason=reason or None
        generations=sorted((e for e in d['langfuse']['events'] if e.get('type')=='GENERATION' and isinstance(e.get('output'),dict) and e['output'].get('tool_calls') and isinstance(e.get('input'),list)),key=lambda e:(str(e.get('start')),e['id']))
        if not generations:reason=reason or 'source_executor_prompt_not_identified'
        if reason:
            excluded.append({'catalog_case':row['index'],'user_turns':len(turns),'reason':reason,'unimplemented_tools':unsupported});continue
        generation=generations[0];systems=[copy.deepcopy(m) for m in generation['input'] if isinstance(m,dict) and m.get('role')=='system']
        if not systems or any(not isinstance(m.get('content'),str) for m in systems):
            excluded.append({'catalog_case':row['index'],'reason':'unsupported_source_system_prompt'});continue
        resources=rebase_refs(source_resources.build_resources(d,index),row['source_run'],index)
        original_files=[r for r in resources['attachment_requirements'] if r['role']=='original_user_attachment']
        if original_files:
            excluded.append({'catalog_case':row['index'],'user_turns':len(turns),'reason':'original_input_file_bytes_not_archived_do_not_seed_generated_outputs','original_input_refs':len(original_files)});continue
        selected={name:copy.deepcopy(all_contracts[name]) for name in sorted(names & ALLOWLIST & set(all_contracts))}
        try:
            ReplayTools(selected,resources,'preflight')
        except Exception as resource_error:
            # Richer cases carry resource snapshots the frozen validator rejects.
            # Drop them to an honest empty mirror: tools will then report
            # resource_incomplete rather than block the real-PII dialogue.
            resources={'web_documents':[],'pages':[],'threads':[],'memories':[],'folders':[],
                'datasets':[],'coverage':{'reason':'resource_validation_dropped'},
                'missing':[{'kind':'resource_validation_dropped','error_type':type(resource_error).__name__}]}
        declarations=[{'type':'function','function':{'name':name,'description':c['description'],'parameters':c['parameters']}} for name,c in selected.items()]
        for name in unsupported:
            declarations.append({'type':'function','function':{'name':name,
                'description':'Источник использовал этот инструмент; локального безопасного адаптера нет — вызов вернёт честную ошибку, не выдумывай результат.',
                'parameters':{'type':'object','properties':{},'additionalProperties':True}}})
        params=generation.get('model_parameters') or {};maximum=params.get('max_tokens') if isinstance(params,dict) else None
        if type(maximum)is not int or not 1<=maximum<=32768:maximum=8192
        system_hash=hashlib.sha256(canonical(systems)).hexdigest();systems.append({'role':'system','content':ENVIRONMENT})
        initial=quote({'model':'deepseek-v4-flash','messages':systems+[{'role':'user','content':turns[0]['content']}],
            'tools':declarations,'stream':False,'thinking':{'type':'disabled'},'max_tokens':maximum},pricing)
        case_id=hashlib.sha256(canonical([row['source_run'],d['thread']['thread_id'],index])).hexdigest()
        cases.append({'case_id':case_id,'catalog_case':row['index'],'source_index':index,'source_run':row['source_run'],
            'source_manifest_sha256':hashlib.sha256(canonical(manifest)).hexdigest(),
            'source_user_turns':copy.deepcopy(turns),'source_user_sequence_sha256':hashlib.sha256(canonical(turns)).hexdigest(),
            'system_messages':systems,'source_system_before_environment_sha256':system_hash,
            'system_source_observation_id':generation['id'],'system_source_trace_id':generation['trace_id'],
            'tools':declarations,'contracts':selected,'resources':resources,'max_tokens':maximum,'max_tool_steps_per_turn':24,
            'thinking_mode':'disabled','initial_quote':initial,'mode':'source_executor_prompt_explicit_local_environment',
            'source_tool_scope':'observed_source_tool_names; unsupported ones fail honestly at dispatch',
        'unsupported_source_tools':unsupported,
            'historical_orchestrator_reproduced':False,'historical_assistant_answers_or_outputs_preloaded':False})
    cases.sort(key=lambda c:(len(c['source_user_turns']),c['catalog_case']))
    if not cases:raise RuntimeError('no_complete_safe_sensitive_cases')
    packet={'run_id':'sensitive-corpus-causal-v1','model':'deepseek-v4-flash','limit_usd':10,'cases':cases,'excluded':excluded,
        'original_engine_without_uuid_fix':True,'user_sequences_unmodified':True,'manual_pii_labels':False,
        'tool_contracts_manifest_sha256':hashlib.sha256(canonical(contract_manifest)).hexdigest(),
        'common_environment_adaptation_explicit':True,'history_shortened':False}
    key=AESGCM.generate_key(bit_length=256);nonce=os.urandom(12);plain=canonical(packet)
    write_private(runtime/'sensitive-corpus-cases-v1.key',key);write_private(destination,nonce+AESGCM(key).encrypt(nonce,plain,AAD))
    public={'run_id':packet['run_id'],'cases':[{'catalog_case':c['catalog_case'],'source_index':c['source_index'],
        'user_turns':len(c['source_user_turns']),'tools':list(c['contracts']),'initial_three_arm_reservation_usd':c['initial_quote']['reserved_nano']*3/1e9,
        'missing_resource_requirements':len(c['resources']['missing'])} for c in cases],
        'excluded':excluded,'no_images_stripped':True,'no_input_file_or_historical_answer_fabrication':True,
        'no_source_history_truncation':True,'common_local_environment_description_added':True,'provider_calls':0,
        'full_run_cost_not_known_in_advance':True,'budget_total_usd':10}
    write_private(state/'sensitive-replay-selection-v1.json',json.dumps(public,indent=2).encode())
    print(json.dumps(public))


if __name__=='__main__':prepare()
