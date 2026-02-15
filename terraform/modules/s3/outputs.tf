output "reports_bucket_name" {
  description = "Name of the S3 bucket for reports"
  value       = aws_s3_bucket.reports.bucket
}

output "reports_bucket_arn" {
  description = "ARN of the S3 bucket for reports"
  value       = aws_s3_bucket.reports.arn
}

output "backups_bucket_name" {
  description = "Name of the S3 bucket for backups"
  value       = aws_s3_bucket.backups.bucket
}

output "backups_bucket_arn" {
  description = "ARN of the S3 bucket for backups"
  value       = aws_s3_bucket.backups.arn
}

output "summary_s3" {
  description = "Summary of S3 bucket information"
  value = {
    reports = aws_s3_bucket.reports.bucket
    backups = aws_s3_bucket.backups.bucket
  }
}