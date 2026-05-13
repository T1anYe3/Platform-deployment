#!/bin/sh
# Initialize Vault: unseal, enable engines, apply policies
# Note: does NOT use 'set -e' because vault CLI returns non-zero for sealed state

VAULT_ADDR="https://vault:8200"
VAULT_CACERT="/tls/root-ca.crt"
VAULT_INIT_FILE="/vault/data/init-output.json"

export VAULT_ADDR
export VAULT_CACERT

echo "[vault-init] Waiting for Vault to be reachable..."
READY=false
for i in $(seq 1 30); do
  OUT=$(vault status -tls-skip-verify -format=json 2>/dev/null) || true
  if echo "$OUT" | grep -q '"initialized"'; then
    echo "[vault-init] Vault is reachable (i=$i)."
    READY=true
    break
  fi
  sleep 3
done

if [ "$READY" != "true" ]; then
  echo "[vault-init] ERROR: Vault did not become reachable. Aborting."
  exit 1
fi

# Check if already initialized
if echo "$OUT" | grep -q '"initialized" *: *true'; then
  echo "[vault-init] Vault already initialized."
  if echo "$OUT" | grep -q '"sealed" *: *true'; then
    echo "[vault-init] Vault is sealed. Attempting unseal..."
    if [ -f "${VAULT_INIT_FILE}" ]; then
      UNSEAL_KEY=$(grep -o '"unseal_keys_b64" *: *\[ *"[^"]*"' "${VAULT_INIT_FILE}" | sed 's/.*"\([^"]*\)".*/\1/')
      echo "[vault-init] Got unseal key from ${VAULT_INIT_FILE}"
      wget -q -O - --no-check-certificate --header="Content-Type: application/json" --post-data="{\"key\":\"${UNSEAL_KEY}\"}" https://vault:8200/v1/sys/unseal || true
    else
      echo "[vault-init] WARNING: ${VAULT_INIT_FILE} not found, cannot auto-unseal."
    fi
  fi
  exit 0
fi

echo "[vault-init] Initializing Vault..."
vault operator init -tls-skip-verify -key-shares=1 -key-threshold=1 -format=json > "${VAULT_INIT_FILE}"

UNSEAL_KEY=$(grep -A1 '"unseal_keys_b64"' "${VAULT_INIT_FILE}" | tail -1 | sed 's/.*"\([^"]*\)".*/\1/')
ROOT_TOKEN=$(grep '"root_token"' "${VAULT_INIT_FILE}" | sed 's/.*"\([^"]*\)".*/\1/')

echo "[vault-init] Unsealing Vault via API..."
wget -q -O - --no-check-certificate --header="Content-Type: application/json" --post-data="{\"key\":\"${UNSEAL_KEY}\"}" https://vault:8200/v1/sys/unseal

export VAULT_TOKEN="$ROOT_TOKEN"

echo "[vault-init] Enabling PKI secrets engine..."
vault secrets enable -tls-skip-verify pki 2>/dev/null || true

echo "[vault-init] Enabling Transit secrets engine..."
vault secrets enable -tls-skip-verify transit 2>/dev/null || true

echo "[vault-init] Enabling KV v2 secrets engine..."
vault secrets enable -tls-skip-verify -path=secret kv-v2 2>/dev/null || true

echo "[vault-init] Applying ACL policies..."
for policy in /vault/config/policies/*.hcl; do
  name=$(basename "$policy" .hcl)
  vault policy write -tls-skip-verify "$name" "$policy" 2>/dev/null && echo "  Policy: $name" || echo "  Policy: $name (already exists?)"
done

echo "[vault-init] Enabling audit logging..."
vault audit enable -tls-skip-verify file file_path=/vault/data/audit.log 2>/dev/null || true

echo "[vault-init] Vault initialization complete."
echo "  Root token: ${ROOT_TOKEN}"
