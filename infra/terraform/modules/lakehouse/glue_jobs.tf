# Jobs de demo de Glue (Fase 8): Bronze generico y los seis Silver. Glue 5.0 Flex,
# 2 DPU, sin trigger ni schedule (Convention No hourly-billed resources): el owner los
# lanza a mano con `aws glue start-job-run --arguments '{"--run-date":"YYYY-MM-DD"}'`
# (Bronze ademas pide "--source"). El codigo es el mismo que corre en local
# (Ruling "Donde corre Spark").
#
# Scripts como aws_s3_object en scripts/ (Design Decision 11): cada job es su script;
# lib/ y jobs/ viajan en un zip (--extra-py-files) para que `from lib.args import ...`
# funcione igual que en local; los YAML de checks viajan como --extra-files (Glue los
# copia "to the working directory of your script on the driver node", doc "Using job
# parameters in AWS Glue jobs") y --checks-dir "." los lee de ahi; cada job Silver falla al
# arrancar si el YAML no esta (lib.checks.require_rules_file).
#
# PyYAML no viene en Glue 5.0 (doc "Using Python libraries with AWS Glue", lista "Python
# modules already provided", 2026-11-21): los jobs Silver lo instalan con
# --additional-python-modules, con la misma version que spark/requirements.txt.

locals {
  spark_dir     = "${path.module}/../../../../spark"
  scripts_s3    = "s3://${var.bucket_name}/scripts"
  silver_tables = ["bookings_scd2", "bookings_current", "fx_daily", "bookings_eur", "events", "sessions"]

  # Fuentes que viajan en el zip; su hash decide cuando se vuelve a subir (ver spark_libs).
  spark_lib_files = sort(setunion(
    fileset(local.spark_dir, "lib/**/*.py"),
    fileset(local.spark_dir, "jobs/**/*.py"),
  ))

  glue_jobs = merge(
    {
      "bronze-ingest" = {
        script      = "jobs/bronze/ingest.py"
        warehouse   = "bronze"
        extra_files = null
        arguments   = { "--landing-root" = "s3://${var.bucket_name}" }
      }
    },
    {
      for table in local.silver_tables : "silver-${table}" => {
        script      = "jobs/silver/${table}.py"
        warehouse   = "silver"
        extra_files = "${local.scripts_s3}/checks/${table}.yaml"
        arguments = {
          "--checks-dir"                = "."
          "--additional-python-modules" = "PyYAML==6.0.4"
        }
      }
    },
  )
}

# Zip con lib/ y jobs/ (sin tests, checks ni requirements), como el zip del generador.
# El zip se genera en `.terraform/` del root module, en el mismo job que lo sube: los
# workflows terraform-plan y terraform-apply hacen init + plan/apply sin plan guardado
# (`terraform apply -auto-approve` planifica y aplica en el mismo run), asi que la ruta existe.
data "archive_file" "spark_libs" {
  type        = "zip"
  source_dir  = local.spark_dir
  output_path = "${path.root}/.terraform/spark-${var.env}.zip"
  excludes = [
    "tests",
    "tests/**",
    "checks",
    "checks/**",
    "requirements.txt",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.ruff_cache/**",
    "**/.venv/**",
    "**/*.pyc",
  ]
}

# source_hash (no etag): el md5 del zip puede variar entre maquinas (marcas de tiempo, archivos
# locales); el hash de las fuentes .py es el mismo en cualquier checkout y solo sube el zip
# cuando cambia el codigo.
resource "aws_s3_object" "spark_libs" {
  bucket       = var.bucket_name
  key          = "scripts/spark-libs.zip"
  source       = data.archive_file.spark_libs.output_path
  source_hash  = md5(join(",", [for f in local.spark_lib_files : "${f}:${filemd5("${local.spark_dir}/${f}")}"]))
  content_type = "application/zip"
}

resource "aws_s3_object" "job_script" {
  for_each = local.glue_jobs

  bucket       = var.bucket_name
  key          = "scripts/${each.value.script}"
  source       = "${local.spark_dir}/${each.value.script}"
  etag         = filemd5("${local.spark_dir}/${each.value.script}")
  content_type = "text/x-python"
}

resource "aws_s3_object" "check_rules" {
  for_each = toset(local.silver_tables)

  bucket       = var.bucket_name
  key          = "scripts/checks/${each.key}.yaml"
  source       = "${local.spark_dir}/checks/${each.key}.yaml"
  etag         = filemd5("${local.spark_dir}/checks/${each.key}.yaml")
  content_type = "application/yaml"
}

resource "aws_glue_job" "this" {
  #checkov:skip=CKV_AWS_195:S3 y CloudWatch cifran en reposo por defecto; jobs de demo lanzados a mano. La security configuration exige glue:*SecurityConfiguration en bootstrap (deuda, findings.md).
  for_each = local.glue_jobs

  name              = "${local.name_prefix}-${each.key}"
  description       = "Demo Glue Flex de ${each.key} en ${var.env}; se lanza a mano, sin trigger."
  role_arn          = aws_iam_role.glue_job.arn
  glue_version      = "5.0"
  execution_class   = "FLEX"
  worker_type       = "G.1X"
  number_of_workers = 2
  max_retries       = 0
  timeout           = 30 # minutos; tope de gasto si un job se cuelga

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "${local.scripts_s3}/${each.value.script}"
  }

  default_arguments = merge(
    {
      "--job-language"        = "python"
      "--datalake-formats"    = "iceberg"
      "--TempDir"             = "s3://${var.bucket_name}/glue-temp/"
      "--extra-py-files"      = "${local.scripts_s3}/spark-libs.zip"
      "--env"                 = var.env
      "--catalog-name"        = "skyroute"
      "--catalog-impl"        = "glue"
      "--warehouse"           = "s3://${var.bucket_name}/${each.value.warehouse}"
      "--region"              = local.region
      "--jars-packages"       = "none" # Glue 5.0 ya trae los jars de Iceberg
      "--enable-metrics"      = "true"
      "--enable-spark-ui"     = "false"
      "--job-bookmark-option" = "job-bookmark-disable"
      # Las extensiones de Iceberg son estaticas: han de estar antes de crear la sesion.
      "--conf" = "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions --conf spark.sql.session.timeZone=UTC"
    },
    each.value.extra_files == null ? {} : { "--extra-files" = each.value.extra_files },
    each.value.arguments,
  )

  # Los objetos de scripts/ deben existir antes de que el job pueda lanzarse.
  depends_on = [
    aws_s3_object.spark_libs,
    aws_s3_object.job_script,
    aws_s3_object.check_rules,
    aws_iam_role_policy.glue_job,
  ]
}
