# State backend bootstrap

This creates an S3 bucket for state storage and a DynamoDB table for locking.
We commit the `terraform.tfstate` on purpose. It does not contain anything sensitive.
