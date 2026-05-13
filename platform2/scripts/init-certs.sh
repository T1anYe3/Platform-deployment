#!/bin/sh
# Generate TLS certificates for Platform 2 Docker deployment
# Certificates include SANs for localhost, 127.0.0.1, and Docker service names

set -e

TLS_DIR="/tls"
ROOT_CA="${TLS_DIR}/root-ca"
SERVICES="vault nifi minio"

echo "[cert-init] Generating Platform 2 Root CA..."
mkdir -p "${TLS_DIR}"

# Generate Root CA
openssl genrsa -out "${ROOT_CA}.key" 4096
openssl req -x509 -new -nodes \
  -key "${ROOT_CA}.key" \
  -sha256 -days 3650 \
  -subj "/C=CN/ST=Platform/L=Lab/O=Platform2/CN=platform2-root-ca" \
  -out "${ROOT_CA}.crt"

echo "01" > "${ROOT_CA}.srl"

# Generate service certificates
for SVC in ${SERVICES}; do
  echo "[cert-init] Generating certificate for: ${SVC}"

  SVC_DIR="${TLS_DIR}/${SVC}"
  mkdir -p "${SVC_DIR}"

  # Generate private key
  openssl genrsa -out "${SVC_DIR}/${SVC}.key" 2048

  # Create CSR
  openssl req -new \
    -key "${SVC_DIR}/${SVC}.key" \
    -subj "/C=CN/ST=Platform/L=Lab/O=Platform2/CN=${SVC}.sec.local" \
    -out "${SVC_DIR}/${SVC}.csr"

  # Create SAN extensions file
  cat > "${SVC_DIR}/${SVC}.ext" << EXTEOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,nonRepudiation,keyEncipherment,dataEncipherment
subjectAltName=DNS:${SVC},DNS:localhost,IP:127.0.0.1,IP:0.0.0.0
EXTEOF

  # Sign with Root CA
  openssl x509 -req \
    -in "${SVC_DIR}/${SVC}.csr" \
    -CA "${ROOT_CA}.crt" \
    -CAkey "${ROOT_CA}.key" \
    -CAserial "${ROOT_CA}.srl" \
    -out "${SVC_DIR}/${SVC}.crt" \
    -days 3650 -sha256 \
    -extfile "${SVC_DIR}/${SVC}.ext"
done

# MinIO requires specific filenames: public.crt + private.key at TLS root
# MinIO auto-detects certs at ${HOME}/.minio/certs/ (HOME=/root → /root/.minio/certs/)
# Generate MinIO certs directly to root level to ensure correct permissions (private key must be 0600)
openssl genrsa -out "${TLS_DIR}/private.key" 2048
openssl req -new \
  -key "${TLS_DIR}/private.key" \
  -subj "/C=CN/ST=Platform/L=Lab/O=Platform2/CN=minio.sec.local" \
  -out "${TLS_DIR}/minio-tmp.csr"
cat > "${TLS_DIR}/minio-tmp.ext" << EXTEOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,nonRepudiation,keyEncipherment,dataEncipherment
subjectAltName=DNS:minio,DNS:localhost,IP:127.0.0.1,IP:0.0.0.0
EXTEOF
openssl x509 -req \
  -in "${TLS_DIR}/minio-tmp.csr" \
  -CA "${ROOT_CA}.crt" \
  -CAkey "${ROOT_CA}.key" \
  -CAserial "${ROOT_CA}.srl" \
  -out "${TLS_DIR}/public.crt" \
  -days 3650 -sha256 \
  -extfile "${TLS_DIR}/minio-tmp.ext"
rm -f "${TLS_DIR}/minio-tmp.csr" "${TLS_DIR}/minio-tmp.ext"
# Remove minio/ subdirectory (no longer needed; contains duplicate cert with IP SANs)
rm -rf "${TLS_DIR}/minio"
# Enforce correct permissions (MinIO requires private.key to be 0600, not world-readable)
chmod 600 "${TLS_DIR}/private.key"
chmod 600 "${TLS_DIR}/root-ca.key"
chmod 644 "${TLS_DIR}/public.crt"
chmod 644 "${TLS_DIR}/root-ca.crt"

echo "[cert-init] All certificates generated successfully."
ls -la ${TLS_DIR}/
ls -la ${TLS_DIR}/*/
