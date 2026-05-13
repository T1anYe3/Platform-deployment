"""Shared utilities for Platform 1 bridge scripts."""
import os, json, base64, time, urllib.request, ssl, sys

ES_URL = os.environ.get('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
ES_USER = os.environ.get('ELASTICSEARCH_USER', '')
ES_PASS = os.environ.get('ELASTICSEARCH_PASSWORD', '')

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

MAX_RETRIES = 3
RETRY_BACKOFF = [1, 3, 5]  # seconds


def _retry_request(req, timeout, is_bulk=False):
    """Execute a request with retry on connection errors."""
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = urllib.request.urlopen(req, context=_ctx, timeout=timeout)
            if is_bulk:
                result = json.loads(resp.read())
                if result.get('errors'):
                    print(f'[bridge] Bulk errors (attempt {attempt+1}): {result["errors"]}', file=sys.stderr)
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_BACKOFF[attempt])
                        continue
                return result
            return json.loads(resp.read())
        except (urllib.error.URLError, OSError, ConnectionError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                print(f'[bridge] Connection error (attempt {attempt+1}/{MAX_RETRIES+1}): {e}', file=sys.stderr)
                time.sleep(RETRY_BACKOFF[attempt])
        except Exception as e:
            last_error = e
            print(f'[bridge] Error: {e}', file=sys.stderr)
            break
    raise last_error or RuntimeError('ES request failed after retries')


def es_request(method, path, body=None, timeout=30):
    """Make an Elasticsearch API request, with auth and retry."""
    url = f'{ES_URL}{path}'
    data = None
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if ES_USER and ES_PASS:
        auth = base64.b64encode(f'{ES_USER}:{ES_PASS}'.encode()).decode()
        req.add_header('Authorization', f'Basic {auth}')
    return _retry_request(req, timeout)


def es_bulk_index(lines):
    """Bulk index newline-delimited JSON to ES, with retry."""
    body = '\n'.join(lines) + '\n'
    url = f'{ES_URL}/_bulk'
    data = body.encode()
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-ndjson')
    if ES_USER and ES_PASS:
        auth = base64.b64encode(f'{ES_USER}:{ES_PASS}'.encode()).decode()
        req.add_header('Authorization', f'Basic {auth}')
    return _retry_request(req, timeout=30, is_bulk=True)


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
