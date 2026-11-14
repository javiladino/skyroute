module "generator_landing" {
  source = "../../modules/generator-landing"

  env              = "prod"
  schedule_enabled = true
  alarm_email      = var.alarm_email
}
