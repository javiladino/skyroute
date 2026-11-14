variable "alarm_email" {
  description = "Email de la alarma de Invocations. Llega por TF_VAR_alarm_email desde la variable de repositorio ALARM_EMAIL."
  type        = string
  sensitive   = true
}
