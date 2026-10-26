"""Causal complete-user-sequence replay through the real DoubleUp tools loop.

The original executor prompt is frozen, not the historical multi-agent planner.
Each arm owns a fresh local resource mirror/workspace. Tools run for real locally;
source assistant answers, outputs and generated artifacts are never injected.
"""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'prototype'))
from bench.doubleup.replay_executor import run_python
from bench.doubleup.replay_tools import ReplayTools
from prepare_dialogue_replay import AAD
from stand import STATE

BRIDGE = (HERE / 'dialogue_bridge.py').read_text()
CONTAINER = 'obscura-doubleup-pilot-graph_server-1'
CANCELLED = threading.Event()


class BridgeFailure(RuntimeError):
    def __init__(self, payload):
        super().__init__('bridge_command_failed')
        self.payload = payload


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def seal(path, value, key, context):
    nonce = os.urandom(12)
    write_new(path, nonce + AESGCM(key).encrypt(nonce, canonical(value), context.encode()))


def scope_for(case, mode, run_tag):
    org = 'doubleup-dialogue-' + hashlib.sha256((case['case_id'] + ':' + run_tag).encode()).hexdigest()[:12]
    return {'tenant_id': org, 'owner_id': 'pilot-owner',
        'agent_id': str(uuid.uuid5(uuid.NAMESPACE_URL, org + '/' + mode + '/graph')),
        'thread_id': str(uuid.uuid5(uuid.NAMESPACE_URL, org + '/' + mode + '/thread'))}


def bridge(command, handle=None):
    nonce = uuid.uuid4().hex
    remote_pid = None
    process = subprocess.Popen(['docker', 'exec', '-i', '-e', 'PSEUDEX_REPLAY_EXEC_ID=' + nonce, CONTAINER, 'python', '-c', BRIDGE],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert process.stdin and process.stdout
    process.stdin.write(canonical(command) + b'\n'); process.stdin.flush()
    selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
    output = None; deadline = time.monotonic() + 2400
    try:
        while time.monotonic() < deadline and not CANCELLED.is_set():
            if not selector.select(timeout=15):
                if process.poll() is not None: break
                continue
            line = process.stdout.readline(4 * 1024 * 1024)
            if not line: break
            if len(line) >= 4 * 1024 * 1024: raise RuntimeError('bridge_response_size_limit')
            try: event = json.loads(line)
            except ValueError: continue  # Suppress library startup prints; never customer logs.
            if event.get('type') == 'hello':
                if event.get('nonce') != nonce or type(event.get('pid')) is not int or event['pid'] <= 1:
                    raise RuntimeError('bridge_identity_invalid')
                remote_pid = event['pid']; continue
            if event.get('type') == 'final': output = event['payload']; break
            if event.get('ok') is False: output = event; break
            if handle is None: raise RuntimeError('unexpected_bridge_rpc')
            reply = handle(event)
            process.stdin.write(canonical(reply) + b'\n'); process.stdin.flush()
        if output is None: raise RuntimeError('bridge_interrupted_delivery_not_retried')
        process.stdin.close(); process.wait(timeout=15)
        if process.returncode or not output.get('ok'): raise BridgeFailure(output)
        return output
    finally:
        selector.close()
        if process.poll() is None:
            # A killed Docker CLI alone leaves its exec Python alive. Verify the
            # exact per-exec nonce before signalling ONLY our owned remote PID.
            if remote_pid is not None:
                cleanup = f"import os,signal,pathlib; p={remote_pid}; expected={('PSEUDEX_REPLAY_EXEC_ID=' + nonce).encode()!r}; env=pathlib.Path('/proc/'+str(p)+'/environ'); data=env.read_bytes().split(bytes([0])) if env.exists() else []; os.kill(p,signal.SIGTERM) if expected in data else None"
                subprocess.run(['docker', 'exec', CONTAINER, 'python', '-c', cleanup],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=True)
            process.kill(); process.wait(timeout=5)


def local_tool(mirror, workspace, name, arguments):
    answer = mirror.dispatch(name, arguments)
    if name != 'run_code' or answer.get('ok') or answer.get('error', {}).get('code') != 'executor_unavailable':
        return answer, workspace
    if arguments.get('dataset_id'):
        return {'ok': False, 'error': {'code': 'dataset_unavailable', 'action': 'supply_original_dataset_bytes'}, 'remote_mutations': 0}, workspace
    execution = run_python(arguments['code'], workspace, 45)
    if execution['status'] == 'ok':
        workspace = {item['path']: item['content'] for item in execution['artifacts']}
    result = {'status': execution['status'], 'exit_code': execution['exit_code'],
        'stdout': execution['stdout'], 'stderr': execution['stderr'],
        'artifacts': [{'filename': name, 'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()} for name, value in workspace.items()],
        'limits_hit': execution['limits_hit'], 'network': 'none', 'error': execution['error']}
    return {'ok': execution['status'] == 'ok', 'result': result, 'remote_mutations': 0}, workspace


def unseal(path, key, context):
    raw = path.read_bytes()
    return json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], context.encode()))


