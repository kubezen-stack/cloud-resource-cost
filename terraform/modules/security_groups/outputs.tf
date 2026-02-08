output "ec2_security_group_id" {
  description = "The ID of the security group created for EC2 instances"
  value       = aws_security_group.ec2_sg_id.id
}

output "ec2_security_group_name" {
  description = "The name of the security group created for EC2 instances"
  value       = aws_security_group.ec2_sg_id.name
}

output "arn_ec2_security_group" {
  description = "The ARN of the security group created for EC2 instances"
  value       = aws_security_group.ec2_sg_id.arn
}

output "rds_security_group_id" {
  description = "The ID of the security group created for RDS instances"
  value       = aws_security_group.rds.id
}

output "rds_security_group_name" {
   description = "Name of RDS security group"
   value = aws_security_group.rds.name
}

output "arn_rds_security_group" {
  description = "The ARN of the security group created for RDS instances"
  value       = aws_security_group.rds.arn
}

output "redis_sg_id" {
  description = "The ID of the security group created for Redis instances (only in prod environment)"
  value       = var.environment == "prod" ? aws_security_group.redis[0].id : null
}

output "alb_security_group_id" {
  description = "The ID of the security group created for ALB"
  value       = var.environment == "prod" ? aws_security_group.alb[0].id : null
}

output "security_groups" {
  description = "List of all security group IDs created"
  value = {
    ec2 = aws_security_group.ec2_sg_id.id,
    rds = aws_security_group.rds.id,
    redis = var.environment == "prod" ? aws_security_group.redis[0].id : null,
    alb = var.environment == "prod" ? aws_security_group.alb[0].id : null
  }
}