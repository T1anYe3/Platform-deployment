#!/usr/bin/env python3
"""Ingest SafeLine WAF attack records into Elasticsearch.

Connects to SafeLine WAF at localhost:9443.
Writes to ES index safeline-records-YYYY.MM.DD.
"""
import os, sys, json, time, urllib.request, ssl
from datetime import datetime, timezone

ES_URL = os.environ.get('ES_URL', 'http://localhost:19200')
INDEX_PREFIX = 'safeline-records'
SAFELINE_URL = os.environ.get('SAFELINE_URL', 'https://localhost:9443')
SAFELINE_USER = os.environ.get('SAFELINE_ADMIN_USER', 'admin')
SAFELINE_PASS = os.environ.get('SAFELINE_ADMIN_PASS', 'admin')
MAX_RETRIES = 3

def es_bulk_index(lines):
    if not lines:
        return 0
    body = '\n'.join(lines) + '\n'
    url = f'{ES_URL}/_bulk'
    req = urllib.request.Request(url, data=body.encode(), method='POST')
    req.add_header('Content-Type', 'application/x-ndjson')
    for attempt in range(MAX_RETRIES):
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read())
            return result.get('items', [])
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                print(f'  Bulk request failed: {e}', file=sys.stderr)
                return []
            time.sleep(2 ** attempt)

def safeline_request(path):
    """Make a request to SafeLine API."""
    import base64

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = f'{SAFELINE_URL}{path}'
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/json')
    req.add_header('Content-Type', 'application/json')

    credentials = base64.b64encode(f'{SAFELINE_USER}:{SAFELINE_PASS}'.encode()).decode()
    req.add_header('Authorization', f'Basic {credentials}')

    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        if resp.status == 200:
            return json.loads(resp.read())
    except Exception as e:
        pass
    return {}

def main():
    today = datetime.now(timezone.utc).strftime('%Y.%m.%d')
    index_name = f'{INDEX_PREFIX}-{today}'

    print(f'[ingest-safeline] Indexing to: {index_name}')
    print(f'[ingest-safeline] SafeLine address: {SAFELINE_URL}')

    records = []

    # 1. SafeLine health check
    health = safeline_request('/api/open/health')
    if health:
        records.append({
            '@timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'event': {
                'source': 'safeline',
                'action': 'health-check',
                'dataset': 'safeline-records'
            },
            'event_id': f'sl-health-{int(time.time())}',
            'attack_type': 'health-check',
            'src_ip': '127.0.0.1',
            'url_path': '/api/open/health',
            'action': 'allow',
            'reason': 'internal-health-probe'
        })

    # 2. SafeLine event logs (attack records)
    events = safeline_request('/api/open/events?page=1&page_size=50')
    if events:
        event_list = events.get('items', events.get('data', events.get('results', [])))
        if isinstance(event_list, list):
            for evt in event_list:
                records.append({
                    '@timestamp': evt.get('timestamp',
                        evt.get('created_at',
                        datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z')),
                    'event': {
                        'source': 'safeline',
                        'action': evt.get('action', 'detect'),
                        'dataset': 'safeline-records'
                    },
                    'event_id': str(evt.get('id', '')),
                    'attack_type': str(evt.get('attack_type', '')),
                    'src_ip': str(evt.get('src_ip', evt.get('remote_addr', ''))),
                    'url_path': str(evt.get('url', evt.get('path', ''))),
                    'action': str(evt.get('action', '')),
                    'reason': str(evt.get('reason', evt.get('msg', '')))
                })
        else:
            # If the response format is different, log what we see
            records.append({
                '@timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
                'event': {
                    'source': 'safeline',
                    'action': 'api-ping',
                    'dataset': 'safeline-records'
                },
                'event_id': f'sl-ping-{int(time.time())}',
                'attack_type': 'api-status-check',
                'src_ip': '127.0.0.1',
                'url_path': '/api/open/events',
                'action': 'log',
                'reason': f'Response type: {type(event_list).__name__}, keys: {list(event_list.keys()) if isinstance(event_list, dict) else "N/A"}'
            })
            print(f'[ingest-safeline] Response format: {type(event_list).__name__}')
            if isinstance(event_list, dict):
                print(f'  Keys: {list(event_list.keys())[:10]}')

    # 3. SafeLine statistics
    stats = safeline_request('/api/open/statistics')
    if stats:
        records.append({
            '@timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'event': {
                'source': 'safeline',
                'action': 'statistics',
                'dataset': 'safeline-records'
            },
            'event_id': f'sl-stats-{int(time.time())}',
            'attack_type': 'statistics',
            'src_ip': '127.0.0.1',
            'url_path': '/api/open/statistics',
            'action': 'collect',
            'reason': json.dumps(stats, default=str)[:200]
        })

    if not records:
        print('[ingest-safeline] No records collected (SafeLine may not be running).')
        return

    # Build bulk body
    lines = []
    for doc in records:
        lines.append(json.dumps({'index': {'_index': index_name}}))
        lines.append(json.dumps(doc))

    result = es_bulk_index(lines)
    print(f'[ingest-safeline] Indexed {len(records)} records to {index_name}')

if __name__ == '__main__':
    main()
