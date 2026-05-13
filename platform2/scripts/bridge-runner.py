#!/usr/bin/env python3
"""Bridge Runner: orchestrates all Platform 2 data bridges on a schedule."""

import os, sys, time, subprocess, logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
log = logging.getLogger('bridge-runner')

BRIDGES = [
    ('minio', 60),    # every 60 seconds
    ('nifi',  120),   # every 2 minutes
    ('vault', 300),   # every 5 minutes
]

SCRIPTS_DIR = '/scripts'

MAX_RETRIES = 3
RETRY_BACKOFF = [5, 15, 30]  # seconds between retries

def run_bridge(name):
    script = os.path.join(SCRIPTS_DIR, f'bridge-{name}.py')
    if not os.path.exists(script):
        log.warning(f'Bridge script not found: {script}')
        return False

    for attempt in range(MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                ['python3', script],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                log.info(f'[{name}] OK: {result.stdout.strip()[:200]}')
                return True
            else:
                err = result.stderr.strip()[:300]
                log.warning(f'[{name}] FAILED (attempt {attempt+1}/{MAX_RETRIES+1}): {err}')
        except subprocess.TimeoutExpired:
            log.warning(f'[{name}] TIMEOUT (attempt {attempt+1}/{MAX_RETRIES+1})')
        except Exception as e:
            log.warning(f'[{name}] ERROR (attempt {attempt+1}/{MAX_RETRIES+1}): {e}')

        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            log.info(f'[{name}] Retrying in {wait}s...')
            time.sleep(wait)

    log.error(f'[{name}] All {MAX_RETRIES+1} attempts failed, skipping this cycle')
    return False

def main():
    log.info('Platform 2 Bridge Runner starting...')

    # Initial run of all bridges
    for name, _ in BRIDGES:
        run_bridge(name)

    # Scheduled runs
    last_run = {name: 0 for name, _ in BRIDGES}
    while True:
        now = time.time()
        for name, interval in BRIDGES:
            if now - last_run[name] >= interval:
                run_bridge(name)
                last_run[name] = now
        time.sleep(10)

if __name__ == '__main__':
    main()
