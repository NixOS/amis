variable "repo" {
  type    = string
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "assume_AdministratorAccess" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [data.aws_caller_identity.current.arn]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:PrincipalArn"
      values   = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AdministratorAccess_*"]
    }
  }
}

data "aws_iam_policy_document" "assume_plan" {
  source_policy_documents = [data.aws_iam_policy_document.assume_AdministratorAccess.json]
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = aws_iam_openid_connect_provider.github_actions.client_id_list
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.repo}:pull_request",
        "repo:${var.repo}:ref:refs/heads/main",
        "repo:${var.repo}:environment:images",
        "repo:${var.repo}:environment:infra",
      ]
    }
  }
}

data "aws_iam_policy_document" "state" {
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
    ]
    resources = [data.terraform_remote_state.state_backend.outputs.dynamodb_table_arn]
  }
  statement {
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetObject",
      "s3:HeadObject",
    ]
    resources = [data.terraform_remote_state.state_backend.outputs.bucket_arn]

  }
}


resource "aws_iam_policy" "state" {
  name   = "state"
  policy = data.aws_iam_policy_document.state.json
}

data "aws_iam_policy_document" "assume_state" {
  source_policy_documents = [data.aws_iam_policy_document.assume_AdministratorAccess.json]
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = aws_iam_openid_connect_provider.github_actions.client_id_list
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.repo}:environment:infra",
        "repo:${var.repo}:environment:images",
        "repo:${var.repo}:ref:refs/heads/main",
        "repo:${var.repo}:pull_request",
      ]
    }
  }
}

resource "aws_iam_role" "state" {
  name                = "state"
  assume_role_policy  = data.aws_iam_policy_document.assume_state.json
  managed_policy_arns = [aws_iam_policy.state.arn]
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
  source_policy_documents = [data.aws_iam_policy_document.assume_AdministratorAccess.json]
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = aws_iam_openid_connect_provider.github_actions.client_id_list
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
  source_policy_documents = [data.aws_iam_policy_document.assume_AdministratorAccess.json]
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = aws_iam_openid_connect_provider.github_actions.client_id_list
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.repo}:environment:images"]
    }
  }
}

data "aws_iam_policy_document" "upload_ami" {
  statement {
    effect = "Allow"
    actions = [
      "s3:HeadObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.images.arn}/*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "ec2:ImportSnapshot",
      "ec2:DescribeImportSnapshotTasks",
      "ec2:DescribeSnapshots",
      "ec2:DeleteSnapshot",
      "ec2:DescribeImages",
      "ec2:RegisterImage",
      "ec2:DeregisterImage",
      "ec2:DescribeRegions",
      "ec2:CopyImage",
      "ec2:ModifyImageAttribute",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "upload_ami" {
  name   = "upload-ami"
  policy = data.aws_iam_policy_document.upload_ami.json
}

resource "aws_iam_role" "upload_ami" {
  name                = "upload-ami"
  assume_role_policy  = data.aws_iam_policy_document.assume_upload_ami.json
  managed_policy_arns = [aws_iam_policy.upload_ami.arn]
}

output "upload_ami_role_arn" {
  value = aws_iam_role.upload_ami.arn
}