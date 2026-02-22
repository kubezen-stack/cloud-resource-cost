variable "project_name" {
  description = "The name of the project."
  type        = string
}

variable "environment" {
  description = "The environment (e.g., dev, staging, prod)."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of 'dev', 'staging', or 'prod'."
  }
}

variable "enable_rds" {
  description = "Whether to create the RDS instance."
  type        = bool
  default     = true
}

variable "vpc_id" {
  description = "The ID of the VPC where the RDS instance will be deployed."
  type        = string
}

variable "subnet_ids" {
  description = "A list of subnet IDs for the RDS instance."
  type        = list(string)
}

variable "security_group_id" {
  description = "The security group ID for the RDS instance."
  type        = string
}

variable "db_instance_class" {
  description = "The instance class for the RDS instance."
  type        = string
  default     = "db.t3.micro"
}

variable "db_engine" {
  description = "The database engine to use for the RDS instance."
  type        = string
  default     = "postgres"
}

variable "db_engine_version" {
  description = "The version of the database engine."
  type        = string
  default     = "15"
}

variable "db_name" {
  description = "The name of the database to create."
  type        = string
  default     = "cost-optimizer"
}

variable "db_username" {
  description = "The username for the database."
  type        = string
  default     = "app_user"
}

variable "allocated_storage" {
  description = "The allocated storage in gigabytes for the RDS instance."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "The maximum allocated storage in gigabytes for the RDS instance."
  type        = number
  default     = 100
}

variable "storage_encrypted" {
  description = "Whether to enable encryption for the RDS instance."
  type        = bool
  default     = true
}

variable "storage_type" {
  description = "The storage type for the RDS instance."
  type        = string
  default     = "gp3"
}

variable "backup_retention_period" {
  description = "The number of days to retain backups for the RDS instance."
  type        = number
  default     = 3
}

variable "backup_window" {
  description = "The daily time range during which automated backups are created."
  type        = string
  default     = "03:00-04:00"
}

variable "multi_az" {
  description = "Whether to create a Multi-AZ RDS instance."
  type        = bool
  default     = false
}

variable "publicly_accessible" {
  description = "Whether the RDS instance should be publicly accessible."
  type        = bool
  default     = false
}

variable "skip_final_snapshot" {
  description = "Whether to skip the final snapshot before deleting the RDS instance."
  type        = bool
  default     = true
}

variable "deletion_protection" {
  description = "Whether to enable deletion protection for the RDS instance."
  type        = bool
  default     = false
}

variable "apply_immediately" {
  description = "Whether to apply changes immediately to the RDS instance."
  type        = bool
  default     = false
}

variable "maintenance_window" {
  description = "The maintenance window for the RDS instance."
  type        = string
  default     = "Mon:04:00-Mon:05:00"
}

variable "auto_minor_version_upgrade" {
  description = "Whether to enable automatic minor version upgrades for the RDS instance."
  type        = bool
  default     = true
}

variable "performance_insights_enabled" {
  description = "Whether to enable Performance Insights for the RDS instance."
  type        = bool
  default     = false
}

variable "monitoring_interval" {
  description = "The interval in seconds for enhanced monitoring of the RDS instance (0 to disable)."
  type        = number
  default     = 0
}

variable "enabled_cloudwatch_logs" {
  description = "A list of log types to enable for export to CloudWatch Logs."
  type        = list(string)
  default     = ["postgresql"]
}

variable "master_username" {
  description = "The master username for the RDS instance."
  type        = string
  default     = "vault_admin"
}

variable "tags" {
  description = "A map of tags to assign to the RDS instance."
  type        = map(string)
  default     = {}
}