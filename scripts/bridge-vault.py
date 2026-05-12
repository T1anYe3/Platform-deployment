#!/usr/bin/env python3
"""Bridge: Vault audit log → Elasticsearch"""

import os, sys, json, time
import urllib.request

ES_URL = os.environ.get('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
AUDIT_LOG = '/vault/data/audit.log'
STATE_FILE = '/state/vault-bridge.json'

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'last_position': 0}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def ensure_index_template():
    template = {
        'index_patterns': ['vault-audit-*'],
        'template': {
            'settings': {'number_of_shards': 1, 'number_of_replicas': 0},
            'mappings': {
                'properties': {
                    '@timestamp': {'type': 'date'},
                    'event.source': {'type': 'keyword'},
                    'type': {'type': 'keyword'},
                    'auth': {
                        'properties': {
                            'display_name': {'type': 'keyword'},
                            'policies': {'type': 'keyword'},
                            'token_type': {'type': 'keyword'}
                        }
                    },
                    'request': {
                        'properties': {
                            'id': {'type': 'keyword'},
                            'operation': {'type': 'keyword'},
                            'path': {'type': 'keyword'},
                            'remote_address': {'type': 'keyword'}
                        }
                    },
                    'error': {'type': 'keyword'},
                    'message': {'type': 'text'}
                }
            }
        }
    }
    req = urllib.request.Request(
        f'{ES_URL}/_index_template/vault-audit-template',
        data=json.dumps(template).encode(),
        headers={'Content-Type': 'application/json'},
        method='PUT'
    )
    urllib.request.urlopen(req, timeout=10)

def get_new_entries(state):
    if not os.path.exists(AUDIT_LOG):
        return [], state

    file_size = os.path.getsize(AUDIT_LOG)
    if file_size <= state['last_position']:
        return [], state

    docs = []
    with open(AUDIT_LOG, 'r') as f:
        if state['last_position'] > 0:
            f.seek(state['last_position'])

        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            doc = {
                '@timestamp': entry.get('time', ''),
                'event.source': 'vault',
                'type': str(entry.get('type', '')),
                'message': ''
            }
            if 'request' in entry:
                doc['request'] = {
                    'id': str(entry['request'].get('id', '')),
                    'operation': str(entry['request'].get('operation', '')),
                    'path': str(entry['request'].get('path', '')),
                }
                ra = str(entry['request'].get('remote_address', ''))
                if ra and ra != 'None':
                    doc['request']['remote_address'] = ra
                doc['message'] = f"{entry['type']} {entry['request'].get('operation','')} {entry['request'].get('path','')}"
            if 'auth' in entry:
                doc['auth'] = {
                    'display_name': str(entry['auth'].get('display_name', '')),
                    'policies': ','.join(entry['auth'].get('policies', [])),
                    'token_type': str(entry['auth'].get('token_type', ''))
                }
            if 'error' in entry:
                doc['error'] = str(entry['error'])
            docs.append(doc)

    return docs, {'last_position': os.path.getsize(AUDIT_LOG)}

def index_entries(docs):
    if not docs:
        return 0
    lines = []
    for i, doc in enumerate(docs):
        ts = doc.get('@timestamp', '')
        date = ts[:10].replace('-', '.') if ts else time.strftime('%Y.%m.%d')
        lines.append(json.dumps({'index': {'_index': f'vault-audit-{date}', '_id': f'v-{i}'}}))
        lines.append(json.dumps(doc, default=str))
    body = '\n'.join(lines) + '\n'
    req = urllib.request.Request(
        f'{ES_URL}/_bulk',
        data=body.encode(),
        headers={'Content-Type': 'application/x-ndjson'}
    )
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read())
    if result.get('errors'):
        print('Bulk errors', file=sys.stderr)
    return len(docs)

def main():
    state = load_state()
    ensure_index_template()
    docs, new_state = get_new_entries(state)
    indexed = index_entries(docs)
    save_state(new_state)
    print(f'Indexed {indexed} Vault audit entries')

if __name__ == '__main__':
    main()
