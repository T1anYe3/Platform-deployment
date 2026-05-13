#!/bin/sh
# Initialize Kibana for Platform 2: create Index Patterns and Dashboards

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
for idx in platform2-vault-audit platform2-minio-audit platform2-nifi-logs; do
  echo "  Checking for index: ${idx}-*"
  for j in $(seq 1 30); do
    if curl -s "http://elasticsearch:9200/_cat/indices/${idx}-*" 2>/dev/null | grep -q open; then
      echo "    Found ${idx} indices"
      break
    fi
    sleep 3
  done
done

create_or_skip "index-pattern" "platform2-vault-audit" \
  '{"attributes":{"name":"Platform 2 Vault Audit Logs","title":"platform2-vault-audit-*","timeFieldName":"@timestamp"}}' \
  "Index Pattern: Vault Audit Logs"

create_or_skip "index-pattern" "platform2-minio-audit" \
  '{"attributes":{"name":"Platform 2 MinIO Audit Logs","title":"platform2-minio-audit-*","timeFieldName":"@timestamp"}}' \
  "Index Pattern: MinIO Audit Logs"

create_or_skip "index-pattern" "platform2-nifi-logs" \
  '{"attributes":{"name":"Platform 2 NiFi System Logs","title":"platform2-nifi-logs-*","timeFieldName":"@timestamp"}}' \
  "Index Pattern: NiFi System Logs"

echo "[kibana-init] Creating Dashboards..."

create_or_skip "dashboard" "platform2-data-lifecycle" \
  '{"attributes":{"title":"Platform 2 Data Lifecycle Overview","description":"Data pipeline health and lifecycle monitoring dashboard","panelsJSON":"[]","kibanaSavedObjectMeta":{"searchSourceJSON":"{\"query\":{\"query\":\"\",\"language\":\"kuery\"},\"filter\":[]}"}}}' \
  "Dashboard: Data Lifecycle Overview"

create_or_skip "dashboard" "platform2-minio-status" \
  '{"attributes":{"title":"Platform 2 MinIO Bucket Status","description":"Object storage bucket metrics and object counts","panelsJSON":"[]","kibanaSavedObjectMeta":{"searchSourceJSON":"{\"query\":{\"query\":\"\",\"language\":\"kuery\"},\"filter\":[]}"}}}' \
  "Dashboard: MinIO Bucket Status"

create_or_skip "dashboard" "platform2-nifi-status" \
  '{"attributes":{"title":"Platform 2 NiFi Flow Status","description":"Data flow pipeline status and processor monitoring","panelsJSON":"[]","kibanaSavedObjectMeta":{"searchSourceJSON":"{\"query\":{\"query\":\"\",\"language\":\"kuery\"},\"filter\":[]}"}}}' \
  "Dashboard: NiFi Flow Status"

echo "[kibana-init] Kibana setup complete."
echo "  Kibana: http://localhost:5601"
