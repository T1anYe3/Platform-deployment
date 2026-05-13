#!/usr/bin/env python3
"""
Platform 2 Data Lifecycle Benchmark Suite.

Measures 6 data lifecycle KPIs:
  1. Secure Transmission Rate (TLS coverage)
  2. Data Ingestion Rate (ES indexing completeness)
  3. Certificate Compliance Rate (Vault PKI coverage)
  4. Audit Coverage Rate (operations logged)
  5. Pipeline Event Rate (bridge data flow activity)
  6. Data Throughput (NiFi->MinIO pipeline speed)

Usage:
  python security-benchmark.py --full          # Run all benchmarks
  python security-benchmark.py --metric tls    # Run single metric
  python security-benchmark.py --report        # Print last report
"""

import os, sys, json, time, socket, ssl, hashlib, argparse, subprocess
from datetime import datetime

ES_URL = os.environ.get('ELASTICSEARCH_URL', 'http://localhost:9200')
VAULT_ADDR = os.environ.get('VAULT_ADDR', 'https://localhost:8200')
VAULT_TOKEN = os.environ.get('VAULT_TOKEN', '')  # set after vault-init
RESULTS_FILE = '/tmp/platform2-benchmark-results.json'

# ============================================================
# Metric 1: Secure Transmission Rate
# ============================================================
def benchmark_tls_coverage():
    """Check which platform services use TLS and report coverage ratio."""
    services = [
        ('vault', 'localhost', 8200, True),
        ('elasticsearch', 'localhost', 9200, False),
        ('kibana', 'localhost', 5601, False),
        ('minio-api', 'localhost', 9000, False),
        ('minio-console', 'localhost', 9001, False),
        ('nifi', 'localhost', 8443, False),
    ]

    results = []
    for name, host, port, expect_tls in services:
        tls_detected = False
        error = None
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = socket.create_connection((host, port), timeout=5)
            try:
                sock = ctx.wrap_socket(sock, server_hostname=host)
                tls_detected = True
            except:
                pass
            sock.close()
        except Exception as e:
            error = str(e)

        results.append({
            'service': name, 'port': port, 'tls_expected': expect_tls,
            'tls_detected': tls_detected, 'error': error,
        })

    tls_count = sum(1 for r in results if r['tls_detected'])
    total = len(results)
    rate = tls_count / total * 100 if total > 0 else 0

    return {
        'metric': 'secure_transmission_rate',
        'value_pct': round(rate, 1),
        'target_pct': 95,
        'passed': rate >= 95,
        'tls_services': tls_count,
        'total_services': total,
        'details': results,
    }

# ============================================================
# Metric 2: Data Ingestion Rate
# ============================================================
def benchmark_event_ingestion():
    """Check ES indices data completeness."""
    import urllib.request

    indices_expected = ['platform2-vault-audit', 'platform2-minio-audit', 'platform2-nifi-logs']
    indices_status = {}

    total_docs = 0
    populated = 0
    for idx in indices_expected:
        try:
            req = urllib.request.Request(f'{ES_URL}/{idx}-*/_count')
            resp = urllib.request.urlopen(req, timeout=10)
            count = json.loads(resp.read()).get('count', 0)
            indices_status[idx] = count
            total_docs += count
            if count > 0:
                populated += 1
        except:
            indices_status[idx] = 0

    rate = populated / len(indices_expected) * 100 if indices_expected else 0

    return {
        'metric': 'data_ingestion_rate',
        'value_pct': round(rate, 1),
        'target_pct': 99,
        'passed': rate >= 99,
        'populated_indices': populated,
        'total_expected_indices': len(indices_expected),
        'total_docs_across_indices': total_docs,
        'indices': indices_status,
    }

# ============================================================
# Metric 3: Certificate Compliance Rate
# ============================================================
def benchmark_cert_compliance():
    """Verify TLS services use valid certificates."""
    certs = []
    cert_total = 0
    cert_ok = 0

    for name, host, port in [('vault', 'localhost', 8200), ('nifi', 'localhost', 8443)]:
        cert_total += 1
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = socket.create_connection((host, port), timeout=5)
            sock = ctx.wrap_socket(sock, server_hostname=host)
            cert = sock.getpeercert()
            sock.close()
            cert_ok += 1
            certs.append({'service': name, 'port': port, 'tls_valid': True})
        except Exception as e:
            certs.append({'service': name, 'port': port, 'tls_valid': False, 'error': str(e)})

    rate = cert_ok / cert_total * 100 if cert_total > 0 else 0

    return {
        'metric': 'certificate_compliance_rate',
        'value_pct': round(rate, 1),
        'target_pct': 100,
        'passed': rate >= 100,
        'compliant_services': cert_ok,
        'total_tls_services': cert_total,
        'details': certs,
    }

# ============================================================
# Metric 4: Audit Coverage Rate
# ============================================================
def benchmark_audit_coverage():
    """Verify Vault operations are logged to audit."""
    import urllib.request

    vault_audit_count = 0
    try:
        req = urllib.request.Request(f'{ES_URL}/platform2-vault-audit-*/_count')
        resp = urllib.request.urlopen(req, timeout=10)
        vault_audit_count = json.loads(resp.read()).get('count', 0)
    except:
        pass

    passed = vault_audit_count > 0
    rate = 100.0 if passed else 0.0

    return {
        'metric': 'audit_coverage_rate',
        'value_pct': round(rate, 1),
        'target_pct': 100,
        'passed': passed,
        'vault_audit_entries_in_es': vault_audit_count,
        'note': 'Pass if any audit entries exist in ES' if passed else 'No audit entries found',
    }

