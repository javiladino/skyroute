variable "env" {
  description = "Entorno: dev o prod. Fija el prefijo skyroute-<env> y las bases skyroute_<env>_*."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env debe ser dev o prod."
  }
}

variable "bucket_name" {
  description = "Nombre del bucket de datos del entorno (salida bucket_name de generator-landing)."
  type        = string
}

variable "create_local_data_role" {
  description = "true crea el rol skyroute-<env>-local-data (dev); false lo omite (prod hasta el cierre de la fase)."
  type        = bool
  default     = true
}

variable "create_local_dbt_role" {
  description = "true crea el rol skyroute-<env>-local-dbt; false lo omite."
  type        = bool
  default     = true
}

variable "owner_user_name" {
  description = "Usuario IAM del owner al que confia el rol local-data (con MFA)."
  type        = string
  default     = "skyroute-dev"
}

variable "hmac_key_version" {
  description = "Version de la clave HMAC (value_wo_version). Subirla rota la clave: Terraform vuelve a escribir el parametro."
  type        = number
  default     = 1
}
