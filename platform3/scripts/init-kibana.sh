#!/bin/sh
# Initialize Kibana: create Data Views (Index Patterns) for all 5 Platform 3 data sources
# Uses Kibana 9.x data_views API (not deprecated saved_objects/index-pattern)

set -e

KIBANA_URL="${KIBANA_URL:-http://kibana:5601}"

echo "[kibana-init] Waiting for Kibana to be ready..."
for i in $(seq 1 60); do
  STATUS=$(curl -s "${KIBANA_URL}/api/status" 2>/dev/null)
  if echo "$STATUS" | grep -q '"overall":{'; then
    echo "[kibana-init] Kibana is ready."
    break
  fi
  sleep 5
done

# Use Kibana 9.x data_views API
create_data_view() {
  local NAME="$1" PATTERN="$2" TIMEFIELD="$3" DESC="$4"

  # Check if already exists
  EXISTING=$(curl -s "${KIBANA_URL}/api/data_views" \
    -H "kbn-xsrf: true" 2>/dev/null | grep -o "\"title\":\"${PATTERN}\"" || true)

  if [ -n "$EXISTING" ]; then
    echo "  [skip] ${DESC}"
    return
  fi

  curl -s -X POST "${KIBANA_URL}/api/data_views/data_view" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d "{\"data_view\":{\"title\":\"${PATTERN}\",\"name\":\"${NAME}\",\"timeFieldName\":\"${TIMEFIELD}\"}}" >/dev/null
  echo "  [ok]   ${DESC}"
}

echo "[kibana-init] Creating Kibana Data Views for Platform 3..."

create_data_view "Vault Audit Logs"      "vault-audit-*"       "@timestamp" "Data View: Vault Audit Logs"
create_data_view "MinIO Audit Logs"      "minio-audit-*"       "@timestamp" "Data View: MinIO Audit Logs"
create_data_view "NiFi Logs"             "nifi-logs-*"         "@timestamp" "Data View: NiFi Logs"
create_data_view "SafeLine WAF Records"  "safeline-records-*"  "@timestamp" "Data View: SafeLine WAF Records"
create_data_view "Suricata IDS Alerts"   "suricata-alerts-*"   "@timestamp" "Data View: Suricata IDS Alerts"

echo "[kibana-init] Kibana Data Views created successfully."
