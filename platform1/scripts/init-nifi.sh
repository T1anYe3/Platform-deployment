#!/bin/sh
# Initialize NiFi: import flow template via REST API

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

echo "[nifi-init] Creating platform1-demo-ingest process group..."
PG_RESP=$(curl -sk -X POST "${NIFI_URL}/nifi-api/process-groups/${ROOT_ID}/process-groups" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"revision":{"version":0},"component":{"name":"platform1-demo-ingest","position":{"x":0,"y":0}}}')
PG_ID=$(echo "$PG_RESP" | grep -o '"id":"[^"]*"' | head -1 | sed 's/"id":"\([^"]*\)"/\1/')
echo "[nifi-init] Process group created: ${PG_ID}"

echo "[nifi-init] NiFi setup complete."
echo "  NiFi UI: https://localhost:8443/nifi"
echo "  Username: ${NIFI_USER}"
