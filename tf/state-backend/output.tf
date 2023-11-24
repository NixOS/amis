output "bucket_arn" {
  value = aws_s3_bucket.state.arn
}

output "region" {
  value = aws_s3_bucket.state.region
}

output "bucket" {
  value = aws_s3_bucket.state.bucket
}

output "dynamodb_table" {
  value = aws_dynamodb_table.lock.name
}
