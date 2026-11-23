data "aws_caller_identity" "current" {}

locals {
  account_id             = data.aws_caller_identity.current.account_id
  aws_region             = "eu-west-3"
  ci_plan_role_arn       = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/ci-plan"
  ci_apply_dev_role_arn  = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/ci-apply-dev"
  ci_apply_prod_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/ci-apply-prod"
  ci_boundary_arn        = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/ci-boundary"

  workload_boundary_dev_arn  = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/workload-boundary-dev"
  workload_boundary_prod_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/workload-boundary-prod"

  # ARN exactos por servicio y entorno (proposal, Comunes). Los usan la boundary
  # comun, los roles de apply y las boundaries de workload.
  env_arns = {
    for env in ["dev", "prod"] : env => {
      data_bucket       = "arn:aws:s3:::skyroute-${env}-data-${data.aws_caller_identity.current.account_id}"
      function          = "arn:aws:lambda:${local.aws_region}:${data.aws_caller_identity.current.account_id}:function:skyroute-${env}-generator"
      function_pattern  = "arn:aws:lambda:${local.aws_region}:${data.aws_caller_identity.current.account_id}:function:skyroute-${env}-*"
      schedule          = "arn:aws:scheduler:${local.aws_region}:${data.aws_caller_identity.current.account_id}:schedule/default/skyroute-${env}-generator"
      workload_roles    = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/workload/skyroute-${env}-*"
      log_group         = "arn:aws:logs:${local.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/skyroute-${env}-generator"
      topic             = "arn:aws:sns:${local.aws_region}:${data.aws_caller_identity.current.account_id}:skyroute-${env}-*"
      alarm             = "arn:aws:cloudwatch:${local.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:skyroute-${env}-*"
      workload_boundary = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/workload-boundary-${env}"

      # Lakehouse (Fase 3, Design Decisions 11-13). Las bases de Glue son por
      # entorno (skyroute_<env>_{bronze,silver,gold,ops}, Convention "Medallion
      # layers"); jobs, workgroup, parametro y rol tambien llevan el entorno.
      glue_catalog     = "arn:aws:glue:${local.aws_region}:${data.aws_caller_identity.current.account_id}:catalog"
      glue_database    = "arn:aws:glue:${local.aws_region}:${data.aws_caller_identity.current.account_id}:database/skyroute_${env}_*"
      glue_table       = "arn:aws:glue:${local.aws_region}:${data.aws_caller_identity.current.account_id}:table/skyroute_${env}_*/*"
      glue_job         = "arn:aws:glue:${local.aws_region}:${data.aws_caller_identity.current.account_id}:job/skyroute-${env}-*"
      athena_workgroup = "arn:aws:athena:${local.aws_region}:${data.aws_caller_identity.current.account_id}:workgroup/skyroute-${env}"
      # Workgroup de dbt (Fase 4, Ruling "Plan decisions"): ARN exacto, sin comodin.
      athena_workgroup_dbt = "arn:aws:athena:${local.aws_region}:${data.aws_caller_identity.current.account_id}:workgroup/skyroute-${env}-dbt"
      ssm_parameter        = "arn:aws:ssm:${local.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/skyroute/${env}/*"
      hmac_key             = "arn:aws:ssm:${local.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/skyroute/${env}/hmac-email-key"
      glue_job_role        = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/workload/skyroute-${env}-glue-job"
      scripts_objects      = "arn:aws:s3:::skyroute-${env}-data-${data.aws_caller_identity.current.account_id}/scripts/*"
    }
  }

  # Clave gestionada aws/ssm: DescribeKey se acota por alias, no por ARN de clave.
  kms_ssm_alias       = ["alias/aws/ssm"]
  kms_via_ssm_service = "ssm.${local.aws_region}.amazonaws.com"
  # Variables de entorno de Lambda cifradas con la clave aws/lambda: el contexto
  # de cifrado lleva el ARN de la funcion.
  kms_via_lambda_service = "lambda.${local.aws_region}.amazonaws.com"
  kms_lambda_fn_context  = "kms:EncryptionContext:aws:lambda:FunctionArn"
  scripts_objects_read   = [local.env_arns["dev"].scripts_objects, local.env_arns["prod"].scripts_objects]

  # Objetos de state que ci-plan lee (StateRead); DenyDataObjectRead los exime.
  ci_plan_state_read_arns = [
    "${aws_s3_bucket.state.arn}/envs/dev/terraform.tfstate",
    "${aws_s3_bucket.state.arn}/envs/prod/terraform.tfstate",
  ]

  # Todos los logs de la region: DescribeLogGroups evalua este recurso.
  log_groups_all_arn = "arn:aws:logs:${local.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:*"

  # Roles y OIDC que ningun rol de CI puede modificar.
  ci_protected_arns = [
    local.ci_plan_role_arn,
    local.ci_apply_dev_role_arn,
    local.ci_apply_prod_role_arn,
    aws_iam_openid_connect_provider.github.arn,
  ]

  owner_identity_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/skyroute-dev",
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:group/admins",
  ]

  # Acciones IAM de ci-apply-<env> sobre roles de workload (S2): enumeradas, sin
  # iam:*, sin AttachRolePolicy, CreatePolicy ni PutRolePermissionsBoundary.
  workload_role_actions = [
    "iam:CreateRole",
    "iam:DeleteRole",
    "iam:GetRole",
    "iam:UpdateRole",
    "iam:TagRole",
    "iam:UntagRole",
    "iam:ListRoleTags",
    "iam:PutRolePolicy",
    "iam:GetRolePolicy",
    "iam:DeleteRolePolicy",
    "iam:ListRolePolicies",
    "iam:ListAttachedRolePolicies",
    "iam:ListInstanceProfilesForRole",
  ]

  # Servicios a los que se puede pasar un rol de workload (techo y Deny).
  pass_role_services = ["lambda.amazonaws.com", "scheduler.amazonaws.com", "glue.amazonaws.com"]

  # Servicios del generador: ci-apply-<env> los usa para el Allow sobre los roles
  # de workload en general. Glue solo recibe el rol skyroute-<env>-glue-job.
  pass_role_services_generator = ["lambda.amazonaws.com", "scheduler.amazonaws.com"]

  # Acciones de iam sobre roles ajenos al workload que se deniegan siempre (b).
  role_write_actions = [
    "iam:UpdateAssumeRolePolicy",
    "iam:PutRolePolicy",
    "iam:AttachRolePolicy",
    "iam:DetachRolePolicy",
    "iam:DeleteRolePolicy",
    "iam:CreatePolicy",
    "iam:PassRole",
  ]

  # Acciones concretas de ci-apply-<env> por servicio. Las mismas listas las usan
  # las inline de ci_apply_dev.tf y ci_apply_prod.tf; la boundary comun solo fija
  # el techo por servicio y recurso.
  apply_s3_actions = [
    "s3:CreateBucket",
    "s3:DeleteBucket",
    "s3:ListBucket",
    "s3:GetBucketLocation",
    "s3:GetBucketAcl",
    "s3:GetBucketCors",
    "s3:GetBucketWebsite",
    "s3:GetBucketLogging",
    "s3:GetBucketVersioning",
    "s3:GetBucketTagging",
    "s3:GetBucketRequestPayment",
    "s3:GetAccelerateConfiguration",
    "s3:GetBucketObjectLockConfiguration",
    "s3:GetReplicationConfiguration",
    "s3:GetBucketPolicy",
    "s3:GetLifecycleConfiguration",
    "s3:GetEncryptionConfiguration",
    "s3:GetBucketPublicAccessBlock",
    "s3:GetBucketOwnershipControls",
    "s3:PutBucketTagging",
    "s3:PutBucketPolicy",
    "s3:DeleteBucketPolicy",
    "s3:PutEncryptionConfiguration",
    "s3:PutBucketPublicAccessBlock",
    "s3:PutBucketOwnershipControls",
    "s3:PutLifecycleConfiguration",
  ]

  apply_lambda_actions = [
    "lambda:CreateFunction",
    "lambda:DeleteFunction",
    "lambda:GetFunction",
    "lambda:GetFunctionConfiguration",
    "lambda:UpdateFunctionConfiguration",
    "lambda:UpdateFunctionCode",
    "lambda:GetFunctionCodeSigningConfig",
    "lambda:ListVersionsByFunction",
    "lambda:GetPolicy",
    "lambda:TagResource",
    "lambda:UntagResource",
    "lambda:ListTags",
    "lambda:PutFunctionConcurrency",
    "lambda:DeleteFunctionConcurrency",
    "lambda:GetFunctionConcurrency",
    "lambda:PutFunctionEventInvokeConfig",
    "lambda:UpdateFunctionEventInvokeConfig",
    "lambda:GetFunctionEventInvokeConfig",
    "lambda:DeleteFunctionEventInvokeConfig",
  ]

  apply_scheduler_actions = [
    "scheduler:CreateSchedule",
    "scheduler:UpdateSchedule",
    "scheduler:DeleteSchedule",
    "scheduler:GetSchedule",
  ]

  apply_logs_actions = [
    "logs:CreateLogGroup",
    "logs:DeleteLogGroup",
    "logs:PutRetentionPolicy",
    "logs:DeleteRetentionPolicy",
    "logs:TagResource",
    "logs:UntagResource",
    "logs:ListTagsForResource",
    "logs:ListTagsLogGroup",
  ]

  apply_sns_actions = [
    "sns:CreateTopic",
    "sns:DeleteTopic",
    "sns:GetTopicAttributes",
    "sns:SetTopicAttributes",
    "sns:Subscribe",
    "sns:Unsubscribe",
    "sns:GetSubscriptionAttributes",
    "sns:SetSubscriptionAttributes",
    "sns:ListSubscriptionsByTopic",
    "sns:ListTagsForResource",
    "sns:TagResource",
    "sns:UntagResource",
  ]

  apply_cloudwatch_actions = [
    "cloudwatch:PutMetricAlarm",
    "cloudwatch:DeleteAlarms",
    "cloudwatch:DescribeAlarms",
    "cloudwatch:ListTagsForResource",
    "cloudwatch:TagResource",
    "cloudwatch:UntagResource",
  ]

  apply_glue_actions = [
    "glue:CreateDatabase",
    "glue:GetDatabase",
    "glue:UpdateDatabase",
    "glue:DeleteDatabase",
    "glue:DeleteTable",
    "glue:CreateJob",
    "glue:GetJob",
    "glue:UpdateJob",
    "glue:DeleteJob",
    "glue:GetTags",
    "glue:TagResource",
    "glue:UntagResource",
  ]

  apply_athena_actions = [
    "athena:CreateWorkGroup",
    "athena:GetWorkGroup",
    "athena:UpdateWorkGroup",
    "athena:DeleteWorkGroup",
    "athena:ListTagsForResource",
    "athena:TagResource",
    "athena:UntagResource",
  ]

  apply_ssm_actions = [
    "ssm:PutParameter",
    "ssm:GetParameter",
    "ssm:DeleteParameter",
    "ssm:ListTagsForResource",
    "ssm:AddTagsToResource",
    "ssm:RemoveTagsFromResource",
  ]

  # Escritura de un SecureString con la clave aws/ssm. kms:Decrypt no va aqui:
  # solo se concede acotado al parametro HMAC (ver PlanKmsDecryptHmac y
  # ApplyKmsDecryptHmac).
  apply_kms_via_ssm_actions = ["kms:Encrypt", "kms:GenerateDataKey"]

  apply_scripts_actions = [
    "s3:PutObject",
    "s3:GetObject",
    "s3:DeleteObject",
    "s3:GetObjectTagging",
    "s3:PutObjectTagging",
  ]
}

