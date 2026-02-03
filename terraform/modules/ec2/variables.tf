variable "environment" {
  description = "The environment for the VPC (e.g., dev, prod)"
  type        = string
}

variable "vpc_id" {
  description = "The ID of the VPC where EC2 instances will be launched"
  type        = string
}

variable "subnet_ids" {
  description = "The subnet ID where EC2 instances will be launched"
  type        = string
}

variable "security_group_ids" {
  description = "A list of security group IDs to associate with the EC2 instances"
  type        = list(string)
  default     = []
}

variable "instance_type" {
  description = "The EC2 instance type"
  type        = string
  default     = "t3.medium"

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
    error_message = "Storage type must be one of 'gp2', 'gp3', 'io2'."
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
  default     = true
}

variable "kubernetes_version" {
  description = "The Kubernetes version to install on the EC2 instances"
  type        = string
  default     = "1.21"
}

variable "project_name" {
  description = "The name of the project for tagging purposes"
  type        = string
}

variable "tags" {
  description = "A map of tags to assign to the EC2 instances"
  type        = map(string)
  default     = {}
}