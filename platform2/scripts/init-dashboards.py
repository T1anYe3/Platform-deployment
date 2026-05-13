#!/usr/bin/env python3
"""Create Kibana dashboards with actual visualization panels via REST API (Platform 2)."""
import os, json, urllib.request, sys

KIBANA_URL = os.environ.get('KIBANA_URL', 'http://kibana:5601')
HEADERS = {'Content-Type': 'application/json', 'kbn-xsrf': 'true'}

def api(method, path, body=None):
    url = f'{KIBANA_URL}{path}'
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read()) if resp.status < 300 else {}
    except Exception as e:
        print(f'  API error: {e}', file=sys.stderr)
        return {}

def create_visualization(title, vis_type, index_pattern, aggs, desc=''):
    """Create a visualization and return its saved object ID."""
    body = {
        'attributes': {
            'title': title,
            'visState': json.dumps({
                'title': title, 'type': vis_type,
                'aggs': aggs,
                'params': {
                    'type': vis_type,
                    'addTooltip': True,
                    'addLegend': True,
                    'legendPosition': 'right',
                    'isDonut': True if vis_type == 'pie' else False
                }
            }),
            'uiStateJSON': '{}',
            'description': desc,
            'version': 1,
            'kibanaSavedObjectMeta': {
                'searchSourceJSON': json.dumps({
                    'index': index_pattern,
                    'query': {'query': '', 'language': 'kuery'},
                    'filter': []
                })
            }
        },
        'type': 'visualization'
    }
    result = api('POST', '/api/saved_objects/visualization', body)
    vid = result.get('id', '')
    if vid:
        print(f'  [ok] Viz: {title} ({vid[:12]}...)')
    return vid

def create_dashboard(title, panels, desc=''):
    """Create a dashboard with given panels."""
    panel_objs = []
    for i, (viz_id, viz_title, w, h, x, y) in enumerate(panels):
        panel_objs.append({
            'version': '7.17.0',
            'type': 'visualization',
            'gridData': {'x': x, 'y': y, 'w': w, 'h': h, 'i': f'panel-{i}'},
            'panelIndex': str(i),
            'embeddableConfig': {'title': viz_title},
            'panelRefName': f'panel_{i}'
        })

    references = []
    for i, (viz_id, *_) in enumerate(panels):
        references.append({
            'name': f'panel_{i}',
            'type': 'visualization',
            'id': viz_id
        })

    body = {
        'attributes': {
            'title': title,
            'description': desc,
            'panelsJSON': json.dumps(panel_objs),
            'version': 1,
            'kibanaSavedObjectMeta': {'searchSourceJSON': '{"query":{"query":"","language":"kuery"},"filter":[]}'}
        },
        'references': references
    }
    result = api('POST', '/api/saved_objects/dashboard', body)
    did = result.get('id', '')
    if did:
        print(f'  [ok] Dashboard: {title} ({did})')
    return did

# ================================================================
# Dashboard 1: Data Lifecycle Overview
# ================================================================
print('[init-dashboards] Creating Data Lifecycle Overview visualizations...')

NAME_PREFIX = 'P2-'

# Viz 1: Total ES documents (metric)
v1 = create_visualization(
    f'{NAME_PREFIX}Total Documents', 'metric', 'platform2-minio-audit',
    [{'id': '1', 'type': 'count', 'schema': 'metric'}],
    'Total data lifecycle events indexed in Elasticsearch'
)

# Viz 2: Bucket object distribution (pie chart)
v2 = create_visualization(
    f'{NAME_PREFIX}Bucket Distribution', 'pie', 'platform2-minio-audit',
    [
        {'id': '1', 'type': 'count', 'schema': 'metric'},
        {'id': '2', 'type': 'terms', 'schema': 'segment', 'params': {'field': 'minio.bucket', 'size': 10}}
    ],
    'Objects per MinIO bucket'
)

# Viz 3: Data throughput over time (histogram)
v3 = create_visualization(
    f'{NAME_PREFIX}Ingestion Throughput', 'histogram', 'platform2-minio-audit',
    [
        {'id': '1', 'type': 'count', 'schema': 'metric'},
        {'id': '2', 'type': 'date_histogram', 'schema': 'segment',
         'params': {'field': '@timestamp', 'interval': 'auto'}}
    ],
    'Data lifecycle events over time'
)

# Viz 4: NiFi processors running (metric)
v4 = create_visualization(
    f'{NAME_PREFIX}NiFi Processors Running', 'metric', 'platform2-nifi-logs',
    [{'id': '1', 'type': 'max', 'schema': 'metric', 'params': {'field': 'nifi.processors_running'}}],
    'Number of running NiFi processors'
)

