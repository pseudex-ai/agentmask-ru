"""Synthetic, network-free tests. Run: python3 -m bench.doubleup.test_mongo_dialogues."""

import copy
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from . import mongo_dialogues as md
from .storage import PilotError, canonical, digest, hashed


def message(mid, kind, content='same text', **fields):
    return {'id': mid, 'type': kind, 'content': content, **fields}


def root(messages, parent=None, ns=''):
    return {'attrs': {'thread_id': 'thread-synthetic', 'checkpoint_ns': ns,
        'checkpoint_id': 'checkpoint-synthetic', 'parent_checkpoint_id': parent, 'ts': None},
        'checkpoint': {'channel_values': {'messages': messages}}, 'metadata': {},
        'message_classes': []}


def fixture():
    messages = [message('h1', 'human'), message('a1', 'ai'), message('h2', 'human'), message('a2', 'ai')]
    item = {'thread': {'thread_id': 'thread-synthetic', 'org_id': 'org-synthetic', 'user_id': 'user-synthetic'},
        'candidate': {}, 'root_checkpoint_count': {'$numberInt': '5'}, 'compactions': [],
        'messages': [{'message_id': 'mongo-new-' + str(i), 'sender': {'type': 'user'},
            'content': {'text': 'same text'}, 'created_at': None} for i in range(2)]}
    decoded = {'index': 0, 'latest': root(messages), 'earliest': root(messages[:1])}
    return item, decoded


class MemoryStore:
    def __init__(self):
        self.values = []

    def encrypt(self, name, value):
        self.values.append((name, copy.deepcopy(value)))


class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.response_receipts, self.calls = [], []
        self.pages = []
        self.requests, self.retries = 0, 0

    def get(self, path, params=None, record=True):
        self.requests += 1
        self.calls.append((path, params))
        value = next(self.replies)
        if isinstance(value, Exception):
            raise value
        self.response_receipts.append({'body_sha256': digest(canonical(value)), 'body_bytes': len(canonical(value))})
        return copy.deepcopy(value)

    def paginated(self, path, params, max_pages=4):
        return md.Client.paginated(self, path, params, max_pages)


def trace(tid='trace-synthetic', session='thread-synthetic', **fields):
    return {'id': tid, 'sessionId': session, 'timestamp': '2026-01-01T00:00:00Z', **fields}


def page(rows, total=None):
    return {'data': rows, 'meta': {'totalItems': len(rows) if total is None else total}}


