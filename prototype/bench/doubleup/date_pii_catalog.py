"""September+ real-dialogue PII catalog: opaque counts, encrypted originals only.

The Mongo thread universe comes from an authenticated RunStore snapshot
(`original-user-candidate-inventory.aesgcm`) because it is the only Mongo read
that is available without any write to the source; the live Mongo credential is
used only through the read-only Docker reader and never printed. Langfuse tool
activity is the APPLICATION project (`values-prod.yaml` LANGFUSE_*), GET only.

Output is counts, hashes and tool NAMES. Names, phones, e-mails, identifiers,
thread ids and session ids never reach stdout: they live only inside the
AES-256-GCM case artifacts under `.pilot-state/runs/<run-id>/`.
"""

import argparse
from collections import Counter
import datetime as dt
import json
import re
import sys

from .__main__ import observations
from .mongo_dialogues import application_client, normalized_events
from .storage import PilotError, RunStore, hashed

CUTOFF = '2026-09-01T00:00:00Z'
SNAPSHOT = 'real-sensitive-chat-inventory-v1'
EXISTING_PREFIX = 'real-sensitive-corpus-'

RESERVED = {'example.com', 'example.org', 'example.net', 'example.ru', 'localhost',
            'test.com', 'test.ru', 'test.local'}
EMAIL = re.compile(r"(?i)(?<![\w.+-])[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63}){1,8}(?![\w.-])")
PHONE = re.compile(r"(?<!\w)(?:[+][1-9](?:[ ()-]*[0-9]){6,14}|8(?:[ ()-]*[0-9]){10})(?![0-9])")
WORD = re.compile(r"[А-ЯЁа-яё][А-ЯЁа-яё-]*")
CAP = re.compile(r"[А-ЯЁ][а-яё-]+")
SNILS_SHAPE = re.compile(r"(?<!\d)(\d{3}[ -]?\d{3}[ -]?\d{3}[ -]?\d{2})(?!\d)")
INN12 = re.compile(r"(?<!\d)(\d{12})(?!\d)")
INN10 = re.compile(r"(?<!\d)(\d{10})(?!\d)")
PATRONYMIC = re.compile(r"(ович|евич|ьич|овна|евна|ична|инична)$", re.I)


