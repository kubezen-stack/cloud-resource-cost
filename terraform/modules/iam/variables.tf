variable "environment" {
  description = "The environment for the VPC (e.g., dev, prod)"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "enable_cost_explorer" {
  description = "Enable Cost Explorer API permissions"
  type        = bool
  default     = true
}

variable "enable_cloudwatch" {
  description = "Enable CloudWatch API permissions"
  type        = bool
  default     = true
}

variable "enable_vault_auth" {
  description = "Enable permissions for EC2 instances to access AWS Systems Manager Parameter Store for secure value retrieval"
  type        = bool
  default     = true
}

variable "s3_bucket_arns" {
  description = "List of S3 bucket ARNs to grant access to EC2 instances"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "A map of tags to assign to the EC2 instances"
  type        = map(string)
  default     = {}
}