panels_overview = [
    (v1, 'Total Documents', 4, 3, 0, 0),
    (v4, 'NiFi Processors', 4, 3, 4, 0),
    (v2, 'Bucket Distribution', 4, 4, 8, 0),
    (v3, 'Throughput Timeline', 12, 5, 0, 3),
]

if all([v1, v2, v3, v4]):
    create_dashboard('platform2-data-lifecycle', panels_overview,
                     'Data Lifecycle Overview: pipeline health and throughput')

# ================================================================
# Dashboard 2: MinIO Bucket Status
# ================================================================
print('[init-dashboards] Creating MinIO Bucket Status visualizations...')

# Viz 5: Objects per bucket (bar chart / table)
v5 = create_visualization(
    f'{NAME_PREFIX}Objects Per Bucket', 'table', 'platform2-minio-audit',
    [
        {'id': '1', 'type': 'count', 'schema': 'metric'},
        {'id': '2', 'type': 'terms', 'schema': 'bucket', 'params': {'field': 'minio.bucket', 'size': 10, 'orderBy': '1', 'order': 'desc'}}
    ],
    'Object count by MinIO bucket'
)

# Viz 6: Bucket scan events over time (histogram)
v6 = create_visualization(
    f'{NAME_PREFIX}Bucket Scan Events', 'histogram', 'platform2-minio-audit',
    [
        {'id': '1', 'type': 'count', 'schema': 'metric'},
        {'id': '2', 'type': 'date_histogram', 'schema': 'segment',
         'params': {'field': '@timestamp', 'interval': 'auto'}}
    ],
    'Bucket scan events timeline'
)

# Viz 7: Server status (metric)
v7 = create_visualization(
    f'{NAME_PREFIX}MinIO Heartbeat Count', 'metric', 'platform2-minio-audit',
    [{'id': '1', 'type': 'count', 'schema': 'metric'}],
    'MinIO server heartbeat events'
)

panels_minio = [
    (v7, 'Server Heartbeats', 4, 3, 0, 0),
    (v5, 'Objects Per Bucket', 8, 4, 4, 0),
    (v6, 'Scan Events Timeline', 12, 5, 0, 3),
]

if v5 and v6 and v7:
    create_dashboard('platform2-minio-status', panels_minio,
                     'MinIO Bucket Status: object storage monitoring')

# ================================================================
# Dashboard 3: NiFi Flow Status
# ================================================================
print('[init-dashboards] Creating NiFi Flow Status visualizations...')

# Viz 8: Queued flow files (metric)
v8 = create_visualization(
    f'{NAME_PREFIX}Queued FlowFiles', 'metric', 'platform2-nifi-logs',
    [{'id': '1', 'type': 'max', 'schema': 'metric', 'params': {'field': 'nifi.queued_count'}}],
    'Total queued flow files in NiFi'
)

# Viz 9: Active threads (metric)
v9 = create_visualization(
    f'{NAME_PREFIX}Active Threads', 'metric', 'platform2-nifi-logs',
    [{'id': '1', 'type': 'max', 'schema': 'metric', 'params': {'field': 'nifi.active_threads'}}],
    'Active NiFi processing threads'
)

# Viz 10: NiFi memory usage over time (histogram)
v10 = create_visualization(
    f'{NAME_PREFIX}Memory Usage Timeline', 'histogram', 'platform2-nifi-logs',
    [
        {'id': '1', 'type': 'avg', 'schema': 'metric', 'params': {'field': 'nifi.free_memory_mb'}},
        {'id': '2', 'type': 'date_histogram', 'schema': 'segment',
         'params': {'field': '@timestamp', 'interval': 'auto'}}
    ],
    'NiFi free memory over time (MB)'
)

# Viz 11: Processor status (pie chart)
v11 = create_visualization(
    f'{NAME_PREFIX}Processor Status', 'pie', 'platform2-nifi-logs',
    [
        {'id': '1', 'type': 'max', 'schema': 'metric', 'params': {'field': 'nifi.processors_running'}},
        {'id': '2', 'type': 'max', 'schema': 'metric', 'params': {'field': 'nifi.processors_stopped'}}
    ],
    'Running vs stopped processors'
)

panels_nifi = [
    (v8, 'Queued FlowFiles', 4, 3, 0, 0),
    (v9, 'Active Threads', 4, 3, 4, 0),
    (v11, 'Processor Status', 4, 4, 8, 0),
    (v10, 'Memory Timeline', 12, 5, 0, 3),
]

if v8 and v9 and v10 and v11:
    create_dashboard('platform2-nifi-status', panels_nifi,
                     'NiFi Flow Status: data pipeline monitoring')

print('[init-dashboards] Dashboard creation complete.')
