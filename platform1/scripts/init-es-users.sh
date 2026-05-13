#!/bin/sh
# Initialize Elasticsearch built-in user passwords
# Only runs when ES_SECURITY_ENABLED=true

set -e

ES_URL="${ELASTICSEARCH_URL:-http://elasticsearch:9200}"
ES_PASSWORD="${ELASTIC_PASSWORD:-}"

if [ -z "$ES_PASSWORD" ] || [ "$ES_SECURITY_ENABLED" != "true" ]; then
  echo "[es-users-init] ES security not enabled, skipping."
  exit 0
fi

echo "[es-users-init] Waiting for Elasticsearch..."
for i in $(seq 1 30); do
  if curl -s -u "elastic:${ES_PASSWORD}" "${ES_URL}" >/dev/null 2>&1; then
    break
  fi
  sleep 3
done

echo "[es-users-init] Setting built-in user passwords..."
# Set kibana_system password
curl -s -u "elastic:${ES_PASSWORD}" -X POST "${ES_URL}/_security/user/kibana_system/_password" \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"${KIBANA_ES_PASSWORD}\"}" >/dev/null
echo "  [ok] kibana_system password set"

# Set logstash_system password (for future Logstash use)
curl -s -u "elastic:${ES_PASSWORD}" -X POST "${ES_URL}/_security/user/logstash_system/_password" \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"$(openssl rand -base64 24 2>/dev/null || echo "${ES_PASSWORD}_ls")\"}" >/dev/null
echo "  [ok] logstash_system password rotated"

echo "[es-users-init] ES user initialization complete."
