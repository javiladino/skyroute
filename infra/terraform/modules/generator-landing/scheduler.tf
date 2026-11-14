resource "aws_scheduler_schedule" "generator" {
  name                = local.function_name
  group_name          = "default"
  schedule_expression = "rate(15 minutes)"
  state               = var.schedule_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.generator.arn
    role_arn = aws_iam_role.scheduler_invoke.arn
    # Literal, no jsonencode: jsonencode escapa < y > y Scheduler no sustituiria
    # el marcador.
    input = "{\"scheduled_time\": \"<aws.scheduler.scheduled-time>\"}"

    # Unica retry_policy del modulo (Ruling Schedule).
    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 900
    }
  }
}
