terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "cost-resource-optimizer"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}

module "vpc" {
  source             = "../../modules/vpc"
  project_name       = "cost-resource-optimizer"
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  environment        = var.environment

  nat_gateway_enabled   = var.nat_gateway_enabled
  nat_gateway_single    = var.nat_gateway_single
  dns_support_enabled   = var.dns_support_enabled
  dns_hostnames_enabled = var.dns_hostnames_enabled

  tags = var.tags
}