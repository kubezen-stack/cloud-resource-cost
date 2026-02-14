output "db_insance_id" {
  description = "The ID of the RDS instance."
  value       = aws_db_instance.main.id
}

output "db_endpoint" {
  description = "The connection endpoint for the RDS instance."
  value       = aws_db_instance.main.address
}

output "db_port" {
  description = "The port on which the RDS instance is listening."
  value       = aws_db_instance.main.port
}

output "db_name" {
  description = "The name of the database created in the RDS instance."
  value       = local.database-name
}

output "db_username" {
  description = "The username for the database."
  value       = var.db_username
}

output "db_url_connection_string" {
  description = "The connection string for the database (useful for application configuration)."
  value       = "postgres://${var.db_username}:${random_password.db_password.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${local.database-name}"
}

output "master_secret_name" {
    description = "The name of the Secrets Manager secret storing the database credentials."
    value       = aws_secretsmanager_secret.db_credentials.name
}

output "master_secret_arn" {
    description = "The ARN of the Secrets Manager secret storing the database credentials."
    value       = aws_secretsmanager_secret.db_credentials.arn
}

output "rds_summary" {
  description = "A summary of the RDS instance configuration for easy reference."
  value = {
    "instance_id" = aws_db_instance.main.id
    "endpoint" = aws_db_instance.main.address
    "port" = aws_db_instance.main.port
    "name" = local.database-name
    "username" = var.db_username
    "url_connection_string" = "postgres://${var.db_username}:${random_password.db_password.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${local.database-name}"
  }
}