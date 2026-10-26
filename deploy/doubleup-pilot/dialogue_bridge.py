"""One private local command using the actual DoubleUp provider boundary.

Executed in the owned graph container; no HTTP endpoint, source DB or model key
is accepted from callers. Model/tool values travel stdin/captured stdout only.
Actual untrusted Python execution belongs to the separate host-side sandbox.
"""

import copy
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
import uuid

logging.disable(logging.CRITICAL)

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pymongo import MongoClient

from chat_graph.llm_utils import http_post_with_retry, messages_to_openai_format
from chat_graph.security.engine import mask_before_provider, restore
from chat_graph.security.levels import SecurityLevel
from chat_graph.security.vault import get_vault
from chat_graph.stages.execution_stage import trim_tool_result
from observability.request_context import RequestContext, reset_context, set_context
from repository.pseudex_pilot_inspections import get_inspection_store
from services.pseudex_pilot import record_tool_dispatch, record_tool_result
from services.pseudex_pilot_links import attach_output_message, attach_tool_message, text_digest


def message(value):
    role, content = value['role'], value.get('content')
    kwargs = dict(value.get('additional_kwargs') or {})
    identity = value['id']
    if role == 'user':
        kwargs['pseudex_message_id'] = identity
        kwargs['pseudex_source_text_sha256'] = text_digest(content) if isinstance(content, str) else None
        return HumanMessage(id=identity, content=content, additional_kwargs=kwargs)
    if role == 'system': return SystemMessage(id=identity, content=content)
    if role == 'tool': return ToolMessage(id=identity, content=content, tool_call_id=value['tool_call_id'], additional_kwargs=kwargs)
    calls = [{'id': call['id'], 'name': call['function']['name'], 'args': json.loads(call['function']['arguments']),
              'type': 'tool_call'} for call in value.get('tool_calls') or []]
    return AIMessage(id=identity, content=content or '', tool_calls=calls, additional_kwargs=kwargs)


def wire(value):
    result = {'role': 'user' if value.type == 'human' else 'assistant' if value.type == 'ai' else value.type,
              'content': value.content, 'id': value.id, 'additional_kwargs': value.additional_kwargs}
    if isinstance(value, ToolMessage): result['tool_call_id'] = value.tool_call_id
    if isinstance(value, AIMessage) and value.tool_calls:
        result['tool_calls'] = [{'id': call['id'], 'type': 'function', 'function': {'name': call['name'],
            'arguments': json.dumps(call['args'], ensure_ascii=False)}} for call in value.tool_calls]
    return result


def seed(db, scope, case_index, mode, live):
    now = datetime.now(timezone.utc)
    kind = 'LiteLLM' if live else 'Fixture (без модели)'
    org, graph, thread = (scope[key] for key in ('tenant_id', 'agent_id', 'thread_id'))
    db.organizations.update_one({'org_id': org}, {'$setOnInsert': {'org_id': org, 'slug': org,
        'name': f'Диалог {case_index + 1} · {kind}', 'owner_id': 'pilot-owner',
        'status': 'active', 'created_at': now}}, upsert=True)
    db.organization_members.update_one({'org_id': org, 'user_id': 'pilot-owner'}, {'$setOnInsert': {
        'org_id': org, 'user_id': 'pilot-owner', 'role': 'owner', 'status': 'active', 'created_at': now}}, upsert=True)
    db.graphs.update_one({'graph_id': graph}, {'$setOnInsert': {'graph_id': graph, 'builtin_id': 'simple_chat',
        'type': 'builtin', 'enabled': True, 'name': f'{kind} · диалог {case_index + 1} · {mode}', 'user_id': 'pilot-owner',
        'org_id': org, 'public': False, 'security_level': 3, 'tools': [], 'default_tools': [],
        'model_id': 'pilot/deepseek-v4-flash', 'ai_model': 'pilot/deepseek-v4-flash',
        'description': 'Наглядный causal replay с локальными инструментами; не исторический multi-agent orchestrator.',
        'retrieval': {'enabled': False}, 'kb_tools': False, 'created_at': now}}, upsert=True)
    db.threads.update_one({'thread_id': thread}, {'$setOnInsert': {'thread_id': thread, 'org_id': org,
        'graph_id': graph, 'user_id': 'pilot-owner', 'title': f'{kind} · полный диалог {case_index + 1} · {mode}',
        'status': 'active', 'created_at': now, 'last_activity': now, 'message_count': 0}}, upsert=True)


