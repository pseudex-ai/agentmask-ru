"""Complete pending long application sessions without re-exporting Mongo/finished joins."""

import argparse
import json
import sys

from .mongo_dialogues import (EvidenceClient, application_client, application_activity, explicit_context,
    join_session, list_session, message_role, opportunity_counts, public_summary)
from .storage import PilotError, RunStore, hashed


def collect(run_id: str, source_run: str):
    source = RunStore(source_run, False)
    parent = source.verify()
    payload = source.read_encrypted('full-dialogues.aesgcm')
    store = RunStore(run_id, True)
    client = EvidenceClient(application_client(), store, 260, 300)
    for dialogue in payload['dialogues']:
        if dialogue['langfuse'].get('complete'):
            continue
        rows, proof = list_session(client, dialogue['thread'])
        if len(rows) > client.trace_cap - client.trace_requests or len(rows) > client.observation_cap - client.observation_requests:
            dialogue['langfuse']['reason'] = 'remaining_bounded_read_budget_insufficient'
            continue
        dialogue['langfuse'] = join_session(client, dialogue, rows, proof)
        sources = [('mongo_root_messages', [{**message, 'role': message_role(message)} for message in dialogue['messages']]),
                   ('mongo_latest_checkpoint', dialogue['checkpoint_proof']['latest']), ('langfuse', dialogue['langfuse'])]
        context = explicit_context(sources)
        context['application_activity'] = application_activity(dialogue['langfuse'])
        context['observed_io_opportunity_shape_counts'] = opportunity_counts([{'content':
            [call['arguments'] for call in context['tool_evidence']['calls']] +
            [result['result'] for result in context['tool_evidence']['results']]}])
        dialogue['source_context'] = context
    store.encrypt('full-dialogues.aesgcm', payload)
    store.encrypt('http-provenance.aesgcm', {'responses': client.client.response_receipts, 'pages': client.pages,
        'trace_detail_requests': client.trace_requests, 'observation_requests': client.observation_requests})
    summaries = [public_summary(dialogue) for dialogue in payload['dialogues']]
    result = store.finish({'kind': 'extended_mongo_dialogues_application_join', 'source_run': source_run,
        'source_manifest_sha256': hashed(parent), 'threads': summaries,
        'complete_langfuse_sessions': sum(item['langfuse_complete'] for item in summaries),
        'requests': client.client.requests, 'trace_detail_requests': client.trace_requests,
        'observation_requests': client.observation_requests, 'remote_mutations': 0, 'provider_calls': 0,
        'root_transcripts_unmodified': True, 'prior_complete_joins_reused': True, 'pii_gold_labels': False})
    store.verify()
    return {key: result[key] for key in ('run_id', 'complete_langfuse_sessions', 'requests', 'trace_detail_requests',
                                       'observation_requests', 'provider_calls', 'remote_mutations')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--source', default='mongo-dialogues-application-normalized-v2')
    args = parser.parse_args()
    try:
        print(json.dumps(collect(args.run_id, args.source)))
    except Exception as error:
        code = str(error) if isinstance(error, PilotError) and str(error).replace('_', '').isalnum() else 'long_dialogue_join_unavailable'
        print(json.dumps({'ok': False, 'error_code': code}), file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__': main()
