#!/usr/bin/env python3
"""Bridge: Suricata IDS alerts → Elasticsearch"""

import os, sys, json, time
from bridge_common import es_request, es_bulk_index, ensure_index_template, ES_URL

EVE_PATH = '/suricata-logs/eve.json'
STATE_FILE = '/state/suricata-bridge.json'

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'file_length': 0, 'line_count': 0}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

SURICATA_MAPPINGS = {
    '@timestamp': {'type': 'date'},
    'event.source': {'type': 'keyword'},
    'event_type': {'type': 'keyword'},
    'src_ip': {'type': 'ip'},
    'dest_ip': {'type': 'ip'},
    'src_port': {'type': 'long'},
    'dest_port': {'type': 'long'},
    'proto': {'type': 'keyword'},
    'alert': {
        'properties': {
            'action': {'type': 'keyword'},
            'category': {'type': 'keyword'},
            'signature': {'type': 'text'},
            'signature_id': {'type': 'integer'},
            'severity': {'type': 'integer'}
        }
    },
    'message': {'type': 'text'}
}

def get_new_alerts(state):
    if not os.path.exists(EVE_PATH):
        print(f'EVE file not found: {EVE_PATH}', file=sys.stderr)
        return [], state

    file_size = os.path.getsize(EVE_PATH)
    if file_size <= state['file_length']:
        return [], state

    docs = []
    line_idx = 0
    with open(EVE_PATH, 'r') as f:
        # Skip previously read lines
        for _ in range(state['line_count']):
            f.readline()
            line_idx += 1

        for line in f:
            line_idx += 1
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('event_type') != 'alert':
                continue
            event['@timestamp'] = event.get('timestamp', '')
            event['event.source'] = 'suricata'
            event['message'] = event.get('alert', {}).get('signature', '')
            docs.append(event)

    new_state = {'file_length': file_size, 'line_count': line_idx}
    return docs, new_state

def index_alerts(docs):
    if not docs:
        return 0
    lines = []
    for doc in docs:
        ts = doc.get('@timestamp', '')
        date = ts[:10].replace('-', '.') if ts else time.strftime('%Y.%m.%d')
        lines.append(json.dumps({'index': {'_index': f'suricata-alerts-{date}'}}))
        lines.append(json.dumps(doc, default=str))
    body = '\n'.join(lines) + '\n'
    es_bulk_index(lines)
    return len(docs)

def main():
    state = load_state()
    ensure_index_template('suricata-alerts', SURICATA_MAPPINGS)
    docs, new_state = get_new_alerts(state)
    indexed = index_alerts(docs)
    save_state(new_state)
    print(f'Indexed {indexed} Suricata alerts (scanned {new_state["line_count"]} lines)')

if __name__ == '__main__':
    main()
