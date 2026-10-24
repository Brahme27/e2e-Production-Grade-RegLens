# GitHub Actions -> AWS without long-lived access keys (OpenID Connect).
# Only workflows on the main branch of one repository can assume this role.
variable "github_repository" {
  type        = string
  description = "owner/repo"
}

variable "ecr_repository_arns" { type = list(string) }

variable "ecs_cluster_arn" {
  type        = string
  description = "CI may roll out new task definitions to services in this cluster only"
}

variable "pass_role_arns" {
  type        = list(string)
  description = "Task / execution roles CI may hand to ECS when registering task definitions"
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  tags           = var.tags
}

data "aws_iam_policy_document" "trust" {
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

resource "aws_iam_role" "ci" {
  name               = "reglens-github-actions"
  assume_role_policy = data.aws_iam_policy_document.trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "push_images" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage",
    ]
    resources = var.ecr_repository_arns
  }
}

resource "aws_iam_role_policy" "push_images" {
  name   = "push-images"
  role   = aws_iam_role.ci.id
  policy = data.aws_iam_policy_document.push_images.json
}

data "aws_iam_policy_document" "deploy" {
  statement {
    actions   = ["ecs:RegisterTaskDefinition", "ecs:DescribeTaskDefinition"]
    resources = ["*"] # these ECS actions do not support resource-level permissions
  }
  statement {
    actions   = ["ecs:UpdateService", "ecs:DescribeServices", "ecs:RunTask"]
    resources = ["*"]
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [var.ecs_cluster_arn]
    }
  }
  statement {
    actions   = ["iam:PassRole"]
    resources = var.pass_role_arns
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy-ecs"
  role   = aws_iam_role.ci.id
  policy = data.aws_iam_policy_document.deploy.json
}

output "role_arn" { value = aws_iam_role.ci.arn }
