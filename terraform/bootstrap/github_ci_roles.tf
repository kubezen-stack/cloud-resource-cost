variable "github_environments" {
  description = "Environments (Terraform root modules and GitHub Environments) that get CI roles"
  type        = list(string)
  default     = ["dev", "stage"]
}

variable "aws_region" {
  description = "Region of the application infrastructure; CI roles cannot use other regions"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix of the resource names, as in the environments"
  type        = string
  default     = "cost-optimizer"
}

data "aws_caller_identity" "current" {}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  state_bucket = aws_s3_bucket.terraform_state.id
  ci_roles = {
    for pair in setproduct(var.github_environments, ["terraform", "ansible", "deploy"]) :
    "${pair[0]}-${pair[1]}" => { environment = pair[0], kind = pair[1] }
  }
}

data "aws_iam_policy_document" "ci_trust" {
  for_each = toset(var.github_environments)

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:environment:${each.key}"]
    }
  }
}

resource "aws_iam_role" "ci" {
  for_each = local.ci_roles

  name                 = "${var.project_name}-gh-${each.key}"
  assume_role_policy   = data.aws_iam_policy_document.ci_trust[each.value.environment].json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "ci_state_read" {
  for_each = toset(var.github_environments)

  statement {
    sid       = "ListState"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.state_bucket}"]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${each.key}/*", "env:/*"]
    }
  }

  statement {
    sid       = "ReadState"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${local.state_bucket}/${each.key}/terraform.tfstate"]
  }
}

data "aws_iam_policy_document" "ansible" {
  for_each                = toset(var.github_environments)
  source_policy_documents = [data.aws_iam_policy_document.ci_state_read[each.key].json]

  statement {
    sid       = "FindMasterNode"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"]
  }

  statement {
    sid       = "ReadSshKey"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = ["arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.project_name}-${each.key}-ssh-private-key-*"]
  }

  statement {
    sid = "StoreKubeconfig"
    actions = [
      "secretsmanager:CreateSecret",
      "secretsmanager:PutSecretValue",
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue",
      "secretsmanager:TagResource",
    ]
    resources = ["arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.project_name}-${each.key}-kubeconfig-*"]
  }
}

data "aws_iam_policy_document" "deploy" {
  for_each                = toset(var.github_environments)
  source_policy_documents = [data.aws_iam_policy_document.ci_state_read[each.key].json]

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "PushImages"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = ["arn:aws:ecr:${var.aws_region}:${local.account_id}:repository/${var.project_name}-${each.key}"]
  }

  statement {
    sid       = "FindNodes"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"]
  }

  statement {
    sid     = "ReadKubeconfigAndDatabaseCredentials"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      "arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.project_name}-${each.key}-kubeconfig-*",
      "arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.project_name}-${each.key}-db-credentials-*",
    ]
  }

  statement {
    sid = "StoreArgoCdPassword"
    actions = [
      "secretsmanager:CreateSecret",
      "secretsmanager:PutSecretValue",
      "secretsmanager:TagResource",
    ]
    resources = ["arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.project_name}-${each.key}-argocd-password-*"]
  }
}

data "aws_iam_policy_document" "terraform" {
  for_each = toset(var.github_environments)

  statement {
    sid = "State"
    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["arn:aws:s3:::${local.state_bucket}/${each.key}/terraform.tfstate*"]
  }

  statement {
    sid       = "ListState"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.state_bucket}"]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${each.key}/*", "env:/*"]
    }
  }

  statement {
    sid = "Infrastructure"
    actions = [
      "cloudwatch:*",
      "ec2:*",
      "ecr:*",
      "elasticloadbalancing:*",
      "rds:*",
      "tag:GetResources",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.aws_region]
    }
  }

  statement {
    sid       = "Buckets"
    actions   = ["s3:*"]
    resources = ["arn:aws:s3:::${var.project_name}-${each.key}-*", "arn:aws:s3:::${var.project_name}-${each.key}-*/*"]
  }

  statement {
    sid       = "Secrets"
    actions   = ["secretsmanager:*"]
    resources = ["arn:aws:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.project_name}-${each.key}-*"]
  }

  statement {
    sid     = "IamOfThisEnvironment"
    actions = ["iam:*"]
    resources = [
      "arn:aws:iam::${local.account_id}:role/${var.project_name}-${each.key}-*",
      "arn:aws:iam::${local.account_id}:policy/${var.project_name}-${each.key}-*",
      "arn:aws:iam::${local.account_id}:instance-profile/${var.project_name}-${each.key}-*",
    ]
  }

  statement {
    sid       = "NoAwsManagedPolicies"
    effect    = "Deny"
    actions   = ["iam:AttachRolePolicy"]
    resources = ["*"]

    condition {
      test     = "ArnNotLike"
      variable = "iam:PolicyARN"
      values   = ["arn:aws:iam::${local.account_id}:policy/${var.project_name}-${each.key}-*"]
    }
  }

  statement {
    sid       = "ServiceLinkedRoles"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/aws-service-role/*"]

    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values   = ["elasticloadbalancing.amazonaws.com", "rds.amazonaws.com"]
    }
  }
}

locals {
  ci_policies = {
    terraform = data.aws_iam_policy_document.terraform
    ansible   = data.aws_iam_policy_document.ansible
    deploy    = data.aws_iam_policy_document.deploy
  }
}

resource "aws_iam_role_policy" "ci" {
  for_each = local.ci_roles

  name   = each.value.kind
  role   = aws_iam_role.ci[each.key].id
  policy = local.ci_policies[each.value.kind][each.value.environment].json
}
