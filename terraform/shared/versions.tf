terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
  # bucket is passed at init:  terraform init -backend-config="bucket=<state bucket>"
  backend "s3" {
    key          = "shared/terraform.tfstate"
    region       = "us-west-1"
    use_lockfile = true
    encrypt      = true
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.aws_account_id] # refuses to run against any other account
  default_tags { tags = { Project = "peoplepulse", Owner = var.owner, ManagedBy = "terraform" } }
}
