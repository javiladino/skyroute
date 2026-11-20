terraform {
  required_version = ">= 1.11.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
    # random_password efimero: disponible desde hashicorp/random 3.7.0.
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}
