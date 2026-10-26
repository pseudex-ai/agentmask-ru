"""Seed only synthetic, side-effect-free four-hop chat in the owned local DB."""

from datetime import datetime, timezone
import json
import os
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

GRAPH = str(uuid5(NAMESPACE_URL, 'obscura-doubleup-pilot/four-hop-graph'))
THREAD = str(uuid5(NAMESPACE_URL, 'obscura-doubleup-pilot/four-hop-thread'))
BASE_GRAPH = str(uuid5(NAMESPACE_URL, 'obscura-doubleup-pilot/graph'))


def main():
    from pymongo import MongoClient
    uri = os.environ.get('MONGO_URI', '')
    parsed = urlsplit(uri)
    if (os.getenv('PSEUDEX_PILOT') != '1' or parsed.hostname != 'mongodb'
            or parsed.path != '/doubleup_pilot' or os.getenv('MONGO_DB_NAME') != 'doubleup_pilot'):
        raise SystemExit('local_four_hop_seed_refused')
    with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
        db = client.get_database()
        base = db.graphs.find_one({'graph_id': BASE_GRAPH})
        if not base:
            raise SystemExit('base_pilot_must_be_seeded_first')
        graph = {key: value for key, value in base.items() if key != '_id'}
        now = datetime.now(timezone.utc)
        graph.update({'graph_id': GRAPH, 'name': 'Четыре хопа · синтетический стенд',
            'description': 'Без внешних действий и вызовов платной модели.',
            'tools': ['pseudex_pilot_contact'], 'default_tools': ['pseudex_pilot_contact'],
            'enabled_tools': ['pseudex_pilot_contact'], 'updated_at': now})
        db.graphs.update_one({'graph_id': GRAPH}, {'$set': graph}, upsert=True)
        db.threads.update_one({'thread_id': THREAD}, {'$setOnInsert': {'thread_id': THREAD,
            'graph_id': GRAPH, 'org_id': 'doubleup-pilot', 'user_id': 'pilot-owner',
            'title': 'Четыре перехода · синтетика', 'status': 'active', 'created_at': now,
            'updated_at': now, 'last_activity': now, 'message_count': 0}}, upsert=True)
    print(json.dumps({'graph_id': GRAPH, 'thread_id': THREAD, 'synthetic_only': True,
        'url': f'http://127.0.0.1:18880/doubleup-pilot/assistantnew/{GRAPH}?thread={THREAD}'}))


if __name__ == '__main__':
    main()
