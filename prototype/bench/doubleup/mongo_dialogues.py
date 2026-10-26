"""DATA-ONLY full-root transcript intake and application-project Langfuse join.

No Mongo constructors, provider SDKs, model calls, source tools or remote writes.
Checkpoint decoding is isolated in the existing backend image, without network,
mounts or Docker logs. Only ciphertext is written; CLI errors are constant codes.
"""

import argparse
import collections
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse

import yaml

from .__main__ import observations
from .corpus import tools, walk
from .langfuse import Client, HOST, attribution
from .storage import PilotError, RunStore, canonical, digest, hashed

CONFIG = Path('/Users/igor/Projects/2up/projects/2up-aiplatform-gitops/2up-aiplatform-backend/values-prod.yaml')
IMAGE = '2up-aiplatform-backend-user_api:latest'
SOURCE = 'mongo-full-chats-local-pilot-v2'
MAX_BYTES = 128 * 1024 * 1024

# Never use MongoSaver here: its constructor creates indexes. The type-pair is
# exactly the dumps_typed tuple stored by MongoSaver._safe_serialize/put.
DECODER = r'''
import sys,json,logging,warnings,datetime,uuid
from bson import json_util,ObjectId,Binary,Decimal128
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langchain_core.messages import BaseMessage,HumanMessage,AIMessage,ToolMessage,SystemMessage,FunctionMessage,ChatMessage
import inspect,ormsgpack
logging.disable(logging.CRITICAL)
# This image's older serde advertises allowed_objects in a warning but lacks
# that keyword. Never fall back to its arbitrary-import msgpack hook/reviver.
classes={c.__name__:c for c in (HumanMessage,AIMessage,ToolMessage,SystemMessage,FunctionMessage,ChatMessage)}
allowed={(c.__module__,c.__name__):c for c in classes.values()}
allowed.update({('langchain_core.messages',name):cls for name,cls in classes.items()})
def safe_ext(code,data):
    value=ormsgpack.unpackb(data,ext_hook=safe_ext,option=ormsgpack.OPT_NON_STR_KEYS)
    if code not in (0,1,2,4,5) or not isinstance(value,(list,tuple)) or len(value)<3:
        raise TypeError('unsupported_extension')
    cls=allowed.get(tuple(value[:2]))
    if cls is None:
        # Preserve non-message graph state as explicitly UNSUPPORTED data, never
        # import application constructors, coerce to str or fabricate objects.
        return {'$unsupported_constructor':{'ext_code':code,'module':value[0],
            'class':value[1],'serialized_arguments':value[2:]}}
    if code==0:return cls(value[2])
    if code==1:return cls(*value[2])
    return cls(**value[2])
class MessagesOnlySerializer(JsonPlusSerializer):
    def _reviver(self,value):
        if value.get('type')=='constructor' and value.get('lc') in (1,2):
            identity=value.get('id')
            if not isinstance(identity,list) or len(identity)<2:raise TypeError('unsupported_constructor')
            module='.'.join(identity[:-1]); cls=allowed.get((module,identity[-1]))
            if cls is None and identity[:-1] in (['langchain','schema','messages'],['langchain_core','messages']):
                cls=classes.get(identity[-1])
            if cls is None:return {'$unsupported_constructor':value}
            return cls(**value.get('kwargs',{}))
        if value.get('lc') in (1,2):raise TypeError('unsupported_constructor')
        return value
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    if 'allowed_objects' in inspect.signature(JsonPlusSerializer).parameters:
        serde=JsonPlusSerializer(allowed_objects='messages')
        policy='native_allowed_objects_messages'
    else:
        serde=MessagesOnlySerializer(__unpack_ext_hook__=safe_ext,pickle_fallback=False)
        policy='legacy_explicit_messages_only_no_default_reviver_or_ext_hook'
def convert(value):
    if isinstance(value,BaseMessage):
        return convert(value.model_dump(mode='python'))
    if value is None or type(value) in (str,int,float,bool):return value
    if isinstance(value,dict):
        if not all(isinstance(k,str) for k in value):raise TypeError('unsupported_key')
        if value.get('lc') == 1 and value.get('type') in ('constructor','not_implemented'):
            raise TypeError('unsupported_constructor')
        return {k:convert(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [convert(v) for v in value]
    if isinstance(value,(datetime.datetime,datetime.date,uuid.UUID,ObjectId,bytes,Binary,Decimal128)):
        return json.loads(json_util.dumps(value,json_options=json_util.CANONICAL_JSON_OPTIONS))
    raise TypeError('unsupported_object')
def checkpoint(doc):
    if doc is None:return None
    pair=doc.get('checkpoint_b')
    if not isinstance(pair,(list,tuple)) or len(pair)!=2 or pair[0] not in ('json','msgpack') or not isinstance(pair[1],bytes):
        raise TypeError('unsupported_typed_pair')
    cp=serde.loads_typed(tuple(pair))
    meta=serde.loads_typed(tuple(doc['metadata_b']))
    if not isinstance(cp,dict) or not isinstance(meta,dict):raise TypeError('unsupported_checkpoint')
    messages=(cp.get('channel_values') or {}).get('messages')
    if messages is not None and (not isinstance(messages,list) or not all(isinstance(m,BaseMessage) for m in messages)):
        raise TypeError('unsupported_messages')
    return {'attrs':convert({k:v for k,v in doc.items() if k not in ('checkpoint_b','metadata_b')}),
        'checkpoint':convert(cp),'metadata':convert(meta),
        'message_classes':[type(m).__name__ for m in messages] if messages is not None else []}
try:
    payload=json_util.loads(sys.stdin.buffer.read())
    decoded=[]
    for index,item in enumerate(payload['threads']):
        decoded.append({'index':index,'earliest':checkpoint(item['earliest_root_checkpoint']),
            'latest':checkpoint(item['latest_root_checkpoint'])})
    result={'ok':True,'decoded':decoded,'serializer_policy':policy}
    sys.stdout.write(json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':')))
except Exception as error:
    sys.stdout.write(json.dumps({'ok':False,'error_type':type(error).__name__}))
'''


