#!/bin/sh
# Generate TLS certificates for Platform 1 Docker deployment
# Certificates include SANs for localhost, 127.0.0.1, and Docker service names

set -e

TLS_DIR="/tls"
ROOT_CA="${TLS_DIR}/root-ca"
SERVICES="vault nifi minio"

echo "[cert-init] Generating Platform 1 Root CA..."
mkdir -p "${TLS_DIR}"

# Generate Root CA
openssl genrsa -out "${ROOT_CA}.key" 4096
openssl req -x509 -new -nodes \
  -key "${ROOT_CA}.key" \
  -sha256 -days 3650 \
  -subj "/C=CN/ST=Platform/L=Lab/O=Platform1/CN=platform1-root-ca" \
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
    -subj "/C=CN/ST=Platform/L=Lab/O=Platform1/CN=${SVC}.sec.local" \
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

# MinIO requires specific filenames: public.crt + private.key
cp "${TLS_DIR}/minio/minio.crt" "${TLS_DIR}/minio/public.crt"
cp "${TLS_DIR}/minio/minio.key" "${TLS_DIR}/minio/private.key"

echo "[cert-init] All certificates generated successfully."
ls -la ${TLS_DIR}/*/
