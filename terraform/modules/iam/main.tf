locals {
  common_tags = {
    "Environment" = var.environment
    "Project"     = var.project_name
    "ManagedBy"   = "Terraform"
    "Module"      = "iam"
  }

  hostname-tag = "${var.project_name}-${var.environment}"
}

resource "aws_iam_role" "ec2_role" {
  name = "${local.hostname-tag}-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.hostname-tag}-ec2-role-${var.environment}"
    }
  )
}

resource "aws_iam_policy" "ec2_policy" {
  name = "${local.hostname-tag}-ec2-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      length(var.s3_bucket_arns) > 0 ? [
        {
          Effect = "Allow"
          Action = [
            "s3:ListBucket",
            "s3:GetObject",
            "s3:PutObject",
            "s3:DeleteObject"
          ]
          Resource = concat(var.s3_bucket_arns,
            [for arn in var.s3_bucket_arns : "${arn}/*"]
          )
        }
      ] : [],

      [
        {
          Effect = "Allow"
          Action = [
            "s3:ListAllMyBuckets",
            "s3:GetBucketLocation"
          ]
          Resource = "*"
        }
      ],

      [
        {
          Effect = "Allow"
          Action = [
            "sts:AssumeRole"
          ]
          Resource = "*"
        }
      ]
    )
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.hostname-tag}-ec2-policy-${var.environment}"
    }
  )
}

resource "aws_iam_policy" "cloudwatch_policy" {
  count       = var.enable_cloudwatch ? 1 : 0
  name        = "${local.hostname-tag}-cloudwatch-policy"
  description = "Policy for EC2 instances to send logs and metrics to CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.hostname-tag}-cloudwatch-policy-${var.environment}"
    }
  )
}

resource "aws_iam_policy" "cost_explorer_policy" {
  count       = var.enable_cost_explorer ? 1 : 0
  name        = "${local.hostname-tag}-cost-explorer-policy"
  description = "Policy for EC2 instances to access Cost Explorer API"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ce:GetCostAndUsage",
          "ce:GetCostForecast",
          "ce:GetDimensionValues",
          "ce:GetReservationUtilization",
          "ce:GetRightsizingRecommendation",
          "ce:GetSavingsPlansUtilization",
          "ce:GetSavingsPlansUtilizationDetails",
          "ce:GetTags",
          "ce:GetUsageForecast"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets",
          "s3:GetBucketLocation",
          "ec2:DescribeInstances",
          "ec2:DescribeTags",
          "ec2:DescribeVolumes",
          "ec2:DescribeVolumesModifications",
          "ec2:DescribeSnapshots",
          "ec2:DescribeRegions",
          "ec2:DescribeAvailabilityZones",
          "rds:DescribeDBInstances",
          "rds:DescribeDBClusters",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:DescribeListeners"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.hostname-tag}-cost-explorer-policy-${var.environment}"
    }
  )
}

resource "aws_iam_policy" "vault_hashicorp_policy" {
  count       = var.enable_vault_auth ? 1 : 0
  name        = "${local.hostname-tag}-vault-hashicorp-policy"
  description = "Policy for EC2 instances to access AWS Systems Manager Parameter Store"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "iam:GetInstanceProfile",
          "iam:GetRole",
          "iam:GetUser"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.hostname-tag}-vault-hashicorp-policy-${var.environment}"
    }
  )
}

resource "aws_iam_policy" "ecr_policy" {
  count       = var.enable_ecr ? 1 : 0
  name        = "${local.hostname-tag}-ecr-policy"
  description = "Policy for EC2 instances to pull images from ECR"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability",
          "ecr:DescribeRepositories",
          "ecr:ListImages",
          "ecr:DescribeImages"
        ]
        Resource = length(var.ecr_repository_arns) > 0 ? var.ecr_repository_arns : ["*"]
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${local.hostname-tag}-ecr-policy-${var.environment}"
    }
  )
}

resource "aws_iam_role_policy_attachment" "ec2_role_policy_attachment" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.ec2_policy.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch_policy_attachment" {
  count      = var.enable_cloudwatch ? 1 : 0
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.cloudwatch_policy[0].arn
}

resource "aws_iam_role_policy_attachment" "cost_explorer_policy_attachment" {
  count      = var.enable_cost_explorer ? 1 : 0
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.cost_explorer_policy[0].arn
}

resource "aws_iam_role_policy_attachment" "vault_hashicorp_policy_attachment" {
  count      = var.enable_vault_auth ? 1 : 0
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.vault_hashicorp_policy[0].arn
}

resource "aws_iam_role_policy_attachment" "ecr_policy_attachment" {
  count      = var.enable_ecr ? 1 : 0
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.ecr_policy[0].arn
}

resource "aws_iam_instance_profile" "ec2_instance_profile" {
  name = "${local.hostname-tag}-ec2-instance-profile"
  role = aws_iam_role.ec2_role.name

  tags = local.common_tags
}

data "aws_caller_identity" "current" {}