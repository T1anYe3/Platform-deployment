#!/bin/sh
# Initialize MinIO for Platform 2: create data lifecycle buckets and configure lifecycle policies

set -e

MINIO_ALIAS="platform2"
MINIO_URL="https://minio:9000"
MINIO_USER="${MINIO_ROOT_USER:?MINIO_ROOT_USER not set}"
MINIO_PASS="${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD not set}"

echo "[minio-init] Configuring MinIO client..."
mc alias set ${MINIO_ALIAS} ${MINIO_URL} ${MINIO_USER} ${MINIO_PASS} --insecure

# All mc commands need --insecure for self-signed TLS certs
MC="mc --insecure"

echo "[minio-init] Creating data lifecycle buckets..."
BUCKETS="raw-data processed-data model-files evaluation-results archive-data audit-evidence"
for BUCKET in ${BUCKETS}; do
  if ${MC} ls ${MINIO_ALIAS}/${BUCKET} >/dev/null 2>&1; then
    echo "  [skip] Bucket exists: ${BUCKET}"
  else
    ${MC} mb ${MINIO_ALIAS}/${BUCKET}
    echo "  [ok]   Created bucket: ${BUCKET}"
  fi
done

echo "[minio-init] Configuring lifecycle rules..."

# raw-data: 90 days (ingested raw data, short retention)
${MC} ilm rule add --expire-days 90 ${MINIO_ALIAS}/raw-data 2>/dev/null || echo "  (lifecycle may already exist for raw-data)"

# processed-data: 180 days (transformed data, medium retention)
${MC} ilm rule add --expire-days 180 ${MINIO_ALIAS}/processed-data 2>/dev/null || echo "  (lifecycle may already exist for processed-data)"

# model-files: 365 days (ML models, long retention)
${MC} ilm rule add --expire-days 365 ${MINIO_ALIAS}/model-files 2>/dev/null || echo "  (lifecycle may already exist for model-files)"

# evaluation-results: 180 days (model evaluation outputs)
${MC} ilm rule add --expire-days 180 ${MINIO_ALIAS}/evaluation-results 2>/dev/null || echo "  (lifecycle may already exist for evaluation-results)"

# archive-data: 730 days (2 years, long-term archive)
${MC} ilm rule add --expire-days 730 ${MINIO_ALIAS}/archive-data 2>/dev/null || echo "  (lifecycle may already exist for archive-data)"

# audit-evidence: try to enable object locking (immutability for compliance)
${MC} mb --with-lock ${MINIO_ALIAS}/audit-evidence 2>/dev/null || echo "  audit-evidence: object locking may not be supported, continuing..."
# Set retention for audit evidence (30 days minimum, governed mode)
${MC} retention set --default GOVERNANCE 30d ${MINIO_ALIAS}/audit-evidence 2>/dev/null || echo "  audit-evidence: retention config skipped (may already be set)"

echo "[minio-init] MinIO setup complete."
${MC} ls ${MINIO_ALIAS}