class Matchers:
    """Dictionary/checksum matchers; no model call, no network."""

    def __init__(self, data_dir):
        self.first = {w.strip().lower() for w in (data_dir / 'first_names.txt').read_text(encoding='utf-8').splitlines() if w.strip()}
        self.surname = {w.strip().lower() for w in (data_dir / 'surnames.txt').read_text(encoding='utf-8').splitlines() if w.strip()}
        import phonenumbers
        self.phonenumbers = phonenumbers

    def snils_ok(self, text):
        d = re.sub(r'\D', '', text)
        if len(d) != 11:
            return False
        total = sum(int(d[i]) * (9 - i) for i in range(9))
        control = int(d[9:])
        check = total if total < 100 else 0 if total in (100, 101) else total % 101
        if check == 100:
            check = 0
        return check == control

    def inn_ok(self, text):
        d = re.sub(r'\D', '', text)
        if len(d) == 10:
            w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
            return sum(int(d[i]) * w[i] for i in range(9)) % 11 % 10 == int(d[9])
        if len(d) == 12:
            w11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
            w12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
            return (sum(int(d[i]) * w11[i] for i in range(10)) % 11 % 10 == int(d[10])
                    and sum(int(d[i]) * w12[i] for i in range(11)) % 11 % 10 == int(d[11]))
        return False

    def names(self, text):
        out = []
        tokens = [(m.start(), m.end(), m.group()) for m in WORD.finditer(text)]
        for i in range(len(tokens) - 1):
            for span in (2, 3):
                if i + span > len(tokens):
                    break
                group = tokens[i:i + span]
                if any(text[a[1]:b[0]].strip(' \t\n\r-') for a, b in zip(group, group[1:])):
                    continue
                if not all(CAP.fullmatch(g[2]) for g in group):
                    continue
                lows = [g[2].lower() for g in group]
                given = [j for j, w in enumerate(lows) if w in self.first]
                sur = [j for j, w in enumerate(lows) if w in self.surname and not PATRONYMIC.search(w)]
                if not given or not sur or given == sur:
                    continue
                patronymic = any(PATRONYMIC.search(w) for j, w in enumerate(lows)
                                 if j not in given and j not in sur)
                out.append({'start': group[0][0], 'end': group[-1][1], 'kind': 'name',
                            'tokens': span, 'patronymic': patronymic})
        return out

    def emails(self, text):
        out = []
        for m in EMAIL.finditer(text):
            address = m.group().strip('.')
            domain = address.rsplit('@', 1)[-1].casefold()
            if domain in RESERVED or domain.endswith(('.invalid', '.test', '.example', '.local')):
                continue
            out.append({'start': m.start(), 'end': m.start() + len(address), 'kind': 'email'})
        return out

    def phones(self, text):
        out = []
        for m in PHONE.finditer(text):
            try:
                number = self.phonenumbers.parse(m.group(), 'RU')
                if not self.phonenumbers.is_valid_number(number):
                    continue
            except self.phonenumbers.NumberParseException:
                continue
            out.append({'start': m.start(), 'end': m.end(), 'kind': 'phone'})
        return out

    def personal_structured(self, text):
        """12-digit INN (both checksums) and SNILS with a cue; a 10-digit INN is an
        ORGANISATION identifier, never counted as personal data."""
        out = []
        for m in SNILS_SHAPE.finditer(text):
            window = text[max(0, m.start() - 45):m.end() + 45].lower()
            if 'снилс' in window and self.snils_ok(m.group()):
                out.append({'start': m.start(), 'end': m.end(), 'kind': 'snils'})
        for m in INN12.finditer(text):
            if self.inn_ok(m.group()):
                out.append({'start': m.start(), 'end': m.end(), 'kind': 'inn'})
        return out

    def organisation_ids(self, text):
        out = []
        for m in INN10.finditer(text):
            window = text[max(0, m.start() - 30):m.end() + 30].lower()
            if 'инн' in window and self.inn_ok(m.group()):
                out.append({'start': m.start(), 'end': m.end(), 'kind': 'inn_org'})
        return out

    def all_personal(self, text):
        if not isinstance(text, str) or not text:
            return []
        found = self.phones(text) + self.emails(text) + self.names(text) + self.personal_structured(text)
        found.sort(key=lambda hit: (hit['start'], hit['end']))
        return found

    def canonical(self, text, hit):
        surface = text[hit['start']:hit['end']]
        if hit['kind'] == 'phone':
            try:
                return ('phone', self.phonenumbers.format_number(
                    self.phonenumbers.parse(surface, 'RU'), self.phonenumbers.PhoneNumberFormat.E164))
            except self.phonenumbers.NumberParseException:
                return ('phone', surface)
        if hit['kind'] == 'email':
            return ('email', surface.casefold())
        if hit['kind'] in ('inn', 'snils'):
            return (hit['kind'], ''.join(ch for ch in surface if ch.isdigit()))
        if hit['kind'] == 'name':
            return ('name', ' '.join(surface.lower().split()))
        return (hit['kind'], surface.lower())


def ms(value):
    if isinstance(value, dict):
        inner = value.get('$date', value)
        if isinstance(inner, dict):
            return int(inner['$numberLong'])
        return int(inner)
    if isinstance(value, dt.datetime):
        return int(value.timestamp() * 1000)
    if isinstance(value, (int, float)):
        return int(value)
    raise PilotError('snapshot_date_unsupported')


def message_text(message):
    content = message.get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, dict) and isinstance(content.get('text'), str):
        return content['text']
    if isinstance(content, list):
        return '\n'.join(part.get('text', '') for part in content
                         if isinstance(part, dict) and isinstance(part.get('text'), str))
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return ''


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def existing_joins(state):
    """Reuse only authenticated complete joins that were fetched read-only earlier."""
    import os
    joined = {}
    for name in sorted(os.listdir(state)):
        path = state / name / 'manifest.json'
        if not path.exists():
            continue
        manifest = json.loads(path.read_text())
        if manifest.get('kind') != 'complete_real_sensitive_dialogue':
            continue
        joined[manifest['source_thread_sha256']] = name
    return joined