def known_prefix(folder, prefix, key, total_turns):
    completed = []
    for index in range(total_turns):
        path = folder / f'{prefix}:{index}.complete.aesgcm'
        if not path.exists(): break
        completed.append(unseal(path, key, f'{prefix}:{index}:complete'))
    if not completed or len(completed) == total_turns:
        raise RuntimeError('resume_requires_known_completed_prefix_and_failed_turn')
    turn = len(completed); context = f'{prefix}:{turn}'
    pending = list(folder.glob(context + '-tool-*.aesgcm'))
    starts = list(folder.glob(context + '-*.started.aesgcm'))
    if pending or len(starts) != 1 or starts[0].name != context + '-1.started.aesgcm':
        raise RuntimeError('partial_turn_has_effects_or_multiple_requests_manual_reconciliation_required')
    first = unseal(starts[0], key, context + ':1:start')
    done_path = folder / (context + '-1.done.aesgcm')
    if not done_path.exists():
        raise RuntimeError('request_outcome_not_yet_reconciled')
    failed = unseal(done_path, key, context + ':1:done')
    if failed.get('http_status') not in (500, 502, 503, 504):
        raise RuntimeError('resume_only_owner_approved_upstream_failure')
    return completed[-1], turn, first['request_sha256']


def run_arm(packet, case, mode, live, key, folder, resume_known_prefix):
    scope = scope_for(case, mode, folder.name)
    prefix = case['case_id'] + '-' + mode
    summary_path = folder / (prefix + '.complete.aesgcm')
    started = folder / (prefix + '.started')
    if summary_path.exists():
        prior = unseal(summary_path, key, prefix + ':complete')
        return {**prior, 'already_complete_not_repaid': True}
    restored = None; completed_turns = 0; retry_hash = None; retry_tag = ''
    if started.exists():
        if not resume_known_prefix: raise RuntimeError('partial_arm_not_automatically_repaid')
        restored, completed_turns, retry_hash = known_prefix(folder, prefix, key, len(case['source_user_turns']))
        retry_tag = 'owner-retry-' + uuid.uuid4().hex[:8]
        write_new(folder / (prefix + '-' + retry_tag + '.approved'), canonical({
            'owner_approved': True, 'resume_after_turns': completed_turns, 'original_unknown_reservation_retained': True,
            'same_total_budget_usd': 10, 'prior_request_sha256': retry_hash}))
    else:
        write_new(started, canonical({'started_utc': datetime.now(timezone.utc).isoformat(), 'mode': mode,
            'case_id': case['case_id'], 'live': live}))
    root_request = uuid.uuid4().hex
    base = {'mode': mode, 'scope': scope, 'root_request_id': root_request, 'live': live}
    bridge({**base, 'kind': 'seed', 'case_index': case['source_index']})
    native_documents = frozenset(('create_document', 'read_document', 'append_to_document'))
    mirror_contracts = {name: contract for name, contract in case['contracts'].items() if name not in native_documents}
    mirror = ReplayTools(mirror_contracts, case['resources'], mode)
    workspace = {}
    history = [{'role': 'system', 'content': message['content'], 'id': 'pilot-system-' + uuid.uuid4().hex}
               for message in case['system_messages']]
    display = []; counts = {'models': 0, 'tools': 0, 'tool_errors': 0, 'turns': 0}
    if restored is not None:
        history = restored['history']
        display = [value for value in history if value['role'] != 'system']
        workspace = {name: base64.b64decode(data, validate=True) for name, data in restored['workspace'].items()}
        mirror = ReplayTools(mirror_contracts, restored['mirror_state'], mode)
        counts = dict(restored['counts'])
        counts['models'] += 1  # Preserve the original unknown attempted request.
        counts['owner_authorized_unknown_retries'] = counts.get('owner_authorized_unknown_retries', 0) + 1
    for turn_index, source in enumerate(case['source_user_turns']):
        if CANCELLED.is_set(): raise RuntimeError('run_cancelled_no_new_request')
        if turn_index < completed_turns: continue
        user = {'role': 'user', 'content': source['content'], 'id': 'pilot-user-' + uuid.uuid4().hex}
        history.append(user); display.append(user)
        # Show the actually accepted user input while the tool loop is running;
        # an interrupted turn must not look like an empty chat. No AI is invented.
        bridge({**base, 'kind': 'save', 'messages': display, 'turn_index': turn_index})
        steps = {}; turn_key = prefix + ':' + str(turn_index)
        turn_context = turn_key + (':' + retry_tag if retry_tag else '')
        def event(value):
            nonlocal workspace
            kind = value['type']
            if kind == 'model_start':
                if CANCELLED.is_set(): raise RuntimeError('run_cancelled_before_model_socket')
                if retry_hash is not None and turn_index == completed_turns and value['step'] == 1 and value['request_sha256'] != retry_hash:
                    raise RuntimeError('resumed_request_input_hash_changed')
                counts['models'] += 1
                step = value['step']; steps[step] = True
                seal(folder / f'{turn_context}-{step}.started.aesgcm', value, key, turn_context + ':' + str(step) + ':start')
                return {'ok': True}
            if kind in ('model_done', 'model_error'):
                seal(folder / f'{turn_context}-{value["step"]}.done.aesgcm', value, key, turn_context + ':' + str(value['step']) + ':done')
                return {'ok': True}
            if kind == 'tool':
                counts['tools'] += 1
                generated = []
                if value['name'] in native_documents:
                    from bench.doubleup.replay_tools import validate
                    validate(value['arguments'], case['contracts'][value['name']]['parameters'], tool_root=True)
                    native = bridge({**base, 'kind':'native_document', 'name':value['name'], 'arguments':value['arguments']})
                    result = {'ok':native['tool_ok'],'result':native['result'],'remote_mutations':0,
                              'local_mutations_only':True,'generated_documents':native['generated_documents']}
                    generated = native['generated_documents']
                else:
                    result, workspace = local_tool(mirror, workspace, value['name'], value['arguments'])
                counts['tool_errors'] += not result.get('ok', False)
                seal(folder / f'{turn_context}-tool-{counts["tools"]}.aesgcm', {'request': value, 'response': result,
                    'workspace': {name: base64.b64encode(data).decode() for name, data in workspace.items()}}, key,
                    turn_context + ':tool:' + str(counts['tools']))
                return {'ok': True, 'result': json.dumps(result, ensure_ascii=True), 'generated_documents':generated}
            raise RuntimeError('bridge_rpc_type_invalid')
        try:
            result = bridge({**base, 'kind': 'turn', 'live': live, 'history': history,
                'contracts': case['contracts'], 'max_tokens': case['max_tokens']}, event)
        except BridgeFailure as error:
            seal(folder / (turn_context + '.failed.aesgcm'), {'actual_bridge_payload': error.payload,
                'history': history, 'counts': counts,
                'workspace': {name: base64.b64encode(data).decode() for name, data in workspace.items()}},
                key, turn_context + ':failed')
            notice = {'role': 'assistant', 'id': 'pilot-system-event-' + uuid.uuid4().hex,
                'content': 'Системное событие стенда — не ответ модели. Исполнение этого хода остановлено. Запросы и результаты инструментов сохранены в «Границе данных»; автоматического повтора не было.',
                'additional_kwargs': {'pilot_system_error': True}}
            try:
                bridge({**base, 'kind': 'save', 'messages': display + [notice], 'turn_index': turn_index})
            except Exception as ui_error:
                seal(folder / (turn_context + '.ui-save-failed.aesgcm'), {'error_type': type(ui_error).__name__},
                    key, turn_context + ':ui-save-failed')
            raise
        final = result['messages']
        if not final: raise RuntimeError('empty_turn_result')
        history.extend(final); display.extend(final); counts['turns'] += 1
        bridge({**base, 'kind': 'save', 'messages': display, 'turn_index': turn_index})
        seal(folder / f'{turn_key}.complete.aesgcm', {'messages': final, 'history': history, 'counts': counts,
            'workspace': {name: base64.b64encode(data).decode() for name, data in workspace.items()},
            'mirror_state': mirror.state(), 'source_loop': result, 'owner_retry_tag': retry_tag or None}, key, turn_key + ':complete')
        print(json.dumps({'case': case['source_index'], 'mode': mode, 'turn_complete': counts['turns'],
                          'total_turns': len(case['source_user_turns']), 'model_requests': counts['models'],
                          'local_tool_calls': counts['tools'], 'live': live}), flush=True)
    summary = {'source_index': case['source_index'], 'mode': mode, 'status': 'complete', **counts,
        'scope': scope, 'live': live, 'original_user_sequence_sha256': case['source_user_sequence_sha256'],
        'historical_answers_injected': False, 'original_orchestrator_reproduced': False,
        'actual_doubleup_execution_stage': True, 'local_tools_only': True,
        'url': f'http://127.0.0.1:18880/{scope["tenant_id"]}/assistantnew/{scope["agent_id"]}?thread={scope["thread_id"]}'}
    seal(summary_path, summary, key, prefix + ':complete')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--case-index', type=int)
    parser.add_argument('--mode', action='append', choices=('none', 'builtin', 'pseudex'))
    parser.add_argument('--continue-other-arms', action='store_true', help='Preserve a stopped arm without retrying it, then run independent fresh arms')
    parser.add_argument('--revision', default='v1')
    parser.add_argument('--bundle', default='full-dialogue-cases')
    parser.add_argument('--parallel-cases', type=int, default=1)
    parser.add_argument('--resume-known-prefix', action='store_true', help='Owner-approved new attempt only after an authenticated completed prefix; unknown hold remains')
    args = parser.parse_args()
    if not args.revision or any(char not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for char in args.revision):
        raise RuntimeError('invalid_run_revision')
    if not 1 <= args.parallel_cases <= 10: raise RuntimeError('invalid_parallel_case_bound')
    if args.mode and len(args.mode) != len(set(args.mode)): raise RuntimeError('duplicate_modes_refused')
    CANCELLED.clear()
    with httpx.Client(timeout=5, trust_env=False) as client:
        health = client.get('http://127.0.0.1:18850/health'); health.raise_for_status()
    if health.json().get('mode') != ('live' if args.live else 'fixture'):
        raise RuntimeError('gateway_mode_does_not_match_run')
    if not args.bundle or len(args.bundle) > 60 or any(char not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for char in args.bundle):
        raise RuntimeError('invalid_bundle_name')
    runtime = STATE / 'runtime'; key = (runtime / (args.bundle + '.key')).read_bytes()
    raw = (runtime / (args.bundle + '.aesgcm')).read_bytes()
    packet = json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], AAD))
    folder = STATE / (packet['run_id'] + ('-live-' if args.live else '-dry-') + args.revision)
    folder.mkdir(mode=0o700, exist_ok=True)
    cases = [case for case in packet['cases'] if args.case_index is None or case['source_index'] == args.case_index]
    ids = [case['case_id'] for case in cases]
    if len(ids) != len(set(ids)): raise RuntimeError('duplicate_case_ids_refused')
    def run_case(case):
        results = []
        for mode in args.mode or ('none', 'builtin', 'pseudex'):
            if CANCELLED.is_set(): break
            try:
                results.append(run_arm(packet, case, mode, args.live, key, folder, args.resume_known_prefix))
            except Exception as error:
                if not args.continue_other_arms: raise
                stopped = {'source_index': case['source_index'], 'mode': mode, 'status': 'stopped',
                    'error_type': type(error).__name__, 'retry_performed': False, 'completed_user_sequence': False}
                prefix = case['case_id'] + '-' + mode
                seal(folder / (prefix + '.stopped-' + uuid.uuid4().hex + '.aesgcm'), stopped, key, prefix + ':stopped')
                results.append(stopped)
                print(json.dumps({**stopped, 'independent_arms_will_continue': not CANCELLED.is_set()}), flush=True)
        return results
    summaries = []
    if args.parallel_cases == 1:
        for case in cases: summaries.extend(run_case(case))
    else:
        # Only the outer wrapper owns egress/key lifecycle. Each worker owns one
        # case and executes its modes/turns in order; the ledger is global/atomic.
        pool = ThreadPoolExecutor(max_workers=min(args.parallel_cases, max(1, len(cases))))
        try:
            futures = [pool.submit(run_case, case) for case in cases]
            for future in as_completed(futures): summaries.extend(future.result())
        finally:
            CANCELLED.set()
            pool.shutdown(wait=True, cancel_futures=True)
    if not summaries: raise RuntimeError('no_cases_selected')
    seal(folder / ('report-' + uuid.uuid4().hex + '.aesgcm'), {'run_id': packet['run_id'], 'arms': summaries,
         'manual_qualitative_review_only': True, 'formal_pii_metrics': False}, key, packet['run_id'] + ':report')
    print(json.dumps({'complete_arms': sum(row.get('status') == 'complete' for row in summaries),
        'stopped_arms': sum(row.get('status') == 'stopped' for row in summaries),
        'live': args.live, 'historical_answers_injected': False}))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'ok': False, 'error_type': type(error).__name__, 'error_code': str(error) if isinstance(error, RuntimeError) else 'replay_failed'}), file=sys.stderr)
        raise SystemExit(2)
