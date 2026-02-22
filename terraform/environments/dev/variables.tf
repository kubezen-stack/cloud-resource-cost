# ==========================================
# COMMON / GLOBAL VARIABLES
# ==========================================
variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "cost-optimizer"
}

variable "environment" {
  description = "The environment for the VPC (e.g., dev, prod, staging)"
  type        = string

  validation {
    condition     = contains(["dev", "prod", "staging"], var.environment)
    error_message = "Environment must be one of 'dev', 'prod', or 'staging'."
  }
}

variable "aws_region" {
  description = "The AWS region to deploy resources in"
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "A map of tags to assign to the resources"
  type        = map(string)
  default     = {}
}

# ==========================================
# NETWORKING (VPC, Subnets, Gateways)
# ==========================================
variable "vpc_cidr" {
  description = "The CIDR block for the VPC"
  type        = string

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid CIDR block."
  }
}

variable "availability_zones" {
  description = "A list of availability zones for the VPC"
  type        = list(string)
}

variable "dns_support_enabled" {
  description = "Enable DNS support in the VPC"
  type        = bool
  default     = true
}

variable "dns_hostnames_enabled" {
  description = "Enable DNS hostnames in the VPC"
  type        = bool
  default     = true
}

variable "nat_gateway_enabled" {
  description = "Enable NAT Gateway"
  type        = bool
  default     = false
}

variable "nat_gateway_single" {
  description = "Use a single NAT Gateway for the VPC"
  type        = bool
  default     = false
}

# ==========================================
# COMPUTE (EC2 Instances)
# ==========================================
variable "instance_type" {
  description = "The EC2 instance type"
  type        = string
  default     = "t3.small"

  validation {
    condition     = can(regex("^(t3\\.small|t3\\.medium|t3\\.large)$", var.instance_type))
    error_message = "Instance type must be one of 't3.small', 't3.medium', 't3.large'."
  }
}

variable "instance_count" {
  description = "The number of EC2 instances to launch"
  type        = number
  default     = 2

  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 10
    error_message = "Instance count must be between 1 and 10."
  }
}

variable "ami_id" {
  description = "The AMI ID to use for the EC2 instances"
  type        = string
  default     = ""
}

variable "key_name" {
  description = "The name of the key pair to use for EC2 instances"
  type        = string
  default     = ""
}

variable "storage_size" {
  description = "The size of the root EBS volume in GB"
  type        = number
  default     = 30

  validation {
    condition     = var.storage_size >= 20 && var.storage_size <= 1000
    error_message = "Storage size must be between 20 GB and 1000 GB."
  }
}

variable "storage_type" {
  description = "The type of the root EBS volume"
  type        = string
  default     = "gp3"

  validation {
    condition     = contains(["gp2", "gp3", "io2"], var.storage_type)
    error_message = "Storage type must be one of 'gp2', 'gp3', 'io2'"
  }
}

variable "enable_monitoring" {
  description = "Enable detailed monitoring for the EC2 instances"
  type        = bool
  default     = false
}

# ==========================================
# LOAD BALANCER (ALB)
# ==========================================
variable "create_alb" {
  description = "Whether to create an Application Load Balancer (ALB)"
  type        = bool
  default     = false
}

variable "public_subnet_ids" {
  description = "A list of public subnet IDs to associate with the ALB"
  type        = list(string)
  default     = []
}

# ==========================================
# DATABASE (RDS)
# ==========================================
variable "enable_rds" {
  description = "Whether to create the RDS instance"
  type        = bool
  default     = false
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

variable "db_instance_class" {
  description = "The instance class for the RDS instance."
  type        = string
  default     = "db.t3.micro"
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

variable "master_username" {
  description = "The master username for the RDS instance."
  type        = string
  default     = "vault_admin"
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

variable "maintenance_window" {
  description = "The maintenance window for the RDS instance."
  type        = string
  default     = "Mon:04:00-Mon:05:00"
}

variable "deletion_protection" {
  description = "Whether to enable deletion protection for the RDS instance."
  type        = bool
  default     = false
}

variable "skip_final_snapshot" {
  description = "Whether to skip the final snapshot before deleting the RDS instance."
  type        = bool
  default     = true
}

variable "apply_immediately" {
  description = "Whether to apply changes immediately to the RDS instance."
  type        = bool
  default     = false
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

# ==========================================
# IAM, SECURITY & PERMISSIONS
# ==========================================
variable "security_group_ids" {
  description = "A list of security group IDs to associate with resources"
  type        = list(string)
  default     = []
}

variable "ssh_access_cidr" {
  description = "The CIDR block allowed to access EC2 instances via SSH"
  type        = list(string)
  default     = ["0.0.0.0/0"]

  validation {
    condition     = alltrue([for cidr in var.ssh_access_cidr : can(cidrhost(cidr, 0))])
    error_message = "All SSH access CIDR blocks must be valid."
  }
}

variable "iam_instance_profile" {
  description = "The name of the IAM instance profile to attach to the EC2 instances"
  type        = string
  default     = ""
}

variable "enable_cost_explorer" {
  description = "Enable Cost Explorer API permissions"
  type        = bool
  default     = false
}

variable "enable_cloudwatch" {
  description = "Enable CloudWatch API permissions"
  type        = bool
  default     = true
}

variable "enable_vault_auth" {
  description = "Enable permissions for EC2 instances to access SSM Parameter Store"
  type        = bool
  default     = false
}

variable "s3_bucket_arns" {
  description = "List of S3 bucket ARNs to grant access to"
  type        = list(string)
  default     = []
}

# ==========================================
# S3 SUPPORT
# ==========================================
variable "reports_lifecycle_days" {
  description = "Days before reports are deleted"
  type        = number
  default     = 30
}

variable "backups_lifecycle_days" {
  description = "Days before backups are deleted"
  type        = number
  default     = 14
}

# ==========================================
# KUBERNETES SUPPORT (Optional)
# ==========================================
variable "enable_kubernetes" {
  description = "Enable Kubernetes support for the EC2 instances"
  type        = bool
  default     = false
}

variable "kubernetes_version" {
  description = "The Kubernetes version to install on the EC2 instances"
  type        = string
  default     = "1.21"
}