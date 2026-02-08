variable "environment" {
  description = "The environment for the VPC (e.g., dev, prod)"
  type        = string
}

variable "vpc_id" {
  description = "The ID of the VPC where the security group will be created"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "cost-optimizer"
}

variable "ssh_access_cidr" {
  description = "List of CIDR blocks allowed for SSH access"
  type        = list(string)
  default     = ["0.0.0.0/0"]

  validation {
    condition    = alltrue([for cidr in var.ssh_access_cidr : can(cidrhost(cidr, 0))])
    error_message = "At least one CIDR block must be specified for SSH access."
  }
}

variable "tags" {
  description = "A map of tags to assign to the security group"
  type        = map(string)
  default     = {}
}