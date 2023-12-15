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
      values = [
        "repo:${var.repo}:ref:refs/heads/main",
        "repo:${var.repo}:environment:images",
      ]
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


# TODO: Tighten rules
resource "aws_iam_role" "upload_ami" {
  name                = "upload-ami"
  assume_role_policy  = data.aws_iam_policy_document.assume_deploy.json
  managed_policy_arns = ["arn:aws:iam::aws:policy/AdministratorAccess"]
}

output "upload_ami_role_arn" {
  value = aws_iam_role.upload_ami.arn
}
