"""Seal complete original user sequences and source-backed local tool resources.

A frozen executor prompt/tool loop is an explicit experiment adaptation, not the
historical multi-agent orchestrator. New model/tool outputs feed later steps;
original assistant answers and generated files are never preloaded.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / 'prototype'))
from bench.doubleup.storage import RunStore
from budget import load_pricing, quote
from prepare_live import canonical, write_private

AAD = b'doubleup-full-dialogue-causal-replay-v1'


def prepare():
    source = RunStore('mongo-dialogues-application-normalized-v2', False)
    source_manifest = source.verify()
    payload = source.read_encrypted('full-dialogues.aesgcm')
    resources = RunStore('safe-local-replay-plan-v4', False)
    resources_manifest = resources.verify()
    contracts = resources.read_encrypted('tool-contracts.aesgcm')
    tools = [{'type': 'function', 'function': {'name': name, 'description': item['description'],
               'parameters': item['parameters']}} for name, item in sorted(contracts.items())]
    pricing = load_pricing(HERE / '.state' / 'pricing.json')
    cases, excluded = [], []
    for index, dialogue in enumerate(payload['dialogues']):
        turns = dialogue['user_turns']
        if not dialogue['langfuse'].get('complete'):
            excluded.append({'index': index, 'reason': 'application_hops_not_yet_complete'}); continue
        if not all(isinstance(turn['content'], str) or (isinstance(turn['content'], list) and all(
                isinstance(part, dict) and part.get('type') == 'text' and isinstance(part.get('text'), str)
                for part in turn['content'])) for turn in turns):
            excluded.append({'index': index, 'reason': 'nontext_original_input_requires_separate_protected_adapter'}); continue
        generations = sorted((event for event in dialogue['langfuse']['events']
            if event.get('type') == 'GENERATION' and isinstance(event.get('output'), dict)
            and event['output'].get('tool_calls')), key=lambda event: (str(event.get('start')), event['id']))
        if not generations:
            excluded.append({'index': index, 'reason': 'no_source_executor_generation'}); continue
        generation = generations[0]
        systems = [copy.deepcopy(message) for message in generation['input']
                   if isinstance(message, dict) and message.get('role') == 'system']
        if not systems or any(not isinstance(message.get('content'), str) for message in systems):
            excluded.append({'index': index, 'reason': 'source_system_prompt_unsupported'}); continue
        params = generation.get('model_parameters') or {}
        maximum = params.get('max_tokens') if isinstance(params, dict) else None
        if type(maximum) is not int or not 1 <= maximum <= 32768:
            maximum = 4000
        body = {'model': 'deepseek-v4-flash', 'messages': systems + [
            {'role': 'user', 'content': copy.deepcopy(turns[0]['content'])}],
            'tools': tools, 'stream': False, 'thinking': {'type': 'disabled'}, 'max_tokens': maximum}
        estimate = quote(body, pricing)
        case_id = hashlib.sha256(canonical([source.run_id, index, dialogue['thread']['thread_id']])).hexdigest()
        cases.append({'case_id': case_id, 'source_index': index, 'source_user_turns': copy.deepcopy(turns),
            'source_user_sequence_sha256': hashlib.sha256(canonical(turns)).hexdigest(),
            'system_messages': systems, 'system_source_observation_id': generation['id'],
            'system_source_trace_id': generation['trace_id'], 'tools': tools,
            'contracts': contracts, 'resources': resources.read_encrypted(f'resources-case-{index}.aesgcm'),
            'max_tokens': maximum, 'max_tool_steps_per_turn': 30, 'thinking_mode': 'disabled',
            'initial_quote': estimate, 'mode': 'source_executor_prompt_local_causal_tool_loop',
            'historical_orchestrator_reproduced': False,
            'historical_assistant_answers_or_outputs_preloaded': False})
    if not cases:
        raise SystemExit('no_complete_text_only_dialogue_with_source_executor_prompt')
    packet = {'run_id': 'full-dialogue-causal-replay-v1', 'model': 'deepseek-v4-flash', 'limit_usd': 10,
        'cases': cases, 'excluded': excluded,
        'source_manifest_sha256': hashlib.sha256(canonical(source_manifest)).hexdigest(),
        'resources_manifest_sha256': hashlib.sha256(canonical(resources_manifest)).hexdigest(),
        'causal_new_model_and_local_tool_outputs': True, 'manual_pii_labels': False}
    runtime = HERE / '.state' / 'runtime'
    destination = runtime / 'full-dialogue-cases.aesgcm'
    if destination.exists():
        raise SystemExit('immutable_full_dialogue_case_bundle_already_exists')
    key = AESGCM.generate_key(bit_length=256); nonce = os.urandom(12)
    plain = canonical(packet)
    write_private(runtime / 'full-dialogue-cases.key', key)
    write_private(destination, nonce + AESGCM(key).encrypt(nonce, plain, AAD))
    public = {'run_id': packet['run_id'], 'cases': len(cases),
        'case_user_turns': [len(case['source_user_turns']) for case in cases],
        'case_indices': [case['source_index'] for case in cases], 'tools': len(tools),
        'all_arms': ['none', 'builtin', 'pseudex'], 'source_messages_unmodified': True,
        'original_orchestrator_reproduced': False, 'explicit_adaptation': 'frozen_source_executor_prompt_with_safe_local_tools',
        'no_historical_answer_injection': True, 'no_historical_generated_files_seeded': True,
        'first_call_three_arm_upper_usd': sum(case['initial_quote']['reserved_nano'] * 3 for case in cases) / 1e9,
        'full_run_quote_not_known_in_advance': True, 'persistent_budget_hardcap_usd': 10,
        'excluded': excluded, 'plaintext_packet_sha256': hashlib.sha256(plain).hexdigest(), 'provider_calls': 0}
    write_private(HERE / '.state' / 'full-dialogue-selection.json', json.dumps(public, indent=2).encode())
    print(json.dumps(public))


if __name__ == '__main__': prepare()
