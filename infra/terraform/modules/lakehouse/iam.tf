# Roles de workload del lakehouse (Ruling Boundary): path /workload/, nombre
# skyroute-<env>-* y permissions_boundary = workload-boundary-<env>. Solo
# aws_iam_role_policy (inline): iam:CreatePolicy e iam:AttachRolePolicy estan
# denegados a CI. Cada inline queda dentro de la boundary: ningun Allow pide
# una accion o ruta que workload-boundary-<env> no conceda.

locals {
  workload_boundary_arn = "arn:aws:iam::${local.account_id}:policy/workload-boundary-${var.env}"
  owner_user_arn        = "arn:aws:iam::${local.account_id}:user/${var.owner_user_name}"

  glue_arn_prefix = "arn:aws:glue:${local.region}:${local.account_id}"
  hmac_param_arn  = "arn:aws:ssm:${local.region}:${local.account_id}:parameter/skyroute/${var.env}/hmac-email-key"

  # Rutas de datos (sin scripts/: solo lectura).
  read_prefixes   = ["landing", "bronze", "silver", "scripts", "athena-results", "glue-temp"]
  write_prefixes  = ["bronze", "silver", "athena-results", "glue-temp"]
  delete_prefixes = ["bronze", "silver", "athena-results", "glue-temp"]

  # Sentencias comunes a glue-job y local-data.
  common_statements = [
    {
      Sid      = "DataRead"
      Effect   = "Allow"
      Action   = "s3:GetObject"
      Resource = [for p in local.read_prefixes : "${local.bucket_arn}/${p}/*"]
    },
    {
      Sid      = "DataWrite"
      Effect   = "Allow"
      Action   = "s3:PutObject"
      Resource = [for p in local.write_prefixes : "${local.bucket_arn}/${p}/*"]
    },
    {
      Sid      = "DataDelete"
      Effect   = "Allow"
      Action   = "s3:DeleteObject"
      Resource = [for p in local.delete_prefixes : "${local.bucket_arn}/${p}/*"]
    },
    {
      # Riesgo aceptado: ListBucket sin condicion s3:prefix. Solo lista las
      # claves del bucket de su propio entorno y Spark/Iceberg necesitan listar.
      Sid      = "BucketList"
      Effect   = "Allow"
      Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
      Resource = local.bucket_arn
    },
    {
      Sid    = "GlueCatalog"
      Effect = "Allow"
      Action = [
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetTable",
        "glue:GetTables",
        "glue:GetTableVersion",
        "glue:GetTableVersions",
        "glue:GetPartition",
        "glue:GetPartitions",
        "glue:CreateTable",
        "glue:UpdateTable",
        "glue:DeleteTable",
      ]
      Resource = [
        "${local.glue_arn_prefix}:catalog",
        "${local.glue_arn_prefix}:database/skyroute_${var.env}_*",
        "${local.glue_arn_prefix}:table/skyroute_${var.env}_*/*",
      ]
    },
    {
      Sid    = "AthenaWorkgroup"
      Effect = "Allow"
      Action = [
        "athena:StartQueryExecution",
        "athena:StopQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:GetWorkGroup",
      ]
      Resource = aws_athena_workgroup.this.arn
    },
    {
      Sid      = "HmacParameter"
      Effect   = "Allow"
      Action   = "ssm:GetParameter"
      Resource = local.hmac_param_arn
    },
    {
      # El parametro es SecureString con aws/ssm: solo se descifra via SSM y
      # solo para el parametro HMAC (contexto de cifrado PARAMETER_ARN).
      Sid      = "KmsDecryptViaSsm"
      Effect   = "Allow"
      Action   = "kms:Decrypt"
      Resource = "*"
      Condition = {
        StringEquals = {
          "kms:ViaService"                      = "ssm.${local.region}.amazonaws.com"
          "kms:EncryptionContext:PARAMETER_ARN" = local.hmac_param_arn
        }
      }
    },
  ]
}

# Rol que asume Glue para los jobs de demo (Fase 8). Los logs usan los log
# groups por defecto /aws-glue/*, que la boundary ya permite.
resource "aws_iam_role" "glue_job" {
  name                 = "${local.name_prefix}-glue-job"
  path                 = "/workload/"
  description          = "Rol de ejecucion de los Glue jobs de ${var.env}."
  permissions_boundary = local.workload_boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "glue.amazonaws.com" }
        Action    = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "${local.glue_arn_prefix}:job/${local.name_prefix}-*"
          }
        }
      },
    ]
  })
}

resource "aws_iam_role_policy" "glue_job" {
  name = "glue-job"
  role = aws_iam_role.glue_job.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.common_statements, [
      {
        Sid    = "GlueJobLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws-glue/*",
          "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws-glue/*:*",
        ]
      },
    ])
  })
}

# Rol para Spark, export y FX en local (Ruling "Credenciales en local"): solo el
# usuario del owner, con MFA y sesion de 1 hora. Es el unico rol que escribe en
# landing/ (export de Reservas y FX).
resource "aws_iam_role" "local_data" {
  count = var.create_local_data_role ? 1 : 0

  name                 = "${local.name_prefix}-local-data"
  path                 = "/workload/"
  description          = "Rol de datos para ejecucion local en ${var.env}; solo ${var.owner_user_name} con MFA."
  permissions_boundary = local.workload_boundary_arn
  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { AWS = local.owner_user_arn }
        Action    = "sts:AssumeRole"
        Condition = {
          Bool = {
            "aws:MultiFactorAuthPresent" = "true"
          }
          NumericLessThan = {
            "aws:MultiFactorAuthAge" = "3600"
          }
        }
      },
    ]
  })
}

resource "aws_iam_role_policy" "local_data" {
  count = var.create_local_data_role ? 1 : 0

  name = "local-data"
  role = aws_iam_role.local_data[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.common_statements, [
      {
        Sid      = "LandingWrite"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${local.bucket_arn}/landing/*"
      },
    ])
  })
}
