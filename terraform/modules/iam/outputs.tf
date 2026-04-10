output "ec2_role_arn" {
  description = "The ARN of the EC2 role"
  value       = aws_iam_role.ec2_role.arn
}

output "ec2_role_name" {
  description = "The name of the EC2 role"
  value       = aws_iam_role.ec2_role.name
}

output "ec2_policy_arn" {
  description = "The ARN of the EC2 policy"
  value       = aws_iam_policy.ec2_policy.arn
}

output "ec2_policy_name" {
  description = "The name of the EC2 policy"
  value       = aws_iam_policy.ec2_policy.name
}

output "ec2_instance_profile_name" {
  description = "The name of the EC2 instance profile"
  value       = aws_iam_instance_profile.ec2_instance_profile.name
}

output "s3_bucket_arns" {
  description = "The ARNs of the S3 buckets"
  value       = var.s3_bucket_arns
}

output "cloudwatch_policy_arn" {
  description = "The ARN of the CloudWatch policy"
  value       = var.enable_cloudwatch ? aws_iam_policy.cloudwatch_policy[0].arn : null
}

output "cloudwatch_policy_name" {
  description = "The name of the CloudWatch policy"
  value       = var.enable_cloudwatch ? aws_iam_policy.cloudwatch_policy[0].name : null
}

output "cost_explorer_policy_arn" {
  description = "The ARN of the Cost Explorer policy"
  value       = var.enable_cost_explorer ? aws_iam_policy.cost_explorer_policy[0].arn : null
}

output "cost_explorer_policy_name" {
  description = "The name of the Cost Explorer policy"
  value       = var.enable_cost_explorer ? aws_iam_policy.cost_explorer_policy[0].name : null
}

output "ecr_policy_arn" {
  description = "The ARN of the ECR policy"
  value       = var.enable_ecr ? aws_iam_policy.ecr_policy[0].arn : null
}

output "ecr_policy_name" {
  description = "The name of the ECR policy"
  value       = var.enable_ecr ? aws_iam_policy.ecr_policy[0].name : null
}

output "aws_account_id" {
  description = "The AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "summary_iam" {
  description = "Summary of IAM resources created"
  value = {
    iam_role_arn       = aws_iam_role.ec2_role.arn
    instance_profile   = aws_iam_instance_profile.ec2_instance_profile.name
    aws_account_id     = data.aws_caller_identity.current.account_id
    vault_auth_enabled = var.enable_vault_auth
    ecr_enabled        = var.enable_ecr
    policies_attached = (
      1 +
      (var.enable_cloudwatch ? 1 : 0) +
      (var.enable_cost_explorer ? 1 : 0) +
      (var.enable_vault_auth ? 1 : 0) +
      (var.enable_ecr ? 1 : 0)
    )
  }
}