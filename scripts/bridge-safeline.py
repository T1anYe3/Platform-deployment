#!/usr/bin/env python3
"""Bridge: SafeLine WAF attack records → Elasticsearch"""

import os, sys, json, time
from bridge_common import es_request, es_bulk_index, ensure_index_template, ES_URL
import ssl

SAFELINE_URL = os.environ.get('SAFELINE_URL', 'https://safeline:9443')
SAFELINE_USER = os.environ.get('SAFELINE_ADMIN_USER', 'admin')
SAFELINE_PASS = os.environ.get('SAFELINE_ADMIN_PASS', 'w4WmJByY')
STATE_FILE = '/state/safeline-bridge.json'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'last_event_id': ''}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

SAFELINE_MAPPINGS = {
    '@timestamp': {'type': 'date'},
    'event.source': {'type': 'keyword'},
    'event_id': {'type': 'keyword'},
    'src_ip': {'type': 'ip'},
    'attack_type': {'type': 'keyword'},
    'action': {'type': 'keyword'},
    'risk_level': {'type': 'integer'},
    'module': {'type': 'keyword'},
    'message': {'type': 'text'}
}

def get_safeline_jwt():
    """Authenticate to SafeLine and get JWT token."""
    login_data = json.dumps({
        'username': SAFELINE_USER,
        'password': SAFELINE_PASS
    }).encode()
    req = urllib.request.Request(
        f'{SAFELINE_URL}/api/open/auth/login',
        data=login_data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    return json.loads(resp.read())['data']['jwt']

def fetch_records(jwt, last_event_id):
    """Fetch attack records from SafeLine API."""
    records = []
    for page in range(1, 6):
        url = f'{SAFELINE_URL}/api/open/records?page={page}&page_size=100'
        req = urllib.request.Request(url, headers={'Authorization': jwt})
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        data = json.loads(resp.read())
        page_records = data.get('data', {}).get('data', [])
        for rec in page_records:
            if rec.get('event_id') == last_event_id:
                return records
            records.append(rec)
        if len(page_records) == 0:
            break
    return records

def index_records(records):
    """Bulk index records to Elasticsearch."""
    if not records:
        return 0
    lines = []
    for rec in records:
        ts = rec.get('timestamp', int(time.time()))
        dt = time.strftime('%Y.%m.%d', time.gmtime(ts))
        doc = {
            '@timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(ts)),
            'event.source': 'safeline',
            **{k: v for k, v in rec.items() if k not in ('timestamp',)}
        }
        lines.append(json.dumps({'index': {
            '_index': f'safeline-records-{dt}',
            '_id': str(rec.get('event_id', ''))
        }}))
        lines.append(json.dumps(doc, default=str))
    body = '\n'.join(lines) + '\n'
    es_bulk_index(lines)
    return len(records)

def main():
    state = load_state()
    ensure_index_template('safeline-records', SAFELINE_MAPPINGS)
    try:
        jwt = get_safeline_jwt()
        records = fetch_records(jwt, state['last_event_id'])
        indexed = index_records(records)
        if records:
            state['last_event_id'] = records[0].get('event_id', state['last_event_id'])
            save_state(state)
        print(f'Indexed {indexed} SafeLine records')
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
