# Ruling Athena: workgroup skyroute-<env>, configuracion forzada, tope de
# 100 MB escaneados por consulta y resultados en athena-results/ (SSE-S3).
# El lifecycle de 7 dias de athena-results/ vive en generator-landing/bucket.tf
# (un bucket admite una sola aws_s3_bucket_lifecycle_configuration).
resource "aws_athena_workgroup" "this" {
  name        = local.name_prefix
  description = "Workgroup de consultas de comprobacion de ${var.env}."

  #checkov:skip=CKV_AWS_159:SSE-S3 por Ruling Bucket; KMS vetado (foundations/current/plan.md:237).

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = 104857600

    result_configuration {
      output_location = "s3://${var.bucket_name}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}
