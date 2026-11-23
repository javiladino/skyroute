module "generator_landing" {
  source = "../../modules/generator-landing"

  env              = "prod"
  schedule_enabled = true
  alarm_email      = var.alarm_email
}

module "lakehouse" {
  source = "../../modules/lakehouse"

  env         = "prod"
  bucket_name = module.generator_landing.bucket_name

  # Ruling "Plan decisions": en prod el rol local-data no se crea hasta el cierre
  # de la fase (las fases 4-8 leen dev).
  create_local_data_role = false

  # Ruling "Prod": la infraestructura de dbt existe en los dos entornos.
  create_local_dbt_role = true
}
