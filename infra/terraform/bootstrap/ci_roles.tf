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
      schedule          = "arn:aws:scheduler:${local.aws_region}:${data.aws_caller_identity.current.account_id}:schedule/default/skyroute-${env}-generator"
      workload_roles    = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/workload/skyroute-${env}-*"
      log_group         = "arn:aws:logs:${local.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/skyroute-${env}-generator"
      topic             = "arn:aws:sns:${local.aws_region}:${data.aws_caller_identity.current.account_id}:skyroute-${env}-*"
      alarm             = "arn:aws:cloudwatch:${local.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:skyroute-${env}-*"
      workload_boundary = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/workload-boundary-${env}"
    }
  }

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

  pass_role_services = ["lambda.amazonaws.com", "scheduler.amazonaws.com"]

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
        Resource = [
          local.env_arns["dev"].data_bucket,
          local.env_arns["dev"].function,
          local.env_arns["dev"].schedule,
          local.env_arns["dev"].log_group,
          "${local.env_arns["dev"].log_group}:*",
          local.env_arns["dev"].topic,
          local.env_arns["dev"].alarm,
          local.env_arns["prod"].data_bucket,
          local.env_arns["prod"].function,
          local.env_arns["prod"].schedule,
          local.env_arns["prod"].log_group,
          "${local.env_arns["prod"].log_group}:*",
          local.env_arns["prod"].topic,
          local.env_arns["prod"].alarm,
        ]
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
        Sid    = "StateRead"
        Effect = "Allow"
        Action = "s3:GetObject"
        Resource = [
          "${aws_s3_bucket.state.arn}/envs/dev/terraform.tfstate",
          "${aws_s3_bucket.state.arn}/envs/prod/terraform.tfstate",
        ]
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
        Sid      = "DenyDataObjectRead"
        Effect   = "Deny"
        Action   = "s3:GetObject"
        Resource = "arn:aws:s3:::skyroute-*-data-*/*"
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
