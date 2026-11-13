variable "budget_email" {
  description = "Email que recibe los avisos del budget. El valor real va solo en terraform.tfvars (gitignored)."
  type        = string
  sensitive   = true
}

variable "state_bucket_name" {
  description = "Nombre del bucket de state remoto (eu-west-3). Debe coincidir con el literal de los backends."
  type        = string
  default     = "skyroute-tfstate-437266392155-eu-west-3"
}
