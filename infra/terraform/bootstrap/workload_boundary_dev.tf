# Permissions boundary de los roles de workload de dev (path /workload/, prefijo
# skyroute-dev-). Sin acceso al bucket de state (Deny explicito).
resource "aws_iam_policy" "workload_boundary_dev" {
  name        = "workload-boundary-dev"
  description = "Permissions boundary de los roles de workload de dev."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowLandingWrite"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${local.env_arns["dev"].data_bucket}/landing/*"
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