def live_join(client, thread_id, budget):
    rows, proof = client.paginated('/api/public/traces', {
        'sessionId': thread_id, 'fields': 'core', 'orderBy': 'timestamp.asc'}, 8)
    if any(row.get('sessionId') != thread_id for row in rows):
        raise PilotError('session_filter_not_applied')
    events, trace_ids, detail_obs = [], [], []
    for row in rows:
        # The trace-detail endpoint is skipped deliberately: on this deployment it
        # takes 90-110 s for large traces and adds nothing the listing row and the
        # independent observation list do not already carry. Identity comes from
        # the session-filtered listing row.
        if row.get('sessionId') != thread_id:
            raise PilotError('trace_identity_mismatch')
        listed, obs_proof = observations(client, row['id'], 6)
        for observation in listed:
            if observation.get('traceId', observation.get('trace_id')) not in (None, row['id']):
                raise PilotError('observation_trace_filter_ignored')
        events.extend(normalized_events(row, listed))
        trace_ids.append(row['id'])
        detail_obs.append({'trace_id': row['id'], 'observations': len(listed),
                           'embedded_not_fetched': True, 'proof': obs_proof})
        budget[0] -= 1
        if budget[0] < 0:
            raise PilotError('request_budget_exhausted')
    after, after_proof = client.paginated('/api/public/traces', {
        'sessionId': thread_id, 'fields': 'core'}, 8)
    if {row['id'] for row in after} != set(trace_ids) or after_proof.get('server_total') != proof.get('server_total'):
        raise PilotError('session_drifted_during_join')
    return {'complete': True, 'traces': len(trace_ids), 'events': events,
            'trace_metadata': rows, 'observation_proofs': detail_obs,
            'session_listing': proof, 'session_recheck': after_proof,
            'identity_authority': 'langfuse_application_project_sessionId_only',
            'point_in_time_snapshot': False}


def analyse(thread, messages, events, matchers, cutoff_ms):
    user_types, user_keys, user_before = Counter(), set(), 0
    user_evidence = []
    for position, message in enumerate(messages):
        text = message_text(message)
        if ms(message.get('created_at')) < cutoff_ms:
            user_before += 1
        for hit in matchers.all_personal(text):
            key = matchers.canonical(text, hit)
            user_types[hit['kind']] += 1
            user_keys.add(key)
            user_evidence.append({'type': hit['kind'], 'canonical': key[1], 'pointer': position,
                                  'surface': text[hit['start']:hit['end']]})
    tool_input_types, tool_output_types = Counter(), Counter()
    tool_input_keys, tool_output_keys = set(), set()
    tools_with_pii, tools_with_user_pii = set(), set()
    spans = []
    for event in events:
        if event.get('type') != 'SPAN' or not str(event.get('name') or '').startswith('tool:'):
            continue
        name = event['name'][len('tool:'):]
        values = {'arguments': event.get('arguments', event.get('input')),
                  'result': event.get('result', event.get('output'))}
        for field, counter, keys in (('arguments', tool_input_types, tool_input_keys),
                                     ('result', tool_output_types, tool_output_keys)):
            field_hits = []
            for text in strings(values[field]):
                for hit in matchers.all_personal(text):
                    key = matchers.canonical(text, hit)
                    counter[hit['kind']] += 1
                    keys.add(key)
                    field_hits.append({'type': hit['kind'], 'canonical': key[1],
                                       'surface': text[hit['start']:hit['end']]})
            if field_hits:
                tools_with_pii.add(name)
                if any((hit['type'], hit['canonical']) in user_keys for hit in field_hits):
                    tools_with_user_pii.add(name)
                spans.append({'name': name, 'field': field, 'trace_id': event['trace_id'],
                              'observation_id': event['id'], 'hits': field_hits})
    return {'user_types': dict(user_types), 'user_canonical': sorted(user_keys),
            'user_evidence': user_evidence, 'user_turns_before_cutoff': user_before,
            'tool_input_types': dict(tool_input_types), 'tool_output_types': dict(tool_output_types),
            'tools_with_pii': sorted(tools_with_pii), 'tools_with_user_pii': sorted(tools_with_user_pii),
            'user_in_tool_arguments': len(user_keys & tool_input_keys),
            'user_in_tool_results': len(user_keys & tool_output_keys),
            'tool_spans': spans}


