#!/usr/bin/env python3
"""Create Kibana dashboards with actual visualization panels via REST API."""
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
# Build Security Overview Dashboard
# ================================================================
print('[init-dashboards] Creating Security Overview visualizations...')

NAME_PREFIX = 'P1-'

# Viz 1: WAF attacks by type (pie chart)
v1 = create_visualization(
    f'{NAME_PREFIX}WAF Attack Types', 'pie', 'safeline-records',
    [
        {'id': '1', 'type': 'count', 'schema': 'metric'},
        {'id': '2', 'type': 'terms', 'schema': 'segment', 'params': {'field': 'attack_type', 'size': 10}}
    ],
    'SafeLine WAF attacks broken down by type'
)

# Viz 2: Suricata alerts timeline (histogram)
v2 = create_visualization(
    f'{NAME_PREFIX}Suricata Alert Timeline', 'histogram', 'suricata-alerts',
    [
        {'id': '1', 'type': 'count', 'schema': 'metric'},
        {'id': '2', 'type': 'date_histogram', 'schema': 'segment',
         'params': {'field': '@timestamp', 'interval': 'auto'}}
    ],
    'Suricata IDS alerts over time'
)

# Viz 3: Total threats (metric)
v3 = create_visualization(
    f'{NAME_PREFIX}Total Threats', 'metric', 'suricata-alerts',
    [{'id': '1', 'type': 'count', 'schema': 'metric'}],
    'Total detected threats'
)

# Viz 4: Top source IPs (table)
v4 = create_visualization(
    f'{NAME_PREFIX}Top Source IPs', 'table', 'suricata-alerts',
    [
        {'id': '1', 'type': 'count', 'schema': 'metric'},
        {'id': '2', 'type': 'terms', 'schema': 'bucket', 'params': {'field': 'src_ip', 'size': 10}}
    ],
    'Top attacking source IP addresses'
)

# Viz 5: Recent alerts (table)
v5 = create_visualization(
    f'{NAME_PREFIX}Recent Alerts', 'table', 'suricata-alerts',
    [
        {'id': '1', 'type': 'count', 'schema': 'metric'},
        {'id': '2', 'type': 'terms', 'schema': 'bucket', 'params': {'field': 'alert.signature_id', 'size': 20}}
    ],
    'Most frequent alert signatures'
)

print('[init-dashboards] Creating Security Overview dashboard...')

panels_security = [
    (v3, 'Total Threats', 6, 3, 0, 0),       # metric top-left
    (v1, 'WAF Attack Types', 6, 4, 6, 0),    # pie top-right
    (v2, 'Alert Timeline', 12, 4, 0, 3),      # timeline full-width
    (v4, 'Top Source IPs', 6, 4, 0, 7),      # table bottom-left
    (v5, 'Alert Signatures', 6, 4, 6, 7),    # table bottom-right
]

if all([v1, v2, v3, v4, v5]):
    create_dashboard('platform1-security-overview', panels_security,
                     'Unified security dashboard: WAF, IDS, threat metrics')

# ================================================================
# Build Data Lifecycle Dashboard
# ================================================================
print('[init-dashboards] Creating Data Lifecycle visualizations...')

# Viz 6: ES document count (metric)
v6 = create_visualization(
    f'{NAME_PREFIX}ES Total Documents', 'metric', 'minio-audit',
    [{'id': '1', 'type': 'count', 'schema': 'metric'}],
    'Total documents in ES'
)

# Viz 7: Pipeline throughput (area chart - docs over time)
v7 = create_visualization(
    f'{NAME_PREFIX}Pipeline Throughput', 'histogram', 'minio-audit',
    [
        {'id': '1', 'type': 'count', 'schema': 'metric'},
        {'id': '2', 'type': 'date_histogram', 'schema': 'segment',
         'params': {'field': '@timestamp', 'interval': 'auto'}}
    ],
    'Data pipeline throughput over time'
)

# Viz 8: NiFi processor status (metric - latest)
v8 = create_visualization(
    f'{NAME_PREFIX}NiFi Processors Running', 'metric', 'nifi-logs',
    [{'id': '1', 'type': 'max', 'schema': 'metric', 'params': {'field': 'nifi.processors_running'}}],
    'Number of running NiFi processors'
)

panels_data = [
    (v6, 'Total Documents', 4, 3, 0, 0),
    (v8, 'NiFi Processors', 4, 3, 4, 0),
    (v7, 'Throughput Timeline', 8, 6, 0, 3),
]

if v6 and v7 and v8:
    create_dashboard('platform2-data-lifecycle', panels_data,
                     'Data pipeline health and throughput monitoring')

print('[init-dashboards] Dashboard creation complete.')
