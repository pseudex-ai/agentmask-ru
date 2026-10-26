"""Qualify authenticated Sept+ inputs; never print source text or identifiers.

Tool-presence/PII counts are screening evidence, NOT precision/recall or a claim
that a real model has completed the task. No source writes and no model calls.
Original ordered Mongo text is kept in full; no historical answer is preloaded.
"""
import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'prototype'))
from bench.doubleup.storage import RunStore, canonical, hashed
from bench.doubleup.date_pii_catalog import Matchers, message_text, ms, strings
from bench.doubleup.mongo_dialogues import normalized_events
from bench.doubleup.source_resources import attachment_locators, build_resources
from bench.doubleup.replay_tools import ALLOWLIST, ReplayTools
from prepare_dialogue_replay import AAD
from prepare_live import write_private
from budget import quote, load_pricing
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

CUTOFF_MS = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
BASE = 'september-pii-tools-v4'
QUALIFIED = 'september-replay-qualified-v1'
BUNDLE = 'september-qualified-cases-v1'
ENVIRONMENT = '''Локальная среда нового прогона (одинакова для всех режимов защиты):
Выполняй инструменты заново; исторические ответы и файлы не предзагружены.
Python работает в изолированном Linux-контейнере без сети. Доступны stdlib,
numpy, pandas, openpyxl, matplotlib. python-docx и сетевые библиотеки недоступны.
Каждый вызов Python независим: повторяй импорты; файлы предыдущего вызова
сохраняются. Рабочая папка /work. Для новых файлов используй простые относительные
имена без подпапок. При недостающем ресурсе сообщи об ограничении; не выдумывай
содержимое или успешный вызов. Исходные сообщения пользователя не сокращены.'''


def original_text(message):
    value = message.get('content')
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get('text'), str):
        if set(value) - {'text', 'type', 'language', 'format'}:
            raise ValueError('unarchived_user_content_fields')
        return value['text']
    raise ValueError('unsupported_original_input_do_not_strip')


def hit_keys(matchers, value):
    return {matchers.canonical(text, hit) for text in strings(value)
            for hit in matchers.all_personal(text)}