def rpc(event):
    print(json.dumps(event, ensure_ascii=False, allow_nan=False), flush=True)
    value = json.loads(sys.stdin.readline())
    if value.get('ok') is not True:
        raise RuntimeError('replay_parent_refused_rpc')
    return value


def run_turn(command, scope):
    from types import SimpleNamespace
    from chat_graph.stages import execution_stage as execution
    from chat_graph.stages.response_formatting_stage import ResponseFormattingStage
    from tools.search_tools import get_tool_input_schema

    class RemoteTool:
        def __init__(self, declaration):
            self.name = declaration['name']
            self.description = declaration['description']
            schema = copy.deepcopy(declaration['parameters'])
            class Arguments:
                @classmethod
                def model_json_schema(cls): return schema
                @classmethod
                def schema(cls): return schema
            self.args_schema = Arguments

        def invoke(self, arguments):
            response = rpc({'type': 'tool', 'name': self.name, 'arguments': arguments})
            if response.get('generated_documents'):
                import threading
                ctx = getattr(threading.current_thread(), 'pipeline_context', None)
                if isinstance(ctx, dict):
                    ctx.setdefault('generated_documents', []).extend(response['generated_documents'])
            return response['result']

    tools = [RemoteTool(item) for item in command['contracts'].values()]
    for tool in tools:
        if get_tool_input_schema(tool) != command['contracts'][tool.name]['parameters']:
            raise RuntimeError('replay_tool_schema_projection_mismatch')
    access = json.loads(Path('/run/pilot/model-access.json').read_text()) if command['live'] else {'request_key': 'pilot-fixture-no-remote-access'}
    original_post = execution.http_post_with_retry
    counts = {'models': 0, 'http_failure': False, 'model_statuses': []}
    def boundary(url, **kwargs):
        if url != 'http://gateway:4000/v1/chat/completions':
            raise RuntimeError('replay_provider_route_refused')
        body = kwargs['json_data']
        body['thinking'] = {'type': 'disabled'}
        body['max_tokens'] = command['max_tokens']
        body['stream'] = False
        counts['models'] += 1
        from hashlib import sha256
        digest = sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        rpc({'type': 'model_start', 'step': counts['models'], 'request_sha256': digest})
        kwargs.update(max_retries=0, retry_delay=0, timeout=360)
        try:
            result = original_post(url, **kwargs)
        except Exception as error:
            counts['http_failure'] = True
            counts['model_statuses'].append('error:' + type(error).__name__)
            rpc({'type': 'model_error', 'step': counts['models'], 'error_type': type(error).__name__})
            raise
        counts['model_statuses'].append(int(result.status_code))
        counts['http_failure'] = counts['http_failure'] or result.status_code != 200
        rpc({'type': 'model_done', 'step': counts['models'], 'http_status': result.status_code,
             'attempt_id': result.extensions.get('pseudex_attempt_id')})
        result.raise_for_status()
        return result
    execution.http_post_with_retry = boundary
    try:
        current = [message(value) for value in command['history']]
        prepared = mask_before_provider(current, model_name='deepseek-v4-flash', graph_id=scope['agent_id'],
            thread_id=scope['thread_id'], org_id=scope['tenant_id'], level=SecurityLevel.HIGH)
        context = SimpleNamespace(extra_data={}, connection_manager=None, user_id='pilot-owner', org_id=scope['tenant_id'],
            config={'configurable': {'thread_id': scope['thread_id']}}, final_messages=None)
        stage = execution.ExecutionStage()
        previous_max = execution.MAX_TOOL_ITERATIONS
        if command.get('remaining_tool_iterations') is not None:
            remaining = command['remaining_tool_iterations']
            if type(remaining) is not int or not 1 <= remaining < previous_max:
                raise RuntimeError('recovery_iteration_bound_invalid')
            execution.MAX_TOOL_ITERATIONS = remaining
        final = stage._execute_with_tools_new_api(prepared, {'model': 'deepseek-v4-flash',
            'base_url': 'http://gateway:4000/v1', 'api_key': access['request_key'],
            'headers': {} if command['live'] else {'X-Pilot-Tool-Loop-Fixture': '1'}}, tools,
            model_name='deepseek-v4-flash', user_id='pilot-owner', graph_id=scope['agent_id'],
            thread_id=scope['thread_id'], context=context)
        context.final_messages = final
        ResponseFormattingStage().process(context)
        if command['mode'] == 'builtin':
            # Capture the actual delivered post-formatter text. No v2 receipt is
            # invented for the legacy renderer, and tool arguments stay untouched.
            store = get_inspection_store()
            for value in context.final_messages:
                attempt = value.additional_kwargs.get('pseudex_attempt_id')
                if not attempt or not isinstance(value.content, str): continue
                recorded = store.get_attempt(scope['tenant_id'], attempt)
                delivered = copy.deepcopy(recorded.get('restored_response'))
                if isinstance(delivered, dict) and delivered.get('choices'):
                    delivered['choices'][0]['message']['content'] = value.content
                    store.update_attempt(attempt, restored_response=delivered)
                    attach_output_message(value, attempt)
        return {'ok': not counts['http_failure'], 'model_statuses': counts['model_statuses'], 'messages': [wire(value) for value in context.final_messages],
            'model_requests': counts['models'], 'source_tool_loop': True,
            'source_max_tool_iterations': execution.MAX_TOOL_ITERATIONS}
    finally:
        execution.http_post_with_retry = original_post


