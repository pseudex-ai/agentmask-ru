"""Source-backed contact evidence for real full dialogues, not gold PII labels.

Original values/positions stay encrypted. Public manifests report only counts,
source roles, actual tool identifiers and exact source-pointer availability.
"""

import argparse
from collections import Counter
import json
import re
import sys

import phonenumbers

from .storage import RunStore, hashed

EMAIL = re.compile(r"(?i)(?<![\w.+-])[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63}){1,8}(?![\w.-])")
PHONE = re.compile(r"(?<!\w)(?:[+][1-9](?:[ ()-]*[0-9]){6,14}|8(?:[ ()-]*[0-9]){10})(?![0-9])")
RESERVED = {'example.com', 'example.org', 'example.net', 'example.ru', 'localhost', 'test.com', 'test.ru'}


def strings(value, pointer=''):
    if isinstance(value, str):
        yield pointer, value
    elif isinstance(value, dict):
        for key, item in value.items():
            escaped = str(key).replace('~', '~0').replace('/', '~1')
            yield from strings(item, pointer + '/' + escaped)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from strings(item, pointer + '/' + str(index))


def evidence(value, pointer):
    found = []
    for path, text in strings(value, pointer):
        if text.startswith(('data:image/', 'data:application/', 'data:audio/')):
            continue  # Binary media are retained as originals, not contact text.
        for match in EMAIL.finditer(text):
            address = match.group().strip('.')
            domain = address.rsplit('@', 1)[-1].casefold()
            if domain in RESERVED or domain.endswith(('.invalid', '.test', '.example')):
                continue
            found.append({'type': 'email_contact', 'value': address, 'canonical': address.casefold(),
                'pointer': path, 'start': match.start(), 'end': match.start() + len(address),
                'offset_unit': 'unicode_codepoint', 'criterion': 'non_reserved_email_shape_not_identity_verification'})
        for match in PHONE.finditer(text):
            try:
                number = phonenumbers.parse(match.group(), 'RU')
            except phonenumbers.NumberParseException:
                continue
            if not phonenumbers.is_valid_number(number): continue
            found.append({'type': 'phone_contact', 'value': match.group(),
                'canonical': phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164),
                'pointer': path, 'start': match.start(), 'end': match.end(),
                'offset_unit': 'unicode_codepoint', 'criterion': 'valid_number_shape_not_ownership_verification'})
    return found


def qualify(run_id, source_run):
    source = RunStore(source_run, False); parent = source.verify()
    payload = source.read_encrypted('full-dialogues.aesgcm')
    store = RunStore(run_id, True); summaries = []
    for index, dialogue in enumerate(payload['dialogues']):
        user_evidence = [entry for position, message in enumerate(dialogue['user_turns'])
            for entry in evidence(message['content'], f'/user_turns/{position}/content')]
        answer_evidence = [entry for position, message in enumerate(dialogue['messages']) if message.get('type') == 'ai'
            for entry in evidence(message.get('content'), f'/messages/{position}/content')]
        user_keys = {(entry['type'], entry['canonical']) for entry in user_evidence}
        tools = []; tool_input_values = set(); tool_output_values = set(); tools_with_contacts = set()
        for span in dialogue['source_context']['application_activity']['source_tool_execution_spans']:
            inputs = evidence(span['arguments'], '/input')
            outputs = evidence(span['result'], '/output')
            if inputs or outputs:
                tools_with_contacts.add(span['name'])
                tools.append({'observation_id': span['observation_id'], 'trace_id': span['trace_id'],
                    'name': span['name'], 'arguments': inputs, 'result': outputs,
                    'source_semantics': span['source_semantics']})
            tool_input_values.update((entry['type'], entry['canonical']) for entry in inputs)
            tool_output_values.update((entry['type'], entry['canonical']) for entry in outputs)
        sensitive = bool(user_evidence or answer_evidence or tools)
        record = {'source_run': source_run, 'source_index': index,
            'source_thread': dialogue['thread'], 'user_evidence': user_evidence,
            'root_answer_evidence': answer_evidence, 'tool_evidence': tools,
            'original_dialogue': dialogue, 'selection_is_not_manual_annotation': True,
            'contact_ownership_or_real_world_person_not_verified': True}
        store.encrypt(f'dialogue-{index:03d}.aesgcm', record)
        summary = {'source_index': index, 'user_turns': len(dialogue['user_turns']),
            'root_messages': len(dialogue['messages']), 'langfuse_complete': dialogue['langfuse']['complete'],
            'source_tool_execution_spans': len(dialogue['source_context']['application_activity']['source_tool_execution_spans']),
            'user_contact_occurrences': dict(Counter(item['type'] for item in user_evidence)),
            'root_answer_contact_occurrences': dict(Counter(item['type'] for item in answer_evidence)),
            'unique_user_contacts': len(user_keys), 'tool_calls_with_contact_evidence': len(tools),
            'unique_tool_input_contacts': len(tool_input_values), 'unique_tool_output_contacts': len(tool_output_values),
            'user_contacts_reobserved_in_tool_arguments': len(user_keys & tool_input_values),
            'user_contacts_reobserved_in_tool_results': len(user_keys & tool_output_values),
            'tools_with_contact_evidence': sorted(tools_with_contacts), 'sensitive_contact_evidence_present': sensitive,
            'selection_class': 'user_contact_and_tool' if user_keys & (tool_input_values | tool_output_values)
                else 'contact_in_dialogue_or_tool' if sensitive else 'no_contact_evidence_do_not_claim_pii'}
        summaries.append(summary)
    result = store.finish({'kind': 'real_dialogue_contact_qualification', 'source_run': source_run,
        'source_manifest_sha256': hashed(parent), 'dialogues': summaries,
        'sensitive_evidence_dialogues': sum(row['sensitive_contact_evidence_present'] for row in summaries),
        'user_contact_into_tool_dialogues': sum(bool(row['user_contacts_reobserved_in_tool_arguments'] or row['user_contacts_reobserved_in_tool_results']) for row in summaries),
        'manual_pii_labels': False, 'not_precision_recall_or_person_verification': True,
        'provider_calls': 0, 'remote_mutations': 0, 'raw_values_encrypted': True})
    store.verify()
    print(json.dumps({key: result[key] for key in ('run_id', 'sensitive_evidence_dialogues',
        'user_contact_into_tool_dialogues', 'dialogues', 'provider_calls', 'remote_mutations')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--source', default='mongo-dialogues-all-six-application-join-v1')
    args = parser.parse_args()
    try: qualify(args.run_id, args.source)
    except Exception as error:
        print(json.dumps({'ok': False, 'error_type': type(error).__name__, 'code': 'qualification_unavailable'}), file=sys.stderr)
        raise SystemExit(2)
