#!/bin/sh
# Initialize Elasticsearch ILM policies and index templates for Platform 2
# Usage: runs as a one-shot init container

set -e

ES_URL="${ELASTICSEARCH_URL:-http://elasticsearch:9200}"
ES_USER="${ELASTICSEARCH_USER:-}"
ES_PASS="${ELASTICSEARCH_PASSWORD:-}"

# Auth curl helper
if [ -n "$ES_USER" ] && [ -n "$ES_PASS" ]; then
  CURL_AUTH="-u ${ES_USER}:${ES_PASS}"
else
  CURL_AUTH=""
fi

echo "[init-ilm] Waiting for Elasticsearch..."
for i in $(seq 1 30); do
  if curl -s ${CURL_AUTH} "${ES_URL}" >/dev/null 2>&1; then
    break
  fi
  sleep 3
done

create_ilm_policy() {
  local NAME="$1" HOT_DAYS="$2" WARM_DAYS="$3" DELETE_DAYS="$4"
  echo "[init-ilm] Creating ILM policy: ${NAME}-policy (hot:${HOT_DAYS}d warm:${WARM_DAYS}d delete:${DELETE_DAYS}d)"
  curl -s ${CURL_AUTH} -X PUT "${ES_URL}/_ilm/policy/${NAME}-policy" \
    -H "Content-Type: application/json" \
    -d "{
      \"policy\": {
        \"phases\": {
          \"hot\": {
            \"min_age\": \"0ms\",
            \"actions\": {
              \"rollover\": {
                \"max_primary_shard_size\": \"10gb\",
                \"max_age\": \"1d\"
              },
              \"set_priority\": {\"priority\": 100}
            }
          },
          \"warm\": {
            \"min_age\": \"${HOT_DAYS}d\",
            \"actions\": {
              \"shrink\": {\"number_of_shards\": 1},
              \"forcemerge\": {\"max_num_segments\": 1},
              \"set_priority\": {\"priority\": 50}
            }
          },
          \"delete\": {
            \"min_age\": \"${DELETE_DAYS}d\",
            \"actions\": {\"delete\": {}}
          }
        }
      }
    }" >/dev/null
}

# Platform 2 index lifecycle policies
create_ilm_policy "platform2-vault-audit" 30 90 180
create_ilm_policy "platform2-minio-audit" 30 90 180
create_ilm_policy "platform2-nifi-logs" 30 90 180

echo "[init-ilm] ILM policies created."
echo "[init-ilm] Complete."
