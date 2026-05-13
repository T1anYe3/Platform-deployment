#!/usr/bin/env python3
"""Create Kibana saved searches and dashboards for Platform 3.

Uses Kibana 9.x compatible APIs:
- Saved searches: POST /api/saved_objects/search (works in 9.x)
- Dashboards: POST /api/saved_objects/dashboard with embedded saved search panels
- Data views: created by init-kibana.sh via data_views API

Strategy: Create saved searches, then embed them as dashboard panels.
Avoids the deprecated visualization API and complex Lens format.
Users can customize panels via Kibana UI.
"""
import os, json, urllib.request, sys, time

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
        print(f'  API error ({method} {path}): {e}', file=sys.stderr)
        return {}

def wait_for_kibana():
    for i in range(30):
        try:
            resp = urllib.request.urlopen(f'{KIBANA_URL}/api/status', timeout=10)
            if resp.status == 200:
                print('[init-dashboards] Kibana is ready.')
                return True
        except Exception:
            pass
        time.sleep(3)
    print('[init-dashboards] WARNING: Kibana may not be fully ready.', file=sys.stderr)
    return False

def create_saved_search(title, index_pattern, desc='', columns=None):
    """Create a saved search object. Returns the saved object ID."""
    if columns is None:
        columns = ['@timestamp', 'event.source', 'event.action']
    body = {
        'attributes': {
            'title': title,
            'description': desc,
            'columns': columns,
            'sort': ['@timestamp', 'desc'],
            'kibanaSavedObjectMeta': {
                'searchSourceJSON': json.dumps({
                    'index': index_pattern,
                    'query': {'query': '', 'language': 'kuery'},
                    'filter': []
                })
            }
        }
    }
    result = api('POST', '/api/saved_objects/search', body)
    sid = result.get('id', '')
    if sid:
        print(f'  [ok] Search: {title} ({sid[:12]}...)')
    else:
        print(f'  [warn] Failed to create search: {title}')
    return sid

def create_dashboard_with_searches(title, panels_config, desc=''):
    """Create a dashboard embedding saved searches as panels.

    panels_config: list of (search_id, panel_title, w, h, x, y)
    Each panel references a saved search by ID and displays it in the dashboard.
    """
    panels = []
    references = []
    for i, (search_id, panel_title, w, h, x, y) in enumerate(panels_config):
        ref_name = f'panel_{i}_ref'
        panels.append({
            'version': '7.17.0',
            'type': 'search',
            'gridData': {'x': x, 'y': y, 'w': w, 'h': h, 'i': str(i)},
            'panelIndex': str(i),
            'embeddableConfig': {
                'title': panel_title,
                'savedSearchId': search_id,
            },
            'panelRefName': ref_name,
        })
        references.append({
            'name': ref_name,
            'type': 'search',
            'id': search_id,
        })

    body = {
        'attributes': {
            'title': title,
            'description': desc,
            'panelsJSON': json.dumps(panels),
            'version': 1,
            'kibanaSavedObjectMeta': {
                'searchSourceJSON': json.dumps({
                    'query': {'query': '', 'language': 'kuery'},
                    'filter': []
                })
            }
        },
        'references': references
    }
    result = api('POST', '/api/saved_objects/dashboard', body)
    did = result.get('id', '')
    if did:
        print(f'  [ok] Dashboard: {title} ({did[:12]}...)')
    else:
        print(f'  [warn] Failed to create dashboard: {title}')
    return did

# ================================================================
# Main
# ================================================================
wait_for_kibana()

PREFIX = 'P3-'

# ---- 5 Saved Searches ----
print('[init-dashboards] Creating Saved Searches...')

s1 = create_saved_search(
    f'{PREFIX}Vault Audit Logs', 'vault-audit',
    'Vault audit log entries - operations, authentication, and path access',
    ['@timestamp', 'event.action', 'auth.display_name', 'request.operation', 'request.path']
)

s2 = create_saved_search(
    f'{PREFIX}MinIO Audit Logs', 'minio-audit',
    'MinIO bucket status and object audit records',
    ['@timestamp', 'event.action', 'minio.bucket', 'minio.objects', 'minio.status']
)

s3 = create_saved_search(
    f'{PREFIX}NiFi System Diagnostics', 'nifi-logs',
    'NiFi processor status, thread activity, and cluster health',
    ['@timestamp', 'nifi.active_threads', 'nifi.processors_running', 'event.action']
)

s4 = create_saved_search(
    f'{PREFIX}SafeLine Attack Records', 'safeline-records',
    'SafeLine WAF attack detection, blocking actions, and source analysis',
    ['@timestamp', 'attack_type', 'src_ip', 'url_path', 'action', 'reason']
)

s5 = create_saved_search(
    f'{PREFIX}Suricata IDS Alerts', 'suricata-alerts',
    'Suricata IDS network intrusion detection alerts with severity and signatures',
    ['@timestamp', 'alert.signature', 'alert.severity', 'src_ip', 'dest_ip']
)

# ---- Dashboard 1: Platform Security Overview ----
print('[init-dashboards] Creating Platform Security Overview Dashboard...')

security_panels = []
if s4:  # SafeLine search
    security_panels.append((s4, 'WAF Attack Records', 6, 6, 0, 0))
if s5:  # Suricata search
    security_panels.append((s5, 'IDS Alert Records', 6, 6, 6, 0))
if s1:  # Vault audit for context
    security_panels.append((s1, 'Vault Audit Trail', 12, 5, 0, 6))

if security_panels:
    create_dashboard_with_searches(
        'Platform Security Overview',
        security_panels,
        'Unified security monitoring: SafeLine WAF + Suricata IDS + Vault audit across all platforms'
    )

# ---- Dashboard 2: Data Lifecycle Overview ----
print('[init-dashboards] Creating Data Lifecycle Overview Dashboard...')

data_panels = []
if s3:  # NiFi search
    data_panels.append((s3, 'NiFi System Diagnostics', 6, 6, 0, 0))
if s2:  # MinIO search
    data_panels.append((s2, 'MinIO Bucket Status', 6, 6, 6, 0))
if s1:  # Vault audit for operations
    data_panels.append((s1, 'Vault Operations Log', 12, 5, 0, 6))

if data_panels:
    create_dashboard_with_searches(
        'Data Lifecycle Overview',
        data_panels,
        'Data pipeline monitoring: NiFi processors + MinIO storage + Vault operations'
    )

# ---- Dashboard 3: All Sources Overview ----
print('[init-dashboards] Creating All Sources Overview Dashboard...')

all_panels = []
if s4: all_panels.append((s4, 'SafeLine WAF', 6, 5, 0, 0))
if s5: all_panels.append((s5, 'Suricata IDS', 6, 5, 6, 0))
if s1: all_panels.append((s1, 'Vault Audit', 4, 5, 0, 5))
if s2: all_panels.append((s2, 'MinIO Audit', 4, 5, 4, 5))
if s3: all_panels.append((s3, 'NiFi Logs', 4, 5, 8, 5))

if all_panels:
    create_dashboard_with_searches(
        'All Data Sources Overview',
        all_panels,
        'Complete view of all 5 log sources: WAF, IDS, Vault, MinIO, NiFi'
    )

print('[init-dashboards] Platform 3 dashboard creation complete.')
print(f'  Dashboards: 3 (Platform Security Overview, Data Lifecycle Overview, All Data Sources Overview)')
print(f'  Saved Searches: 5')