def collect(run_id, snapshot, cutoff, live, max_sessions, budget_limit):
    cutoff_dt = dt.datetime.fromisoformat(cutoff.replace('Z', '+00:00'))
    cutoff_ms = int(cutoff_dt.timestamp() * 1000)
    source = RunStore(snapshot, False)
    source_manifest = source.verify()
    raw = source.read_encrypted('original-user-candidate-inventory.aesgcm')
    store = RunStore(run_id, True)
    matchers = Matchers(__import__('pathlib').Path(__file__).resolve().parents[2] / 'licensing' / 'data')
    users = {}
    for message in raw['user_messages']:
        users.setdefault(message['thread_id'], []).append(message)
    threads = []
    for thread in raw['threads']:
        if not thread.get('thread_id'):
            continue
        created = ms(thread['created_at'])
        if created < cutoff_ms:
            continue
        messages = sorted(users.get(thread['thread_id'], []), key=lambda m: ms(m['created_at']))
        if len(messages) < 2:
            continue
        threads.append((thread, messages, created))
    joined = existing_joins(store.path.parent)
    client = application_client() if live else None
    if client is not None:
        client.attempts, client.timeout = 3, 25
    budget = [budget_limit]
    cases, failures = [], []
    for index, (thread, messages, created) in enumerate(threads):
        if max_sessions and len(cases) >= max_sessions:
            break
        sha = hashed(thread['thread_id'])
        if live and index % 5 == 0:
            print(json.dumps({'progress': index, 'of': len(threads), 'matched': len(cases),
                              'failures': len(failures), 'budget': budget[0]}), file=sys.stderr, flush=True)
        live_join_payload = None
        provenance = None
        if sha in joined:
            prior = RunStore(joined[sha], False)
            prior.verify()
            dialogue = prior.read_encrypted('complete-sensitive-dialogue.aesgcm')['dialogue']
            events = [{'type': 'SPAN', 'name': 'tool:' + span['name'],
                       'arguments': span['arguments'], 'result': span['result'],
                       'trace_id': span['trace_id'], 'id': span['observation_id']}
                      for span in dialogue['source_context']['application_activity']['source_tool_execution_spans']]
            provenance = 'authenticated_prior_join'
        elif live:
            try:
                live_join_payload = live_join(client, thread['thread_id'], budget)
            except Exception as error:
                failures.append({'catalog_index': index, 'thread_sha256': sha,
                                 'error_type': type(error).__name__,
                                 'error': str(error)[:80]})
                continue
            events = live_join_payload['events']
            provenance = 'live_langfuse_application_project'
        else:
            continue
        analysis = analyse(thread, messages, events, matchers, cutoff_ms)
        if not analysis['user_types']:
            continue
        record = {'thread': thread, 'source_thread_sha256': sha,
                  'created_ms': created, 'source_month': dt.datetime.fromtimestamp(
                      created / 1000, dt.timezone.utc).strftime('%Y-%m'),
                  'user_messages': messages, 'analysis': analysis,
                  'langfuse': live_join_payload, 'provenance': provenance,
                  'original_values_unchanged': True, 'manual_pii_labels': False,
                  'criterion': 'dictionary_name_valid_phone_non_reserved_email_checksum_identifier'}
        store.encrypt('case-' + str(index).zfill(3) + '.aesgcm', record)
        cases.append({'catalog_index': index, 'thread_sha256': sha,
                      'source_month': record['source_month'],
                      'user_turns': len(messages),
                      'user_turns_before_cutoff': analysis['user_turns_before_cutoff'],
                      'user_pii_types': analysis['user_types'],
                      'tool_pii_input_types': analysis['tool_input_types'],
                      'tool_pii_output_types': analysis['tool_output_types'],
                      'tools_with_pii': analysis['tools_with_pii'],
                      'user_pii_in_tool_arguments': analysis['user_in_tool_arguments'],
                      'user_pii_in_tool_results': analysis['user_in_tool_results'],
                      'provenance': provenance,
                      'pii_in_tools': bool(analysis['tools_with_pii'])})
        print(json.dumps({'case': len(cases), 'sha': sha[:16], 'month': record['source_month'],
                          'turns': len(messages), 'types': ','.join(sorted(analysis['user_types'])),
                          'tools': ','.join(analysis['tools_with_pii'])[:80],
                          'args': analysis['user_in_tool_arguments'],
                          'results': analysis['user_in_tool_results']}), flush=True)
    payload = {'cases': cases, 'failures': failures,
               'raw_values_encrypted': True}
    store.encrypt('catalog.aesgcm', payload)
    manifest = store.finish({
        'kind': 'september_plus_pii_dialogue_catalog',
        'cutoff_utc': cutoff, 'snapshot_run': snapshot,
        'snapshot_manifest_sha256': hashed(source_manifest),
        'snapshot_threads': len(raw['threads']),
        'snapshot_threads_created_on_or_after_cutoff': sum(
            1 for thread in raw['threads'] if thread.get('thread_id') and ms(thread['created_at']) >= cutoff_ms),
        'scanned_threads_two_plus_user_messages': len(threads),
        'matched_threads': len(cases),
        'pii_in_tools_threads': sum(1 for case in cases if case['pii_in_tools']),
        'user_pii_in_tool_arguments_threads': sum(1 for case in cases if case['user_pii_in_tool_arguments']),
        'user_pii_in_tool_results_threads': sum(1 for case in cases if case['user_pii_in_tool_results']),
        'by_month': dict(Counter(case['source_month'] for case in cases)),
        'by_user_type': dict(Counter(k for case in cases for k in case['user_pii_types'])),
        'by_provenance': dict(Counter(case['provenance'] for case in cases)),
        'live_join_failures': len(failures),
        'request_budget_remaining': budget[0],
        'date_semantics': 'thread.created_at BSON date from mongo threads; user message created_at retained separately',
        'tool_span_semantics': 'SPAN name prefixed tool: in independent Langfuse observations',
        'ten_digit_inn_is_organisation_identifier_not_counted_as_personal': True,
        'passport_has_no_checksum_so_not_counted_as_structured': True,
        'manual_pii_labels': False, 'provider_calls': 0, 'remote_mutations': 0,
        'raw_values_encrypted': True, 'source_credential_values_archived': False})
    store.verify()
    print(json.dumps({key: manifest[key] for key in (
        'run_id', 'snapshot_threads', 'snapshot_threads_created_on_or_after_cutoff',
        'scanned_threads_two_plus_user_messages', 'matched_threads', 'pii_in_tools_threads',
        'user_pii_in_tool_arguments_threads', 'user_pii_in_tool_results_threads',
        'by_month', 'by_user_type', 'by_provenance', 'live_join_failures',
        'request_budget_remaining', 'provider_calls', 'remote_mutations')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--snapshot', default=SNAPSHOT)
    parser.add_argument('--cutoff', default=CUTOFF)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--max-sessions', type=int, default=0)
    parser.add_argument('--request-budget', type=int, default=4000)
    args = parser.parse_args()
    try:
        collect(args.run_id, args.snapshot, args.cutoff, not args.offline,
                args.max_sessions, args.request_budget)
    except Exception as error:
        print(json.dumps({'ok': False, 'error_type': type(error).__name__,
                          'code': 'date_pii_catalog_unavailable'}), file=sys.stderr)
        raise SystemExit(2)
