variable "repo" {
  type = string
}

data "aws_iam_policy_document" "upload_ami" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
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
    ]
    resources = ["*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "ec2:DescribeImages",
      "ec2:RegisterImage",
      "ec2:DeregisterImage",
      "ec2:DescribeRegions",
      "ec2:CopyImage",
      "ec2:ModifyImageAttribute",
      "ec2:DisableImageBlockPublicAccess"
    ]
    resources = ["*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
      "ec2:GetConsoleOutput",
      "ec2:TerminateInstances",
    ]
    resources = ["*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["ec2:RunInstances"]
    resources = ["*"]
  }
  statement {
    effect = "Deny"
    actions = ["ec2:RunInstances"]
    resources = ["arn:aws:ec2:*:*:instance/*"]
    condition {
      test     = "StringNotEquals"
      variable = "ec2:InstanceType"
      values   = ["t3a.nano", "t4g.nano"]
    }
  }
}

resource "aws_iam_policy" "upload_ami" {
  name   = "upload-ami"
  policy = data.aws_iam_policy_document.upload_ami.json
}

module "assume_administrator_access" {
  source = "./assume_administrator_access_policy_document"
}

module "assume_upload_ami" {
  source = "./assume_github_actions_policy_document"
  subject_filter = [
    "repo:${var.repo}:environment:images",
    "repo:${var.repo}:environment:github-pages",
  ]
}

data "aws_iam_policy_document" "assume_upload_ami" {
  source_policy_documents = [
    module.assume_administrator_access.json,
    module.assume_upload_ami.json,
  ]
}

resource "aws_iam_role" "upload_ami" {
  name                = "upload-ami"
  assume_role_policy  = data.aws_iam_policy_document.assume_upload_ami.json
  managed_policy_arns = [aws_iam_policy.upload_ami.arn]
}

output "upload_ami_role_arn" {
  value = aws_iam_role.upload_ami.arn
}