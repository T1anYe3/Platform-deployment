path "secret/data/platform2/minio/*" {
  capabilities = ["read"]
}

path "secret/metadata/platform2/minio/*" {
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
