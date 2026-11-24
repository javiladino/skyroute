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

  # Rutas de datos por rol (sin scripts/ en escritura: solo lectura). athena-results/ solo
  # lo usa local-data: ningun Glue job consulta Athena.
  s3_prefixes = {
    glue_job = {
      read   = ["landing", "bronze", "silver", "scripts", "glue-temp"]
      write  = ["bronze", "silver", "glue-temp"]
      delete = ["bronze", "silver", "glue-temp"]
    }
    local_data = {
      read   = ["landing", "bronze", "silver", "scripts", "athena-results", "glue-temp"]
      write  = ["bronze", "silver", "athena-results", "glue-temp"]
      delete = ["bronze", "silver", "athena-results", "glue-temp"]
    }
    # dbt lee silver y escribe solo gold y athena-results (el Deny de local_dbt_statements
    # cubre landing, bronze y silver).
    local_dbt = {
      read   = ["silver", "gold", "athena-results"]
      write  = ["gold", "athena-results"]
      delete = ["gold", "athena-results"]
    }
  }

  s3_data_statements = {
    for role, p in local.s3_prefixes : role => [
      {
        Sid      = "DataRead"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = [for x in p.read : "${local.bucket_arn}/${x}/*"]
      },
      {
        Sid      = "DataWrite"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = [for x in p.write : "${local.bucket_arn}/${x}/*"]
      },
      {
        Sid      = "DataDelete"
        Effect   = "Allow"
        Action   = "s3:DeleteObject"
        Resource = [for x in p.delete : "${local.bucket_arn}/${x}/*"]
      },
    ]
  }

  glue_catalog_resources = [
    "${local.glue_arn_prefix}:catalog",
    "${local.glue_arn_prefix}:database/skyroute_${var.env}_*",
    "${local.glue_arn_prefix}:table/skyroute_${var.env}_*/*",
  ]

  # DeleteTable solo en bronze y silver (rebuild_tables); gold queda fuera.
  local_data_delete_table_resources = concat(
    ["${local.glue_arn_prefix}:catalog"],
    flatten([for layer in ["bronze", "silver"] : [
      "${local.glue_arn_prefix}:database/skyroute_${var.env}_${layer}",
      "${local.glue_arn_prefix}:table/skyroute_${var.env}_${layer}/*",
    ]]),
  )

  # Sentencias comunes a glue-job y local-data (sin DeleteTable ni Athena: ver
  # local_data_only_statements).
  common_statements = [
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
      ]
      Resource = local.glue_catalog_resources
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

  # Solo local-data: Spark local puede reconstruir tablas (DeleteTable) y consultar con
  # Athena. Ni los Glue jobs ni el mantenimiento borran tablas ni usan Athena.
  local_data_only_statements = [
    {
      Sid      = "GlueCatalogDeleteTable"
      Effect   = "Allow"
      Action   = "glue:DeleteTable"
      Resource = local.local_data_delete_table_resources
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
  ]

  # Solo local-dbt (Design Decision 12). No usa common_statements ni
  # glue_catalog_resources: ni SSM ni KMS, y Glue acotado por capa. El Deny es
  # explicito porque la boundary concede escritura en bronze y silver.
  local_dbt_statements = concat(
    local.s3_data_statements["local_dbt"],
    [
      {
        Sid      = "BucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = local.bucket_arn
      },
      {
        Sid    = "GlueSilverRead"
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
        ]
        Resource = [
          "${local.glue_arn_prefix}:catalog",
          "${local.glue_arn_prefix}:database/skyroute_${var.env}_silver",
          "${local.glue_arn_prefix}:table/skyroute_${var.env}_silver/*",
        ]
      },
      {
        Sid    = "GlueGoldWrite"
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
          "${local.glue_arn_prefix}:database/skyroute_${var.env}_gold",
          "${local.glue_arn_prefix}:table/skyroute_${var.env}_gold/*",
        ]
      },
      {
        Sid    = "AthenaDbtWorkgroup"
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:StopQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:GetWorkGroup",
        ]
        Resource = aws_athena_workgroup.dbt.arn
      },
      {
        Sid      = "DenyUpstreamS3Write"
        Effect   = "Deny"
        Action   = ["s3:PutObject", "s3:DeleteObject"]
        Resource = [for x in ["landing", "bronze", "silver"] : "${local.bucket_arn}/${x}/*"]
      },
      {
        Sid    = "DenyUpstreamGlueWrite"
        Effect = "Deny"
        Action = ["glue:Create*", "glue:Update*", "glue:Delete*"]
        Resource = flatten([
          for layer in ["bronze", "silver"] : [
            "${local.glue_arn_prefix}:database/skyroute_${var.env}_${layer}",
            "${local.glue_arn_prefix}:table/skyroute_${var.env}_${layer}/*",
          ]
        ])
      },
    ],
  )
}

# Rol que asume Glue para los jobs de demo (Fase 8). Los logs de Glue 5.0 van a los log
# groups por defecto /aws-glue/jobs/error y /aws-glue/jobs/output (doc "Logging behavior
# changes in AWS Glue 5.0"), que la boundary ya permite con /aws-glue/*.
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
    Statement = concat(local.s3_data_statements["glue_job"], local.common_statements, [
      {
        # Acotado a /aws-glue/jobs/* (antes /aws-glue/*): los log groups de Glue 5.0.
        Sid    = "GlueJobLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws-glue/jobs/*",
          "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws-glue/jobs/*:*",
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
    Statement = concat(
      local.s3_data_statements["local_data"],
      local.common_statements,
      local.local_data_only_statements,
      [
        {
          Sid      = "LandingWrite"
          Effect   = "Allow"
          Action   = "s3:PutObject"
          Resource = "${local.bucket_arn}/landing/*"
        },
      ],
    )
  })
}

# Rol para dbt en local (Design Decision 12): misma trust con MFA que local-data,
# sesion de 1 hora y politica propia, sin common_statements (sin SSM ni KMS).
resource "aws_iam_role" "local_dbt" {
  count = var.create_local_dbt_role ? 1 : 0

  name                 = "${local.name_prefix}-local-dbt"
  path                 = "/workload/"
  description          = "Rol de dbt para ejecucion local en ${var.env}; solo ${var.owner_user_name} con MFA."
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

resource "aws_iam_role_policy" "local_dbt" {
  count = var.create_local_dbt_role ? 1 : 0

  name = "local-dbt"
  role = aws_iam_role.local_dbt[0].id

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = local.local_dbt_statements
  })
}
