output "repository_url" {
  description = "The URL of the ECR repository"
  value       = aws_ecr_repository.main.repository_url
}

output "repository_arn" {
  description = "The ARN of the ECR repository"
  value       = aws_ecr_repository.main.arn
}

output "repository_name" {
  description = "The name of the ECR repository"
  value       = aws_ecr_repository.main.name
}

output "registry_id" {
  description = "The registry ID (AWS account ID)"
  value       = aws_ecr_repository.main.registry_id
}

output "summary_ecr" {
  description = "Summary of ECR repository"
  value = {
    repository_url  = aws_ecr_repository.main.repository_url
    repository_name = aws_ecr_repository.main.name
    registry_id     = aws_ecr_repository.main.registry_id
    push_commands = [
      "aws ecr get-login-password --region ${split(".", aws_ecr_repository.main.repository_url)[3]} | docker login --username AWS --password-stdin ${aws_ecr_repository.main.registry_id}.dkr.ecr.${split(".", aws_ecr_repository.main.repository_url)[3]}.amazonaws.com",
      "docker build -t ${aws_ecr_repository.main.repository_url}:dev .",
      "docker push ${aws_ecr_repository.main.repository_url}:dev"
    ]
  }
}
