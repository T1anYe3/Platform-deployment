path "secret/data/platform2/nifi/*" {
  capabilities = ["read"]
}

path "secret/metadata/platform2/nifi/*" {
  capabilities = ["read", "list"]
}

path "transit/encrypt/project-data-key" {
  capabilities = ["update"]
}

path "transit/decrypt/project-data-key" {
  capabilities = ["update"]
}

path "transit/sign/project-sign-key" {
  capabilities = ["update"]
}

path "transit/verify/project-sign-key" {
  capabilities = ["update"]
}

path "pki/issue/internal-service" {
  capabilities = ["update"]
}
