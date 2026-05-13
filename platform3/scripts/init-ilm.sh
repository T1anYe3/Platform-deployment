#!/bin/sh
# Initialize Elasticsearch ILM policies and index templates for Platform 3
# Creates 30-day retention policies for all 5 log data sources

set -e

ES_URL="${ES_URL:-http://elasticsearch:9200}"

echo "[init-ilm] Waiting for Elasticsearch..."
for i in $(seq 1 30); do
  if curl -s "${ES_URL}" >/dev/null 2>&1; then
    echo "[init-ilm] Elasticsearch is ready."
    break
  fi
  sleep 3
done

# Create Platform 3 ILM policy: hot phase with rollover, delete after 30 days
echo "[init-ilm] Creating ILM policy: platform3-logs-30d..."
curl -s -X PUT "${ES_URL}/_ilm/policy/platform3-logs-30d" \
  -H 'Content-Type: application/json' \
  -d '{
    "policy": {
      "phases": {
        "hot": {
          "min_age": "0ms",
          "actions": {
            "rollover": {
              "max_primary_shard_size": "5gb",
              "max_age": "1d"
            },
            "set_priority": {
              "priority": 100
            }
          }
        },
        "delete": {
          "min_age": "30d",
          "actions": {
            "delete": {}
          }
        }
      }
    }
  }'

echo "[init-ilm] Creating index templates for all 5 data sources..."

# Create index templates with ILM policy
for prefix in vault-audit minio-audit nifi-logs safeline-records suricata-alerts; do
  echo "  Creating template for: ${prefix}-*"
  curl -s -X PUT "${ES_URL}/_index_template/${prefix}-template" \
    -H 'Content-Type: application/json' \
    -d "{
      \"index_patterns\": [\"${prefix}-*\"],
      \"template\": {
        \"settings\": {
          \"index.lifecycle.name\": \"platform3-logs-30d\",
          \"index.lifecycle.rollover_alias\": \"${prefix}\"
        }
      }
    }"
done

echo "[init-ilm] ILM policies and index templates created successfully."