def decode_offline(payload, store):
    """Capture original-derived bytes privately, encrypt before further inspection."""
    try:
        process = subprocess.run(['docker', 'run', '--rm', '--pull', 'never', '--network', 'none',
            '--log-driver', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt',
            'no-new-privileges', '-i', IMAGE, 'python', '-c', DECODER],
            input=canonical(payload), capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        raise PilotError('dialogues_decoder_process_failed') from None
    if process.returncode or len(process.stdout) > MAX_BYTES:
        raise PilotError('dialogues_decoder_process_or_size_refused')
    try:
        decoded = json.loads(process.stdout)
    except (ValueError, UnicodeDecodeError):
        raise PilotError('dialogues_decoder_response_invalid') from None
    store.encrypt('decoded-checkpoints.aesgcm', decoded)
    if decoded.get('ok') is not True:
        raise PilotError('dialogues_checkpoint_decode_unsupported')
    if len(decoded['decoded']) != len(payload['threads']):
        raise PilotError('dialogues_decoder_count_mismatch')
    return decoded['decoded']


def application_client(path=CONFIG):
    """Config is a credential source, never evidence. Do not archive/log its body."""
    try:
        env = yaml.safe_load(path.read_text())['env']
        host, public, secret = (env[key] for key in ('LANGFUSE_HOST', 'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY'))
    except Exception:
        raise PilotError('dialogues_application_config_unavailable') from None
    if host != HOST or not all(isinstance(v, str) and v for v in (public, secret)):
        raise PilotError('dialogues_application_config_invalid')
    return Client((host, public, secret))


def number(value):
    if isinstance(value, dict):
        for key in ('$numberInt', '$numberLong'):
            if key in value:
                return int(value[key])
        raise PilotError('dialogues_number_unsupported')
    return int(value)


def transcript(decoded):
    if not decoded:
        return []
    return (decoded['checkpoint'].get('channel_values') or {}).get('messages') or []


def message_role(message):
    return {'human': 'user', 'ai': 'assistant', 'tool': 'tool', 'system': 'system',
            'function': 'function', 'chat': 'chat'}.get(message.get('type'), 'unsupported')


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)


