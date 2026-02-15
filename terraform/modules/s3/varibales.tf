variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, stage, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "stage", "prod"], var.environment)
    error_message = "Environment must be dev, stage, or prod."
  }
}

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

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}