variable "environment" {
  description = "The environment for the VPC (e.g., dev, prod)"
  type        = string
}

variable "project_name" {
  description = "The name of the project"
  type        = string
}

variable "name_alb" {
  description = "The name of the Application Load Balancer"
  type        = string
  default     = "alb"
}

variable "create_alb" {
  description = "Whether to create the Application Load Balancer"
  type        = bool
  default     = true
}

variable "listener_port" {
  description = "The port on which the ALB listener will listen"
  type        = number
  default     = 80
}

variable "vpc_id" {
  description = "The ID of the VPC where EC2 instances will be launched"
  type        = string
  default     = ""
}

variable "alb_security_group_id" {
  description = "Security group ID for ALB"
  type        = string
  default     = ""
}

variable "ec2_instance_ids" {
  description = "A list of EC2 instance IDs to register with the ALB"
  type        = list(string)
  default     = []
}

variable "public_subnet_ids" {
  description = "A list of public subnet IDs to associate with the ALB"
  type        = list(string)
  default     = []
}

variable "load_balancer_type" {
  description = "The type of load balancer (application, network, classic)"
  type        = string
  default     = "application"
}

variable "internal" {
  description = "Whether the load balancer is internal or internet-facing"
  type        = bool
  default     = true
}

variable "enable_deletion_protection" {
  description = "Whether to enable deletion protection for the ALB"
  type        = bool
  default     = false
}

variable "target_group_port" {
  description = "The port on which the target group will receive traffic"
  type        = number
  default     = 30080
}

variable "health_check_path" {
  description = "The path for the health check"
  type        = string
  default     = "/health"
}

variable "certificate_arn" {
  description = "The ARN of the SSL certificate for HTTPS listener (optional)"
  type        = string
  default     = ""
}

variable "access_logs_bucket" {
  description = "The name of the S3 bucket for ALB access logs"
  type        = string
  default     = ""
}

variable "tags" {
  description = "A map of tags to assign to the security group"
  type        = map(string)
  default     = {}
}