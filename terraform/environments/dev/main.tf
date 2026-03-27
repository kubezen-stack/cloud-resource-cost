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
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
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
  count     = var.key_name == "" ? 1 : 0
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

resource "aws_secretsmanager_secret" "ssh_private_key" {
  count                   = var.key_name == "" ? 1 : 0
  name                    = "${local.hostname_tag}-ssh-private-key"
  description             = "SSH private key for ${local.hostname_tag} EC2 instances"
  recovery_window_in_days = 0

  tags = merge(
    local.common_tags,
    {
      Name = "${local.hostname_tag}-ssh-private-key"
    }
  )
}

resource "aws_secretsmanager_secret_version" "ssh_private_key" {
  count     = var.key_name == "" ? 1 : 0
  secret_id = aws_secretsmanager_secret.ssh_private_key[0].id
  secret_string = jsonencode({
    private_key = tls_private_key.deployer_key[0].private_key_pem
    key_name    = aws_key_pair.deployer_key.key_name
    environment = var.environment
  })
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

module "s3" {
  source                 = "../../modules/s3"
  project_name           = var.project_name
  environment            = var.environment
  tags                   = local.common_tags
  reports_lifecycle_days = var.environment == "prod" ? 90 : 30
  backups_lifecycle_days = var.environment == "prod" ? 90 : 14
}

module "iam" {
  source               = "../../modules/iam"
  project_name         = var.project_name
  environment          = var.environment
  s3_bucket_arns       = [module.s3.reports_bucket_arn, module.s3.backups_bucket_arn]
  enable_cloudwatch    = var.enable_cloudwatch
  enable_cost_explorer = var.enable_cost_explorer
  enable_vault_auth    = var.enable_vault_auth
  enable_ecr           = true
  ecr_repository_arns  = []

  tags = local.common_tags
}

module "ecr" {
  source       = "../../modules/ecr"
  project_name = var.project_name
  environment  = var.environment
  tags         = local.common_tags

  force_delete         = var.force_delete
  scan_on_push         = true
  image_tag_mutability = "MUTABLE"
  max_image_count      = var.ecr_max_image_count

  allow_ec2_pull = true
  ec2_role_arn   = module.iam.ec2_role_arn

  depends_on = [module.iam]
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
  iam_instance_profile = module.iam.ec2_instance_profile_name
  storage_size         = var.storage_size
  storage_type         = var.storage_type
  enable_monitoring    = var.enable_monitoring
  enable_kubernetes    = var.enable_kubernetes
  kubernetes_version   = var.kubernetes_version

  tags = local.common_tags

  depends_on = [module.vpc, module.security_groups, module.iam]
}

module "alb" {
  source                = "../../modules/alb"
  create_alb            = false
  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  public_subnet_ids     = module.vpc.public_subnet_ids
  alb_security_group_id = module.security_groups.alb_security_group_id != null ? module.security_groups.alb_security_group_id : null
  ec2_instance_ids      = module.ec2.ec2_instance_ids

  tags = local.common_tags

  depends_on = [module.vpc, module.security_groups, module.ec2]
}

module "rds" {
  source                       = "../../modules/rds"
  count                        = var.enable_rds ? 1 : 0
  project_name                 = var.project_name
  environment                  = var.environment
  vpc_id                       = module.vpc.vpc_id
  subnet_ids                   = module.vpc.private_subnet_ids
  security_group_id            = module.security_groups.rds_security_group_id
  db_instance_class            = var.db_instance_class
  db_engine                    = var.db_engine
  db_engine_version            = var.db_engine_version
  db_username                  = var.db_username
  db_name                      = var.db_name
  allocated_storage            = var.allocated_storage
  master_username              = var.master_username
  storage_type                 = var.storage_type
  multi_az                     = var.multi_az
  maintenance_window           = var.maintenance_window
  auto_minor_version_upgrade   = var.auto_minor_version_upgrade
  apply_immediately            = var.apply_immediately
  deletion_protection          = var.deletion_protection
  skip_final_snapshot          = var.skip_final_snapshot
  backup_retention_period      = var.backup_retention_period
  backup_window                = var.backup_window
  performance_insights_enabled = var.performance_insights_enabled
  monitoring_interval          = var.monitoring_interval

  tags = local.common_tags

  depends_on = [module.vpc, module.security_groups]
}