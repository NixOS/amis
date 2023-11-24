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