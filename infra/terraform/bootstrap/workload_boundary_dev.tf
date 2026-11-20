# Permissions boundary de los roles de workload de dev (path /workload/, prefijo
# skyroute-dev-). Sin acceso al bucket de state (Deny explicito).
resource "aws_iam_policy" "workload_boundary_dev" {
  name        = "workload-boundary-dev"
  description = "Permissions boundary de los roles de workload de dev."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Escritura solo en las rutas de datos; scripts/ queda fuera (solo lo
        # escribe ci-apply).
        Sid    = "AllowLakehouseWrite"
        Effect = "Allow"
        Action = "s3:PutObject"
        Resource = [
          "${local.env_arns["dev"].data_bucket}/landing/*",
          "${local.env_arns["dev"].data_bucket}/bronze/*",
          "${local.env_arns["dev"].data_bucket}/silver/*",
          "${local.env_arns["dev"].data_bucket}/athena-results/*",
          "${local.env_arns["dev"].data_bucket}/glue-temp/*",
        ]
      },
      {
        # Lectura de las rutas de datos y de scripts/ (solo lectura).
        Sid    = "AllowLakehouseRead"
        Effect = "Allow"
        Action = "s3:GetObject"
        Resource = [
          "${local.env_arns["dev"].data_bucket}/landing/*",
          "${local.env_arns["dev"].data_bucket}/bronze/*",
          "${local.env_arns["dev"].data_bucket}/silver/*",
          "${local.env_arns["dev"].data_bucket}/scripts/*",
          "${local.env_arns["dev"].data_bucket}/athena-results/*",
          "${local.env_arns["dev"].data_bucket}/glue-temp/*",
        ]
      },
      {
        Sid      = "AllowLakehouseList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = local.env_arns["dev"].data_bucket
      },
      {
        Sid    = "AllowLakehouseDelete"
        Effect = "Allow"
        Action = "s3:DeleteObject"
        Resource = [
          "${local.env_arns["dev"].data_bucket}/bronze/*",
          "${local.env_arns["dev"].data_bucket}/silver/*",
          "${local.env_arns["dev"].data_bucket}/athena-results/*",
          "${local.env_arns["dev"].data_bucket}/glue-temp/*",
        ]
      },
      {
        Sid    = "AllowGlueCatalog"
        Effect = "Allow"
        Action = [
          "glue:Get*",
          "glue:CreateDatabase",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:DeleteTable",
        ]
        Resource = [
          local.env_arns["dev"].glue_catalog,
          local.env_arns["dev"].glue_database,
          local.env_arns["dev"].glue_table,
        ]
      },
      {
        Sid    = "AllowAthenaWorkgroup"
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:StopQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:GetWorkGroup",
        ]
        Resource = local.env_arns["dev"].athena_workgroup
      },
      {
        Sid      = "AllowHmacParameter"
        Effect   = "Allow"
        Action   = "ssm:GetParameter"
        Resource = "arn:aws:ssm:${local.aws_region}:${local.account_id}:parameter/skyroute/dev/hmac-email-key"
      },
      {
        Sid      = "AllowKmsDecryptViaSsm"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = local.kms_via_ssm_service
          }
        }
      },
      {
        # Riesgo aceptado: los log groups por defecto de Glue (/aws-glue/*) son
        # compartidos entre entornos y no admiten prefijo por entorno.
        Sid    = "AllowGlueJobLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws-glue/*",
          "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws-glue/*:*",
        ]
      },
      {
        Sid      = "AllowGeneratorLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${local.env_arns["dev"].log_group}:*"
      },
      {
        Sid      = "AllowGeneratorInvoke"
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = local.env_arns["dev"].function
      },
      {
        Sid      = "DenyStateBucketAccess"
        Effect   = "Deny"
        Action   = "s3:*"
        Resource = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
      },
    ]
  })
}
