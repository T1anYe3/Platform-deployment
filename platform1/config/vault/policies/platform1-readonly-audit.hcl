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

path "transit/keys" {
  capabilities = ["read", "list"]
}