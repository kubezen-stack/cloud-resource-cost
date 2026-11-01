# Security baseline

Minimum controls worth including in any recommendation.

## Network
Place application servers and databases in private subnets and expose only load balancers publicly. Security groups should allow only the needed ports from the needed sources, and administrative access should use Systems Manager Session Manager instead of open SSH.

## Identity
Use IAM roles for workloads instead of long-lived access keys, give each role least privilege, and require MFA for human users. When a service acts on a customer account, use cross-account roles with an external ID.

## Data
Encrypt data at rest with KMS (EBS, RDS, S3) and in transit with TLS. Keep secrets in AWS Secrets Manager or Parameter Store, not in code or images. Enable CloudTrail and keep logs in a separate protected bucket.
