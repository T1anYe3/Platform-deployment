ui = true

listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_disable   = 0
  tls_cert_file = "/vault/tls/vault/vault.crt"
  tls_key_file  = "/vault/tls/vault/vault.key"
}

storage "file" {
  path = "/vault/data"
}

api_addr      = "https://0.0.0.0:8200"
disable_mlock = true
