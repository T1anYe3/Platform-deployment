#!/bin/bash
# ==========================================================================
# Platform 3 - Log Cleanup Script
# Deletes ES indices older than the specified retention days.
#
# Usage:
#   bash cleanup-logs.sh [retention_days]
#   bash cleanup-logs.sh 30     # Delete indices older than 30 days
#   bash cleanup-logs.sh 7      # Delete indices older than 7 days
#
# Default retention: 30 days
# ==========================================================================

RETENTION_DAYS="${1:-30}"
ES_URL="${ES_URL:-http://localhost:19200}"

echo "=============================================="
echo "  Platform 3 - Log Cleanup"
echo "  ES URL: ${ES_URL}"
echo "  Retention: ${RETENTION_DAYS} days"
echo "=============================================="
echo ""

# Determine cutoff date
if date -d "${RETENTION_DAYS} days ago" +%Y.%m.%d >/dev/null 2>&1; then
  CUTOFF=$(date -d "${RETENTION_DAYS} days ago" +%Y.%m.%d)
elif date -v-${RETENTION_DAYS}d +%Y.%m.%d >/dev/null 2>&1; then
  CUTOFF=$(date -v-${RETENTION_DAYS}d +%Y.%m.%d)
else
  echo "ERROR: Cannot determine cutoff date."
  exit 1
fi

echo "Cutoff date: ${CUTOFF} (indices before this date will be deleted)"
echo ""

DELETED=0

for prefix in vault-audit minio-audit nifi-logs safeline-records suricata-alerts; do
  echo "--- Checking: ${prefix}-* ---"

  # Get list of indices
  INDICES=$(curl -s "${ES_URL}/_cat/indices/${prefix}-*?h=index" 2>/dev/null | tr -d '\r')

  if [ -z "$INDICES" ]; then
    echo "  No indices found for ${prefix}"
    continue
  fi

  while IFS= read -r idx; do
    [ -z "$idx" ] && continue

    # Extract date from index name (YYYY.MM.DD)
    idx_date=$(echo "$idx" | grep -o '[0-9]\{4\}\.[0-9]\{2\}\.[0-9]\{2\}' | head -1)

    if [ -z "$idx_date" ]; then
      echo "  Skip: ${idx} (no date in name)"
      continue
    fi

    if [ "$idx_date" \< "$CUTOFF" ] || [ "$idx_date" = "$CUTOFF" ]; then
      echo "  DELETE: ${idx} (date: ${idx_date}, older than ${RETENTION_DAYS}d)"
      curl -s -X DELETE "${ES_URL}/${idx}" >/dev/null 2>&1
      DELETED=$((DELETED + 1))
    else
      echo "  Keep:   ${idx} (date: ${idx_date})"
    fi
  done <<< "$INDICES"
done

echo ""
echo "=============================================="
echo "  Cleanup Complete: ${DELETED} indices deleted"
echo "=============================================="
