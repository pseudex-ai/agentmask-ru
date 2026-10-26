"""Count-only progress/qualitative review index; never a task-quality score."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from budget import Ledger
from dialogue_runner import scope_for
from prepare_dialogue_replay import AAD
from stand import STATE


def load(path, key, context):
    raw = path.read_bytes()
    return json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], context.encode()))


def collect(revision, live, bundle='full-dialogue-cases'):
    if not re.fullmatch(r'[a-z0-9-]{1,60}', bundle): raise RuntimeError('invalid_bundle_name')
    runtime = STATE / 'runtime'; key = (runtime / (bundle + '.key')).read_bytes()
    raw = (runtime / (bundle + '.aesgcm')).read_bytes()
    packet = json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], AAD))
    folder = STATE / (packet['run_id'] + ('-live-' if live else '-dry-') + revision)
    if not folder.is_dir(): raise RuntimeError('dialogue_run_folder_missing')
    files = list(folder.iterdir()); rows = []
    for case in packet['cases']:
        for mode in ('none', 'builtin', 'pseudex'):
            prefix = case['case_id'] + '-' + mode
            if not (folder / (prefix + '.started')).exists(): continue
            scope = scope_for(case, mode, folder.name)
            completed = []
            for index in range(len(case['source_user_turns'])):
                path = folder / f'{prefix}:{index}.complete.aesgcm'
                if not path.exists(): break
                completed.append(load(path, key, f'{prefix}:{index}:complete'))
            tool_names, tool_status, errors, execution_status, modules = Counter(), Counter(), Counter(), Counter(), Counter()
            requests, statuses, retries = 0, Counter(), 0
            for path in files:
                if path.name.startswith(prefix + '-owner-retry-') and path.name.endswith('.approved'): retries += 1
                match = re.fullmatch(re.escape(prefix) + r'(:\d+(?::owner-retry-[0-9a-f]+)?)-tool-(\d+)\.aesgcm', path.name)
                if match:
                    data = load(path, key, prefix + match[1] + ':tool:' + match[2])
                    tool_names[data['request']['name']] += 1
                    response = data['response']; tool_status['ok' if response.get('ok') else 'error'] += 1
                    if response.get('error'): errors[response['error'].get('code', 'unknown')] += 1
                    result = response.get('result')
                    if isinstance(result, dict) and 'status' in result:
                        execution_status[str(result['status'])] += 1
                        for line in str(result.get('stderr', '')).splitlines():
                            kind = re.match(r'^([A-Za-z][A-Za-z0-9_.]*(?:Error|Exception)):', line)
                            if kind: errors[kind[1]] += 1
                            module = re.search(r"No module named ['\"]([A-Za-z0-9_.]+)['\"]", line)
                            if module: modules[module[1]] += 1
                    continue
                match = re.fullmatch(re.escape(prefix) + r'(:\d+(?::owner-retry-[0-9a-f]+)?)-(\d+)\.(started|done)\.aesgcm', path.name)
                if match:
                    context = prefix + match[1] + ':' + match[2]
                    if match[3] == 'started': requests += 1
                    else:
                        data = load(path, key, context + ':done')
                        statuses[str(data.get('http_status', data.get('error_type', 'unknown')))] += 1
            final_workspace = completed[-1]['workspace'] if completed else {}
            summary = folder / (prefix + '.complete.aesgcm')
            rows.append({'source_index': case['source_index'], 'mode': mode,
                'status': 'complete_user_sequence' if summary.exists() else 'stopped' if any(path.name.startswith(prefix + '.stopped-') for path in files) else 'partial_or_running',
                'source_user_turns': len(case['source_user_turns']), 'completed_user_turns': len(completed),
                'attempted_model_requests': requests, 'received_model_statuses': dict(statuses),
                'owner_approved_retry_records': retries, 'tool_calls': dict(tool_names),
                'tool_invocation_outcomes': dict(tool_status), 'execution_statuses': dict(execution_status),
                'error_types_or_fixed_codes': dict(errors), 'missing_library_identifiers': dict(modules),
                'last_completed_workspace_files': len(final_workspace),
                'last_completed_workspace_base64_bytes': sum(len(value) for value in final_workspace.values()),
                'source_user_sequence_sha256': case['source_user_sequence_sha256'],
                'historical_generated_answers_injected': False, 'original_orchestrator_reproduced': False,
                'url': f'http://127.0.0.1:18880/{scope["tenant_id"]}/assistantnew/{scope["agent_id"]}?thread={scope["thread_id"]}'})
    report = {'run_id': packet['run_id'], 'revision': revision, 'live': live, 'arms': rows,
        'accounting': Ledger(STATE / 'ledger' / 'spend.sqlite3').summary(),
        'qualitative_only': True, 'manual_pii_labels': False, 'task_success_proven': False,
        'original_orchestrator_reproduced': False, 'external_customer_tool_actions': 0,
        'complete_user_sequence_is_not_business_task_success': True}
    target = STATE / ('dialogue-replay-progress-' + ('live' if live else 'dry') + '-' + revision + '.json')
    # This public index has only counters/local opaque IDs; no source utterances,
    # code, output files, counterpart values, customer filenames or credentials.
    target.write_text(json.dumps(report, indent=2)); target.chmod(0o600)
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default='v1'); parser.add_argument('--live', action='store_true')
    parser.add_argument('--bundle', default='full-dialogue-cases')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]{1,40}', args.revision): raise SystemExit('invalid_revision')
    collect(args.revision, args.live, args.bundle)