def main(command):
    if os.getenv('PSEUDEX_PILOT') != '1' or os.getenv('MONGO_DB_NAME') != 'doubleup_pilot':
        raise RuntimeError('isolated_pilot_required')
    mode, scope = command['mode'], command['scope']
    if mode not in ('none', 'builtin', 'pseudex') or not re.fullmatch(r'doubleup-dialogue-[0-9a-f]{12}', scope['tenant_id']):
        raise RuntimeError('replay_scope_invalid')
    if scope['owner_id'] != 'pilot-owner': raise RuntimeError('replay_owner_invalid')
    os.environ['PII_BACKEND'] = mode
    token = set_context(RequestContext(command['root_request_id'], user_id='pilot-owner', org_id=scope['tenant_id'],
        graph_id=scope['agent_id'], thread_id=scope['thread_id']))
    try:
        kind = command['kind']
        if kind == 'turn':
            return run_turn(command, scope)
        if kind == 'seed':
            with MongoClient(os.environ['MONGO_URI'], serverSelectionTimeoutMS=5000) as client:
                seed(client.get_database(), scope, command['case_index'], mode, command['live'])
            return {'ok': True}
        if kind == 'call':
            body = copy.deepcopy(command['body'])
            if body.get('model') != 'deepseek-v4-flash' or body.get('stream') is not False:
                raise RuntimeError('replay_model_or_stream_invalid')
            original = [message(value) for value in command['history']]
            prepared = mask_before_provider(original, model_name=body['model'], graph_id=scope['agent_id'],
                thread_id=scope['thread_id'], org_id=scope['tenant_id'], level=SecurityLevel.HIGH)
            body['messages'] = messages_to_openai_format(prepared)
            access = json.loads(Path('/run/pilot/model-access.json').read_text()) if command['live'] else {'request_key': 'pilot-fixture-no-remote-access'}
            headers = {'Authorization': 'Bearer ' + access['request_key'], 'x-litellm-spend-logs-metadata': json.dumps({
                'billing_tenant_id': scope['tenant_id'], 'billing_user_id': 'pilot-owner',
                'billing_assistant_id': scope['agent_id'], 'billing_dialog_id': scope['thread_id']})}
            response = http_post_with_retry('http://gateway:4000/v1/chat/completions', headers=headers, json_data=body,
                timeout=150, max_retries=0, retry_delay=0)
            response.raise_for_status()
            result = response.json(); attempt = response.extensions['pseudex_attempt_id']
            choice = result['choices'][0]['message']
            final = not choice.get('tool_calls')
            if final and mode == 'builtin' and isinstance(choice.get('content'), str):
                # Mirror ResponseFormattingStage exactly: builtin does NOT
                # restore function arguments before tool invocation.
                choice['content'] = restore(choice['content'], get_vault().load(scope['thread_id']))
                get_inspection_store().update_attempt(attempt, restored_response=copy.deepcopy(result))
            ai = message({'id': 'pilot-assistant-' + uuid.uuid4().hex, 'role': 'assistant', **choice})
            ai = attach_output_message(ai, attempt, record_output=final)
            return {'ok': True, 'attempt_id': attempt, 'message': wire(ai), 'usage': result.get('usage'),
                    'finish_reason': result['choices'][0].get('finish_reason'), 'model': result.get('model')}
        if kind == 'native_document':
            # Execute the TARGET backend implementation, with identities supplied
            # only by this trusted local scope. Never call a production store.
            from urllib.parse import urlsplit
            import threading
            name = command['name']
            if name not in ('create_document', 'read_document', 'append_to_document'):
                raise RuntimeError('native_document_tool_refused')
            mongo = urlsplit(os.environ.get('MONGO_URI', ''))
            if mongo.hostname not in ('mongodb', '127.0.0.1', 'localhost'):
                raise RuntimeError('native_document_nonlocal_mongo_refused')
            from tools import document_tools
            endpoint = os.environ.get('S3_ENDPOINT_URL', '')
            if urlsplit(endpoint).hostname not in ('minio', '127.0.0.1', 'localhost'):
                raise RuntimeError('native_document_nonlocal_storage_refused')
            ctx = {'user_id':scope['owner_id'],'org_id':scope['tenant_id'],
                   'graph_id':scope['agent_id'],'thread_id':scope['thread_id'],
                   'generated_documents':[]}
            threading.current_thread().pipeline_context = ctx
            output = getattr(document_tools, name).invoke(command['arguments'])
            failed = not isinstance(output, str) or output.startswith(('Ошибка', 'Нет доступа', 'Документ не найден', 'У документа нет'))
            return {'ok':True,'tool_ok':not failed,
                    'result':output if not failed else 'local_document_operation_failed',
                    'generated_documents':ctx['generated_documents'],'local_mutations_only':True}
        if kind == 'dispatch':
            record_tool_dispatch(command['attempt_id'], command['name'], command['arguments'],
                tool_call_id=command['tool_call_id'], execution_id=command['execution_id'], choice_index=0,
                executor='safe_local_replay')
            return {'ok': True}
        if kind == 'result':
            raw = command['raw_result']
            record_tool_result(command['attempt_id'], event='completed', name=command['name'],
                tool_call_id=command['tool_call_id'], execution_id=command['execution_id'], choice_index=0,
                result_status=command['result_status'], result=raw, executor='safe_local_replay')
            forwarded = trim_tool_result(raw)
            if not isinstance(forwarded, str): forwarded = json.dumps(forwarded, ensure_ascii=False)
            msg = ToolMessage(content=forwarded, tool_call_id=command['tool_call_id'])
            msg = attach_tool_message(msg, command['attempt_id'], raw, command['name'])
            return {'ok': True, 'message': wire(msg)}
        if kind == 'save':
            from graph_manager.mongo_graph_saver import MongoSaver
            from langgraph.checkpoint.base import empty_checkpoint
            checkpoint = empty_checkpoint(); checkpoint['channel_values'] = {'messages': [message(value) for value in command['messages']]}
            saver = MongoSaver()
            saver.put({'configurable': {'thread_id': scope['thread_id'], 'checkpoint_ns': ''}}, checkpoint,
                {'source': 'update', 'step': command['turn_index'], 'parents': {}}, {})
            return {'ok': True}
        raise RuntimeError('replay_command_unknown')
    finally:
        reset_context(token)


if __name__ == '__main__':
    try:
        command = json.loads(sys.stdin.readline())
        print(json.dumps({'type': 'hello', 'pid': os.getpid(), 'nonce': os.environ.get('PSEUDEX_REPLAY_EXEC_ID')}), flush=True)
        print(json.dumps({'type': 'final', 'payload': main(command)}, ensure_ascii=True, allow_nan=False), flush=True)
    except Exception as error:
        import httpx
        result = {'ok': False, 'error_type': type(error).__name__}
        if isinstance(error, httpx.HTTPStatusError): result['http_status'] = error.response.status_code
        print(json.dumps(result))
        raise SystemExit(2)
