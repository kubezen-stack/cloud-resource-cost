output "alb_id" {
  description = "The ID of the Application Load Balancer"
  value       = var.create_alb ? aws_lb.alb[0].id : null
}

output "alb_arn" {
  description = "The ARN of the Application Load Balancer"
  value       = var.create_alb ? aws_lb.alb[0].arn : null
}

output "alb_dns_name" {
  description = "The DNS name of the Application Load Balancer"
  value       = var.create_alb ? aws_lb.alb[0].dns_name : null
}

output "alb_target_group_arn" {
  description = "The ARN of the ALB target group"
  value       = var.create_alb ? aws_lb_target_group.alb_target_group[0].arn : null
}

output "alb_url" {
  description = "The URL of the Application Load Balancer"
  value       = var.create_alb ? "http://${aws_lb.alb[0].dns_name}" : null
}

output "enabled_alb" {
  description = "Whether the Application Load Balancer was created"
  value       = var.create_alb
}