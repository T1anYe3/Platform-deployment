#!/bin/bash
# Platform 2 Restore Script
set -e

BACKUP_PATH="$1"
if [ -z "$BACKUP_PATH" ] || [ ! -d "$BACKUP_PATH" ]; then
  echo "Usage: bash restore.sh <backup-path>"
  echo "Example: bash restore.sh backups/20260513-120000"
  exit 1
fi

ES_URL="${ES_URL:-http://localhost:9200}"
ES_USER="${ELASTICSEARCH_USER:-}"
ES_PASS="${ELASTICSEARCH_PASSWORD:-}"
CURL_AUTH="${ES_USER:+ -u ${ES_USER}:${ES_PASS}}"

echo "[restore] === Platform 2 Restore from: ${BACKUP_PATH} ==="

MANIFEST="${BACKUP_PATH}/manifest.json"
if [ ! -f "$MANIFEST" ]; then
  echo "[restore] ERROR: manifest.json not found in backup path"
  exit 1
fi

SNAPSHOT_NAME=$(grep -o '"snapshot_name":"[^"]*"' "$MANIFEST" | cut -d'"' -f4)
echo "[restore] Snapshot: ${SNAPSHOT_NAME}"

# 1. Restore ES snapshot
echo "[restore] Restoring ES indices from snapshot..."
curl -s ${CURL_AUTH} -X POST "${ES_URL}/_all/_close" >/dev/null 2>&1 || true
sleep 2
curl -s ${CURL_AUTH} -X POST "${ES_URL}/_snapshot/platform2-backup/${SNAPSHOT_NAME}/_restore" \
  -H "Content-Type: application/json" \
  -d '{"indices": "platform2-vault-audit-*,platform2-minio-audit-*,platform2-nifi-logs-*"}' >/dev/null 2>&1 || echo "  (restore may have partially failed - check ES logs)"
echo "  [ok] ES restore attempted"

# 2. Restore Vault data
if [ -d "${BACKUP_PATH}/vault-data" ]; then
  echo "[restore] Restoring Vault data..."
  docker compose stop vault 2>/dev/null || true
  docker cp "${BACKUP_PATH}/vault-data/." platform2-vault:/vault/data/ 2>/dev/null || echo "  (vault data copy skipped)"
  docker compose start vault 2>/dev/null || true
fi

# 3. Restore .env
if [ -f "${BACKUP_PATH}/.env.backup" ]; then
  cp "${BACKUP_PATH}/.env.backup" "$(dirname "$0")/../.env"
  echo "  [ok] .env restored"
fi

echo "[restore] === Restore complete ==="
echo "  Please restart services: cd .. && docker compose restart"
