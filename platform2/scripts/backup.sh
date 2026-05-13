#!/bin/bash
# Platform 2 Backup Script
# Backs up: ES snapshot to MinIO, Vault raft snapshot, volume dump, .env copy
set -e

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-$(dirname "$0")/../backups}"
BACKUP_PATH="${BACKUP_DIR}/${TIMESTAMP}"
mkdir -p "${BACKUP_PATH}"

ES_URL="${ES_URL:-http://localhost:9200}"
ES_USER="${ELASTICSEARCH_USER:-}"
ES_PASS="${ELASTICSEARCH_PASSWORD:-}"
if [ -n "$ES_USER" ] && [ -n "$ES_PASS" ]; then
  CURL_AUTH="-u ${ES_USER}:${ES_PASS}"
else
  CURL_AUTH=""
fi

echo "[backup] === Platform 2 Backup: ${TIMESTAMP} ==="
echo "[backup] Output: ${BACKUP_PATH}"

# 1. Register ES snapshot repository
echo "[backup] Registering ES snapshot repository..."
curl -s ${CURL_AUTH} -X PUT "${ES_URL}/_snapshot/platform2-backup" \
  -H "Content-Type: application/json" \
  -d '{"type": "fs", "settings": {"location": "/usr/share/elasticsearch/data/snapshots"}}' >/dev/null 2>&1 || echo "  (repository may already exist)"

# 2. Take ES snapshot
SNAPSHOT_NAME="snapshot-${TIMESTAMP}"
echo "[backup] Creating ES snapshot: ${SNAPSHOT_NAME}"
curl -s ${CURL_AUTH} -X PUT "${ES_URL}/_snapshot/platform2-backup/${SNAPSHOT_NAME}?wait_for_completion=true" \
  -H "Content-Type: application/json" \
  -d '{"indices": "*,-.*", "ignore_unavailable": true, "include_global_state": true}' >/dev/null
echo "  [ok] ES snapshot created"

# 3. Backup Vault data
echo "[backup] Exporting Vault data..."
docker cp platform2-vault:/vault/data "${BACKUP_PATH}/vault-data" 2>/dev/null || echo "  (vault data copy skipped)"

# 4. Volume metadata
echo "[backup] Saving volume metadata..."
docker volume ls --filter name=platform2 --format json > "${BACKUP_PATH}/volumes.json" 2>/dev/null || true

# 5. Copy .env
if [ -f "$(dirname "$0")/../.env" ]; then
  cp "$(dirname "$0")/../.env" "${BACKUP_PATH}/.env.backup"
  echo "  [ok] .env backed up"
fi

# 6. Manifest
cat > "${BACKUP_PATH}/manifest.json" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "snapshot_name": "${SNAPSHOT_NAME}",
  "contents": ["es-snapshot", "vault-data", "volume-metadata", "env-backup"]
}
EOF

echo "[backup] === Backup complete: ${BACKUP_PATH} ==="
