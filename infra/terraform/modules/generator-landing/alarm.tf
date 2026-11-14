resource "aws_sns_topic" "alarms" {
  name = "${local.name_prefix}-alarms"

  #checkov:skip=CKV_AWS_26:Sin KMS (vetado); la clave aws/sns no deja publicar a CloudWatch y el contenido es solo una alarma.
}

resource "aws_sns_topic_policy" "alarms" {
  arn = aws_sns_topic.alarms.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudWatchAlarmPublish"
        Effect    = "Allow"
        Principal = { Service = "cloudwatch.amazonaws.com" }
        Action    = "sns:Publish"
        Resource  = aws_sns_topic.alarms.arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:cloudwatch:${local.region}:${local.account_id}:alarm:${local.name_prefix}-*"
          }
        }
      },
    ]
  })
}

# Queda en PendingConfirmation hasta que el owner confirme el email.
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "invocations" {
  alarm_name          = "${local.name_prefix}-generator-invocations"
  alarm_description   = "Invocations de la Lambda del generador por encima del umbral en 1 hora."
  namespace           = "AWS/Lambda"
  metric_name         = "Invocations"
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  threshold           = var.alarm_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.generator.function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
}

# Fuente: https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html
# "Lambda reports concurrency metrics as an aggregate count of the number of instances
# processing events across an Event Function, version, alias, or AWS Region."
# La doc no limita la métrica por función a funciones con concurrencia reservada.
resource "aws_cloudwatch_metric_alarm" "concurrency" {
  alarm_name          = "${local.name_prefix}-generator-concurrency"
  alarm_description   = "ConcurrentExecutions de la Lambda del generador por encima del umbral (posible bucle o fan-out)."
  namespace           = "AWS/Lambda"
  metric_name         = "ConcurrentExecutions"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.concurrency_alarm_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.generator.function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
}
