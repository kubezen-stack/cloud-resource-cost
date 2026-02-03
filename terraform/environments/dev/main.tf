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

resource "tls_private_key" "deployer_key" {
  count = var.key_name == "" ? 1 : 0

  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "deployer_key" {
  key_name   = var.key_name != "" ? var.key_name : "${local.hostname_tag}-key"
  public_key = var.key_name != "" ? "" : tls_private_key.deployer_key[0].public_key_openssh

  tags = merge(
    common_tags,
    {
      Name = "${local.hostname_tag}-key"
    }
  )
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

module "ec2" {
  source               = "../../modules/ec2"
  project_name         = "cost-resource-optimizer"
  environment          = var.environment
  ami_id               = var.ami_id
  instance_type        = var.instance_type
  subnet_ids           = var.nat_gateway_enabled ? module.vpc.private_subnet_ids : module.vpc.public_subnet_ids
  security_group_ids   = [module.security_group.ec2_sg_id]
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