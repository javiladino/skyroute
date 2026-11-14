locals {
  function_name = "${local.name_prefix}-generator"
}

# Zip unico desde generators/ (raiz del repo desde modules/generator-landing),
# sin tests ni piezas locales. El handler importa como lo hara Lambda (A12).
data "archive_file" "generator" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../generators"
  output_path = "${path.root}/.terraform/generator-${var.env}.zip"
  excludes = [
    "tests",
    "ota/seed_postgres.py",
    "verify_landing.py",
    "__pycache__",
    "ota/__pycache__",
  ]
}

# El log group se declara antes que la funcion: el rol de ejecucion no tiene
# logs:CreateLogGroup (boundary), asi que Lambda no puede crearlo.
resource "aws_cloudwatch_log_group" "generator" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 14

  #checkov:skip=CKV_AWS_158:Sin KMS, vetado por la Convention No hourly-billed resources y foundations/current/plan.md:237.
  #checkov:skip=CKV_AWS_338:Retención de 14 días por Ruling Schedule, no 1 año; son logs de un generador sintético.
}

# Sin concurrencia reservada: Ruling Implement decisions (2026-11-14),
# la cuota de la cuenta es 10 y la PR-Q (Fase 11) lo restaura a 1.
resource "aws_lambda_function" "generator" {
  function_name    = local.function_name
  role             = aws_iam_role.generator_exec.arn
  runtime          = "python3.13"
  handler          = "lambda_handler.handler"
  architectures    = [var.architecture]
  timeout          = var.backfill_timeout
  memory_size      = 256
  filename         = data.archive_file.generator.output_path
  source_code_hash = data.archive_file.generator.output_base64sha256

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.data.bucket
    }
  }

  #checkov:skip=CKV_AWS_117:Sin VPC por la Convention No hourly-billed resources.
  #checkov:skip=CKV_AWS_116:Sin DLQ: RetryPolicy acotada en el Scheduler y regeneración determinista de los datos.
  #checkov:skip=CKV_AWS_173:Sin variables de entorno secretas (solo el nombre del bucket); KMS vetado.
  #checkov:skip=CKV_AWS_272:Sin code signing: coste y complejidad fuera de alcance del portfolio.
  #checkov:skip=CKV_AWS_50:Sin X-Ray: no hay trazas distribuidas que analizar.
  #checkov:skip=CKV_AWS_115:Sin concurrencia reservada: la cuota de la cuenta es 10 (Ruling Implement decisions); la PR-Q la restaura.

  depends_on = [
    aws_cloudwatch_log_group.generator,
    aws_iam_role_policy.generator_exec,
  ]
}

# Los unicos reintentos son los del Scheduler: la funcion no reintenta.
resource "aws_lambda_function_event_invoke_config" "generator" {
  function_name                = aws_lambda_function.generator.function_name
  maximum_retry_attempts       = 0
  maximum_event_age_in_seconds = 900
}
