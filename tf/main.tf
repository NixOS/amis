terraform {
  backend "s3" {
    key = "terraform.tfstate"
  }
}

provider "aws" {
  region = "eu-central-1"
}

resource "aws_s3_bucket" "images" {
  bucket_prefix = "images"
  force_destroy = true
}

resource "aws_iam_role" "vmimport" {
  name               = "vmimport"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "vmie.amazonaws.com" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals":{
          "sts:Externalid": "vmimport"
        }
      }
    }
  ]
}
EOF
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