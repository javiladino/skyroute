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
}
