#!/usr/bin/env python3
"""Bridge: MinIO server & bucket status → Elasticsearch"""

import os, sys, json, time, subprocess
from bridge_common import es_request, es_bulk_index, ensure_index_template, ES_URL

MINIO_URL = os.environ.get('MINIO_URL', 'https://minio:9000')
MINIO_USER = os.environ.get('MINIO_ROOT_USER', 'minioadmin')
MINIO_PASS = os.environ.get('MINIO_ROOT_PASSWORD', 'ChangeThis-Local-123!')
STATE_FILE = '/state/minio-bridge.json'
MC_ALIAS = 'platform1'

BUCKETS = ['raw-data', 'processed-data', 'model-files', 'evaluation-results', 'archive-data', 'audit-evidence']

MINIO_MAPPINGS = {
    '@timestamp': {'type': 'date'},
    'event.source': {'type': 'keyword'},
    'event.action': {'type': 'keyword'},
    'minio': {
        'properties': {
            'bucket': {'type': 'keyword'},
            'objects': {'type': 'long'},
            'size_bytes': {'type': 'long'},
            'status': {'type': 'keyword'},
            'uptime_seconds': {'type': 'long'}
        }
    },
    'message': {'type': 'text'}
}

def mc(*args):
    """Run MinIO client command."""
    result = subprocess.run(
        ['mc'] + list(args),
        capture_output=True, text=True,
        env={**os.environ, 'MC_ALIAS': MC_ALIAS}
    )
    return result.stdout

def get_minio_events():
    events = []
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    # Configure mc alias
    mc('alias', 'set', MC_ALIAS, MINIO_URL, MINIO_USER, MINIO_PASS, '--insecure')

    # Server info
    info = mc('admin', 'info', MC_ALIAS)
    events.append({
        '@timestamp': now,
        'event.source': 'minio',
        'event.action': 'server-status',
        'minio': {'status': 'online'},
        'message': 'MinIO server heartbeat'
    })

    # Bucket stats
    for bucket in BUCKETS:
        ls_out = mc('ls', f'{MC_ALIAS}/{bucket}')
        obj_count = len([l for l in ls_out.split('\n') if l.strip() and not l.startswith('[')])
        events.append({
            '@timestamp': now,
            'event.source': 'minio',
            'event.action': 'bucket-scan',
            'minio': {'bucket': bucket, 'objects': obj_count},
            'message': f'Bucket {bucket}: {obj_count} objects'
        })

    return events

def index_events(events):
    if not events:
        return 0
    lines = []
    for doc in events:
        date = time.strftime('%Y.%m.%d')
        uid = f"minio-{doc['event.action']}-{date}-{hash(json.dumps(doc, sort_keys=True)) & 0x7FFFFFFF:08x}"
        lines.append(json.dumps({'index': {'_index': f'minio-audit-{date}', '_id': uid}}))
        lines.append(json.dumps(doc))
    es_bulk_index(lines)
    return len(events)

def main():
    ensure_index_template('minio-audit', MINIO_MAPPINGS)
    events = get_minio_events()
    indexed = index_events(events)
    print(f'Indexed {indexed} MinIO events')

if __name__ == '__main__':
    main()
