#!/bin/sh
# Initialize NiFi for Platform 2: create demo data ingest process group

set -e

NIFI_URL="https://nifi:8443"
NIFI_USER="${NIFI_ADMIN_USER:-admin}"
NIFI_PASS="${NIFI_ADMIN_PASS:-Admin123!ChangeMe}"

echo "[nifi-init] Waiting for NiFi to be ready..."
for i in $(seq 1 60); do
  if curl -sk "${NIFI_URL}/nifi-api/access/config" >/dev/null 2>&1; then
    echo "[nifi-init] NiFi is reachable."
    break
  fi
  sleep 5
done

echo "[nifi-init] Obtaining NiFi access token..."
TOKEN=$(curl -sk -X POST "${NIFI_URL}/nifi-api/access/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${NIFI_USER}&password=${NIFI_PASS}")

if [ -z "$TOKEN" ]; then
  echo "[nifi-init] WARNING: Could not obtain NiFi token. Skipping flow import."
  echo "  Please import the flow template manually via the NiFi UI."
  exit 0
fi

echo "[nifi-init] Getting root process group..."
ROOT_PG=$(curl -sk "${NIFI_URL}/nifi-api/flow/process-groups/root" \
  -H "Authorization: Bearer ${TOKEN}")
ROOT_ID=$(echo "$ROOT_PG" | sed 's/.*"id":"\([^"]*\)".*processGroupFlow.*/\1/')
if [ -z "$ROOT_ID" ] || [ "$ROOT_ID" = "$ROOT_PG" ]; then
  ROOT_ID=$(echo "$ROOT_PG" | grep -o '"id":"[^"]*"' | head -1 | sed 's/"id":"\([^"]*\)"/\1/')
fi
echo "[nifi-init] Root PG ID: ${ROOT_ID}"

# Check if process group already exists (idempotency)
# Use NiFi search API for reliable detection (grep on root flow JSON is unreliable for large responses)
echo "[nifi-init] Checking for existing platform2-demo-ingest process group..."
SEARCH_RESULT=$(curl -sk "${NIFI_URL}/nifi-api/flow/search-results?q=platform2-demo-ingest" \
  -H "Authorization: Bearer ${TOKEN}" 2>/dev/null)
if echo "$SEARCH_RESULT" | grep -q '"platform2-demo-ingest"'; then
  echo "[nifi-init] [skip] Process group 'platform2-demo-ingest' already exists."
  echo "[nifi-init] NiFi setup complete (already initialized)."
  echo "  NiFi UI: https://localhost:8443/nifi"
  echo "  Username: ${NIFI_USER}"
  exit 0
fi

echo "[nifi-init] Creating platform2-demo-ingest process group..."
PG_RESP=$(curl -sk -X POST "${NIFI_URL}/nifi-api/process-groups/${ROOT_ID}/process-groups" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"revision":{"version":0},"component":{"name":"platform2-demo-ingest","position":{"x":0,"y":0}}}')
PG_ID=$(echo "$PG_RESP" | grep -o '"id":"[^"]*"' | head -1 | sed 's/"id":"\([^"]*\)"/\1/')
echo "[nifi-init] Process group created: ${PG_ID}"

# Create GetFile processor (reads sample data files)
echo "[nifi-init] Creating GetFile processor..."
GETFILE_RESP=$(curl -sk -X POST "${NIFI_URL}/nifi-api/process-groups/${PG_ID}/processors" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "revision": {"version": 0},
    "component": {
      "name": "GetFile-Ingest",
      "type": "org.apache.nifi.processors.standard.GetFile",
      "position": {"x": 100, "y": 100},
      "config": {
        "properties": {
          "Input Directory": "/opt/nifi/data/input",
          "File Filter": ".*\\.(json|csv)$",
          "Keep Source File": "false",
          "Polling Interval": "10 sec"
        },
        "schedulingPeriod": "10 sec",
        "schedulingStrategy": "TIMER_DRIVEN"
      }
    }
  }')
GETFILE_ID=$(echo "$GETFILE_RESP" | grep -o '"id":"[^"]*"' | head -1 | sed 's/"id":"\([^"]*\)"/\1/')
echo "[nifi-init] GetFile processor: ${GETFILE_ID}"

