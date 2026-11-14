module "generator_landing" {
  source = "../../modules/generator-landing"

  env              = "prod"
  schedule_enabled = true
  alarm_email      = var.alarm_email

  # PR-T1: timeout de backfill (OQ2); PR-T2 lo vuelve a 60 al terminar el backfill
  backfill_timeout = 300
}
