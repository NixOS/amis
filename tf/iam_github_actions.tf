locals {
  audience = "sts.amazonaws.com"
}

variable "repo" {
  type    = string
  default = "arianvp/amis"
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = [local.audience]
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]
}

data "aws_iam_policy_document" "assume_plan" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = [local.audience]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.repo}:pull_request"]
    }
  }
}

data "aws_iam_policy_document" "state" {
  statement {
    actions = [
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
    ]
    effect    = "Allow"
    resources = [data.terraform_remote_state.state_backend.outputs.dynamodb_table_arn]
  }
  statement {
    actions = [
      "s3:ListBucket",
      "s3:GetObject",
    ]
    effect    = "Allow"
    resources = [data.terraform_remote_state.state_backend.outputs.bucket_arn]

  }
}


resource "aws_iam_policy" "state" {
  name   = "state"
  policy = data.aws_iam_policy_document.state.json
}

resource "aws_iam_role" "plan" {
  name               = "plan"
  assume_role_policy = data.aws_iam_policy_document.assume_plan.json
  managed_policy_arns = [
    "arn:aws:iam::aws:policy/ReadOnlyAccess",
    aws_iam_policy.state.arn,
  ]
}

output "plan_role_arn" {
  value = aws_iam_role.plan.arn
}

data "aws_iam_policy_document" "assume_deploy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = [local.audience]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.repo}:environment:infra"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                = "deploy"
  assume_role_policy  = data.aws_iam_policy_document.assume_deploy.json
  managed_policy_arns = ["arn:aws:iam::aws:policy/AdministratorAccess"]
}

output "deploy_role_arn" {
  value = aws_iam_role.deploy.arn
}


data "aws_iam_policy_document" "assume_upload_ami" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = [local.audience]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.repo}:environment:images",
        "repo:${var.repo}:environment:amis",
      ]
    }
  }
}

# TODO: Tighten rules
resource "aws_iam_role" "upload_ami" {
  name                = "upload-ami"
  assume_role_policy  = data.aws_iam_policy_document.assume_upload_ami.json
  managed_policy_arns = ["arn:aws:iam::aws:policy/AdministratorAccess"]
}

output "upload_ami_role_arn" {
  value = aws_iam_role.upload_ami.arn
}