# Permissions boundary comun a ci-plan, ci-apply-dev y ci-apply-prod: techo de backend del state
# (solo envs/dev y envs/prod, nunca bootstrap/), techo por servicio y ARN de los
# dos entornos (el aislamiento por entorno lo dan cada inline y el Deny de D2) y
# los mismos Deny que los roles. Los comodines por servicio de
# AllowWorkloadServices son solo techo: caben en el limite de 6.144 caracteres de
# una managed policy; las acciones concretas estan en las inline.
resource "aws_iam_policy" "ci_boundary" {
  name = "ci-boundary"
  # La description de una aws_iam_policy es inmutable en IAM: cambiarla fuerza
  # replacement de la boundary. Se conserva el texto original aunque mencione
  # ci-apply, retirado en la Fase 7.
  description = "Permissions boundary de los roles de CI (ci-plan, ci-apply)."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowStateBucketList"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.state.arn
      },
      {
        Sid    = "AllowStateObjects"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = [
          "${aws_s3_bucket.state.arn}/envs/dev/terraform.tfstate",
          "${aws_s3_bucket.state.arn}/envs/dev/terraform.tfstate.tflock",
          "${aws_s3_bucket.state.arn}/envs/prod/terraform.tfstate",
          "${aws_s3_bucket.state.arn}/envs/prod/terraform.tfstate.tflock",
        ]
      },
      {
        Sid    = "AllowWorkloadServices"
        Effect = "Allow"
        Action = ["s3:*", "lambda:*", "scheduler:*", "logs:*", "sns:*", "cloudwatch:*"]
        # Buckets exactos; el resto con el entorno como comodin (skyroute-*-...) para
        # liberar espacio en la boundary (Design Decision 13). El aislamiento por
        # entorno lo dan las inline y los Deny.
        Resource = [
          local.env_arns["dev"].data_bucket,
          local.env_arns["prod"].data_bucket,
          "arn:aws:lambda:${local.aws_region}:${local.account_id}:function:skyroute-*-generator",
          "arn:aws:scheduler:${local.aws_region}:${local.account_id}:schedule/default/skyroute-*-generator",
          "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws/lambda/skyroute-*-generator",
          "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws/lambda/skyroute-*-generator:*",
          "arn:aws:sns:${local.aws_region}:${local.account_id}:skyroute-*",
          "arn:aws:cloudwatch:${local.aws_region}:${local.account_id}:alarm:skyroute-*",
        ]
      },
      {
        # Techo del lakehouse agrupado con comodines para caber en 6.144
        # caracteres (Design Decision 13); las acciones concretas estan en las inline.
        Sid    = "AllowLakehouse"
        Effect = "Allow"
        Action = ["glue:*", "athena:*", "ssm:*", "s3:*"]
        Resource = [
          "arn:aws:glue:${local.aws_region}:${local.account_id}:catalog",
          "arn:aws:glue:${local.aws_region}:${local.account_id}:database/skyroute_*",
          "arn:aws:glue:${local.aws_region}:${local.account_id}:table/skyroute_*/*",
          "arn:aws:glue:${local.aws_region}:${local.account_id}:job/skyroute-*",
          "arn:aws:athena:${local.aws_region}:${local.account_id}:workgroup/skyroute-*",
          "arn:aws:ssm:${local.aws_region}:${local.account_id}:parameter/skyroute/*",
          "arn:aws:s3:::skyroute-*-data-*/scripts/*",
        ]
      },
      {
        Sid      = "AllowSsmKmsDescribe"
        Effect   = "Allow"
        Action   = ["ssm:DescribeParameters", "kms:DescribeKey"]
        Resource = "*"
      },
      {
        # Techo: incluye kms:Decrypt (via SSM); cada rol lo concede solo sobre el HMAC.
        Sid      = "AllowKmsViaSsm"
        Effect   = "Allow"
        Action   = concat(local.apply_kms_via_ssm_actions, ["kms:Decrypt"])
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = local.kms_via_ssm_service
          }
        }
      },
      {
        # Techo: Decrypt de las variables de entorno de las funciones skyroute-*.
        Sid      = "AllowKmsViaLambda"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = { "kms:ViaService" = local.kms_via_lambda_service }
          StringLike   = { (local.kms_lambda_fn_context) = "arn:aws:lambda:${local.aws_region}:${local.account_id}:function:skyroute-*" }
        }
      },
      {
        Sid      = "AllowLogGroupsDescribe"
        Effect   = "Allow"
        Action   = "logs:DescribeLogGroups"
        Resource = local.log_groups_all_arn
      },
      {
        Sid    = "AllowWorkloadIam"
        Effect = "Allow"
        Action = concat(local.workload_role_actions, ["iam:GetPolicy", "iam:GetPolicyVersion"])
        Resource = [
          local.env_arns["dev"].workload_roles,
          local.env_arns["prod"].workload_roles,
          local.workload_boundary_dev_arn,
          local.workload_boundary_prod_arn,
        ]
      },
      {
        Sid      = "AllowPassRoleToWorkloadServices"
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = [local.env_arns["dev"].workload_roles, local.env_arns["prod"].workload_roles]
        Condition = {
          StringEquals = {
            "iam:PassedToService" = local.pass_role_services
          }
        }
      },
      {
        Sid      = "DenyOwnerIdentity"
        Effect   = "Deny"
        Action   = "iam:*"
        Resource = local.owner_identity_arns
      },
      {
        Sid      = "DenyCiAndOidcChanges"
        Effect   = "Deny"
        Action   = "iam:*"
        Resource = local.ci_protected_arns
      },
      {
        Sid      = "DenyCreateRoleWithoutBoundary"
        Effect   = "Deny"
        Action   = ["iam:CreateRole", "iam:PutRolePermissionsBoundary"]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "iam:PermissionsBoundary" = [local.workload_boundary_dev_arn, local.workload_boundary_prod_arn]
          }
        }
      },
      {
        Sid         = "DenyRoleWritesOutsideWorkload"
        Effect      = "Deny"
        Action      = local.role_write_actions
        NotResource = [local.env_arns["dev"].workload_roles, local.env_arns["prod"].workload_roles]
      },
      {
        Sid      = "DenyPassRoleWrongService"
        Effect   = "Deny"
        Action   = "iam:PassRole"
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "iam:PassedToService" = local.pass_role_services
          }
        }
      },
      {
        Sid      = "DenyDeleteBoundary"
        Effect   = "Deny"
        Action   = "iam:DeleteRolePermissionsBoundary"
        Resource = "*"
      },
      {
        Sid    = "DenyBoundaryPolicyChanges"
        Effect = "Deny"
        Action = [
          "iam:CreatePolicyVersion",
          "iam:SetDefaultPolicyVersion",
          "iam:DeletePolicy",
          "iam:DeletePolicyVersion",
        ]
        Resource = [
          local.ci_boundary_arn,
          local.workload_boundary_dev_arn,
          local.workload_boundary_prod_arn,
        ]
      },
      {
        Sid    = "DenyStateBucketProtectionChanges"
        Effect = "Deny"
        Action = [
          "s3:DeleteObjectVersion",
          "s3:PutBucketVersioning",
          "s3:PutBucketPublicAccessBlock",
          "s3:PutLifecycleConfiguration",
          "s3:PutBucketPolicy",
        ]
        Resource = [
          aws_s3_bucket.state.arn,
          "${aws_s3_bucket.state.arn}/*",
        ]
      },
      {
        Sid      = "DenyAttachRolePolicy"
        Effect   = "Deny"
        Action   = "iam:AttachRolePolicy"
        Resource = "*"
      },
      {
        Sid      = "DenyLambdaUrlAndPermission"
        Effect   = "Deny"
        Action   = ["lambda:CreateFunctionUrlConfig", "lambda:UpdateFunctionUrlConfig", "lambda:AddPermission"]
        Resource = "*"
      },
      {
        Sid      = "DenyNonEmailSnsSubscribe"
        Effect   = "Deny"
        Action   = "sns:Subscribe"
        Resource = [local.env_arns["dev"].topic, local.env_arns["prod"].topic]
        Condition = {
          StringNotEquals = {
            "sns:Protocol" = ["email"]
          }
        }
      },
      {
        Sid      = "DenyLogRead"
        Effect   = "Deny"
        Action   = ["logs:GetLogEvents", "logs:FilterLogEvents", "logs:StartQuery"]
        Resource = "*"
      },
    ]
  })
}

