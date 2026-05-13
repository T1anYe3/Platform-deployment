#!/bin/bash
# ==========================================================================
# Platform 3 - Unified Log Ingestion
# Runs all 5 ingestion scripts sequentially.
#
# Usage:
#   bash ingest-all.sh                          # From inside a container with scripts mounted
#   ES_URL=http://localhost:19200 bash ingest-all.sh   # From host machine
#
# Prerequisites:
#   - Elasticsearch running on ES_URL (default: http://localhost:19200)
#   - Python 3 with urllib available
#   - Access to source services (Vault, MinIO, NiFi, SafeLine, Suricata)
# ==========================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ES_URL="${ES_URL:-http://localhost:19200}"
export ES_URL

echo "=============================================="
echo "  Platform 3 — Unified Log Ingestion"
echo "  ES Target: ${ES_URL}"
echo "  Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

PASS=0
FAIL=0

run_ingest() {
  local name="$1" script="$2"
  echo "--- ${name} ---"
  if python3 "${script}" 2>&1; then
    echo "  [OK] ${name}"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] ${name} (check logs above)"
    FAIL=$((FAIL + 1))
  fi
  echo ""
}

run_ingest "Vault Audit"     "ingest-vault-audit.py"
run_ingest "MinIO Audit"     "ingest-minio-audit.py"
run_ingest "NiFi Logs"       "ingest-nifi-logs.py"
run_ingest "SafeLine WAF"    "ingest-safeline.py"
run_ingest "Suricata IDS"    "ingest-suricata.py"

echo "=============================================="
echo "  Ingestion Complete: ${PASS} passed, ${FAIL} failed"
echo "=============================================="

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "  Some sources may not be available. This is normal if the"
  echo "  corresponding platform services are not currently running."
  echo ""
  echo "  To check results, visit:"
  echo "    http://localhost:15601 (Kibana) -> Discover"
fi
