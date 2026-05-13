#!/usr/bin/env python3
"""Generate realistic attack traffic for Suricata IDS testing.

Generates HTTP requests with malicious User-Agent strings and URLs
matching the 3 custom Suricata rules + additional attack patterns.

Default: 50,000 requests (~200 MB of traffic)
"""

import socket, ssl, time, random, sys, json, argparse

# Attack payloads matching Suricata local.rules
ATTACK_PATTERNS = [
    # SID 9900101: sqlmap scanner
    {
        'method': 'GET',
        'path': '/api/v1/users?id=1',
        'headers': {
            'User-Agent': 'sqlmap/1.6#stable (http://sqlmap.org)',
            'Accept': '*/*',
        },
        'rule': 'SID 9900101 (sqlmap)',
        'category': 'web-application-attack',
    },
    # SID 9900102: Nikto scanner
    {
        'method': 'GET',
        'path': '/cgi-bin/test.cgi',
        'headers': {
            'User-Agent': 'Mozilla/4.75 (Nikto/2.1.6) (Evasions:None) (Test:ports)',
            'Host': 'localhost',
        },
        'rule': 'SID 9900102 (Nikto)',
        'category': 'web-application-attack',
    },
    # SID 9900103: sensitive file probe
    {
        'method': 'GET',
        'path': '/../../etc/passwd',
        'headers': {
            'User-Agent': 'curl/7.68.0',
            'Accept': '*/*',
        },
        'rule': 'SID 9900103 (/etc/passwd)',
        'category': 'web-application-attack',
    },
]

# Additional realistic attack patterns (for diversity)
BONUS_ATTACKS = [
    {
        'method': 'GET',
        'path': "/search?q=' OR 1=1--",
        'headers': {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'},
        'rule': 'SQL Injection probe',
        'category': 'web-application-attack',
    },
    {
        'method': 'POST',
        'path': '/login',
        'headers': {
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        'body': "username=admin'--&password=x",
        'rule': 'SQL Injection login bypass',
        'category': 'web-application-attack',
    },
    {
        'method': 'GET',
        'path': '/<script>alert(1)</script>',
        'headers': {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'},
        'rule': 'XSS probe',
        'category': 'web-application-attack',
    },
    {
        'method': 'POST',
        'path': '/api/exec',
        'headers': {
            'User-Agent': 'python-requests/2.28',
            'Content-Type': 'application/json',
        },
        'body': '{"cmd": "cat /etc/shadow; id"}',
        'rule': 'Command injection',
        'category': 'web-application-attack',
    },
    {
        'method': 'GET',
        'path': '/wp-admin/install.php',
        'headers': {'User-Agent': 'WPScan/3.1', 'Accept': '*/*'},
        'rule': 'WordPress scanner (WPScan)',
        'category': 'web-application-attack',
    },
]

# Normal traffic for mixing (makes detection more realistic)
NORMAL_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1',
    'Mozilla/5.0 (X11; Linux x86_64) Firefox/121.0',
]
NORMAL_PATHS = ['/', '/index.html', '/api/status', '/css/main.css', '/js/app.js', '/images/logo.png']
NORMAL_METHODS = ['GET', 'GET', 'GET', 'GET', 'POST']

def build_http_request(host, port, method, path, headers, body=''):
    req = f'{method} {path} HTTP/1.1\r\n'
    req += f'Host: {host}:{port}\r\n'
    for k, v in headers.items():
        req += f'{k}: {v}\r\n'
    if body:
        req += f'Content-Length: {len(body)}\r\n'
    req += 'Connection: close\r\n\r\n'
    if body:
        req += body
    return req.encode()

def send_request(host, port, use_tls, pattern):
    try:
        ctx = ssl.create_default_context() if use_tls else None
        if use_tls:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        if use_tls:
            sock = ctx.wrap_socket(sock, server_hostname=host)

        sock.connect((host, port))
        req = build_http_request(host, port,
                                 pattern['method'], pattern['path'],
                                 pattern['headers'], pattern.get('body', ''))
        sock.sendall(req)
        # Read response (don't care about content)
        try:
            while sock.recv(4096):
                pass
        except:
            pass
        sock.close()
        return True
    except Exception as e:
        return False

def main():
    parser = argparse.ArgumentParser(description='Generate attack traffic for Suricata testing')
    parser.add_argument('--target', default='127.0.0.1', help='Target host')
    parser.add_argument('--port', type=int, default=80, help='Target port')
    parser.add_argument('--tls', action='store_true', help='Use TLS')
    parser.add_argument('--num-attacks', type=int, default=50000,
                       help='Number of attack requests (default: 50000)')
    parser.add_argument('--normal-ratio', type=float, default=0.3,
                       help='Ratio of normal traffic mixed in (default: 0.3)')
    parser.add_argument('--delay', type=float, default=0.001,
                       help='Delay between requests in seconds')
    args = parser.parse_args()

    all_attacks = ATTACK_PATTERNS + BONUS_ATTACKS
    total = args.num_attacks
    detected = 0
    sent = 0

    print(f'Generating {total:,} HTTP requests to {args.target}:{args.port} (TLS={args.tls})')
    print(f'Normal traffic ratio: {args.normal_ratio}')
    print(f'Attack patterns: {len(all_attacks)}')

    results = {'total_sent': 0, 'attack_sent': 0, 'normal_sent': 0, 'errors': 0, 'by_rule': {}}

    start = time.time()
    for i in range(total):
        is_attack = random.random() > args.normal_ratio

        if is_attack:
            pattern = random.choice(all_attacks)
            success = send_request(args.target, args.port, args.tls, pattern)
            results['attack_sent'] += 1
            if success:
                rule = pattern.get('rule', 'unknown')
                results['by_rule'][rule] = results['by_rule'].get(rule, 0) + 1
        else:
            pattern = {
                'method': random.choice(NORMAL_METHODS),
                'path': random.choice(NORMAL_PATHS),
                'headers': {'User-Agent': random.choice(NORMAL_USER_AGENTS)},
                'rule': 'normal',
            }
            success = send_request(args.target, args.port, args.tls, pattern)
            results['normal_sent'] += 1

        if not success:
            results['errors'] += 1
        results['total_sent'] += 1

        if (i + 1) % 5000 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            print(f'  {i+1:,}/{total:,} requests ({rate:.0f} req/s)')

        if args.delay > 0:
            time.sleep(args.delay)

    elapsed = time.time() - start
    print(f'\nDone: {results["total_sent"]:,} requests in {elapsed:.1f}s ({results["total_sent"]/elapsed:.0f} req/s)')
    print(f'  Attack:  {results["attack_sent"]:,}')
    print(f'  Normal:  {results["normal_sent"]:,}')
    print(f'  Errors:  {results["errors"]:,}')
    print(f'\nAttack distribution:')
    for rule, count in sorted(results['by_rule'].items(), key=lambda x: -x[1]):
        print(f'  {count:>8,}  {rule}')

if __name__ == '__main__':
    main()
