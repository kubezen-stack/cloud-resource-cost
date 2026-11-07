variable "github_repository" {
  description = "The repository whose workflows may assume the roles (owner/name)"
  type        = string
  default     = "kubezen-stack/cloud-resource-cost"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "cost_alerts_trust" {
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
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "cost_alerts" {
  name                 = "cost-optimizer-github-cost-alerts"
  assume_role_policy   = data.aws_iam_policy_document.cost_alerts_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "cost_alerts" {
  statement {
    sid       = "ReadCosts"
    actions   = ["ce:GetCostAndUsage"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "cost_alerts" {
  name = "read-costs"
  role   = aws_iam_role.cost_alerts.id
  policy = data.aws_iam_policy_document.cost_alerts.json
}
