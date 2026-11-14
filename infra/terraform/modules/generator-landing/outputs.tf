output "bucket_name" {
  description = "Nombre del bucket de datos del entorno."
  value       = aws_s3_bucket.data.bucket
}

output "function_name" {
  description = "Nombre de la Lambda del generador."
  value       = aws_lambda_function.generator.function_name
}

output "topic_arn" {
  description = "ARN del topic SNS de alarmas."
  value       = aws_sns_topic.alarms.arn
}
