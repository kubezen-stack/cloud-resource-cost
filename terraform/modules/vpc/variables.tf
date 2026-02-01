variable "environment" {
  description = "The environment for the VPC (e.g., dev, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "prod", "staging"], var.environment)
    error_message = "Environment must be one of 'dev', 'prod', or 'staging'."
  }
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
    default     = true
}

variable "nat_gateway_single" {
    description = "Use a single NAT Gateway for the VPC"
    type        = bool
    default     = true
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

variable "tags" {
    description = "A map of tags to assign to the VPC"
    type        = map(string)
    default     = {}
}