data "aws_caller_identity" "current" {}

locals {
  account_id        = data.aws_caller_identity.current.account_id
  ci_plan_role_arn  = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/ci-plan"
  ci_apply_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/ci-apply"
  ci_boundary_arn   = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/ci-boundary"
}

# Permissions boundary comun a ci-plan y ci-apply: techo de backend del state
# (solo envs/dev y envs/prod, nunca bootstrap/) y los mismos Deny que los roles.
resource "aws_iam_policy" "ci_boundary" {
  name        = "ci-boundary"
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
        Sid    = "DenyOwnerIdentity"
        Effect = "Deny"
        Action = "iam:*"
        Resource = [
          "arn:aws:iam::${local.account_id}:user/skyroute-dev",
          "arn:aws:iam::${local.account_id}:group/admins",
        ]
      },
      {
        Sid    = "DenyCiAndOidcChanges"
        Effect = "Deny"
        Action = "iam:*"
        Resource = [
          local.ci_plan_role_arn,
          local.ci_apply_role_arn,
          aws_iam_openid_connect_provider.github.arn,
        ]
      },
      {
        Sid      = "DenyCreateRoleWithoutBoundary"
        Effect   = "Deny"
        Action   = ["iam:CreateRole", "iam:PutRolePermissionsBoundary"]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "iam:PermissionsBoundary" = local.ci_boundary_arn
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
        Resource = local.ci_boundary_arn
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
        Sid    = "StateLock"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = [
          "${aws_s3_bucket.state.arn}/envs/dev/terraform.tfstate.tflock",
          "${aws_s3_bucket.state.arn}/envs/prod/terraform.tfstate.tflock",
        ]
      },
      {
        Sid    = "DenyOwnerIdentity"
        Effect = "Deny"
        Action = "iam:*"
        Resource = [
          "arn:aws:iam::${local.account_id}:user/skyroute-dev",
          "arn:aws:iam::${local.account_id}:group/admins",
        ]
      },
      {
        Sid    = "DenyCiAndOidcChanges"
        Effect = "Deny"
        Action = "iam:*"
        Resource = [
          local.ci_plan_role_arn,
          local.ci_apply_role_arn,
          aws_iam_openid_connect_provider.github.arn,
        ]
      },
      {
        Sid      = "DenyCreateRoleWithoutBoundary"
        Effect   = "Deny"
        Action   = ["iam:CreateRole", "iam:PutRolePermissionsBoundary"]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "iam:PermissionsBoundary" = local.ci_boundary_arn
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
        Resource = local.ci_boundary_arn
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

# ---------------------------------------------------------------- ci-apply

resource "aws_iam_role" "ci_apply" {
  name                 = "ci-apply"
  description          = "Rol de CI para terraform apply desde los environments dev y prod."
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
            "token.actions.githubusercontent.com:sub" = [
              "repo:javiladino@97758532/skyroute@1455233709:environment:dev",
              "repo:javiladino@97758532/skyroute@1455233709:environment:prod",
            ]
          }
        }
      },
    ]
  })
}

resource "aws_iam_role_policy" "ci_apply" {
  name = "ci-apply-backend"
  role = aws_iam_role.ci_apply.id

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
        Sid    = "StateReadWrite"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject"]
        Resource = [
          "${aws_s3_bucket.state.arn}/envs/dev/terraform.tfstate",
          "${aws_s3_bucket.state.arn}/envs/prod/terraform.tfstate",
        ]
      },
      {
        Sid    = "StateLock"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = [
          "${aws_s3_bucket.state.arn}/envs/dev/terraform.tfstate.tflock",
          "${aws_s3_bucket.state.arn}/envs/prod/terraform.tfstate.tflock",
        ]
      },
      {
        Sid    = "DenyOwnerIdentity"
        Effect = "Deny"
        Action = "iam:*"
        Resource = [
          "arn:aws:iam::${local.account_id}:user/skyroute-dev",
          "arn:aws:iam::${local.account_id}:group/admins",
        ]
      },
      {
        Sid    = "DenyCiAndOidcChanges"
        Effect = "Deny"
        Action = "iam:*"
        Resource = [
          local.ci_plan_role_arn,
          local.ci_apply_role_arn,
          aws_iam_openid_connect_provider.github.arn,
        ]
      },
      {
        Sid      = "DenyCreateRoleWithoutBoundary"
        Effect   = "Deny"
        Action   = ["iam:CreateRole", "iam:PutRolePermissionsBoundary"]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "iam:PermissionsBoundary" = local.ci_boundary_arn
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
        Resource = local.ci_boundary_arn
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
