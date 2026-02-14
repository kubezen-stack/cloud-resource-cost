locals {
  common_tags = merge(
    var.tags,
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Module      = "rds"
    }
  )
  
  hostname-tag = "${var.project_name}-${var.environment}"
  database-name = replace("${var.db_name}_${var.environment}", "-", "_")
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnet-group"
  description = "Subnet group for RDS instance in ${var.environment} environment"
  subnet_ids = var.subnet_ids

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-db-subnet-group"
    }
  )
}

resource "random_password" "db_password" {
  length  = 16
  special = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_db_instance" "main" {
  # --- General Configuration ---
  identifier        = "${var.project_name}-${var.environment}-db-instance"
  allocated_storage = 50
  storage_type      = var.storage_type
  engine            = var.db_engine
  engine_version    = var.db_engine_version
  instance_class    = var.db_instance_class
  db_name  = local.database-name 
  username = var.db_username
  password = random_password.db_password.result

  # --- Network & Security ---
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = var.publicly_accessible
  storage_encrypted      = var.storage_encrypted

  # --- High Availability & Maintenance ---
  multi_az               = var.multi_az
  parameter_group_name   = aws_db_parameter_group.main.name
  maintenance_window     = var.maintenance_window
  auto_minor_version_upgrade = var.auto_minor_version_upgrade
  apply_immediately      = var.apply_immediately   

  # --- Backup & Termination Protection ---
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.project_name}-${var.environment}-db-final-snapshot"
  backup_retention_period   = var.backup_retention_period
  backup_window             = var.backup_window

  # --- Monitoring & Logging ---
  performance_insights_enabled    = var.performance_insights_enabled
  monitoring_interval             = var.monitoring_interval
  enabled_cloudwatch_logs_exports = var.enabled_cloudwatch_logs

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-db-instance"
    }
  )

  lifecycle {
    ignore_changes = [
      password,
      final_snapshot_identifier
    ]
  }

  depends_on = [aws_db_parameter_group.main]
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.project_name}-${var.environment}-db-credentials"
  description = "Secret for RDS database credentials in ${var.environment} environment"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-db-credentials"
    }
  )
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id     = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db_password.result
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    dbname   = local.database-name
    vault_connection_url = "postgres://${var.db_username}:${random_password.db_password.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${local.database-name}"
  })
}

resource "aws_db_parameter_group" "main" {
  name        = "${var.project_name}-${var.environment}-db-parameter-group"
  family      = "${var.db_engine}${var.db_engine_version}"
  description = "Parameter group for RDS instance in ${var.environment} environment"

  parameter {
    name = "rds.force_ssl"
    value = var.environment == "prod" ? "1" : "0"
    apply_method = "immediate"
  }

  parameter {
    name = "max_connections"
    value = var.environment == "prod" ? "200" : "50"
    apply_method = "pending-reboot"
  }

  parameter {
    name = "log_min_duration_statement"
    value = var.environment == "prod" ? "1000" : "0"
    apply_method = "immediate"
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.project_name}-${var.environment}-db-parameter-group"
    }
  )
}