class MongoDialogueTests(unittest.TestCase):
    def test_repeated_identical_user_text_is_two_turns_with_original_ids(self):
        item, decoded = fixture()
        out = md.normalize_mongo(item, decoded)
        self.assertTrue(out['source_completeness']['visible_transcript_complete'])
        self.assertEqual(out['user_message_ids'], ['h1', 'h2'])
        self.assertEqual(out['counts']['user'], 2)
        self.assertEqual(out['ordered_message_ids'], ['h1', 'a1', 'h2', 'a2'])
        self.assertTrue(out['checkpoint_proof']['all_mongo_users_retained_unchanged'])
        self.assertEqual(item, fixture()[0])
        self.assertEqual(decoded, fixture()[1])

    def test_source_mongo_ai_documents_not_unique_transcript(self):
        item, decoded = fixture()
        item['messages'] += [{'sender': {'type': 'assistant'}, 'content': {'text': 'same text'}}] * 99
        out = md.normalize_mongo(item, decoded)
        self.assertEqual(out['counts']['assistant'], 2)
        self.assertEqual(out['counts']['mongo_assistant_documents'], 99)

    def test_truncated_latest_flags_exact_user_and_earliest_gap(self):
        item, decoded = fixture()
        decoded['latest']['checkpoint']['channel_values']['messages'] = md.transcript(decoded['latest'])[2:]
        gaps = md.normalize_mongo(item, decoded)['source_completeness']['gaps']
        self.assertIn('user_content_sequence_gap', gaps)
        self.assertIn('earliest_root_not_unchanged_prefix', gaps)

    def test_changed_order_never_deduped_or_repaired(self):
        item, decoded = fixture()
        md.transcript(decoded['latest'])[0]['content'] = 'first'
        item['messages'][0]['content']['text'] = 'second'
        self.assertIn('user_content_sequence_gap', md.normalize_mongo(item, decoded)['source_completeness']['gaps'])

    def test_duplicate_or_missing_ids_are_not_rewritten(self):
        for value in ('h1', None):
            item, decoded = fixture()
            md.transcript(decoded['latest'])[2]['id'] = value
            out = md.normalize_mongo(item, decoded)
            self.assertIn('root_message_ids_missing_or_duplicated', out['source_completeness']['gaps'])
            self.assertEqual(out['ordered_message_ids'][2], value)

    def test_retained_earliest_parent_is_explicit_gap(self):
        item, decoded = fixture()
        decoded['earliest']['attrs']['parent_checkpoint_id'] = 'older-root'
        self.assertIn('earliest_retained_root_has_parent', md.normalize_mongo(item, decoded)['source_completeness']['gaps'])

    def test_compaction_and_fork_metadata_are_preserved(self):
        item, decoded = fixture()
        item['thread']['forked_from'] = 'synthetic-source'
        item['compactions'] = [{'compaction': True}]
        out = md.normalize_mongo(item, decoded)
        self.assertIn('source_compaction_records_present', out['source_completeness']['gaps'])
        self.assertTrue(any(m['value'] == 'synthetic-source' for m in out['checkpoint_proof']['markers']))

    def test_unsupported_root_messages_remain_gap(self):
        item, decoded = fixture()
        md.transcript(decoded['latest']).append(message('x', 'imaginary'))
        self.assertIn('unsupported_message_type', md.normalize_mongo(item, decoded)['source_completeness']['gaps'])

    def test_multimodal_original_preserved_and_source_text_projection(self):
        item, decoded = fixture()
        blocks = [{'type': 'text', 'text': 'same text'}, {'type': 'image_url', 'image_url': {'url': 'synthetic'}}]
        md.transcript(decoded['latest'])[0]['content'] = blocks
        md.transcript(decoded['earliest'])[0]['content'] = blocks
        out = md.normalize_mongo(item, decoded)
        self.assertTrue(out['checkpoint_proof']['all_mongo_users_retained_unchanged'])
        self.assertEqual(out['user_turns'][0]['content'], blocks)
        with self.assertRaises(PilotError):
            md.source_text_projection(object())

    def test_call_links_use_call_id_not_name_or_text(self):
        messages = [message('a', 'ai', tool_calls=[{'id': 'c1', 'name': 'search', 'args': {'email': 'a@example.test'}}]),
            message('t', 'tool', tool_call_id='c1'), message('t2', 'tool', tool_call_id='orphan')]
        out = md.ordered_tool_activity(messages)
        self.assertEqual(out['links'][0]['status'], 'linked')
        self.assertEqual(len(out['orphan_results']), 1)
        messages.append(message('t3', 'tool', tool_call_id='c1'))
        self.assertEqual(md.ordered_tool_activity(messages)['links'][0]['status'], 'ambiguous_results')

    def test_additional_kwargs_do_not_duplicate_canonical_tool_calls(self):
        call = {'id': 'c', 'name': 'search', 'args': {}}
        out = md.ordered_tool_activity([message('a', 'ai', tool_calls=[call], additional_kwargs={'tool_calls': [call]})])
        self.assertEqual(len(out['calls']), 1)

    def test_sensitive_shapes_are_counts_only_not_labels(self):
        out = md.opportunity_counts([message('h', 'human', 'a@example.test +7 999 123-45-67 паспорт 1234 567890')])
        self.assertEqual(out, {'email_shape': 1, 'ru_phone_shape': 1, 'cued_id_shape': 1})
        self.assertTrue(all(isinstance(value, int) for value in out.values()))

    def test_explicit_schemas_and_resources_not_invented_from_calls(self):
        sources = [('synthetic', {'tools': [{'type': 'function', 'function': {'name': 'search', 'parameters': {'type': 'object'}}}],
            'messages': [{'role': 'system', 'content': 'synthetic prompt'}, {'role': 'tool', 'tool_call_id': 'c', 'content': 'synthetic'}],
            'resources': [{'uri': 'synthetic-resource'}]})]
        context = md.explicit_context(sources)
        self.assertEqual(len(context['tool_evidence']['schemas']), 1)
        self.assertEqual(len(context['resource_evidence']), 1)
        self.assertFalse(context['causal_execution_supported'])
        self.assertEqual(md.explicit_context([('call', {'tool_calls': [{'id': 'c', 'name': 'search', 'args': {}}]})])['tool_evidence']['schemas'], [])

    def test_exact_session_required_and_user_id_never_org(self):
        thread = fixture()[0]['thread']
        md.require_session(trace(userId='not-the-org'), thread)
        with self.assertRaisesRegex(PilotError, 'session_filter_mismatch'):
            md.require_session(trace(session='wrong'), thread)
        with self.assertRaisesRegex(PilotError, 'org_conflict'):
            md.require_session(trace(metadata={'org_id': 'wrong'}), thread)
        self.assertTrue(md.require_session(trace(metadata={'org_id': thread['org_id']}), thread)['org_metadata_present'])

    def test_filtered_pagination_no_time_window(self):
        client = FakeClient([page([trace()])])
        rows, proof = md.list_session(client, fixture()[0]['thread'])
        self.assertEqual(proof['server_total'], 1)
        query = client.calls[0][1]
        self.assertEqual(query['sessionId'], 'thread-synthetic')
        self.assertNotIn('fromTimestamp', query)
        self.assertEqual(len(rows), 1)

    def test_pagination_drift_cap_duplicates_and_ignored_session_refused(self):
        cases = [([page([trace()], 2), page([trace('two')], 3)], 'total_changed'),
                 ([page([trace()], 2)] * 2, 'duplicate_id'),
                 ([page([trace(str(i))], 9) for i in range(4)], 'cap_incomplete'),
                 ([page([trace(session='wrong')])], 'session_filter_mismatch')]
        for replies, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(PilotError, code):
                md.list_session(FakeClient(replies), fixture()[0]['thread'])

    def test_encrypt_every_response_before_return_and_budget_before_network(self):
        raw = FakeClient([trace()])
        store = MemoryStore()
        client = md.EvidenceClient(raw, store, 1, 1)
        client.get('/api/public/traces/trace-synthetic')
        self.assertEqual(store.values[0][1]['response'], trace())
        self.assertEqual(store.values[0][1]['request_body_sha256'], digest(b''))
        with self.assertRaisesRegex(PilotError, 'budget_incomplete'):
            client.get('/api/public/traces/another')
        self.assertEqual(raw.requests, 1)

    def test_independent_observations_have_exact_trace_identity(self):
        obs = {'id': 'o', 'traceId': 'trace-synthetic', 'type': 'GENERATION', 'model': 'source-model', 'modelParameters': {'temperature': 0.3}}
        events = md.normalized_events(trace(), [obs])
        self.assertEqual(events[0]['original_observation'], obs)
        self.assertEqual(events[0]['model_parameters'], {'temperature': 0.3})
        with self.assertRaises(PilotError):
            md.normalized_events(trace(), [{'id': 'missing-trace'}])

    def test_complete_join_fetches_independent_lists_and_rechecks_membership(self):
        item, decoded = fixture()
        dialogue = md.normalize_mongo(item, decoded)
        source_trace = trace(observations=[{'id': 'o'}])
        observation = {'id': 'o', 'traceId': 'trace-synthetic', 'type': 'SPAN'}
        raw = FakeClient([source_trace, page([observation]), page([trace()])])
        client = md.EvidenceClient(raw, MemoryStore(), 60, 60)
        out = md.join_session(client, dialogue, [trace()], {'server_total': 1, 'complete': True})
        self.assertTrue(out['complete'])
        self.assertEqual(out['counts'], {'traces': 1, 'observations': 1})
        self.assertEqual(client.trace_requests, 1)
        self.assertEqual(client.observation_requests, 1)
        self.assertEqual(source_trace, out['trace_details'][0])

    def test_join_recheck_drift_is_not_complete(self):
        item, decoded = fixture()
        client = md.EvidenceClient(FakeClient([trace(), page([]), page([])]), MemoryStore(), 60, 60)
        with self.assertRaisesRegex(PilotError, 'drift_incomplete'):
            md.join_session(client, md.normalize_mongo(item, decoded), [trace()], {'server_total': 1})

    def test_offline_decoder_flags_no_network_mount_logs_or_pull(self):
        result = {'ok': True, 'decoded': [{'index': 0}]}
        process = subprocess.CompletedProcess([], 0, canonical(result), b'private stderr never printed')
        store = MemoryStore()
        with patch.object(md.subprocess, 'run', return_value=process) as run:
            md.decode_offline({'threads': [{}]}, store)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index('--network') + 1], 'none')
        self.assertEqual(command[command.index('--log-driver') + 1], 'none')
        self.assertEqual(command[command.index('--pull') + 1], 'never')
        self.assertNotIn('-v', command)
        self.assertEqual(store.values[0][1], result)

    def test_decoder_unknown_errors_constant_and_encrypted(self):
        process = subprocess.CompletedProcess([], 0, canonical({'ok': False, 'error_type': 'TypeError'}), b'private')
        store = MemoryStore()
        with patch.object(md.subprocess, 'run', return_value=process), self.assertRaisesRegex(PilotError, 'decode_unsupported'):
            md.decode_offline({'threads': []}, store)
        self.assertEqual(len(store.values), 1)

    def test_application_client_reads_only_named_in_memory_config_keys(self):
        config = {'env': {'LANGFUSE_HOST': md.HOST, 'LANGFUSE_PUBLIC_KEY': 'synthetic-public',
            'LANGFUSE_SECRET_KEY': 'synthetic-secret', 'MONGO_URI': 'synthetic-unused'}}
        with patch.object(Path, 'read_text', return_value=json.dumps(config)), patch.object(md, 'Client') as cls:
            md.application_client(Path('/synthetic'))
            cls.assert_called_once_with((md.HOST, 'synthetic-public', 'synthetic-secret'))
        config['env']['LANGFUSE_HOST'] = 'https://not-allowlisted.invalid'
        with patch.object(Path, 'read_text', return_value=json.dumps(config)), self.assertRaises(PilotError):
            md.application_client(Path('/synthetic'))

    def test_root_export_and_cross_source_user_equality_are_separate(self):
        item, decoded = fixture()
        md.transcript(decoded['latest'])[2]['content'] = 'source model context differs'
        out = md.normalize_mongo(item, decoded)
        self.assertTrue(out['source_completeness']['authoritative_root_export_complete'])
        self.assertFalse(out['source_completeness']['cross_source_user_projection_equal'])
        self.assertEqual(out['mongo_user_messages'], item['messages'])
        self.assertEqual(out['user_turns'][1]['content'], 'source model context differs')

    def test_tool_execution_span_prefix_uses_source_semantics_without_call_id(self):
        events = [{'id': 'o1', 'trace_id': 't', 'type': 'SPAN', 'name': 'tool:run_code',
            'input': {'code': 'synthetic'}, 'output': 'synthetic', 'output_present': True},
            {'id': 'o2', 'type': 'SPAN', 'name': 'unproven_tool_name'}]
        out = md.application_activity({'events': events})
        self.assertEqual(len(out['source_tool_execution_spans']), 1)
        self.assertIsNone(out['source_tool_execution_spans'][0]['call_id'])
        self.assertEqual(out['source_tool_execution_spans'][0]['name'], 'run_code')

    def test_actual_resource_references_extracted_without_fabricating_contents(self):
        sources = [('synthetic', {'tool_calls': [{'id': 'c', 'function': {'name': 'read_webpage',
            'arguments': {'url': 'synthetic-url'}}}]})]
        out = md.explicit_context(sources)
        refs = [r for r in out['resource_evidence'] if r['source'] == 'observed_tool_arguments']
        self.assertEqual(refs[0]['value'], 'synthetic-url')
        self.assertFalse(refs[0]['external_resource_contents_exported'])
        self.assertEqual(out['missing_schema_tool_names'], ['read_webpage'])

    def test_offline_join_rederivation_does_not_construct_network_client(self):
        item, decoded = fixture()
        source_manifest = {'synthetic': True}
        previous = md.normalize_mongo(item, decoded)
        previous['langfuse'] = {'complete': False, 'reason': 'budget_pending'}
        payload = {'format': 'mongo-extended-json-canonical-v2', 'threads': [item], 'source_collection_counts': {}}
        class Store(MemoryStore):
            def __init__(self, run_id, create):
                super().__init__()
                self.run_id = run_id
            def verify(self):
                if self.run_id == 'source':
                    return source_manifest
                return {'source_manifest_sha256': hashed(source_manifest)}
            def read_encrypted(self, name):
                if name == 'mongo-originals.aesgcm': return payload
                if name == 'decoded-checkpoints.aesgcm': return {'ok': True, 'decoded': [decoded]}
                if name == 'full-dialogues.aesgcm': return {'dialogues': [previous], 'projects': {'data': []}}
                if name == 'http-provenance.aesgcm': return {'responses': [], 'pages': []}
                raise AssertionError('unexpected artifact')
            def finish(self, manifest):
                return {**manifest, 'run_id': self.run_id}
        with patch.object(md, 'RunStore', Store), patch.object(md, 'application_client', side_effect=AssertionError('network forbidden')):
            out = md.collect('new', 'source', 'decoded', True, 'joined')
        self.assertEqual(out['requests'], 0)
        self.assertEqual(out['threads'][0]['langfuse_pending_reason'], 'budget_pending')
        self.assertEqual(out['complete_authoritative_root_exports'], 1)

    def test_public_summary_never_contains_source_values(self):
        item, decoded = fixture()
        out = md.public_summary(md.normalize_mongo(item, decoded))
        serialized = json.dumps(out)
        for value in ('same text', 'thread-synthetic', 'org-synthetic', 'user-synthetic', 'h1'):
            self.assertNotIn(value, serialized)
        self.assertEqual(out['root_ordered_ids_sha256'], hashed(['h1', 'a1', 'h2', 'a2']))


def main():
    # These tests must never reach a network even if a future fixture drifts.
    with patch('socket.create_connection', side_effect=AssertionError('network forbidden')):
        unittest.main()


if __name__ == '__main__':
    main()
