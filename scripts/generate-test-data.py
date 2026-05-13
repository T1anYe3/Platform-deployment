#!/usr/bin/env python3
"""Generate GB-scale test data for Platform 1 benchmark testing.

Outputs:
  test-data/bench-256m.json   (256 MB,  ~500K records)
  test-data/bench-256m.csv    (256 MB,  ~2M rows)
  test-data/bench-512m.mixed  (512 MB,  mixed formats)
  test-data/bench-1g.bin      (1 GB,    binary blob)
"""

import os, sys, json, time, random, hashlib, argparse

SENSOR_TYPES = ['temperature', 'humidity', 'power_draw', 'network_throughput', 'disk_io']
LOCATIONS = ['server-room-a', 'server-room-b', 'rack-c-01', 'rack-d-02', 'core-switch']
LEVELS = ['internal', 'confidential', 'secret']

USERS = ['zhangsan', 'lisi', 'wangwu', 'admin', 'auditor']
ACTIONS = ['login', 'logout', 'file_download', 'file_upload', 'api_call', 'data_export', 'config_change']
ENDPOINTS = ['/api/v1/records', '/api/v1/users', '/api/v1/config', '/data/report-q1.pdf', '/data/sensor-feed.csv']
IPS = [f'192.168.{a}.{b}' for a in range(1, 10) for b in range(1, 50)] + \
      [f'10.0.{a}.{b}' for a in range(5) for b in range(100)]

def mb_written(path):
    return os.path.getsize(path) / (1024 * 1024) if os.path.exists(path) else 0

def generate_json_file(path, target_mb):
    i = 0
    with open(path, 'w') as f:
        while mb_written(path) < target_mb:
            rec = {
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'user': random.choice(USERS),
                'action': random.choice(ACTIONS),
                'source_ip': random.choice(IPS),
                'status': random.choice(['success'] * 8 + ['denied', 'error']),
                'level': random.choice(LEVELS),
            }
            if rec['action'] in ('file_download', 'file_upload', 'data_export'):
                rec['resource'] = random.choice(ENDPOINTS)
            if rec['action'] == 'api_call':
                rec['endpoint'] = random.choice(ENDPOINTS)
            f.write(json.dumps(rec) + '\n')
            i += 1
    return i

def generate_csv_file(path, target_mb):
    header = 'timestamp,sensor_id,type,value,unit,location,level\n'
    i = 0
    with open(path, 'w') as f:
        f.write(header)
        while mb_written(path) < target_mb:
            row = [
                time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                f'S{random.randint(1, 50):04d}',
                random.choice(SENSOR_TYPES),
                f'{random.uniform(0, 100):.2f}',
                random.choice(['celsius', 'percent', 'kw', 'mbps']),
                random.choice(LOCATIONS),
                random.choice(LEVELS),
            ]
            f.write(','.join(row) + '\n')
            i += 1
    return i

def generate_mixed_file(path, target_mb):
    i = 0
    with open(path, 'w') as f:
        while mb_written(path) < target_mb:
            fmt = random.choice(['json', 'csv', 'log'])
            if fmt == 'json':
                f.write(json.dumps({
                    'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'event': random.choice(ACTIONS),
                    'src': random.choice(IPS),
                    'level': random.choice(LEVELS),
                }) + '\n')
            elif fmt == 'csv':
                f.write(f'{time.time()},{random.choice(SENSOR_TYPES)},{random.uniform(0, 100):.3f}\n')
            else:
                f.write(f'[{time.strftime("%H:%M:%S")}] {random.choice(ACTIONS)} from {random.choice(IPS)} - level={random.choice(LEVELS)}\n')
            i += 1
    return i

def generate_binary_file(path, target_mb):
    chunk = os.urandom(1024 * 1024)  # 1 MB random chunk
    with open(path, 'wb') as f:
        for _ in range(int(target_mb)):
            f.write(chunk)
    return int(target_mb)

def main():
    parser = argparse.ArgumentParser(description='Generate Platform 1 benchmark test data')
    parser.add_argument('--output-dir', default='/tmp/platform1-benchmark-data',
                       help='Output directory for test data')
    parser.add_argument('--total-size', type=float, default=2.0,
                       help='Total data size in GB (default: 2.0)')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    total_target_mb = args.total_size * 1024

    # Allocate sizes
    sizes = {
        'bench-256m.json': 256,
        'bench-256m.csv': 256,
        'bench-512m.mixed': 512,
        'bench-1g.bin': total_target_mb - 256 - 256 - 512,
    }

    results = {}
    total_mb = 0
    start = time.time()

    for filename, size_mb in sizes.items():
        path = os.path.join(args.output_dir, filename)
        size_mb = max(size_mb, 50)  # minimum 50 MB

        print(f'Generating {filename} ({size_mb:.0f} MB)...')
        t0 = time.time()

        if filename.endswith('.json'):
            records = generate_json_file(path, size_mb)
        elif filename.endswith('.csv'):
            records = generate_csv_file(path, size_mb)
        elif filename.endswith('.mixed'):
            records = generate_mixed_file(path, size_mb)
        elif filename.endswith('.bin'):
            records = generate_binary_file(path, size_mb)
        else:
            continue

        elapsed = time.time() - t0
        actual_mb = mb_written(path)
        total_mb += actual_mb
        results[filename] = {
            'target_mb': size_mb,
            'actual_mb': actual_mb,
            'records': records,
            'time_s': round(elapsed, 1),
            'throughput_mbps': round(actual_mb / elapsed, 1) if elapsed > 0 else 0,
        }
        print(f'  Done: {actual_mb:.1f} MB, {records} records, {elapsed:.1f}s ({actual_mb/elapsed:.1f} MB/s)')

    total_time = time.time() - start
    print(f'\nTotal: {total_mb:.1f} MB in {total_time:.1f}s ({total_mb/total_time:.1f} MB/s)')
    print(f'Output: {args.output_dir}')

    # Write manifest
    manifest = {
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'total_mb': round(total_mb, 1),
        'total_time_s': round(total_time, 1),
        'files': results,
    }
    manifest_path = os.path.join(args.output_dir, 'manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f'Manifest: {manifest_path}')

if __name__ == '__main__':
    main()
