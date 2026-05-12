#!/usr/bin/env python3
"""Bridge Runner: orchestrates all Platform 1 data bridges on a schedule."""

import os, sys, time, subprocess, logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
log = logging.getLogger('bridge-runner')

BRIDGES = [
    ('safeline', 300),   # every 5 minutes
    ('suricata', 60),    # every 1 minute
    ('vault',    600),   # every 10 minutes
    ('minio',    600),   # every 10 minutes
    ('nifi',     600),   # every 10 minutes
]

SCRIPTS_DIR = '/scripts'

def run_bridge(name):
    script = os.path.join(SCRIPTS_DIR, f'bridge-{name}.py')
    if not os.path.exists(script):
        log.warning(f'Bridge script not found: {script}')
        return False
    try:
        result = subprocess.run(
            ['python3', script],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            log.info(f'[{name}] OK: {result.stdout.strip()[:200]}')
            return True
        else:
            log.error(f'[{name}] FAILED: {result.stderr.strip()[:300]}')
            return False
    except Exception as e:
        log.error(f'[{name}] ERROR: {e}')
        return False

def main():
    log.info('Platform 1 Bridge Runner starting...')

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