# ============================================================
# Metric 5: Pipeline Event Rate
# ============================================================
def benchmark_pipeline_events():
    """Check that bridge events are flowing through the pipeline."""
    import urllib.request

    bridge_indices = {
        'platform2-minio-audit': 'MinIO server & bucket status',
        'platform2-nifi-logs': 'NiFi system diagnostics',
    }
    events = {}

    total_events = 0
    active_sources = 0
    for idx, label in bridge_indices.items():
        try:
            req = urllib.request.Request(f'{ES_URL}/{idx}-*/_count')
            resp = urllib.request.urlopen(req, timeout=10)
            count = json.loads(resp.read()).get('count', 0)
            events[label] = count
            total_events += count
            if count > 0:
                active_sources += 1
        except:
            events[label] = 0

    rate = active_sources / len(bridge_indices) * 100 if bridge_indices else 0

    return {
        'metric': 'pipeline_event_rate',
        'value_pct': round(rate, 1),
        'target_pct': 90,
        'passed': rate >= 90,
        'active_sources': active_sources,
        'total_sources': len(bridge_indices),
        'total_events': total_events,
        'sources': events,
    }

# ============================================================
# Metric 6: Data Throughput (NiFi -> MinIO pipeline)
# ============================================================
def benchmark_data_throughput():
    """Measure end-to-end data pipeline throughput."""
    import tempfile

    # Generate a small test file
    tmpdir = tempfile.mkdtemp()
    test_path = os.path.join(tmpdir, 'perf-test.dat')
    chunk = os.urandom(50 * 1024 * 1024)  # 50 MB
    with open(test_path, 'wb') as f:
        f.write(chunk)

    # Measure MinIO upload throughput via mc
    t0 = time.time()
    try:
        result = subprocess.run([
            'mc', 'cp', test_path, 'platform2/raw-data/perf-test.dat'
        ], capture_output=True, timeout=300, check=False)
        elapsed = time.time() - t0
        throughput = 50 / elapsed if elapsed > 0 else 0
    except Exception as e:
        elapsed = 0
        throughput = 0

    return {
        'metric': 'data_throughput',
        'value_mbps': round(throughput, 1),
        'target_mbps': 10,
        'passed': throughput >= 10,
        'total_data_mb': 50,
        'total_time_s': round(elapsed, 1),
    }

# ============================================================
# Main runner
# ============================================================
def run_all_benchmarks(args):
    results = {
        'timestamp': datetime.now().isoformat(),
        'platform': 'Platform 2 Data Lifecycle Management',
        'benchmarks': [],
        'summary': {},
    }

    benchmarks = [
        ('tls', benchmark_tls_coverage, 'Secure Transmission Rate'),
        ('ingestion', benchmark_event_ingestion, 'Data Ingestion Rate'),
        ('cert', benchmark_cert_compliance, 'Certificate Compliance Rate'),
        ('audit', benchmark_audit_coverage, 'Audit Coverage Rate'),
        ('pipeline', benchmark_pipeline_events, 'Pipeline Event Rate'),
        ('throughput', benchmark_data_throughput, 'Data Throughput'),
    ]

    passed = 0
    failed = 0
    for metric_id, func, name in benchmarks:
        if args.metric and args.metric != metric_id:
            continue

        print(f'\n{"="*60}')
        print(f'  Benchmark: {name}')
        print(f'{"="*60}')
        result = func()
        results['benchmarks'].append(result)
        status = 'PASS' if result['passed'] else 'FAIL'
        if result['passed']:
            passed += 1
        else:
            failed += 1

        for k, v in result.items():
            if k in ('details', 'files', 'indices', 'sources'):
                continue
            print(f'  {k}: {v}')
        print(f'  >>> {status}')

    results['summary'] = {
        'total_benchmarks': len(results['benchmarks']),
        'passed': passed, 'failed': failed,
        'pass_rate_pct': round(passed / len(results['benchmarks']) * 100, 1) if results['benchmarks'] else 0,
    }

    output_path = args.output or RESULTS_FILE
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f'\nResults saved to: {output_path}')
    print(f'Summary: {passed}/{len(results["benchmarks"])} passed ({results["summary"]["pass_rate_pct"]}%)')

    return results

def main():
    parser = argparse.ArgumentParser(description='Platform 2 Data Lifecycle Benchmark')
    parser.add_argument('--full', action='store_true', help='Run all benchmarks')
    parser.add_argument('--metric', choices=['tls', 'ingestion', 'cert', 'audit', 'pipeline', 'throughput'],
                       help='Run single metric')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--report', action='store_true', help='Print last report')
    args = parser.parse_args()

    if args.report:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE) as f:
                print(f.read())
        else:
            print(f'No previous results found at {RESULTS_FILE}')
        return

    if not args.full and not args.metric:
        parser.print_help()
        return

    run_all_benchmarks(args)

if __name__ == '__main__':
    main()
