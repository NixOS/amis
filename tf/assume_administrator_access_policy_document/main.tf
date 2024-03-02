terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.37.0"
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "this" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [data.aws_caller_identity.current.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:PrincipalArn"
      values = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:assumed-role/AWSReservedSSO_AWSAdministratorAccess_*/*"]
    }
  }
}

output "json" {
  value = data.aws_iam_policy_document.this.json
}