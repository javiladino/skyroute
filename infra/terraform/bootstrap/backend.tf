terraform {
  backend "s3" {
    bucket       = "skyroute-tfstate-437266392155-eu-west-3"
    key          = "bootstrap/terraform.tfstate"
    region       = "eu-west-3"
    use_lockfile = true
    encrypt      = true
  }
}
