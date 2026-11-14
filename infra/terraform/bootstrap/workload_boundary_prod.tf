# Permissions boundary de los roles de workload de prod (path /workload/, prefijo
# skyroute-prod-). Sin acceso al bucket de state (Deny explicito).
resource "aws_iam_policy" "workload_boundary_prod" {
  name        = "workload-boundary-prod"
  description = "Permissions boundary de los roles de workload de prod."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowLandingWrite"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${local.env_arns["prod"].data_bucket}/landing/*"
      },
      {
        Sid      = "AllowGeneratorLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${local.env_arns["prod"].log_group}:*"
      },
      {
        Sid      = "AllowGeneratorInvoke"
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = local.env_arns["prod"].function
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
