#!/bin/bash
# Platform 3 Restore Script
# Restores ES snapshot, Vault data, and .env from a backup directory
set -e

BACKUP_PATH="$1"
if [ -z "$BACKUP_PATH" ] || [ ! -d "$BACKUP_PATH" ]; then
  echo "Usage: bash restore.sh <backup-path>"
  echo "Example: bash restore.sh backups/20260513-120000"
  exit 1
fi

ES_URL="${ES_URL:-http://localhost:19200}"
ES_USER="${ELASTICSEARCH_USER:-}"
ES_PASS="${ELASTICSEARCH_PASSWORD:-}"
CURL_AUTH="${ES_USER:+ -u ${ES_USER}:${ES_PASS}}"

echo "[restore] === Platform 3 Restore from: ${BACKUP_PATH} ==="

MANIFEST="${BACKUP_PATH}/manifest.json"
if [ ! -f "$MANIFEST" ]; then
  echo "[restore] WARNING: manifest.json not found in backup path"
else
  SNAPSHOT_NAME=$(grep -o '"snapshot_name":"[^"]*"' "$MANIFEST" | cut -d'"' -f4)
  echo "[restore] Snapshot: ${SNAPSHOT_NAME}"
fi

# 1. Delete existing indices for clean restore
echo "[restore] Deleting existing indices..."
for prefix in vault-audit minio-audit nifi-logs safeline-records suricata-alerts; do
  curl -s ${CURL_AUTH} -X DELETE "${ES_URL}/${prefix}-*" >/dev/null 2>&1 || true
done
sleep 2

# 2. Restore ES snapshot
echo "[restore] Restoring ES indices from snapshot..."
curl -s ${CURL_AUTH} -X POST "${ES_URL}/_snapshot/platform3-backup/${SNAPSHOT_NAME}/_restore" \
  -H "Content-Type: application/json" \
  -d '{"indices": "vault-audit-*,minio-audit-*,nifi-logs-*,safeline-records-*,suricata-alerts-*", "ignore_unavailable": true}' >/dev/null 2>&1 || echo "  (restore may have partially failed - check ES logs)"
echo "  [ok] ES restore attempted"

# 3. Restore Vault data
if [ -d "${BACKUP_PATH}/vault-data" ]; then
  echo "[restore] Restoring Vault data..."
  docker compose stop vault 2>/dev/null || true
  docker cp "${BACKUP_PATH}/vault-data/." platform3-vault:/vault/data/ 2>/dev/null || echo "  (vault data copy skipped)"
  docker compose start vault 2>/dev/null || true
fi

# 4. Restore .env
if [ -f "${BACKUP_PATH}/.env.backup" ]; then
  cp "${BACKUP_PATH}/.env.backup" "$(dirname "$0")/../.env"
  echo "  [ok] .env restored"
fi

echo "[restore] === Restore complete ==="
echo "  Please restart services: cd .. && docker compose restart"
