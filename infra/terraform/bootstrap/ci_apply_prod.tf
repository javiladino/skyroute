# Rol de CI para terraform apply del environment prod: un solo sub, solo el state
# de envs/prod/ y solo los ARN de skyroute-prod-*. Crea o adjunta solo
# workload-boundary-prod (D2).

resource "aws_iam_role" "ci_apply_prod" {
  name                 = "ci-apply-prod"
  description          = "Rol de CI para terraform apply desde el environment prod."
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
            "token.actions.githubusercontent.com:sub" = "repo:javiladino@97758532/skyroute@1455233709:environment:prod"
          }
        }
      },
    ]
  })
}

resource "aws_iam_role_policy" "ci_apply_prod" {
  name = "ci-apply-prod-backend"
  role = aws_iam_role.ci_apply_prod.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "StateBucketList"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.state.arn
        Condition = {
          StringEquals = {
            "s3:prefix" = "envs/prod/"
          }
        }
      },
      {
        Sid      = "StateReadWrite"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.state.arn}/envs/prod/terraform.tfstate"
      },
      {
        Sid      = "StateLock"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.state.arn}/envs/prod/terraform.tfstate.tflock"
      },
      {
        Sid      = "ApplyS3"
        Effect   = "Allow"
        Action   = local.apply_s3_actions
        Resource = local.env_arns["prod"].data_bucket
      },
      {
        Sid      = "ApplyLambda"
        Effect   = "Allow"
        Action   = local.apply_lambda_actions
        Resource = local.env_arns["prod"].function
      },
      {
        Sid      = "ApplyScheduler"
        Effect   = "Allow"
        Action   = local.apply_scheduler_actions
        Resource = local.env_arns["prod"].schedule
      },
      {
        Sid      = "ApplyWorkloadIam"
        Effect   = "Allow"
        Action   = local.workload_role_actions
        Resource = local.env_arns["prod"].workload_roles
      },
      {
        Sid      = "ApplyPassRoleToWorkloadServices"
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = local.env_arns["prod"].workload_roles
        Condition = {
          StringEquals = {
            "iam:PassedToService" = local.pass_role_services_generator
          }
        }
      },
      {
        # Glue solo recibe el rol skyroute-prod-glue-job.
        Sid      = "ApplyPassRoleToGlue"
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = local.env_arns["prod"].glue_job_role
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "glue.amazonaws.com"
          }
        }
      },
      {
        Sid    = "ApplyGlue"
        Effect = "Allow"
        Action = local.apply_glue_actions
        Resource = [
          local.env_arns["prod"].glue_catalog,
          local.env_arns["prod"].glue_database,
          local.env_arns["prod"].glue_table,
          local.env_arns["prod"].glue_job,
        ]
      },
      {
        Sid    = "ApplyAthena"
        Effect = "Allow"
        Action = local.apply_athena_actions
        Resource = [
          local.env_arns["prod"].athena_workgroup,
          local.env_arns["prod"].athena_workgroup_dbt,
        ]
      },
      {
        Sid      = "ApplySsm"
        Effect   = "Allow"
        Action   = local.apply_ssm_actions
        Resource = local.env_arns["prod"].ssm_parameter
      },
      {
        # DescribeParameters no admite ARN de recurso.
        Sid      = "ApplySsmDescribe"
        Effect   = "Allow"
        Action   = "ssm:DescribeParameters"
        Resource = "*"
      },
      {
        # Escribir un SecureString con aws/ssm.
        Sid      = "ApplyKmsViaSsm"
        Effect   = "Allow"
        Action   = local.apply_kms_via_ssm_actions
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = local.kms_via_ssm_service
          }
        }
      },
      {
        # El refresh de aws_ssm_parameter lee con WithDecryption=true: Decrypt solo
        # del HMAC de este entorno, via SSM.
        Sid      = "ApplyKmsDecryptHmac"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService"                      = local.kms_via_ssm_service
            "kms:EncryptionContext:PARAMETER_ARN" = local.env_arns["prod"].hmac_key
          }
        }
      },
      {
        # El refresh de aws_lambda_function lee Environment.Variables (clave aws/lambda).
        Sid      = "ApplyKmsDecryptLambdaEnv"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = { "kms:ViaService" = local.kms_via_lambda_service }
          StringLike   = { (local.kms_lambda_fn_context) = local.env_arns["prod"].function_pattern }
        }
      },
      {
        Sid      = "ApplyKmsDescribe"
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
        Sid      = "ApplyScriptsObjects"
        Effect   = "Allow"
        Action   = local.apply_scripts_actions
        Resource = local.env_arns["prod"].scripts_objects
      },
      {
        Sid      = "ApplyLogs"
        Effect   = "Allow"
        Action   = local.apply_logs_actions
        Resource = [local.env_arns["prod"].log_group, "${local.env_arns["prod"].log_group}:*"]
      },
      {
        Sid      = "ApplyLogGroupsDescribe"
        Effect   = "Allow"
        Action   = "logs:DescribeLogGroups"
        Resource = local.log_groups_all_arn
      },
      {
        Sid      = "ApplySns"
        Effect   = "Allow"
        Action   = local.apply_sns_actions
        Resource = local.env_arns["prod"].topic
      },
      {
        Sid      = "ApplyCloudwatch"
        Effect   = "Allow"
        Action   = local.apply_cloudwatch_actions
        Resource = local.env_arns["prod"].alarm
      },
      {
        # Todo Decrypt cuyo PARAMETER_ARN no sea el HMAC de prod queda denegado
        # (StringNotEquals es verdadero si la clave falta); espeja ci-plan. El
        # StringNotLike (AND) exime las variables de entorno de skyroute-prod-*.
        Sid      = "DenyKmsDecrypt"
        Effect   = "Deny"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "kms:EncryptionContext:PARAMETER_ARN" = local.env_arns["prod"].hmac_key
          }
          StringNotLike = {
            (local.kms_lambda_fn_context) = local.env_arns["prod"].function_pattern
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
            "iam:PermissionsBoundary" = local.workload_boundary_prod_arn
          }
        }
      },
      {
        Sid      = "DenyAttachCrossEnvBoundary"
        Effect   = "Deny"
        Action   = ["iam:CreateRole", "iam:PutRolePermissionsBoundary"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "iam:PermissionsBoundary" = local.workload_boundary_dev_arn
          }
        }
      },
      {
        Sid         = "DenyRoleWritesOutsideWorkload"
        Effect      = "Deny"
        Action      = local.role_write_actions
        NotResource = local.env_arns["prod"].workload_roles
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
        Resource = local.env_arns["prod"].topic
        Condition = {
          StringNotEquals = {
            "sns:Protocol" = ["email"]
          }
        }
      },
    ]
  })
}
