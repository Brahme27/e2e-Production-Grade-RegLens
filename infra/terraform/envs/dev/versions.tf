terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # Remote state (enable once the bucket + lock table exist):
  # backend "s3" {
  #   bucket         = "reglens-terraform-state-<account-id>"
  #   key            = "dev/terraform.tfstate"
  #   region         = "ap-south-1"
  #   dynamodb_table = "reglens-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = local.tags # every resource is tagged for cost tracking and clean-up
  }
}
