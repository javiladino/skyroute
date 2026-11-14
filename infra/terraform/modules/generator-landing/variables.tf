variable "env" {
  description = "Entorno: dev o prod. Fija el prefijo skyroute-<env>- de todos los recursos."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env debe ser dev o prod."
  }
}

variable "schedule_enabled" {
  description = "true deja el schedule en ENABLED (prod); false en DISABLED (dev)."
  type        = bool
}

variable "alarm_email" {
  description = "Email que recibe la alarma de Invocations por SNS. Sin default: no se versiona."
  type        = string
  sensitive   = true
}

variable "architecture" {
  description = "Arquitectura de la Lambda: arm64 o x86_64 (salida si arm64 falla en eu-west-3)."
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["arm64", "x86_64"], var.architecture)
    error_message = "architecture debe ser arm64 o x86_64."
  }
}

variable "backfill_timeout" {
  description = "Timeout de la Lambda en segundos. 60 en régimen normal; la ventana de backfill la fija la PR de la Fase 10."
  type        = number
  default     = 60
}

variable "alarm_threshold" {
  description = "Umbral de Invocations por hora de la alarma (OQ3)."
  type        = number
  default     = 120
}

variable "concurrency_alarm_threshold" {
  description = "Umbral de ConcurrentExecutions (máximo en 5 min) de la alarma de concurrencia."
  type        = number
  default     = 2
}
