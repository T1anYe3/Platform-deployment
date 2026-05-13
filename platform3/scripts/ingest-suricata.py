#!/usr/bin/env python3
"""Ingest Suricata eve.json alerts into Elasticsearch.

Reads Suricata eve.json log file and indexes IDS alerts.
Connects to Suricata logs from a mounted or accessible path.
Writes to ES index suricata-alerts-YYYY.MM.DD.
"""
import os, sys, json, time, urllib.request, glob
from datetime import datetime, timezone

ES_URL = os.environ.get('ES_URL', 'http://localhost:19200')
INDEX_PREFIX = 'suricata-alerts'
SURICATA_LOG_DIR = os.environ.get('SURICATA_LOG_DIR', '/var/log/suricata')
SURICATA_EVE_FILE = os.environ.get('SURICATA_EVE_FILE', '')
MAX_RETRIES = 3

# State file to track last read position
STATE_FILE = os.environ.get('STATE_FILE', '/tmp/suricata-ingest-state.json')

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

def load_state():
    """Load last read position from state file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {'last_offset': 0, 'last_processed': ''}

def save_state(state):
    """Save current position to state file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f'  Could not save state: {e}', file=sys.stderr)

def find_eve_file():
    """Find the Suricata eve.json file."""
    if SURICATA_EVE_FILE and os.path.exists(SURICATA_EVE_FILE):
        return SURICATA_EVE_FILE

    # Try common locations
    candidates = [
        f'{SURICATA_LOG_DIR}/eve.json',
        '/var/log/suricata/eve.json',
        '/suricata-logs/eve.json',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path

    # Try glob
    matches = glob.glob(f'{SURICATA_LOG_DIR}/eve*.json')
    if matches:
        matches.sort(reverse=True)
        return matches[0]

    return None

def main():
    today = datetime.now(timezone.utc).strftime('%Y.%m.%d')
    index_name = f'{INDEX_PREFIX}-{today}'

    print(f'[ingest-suricata] Indexing to: {index_name}')
    print(f'[ingest-suricata] ES address: {ES_URL}')

    # Find eve.json
    eve_path = find_eve_file()
    if not eve_path:
        print(f'[ingest-suricata] No eve.json found. Searched: {SURICATA_LOG_DIR}')
        print(f'[ingest-suricata] Skipping (Suricata may not be running or logs not mounted).')
        return

    print(f'[ingest-suricata] Reading: {eve_path}')

    # Load state
    state = load_state()
    last_offset = state.get('last_offset', 0)
    file_size = os.path.getsize(eve_path)

    if file_size <= last_offset:
        print(f'[ingest-suricata] No new data (offset: {last_offset}, size: {file_size})')
        return

    # Read new lines
    records = []
    bytes_read = 0
    try:
        with open(eve_path, 'r') as f:
            f.seek(last_offset)
            for line in f:
                bytes_read += len(line)
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Only index alert events
                evt_type = evt.get('event_type', '')
                if evt_type != 'alert':
                    continue

                alert = evt.get('alert', {})
                src = evt.get('src_ip', '')
                dest = evt.get('dest_ip', '')

                records.append({
                    '@timestamp': evt.get('timestamp',
                        datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'),
                    'event': {
                        'source': 'suricata',
                        'action': 'alert',
                        'dataset': 'suricata-alerts'
                    },
                    'alert': {
                        'signature': alert.get('signature', ''),
                        'signature_id': alert.get('signature_id', 0),
                        'severity': alert.get('severity', 0),
                        'category': alert.get('category', ''),
                        'action': alert.get('action', '')
                    },
                    'src_ip': src,
                    'dest_ip': dest,
                    'proto': evt.get('proto', ''),
                    'src_port': evt.get('src_port', 0),
                    'dest_port': evt.get('dest_port', 0)
                })
    except Exception as e:
        print(f'[ingest-suricata] Error reading eve.json: {e}', file=sys.stderr)

    new_offset = last_offset + bytes_read

    if not records:
        print(f'[ingest-suricata] No new alerts found (read {bytes_read} bytes).')
        # Still save state to advance offset
        state['last_offset'] = new_offset
        state['last_processed'] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        return

    # Build bulk body
    lines = []
    for doc in records:
        lines.append(json.dumps({'index': {'_index': index_name}}))
        lines.append(json.dumps(doc))

    result = es_bulk_index(lines)
    print(f'[ingest-suricata] Indexed {len(records)} records to {index_name}')

    # Save state
    state['last_offset'] = new_offset
    state['last_processed'] = datetime.now(timezone.utc).isoformat()
    save_state(state)

if __name__ == '__main__':
    main()
