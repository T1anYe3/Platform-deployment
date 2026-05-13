#!/bin/bash
# Platform 3 Backup Script
# Backs up: ES snapshot, Vault data, volume metadata, .env copy
set -e

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${SCRIPT_DIR}/../backups}"
BACKUP_PATH="${BACKUP_DIR}/${TIMESTAMP}"
mkdir -p "${BACKUP_PATH}"

ES_URL="${ES_URL:-http://localhost:19200}"
ES_USER="${ELASTICSEARCH_USER:-}"
ES_PASS="${ELASTICSEARCH_PASSWORD:-}"
if [ -n "$ES_USER" ] && [ -n "$ES_PASS" ]; then
  CURL_AUTH="-u ${ES_USER}:${ES_PASS}"
else
  CURL_AUTH=""
fi

echo "[backup] === Platform 3 Backup: ${TIMESTAMP} ==="
echo "[backup] Output: ${BACKUP_PATH}"

# 1. Register ES snapshot repository (filesystem)
echo "[backup] Registering ES snapshot repository..."
curl -s ${CURL_AUTH} -X PUT "${ES_URL}/_snapshot/platform3-backup" \
  -H "Content-Type: application/json" \
  -d '{"type": "fs", "settings": {"location": "/usr/share/elasticsearch/data/snapshots"}}' >/dev/null 2>&1 || echo "  (repository may already exist)"

# 2. Take ES snapshot
SNAPSHOT_NAME="snapshot-${TIMESTAMP}"
echo "[backup] Creating ES snapshot: ${SNAPSHOT_NAME}"
curl -s ${CURL_AUTH} -X PUT "${ES_URL}/_snapshot/platform3-backup/${SNAPSHOT_NAME}?wait_for_completion=true" \
  -H "Content-Type: application/json" \
  -d '{"indices": "vault-audit-*,minio-audit-*,nifi-logs-*,safeline-records-*,suricata-alerts-*", "ignore_unavailable": true, "include_global_state": true}' >/dev/null
echo "  [ok] ES snapshot created"

# 3. Backup Vault data
echo "[backup] Exporting Vault data..."
docker cp platform3-vault:/vault/data "${BACKUP_PATH}/vault-data" 2>/dev/null || echo "  (vault data copy skipped - container may not be running)"

# 4. Volume metadata
echo "[backup] Saving volume metadata..."
docker volume ls --filter name=platform3 --format json > "${BACKUP_PATH}/volumes.json" 2>/dev/null || true

# 5. Copy .env
if [ -f "${SCRIPT_DIR}/../.env" ]; then
  cp "${SCRIPT_DIR}/../.env" "${BACKUP_PATH}/.env.backup"
  echo "  [ok] .env backed up"
fi

# 6. Manifest
cat > "${BACKUP_PATH}/manifest.json" << EOF
{
  "timestamp": "$(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S%z')",
  "snapshot_name": "${SNAPSHOT_NAME}",
  "platform": "platform3",
  "contents": ["es-snapshot", "vault-data", "volume-metadata", "env-backup"]
}
EOF

echo "[backup] === Backup complete: ${BACKUP_PATH} ==="
echo "  To restore: bash scripts/restore.sh ${BACKUP_PATH}"