# ---------------------------------------------------------------- ci-plan

resource "aws_iam_role" "ci_plan" {
  name                 = "ci-plan"
  description          = "Rol de CI para terraform plan en pull_request."
  permissions_boundary = aws_iam_policy.ci_boundary.arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = "repo:javiladino@97758532/skyroute@1455233709:pull_request"
          }
        }
      },
    ]
  })
}

# Plan de PR con -lock=false (D1): sin acceso al .tflock. Solo lectura de
# metadatos para el refresh; sin GetObject de datos ni lectura de logs.
resource "aws_iam_role_policy" "ci_plan" {
  name = "ci-plan-backend"
  role = aws_iam_role.ci_plan.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "StateBucketList"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.state.arn
      },
      {
        Sid      = "StateRead"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = local.ci_plan_state_read_arns
      },
      {
        Sid    = "PlanS3Metadata"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketPolicy",
          "s3:GetBucketLocation",
          "s3:GetBucketAcl",
          "s3:GetBucketCors",
          "s3:GetBucketWebsite",
          "s3:GetBucketLogging",
          "s3:GetBucketVersioning",
          "s3:GetBucketTagging",
          "s3:GetBucketRequestPayment",
          "s3:GetAccelerateConfiguration",
          "s3:GetBucketObjectLockConfiguration",
          "s3:GetReplicationConfiguration",
          "s3:GetLifecycleConfiguration",
          "s3:GetEncryptionConfiguration",
          "s3:GetBucketPublicAccessBlock",
          "s3:GetBucketOwnershipControls",
        ]
        Resource = [
          "arn:aws:s3:::skyroute-dev-data-*",
          "arn:aws:s3:::skyroute-prod-data-*",
        ]
      },
      {
        Sid    = "PlanLambdaRead"
        Effect = "Allow"
        Action = [
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "lambda:ListVersionsByFunction",
          "lambda:GetPolicy",
          "lambda:GetFunctionCodeSigningConfig",
          "lambda:GetFunctionEventInvokeConfig",
          "lambda:GetFunctionConcurrency",
          "lambda:ListTags",
        ]
        Resource = "arn:aws:lambda:${local.aws_region}:${local.account_id}:function:skyroute-*-generator"
      },
      {
        Sid      = "PlanSchedulerRead"
        Effect   = "Allow"
        Action   = "scheduler:GetSchedule"
        Resource = [local.env_arns["dev"].schedule, local.env_arns["prod"].schedule]
      },
      {
        Sid    = "PlanIamRead"
        Effect = "Allow"
        Action = [
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
        ]
        Resource = [
          local.env_arns["dev"].workload_roles,
          local.env_arns["prod"].workload_roles,
          local.workload_boundary_dev_arn,
          local.workload_boundary_prod_arn,
        ]
      },
      {
        Sid      = "PlanLogsDescribe"
        Effect   = "Allow"
        Action   = "logs:DescribeLogGroups"
        Resource = local.log_groups_all_arn
      },
      {
        Sid      = "PlanLogsTags"
        Effect   = "Allow"
        Action   = "logs:ListTagsForResource"
        Resource = [local.env_arns["dev"].log_group, local.env_arns["prod"].log_group]
      },
      {
        Sid    = "PlanSnsRead"
        Effect = "Allow"
        Action = [
          "sns:GetTopicAttributes",
          "sns:ListTagsForResource",
          "sns:ListSubscriptionsByTopic",
          "sns:GetSubscriptionAttributes",
        ]
        Resource = [local.env_arns["dev"].topic, local.env_arns["prod"].topic]
      },
      {
        Sid      = "PlanCloudwatchRead"
        Effect   = "Allow"
        Action   = ["cloudwatch:DescribeAlarms", "cloudwatch:ListTagsForResource"]
        Resource = [local.env_arns["dev"].alarm, local.env_arns["prod"].alarm]
      },
      {
        Sid    = "PlanGlueRead"
        Effect = "Allow"
        Action = ["glue:Get*"]
        Resource = [
          local.env_arns["dev"].glue_catalog,
          local.env_arns["dev"].glue_database,
          local.env_arns["dev"].glue_table,
          local.env_arns["prod"].glue_database,
          local.env_arns["prod"].glue_table,
          local.env_arns["dev"].glue_job,
          local.env_arns["prod"].glue_job,
        ]
      },
      {
        Sid    = "PlanAthenaRead"
        Effect = "Allow"
        Action = ["athena:GetWorkGroup", "athena:ListTagsForResource"]
        Resource = [
          local.env_arns["dev"].athena_workgroup,
          local.env_arns["dev"].athena_workgroup_dbt,
          local.env_arns["prod"].athena_workgroup,
          local.env_arns["prod"].athena_workgroup_dbt,
        ]
      },
      {
        Sid      = "PlanSsmRead"
        Effect   = "Allow"
        Action   = "ssm:ListTagsForResource"
        Resource = [local.env_arns["dev"].ssm_parameter, local.env_arns["prod"].ssm_parameter]
      },
      {
        # El refresh de aws_ssm_parameter llama GetParameter con WithDecryption=true
        # aunque se use value_wo; por eso GetParameter solo sobre el HMAC exacto.
        Sid      = "PlanSsmGetHmac"
        Effect   = "Allow"
        Action   = "ssm:GetParameter"
        Resource = [local.env_arns["dev"].hmac_key, local.env_arns["prod"].hmac_key]
      },
      {
        Sid      = "PlanKmsDecryptHmac"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService"                      = local.kms_via_ssm_service
            "kms:EncryptionContext:PARAMETER_ARN" = [local.env_arns["dev"].hmac_key, local.env_arns["prod"].hmac_key]
          }
        }
      },
      {
        # El refresh de aws_lambda_function lee Environment.Variables (clave aws/lambda).
        Sid      = "PlanKmsDecryptLambdaEnv"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = { "kms:ViaService" = local.kms_via_lambda_service }
          StringLike   = { (local.kms_lambda_fn_context) = [local.env_arns["dev"].function_pattern, local.env_arns["prod"].function_pattern] }
        }
      },
      {
        # DescribeParameters no admite ARN de recurso.
        Sid      = "PlanSsmDescribe"
        Effect   = "Allow"
        Action   = "ssm:DescribeParameters"
        Resource = "*"
      },
      {
        Sid      = "PlanKmsDescribe"
        Effect   = "Allow"
        Action   = "kms:DescribeKey"
        Resource = "*"
        Condition = {
          "ForAnyValue:StringEquals" = {
            "kms:ResourceAliases" = local.kms_ssm_alias
          }
        }
      },
      {
        # Unica excepcion a la lectura de datos: los scripts de Glue (Design Decision 11).
        Sid      = "PlanScriptsRead"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectTagging"]
        Resource = local.scripts_objects_read
      },
      {
        # NotResource exime scripts/* y los dos objetos de state que ci-plan lee
        # (StateRead); el resto de rutas de datos sigue denegado.
        Sid         = "DenyDataObjectRead"
        Effect      = "Deny"
        Action      = ["s3:GetObject", "s3:GetObjectVersion"]
        NotResource = concat(local.scripts_objects_read, local.ci_plan_state_read_arns)
      },
      {
        # Logica: el Deny aplica si PARAMETER_ARN NO esta en {hmac dev, hmac prod}.
        # StringNotEquals es verdadero cuando la clave falta, asi que un Decrypt
        # directo (sin contexto de SSM) o sobre otro parametro sigue denegado; solo
        # el Decrypt del HMAC (concedido en PlanKmsDecryptHmac) escapa del Deny.
        # El StringNotLike de FunctionArn (AND) exime ademas el Decrypt de las
        # variables de entorno de las funciones skyroute-<env>-* (PlanKmsDecryptLambdaEnv).
        Sid      = "DenyKmsDecrypt"
        Effect   = "Deny"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "kms:EncryptionContext:PARAMETER_ARN" = [local.env_arns["dev"].hmac_key, local.env_arns["prod"].hmac_key]
          }
          StringNotLike = {
            (local.kms_lambda_fn_context) = [local.env_arns["dev"].function_pattern, local.env_arns["prod"].function_pattern]
          }
        }
      },
      {
        Sid      = "DenyLogRead"
        Effect   = "Deny"
        Action   = ["logs:GetLogEvents", "logs:FilterLogEvents", "logs:StartQuery"]
        Resource = "*"
      },
      {
        Sid      = "DenyOwnerIdentity"
        Effect   = "Deny"
        Action   = "iam:*"
        Resource = local.owner_identity_arns
      },
      {
        Sid      = "DenyCiAndOidcChanges"
        Effect   = "Deny"
        Action   = "iam:*"
        Resource = local.ci_protected_arns
      },
      {
        Sid      = "DenyCreateRoleWithoutBoundary"
        Effect   = "Deny"
        Action   = ["iam:CreateRole", "iam:PutRolePermissionsBoundary"]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "iam:PermissionsBoundary" = [local.workload_boundary_dev_arn, local.workload_boundary_prod_arn]
          }
        }
      },
      {
        Sid         = "DenyRoleWritesOutsideWorkload"
        Effect      = "Deny"
        Action      = local.role_write_actions
        NotResource = [local.env_arns["dev"].workload_roles, local.env_arns["prod"].workload_roles]
      },
      {
        Sid      = "DenyPassRoleWrongService"
        Effect   = "Deny"
        Action   = "iam:PassRole"
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "iam:PassedToService" = local.pass_role_services
          }
        }
      },
      {
        Sid      = "DenyDeleteBoundary"
        Effect   = "Deny"
        Action   = "iam:DeleteRolePermissionsBoundary"
        Resource = "*"
      },
      {
        Sid    = "DenyBoundaryPolicyChanges"
        Effect = "Deny"
        Action = [
          "iam:CreatePolicyVersion",
          "iam:SetDefaultPolicyVersion",
          "iam:DeletePolicy",
          "iam:DeletePolicyVersion",
        ]
        Resource = [
          local.ci_boundary_arn,
          local.workload_boundary_dev_arn,
          local.workload_boundary_prod_arn,
        ]
      },
      {
        Sid    = "DenyStateBucketProtectionChanges"
        Effect = "Deny"
        Action = [
          "s3:DeleteObjectVersion",
          "s3:PutBucketVersioning",
          "s3:PutBucketPublicAccessBlock",
          "s3:PutLifecycleConfiguration",
          "s3:PutBucketPolicy",
        ]
        Resource = [
          aws_s3_bucket.state.arn,
          "${aws_s3_bucket.state.arn}/*",
        ]
      },
    ]
  })
}
