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

output "images_bucket" {
  value = aws_s3_bucket.images.bucket
}