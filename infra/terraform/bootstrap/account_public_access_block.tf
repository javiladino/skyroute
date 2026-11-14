# Bloqueo publico de S3 a nivel de cuenta (OQ11, S9): CI no puede dejar publico
# un bucket de datos aunque desactive el bloqueo del propio bucket.
resource "aws_s3_account_public_access_block" "this" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