SHAPES = {
    'email_shape': re.compile(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b'),
    'ru_phone_shape': re.compile(r'(?<!\d)(?:\+7|8)[ ()-]*\d{3}[ ()-]*\d{3}[ ()-]*\d{2}[ ()-]*\d{2}(?!\d)'),
    'cued_id_shape': re.compile(r'(?i)(?:паспорт|снилс|инн)\s*[:№#-]?\s*\d[\d -]{5,22}\d'),
}


def opportunity_counts(messages):
    # Selection opportunities only: no gold labels, names/addresses guessed from
    # prose, entity annotation, detector tuning, recall or provider-bound output.
    counts = collections.Counter({key: 0 for key in SHAPES})
    for message in messages:
        fields = [message.get('content'), message.get('tool_calls')]
        for text in strings(fields):
            counts.update({key: len(pattern.findall(text)) for key, pattern in SHAPES.items()})
    return dict(counts)


def ordered_tool_activity(messages):
    calls, results = [], []
    for index, message in enumerate(messages):
        if message_role(message) == 'assistant':
            # BaseMessage.tool_calls is canonical. additional_kwargs often repeats
            # the same provider calls; preserve it in messages, do not double count.
            for call in message.get('tool_calls') or []:
                calls.append({'message_index': index, 'message_id': message.get('id'), 'call': call})
        if message_role(message) == 'tool':
            results.append({'message_index': index, 'message_id': message.get('id'),
                'call_id': message.get('tool_call_id'), 'message': message})
    links = []
    for call in calls:
        cid = call['call'].get('id')
        matching = [r for r in results if cid and r['call_id'] == cid]
        variants = [c for c in calls if cid and c['call'].get('id') == cid]
        status = ('missing_call_id' if not cid else 'ambiguous_call_id' if len(variants) > 1 else
                  'ambiguous_results' if len(matching) > 1 else 'missing_result' if not matching else
                  'result_precedes_call' if matching[0]['message_index'] <= call['message_index'] else 'linked')
        links.append({'call_id': cid, 'status': status, 'call_message_index': call['message_index'],
            'result_message_indices': [r['message_index'] for r in matching]})
    return {'calls': calls, 'results': results, 'links': links,
        'orphan_results': [r for r in results if not r['call_id'] or not any(c['call'].get('id') == r['call_id'] for c in calls)]}


def source_text_projection(content):
    """Mirror only supported extract_text_content semantics, never str(object)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get('type') == 'text':
                    text = block.get('text', '')
                    if not isinstance(text, str):
                        raise PilotError('dialogues_user_text_block_unsupported')
                    parts.append(text)
            else:
                raise PilotError('dialogues_user_content_unsupported')
        return '\n'.join(parts)
    if isinstance(content, dict) and content.get('type') == 'text' and isinstance(content.get('text', ''), str):
        return content.get('text', '')
    raise PilotError('dialogues_user_content_unsupported')


def normalize_mongo(item, decoded):
    """Use checkpoint order and stable IDs, never dedup source text or Mongo saves."""
    thread = item['thread']
    messages, early = transcript(decoded['latest']), transcript(decoded['earliest'])
    ids = [m.get('id') for m in messages]
    early_ids = [m.get('id') for m in early]
    users = [m for m in messages if message_role(m) == 'user']
    docs = [m for m in item['messages'] if m.get('sender', {}).get('type') == 'user']
    # save_conversation_to_messages gives Mongo docs NEW IDs, unrelated to the
    # original BaseMessage IDs. Verify its actual text projection in exact order
    # and multiplicity; this is correspondence, never deduplication by text.
    doc_ids = [m.get('message_id') for m in docs]
    user_ids = [m.get('id') for m in users]
    user_text_matches = [source_text_projection(m.get('content')) == d.get('content', {}).get('text') for m, d in zip(users, docs)]
    latest, earliest = decoded['latest'], decoded['earliest']
    gaps = []
    if not latest or not messages:
        gaps.append('latest_root_messages_missing')
    if any(not isinstance(mid, str) or not mid for mid in ids) or len(set(ids)) != len(ids):
        gaps.append('root_message_ids_missing_or_duplicated')
    if any(message_role(m) == 'unsupported' for m in messages):
        gaps.append('unsupported_message_type')
    if len(users) != len(docs) or not all(user_text_matches):
        gaps.append('user_content_sequence_gap')
    if early_ids != ids[:len(early_ids)] or early != messages[:len(early)]:
        gaps.append('earliest_root_not_unchanged_prefix')
    if not earliest:
        gaps.append('earliest_root_missing')
    for root in (earliest, latest):
        if root and (root['attrs'].get('thread_id') != thread['thread_id'] or root['attrs'].get('checkpoint_ns') != ''):
            gaps.append('root_identity_mismatch')
    if earliest and earliest['attrs'].get('parent_checkpoint_id'):
        gaps.append('earliest_retained_root_has_parent')
    if item['compactions']:
        gaps.append('source_compaction_records_present')
    markers = []
    for source, obj in (('thread', thread), ('earliest', earliest), ('latest', latest)):
        for node, pointer in walk(obj):
            if isinstance(node, dict):
                for key, value in node.items():
                    if re.search(r'compact|truncat|fork|branch|strip', key, re.I):
                        markers.append({'source': source, 'pointer': pointer + '/' + key, 'value': value})
    activity = ordered_tool_activity(messages)
    counts = collections.Counter(message_role(m) for m in messages)
    root_gaps = [g for g in gaps if g not in ('user_content_sequence_gap',)]
    unsupported = [{'pointer': pointer, 'value': node['$unsupported_constructor']}
        for node, pointer in walk(latest) if isinstance(node, dict) and '$unsupported_constructor' in node]
    return {'thread': thread, 'candidate': item['candidate'], 'messages': messages,
        'ordered_message_ids': ids, 'user_turns': users, 'user_message_ids': user_ids,
        'mongo_user_messages': docs, 'mongo_user_message_ids': doc_ids,
        'system_prompts': [m for m in messages if message_role(m) == 'system'],
        'checkpoint_proof': {'earliest': earliest, 'latest': latest,
            'root_checkpoint_count': item['root_checkpoint_count'], 'compactions': item['compactions'],
            'markers': markers, 'unsupported_nonmessage_constructors': unsupported,
            'all_mongo_users_retained_unchanged': len(users) == len(docs) and all(user_text_matches),
            'user_correspondence': [{'mongo_message_id': did, 'root_message_id': uid, 'source_text_equal': match}
                for did, uid, match in zip(doc_ids, user_ids, user_text_matches)],
            'user_identity_semantics': 'mongo_save_generates_new_ids_match_full_ordered_text_projection_not_id',
            'earliest_root_unchanged_prefix': early == messages[:len(early)],
            'earliest_root_ids_retained_in_order': early_ids == ids[:len(early_ids)],
            'full_root_chain_exported': False, 'point_in_time_snapshot': False},
        'source_completeness': {'visible_transcript_complete': not gaps, 'gaps': sorted(set(gaps)),
            'authoritative_root_export_complete': not root_gaps,
            'cross_source_user_projection_equal': len(users) == len(docs) and all(user_text_matches),
            'user_projection_mismatch_is_not_proof_of_deletion': True,
            'original_mongo_user_sequence_preserved_separately': True,
            'scope': 'latest_root_visible_history_verified_against_all_user_docs_and_earliest_root',
            'all_mongo_message_docs_no_date_window': True, 'graph_config_resources_exported': False},
        'counts': {'user': counts['user'], 'assistant': counts['assistant'], 'tool': counts['tool'],
            'system': counts['system'], 'messages': len(messages), 'tool_calls': len(activity['calls']),
            'tool_results': len(activity['results']), 'linked_tool_calls': sum(l['status'] == 'linked' for l in activity['links']),
            'mongo_user_documents': len(docs), 'mongo_assistant_documents': sum(m.get('sender', {}).get('type') == 'assistant' for m in item['messages'])},
        'timestamps': {'first_mongo_message': item['messages'][0].get('created_at') if item['messages'] else None,
            'last_mongo_message': item['messages'][-1].get('created_at') if item['messages'] else None,
            'latest_checkpoint': latest['attrs'].get('ts') if latest else None},
        'sensitive_opportunity_shape_counts': opportunity_counts(messages), 'tools': activity,
        'is_causal_replay': False, 'pii_gold_labels': False, 'original_values_unchanged': True}


class EvidenceClient:
    """GET-only adapter: encrypt each successful response before any downstream use."""

    def __init__(self, client, store, trace_cap, observation_cap):
        self.client, self.store = client, store
        self.trace_cap, self.observation_cap = trace_cap, observation_cap
        self.trace_requests, self.observation_requests = 0, 0
        self.sequence = 0
        self.pages = []

    def get(self, path, params=None, record=True):
        if path.startswith('/api/public/traces/'):
            if self.trace_requests >= self.trace_cap:
                raise PilotError('dialogues_trace_budget_incomplete')
            self.trace_requests += 1
        if path.startswith(('/api/public/observations', '/api/public/v2/observations')):
            if self.observation_requests >= self.observation_cap:
                raise PilotError('dialogues_observation_budget_incomplete')
            self.observation_requests += 1
        response = self.client.get(path, params, record)
        self.store.encrypt('http-' + str(self.sequence).zfill(5) + '.aesgcm', {
            'request': {'method': 'GET', 'path': path, 'params': params, 'body': None},
            'request_sha256': hashed([path, params]), 'request_body_sha256': digest(b''),
            'response': response, 'receipt': self.client.response_receipts[-1]})
        self.sequence += 1
        return response

    def paginated(self, path, params, max_pages=4):
        return Client.paginated(self, path, params, max_pages)


def require_session(trace, thread):
    if trace.get('sessionId') != thread['thread_id']:
        raise PilotError('dialogues_session_filter_mismatch')
    # userId is never a tenant. Missing org metadata is allowed, not certified by
    # guessing: the Mongo thread itself supplies the authoritative identity.
    tenants = attribution(trace)['tenant_evidence']
    if any(value != thread['org_id'] for value in tenants):
        raise PilotError('dialogues_trace_org_conflict')
    return {'org_metadata_present': bool(tenants), 'org_metadata_consistent': True}


def list_session(client, thread):
    rows, proof = client.paginated('/api/public/traces', {
        'sessionId': thread['thread_id'], 'fields': 'core', 'orderBy': 'timestamp.asc'}, 4)
    org = [require_session(row, thread) for row in rows]
    return rows, {**proof, 'session_filter_verified': True,
        'listing_org_metadata_present': sum(p['org_metadata_present'] for p in org)}


def normalized_events(trace, independent):
    """Independent list is the observation authority; retain embed separately."""
    events = []
    for observation in independent:
        if observation.get('traceId', observation.get('trace_id')) != trace['id']:
            raise PilotError('dialogues_observation_trace_identity_missing_or_mismatch')
        events.append({'id': observation['id'], 'trace_id': trace['id'],
            'parent_observation_id': observation.get('parentObservationId'),
            'type': observation.get('type'), 'name': observation.get('name'),
            'start': observation.get('startTime'), 'end': observation.get('endTime'),
            'input_present': 'input' in observation, 'output_present': 'output' in observation,
            'input': observation.get('input'), 'output': observation.get('output'),
            'model': observation.get('model'), 'model_parameters': observation.get('modelParameters'),
            'metadata': observation.get('metadata'), 'original_observation': observation})
    return events


def explicit_context(sources):
    schemas = tools(sources)
    prompts, resources, models = [], [], []
    for source, value in sources:
        for node, pointer in walk(value):
            if not isinstance(node, dict):
                continue
            identity = node.get('id')
            is_constructor_system = (isinstance(identity, list) and identity[-1:] == ['SystemMessage']
                                     and node.get('type') == 'constructor')
            if node.get('role') == 'system' or node.get('type') == 'system' or is_constructor_system:
                prompts.append({'source': source, 'pointer': pointer, 'value': node})
            for key in ('resources', 'resource', 'resource_uri', 'resource_id', 'resourceIds', 'resource_ids',
                        'attachments', 'attachment_refs'):
                if key in node:
                    resources.append({'source': source, 'pointer': pointer + '/' + key, 'value': node[key]})
            if any(k in node for k in ('model', 'modelParameters', 'model_kwargs', 'model_name')):
                models.append({'source': source, 'pointer': pointer, 'values': {
                    k: node[k] for k in ('model', 'model_name', 'modelParameters', 'model_kwargs', 'temperature', 'max_tokens') if k in node}})
    for call in schemas['calls']:
        arguments = call['arguments']
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                continue
        for node, pointer in walk(arguments):
            if isinstance(node, dict):
                for key in ('url', 'urls', 'dataset_id', 'thread_id', 'sheet', 'file_id', 'folder_id'):
                    if key in node:
                        resources.append({'source': 'observed_tool_arguments', 'call_id': call['call_id'],
                            'pointer': pointer + '/' + key, 'value': node[key],
                            'external_resource_contents_exported': False})
    missing_names = sorted({c['name'] for c in schemas['calls'] if c['schema_status'] == 'missing' and c['name']})
    return {'tool_evidence': schemas, 'system_prompt_evidence': prompts,
        'resource_evidence': resources, 'model_settings_evidence': models,
        'missing_schema_tool_names': missing_names,
        'graph_config_resources_exported': False, 'causal_execution_supported': False}


def application_activity(join):
    # Source execution_stage wraps actual source tool invocations with the literal
    # span_context(f'tool:{tool_name}', input=tool_args). This is not a generic
    # named-SPAN heuristic and never supplies a fabricated tool call ID/schema.
    spans = []
    for event in join.get('events', []):
        name = event.get('name')
        if event.get('type') == 'SPAN' and isinstance(name, str) and name.startswith('tool:'):
            spans.append({'observation_id': event['id'], 'trace_id': event['trace_id'],
                'name': name[len('tool:'):], 'arguments': event.get('input'),
                'result': event.get('output'), 'output_present': event['output_present'],
                'call_id': None, 'call_id_link_status': 'not_emitted_by_source_span',
                'source_semantics': 'execution_stage.span_context_tool_prefix'})
    return {'source_tool_execution_spans': spans,
        'source_tool_execution_spans_are_not_additional_unique_calls': True}


def join_session(client, dialogue, rows, proof):
    thread = dialogue['thread']
    details, all_observations, events, observations_proof = [], [], [], []
    for row in sorted(rows, key=lambda r: (r.get('timestamp', ''), r['id'])):
        trace = client.get('/api/public/traces/' + urllib.parse.quote(row['id'], safe=''))
        if trace.get('id') != row['id']:
            raise PilotError('dialogues_trace_detail_id_mismatch')
        org = require_session(trace, thread)
        obs, obs_proof = observations(client, row['id'], 4)
        # Check org metadata on independent observations too, without assigning a
        # missing session to an observation that never carried one originally.
        for observation in obs:
            tenants = attribution({'metadata': observation.get('metadata')})['tenant_evidence']
            if any(value != thread['org_id'] for value in tenants):
                raise PilotError('dialogues_observation_org_conflict')
        events.extend(normalized_events(trace, obs))
        details.append(trace)
        all_observations.append({'trace_id': trace['id'], 'observations': obs})
        embedded = trace.get('observations') or []
        if not isinstance(embedded, list):
            raise PilotError('dialogues_embedded_observations_unsupported')
        independent_ids = {o['id'] for o in obs}
        embedded_ids = {o.get('id') for o in embedded if isinstance(o, dict)}
        if embedded_ids - independent_ids:
            raise PilotError('dialogues_independent_observations_missing_embedded_ids')
        observations_proof.append({'trace_id_sha256': hashed(trace['id']), **obs_proof, **org,
            'embedded_observations': len(embedded), 'independent_observations': len(obs),
            'embedded_ids_subset_of_independent': True})
    # Check membership and totals again after details: no implicit fixed snapshot
    # or silently drifting live listing. Both originals are encrypted by adapter.
    after, after_proof = list_session(client, thread)
    if {r['id'] for r in after} != {r['id'] for r in rows} or after_proof['server_total'] != proof['server_total']:
        raise PilotError('dialogues_session_drift_incomplete')
    return {'complete': True, 'session_listing': proof, 'session_recheck': after_proof,
        'trace_metadata': rows, 'trace_details': details, 'independent_observations': all_observations,
        'observation_proofs': observations_proof, 'events': events,
        'counts': {'traces': len(details), 'observations': len(events)},
        'identity_authority': 'mongo_thread_org_id_user_id_and_exact_langfuse_sessionId',
        'point_in_time_snapshot': False}


def public_summary(dialogue):
    join = dialogue.get('langfuse') or {}
    context = dialogue.get('source_context') or {}
    return {'thread_sha256': hashed(dialogue['thread']['thread_id']),
        'counts': dialogue['counts'], 'sensitive_opportunity_shape_counts': dialogue['sensitive_opportunity_shape_counts'],
        'mongo_visible_transcript_complete': dialogue['source_completeness']['visible_transcript_complete'],
        'mongo_authoritative_root_export_complete': dialogue['source_completeness']['authoritative_root_export_complete'],
        'mongo_cross_source_user_projection_equal': dialogue['source_completeness']['cross_source_user_projection_equal'],
        'mongo_gaps': dialogue['source_completeness']['gaps'],
        'source_compactions': len(dialogue['checkpoint_proof']['compactions']),
        'source_marker_records': len(dialogue['checkpoint_proof']['markers']),
        'unsupported_nonmessage_constructor_records': len(dialogue['checkpoint_proof']['unsupported_nonmessage_constructors']),
        'root_ordered_ids_sha256': hashed(dialogue['ordered_message_ids']),
        'user_turns_sha256': hashed(dialogue['user_turns']), 'langfuse_complete': join.get('complete', False),
        'langfuse_counts': join.get('counts', {}), 'langfuse_pending_reason': join.get('reason'),
        'tool_schema_variants': len(context.get('tool_evidence', {}).get('schemas', [])),
        'observed_call_id_count': len({c['call_id'] for c in context.get('tool_evidence', {}).get('calls', []) if c['call_id']}),
        'observed_result_variants': len(context.get('tool_evidence', {}).get('results', [])),
        'observed_call_link_status_counts': dict(collections.Counter(c['link_status'] for c in context.get('tool_evidence', {}).get('calls', []))),
        'source_tool_execution_spans': len(context.get('application_activity', {}).get('source_tool_execution_spans', [])),
        'source_system_prompt_records': len(context.get('system_prompt_evidence', [])),
        'resource_evidence_records': len(context.get('resource_evidence', [])),
        'observed_io_opportunity_shape_counts': context.get('observed_io_opportunity_shape_counts', {}),
        'normalized_sha256': hashed(dialogue)}


def collect(run_id, source_run=SOURCE, decoded_run=None, join=True, joined_run=None):
    source = RunStore(source_run, False)
    source_manifest = source.verify()
    payload = source.read_encrypted('mongo-originals.aesgcm')
    if len(payload['threads']) > 6 or payload.get('format') != 'mongo-extended-json-canonical-v2':
        raise PilotError('dialogues_source_bounds_or_format_unsupported')
    store = RunStore(run_id, True)
    # Keep source EJSON unchanged and separately authenticated, not reserialized
    # through BSON decoding. No configs/keys enter the lineage.
    store.encrypt('mongo-originals.aesgcm', payload)
    decoded_lineage = None
    if decoded_run:
        prior = RunStore(decoded_run, False)
        dm = prior.verify()
        if dm.get('source_manifest_sha256') != hashed(source_manifest):
            raise PilotError('dialogues_decoded_source_lineage_mismatch')
        value = prior.read_encrypted('decoded-checkpoints.aesgcm')
        if value.get('ok') is not True:
            raise PilotError('dialogues_decoded_source_unsupported')
        store.encrypt('decoded-checkpoints.aesgcm', value)
        decoded = value['decoded']
        decoded_lineage = {'run_id': decoded_run, 'manifest_sha256': hashed(dm),
            'serializer_policy': value.get('serializer_policy')}
    else:
        decoded = decode_offline(payload, store)
    if [d['index'] for d in decoded] != list(range(len(payload['threads']))):
        raise PilotError('dialogues_decoded_source_order_mismatch')
    dialogues = [normalize_mongo(item, dc) for item, dc in zip(payload['threads'], decoded)]
    saved, joined_lineage, prior_http = {}, None, None
    if joined_run:
        joined_store = RunStore(joined_run, False)
        jm = joined_store.verify()
        if jm.get('source_manifest_sha256') != hashed(source_manifest):
            raise PilotError('dialogues_joined_source_lineage_mismatch')
        prior_payload = joined_store.read_encrypted('full-dialogues.aesgcm')
        saved = {d['thread']['thread_id']: d for d in prior_payload['dialogues']}
        projects = prior_payload['projects']
        prior_http = joined_store.read_encrypted('http-provenance.aesgcm')
        joined_lineage = {'run_id': joined_run, 'manifest_sha256': hashed(jm),
            'raw_http_artifacts_retained_in_parent': True, 'new_remote_requests': 0}
        ec = None
    else:
        ec = EvidenceClient(application_client(), store, 60, 60) if join else None
        projects = ec.get('/api/public/projects') if ec else None
    # Complete short sessions first. All six Mongo transcripts remain in output,
    # including long sessions whose trace details exceed this bounded GET budget.
    for dialogue in sorted(dialogues, key=lambda d: d['counts']['user']):
        if joined_run:
            previous = saved.get(dialogue['thread']['thread_id'])
            if not previous or previous['messages'] != dialogue['messages'] or previous['user_turns'] != dialogue['user_turns']:
                raise PilotError('dialogues_joined_root_transcript_mismatch')
            dialogue['langfuse'] = previous['langfuse']
        elif ec:
            try:
                rows, proof = list_session(ec, dialogue['thread'])
                if len(rows) > ec.trace_cap - ec.trace_requests or len(rows) > ec.observation_cap - ec.observation_requests:
                    dialogue['langfuse'] = {'complete': False, 'reason': 'session_details_exceed_remaining_budget',
                        'session_listing': proof, 'trace_metadata': rows,
                        'counts': {'listed_traces': len(rows), 'traces': 0, 'observations': 0}}
                else:
                    dialogue['langfuse'] = join_session(ec, dialogue, rows, proof)
            except PilotError as error:
                # Every successful raw response is already encrypted even when
                # filter/drift/shape validation refuses to certify the join.
                code = str(error)
                if not re.fullmatch(r'[a-z0-9_]+', code):
                    code = 'dialogues_join_unavailable'
                dialogue['langfuse'] = {'complete': False, 'reason': code}
        else:
            dialogue['langfuse'] = {'complete': False, 'reason': 'offline_only_no_langfuse_requests'}
        sources = [('mongo_root_messages', [{**m, 'role': message_role(m)} for m in dialogue['messages']]),
            ('mongo_latest_checkpoint', dialogue['checkpoint_proof']['latest']), ('langfuse', dialogue['langfuse'])]
        context = explicit_context(sources)
        context['application_activity'] = application_activity(dialogue['langfuse'])
        context['observed_io_opportunity_shape_counts'] = opportunity_counts([{'content':
            [c['arguments'] for c in context['tool_evidence']['calls']] +
            [r['result'] for r in context['tool_evidence']['results']]}])
        dialogue['source_context'] = context
    store.encrypt('full-dialogues.aesgcm', {'dialogues': dialogues, 'source_collection_counts': payload['source_collection_counts'],
        'projects': projects, 'graph_config_resources_exported': False, 'data_only': True, 'pii_gold_labels': False})
    if ec:
        store.encrypt('http-provenance.aesgcm', {'responses': ec.client.response_receipts, 'pages': ec.pages,
            'trace_detail_requests': ec.trace_requests, 'observation_requests': ec.observation_requests,
            'credentials_source_keys': ['env.LANGFUSE_HOST', 'env.LANGFUSE_PUBLIC_KEY', 'env.LANGFUSE_SECRET_KEY']})
    if prior_http is not None:
        store.encrypt('http-provenance.aesgcm', prior_http)
    summaries = [public_summary(d) for d in dialogues]
    manifest = store.finish({'kind': 'mongo_full_dialogues_application_langfuse_join',
        'source_run_id': source_run, 'source_manifest_sha256': hashed(source_manifest),
        'decoded_lineage': decoded_lineage, 'application_join_lineage': joined_lineage,
        'threads': summaries, 'exported_threads': len(dialogues),
        'complete_authoritative_root_exports': sum(s['mongo_authoritative_root_export_complete'] for s in summaries),
        'complete_mongo_transcripts': sum(s['mongo_visible_transcript_complete'] for s in summaries),
        'complete_langfuse_sessions': sum(s['langfuse_complete'] for s in summaries),
        'langfuse_project_identity_sha256': hashed(projects),
        'requests': ec.client.requests if ec else 0, 'retries': ec.client.retries if ec else 0,
        'trace_detail_requests': ec.trace_requests if ec else 0, 'observation_requests': ec.observation_requests if ec else 0,
        'all_original_mongo_ejson_preserved': True, 'credentials_archived': False,
        'data_only': True, 'is_causal_replay': False, 'pii_gold_labels': False,
        'graph_config_resources_exported': False, 'provider_calls': 0, 'remote_mutations': 0})
    store.verify()
    return {key: manifest[key] for key in ('run_id', 'source_manifest_sha256', 'threads', 'exported_threads',
        'complete_authoritative_root_exports', 'complete_mongo_transcripts', 'complete_langfuse_sessions', 'requests', 'trace_detail_requests',
        'observation_requests', 'provider_calls', 'remote_mutations')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--source-run', default=SOURCE)
    parser.add_argument('--decoded-run')
    parser.add_argument('--joined-run', help='Re-derive from an authenticated existing join, with zero new GETs')
    parser.add_argument('--offline-only', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(collect(args.run_id, args.source_run, args.decoded_run, not args.offline_only, args.joined_run)))
    except Exception:
        # Exception text may include payload bytes, Docker stderr or credentials.
        print(json.dumps({'ok': False, 'error_code': 'dialogues_export_unavailable'}), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == '__main__':
    main()
