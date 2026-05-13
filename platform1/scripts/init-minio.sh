#!/bin/sh
# Initialize MinIO: create buckets and configure lifecycle policies

set -e

MINIO_ALIAS="platform1"
MINIO_URL="https://minio:9000"
MINIO_USER="${MINIO_ROOT_USER:?MINIO_ROOT_USER not set}"
MINIO_PASS="${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD not set}"

echo "[minio-init] Configuring MinIO client..."
mc alias set ${MINIO_ALIAS} ${MINIO_URL} ${MINIO_USER} ${MINIO_PASS} --insecure

echo "[minio-init] Creating buckets..."
BUCKETS="raw-data processed-data model-files evaluation-results archive-data audit-evidence"
for BUCKET in ${BUCKETS}; do
  if mc ls ${MINIO_ALIAS}/${BUCKET} >/dev/null 2>&1; then
    echo "  [skip] Bucket exists: ${BUCKET}"
  else
    mc mb ${MINIO_ALIAS}/${BUCKET}
    echo "  [ok]   Created bucket: ${BUCKET}"
  fi
done

echo "[minio-init] Configuring lifecycle rules..."
# raw-data: 90 days
mc ilm rule add --expire-days 90 ${MINIO_ALIAS}/raw-data 2>/dev/null || true
# processed-data: 180 days
mc ilm rule add --expire-days 180 ${MINIO_ALIAS}/processed-data 2>/dev/null || true
# model-files: 365 days
mc ilm rule add --expire-days 365 ${MINIO_ALIAS}/model-files 2>/dev/null || true
# evaluation-results: 180 days
mc ilm rule add --expire-days 180 ${MINIO_ALIAS}/evaluation-results 2>/dev/null || true
# archive-data: 730 days (2 years)
mc ilm rule add --expire-days 730 ${MINIO_ALIAS}/archive-data 2>/dev/null || true

echo "[minio-init] MinIO setup complete."
mc ls ${MINIO_ALIAS}
