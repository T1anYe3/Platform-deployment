#!/usr/bin/env python3
"""Ingest NiFi system diagnostics into Elasticsearch.

Connects to Platform 2's NiFi at localhost:8443.
Writes to ES index nifi-logs-YYYY.MM.DD.
"""
import os, sys, json, time, urllib.request, ssl
from datetime import datetime, timezone

ES_URL = os.environ.get('ES_URL', 'http://localhost:19200')
INDEX_PREFIX = 'nifi-logs'
NIFI_URL = os.environ.get('NIFI_URL', 'https://localhost:8443')
NIFI_USER = os.environ.get('NIFI_ADMIN_USER', 'admin')
NIFI_PASS = os.environ.get('NIFI_ADMIN_PASS', 'Admin123!ChangeMe')
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

def nifi_request(path, accept='application/json'):
    """Make an authenticated request to NiFi API."""
    import base64

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = f'{NIFI_URL}{path}'
    req = urllib.request.Request(url)
    req.add_header('Accept', accept)

    # Basic auth
    credentials = base64.b64encode(f'{NIFI_USER}:{NIFI_PASS}'.encode()).decode()
    req.add_header('Authorization', f'Basic {credentials}')

    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        if resp.status == 200:
            return json.loads(resp.read())
        else:
            print(f'  NiFi API returned status {resp.status}: {resp.read().decode()[:200]}', file=sys.stderr)
            return {}
    except Exception as e:
        return {}

def main():
    today = datetime.now(timezone.utc).strftime('%Y.%m.%d')
    index_name = f'{INDEX_PREFIX}-{today}'

    print(f'[ingest-nifi] Indexing to: {index_name}')
    print(f'[ingest-nifi] NiFi address: {NIFI_URL}')

    records = []

    # 1. NiFi system diagnostics
    sys_diag = nifi_request('/nifi-api/system-diagnostics')
    if sys_diag:
        diag = sys_diag.get('systemDiagnostics', {}).get('aggregateSnapshot', {})
        records.append({
            '@timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'event': {
                'source': 'nifi',
                'action': 'system-diagnostics',
                'dataset': 'nifi-logs'
            },
            'nifi': {
                'active_threads': diag.get('activeThreads', 0),
                'total_threads': diag.get('totalThreads', 0),
                'processors_running': diag.get('processorsRunning', 0),
                'processors_stopped': diag.get('processorsStopped', 0),
                'available_processors': diag.get('availableProcessors', 0),
                'free_memory': diag.get('freeMemory', ''),
                'total_memory': diag.get('totalMemory', ''),
                'uptime': diag.get('uptime', '')
            }
        })

    # 2. NiFi process group status
    pg_status = nifi_request('/nifi-api/flow/process-groups/root/status')
    if pg_status:
        proc_group = pg_status.get('processGroupStatus', {})
        records.append({
            '@timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'event': {
                'source': 'nifi',
                'action': 'process-group-status',
                'dataset': 'nifi-logs'
            },
            'nifi': {
                'flow_files_queued': proc_group.get('flowFilesQueued', 0),
                'flow_files_sent': proc_group.get('flowFilesSent', 0),
                'flow_files_received': proc_group.get('flowFilesReceived', 0),
                'bytes_queued': proc_group.get('bytesQueued', 0),
                'bytes_sent': proc_group.get('bytesSent', 0),
                'bytes_received': proc_group.get('bytesReceived', 0)
            }
        })

    # 3. NiFi cluster summary
    cluster = nifi_request('/nifi-api/controller/cluster')
    if cluster:
        cluster_info = cluster.get('cluster', {})
        nodes = cluster_info.get('nodes', [])
        records.append({
            '@timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'event': {
                'source': 'nifi',
                'action': 'cluster-status',
                'dataset': 'nifi-logs'
            },
            'nifi': {
                'cluster_nodes': len(nodes),
                'clustered': cluster_info.get('clustered', False),
                'connected_nodes': sum(1 for n in nodes if n.get('status') == 'CONNECTED')
            }
        })

    if not records:
        print('[ingest-nifi] No records collected (NiFi may not be running).')
        return

    # Build bulk body
    lines = []
    for doc in records:
        lines.append(json.dumps({'index': {'_index': index_name}}))
        lines.append(json.dumps(doc))

    result = es_bulk_index(lines)
    print(f'[ingest-nifi] Indexed {len(records)} records to {index_name}')

if __name__ == '__main__':
    main()
