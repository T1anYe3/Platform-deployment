#!/bin/sh
# Initialize Kibana: create Index Patterns, Dashboards, and Saved Searches

set -e

KIBANA_URL="http://kibana:5601"

echo "[kibana-init] Waiting for Kibana to be ready..."
for i in $(seq 1 60); do
  STATUS=$(curl -s "${KIBANA_URL}/api/status" 2>/dev/null)
  if echo "$STATUS" | grep -q '"overall":{'; then
    echo "[kibana-init] Kibana is ready."
    break
  fi
  sleep 5
done

# Helper function to create or skip saved objects
create_or_skip() {
  local TYPE=$1 ID=$2 BODY=$3 DESC=$4

  CHECK=$(curl -s "${KIBANA_URL}/api/saved_objects/${TYPE}/${ID}" \
    -H "kbn-xsrf: true" 2>/dev/null)

  if echo "$CHECK" | grep -q '"id"'; then
    echo "  [skip] ${DESC}"
    return
  fi

  curl -s -X POST "${KIBANA_URL}/api/saved_objects/${TYPE}/${ID}" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d "$BODY" >/dev/null
  echo "  [ok]   ${DESC}"
}

echo "[kibana-init] Creating Index Patterns..."

# Wait for ES indices to exist before creating data views
for idx in safeline-records suricata-alerts vault-audit minio-audit nifi-logs; do
  echo "  Checking for index: ${idx}-*"
  for j in $(seq 1 30); do
    if curl -s "http://elasticsearch:9200/_cat/indices/${idx}-*" 2>/dev/null | grep -q open; then
      echo "    Found ${idx} indices"
      break
    fi
    sleep 3
  done
done

create_or_skip "index-pattern" "safeline-records" \
  '{"data_view":{"name":"SafeLine WAF Records","title":"safeline-records-*","timeFieldName":"@timestamp"}}' \
  "Index Pattern: SafeLine Records"

create_or_skip "index-pattern" "suricata-alerts" \
  '{"data_view":{"name":"Suricata IDS Alerts","title":"suricata-alerts-*","timeFieldName":"@timestamp"}}' \
  "Index Pattern: Suricata Alerts"

create_or_skip "index-pattern" "vault-audit" \
  '{"data_view":{"name":"Vault Audit Logs","title":"vault-audit-*","timeFieldName":"@timestamp"}}' \
  "Index Pattern: Vault Audit"

create_or_skip "index-pattern" "minio-audit" \
  '{"data_view":{"name":"MinIO Audit Logs","title":"minio-audit-*","timeFieldName":"@timestamp"}}' \
  "Index Pattern: MinIO Audit"

create_or_skip "index-pattern" "nifi-logs" \
  '{"data_view":{"name":"NiFi Logs","title":"nifi-logs-*","timeFieldName":"@timestamp"}}' \
  "Index Pattern: NiFi Logs"

echo "[kibana-init] Creating Dashboards..."

create_or_skip "dashboard" "platform1-security-overview" \
  '{"attributes":{"title":"Platform1 Security Overview","description":"Unified security dashboard for WAF and IDS","panelsJSON":"[]","kibanaSavedObjectMeta":{"searchSourceJSON":"{\"query\":{\"query\":\"\",\"language\":\"kuery\"},\"filter\":[]}"}}}' \
  "Dashboard: Platform1 Security Overview"

create_or_skip "dashboard" "platform2-data-lifecycle" \
  '{"attributes":{"title":"Platform2 Data Lifecycle Overview","description":"Data pipeline health","panelsJSON":"[]","kibanaSavedObjectMeta":{"searchSourceJSON":"{\"query\":{\"query\":\"\",\"language\":\"kuery\"},\"filter\":[]}"}}}' \
  "Dashboard: Platform2 Data Lifecycle"

echo "[kibana-init] Kibana setup complete."
echo "  Kibana: http://localhost:5601"
