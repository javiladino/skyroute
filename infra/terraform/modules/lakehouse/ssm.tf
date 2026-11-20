# Clave HMAC del email (Silver events). La clave sale de un recurso efimero y se
# escribe con value_wo: nunca queda en el state ni en el repo. Rotar = subir
# var.hmac_key_version.
ephemeral "random_password" "hmac_email_key" {
  length  = 64
  special = false
}

resource "aws_ssm_parameter" "hmac_email_key" {
  #checkov:skip=CKV_AWS_337:Clave gestionada aws/ssm (SSE de AWS); KMS propio vetado, como en el Ruling Bucket.

  name             = "/skyroute/${var.env}/hmac-email-key"
  description      = "Clave HMAC-SHA256 para seudonimizar el email en Silver (${var.env})."
  type             = "SecureString"
  tier             = "Standard"
  value_wo         = ephemeral.random_password.hmac_email_key.result
  value_wo_version = var.hmac_key_version
}
