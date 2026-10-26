"""Real authenticated web/tool loop, synthetic contact, fixture-only model."""

import json

import httpx

from seed_four_hop import GRAPH, THREAD
from stand import STATE


def main():
    private = json.loads((STATE / 'runtime' / 'browser.json').read_text())
    with httpx.Client(timeout=90, trust_env=False) as client:
        assert client.get('http://127.0.0.1:18850/health').json()['mode'] == 'fixture'
        auth = client.post('http://127.0.0.1:18860/auth/login', json={
            'user_id': 'pilot-owner@example.invalid', 'password': private['password']})
        auth.raise_for_status()
        headers = {'Authorization': 'Bearer ' + auth.json()['access_token'], 'X-Org-Id': 'doubleup-pilot'}
        response = client.post('http://127.0.0.1:18860/query', headers=headers, json={
            'graph_id': GRAPH, 'thread_id': THREAD,
            'query': '😀 Проверь контакт Иванов Пётр, почта pilot.person@example.org, телефон +7 916 123-45-67.',
            'config': {'retrieval': {'enabled': False}, 'kb_tools': False}})
        response.raise_for_status()
        events = []
        for line in response.text.splitlines():
            if line.startswith('data:'):
                try: events.append(json.loads(line[5:].strip()))
                except ValueError: pass
        starts = [event for event in events if event.get('type') == 'start']
        ends = [event for event in events if event.get('type') == 'end']
        errors = [event for event in events if event.get('type') == 'error']
        value = client.get('http://127.0.0.1:18860/api/v1/pseudex/inspections/highlights',
            params={'thread_id': THREAD}, headers=headers)
        value.raise_for_status()
        data = value.json()
    hops = {entry['hop'] for entry in data['messages'] + data['tools'] if entry.get('highlights')}
    expected = {'user_to_model', 'model_to_tool', 'tool_to_model', 'model_to_user'}
    input_links = starts[0].get('pseudex_input_messages', []) if starts else []
    end_id = ends[-1].get('answer_message_id') if ends else None
    user_ids = {entry['message_id'] for entry in data['messages'] if entry['hop'] == 'user_to_model'}
    assistant_ids = {entry['message_id'] for entry in data['messages'] if entry['hop'] == 'model_to_user'}
    linked_user = bool(input_links) and input_links[0]['message_id'] in user_ids
    linked_answer = bool(end_id) and end_id in assistant_ids
    tool_dispatched = any(entry.get('arguments_match') is True and entry.get('completed') is True
                          for entry in data['tools'] if entry['hop'] == 'model_to_tool')
    report = {'passed': not errors and expected.issubset(hops) and linked_user and linked_answer and tool_dispatched,
        'http_status': response.status_code, 'hop_types_with_marks': sorted(hops),
        'new_input_id_linked': linked_user, 'final_answer_id_linked': linked_answer,
        'matching_tool_dispatch_completed': tool_dispatched, 'error_events': len(errors),
        'message_evidence_entries': len(data['messages']), 'tool_evidence_entries': len(data['tools']),
        'synthetic_only': True, 'real_web_rpc': True, 'real_tool_executor': True,
        'scripted_provider_not_agent_quality': True, 'provider_calls_external': 0, 'paid_usd': 0}
    path = STATE / 'four-hop-web-gate.json'
    path.write_text(json.dumps(report, indent=2)); path.chmod(0o600)
    print(json.dumps(report))
    if not report['passed']: raise SystemExit(1)


if __name__ == '__main__': main()
