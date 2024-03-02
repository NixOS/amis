terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.37.0"
    }
  }
}

variable "sso_region" {
  type    = string
  default = "eu-north-1"
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
      values = [
        var.sso_region == "us-east-1" ?
        "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AWSAdministratorAccess_*" :
        "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/aws-reserved/sso.amazonaws.com/${var.sso_region}/AWSReservedSSO_AWSAdministratorAccess_*"
      ]
    }
  }
}

output "json" {
  value = data.aws_iam_policy_document.this.json
}