# Roles de workload (Ruling Boundary): path /workload/, nombre skyroute-<env>-*
# y permissions_boundary = workload-boundary-<env>. Solo aws_iam_role_policy
# (inline): aws_iam_policy queda fuera porque iam:CreatePolicy esta denegado a
# CI y iam:AttachRolePolicy tambien (S11). El modulo no declara
# aws_iam_role_policy_attachment.

locals {
  workload_boundary_arn = "arn:aws:iam::${local.account_id}:policy/workload-boundary-${var.env}"
  scheduler_group_arn   = "arn:aws:scheduler:${local.region}:${local.account_id}:schedule-group/default"
}

resource "aws_iam_role" "generator_exec" {
  name                 = "${local.name_prefix}-generator-exec"
  path                 = "/workload/"
  description          = "Rol de ejecucion de la Lambda del generador de ${var.env}."
  permissions_boundary = local.workload_boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      },
    ]
  })
}

resource "aws_iam_role_policy" "generator_exec" {
  name = "generator-exec"
  role = aws_iam_role.generator_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "LandingWrite"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.data.arn}/landing/*"
      },
      {
        Sid      = "GeneratorLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.generator.arn}:*"
      },
    ]
  })
}

resource "aws_iam_role" "scheduler_invoke" {
  name                 = "${local.name_prefix}-scheduler-invoke"
  path                 = "/workload/"
  description          = "Rol con el que EventBridge Scheduler invoca la Lambda del generador de ${var.env}."
  permissions_boundary = local.workload_boundary_arn

  # PC5 / S5: aws:SourceArn es el ARN del schedule group, no el del schedule.
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "scheduler.amazonaws.com" }
        Action    = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
            "aws:SourceArn"     = local.scheduler_group_arn
          }
        }
      },
    ]
  })
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name = "scheduler-invoke"
  role = aws_iam_role.scheduler_invoke.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "InvokeGenerator"
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.generator.arn
      },
    ]
  })
}
