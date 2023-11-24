terraform {
  backend "s3" {
    key = "terraform.tfstate"
  }
}

provider "aws" {
  region = "eu-central-1"
}