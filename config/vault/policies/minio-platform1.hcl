path "kv/data/apps/minio/*" {
  capabilities = ["read"]
}

path "kv/metadata/apps/minio/*" {
  capabilities = ["read", "list"]
}

path "transit/encrypt/project-data-key" {
  capabilities = ["update"]
}

path "transit/decrypt/project-data-key" {
  capabilities = ["update"]
}

path "pki/issue/internal-service" {
  capabilities = ["update"]
}