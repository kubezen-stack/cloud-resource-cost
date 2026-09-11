terraform {
  backend "s3" {
    bucket       = "cost-optimizer-terraform-state"
    key          = "stage/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}