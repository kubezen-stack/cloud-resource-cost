output "s3_bucket_name" {
  description = "The name of the S3 bucket created for bootstrapping"
  value       = aws_s3_bucket.terraform_state.id
}

output "s3_bucket_arn" {
  description = "The ARN of the S3 bucket created for bootstrapping"
  value       = aws_s3_bucket.terraform_state.arn
}

output "s3_bucket_region" {
  description = "The AWS region where the S3 bucket is created"
  value       = aws_s3_bucket.terraform_state.region
}

output "dynamodb_table_name" {
  description = "The name of the DynamoDB table created for bootstrapping"
  value       = aws_dynamodb_table.terraform_locks.name
}

output "dynamodb_table_arn" {
  description = "The ARN of the DynamoDB table created for bootstrapping"
  value       = aws_dynamodb_table.terraform_locks.arn
}

output "github_cost_alerts_role_arn" {
  description = "Role for the Cost Alerts workflow: save it as the GitHub variable AWS_COST_ALERTS_ROLE_ARN"
  value       = aws_iam_role.cost_alerts.arn
}