def prepare():
    source = RunStore(BASE, False)
    manifest = source.verify()
    snapshot = RunStore(manifest['source_snapshot'], False)
    snapshot_manifest = snapshot.verify()
    raw = snapshot.read_encrypted('original-user-candidate-inventory.aesgcm')
    users = {}
    for row in raw['user_messages']:
        users.setdefault(row['thread_id'], []).append(row)
    threads = {row['thread_id']: row for row in raw['threads'] if row.get('thread_id')}
    matchers = Matchers(HERE.parent.parent / 'prototype/licensing/data')
    contracts_store = RunStore('safe-local-replay-plan-v4', False)
    contracts_manifest = contracts_store.verify()
    contracts_all = contracts_store.read_encrypted('tool-contracts.aesgcm')
    qualified = RunStore(QUALIFIED, True)
    summaries, cases = [], []
    complete_index = 0
    pricing = load_pricing(HERE / '.state/pricing.json')
    for entry in manifest['artifacts']:
        if not entry['file'].startswith('tc-'):
            continue
        evidence = source.read_encrypted(entry['file'])
        if not evidence.get('complete'):
            continue
        complete_index += 1
        alias = 'sept-' + str(complete_index).zfill(2)
        messages = sorted(users.get(evidence['thread_id'], []), key=lambda row: ms(row['created_at']))
        thread = threads[evidence['thread_id']]
        reasons = []
        if evidence['created_ms'] < CUTOFF_MS or any(ms(row['created_at']) < CUTOFF_MS for row in messages):
            reasons.append('source_before_september')
        if len(messages) < 2:
            reasons.append('not_multiturn')
        if attachment_locators({'mongo_user_messages': messages}, complete_index):
            reasons.append('original_attachment_bytes_not_archived')
        try:
            turns = [{'role': 'user', 'content': original_text(row)} for row in messages]
        except ValueError:
            turns = []
            reasons.append('unsupported_original_input_do_not_strip')
        user_keys = hit_keys(matchers, [row['content'] for row in turns])
        arg_keys, result_keys = set(), set()
        pii_tools, names = set(), set()
        for tool in evidence['tool_spans']:
            names.add(tool['name'])
            args = hit_keys(matchers, tool.get('arguments'))
            results = hit_keys(matchers, tool.get('result'))
            arg_keys |= args
            result_keys |= results
            if args or results:
                pii_tools.add(tool['name'])
        if not user_keys:
            reasons.append('user_pii_not_confirmed_by_screening')
        if not arg_keys and not result_keys:
            reasons.append('no_pii_in_tools')
        if not user_keys.intersection(arg_keys | result_keys):
            reasons.append('no_same_user_pii_observed_in_tools')
        unsupported = sorted(names - ALLOWLIST | names - set(contracts_all))
        if unsupported:
            reasons.append('source_tools_without_safe_local_adapter')
        events = []
        trace_map = {row['id']: row for row in evidence['traces']}
        for trace_id, observations in evidence['observations'].items():
            events.extend(normalized_events(trace_map[trace_id], observations))
        generations = sorted((event for event in events if event.get('type') == 'GENERATION'
                              and isinstance(event.get('input'), list)
                              and isinstance(event.get('output'), dict)
                              and event['output'].get('tool_calls')),
                             key=lambda event: (str(event.get('start')), event['id']))
        systems = []
        if generations:
            systems = [copy.deepcopy(row) for row in generations[0]['input']
                       if isinstance(row, dict) and row.get('role') == 'system']
        if not systems or any(not isinstance(row.get('content'), str) for row in systems):
            reasons.append('original_executor_prompt_missing')
        d = {'thread': thread, 'mongo_user_messages': messages, 'user_turns': turns,
             'langfuse': {'complete': True, 'events': events},
             'source_context': {'application_activity': {'source_tool_execution_spans': evidence['tool_spans']}}}
        resources = build_resources(d, complete_index)
        selected_contracts = {name: copy.deepcopy(contracts_all[name]) for name in sorted(names & ALLOWLIST & set(contracts_all))}
        try:
            ReplayTools(selected_contracts, resources, 'qualification')
        except Exception:
            reasons.append('resource_mirror_validation_failed')
        public = {'case': alias, 'source_month': datetime.fromtimestamp(evidence['created_ms']/1000, timezone.utc).strftime('%Y-%m'),
                  'user_turns': len(turns), 'source_text_chars': sum(len(row['content']) for row in turns),
                  'user_pii_types': sorted({key[0] for key in user_keys}),
                  'pii_in_tool_arguments': bool(arg_keys), 'pii_in_tool_results': bool(result_keys),
                  'same_user_pii_in_tool_arguments': len(user_keys & arg_keys),
                  'same_user_pii_in_tool_results': len(user_keys & result_keys),
                  'pii_tool_names': sorted(pii_tools), 'all_tool_names': sorted(names),
                  'unimplemented_tools': unsupported, 'readiness': 'eligible' if not reasons else 'excluded',
                  'exclusion_reasons': reasons, 'missing_resource_requirements': len(resources['missing']),
                  'source_visible_root_checkpoint_exported': False,
                  'source_snapshot_not_atomic_with_langfuse': True}
        provenance = {'run': BASE, 'artifact': entry['file'], 'source_manifest_sha256': hashed(manifest),
                      'snapshot': manifest['source_snapshot'], 'snapshot_manifest_sha256': hashed(snapshot_manifest),
                      'raw_user_sequence_sha256': hashed(messages)}
        qualified.encrypt(alias + '.aesgcm', {'dialogue': d, 'public': public, 'provenance': provenance})
        if not reasons:
            adapted_systems = systems + [{'role': 'system', 'content': ENVIRONMENT}]
            maximum = 8192
            declarations = [{'type':'function','function':{'name':name,'description':c['description'],'parameters':c['parameters']}}
                            for name,c in selected_contracts.items()]
            initial = quote({'model':'deepseek-v4-flash','messages': adapted_systems + [turns[0]],
                             'stream':False,'thinking':{'type':'disabled'},'max_tokens':maximum,
                             'tools':declarations}, pricing)
            case = {'case_id': hashed([BASE, entry['file']]), 'catalog_case': complete_index,
                    'source_index': complete_index - 1, 'source_run': QUALIFIED,
                    'source_user_turns': turns, 'source_user_sequence_sha256': hashed(turns),
                    'system_messages': adapted_systems, 'source_system_before_environment_sha256': hashed(systems),
                    'contracts': selected_contracts, 'resources': resources, 'max_tokens': maximum,
                    'tools':[{'type':'function','function':{'name':name,'description':c['description'],'parameters':c['parameters']}}
                             for name,c in selected_contracts.items()],
                    'max_tool_steps_per_turn':24, 'thinking_mode':'disabled', 'initial_quote':initial,
                    'historical_orchestrator_reproduced':False, 'historical_assistant_answers_or_outputs_preloaded':False,
                    'original_values_unchanged':True, 'source_provenance': provenance}
            cases.append(case)
            public['initial_three_arm_reservation_usd'] = initial['reserved_nano']*3/1e9
        summaries.append(public)
    qualified.encrypt('qualification.aesgcm', {'cases': summaries, 'eligible':len(cases)})
    qualified.finish({'kind':'qualified_september_replay_inputs','cases':len(summaries),'eligible':len(cases),
                      'provider_calls':0,'remote_mutations':0,'manual_pii_labels':False,'source':BASE})
    qualified.verify()
    cases.sort(key=lambda case: (len(case['source_user_turns']), sum(len(t['content']) for t in case['source_user_turns'])))
    packet = {'run_id':'september-qualified-replay-v1','model':'deepseek-v4-flash','cases':cases,
              'source_user_sequences_unmodified':True,'manual_pii_labels':False,'original_orchestrator_reproduced':False}
    runtime = HERE / '.state/runtime'
    key = AESGCM.generate_key(bit_length=256); nonce = os.urandom(12)
    write_private(runtime / (BUNDLE+'.key'),key)
    write_private(runtime / (BUNDLE+'.aesgcm'),nonce+AESGCM(key).encrypt(nonce,canonical(packet),AAD))
    report = {'source':BASE,'manifest_integrity_verified':True,'cases_complete':len(summaries),
              'eligible':len(cases),'cases':summaries,'provider_calls':0,'source_mutations':0,
              'counts_are_screening_not_detection_quality_metrics':True}
    write_private(HERE/'.state/september-qualification-v1.json',json.dumps(report,ensure_ascii=False,indent=2).encode())
    print(json.dumps(report,ensure_ascii=False))

if __name__ == '__main__':
    prepare()
