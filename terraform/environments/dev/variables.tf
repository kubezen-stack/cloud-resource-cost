variable "environment" {
  description = "The environment for the VPC (e.g., dev, prod)"
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

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "cost-optimizer"
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

variable "security_group_ids" {
  description = "A list of security group IDs to associate with the EC2 instances"
  type        = list(string)
  default     = []
}

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

variable "key_name" {
  description = "The name of the key pair to use for EC2 instances"
  type        = string
  default     = ""
}

variable "ami_id" {
  description = "The AMI ID to use for the EC2 instances"
  type        = string
  default     = ""
}

variable "iam_instance_profile" {
  description = "The name of the IAM instance profile to attach to the EC2 instances"
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

variable "ssh_access_cidr" {
  description = "The CIDR block allowed to access EC2 instances via SSH"
  type        = list(string)
  default     = ["0.0.0.0/0"]

  validation {
    condition     = alltrue([for cidr in var.ssh_access_cidr : can(cidrhost(cidr, 0))])
    error_message = "All SSH access CIDR blocks must be valid."
  }
}

variable "ssh_key_path" {
  description = "The path to the SSH public key file"
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
  description = "Enable permissions for EC2 instances to access AWS Systems Manager Parameter Store for secure value retrieval"
  type        = bool
  default     = false
}

variable "s3_bucket_arns" {
  description = "List of S3 bucket ARNs to grant access to"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "A map of tags to assign to the VPC"
  type        = map(string)
  default     = {}
}