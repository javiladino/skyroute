module "generator_landing" {
  source = "../../modules/generator-landing"

  env              = "dev"
  schedule_enabled = false
  alarm_email      = var.alarm_email
}

module "lakehouse" {
  source = "../../modules/lakehouse"

  env                    = "dev"
  bucket_name            = module.generator_landing.bucket_name
  create_local_data_role = true
  create_local_dbt_role  = true

  # Temporal para el backfill de Silver de la Fase 4 (gold-dbt): sesión de 12 h.
  # Se revierte a 3600 al cerrar el backfill (ruling pendiente de registrar).
  local_data_session_seconds = 43200
}
