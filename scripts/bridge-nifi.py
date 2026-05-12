#!/usr/bin/env python3
"""Bridge: NiFi system diagnostics → Elasticsearch"""

import os, sys, json, time, subprocess
import urllib.request

ES_URL = os.environ.get('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
NIFI_URL = os.environ.get('NIFI_URL', 'https://nifi:8443')
NIFI_USER = os.environ.get('NIFI_ADMIN_USER', 'admin')
NIFI_PASS = os.environ.get('NIFI_ADMIN_PASS', 'Admin123!ChangeMe')
STATE_FILE = '/state/nifi-bridge.json'

def ensure_index_template():
    template = {
        'index_patterns': ['nifi-logs-*'],
        'template': {
            'settings': {'number_of_shards': 1, 'number_of_replicas': 0},
            'mappings': {
                'properties': {
                    '@timestamp': {'type': 'date'},
                    'event.source': {'type': 'keyword'},
                    'event.action': {'type': 'keyword'},
                    'nifi': {
                        'properties': {
                            'active_threads': {'type': 'integer'},
                            'queued_count': {'type': 'long'},
                            'processors_running': {'type': 'integer'},
                            'processors_stopped': {'type': 'integer'},
                            'free_memory_mb': {'type': 'long'},
                            'total_memory_mb': {'type': 'long'},
                            'cluster_nodes': {'type': 'integer'}
                        }
                    },
                    'message': {'type': 'text'}
                }
            }
        }
    }
    req = urllib.request.Request(
        f'{ES_URL}/_index_template/nifi-logs-template',
        data=json.dumps(template).encode(),
        headers={'Content-Type': 'application/json'},
        method='PUT'
    )
    urllib.request.urlopen(req, timeout=10)

def get_nifi_token():
    """Get NiFi JWT access token."""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    data = f'username={NIFI_USER}&password={NIFI_PASS}'.encode()
    req = urllib.request.Request(
        f'{NIFI_URL}/nifi-api/access/token',
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST'
    )
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    return resp.read().decode().strip()

def nifi_api(path, token):
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        f'{NIFI_URL}/nifi-api/{path}',
        headers={'Authorization': f'Bearer {token}'}
    )
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    return json.loads(resp.read())

def get_nifi_events():
    events = []
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    try:
        token = get_nifi_token()
    except Exception as e:
        print(f'NiFi auth failed: {e}', file=sys.stderr)
        return []

    # System diagnostics
    try:
        diag = nifi_api('system-diagnostics', token)
        snap = diag.get('systemDiagnostics', {}).get('aggregateSnapshot', {})
        events.append({
            '@timestamp': now,
            'event.source': 'nifi',
            'event.action': 'system-diagnostics',
            'nifi': {
                'active_threads': int(snap.get('activeThreadCount', 0)),
                'queued_count': int(snap.get('flowFileCount', 0)),
                'free_memory_mb': int(float(snap.get('freeHeapBytes', 0)) / (1024*1024)),
                'total_memory_mb': int(float(snap.get('totalHeapBytes', 0)) / (1024*1024)),
            },
            'message': f"NiFi: {snap.get('activeThreadCount', 0)} threads, {snap.get('flowFileCount', 0)} queued"
        })
    except Exception as e:
        print(f'System diag failed: {e}', file=sys.stderr)

    # Flow status
    try:
        flow = nifi_api('flow/process-groups/root', token)
        processors = flow.get('processGroupFlow', {}).get('flow', {}).get('processors', [])
        running = sum(1 for p in processors if p.get('status', {}).get('runStatus') == 'Running')
        stopped = len(processors) - running
        events.append({
            '@timestamp': now,
            'event.source': 'nifi',
            'event.action': 'flow-status',
            'nifi': {
                'processors_running': running,
                'processors_stopped': stopped,
                'cluster_nodes': 1
            },
            'message': f'NiFi flow: {running} running, {stopped} stopped'
        })
    except Exception as e:
        print(f'Flow status failed: {e}', file=sys.stderr)

    return events

def index_events(events):
    if not events:
        return 0
    lines = []
    for doc in events:
        date = time.strftime('%Y.%m.%d')
        uid = f"nifi-{doc['event.action']}-{date}-{hash(json.dumps(doc, sort_keys=True)) & 0x7FFFFFFF:08x}"
        lines.append(json.dumps({'index': {'_index': f'nifi-logs-{date}', '_id': uid}}))
        lines.append(json.dumps(doc))
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
    return len(events)

def main():
    ensure_index_template()
    events = get_nifi_events()
    indexed = index_events(events)
    print(f'Indexed {indexed} NiFi events')

if __name__ == '__main__':
    main()
