"""Shared utilities for Platform 1 bridge scripts."""
import os, json, base64, urllib.request, ssl

ES_URL = os.environ.get('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
ES_USER = os.environ.get('ELASTICSEARCH_USER', '')
ES_PASS = os.environ.get('ELASTICSEARCH_PASSWORD', '')

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def es_request(method, path, body=None, timeout=30):
    """Make an Elasticsearch API request, with auth if configured."""
    url = f'{ES_URL}{path}'
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if ES_USER and ES_PASS:
        auth = base64.b64encode(f'{ES_USER}:{ES_PASS}'.encode()).decode()
        req.add_header('Authorization', f'Basic {auth}')
    resp = urllib.request.urlopen(req, context=_ctx, timeout=timeout)
    return json.loads(resp.read())


def es_bulk_index(lines):
    """Bulk index newline-delimited JSON to ES."""
    body = '\n'.join(lines) + '\n'
    url = f'{ES_URL}/_bulk'
    data = body.encode()
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-ndjson')
    if ES_USER and ES_PASS:
        auth = base64.b64encode(f'{ES_USER}:{ES_PASS}'.encode()).decode()
        req.add_header('Authorization', f'Basic {auth}')
    resp = urllib.request.urlopen(req, context=_ctx, timeout=30)
    result = json.loads(resp.read())
    if result.get('errors'):
        print(f'Bulk errors: {result["errors"]}', file=__import__('sys').stderr)
    return result


def ensure_index_template(name, mappings, settings=None):
    """Create or update an ES index template."""
    if settings is None:
        settings = {'number_of_shards': 1, 'number_of_replicas': 0}
    template = {
        'index_patterns': [f'{name}-*'],
        'template': {
            'settings': settings,
            'mappings': {'properties': mappings}
        }
    }
    es_request('PUT', f'/_index_template/{name}-template', template, timeout=10)
