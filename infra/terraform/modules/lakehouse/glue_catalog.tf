# Convention Medallion layers: bases Glue por entorno skyroute_<env>_<capa>.
# gold queda fuera: lo crea la fase de dbt.
locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = "eu-west-3"
  name_prefix = "skyroute-${var.env}"
  bucket_arn  = "arn:aws:s3:::${var.bucket_name}"

  databases = toset(["bronze", "silver", "ops"])
}

data "aws_caller_identity" "current" {}

resource "aws_glue_catalog_database" "layer" {
  for_each = local.databases

  name        = "skyroute_${var.env}_${each.key}"
  description = "Capa ${each.key} del lakehouse de ${var.env}."
}