# Create UpdateAttribute processor (adds data.source, data.level, data.ingested fields)
echo "[nifi-init] Creating UpdateAttribute processor..."
UPDATE_RESP=$(curl -sk -X POST "${NIFI_URL}/nifi-api/process-groups/${PG_ID}/processors" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "revision": {"version": 0},
    "component": {
      "name": "UpdateAttribute-Enrich",
      "type": "org.apache.nifi.processors.attributes.UpdateAttribute",
      "position": {"x": 400, "y": 100},
      "config": {
        "properties": {
          "data.source": "nifi-ingest",
          "data.level": "${data.level:internal}",
          "data.ingested": "${now():format(\"yyyy-MM-dd HH:mm:ss.SSS\")}"
        },
        "schedulingPeriod": "0 sec",
        "schedulingStrategy": "TIMER_DRIVEN"
      }
    }
  }')
UPDATE_ID=$(echo "$UPDATE_RESP" | grep -o '"id":"[^"]*"' | head -1 | sed 's/"id":"\([^"]*\)"/\1/')
echo "[nifi-init] UpdateAttribute processor: ${UPDATE_ID}"

# Create PutS3Object processor (writes to MinIO raw-data bucket)
echo "[nifi-init] Creating PutS3Object processor..."
PUTS3_RESP=$(curl -sk -X POST "${NIFI_URL}/nifi-api/process-groups/${PG_ID}/processors" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "revision": {"version": 0},
    "component": {
      "name": "PutS3Object-MinIO",
      "type": "org.apache.nifi.processors.aws.s3.PutS3Object",
      "position": {"x": 700, "y": 100},
      "config": {
        "properties": {
          "Bucket": "raw-data",
          "Endpoint Override": "https://minio:9000",
          "Access Key ID": "${MINIO_ROOT_USER}",
          "Secret Access Key": "${MINIO_ROOT_PASSWORD}",
          "s3-endpoint": "https://minio:9000",
          "Object Key": "${filename}",
          "Content Type": "application/octet-stream",
          "Use Path Style Access": "true"
        },
        "schedulingPeriod": "0 sec",
        "schedulingStrategy": "TIMER_DRIVEN"
      }
    }
  }')
PUTS3_ID=$(echo "$PUTS3_RESP" | grep -o '"id":"[^"]*"' | head -1 | sed 's/"id":"\([^"]*\)"/\1/')
echo "[nifi-init] PutS3Object processor: ${PUTS3_ID}"

if [ -n "$GETFILE_ID" ] && [ -n "$UPDATE_ID" ] && [ -n "$PUTS3_ID" ]; then
  echo "[nifi-init] Creating connections between processors..."

  # Connect GetFile -> UpdateAttribute
  curl -sk -X POST "${NIFI_URL}/nifi-api/process-groups/${PG_ID}/connections" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"revision\":{\"version\":0},\"component\":{\"name\":\"GetFile->UpdateAttribute\",\"source\":{\"id\":\"${GETFILE_ID}\",\"type\":\"PROCESSOR\"},\"destination\":{\"id\":\"${UPDATE_ID}\",\"type\":\"PROCESSOR\"},\"selectedRelationships\":[\"success\"]}}" >/dev/null 2>&1
  echo "  [ok] GetFile -> UpdateAttribute"

  # Connect UpdateAttribute -> PutS3Object
  curl -sk -X POST "${NIFI_URL}/nifi-api/process-groups/${PG_ID}/connections" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"revision\":{\"version\":0},\"component\":{\"name\":\"UpdateAttribute->PutS3Object\",\"source\":{\"id\":\"${UPDATE_ID}\",\"type\":\"PROCESSOR\"},\"destination\":{\"id\":\"${PUTS3_ID}\",\"type\":\"PROCESSOR\"},\"selectedRelationships\":[\"success\"]}}" >/dev/null 2>&1
  echo "  [ok] UpdateAttribute -> PutS3Object"
else
  echo "[nifi-init] WARNING: Could not create all processors. Flow may be incomplete."
fi

echo "[nifi-init] NiFi setup complete."
echo "  NiFi UI: https://localhost:8443/nifi"
echo "  Username: ${NIFI_USER}"
