#!/bin/sh
# Initialize Vault for Platform 3
# Enables audit logging for compliance tracking

set -e

export VAULT_ADDR="${VAULT_ADDR:-https://vault:8200}"
export VAULT_CACERT="${VAULT_CACERT:-/tls/root-ca.crt}"

echo "[vault-init] Waiting for Vault to be ready..."
for i in $(seq 1 30); do
  if vault status -tls-skip-verify >/dev/null 2>&1; then
    echo "[vault-init] Vault is reachable."
    break
  fi
  sleep 3
done

# Check if already initialized
if vault status -tls-skip-verify 2>/dev/null | grep -q 'Initialized.*true'; then
  echo "[vault-init] Vault already initialized."
  exit 0
fi

# Initialize Vault
echo "[vault-init] Initializing Vault..."
vault operator init -tls-skip-verify -key-shares=1 -key-threshold=1 > /tmp/init-output.json

UNSEAL_KEY=$(grep 'Unseal Key 1' /tmp/init-output.json | awk '{print $NF}')
ROOT_TOKEN=$(grep 'Initial Root Token' /tmp/init-output.json | awk '{print $NF}')

echo "[vault-init] Init output:"
cat /tmp/init-output.json

# Unseal
echo "[vault-init] Unsealing Vault..."
vault operator unseal -tls-skip-verify "$UNSEAL_KEY"

# Login with root token
echo "[vault-init] Logging in with root token..."
vault login -tls-skip-verify "$ROOT_TOKEN"

# Enable audit logging (file backend)
echo "[vault-init] Enabling audit logging..."
vault audit enable -tls-skip-verify file file_path=/vault/data/vault-audit.log 2>/dev/null || echo "  (audit may already be enabled)"

# Save tokens for reference
cp /tmp/init-output.json /vault/data/init-output.json 2>/dev/null || true

echo "[vault-init] Vault initialized for Platform 3."
echo "[vault-init] Root Token: ${ROOT_TOKEN}"
