# One-time: the S3 bucket that stores Terraform state for every other folder.
# Run with local state:  terraform init && terraform apply
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.aws_account_id] # refuses to run against any other account
  default_tags { tags = { Project = "peoplepulse", Owner = var.owner, ManagedBy = "terraform" } }
}

variable "region" {
  type    = string
  default = "us-west-1"
}

variable "aws_account_id" {
  description = "The only AWS account this code may touch"
  type        = string
  default     = "866934333672"
}

variable "owner" {
  description = "Owner tag on every resource: lets Cost Explorer and Budgets show the cost you generated"
  type        = string
  default     = "Saket.Saurabh@techconsulting.net"
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "state" {
  bucket = "peoplepulse-tfstate-${data.aws_caller_identity.current.account_id}"
  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# Old state versions are kept 90 days (enough to recover from a mistake), then deleted
resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    id     = "expire-old-state-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 90 }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "state_bucket" {
  value = aws_s3_bucket.state.bucket
}
