/*terraform {
  backend "s3" {
    bucket         = "cost-optimizer-terraform-state"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "cost-optimizer-terraform-locks"
    encrypt        = true
  }
}
*/