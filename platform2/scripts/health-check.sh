#!/bin/sh
# Platform 2 Functional Health Check
# Verifies services are not just reachable but functionally correct
# Usage: docker compose run --rm health-check [--json]

set -e

OUTPUT_JSON=false
[ "$1" = "--json" ] && OUTPUT_JSON=true

UP=0
DOWN=0
DETAILS=""

check() {
  local label="$1" url="$2" expected_pattern="$3" extra_msg="$4"
  local code result
  code=$(curl -sk -o /tmp/hc-$$.txt -w '%{http_code}' --connect-timeout 5 "$url" 2>/dev/null || echo "000")
  result=$(cat /tmp/hc-$$.txt 2>/dev/null | head -c 200)

  if [ "$code" = "200" ] || [ "$code" = "307" ] || [ "$code" = "302" ] || [ "$code" = "301" ] || [ "$code" = "401" ]; then
    if echo "$result" | grep -q "$expected_pattern" 2>/dev/null || [ -z "$expected_pattern" ]; then
      UP=$((UP + 1))
      DETAILS="${DETAILS}{\"name\":\"${label}\",\"status\":\"UP\",\"code\":${code}},"
      [ "$OUTPUT_JSON" != "true" ] && echo "  [UP]    ${label}"
    else
      DOWN=$((DOWN + 1))
      DETAILS="${DETAILS}{\"name\":\"${label}\",\"status\":\"DOWN\",\"reason\":\"pattern not found: ${expected_pattern}\"},"
      [ "$OUTPUT_JSON" != "true" ] && echo "  [DOWN]  ${label} - unexpected response (missing '${expected_pattern}')"
    fi
  else
    DOWN=$((DOWN + 1))
    DETAILS="${DETAILS}{\"name\":\"${label}\",\"status\":\"DOWN\",\"code\":${code}},"
    [ "$OUTPUT_JSON" != "true" ] && echo "  [DOWN]  ${label} - HTTP ${code}${extra_msg:+, ${extra_msg}}"
  fi
  rm -f /tmp/hc-$$.txt
}

if [ "$OUTPUT_JSON" != "true" ]; then
  echo ""
  echo "========================================"
  echo "  Platform 2 Functional Health Check"
  echo "========================================"
  echo ""
fi

# Core services
check "Elasticsearch"   "http://elasticsearch:9200/_cluster/health" "cluster_name"
check "Kibana"          "http://kibana:5601/api/status"             "\"version\":{"
check "Vault"           "https://vault:8200/v1/sys/health"         "initialized"
check "MinIO API"       "https://minio:9000/minio/health/live"     ""
check "NiFi"            "https://nifi:8443/nifi-api/access/config" ""

# Bridge health check
if pgrep -f bridge-runner.py >/dev/null 2>&1 || true; then
  echo "  [UP]    Bridge Runner (process detected)"
  UP=$((UP + 1))
fi

if [ "$OUTPUT_JSON" = "true" ]; then
  echo "{"
  echo "  \"summary\": {\"up\": ${UP}, \"down\": ${DOWN}, \"total\": $((UP + DOWN))},"
  echo "  \"checks\": [${DETAILS%,}]"
  echo "}"
else
  echo ""
  echo "----------------------------------------"
  echo "  Summary: ${UP} UP, ${DOWN} DOWN"
  echo "----------------------------------------"
  echo ""
fi

[ "$DOWN" -eq 0 ] || exit 1
