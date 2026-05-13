path "sys/health" {
  capabilities = ["read"]
}

path "sys/mounts" {
  capabilities = ["read"]
}

path "sys/audit" {
  capabilities = ["read", "list"]
}

path "pki/cert/ca" {
  capabilities = ["read"]
}

path "secret/data/platform2/config" {
  capabilities = ["read"]
}

path "transit/keys" {
  capabilities = ["read", "list"]
}
