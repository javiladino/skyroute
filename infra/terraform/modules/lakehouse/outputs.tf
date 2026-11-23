output "database_names" {
  description = "Nombres de las bases Glue por capa."
  value       = { for layer, db in aws_glue_catalog_database.layer : layer => db.name }
}

output "workgroup_name" {
  description = "Nombre del workgroup de Athena."
  value       = aws_athena_workgroup.this.name
}

output "dbt_workgroup_name" {
  description = "Nombre del workgroup de Athena de dbt (skyroute-<env>-dbt)."
  value       = aws_athena_workgroup.dbt.name
}

output "glue_job_role_arn" {
  description = "ARN del rol skyroute-<env>-glue-job."
  value       = aws_iam_role.glue_job.arn
}

output "glue_job_names" {
  description = "Nombres de los Glue jobs de demo (se lanzan a mano)."
  value       = sort([for job in aws_glue_job.this : job.name])
}

output "local_data_role_arn" {
  description = "ARN del rol skyroute-<env>-local-data; null si no se crea."
  value       = one(aws_iam_role.local_data[*].arn)
}

output "local_dbt_role_arn" {
  description = "ARN del rol skyroute-<env>-local-dbt; null si no se crea."
  value       = one(aws_iam_role.local_dbt[*].arn)
}

output "hmac_parameter_name" {
  description = "Nombre del parametro SSM con la clave HMAC."
  value       = aws_ssm_parameter.hmac_email_key.name
}
