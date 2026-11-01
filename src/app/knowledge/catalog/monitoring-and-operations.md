# Monitoring and operations

What a production setup needs in order to be run safely.

## Metrics and alarms
Use CloudWatch metrics and alarms on the signals users feel: load balancer 5xx rate and target response time, instance or container CPU, database CPU, free storage and connections, queue age, and the number of healthy targets. Send alarms to an SNS topic that reaches the on-call person.

## Logs and tracing
Ship application and load balancer logs to CloudWatch Logs or S3 with a retention period, because logs without retention grow silently. Add distributed tracing such as AWS X-Ray or OpenTelemetry when several services call each other.

## Backups and recovery
Define a recovery point objective and a recovery time objective. Automated RDS backups, S3 versioning and AWS Backup cover most needs; copy critical backups to another region when the objective requires it. A backup that has never been restored is not a backup.

## Delivery and change
Use infrastructure as code such as Terraform, deploy through a pipeline, and keep production changes reviewed. Budgets and cost anomaly alerts catch surprises early.
