terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.37.0"
    }
  }
}

variable "repo" {
  type = string
}

data "aws_caller_identity" "current" {
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]
}

import {
  id = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
  to = aws_iam_openid_connect_provider.github_actions
}

resource "aws_s3_bucket" "state" {
  bucket_prefix = "tf-state"
  force_destroy = true
}

resource "aws_dynamodb_table" "lock" {
  name         = "tf-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  attribute {
    name = "LockID"
    type = "S"
  }
}

module "assume_administrator_access" {
  providers = { aws = aws }
  source    = "../assume_administrator_access_policy_document"
}

module "assume_gha_plan" {
  providers  = { aws = aws }
  source     = "../assume_github_actions_policy_document"
  depends_on = [aws_iam_openid_connect_provider.github_actions]
  subject_filter = [
    "repo:${var.repo}:pull_request",
    "repo:${var.repo}:ref:refs/heads/main",
    "repo:${var.repo}:environment:images",
    "repo:${var.repo}:environment:infra",
  ]
}

data "aws_iam_policy_document" "assume_plan" {
  source_policy_documents = [
    module.assume_administrator_access.json,
    module.assume_gha_plan.json,
  ]
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
    resources = [aws_dynamodb_table.lock.arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.state.arn]

  }
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.state.arn}/*"]

  }
}

data "aws_iam_policy_document" "write_state" {
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.state.arn}/*"]
  }
}

resource "aws_iam_policy" "write_state" {
  name   = "write-state"
  policy = data.aws_iam_policy_document.write_state.json
}

import {
  id = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/write-state"
  to = aws_iam_policy.write_state
}

resource "aws_iam_policy" "state" {
  name   = "state"
  policy = data.aws_iam_policy_document.state.json
}

import {
  id = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/state"
  to = aws_iam_policy.state
}

module "assume_gha_state" {
  providers  = { aws = aws }
  source     = "../assume_github_actions_policy_document"
  depends_on = [aws_iam_openid_connect_provider.github_actions]
  subject_filter = [
    "repo:${var.repo}:environment:infra",
    "repo:${var.repo}:environment:images",
    "repo:${var.repo}:ref:refs/heads/main",
    "repo:${var.repo}:pull_request",
  ]
}

data "aws_iam_policy_document" "assume_state" {
  source_policy_documents = [
    module.assume_administrator_access.json,
    module.assume_gha_state.json,
  ]
}


resource "aws_iam_role" "state" {
  name                = "state"
  assume_role_policy  = data.aws_iam_policy_document.assume_state.json
  managed_policy_arns = [aws_iam_policy.state.arn]
}

import {
  id = "state"
  to = aws_iam_role.state
}

resource "aws_iam_role" "plan" {
  name               = "plan"
  assume_role_policy = data.aws_iam_policy_document.assume_plan.json
  managed_policy_arns = [
    "arn:aws:iam::aws:policy/ReadOnlyAccess",
    aws_iam_policy.state.arn,
    aws_iam_policy.write_state.arn,
  ]
}

import {
  id = "plan"
  to = aws_iam_role.plan
}

output "plan_role_arn" {
  value = aws_iam_role.plan.arn
}

module "assume_gha_deploy" {
  providers      = { aws = aws }
  source         = "../assume_github_actions_policy_document"
  depends_on     = [aws_iam_openid_connect_provider.github_actions]
  subject_filter = ["repo:${var.repo}:environment:infra"]
}

data "aws_iam_policy_document" "assume_deploy" {
  source_policy_documents = [
    module.assume_administrator_access.json,
    module.assume_gha_deploy.json,
  ]
}

resource "aws_iam_role" "deploy" {
  name                = "deploy"
  assume_role_policy  = data.aws_iam_policy_document.assume_deploy.json
  managed_policy_arns = ["arn:aws:iam::aws:policy/AdministratorAccess"]
}

import {
  id = "deploy"
  to = aws_iam_role.deploy
}

output "deploy_role_arn" {
  value = aws_iam_role.deploy.arn
}
