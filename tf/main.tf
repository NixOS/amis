terraform {
  backend "s3" {
    key = "terraform.tfstate"
  }
}

provider "aws" {
  region = "eu-central-1"
}

data "terraform_remote_state" "state_backend" {
  backend = "local"
  config = {
    path = "./state-backend/terraform.tfstate"
  }
}

resource "aws_s3_bucket" "images" {
  bucket_prefix = "images"
  force_destroy = true
}

data "aws_iam_policy_document" "assume_vmimport" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["vmie.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:Externalid"
      values   = ["vmimport"]
    }
  }
}

resource "aws_iam_role" "vmimport" {
  name               = "vmimport"
  assume_role_policy = data.aws_iam_policy_document.assume_vmimport.json
}

data "aws_iam_policy_document" "vmimport" {
  statement {
    actions = ["s3:ListBucket"]
    effect  = "Allow"
    resources = [
      "${aws_s3_bucket.images.arn}"
    ]
  }

  statement {
    actions = ["s3:GetObject"]
    effect  = "Allow"
    resources = [
      "${aws_s3_bucket.images.arn}/*"
    ]
  }

  statement {
    actions = [
      "ec2:ModifySnapshotAttribute",
      "ec2:CopySnapshot",
      "ec2:RegisterImage",
      "ec2:Describe*"
    ]
    effect    = "Allow"
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "vmimport" {
  name   = "vmimport"
  role   = aws_iam_role.vmimport.id
  policy = data.aws_iam_policy_document.vmimport.json
}

output "images_bucket" {
  value = aws_s3_bucket.images.bucket
}
