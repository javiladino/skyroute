module "generator_landing" {
  source = "../../modules/generator-landing"

  env              = "dev"
  schedule_enabled = false
  alarm_email      = var.alarm_email
}
