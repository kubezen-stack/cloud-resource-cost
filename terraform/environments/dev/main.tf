locals {
  common_tags = merge(
    var.tags,
    {
      Project     = var.project_name
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  )

  hostname_tag = "${var.project_name}-${var.environment}"
}

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
    tags = local.common_tags
  }
}

resource "tls_private_key" "deployer_key" {
  count = var.key_name == "" ? 1 : 0

  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "deployer_key" {
  key_name   = "${local.hostname_tag}-key"
  public_key = tls_private_key.deployer_key[0].public_key_openssh

  tags = merge(
    local.common_tags,
    {
      Name = "${local.hostname_tag}-key"
    }
  )
}

resource "local_sensitive_file" "private_key" {
  count           = var.key_name == "" ? 1 : 0
  filename        = "${path.module}/../../../ssh/${aws_key_pair.deployer_key.key_name}.pem"
  content         = tls_private_key.deployer_key[0].private_key_pem
  file_permission = "0600"
}

module "vpc" {
  source             = "../../modules/vpc"
  project_name       = var.project_name
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  environment        = var.environment

  nat_gateway_enabled   = var.nat_gateway_enabled
  nat_gateway_single    = var.nat_gateway_single
  dns_support_enabled   = var.dns_support_enabled
  dns_hostnames_enabled = var.dns_hostnames_enabled

  tags = local.common_tags
}

module "security_groups" {
  source       = "../../modules/security_groups"
  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.vpc.vpc_id
  tags         = local.common_tags

  depends_on = [module.vpc]
}

module "iam" {
  source               = "../../modules/iam"
  project_name         = var.project_name
  environment          = var.environment
  s3_bucket_arns       = []
  enable_cloudwatch    = var.enable_cloudwatch
  enable_cost_explorer = var.enable_cost_explorer
  enable_vault_auth    = var.enable_vault_auth

  tags = local.common_tags
}

module "ec2" {
  source               = "../../modules/ec2"
  project_name         = var.project_name
  environment          = var.environment
  vpc_id               = module.vpc.vpc_id
  ami_id               = var.ami_id
  instance_type        = var.instance_type
  subnet_ids           = var.nat_gateway_enabled ? module.vpc.private_subnet_ids : module.vpc.public_subnet_ids
  security_group_ids   = [module.security_groups.ec2_security_group_id]
  key_name             = aws_key_pair.deployer_key.key_name
  iam_instance_profile = var.iam_instance_profile
  storage_size         = var.storage_size
  storage_type         = var.storage_type
  enable_monitoring    = var.enable_monitoring
  enable_kubernetes    = var.enable_kubernetes
  kubernetes_version   = var.kubernetes_version

  tags = local.common_tags

  depends_on = [module.vpc, module.security_groups, module.iam]
}