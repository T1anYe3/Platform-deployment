#!/bin/sh
# Platform 1 Health Check - verifies all services are running

echo "========================================"
echo "  Platform 1 Docker Health Check"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

check_http() {
  local NAME=$1 URL=$2 TIMEOUT=${3:-5}
  if curl -sk --connect-timeout "$TIMEOUT" "$URL" >/dev/null 2>&1; then
    echo "  [UP]    $NAME"
    return 0
  else
    echo "  [DOWN]  $NAME"
    return 1
  fi
}

check_port() {
  local NAME=$1 HOST=$2 PORT=$3
  if timeout 3 sh -c "echo >/dev/tcp/$HOST/$PORT" 2>/dev/null; then
    echo "  [UP]    $NAME :$PORT"
    return 0
  else
    echo "  [DOWN]  $NAME :$PORT"
    return 1
  fi
}

UP=0
DOWN=0

echo "--- Core Services ---"
check_http "Vault"            "https://localhost:8200/v1/sys/health" 5 && UP=$((UP+1)) || DOWN=$((DOWN+1))
check_http "Elasticsearch"    "http://localhost:9200" 5 && UP=$((UP+1)) || DOWN=$((DOWN+1))
check_http "Kibana"           "http://localhost:5601/api/status" 10 && UP=$((UP+1)) || DOWN=$((DOWN+1))
check_http "MinIO API"        "http://localhost:9000/minio/health/live" 5 && UP=$((UP+1)) || DOWN=$((DOWN+1))
check_http "MinIO Console"    "http://localhost:9001" 5 && UP=$((UP+1)) || DOWN=$((DOWN+1))

echo ""
echo "--- Security Services ---"
check_http "NiFi"             "https://localhost:8443/nifi-api/access/config" 10 && UP=$((UP+1)) || DOWN=$((DOWN+1))
check_http "SafeLine WAF"     "https://localhost:9443" 10 && UP=$((UP+1)) || DOWN=$((DOWN+1))

echo ""
echo "--- Docker Containers ---"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | grep platform1 || echo "  (no containers found)"

echo ""
echo "--- Data Flow ---"
ES_INDICES=$(curl -s "http://localhost:9200/_cat/indices?format=json" 2>/dev/null | python3 -c "
import sys,json
try:
    indices = json.load(sys.stdin)
    for i in indices:
        if not i['index'].startswith('.'):
            print(f\"  {i['index']:40s} docs={i.get('docs.count','?'):>6}\")
except: pass
" 2>/dev/null)
if [ -n "$ES_INDICES" ]; then
  echo "$ES_INDICES"
  UP=$((UP+1))
else
  echo "  [DOWN]  ES indices not accessible"
  DOWN=$((DOWN+1))
fi

echo ""
echo "========================================"
echo "  Summary: $UP UP, $DOWN DOWN"
echo "========================================"
echo ""
echo "  Access URLs:"
echo "    Vault:        https://localhost:8200"
echo "    Elasticsearch: http://localhost:9200"
echo "    Kibana:        http://localhost:5601"
echo "    MinIO Console: http://localhost:9001"
echo "    NiFi:          https://localhost:8443/nifi"
echo "    SafeLine WAF:  https://localhost:9443"
